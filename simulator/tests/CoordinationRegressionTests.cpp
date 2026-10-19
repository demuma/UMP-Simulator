#include "CellLocalAggregation.hpp"
#include "PolicyTree.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <set>
#include <stdexcept>
#include <tuple>

namespace {
using namespace ump;
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected an explicit rejection");
}
AggregationConfig settings(int depth = 3, AggregationTime window = 200) {
    AggregationConfig result{"run", "sensor", "app", {0,0,80,80,depth}, 100, window};
    result.history = HistoryLimits{2000,32,10000,1000000,1024};
    return result;
}
MetricEvaluator policy(const AggregationConfig& config, double support = 1, double side = 40,
    std::vector<PolicyRegion> regions = {}) {
    return MetricEvaluator(std::make_shared<const PolicyTree>(
        PolicyTreeConfig{"regional","1","app",config.coverage,
            {{MetricId::DistinctContributors,support,{}},{MetricId::CellSideM,{},side}}},std::move(regions)));
}
PolicyRegion regional(const AggregationConfig& config, int id, int depth,
    std::vector<MetricRequirement> requirements) {
    const auto cell = historyCell(config.coverage,id,depth);
    return {std::to_string(id),"test",cell.x,cell.y,cell.width,cell.height,{},std::move(requirements)};
}
bool contains(const CellGeometry& outer, const CellGeometry& inner) {
    return inner.x >= outer.x && inner.y >= outer.y
        && inner.x+inner.width <= outer.x+outer.width
        && inner.y+inner.height <= outer.y+outer.height;
}
bool intersects(const CellGeometry& a, const CellGeometry& b) {
    return std::max(a.x,b.x) < std::min(a.x+a.width,b.x+b.width)
        && std::max(a.y,b.y) < std::min(a.y+a.height,b.y+b.height);
}

void auditFrontier(const CellLocalAggregation& engine,const GridCoverage& coverage) {
    const auto windows=engine.windows();
    double area=0;
    for (std::size_t i=0;i<windows.size();++i) {
        area+=windows[i].cell.width*windows[i].cell.height;
        for (std::size_t j=0;j<i;++j)
            require(!intersects(windows[i].cell,windows[j].cell),
                "The active ownership frontier contains overlapping ancestor/descendant windows");
    }
    require(std::abs(area-coverage.width*coverage.height)<1e-9,
        "The active ownership frontier has a coverage hole");
}

using WindowState = std::tuple<int,int,AggregationTime,AggregationTime,AggregationTime,std::size_t,std::size_t>;
std::vector<WindowState> state(const CellLocalAggregation& engine) {
    std::vector<WindowState> result;
    for (const auto& window : engine.windows()) result.emplace_back(window.cell.id,window.cell.depth,
        window.startMs,window.nextEndMs,window.hardDeadlineMs,window.extensions,window.evaluations);
    std::sort(result.begin(),result.end());
    return result;
}
struct Fixture {
    AggregationConfig config;
    AggregationHistory history;
    std::vector<ObservationBatch> raw;
    std::vector<SpatialSelection> outputs;
    CellLocalAggregation engine;
    Fixture(AggregationConfig config, MetricEvaluator metrics,
        TemporalAdaptationConfig temporal = {AdaptationStrategy::SpatialFirst,100,800,32},
        SpatialSelectionConfig spatial = {2,4096})
        : config(std::move(config)),history(this->config,*this->config.history),
          engine(this->config,temporal,spatial,std::move(metrics),
              [this](const SpatialSelection& output) { outputs.push_back(output); }) {}
    CellObservation observation(std::string id,int cell) const {
        return {std::move(id),"pedestrian",historyCell(config.coverage,cell,config.coverage.leafDepth)};
    }
    void sample(AggregationTime time,std::vector<CellObservation> observations = {},bool run = true,
        ObservationStatus status = ObservationStatus::Measured) {
        ObservationBatch batch{config.runId,config.sensorId,static_cast<std::uint64_t>(time/100),
            time,status,std::move(observations)};
        history.append(batch); raw.push_back(std::move(batch));
        if (run) engine.advance(time,history);
    }
    void advance(AggregationTime time) { history.advance(time); engine.advance(time,history); }
    void finish(AggregationTime time) { history.advance(time); engine.finish(time,history); }
};

