#include "AdaptiveAggregation.hpp"
#include "AggregationManager.hpp"
#include "CellLocalAggregation.hpp"
#include "PolicyTree.hpp"
#include "PublicationCoordinator.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ump;
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected an explicit rejection");
}
AggregationConfig settings(int depth = 2) {
    AggregationConfig c{"a07-run", "sensor", "app", {0,0,80,80,depth}, 100, 400};
    c.history = HistoryLimits{4000,64,10000,1000000,128};
    return c;
}
MetricEvaluator policy(double support = 2, double maxSide = 20) {
    return MetricEvaluator(MetricPolicy{"a07-policy","1", {
        {MetricId::DistinctContributors,support,{}}, {MetricId::CellSideM,{},maxSide}}});
}
CellObservation observation(const AggregationConfig& c, const std::string& id, int cell) {
    return {id,"pedestrian",historyCell(c.coverage,cell,c.coverage.leafDepth)};
}
bool contains(const CellGeometry& outer, const CellGeometry& inner) {
    return inner.x >= outer.x && inner.y >= outer.y
        && inner.x + inner.width <= outer.x + outer.width
        && inner.y + inner.height <= outer.y + outer.height;
}
bool overlaps(const CellGeometry& a, const CellGeometry& b) {
    return std::max(a.x,b.x) < std::min(a.x+a.width,b.x+b.width)
        && std::max(a.y,b.y) < std::min(a.y+a.height,b.y+b.height);
}
struct Fixture {
    AggregationConfig config;
    std::vector<AggregationCandidate> windows;
    std::vector<ObservationBatch> raw;
    AggregationManager manager;
    explicit Fixture(int depth = 2)
        : config(settings(depth)), manager(config,[this](const auto& c) { windows.push_back(c); }) {}
    void sample(int time, std::vector<CellObservation> data,
        ObservationStatus status = ObservationStatus::Measured) {
        ObservationBatch batch{config.runId,config.sensorId,static_cast<std::uint64_t>(time/100),
            time,status,std::move(data)};
        raw.push_back(batch); manager.ingest(batch);
    }
    CellObservation roadUser(const std::string& id,int cell) const {
        return observation(config,id,cell);
    }
    void period(int start,const std::vector<CellObservation>& data) {
        for (int time = start ? start : 100; time < start+400; time += 100) sample(time,data);
        manager.advance(start+400);
    }
};
std::vector<int> selectedIds(const SpatialSelection& output) {
    std::vector<int> ids;
    for (const auto& decision : output.decisions) if (decision.selected) ids.push_back(decision.cellId);
    return ids;
}
std::uint64_t selectedContributions(const SpatialSelection& output) {
    std::uint64_t total = 0;
    for (std::size_t i=0;i<output.decisions.size();++i)
        if (output.decisions[i].selected) total += output.candidate.cells[i].counts.observationContributions;
    return total;
}
// Independent rectangle/time/identity scan: never use production ancestor queries
// or production candidate counts as the expected evidence.
void audit(const SpatialSelection& output,const std::vector<ObservationBatch>& raw) {
    const auto& candidate=output.candidate;
    require(candidate.cells.size()==output.decisions.size(),"Cut/decision alignment failed");
    std::uint64_t input=0,total=0,measured=0,unavailable=0,expected=0;
    std::set<std::string> identities;
    for (AggregationTime time=100;time<candidate.endMs;time+=100)
        if (time>=candidate.startMs) ++expected;
    for (const auto& batch : raw) if (batch.observedAtMs>=candidate.startMs && batch.observedAtMs<candidate.endMs) {
        if (batch.status==ObservationStatus::Unavailable) { ++unavailable; continue; }
        ++measured;
        for (const auto& item : batch.observations) {
            ++input; identities.insert(item.contributorId);
            std::size_t owners=0;
            for (const auto& cell : candidate.cells) if (contains(cell.cell,item.cell)) ++owners;
            require(owners==1,"A source contribution is missing or appears in overlapping final footprints");
        }
    }
    require(candidate.expectedSamples==expected && candidate.measuredSamples==measured
        && candidate.unavailableSamples==unavailable && candidate.missingSamples==expected-measured-unavailable,
        "Coverage differs from raw scheduled samples");
    require(candidate.counts.observationContributions==input
        && candidate.counts.distinctContributors==identities.size(),"Global raw support changed during rescue");
    std::size_t selected=0,suppressed=0;
    for (std::size_t i=0;i<candidate.cells.size();++i) {
        const auto& cell=candidate.cells[i];
        require(output.decisions[i].cellId==cell.cell.id,"Decision refers to another footprint");
        for (std::size_t j=0;j<i;++j)
            require(!overlaps(cell.cell,candidate.cells[j].cell),"Final parent/descendant footprints overlap");
        std::uint64_t contributions=0;
        std::set<std::string> members;
        for (const auto& batch : raw) if (batch.status==ObservationStatus::Measured
            && batch.observedAtMs>=candidate.startMs && batch.observedAtMs<candidate.endMs)
            for (const auto& item : batch.observations) if (contains(cell.cell,item.cell)) {
                ++contributions; members.insert(item.contributorId);
            }
        require(cell.counts.observationContributions==contributions
            && cell.counts.distinctContributors==members.size(),"A rescued cell has altered or summed identity support");
        if (measured) require(cell.counts.meanSampleOccupancy.has_value()
            && std::abs(*cell.counts.meanSampleOccupancy-static_cast<double>(contributions)/measured)<1e-12,
            "A rescued cell changed its sample-mean denominator");
        total+=contributions;
        if (output.decisions[i].selected) ++selected; else ++suppressed;
    }
    require(total==input && selected==output.selectedCells && suppressed==output.suppressedCells,
        "Selected/suppressed conservation or decision counters failed");
}

