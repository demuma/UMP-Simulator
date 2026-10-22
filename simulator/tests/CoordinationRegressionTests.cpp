#include "CellLocalAggregation.hpp"
#include "PolicyTree.hpp"
#include <algorithm>
#include <cmath>
#include <functional>
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
    std::function<void(const SpatialSelection&)> beforeOutput;
    CellLocalAggregation engine;
    Fixture(AggregationConfig config, MetricEvaluator metrics,
        TemporalAdaptationConfig temporal = {AdaptationStrategy::SpatialFirst,100,800,32},
        SpatialSelectionConfig spatial = {2,4096}, std::size_t maxActiveCells = 16384)
        : config(std::move(config)),history(this->config,*this->config.history),
          engine(this->config,temporal,spatial,std::move(metrics),
              [this](const SpatialSelection& output) {
                  if (beforeOutput) beforeOutput(output);
                  outputs.push_back(output);
              }, maxActiveCells) {}
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
// A passing child must not inherit a neighbouring failure's waiting time when
// every shared parent violates a policy bound. This is the hand-checkable causal
// case from the frozen coordination study, rather than an aggregate winner test.
void anIllegalParentCannotDelayAPassingSibling() {
    for (const auto strategy : {AdaptationStrategy::TemporalFirst, AdaptationStrategy::SpatialFirst}) {
        auto config=settings();
        Fixture f(config,policy(config,2,10),{strategy,100,800,32},{2,4096});
        for (int time : {100,200}) f.sample(time,{f.observation("valid-A",192),
            f.observation("valid-B",192),f.observation("singleton",193),
            f.observation("independent-A",208),f.observation("independent-B",208)});
        const auto* valid=find(f.outputs,192,0,200);
        const auto* independent=find(f.outputs,208,0,200);
        require(valid && independent && valid->selectedCells==1 && independent->selectedCells==1,
            "An infeasible shared parent delayed a passing child or an independent merge group");
        require(valid->candidate.counts.observationContributions==2,
            "A timely valid-child release included the excluded endpoint");
        bool singletonPending=false;
        for (const auto& window : f.engine.windows()) if (window.cell.id==193)
            singletonPending=window.startMs==0 && window.nextEndMs>200;
        require(singletonPending,"Releasing a passing sibling silently discarded an unresolved child");
        for (const auto& output : f.outputs) if (output.selectedCells)
            require(output.coordinationCell->width<=10,
                "A hold repair bypassed the configured maximum cell size");
        f.finish(400); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,400,true);
    }
}

void sameEndpointPlanningProtectsNestedAndIndependentRescues() {
    auto config=settings(4);
    Fixture f(config,policy(config,2,40),{AdaptationStrategy::TemporalFirst,100,800,32},{1,4096});
    // In each 40-m quadrant the first two identities can already use a 20-m
    // parent. The isolated third needs the full 40-m parent at this same endpoint.
    // Publishing the smaller merge first would irreversibly close that option.
    for (int time : {100,200}) f.sample(time,{f.observation("west-A",768),
        f.observation("west-B",772),f.observation("west-C",806),
        f.observation("east-A",896),f.observation("east-B",900),f.observation("east-C",934)});
    for (int parent : {12,14}) {
        const auto* selected=find(f.outputs,parent,0,200);
        require(selected && selected->selectedCells==1
            && selected->candidate.counts.distinctContributors==3
            && selected->candidate.counts.observationContributions==3,
            "A same-endpoint smaller publication blocked a broader valid rescue");
    }
    require(!find(f.outputs,48,0,200) && !find(f.outputs,56,0,200),
        "Nested rescue planning emitted an overlapping descendant before its parent");
    auditFrontier(f.engine,config.coverage);
    f.finish(400); audit(f.outputs,f.raw,400,true);
}

void independentNearestRescuesPreserveTheirFinerResolution() {
    auto config=settings(4);
    Fixture f(config,policy(config,2,40),{AdaptationStrategy::TemporalFirst,100,800,32},{1,4096});
    for (int time : {100,200}) f.sample(time,{f.observation("A",896),f.observation("B",900),
        f.observation("C",928),f.observation("D",932)});
    const auto* north=find(f.outputs,56,0,200);
    const auto* south=find(f.outputs,58,0,200);
    require(north && south && north->selectedCells==1 && south->selectedCells==1,
        "Two disjoint nearest rescue groups were replaced by unnecessary broader aggregation");
    require(!find(f.outputs,14,0,200),
        "A passing ancestor displaced disjoint finer rescues without rescuing additional failed support");
    f.finish(400); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,400,true);
}

