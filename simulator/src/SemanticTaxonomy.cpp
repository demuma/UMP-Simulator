#include "SemanticTaxonomy.hpp"
#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <set>
#include <stdexcept>
#include <utility>

namespace ump {
namespace {
constexpr std::uint64_t exactMaximum=9007199254740991ULL;
void boundedText(const std::string& value,std::size_t maximum,const char* context) {
    if (value.empty() || value.size()>maximum
        || std::any_of(value.begin(),value.end(),[](unsigned char c) { return c<32 || c==127; }))
        throw std::invalid_argument(std::string("Invalid semantic ")+context);
}
void validCounts(std::uint64_t observations,std::uint64_t distinct) {
    if (observations>exactMaximum || distinct>observations || (!distinct && observations))
        throw std::invalid_argument("Invalid exact semantic observation/identity counts");
}
std::uint64_t checkedSum(std::uint64_t left,std::uint64_t right) {
    if (right>exactMaximum || left>exactMaximum-right)
        throw std::invalid_argument("Semantic counts exceed the exact metric range");
    return left+right;
}
bool close(double left,double right) {
    return std::isfinite(left) && std::abs(left-right)<=1e-12;
}
}

SemanticTaxonomy::SemanticTaxonomy(std::string id,std::string version,std::vector<SemanticNode> nodes)
    : taxonomyId(std::move(id)),taxonomyVersion(std::move(version)),catalog(std::move(nodes)) {
    boundedText(taxonomyId,128,"taxonomy ID");
    boundedText(taxonomyVersion,128,"taxonomy version");
    if (catalog.empty() || catalog.size()>256)
        throw std::invalid_argument("Semantic taxonomy requires 1--256 nodes");
    std::sort(catalog.begin(),catalog.end(),[](const auto& a,const auto& b) { return a.id<b.id; });
    std::size_t roots=0,labels=0;
    for (std::size_t i=0;i<catalog.size();++i) {
        const auto& item=catalog[i];
        boundedText(item.id,128,"node ID");
        if (!item.parent.empty()) boundedText(item.parent,128,"parent ID");
        if (!indices.emplace(item.id,i).second)
            throw std::invalid_argument("Duplicate semantic node ID");
        children.emplace(item.id,std::vector<std::string>{});
        if (!std::isfinite(item.loss) || item.loss<0 || item.loss>1)
            throw std::invalid_argument("Semantic node loss must be finite and within [0,1]");
        if (item.parent.empty()) { ++roots; rootId=item.id; }
        if (item.inputTypes.size()>4096-labels)
            throw std::invalid_argument("Semantic taxonomy exceeds 4096 input labels");
        labels+=item.inputTypes.size();
        for (const auto& type : item.inputTypes) {
            boundedText(type,256,"input type");
            if (!terminalByType.emplace(type,item.id).second)
                throw std::invalid_argument("Semantic input type is mapped more than once");
        }
    }
    if (roots!=1) throw std::invalid_argument("Semantic taxonomy needs exactly one root");
    if (node(rootId).loss!=1) throw std::invalid_argument("Semantic root loss must be one");
    for (const auto& item : catalog) if (!item.parent.empty()) {
        const auto parent=indices.find(item.parent);
        if (parent==indices.end()) throw std::invalid_argument("Unknown semantic parent");
        if (catalog[parent->second].loss<item.loss)
            throw std::invalid_argument("Semantic ancestor loss cannot be below descendant loss");
        children.at(item.parent).push_back(item.id);
    }
    std::set<std::string> reached;
    std::function<void(const std::string&,std::size_t)> visit=[&](const std::string& id,std::size_t depth) {
        if (depth>32 || !reached.insert(id).second)
            throw std::invalid_argument("Semantic taxonomy has a cycle or exceeds depth 32");
        for (const auto& child : children.at(id)) visit(child,depth+1);
    };
    visit(rootId,0);
    if (reached.size()!=catalog.size())
        throw std::invalid_argument("Semantic taxonomy contains a disconnected component or cycle");
    for (const auto& item : catalog) {
        if (children.at(item.id).empty()) {
            if (item.loss!=0 || item.inputTypes.empty())
                throw std::invalid_argument("Every semantic terminal needs zero loss and at least one input type");
        } else if (!item.inputTypes.empty())
            throw std::invalid_argument("Raw input types may map only to semantic terminals");
    }
}

const SemanticNode& SemanticTaxonomy::node(const std::string& id) const {
    const auto found=indices.find(id);
    if (found==indices.end()) throw std::invalid_argument("Unknown semantic category: "+id);
    return catalog[found->second];
}
const std::string& SemanticTaxonomy::leafForType(const std::string& raw) const {
    const auto found=terminalByType.find(raw);
    if (found==terminalByType.end()) throw std::invalid_argument("Unmapped semantic input type: "+raw);
    return found->second;
}
bool SemanticTaxonomy::contains(const std::string& ancestor,const std::string& descendant) const {
    node(ancestor);
    const SemanticNode* current=&node(descendant);
    for (;;) {
        if (current->id==ancestor) return true;
        if (current->parent.empty()) return false;
        current=&node(current->parent);
    }
}

void SemanticTaxonomy::validateEvidence(const SemanticEvidence& evidence,std::uint64_t totalObs,
    std::uint64_t totalDistinct) const {
    validCounts(totalObs,totalDistinct);
    if (evidence.taxonomyId!=taxonomyId || evidence.taxonomyVersion!=taxonomyVersion
        || evidence.nodes.size()!=catalog.size())
        throw std::invalid_argument("Semantic evidence has a different taxonomy or incomplete catalog");
    for (const auto& item : evidence.nodes) node(item.first);
    for (const auto& item : catalog) {
        const auto found=evidence.nodes.find(item.id);
        if (found==evidence.nodes.end()) throw std::invalid_argument("Semantic evidence omitted a taxonomy node");
        const auto& value=found->second;
        validCounts(value.observationContributions,value.distinctContributors);
        if (value.observationContributions>totalObs || value.distinctContributors>totalDistinct)
            throw std::invalid_argument("Semantic category exceeds its original candidate totals");
        if (!children.at(item.id).empty()) {
            std::uint64_t observations=0,distinct=0;
            for (const auto& child : children.at(item.id)) {
                const auto at=evidence.nodes.find(child);
                if (at==evidence.nodes.end()) throw std::invalid_argument("Semantic evidence omitted a child");
                observations=checkedSum(observations,at->second.observationContributions);
                distinct=checkedSum(distinct,at->second.distinctContributors);
            }
            if (observations!=value.observationContributions || distinct!=value.distinctContributors)
                throw std::invalid_argument("Semantic evidence violates the stable-type child partition");
        }
    }
    const auto& rootCounts=evidence.nodes.at(rootId);
    if (rootCounts.observationContributions!=totalObs || rootCounts.distinctContributors!=totalDistinct)
        throw std::invalid_argument("Semantic root does not equal candidate support");
}

SemanticRepresentation SemanticTaxonomy::representation(std::vector<SemanticBin> bins) const {
    std::sort(bins.begin(),bins.end(),[](const auto& a,const auto& b) { return a.categoryId<b.categoryId; });
    SemanticRepresentation result{taxonomyId,taxonomyVersion,std::move(bins)};
    if (result.bins.empty()) return result;
    std::uint64_t total=0,minimum=exactMaximum;
    long double weighted=0;
    for (const auto& bin : result.bins) {
        const auto& item=node(bin.categoryId);
        total=checkedSum(total,bin.observationContributions);
        minimum=std::min(minimum,bin.distinctContributors);
        result.maxLoss=std::max(result.maxLoss,item.loss);
        weighted+=static_cast<long double>(bin.observationContributions)*item.loss;
    }
    if (!total) throw std::invalid_argument("Semantic representation contains zero-observation bins");
    result.minimumDistinctContributors=static_cast<double>(minimum);
    result.meanLoss=static_cast<double>(weighted/total);
    return result;
}

const char* semanticGeneralizationModeName(SemanticGeneralizationMode mode) {
    switch (mode) {
        case SemanticGeneralizationMode::Enabled: return "enabled";
        case SemanticGeneralizationMode::ExactOnly: return "exact_only";
    }
    throw std::invalid_argument("Unknown semantic generalization mode");
}

SemanticRepresentation SemanticTaxonomy::select(const SemanticEvidence& evidence,std::uint64_t totalObs,
    std::uint64_t totalDistinct,std::uint64_t minimumSupport,SemanticGeneralizationMode mode) const {
    semanticGeneralizationModeName(mode);
    validateEvidence(evidence,totalObs,totalDistinct);
    if (!minimumSupport || minimumSupport>exactMaximum) throw std::invalid_argument("Semantic support threshold must be positive and within the exact metric range");
    if (!totalObs) return representation({});
    if (mode == SemanticGeneralizationMode::ExactOnly) {
        std::vector<SemanticBin> bins;
        for (const auto& terminal : catalog) {
            if (!children.at(terminal.id).empty()) continue;
            const auto& counts=evidence.nodes.at(terminal.id);
            if (counts.observationContributions)
                bins.push_back({terminal.id,counts.observationContributions,counts.distinctContributors});
        }
        // Do not omit a rare leaf or promote it to an ancestor. Existing hard
        // category-support checks decide whether the whole footprint can publish.
        return representation(std::move(bins));
    }
    struct Cut { bool passes; std::vector<SemanticBin> bins; };
    std::function<Cut(const std::string&)> visit=[&](const std::string& id)->Cut {
        const auto& value=evidence.nodes.at(id);
        if (!value.observationContributions) return {true,{}};
        if (!children.at(id).empty()) {
            bool all=true;
            std::vector<SemanticBin> bins;
            for (const auto& child : children.at(id)) {
                auto cut=visit(child);
                all=all && cut.passes;
                bins.insert(bins.end(),cut.bins.begin(),cut.bins.end());
            }
            if (all) return {true,std::move(bins)};
        }
        if (value.distinctContributors>=minimumSupport)
            return {true,{{id,value.observationContributions,value.distinctContributors}}};
        return {false,{}};
    };
    auto cut=visit(rootId);
    if (!cut.passes) cut.bins={{rootId,totalObs,totalDistinct}};
    return representation(std::move(cut.bins));
}

std::vector<SemanticSuppressionCandidate> SemanticTaxonomy::suppressionCandidates(
    const SemanticEvidence& evidence, std::uint64_t totalObs, std::uint64_t totalDistinct,
    std::uint64_t minimumSupport) const {
    validateEvidence(evidence,totalObs,totalDistinct);
    if (!minimumSupport || minimumSupport>exactMaximum)
        throw std::invalid_argument("Semantic suppression support must be positive and exact");
    const auto ordinary=select(evidence,totalObs,totalDistinct,minimumSupport);
    if (!totalObs || ordinary.maxLoss==0) return {};
    std::set<double> tiers{0};
    for (const auto& item : catalog) if (item.loss<ordinary.maxLoss) tiers.insert(item.loss);
    std::vector<SemanticSuppressionCandidate> output;
    std::set<std::vector<std::string>> seen;
    for (double tier : tiers) {
        struct Cut { bool complete; std::vector<SemanticBin> bins; std::vector<std::string> removed; };
        std::function<Cut(const std::string&)> visit=[&](const std::string& id)->Cut {
            const auto& value=evidence.nodes.at(id);
            if (!value.observationContributions) return {true,{},{}};
            Cut result{true,{},{}};
            for (const auto& child : children.at(id)) {
                auto cut=visit(child);
                result.complete &= cut.complete;
                result.bins.insert(result.bins.end(),cut.bins.begin(),cut.bins.end());
                result.removed.insert(result.removed.end(),cut.removed.begin(),cut.removed.end());
            }
            if (!children.at(id).empty() && result.complete) return result;
            if (value.distinctContributors>=minimumSupport && node(id).loss<=tier)
                return {true,{{id,value.observationContributions,value.distinctContributors}},{}};
            if (children.at(id).empty()) return {false,{}, {id}};
            return result;
        };
        auto cut=visit(rootId);
        std::sort(cut.removed.begin(),cut.removed.end());
        if (cut.removed.empty() || cut.bins.empty() || !seen.insert(cut.removed).second) continue;
        auto retained=evidence;
        for (const auto& leaf : cut.removed) {
            const auto removed=evidence.nodes.at(leaf);
            const SemanticNode* at=&node(leaf);
            for (;;) {
                auto& counts=retained.nodes.at(at->id);
                counts.observationContributions-=removed.observationContributions;
                counts.distinctContributors-=removed.distinctContributors;
                if (at->parent.empty()) break;
                at=&node(at->parent);
            }
        }
        const auto totals=retained.nodes.at(rootId);
        validateEvidence(retained,totals.observationContributions,totals.distinctContributors);
        auto selected=representation(std::move(cut.bins));
        output.push_back({std::move(retained),std::move(selected),std::move(cut.removed)});
    }
    return output;
}

std::optional<SemanticBin> SemanticTaxonomy::exactQuery(const SemanticRepresentation& input,
    const std::string& category) const {
    node(category);
    if (input.taxonomyId!=taxonomyId || input.taxonomyVersion!=taxonomyVersion || input.bins.size()>catalog.size())
        throw std::invalid_argument("Semantic query representation has a different taxonomy or too many bins");
    for (std::size_t i=0;i<input.bins.size();++i) {
        const auto& bin=input.bins[i];
        node(bin.categoryId);
        validCounts(bin.observationContributions,bin.distinctContributors);
        if (!bin.observationContributions) throw std::invalid_argument("Semantic public bins must contain observations");
        for (std::size_t j=0;j<i;++j)
            if (contains(bin.categoryId,input.bins[j].categoryId) || contains(input.bins[j].categoryId,bin.categoryId))
                throw std::invalid_argument("Semantic representation has duplicate or overlapping categories");
    }
    const auto calculated=representation(input.bins);
    if (input.minimumDistinctContributors!=calculated.minimumDistinctContributors
        || !close(input.maxLoss,calculated.maxLoss) || !close(input.meanLoss,calculated.meanLoss))
        throw std::invalid_argument("Semantic representation metric summaries contradict its bins");
    SemanticBin answer{category,0,0};
    for (const auto& bin : input.bins) {
        if (contains(category,bin.categoryId)) {
            answer.observationContributions=checkedSum(answer.observationContributions,bin.observationContributions);
            answer.distinctContributors=checkedSum(answer.distinctContributors,bin.distinctContributors);
        } else if (contains(bin.categoryId,category)) {
            // An ancestor along a unary chain has the same terminal domain.
            // It straddles the query only if another possible terminal lies
            // outside the requested category, irrespective of hidden counts.
            const bool straddles=std::any_of(catalog.begin(),catalog.end(),[&](const auto& item) {
                return children.at(item.id).empty() && contains(bin.categoryId,item.id)
                    && !contains(category,item.id);
            });
            if (straddles) return std::nullopt;
            answer.observationContributions=checkedSum(answer.observationContributions,bin.observationContributions);
            answer.distinctContributors=checkedSum(answer.distinctContributors,bin.distinctContributors);
        }
    }
    return answer;
}

SemanticAccumulator::SemanticAccumulator(std::shared_ptr<const SemanticTaxonomy> configured)
    : taxonomy(std::move(configured)) {
    if (!taxonomy) throw std::invalid_argument("Semantic accumulator requires a taxonomy");
    accumulated.taxonomyId=taxonomy->id(); accumulated.taxonomyVersion=taxonomy->version();
    for (const auto& node : taxonomy->nodes()) accumulated.nodes.emplace(node.id,SemanticNodeCounts{});
}
void SemanticAccumulator::add(const std::string& identity,const std::string& rawType) {
    if (identity.empty()) throw std::invalid_argument("Semantic contributor identity cannot be empty");
    const auto& leaf=taxonomy->leafForType(rawType);
    const auto known=identityLeaves.find(identity);
    if (known!=identityLeaves.end() && known->second!=leaf)
        throw std::invalid_argument("One semantic candidate cannot assign an identity to multiple terminal types");
    const bool newIdentity=known==identityLeaves.end();
    std::vector<const SemanticNode*> path;
    const SemanticNode* current=&taxonomy->node(leaf);
    for (;;) {
        const auto& value=accumulated.nodes.at(current->id);
        if (value.observationContributions==exactMaximum || (newIdentity && value.distinctContributors==exactMaximum))
            throw std::length_error("Semantic accumulator exceeds exact count range");
        path.push_back(current);
        if (current->parent.empty()) break;
        current=&taxonomy->node(current->parent);
    }
    // Allocate the new identity before changing any counts. All node entries
    // exist already, so a rejected type change leaves the evidence unchanged.
    if (newIdentity) identityLeaves.emplace(identity,leaf);
    for (const auto* item : path) {
        auto& value=accumulated.nodes.at(item->id);
        ++value.observationContributions;
        if (newIdentity) ++value.distinctContributors;
    }
}
} // namespace ump