void simplePartialAndBaseline() {
    Fixture f;
    f.period(0,{f.roadUser("a",48),f.roadUser("b",48),f.roadUser("c",49)});
    SpatialSelector baseline(f.config,{1,64});
    auto old=baseline.select(f.windows[0],*f.manager.history(),policy());
    require(old.selectedCells==0 && old.suppressedCells==1,"Default whole-subtree baseline changed");
    audit(old,f.raw);
    SpatialSelector selective(f.config,{1,64,true});
    auto result=selective.select(f.windows[0],*f.manager.history(),policy());
    require(selectedIds(result)==std::vector<int>{48} && selectedContributions(result)==6
        && result.suppressedCells==1 && result.candidate.counts.observationContributions==9,
        "The hand-worked 9-input/6-retained case failed");
    require(result.candidate.cells.size()==2 && result.candidate.cells[1].cell.id==49,
        "The partial cut did not preserve the actual suppressed sibling footprint");
    require(std::any_of(result.attempts.begin(),result.attempts.end(),[](const auto& attempt) {
        return attempt.cell.cell.id==12 && attempt.assessment.status==AssessmentStatus::Fail;
    }),"Failed parent assessment disappeared from private provenance");
    audit(result,f.raw);
    SpatialSelector legalParent(f.config,{1,64,true});
    auto all=legalParent.select(f.windows[0],*f.manager.history(),policy(2,40));
    require(selectedIds(all)==std::vector<int>{12} && selectedContributions(all)==9 && all.suppressedCells==0,
        "Partial fallback prevented an eligible parent from retaining all original support");
    audit(all,f.raw);
}

void commonWindowOptionRejectedByLocalApi() {
    const auto config=settings();
    TemporalAdaptationConfig temporal{AdaptationStrategy::SpatialFirst,100,800,16};
    temporal.coordination=CoordinationMode::CellLocal;
    const auto sink=[](const SpatialSelection&) {};
    CellLocalAggregation baseline(config,temporal,{1,64,false},policy(),sink);
    require(baseline.windows().size()==4,"Valid local baseline did not construct its four-owner frontier");
    rejects([&] {
        CellLocalAggregation unsupported(config,temporal,{1,64,true},policy(),sink);
    });
}

void regionalThresholdRescue() {
    Fixture f;
    std::vector<CellObservation> data{f.roadUser("a",48)};
    for (int id=49;id<=51;++id) for (int n=0;n<2;++n)
        data.push_back(f.roadUser(std::to_string(id)+":"+std::to_string(n),id));
    f.period(0,data);
    auto tree=std::make_shared<const PolicyTree>(PolicyTreeConfig{"regional","1","app",f.config.coverage,
        {{MetricId::DistinctContributors,2,{}},{MetricId::CellSideM,{},40}}},
        std::vector<PolicyRegion>{{"strict","entrance",0,0,20,20,{},{{MetricId::DistinctContributors,10,{}}}}});
    SpatialSelector selector(f.config,{1,64,true});
    auto result=selector.select(f.windows[0],*f.manager.history(),MetricEvaluator(tree));
    require(selectedIds(result)==std::vector<int>({49,50,51}) && selectedContributions(result)==18
        && result.candidate.counts.observationContributions==21 && result.suppressedCells==1,
        "Regional 10/2/2/2 requirements did not preserve 18 of 21 contributions");
    audit(result,f.raw);
}