void aBroaderRescueCannotBypassItsSpatialPolicy() {
    auto config=settings(4);
    Fixture f(config,policy(config,2,20),{AdaptationStrategy::TemporalFirst,100,800,32},{1,4096});
    for (int time : {100,200}) f.sample(time,{f.observation("A",896),f.observation("B",900),
        f.observation("isolated",934)});
    const auto* allowed=find(f.outputs,56,0,200);
    require(allowed && allowed->selectedCells==1 && allowed->candidate.counts.distinctContributors==2,
        "An illegal broader rescue prevented its policy-valid nearest subgroup from publishing");
    require(!find(f.outputs,14,0,200),"A nested rescue exceeded its 20-m policy size cap");
    f.finish(400); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,400,true);
}

void endpointPlanningPreservesTheDeclaredActionPriority() {
    for (const auto strategy : {AdaptationStrategy::TemporalFirst, AdaptationStrategy::SpatialFirst}) {
        auto config=settings();
        Fixture f(config,policy(config,2,40),{strategy,100,800,32},{2,4096});
        for (int time : {100,200}) f.sample(time,{f.observation("A",192),f.observation("B",193)});
        if (strategy==AdaptationStrategy::TemporalFirst) {
            const auto* parent=find(f.outputs,48,0,200);
            require(parent && parent->selectedCells==1,
                "Temporal First failed to preserve time through an immediately feasible spatial rescue");
        } else {
            require(!find(f.outputs,48,0,200),
                "Spatial First coarsened before its legal temporal extension was exhausted");
            f.sample(300,{f.observation("A2",192),f.observation("B2",193)});
            f.sample(400,{f.observation("A2",192),f.observation("B2",193)});
            const auto* left=find(f.outputs,192,0,400);
            const auto* right=find(f.outputs,193,0,400);
            require(left && right && left->selectedCells==1 && right->selectedCells==1,
                "Spatial First failed to preserve fine cells when temporal support became sufficient");
            require(!find(f.outputs,48,0,400),
                "Spatial First used a parent despite both finer cells independently passing");
        }
        f.finish(500); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,500,true);
    }
}

void aRescueCannotBorrowIdentitiesFromItsExcludedEndpoint() {
    auto config=settings();
    Fixture f(config,policy(config,2,40),{AdaptationStrategy::TemporalFirst,100,800,32},{1,4096});
    f.sample(100,{f.observation("original",192)});
    f.sample(200,{f.observation("arrives-at-endpoint",192)});
    for (const auto& output : f.outputs)
        require(!output.selectedCells,"A selected interval borrowed an identity from its excluded endpoint");
    f.sample(300,{f.observation("not-yet-in-prefix",192)});
    const auto* selected=find(f.outputs,192,0,300);
    require(selected && selected->selectedCells==1
        && selected->candidate.counts.distinctContributors==2
        && selected->candidate.counts.observationContributions==2,
        "The next legal interval lost exact support or borrowed a future identity");
    f.finish(400); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,400,true);
}

void boundedEndpointSearchFailsBeforeAnyDisclosure() {
    auto config=settings(4);
    Fixture f(config,policy(config,2,40),{AdaptationStrategy::TemporalFirst,100,800,32},{1,1});
    f.sample(100,{f.observation("A",896),f.observation("B",900),f.observation("C",934)});
    f.sample(200,{f.observation("A",896),f.observation("B",900),f.observation("C",934)},false);
    // One ancestor assessment cannot establish this two-level rescue. The bounded
    // planner must fail explicitly before disclosing a tempting smaller release.
    bool exhausted=false;
    try { f.engine.advance(200,f.history); }
    catch (const std::length_error&) { exhausted=true; }
    require(exhausted,"A bounded endpoint search ignored its spatial proposal limit");
    require(f.outputs.empty() && f.engine.debugState().completedWindows==0,
        "An exhausted endpoint search disclosed or retired a partial candidate set");
    for (const auto& window : f.engine.windows())
        require(window.startMs==0,"Budget exhaustion consumed a private interval");
    auditFrontier(f.engine,config.coverage);
    const auto beforeRetry=state(f.engine);
    rejects([&] { f.engine.advance(200,f.history); });
    require(f.outputs.empty() && state(f.engine)==beforeRetry,
        "Retrying an exhausted bounded search changed support or evaluation progress");
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
    // 48 has only two identities and fails. Ancestor12 has three and passes.
    // A valid broader supersession may now replace the contained private intent;
    // either outcome must preserve the full-domain ownership and exact support.
    for (int time : {200,300}) {
        f.sample(time,{f.observation("A",192),f.observation("B",193),f.observation("C",196)});
        auditFrontier(f.engine,config.coverage);
    }
    f.finish(400); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,400,true);
}

