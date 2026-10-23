#include "SemanticTaxonomy.hpp"

#include <cmath>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ump;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

std::shared_ptr<const SemanticTaxonomy> taxonomy() {
    return std::make_shared<const SemanticTaxonomy>(
        "ump-mapped-pedestrian-release", "1", std::vector<SemanticNode>{
            {"road_user", "", 1, {}},
            {"pedestrian", "road_user", .5, {}},
            {"adult_pedestrian", "pedestrian", 0, {"Adult Pedestrian"}},
            {"child_pedestrian", "pedestrian", 0, {"Child Pedestrian"}},
            {"senior_pedestrian", "pedestrian", 0, {"Senior Pedestrian"}},
            {"pedestrian_with_stroller", "pedestrian", 0, {"Pedestrian With Stroller"}},
            {"pedestrian_with_mobility_aid", "pedestrian", 0, {"Pedestrian With Mobility Aid"}},
        });
}

void addPeople(SemanticAccumulator& accumulator, const std::string& prefix,
    const std::string& type, unsigned people, unsigned observationsPerPerson) {
    for (unsigned observation = 0; observation < observationsPerPerson; ++observation)
        for (unsigned person = 0; person < people; ++person)
            accumulator.add(prefix + std::to_string(person), type);
}

std::vector<std::string> categories(const SemanticRepresentation& representation) {
    std::vector<std::string> result;
    for (const auto& bin : representation.bins) result.push_back(bin.categoryId);
    return result;
}

void sparseEquipmentProfilesGeneralizeToPedestrian() {
    const auto configured = taxonomy();
    SemanticAccumulator accumulator(configured);
    addPeople(accumulator, "adult-track-", "Adult Pedestrian", 2, 3);
    addPeople(accumulator, "stroller-track-", "Pedestrian With Stroller", 1, 3);
    addPeople(accumulator, "aid-track-", "Pedestrian With Mobility Aid", 1, 3);

    const auto evidence = accumulator.evidence();
    configured->validateEvidence(evidence, 12, 4);
    const auto output = configured->select(evidence, 12, 4, 4);
    require(categories(output) == std::vector<std::string>{"pedestrian"},
        "Sparse adult, stroller and mobility-aid profiles did not share the pedestrian ancestor");
    require(output.bins.front().observationContributions == 12
            && output.bins.front().distinctContributors == 4,
        "Pedestrian generalization changed observation or distinct-track support");
    require(output.minimumDistinctContributors == 4
            && output.maxLoss == .5 && output.meanLoss == .5,
        "Pedestrian generalization has incorrect support or configured abstraction loss");
    require(!configured->exactQuery(output, "adult_pedestrian")
            && !configured->exactQuery(output, "pedestrian_with_stroller")
            && !configured->exactQuery(output, "pedestrian_with_mobility_aid"),
        "A generalized pedestrian release exposed a hidden subtype count");

    const auto pedestrians = configured->exactQuery(output, "pedestrian");
    const auto all = configured->exactQuery(output, "road_user");
    require(pedestrians && all && pedestrians->observationContributions == 12
            && pedestrians->distinctContributors == 4
            && all->observationContributions == 12 && all->distinctContributors == 4,
        "Pedestrian and Road User rollup queries failed exact count conservation");
}

void sufficientSubtypeSupportPreservesAllThreeCategories() {
    const auto configured = taxonomy();
    SemanticAccumulator accumulator(configured);
    addPeople(accumulator, "adult-track-", "Adult Pedestrian", 4, 3);
    addPeople(accumulator, "stroller-track-", "Pedestrian With Stroller", 4, 3);
    addPeople(accumulator, "aid-track-", "Pedestrian With Mobility Aid", 4, 3);

    const auto output = configured->select(accumulator.evidence(), 36, 12, 4);
    require(categories(output) == std::vector<std::string>{
        "adult_pedestrian", "pedestrian_with_mobility_aid", "pedestrian_with_stroller"},
        "Adequately supported pedestrian variants were unnecessarily generalized");
    require(output.minimumDistinctContributors == 4 && output.maxLoss == 0 && output.meanLoss == 0,
        "Retained terminal categories were assigned nonzero abstraction loss");
    std::uint64_t observations = 0, distinct = 0;
    for (const auto& bin : output.bins) {
        require(bin.observationContributions == 12 && bin.distinctContributors == 4,
            "Terminal profile confused repeat observations with distinct people");
        observations += bin.observationContributions;
        distinct += bin.distinctContributors;
        const auto query = configured->exactQuery(output, bin.categoryId);
        require(query && query->observationContributions == 12 && query->distinctContributors == 4,
            "A preserved terminal category was unavailable as an exact query");
    }
    require(observations == 36 && distinct == 12,
        "Complete pedestrian terminal cut did not conserve source counts");
    const auto parent = configured->exactQuery(output, "pedestrian");
    require(parent && parent->observationContributions == 36 && parent->distinctContributors == 12,
        "Supported subtype bins did not roll up exactly to Pedestrian");
}

void oldAndNewPedestrianLabelsRemainOnOneBranch() {
    const auto configured = taxonomy();
    const std::vector<std::string> labels{
        "Adult Pedestrian", "Child Pedestrian", "Senior Pedestrian",
        "Pedestrian With Stroller", "Pedestrian With Mobility Aid"};
    SemanticAccumulator accumulator(configured);
    for (std::size_t index = 0; index < labels.size(); ++index) {
        const auto& leaf = configured->leafForType(labels[index]);
        require(configured->contains("pedestrian", leaf)
                && configured->node(leaf).loss == 0,
            "A configured old or new pedestrian label left the pedestrian branch");
        accumulator.add("observed-track-" + std::to_string(index), labels[index]);
    }
    const auto output = configured->select(accumulator.evidence(), 5, 5, 5);
    require(categories(output) == std::vector<std::string>{"pedestrian"}
            && output.bins.front().distinctContributors == 5 && output.maxLoss == .5,
        "The full mapped profile family unnecessarily collapsed to Road User");
}
} // namespace

int main() {
    try {
        sparseEquipmentProfilesGeneralizeToPedestrian();
        sufficientSubtypeSupportPreservesAllThreeCategories();
        oldAndNewPedestrianLabelsRemainOnOneBranch();
        std::cout << "Mapped pedestrian semantics passed: sparse profile generalization, exact count "
                     "conservation, hidden subtype queries, supported terminal detail and shared "
                     "Pedestrian ancestry for all five configured profiles.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
