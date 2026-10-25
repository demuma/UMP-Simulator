"""Frozen P25.4 scalar occupancy workload, exact answers and estimates separate.

The root/all-road-user query is the mean count across scheduled sensor samples
in a fixed spatial footprint and half-open query interval. A conservative exact
answer requires whole public tiles contained in that footprint and interval,
known occupancy means and complete space-time support. Counts are not clipped
or allocated to obtain exact answers. This is not maximal transcript inference:
for example, a straddling explicit zero is deliberately not specialized.

The separate estimator calls the unchanged ``occupancy.evaluate`` and therefore
retains its declared uniform spatial allocation/constant temporal occupancy
assumptions. Private observations supply each world's reference only. Missing
public output never becomes a zero, even when that reference is measured empty.
All releases are evaluated as a retrospective final snapshot, not live delivery.
"""
from __future__ import annotations

from copy import deepcopy
import math

import occupancy
import semantic_privacy

SCHEMA = "ump.urban-privacy-occupancy.v1"


def _as_result(replay, public_or_result):
    """Adapt the actual semantic recipient channel without consulting diagnostics."""
    if not isinstance(public_or_result, dict):
        raise ValueError("Expected a semantic public transcript or replay result")
    if public_or_result.get("schema") == occupancy.RESULT_SCHEMA:
        result = public_or_result
    elif public_or_result.get("schema") == semantic_privacy.PUBLIC_SCHEMA:
        public = semantic_privacy.validate_public(public_or_result)
        source = {key: deepcopy(public[key]) for key in
                  ("coverage", "sampling_period_ms", "end_ms")}
        for key in ("run_id", "sensor_id"):
            if key in replay:
                source[key] = replay[key]
        result = {"schema": occupancy.RESULT_SCHEMA, "source": source,
                  "mode": "semantic_public_snapshot", "releases": public["releases"]}
    else:
        raise ValueError("Expected semantic public v2 or replay-result v1")
    horizon = replay.get("end_ms")
    if type(horizon) is not int:
        raise ValueError("Replay end_ms must be an integer")
    releases = result.get("releases")
    if not isinstance(releases, list):
        raise ValueError("Recipient releases must be a list")
    for release in releases:
        sealed = release.get("sealed_at_ms")
        if type(sealed) is not int or sealed > horizon:
            raise ValueError("A final snapshot cannot include a release sealed after its horizon")
    return result


def _summary(queries):
    total = len(queries)
    available = sum(row["reference_available"] for row in queries)
    answered = sum(row["answered"] for row in queries)
    scored = [row for row in queries if row["absolute_error"] is not None]
    error_sum = math.fsum(row["absolute_error"] for row in scored)
    return {
        "reference_queries": total,
        "reference_available_queries": available,
        "answered_queries": answered,
        "scored_queries": len(scored),
        "reference_availability": available / total if total else None,
        "answered_query_coverage": answered / total if total else None,
        "scored_query_coverage": len(scored) / total if total else None,
        "absolute_error_sum": error_sum,
        "occupancy_mae": error_sum / len(scored) if scored else None,
        "occupancy_mae_unit": "agents",
        "known_zero_reference_queries": sum(row["reference_available"] and row["reference"] == 0
                                             for row in queries),
        "positive_reference_queries": sum(row["reference_available"] and row["reference"] > 0
                                           for row in queries),
    }


