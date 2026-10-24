#include "AdaptiveAggregation.hpp"
#include "AggregationManager.hpp"
#include "CellLocalAggregation.hpp"
#include "PolicyTree.hpp"
#include "PublicationCoordinator.hpp"
#include <cmath>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>

namespace {
using namespace ump;
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
template<class F> void rejects(F action) {
    try { action(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected suppression validation rejection");
}
std::shared_ptr<const SemanticTaxonomy> taxonomy() {
    return std::make_shared<const SemanticTaxonomy>("suppression-test", "1", std::vector<SemanticNode>{
        {"road_user", "", 1, {}}, {"pedestrian", "road_user", .5, {}},
        {"adult_pedestrian", "pedestrian", 0, {"AdultPedestrian", "AdultPedAlias"}},
        {"child_pedestrian", "pedestrian", 0, {"ChildPedestrian"}},
        {"cyclist", "road_user", .5, {}}, {"adult_cyclist", "cyclist", 0, {"AdultCyclist", "CyclistAlias"}},
        {"child_cyclist", "cyclist", 0, {"ChildCyclist"}}});
}
AggregationConfig settings() {
    AggregationConfig config{"suppression-run", "agbs", "application", {0,0,80,80,2}, 100, 400};
    config.history = HistoryLimits{2000, 32, 10000, 1000000, 128};
    config.semanticTaxonomy = taxonomy(); return config;
}
std::vector<MetricRequirement> requirements(std::optional<double> cap = std::nullopt,
    double totalFloor = 5, double loss = 1, double side = 40) {
    std::vector<MetricRequirement> r{{MetricId::DistinctContributors, totalFloor, {}},
        {MetricId::MinCategoryDistinctContributors, 5, {}}, {MetricId::SemanticMaxLoss, {}, loss},
        {MetricId::CellSideM, {}, side}};
    if (cap) r.push_back({MetricId::SemanticSuppressionFraction, {}, *cap});
    return r;
}
MetricEvaluator evaluator(const AggregationConfig& config, std::optional<double> cap = std::nullopt,
    double totalFloor = 5, double loss = 1, double side = 40) {
    return MetricEvaluator(MetricPolicy{"suppression-policy", "1", requirements(cap,totalFloor,loss,side)}, config.semanticTaxonomy);
}
struct Fixture {
    AggregationConfig config = settings();
    std::vector<AggregationCandidate> output;
    AggregationManager manager{config, [this](const auto& c) { output.push_back(c); }};
    std::vector<CellObservation> people;
    Fixture() = default;
    explicit Fixture(bool withRare) {
        if (withRare) { add("AdultPedestrian",20,"p"); add("AdultCyclist",1,"c"); period(); }
    }
    void add(std::string type, int n, std::string prefix) {
        for (int i=0; i<n; ++i) people.push_back({prefix+std::to_string(i),type,historyCell(config.coverage,48,2)});
    }
    void period() {
        for (int t : {100,200,300}) manager.ingest({config.runId,config.sensorId,static_cast<std::uint64_t>(t/100),t,
            ObservationStatus::Measured,people});
        manager.advance(400);
    }
    const AggregationCandidate& candidate() const { return output.at(0); }
};
SpatialSelection selection(const AggregationCandidate& c, const MetricEvaluator& e) {
    auto assessed=e.evaluate(c,c.closedAtMs);
    SpatialSelection s{c,assessed,c,assessed,{},{},2};
    s.decisions.push_back({48,assessed.status==AssessmentStatus::Pass,"test",{}});
    s.selectedCells=s.decisions.front().selected; return s;
}
void defaultOffAndInclusiveCap() {
    Fixture f(true);
    const auto old=evaluator(f.config).evaluate(f.candidate(),400).cells.at(0);
    const auto disabled=evaluator(f.config,0).evaluate(f.candidate(),400).cells.at(0);
    require(old.semantic->bins.size()==1 && old.semantic->bins[0].categoryId=="road_user"
        && old.semantic->meanLoss==1 && !old.retainedCounts && !old.semanticSuppression,
        "Default-off changed ordinary full-data generalization");
    require(disabled.semantic->bins[0].categoryId==old.semantic->bins[0].categoryId
        && disabled.semantic->meanLoss==old.semantic->meanLoss && !disabled.retainedCounts
        && !disabled.semanticSuppression,"Explicit cap zero differs from disabled semantics");
    const auto below=evaluator(f.config,.04).evaluate(f.candidate(),400).cells.at(0);
    require(!below.retainedCounts && below.semanticSuppression->suppressedObservations==0,
        "Suppression exceeded its contribution fraction budget");
    const auto exact=evaluator(f.config,1.0/21).evaluate(f.candidate(),400).cells.at(0);
    require(exact.status==AssessmentStatus::Pass && exact.retainedCounts
        && exact.retainedCounts->observationContributions==60 && exact.retainedCounts->distinctContributors==20
        && exact.semantic->bins.size()==1 && exact.semantic->bins[0].categoryId=="adult_pedestrian"
        && exact.semantic->meanLoss==0,"Inclusive cap failed a truthful rare-class suppression");
    const auto& audit=*exact.semanticSuppression;
    require(audit.inputObservations==63 && audit.retainedObservations==60 && audit.suppressedObservations==3
        && audit.inputDistinct==21 && audit.retainedDistinct==20 && audit.suppressedDistinct==1
        && audit.suppressedTypeObservations.at("AdultCyclist")==3
        && audit.suppressedLeaves==std::vector<std::string>{"adult_cyclist"}
        && audit.evaluatedCandidates<=f.config.semanticTaxonomy->nodes().size()
        && std::abs(audit.fullInputSemanticLoss-1.0/21)<1e-12,
        "Private suppression counts, exact type mask or full-input loss are wrong");
    require(f.candidate().counts.observationContributions==63 && f.candidate().counts.distinctContributors==21,
        "Suppression mutated the original retirement candidate");
}
void totalFloorOtherRequirementsAndEvidence() {
    Fixture f(true);
    const auto floor=evaluator(f.config,.1,21).evaluate(f.candidate(),400).cells.at(0);
    require(!floor.retainedCounts && floor.semantic->maxLoss==1 && floor.status==AssessmentStatus::Pass,
        "Removed track counted toward retained total-support minimum");
    const auto side=evaluator(f.config,.1,5,1,10).evaluate(f.candidate(),400).cells.at(0);
    require(side.status==AssessmentStatus::Fail && !side.retainedCounts,"Suppression bypassed an unrelated hard geometry bound");
    const auto cap=evaluator(f.config,.1,5,0).evaluate(f.candidate(),400).cells.at(0);
    require(cap.status==AssessmentStatus::Pass && cap.semantic->maxLoss==0,"Valid suppression did not honor zero semantic loss");
    auto unavailable=f.candidate(); unavailable.cells.front().counts.semanticEvidence.reset();
    const auto noEvidence=evaluator(f.config,.1).evaluate(unavailable,400).cells.at(0);
    require(noEvidence.status==AssessmentStatus::Unavailable && !noEvidence.retainedCounts,
        "Missing evidence was treated as known or suppressed away");
    auto malformed=f.candidate(); malformed.cells.front().counts.semanticEvidence->nodes.at("adult_cyclist").distinctContributors=2;
    rejects([&]{evaluator(f.config,.1).evaluate(malformed,400);});
}
void intermediateTierAndRemovalPenalty() {
    Fixture mixed; mixed.add("AdultPedestrian",19,"p"); mixed.add("ChildPedestrian",1,"child");
    mixed.add("AdultCyclist",1,"bike"); mixed.period();
    const auto kept=evaluator(mixed.config,.05).evaluate(mixed.candidate(),400).cells.at(0);
    require(kept.retainedCounts && kept.retainedCounts->distinctContributors==20
        && kept.semantic->bins.size()==1 && kept.semantic->bins[0].categoryId=="pedestrian"
        && kept.semantic->meanLoss==.5,"Intermediate semantic family was not retained within the tighter removal cap");
    Fixture counter; counter.add("AdultPedestrian",40,"p"); counter.add("AdultCyclist",2,"a");
    counter.add("ChildCyclist",2,"c"); counter.period();
    auto req=requirements(.2); req[1].min=4;
    MetricEvaluator e(MetricPolicy{"counterexample","1",req},counter.config.semanticTaxonomy);
    const auto assessment=e.evaluate(counter.candidate(),400).cells.at(0);
    require(!assessment.retainedCounts && assessment.semantic->bins.size()==2
        && std::abs(assessment.semantic->meanLoss-2.0/44)<1e-12
        && assessment.semanticSuppression->fullInputSemanticLoss==assessment.semanticSuppression->unsuppressedSemanticLoss,
        "Removing four cyclists was rewarded over a lower-cost intermediate category");
}
void repeatedTracksAndAliases() {
    Fixture f; f.add("AdultPedestrian",20,"p"); f.add("AdultCyclist",1,"c");
    f.people.back().type="CyclistAlias"; f.period();
    const auto kept=evaluator(f.config,.1).evaluate(f.candidate(),400).cells.at(0);
    require(kept.semanticSuppression->suppressedDistinct==1 && kept.semanticSuppression->suppressedObservations==3
        && kept.semanticSuppression->suppressedTypeObservations.at("CyclistAlias")==3,
        "Repeated aliases became multiple people or an incorrect raw-type mask");
    Fixture repeated; repeated.add("AdultPedestrian",1,"p"); repeated.add("AdultCyclist",1,"c"); repeated.period();
    const auto small=evaluator(repeated.config,.9).evaluate(repeated.candidate(),400).cells.at(0);
    require(small.status==AssessmentStatus::Fail && !small.retainedCounts,"Repeated samples manufactured the support floor");
}
void strictRegionalInheritance() {
    Fixture f(true);
    const std::vector<PolicyRegion> regions{{"strict","crossing",0,0,20,20,{},
        {{MetricId::SemanticSuppressionFraction,{},0}}}, {"loose","plaza",0,0,40,40,{},
        {{MetricId::SemanticSuppressionFraction,{},.3}}}};
    auto tree=std::make_shared<const PolicyTree>(PolicyTreeConfig{"regional","1","application",f.config.coverage,
        requirements(.2)},regions);
    const auto checked=MetricEvaluator(tree,f.config.semanticTaxonomy).evaluate(f.candidate(),400).cells.at(0);
    require(!checked.retainedCounts && checked.semantic->meanLoss==1,"A looser overlapping region overrode a strict suppression prohibition");
    auto rootOff=std::make_shared<const PolicyTree>(PolicyTreeConfig{"regional-off","1","application",f.config.coverage,
        requirements()}, std::vector<PolicyRegion>{regions.back()});
    require(!MetricEvaluator(rootOff,f.config.semanticTaxonomy).evaluate(f.candidate(),400).cells.at(0).retainedCounts,
        "A child region enabled suppression without explicit root permission");
}
void publicationRetryAndFullRetirement() {
    Fixture f(true); auto e=evaluator(f.config,.1);
    auto chosen=selection(f.candidate(),e);
    PublicationCoordinator coordinator(f.config,e);
    const auto release=coordinator.seal(chosen,400);
    require(release->cells.size()==1 && release->cells[0].aggregate.counts.observationContributions==60
        && release->cells[0].aggregate.counts.distinctContributors==20
        && release->cells[0].aggregate.counts.typeObservationContributions.empty()
        && !release->cells[0].aggregate.counts.semanticEvidence
        && release->cells[0].semantic->bins[0].observationContributions==60,
        "Recipient payload disclosed source totals or omitted categories");
    require(!coordinator.deliver(400,[&](const auto& same){
        require(&same==release.get(),"Retry changed the sealed immutable payload"); return SinkResult::Retry;
    }),"Retry unexpectedly retired private support");
    require(coordinator.state().retiredThroughMs==0 && coordinator.state().reservedEndMs==400,
        "Failed acknowledgement lost the full original reservation");
    require(coordinator.deliver(450,[&](const auto& same){
        require(&same==release.get() && same.cells[0].aggregate.counts.observationContributions==60,
            "Retry recomputed a different filtered release"); return SinkResult::Acknowledged;
    }) && coordinator.state().retiredThroughMs==400,"ACK did not retire the full raw cell-window");
    rejects([&]{coordinator.seal(chosen,450);});
}
void commonAndLocalImmediateRelease() {
    Fixture f(true); auto e=evaluator(f.config,.1);
    for (auto local : {false,true}) {
        std::vector<SpatialSelection> released;
        TemporalAdaptationConfig temporal; temporal.strategy=AdaptationStrategy::SemanticFirst;
        temporal.extensionStepMs=100; temporal.maxWindowMs=1000;
        temporal.releaseTrigger=ReleaseTrigger::PolicySatisfied;
        if (local) {
            temporal.coordination=CoordinationMode::CellLocal;
            CellLocalAggregation core(f.config,temporal,{1,128,false},e,
                [&](const auto& s){ if(s.candidate.counts.observationContributions) released.push_back(s); });
            core.advance(400,*f.manager.history());
        } else {
            AdaptiveAggregation core(f.config,temporal,{1,128,true},e,
                [&](const auto& s){released.push_back(s);});
            core.advance(400,*f.manager.history());
        }
        require(released.size()==1 && released.front().candidate.endMs==400
            && released.front().candidate.counts.observationContributions==63
            && released.front().assessment.cells.front().retainedCounts->observationContributions==60,
            "A valid filtered release waited until deadline or lost original conservation accounting");
    }
}
void invalidBounds() {
    Fixture f(true);
    rejects([&]{evaluator(f.config,1.001);}); rejects([&]{evaluator(f.config,-.1);});
    rejects([&]{MetricEvaluator(MetricPolicy{"bad","1",{{MetricId::SemanticSuppressionFraction,.1,{}}}});});
    rejects([&]{MetricEvaluator noTaxonomy(MetricPolicy{"bad","1",{{MetricId::SemanticSuppressionFraction,{},.1}}});});
}
}
int main() {
    try {
        defaultOffAndInclusiveCap(); totalFloorOtherRequirementsAndEvidence(); intermediateTierAndRemovalPenalty();
        repeatedTracksAndAliases(); strictRegionalInheritance(); publicationRetryAndFullRetirement();
        commonAndLocalImmediateRelease(); invalidBounds();
        std::cout << "PASS: 8 semantic suppression groups: default-off, bounded exact masks, retained hard checks, "
            "full-input loss benefit, regional prohibition, immutable retries and full-window retirement.\n";
    } catch(const std::exception& error) {std::cerr << error.what() << '\n'; return 1;}
}
