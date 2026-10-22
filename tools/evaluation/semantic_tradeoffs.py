"""Bounded raw-data reference for one fixed actual common interval.

Scope: 80m D2, observations confined to NW parent12; one parent or any subset
of its four children; complete semantic antichains. Alternatives are mutually
exclusive fixed-interval representations, never an optimal online schedule.
Predictions use recipient cells only. Source data supplies counts/reference
feasibility, never missing zeros or an inferred split of a generalized bin.
"""
from copy import deepcopy
import itertools
import math

CLASSES = ("road_user", "cyclist", "adult_cyclist", "child_cyclist")
SEMANTIC_METRICS = {"min_category_distinct_contributors", "semantic_max_loss", "semantic_mean_loss"}
SCALAR_METRICS = {"observation_contributions", "distinct_contributors", "mean_sample_occupancy",
                  "cell_side_m", "cell_area_m2", "window_duration_ms", "age_at_evaluation_ms",
                  "post_window_delay_ms", "measured_sample_fraction"}
METRICS = SCALAR_METRICS | SEMANTIC_METRICS
INTEGRAL = {"observation_contributions", "distinct_contributors", "window_duration_ms",
            "age_at_evaluation_ms", "post_window_delay_ms", "min_category_distinct_contributors"}
EXACT_MAX = 2**53 - 1


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, name, minimum=0, maximum=EXACT_MAX):
    _require(type(value) in (int, float) and minimum <= value <= maximum
             and math.isfinite(value), "Invalid " + name)
    return value


def _integer(value, name, minimum=0, maximum=EXACT_MAX):
    _require(type(value) is int and minimum <= value <= maximum, "Invalid " + name)
    return value


def _text(value, name):
    _require(isinstance(value, str) and 0 < len(value) <= 256
             and all(ord(c) >= 32 and ord(c) != 127 for c in value), "Invalid " + name)
    return value


