#include "CellLocalAggregation.hpp"
#include "PolicyTree.hpp"
#include <algorithm>
#include <cmath>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace {
using namespace ump;
void require(bool condition, const char* reason) { if (!condition) throw std::runtime_error(reason); }
template<class F> void rejects(F call, const char* reason) {
    try { call(); } catch (const std::exception&) { return; }
    throw std::runtime_error(reason);
}
std::shared_ptr<const SemanticTaxonomy> catalog() {
    return std::make_shared<const SemanticTaxonomy>("local-semantic", "1", std::vector<SemanticNode>{
        {"road_user", "", 1, {}}, {"pedestrian", "road_user", .5, {}},
        {"adult_pedestrian", "pedestrian", 0, {"Adult Pedestrian"}},
        {"child_pedestrian", "pedestrian", 0, {"Child Pedestrian"}},
        {"cyclist", "road_user", .5, {}},
        {"adult_cyclist", "cyclist", 0, {"Adult Cyclist"}},
        {"child_cyclist", "cyclist", 0, {"Child Cyclist"}},
        {"scooter", "road_user", 0, {"Scooter"}}});
}
AggregationConfig settings(int depth = 2) {
    AggregationConfig c{"local-semantic-run", "agbs", "app", {0,0,80,80,depth}, 100, 400};
    c.history = HistoryLimits{2000,32,100000,1000000,1024};
    c.semanticTaxonomy = catalog();
    return c;
}
TemporalAdaptationConfig timeSettings(AdaptationStrategy strategy = AdaptationStrategy::SemanticFirst,
    ReleaseTrigger trigger = ReleaseTrigger::PolicySatisfied,
    SemanticSecondaryStrategy secondary = SemanticSecondaryStrategy::TemporalFirst,
    AggregationTime maximum = 1000) {
    TemporalAdaptationConfig t{strategy,100,maximum,32};
    t.coordination=CoordinationMode::CellLocal; t.releaseTrigger=trigger; t.semanticSecondaryStrategy=secondary;
    return t;
}
MetricEvaluator metrics(const AggregationConfig& c, double support = 4, double side = 40,
    double loss = 1, std::vector<PolicyRegion> regions = {}) {
    return MetricEvaluator(std::make_shared<const PolicyTree>(PolicyTreeConfig{"local-policy","1","app",c.coverage,
        {{MetricId::DistinctContributors,1,{}},{MetricId::CellSideM,{},side},
         {MetricId::WindowDurationMs,{},1000},{MetricId::AgeAtEvaluationMs,{},1000},
         {MetricId::MinCategoryDistinctContributors,support,{}},{MetricId::SemanticMaxLoss,{},loss}}},
         std::move(regions)),c.semanticTaxonomy);
}
PolicyRegion region(const AggregationConfig& c, int id, int depth, std::vector<MetricRequirement> bounds) {
    const auto geometry=historyCell(c.coverage,id,depth);
    return {std::to_string(id),std::to_string(id),geometry.x,geometry.y,geometry.width,geometry.height,{},std::move(bounds)};
}
bool contains(const CellGeometry& outer,const CellGeometry& inner) {
    return outer.depth<=inner.depth && (inner.id>>(2*(inner.depth-outer.depth)))==outer.id;
}
bool intersects(const CellGeometry& a,const CellGeometry& b) {
    return a.x<b.x+b.width && b.x<a.x+a.width && a.y<b.y+b.height && b.y<a.y+a.height;
}
struct Fixture {
    AggregationConfig config;
    AggregationHistory history;
    std::vector<ObservationBatch> raw;
    std::vector<SpatialSelection> outputs;
    std::function<void(const SpatialSelection&)> before;
    CellLocalAggregation engine;
    Fixture(AggregationConfig c, MetricEvaluator evaluator, TemporalAdaptationConfig temporal = timeSettings(),
        SpatialSelectionConfig spatial = {1,4096})
        : config(std::move(c)),history(config,*config.history),engine(config,temporal,spatial,std::move(evaluator),
            [this](const auto& selection) { if(before) before(selection); outputs.push_back(selection); }) {}
    CellObservation person(std::string id,std::string kind="Adult Pedestrian",int leaf=48) const {
        return {std::move(id),std::move(kind),historyCell(config.coverage,leaf,config.coverage.leafDepth)};
    }
    std::vector<CellObservation> people(const std::string& prefix,int count,const std::string& kind,int leaf) const {
        std::vector<CellObservation> rows;
        for(int i=0;i<count;++i) rows.push_back(person(prefix+std::to_string(i),kind,leaf));
        return rows;
    }
    void sample(int time,std::vector<CellObservation> people,bool advance=true,
        ObservationStatus status=ObservationStatus::Measured) {
        ObservationBatch b{config.runId,config.sensorId,static_cast<std::uint64_t>(time/100),time,status,std::move(people)};
        history.append(b);raw.push_back(b);if(advance)engine.advance(time,history);
    }
    void advance(int time) { history.advance(time);engine.advance(time,history); }
    void finish(int time) {history.advance(time);engine.finish(time,history);}
};
void add(std::vector<CellObservation>& rows,std::vector<CellObservation> values) {
    rows.insert(rows.end(),values.begin(),values.end());
}
const SpatialSelection* find(const Fixture& f,int cell,int start,int end) {
    for(const auto& out:f.outputs) if(out.coordinationCell && out.coordinationCell->id==cell
        && out.candidate.startMs==start && out.candidate.endMs==end) return &out;
    return nullptr;
}
const SemanticRepresentation& semantic(const SpatialSelection& out) {
    require(out.selectedCells==1 && out.assessment.cells.size()==1 && out.assessment.cells[0].semantic,
        "Expected one published semantic owner");
    return *out.assessment.cells[0].semantic;
}
std::map<std::string,std::uint64_t> categories(const SpatialSelection& out) {
    std::map<std::string,std::uint64_t> counts;
    for(const auto& b:semantic(out).bins)counts.emplace(b.categoryId,b.distinctContributors);
    return counts;
}
void audit(const Fixture& f,int end) {
    std::uint64_t accounted=0,input=0;
    for(const auto& b:f.raw)input+=b.observations.size();
    for(std::size_t index=0;index<f.outputs.size();++index) {
        const auto& out=f.outputs[index];const auto& c=out.candidate;
        require(out.coordinationCell.has_value(),"Output has no explicit local scope");
        const auto& scope=*out.coordinationCell;
        std::vector<CellObservation> rows;
        for(const auto& b:f.raw)if(c.startMs<=b.observedAtMs && b.observedAtMs<c.endMs)
            for(const auto& r:b.observations)if(contains(scope,r.cell))rows.push_back(r);
        std::set<std::string> identities;for(const auto& r:rows)identities.insert(r.contributorId);
        require(c.counts.observationContributions==rows.size() && c.counts.distinctContributors==identities.size(),
            "Local scope does not equal raw observation/identity union");
        accounted+=rows.size();
        for(std::size_t old=0;old<index;++old) {
            const auto& prior=f.outputs[old];
            require(!(std::max(c.startMs,prior.candidate.startMs)<std::min(c.endMs,prior.candidate.endMs)
                && intersects(scope,*prior.coordinationCell)),"Local source scope was retired twice");
        }
        if(!out.selectedCells)continue;
        require(c.coverage==WindowCoverage::Complete,"Incomplete source coverage was released");
        const auto& value=semantic(out);std::uint64_t represented=0;double maximum=0,weighted=0;
        for(const auto& bin:value.bins) {
            std::set<std::string> people;std::uint64_t observations=0;
            for(const auto& r:rows)if(f.config.semanticTaxonomy->contains(bin.categoryId,
                f.config.semanticTaxonomy->leafForType(r.type))) {++observations;people.insert(r.contributorId);}
            require(bin.observationContributions==observations && bin.distinctContributors==people.size(),
                "Released semantic bin disagrees with original identities");
            represented+=observations;
            const auto loss=f.config.semanticTaxonomy->node(bin.categoryId).loss;
            maximum=std::max(maximum,loss);weighted+=loss*observations;
        }
        require(represented==rows.size() && value.maxLoss==maximum
            && std::abs(value.meanLoss-weighted/represented)<1e-12,"Semantic representation omitted input or misstated its loss");
        for(const auto& row:rows) {
            int bins=0;for(const auto& bin:value.bins)
                bins+=f.config.semanticTaxonomy->contains(bin.categoryId,f.config.semanticTaxonomy->leafForType(row.type));
            require(bins==1,"Raw observation is omitted or represented by overlapping semantic bins");
        }
        double measured=0,expected=0;
        for(AggregationTime time=std::max<AggregationTime>(100,((c.startMs+99)/100)*100);time<c.endMs;time+=100)++expected;
        for(const auto& batch:f.raw)if(c.startMs<=batch.observedAtMs && batch.observedAtMs<c.endMs
            && batch.status==ObservationStatus::Measured)++measured;
        std::uint64_t smallest=std::numeric_limits<std::uint64_t>::max();
        for(const auto& bin:value.bins)smallest=std::min(smallest,bin.distinctContributors);
        for(const auto& check:out.assessment.cells[0].checks) {
            require(check.status==AssessmentStatus::Pass,"Selected owner violates a hard metric bound");
            double observed=0;
            switch(check.requirement.id) {
                case MetricId::ObservationContributions: observed=rows.size();break;
                case MetricId::DistinctContributors: observed=identities.size();break;
                case MetricId::MeanSampleOccupancy: observed=rows.size()/measured;break;
                case MetricId::CellSideM: observed=scope.width;break;
                case MetricId::CellAreaM2: observed=scope.width*scope.height;break;
                case MetricId::WindowDurationMs: observed=c.endMs-c.startMs;break;
                case MetricId::AgeAtEvaluationMs: observed=c.closedAtMs-c.startMs;break;
                case MetricId::PostWindowDelayMs: observed=c.closedAtMs-c.endMs;break;
                case MetricId::MeasuredSampleFraction: observed=measured/expected;break;
                case MetricId::MinCategoryDistinctContributors: observed=smallest;break;
                case MetricId::SemanticMaxLoss: observed=maximum;break;
                case MetricId::SemanticMeanLoss: observed=weighted/represented;break;
                default:throw std::runtime_error("Unexpected unavailable metric in released semantic gate");
            }
            require((!check.requirement.min || observed>=*check.requirement.min)
                && (!check.requirement.max || observed<=*check.requirement.max),
                "Independently recomputed source statistic violates a released hard bound");
        }
        if(out.strategy=="semantic_first")require(out.semanticPriority
            && out.semanticPriority->actualMaxLoss==std::optional<double>{value.maxLoss},
            "Local semantic preference metadata does not describe actual output");
    }
    require(accounted==input,"Finished local stream lost source contributions");
    for(const auto& b:f.raw)for(const auto& r:b.observations) {
        int count=0;for(const auto& out:f.outputs)if(out.candidate.startMs<=b.observedAtMs
            && b.observedAtMs<out.candidate.endMs && contains(*out.coordinationCell,r.cell))++count;
        require(count==1,"A raw contribution has zero or several retired owners");
    }
    const auto owners=f.engine.windows();double area=0;
    for(std::size_t i=0;i<owners.size();++i) {
        require(owners[i].startMs==end,"EOF left an unresolved local prefix");
        area+=owners[i].cell.width*owners[i].cell.height;
        for(std::size_t j=0;j<i;++j)require(!intersects(owners[i].cell,owners[j].cell),"Ownership frontier overlaps");
    }
    require(area==6400,"Ownership frontier has a spatial hole");
}
void independentDefaultAndEmptyRegionalClock() {
    for(const auto strategy:{AdaptationStrategy::SemanticFirst,AdaptationStrategy::TemporalFirst,AdaptationStrategy::SpatialFirst}) {
        auto c=settings(3);
        Fixture f(c,metrics(c,4,10,1,{region(c,193,3,{{MetricId::WindowDurationMs,{},600},
            {MetricId::AgeAtEvaluationMs,{},600}})}),timeSettings(strategy),{3,4096});
        auto rows=f.people("good",4,"Adult Pedestrian",192);add(rows,f.people("bad",1,"Adult Cyclist",208));
        for(int t=100;t<=900;t+=100) {
            f.sample(t,rows);
            if(t==400) {
                require(find(f,192,0,400) && find(f,192,0,400)->selectedCells==1,"Valid owner waited for unrelated semantic failure");
                require(!find(f,208,0,400),"Failed owner was prematurely discarded");
            }
        }
        f.finish(1000);require(find(f,208,0,1000) && !find(f,208,0,1000)->selectedCells,
            "Failed owner's independent window did not reach its own deadline");
        require(find(f,192,400,800),"Empty strict region incorrectly imposed its 600-ms clock on an unrelated owner");
        audit(f,1000);
    }
}
void defaultDoesNotHoldPassingSiblingForSpeculation() {
    auto c=settings();Fixture f(c,metrics(c,4,40,.5));
    auto rows=f.people("good",4,"Adult Pedestrian",48);add(rows,f.people("rare",1,"Scooter",49));
    for(int t:{100,200,300,400})f.sample(t,rows);
    require(find(f,48,0,400) && find(f,48,0,400)->selectedCells==1,
        "Default trigger held a passing sibling for a future-only semantic merge");
    require(!find(f,49,0,400),"Failed sibling lost its independent interval");
    f.finish(500);audit(f,500);
}
void currentLegalRescueMayConsumeAnExactSibling() {
    auto c=settings();Fixture f(c,metrics(c,4,40));
    auto rows=f.people("exact",4,"Adult Pedestrian",48);add(rows,f.people("rare",1,"Adult Cyclist",49));
    for(int t:{100,200,300})f.sample(t,rows);f.advance(400);
    const auto* out=find(f,12,0,400);
    require(out && out->selectedCells && categories(*out)==std::map<std::string,std::uint64_t>{{"road_user",5}},
        "Current complete legal rescue was lost by disclosing its exact sibling first");
    require(!find(f,48,0,400),"Exact sibling was published separately and then reused");
    f.finish(500);audit(f,500);
}
void exactParentBeatsGeneralizedLeavesBeforeDisclosure() {
    auto c=settings();Fixture f(c,metrics(c));std::vector<CellObservation> rows;
    for(int leaf:{48,49}) {add(rows,f.people(std::to_string(leaf)+"p",2,"Adult Pedestrian",leaf));
        add(rows,f.people(std::to_string(leaf)+"c",2,"Adult Cyclist",leaf));}
    for(int t:{100,200,300})f.sample(t,rows);f.advance(400);
    const auto* out=find(f,12,0,400);
    require(out && out->selectedCells==1 && categories(*out)==std::map<std::string,std::uint64_t>{{"adult_pedestrian",4},{"adult_cyclist",4}},
        "Semantic First disclosed generalized fine leaves before their exact parent");
    require(out->candidate.counts.observationContributions==24 && out->candidate.counts.distinctContributors==8,
        "Exact parent lost source support");
    require(out->semanticPriority->attemptedCeilings==1 && out->semanticPriority->lossCeiling==0,
        "Exact-parent semantic metadata is incorrect");
    f.finish(500);audit(f,500);
}
void intermediatePedestrianAndCyclistRemainAvailable() {
    auto c=settings();Fixture f(c,metrics(c,4,20));auto rows=f.people("pa",2,"Adult Pedestrian",48);
    add(rows,f.people("pc",2,"Child Pedestrian",48));add(rows,f.people("ca",2,"Adult Cyclist",52));
    add(rows,f.people("cc",2,"Child Cyclist",52));
    for(int t:{100,200,300})f.sample(t,rows);f.advance(400);
    const auto* p=find(f,48,0,400);const auto* q=find(f,52,0,400);
    require(p && q && categories(*p)==std::map<std::string,std::uint64_t>{{"pedestrian",4}}
        && categories(*q)==std::map<std::string,std::uint64_t>{{"cyclist",4}},"Intermediate semantic tiers were skipped for Root");
    require(p->semanticPriority->lossCeiling==.5 && p->semanticPriority->attemptedCeilings==2,
        "Intermediate-tier metadata is inaccurate");
    f.finish(500);audit(f,500);
}
void explicitSecondaryWaitingAndDefaultOverride() {
    for(bool immediate:{false,true})for(auto secondary:{SemanticSecondaryStrategy::TemporalFirst,SemanticSecondaryStrategy::SpatialFirst}) {
        auto c=settings();Fixture f(c,metrics(c),timeSettings(AdaptationStrategy::SemanticFirst,
            immediate?ReleaseTrigger::PolicySatisfied:ReleaseTrigger::PrioritySatisfied,secondary));
        for(int t=100;t<=600;t+=100) {
            std::vector<CellObservation> rows;
            for(int leaf:{48,49})add(rows,f.people(std::to_string(leaf)+"p",t<600?3:4,"Adult Pedestrian",leaf));
            f.sample(t,rows);
            if(t==400 && !immediate && secondary==SemanticSecondaryStrategy::SpatialFirst)
                require(!f.engine.requestMerge(historyCell(c.coverage,12,1),400,f.history),
                    "Explicit exact-parent request bypassed Spatial secondary's preference wait");
        }
        if(immediate || secondary==SemanticSecondaryStrategy::TemporalFirst)
            require(find(f,12,0,400) && find(f,12,0,400)->selectedCells,"Exact parent was delayed despite current allowed rescue");
        else {
            require(!find(f,12,0,400) && !find(f,48,0,400),"Spatial secondary merged before terminal while explicit preference waiting");
            f.advance(700);require(find(f,48,0,700) && find(f,49,0,700),"Spatial secondary did not release exact fine cells after arrivals");
        }
        f.finish(800);audit(f,800);
    }
}
void lossyHardRescueAndExplicitMergeWaitForTerminal() {
    for(auto secondary:{SemanticSecondaryStrategy::TemporalFirst,SemanticSecondaryStrategy::SpatialFirst}) {
        auto c=settings();Fixture f(c,metrics(c),timeSettings(AdaptationStrategy::SemanticFirst,ReleaseTrigger::PrioritySatisfied,secondary,800));
        auto rows=f.people("a",2,"Adult Pedestrian",48);add(rows,f.people("b",2,"Child Pedestrian",49));
        for(int t=100;t<=700;t+=100) {
            f.sample(t,rows);require(std::none_of(f.outputs.begin(),f.outputs.end(),[](const auto& out){return out.selectedCells;}),
                "A lossy hard-failure parent bypassed explicit semantic preference waiting");
            if(t==400)require(!f.engine.requestMerge(historyCell(c.coverage,12,1),400,f.history),
                "Explicit requestMerge bypassed the semantic preference gate");
        }
        f.advance(800);const auto* out=find(f,12,0,800);
        require(out && categories(*out)==std::map<std::string,std::uint64_t>{{"pedestrian",4}}
            && out->semanticPriority->terminalFallback,"Terminal intermediate rescue failed or omitted metadata");
        f.finish(900);audit(f,900);
    }
}
void aHandoffBoundaryIsAlsoAParentTerminal() {
    auto c=settings();Fixture f(c,metrics(c),timeSettings(AdaptationStrategy::SemanticFirst,
        ReleaseTrigger::PrioritySatisfied,SemanticSecondaryStrategy::SpatialFirst));
    std::vector<CellObservation> rows;
    for(int leaf:{48,49}) {
        add(rows,f.people(std::to_string(leaf)+"a",2,"Adult Pedestrian",leaf));
        add(rows,f.people(std::to_string(leaf)+"c",2,"Child Pedestrian",leaf));
    }
    f.sample(100,rows);
    require(f.engine.scheduleMerge(historyCell(c.coverage,12,1)),"Explicit rendezvous could not be scheduled");
    f.sample(200,rows);f.sample(300,rows);f.advance(400);
    const auto* out=find(f,12,0,400);
    require(out && out->selectedCells && semantic(*out).maxLoss==0,
        "Handoff terminal released generalized children before an exact legal parent rescue");
    require(!find(f,48,0,400) && !find(f,49,0,400),"Handoff parent duplicated child disclosure");
    f.finish(500);audit(f,500);
}
void regionalLossAgeAndValidNeighbourSurvive() {
    auto c=settings();Fixture f(c,metrics(c,4,40,1,{region(c,48,2,{{MetricId::SemanticMaxLoss,{},0},
        {MetricId::AgeAtEvaluationMs,{},600}})}));
    auto rows=f.people("a",2,"Adult Pedestrian",48);add(rows,f.people("c",2,"Child Pedestrian",48));
    add(rows,f.people("other",4,"Adult Pedestrian",49));
    for(int t=100;t<=600;t+=100)f.sample(t,rows);
    require(find(f,49,0,400) && find(f,49,0,400)->selectedCells,
        "Local loss restriction suppressed or delayed a disjoint valid neighbour");
    require(find(f,48,0,600) && !find(f,48,0,600)->selectedCells,
        "Regional exact-only/age limit was bypassed by ancestor generalization");
    f.finish(700);audit(f,700);
}
void repeatedMovingIdentityUsesUnions() {
    auto c=settings();Fixture f(c,metrics(c,4,40,0));
    for(int t=100;t<=300;t+=100) {
        std::vector<CellObservation> rows;for(int n=0;n<4;++n)
            rows.push_back(f.person("moving"+std::to_string(n),"Adult Pedestrian",
                (t==200 ? (n==0 || n==2) : n<2) ? 48 : 49));
        f.sample(t,rows);
    }
    f.advance(400);const auto* out=find(f,12,0,400);
    require(out && out->candidate.counts.distinctContributors==4 && out->candidate.counts.observationContributions==12,
        "Parent summed per-child identities rather than their distinct union");
    f.finish(500);audit(f,500);
}
void mixedDepthAndDifferentRetiredStartsCannotReuseHistory() {
    auto c=settings(3);const auto evaluator=metrics(c,4,40,0);Fixture f(c,evaluator);
    auto rows=f.people("a",2,"Adult Pedestrian",192);add(rows,f.people("b",2,"Adult Pedestrian",193));
    add(rows,f.people("rare",1,"Adult Cyclist",196));
    for(int t:{100,200,300,400})f.sample(t,rows);
    require(find(f,48,0,400) && find(f,48,0,400)->selectedCells,"Aligned mixed-depth ownership did not merge fine support");
    require(!f.engine.requestMerge(historyCell(c.coverage,12,1),400,f.history),
        "An ancestor reused a previously retired descendant prefix");
    add(rows,f.people("arrived",3,"Adult Cyclist",196));
    f.sample(500,rows);f.sample(600,rows);
    const auto retained=f.history.query(historyCell(c.coverage,12,1),0,600);
    require(retained.candidate && evaluator.evaluate(*retained.candidate,600).status==AssessmentStatus::Pass,
        "Different-start test lacks a truthful passing historical parent");
    require(!f.engine.requestMerge(historyCell(c.coverage,12,1),600,f.history),
        "A passing retained historical parent resurrected differently retired starts");
    f.sample(700,rows);f.finish(800);audit(f,800);
}
void missingCoverageEofAndHalfOpenInput() {
    auto c=settings();Fixture f(c,metrics(c,4,20));const auto rows=f.people("a",4,"Adult Pedestrian",48);
    f.sample(100,rows);f.sample(200,{},true,ObservationStatus::Unavailable);f.sample(300,rows);f.sample(400,rows);
    require(find(f,48,0,400) && !find(f,48,0,400)->selectedCells,"Unavailable input was published as complete");
    f.sample(500,rows);f.sample(600,rows);f.finish(650);const auto* out=find(f,48,400,650);
    require(out && out->selectedCells && out->candidate.counts.observationContributions==12
        && out->candidate.truncated,"EOF included missing or excluded endpoint observations");
    audit(f,650);
}
void immutableRetryAndExpiredRetry() {
    for(bool expire:{false,true}) {
        auto c=settings();Fixture f(c,metrics(c,4,20,1,{region(c,48,2,{{MetricId::AgeAtEvaluationMs,{},400}})}));
        auto rows=f.people("a",2,"Adult Pedestrian",48);add(rows,f.people("b",2,"Child Pedestrian",48));
        for(int t:{100,200,300})f.sample(t,rows);
        std::string original;f.before=[&](const auto& out){if(out.selectedCells){
            std::ostringstream s;s<<out.candidate.startMs<<':'<<out.candidate.endMs<<':'<<semantic(out).bins[0].categoryId;
            if(original.empty())original=s.str();else require(original==s.str(),"Retry mutated the immutable semantic output");
            throw std::runtime_error("lost acknowledgement");}};
        f.history.advance(400);rejects([&]{f.engine.advance(400,f.history);},"Failed sink did not interrupt semantic publication");
        require(std::none_of(f.outputs.begin(),f.outputs.end(),[](const auto& out){return out.selectedCells;}),
            "A failed first disclosure committed output state");
        if(expire) {
            f.before={};f.history.advance(500);rejects([&]{f.engine.advance(500,f.history);},"Expired semantic retry was delivered");
            require(std::none_of(f.outputs.begin(),f.outputs.end(),[](const auto& out){return out.selectedCells;}),
                "Expired retry disclosed a payload");
        } else {
            f.before={};f.engine.advance(400,f.history);
            const auto* out=find(f,48,0,400);require(out && categories(*out)==std::map<std::string,std::uint64_t>{{"pedestrian",4}},
                "Retry failed to preserve and acknowledge original semantic scope");
            f.finish(500);audit(f,500);
        }
    }
}
void budgetsAndTaxonomyIdentityFailBeforeDisclosure() {
    auto c=settings(3);Fixture f(c,metrics(c),timeSettings(),{1,1});
    auto rows=f.people("a",2,"Adult Pedestrian",192);add(rows,f.people("b",2,"Adult Cyclist",192));
    for(int t:{100,200,300})f.sample(t,rows);
    f.history.advance(400);rejects([&]{f.engine.advance(400,f.history);},"Semantic ancestor budget failed to bound planning");
    require(f.outputs.empty(),"Resource failure happened after disclosure");
    auto wrong=c;wrong.semanticTaxonomy=catalog();
    rejects([&]{CellLocalAggregation invalid(wrong,timeSettings(),{1,4096},metrics(c),[](const auto&){});},
        "Cell-local semantic evidence accepted a different trusted taxonomy instance");
}
}
int main() {try {
    independentDefaultAndEmptyRegionalClock();defaultDoesNotHoldPassingSiblingForSpeculation();
    currentLegalRescueMayConsumeAnExactSibling();exactParentBeatsGeneralizedLeavesBeforeDisclosure();intermediatePedestrianAndCyclistRemainAvailable();
    explicitSecondaryWaitingAndDefaultOverride();lossyHardRescueAndExplicitMergeWaitForTerminal();
    aHandoffBoundaryIsAlsoAParentTerminal();regionalLossAgeAndValidNeighbourSurvive();repeatedMovingIdentityUsesUnions();
    mixedDepthAndDifferentRetiredStartsCannotReuseHistory();missingCoverageEofAndHalfOpenInput();
    immutableRetryAndExpiredRetry();budgetsAndTaxonomyIdentityFailBeforeDisclosure();
    std::cout<<"PASS: 14 semantic cell-local gates, independent windows, tiered parents, policy bounds, unions, retirement, retries and budgets.\n";
    return 0;
} catch(const std::exception& error) {std::cerr<<"FAIL: "<<error.what()<<'\n';return 1;}}
