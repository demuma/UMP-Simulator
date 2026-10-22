"""Actual semantic replay acceptance with independent raw-data release auditing.

Scalar geometry/counts/timing use the existing raw oracle after explicitly removing
semantic policy and diagnostic fields. Semantic checks independently scan original
observations, reconstruct identity sets and enumerate tiny catalog antichains. No
production accumulator, selector, diagnostics or taxonomy helper supplies expectations.
All replay artifacts are confined to temporary directories. No attack is fitted.
"""
from copy import deepcopy
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from oracle import validate_result

ROOT = Path(os.environ.get("UMP_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
BINARY = Path(os.environ.get("UMP_REPLAY_BINARY", ROOT / "simulator/build/AggregationReplay"))
SEMANTIC_METRICS = {"min_category_distinct_contributors", "semantic_max_loss", "semantic_mean_loss"}
GRID = dict(x=0, y=0, width=80, height=80, leaf_depth=2)
POSITIONS = {48: (1, 1), 49: (21, 1), 50: (1, 21), 51: (21, 21)}


def taxonomy():
    return dict(id="semantic-replay", version="1", nodes=[
        dict(id="road_user", loss=1),
        dict(id="pedestrian", parent="road_user", loss=0, input_types=["pedestrian"]),
        dict(id="cyclist", parent="road_user", loss=.5),
        dict(id="adult_cyclist", parent="cyclist", loss=0, input_types=["adult_cyclist", "Adult alias"]),
        dict(id="child_cyclist", parent="cyclist", loss=0, input_types=["child_cyclist"])])


def observation(identity, kind="pedestrian", cell=48):
    x, y = POSITIONS[cell]
    return dict(id=identity, type=kind, cell_id=cell, x=x, y=y)


def population(pedestrians=0, adults=0, children=0, *, cell=48):
    return [observation(f"{kind}-{i}", kind, cell)
            for kind, count in (("pedestrian", pedestrians), ("adult_cyclist", adults),
                                ("child_cyclist", children)) for i in range(count)]


def source(samples, *, end=400):
    batches = []
    for sequence, observations in enumerate(samples, 1):
        if observations == "missing":
            continue
        batches.append(dict(sequence=sequence, observed_at_ms=sequence * 100,
            status="unavailable" if observations is None else "measured",
            observations=[] if observations is None else observations))
    return dict(schema="ump.observation-replay.v1", run_id="semantic-acceptance", sensor_id="agbs",
                coverage=deepcopy(GRID), sampling_period_ms=100, end_ms=end, batches=batches)


def policy(*, support=5, loss=1, side=20, min_depth=2, window=400, maximum=1000):
    return dict(application_id="semantic-acceptance", window_ms=window,
        max_observations_per_window=1000000,
        history=dict(retention_ms=2000, max_bins=32, max_observations=100000,
                     max_identity_bytes=16000000, max_buckets=128),
        spatial_selection=dict(min_depth=min_depth, max_evaluations=4096),
        temporal_adaptation=dict(extension_step_ms=100, max_window_ms=maximum,
                                 max_evaluations=16, coordination="common_window"),
        semantic_taxonomy=taxonomy(),
        policy_tree=dict(id="semantic-policy", version="1", max_nodes=65536,
            execution=dict(publication_model="private_final_snapshot", strategy="spatial_first"),
            root=dict(distinct_contributors=dict(min=1), cell_side_m=dict(min=1.25, max=side),
                window_duration_ms=dict(max=maximum), age_at_evaluation_ms=dict(max=maximum),
                min_category_distinct_contributors=dict(min=support), semantic_max_loss=dict(max=loss)),
            regions=[]), policy_regions=[])


def scalar_projection(config, actual):
    config, actual = deepcopy(config), deepcopy(actual)
    config.pop("semantic_taxonomy", None)
    requirements = [config.get("policy_tree", {}).get("root", {}),
                    config.get("metric_policy", {}).get("requirements", {})]
    for region in config.get("policy_regions", []):
        requirements.extend([region.get("type_requirements", {}), region.get("requirements", {})])
    for bounds in requirements:
        for name in SEMANTIC_METRICS:
            bounds.pop(name, None)
    for window in actual["windows"]:
        for cell in window["cells"]:
            cell.pop("semantic", None)
            # A semantics-suppressed cell may pass scalar rules. Leave its
            # selected flag/counts untouched, but do not assert obsolete status.
            cell.pop("assessment_status", None)
            if "metrics" in cell:
                for name in SEMANTIC_METRICS:
                    cell["metrics"].pop(name, None)
            cell["checks"] = [check for check in cell.get("checks", [])
                              if check.get("metric") not in SEMANTIC_METRICS]
    for release in actual["releases"]:
        for cell in release["cells"]:
            cell.pop("semantic", None)
    return config, actual


def catalog(config):
    nodes = {node["id"]: node for node in config["semantic_taxonomy"]["nodes"]}
    labels = {label: node["id"] for node in nodes.values() for label in node.get("input_types", [])}
    return nodes, labels


def contains(nodes, ancestor, descendant):
    current = descendant
    while current is not None:
        if ancestor == current:
            return True
        current = nodes[current].get("parent")
    return False


def intersects(cell, region):
    return (cell["x"] < region["x"] + region["width"]
            and region["x"] < cell["x"] + cell["width"]
            and cell["y"] < region["y"] + region["height"]
            and region["y"] < cell["y"] + cell["height"])


def effective_semantic_bounds(config, cell):
    requirements = [config["policy_tree"]["root"]]
    selected = set(config["policy_tree"]["regions"])
    for region in config.get("policy_regions", []):
        if region["id"] in selected and intersects(cell, region):
            requirements.extend([region.get("type_requirements", {}), region.get("requirements", {})])
    effective = {}
    for requirements_here in requirements:
        for name, bounds in requirements_here.items():
            if name not in SEMANTIC_METRICS:
                continue
            target = effective.setdefault(name, {})
            if "min" in bounds:
                target["min"] = max(target.get("min", -math.inf), bounds["min"])
            if "max" in bounds:
                target["max"] = min(target.get("max", math.inf), bounds["max"])
    return effective


def raw_observations(data, cell, start, end):
    return [observation for batch in data["batches"]
            if start <= batch["observed_at_ms"] < end and batch["status"] == "measured"
            for observation in batch["observations"]
            if cell["x"] <= observation["x"] < cell["x"] + cell["width"]
            and cell["y"] <= observation["y"] < cell["y"] + cell["height"]]


def audit_semantics(data, config, actual):
    """Independently audit every released bin and corresponding selected diagnostic."""
    nodes, labels = catalog(config)
    expected_semantic_fields = {"schema", "taxonomy_id", "taxonomy_version", "categories",
                               "min_category_distinct_contributors", "semantic_max_loss", "semantic_mean_loss"}
    expected_category_fields = {"category_id", "observation_contributions", "distinct_contributors"}
    checked = 0
    for release in actual["releases"]:
        assert "suppressed_cells" not in release and "input_observation_contributions" not in release
        for cell in release["cells"]:
            assert set(cell) == {"cell_id", "depth", "x", "y", "width", "height",
                                 "observation_contributions", "distinct_road_users", "mean_sample_occupancy",
                                 "effective_policy_id", "semantic"}, "Unexpected recipient cell/private field"
            semantic = cell["semantic"]
            assert set(semantic) == expected_semantic_fields
            assert semantic["schema"] == "ump.semantic-release.v1"
            assert semantic["taxonomy_id"] == config["semantic_taxonomy"]["id"]
            assert semantic["taxonomy_version"] == config["semantic_taxonomy"]["version"]
            bins = semantic["categories"]
            assert bins, "Nonempty released cell has no semantic representation"
            categories = [row["category_id"] for row in bins]
            assert len(categories) == len(set(categories))
            assert categories == sorted(categories), "Semantic cut ordering is nondeterministic"
            for i, left in enumerate(categories):
                assert left in nodes
                for right in categories[i + 1:]:
                    assert not contains(nodes, left, right) and not contains(nodes, right, left), "Semantic categories overlap"
            original = raw_observations(data, cell, release["start_ms"], release["end_ms"])
            identity_classes = {}
            for item in original:
                leaf = labels[item["type"]]
                assert identity_classes.setdefault(item["id"], leaf) == leaf, "Unstable canonical classification"
                assert sum(contains(nodes, category, leaf) for category in categories) == 1, "Semantic cut drops/duplicates an observation"
            assert len(original) == cell["observation_contributions"]
            assert len(identity_classes) == cell["distinct_road_users"]
            for row in bins:
                assert set(row) == expected_category_fields, "Semantic category leaked private evidence"
                assigned = [item for item in original if contains(nodes, row["category_id"], labels[item["type"]])]
                assert assigned, "Empty category should not be published"
                assert row["observation_contributions"] == len(assigned)
                assert row["distinct_contributors"] == len({item["id"] for item in assigned})
            minimum = min(row["distinct_contributors"] for row in bins)
            maximum_loss = max(nodes[row["category_id"]]["loss"] for row in bins)
            mean_loss = sum(row["observation_contributions"] * nodes[row["category_id"]]["loss"]
                            for row in bins) / len(original)
            values = dict(min_category_distinct_contributors=minimum,
                          semantic_max_loss=maximum_loss, semantic_mean_loss=mean_loss)
            for name, expected in values.items():
                assert math.isclose(semantic[name], expected, abs_tol=1e-12, rel_tol=1e-12), "Semantic metric summary is false"
            for name, bounds in effective_semantic_bounds(config, cell).items():
                assert bounds.get("min", -math.inf) <= values[name] <= bounds.get("max", math.inf), "Released semantic cut violates regional policy"
            matches = [diagnostic for window in actual["windows"]
                       if (window["start_ms"], window["end_ms"]) == (release["start_ms"], release["end_ms"])
                       for diagnostic in window["cells"] if diagnostic["cell_id"] == cell["cell_id"] and diagnostic["selected"]]
            assert len(matches) == 1 and matches[0]["semantic"] == semantic, "Sealed semantic payload differs from selected diagnostic"
            checked += 1
    return checked


def exact_class_query(config, semantic, category):
    """Interpret the public product only; unknown means a bin straddles the query."""
    nodes, _ = catalog(config)
    total = 0
    for row in semantic["categories"]:
        if contains(nodes, category, row["category_id"]):
            total += row["observation_contributions"]
        elif contains(nodes, row["category_id"], category):
            return None
    return total


def enumerate_catalog_cuts(config, observations):
    """Independent brute-force subsets, no production-style recursive traversal."""
    nodes, labels = catalog(config)
    support = config["policy_tree"]["root"]["min_category_distinct_contributors"]["min"]
    loss_limit = config["policy_tree"]["root"]["semantic_max_loss"]["max"]
    occupied_nodes = [node for node in nodes if any(contains(nodes, node, labels[o["type"]]) for o in observations)]
    alternatives = []
    for number in range(1, len(occupied_nodes) + 1):
        for cut in itertools.combinations(occupied_nodes, number):
            if any(contains(nodes, a, b) or contains(nodes, b, a) for a, b in itertools.combinations(cut, 2)):
                continue
            if any(sum(contains(nodes, category, labels[o["type"]]) for category in cut) != 1 for o in observations):
                continue
            groups = [[o for o in observations if contains(nodes, category, labels[o["type"]])] for category in cut]
            if any(len({o["id"] for o in group}) < support for group in groups):
                continue
            if max(nodes[category]["loss"] for category in cut) > loss_limit:
                continue
            cost = sum(len(group) * nodes[category]["loss"] for category, group in zip(cut, groups))
            alternatives.append((cost, tuple(sorted(cut))))
    return min(alternatives)[1] if alternatives else None


@unittest.skipUnless(BINARY.is_file(), "Build AggregationReplay for semantic real-core acceptance")
class SemanticAdaptationReplayTests(unittest.TestCase):
    def run_core(self, data, config, mode="spatial", *, succeeds=True):
        with tempfile.TemporaryDirectory(prefix="ump-semantic-replay-") as temporary:
            directory = Path(temporary)
            input_file, policy_file, output_file = [directory / name for name in ("input.json", "policy.json", "result.json")]
            input_file.write_text(json.dumps(data), encoding="utf-8")
            policy_file.write_text(json.dumps(config), encoding="utf-8")
            completed = subprocess.run([str(BINARY), "--input", str(input_file), "--config", str(policy_file),
                "--mode", mode, "--output", str(output_file)], capture_output=True, text=True, timeout=20)
            if not succeeds:
                self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertFalse(output_file.exists(), "Rejected semantic replay wrote a result")
                return completed
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            actual = json.loads(output_file.read_text(encoding="utf-8"))
        scalar_config, scalar_result = scalar_projection(config, actual)
        report = validate_result(data, scalar_config, scalar_result)
        self.assertTrue(report["valid"], json.dumps(report["violations"][:10], indent=2))
        audit_semantics(data, config, actual)
        return actual

    def test_nineteen_pedestrians_and_one_cyclist_truthfully_become_twenty_road_users(self):
        data, config = source([population(19, 1)] * 3), policy()
        for mode in ("spatial", "temporal_first", "spatial_first"):
            with self.subTest(mode=mode):
                actual = self.run_core(data, config, mode)
                semantic = actual["releases"][0]["cells"][0]["semantic"]
                self.assertEqual(semantic["categories"], [dict(category_id="road_user", observation_contributions=60,
                                                              distinct_contributors=20)])
                self.assertEqual(semantic["min_category_distinct_contributors"], 20)
                self.assertEqual(semantic["semantic_max_loss"], 1)
                self.assertEqual(semantic["semantic_mean_loss"], 1)

    def test_loss_limit_prevents_root_and_individual_suppression(self):
        actual = self.run_core(source([population(19, 1)] * 3), policy(loss=.5))
        self.assertEqual(actual["releases"], [])
        self.assertEqual(actual["accounted_observation_contributions"], 60)

    def test_two_adult_two_child_cyclists_use_truthful_intermediate_category(self):
        data, config = source([population(0, 2, 2)] * 3), policy(support=4, loss=.5)
        actual = self.run_core(data, config)
        semantic = actual["releases"][0]["cells"][0]["semantic"]
        self.assertEqual(semantic["categories"], [dict(category_id="cyclist", observation_contributions=12,
                                                      distinct_contributors=4)])
        self.assertEqual((semantic["semantic_max_loss"], semantic["semantic_mean_loss"]), (.5, .5))

    def test_repeating_four_people_never_creates_a_fifth(self):
        data = source([population(0, 2, 2)] * 7, end=800)
        actual = self.run_core(data, policy(support=5, window=800))
        self.assertEqual(actual["input_observation_contributions"], 28)
        self.assertEqual(actual["releases"], [])

    def test_declared_node_cost_is_used_instead_of_normalized_tree_depth(self):
        data, config = source([population(0, 2, 2)] * 3), policy(support=4, loss=.4)
        for node in config["semantic_taxonomy"]["nodes"]:
            if node["id"] == "cyclist":
                node["loss"] = .37
        actual = self.run_core(data, config)
        semantic = actual["releases"][0]["cells"][0]["semantic"]
        self.assertAlmostEqual(semantic["semantic_max_loss"], .37)
        self.assertAlmostEqual(semantic["semantic_mean_loss"], .37)
        config["policy_tree"]["root"]["semantic_max_loss"] = dict(max=.36)
        self.assertEqual(self.run_core(data, config)["releases"], [])

    def test_passing_terminals_preserve_zero_loss_and_alias_identity(self):
        samples = [population(2, 2, 2) for _ in range(3)]
        samples[1][2]["type"] = "Adult alias"
        actual = self.run_core(source(samples), policy(support=2))
        semantic = actual["releases"][0]["cells"][0]["semantic"]
        self.assertEqual([row["category_id"] for row in semantic["categories"]],
                         ["adult_cyclist", "child_cyclist", "pedestrian"])
        self.assertEqual((semantic["semantic_max_loss"], semantic["semantic_mean_loss"]), (0, 0))

    def test_generalized_public_class_queries_are_unknown_instead_of_invented_counts(self):
        config = policy(support=4, loss=.5)
        semantic = self.run_core(source([population(0, 2, 2)] * 3), config)["releases"][0]["cells"][0]["semantic"]
        self.assertIsNone(exact_class_query(config, semantic, "adult_cyclist"))
        self.assertIsNone(exact_class_query(config, semantic, "child_cyclist"))
        self.assertEqual(exact_class_query(config, semantic, "cyclist"), 12)
        self.assertEqual(exact_class_query(config, semantic, "road_user"), 12)
        self.assertEqual(exact_class_query(config, semantic, "pedestrian"), 0)

    def test_spatial_rescue_preserves_semantic_detail_instead_of_fabricating_classes(self):
        observations = [observation("p-left"), observation("a-left", "adult_cyclist"),
                        observation("p-right", cell=49), observation("a-right", "adult_cyclist", 49)]
        config = policy(support=2, loss=0, side=40, min_depth=1)
        actual = self.run_core(source([observations] * 3), config)
        self.assertEqual([cell["cell_id"] for release in actual["releases"] for cell in release["cells"]], [12])
        self.assertEqual(actual["releases"][0]["cells"][0]["observation_contributions"], 12)
        self.assertEqual(actual["releases"][0]["cells"][0]["semantic"]["semantic_max_loss"], 0)

    def test_temporal_rescue_waits_for_new_people_without_resetting_start(self):
        samples = [[observation("p-a"), observation("a-a", "adult_cyclist")] +
                   ([observation("p-b"), observation("a-b", "adult_cyclist")] if time >= 400 else [])
                   for time in range(100, 800, 100)]
        data = source(samples, end=800)
        for mode in ("temporal_first", "spatial_first"):
            with self.subTest(mode=mode):
                actual = self.run_core(data, policy(support=2, loss=0, maximum=800), mode)
                first = actual["releases"][0]
                self.assertEqual((first["start_ms"], first["end_ms"], first["sealed_at_ms"]), (0, 500, 500))
                self.assertEqual(first["cells"][0]["semantic"]["semantic_max_loss"], 0)

    def test_regional_semantic_bounds_intersect_for_the_complete_parent(self):
        observations = [observation("a-one", "adult_cyclist"), observation("a-two", "adult_cyclist"),
                        observation("p-one", cell=49), observation("p-two", cell=49)]
        for minimum, loss in ((3, 0), (5, 1)):
            with self.subTest(minimum=minimum, loss=loss):
                config = policy(support=1, side=40, min_depth=1)
                config["spatial_selection"]["preserve_valid_descendants"] = True
                config["policy_tree"]["regions"] = ["strict"]
                config["policy_regions"] = [dict(id="strict", type="sensitive", x=0, y=0, width=20, height=20,
                    type_requirements=dict(min_category_distinct_contributors=dict(min=minimum)),
                    requirements=dict(semantic_max_loss=dict(max=loss)))]
                actual = self.run_core(source([observations] * 3), config)
                self.assertEqual([cell["cell_id"] for release in actual["releases"] for cell in release["cells"]], [49])

    def test_mean_loss_bound_remains_mandatory(self):
        config = policy(support=4, loss=1)
        config["policy_tree"]["root"]["semantic_mean_loss"] = dict(max=.25)
        actual = self.run_core(source([population(0, 2, 2)] * 3), config)
        self.assertEqual(actual["releases"], [])

    def test_incomplete_coverage_cannot_publish_semantic_bins(self):
        for absent in ("missing", None):
            with self.subTest(absent=absent):
                actual = self.run_core(source([population(19, 1), absent, population(19, 1)]), policy())
                self.assertEqual(actual["releases"], [])

    def test_unknown_conflicting_and_invalid_coordination_inputs_reject_without_output(self):
        bad_label = source([[observation("a", "not-in-taxonomy")]] * 3)
        conflicting = source([[observation("a")], [observation("a", "adult_cyclist")], []])
        for data in (bad_label, conflicting):
            with self.subTest(data=data):
                self.run_core(data, policy(), succeeds=False)
        config = policy()
        # Semantic cell-local execution is supported by the subsequent local gate;
        # unknown modes must still fail before producing a recipient stream.
        config["temporal_adaptation"]["coordination"] = "unknown_coordination"
        self.run_core(source([population(19, 1)] * 3), config, "spatial_first", succeeds=False)

    def test_semantic_auditor_detects_false_counts_overlap_and_false_loss(self):
        data, config = source([population(19, 1)] * 3), policy()
        actual = self.run_core(data, config)
        for mutation in (lambda sem: sem["categories"][0].update(observation_contributions=59),
                         lambda sem: sem["categories"].append(dict(category_id="pedestrian", observation_contributions=57,
                                                                  distinct_contributors=19)),
                         lambda sem: sem.update(semantic_max_loss=0),
                         lambda sem: sem.update(taxonomy_version="other")):
            with self.subTest(mutation=mutation):
                damaged = deepcopy(actual)
                mutation(damaged["releases"][0]["cells"][0]["semantic"])
                with self.assertRaises(AssertionError):
                    audit_semantics(data, config, damaged)

    def test_all_eighty_one_tiny_class_populations_match_independent_antichain_enumeration(self):
        for counts in itertools.product(range(3), repeat=3):
            observations = population(*counts)
            data = source([observations], end=200)
            for support in (1, 2, 3):
                with self.subTest(counts=counts, support=support):
                    config = policy(support=support)
                    expected = enumerate_catalog_cuts(config, observations)
                    actual = self.run_core(data, config)
                    cells = [cell for release in actual["releases"] for cell in release["cells"]]
                    if expected is None:
                        self.assertEqual(cells, [])
                    else:
                        self.assertEqual(len(cells), 1)
                        self.assertEqual(tuple(row["category_id"] for row in cells[0]["semantic"]["categories"]), expected)
                        self.assertEqual(cells[0]["observation_contributions"], len(observations))


if __name__ == "__main__":
    unittest.main()