// Future alignment requests reserve private intentions, not recipient-visible
// data. A genuinely passing broader current prefix may replace contained plans;
// it must still cover every mixed-depth/empty descendant with one common start.
void passingParentCanReplaceContainedFuturePlans() {
    for (const auto strategy : {AdaptationStrategy::TemporalFirst, AdaptationStrategy::SpatialFirst})
        for (bool regionalDeadline : {false,true}) {
            auto config=settings(4,400);
            std::vector<PolicyRegion> regions;
            if (regionalDeadline) regions.push_back(regional(config,768,4,
                {{MetricId::WindowDurationMs,{},300}}));
            Fixture f(config,policy(config,2,40,std::move(regions)),{strategy,100,800,32},{1,4096});
            const auto parent=historyCell(config.coverage,48,2);
            const auto finePlan=historyCell(config.coverage,768,4);
            const auto secondPlan=historyCell(config.coverage,193,3);
            const auto unrelated=historyCell(config.coverage,196,3);
            require(f.engine.scheduleMerge(finePlan) && f.engine.scheduleMerge(secondPlan)
                && f.engine.scheduleMerge(unrelated),"The supersession fixture failed to reserve disjoint future plans");
            bool fine=false,coarse=false;
            for (const auto& window : f.engine.windows()) if (contains(parent,window.cell)) {
                fine|=window.cell.depth==4; coarse|=window.cell.depth==3;
            }
            require(fine && coarse,"The future-plan fixture did not retain mixed-depth private ownership");
            f.sample(100,{f.observation("A",768),f.observation("B",772)},false);
            f.history.advance(200);
            require(f.engine.requestMerge(parent,200,f.history),
                "Contained future plans blocked an already passing common private parent prefix");
            const auto* selected=find(f.outputs,48,0,200);
            require(selected && selected->selectedCells==1 && selected->suppressedCells==0
                && selected->candidate.counts.distinctContributors==2
                && selected->candidate.counts.observationContributions==2,
                "Superseding future plans changed the parent support or failed to include its empty siblings");
            if (regionalDeadline) require(selected->candidate.endMs-selected->candidate.startMs<=300,
                "A passing supersession bypassed an intersecting regional temporal maximum");
            auditFrontier(f.engine,config.coverage);
            const auto emitted=f.outputs.size(); const auto after=state(f.engine);
            require(!f.engine.requestMerge(parent,200,f.history)
                && f.outputs.size()==emitted && state(f.engine)==after,
                "A superseding parent reopened its acknowledged historical support");
            require(!f.engine.scheduleMerge(unrelated),
                "A parent takeover canceled a disjoint future alignment request");
            // This new explicit parent request would overlap either old contained
            // reservation if it had survived the successful ACK.
            require(f.engine.scheduleMerge(parent),
                "A successful parent ACK left one of its superseded descendant plans live");
            for (int time : {200,300}) f.sample(time,{f.observation("A",768),f.observation("B",772)},false);
            f.finish(400); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,400,true);
        }
}

void anEnclosingFuturePlanStillBlocksANarrowerTakeover() {
    auto config=settings(4,400);
    Fixture f(config,policy(config,2,40),{AdaptationStrategy::TemporalFirst,100,800,32},{1,4096});
    const auto enclosing=historyCell(config.coverage,48,2);
    const auto child=historyCell(config.coverage,192,3);
    require(f.engine.scheduleMerge(enclosing),"The enclosing future-plan fixture did not reserve its domain");
    f.sample(100,{f.observation("A",768),f.observation("B",769)},false);
    f.history.advance(200);
    const auto before=state(f.engine);
    require(!f.engine.requestMerge(child,200,f.history) && state(f.engine)==before && f.outputs.empty(),
        "A narrower passing child escaped a strictly enclosing future alignment request");
    require(!f.engine.scheduleMerge(enclosing),"A rejected child takeover erased its enclosing reservation");
    require(f.engine.requestMerge(enclosing,200,f.history),
        "An enclosing reservation prevented its own genuinely passing current-prefix replacement");
    for (int time : {200,300}) f.sample(time,{},false);
    f.finish(400); audit(f.outputs,f.raw,400,true);
}