void internalDescendantAndFutureRefinement() {
    Fixture f(3);
    SpatialSelector selector(f.config,{1,64,true});
    f.period(0,{f.roadUser("a",192),f.roadUser("b",193),f.roadUser("c",196)});
    auto first=selector.select(f.windows[0],*f.manager.history(),policy());
    require(selectedIds(first)==std::vector<int>{48} && selectedContributions(first)==6
        && first.suppressedCells==1,"Fallback lost a passing internal descendant whose own leaves fail");
    audit(first,f.raw);
    f.period(400,{f.roadUser("a",192),f.roadUser("d",192),f.roadUser("b",193),
        f.roadUser("e",193),f.roadUser("c",196)});
    auto second=selector.select(f.windows.back(),*f.manager.history(),policy());
    require(selectedIds(second)==std::vector<int>({192,193}) && second.refinedCells==2
        && second.candidate.startMs==400 && second.candidate.endMs==800
        && selectedContributions(second)==16,"A rescued internal cut could not refine in a future disjoint interval");
    audit(second,f.raw);
    rejects([&] { selector.select(f.windows.back(),*f.manager.history(),policy()); });
}

void insufficientExactUnionAndGeometry() {
    Fixture moving;
    moving.sample(100,{moving.roadUser("a",48),moving.roadUser("b",49)});
    moving.sample(200,{moving.roadUser("a",49),moving.roadUser("b",48)});
    moving.sample(300,{moving.roadUser("a",48),moving.roadUser("b",49)});
    moving.manager.advance(400);
    SpatialSelector selector(moving.config,{1,64,true});
    auto result=selector.select(moving.windows[0],*moving.manager.history(),policy(3,40));
    require(result.selectedCells==0 && result.suppressedCells==1
        && result.candidate.counts.distinctContributors==2 && result.candidate.counts.observationContributions==6,
        "Repeated/moving identities fabricated a uniform support rescue");
    audit(result,moving.raw);
    Fixture f;
    f.period(0,{f.roadUser("a",48),f.roadUser("b",48),f.roadUser("c",49)});
    MetricEvaluator impossible(MetricPolicy{"geometry","1",{{MetricId::DistinctContributors,2,{}},
        {MetricId::CellSideM,25,30}}});
    SpatialSelector noSize(f.config,{1,64,true});
    auto none=noSize.select(f.windows[0],*f.manager.history(),impossible);
    require(none.selectedCells==0,"Fallback invented a quadtree level within an impossible 25--30 m bound");
    audit(none,f.raw);
    SpatialSelector depthCap(f.config,{2,64,true});
    auto capped=depthCap.select(f.windows[0],*f.manager.history(),policy(3,40));
    require(capped.selectedCells==0,"A07 bypassed min_depth to reach a passing parent");
    audit(capped,f.raw);
}

void missingUnavailableAndExpiredEvidence() {
    for (bool unavailable : {false,true}) {
        Fixture f;
        const std::vector<CellObservation> data{f.roadUser("a",48),f.roadUser("b",48),f.roadUser("c",49)};
        f.sample(100,data);
        if (unavailable) f.sample(200,{},ObservationStatus::Unavailable);
        f.sample(300,data); f.manager.advance(400);
        SpatialSelector selector(f.config,{1,64,true});
        auto result=selector.select(f.windows[0],*f.manager.history(),policy());
        require(result.selectedCells==0 && result.assessment.coverageStatus==AssessmentStatus::Unavailable,
            "Partial rescue converted missing/unavailable measurements into complete evidence");
        audit(result,f.raw);
    }
    Fixture f;
    f.period(0,{f.roadUser("a",48),f.roadUser("b",48),f.roadUser("c",49)});
    MetricEvaluator unavailable(MetricPolicy{"offline","1",{{MetricId::OccupancyMae,{},1}}});
    SpatialSelector noMetric(f.config,{1,64,true});
    auto unknown=noMetric.select(f.windows[0],*f.manager.history(),unavailable);
    require(unknown.selectedCells==0,"An unavailable required metric was omitted from descendant checks");
    audit(unknown,f.raw);
    auto delayed=f.windows[0]; delayed.closedAtMs=401;
    MetricEvaluator age(MetricPolicy{"age","1",{{MetricId::DistinctContributors,2,{}},
        {MetricId::CellSideM,{},20},{MetricId::AgeAtEvaluationMs,{},400}}});
    SpatialSelector late(f.config,{1,64,true});
    auto expired=late.select(delayed,*f.manager.history(),age);
    require(expired.selectedCells==0,"Rescue reset the interval age or ignored the actual evaluation time");
    audit(expired,f.raw);
}

