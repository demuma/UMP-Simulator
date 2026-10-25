"""Small hand-derived channel/property tests, with no native execution or fitting."""
from copy import deepcopy
import json
import math
import unittest

import empirical_privacy as legacy
import semantic_privacy as channel


def taxonomy():
    return {"id": "public-road-users", "version": "1", "nodes": [
        {"id": "road", "loss": 1},
        {"id": "active", "parent": "road", "loss": .5},
        {"id": "walk", "parent": "active", "loss": 0, "input_types": ["private-walking-label"]},
        {"id": "bike", "parent": "active", "loss": 0, "input_types": ["private-bike-label"]},
        {"id": "motor", "parent": "road", "loss": 0, "input_types": ["private-motor-label"]}]}


def private_result():
    return {"schema": "ump.replay-result.v1", "configuration_yaml": "private scenario",
        "source": {"run_id": "private-run", "sensor_id": "private-sensor", "application_id": "private-app",
            "coverage": {"x": 0, "y": 0, "width": 80, "height": 80, "leaf_depth": 2},
            "sampling_period_ms": 100, "end_ms": 1000},
        "windows": [{"raw_ids": ["private-target"], "suppression_reason": "private"}],
        "input_observation_contributions": 99999,
        "releases": [{"release_id": "private-run/window-0", "start_ms": 0, "end_ms": 400,
            "sealed_at_ms": 500, "model": "private_final_snapshot", "policy_id": "public-policy",
            "policy_version": "1", "cells": [{"cell_id": 12, "depth": 1, "x": 0, "y": 0,
                "width": 40, "height": 40, "observation_contributions": 6,
                "distinct_road_users": 3, "mean_sample_occupancy": None, "effective_policy_id": "public-root",
                "semantic": {"schema": "ump.semantic-release.v1", "taxonomy_id": "public-road-users",
                    "taxonomy_version": "1", "min_category_distinct_contributors": 1,
                    "semantic_mean_loss": 1 / 3, "semantic_max_loss": .5,
                    "categories": [{"category_id": "active", "observation_contributions": 4, "distinct_contributors": 2},
                        {"category_id": "motor", "observation_contributions": 2, "distinct_contributors": 1}]}}]}]}


def point(time=100, x=1, y=1, cell_id=48):
    return {"observed_at_ms": time, "x": x, "y": y, "cell_id": cell_id}


def feature_dict(public, knowledge):
    return dict(zip(channel.feature_names(public), channel.feature_vector(public, knowledge)))