void aFailedParentDoesNotCancelContainedAlignmentRequests() {
    for (bool incomplete : {false,true}) {
        auto config=settings(4,400);
        Fixture f(config,policy(config,2,incomplete ? 40 : 10),
            {AdaptationStrategy::TemporalFirst,100,800,32},{1,4096});
        const auto plan=historyCell(config.coverage,768,4);
        require(f.engine.scheduleMerge(plan),"The failed-parent fixture could not reserve its future plan");
        if (incomplete) f.sample(100,{},false,ObservationStatus::Unavailable);
        else f.sample(100,{f.observation("A",768),f.observation("B",772)},false);
        f.history.advance(200);
        const auto before=state(f.engine); const auto decisions=f.engine.debugState().retainedDecisions;
        require(!f.engine.requestMerge(historyCell(config.coverage,48,2),200,f.history),
            "An infeasible or incompletely measured parent superseded a private future plan");
        require(state(f.engine)==before && f.outputs.empty()
            && f.engine.debugState().retainedDecisions==decisions,
            "A failed superseding candidate changed private ownership, progress or output");
        require(!f.engine.scheduleMerge(plan),
            "A failed parent proposal canceled a contained alignment request before acceptance");
        f.sample(200,{},false); f.sample(300,{},false);
        f.finish(400); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,400,true);
    }
}

bool sameReservedProposal(const SpatialSelection& a,const SpatialSelection& b) {
    const auto counts=[](const AggregateCounts& x,const AggregateCounts& y) {
        return x.observationContributions==y.observationContributions
            && x.distinctContributors==y.distinctContributors
            && x.typeObservationContributions==y.typeObservationContributions
            && x.meanSampleOccupancy==y.meanSampleOccupancy;
    };
    if (a.candidate.startMs!=b.candidate.startMs || a.candidate.endMs!=b.candidate.endMs
        || a.candidate.closedAtMs!=b.candidate.closedAtMs || a.candidate.truncated!=b.candidate.truncated
        || a.candidate.expectedSamples!=b.candidate.expectedSamples
        || a.candidate.measuredSamples!=b.candidate.measuredSamples
        || a.candidate.unavailableSamples!=b.candidate.unavailableSamples
        || a.candidate.missingSamples!=b.candidate.missingSamples
        || a.candidate.coverage!=b.candidate.coverage || !counts(a.candidate.counts,b.candidate.counts)
        || a.candidate.cells.size()!=b.candidate.cells.size() || a.selectedCells!=b.selectedCells
        || a.suppressedCells!=b.suppressedCells || a.completionReason!=b.completionReason
        || a.strategy!=b.strategy || a.temporalExtensions!=b.temporalExtensions
        || a.decisions.size()!=b.decisions.size() || a.temporalDecisions.size()!=b.temporalDecisions.size()
        || a.assessment.cells.size()!=b.assessment.cells.size()
        || bool(a.coordinationCell)!=bool(b.coordinationCell)) return false;
    if (a.coordinationCell && (a.coordinationCell->id!=b.coordinationCell->id
        || a.coordinationCell->depth!=b.coordinationCell->depth)) return false;
    for (std::size_t i=0;i<a.candidate.cells.size();++i)
        if (a.candidate.cells[i].cell.id!=b.candidate.cells[i].cell.id
            || !counts(a.candidate.cells[i].counts,b.candidate.cells[i].counts)) return false;
    for (std::size_t i=0;i<a.decisions.size();++i)
        if (a.decisions[i].cellId!=b.decisions[i].cellId || a.decisions[i].selected!=b.decisions[i].selected
            || a.decisions[i].reason!=b.decisions[i].reason || a.decisions[i].transition!=b.decisions[i].transition
            || a.decisions[i].triggerCells!=b.decisions[i].triggerCells) return false;
    for (std::size_t i=0;i<a.temporalDecisions.size();++i) {
        const auto& x=a.temporalDecisions[i]; const auto& y=b.temporalDecisions[i];
        if (x.action!=y.action || x.startMs!=y.startMs || x.endMs!=y.endMs
            || x.evaluatedAtMs!=y.evaluatedAtMs || x.status!=y.status) return false;
    }
    for (std::size_t i=0;i<a.assessment.cells.size();++i) {
        const auto& x=a.assessment.cells[i]; const auto& y=b.assessment.cells[i];
        if (x.status!=y.status || x.effectivePolicyId!=y.effectivePolicyId
            || x.policySources!=y.policySources || x.policyFeasible!=y.policyFeasible
            || x.metrics.size()!=y.metrics.size() || x.checks.size()!=y.checks.size()) return false;
        for (std::size_t j=0;j<x.metrics.size();++j)
            if (x.metrics[j].id!=y.metrics[j].id || x.metrics[j].value!=y.metrics[j].value
                || x.metrics[j].unavailableReason!=y.metrics[j].unavailableReason) return false;
        for (std::size_t j=0;j<x.checks.size();++j)
            if (x.checks[j].requirement.id!=y.checks[j].requirement.id
                || x.checks[j].requirement.min!=y.checks[j].requirement.min
                || x.checks[j].requirement.max!=y.checks[j].requirement.max
                || x.checks[j].observed!=y.checks[j].observed || x.checks[j].status!=y.checks[j].status
                || x.checks[j].reason!=y.checks[j].reason) return false;
    }
    return true;
}