// This oracle scans rectangles, timestamps and identities independently of quadtree
// prefix arithmetic, history queries, parent caches and the scheduling implementation.
void checkEvidence(const AggregationCandidate& candidate,const CellGeometry& scope,
    const std::vector<ObservationBatch>& raw,const AggregateCounts& actual) {
    std::uint64_t contributions=0,measured=0,unavailable=0,expected=0;
    std::set<std::string> identities;
    std::map<std::string,std::uint64_t> types;
    for (AggregationTime time=100;time<candidate.endMs;time+=100)
        if (time>=candidate.startMs) ++expected;
    for (const auto& batch : raw) if (batch.observedAtMs>=candidate.startMs
        && batch.observedAtMs<candidate.endMs) {
        if (batch.status==ObservationStatus::Unavailable) { ++unavailable; continue; }
        ++measured;
        for (const auto& observation : batch.observations) if (contains(scope,observation.cell)) {
            ++contributions; identities.insert(observation.contributorId); ++types[observation.type];
        }
    }
    require(candidate.expectedSamples==expected && candidate.measuredSamples==measured
        && candidate.unavailableSamples==unavailable && candidate.missingSamples==expected-measured-unavailable,
        "Local output sample coverage differs from the independent raw scan");
    require(actual.observationContributions==contributions && actual.distinctContributors==identities.size()
        && actual.typeObservationContributions==types,"Local output support differs from the independent raw scan");
    if (measured) require(actual.meanSampleOccupancy.has_value()
        && std::abs(*actual.meanSampleOccupancy-static_cast<double>(contributions)/measured)<1e-12,
        "Local output sample mean differs from the independent raw scan");
    else require(!actual.meanSampleOccupancy,"A candidate without measured samples invented a sample mean");
}
void audit(const std::vector<SpatialSelection>& outputs,const std::vector<ObservationBatch>& raw,
    AggregationTime end,bool complete) {
    for (std::size_t i=0;i<outputs.size();++i) {
        const auto& output=outputs[i];
        require(output.coordinationCell.has_value(),"Local output omitted its explicit coordination footprint");
        const auto& scope=*output.coordinationCell;
        require(output.candidate.startMs>=0 && output.candidate.endMs>output.candidate.startMs
            && output.candidate.endMs<=end,"Local output has an invalid interval");
        checkEvidence(output.candidate,scope,raw,output.candidate.counts);
        for (const auto& cell : output.candidate.cells) {
            require(contains(scope,cell.cell),"Local candidate escaped its coordination footprint");
            checkEvidence(output.candidate,cell.cell,raw,cell.counts);
        }
        for (std::size_t j=0;j<i;++j) {
            const auto& other=outputs[j];
            require(!intersects(scope,*other.coordinationCell)
                || std::max(output.candidate.startMs,other.candidate.startMs)
                    >=std::min(output.candidate.endMs,other.candidate.endMs),
                "Two terminal decisions consumed overlapping space-time support");
        }
    }
    if (complete) for (const auto& batch : raw) if (batch.observedAtMs<end)
        for (const auto& observation : batch.observations) {
            std::size_t owners=0;
            for (const auto& output : outputs) if (batch.observedAtMs>=output.candidate.startMs
                && batch.observedAtMs<output.candidate.endMs
                && contains(*output.coordinationCell,observation.cell)) ++owners;
            require(owners==1,"A source contribution was lost or consumed more than once");
        }
}
const SpatialSelection* find(const std::vector<SpatialSelection>& outputs,int cell,
    AggregationTime start,AggregationTime end) {
    for (const auto& output : outputs) if (output.coordinationCell && output.coordinationCell->id==cell
        && output.candidate.startMs==start && output.candidate.endMs==end) return &output;
    return nullptr;
}
void independentWindowsFollowRegionalPolicies() {
    auto config=settings();
    Fixture f(config,policy(config,1,10,{
        regional(config,192,3,{{MetricId::WindowDurationMs,400,{}}}),
        regional(config,193,3,{{MetricId::WindowDurationMs,{},200}})}));
    for (int time : {100,200}) f.sample(time,{f.observation("A",192),f.observation("B",193)});
    require(find(f.outputs,193,0,200) && !find(f.outputs,192,0,200),
        "A regional duration minimum delayed a different cell or failed to hold its own cell");
    bool pending=false;
    for (const auto& window : f.engine.windows()) if (window.cell.id==192)
        pending=window.startMs==0 && window.nextEndMs>200;
    require(pending,"The unresolved local window lost its original start");
    for (int time : {300,400}) f.sample(time,{f.observation("A",192),f.observation("B",193)});
    require(find(f.outputs,192,0,400) && find(f.outputs,193,200,400),
        "Independent cells did not use different legal aggregation intervals");
    f.finish(500); audit(f.outputs,f.raw,500,true);
}
void mixedDepthTakeoverIncludesEmptySiblings() {
    auto config=settings(4);
    Fixture f(config,policy(config,3,40));
    f.sample(100,{f.observation("moving",768),f.observation("other",769),f.observation("third",770)});
    f.sample(200,{f.observation("moving",769),f.observation("other",768),f.observation("third",770)});
    f.history.advance(300);
    const auto before=f.engine.windows();
    bool fine=false,coarse=false;
    const auto domain=historyCell(config.coverage,48,2);
    for (const auto& window : before) if (contains(domain,window.cell)) {
        fine|=window.cell.depth==4; coarse|=window.cell.depth<4;
    }
    require(fine && coarse,"The mixed-depth takeover scenario did not retain its sparse frontier");
    require(f.engine.requestMerge(domain,300,f.history),
        "A parent could not take over mixed-depth private descendants and known-empty siblings");
    const auto* merged=find(f.outputs,48,0,300);
    require(merged && merged->selectedCells==1 && merged->candidate.counts.distinctContributors==3
        && merged->candidate.counts.observationContributions==6,
        "Mixed-depth takeover lost support or summed child identities");
    f.sample(300,{f.observation("moving",768),f.observation("other",769),f.observation("third",770)});
    f.finish(400); audit(f.outputs,f.raw,400,true);
}
void unequalPrivateEndpointsPermitPrefixTakeover() {
    auto config=settings(3,400);
    Fixture f(config,policy(config,2,40,{
        regional(config,192,3,{{MetricId::WindowDurationMs,{},500}})}),
        {AdaptationStrategy::SpatialFirst,200,800,32});
    for (int time : {100,200,300,400})
        f.sample(time,{f.observation("A",192),f.observation("B",193)});
    AggregationTime aEnd=0,bEnd=0;
    for (const auto& window : f.engine.windows()) {
        if (window.cell.id==192) aEnd=window.nextEndMs;
        if (window.cell.id==193) bEnd=window.nextEndMs;
    }
    require(aEnd==500 && bEnd==600,"The test did not create unequal unpublished next endpoints");
    require(f.engine.requestMerge(historyCell(config.coverage,48,2),300,f.history),
        "Unequal future deadlines blocked an eligible common private prefix");
    const auto* merged=find(f.outputs,48,0,300);
    require(merged && merged->candidate.counts.observationContributions==4,
        "Parent takeover included its excluded endpoint or discarded earlier support");
    for (int time : {500,600}) f.sample(time,{f.observation("A",192),f.observation("B",193)});
    f.finish(700); audit(f.outputs,f.raw,700,true);
}
void alreadyPublishedSiblingBlocksHistoricalTakeover() {
    auto config=settings();
    Fixture f(config,policy(config,2,40,{
        regional(config,192,3,{{MetricId::DistinctContributors,4,{}}}),
        regional(config,193,3,{{MetricId::WindowDurationMs,{},200}})}));
    for (int time : {100,200}) f.sample(time,{f.observation("A",192),
        f.observation("B",193),f.observation("C",193)});
    require(find(f.outputs,193,0,200),"The public-barrier fixture did not release its passing sibling");
    const auto before=state(f.engine); const auto emitted=f.outputs.size();
    require(!f.engine.requestMerge(historyCell(config.coverage,48,2),200,f.history),
        "A parent reused an already released child interval");
    require(state(f.engine)==before && f.outputs.size()==emitted,
        "A rejected historical takeover mutated active windows or emitted data");
    f.finish(300); audit(f.outputs,f.raw,300,true);
}
void incompatiblePoliciesAndUnavailableHistoryAreAtomic() {
    auto config=settings();
    Fixture incompatible(config,policy(config,1,40,{
        regional(config,192,3,{{MetricId::WindowDurationMs,400,{}}}),
        regional(config,193,3,{{MetricId::WindowDurationMs,{},200}})}));
    incompatible.sample(100,{incompatible.observation("A",192),incompatible.observation("B",193)},false);
    incompatible.history.advance(200);
    const auto before=state(incompatible.engine);
    require(!incompatible.engine.requestMerge(historyCell(config.coverage,48,2),200,incompatible.history),
        "A parent ignored contradictory regional time bounds");
    require(state(incompatible.engine)==before && incompatible.outputs.empty(),
        "Infeasible policy intersection consumed private descendants");

    Fixture unavailable(config,policy(config));
    unavailable.sample(100,{},false,ObservationStatus::Unavailable);
    unavailable.history.advance(200);
    const auto beforeUnavailable=state(unavailable.engine);
    require(!unavailable.engine.requestMerge(historyCell(config.coverage,48,2),200,unavailable.history),
        "Unavailable observations became a complete known-empty parent");
    require(state(unavailable.engine)==beforeUnavailable && unavailable.outputs.empty(),
        "A failed incomplete-history takeover changed reservations");
}
void futureHandoffResolvesPrefixesBeforeCommonParentStart() {
    for (bool minimumViolation : {false,true}) {
        auto config=settings();
        const auto firstRequirement=minimumViolation
            ? MetricRequirement{MetricId::WindowDurationMs,300,{}}
            : MetricRequirement{MetricId::DistinctContributors,4,{}};
        Fixture f(config,policy(config,minimumViolation ? 1 : 2,40,{
            regional(config,192,3,{firstRequirement}),
            regional(config,193,3,{{MetricId::WindowDurationMs,{},200}})}));
        for (int time : {100,200}) f.sample(time,{f.observation("A",192),
            f.observation("B",193),f.observation("C",193)});
        require(find(f.outputs,193,0,200),"Future-handoff fixture did not create different retired starts");
        const auto domain=historyCell(config.coverage,48,2);
        const auto emitted=f.outputs.size();
        require(f.engine.scheduleMerge(domain),"Compatible descendants could not schedule a future handoff");
        require(f.outputs.size()==emitted,"Scheduling a handoff published or silently retired an unfinished prefix");
        for (int time : {300,400}) {
            auto observations=std::vector<CellObservation>{f.observation("A",192),
                f.observation("B",193),f.observation("C",193)};
            if (!minimumViolation && time>=400) observations.push_back(f.observation("D",193));
            f.sample(time,std::move(observations));
        }
        const auto* prefix=find(f.outputs,192,minimumViolation ? 300 : 0,400);
        require(prefix && prefix->selectedCells==0 && prefix->suppressedCells==1,
            "An unresolved prefix was lost or incorrectly approved at the future handoff");
        if (minimumViolation) {
            bool rejectedDuration=false;
            for (const auto& assessment : prefix->assessment.cells)
                for (const auto& check : assessment.checks)
                    rejectedDuration|=check.requirement.id==MetricId::WindowDurationMs
                        && check.status==AssessmentStatus::Fail;
            require(rejectedDuration,"An undersized handoff prefix lost its failed duration requirement");
        }
        bool aligned=false;
        for (const auto& window : f.engine.windows()) if (window.cell.id==48)
            aligned=window.startMs==400;
        require(aligned,"The future handoff did not create one parent at the common boundary");
        for (int time : {500,600}) {
            auto observations=std::vector<CellObservation>{f.observation("A",192),
                f.observation("B",193),f.observation("C",193)};
            if (!minimumViolation) observations.push_back(f.observation("D",193));
            f.sample(time,std::move(observations));
        }
        if (!minimumViolation) require(find(f.outputs,48,400,600),
            "A future parent could not aggregate newly aligned support after its old sibling barrier");
        f.finish(700); audit(f.outputs,f.raw,700,true);
    }
}
void sparseDepthSixInitializationHonorsAnExplicitFrontierBudget() {
    auto config=settings(6);
    std::vector<SpatialSelection> outputs;
    CellLocalAggregation engine(config,{AdaptationStrategy::SpatialFirst,100,800,32},{2,4096},
        policy(config),[&](const SpatialSelection& output) { outputs.push_back(output); },128);
    require(engine.windows().size()==4,"Depth-six initialization allocated all 4096 finest windows");
    AggregationHistory history(config,*config.history);
    history.append({"run","sensor",1,100,ObservationStatus::Measured,
        {{"A","pedestrian",historyCell(config.coverage,12288,6)}}});
    engine.advance(100,history); history.advance(200); engine.advance(200,history);
    require(engine.windows().size()<=128,"Sparse refinement exceeded its configured active-frontier budget");
}