def evaluate(replay, public_or_result, reference_cell_m=10,
             reference_window_ms=1000, *, include_queries=False):
    """Evaluate the predeclared fixed root-occupancy query bank.

    Returns ``exact.summary`` and ``estimate.summary`` with identical fixed query
    denominators and the unchanged estimation definition. Optional per-query
    rows are private evaluation artifacts. A complete 80-m square / 300-s source
    with defaults has 19,200 queries. The first one-second interval has nine
    100-ms samples because t=0 is initialization; later intervals have ten.

    ``public_or_result`` accepts the validated semantic v2 channel or a native
    result whose recipient releases have passed the separate source/policy audit.
    No private ``windows`` or accounting/debug metadata are used for prediction.
    """
    if not isinstance(include_queries, bool):
        raise ValueError("include_queries must be a boolean")
    result = _as_result(replay, public_or_result)
    # This exact call is protocol-bound: do not silently substitute a differently
    # weighted or gap-filling estimator when reporting primary-study results.
    estimated = occupancy.evaluate(replay, result, reference_cell_m,
                                   reference_window_ms)
    reference = estimated["reference"]
    period = reference["sampling_period_ms"]
    columns, rows = reference["columns"], reference["rows"]
    coverage = occupancy._rectangle(replay["coverage"], "coverage")
    window_count = reference["query_end_ms"] // reference_window_ms
    footprint_area = reference_cell_m ** 2
    volumes = [0.0] * len(estimated["queries"])
    terms = [[] for _ in estimated["queries"]]

    # Whole-tile containment leaves at most one spatial query and one temporal
    # query eligible per public tile. Nonoverlap was independently validated by
    # occupancy.evaluate, so complete contained volume proves complete sampled
    # support rather than hiding overlapping tiles or a gap with double counts.
    for release in result["releases"]:
        start, stop = release["start_ms"], release["end_ms"]
        window_index = start // reference_window_ms
        if (window_index >= window_count or
                stop > (window_index + 1) * reference_window_ms):
            continue
        first_sample = max(period, ((start + period - 1) // period) * period)
        sample_count = max(0, (stop - 1 - first_sample) // period + 1)
        if not sample_count:
            continue
        for cell in release["cells"]:
            mean = cell.get("mean_sample_occupancy")
            if mean is None:
                continue
            rectangle = occupancy._rectangle(cell, "released cell")
            column = math.floor((rectangle[0] - coverage[0]) / reference_cell_m)
            row = math.floor((rectangle[1] - coverage[1]) / reference_cell_m)
            if not (0 <= column < columns and 0 <= row < rows):
                continue
            query_rectangle = (coverage[0] + column * reference_cell_m,
                               coverage[1] + row * reference_cell_m,
                               reference_cell_m, reference_cell_m)
            if not occupancy._inside(rectangle, query_rectangle):
                continue
            index = (window_index * rows + row) * columns + column
            volumes[index] += rectangle[2] * rectangle[3] * sample_count
            terms[index].append(mean * sample_count)

    exact_queries = []
    for index, estimated_query in enumerate(estimated["queries"]):
        query = {key: value for key, value in estimated_query.items()
                 if key not in ("answered", "prediction", "absolute_error")}
        count = query["scheduled_samples"]
        required = footprint_area * count
        answered = bool(count) and math.isclose(volumes[index], required,
                                                rel_tol=1e-9, abs_tol=1e-9)
        prediction = math.fsum(terms[index]) / count if answered else None
        # An exact tile sum must also be an answered instance of the separate
        # estimator and agree numerically. This guards decoder drift; neither
        # side reads private reference counts to manufacture an answer.
        if answered and (not estimated_query["answered"] or not math.isclose(
                prediction, estimated_query["prediction"], rel_tol=1e-10, abs_tol=1e-10)):
            raise ValueError("Exact answer disagrees with unchanged uniform reconstruction")
        query.update(answered=answered, prediction=prediction,
                     absolute_error=(abs(prediction - query["reference"])
                         if answered and query["reference_available"] else None),
                     required_area_samples=required,
                     exact_covered_area_samples=volumes[index])
        exact_queries.append(query)
    exact = {"summary": _summary(exact_queries)}
    estimate = {"summary": {**deepcopy(estimated["summary"]),
                            "absolute_error_sum": math.fsum(row["absolute_error"]
                                for row in estimated["queries"] if row["absolute_error"] is not None)}}
    if include_queries:
        exact["queries"] = exact_queries
        estimate["queries"] = estimated["queries"]
    return {
        "schema": SCHEMA,
        "reference": deepcopy(reference),
        "contract": {
            "category": "root/all_road_users",
            "availability": "retrospective_final_snapshot_at_horizon",
            "exact": "complete whole-public-tile spatial/temporal containment with known means; no straddling, clipping or proportional allocation",
            "exact_scope": "conservative decoder, not maximal transcript inference; no zero specialization",
            "estimate": "unchanged occupancy.evaluate: uniform spatial allocation and constant occupancy within released intervals",
            "absence": "unknown, never filled as zero",
            "reference": "world-specific sampled IN or OUT source; measured-empty is zero, unavailable/missing is unknown",
            "timing": "no live delivery, online deadline or real-time guarantee",
        },
        "exact": exact,
        "estimate": estimate,
    }
