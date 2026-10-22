#include "SemanticTaxonomy.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ump;
void require(bool value,const char* message) { if (!value) throw std::runtime_error(message); }
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected semantic validation rejection");
}
bool near(double a,double b) { return std::abs(a-b)<1e-12; }
std::vector<SemanticNode> nodes() {
    return {{"road_user","",1,{}}, {"pedestrian","road_user",.5,{}},
        {"adult_pedestrian","pedestrian",0,{"AdultPedestrian","adult_ped_alias"}},
        {"child_pedestrian","pedestrian",0,{"ChildPedestrian"}},
        {"cyclist","road_user",.5,{}},
        {"adult_cyclist","cyclist",0,{"AdultCyclist","adult_cycle_alias"}},
        {"child_cyclist","cyclist",0,{"ChildCyclist"}}};
}
std::shared_ptr<const SemanticTaxonomy> taxonomy() {
    return std::make_shared<const SemanticTaxonomy>("road-users","1",nodes());
}
void addPeople(SemanticAccumulator& accumulator,const std::string& prefix,const std::string& type,
    int count,int observations=1) {
    for (int observation=0;observation<observations;++observation)
        for (int i=0;i<count;++i) accumulator.add(prefix+std::to_string(i),type);
}
std::vector<std::string> categories(const SemanticRepresentation& result) {
    std::vector<std::string> ids;
    for (const auto& bin : result.bins) ids.push_back(bin.categoryId);
    return ids;
}
void sameEvidence(const SemanticEvidence& a,const SemanticEvidence& b) {
    require(a.taxonomyId==b.taxonomyId && a.taxonomyVersion==b.taxonomyVersion
        && a.nodes.size()==b.nodes.size(),"Rejected observation changed evidence metadata");
    for (const auto& item : a.nodes) {
        const auto found=b.nodes.find(item.first);
        require(found!=b.nodes.end() && item.second.observationContributions==found->second.observationContributions
            && item.second.distinctContributors==found->second.distinctContributors,
            "Rejected observation changed exact taxonomy counts");
    }
}
void rareCyclistNeedsWholeRoot() {
    const auto t=taxonomy(); SemanticAccumulator observations(t);
    addPeople(observations,"p","AdultPedestrian",19,3);
    addPeople(observations,"c","AdultCyclist",1,3);
    const auto evidence=observations.evidence();
    t->validateEvidence(evidence,60,20);
    const auto output=t->select(evidence,60,20,5);
    require(categories(output)==std::vector<std::string>{"road_user"}
        && output.bins[0].observationContributions==60 && output.bins[0].distinctContributors==20
        && output.minimumDistinctContributors==20 && output.maxLoss==1 && output.meanLoss==1,
        "19 pedestrians and one cyclist were not generalized as one complete root category");
    require(!t->exactQuery(output,"cyclist") && !t->exactQuery(output,"pedestrian"),
        "Root generalization guessed a hidden mode count");
    const auto total=t->exactQuery(output,"road_user");
    require(total && total->observationContributions==60 && total->distinctContributors==20,
        "Root query lost original occupancy/support");
    const auto detailed=t->select(evidence,60,20,1);
    require(categories(detailed)==std::vector<std::string>({"adult_cyclist","adult_pedestrian"})
        && detailed.minimumDistinctContributors==1 && detailed.maxLoss==0 && detailed.meanLoss==0,
        "Already valid terminal labels were generalized unnecessarily");
    // Support and loss are independent constraints: this representation cannot
    // pass an application that requires max loss <= .5.
    require(output.maxLoss>.5,"Root representation fabricated an acceptable tighter semantic loss");
}
void childAdultCyclistsAndInsufficientRoot() {
    const auto t=taxonomy(); SemanticAccumulator observations(t);
    addPeople(observations,"adult","AdultCyclist",2,10);
    addPeople(observations,"child","ChildCyclist",2,10);
    const auto evidence=observations.evidence();
    const auto output=t->select(evidence,40,4,4);
    require(categories(output)==std::vector<std::string>{"cyclist"}
        && output.minimumDistinctContributors==4 && output.maxLoss==.5 && output.meanLoss==.5,
        "2 adult and 2 child cyclists did not produce the finest valid cyclist category");
    require(!t->exactQuery(output,"adult_cyclist"),"Generalized cyclist count invented an age breakdown");
    const auto cyclists=t->exactQuery(output,"cyclist");
    require(cyclists && cyclists->observationContributions==40 && cyclists->distinctContributors==4,
        "Cyclist query confused contributions with distinct people");
    const auto absent=t->exactQuery(output,"pedestrian");
    require(absent && absent->observationContributions==0 && absent->distinctContributors==0,
        "Disjoint measured-absent category did not have an exact zero");
    const auto impossible=t->select(evidence,40,4,5);
    require(categories(impossible)==std::vector<std::string>{"road_user"}
        && impossible.minimumDistinctContributors==4 && impossible.minimumDistinctContributors<5,
        "Repeated observations or root fallback fabricated a fifth road user");
}
void mixedResolutionMeanLossAndQueries() {
    const auto t=taxonomy(); SemanticAccumulator observations(t);
    addPeople(observations,"a","AdultCyclist",2);
    addPeople(observations,"c","ChildCyclist",2);
    addPeople(observations,"p","AdultPedestrian",5);
    const auto output=t->select(observations.evidence(),9,9,4);
    require(categories(output)==std::vector<std::string>({"adult_pedestrian","cyclist"})
        && output.minimumDistinctContributors==4 && output.maxLoss==.5 && near(output.meanLoss,2.0/9),
        "Mixed-resolution cut has incorrect support or observation-weighted semantic loss");
    const auto p=t->exactQuery(output,"pedestrian");
    const auto root=t->exactQuery(output,"road_user");
    require(p && p->distinctContributors==5 && root && root->distinctContributors==9
        && root->observationContributions==9,"Exact rollup over disjoint semantic bins failed");
    require(!t->exactQuery(output,"child_cyclist"),"Straddled query was returned as zero instead of unavailable");
    auto shuffled=nodes(); std::reverse(shuffled.begin(),shuffled.end());
    SemanticTaxonomy reordered("road-users","1",shuffled);
    require(categories(reordered.select(observations.evidence(),9,9,4))==categories(output),
        "Taxonomy declaration order changed the deterministic cut");
}
void aliasesRepeatedIdentityAndRejectedChanges() {
    const auto t=taxonomy(); SemanticAccumulator observations(t);
    observations.add("moving-cyclist","AdultCyclist");
    observations.add("moving-cyclist","adult_cycle_alias");
    observations.add("second-cyclist","AdultCyclist");
    observations.add("moving-cyclist","AdultCyclist");
    const auto before=observations.evidence();
    t->validateEvidence(before,4,2);
    require(before.nodes.at("cyclist").distinctContributors==2
        && before.nodes.at("adult_cyclist").observationContributions==4,
        "Repeated observations/aliases inflated exact identity unions");
    rejects([&] { observations.add("moving-cyclist","ChildCyclist"); });
    sameEvidence(before,observations.evidence());
    rejects([&] { observations.add("new","UnmappedVehicle"); });
    sameEvidence(before,observations.evidence());
    rejects([&] { observations.add("","AdultCyclist"); });
    sameEvidence(before,observations.evidence());
    require(t->leafForType("adult_cycle_alias")=="adult_cyclist"
        && t->contains("cyclist","adult_cyclist") && t->contains("cyclist","cyclist")
        && !t->contains("pedestrian","adult_cyclist"),"Taxonomy lookup/ancestry is inconsistent");
    rejects([&] { t->node("missing"); });
    rejects([&] { t->contains("missing","cyclist"); });
    rejects([&] { SemanticAccumulator invalid(nullptr); });
}
void emptyEvidenceAndMalformedEvidence() {
    const auto t=taxonomy(); SemanticAccumulator empty(t);
    const auto zero=empty.evidence(); t->validateEvidence(zero,0,0);
    const auto representation=t->select(zero,0,0,5);
    require(representation.bins.empty() && representation.minimumDistinctContributors==0
        && representation.maxLoss==0 && representation.meanLoss==0,"Empty evidence invented semantic support or loss");
    const auto query=t->exactQuery(representation,"cyclist");
    require(query && query->distinctContributors==0,"Empty complete representation has no exact zero");
    SemanticAccumulator observations(t); addPeople(observations,"a","AdultCyclist",2,3);
    const auto valid=observations.evidence();
    const auto bad=[&](const auto& mutation) {
        auto evidence=valid; mutation(evidence);
        rejects([&] { t->validateEvidence(evidence,6,2); });
        rejects([&] { t->select(evidence,6,2,2); });
    };
    bad([](auto& e) { e.taxonomyVersion="other"; });
    bad([](auto& e) { e.nodes.erase("child_pedestrian"); });
    bad([](auto& e) { e.nodes.emplace("unknown",SemanticNodeCounts{}); });
    bad([](auto& e) { e.nodes.at("adult_cyclist").distinctContributors=3; });
    bad([](auto& e) { e.nodes.at("adult_cyclist").observationContributions=5; });
    bad([](auto& e) { e.nodes.at("road_user").distinctContributors=1; });
    bad([](auto& e) { e.nodes.at("pedestrian")={1,0}; });
    rejects([&] { t->validateEvidence(valid,7,2); });
    rejects([&] { t->validateEvidence(valid,6,7); });
    rejects([&] { t->select(valid,6,2,9007199254740992ULL); });
}
void invalidTreesAndResourceBounds() {
    const auto invalid=[](std::vector<SemanticNode> catalog) {
        rejects([&] { SemanticTaxonomy t("id","1",catalog); });
    };
    invalid({});
    auto n=nodes(); n.push_back(n.back()); invalid(n);
    n=nodes(); n[1].parent.clear(); invalid(n);
    n=nodes(); n[1].parent="missing"; invalid(n);
    n=nodes(); n[1].parent="cyclist"; n[4].parent="pedestrian"; invalid(n);
    n=nodes(); n[1].inputTypes={"nonterminal"}; invalid(n);
    n=nodes(); n[2].inputTypes.clear(); invalid(n);
    n=nodes(); n[3].inputTypes={"AdultPedestrian"}; invalid(n);
    n=nodes(); n[0].loss=.9; invalid(n);
    n=nodes(); n[2].loss=.1; invalid(n);
    n=nodes(); n[4].loss=std::numeric_limits<double>::quiet_NaN(); invalid(n);
    n=nodes(); n[4].loss=1.01; invalid(n);
    n=nodes(); n[1].loss=-.1; invalid(n);
    n=nodes(); n[2].id=std::string(129,'x'); invalid(n);
    n=nodes(); n[2].inputTypes={std::string(257,'x')}; invalid(n);
    n=nodes(); n[2].inputTypes={"line\nbreak"}; invalid(n);
    rejects([&] { SemanticTaxonomy t("","1",nodes()); });
    rejects([&] { SemanticTaxonomy t("id",std::string(129,'v'),nodes()); });
    n={{"root","",1,{}}};
    for (int i=0;i<255;++i) n.push_back({"leaf"+std::to_string(i),"root",0,{"type"+std::to_string(i)}});
    SemanticTaxonomy maximum("id","1",n);
    require(maximum.nodes().size()==256,"Exact node limit rejected a valid taxonomy");
    n.push_back({"overflow","root",0,{"overflow"}}); invalid(n);
    const auto chain=[](int depth) {
        std::vector<SemanticNode> out{{"root","",1,{}}};
        for (int i=1;i<=depth;++i) out.push_back({"n"+std::to_string(i),i==1?"root":"n"+std::to_string(i-1),
            i==depth?0:.5,i==depth?std::vector<std::string>{"terminal"}:std::vector<std::string>{}});
        return out;
    };
    SemanticTaxonomy deep("id","1",chain(32));
    invalid(chain(33));
    n={{"root","",1,{}},{"leaf","root",0,{}}};
    for (int i=0;i<4096;++i) n[1].inputTypes.push_back("alias"+std::to_string(i));
    SemanticTaxonomy labels("id","1",n);
    require(labels.leafForType("alias4095")=="leaf","Exact input-label limit failed");
    n[1].inputTypes.push_back("overflow"); invalid(n);
    invalid({{"root","",1,{}},{"internal","root",.2,{}},{"deeper","internal",.5,{}},
        {"terminal","deeper",0,{"type"}}});
}
void queryRejectsMalformedCutAndHandlesUnaryDomain() {
    const auto t=taxonomy(); SemanticAccumulator observations(t);
    addPeople(observations,"a","AdultCyclist",2); addPeople(observations,"c","ChildCyclist",2);
    rejects([&] { t->select(observations.evidence(),4,4,0); });
    const auto valid=t->select(observations.evidence(),4,4,4);
    const auto bad=[&](const auto& mutation) {
        auto output=valid; mutation(output);
        rejects([&] { t->exactQuery(output,"road_user"); });
    };
    bad([](auto& r) { r.bins.push_back(r.bins[0]); });
    bad([](auto& r) { r.bins.push_back({"adult_cyclist",2,2}); });
    bad([](auto& r) { r.bins[0].categoryId="unknown"; });
    bad([](auto& r) { r.bins[0].distinctContributors=5; });
    bad([](auto& r) { r.taxonomyId="other"; });
    bad([](auto& r) { r.meanLoss=0; });
    bad([](auto& r) { r.minimumDistinctContributors=5; });
    bad([](auto& r) { r.maxLoss=std::numeric_limits<double>::infinity(); });
    bad([](auto& r) { r.bins.push_back({"child_pedestrian",0,0}); });
    rejects([&] { t->exactQuery(valid,"unknown"); });
    auto unary=std::make_shared<const SemanticTaxonomy>("unary","1",std::vector<SemanticNode>{
        {"root","",1,{}},{"cyclist","root",.5,{}},{"adult","cyclist",0,{"a"}}});
    SemanticAccumulator one(unary); one.add("person","a");
    const auto fallback=unary->select(one.evidence(),1,1,2);
    const auto exact=unary->exactQuery(fallback,"cyclist");
    require(exact && exact->distinctContributors==1,
        "Unary ancestor was called straddling despite an identical possible terminal domain");
}
}
int main() {
    try {
        rareCyclistNeedsWholeRoot();
        childAdultCyclistsAndInsufficientRoot();
        mixedResolutionMeanLossAndQueries();
        aliasesRepeatedIdentityAndRejectedChanges();
        emptyEvidenceAndMalformedEvidence();
        invalidTreesAndResourceBounds();
        queryRejectsMalformedCutAndHandlesUnaryDomain();
        std::cout << "Semantic taxonomy passed: exact support, complete cuts, bounded loss, query unknowns, "
            "aliases/stable identity types, malformed evidence and bounded graph validation.\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