void scheduledSubtreeCannotEscapeThroughAnAncestor() {
    auto config=settings();
    Fixture f(config,policy(config,3,40),{AdaptationStrategy::TemporalFirst,100,800,32},{1,4096});
    f.sample(100,{f.observation("A",192),f.observation("B",193),f.observation("C",196)});
    require(f.engine.scheduleMerge(historyCell(config.coverage,48,2)),
        "A subtree inside an existing private owner could not schedule a handoff");
    auditFrontier(f.engine,config.coverage);
    // 48 has only two identities and fails. Ancestor12 has three and passes,
    // but taking it here would absorb the pending handoff's exclusive domain.
    for (int time : {200,300}) {
        f.sample(time,{f.observation("A",192),f.observation("B",193),f.observation("C",196)});
        auditFrontier(f.engine,config.coverage);
    }
    f.finish(400); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,400,true);
}
void explicitTakeoverCannotExceedTheConfiguredTemporalMaximum() {
    auto config=settings(3,400);
    Fixture f(config,policy(config,2,40)); // No policy duration/age bound duplicates the engine limit.
    for (int time=100;time<1000;time+=100)
        f.sample(time,{f.observation("A",192),f.observation("B",193)},false);
    f.history.advance(1000);
    const auto before=state(f.engine);
    require(!f.engine.requestMerge(historyCell(config.coverage,48,2),1000,f.history),
        "An explicit takeover bypassed the configured 800-ms temporal maximum");
    require(state(f.engine)==before && f.outputs.empty(),
        "An oversized manual takeover changed ownership or published data");
}