void futurePlanSupersessionCommitsOnlyAfterAnIdenticalAcknowledgedRetry() {
    auto config=settings(4,400);
    Fixture f(config,policy(config,2,40),{AdaptationStrategy::TemporalFirst,100,800,32},{1,4096});
    const auto parent=historyCell(config.coverage,48,2);
    const auto plan=historyCell(config.coverage,768,4);
    const auto unrelated=historyCell(config.coverage,196,3);
    require(f.engine.scheduleMerge(plan) && f.engine.scheduleMerge(unrelated),
        "The retry/supersession fixture failed to reserve its future domains");
    f.sample(100,{f.observation("A",768),f.observation("B",772)},false);
    f.history.advance(200);
    const auto before=state(f.engine); const auto decisions=f.engine.debugState().retainedDecisions;
    bool fail=true;
    std::vector<SpatialSelection> attempts;
    f.beforeOutput=[&](const SpatialSelection& proposal) {
        attempts.push_back(proposal);
        if (fail) throw std::runtime_error("Controlled supersession sink failure");
    };
    rejects([&] { f.engine.requestMerge(parent,200,f.history); });
    require(attempts.size()==1 && f.outputs.empty() && state(f.engine)==before
        && f.engine.debugState().retainedDecisions==decisions,
        "A failed sink committed a proposed future-plan supersession");
    rejects([&] { f.engine.requestMerge(historyCell(config.coverage,49,2),200,f.history); });
    rejects([&] { f.engine.scheduleMerge(parent); });
    require(attempts.size()==1 && state(f.engine)==before,
        "Later work bypassed an unacknowledged superseding reservation");
    fail=false;
    require(f.engine.requestMerge(parent,200,f.history),"An identical superseding parent could not resume after sink failure");
    require(attempts.size()==2 && f.outputs.size()==1 && sameReservedProposal(attempts[0],attempts[1]),
        "Retrying future-plan supersession changed its immutable candidate or policy evidence");
    require(!f.engine.scheduleMerge(unrelated),"ACK canceled an unrelated future handoff");
    require(f.engine.scheduleMerge(parent),"ACK did not atomically retire the contained superseded request");
    f.beforeOutput={};
    for (int time : {200,300}) f.sample(time,{},false);
    f.finish(400); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,400,true);
}

void expiredSupersessionCannotReachTheSinkOrCommitItsReplacement() {
    auto config=settings(4,400);
    MetricEvaluator metrics(MetricPolicy{"age","1",{{MetricId::DistinctContributors,2,{}},
        {MetricId::CellSideM,{},40},{MetricId::AgeAtEvaluationMs,{},300}}});
    Fixture f(config,std::move(metrics),{AdaptationStrategy::TemporalFirst,100,800,32},{1,4096});
    const auto parent=historyCell(config.coverage,48,2);
    require(f.engine.scheduleMerge(historyCell(config.coverage,768,4)),
        "The expiration fixture failed to reserve its future descendant");
    f.sample(100,{f.observation("A",768),f.observation("B",772)},false);
    f.history.advance(200); const auto before=state(f.engine);
    std::size_t calls=0;
    f.beforeOutput=[&](const SpatialSelection&) { ++calls; throw std::runtime_error("Controlled sink failure"); };
    rejects([&] { f.engine.requestMerge(parent,200,f.history); });
    require(calls==1 && state(f.engine)==before && f.outputs.empty(),
        "Initial supersession sink failure changed private support");
    f.history.advance(400);
    rejects([&] { f.engine.requestMerge(parent,200,f.history); });
    rejects([&] { f.engine.advance(400,f.history); });
    require(calls==1 && state(f.engine)==before && f.outputs.empty(),
        "An expired superseding proposal reached the sink or committed its successor/plan cancellation");
    rejects([&] { f.engine.scheduleMerge(historyCell(config.coverage,49,2)); });
    auditFrontier(f.engine,config.coverage);
}


