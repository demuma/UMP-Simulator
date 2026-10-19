"""Independent, bounded EP01 compliance and tiny-case feasibility reference.

Public API (all dictionaries are JSON serializable):

* ``validate_result(replay, config, result, max_cells=20000)`` independently
  recomputes released and diagnostic cell geometry, identity unions, counts,
  coverage and configured requirements. It never invokes production code or
  trusts its pass flags. It does NOT enumerate feasible alternatives.
* ``reference_interval(replay, config, start_ms, end_ms, evaluated_at_ms=None,
  min_depth=1, max_nodes=1024, common_deadline=False)`` computes exact best cuts
  on occupied paths for one interval. The whole-sibling model may retain a
  branch only in full; partial-child rescue may suppress individual branches.
* ``analyze_windows(replay, config, result, max_nodes=1024)`` compares the
  actual retired intervals with both bounded reference classes.
* ``enumerate_endpoints(replay, config, start_ms, endpoints_ms, **kwargs)``
  evaluates each explicit endpoint independently. This is a hindsight bound,
  not an online algorithm, and does not combine or reuse overlapping windows.

Replay/configuration errors and unsupported metrics raise ValueError. A malformed
production result is returned as ``valid=False`` with private violations. Resource
budgets raise ValueError rather than silently returning incomplete evidence.
All registry metrics except occupancy_mae are supported: occupancy error requires
an external application reference and cannot be a release-local check here.
Empty support is reported separately, never as evidence of privacy or utility.
No helper from the production selector, metric evaluator, fixture encoder or
occupancy evaluator is imported. This is research validation, not a privacy proof.
"""

from bisect import bisect_left, insort
from collections import Counter
import math

SCHEMA = "ump.independent-oracle.v1"
SUPPORTED = frozenset({"observation_contributions", "distinct_contributors",
    "mean_sample_occupancy", "cell_side_m", "cell_area_m2", "window_duration_ms",
    "age_at_evaluation_ms", "post_window_delay_ms", "measured_sample_fraction"})
INTEGRAL = frozenset({"observation_contributions", "distinct_contributors",
    "window_duration_ms", "age_at_evaluation_ms", "post_window_delay_ms"})


def _int(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 2**53 - 1:
        raise ValueError(f"{name} must be an exact integer >= {minimum}")
    return value


def _number(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite numeric")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be nonempty text")
    return value


def _rect(raw):
    values = tuple(_number(raw.get(k), k) for k in ("x", "y", "width", "height"))
    if values[2] <= 0 or values[3] <= 0 or not all(math.isfinite(v) for v in
            (values[0] + values[2], values[1] + values[3], values[2] * values[3])):
        raise ValueError("Rectangle must have positive finite dimensions and bounds")
    return values


def _intersects(a, b):
    # Touching at a boundary has zero area and does not inherit a region policy.
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _close(a, b):
    return (not isinstance(a, bool) and isinstance(a, (int, float))
            and math.isfinite(a) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10))


def decode_cell(coverage, cell_id, depth):
    """Decode a data cell; synthetic depth-zero root is deliberately forbidden."""
    _int(depth, "cell depth", 1)
    _int(cell_id, "cell ID", 1)
    if depth > coverage["leaf_depth"] or cell_id >> (2 * depth) != 3:
        raise ValueError("Cell ID/depth does not encode a supported quadtree data cell")
    x, y, width, height = _rect(coverage)
    for level in reversed(range(depth)):
        quadrant = (cell_id >> (2 * level)) & 3
        width /= 2
        height /= 2
        if quadrant & 1:
            x += width
        if quadrant & 2:
            y += height
    return dict(cell_id=cell_id, depth=depth, x=x, y=y, width=width, height=height)