def geometry(cell_id):
    """Hand-derived bounded geometry, independent of production Morton decoding."""
    _integer(cell_id, "cell ID")
    _require(cell_id in (12, 48, 49, 50, 51), "Reference geometry is confined to parent12")
    if cell_id == 12:
        return dict(cell_id=12, depth=1, x=0, y=0, width=40, height=40)
    quadrant = cell_id - 48
    return dict(cell_id=cell_id, depth=2, x=20 * (quadrant % 2), y=20 * (quadrant // 2), width=20, height=20)


def _contains(nodes, ancestor, descendant):
    current = descendant
    while current is not None:
        if current == ancestor:
            return True
        current = nodes[current].get("parent")
    return False


def _catalog(config):
    raw = config.get("semantic_taxonomy")
    _require(isinstance(raw, dict), "Reference requires semantic_taxonomy")
    _text(raw.get("id"), "taxonomy ID"); _text(raw.get("version"), "taxonomy version")
    rows = raw.get("nodes")
    _require(isinstance(rows, list) and 1 <= len(rows) <= 12,
             "Bounded reference supports at most twelve taxonomy nodes")
    nodes, labels = {}, {}
    for row in rows:
        _require(isinstance(row, dict) and set(row) <= {"id", "parent", "loss", "input_types"},
                 "Invalid taxonomy node fields")
        node = _text(row.get("id"), "taxonomy node ID")
        _require(node not in nodes, "Duplicate taxonomy node ID")
        value = dict(row)
        parent = row.get("parent")
        if parent is not None:
            _text(parent, "taxonomy parent")
        value["parent"] = parent
        _number(row.get("loss"), "taxonomy loss", maximum=1)
        types = row.get("input_types", [])
        _require(isinstance(types, list), "Taxonomy input types must be a list")
        for label in types:
            _text(label, "taxonomy input type")
            _require(label not in labels, "Duplicate/ambiguous taxonomy input type")
            labels[label] = node
        nodes[node] = value
    roots = [node for node in nodes if nodes[node]["parent"] is None]
    _require(roots == ["road_user"], "Workload requires road_user as the unique taxonomy root")
    _require(all(category in nodes for category in CLASSES), "Taxonomy is missing a fixed query category")
    _require(nodes["road_user"]["loss"] == 1, "Taxonomy root loss must be one")
    for node, row in nodes.items():
        seen, current = set(), node
        while current is not None:
            _require(current in nodes and current not in seen, "Taxonomy has unknown parent or cycle")
            seen.add(current); current = nodes[current]["parent"]
        children = [child for child in nodes if nodes[child]["parent"] == node]
        if children:
            _require(not row.get("input_types"), "Only terminals may map raw labels")
            _require(all(row["loss"] >= nodes[child]["loss"] for child in children),
                     "Ancestor loss is below descendant loss")
        else:
            _require(row["loss"] == 0 and row.get("input_types"), "Terminal requires loss zero and input labels")
    return nodes, labels


def _bounds(raw):
    _require(isinstance(raw, dict), "Metric requirements must be a map")
    output = {}
    for name, row in raw.items():
        _require(name in METRICS, "Unsupported bounded-reference metric: " + str(name))
        _require(isinstance(row, dict) and bool(row) and set(row) <= {"min", "max"}, "Invalid metric bounds")
        output[name] = dict(row)
        for direction, value in row.items():
            _number(value, name, maximum=1 if name in SEMANTIC_METRICS - {"min_category_distinct_contributors"}
                    or name == "measured_sample_fraction" else EXACT_MAX)
            if name in INTEGRAL:
                _require(int(value) == value, "Metric bound must be integral")
        _require(row.get("min", 0) <= row.get("max", math.inf), "Contradictory metric bounds")
        if name == "min_category_distinct_contributors":
            _require(set(row) == {"min"} and row["min"] >= 1, "Semantic support accepts a positive minimum only")
        if name in {"semantic_max_loss", "semantic_mean_loss"}:
            _require(set(row) == {"max"}, "Semantic loss accepts an upper bound only")
    return output


def _merge(*requirements):
    merged = {}
    for requirement in requirements:
        for name, row in requirement.items():
            target = merged.setdefault(name, {})
            if "min" in row:
                target["min"] = max(target.get("min", -math.inf), row["min"])
            if "max" in row:
                target["max"] = min(target.get("max", math.inf), row["max"])
    return merged


def _intersects(a, b):
    return (a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
            and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"])


def _policy(config):
    _require(isinstance(config, dict), "Configuration must be a map")
    _require(config.get("temporal_adaptation", {}).get("coordination", "common_window") == "common_window",
             "Reference supports common-window intervals only")
    spatial = config.get("spatial_selection", {})
    minimum_depth = _integer(spatial.get("min_depth", 1), "minimum depth", 1, 2)
    uniform, tree = config.get("metric_policy"), config.get("policy_tree")
    _require(bool(uniform) != bool(tree), "Exactly one explicit policy is required")
    if uniform:
        _require(not config.get("policy_regions"), "Uniform policy cannot select regions")
        root, selected = _bounds(uniform.get("requirements")), []
    else:
        _require(isinstance(tree, dict), "Invalid policy tree")
        root = _bounds(tree.get("root"))
        references = tree.get("regions")
        _require(isinstance(references, list) and all(isinstance(item, str) for item in references)
                 and len(set(references)) == len(references), "Invalid selected policy regions")
        rows = config.get("policy_regions", [])
        _require(isinstance(rows, list), "Policy region definitions must be a list")
        definitions = {}
        for region in rows:
            _require(isinstance(region, dict), "Invalid policy region")
            rid = _text(region.get("id"), "policy region ID")
            _require(rid not in definitions, "Duplicate policy region ID")
            definitions[rid] = region
        selected, typed = [], {}
        for rid in references:
            _require(rid in definitions, "Unknown selected policy region")
            region = definitions[rid]
            for name in ("x", "y", "width", "height"):
                _number(region.get(name), "policy region " + name)
            _require(region["width"] > 0 and region["height"] > 0
                     and region["x"] + region["width"] <= 80 and region["y"] + region["height"] <= 80,
                     "Policy region lies outside coverage")
            _require(all(value % 20 == 0 for value in (region["x"], region["y"], region["width"], region["height"])),
                     "Policy region is not finest-grid aligned")
            type_name = _text(region.get("type", "replay_region"), "region type")
            type_bounds = _bounds(region.get("type_requirements", {}))
            if type_name in typed:
                _require(typed[type_name] == type_bounds, "Inconsistent region type definitions")
            typed[type_name] = type_bounds
            instance = _bounds(region.get("requirements", {}))
            inherited = _merge(root, type_bounds, instance)
            _require(all(row.get("min", 0) <= row.get("max", math.inf) for row in inherited.values()),
                     "Contradictory inherited regional bounds")
            _require(not any(_intersects(region, prior[0]) for prior in selected), "Selected policy regions overlap")
            selected.append((region, type_bounds, instance))
    _require("min_category_distinct_contributors" in root and "semantic_max_loss" in root,
             "Semantic root support and maximum loss are mandatory")
    return root, selected, minimum_depth


def _effective(root, regions, cell):
    parts = [root]
    for region, typed, instance in regions:
        if _intersects(cell, region):
            parts.extend((typed, instance))
    return _merge(*parts)


def _input(replay, labels, start, end, now):
    _require(isinstance(replay, dict) and replay.get("schema") == "ump.observation-replay.v1", "Invalid replay schema")
    _require(replay.get("coverage") == dict(x=0, y=0, width=80, height=80, leaf_depth=2)
             and type(replay["coverage"]["leaf_depth"]) is int,
             "Reference scope is exactly 80x80m depth two at origin zero")
    period = _integer(replay.get("sampling_period_ms"), "sampling period", 1)
    horizon = _integer(replay.get("end_ms"), "source horizon", 1)
    _integer(start, "interval start"); _integer(end, "interval end", 1); _integer(now, "evaluation time", 1)
    _require(start < end <= now <= horizon and start % period == 0
             and (end % period == 0 or end == horizon), "Invalid same-data interval/evaluation time")
    batches = replay.get("batches")
    _require(isinstance(batches, list) and len(batches) <= 10000, "Reference source exceeds ten thousand batches")
    observations, measured, unavailable, previous_time, previous_sequence = [], 0, 0, 0, 0
    identity_leaf = {}
    for batch in batches:
        _require(isinstance(batch, dict), "Invalid observation batch")
        time = _integer(batch.get("observed_at_ms"), "sample time", 1)
        sequence = _integer(batch.get("sequence"), "sample sequence", 1)
        _require(previous_time < time < horizon and time % period == 0 and sequence > previous_sequence,
                 "Observation sequence/time is duplicate, late or off cadence")
        previous_time, previous_sequence = time, sequence
        status, rows = batch.get("status"), batch.get("observations")
        _require(status in ("measured", "unavailable") and isinstance(rows, list), "Invalid measurement status")
        _require(status == "measured" or not rows, "Unavailable sample contains observations")
        included = start <= time < end
        if included:
            measured += status == "measured"; unavailable += status == "unavailable"
        seen = set()
        for observation in rows:
            _require(isinstance(observation, dict), "Invalid observation")
            identity = _text(observation.get("id"), "contributor identity")
            raw = _text(observation.get("type"), "raw type")
            _require(raw in labels, "Unknown semantic input type")
            _require(identity not in seen, "Repeated contributor in one sample"); seen.add(identity)
            cell = geometry(observation.get("cell_id"))
            _require(cell["depth"] == 2, "Source observations must use finest cells48--51")
            x = _number(observation.get("x"), "source x"); y = _number(observation.get("y"), "source y")
            _require(cell["x"] <= x < cell["x"] + 20 and cell["y"] <= y < cell["y"] + 20,
                     "Observation coordinate contradicts declared cell")
            if included:
                _require(identity_leaf.setdefault(identity, labels[raw]) == labels[raw],
                         "Identity changes terminal class inside the fixed interval")
                observations.append(dict(observation))
    _require(len(observations) <= 100000, "Reference interval exceeds one hundred thousand observations")
    before = lambda time: max(0, (time - 1) // period)
    expected = before(end) - before(start)
    missing = expected - measured - unavailable
    _require(missing >= 0, "Inconsistent source coverage")
    return observations, dict(expected=expected, measured=measured, unavailable=unavailable, missing=missing,
        complete=expected > 0 and missing == 0 and unavailable == 0)


def _representation(nodes, config, categories, rows, labels):
    bins = []
    for category in sorted(categories):
        assigned = [item for item in rows if _contains(nodes, category, labels[item["type"]])]
        bins.append(dict(category_id=category, observation_contributions=len(assigned),
                         distinct_contributors=len({item["id"] for item in assigned})))
    return dict(schema="ump.semantic-release.v1", taxonomy_id=config["semantic_taxonomy"]["id"],
        taxonomy_version=config["semantic_taxonomy"]["version"], categories=bins,
        min_category_distinct_contributors=min(row["distinct_contributors"] for row in bins),
        semantic_max_loss=max(nodes[row["category_id"]]["loss"] for row in bins),
        semantic_mean_loss=math.fsum(row["observation_contributions"] * nodes[row["category_id"]]["loss"]
                                    for row in bins) / len(rows))


def _public_semantic(semantic, config, nodes):
    _require(isinstance(semantic, dict) and semantic.get("schema") == "ump.semantic-release.v1"
             and semantic.get("taxonomy_id") == config["semantic_taxonomy"]["id"]
             and semantic.get("taxonomy_version") == config["semantic_taxonomy"]["version"], "Invalid public semantic provenance")
    bins = semantic.get("categories")
    _require(isinstance(bins, list) and bool(bins) and len(bins) <= len(nodes), "Invalid public semantic categories")
    selected = []
    for row in bins:
        _require(isinstance(row, dict) and set(row) == {"category_id", "observation_contributions", "distinct_contributors"},
                 "Invalid public semantic category fields")
        category = row["category_id"]
        _require(category in nodes and not any(_contains(nodes, category, prior) or _contains(nodes, prior, category)
                                             for prior in selected), "Public semantic categories overlap or are unknown")
        selected.append(category)
        count = _integer(row["observation_contributions"], "semantic observation count", 1)
        _integer(row["distinct_contributors"], "semantic distinct support", 1, count)
    total = sum(row["observation_contributions"] for row in bins)
    summaries = dict(min_category_distinct_contributors=min(row["distinct_contributors"] for row in bins),
        semantic_max_loss=max(nodes[row["category_id"]]["loss"] for row in bins),
        semantic_mean_loss=math.fsum(row["observation_contributions"] * nodes[row["category_id"]]["loss"] for row in bins) / total)
    for key, expected in summaries.items():
        value = _number(semantic.get(key), "public " + key)
        _require(math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-12), "Public semantic summary contradicts categories")
    return bins


def exact_category_contributions(semantic, config, category):
    """Observation contributions, or None if a generalized bin straddles the class.

    A missing class within a complete published semantic partition is known zero.
    Distinct support is never added across published cells or windows.
    """
    nodes, _ = _catalog(config)
    _require(category in nodes, "Unknown requested class")
    bins = _public_semantic(semantic, config, nodes)
    total = 0
    for row in bins:
        if _contains(nodes, category, row["category_id"]):
            total += row["observation_contributions"]
        elif _contains(nodes, row["category_id"], category):
            return None
    return total


def score_candidate(cells, config, start_ms, end_ms, source_contributions):
    """Fixed-interval exact queries: four classes at four20m tiles and one40m tile."""
    nodes, _ = _catalog(config)
    _integer(start_ms, "score start"); _integer(end_ms, "score end", 1)
    _require(end_ms > start_ms and isinstance(cells, list), "Invalid scored interval/cells")
    _integer(source_contributions, "source contributions")
    seen, retained = set(), 0
    for cell in cells:
        _require(isinstance(cell, dict), "Invalid recipient cell")
        expected = geometry(cell.get("cell_id"))
        _require(all(cell.get(key) == value for key, value in expected.items()), "Recipient cell geometry is noncanonical")
        _require(cell["cell_id"] not in seen, "Repeated recipient cell"); seen.add(cell["cell_id"])
        bins = _public_semantic(cell.get("semantic"), config, nodes)
        total = _integer(cell.get("observation_contributions"), "public cell contributions", 1)
        _require(total == sum(row["observation_contributions"] for row in bins), "Semantic histogram does not preserve cell total")
        distinct = _integer(cell.get("distinct_road_users"), "public distinct support", 1, total)
        _require(distinct == sum(row["distinct_contributors"] for row in bins), "Stable-class partition does not preserve distinct support")
        retained += total
    _require(not (12 in seen and len(seen) > 1), "Recipient cut overlaps parent and child")
    _require(retained <= source_contributions, "Retained contributions exceed original interval")
    result = dict(retained_contributions=retained,
        retained_fraction=retained / source_contributions if source_contributions else None,
        mean_semantic_loss=(math.fsum(cell["observation_contributions"] * cell["semantic"]["semantic_mean_loss"]
                                     for cell in cells) / retained if retained else None),
        max_semantic_loss=max((cell["semantic"]["semantic_max_loss"] for cell in cells), default=None),
        contribution_weighted_cell_side_m=(math.fsum(cell["observation_contributions"] * cell["width"] for cell in cells)
                                           / retained if retained else None))
    for side, queries in ((20, [geometry(cid) for cid in range(48, 52)]), (40, [geometry(12)])):
        answers = []
        for query in queries:
            relevant = [cell for cell in cells if _intersects(cell, query)]
            complete = (all(cell["x"] >= query["x"] and cell["y"] >= query["y"]
                            and cell["x"] + cell["width"] <= query["x"] + side
                            and cell["y"] + cell["height"] <= query["y"] + side for cell in relevant)
                        and sum(cell["width"] * cell["height"] for cell in relevant) == side**2)
            for category in CLASSES:
                values = [exact_category_contributions(cell["semantic"], config, category) for cell in relevant] if complete else []
                answered = complete and all(value is not None for value in values)
                answers.append(dict(cell_id=query["cell_id"], category=category, answered=answered,
                                    observation_contributions=sum(values) if answered else None))
        count = sum(answer["answered"] for answer in answers)
        result["query" + str(side) + "_coverage"] = count / len(answers)
        result["query" + str(side)] = dict(answered=count, total=len(answers), queries=answers)
    return result


def reference_candidates(replay, config, start_ms, end_ms, evaluated_at_ms=None, max_candidates=4096):
    """Enumerate all bounded legal representations, retaining complete private input.

    Missing/unavailable evidence permits only the all-suppressed candidate. Budget
    exhaustion raises instead of returning a truncated alleged feasible frontier.
    The actual interval/evaluation time are held fixed; this does not revise history.
    """
    _integer(max_candidates, "candidate budget", 1, 100000)
    nodes, labels = _catalog(config)
    root, regions, minimum_depth = _policy(config)
    now = end_ms if evaluated_at_ms is None else evaluated_at_ms
    observations, coverage = _input(replay, labels, start_ms, end_ms, now)
    failures, alternatives = {}, {}

    def record(cell_id, metric, reason, observed=None, bounds=None):
        item = dict(cell_id=cell_id, metric=metric, reason=reason, observed=observed)
        if bounds:
            item.update(bounds)
        key = repr(sorted(item.items()))
        failures[key] = item

    def passes(cell_id, values, bounds):
        valid = True
        for name, rule in bounds.items():
            observed = values.get(name)
            reason = ("contradictory_bounds" if rule.get("min", 0) > rule.get("max", math.inf)
                      else "unavailable" if observed is None
                      else "below_minimum" if observed < rule.get("min", -math.inf)
                      else "above_maximum" if observed > rule.get("max", math.inf) else None)
            if reason:
                valid = False; record(cell_id, name, reason, observed, rule)
        return valid

    for cell_id in (12, 48, 49, 50, 51):
        alternatives[cell_id] = []
        cell = geometry(cell_id)
        rows = [row for row in observations if cell_id == 12 or row["cell_id"] == cell_id]
        if not rows or cell["depth"] < minimum_depth:
            continue
        if not coverage["complete"]:
            record(cell_id, "complete_coverage", "no_scheduled_samples" if not coverage["expected"] else "incomplete")
            continue
        bounds = _effective(root, regions, cell)
        scalar_values = dict(observation_contributions=len(rows), distinct_contributors=len({row["id"] for row in rows}),
            mean_sample_occupancy=len(rows) / coverage["measured"], cell_side_m=cell["width"], cell_area_m2=cell["width"]**2,
            window_duration_ms=end_ms - start_ms, age_at_evaluation_ms=now - start_ms,
            post_window_delay_ms=now - end_ms, measured_sample_fraction=coverage["measured"] / coverage["expected"])
        if not passes(cell_id, scalar_values, {name: rule for name, rule in bounds.items() if name in SCALAR_METRICS}):
            continue
        occupied_nodes = [node for node in nodes if any(_contains(nodes, node, labels[row["type"]]) for row in rows)]
        for size in range(1, len(occupied_nodes) + 1):
            for cut in itertools.combinations(occupied_nodes, size):
                if any(_contains(nodes, left, right) or _contains(nodes, right, left) for left, right in itertools.combinations(cut, 2)):
                    continue
                if any(sum(_contains(nodes, category, labels[row["type"]]) for category in cut) != 1 for row in rows):
                    continue
                semantic = _representation(nodes, config, cut, rows, labels)
                values = {name: semantic[name] for name in SEMANTIC_METRICS}
                if not passes(cell_id, values, {name: rule for name, rule in bounds.items() if name in SEMANTIC_METRICS}):
                    continue
                alternatives[cell_id].append(dict(cell, observation_contributions=len(rows),
                    distinct_road_users=scalar_values["distinct_contributors"], mean_sample_occupancy=scalar_values["mean_sample_occupancy"],
                    effective_policy_id="reference", semantic=semantic))
    combinations = math.prod(1 + len(alternatives[leaf]) for leaf in range(48, 52))
    required = combinations + len(alternatives[12])
    _require(required <= max_candidates, "Reference candidate budget exceeded; no partial enumeration returned")
    cuts = [[]]
    cuts.extend([[parent] for parent in alternatives[12]])
    for combination in itertools.product(*[[None] + alternatives[leaf] for leaf in range(48, 52)]):
        if any(cell is not None for cell in combination):
            cuts.append([cell for cell in combination if cell is not None])
    _require(len(cuts) == required, "Reference enumeration accounting failed")
    candidates = [dict(cells=deepcopy(cut), **score_candidate(cut, config, start_ms, end_ms, len(observations))) for cut in cuts]
    return dict(schema="ump.semantic-fixed-interval-reference.v1", candidates=candidates,
        source_contributions=len(observations), interval=dict(start_ms=start_ms, end_ms=end_ms, evaluated_at_ms=now),
        binding_failures=sorted(failures.values(), key=lambda row: (row["cell_id"], row["metric"], repr(row))),
        coverage=coverage,
        candidate_class=dict(geometry="80m D2; parent12 or any subset of leaves48--51; no parent/child overlap",
            semantics="all complete occupied taxonomy antichains; no partial-class suppression",
            temporal="one fixed actual interval and evaluation time; no endpoint/future-data alternatives",
            resource_budget=max_candidates, maximum_taxonomy_nodes=12,
            spatial_min_depth=minimum_depth, absent_public_support="unknown, never source-derived zero",
            interpretation="bounded fixed-interval feasible representations, not an optimal online schedule"))


def pareto_candidates(candidates):
    """Nondominated scored representations; no weights or claimed unique optimum.

    No-output has undefined detail and is kept only if no nonempty candidate exists.
    Privacy is not an objective here; a zero-output privacy control belongs separately.
    """
    _require(isinstance(candidates, list) and bool(candidates), "Pareto input must be a nonempty candidate list")
    nonempty = [item for item in candidates if item["retained_contributions"] > 0]
    if not nonempty:
        return list(candidates)
    keys = ("retained_contributions", "query20_coverage", "query40_coverage")
    costs = ("mean_semantic_loss", "max_semantic_loss", "contribution_weighted_cell_side_m")
    def dominates(left, right):
        a = [left[key] for key in keys] + [-left[key] for key in costs]
        b = [right[key] for key in keys] + [-right[key] for key in costs]
        return all(x >= y or math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12) for x, y in zip(a, b)) and any(
            x > y and not math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12) for x, y in zip(a, b))
    return [item for item in nonempty if not any(dominates(other, item) for other in nonempty if other is not item)]
