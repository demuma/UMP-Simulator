"""Hand-worked and adversarial tests for the bounded fixed-interval reference."""
from copy import deepcopy
import json
import unittest

from semantic_tradeoffs import (exact_category_contributions, geometry, pareto_candidates,
                               reference_candidates, score_candidate)


def taxonomy():
    return dict(id="tradeoff-taxonomy", version="1", nodes=[
        dict(id="road_user", loss=1),
        dict(id="pedestrian", parent="road_user", loss=0, input_types=["pedestrian"]),
        dict(id="cyclist", parent="road_user", loss=.5),
        dict(id="adult_cyclist", parent="cyclist", loss=0, input_types=["adult", "adult-alias"]),
        dict(id="child_cyclist", parent="cyclist", loss=0, input_types=["child"])])


def policy(support=5, loss=1):
    return dict(window_ms=400, history=dict(retention_ms=2000),
        spatial_selection=dict(min_depth=1, preserve_valid_descendants=True),
        temporal_adaptation=dict(coordination="common_window"), semantic_taxonomy=taxonomy(),
        policy_tree=dict(id="tradeoff-policy", version="1", root=dict(
            distinct_contributors=dict(min=1), cell_side_m=dict(min=20, max=40),
            window_duration_ms=dict(max=1000), age_at_evaluation_ms=dict(max=1000),
            min_category_distinct_contributors=dict(min=support), semantic_max_loss=dict(max=loss)), regions=[]),
        policy_regions=[])


def observation(identity, kind="pedestrian", cell_id=48):
    cell = geometry(cell_id)
    return dict(id=identity, type=kind, cell_id=cell_id, x=cell["x"] + 1, y=cell["y"] + 1)


def replay(samples=None, end=400):
    if samples is None:
        samples = [[] for _ in range(3)]
    batches = []
    for sequence, observations in enumerate(samples, 1):
        if observations == "missing":
            continue
        batches.append(dict(sequence=sequence, observed_at_ms=sequence * 100,
            status="unavailable" if observations is None else "measured",
            observations=[] if observations is None else observations))
    return dict(schema="ump.observation-replay.v1", run_id="tradeoff-hand", sensor_id="agbs",
        coverage=dict(x=0, y=0, width=80, height=80, leaf_depth=2), sampling_period_ms=100,
        end_ms=end, batches=batches)


def witness():
    rows = [observation("p" + str(i)) for i in range(19)] + [observation("rare", "adult")]
    rows += [observation("adult" + str(i), "adult", 49) for i in range(5)]
    return replay([deepcopy(rows) for _ in range(3)])


def bins(candidate):
    return tuple((cell["cell_id"], tuple(row["category_id"] for row in cell["semantic"]["categories"]))
                 for cell in candidate["cells"])


