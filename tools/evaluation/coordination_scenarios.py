"""Frozen analytical inputs for comparing common and cell-local coordination.

These fixtures test aggregation mechanisms. They are not calibrated traffic or
physical pedestrian simulations. Time zero initializes replay state; every actual
measurement is on the 100-ms cadence, and the final endpoint is excluded. Regions
are disjoint fixed reporting masks, independent of adaptive output geometry.

The six small mechanism fixtures have hand-checkable support and policy conditions.
Their expected metadata describes those conditions, never an asserted algorithmic
winner. Independent seeded realizations use random.Random only. Their paths,
population schedules and source observations are frozen before any policy variant
is evaluated, and have no CPU-clock or production-simulator randomness dependency.
"""
from __future__ import annotations

from copy import deepcopy
import math
import random

from make_fixture import cell_id

PERIOD_MS = 100
PREDECLARED_SEEDS = tuple(range(19, 27))
MECHANISM_SCENARIOS = (
    "homogeneous_dense_control", "blocked_branch", "heterogeneous_sibling_deadlines",
    "identity_turnover", "publication_barrier", "parent_infeasible_valid_children",
)
REPLICATE_SCENARIOS = ("mixed_density", "regional_latency", "turnover")


def scenarios() -> list[str]:
    """Names of the six finite, explanatory mechanism cases."""
    return list(MECHANISM_SCENARIOS)


def replicate_scenarios() -> list[str]:
    """Families for independent seeded realizations; not additional mechanisms."""
    return list(REPLICATE_SCENARIOS)


def _grid(depth: int) -> dict:
    return dict(x=0, y=0, width=80, height=80, leaf_depth=depth)


def _reporting_regions() -> list[dict]:
    # These masks cover the complete domain and snap to the fixed 10-m query grid.
    return [dict(id=name, x=x, y=y, width=40, height=40)
            for name, x, y in (("north_west", 0, 0), ("north_east", 40, 0),
                               ("south_west", 0, 40), ("south_east", 40, 40))]


def _region(name: str, x: float, y: float, width: float, height: float,
            requirements: dict) -> dict:
    return dict(id=name, type="analytical_constraint", x=x, y=y,
                width=width, height=height, requirements=deepcopy(requirements))


def _policy(support: int = 3, side: int = 40, minimum_depth: int = 1,
            regions: tuple | list = ()) -> dict:
    """One source policy; study variants must explicitly choose action order/mode."""
    return dict(application_id="coordination-study", window_ms=200,
        max_observations_per_window=1000000,
        history=dict(retention_ms=2000, max_bins=32, max_observations=100000,
                     max_identity_bytes=16000000, max_buckets=128),
        spatial_selection=dict(min_depth=minimum_depth, max_evaluations=4096),
        temporal_adaptation=dict(extension_step_ms=100, max_window_ms=1000,
                                 max_evaluations=32, coordination="common_window",
                                 max_active_cells=1024),
        policy_tree=dict(id="coordination-study-policy", version="1", max_nodes=65536,
            execution=dict(publication_model="private_final_snapshot", strategy="spatial_first"),
            root=dict(distinct_contributors=dict(min=support), cell_side_m=dict(max=side),
                      window_duration_ms=dict(max=1000), age_at_evaluation_ms=dict(max=1000)),
            regions=[r["id"] for r in regions]), policy_regions=deepcopy(list(regions)))


def _observation(identity: str, x: float, y: float, grid: dict,
                 kind: str = "pedestrian") -> dict:
    x, y = round(x, 8), round(y, 8)
    return dict(id=identity, type=kind, x=x, y=y, cell_id=cell_id(x, y, grid))