class _Input:
    def __init__(self, replay):
        if replay.get("schema") != "ump.observation-replay.v1":
            raise ValueError("Unsupported replay schema")
        self.replay = replay
        for name in ("run_id", "sensor_id"):
            _text(replay.get(name), name)
        self.grid = replay.get("coverage", {})
        x, y, side, height = _rect(self.grid)
        self.depth = _int(self.grid.get("leaf_depth"), "leaf_depth", 1)
        if side != height or self.depth > 14 or x + side / 2**self.depth == x or y + side / 2**self.depth == y:
            raise ValueError("Independent reference requires representable square coverage and depth 1..14")
        self.period = _int(replay.get("sampling_period_ms"), "sampling_period_ms", 1)
        self.end = _int(replay.get("end_ms"), "end_ms", 1)
        if self.end // self.period > 1000000:
            raise ValueError("Replay exceeds oracle one-million-sample budget")
        if not isinstance(replay.get("batches"), list):
            raise ValueError("Replay batches must be a list")
        self.batches = {}
        previous_time = previous_sequence = 0
        self.contributions = 0
        for batch in replay["batches"]:
            time = _int(batch.get("observed_at_ms"), "observed_at_ms", 1)
            sequence = _int(batch.get("sequence"), "sequence", 1)
            if time <= previous_time or sequence <= previous_sequence or time >= self.end or time % self.period:
                raise ValueError("Batches must have increasing sequence/time on cadence in (0,end_ms)")
            previous_time, previous_sequence = time, sequence
            status, observations = batch.get("status"), batch.get("observations")
            if status not in ("measured", "unavailable") or not isinstance(observations, list):
                raise ValueError("Invalid observation status/list")
            if status == "unavailable" and observations:
                raise ValueError("Unavailable samples cannot carry observations")
            seen = set()
            for observation in observations:
                identity = _text(observation.get("id"), "observation.id")
                _text(observation.get("type"), "observation.type")
                if identity in seen:
                    raise ValueError("Duplicate Road User within a sample")
                seen.add(identity)
                cell = decode_cell(self.grid, observation.get("cell_id"), self.depth)
                if ("x" in observation) != ("y" in observation):
                    raise ValueError("Observation coordinates must supply both x and y")
                if "x" in observation:
                    ox = _number(observation["x"], "observation.x")
                    oy = _number(observation["y"], "observation.y")
                    if not (cell["x"] <= ox < cell["x"] + cell["width"] and
                            cell["y"] <= oy < cell["y"] + cell["height"]):
                        raise ValueError("Observation coordinates contradict half-open cell ID geometry")
            self.contributions += len(observations)
            self.batches[time] = batch

    def interval(self, start, end, now=None):
        start = _int(start, "start_ms")
        end = _int(end, "end_ms", 1)
        now = end if now is None else _int(now, "evaluated_at_ms")
        if not 0 <= start < end <= self.end or now < end:
            raise ValueError("Interval/evaluation times are invalid")
        return _Window(self, start, end, now)