void aLateRetryCannotAcknowledgeAnExpiredPrivateProposal() {
    auto config=settings();
    AggregationHistory history(config,*config.history);
    std::size_t sinkCalls=0;
    MetricEvaluator metrics(MetricPolicy{"age","1",{{MetricId::DistinctContributors,2,{}},
        {MetricId::CellSideM,{},40},{MetricId::AgeAtEvaluationMs,{},300}}});
    CellLocalAggregation engine(config,{AdaptationStrategy::SpatialFirst,100,800,32},{2,4096},
        std::move(metrics),[&](const SpatialSelection&) {
            ++sinkCalls; throw std::runtime_error("sink failure");
        });
    history.append({"run","sensor",1,100,ObservationStatus::Measured,
        {{"A","pedestrian",historyCell(config.coverage,192,3)},
         {"B","pedestrian",historyCell(config.coverage,193,3)}}});
    history.advance(200);
    const auto before=state(engine); const auto domain=historyCell(config.coverage,48,2);
    rejects([&] { engine.requestMerge(domain,200,history); });
    require(sinkCalls==1 && state(engine)==before,"The initial failed sink changed the private reservation");
    history.advance(400);
    rejects([&] { engine.requestMerge(domain,200,history); });
    require(sinkCalls==1 && state(engine)==before,
        "A late retry called the sink after its private age requirement expired");
    rejects([&] { engine.advance(400,history); });
    require(sinkCalls==1 && state(engine)==before,
        "An unresolved expired proposal was silently discarded or replaced by later work");
}
void explicitTakeoverRespectsTheActiveFrontierBudget() {
    auto config=settings(6);
    AggregationHistory history(config,*config.history);
    std::size_t emitted=0;
    CellLocalAggregation engine(config,{AdaptationStrategy::SpatialFirst,100,800,32},{2,4096},
        policy(config,1),[&](const SpatialSelection&) { ++emitted; },4);
    history.append({"run","sensor",1,100,ObservationStatus::Measured,
        {{"A","pedestrian",historyCell(config.coverage,12288,6)}}});
    history.advance(200); const auto before=state(engine);
    rejects([&] { engine.requestMerge(historyCell(config.coverage,12288,6),200,history); });
    require(state(engine)==before && !emitted,
        "A rejected frontier-budget expansion changed ownership or published a partial result");
    auditFrontier(engine,config.coverage);
}

