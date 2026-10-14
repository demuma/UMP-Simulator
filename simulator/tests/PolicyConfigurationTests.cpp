#include "PolicyConfiguration.hpp"
#include "AggregationConfiguration.hpp"
#include <iostream>

namespace {
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
template<class F> void rejects(F work, const char* text) {
    try { work(); } catch (const std::exception& error) {
        require(std::string(error.what()).find(text) != std::string::npos, error.what()); return;
    }
    throw std::runtime_error(std::string("Expected error: ") + text);
}
}
int main() {
    try {
        Region::RegionTypeAttributes attributes{};
        attributes.privacy.k_anonymity.min = 1000; // Legacy fields must not become support thresholds.
        attributes.metricRequirements = readMetricRequirements(YAML::Load("distinct_contributors: {min: 5}"));
        Region west(attributes); west.id = "west"; west.type = "residential";
        west.area = sf::FloatRect({0, 0}, {40, 40});
        west.metricRequirements = readMetricRequirements(YAML::Load("distinct_contributors: {min: 2}"));
        const std::vector<Region> regions{west};
        const ump::GridCoverage grid{0, 0, 80, 80, 3};
        const auto parse = [&](const std::string& yaml) { return makeMetricEvaluator(YAML::Load(yaml), grid, "app", regions); };
        auto evaluator = parse(R"(
policy_tree:
  id: test-tree
  version: '1'
  root: {distinct_contributors: {min: 3}}
  regions: [west]
)");
        ump::AggregationCandidate candidate{"run", "sensor", "app", grid, 0, 400, 400, false,
            3, 3, 0, 0, ump::WindowCoverage::Complete, {6, 6, {}, 2},
            {{{192, 3, 0, 0, 10, 10}, {6, 6, {}, 2}}}};
        const auto result = evaluator.evaluate(candidate, 400);
        require(result.status == ump::AssessmentStatus::Pass && result.cells[0].checks[0].requirement.min == 5,
            "Region adapter lost inheritance or activated legacy k");
        const std::string prefix = "policy_tree: {id: t, version: '1', root: {distinct_contributors: {min: 3}}, ";
        rejects([&] { parse(prefix + "regions: [missing]}"); }, "Unknown policy region");
        rejects([&] { parse(prefix + "regions: [west, west]}"); }, "Duplicate policy region");
        rejects([&] { parse(prefix + "regions: [west], temporal_first: true}"); }, "Unknown policy_tree");
        rejects([&] { parse(prefix + "regions: [west], max_nodes: 0}"); }, "positive");
        rejects([&] { parse(prefix + "regions: [west], max_nodes: 1}"); }, "max_nodes");
        rejects([&] { parse(prefix + "regions: [west]}\nmetric_policy: {}\n"); }, "not both");
        rejects([&] { parse(prefix + "regions: [west], version: '2'}"); }, "Duplicate");
        rejects([&] { readMetricRequirements(YAML::Load("k_anonymity: {min: 3}")); }, "Unknown metric");
        rejects([&] { readMetricRequirements(YAML::Load("distinct_contributors: {min: 3, min: 2}")); }, "Duplicate");
        rejects([&] { readMetricRequirements(YAML::Load("distinct_contributors: {min: 3}\ndistinct_contributors: {min: 2}")); }, "Duplicate");
        rejects([&] { readMetricRequirements(YAML::Load("distinct_contributors: {min: 3, priority: 2}")); }, "Unknown");
        require(readMetricRequirements(YAML::Load("{}") ["absent"], true).empty(), "Absent optional region rules did not inherit");
        rejects([&] { readMetricRequirements(YAML::Load("null"), true); }, "must be a map");
        require(parse("{}").evaluate(candidate, 400).status == ump::AssessmentStatus::NotConfigured,
            "Absent policy changed baseline behavior");
        require(parse("metric_policy: {id: u, version: '1', requirements: {distinct_contributors: {min: 4}}}")
            .evaluate(candidate, 400).policyMode == "uniform", "Existing uniform YAML stopped working");
        const std::string history = "{retention_ms: 2000, max_bins: 32, max_observations: 1000, max_identity_bytes: 64000, max_buckets: 16}";
        require(readHistoryLimits(YAML::Load(history))->retentionMs == 2000, "History limits were not parsed");
        require(!readHistoryLimits(YAML::Load("{}")["absent"]), "Absent history must stay disabled");
        rejects([&] { readHistoryLimits(YAML::Load("null")); }, "must be a map");
        rejects([&] { readHistoryLimits(YAML::Load("{retention_ms: 2000}")); }, "explicit");
        rejects([&] { readHistoryLimits(YAML::Load("{unsupported: 1}")); }, "Unknown");
        rejects([&] { readHistoryLimits(YAML::Load("{max_bins: 1, max_bins: 2}")); }, "duplicate");
        auto zero = history; zero.replace(zero.find("max_bins: 32"), 12, "max_bins: 0");
        rejects([&] { readHistoryLimits(YAML::Load(zero)); }, "positive");
        std::cout << "PASS: YAML/Region adapter, strict options, inheritance and legacy/uniform compatibility.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n'; return 1;
    }
}