def _source(name: str, depth: int, end_ms: int, population) -> dict:
    grid = _grid(depth)
    batches = [dict(sequence=sequence, observed_at_ms=time, status="measured",
                    observations=population(time, grid))
               for sequence, time in enumerate(range(PERIOD_MS, end_ms, PERIOD_MS), 1)]
    return dict(schema="ump.observation-replay.v1", run_id="coordination-" + name,
                sensor_id="ideal-agbs", coverage=grid, sampling_period_ms=PERIOD_MS,
                end_ms=end_ms, batches=batches)


def _fixed(clusters: list[tuple[str, float, float, int]], turnover_ms: int = 0):
    def population(time: int, grid: dict) -> list[dict]:
        result = []
        for label, x, y, count in clusters:
            generation = (time // turnover_ms) if turnover_ms else 0
            for index in range(count):
                # All points stay strictly inside their named 10-m finest cell.
                result.append(_observation(f"{label}-{generation}-{index}",
                    x + 0.15 * index, y + 0.1 * index, grid))
        return result
    return population


def _mechanism(name: str) -> dict:
    policy = _policy()
    expected = dict(conditions_only=True, no_asserted_algorithmic_winner=True)
    if name == "homogeneous_dense_control":
        clusters = [("nw", 5, 5, 3), ("ne", 45, 5, 3),
                    ("sw", 5, 45, 3), ("se", 45, 45, 3)]
        description = "Four independent finest cells have three stable identities each; all satisfy support without coarsening."
        expected.update(occupancy_per_sample=12, finest_support=3, occupied_finest_cells=4)
        population = _fixed(clusters)
    elif name == "blocked_branch":
        population = _fixed([("impossible-nw", 5, 5, 1), ("valid-ne", 45, 5, 3),
                             ("valid-sw", 5, 45, 3)])
        description = "A stable singleton cannot reach support three inside its legal base quadrant; other base quadrants are independently valid."
        expected.update(occupancy_per_sample=7, impossible_region="north_west",
                        impossible_maximum_support=1, independent_valid_regions=["north_east", "south_west"])
    elif name == "heterogeneous_sibling_deadlines":
        policy = _policy(side=10, regions=[
            _region("slow-sibling", 0, 0, 10, 10, dict(window_duration_ms=dict(min=400))),
            _region("fast-sibling", 10, 0, 10, 10, dict(window_duration_ms=dict(max=200)))])
        population = _fixed([("slow", 5, 5, 3), ("fast", 15, 5, 3)])
        description = "Two finest siblings both pass support; one requires at least 400 ms and the other at most 200 ms. A 10-m size cap isolates temporal coordination."
        expected.update(occupancy_per_sample=6, slow_cell_id=192, fast_cell_id=193,
                        slow_minimum_ms=400, fast_maximum_ms=200,
                        shared_duration_feasible=False)
    elif name == "identity_turnover":
        population = _fixed([("left", 5, 5, 1), ("right", 15, 5, 1)], turnover_ms=200)
        description = "Two fixed occupied cells retain occupancy one while distinct source identities turn over every 200 ms; handovers are analytical capture schedules."
        expected.update(occupancy_per_sample=2, handover_ms=200,
                        support_intervals=[dict(start_ms=0, end_ms=200, support_per_finest_cell=1, parent_support=2),
                                           dict(start_ms=0, end_ms=400, support_per_finest_cell=2, parent_support=4),
                                           dict(start_ms=0, end_ms=600, support_per_finest_cell=3, parent_support=6)])
    elif name == "publication_barrier":
        policy = _policy(side=20, minimum_depth=2, regions=[
            _region("delayed-sparse-sibling", 0, 0, 10, 10,
                    dict(window_duration_ms=dict(min=400)))])
        population = _fixed([("sparse", 5, 5, 1), ("ready", 15, 5, 3)])
        description = "The ready sibling can release at 200 ms; its sparse sibling forces a common parent interval of at least 400 ms. Immediate release would block that parent's overlapping replacement. This is a counterfactual opportunity, not an asserted runtime barrier."
        expected.update(occupancy_per_sample=4,
                        hypothetical_early_release=dict(cell_id=193, depth=3, start_ms=0, end_ms=200, support=3),
                        otherwise_feasible_parent=dict(cell_id=48, depth=2, start_ms=0, end_ms=400, support=4),
                        parent_before_400_ms_feasible=False,
                        actual_runtime_barrier_not_asserted=True)
    elif name == "parent_infeasible_valid_children":
        policy = _policy(support=2, side=10, minimum_depth=2)
        population = _fixed([("valid-child", 5, 5, 2), ("failing-child", 15, 5, 1),
                             ("independent", 45, 5, 2)])
        description = "A support-valid 10-m child sits next to a singleton. Their 20-m parent violates the size cap; a relaxed partial-child rescue may retain the valid child's contributions."
        expected.update(occupancy_per_sample=5, valid_child_id=192, failing_child_id=193,
                        invalid_parent_id=48, parent_side_m=20, maximum_side_m=10,
                        interval=dict(start_ms=0, end_ms=400, samples=3,
                                      valid_child_contributions=6, failing_child_contributions=3),
                        rescue_is_model_comparison=True)
    else:
        raise ValueError(f"Unknown mechanism scenario: {name}")
    return dict(observations=_source(name, 3, 4000, population), policy=policy,
                regions=_reporting_regions(), description=description, kind="mechanism",
                seed=None, expected=expected)


def _replicate(name: str, seed: int) -> dict:
    # Python's Random receives an integer seed directly; family separation avoids
    # accidentally treating the same random realization under two names as replicas.
    family_index = REPLICATE_SCENARIOS.index(name)
    rng = random.Random(seed * 1009 + family_index * 1000003)
    actors = []
    policy_regions = []
    for region_index, region in enumerate(_reporting_regions()):
        if name == "mixed_density":
            count = rng.randint(1, 4) if region_index == 0 else rng.randint(6, 16)
        else:
            count = rng.randint(4, 12)
        if name == "regional_latency":
            duration = dict(min=400) if region_index in (0, 2) else dict(max=200)
            policy_regions.append(_region("latency-" + region["id"], region["x"], region["y"],
                                           40, 40, dict(window_duration_ms=duration)))
        for index in range(count):
            # Compact horizontal corridors stay within their assigned base quadrant.
            # Different draws change physical source geometry/population/timing,
            # rather than merely relabeling identities.
            y = region["y"] + rng.choice((7.5, 17.5, 27.5)) + rng.uniform(-1, 1)
            actors.append(dict(identity=f"r{region_index}-{index}", x0=rng.uniform(4, 34),
                base_x=region["x"], y=y, speed=rng.uniform(0.2, 1.4),
                starts=rng.choice((0, 0, 100, 300)),
                ends=rng.choice((6500, 7000, 8000)) if name == "mixed_density" else 8000,
                turnover=rng.choice((300, 400, 500, 700)), phase=rng.randrange(0, 200, 100),
                kind=rng.choice(("pedestrian", "pedestrian", "bicycle"))))

    def population(time: int, grid: dict) -> list[dict]:
        result = []
        for actor in actors:
            if not actor["starts"] <= time < actor["ends"]:
                continue
            if name == "turnover":
                # Fixed position and analytical identity handover isolate support
                # accumulation from occupancy movement; no physical jump claim.
                local_x = actor["x0"]
                generation = (time + actor["phase"]) // actor["turnover"]
            else:
                local_x = actor["x0"] + actor["speed"] * (time - actor["starts"]) / 1000
                generation = 0
            # A periodic 32-m prescribed path remains strictly inside the quadrant.
            x = actor["base_x"] + 4 + (local_x - 4) % 32
            result.append(_observation(f"{actor['identity']}-g{generation}", x, actor["y"], grid,
                                       actor["kind"]))
        return result

    description = {
        "mixed_density": "Seeded sparse and dense base quadrants with prescribed bounded motion and capture starts/ends.",
        "regional_latency": "Seeded prescribed motion under disjoint regional 400-ms minimum and 200-ms maximum durations.",
        "turnover": "Seeded fixed occupancy positions with heterogeneous analytical identity-handover schedules.",
    }[name]
    return dict(observations=_source(f"{name}-seed-{seed}", 4, 8000, population),
                policy=_policy(regions=policy_regions), regions=_reporting_regions(),
                description=description, kind="replicate", seed=seed,
                expected=dict(conditions_only=True, no_asserted_algorithmic_winner=True,
                              frozen_before_evaluation=True, family=name,
                              source_actor_count=len(actors)))


def make_case(name: str, seed: int | None = None) -> dict:
    """Return a fresh, mutable case; no input depends on an algorithm's outcomes.

    The registered study seeds are 19..26. Other nonnegative seeds are accepted for
    additional validation, but should not silently expand a predeclared experiment.
    Mechanism fixtures have no random seed and reject a supplied one.
    """
    if name in MECHANISM_SCENARIOS:
        if seed is not None:
            raise ValueError("Mechanism fixtures do not accept a seed")
        case = _mechanism(name)
    elif name in REPLICATE_SCENARIOS:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**63:
            raise ValueError("Replicate seed must be an integer in [0,2**63)")
        case = _replicate(name, seed)
    else:
        raise ValueError(f"Unknown coordination scenario: {name}")
    validate_case(case)
    return case


def validate_case(case: dict) -> None:
    """Fail closed on malformed cadence, source identity/geometry, or reporting masks."""
    source = case["observations"]
    grid, end = source["coverage"], source["end_ms"]
    if source.get("schema") != "ump.observation-replay.v1" or grid != _grid(grid["leaf_depth"]):
        raise ValueError("Unexpected source schema or coverage")
    if grid["leaf_depth"] not in (3, 4) or source["sampling_period_ms"] != PERIOD_MS:
        raise ValueError("Expected depth 3/4 and 100-ms sampling")
    if isinstance(end, bool) or not isinstance(end, int) or end < 1000 or end % PERIOD_MS:
        raise ValueError("Invalid replay horizon")
    times = list(range(PERIOD_MS, end, PERIOD_MS))
    if len(source["batches"]) != len(times):
        raise ValueError("Every measurement opportunity must be retained")
    for sequence, (time, batch) in enumerate(zip(times, source["batches"]), 1):
        if (batch["sequence"], batch["observed_at_ms"], batch["status"]) != (sequence, time, "measured"):
            raise ValueError("Invalid measurement cadence")
        seen = set()
        for observation in batch["observations"]:
            if set(observation) != {"id", "type", "x", "y", "cell_id"}:
                raise ValueError("Unexpected observation fields")
            identity = observation["id"]
            if not isinstance(identity, str) or not identity or identity in seen:
                raise ValueError("Invalid or repeated identity in a measurement")
            seen.add(identity)
            if observation["type"] not in ("pedestrian", "bicycle", "car"):
                raise ValueError("Unexpected road-user type")
            if any(isinstance(observation[axis], bool) or not isinstance(observation[axis], (int, float))
                   or not math.isfinite(observation[axis]) for axis in ("x", "y")):
                raise ValueError("Nonfinite source coordinates")
            if isinstance(observation["cell_id"], bool) or not isinstance(observation["cell_id"], int):
                raise ValueError("Invalid source cell ID")
            if observation["cell_id"] != cell_id(observation["x"], observation["y"], grid):
                raise ValueError("Source cell ID does not encode its position")
    if case["regions"] != _reporting_regions():
        raise ValueError("Reporting masks must remain fixed, disjoint and exhaustive")
    policy = case["policy"]
    if policy["policy_tree"]["regions"] != [r["id"] for r in policy["policy_regions"]]:
        raise ValueError("Policy region references do not match definitions")