class ReferenceHandTests(unittest.TestCase):
    def test_hand_witness_fine_and_parent_are_incomparable(self):
        result = reference_candidates(witness(), policy(), 0, 400)
        self.assertEqual(result["source_contributions"], 75)
        self.assertIn("fixed actual interval", result["candidate_class"]["temporal"])
        fine = next(row for row in result["candidates"] if bins(row) == ((48, ("road_user",)), (49, ("adult_cyclist",))))
        parent = next(row for row in result["candidates"] if bins(row) == ((12, ("adult_cyclist", "pedestrian")),))
        self.assertEqual(fine["retained_contributions"], 75)
        self.assertEqual(parent["retained_contributions"], 75)
        self.assertEqual(fine["query20_coverage"], 5 / 16)
        self.assertEqual(fine["query40_coverage"], 0)
        self.assertAlmostEqual(fine["mean_semantic_loss"], .8)
        self.assertEqual(fine["max_semantic_loss"], 1)
        self.assertEqual(fine["contribution_weighted_cell_side_m"], 20)
        self.assertEqual(parent["query20_coverage"], 0)
        self.assertEqual(parent["query40_coverage"], 1)
        self.assertEqual(parent["mean_semantic_loss"], 0)
        self.assertEqual(parent["contribution_weighted_cell_side_m"], 40)
        frontier = pareto_candidates(result["candidates"])
        self.assertIn(fine, frontier)
        self.assertIn(parent, frontier)

    def test_absent_space_unknown_but_absent_class_within_complete_bin_known_zero(self):
        result = reference_candidates(witness(), policy(), 0, 400)
        fine = next(row for row in result["candidates"] if bins(row) == ((48, ("road_user",)), (49, ("adult_cyclist",))))
        empty_queries = [q for q in fine["query20"]["queries"] if q["cell_id"] in (50, 51)]
        self.assertTrue(all(not q["answered"] and q["observation_contributions"] is None for q in empty_queries))
        child = next(q for q in fine["query20"]["queries"] if q["cell_id"] == 49 and q["category"] == "child_cyclist")
        self.assertTrue(child["answered"])
        self.assertEqual(child["observation_contributions"], 0)
        semantic = fine["cells"][0]["semantic"]
        self.assertIsNone(exact_category_contributions(semantic, policy(), "cyclist"))

    def test_repeated_moving_identity_is_not_two_people(self):
        data = replay([[observation("same", "adult", 48)],
                       [observation("same", "adult-alias", 49)], []])
        failed = reference_candidates(data, policy(support=2), 0, 400)
        self.assertEqual(len(failed["candidates"]), 1)
        self.assertEqual(failed["candidates"][0]["retained_contributions"], 0)
        passed = reference_candidates(data, policy(support=1), 0, 400)
        parent = next(row for row in passed["candidates"] if bins(row) == ((12, ("adult_cyclist",)),))
        cell = parent["cells"][0]
        self.assertEqual(cell["observation_contributions"], 2)
        self.assertEqual(cell["distinct_road_users"], 1)
        self.assertEqual(exact_category_contributions(cell["semantic"], policy(support=1), "road_user"), 2)

    def test_region_intersection_applies_to_complete_parent(self):
        config = policy()
        config["policy_tree"]["regions"] = ["strict"]
        config["policy_regions"] = [dict(id="strict", type="entrance", x=0, y=0, width=20, height=20,
            type_requirements=dict(min_category_distinct_contributors=dict(min=7)),
            requirements=dict(semantic_max_loss=dict(max=0)))]
        result = reference_candidates(witness(), config, 0, 400)
        self.assertEqual(max(row["retained_contributions"] for row in result["candidates"]), 15)
        self.assertTrue(all(all(cell["cell_id"] == 49 for cell in row["cells"]) for row in result["candidates"]))
        self.assertTrue(any(item["cell_id"] == 12 and item["metric"] == "semantic_max_loss" for item in result["binding_failures"]))

    def test_mean_loss_can_force_whole_parent_instead_of_fine_generalization(self):
        config = policy()
        config["policy_tree"]["root"]["semantic_mean_loss"] = dict(max=.5)
        result = reference_candidates(witness(), config, 0, 400)
        self.assertTrue(any(row["retained_contributions"] == 75 and bins(row)[0][0] == 12 for row in result["candidates"]))
        self.assertTrue(all(all(cell["cell_id"] != 48 for cell in row["cells"]) for row in result["candidates"]))

    def test_complete_coverage_and_t0_exclusion(self):
        rows = [observation("a", "adult")]
        empty_interval = reference_candidates(replay([rows, rows, rows]), policy(support=1), 0, 100)
        self.assertEqual(empty_interval["source_contributions"], 0)
        self.assertEqual(empty_interval["coverage"]["expected"], 0)
        for absent in ("missing", None):
            with self.subTest(absent=absent):
                result = reference_candidates(replay([rows, absent, rows]), policy(support=1), 0, 400)
                self.assertEqual(len(result["candidates"]), 1)
                self.assertEqual(result["candidates"][0]["retained_contributions"], 0)
                self.assertEqual(result["source_contributions"], 2)
                self.assertTrue(any(failure["metric"] == "complete_coverage" for failure in result["binding_failures"]))

    def test_same_interval_actual_evaluation_age_and_half_open_endpoint(self):
        rows = [observation("a", "adult")]
        data = replay([rows, rows, rows, [observation("b", "adult")]], end=500)
        config = policy(support=1)
        config["policy_tree"]["root"]["age_at_evaluation_ms"] = dict(max=400)
        current = reference_candidates(data, config, 0, 400, 400)
        self.assertEqual(current["source_contributions"], 3)
        self.assertTrue(any(row["retained_contributions"] == 3 for row in current["candidates"]))
        late = reference_candidates(data, config, 0, 400, 450)
        self.assertEqual(max(row["retained_contributions"] for row in late["candidates"]), 0)
        self.assertTrue(any(row["metric"] == "age_at_evaluation_ms" for row in late["binding_failures"]))

    def test_budget_fails_closed_and_inputs_remain_unchanged(self):
        data, config = witness(), policy()
        before = json.dumps([data, config], sort_keys=True)
        with self.assertRaisesRegex(ValueError, "candidate budget"):
            reference_candidates(data, config, 0, 400, max_candidates=1)
        self.assertEqual(before, json.dumps([data, config], sort_keys=True))

    def test_minimum_depth_excludes_parent_and_empty_control_has_undefined_detail(self):
        config = policy(); config["spatial_selection"]["min_depth"] = 2
        result = reference_candidates(witness(), config, 0, 400)
        self.assertTrue(all(all(cell["cell_id"] != 12 for cell in row["cells"]) for row in result["candidates"]))
        empty = result["candidates"][0]
        self.assertEqual(empty["cells"], [])
        self.assertEqual((empty["query20_coverage"], empty["query40_coverage"]), (0, 0))
        self.assertIsNone(empty["mean_semantic_loss"])
        self.assertIsNone(empty["contribution_weighted_cell_side_m"])
        self.assertNotIn(empty, pareto_candidates(result["candidates"]))
        self.assertEqual(pareto_candidates([empty]), [empty])