void budgetAndHistoryFailureDoNotCommit() {
    Fixture f;
    f.period(0,{f.roadUser("a",48),f.roadUser("b",48),f.roadUser("c",49)});
    SpatialSelector limited(f.config,{1,2,true});
    rejects([&] { limited.select(f.windows[0],*f.manager.history(),policy()); });
    auto retry=limited.select(f.windows[0],*f.manager.history(),policy(1));
    require(selectedIds(retry)==std::vector<int>({48,49}) && selectedContributions(retry)==9,
        "An exhausted spatial search committed a partial cut or advanced its interval");
    audit(retry,f.raw);
    AggregationHistory evicted(f.config,*f.config.history);
    for (const auto& batch : f.raw) evicted.append(batch);
    evicted.advance(5000);
    SpatialSelector retained(f.config,{1,64,true});
    rejects([&] { retained.select(f.windows[0],evicted,policy()); });
    auto recovered=retained.select(f.windows[0],*f.manager.history(),policy());
    require(selectedContributions(recovered)==6,"Missing history caused partial state advancement");
    audit(recovered,f.raw);
}

struct AdaptiveFixture {
    AggregationConfig config=settings();
    AggregationHistory history{config,*config.history};
    std::vector<ObservationBatch> raw;
    std::vector<SpatialSelection> outputs;
    AdaptiveAggregation engine;
    explicit AdaptiveFixture(AdaptationStrategy strategy)
        : engine(config,{strategy,100,800,16},{1,64,true},policy(),
            [this](const auto& output) { outputs.push_back(output); }) {}
    std::vector<CellObservation> data(bool secondIdentity=false) const {
        std::vector<CellObservation> result{observation(config,"a",48),observation(config,"b",48),
            observation(config,"c",49)};
        if (secondIdentity) result.push_back(observation(config,"d",49));
        return result;
    }
    void sample(int time,bool secondIdentity=false) {
        ObservationBatch batch{config.runId,config.sensorId,static_cast<std::uint64_t>(time/100),
            time,ObservationStatus::Measured,data(secondIdentity)};
        raw.push_back(batch); history.append(batch); engine.advance(time,history);
    }
    void advance(int time) { history.advance(time); engine.advance(time,history); }
};

void temporalFallbackOnlyAtTerminalAndLaterFullPass() {
    for (auto strategy : {AdaptationStrategy::TemporalFirst,AdaptationStrategy::SpatialFirst}) {
        AdaptiveFixture f(strategy);
        for (int time=100;time<=700;time+=100) {
            f.sample(time);
            require(f.outputs.empty(),"A provisional partial cut ended an interval before its legal deadline");
            require(f.engine.debugState().windowStartMs==0 && f.engine.debugState().hardDeadlineMs==800,
                "Partial rescue moved the original start/deadline");
        }
        f.advance(800);
        require(f.outputs.size()==1 && f.outputs[0].candidate.startMs==0 && f.outputs[0].candidate.endMs==800
            && selectedIds(f.outputs[0])==std::vector<int>{48}
            && selectedContributions(f.outputs[0])==14 && f.outputs[0].candidate.counts.observationContributions==21
            && f.outputs[0].completionReason=="max_window", "Terminal adaptive fallback did not retain the valid child");
        audit(f.outputs[0],f.raw);
        f.advance(800);
        require(f.outputs.size()==1,"Repeated terminal progress duplicated a partial release");
        AdaptiveFixture arrivals(strategy);
        for (int time : {100,200,300}) arrivals.sample(time);
        arrivals.sample(400,true);
        require(arrivals.outputs.empty(),"The excluded endpoint sample caused early full publication");
        arrivals.advance(500);
        require(arrivals.outputs.size()==1 && arrivals.outputs[0].candidate.startMs==0
            && arrivals.outputs[0].candidate.endMs==500 && arrivals.outputs[0].suppressedCells==0
            && selectedIds(arrivals.outputs[0])==std::vector<int>({48,49})
            && selectedContributions(arrivals.outputs[0])==13,
            "A provisional partial cut prevented later arrivals from producing full retention");
        audit(arrivals.outputs[0],arrivals.raw);
    }
}