// Three synthetic identities cross a few finest cells. A's sparse earlier
// prefixes reach their deadline at 1800. B and C then make a legal root-13
// parent possible at the next regular check, 2200. No coordinates, source identities or external data
// are embedded: this is an explicit cell/time counterexample to stale intents.
std::vector<CellObservation> automaticHandoffObservations(const Fixture& f,int time) {
    std::vector<CellObservation> result;
    if (time>=900) {
        const int cell=time<1200 ? 13952 : time<1500 ? 13953 : time<1800 ? 13956
            : time<2100 ? 13957 : 13968;
        result.push_back(f.observation("A",cell));
    }
    if (time>=1900) result.push_back(f.observation("B",time<2100 ? 13866 : 13867));
    if (time>=2000) result.push_back(f.observation("C",13440));
    return result;
}

std::vector<SpatialSelection> runAutomaticHandoffWitness(bool failDuringIntentGeneration) {
    auto config=settings(6,400);
    Fixture f(config,policy(config,3,40),{AdaptationStrategy::TemporalFirst,100,1000,32},{1,4096});
    bool failed=false,retried=false;
    std::optional<SpatialSelection> reserved;
    f.beforeOutput=[&](const SpatialSelection& proposal) {
        if (failDuringIntentGeneration && !failed && proposal.candidate.closedAtMs==1800
            && proposal.candidate.counts.observationContributions) {
            failed=true; reserved=proposal;
            throw std::runtime_error("Controlled endpoint-intent sink failure");
        }
        if (failed && !retried) {
            require(reserved && sameReservedProposal(*reserved,proposal),
                "A resumed endpoint changed its immutable proposal before applying automatic intents");
            retried=true;
        }
    };
    for (int time=100;time<=2200;time+=100) {
        try { f.sample(time,automaticHandoffObservations(f,time)); }
        catch (...) {
            if (!failDuringIntentGeneration || time!=1800 || !failed || retried) throw;
            const auto held=state(f.engine);
            rejects([&] { f.engine.scheduleMerge(historyCell(config.coverage,12,1)); });
            require(state(f.engine)==held,"An endpoint retry bypass allowed new alignment work before ACK");
            f.engine.advance(time,f.history);
            require(retried,"The failed endpoint did not retry its reserved proposal first");
        }
        auditFrontier(f.engine,config.coverage);
    }
    if (failDuringIntentGeneration) require(failed && retried,
        "The automatic-intent regression did not exercise an acknowledged sink retry");
    bool released=false;
    for (const auto& output : f.outputs) if (output.coordinationCell->id==13
        && output.candidate.startMs==1800 && output.candidate.endMs==2200 && output.candidate.closedAtMs==2200) {
        released=true;
        require(output.selectedCells==1 && output.candidate.counts.distinctContributors==3
            && output.candidate.counts.observationContributions==9,
            "The timely ancestor failed its actual observed support check");
    }
    require(released,
        "An obsolete future handoff blocked a passing private ancestor at its regular 2200-ms check");
    f.finish(2300); auditFrontier(f.engine,config.coverage); audit(f.outputs,f.raw,2300,true);
    return f.outputs;
}

