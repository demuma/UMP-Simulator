#pragma once

#include "AggregationInput.hpp"
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace ump {
struct SemanticNode {
    std::string id, parent;
    double loss;
    std::vector<std::string> inputTypes;
};
struct SemanticBin {
    std::string categoryId;
    std::uint64_t observationContributions = 0, distinctContributors = 0;
};
struct SemanticRepresentation {
    std::string taxonomyId, taxonomyVersion;
    std::vector<SemanticBin> bins;
    double minimumDistinctContributors = 0, maxLoss = 0, meanLoss = 0;
};

// Immutable, bounded classification tree. Every source label maps to exactly
// one terminal; published categories form a complete partition of observations.
class SemanticTaxonomy {
public:
    SemanticTaxonomy(std::string id, std::string version, std::vector<SemanticNode> nodes);
    const std::string& id() const { return taxonomyId; }
    const std::string& version() const { return taxonomyVersion; }
    const std::string& root() const { return rootId; }
    const std::vector<SemanticNode>& nodes() const { return catalog; }
    const SemanticNode& node(const std::string& id) const;
    const std::string& leafForType(const std::string& raw) const;
    bool contains(const std::string& ancestor, const std::string& node) const;
    void validateEvidence(const SemanticEvidence&, std::uint64_t totalObs, std::uint64_t totalDistinct) const;
    SemanticRepresentation select(const SemanticEvidence&, std::uint64_t totalObs,
        std::uint64_t totalDistinct, std::uint64_t minimumSupport) const;
    // Input is a full-observation representation, never a partially suppressed
    // semantic table. A generalized ancestor crossing the query is unknown.
    std::optional<SemanticBin> exactQuery(const SemanticRepresentation&, const std::string& category) const;
private:
    SemanticRepresentation representation(std::vector<SemanticBin> bins) const;
    std::string taxonomyId, taxonomyVersion, rootId;
    std::vector<SemanticNode> catalog;
    std::map<std::string,std::size_t> indices;
    std::map<std::string,std::vector<std::string>> children;
    std::map<std::string,std::string> terminalByType;
};

// Private identity accounting for one candidate domain/interval. A road user
// keeps one terminal classification in that interval; aliases are permitted.
class SemanticAccumulator {
public:
    explicit SemanticAccumulator(std::shared_ptr<const SemanticTaxonomy> taxonomy);
    void add(const std::string& identity, const std::string& rawType);
    SemanticEvidence evidence() const { return accumulated; }
private:
    std::shared_ptr<const SemanticTaxonomy> taxonomy;
    SemanticEvidence accumulated;
    std::map<std::string,std::string> identityLeaves;
};
} // namespace ump