void freshOwnerCompactionSurvivesMovementEmptyPeriodsAndNewData() {
    auto config=settings(4);
    Fixture f(config,policy(config,1,40));
    // Move through unrelated fine paths. Closing a fully resolved endpoint must
    // compact fresh ownership, rather than retaining every previously visited leaf.
    for (int step=1;step<=12;++step) {
        f.sample(step*100,{f.observation("moving",768+(step*37)%256)});
        if (step%2==0) {
            require(f.engine.windows().size()==4,
                "Resolved moving support left permanently expanded empty owners");
            auditFrontier(f.engine,config.coverage);
        }
    }
    for (int time : {1300,1400,1500,1600}) f.sample(time);
    const auto beforeEmpty=f.outputs.size();
    for (int time=1700;time<=2400;time+=100) f.sample(time);
    require(f.engine.windows().size()==4 && f.outputs.size()-beforeEmpty==16,
        "An empty period emitted per-visited-leaf retirements instead of four compact root scopes");
    for (std::size_t i=beforeEmpty;i<f.outputs.size();++i)
        require(f.outputs[i].candidate.counts.observationContributions==0
            && f.outputs[i].coordinationCell->depth==1,
            "Compacted empty scopes retained observations or incorrect geometry");
    f.sample(2500,{f.observation("new",1001)});
    f.sample(2600,{f.observation("new",1001)});
    const auto* refined=find(f.outputs,1001,2400,2600);
    require(refined && refined->selectedCells==1
        && refined->candidate.counts.observationContributions==1,
        "New observations did not refine a compacted owner back to its exact finest cell");
    f.finish(2700); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,2700,true);
}