void automaticHandoffPlanningUsesTheCompletedEndpointAndSurvivesRetry() {
    const auto baseline=runAutomaticHandoffWitness(false);
    const auto retried=runAutomaticHandoffWitness(true);
    require(baseline.size()==retried.size(),
        "A transient sink failure lost deferred endpoint intents or changed terminal retirement count");
    for (std::size_t i=0;i<baseline.size();++i)
        require(sameReservedProposal(baseline[i],retried[i]),
            "A transient sink failure changed later automatic handoffs, release geometry or private support");
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

void sparseDeepOwnersCoverEveryQuadrantWithoutDenseInitialization() {
    auto config=settings(14,400);
    // Four sparse depth-14 paths need 4 + 4 * 13 * 3 = 160 owners, not
    // 4^14 leaves. Include the largest supported cell ID and varying child bits.
    Fixture f(config,policy(config,1,40),
        {AdaptationStrategy::SpatialFirst,100,800,32},{2,4096},160);
    std::vector<int> leaves;
    std::vector<CellObservation> rows;
    for(int root=12;root<=15;++root) {
        int leaf=root;
        for(int depth=2;depth<=14;++depth)leaf=4*leaf+(root==15?3:(root+depth)%4);
        leaves.push_back(leaf);
        rows.push_back(f.observation("quadrant-"+std::to_string(root),leaf));
    }
    require(leaves.back()==1073741823,"Deep fixture does not exercise the maximum valid cell ID");
    f.sample(100,rows);f.sample(200,rows);
    require(f.engine.windows().size()==160 && f.outputs.empty(),
        "Sparse deep refinement escaped its exact active-owner budget or published too early");
    const auto first=state(f.engine);
    f.engine.advance(200,f.history);
    require(state(f.engine)==first && f.outputs.empty(),
        "An already represented deepest domain was refined or advanced again");
    for(int leaf:leaves) {
        int owners=0;
        const auto cell=historyCell(config.coverage,leaf,14);
        for(const auto& window:f.engine.windows())if(contains(window.cell,cell)) {
            ++owners;
            require(window.cell.id==leaf && window.cell.depth==14 && window.startMs==0,
                "Sparse refinement selected an unrelated or shallower owner");
        }
        require(owners==1,"A sparse deep cell has no unique enclosing owner");
    }
    auditFrontier(f.engine,config.coverage);
    f.sample(300,rows);f.advance(400);
    for(int leaf:leaves) {
        const auto* output=find(f.outputs,leaf,0,400);
        require(output && output->selectedCells==1 && output->candidate.counts.observationContributions==3,
            "A deepest cell did not preserve its exact source support when published");
    }
    f.finish(400);auditFrontier(f.engine,config.coverage);audit(f.outputs,f.raw,400,true);
}

void retiredCoarseOwnerIgnoresAnotherStartsHistoricalFineSupport() {
    auto config=settings(3,400);
    Fixture f(config,policy(config,1,40),
        {AdaptationStrategy::SpatialFirst,100,800,32},{2,4096},10);
    f.sample(100,{f.observation("retired",192),f.observation("pending",196)},false);
    f.sample(200,{},false);
    require(f.engine.requestMerge(historyCell(config.coverage,48,2),200,f.history),
        "Different-start fixture could not retire its coarse prefix");
    // 48 now starts at 200; neighbouring 49 still starts at 0. The query for
    // start 0 returns both old leaves. Only 196 is still privately owned at 0.
    // Refining 192 as well would exceed this deliberately exact owner budget.
    f.engine.advance(200,f.history);
    bool preserved=false,refined=false;
    for(const auto& window:f.engine.windows()) {
        if(window.cell.id==48)preserved=window.startMs==200 && window.cell.depth==2;
        if(window.cell.id==196)refined=window.startMs==0 && window.cell.depth==3;
        require(window.cell.id!=192,"Retired fine history refined a successor with a different original start");
    }
    require(preserved && refined && f.engine.windows().size()==10 && f.outputs.size()==1,
        "Mixed-start refinement changed the retired owner or skipped its pending neighbour");
    auditFrontier(f.engine,config.coverage);
    f.finish(300);auditFrontier(f.engine,config.coverage);audit(f.outputs,f.raw,300,true);
}

void explicitTakeoverHandlesDescendantFrontierThenExactOwner() {
    auto config=settings(3,400);
    Fixture f(config,policy(config,1,40));
    const auto rows=std::vector<CellObservation>{f.observation("A",192),f.observation("B",193)};
    f.sample(100,rows);f.sample(200,rows);
    const auto parent=historyCell(config.coverage,48,2);
    bool fine=false;
    for(const auto& window:f.engine.windows()) {
        require(window.cell.id!=48,"Descendant-frontier fixture unexpectedly has an exact parent owner");
        if(contains(parent,window.cell))fine|=window.cell.depth==3;
    }
    require(fine && f.engine.requestMerge(parent,200,f.history),
        "An explicit parent without an enclosing owner could not collect its complete descendant frontier");
    f.sample(300,{},false);
    require(f.engine.requestMerge(parent,300,f.history),
        "An exact existing owner was incorrectly treated as needing a strict enclosing ancestor");
    for(const auto interval:{std::pair<int,int>{0,200},{200,300}}) {
        const auto* output=find(f.outputs,48,interval.first,interval.second);
        require(output && output->selectedCells==1 && output->candidate.counts.observationContributions==2,
            "Exact-owner takeover changed the source interval or reused a retired prefix");
    }
    require(!f.engine.requestMerge(parent,300,f.history),"An equal-domain request published a retired interval twice");
    f.finish(400);auditFrontier(f.engine,config.coverage);audit(f.outputs,f.raw,400,true);
}

void partiallyRefinedBudgetFailureLeavesTheWholeFrontierUnchanged() {
    auto config=settings(3,400);
    Fixture f(config,policy(config,1,40),
        {AdaptationStrategy::SpatialFirst,100,800,32},{2,4096},7);
    f.sample(100,{f.observation("A",192)},false);f.sample(200,{},false);
    const auto before=state(f.engine);
    // The first split fits; the second must fail on the private candidate cut.
    // Retrying must not inherit the first attempt's partial path expansion.
    for(int attempt=0;attempt<2;++attempt) {
        rejects([&]{f.engine.advance(200,f.history);});
        require(state(f.engine)==before && f.outputs.empty(),
            "An automatic refinement budget failure committed a partial frontier or publication");
    }
    require(f.engine.requestMerge(historyCell(config.coverage,48,2),200,f.history),
        "A failed deeper refinement prevented a later legal bounded takeover");
    require(f.outputs.size()==1 && f.outputs.front().candidate.counts.observationContributions==1,
        "Recovery after a refinement budget failure omitted or duplicated source evidence");
    f.finish(300);auditFrontier(f.engine,config.coverage);audit(f.outputs,f.raw,300,true);
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
        independentWindowsFollowRegionalPolicies(); anIllegalParentCannotDelayAPassingSibling();
        sameEndpointPlanningProtectsNestedAndIndependentRescues();
        independentNearestRescuesPreserveTheirFinerResolution();
        aBroaderRescueCannotBypassItsSpatialPolicy();
        endpointPlanningPreservesTheDeclaredActionPriority();
        aRescueCannotBorrowIdentitiesFromItsExcludedEndpoint();
        boundedEndpointSearchFailsBeforeAnyDisclosure();
        mixedDepthTakeoverIncludesEmptySiblings();
        unequalPrivateEndpointsPermitPrefixTakeover(); alreadyPublishedSiblingBlocksHistoricalTakeover();
        incompatiblePoliciesAndUnavailableHistoryAreAtomic();
        futureHandoffResolvesPrefixesBeforeCommonParentStart();
        sparseDepthSixInitializationHonorsAnExplicitFrontierBudget();
        scheduledSubtreeCannotEscapeThroughAnAncestor();
        passingParentCanReplaceContainedFuturePlans();
        anEnclosingFuturePlanStillBlocksANarrowerTakeover();
        aFailedParentDoesNotCancelContainedAlignmentRequests();
        futurePlanSupersessionCommitsOnlyAfterAnIdenticalAcknowledgedRetry();
        expiredSupersessionCannotReachTheSinkOrCommitItsReplacement();
        automaticHandoffPlanningUsesTheCompletedEndpointAndSurvivesRetry();
        explicitTakeoverCannotExceedTheConfiguredTemporalMaximum();
        aLateRetryCannotAcknowledgeAnExpiredPrivateProposal();
        explicitTakeoverRespectsTheActiveFrontierBudget();
        sparseDeepOwnersCoverEveryQuadrantWithoutDenseInitialization();
        retiredCoarseOwnerIgnoresAnotherStartsHistoricalFineSupport();
        explicitTakeoverHandlesDescendantFrontierThenExactOwner();
        partiallyRefinedBudgetFailureLeavesTheWholeFrontierUnchanged();
        freshOwnerCompactionSurvivesMovementEmptyPeriodsAndNewData();
        idleAlignmentClosesEmptyOutOfPhasePrefixesBeforeCompaction();
        failedSinkPreservesExactTakeoverAndRetry();
        std::cout << "PASS: independent local windows, mixed-depth takeover, private prefix/suffix conservation, "
            "publication barriers, depth-14 sparse ownership, original-start refinement, atomic split budgets, "
            "incompatible policies, unavailable history, sink retries and raw-data oracle.\n";
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
