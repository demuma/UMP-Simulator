#include "PublicationCoordinator.hpp"
#include "AggregationManager.hpp"
#include <iostream>
#include <map>
#include <stdexcept>

namespace {
using namespace ump;
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected rejection");
}
AggregationConfig settings() {
    AggregationConfig c{"run", "sensor", "app", {0,0,80,80,3},100,400};
    c.history = HistoryLimits{4000,64,10000,1000000,32};
    return c;
}
MetricEvaluator policy(double age = 1000) {
    return MetricEvaluator(MetricPolicy{"p","1",{{MetricId::DistinctContributors,2,{}},
        {MetricId::AgeAtEvaluationMs,{},age}}});
}
struct Fixture {
    AggregationConfig config = settings();
    std::vector<AggregationCandidate> windows;
    AggregationManager manager{config,[&](const auto& c){windows.push_back(c);}};
    SpatialSelector selector{config,{1,128}};
    SpatialSelection period(int start, int count = 2) {
        std::vector<CellObservation> observations;
        for (int cell = 192; cell < 196; ++cell)
            for (int n=0;n<count;++n)
                observations.push_back({std::to_string(cell)+":"+std::to_string(n),"pedestrian",
                    historyCell(config.coverage,cell,3)});
        for (int time=start ? start : 100;time<start+400;time+=100)
            manager.ingest({config.runId,config.sensorId,static_cast<std::uint64_t>(time/100),time,
                ObservationStatus::Measured,observations});
        manager.advance(start+400);
        return selector.select(windows.back(),*manager.history(),policy());
    }
};
void retryAndFutureHandover() {
    Fixture f; auto children=f.period(0);
    PublicationCoordinator coordinator(f.config,policy());
    const auto sealed=coordinator.seal(children,400);
    require(sealed->cells.size()==4,"Expected fine approved road-user cells");
    auto parent=children;
    parent.candidate=*f.manager.history()->query(historyCell(f.config.coverage,48,2),0,400).candidate;
    parent.decisions={{48,true,"test",{}}};
    rejects([&]{coordinator.seal(parent,400);});
    auto future=f.period(400,1);
    rejects([&]{coordinator.seal(future,800);});
    require(coordinator.state().reservedEndMs==400,"Pending support was reopened");
    // Model an ambiguous write: the external sink stores the payload, then loses its ack.
    std::map<std::string,std::uint64_t> stored;
    const auto value=sealed->cells[0].aggregate.counts.observationContributions;
    children.candidate.cells[0].counts.observationContributions=999;
    rejects([&]{coordinator.deliver(400,[&](const auto& release)->SinkResult {
        require(release.cells[0].aggregate.counts.observationContributions==value,"Sealed payload mutated");
        stored.emplace(release.releaseId,value); throw std::runtime_error("ack lost");
    });});
    require(coordinator.pendingRelease()==sealed,"Retry changed immutable payload");
    require(!coordinator.deliver(400,[](const auto&){return SinkResult::Retry;}),"Retry treated as ack");
    require(coordinator.deliver(400,[&](const auto& release){
        require(stored.at(release.releaseId)==value,"Retry changed stable release ID or content");
        rejects([&]{coordinator.deliver(400,[](const auto&){return SinkResult::Acknowledged;});});
        return SinkResult::Acknowledged;
    }),"Acknowledgement did not commit");
    require(stored.size()==1 && !coordinator.pendingRelease() && coordinator.state().retiredThroughMs==400,
        "Commit did not retire the interval");
    rejects([&]{coordinator.seal(parent,400);}); // No subtraction through historical ancestors.
    auto merged=coordinator.seal(future,800);
    require(merged->cells.size()==1 && merged->cells[0].aggregate.cell.depth==2,
        "Future common-boundary merge was not allowed");
    coordinator.deliver(800,[](const auto&){return SinkResult::Acknowledged;});
    auto later=f.period(800,2);
    require(coordinator.seal(later,1200)->cells.size()==4,"Future split was not allowed");
}
void suppressionAndSubtraction() {
    Fixture f; auto selection=f.period(0);
    selection.decisions[0].selected=false;
    const auto hidden=selection.candidate.cells[0].counts.observationContributions;
    const auto total=selection.candidate.counts.observationContributions;
    std::uint64_t visible=0;
    for(std::size_t i=1;i<selection.candidate.cells.size();++i)
        visible+=selection.candidate.cells[i].counts.observationContributions;
    require(total-visible==hidden && hidden>0,"Additive-count subtraction counterexample missing");
    PublicationCoordinator coordinator(f.config,policy());
    auto release=coordinator.seal(selection,400);
    require(release->cells.size()==3,"Suppressed cell reached recipient payload");
    for(const auto& cell:release->cells) require(cell.aggregate.cell.id!=192,"Hidden footprint leaked");
    coordinator.deliver(400,[](const auto&){return SinkResult::Acknowledged;});
    auto empty=f.period(400,0);
    coordinator.seal(empty,800);
    int calls=0;
    coordinator.deliver(800,[&](const auto&){++calls;return SinkResult::Acknowledged;});
    require(calls==0 && coordinator.state().retiredThroughMs==800,"Empty window emitted a record or stalled");

    Fixture suppressed; auto failed=suppressed.period(0);
    for(auto& decision:failed.decisions) decision.selected=false;
    PublicationCoordinator all(suppressed.config,policy());
    require(all.seal(failed,400)->cells.empty(),"Fully suppressed cut has public cells");
    all.deliver(400,[&](const auto&){++calls;return SinkResult::Acknowledged;});
    require(calls==0 && all.state().retiredThroughMs==400,"Suppression did not retire privately");
}
void validationAndDeadlines() {
    Fixture f; auto selection=f.period(0);
    PublicationCoordinator late(f.config,policy(450));
    auto release=late.seal(selection,400);
    rejects([&]{late.deliver(451,[](const auto&){return SinkResult::Acknowledged;});});
    require(late.pendingRelease()==release && late.state().retiredThroughMs==0,"Expiry reopened support");
    rejects([&]{late.deliver(400,[](const auto&){return SinkResult::Acknowledged;});});
    PublicationCoordinator noPolicy(f.config,MetricEvaluator{});
    rejects([&]{noPolicy.seal(selection,400);});
    PublicationCoordinator small(f.config,policy(),{1,100,1000});
    rejects([&]{small.seal(selection,400);});
    PublicationCoordinator bytes(f.config,policy(),{64,100,1});
    rejects([&]{bytes.seal(selection,400);});
    PublicationCoordinator coordinator(f.config,policy());
    auto invalid=selection;invalid.candidate.cells[0].cell.x+=1;
    rejects([&]{coordinator.seal(invalid,400);});
    invalid=selection;invalid.decisions[0].cellId=193;
    rejects([&]{coordinator.seal(invalid,400);});
    invalid=selection;invalid.candidate.cells[0].cell=historyCell(f.config.coverage,48,2);
    invalid.decisions[0].cellId=48;
    rejects([&]{coordinator.seal(invalid,400);});
    invalid=selection;invalid.candidate.applicationId="another";
    rejects([&]{coordinator.seal(invalid,400);});
    invalid=selection;invalid.candidate.unavailableSamples=1;--invalid.candidate.measuredSamples;
    invalid.candidate.coverage=WindowCoverage::Incomplete;
    rejects([&]{coordinator.seal(invalid,400);});
    require(!coordinator.pendingRelease(),"Rejected seal mutated ledger");
    auto truncated=selection;
    truncated.candidate.endMs=350;truncated.candidate.truncated=true;
    PublicationCoordinator terminal(f.config,policy());
    terminal.seal(truncated,400);
    terminal.deliver(400,[](const auto&){return SinkResult::Acknowledged;});
    auto beyond=selection;beyond.candidate.startMs=350;beyond.candidate.endMs=750;
    beyond.candidate.closedAtMs=750;
    rejects([&]{terminal.seal(beyond,750);});
    coordinator.seal(selection,400);
    rejects([&]{coordinator.deliver(399,[](const auto&){return SinkResult::Acknowledged;});});
}
}
int main() {
    try { retryAndFutureHandover();suppressionAndSubtraction();validationAndDeadlines();
        std::cout<<"Publication regression tests passed\n";return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