class ReferenceAdversarialTests(unittest.TestCase):
    def test_source_scope_and_identity_mutations_reject(self):
        mutations = [
            lambda data: data["coverage"].update(leaf_depth=3),
            lambda data: data["batches"][0]["observations"][0].update(cell_id=63, x=61, y=61),
            lambda data: data["batches"][0]["observations"][0].update(x=20),
            lambda data: data["batches"][0]["observations"][0].update(type="unknown"),
            lambda data: data["batches"][0]["observations"].append(deepcopy(data["batches"][0]["observations"][0])),
            lambda data: data["batches"][1]["observations"][0].update(type="adult"),
            lambda data: data["batches"][0].update(observed_at_ms=0),
            lambda data: data["batches"][1].update(sequence=1),
            lambda data: data["batches"][0].update(status="unavailable")]
        for mutate in mutations:
            data = witness(); mutate(data)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                reference_candidates(data, policy(), 0, 400)

    def test_policy_catalog_and_unsupported_context_reject(self):
        mutations = [
            lambda config: config["temporal_adaptation"].update(coordination="cell_local"),
            lambda config: config["policy_tree"]["root"].update(occupancy_mae=dict(max=1)),
            lambda config: config["policy_tree"]["root"].update(min_category_distinct_contributors=dict(max=5)),
            lambda config: config["policy_tree"]["root"].update(semantic_max_loss=dict(max=1.1)),
            lambda config: config["semantic_taxonomy"]["nodes"][1].update(parent="pedestrian"),
            lambda config: config["semantic_taxonomy"]["nodes"][3].update(input_types=["pedestrian"]),
            lambda config: config["policy_tree"].update(regions=["undefined"])]
        for mutate in mutations:
            config = policy(); mutate(config)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                reference_candidates(witness(), config, 0, 400)

    def test_public_mutations_do_not_create_answerable_queries(self):
        config = policy()
        result = reference_candidates(witness(), config, 0, 400)
        parent = next(row for row in result["candidates"] if bins(row) == ((12, ("adult_cyclist", "pedestrian")),))
        mutations = [
            lambda cells: cells.append(deepcopy(cells[0])),
            lambda cells: cells[0].update(width=20),
            lambda cells: cells[0].update(observation_contributions=74),
            lambda cells: cells[0]["semantic"].update(semantic_max_loss=1),
            lambda cells: cells[0]["semantic"]["categories"].append(dict(category_id="road_user", observation_contributions=75, distinct_contributors=25)),
            lambda cells: cells[0]["semantic"]["categories"][0].update(category_id="unknown")]
        for mutate in mutations:
            cells = deepcopy(parent["cells"]); mutate(cells)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                score_candidate(cells, config, 0, 400, 75)


if __name__ == "__main__":
    unittest.main()