void idleAlignmentClosesEmptyOutOfPhasePrefixesBeforeCompaction() {
    auto config=settings();
    Fixture f(config,policy(config,2,40));
    for (int time : {100,200}) f.sample(time,{f.observation("A",192),f.observation("B",192)},false);
    f.history.advance(300);
    require(f.engine.requestMerge(historyCell(config.coverage,192,3),300,f.history),
        "The idle-alignment fixture could not create a valid local clock phase");
    const auto* original=find(f.outputs,192,0,300);
    require(original && original->candidate.counts.observationContributions==4,
        "The phase-shifted private takeover lost its original measured support");
    bool phase0=false,phase300=false;
    for (const auto& window : f.engine.windows()) {
        phase0|=window.startMs==0; phase300|=window.startMs==300;
    }
    require(phase0 && phase300,"The idle-alignment fixture did not create different local phases");
    f.sample(300);
    require(f.engine.windows().size()==4,"Confirmed empty out-of-phase owners did not compact to four roots");
    bool alignedPrefix=false;
    for (const auto& output : f.outputs) if (output.completionReason=="idle_alignment") {
        alignedPrefix=true;
        require(output.candidate.counts.observationContributions==0
            && output.selectedCells==0 && output.suppressedCells==0
            && output.candidate.startMs>=0 && output.candidate.startMs<300
            && output.candidate.endMs==300,
            "Idle alignment claimed nonempty support or omitted its exact private prefix");
    }
    require(alignedPrefix,"Different clocks were silently aligned without retiring their empty prefixes");
    auditFrontier(f.engine,config.coverage);
    for (int time : {400,500,600}) f.sample(time);
    require(f.engine.windows().size()==4,"A quiet phase-shifted region expanded after idle compaction");
    for (int time : {700,800,900})
        f.sample(time,{f.observation("X",193),f.observation("Y",193)});
    const auto* repopulated=find(f.outputs,193,700,900);
    require(repopulated && repopulated->selectedCells==1
        && repopulated->candidate.counts.observationContributions==4,
        "Repopulation after idle alignment lost its exact fine support");
    f.finish(1000); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,1000,true);
}

