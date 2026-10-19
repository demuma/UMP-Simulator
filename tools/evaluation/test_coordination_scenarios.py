"""Independent analytical checks for frozen coordination-study sources."""
from copy import deepcopy
import hashlib
import json
import unittest

from coordination_scenarios import (PREDECLARED_SEEDS, make_case, replicate_scenarios,
                                    scenarios, validate_case)


def _support(case, cell, start, end):
    return {observation["id"] for batch in case["observations"]["batches"]
            if start <= batch["observed_at_ms"] < end
            for observation in batch["observations"] if observation["cell_id"] == cell}


def _position_cell(x, y, depth):
    # Independent integer bit calculation for 80-m, origin-zero fixture geometry.
    ix, iy, value = int(x * (2**depth) / 80), int(y * (2**depth) / 80), 3
    for shift in range(depth - 1, -1, -1):
        value = (value << 2) | ((ix >> shift) & 1) | (((iy >> shift) & 1) << 1)
    return value


def _normalized_fingerprint(case):
    paths = {}
    for batch in case["observations"]["batches"]:
        for observation in batch["observations"]:
            paths.setdefault(observation["id"], []).append(
                [batch["observed_at_ms"], observation["type"], observation["x"], observation["y"]])
    encoded = json.dumps(sorted(paths.values(), key=lambda p: json.dumps(p)), separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


class CoordinationScenarioTests(unittest.TestCase):
    def test_registry_and_invalid_requests(self):
        self.assertEqual(len(scenarios()), 6)
        self.assertEqual(len(set(scenarios())), 6)
        self.assertEqual(replicate_scenarios(), ["mixed_density", "regional_latency", "turnover"])
        self.assertEqual(PREDECLARED_SEEDS, tuple(range(19, 27)))
        for name, seed in (("absent", None), ("mixed_density", None), ("turnover", True),
                           ("regional_latency", -1), ("turnover", 2**63),
                           ("identity_turnover", 19)):
            with self.subTest(name=name, seed=seed), self.assertRaises(ValueError):
                make_case(name, seed)

    def test_all_sources_have_complete_half_open_cadence_and_exact_geometry(self):
        cases = [make_case(name) for name in scenarios()]
        cases += [make_case(name, 19) for name in replicate_scenarios()]
        for case in cases:
            with self.subTest(run=case["observations"]["run_id"]):
                source = case["observations"]
                self.assertEqual([b["observed_at_ms"] for b in source["batches"]],
                                 list(range(100, source["end_ms"], 100)))
                for batch in source["batches"]:
                    self.assertEqual(len({o["id"] for o in batch["observations"]}),
                                     len(batch["observations"]))
                    for observation in batch["observations"]:
                        self.assertEqual(observation["cell_id"], _position_cell(
                            observation["x"], observation["y"], source["coverage"]["leaf_depth"]))
                self.assertTrue(case["expected"]["no_asserted_algorithmic_winner"])

    def test_reporting_masks_are_disjoint_exhaustive_fixed_query_regions(self):
        reference = make_case(scenarios()[0])["regions"]
        for name in scenarios():
            self.assertEqual(make_case(name)["regions"], reference)
        for x in range(0, 80, 10):
            for y in range(0, 80, 10):
                matching = [r for r in reference if r["x"] <= x + 5 < r["x"] + r["width"]
                            and r["y"] <= y + 5 < r["y"] + r["height"]]
                self.assertEqual(len(matching), 1)
        self.assertEqual(sum(r["width"] * r["height"] for r in reference), 6400)

    def test_dense_control_and_impossible_branch_conditions(self):
        dense = make_case("homogeneous_dense_control")
        for cell in (192, 208, 224, 240):
            self.assertEqual(len(_support(dense, cell, 0, 400)), 3)
        blocked = make_case("blocked_branch")
        self.assertEqual(len(_support(blocked, 192, 0, 4000)), 1)
        self.assertEqual(len(_support(blocked, 208, 0, 4000)), 3)
        self.assertEqual(blocked["policy"]["spatial_selection"]["min_depth"], 1)

    def test_heterogeneous_deadlines_have_no_common_duration(self):
        case = make_case("heterogeneous_sibling_deadlines")
        slow, fast = case["policy"]["policy_regions"]
        self.assertEqual(slow["requirements"]["window_duration_ms"]["min"], 400)
        self.assertEqual(fast["requirements"]["window_duration_ms"]["max"], 200)
        self.assertGreater(slow["requirements"]["window_duration_ms"]["min"],
                           fast["requirements"]["window_duration_ms"]["max"])
        self.assertEqual(len(_support(case, 192, 0, 400)), 3)
        self.assertEqual(len(_support(case, 193, 0, 200)), 3)
        self.assertEqual(case["policy"]["policy_tree"]["root"]["cell_side_m"]["max"], 10)

    def test_turnover_changes_support_but_never_occupancy(self):
        case = make_case("identity_turnover")
        for batch in case["observations"]["batches"]:
            self.assertEqual(len(batch["observations"]), 2)
            self.assertEqual({(o["x"], o["y"]) for o in batch["observations"]}, {(5, 5), (15, 5)})
        for end, support in ((200, 1), (400, 2), (600, 3)):
            left, right = _support(case, 192, 0, end), _support(case, 193, 0, end)
            self.assertEqual(len(left), support)
            self.assertEqual(len(right), support)
            self.assertEqual(len(left | right), 2 * support)

    def test_publication_barrier_is_an_explicit_counterfactual(self):
        case = make_case("publication_barrier")
        self.assertEqual(len(_support(case, 193, 0, 200)), 3)
        self.assertEqual(len(_support(case, 192, 0, 400) | _support(case, 193, 0, 400)), 4)
        self.assertEqual(case["policy"]["policy_regions"][0]["requirements"]["window_duration_ms"]["min"], 400)
        self.assertTrue(case["expected"]["actual_runtime_barrier_not_asserted"])
        early = case["expected"]["hypothetical_early_release"]
        parent = case["expected"]["otherwise_feasible_parent"]
        self.assertEqual(early["cell_id"] // 4, parent["cell_id"])
        self.assertLess(early["start_ms"], parent["end_ms"])
        self.assertLess(parent["start_ms"], early["end_ms"])

    def test_a07_fixture_preserves_valid_child_and_invalid_parent_conditions(self):
        case = make_case("parent_infeasible_valid_children")
        self.assertEqual(len(_support(case, 192, 0, 400)), 2)
        self.assertEqual(len(_support(case, 193, 0, 400)), 1)
        contributions = lambda cell: sum(o["cell_id"] == cell for b in case["observations"]["batches"]
                                        if 0 <= b["observed_at_ms"] < 400 for o in b["observations"])
        self.assertEqual(contributions(192), 6)
        self.assertEqual(contributions(193), 3)
        self.assertGreater(20, case["policy"]["policy_tree"]["root"]["cell_side_m"]["max"])

    def test_seeded_realizations_are_deterministic_and_not_id_renamed_clones(self):
        fingerprints = set()
        for name in replicate_scenarios():
            for seed in PREDECLARED_SEEDS:
                first, second = make_case(name, seed), make_case(name, seed)
                self.assertEqual(first, second)
                fingerprint = _normalized_fingerprint(first)
                self.assertNotIn(fingerprint, fingerprints)
                fingerprints.add(fingerprint)
        self.assertEqual(len(fingerprints), 24)

    def test_mutations_do_not_leak_between_cases_and_validation_rejects_corruption(self):
        original = make_case("publication_barrier")
        changed = deepcopy(original)
        changed["observations"]["batches"][0]["observations"][0]["cell_id"] += 1
        with self.assertRaises(ValueError):
            validate_case(changed)
        mutations = [lambda c: c["observations"]["batches"].pop(),
                     lambda c: c["observations"]["batches"][0].update(observed_at_ms=0),
                     lambda c: c["observations"]["batches"][0]["observations"].append(
                         deepcopy(c["observations"]["batches"][0]["observations"][0])),
                     lambda c: c["observations"]["batches"][0]["observations"][0].update(x=float("nan")),
                     lambda c: c["regions"][0].update(width=50),
                     lambda c: c["policy"]["policy_tree"].update(regions=[])]
        for mutation in mutations:
            changed = deepcopy(original)
            mutation(changed)
            with self.assertRaises(ValueError):
                validate_case(changed)
        self.assertEqual(original, make_case("publication_barrier"))


if __name__ == "__main__":
    unittest.main()
