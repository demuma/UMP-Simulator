#include "AdaptiveAggregation.hpp"
#include "AggregationManager.hpp"
#include "PolicyTree.hpp"
#include "PublicationCoordinator.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ump;
void require(bool test, const char* why) { if (!test) throw std::runtime_error(why); }
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected semantic rejection");
}
std::shared_ptr<const SemanticTaxonomy> catalog() {
    return std::make_shared<const SemanticTaxonomy>("road-users", "1", std::vector<SemanticNode>{
        {"road_user","",1,{}}, {"pedestrian","road_user",0,{"Pedestrian"}},
        {"cyclist","road_user",.5,{}}, {"adult_cyclist","cyclist",0,{"Adult Cyclist"}},
        {"child_cyclist","cyclist",0,{"Child Cyclist"}}});
}
AggregationConfig settings() {
    AggregationConfig c{"semantic-run","agbs","app",{0,0,80,80,2},100,400};
    c.history=HistoryLimits{2000,32,10000,1000000,128}; c.semanticTaxonomy=catalog(); return c;
}
MetricEvaluator metrics(const AggregationConfig& c,double support,double loss,double side=20) {
    return MetricEvaluator(MetricPolicy{"semantic-policy","1",{
        {MetricId::DistinctContributors,1,{}}, {MetricId::CellSideM,{},side},
        {MetricId::MinCategoryDistinctContributors,support,{}}, {MetricId::SemanticMaxLoss,{},loss}}},c.semanticTaxonomy);
}
CellObservation person(const AggregationConfig& c,std::string id,std::string type,int cell=48) {
    return {std::move(id),std::move(type),historyCell(c.coverage,cell,2)};
}
std::vector<CellObservation> cyclists(const AggregationConfig& c,int adults,int children,int cell=48) {
    std::vector<CellObservation> rows;
    for(int n=0;n<adults;++n) rows.push_back(person(c,"a"+std::to_string(n),"Adult Cyclist",cell));
    for(int n=0;n<children;++n) rows.push_back(person(c,"c"+std::to_string(n),"Child Cyclist",cell));
    return rows;
}
struct Fixture {
    AggregationConfig config=settings();
    std::vector<AggregationCandidate> windows;
    AggregationManager manager{config,[this](const auto& candidate){windows.push_back(candidate);}};
    void sample(int time,const std::vector<CellObservation>& data) {
        manager.ingest({config.runId,config.sensorId,static_cast<std::uint64_t>(time/100),time,
            ObservationStatus::Measured,data});
    }
    void period(const std::vector<CellObservation>& rows) {
        for(int t:{100,200,300}) sample(t,rows);
        manager.advance(400);
    }
    SpatialSelection select(const MetricEvaluator& evaluator) {
        return SpatialSelector(config,{1,128,true}).select(windows.at(0),*manager.history(),evaluator);
    }
};
void truthfulGeneralizationAndLossBound() {
    Fixture f; auto data=cyclists(f.config,1,0);
    for(int n=0;n<19;++n) data.push_back(person(f.config,"p"+std::to_string(n),"Pedestrian"));
    f.period(data); auto evaluator=metrics(f.config,5,1);
    auto output=f.select(evaluator);
    require(output.selectedCells==1 && output.candidate.cells.at(0).cell.id==48,
        "Semantic generalization needlessly coarsened space");
    const auto& semantic=*output.assessment.cells.at(0).semantic;
    require(semantic.bins.size()==1 && semantic.bins[0].categoryId=="road_user"
        && semantic.bins[0].observationContributions==60 && semantic.bins[0].distinctContributors==20
        && semantic.minimumDistinctContributors==20 && semantic.maxLoss==1 && semantic.meanLoss==1,
        "19 pedestrians and one cyclist were deleted, relabeled falsely, or miscounted");
    require(f.select(metrics(f.config,5,.5)).selectedCells==0,"Semantic detail bound was weakened");
    require(!f.config.semanticTaxonomy->exactQuery(semantic,"cyclist"),"Generalized mode count fabricated an exact zero");
    require(f.config.semanticTaxonomy->exactQuery(semantic,"road_user")->observationContributions==60,
        "Total observation query lost contributions");
}
void intermediateClassAndInsufficientSupport() {
    Fixture f; f.period(cyclists(f.config,2,2));
    auto output=f.select(metrics(f.config,4,.5));
    const auto& value=*output.assessment.cells[0].semantic;
    require(output.selectedCells==1 && value.bins.size()==1 && value.bins[0].categoryId=="cyclist"
        && value.bins[0].distinctContributors==4 && value.bins[0].observationContributions==12
        && value.maxLoss==.5 && value.meanLoss==.5,"2+2 cyclists failed their true parent generalization");
    require(f.select(metrics(f.config,5,1)).selectedCells==0,"Repeated measurements created a fifth person");
    auto exact=f.config.semanticTaxonomy->exactQuery(value,"cyclist");
    require(exact && exact->distinctContributors==4 && !f.config.semanticTaxonomy->exactQuery(value,"adult_cyclist"),
        "Semantic query confused exact parent with unknown child");
    Fixture detailed; detailed.period(cyclists(detailed.config,4,4));
    auto fine=detailed.select(metrics(detailed.config,4,0));
    require(fine.selectedCells==1 && fine.assessment.cells[0].semantic->bins.size()==2
        && fine.assessment.cells[0].semantic->maxLoss==0,"Passing terminal classes were unnecessarily generalized");
}
void regionalConstraintsAndSpatialRescue() {
    Fixture f; auto data=cyclists(f.config,2,2);
    for(int n=0;n<4;++n) data.push_back(person(f.config,"extra"+std::to_string(n),"Adult Cyclist",49));
    f.period(data);
    auto tree=std::make_shared<const PolicyTree>(PolicyTreeConfig{"regional","1","app",f.config.coverage,{
        {MetricId::DistinctContributors,1,{}},{MetricId::CellSideM,{},40},
        {MetricId::MinCategoryDistinctContributors,4,{}},{MetricId::SemanticMaxLoss,{},1}}},
        std::vector<PolicyRegion>{{"strict","cycleway",0,0,20,20,{},{{MetricId::SemanticMaxLoss,{},0}}}});
    auto checked=MetricEvaluator(tree,f.config.semanticTaxonomy);
    auto selected=f.select(checked);
    // Fine cell48 cannot expose its two child cyclists at support4, and a parent
    // still has only2 children; the strict footprint cannot be bypassed.
    require(selected.selectedCells==1 && selected.candidate.cells.back().cell.id==49,
        "Regional semantic bound did not preserve only the unrelated valid cell");
    Fixture spatial; auto rows=cyclists(spatial.config,2,0);
    for(int n=0;n<2;++n) rows.push_back(person(spatial.config,"other"+std::to_string(n),"Adult Cyclist",49));
    spatial.period(rows);
    auto parent=spatial.select(metrics(spatial.config,4,0,40));
    require(parent.selectedCells==1 && parent.candidate.cells[0].cell.id==12
        && parent.assessment.cells[0].semantic->maxLoss==0,
        "Semantic support failure did not trigger an allowed spatial merge");
}
void temporalRescueAndHardMetricGates() {
    auto c=settings(); AggregationHistory history(c,*c.history);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(c,{AdaptationStrategy::SpatialFirst,100,800,16},{1,128,true},metrics(c,4,0),
        [&](const auto& selected){output.push_back(selected);});
    for(int t:{100,200,300,400}) {
        auto rows=cyclists(c,t==400?4:2,0);
        history.append({c.runId,c.sensorId,static_cast<std::uint64_t>(t/100),t,ObservationStatus::Measured,rows});
        engine.advance(t,history);
    }
    require(output.empty(),"Semantic extension published an excluded endpoint sample early");
    history.advance(500);engine.advance(500,history);
    require(output.size()==1 && output[0].candidate.startMs==0 && output[0].candidate.endMs==500
        && output[0].assessment.cells[0].semantic->maxLoss==0,"Temporal support rescue moved the original window");
    Fixture f;f.period(cyclists(f.config,2,2));
    auto missing=f.windows[0];missing.expectedSamples=4;missing.missingSamples=1;missing.coverage=WindowCoverage::Incomplete;
    require(metrics(f.config,4,.5).evaluate(missing,400).status==AssessmentStatus::Unavailable,
        "Semantic support bypassed missing measurement coverage");
    auto wrongTypes=f.windows[0];
    wrongTypes.cells[0].counts.typeObservationContributions={{"Pedestrian",12}};
    rejects([&]{metrics(f.config,4,.5).evaluate(wrongTypes,400);});
    auto noEvidence=f.windows[0];noEvidence.cells[0].counts.semanticEvidence.reset();
    require(metrics(f.config,4,.5).evaluate(noEvidence,400).status==AssessmentStatus::Unavailable,
        "Missing private semantic evidence became a passing candidate");
    auto invalid=f.windows[0];invalid.cells[0].counts.semanticEvidence->nodes.at("cyclist").distinctContributors=9;
    rejects([&]{metrics(f.config,4,.5).evaluate(invalid,400);});
    require(MetricEvaluator(MetricPolicy{"missing","1",{{MetricId::MinCategoryDistinctContributors,4,{}}}})
        .evaluate(f.windows[0],400).status==AssessmentStatus::Unavailable,"Missing catalog was ignored");
}
void immutableApprovedSemanticRelease() {
    Fixture f;f.period(cyclists(f.config,2,2)); auto evaluator=metrics(f.config,4,.5);
    auto selected=f.select(evaluator);
    // Deliberately corrupt diagnostic annotations. Seal must recompute, not copy them.
    selected.assessment.cells[0].semantic->bins[0].observationContributions=999;
    PublicationCoordinator publisher(f.config,evaluator);
    auto release=publisher.seal(selected,400);
    require(release->cells.size()==1 && release->cells[0].semantic
        && release->cells[0].semantic->bins[0].observationContributions==12
        && !release->cells[0].aggregate.counts.semanticEvidence
        && release->cells[0].aggregate.counts.typeObservationContributions.empty(),
        "Publication trusted diagnostic bins or exposed private node/type evidence");
    require(!publisher.deliver(400,[](const auto&){return SinkResult::Retry;}),"Retry prematurely retired semantic support");
    require(publisher.pendingRelease()==release && publisher.state().retiredThroughMs==0,"Semantic retry changed ownership");
    require(publisher.deliver(400,[&](const auto& snapshot){
        require(snapshot.cells[0].semantic->bins[0].categoryId=="cyclist"
            && snapshot.cells[0].semantic->bins[0].distinctContributors==4,"Immutable semantic payload changed");
        return SinkResult::Acknowledged;
    }) && publisher.state().retiredThroughMs==400,"Semantic acknowledgement failed to retire the original interval");
    rejects([&]{publisher.seal(selected,400);});
    auto other=metrics(f.config,4,.5);
    auto mismatched=f.config;mismatched.semanticTaxonomy=catalog();
    rejects([&]{PublicationCoordinator wrong(mismatched,other);});
}
void invalidMetricDirections() {
    for (const auto r:std::vector<MetricRequirement>{{MetricId::MinCategoryDistinctContributors,0,{}},
        {MetricId::MinCategoryDistinctContributors,{},5},{MetricId::SemanticMaxLoss,.5,{}},
        {MetricId::SemanticMaxLoss,{},1.1},{MetricId::SemanticMeanLoss,{},-1}})
        rejects([&]{validateMetricRequirements({r});});
    auto c=settings();
    rejects([&]{MetricEvaluator invalid(MetricPolicy{"no-semantic-contract","1",{{MetricId::DistinctContributors,1,{}}}},c.semanticTaxonomy);});
}
}
int main(){try{
    truthfulGeneralizationAndLossBound();intermediateClassAndInsufficientSupport();
    regionalConstraintsAndSpatialRescue();temporalRescueAndHardMetricGates();
    immutableApprovedSemanticRelease();invalidMetricDirections();
    std::cout<<"PASS: semantic policy metrics, truthful cuts, regional/spatial/temporal adaptation and immutable publication.\n";
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