class SemanticChannelTests(unittest.TestCase):
    def public(self, **kwargs):
        return channel.export_public(private_result(), taxonomy(), **kwargs)

    def test_complete_allowlist_export_and_private_invariance(self):
        original = private_result()
        before = deepcopy(original)
        original["releases"][0]["coordination_cell"] = {key: original["releases"][0]["cells"][0][key]
            for key in ("cell_id", "depth", "x", "y", "width", "height")}
        public = channel.export_public(original, taxonomy())
        changed = deepcopy(original)
        changed["source"].update(run_id="other-secret", target_id="private-target")
        changed.update(configuration_yaml="different secret", windows=[{"private": True}], label=True,
                       runtime={"ms": 99999}, input_observation_contributions=3)
        changed["releases"][0]["release_id"] = "other-secret/window"
        self.assertEqual(public, channel.export_public(changed, taxonomy()))
        encoded = json.dumps(public, allow_nan=False)
        for private in ("private-run", "private-target", "private-walking-label", "configuration", "windows", "runtime", "input_types"):
            self.assertNotIn(private, encoded)
        self.assertEqual(public["schema"], channel.PUBLIC_SCHEMA)
        self.assertEqual(public["availability_model"], "final_snapshot_at_horizon")
        self.assertEqual(public["releases"][0]["available_at_ms"], 1000)
        self.assertEqual(public["releases"][0]["sealed_at_ms"], 500)
        self.assertIn("coordination_cell", public["releases"][0])
        self.assertIsNone(public["releases"][0]["cells"][0]["mean_sample_occupancy"])
        self.assertEqual(set(public["taxonomy"]["nodes"][0]), {"id", "parent", "loss"})
        public["releases"][0]["cells"][0]["semantic"]["categories"][0]["observation_contributions"] = 100
        self.assertEqual(original["releases"][0]["cells"], before["releases"][0]["cells"])

    def test_all_nested_unknown_public_fields_fail(self):
        for level in ("top", "coverage", "taxonomy", "node", "release", "cell", "semantic", "bin", "scope"):
            public = self.public()
            release = public["releases"][0]
            cell = release["cells"][0]
            release["coordination_cell"] = {key: cell[key] for key in ("cell_id", "depth", "x", "y", "width", "height")}
            objects = {"top": public, "coverage": public["coverage"], "taxonomy": public["taxonomy"],
                "node": public["taxonomy"]["nodes"][0], "release": release, "cell": cell,
                "semantic": cell["semantic"], "bin": cell["semantic"]["categories"][0],
                "scope": release["coordination_cell"]}
            objects[level]["private_ids"] = ["private-target"]
            with self.subTest(level=level), self.assertRaisesRegex(ValueError, "unknown"):
                channel.validate_public(public)
        for level in ("release", "cell", "semantic", "bin"):
            private = private_result()
            release = private["releases"][0]
            cell = release["cells"][0]
            {"release": release, "cell": cell, "semantic": cell["semantic"],
                "bin": cell["semantic"]["categories"][0]}[level]["suppression_mask"] = [True]
            with self.subTest(export_level=level), self.assertRaisesRegex(ValueError, "unknown"):
                channel.export_public(private, taxonomy())

    def test_semantic_invariants_and_exact_scalar_types(self):
        mutations = [
            lambda p, c, s: s.update(taxonomy_id="wrong"),
            lambda p, c, s: s.update(taxonomy_version=1),
            lambda p, c, s: s.update(schema="future.schema"),
            lambda p, c, s: s.update(categories=[]),
            lambda p, c, s: s["categories"][0].update(category_id="missing"),
            lambda p, c, s: s["categories"][0].update(category_id="road"),
            lambda p, c, s: s["categories"][0].update(category_id="motor"),
            lambda p, c, s: s["categories"][0].update(observation_contributions=3),
            lambda p, c, s: s["categories"][0].update(distinct_contributors=3),
            lambda p, c, s: s["categories"][0].update(distinct_contributors=0),
            lambda p, c, s: s["categories"][0].update(distinct_contributors=5),
            lambda p, c, s: s.update(min_category_distinct_contributors=2),
            lambda p, c, s: s.update(semantic_mean_loss=.4),
            lambda p, c, s: s.update(semantic_max_loss=1),
            lambda p, c, s: c.update(distinct_road_users=2),
            lambda p, c, s: c.update(distinct_road_users=True),
            lambda p, c, s: c.update(observation_contributions=6.0),
            lambda p, c, s: c.update(observation_contributions=2**53),
            lambda p, c, s: c.update(mean_sample_occupancy=True),
            lambda p, c, s: c.update(effective_policy_id="\x00secret"),
            lambda p, c, s: c.update(mean_sample_occupancy=10**1000),
            lambda p, c, s: c.update(x=10**1000),
        ]
        for key in ("min_category_distinct_contributors", "semantic_mean_loss", "semantic_max_loss"):
            for bad in (True, float("nan"), float("inf"), -1, None):
                mutations.append(lambda p, c, s, key=key, bad=bad: s.update({key: bad}))
        for mutation in mutations:
            public = self.public()
            cell = public["releases"][0]["cells"][0]
            mutation(public, cell, cell["semantic"])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                channel.validate_public(public)

    def test_taxonomy_structure_identity_loss_and_order(self):
        mutations = [lambda t: t.update(version=1), lambda t: t.update(id="x\nsecret"),
            lambda t: t["nodes"][0].update(loss=.9),
            lambda t: t["nodes"][1].update(parent="unknown"),
            lambda t: t["nodes"][1].update(loss=1.1),
            lambda t: t["nodes"][2].update(loss=.2),
            lambda t: t["nodes"][2].update(id="bike"),
            lambda t: t["nodes"][2].update(parent="walk"),
            lambda t: t["nodes"][1].update(parent="walk"),
            lambda t: t["nodes"][1].update(loss=True),
            lambda t: t["nodes"][1].update(loss=float("nan"))]
        for mutate in mutations:
            value = taxonomy()
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                channel.public_taxonomy(value)
        value = taxonomy()
        value["nodes"].reverse()
        self.assertEqual(channel.public_taxonomy(value), channel.public_taxonomy(taxonomy()))
        public = self.public()
        public["taxonomy"]["nodes"].reverse()
        with self.assertRaisesRegex(ValueError, "order"):
            channel.validate_public(public)
        public = self.public()
        next(node for node in public["taxonomy"]["nodes"] if node["id"] == "active")["loss"] = .7
        with self.assertRaisesRegex(ValueError, "metric"):
            channel.validate_public(public)

    def test_geometry_scope_overlap_half_open_and_horizon(self):
        for mutate in (lambda p: p["releases"][0]["cells"][0].update(x=1),
            lambda p: p["releases"][0]["cells"][0].update(depth=True),
            lambda p: p["releases"][0].update(end_ms=1001),
            lambda p: p["releases"][0].update(sealed_at_ms=1001),
            lambda p: p["releases"][0].update(start_ms=False),
            lambda p: p["coverage"].update(width=40)):
            public = self.public()
            mutate(public)
            with self.assertRaises(ValueError):
                channel.validate_public(public)
        public = self.public()
        first = public["releases"][0]
        second = deepcopy(first)
        second.update(release_id="release-000001", start_ms=300, end_ms=600, sealed_at_ms=600)
        public["releases"].append(second)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            channel.validate_public(public)
        second.update(start_ms=400)
        channel.validate_public(public)
        # Concurrent windows are valid in spatially disjoint scopes.
        second.update(start_ms=100)
        second["cells"][0].update(cell_id=13, x=40)
        channel.validate_public(public)
        first["coordination_cell"] = {key: first["cells"][0][key] for key in ("cell_id", "depth", "x", "y", "width", "height")}
        first["coordination_cell"]["x"] = 40
        with self.assertRaisesRegex(ValueError, "scope"):
            channel.validate_public(public)

    def test_overlapping_parent_child_and_nonmonotone_availability_fail(self):
        public = self.public()
        child = deepcopy(public["releases"][0]["cells"][0])
        child.update(cell_id=48, depth=2, width=20, height=20)
        public["releases"][0]["cells"].append(child)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            channel.validate_public(public)
        logical = self.public(availability_model="logical_sealing")
        second = deepcopy(logical["releases"][0])
        second.update(release_id="release-000001", start_ms=400, end_ms=450,
                      sealed_at_ms=450, available_at_ms=450)
        logical["releases"].append(second)
        with self.assertRaisesRegex(ValueError, "availability"):
            channel.validate_public(logical)
        public = self.public()
        release = public["releases"][0]
        release["coordination_cell"] = {key: release["cells"][0][key]
            for key in ("cell_id", "depth", "x", "y", "width", "height")}
        release["coordination_cell"]["depth"] = True
        with self.assertRaises(ValueError):
            channel.validate_public(public)

    def test_native_long_alias_and_ancestor_coordination_scope(self):
        raw = private_result()
        raw["releases"][0]["release_id"] = "private-native-namespace/" + "x" * 400
        release = raw["releases"][0]
        release["coordination_cell"] = {key: release["cells"][0][key]
            for key in ("cell_id", "depth", "x", "y", "width", "height")}
        first = release["cells"][0]
        first.update(cell_id=48, depth=2, width=20, height=20)
        second = deepcopy(first)
        second.update(cell_id=49, x=20)
        release["cells"].append(second)
        public = channel.export_public(raw, taxonomy())
        self.assertEqual(public["releases"][0]["release_id"], "release-000000")
        self.assertEqual(public["releases"][0]["coordination_cell"]["cell_id"], 12)
        outside = deepcopy(public)
        outside["releases"][0]["cells"][1].update(cell_id=52, x=40)
        with self.assertRaisesRegex(ValueError, "scope"):
            channel.validate_public(outside)
        changed = deepcopy(public)
        changed["releases"][0].pop("coordination_cell")
        self.assertNotEqual(channel.canonical_transcript(public), channel.canonical_transcript(changed))

    def test_snapshot_and_explicit_sealing_gate_whole_releases(self):
        snapshot = self.public()
        before = deepcopy(snapshot)
        self.assertEqual(channel.public_view(snapshot, 999)["releases"], [])
        self.assertEqual(channel.public_view(snapshot, 1000), snapshot)
        logical = self.public(availability_model="logical_sealing")
        self.assertEqual(logical["releases"][0]["available_at_ms"], 500)
        self.assertEqual(channel.public_view(logical, 499)["releases"], [])
        self.assertEqual(channel.public_view(logical, 500)["releases"], logical["releases"])
        self.assertEqual(channel.public_view(logical, 600, recent_window_ms=100)["releases"], [])
        self.assertEqual(snapshot, before)
        for now in (True, -1, 1001, float("nan")):
            with self.assertRaises(ValueError):
                channel.public_view(snapshot, now)
        for model in ("sealed", None, True):
            with self.assertRaises(ValueError):
                self.public(availability_model=model)
        for available in (400, 500, 1001, True, 1000.0):
            bad = deepcopy(snapshot)
            bad["releases"][0]["available_at_ms"] = available
            with self.assertRaises(ValueError):
                channel.validate_public(bad)
        # An EOF release may be delivered only at H, never backdated into an interior view.
        raw = private_result()
        raw["releases"][0].update(end_ms=1000, sealed_at_ms=1000)
        final = channel.export_public(raw, taxonomy(), availability_model="logical_sealing")
        self.assertEqual(channel.public_view(final, 999)["releases"], [])
        self.assertEqual(len(channel.public_view(final, 1000)["releases"]), 1)

    def test_fixed_order_features_and_unknown_parent_descendant_semantics(self):
        public = self.public()
        names = channel.feature_names(public)
        values = feature_dict(public, [point()])
        old = legacy.feature_vector(channel._scalar_projection(public), [point()])
        self.assertEqual(channel.feature_vector(public, [point()])[:len(old)], old)
        self.assertEqual(values["category[active].public_contributions_sum"], 4)
        self.assertEqual(values["category[active].public_distinct_support_sum"], 2)
        self.assertEqual(values["category[active].target_published_fraction"], 1)
        self.assertEqual(values["category[active].target_contributions_mean"], 4)
        self.assertEqual(values["category[walk].target_published_fraction"], 0)
        self.assertEqual(values["category[walk].target_contributions_mean"], 0)
        self.assertEqual(values["semantic.public_semantic_mean_loss_mean"], 1 / 3)
        self.assertEqual(values["semantic.release_availability_delay_mean_ms"], 600)
        self.assertEqual(values["semantic.target_availability_age_mean_ms"], 900)
        absent = feature_dict(public, [point(time=400)])
        self.assertEqual(absent["category[active].target_published_fraction"], 0)
        public["releases"] = []
        self.assertEqual(channel.feature_names(public), names)
        self.assertEqual(feature_dict(public, [point()])["category[active].public_published_cell_fraction"], 0)
        unknown = self.public()
        zero = deepcopy(unknown)
        zero["releases"][0]["cells"][0]["mean_sample_occupancy"] = 0
        self.assertEqual(feature_dict(unknown, [point()])["scalar.target_mean_occupancy_mean"], 0)
        self.assertEqual(feature_dict(zero, [point()])["scalar.target_mean_occupancy_mean"], 0)
        self.assertEqual(feature_dict(unknown, [point()])["scalar.target_mean_known_fraction"], 0)
        self.assertEqual(feature_dict(zero, [point()])["scalar.target_mean_known_fraction"], 1)
        for bad in ([dict(point(), target_id="private")], [point(), point()], [point(cell_id=49)]):
            with self.assertRaises(ValueError):
                channel.feature_vector(self.public(), bad)

    def test_canonical_complete_channel_and_legacy_rejection(self):
        public = self.public()
        canonical = channel.canonical_transcript(public)
        changed = deepcopy(public)
        changed["releases"][0]["cells"][0]["semantic"]["categories"].reverse()
        self.assertEqual(canonical, channel.canonical_transcript(changed))
        changed = deepcopy(public)
        changed["releases"][0]["policy_version"] = "2"
        self.assertNotEqual(canonical, channel.canonical_transcript(changed))
        changed = self.public(availability_model="logical_sealing")
        self.assertNotEqual(canonical, channel.canonical_transcript(changed))
        with self.assertRaises(ValueError):
            legacy.export_public(private_result())
        with self.assertRaises(ValueError):
            legacy.feature_vector(public, [])

    def test_semantic_only_change_is_visible_with_fixed_scalar_projection(self):
        left = self.public()
        right = deepcopy(left)
        semantic = right["releases"][0]["cells"][0]["semantic"]
        semantic["categories"][0]["observation_contributions"] = 3
        semantic["categories"][1]["observation_contributions"] = 3
        semantic["semantic_mean_loss"] = .25
        channel.validate_public(right)
        self.assertEqual(channel._scalar_projection(left), channel._scalar_projection(right))
        self.assertEqual(legacy.feature_vector(channel._scalar_projection(left), [point()]),
                         legacy.feature_vector(channel._scalar_projection(right), [point()]))
        self.assertNotEqual(channel.canonical_transcript(left), channel.canonical_transcript(right))
        self.assertNotEqual(channel.feature_vector(left, [point()]), channel.feature_vector(right, [point()]))
        changed = deepcopy(left)
        second = deepcopy(changed["releases"][0])
        second.update(release_id="release-000001", start_ms=400, end_ms=800, sealed_at_ms=800)
        changed["releases"].append(second)
        for release in changed["releases"]:
            release["cells"][0]["mean_sample_occupancy"] = 1e308
        with self.assertRaisesRegex(ValueError, "finite"):
            channel.feature_vector(changed, [])

    def test_valid_count_property_and_feature_support_sums(self):
        # Cover independently generated exact counts and loss arithmetic; no native executable.
        for active in range(1, 7):
            for motor in range(1, 4):
                raw = private_result()
                cell = raw["releases"][0]["cells"][0]
                bins = cell["semantic"]["categories"]
                bins[0].update(observation_contributions=active, distinct_contributors=active)
                bins[1].update(observation_contributions=motor, distinct_contributors=motor)
                cell.update(observation_contributions=active + motor, distinct_road_users=active + motor)
                cell["semantic"].update(min_category_distinct_contributors=min(active, motor),
                    semantic_mean_loss=.5 * active / (active + motor))
                public = channel.export_public(raw, taxonomy())
                self.assertTrue(all(math.isfinite(value) for value in channel.feature_vector(public, [])))
                bad = deepcopy(public)
                bad["releases"][0]["cells"][0]["semantic"]["categories"][0]["observation_contributions"] += 1
                with self.assertRaises(ValueError):
                    channel.validate_public(bad)
        public = self.public()
        second = deepcopy(public["releases"][0])
        second.update(release_id="release-000001", start_ms=400, end_ms=800, sealed_at_ms=800)
        public["releases"].append(second)
        values = feature_dict(public, [])
        self.assertEqual(values["scalar.public_distinct_support_sum"], 6)
        self.assertEqual(values["category[active].public_distinct_support_sum"], 4)
        # This is a support sum across intervals; no whole-history unique union is claimed.

    def test_causal_extension_invariance_and_feature_dimensions(self):
        logical = self.public(availability_model="logical_sealing")
        extended = deepcopy(logical)
        second = deepcopy(logical["releases"][0])
        second.update(release_id="release-000001", start_ms=400, end_ms=800, sealed_at_ms=900, available_at_ms=900)
        extended["releases"].append(second)
        events = [{"acquired_at_ms": 100, "available_at_ms": 100, "reported": point()}]
        self.assertEqual(channel.public_view(logical, 600), channel.public_view(extended, 600))
        self.assertEqual(channel.feature_views(logical, events, 600), channel.feature_views(extended, events, 600))
        views = channel.feature_views(self.public(), events, 600)
        # Snapshot means output stays absent despite an earlier logical seal.
        offset = len(channel.causal_feature_names(logical, "auxiliary"))
        self.assertEqual(views["recent"][offset], 0)
        for name, vector in views.items():
            self.assertEqual(len(channel.causal_feature_names(logical, name)), len(vector))
        for geometry in (False, True):
            self.assertEqual(len(channel.feature_names(logical, geometry)),
                             len(channel.feature_vector(logical, [point()], geometry)))


if __name__ == "__main__":
    unittest.main()
