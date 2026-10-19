#include "PublicationCoordinator.hpp"
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
using namespace ump;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected rejection");
}
void ledgerGeometryChronologyAndCompaction() {
    const GridCoverage grid{0,0,80,80,6};
    const auto c = [&](int id, int depth) { return historyCell(grid,id,depth); };
    require(4*4*4*4*4*4 == 4096 && c(12288,6).width == 1.25,
        "Depth-six finest-grid geometry changed");
    CellWindowLedger ledger(grid);
    require(ledger.nodeCount()==4 && ledger.minimumRetiredThrough()==0,
        "Ledger eagerly allocated finest cells");
    ledger.retire(c(192,3),0,200);
    require(ledger.nodeCount()==12 && ledger.retiredThrough(c(192,3))==200
        && ledger.retiredThrough(c(193,3))==0 && !ledger.retiredThrough(c(48,2)),
        "A child retirement moved its sibling clock or hid a mixed subtree");
    require(!ledger.canRetire(c(192,3),0,400) && !ledger.canRetire(c(48,2),0,400)
        && !ledger.canRetire(c(48,2),200,400), "Overlap or unmatched parent frontier was accepted");
    rejects([&]{ledger.retire(c(48,2),0,400);});
    for (int id=193;id<196;++id) ledger.retire(c(id,3),0,200);
    require(ledger.retiredThrough(c(48,2))==200 && ledger.nodeCount()==8,
        "Equal child frontiers were not coalesced");
    ledger.retire(c(48,2),200,400);
    for (int id=49;id<52;++id) ledger.retire(c(id,2),0,400);
    require(ledger.retiredThrough(c(12,1))==400 && ledger.nodeCount()==4,
        "Mixed-depth child retirement failed to compact into the root");
    for (int id=13;id<16;++id) ledger.retire(c(id,1),0,400);
    require(ledger.minimumRetiredThrough()==400 && ledger.nodeCount()==4,
        "Global frontier was not the minimum over all covered cells");
    auto invalid=c(192,3); invalid.x+=1;
    rejects([&]{ledger.canRetire(invalid,400,600);});
    rejects([&]{ledger.retire(c(192,3),400,400);});
    require(ledger.nodeCount()==4 && ledger.minimumRetiredThrough()==400,
        "Rejected geometry/interval changed the ledger");
}
void ledgerResourceFailureIsAtomic() {
    const GridCoverage grid{0,0,80,80,6};
    CellWindowLedger ledger(grid,11);
    rejects([&]{ledger.retire(historyCell(grid,192,3),0,200);});
    require(ledger.nodeCount()==4 && ledger.retiredThrough(historyCell(grid,12,1))==0,
        "Node budget rejection partially split the ledger");
    ledger.retire(historyCell(grid,48,2),0,200);
    require(ledger.nodeCount()==8 && ledger.retiredThrough(historyCell(grid,48,2))==200,
        "A smaller legal retirement failed after budget rejection");
    rejects([&]{CellWindowLedger invalid(grid,3);});
}
void allFinestClocksAndImmutableLedgerSnapshots() {
    const GridCoverage grid{0,0,80,80,6};
    CellWindowLedger ledger(grid,5460);
    for(int id=12288;id<16384;++id)
        ledger.retire(historyCell(grid,id,6),0,static_cast<AggregationTime>(id-12287)*100);
    require(ledger.nodeCount()==5460 && ledger.minimumRetiredThrough()==100,
        "All 4096 independent clocks exceeded or undercounted the complete depth-six frontier");
    const auto before=ledger;
    for(int id=12288;id<16384;++id) {
        const auto cell=historyCell(grid,id,6);
        const auto start=*ledger.retiredThrough(cell);
        ledger.retire(cell,start,500000);
    }
    require(ledger.nodeCount()==4 && ledger.minimumRetiredThrough()==500000,
        "4096 clocks failed to compact after a common handoff");
    require(before.nodeCount()==5460 && before.minimumRetiredThrough()==100
        && before.retiredThrough(historyCell(grid,16383,6))==409600,
        "Path-copy retirement mutated an immutable publication snapshot");
}
AggregationConfig settings() {
    AggregationConfig config{"run","sensor","app",{0,0,80,80,3},100,200};
    return config;
}
MetricEvaluator policy() {
    return MetricEvaluator(MetricPolicy{"p","1",{{MetricId::DistinctContributors,2,{}},
        {MetricId::AgeAtEvaluationMs,{},10000}}});
}
struct Fixture {
    AggregationConfig config=settings();
    AggregationHistory history{config,{2000,32,10000,1000000,128}};
    Fixture() {
        std::vector<CellObservation> observations;
        for(int id=192;id<256;++id)
            for(int n=0;n<2;++n) observations.push_back({std::to_string(id)+":"+std::to_string(n),
                "pedestrian",historyCell(config.coverage,id,3)});
        for(int time=100;time<=900;time+=100)
            history.append({config.runId,config.sensorId,static_cast<std::uint64_t>(time/100),
                time,ObservationStatus::Measured,observations});
    }
    SpatialSelection selection(int id,int depth,int start,int end) {
        const auto scope=historyCell(config.coverage,id,depth);
        SpatialSelection result{};
        result.candidate=*history.query(scope,start,end).candidate;
        result.decisions={{id,true,"test",{}}};
        result.minDepth=1;
        result.coordinationCell=scope;
        return result;
    }
};
void scopedClocksAndImmutableRetries() {
    Fixture f;
    PublicationCoordinator coordinator(f.config,policy(),{},800,true);
    auto a=f.selection(192,3,0,200), b=f.selection(193,3,0,400);
    const auto release=coordinator.seal(a,900);
    require(release->coordinationCell && release->coordinationCell->id==192
        && release->releaseId.find("ump-release-v2/")==0,
        "Scoped publication omitted its coordination identity");
    const auto original=release->cells.front().aggregate.counts.observationContributions;
    a.candidate.cells.front().counts.observationContributions=999;
    rejects([&]{coordinator.seal(b,900);});
    require(!coordinator.deliver(900,[](const auto&){return SinkResult::Retry;}),
        "Retry retired scoped support");
    require(coordinator.pendingRelease()==release && coordinator.state().retiredThroughMs==0,
        "Retry replaced the immutable reservation or advanced the frontier");
    rejects([&]{coordinator.deliver(900,[&](const auto& value)->SinkResult {
        require(value.cells.front().aggregate.counts.observationContributions==original,
            "Caller mutation changed the sealed scoped payload");
        throw std::runtime_error("Acknowledgement lost");
    });});
    coordinator.deliver(900,[](const auto&){return SinkResult::Acknowledged;});
    auto adjacent=coordinator.seal(b,900);
    require(adjacent->startMs==0 && adjacent->endMs==400 && adjacent->releaseId!=release->releaseId,
        "Adjacent cell could not use its independent window");
    coordinator.deliver(900,[](const auto&){return SinkResult::Acknowledged;});
    rejects([&]{coordinator.seal(f.selection(48,2,0,400),900);});
    coordinator.seal(f.selection(192,3,200,400),900);
    coordinator.deliver(900,[](const auto&){return SinkResult::Acknowledged;});
    for(int id=194;id<196;++id) {
        coordinator.seal(f.selection(id,3,0,400),900);
        coordinator.deliver(900,[](const auto&){return SinkResult::Acknowledged;});
    }
    auto parent=coordinator.seal(f.selection(48,2,400,600),900);
    require(parent->coordinationCell->id==48,"Aligned child frontiers could not hand over to their parent");
    coordinator.deliver(900,[](const auto&){return SinkResult::Acknowledged;});
    coordinator.seal(f.selection(192,3,600,800),900);
    coordinator.deliver(900,[](const auto&){return SinkResult::Acknowledged;});
}
void scopedValidationSuppressionAndFinalWindows() {
    Fixture f;
    PublicationCoordinator coordinator(f.config,policy(),{},800,true);
    auto wrong=f.selection(192,3,0,200);
    wrong.coordinationCell=historyCell(f.config.coverage,193,3);
    rejects([&]{coordinator.seal(wrong,900);});
    wrong=f.selection(192,3,0,200);wrong.coordinationCell->width+=1;
    rejects([&]{coordinator.seal(wrong,900);});
    wrong=f.selection(192,3,0,200);wrong.coordinationCell.reset();
    rejects([&]{coordinator.seal(wrong,900);});
    PublicationCoordinator baseline(f.config,policy());
    rejects([&]{baseline.seal(f.selection(192,3,0,200),900);});
    auto legacy=f.selection(192,3,0,200);legacy.coordinationCell.reset();
    require(baseline.seal(legacy,900)->releaseId.find("ump-release-v1/")==0,
        "Existing whole-grid release IDs changed");
    auto hidden=f.selection(192,3,0,200);hidden.decisions.front().selected=false;
    coordinator.seal(hidden,900);
    int publicCalls=0;
    coordinator.deliver(900,[&](const auto&){++publicCalls;return SinkResult::Acknowledged;});
    require(publicCalls==0,"Suppressed scoped domain emitted a revealing empty release");
    auto final=f.selection(193,3,0,350);final.candidate.truncated=true;
    coordinator.seal(final,900);
    coordinator.deliver(900,[](const auto&){return SinkResult::Acknowledged;});
    coordinator.seal(f.selection(194,3,0,400),900);
    coordinator.deliver(900,[](const auto&){return SinkResult::Acknowledged;});
    require(coordinator.state().retiredThroughMs==0,"One scoped final window ended the whole stream");
    PublicationLimits tiny; tiny.maxCoordinationNodes=11;
    PublicationCoordinator bounded(f.config,policy(),tiny,800,true);
    rejects([&]{bounded.seal(f.selection(192,3,0,200),900);});
    require(!bounded.pendingRelease() && bounded.state().retiredThroughMs==0,
        "Publication ledger budget failure left a partial reservation");
    bounded.seal(f.selection(48,2,0,200),900);
}
}
int main() {
    try {
        ledgerGeometryChronologyAndCompaction();ledgerResourceFailureIsAtomic();
        allFinestClocksAndImmutableLedgerSnapshots();
        scopedClocksAndImmutableRetries();scopedValidationSuppressionAndFinalWindows();
        std::cout<<"Scoped publication regression tests passed\n";return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
