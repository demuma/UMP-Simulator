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

        const std::string selectionPrefix = "history: {}\nmetric_policy: {}\nspatial_selection: ";
        auto selection = readSpatialSelection(YAML::Load(selectionPrefix + "{min_depth: 1, max_evaluations: 64}"), 3);
        require(selection && selection->minDepth == 1 && selection->maxEvaluations == 64, "Selection options not parsed");
        require(!selection->preserveValidDescendants, "Legacy selection must retain whole-candidate suppression");
        auto preserve = readSpatialSelection(YAML::Load(selectionPrefix
            + "{min_depth: 1, max_evaluations: 64, preserve_valid_descendants: true}"), 3);
        require(preserve->preserveValidDescendants, "Selective descendant fallback was not parsed");
        auto disabled = readSpatialSelection(YAML::Load(selectionPrefix
            + "{min_depth: 1, max_evaluations: 64, preserve_valid_descendants: false}"), 3);
        require(!disabled->preserveValidDescendants, "Explicit false changed the baseline");
        rejects([&] { readSpatialSelection(YAML::Load(selectionPrefix
            + "{min_depth: 1, max_evaluations: 64, preserve_valid_descendants: invalid}"), 3); }, "conversion");
        rejects([&] { readSpatialSelection(YAML::Load(selectionPrefix
            + "{min_depth: 1, max_evaluations: 64, preserve_valid_descendants: true, preserve_valid_descendants: false}"), 3); }, "duplicate");
        require(!readSpatialSelection(YAML::Load("{}"), 3), "Absent spatial selection must stay disabled");
        rejects([&] { readSpatialSelection(YAML::Load(selectionPrefix + "{min_depth: 0, max_evaluations: 64}"), 3); }, "Invalid");
        rejects([&] { readSpatialSelection(YAML::Load(selectionPrefix + "{min_depth: 4, max_evaluations: 64}"), 3); }, "Invalid");
        rejects([&] { readSpatialSelection(YAML::Load(selectionPrefix + "{min_depth: 1, max_evaluations: 0}"), 3); }, "Invalid");
        rejects([&] { readSpatialSelection(YAML::Load(selectionPrefix + "{min_depth: 1, max_evaluations: 64, publish: true}"), 3); }, "Unknown");
        rejects([&] { readSpatialSelection(YAML::Load("spatial_selection: {min_depth: 1, max_evaluations: 64}"), 3); }, "requires history");

        const auto configured = parse(prefix + "regions: [west], execution: {publication_model: private_final_snapshot, strategy: temporal_first}}");
        require(configured.evaluate(candidate, 400).status == ump::AssessmentStatus::Pass,
            "Execution settings changed inherited metric policy");
        parse(prefix + "regions: [west], execution: {strategy: spatial_first}}");
        parse(prefix + "regions: [west], execution: {}}");
        rejects([&] { parse(prefix + "regions: [west], execution: {publication_model: immediate_approved}}"); }, "Unsupported");
        rejects([&] { parse(prefix + "regions: [west], execution: {strategy: automatic}}"); }, "Unsupported");
        rejects([&] { parse(prefix + "regions: [west], execution: {strategy: temporal_first, strategy: spatial_first}}"); }, "duplicate");
        rejects([&] { parse(prefix + "regions: [west], execution: {regional: true}}"); }, "Unknown");
        rejects([&] { parse(prefix + "regions: [west], execution: null}"); }, "must be a map");
        rejects([&] { parse(prefix + "regions: [{id: west, execution: {strategy: spatial_first}}]}"); }, "Regional execution");
        rejects([&] { parse("publication: {}\nmetric_policy: {id: u, version: '1', requirements: {distinct_contributors: {min: 4}}}"); }, "policy_tree.execution.publication_model");

        const std::string adaptivePrefix = "history: {}\nspatial_selection: {}\n"
            "policy_tree: {execution: {strategy: temporal_first}}\ntemporal_adaptation: ";
        const std::string temporalOptions = "{extension_step_ms: 100, max_window_ms: 1000, max_evaluations: 64}";
        auto temporal = readTemporalAdaptation(YAML::Load(adaptivePrefix + temporalOptions));
        require(temporal && temporal->strategy == ump::AdaptationStrategy::TemporalFirst
            && temporal->extensionStepMs == 100 && temporal->maxWindowMs == 1000 && temporal->maxEvaluations == 64,
            "Temporal adaptation settings were not parsed");
        auto spatialFirst = YAML::Load(adaptivePrefix + temporalOptions);
        spatialFirst["policy_tree"]["execution"]["strategy"] = "spatial_first";
        require(readTemporalAdaptation(spatialFirst)->strategy == ump::AdaptationStrategy::SpatialFirst,
            "Spatial First strategy was relabeled as Temporal First");
        require(temporal->releaseTrigger == ump::ReleaseTrigger::PolicySatisfied
            && temporal->semanticSecondaryStrategy == ump::SemanticSecondaryStrategy::TemporalFirst,
            "Policy-satisfied release and the compatible semantic secondary must be the defaults");
        const std::string semanticFixture = R"(