void immutablePublicationRetryAndNoHistoricalReopen() {
    Fixture f;
    f.period(0,{f.roadUser("a",48),f.roadUser("b",48),f.roadUser("c",49)});
    SpatialSelector selector(f.config,{1,64,true});
    auto partial=selector.select(f.windows[0],*f.manager.history(),policy());
    const auto originalPartial=partial;
    PublicationCoordinator publication(f.config,policy());
    auto reserved=publication.seal(partial,400);
    require(reserved->cells.size()==1 && reserved->cells[0].aggregate.cell.id==48
        && reserved->cells[0].aggregate.counts.observationContributions==6
        && reserved->cells[0].aggregate.counts.typeObservationContributions.empty(),
        "Partial publication contains a parent total, hidden sibling, or unapproved type breakdown");
    auto parent=partial;
    parent.candidate=*f.manager.history()->query(historyCell(f.config.coverage,12,1),0,400).candidate;
    parent.decisions={{12,true,"overlap-test",{}}};
    rejects([&] { publication.seal(parent,400); });
    const auto immutableId=reserved->releaseId;
    const auto immutableCount=reserved->cells[0].aggregate.counts.observationContributions;
    partial.candidate.cells[0].counts.observationContributions=999;
    std::map<std::string,std::uint64_t> external;
    rejects([&] { publication.deliver(400,[&](const auto& release)->SinkResult {
        external.emplace(release.releaseId,release.cells[0].aggregate.counts.observationContributions);
        throw std::runtime_error("Stored partial release; acknowledgement lost");
    }); });
    require(publication.pendingRelease()==reserved && publication.state().retiredThroughMs==0
        && publication.state().reservedStartMs==0 && publication.state().reservedEndMs==400,
        "A failed partial-release sink retired support or changed its reservation");
    require(!publication.deliver(400,[](const auto&) { return SinkResult::Retry; }),"Retry acknowledged a partial release");
    require(publication.deliver(400,[&](const auto& release) {
        require(release.releaseId==immutableId && release.cells.size()==1
            && release.cells[0].aggregate.counts.observationContributions==immutableCount
            && external.at(release.releaseId)==immutableCount,"Partial retry changed the immutable recipient payload");
        external.emplace(release.releaseId,immutableCount);
        return SinkResult::Acknowledged;
    }),"Partial release acknowledgement did not commit");
    require(external.size()==1 && !publication.pendingRelease() && publication.state().retiredThroughMs==400,
        "Partial acknowledgement duplicated output or failed to retire its complete interval");
    rejects([&] { publication.seal(parent,400); });
    // This exact cut previously passed sealing; rejection after ACK therefore
    // tests the historical publication barrier without a malformed-payload excuse.
    rejects([&] { publication.seal(originalPartial,400); });

    MetricEvaluator age(MetricPolicy{"age","1",{{MetricId::DistinctContributors,2,{}},
        {MetricId::CellSideM,{},20},{MetricId::AgeAtEvaluationMs,{},400}}});
    SpatialSelector fresh(f.config,{1,64,true});
    auto valid=fresh.select(f.windows[0],*f.manager.history(),age);
    PublicationCoordinator expiring(f.config,age);
    auto held=expiring.seal(valid,400);
    require(!expiring.deliver(400,[](const auto&) { return SinkResult::Retry; }),"Expiry fixture unexpectedly committed");
    int calls=0;
    rejects([&] { expiring.deliver(401,[&](const auto&) { ++calls; return SinkResult::Acknowledged; }); });
    require(calls==0 && expiring.pendingRelease()==held && expiring.state().retiredThroughMs==0,
        "Expired partial output reached a sink or reopened its reserved interval");
}
}

int main() {
    try {
        simplePartialAndBaseline();
        commonWindowOptionRejectedByLocalApi();
        regionalThresholdRescue();
        internalDescendantAndFutureRefinement();
        insufficientExactUnionAndGeometry();
        missingUnavailableAndExpiredEvidence();
        budgetAndHistoryFailureDoNotCommit();
        temporalFallbackOnlyAtTerminalAndLaterFullPass();
        immutablePublicationRetryAndNoHistoricalReopen();
        std::cout << "Selective suppression passed: hand cases, regional policies, internal rescue, exact unions, "
            "coverage/geometry/deadlines, rollback, temporal opportunity and immutable publication.\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