void failedSinkPreservesExactTakeoverAndRetry() {
    auto config=settings(3,400);
    AggregationHistory history(config,*config.history);
    std::vector<ObservationBatch> raw;
    std::vector<SpatialSelection> outputs,attempts;
    bool fail=true;
    CellLocalAggregation engine(config,{AdaptationStrategy::SpatialFirst,100,800,32},{2,4096},
        policy(config,2,40),[&](const SpatialSelection& output) {
            attempts.push_back(output);
            if (fail) throw std::runtime_error("sink failure");
            outputs.push_back(output);
        });
    raw.push_back({"run","sensor",1,100,ObservationStatus::Measured,
        {{"A","pedestrian",historyCell(config.coverage,192,3)},
         {"B","pedestrian",historyCell(config.coverage,193,3)}}});
    history.append(raw.back()); history.advance(200);
    const auto before=state(engine); const auto domain=historyCell(config.coverage,48,2);
    rejects([&] { engine.requestMerge(domain,200,history); });
    require(state(engine)==before && outputs.empty(),"A failed sink committed its parent takeover");
    fail=false;
    rejects([&] { engine.requestMerge(historyCell(config.coverage,49,2),200,history); });
    rejects([&] { engine.requestMerge(domain,100,history); });
    require(attempts.size()==1 && outputs.empty() && state(engine)==before,
        "A nonmatching manual retry acknowledged a different reserved proposal");
    require(engine.requestMerge(domain,200,history),"The exact parent takeover could not be retried");
    require(attempts.size()==2 && attempts[0].candidate.startMs==attempts[1].candidate.startMs
        && attempts[0].candidate.endMs==attempts[1].candidate.endMs
        && attempts[0].candidate.counts.distinctContributors==attempts[1].candidate.counts.distinctContributors
        && attempts[0].candidate.cells[0].cell.id==attempts[1].candidate.cells[0].cell.id,
        "A sink retry changed its proposed parent interval or support");
    require(!engine.requestMerge(domain,200,history) && outputs.size()==1,
        "A repeated takeover emitted the same space-time interval twice");
    history.advance(300); engine.finish(300,history);
    audit(outputs,raw,300,true);
}
}
int main() {
    try {
        independentWindowsFollowRegionalPolicies(); mixedDepthTakeoverIncludesEmptySiblings();
        unequalPrivateEndpointsPermitPrefixTakeover(); alreadyPublishedSiblingBlocksHistoricalTakeover();
        incompatiblePoliciesAndUnavailableHistoryAreAtomic();
        futureHandoffResolvesPrefixesBeforeCommonParentStart();
        sparseDepthSixInitializationHonorsAnExplicitFrontierBudget();
        scheduledSubtreeCannotEscapeThroughAnAncestor();
        explicitTakeoverCannotExceedTheConfiguredTemporalMaximum();
        aLateRetryCannotAcknowledgeAnExpiredPrivateProposal();
        explicitTakeoverRespectsTheActiveFrontierBudget();
        freshOwnerCompactionSurvivesMovementEmptyPeriodsAndNewData();
        idleAlignmentClosesEmptyOutOfPhasePrefixesBeforeCompaction();
        failedSinkPreservesExactTakeoverAndRetry();
        std::cout << "PASS: independent local windows, mixed-depth takeover, private prefix/suffix conservation, "
            "publication barriers, incompatible policies, unavailable history, sink retries and raw-data oracle.\n";
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