class _Window:
    def __init__(self, source, start, end, now):
        self.source, self.start, self.end, self.now = source, start, end, now
        # t=0 is initialization; a sample at end belongs to the next interval.
        first = max(source.period, ((start + source.period - 1) // source.period) * source.period)
        self.times = range(first, end, source.period)
        self.expected = len(self.times)
        self.measured = self.unavailable = self.missing = 0
        self.counts, self.identities = Counter(), {}
        self.total = 0
        for time in self.times:
            batch = source.batches.get(time)
            if batch is None:
                self.missing += 1
            elif batch["status"] == "unavailable":
                self.unavailable += 1
            else:
                self.measured += 1
                for observation in batch["observations"]:
                    self.total += 1
                    leaf_id = observation["cell_id"]
                    for depth in range(1, source.depth + 1):
                        cell_id = leaf_id >> (2 * (source.depth - depth))
                        self.counts[cell_id] += 1
                        self.identities.setdefault(cell_id, set()).add(observation["id"])
        self.coverage = ("no_scheduled_samples" if not self.expected else
                         "incomplete" if self.missing or self.unavailable else "complete")

    def metrics(self, cell_id, depth):
        cell = decode_cell(self.source.grid, cell_id, depth)
        contributions = self.counts[cell_id]
        return {
            "observation_contributions": contributions,
            "distinct_contributors": len(self.identities.get(cell_id, ())) if self.measured else None,
            "mean_sample_occupancy": contributions / self.measured if self.measured else None,
            "cell_side_m": cell["width"], "cell_area_m2": cell["width"] * cell["height"],
            "window_duration_ms": self.end - self.start,
            "age_at_evaluation_ms": self.now - self.start,
            "post_window_delay_ms": self.now - self.end,
            "measured_sample_fraction": self.measured / self.expected if self.expected else None,
        }

    def summary(self):
        return {"start_ms": self.start, "end_ms": self.end, "evaluated_at_ms": self.now,
                "expected_samples": self.expected, "measured_samples": self.measured,
                "unavailable_samples": self.unavailable, "missing_samples": self.missing,
                "coverage": self.coverage, "input_observation_contributions": self.total}


def _requirements(raw, allow_empty=False):
    if raw is None and allow_empty:
        return {}
    if not isinstance(raw, dict) or (not raw and not allow_empty):
        raise ValueError("Requirements must be a nonempty metric-bound dictionary")
    result = {}
    for name, bounds in raw.items():
        if name not in SUPPORTED:
            raise ValueError(f"Unsupported oracle metric: {name}")
        if not isinstance(bounds, dict) or not bounds or set(bounds) - {"min", "max"}:
            raise ValueError(f"Invalid requirement bounds for {name}")
        checked = {}
        for key, value in bounds.items():
            _number(value, name, 0)
            if name in INTEGRAL:
                if value != int(value) or value > 2**53 - 1:
                    raise ValueError(f"{name} requires exact integral bounds")
            if name == "measured_sample_fraction" and value > 1:
                raise ValueError("Measured fraction must be in [0,1]")
            checked[key] = value
        if checked.get("min", 0) > checked.get("max", math.inf):
            raise ValueError(f"Contradictory requirement for {name}")
        result[name] = checked
    return result


def _merge(*requirements):
    result = {}
    for group in requirements:
        for metric, bounds in group.items():
            target = result.setdefault(metric, {})
            if "min" in bounds:
                target["min"] = max(target.get("min", -math.inf), bounds["min"])
            if "max" in bounds:
                target["max"] = min(target.get("max", math.inf), bounds["max"])
    return result


class _Policy:
    def __init__(self, source, config):
        self.config, self.source = config, source
        _text(config.get("application_id"), "application_id")
        if ("metric_policy" in config) == ("policy_tree" in config):
            raise ValueError("Exactly one metric_policy or policy_tree is required")
        self.regions = []
        if "metric_policy" in config:
            policy = config["metric_policy"]
            self.root = _requirements(policy.get("requirements"))
            if config.get("policy_regions"):
                raise ValueError("Uniform policy cannot use policy_regions")
        else:
            policy = config["policy_tree"]
            self.root = _requirements(policy.get("root"))
            raw_regions = config.get("policy_regions", [])
            refs = policy.get("regions")
            if not isinstance(raw_regions, list) or not isinstance(refs, list):
                raise ValueError("Policy regions and references must be lists")
            types, ids = {}, set()
            coverage = _rect(source.grid)
            leaf = coverage[2] / 2**source.depth
            for region in raw_regions:
                identity = _text(region.get("id"), "region.id")
                region_type = _text(region.get("type", "replay_region"), "region.type")
                if identity in ids:
                    raise ValueError("Duplicate policy region ID")
                ids.add(identity)
                rect = _rect(region)
                coordinates = ((rect[0] - coverage[0]) / leaf, (rect[1] - coverage[1]) / leaf,
                               (rect[0] + rect[2] - coverage[0]) / leaf,
                               (rect[1] + rect[3] - coverage[1]) / leaf)
                if any(v < 0 or v > 2**source.depth or not math.isclose(v, round(v), abs_tol=1e-8)
                       for v in coordinates):
                    raise ValueError("Region must be inside coverage and finest-grid aligned")
                # Accepted alignment roundoff is canonicalized before positive-
                # area intersection; an epsilon must not create a strict sliver
                # across a shared cell boundary.
                left, top, right, bottom = (round(v) for v in coordinates)
                rect = (coverage[0] + left * leaf, coverage[1] + top * leaf,
                        (right - left) * leaf, (bottom - top) * leaf)
                if rect[2] <= 0 or rect[3] <= 0:
                    raise ValueError("Aligned policy region has no positive area")
                if any(_intersects(rect, prior[1]) for prior in self.regions):
                    raise ValueError("Overlapping policy regions are outside this implementation's scope")
                typed = _requirements(region.get("type_requirements"), True)
                if region_type in types and types[region_type] != typed:
                    raise ValueError("Inconsistent region type requirements")
                types[region_type] = typed
                own = _requirements(region.get("requirements"), True)
                effective = _merge(self.root, typed, own)
                if any(b.get("min", 0) > b.get("max", math.inf) for b in effective.values()):
                    raise ValueError("Contradictory inherited requirements within a region")
                self.regions.append((identity, rect, typed, own))
            if len(refs) != len(set(refs)) or set(refs) != ids:
                raise ValueError("All policy regions must be referenced exactly once")
        self.id = _text(policy.get("id"), "policy.id")
        self.version = _text(policy.get("version"), "policy.version")

    def effective(self, cell_id, depth):
        cell = decode_cell(self.source.grid, cell_id, depth)
        rect = _rect(cell)
        relevant = [r for r in self.regions if _intersects(rect, r[1])]
        bounds = _merge(self.root, *(part for r in relevant for part in r[2:]))
        return bounds, [r[0] for r in relevant]

    def assess(self, window, cell_id, depth):
        values = window.metrics(cell_id, depth)
        bounds, regions = self.effective(cell_id, depth)
        reasons = []
        if window.coverage != "complete":
            reasons.append({"requirement": "complete_coverage", "reason": window.coverage})
        for metric, limit in sorted(bounds.items()):
            observed = values[metric]
            why = ("contradictory_bounds" if limit.get("min", 0) > limit.get("max", math.inf)
                   else "unavailable" if observed is None
                   else "below_minimum" if observed < limit.get("min", -math.inf)
                   else "above_maximum" if observed > limit.get("max", math.inf) else None)
            if why:
                reasons.append({"requirement": metric, "reason": why, "observed": observed, **limit})
        return {"cell_id": cell_id, "depth": depth, "metrics": values,
                "effective_requirements": bounds, "intersected_regions": regions,
                "pass": not reasons, "binding_failures": reasons}

    def common_deadline_failures(self, window):
        # The current adaptive controller includes empty policy areas in this cap.
        groups = [self.root] + [_merge(self.root, r[2], r[3]) for r in self.regions]
        reasons = []
        for metric in ("window_duration_ms", "age_at_evaluation_ms"):
            caps = [r[metric]["max"] for r in groups if metric in r and "max" in r[metric]]
            if caps:
                observed = window.end - window.start if metric == "window_duration_ms" else window.now - window.start
                if observed > min(caps):
                    reasons.append({"requirement": metric, "reason": "whole_domain_deadline", "max": min(caps),
                                    "observed": observed})
        return reasons


def _reference(source, policy, start, end, now, min_depth, max_nodes, common_deadline):
    min_depth = _int(min_depth, "min_depth", 1)
    _int(max_nodes, "max_nodes", 1)
    if min_depth > source.depth:
        raise ValueError("min_depth exceeds leaf_depth")
    window = source.interval(start, end, now)
    nodes = [(cid, depth) for depth in range(min_depth, source.depth + 1)
             for cid in window.counts if cid >> (2 * depth) == 3]
    if len(nodes) > max_nodes:
        raise ValueError("Tiny-case reference exceeds max_nodes budget; no feasibility conclusion returned")
    assessed = {(cid, depth): policy.assess(window, cid, depth) for cid, depth in nodes}
    domains = sorted(cid for cid, depth in nodes if depth == min_depth)
    common_failures = policy.common_deadline_failures(window) if common_deadline else []

    def best(model):
        cache = {}
        def visit(cid, depth):
            key = (cid, depth)
            if key in cache:
                return cache[key]
            if not window.counts[cid]:
                return (0, [], True, 1)
            assessment = assessed[key]
            passing = assessment["pass"] and not common_failures
            # Every node can be suppressed; publishing a passing node is another cut.
            best_count = window.counts[cid] if passing else 0
            cut = [cid] if passing else []
            choices = 1 + int(passing)
            full = bool(passing)
            if depth < source.depth:
                children = [visit(cid * 4 + q, depth + 1) for q in range(4)]
                all_full = all(child[2] for child in children)
                child_count = sum(child[0] for child in children)
                child_cut = [item for child in children for item in child[1]]
                if model == "partial_child_rescue" or all_full:
                    if child_count > best_count or (child_count == best_count and
                            (len(child_cut), sum(c.bit_length() for c in child_cut)) >
                            (len(cut), sum(c.bit_length() for c in cut))):
                        best_count, cut = child_count, child_cut
                    full = full or all_full
                # Count distinct legal cuts without double-counting all-suppressed.
                if model == "partial_child_rescue":
                    combinations = math.prod(child[3] for child in children)
                    choices += combinations - 1
                elif all_full:
                    # Full-only child choices; dynamic count below avoids partial cuts.
                    combinations = math.prod(full_choices(cid * 4 + q, depth + 1) for q in range(4))
                    choices += combinations
            cache[key] = (best_count, cut, full, choices)
            return cache[key]

        full_cache = {}
        def full_choices(cid, depth):
            key = (cid, depth)
            if key in full_cache:
                return full_cache[key]
            if not window.counts[cid]:
                return 1
            count = int(assessed[key]["pass"] and not common_failures)
            if depth < source.depth:
                count += math.prod(full_choices(cid * 4 + q, depth + 1) for q in range(4))
            full_cache[key] = count
            return count

        roots = [visit(cid, min_depth) for cid in domains]
        retained = sum(root[0] for root in roots)
        return {"any_output_feasible": retained > 0,
                "full_retention_feasible": retained == window.total if window.total else None,
                "best_retained_contributions": retained,
                "best_cell_ids": sorted(cid for root in roots for cid in root[1]),
                "legal_cut_count": math.prod(root[3] for root in roots),
                "retention_fraction": retained / window.total if window.total else None}

    return {"schema": SCHEMA, "classification": "private_research_diagnostics", **window.summary(),
            "empty_observed_support": not bool(window.total), "enumerated_nodes": len(nodes),
            "whole_sibling": best("whole_sibling"), "partial_child_rescue": best("partial_child_rescue"),
            "binding_requirements": [{"cell_id": cid, "depth": depth, **reason}
                for (cid, depth), check in sorted(assessed.items()) for reason in check["binding_failures"]],
            "common_deadline_failures": common_failures,
            "scope": {"min_depth": min_depth, "leaf_depth": source.depth, "max_nodes": max_nodes,
                "complete_coverage_required": True, "common_deadline": common_deadline,
                "interval_model": "one fixed common interval; sparse occupied paths; empty cells not released",
                "whole_sibling": "each occupied min-depth branch retained completely or suppressed",
                "partial_child_rescue": "passing descendants may survive a failed sibling/ancestor",
                "information": "offline observations within this interval; no online optimality claim",
                "unsupported": ["occupancy_mae", "cell-local interval coordination", "publication retraction",
                                "composed overlapping intervals", "runtime/history budgets"]}}


def reference_interval(replay, config, start_ms, end_ms, evaluated_at_ms=None, *,
                       min_depth=1, max_nodes=1024, common_deadline=False):
    """Exact bounded best cuts for one declared interval; no future-window reuse."""
    source = _Input(replay)
    return _reference(source, _Policy(source, config), start_ms, end_ms, evaluated_at_ms,
                      min_depth, max_nodes, common_deadline)


def enumerate_endpoints(replay, config, start_ms, endpoints_ms, *, min_depth=1,
                        max_nodes=1024, max_endpoints=32, common_deadline=False):
    """Check explicit cadence-aligned endpoints; feasibility is not assumed monotone."""
    source = _Input(replay)
    policy = _Policy(source, config)
    _int(max_endpoints, "max_endpoints", 1)
    if not isinstance(endpoints_ms, (list, tuple)) or not endpoints_ms or len(endpoints_ms) > max_endpoints:
        raise ValueError("Explicit endpoints must be a nonempty list within max_endpoints budget")
    if len(set(endpoints_ms)) != len(endpoints_ms):
        raise ValueError("Duplicate candidate endpoints")
    for end in endpoints_ms:
        _int(end, "endpoint_ms", 1)
        if end % source.period and end != source.end:
            raise ValueError("Candidate endpoints must be scheduled or the final truncated endpoint")
    return {"schema": SCHEMA, "classification": "private_research_diagnostics",
            "scope": "independent fixed-start alternatives, not a jointly publishable schedule",
            "intervals": [_reference(source, policy, start_ms, end, end, min_depth, max_nodes,
                                     common_deadline) for end in sorted(endpoints_ms)]}



def analyze_windows(replay, config, result, *, max_nodes=1024, max_cells=20000):
    """Compare actual emitted/retired intervals without changing their endpoints.

    A gap against the whole-sibling class is a diagnostic, not automatically a
    coding defect: fixed baselines, finite execution budgets and online choices
    are deliberately not optimized by this reference. A partial-rescue gap is a
    known difference in model capabilities. No cross-window support is reused.
    """
    compliance = validate_result(replay, config, result, max_cells=max_cells)
    if not compliance["valid"]:
        raise ValueError("Refuse feasibility comparison of an independently invalid result")
    source, intervals = _Input(replay), []
    policy = _Policy(source, config)
    min_depth = result.get("parameters", {}).get("min_depth", config.get("spatial_selection", {}).get("min_depth", 1))
    common = result.get("mode") in ("temporal_first", "spatial_first")
    released = Counter()
    for cell in compliance["released_cells"]:
        released[(cell["start_ms"], cell["end_ms"])] += cell["metrics"]["observation_contributions"]
    for window in compliance["checked_windows"]:
        start, end = window["start_ms"], window["end_ms"]
        reference = _reference(source, policy, start, end, window["evaluated_at_ms"], min_depth, max_nodes, common)
        actual = released[(start, end)]
        reference["algorithm_retained_contributions"] = actual
        reference["algorithm_retention_gap"] = {
            model: reference[model]["best_retained_contributions"] - actual
            for model in ("whole_sibling", "partial_child_rescue")}
        intervals.append(reference)
    return {"schema": SCHEMA, "classification": "private_research_diagnostics", "valid": True,
            "intervals": intervals, "scope": "actual retired intervals only; no endpoint or online optimality claim"}


def validate_result(replay, config, result, *, max_cells=20000):
    """Independently validate a complete replay result; does not run cut enumeration.

    Vacuous no-output compliance is explicitly ``no_release=True``. The result
    cannot establish attack resistance, optimality, or full-retention feasibility.
    Input/configuration validation errors raise ValueError; result defects are
    collected under violations and make valid=False.
    """
    source = _Input(replay)
    policy = _Policy(source, config)
    _int(max_cells, "max_cells", 1)
    violations, released_cells, checked_windows = [], [], []
    def fail(path, reason, **details):
        violations.append({"path": path, "reason": reason, **details})
    def equal(actual, expected, path, numeric=False):
        good = _close(actual, expected) if numeric else type(actual) is type(expected) and actual == expected
        if not good:
            fail(path, "recomputed_value_mismatch", expected=expected, observed=actual)
    if not isinstance(result, dict):
        return {"schema": SCHEMA, "valid": False, "violations": [{"path": "result", "reason": "not_a_dictionary"}],
                "released_cells": [], "released_cell_count": 0, "no_release": True}
    equal(result.get("schema"), "ump.replay-result.v1", "schema")
    raw_source = result.get("source", {})
    if not isinstance(raw_source, dict):
        fail("source", "not_a_dictionary")
        raw_source = {}
    for key in ("run_id", "sensor_id", "sampling_period_ms", "end_ms", "coverage"):
        equal(raw_source.get(key), replay.get(key), f"source.{key}")
    equal(raw_source.get("application_id"), config["application_id"], "source.application_id")
    for key in ("input_observation_contributions", "accounted_observation_contributions"):
        equal(result.get(key), source.contributions, key)
    raw_windows, releases = result.get("windows"), result.get("releases")
    if not isinstance(raw_windows, list):
        fail("windows", "not_a_list")
        raw_windows = []
    if not isinstance(releases, list):
        fail("releases", "not_a_list")
        releases = []
    if len(raw_windows) + len(releases) > max_cells:
        raise ValueError("Result exceeds oracle window/release budget")
    visited_cells, window_data, events = 0, {}, []
    def cell(raw, window, path, published=False):
        nonlocal visited_cells
        visited_cells += 1
        if visited_cells > max_cells:
            raise ValueError("Result exceeds oracle cell budget")
        if not isinstance(raw, dict):
            raise ValueError("Cell must be a dictionary")
        cid = _int(raw.get("cell_id"), "cell_id", 1)
        depth = _int(raw.get("depth"), "depth", 1)
        geometry = decode_cell(source.grid, cid, depth)
        for key in ("x", "y", "width", "height"):
            equal(raw.get(key), geometry[key], f"{path}.{key}", True)
        assessment = policy.assess(window, cid, depth)
        values = assessment["metrics"]
        for key, metric in (("observation_contributions", "observation_contributions"),
                            ("distinct_road_users", "distinct_contributors"),
                            ("mean_sample_occupancy", "mean_sample_occupancy")):
            expected = values[metric]
            if metric == "distinct_contributors" and expected is None:
                expected = 0  # AggregateCounts holds zero even when its metric is unavailable.
            equal(raw.get(key), expected, f"{path}.{key}", metric == "mean_sample_occupancy" and expected is not None)
        if values["observation_contributions"] == 0:
            fail(path, "zero_observation_footprint_is_not_sparse_output")
        if published and not assessment["pass"]:
            fail(path, "published_cell_fails_independent_requirements", failures=assessment["binding_failures"])
        if not published and "assessment_status" in raw:
            expected_status = "unavailable" if window.coverage != "complete" else "pass" if assessment["pass"] else "fail"
            equal(raw["assessment_status"], expected_status, f"{path}.assessment_status")
        if isinstance(raw.get("metrics"), dict):
            for metric, actual in raw["metrics"].items():
                expected = values.get(metric)  # occupancy_mae is correctly unavailable.
                equal(actual, expected, f"{path}.metrics.{metric}", expected is not None)
        return assessment

    retired = 0
    for index, raw in enumerate(raw_windows):
        path = f"windows[{index}]"
        try:
            if not isinstance(raw, dict):
                raise ValueError("Window must be a dictionary")
            window = source.interval(raw.get("start_ms"), raw.get("end_ms"), raw.get("evaluated_at_ms"))
            equal(window.start, retired, f"{path}.start_ms")
            retired = window.end
            if window.now > source.end:
                fail(path, "evaluation_after_replay_end")
            if (window.start % source.period or (window.end % source.period and window.end != source.end)):
                fail(path, "window_not_cadence_aligned")
            for key, value in window.summary().items():
                equal(raw.get(key), value, f"{path}.{key}")
            key = (window.start, window.end)
            if key in window_data:
                fail(path, "repeated_retired_interval")
            raw_cells = raw.get("cells")
            if not isinstance(raw_cells, list):
                raise ValueError("Window cells must be a list")
            assessments, selected, ids = [], [], set()
            for j, raw_cell in enumerate(raw_cells):
                assessment = cell(raw_cell, window, f"{path}.cells[{j}]")
                cid, depth = assessment["cell_id"], assessment["depth"]
                if cid in ids:
                    fail(path, "duplicate_diagnostic_cell")
                ids.add(cid)
                for ancestor_depth in range(1, depth):
                    if cid >> (2 * (depth - ancestor_depth)) in ids:
                        fail(path, "diagnostic_parent_child_overlap")
                if not isinstance(raw_cell.get("selected"), bool):
                    fail(f"{path}.cells[{j}].selected", "selected_must_be_boolean")
                elif raw_cell["selected"]:
                    selected.append(cid)
                    if not assessment["pass"]:
                        fail(f"{path}.cells[{j}]", "selected_cell_fails_independent_requirements",
                             failures=assessment["binding_failures"])
                assessments.append(assessment)
            # Check ancestry in both orders, not just when parent came first.
            for assessment in assessments:
                cid, depth = assessment["cell_id"], assessment["depth"]
                if any(cid >> (2 * (depth - d)) in ids for d in range(1, depth)):
                    fail(path, "diagnostic_parent_child_overlap")
            equal(sum(a["metrics"]["observation_contributions"] for a in assessments), window.total,
                  f"{path}.accounted_cell_contributions")
            equal(raw.get("selected_cells"), len(selected), f"{path}.selected_cells")
            equal(raw.get("suppressed_cells"), len(assessments) - len(selected), f"{path}.suppressed_cells")
            window_data[key] = (window, set(selected))
            checked_windows.append({**window.summary(), "selected_cell_ids": sorted(selected)})
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            fail(path, "malformed_window", detail=str(error))
    equal(retired, source.end, "retirement.end_ms")
    release_ids, released_windows = set(), set()
    last_sealed = -1
    for index, raw in enumerate(releases):
        path = f"releases[{index}]"
        try:
            if not isinstance(raw, dict):
                raise ValueError("Release must be a dictionary")
            identity = _text(raw.get("release_id"), "release_id")
            if identity in release_ids:
                fail(path, "duplicate_release_id")
            release_ids.add(identity)
            window = source.interval(raw.get("start_ms"), raw.get("end_ms"), raw.get("sealed_at_ms"))
            if window.now < last_sealed or window.now > source.end:
                fail(path, "invalid_publication_time_order")
            last_sealed = window.now
            key = (window.start, window.end)
            if key in released_windows:
                fail(path, "repeated_release_interval")
            released_windows.add(key)
            equal(raw.get("model"), "private_final_snapshot", f"{path}.model")
            equal(raw.get("policy_id"), policy.id, f"{path}.policy_id")
            equal(raw.get("policy_version"), policy.version, f"{path}.policy_version")
            raw_cells = raw.get("cells")
            if not isinstance(raw_cells, list) or not raw_cells:
                raise ValueError("Sparse public releases must have at least one cell")
            selected = []
            for j, raw_cell in enumerate(raw_cells):
                assessment = cell(raw_cell, window, f"{path}.cells[{j}]", True)
                cid, depth = assessment["cell_id"], assessment["depth"]
                selected.append(cid)
                shift = 2 * (source.depth - depth)
                lo, hi = cid << shift, (cid + 1) << shift
                token = (lo, hi, index, j)
                events.extend([(window.start, 1, token), (window.end, 0, token)])
                released_cells.append({"release_id": identity, "start_ms": window.start, "end_ms": window.end,
                    "sealed_at_ms": window.now, **assessment})
            if len(selected) != len(set(selected)):
                fail(path, "duplicate_public_cell")
            if key not in window_data:
                fail(path, "release_has_no_retired_diagnostic_window")
            else:
                diagnostic_window, expected = window_data[key]
                equal(set(selected), expected, f"{path}.selected_cell_ids")
                equal(window.now, diagnostic_window.now, f"{path}.sealed_at_ms")
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            fail(path, "malformed_release", detail=str(error))
    for key, (_, selected) in window_data.items():
        if selected and key not in released_windows:
            fail("releases", "selected_window_has_no_release", interval=list(key))
    # Morton-code intervals detect ancestor overlap without O(number_of_cells^2).
    active = []
    for _, kind, token in sorted(events):
        at = bisect_left(active, token)
        if not kind:
            if at < len(active) and active[at] == token:
                active.pop(at)
        else:
            if ((at and active[at - 1][1] > token[0]) or
                    (at < len(active) and active[at][0] < token[1])):
                fail("releases", "public_support_overlap_in_space_and_time")
            insort(active, token)
    # Convert sets in mismatch diagnostics to JSON-compatible deterministic values.
    for item in violations:
        for key in ("expected", "observed"):
            if isinstance(item.get(key), set):
                item[key] = sorted(item[key])
    return {"schema": SCHEMA, "classification": "private_research_diagnostics",
            "valid": not violations, "violations": violations, "released_cells": released_cells,
            "released_cell_count": len(released_cells), "no_release": not bool(released_cells),
            "checked_windows": checked_windows,
            "released_observation_contributions": sum(c["metrics"]["observation_contributions"] for c in released_cells),
            "input_observation_contributions": source.contributions,
            "scope": {"supported_metrics": sorted(SUPPORTED), "complete_coverage_required": True,
                "independent_geometry_and_raw_observation_recomputation": True,
                "feasibility_enumerated": False, "max_cells": max_cells,
                "no_release_note": "No output is vacuous release compliance, not demonstrated usefulness or privacy.",
                "not_established": ["attack resistance", "formal anonymity", "optimality", "online feasibility",
                                    "production history/resource budget adequacy"]}}