history: {}
spatial_selection: {}
semantic_taxonomy:
  id: configuration-fixture
  version: '1'
  nodes:
    - {id: road_user, loss: 1}
    - {id: pedestrian, parent: road_user, loss: 0.5}
    - {id: adult_pedestrian, parent: pedestrian, loss: 0, input_types: [Adult_Pedestrian]}
    - {id: child_pedestrian, parent: pedestrian, loss: 0, input_types: [Child_Pedestrian]}
policy_tree:
  id: semantic-policy
  version: '1'
  root: {min_category_distinct_contributors: {min: 5}, semantic_max_loss: {max: 1}}
  execution: {strategy: semantic_first}
temporal_adaptation: {extension_step_ms: 100, max_window_ms: 4000, max_evaluations: 64}
)";
        auto semantic = YAML::Load(semanticFixture);
        const auto taxonomy = readSemanticTaxonomy(semantic);
        require(taxonomy && taxonomy->leafForType("Adult_Pedestrian") == "adult_pedestrian"
            && taxonomy->node("pedestrian").loss == 0.5, "Minimal semantic fixture was not parsed");
        const auto semanticDefaults = readTemporalAdaptation(semantic);
        require(semanticDefaults->strategy == ump::AdaptationStrategy::SemanticFirst
            && semanticDefaults->semanticSecondaryStrategy == ump::SemanticSecondaryStrategy::TemporalFirst
            && semanticDefaults->releaseTrigger == ump::ReleaseTrigger::PolicySatisfied,
            "Semantic First defaults must release on policy satisfaction with Temporal First secondary");
        for (const auto* secondary : {"temporal_first", "spatial_first"}) {
            for (const auto* trigger : {"policy_satisfied", "priority_satisfied"}) {
                auto selected = YAML::Load(semanticFixture);
                selected["policy_tree"]["execution"]["semantic_secondary_strategy"] = secondary;
                selected["policy_tree"]["execution"]["release_trigger"] = trigger;
                const auto settings = readTemporalAdaptation(selected);
                require(settings->semanticSecondaryStrategy == (std::string(secondary) == "spatial_first"
                    ? ump::SemanticSecondaryStrategy::SpatialFirst : ump::SemanticSecondaryStrategy::TemporalFirst),
                    "Semantic secondary strategy was not parsed");
                require(settings->releaseTrigger == (std::string(trigger) == "priority_satisfied"
                    ? ump::ReleaseTrigger::PrioritySatisfied : ump::ReleaseTrigger::PolicySatisfied),
                    "Semantic release trigger was not parsed");
            }
        }
        for (const auto* strategy : {"temporal_first", "spatial_first"}) {
            for (const auto* trigger : {"policy_satisfied", "priority_satisfied"}) {
                auto selected = YAML::Load(adaptivePrefix + temporalOptions);
                selected["policy_tree"]["execution"]["strategy"] = strategy;
                selected["policy_tree"]["execution"]["release_trigger"] = trigger;
                require(readTemporalAdaptation(selected)->releaseTrigger == (std::string(trigger) == "priority_satisfied"
                    ? ump::ReleaseTrigger::PrioritySatisfied : ump::ReleaseTrigger::PolicySatisfied),
                    "Explicit trigger must be accepted for the existing Temporal/Spatial First controllers");
            }
            auto misplaced = YAML::Load(adaptivePrefix + temporalOptions);
            misplaced["policy_tree"]["execution"]["strategy"] = strategy;
            misplaced["policy_tree"]["execution"]["semantic_secondary_strategy"] = "spatial_first";
            rejects([&] { readTemporalAdaptation(misplaced); }, "requires semantic_first");
        }
        for (const auto* key : {"semantic_secondary_strategy", "release_trigger"}) {
            for (const auto* malformed : {"null", "[]", "{}"}) {
                auto invalid = YAML::Load(semanticFixture);
                invalid["policy_tree"]["execution"][key] = YAML::Load(malformed);
                rejects([&] { readTemporalAdaptation(invalid); }, "must be a string");
            }
            for (const auto* unsupported : {"true", "5", "unknown"}) {
                auto invalid = YAML::Load(semanticFixture);
                invalid["policy_tree"]["execution"][key] = YAML::Load(unsupported);
                rejects([&] { readTemporalAdaptation(invalid); }, "Unsupported");
            }
            auto duplicate = YAML::Load(semanticFixture);
            duplicate["policy_tree"]["execution"] = YAML::Load(std::string("{strategy: semantic_first, ")
                + key + ": policy_satisfied, " + key + ": priority_satisfied}");
            rejects([&] { readTemporalAdaptation(duplicate); }, "duplicate");
        }
        auto noStrategy = YAML::Load(semanticFixture);
        noStrategy["policy_tree"]["execution"].remove("strategy");
        noStrategy["policy_tree"]["execution"]["release_trigger"] = "policy_satisfied";
        rejects([&] { validatePolicyExecution(noStrategy); }, "requires policy_tree.execution.strategy");
        noStrategy["policy_tree"]["execution"].remove("release_trigger");
        noStrategy["policy_tree"]["execution"]["semantic_secondary_strategy"] = "spatial_first";
        rejects([&] { validatePolicyExecution(noStrategy); }, "requires semantic_first");
        auto unsupportedLocalSemantic = YAML::Load(semanticFixture);
        unsupportedLocalSemantic["temporal_adaptation"]["coordination"] = "cell_local";
        rejects([&] { readTemporalAdaptation(unsupportedLocalSemantic); }, "common_window only");
        auto missingTaxonomy = YAML::Load(semanticFixture);
        missingTaxonomy.remove("semantic_taxonomy");
        rejects([&] { readTemporalAdaptation(missingTaxonomy); }, "requires semantic_taxonomy");
        auto local = YAML::Load(adaptivePrefix + temporalOptions);
        local["temporal_adaptation"]["coordination"] = "cell_local";
        local["temporal_adaptation"]["max_active_cells"] = 128;
        require(readTemporalAdaptation(local)->coordination == ump::CoordinationMode::CellLocal
            && readTemporalAdaptation(local)->maxActiveCells == 128, "Cell-local coordination settings were lost");
        local["spatial_selection"]["preserve_valid_descendants"] = true;
        rejects([&] { readTemporalAdaptation(local); }, "common_window only");
        local["spatial_selection"]["preserve_valid_descendants"] = false;
        local["temporal_adaptation"]["max_active_cells"] = 3;
        rejects([&] { readTemporalAdaptation(local); }, "four base cells");
        local["temporal_adaptation"]["max_active_cells"] = 128;
        local["temporal_adaptation"]["coordination"] = "arbitrary";
        rejects([&] { readTemporalAdaptation(local); }, "Unsupported");
        require(!readTemporalAdaptation(YAML::Load("{}")), "Absent temporal adaptation must stay disabled");
        rejects([&] { readTemporalAdaptation(YAML::Load(adaptivePrefix + "null")); }, "must be a map");
        rejects([&] { readTemporalAdaptation(YAML::Load(adaptivePrefix + "{extension_step_ms: 100, max_window_ms: 1000}")); }, "explicit");
        rejects([&] { readTemporalAdaptation(YAML::Load(adaptivePrefix + "{extension_step_ms: 100, max_window_ms: 1000, max_evaluations: 64, strategy: spatial_first}")); }, "Unknown");
        rejects([&] { readTemporalAdaptation(YAML::Load(adaptivePrefix + "{extension_step_ms: 100, extension_step_ms: 200}")); }, "duplicate");
        for (const auto* key : {"extension_step_ms", "max_window_ms", "max_evaluations"}) {
            auto invalid = YAML::Load(adaptivePrefix + temporalOptions);
            invalid["temporal_adaptation"][key] = 0;
            rejects([&] { readTemporalAdaptation(invalid); }, "positive");
            invalid["temporal_adaptation"].remove(key);
            rejects([&] { readTemporalAdaptation(invalid); }, "explicit");
        }
        for (const auto* key : {"history", "spatial_selection"}) {
            auto invalid = YAML::Load(adaptivePrefix + temporalOptions);
            invalid.remove(key);
            rejects([&] { readTemporalAdaptation(invalid); }, "requires history and spatial_selection");
        }
        auto missingStrategy = YAML::Load(adaptivePrefix + temporalOptions);
        missingStrategy["policy_tree"].remove("execution");
        rejects([&] { readTemporalAdaptation(missingStrategy); }, "requires policy_tree.execution.strategy");

        const std::string publicationPrefix = "spatial_selection: {}\n"
            "policy_tree: {execution: {publication_model: private_final_snapshot}}\npublication: ";
        const std::string destinations = "{database: UMP_Recipient, journal_database: UMP_PrivateJournal}";
        const auto publication = readPublicationConfiguration(YAML::Load(publicationPrefix + destinations));
        require(publication->journalEmptyRetirements, "Private retirement journaling must default to legacy behavior");
        auto noEmptyJournal = YAML::Load(publicationPrefix + destinations);
        noEmptyJournal["publication"]["journal_empty_retirements"] = false;
        require(!readPublicationConfiguration(noEmptyJournal)->journalEmptyRetirements,
            "Explicit no-output journaling configuration was ignored");
        require(publication && publication->database == "UMP_Recipient" && publication->collection == "releases"
            && publication->journalDatabase == "UMP_PrivateJournal" && publication->journalCollection == "publication_journal"
            && publication->maxDocumentBytes == 8 * 1024 * 1024 && publication->maxAttempts == 3,
            "Publication defaults/destinations were not parsed");
        const auto custom = readPublicationConfiguration(YAML::Load(publicationPrefix
            + "{database: Recipient, collection: approved, journal_database: PrivateJournal, journal_collection: pending, max_document_bytes: 4096, max_attempts: 5}"));
        require(custom->collection == "approved" && custom->journalCollection == "pending"
            && custom->maxDocumentBytes == 4096 && custom->maxAttempts == 5,
            "Explicit publication settings were ignored");
        require(!readPublicationConfiguration(YAML::Load("{}")), "Absent publication must stay disabled");
        rejects([&] { readPublicationConfiguration(YAML::Load(publicationPrefix + "null")); }, "must be a map");
        rejects([&] { readPublicationConfiguration(YAML::Load(publicationPrefix + "{database: Recipient}")); }, "must be explicit");
        rejects([&] { readPublicationConfiguration(YAML::Load(publicationPrefix + "{database: Recipient, journal_database: PrivateJournal, model: private_final_snapshot}")); }, "Unknown");
        rejects([&] { readPublicationConfiguration(YAML::Load(publicationPrefix + "{database: Recipient, database: Another, journal_database: PrivateJournal}")); }, "duplicate");
        for (const auto* key : {"max_document_bytes", "max_attempts"}) {
            auto invalid = YAML::Load(publicationPrefix + destinations);
            invalid["publication"][key] = -1;
            rejects([&] { readPublicationConfiguration(invalid); }, "positive");
        }
        for (const auto* key : {"database", "journal_database"}) {
            for (const auto* reserved : {"Simulation", "admin", "local", "config"}) {
                auto invalid = YAML::Load(publicationPrefix + destinations);
                invalid["publication"][key] = reserved;
                rejects([&] { readPublicationConfiguration(invalid); }, "reserved database");
            }
            auto invalid = YAML::Load(publicationPrefix + destinations);
            invalid["publication"][key] = "";
            rejects([&] { readPublicationConfiguration(invalid); }, "nonempty");
        }
        auto sameDatabase = YAML::Load(publicationPrefix + destinations);
        sameDatabase["publication"]["journal_database"] = "ump_recipient";
        rejects([&] { readPublicationConfiguration(sameDatabase); }, "distinct databases");
        for (const auto* key : {"collection", "journal_collection"}) {
            auto invalid = YAML::Load(publicationPrefix + destinations);
            invalid["publication"][key] = "";
            rejects([&] { readPublicationConfiguration(invalid); }, "nonempty");
        }
        for (const auto* key : {"database", "collection", "journal_database", "journal_collection"}) {
            auto invalid = YAML::Load(publicationPrefix + destinations);
            invalid["publication"][key] = YAML::Load("{invalid: name}");
            rejects([&] { readPublicationConfiguration(invalid); }, "must be a string");
            invalid["publication"][key] = YAML::Load("null");
            rejects([&] { readPublicationConfiguration(invalid); }, "must be a string");
        }
        auto missingSelection = YAML::Load(publicationPrefix + destinations);
        missingSelection.remove("spatial_selection");
        rejects([&] { readPublicationConfiguration(missingSelection); }, "requires spatial_selection");
        auto missingModel = YAML::Load(publicationPrefix + destinations);
        missingModel["policy_tree"].remove("execution");
        rejects([&] { readPublicationConfiguration(missingModel); }, "requires policy_tree.execution.publication_model");
        validatePublicationDestinations(*publication, {"Simulation", "UMP_RawSensors", "UMP_GroundTruth"});
        rejects([&] { validatePublicationDestinations(*publication, {"Unrelated", "UMP_Recipient"}); }, "overlaps raw database");
        rejects([&] { validatePublicationDestinations(*publication, {"Unrelated", "ump_privatejournal"}); }, "overlaps raw database");
        std::cout << "PASS: YAML/Region adapter, execution policy, temporal/publication settings, destination isolation and compatibility.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n'; return 1;
    }
}
