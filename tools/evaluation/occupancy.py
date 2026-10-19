"""Fixed-query occupancy utility from frozen observations and recipient releases.

The reference stays at a fixed spatial and temporal resolution. Predictions use
only ``result['releases']``; diagnostic windows never supply missing public data.
Uniform occupancy within each released interval and uniform spatial allocation
are explicit reconstruction assumptions, not recovered movement information.
"""

import math
from collections import Counter

from coordination_metrics import weighted_distribution


REPLAY_SCHEMA = "ump.observation-replay.v1"
RESULT_SCHEMA = "ump.replay-result.v1"
EVALUATION_SCHEMA = "ump.occupancy-evaluation.v1"


def _number(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f"{name} is outside its permitted range")
    return value


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _rectangle(raw, name):
    x = _number(raw.get("x"), f"{name}.x")
    y = _number(raw.get("y"), f"{name}.y")
    width = _number(raw.get("width"), f"{name}.width")
    height = _number(raw.get("height"), f"{name}.height")
    if (width <= 0 or height <= 0 or not math.isfinite(width * height)
            or not math.isfinite(x + width) or not math.isfinite(y + height)):
        raise ValueError(f"{name} must have finite positive dimensions and bounds")
    return x, y, width, height


def _intersection_area(a, b):
    return (max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
            * max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])))


def _inside(inner, outer):
    tolerance = max(outer[2], outer[3]) * 1e-10
    return (inner[0] >= outer[0] - tolerance
            and inner[1] >= outer[1] - tolerance
            and inner[0] + inner[2] <= outer[0] + outer[2] + tolerance
            and inner[1] + inner[3] <= outer[1] + outer[3] + tolerance)


def _stats(values):
    if not values:
        return {"count": 0, "min": None, "mean": None, "max": None}
    return {"count": len(values), "min": min(values),
            "mean": math.fsum(values) / len(values), "max": max(values)}


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _prepare_reference(replay, cell_m, window_ms):
    if replay.get("schema") != REPLAY_SCHEMA:
        raise ValueError(f"Expected replay schema {REPLAY_SCHEMA}")
    period = _integer(replay.get("sampling_period_ms"), "sampling_period_ms", 1)
    end = _integer(replay.get("end_ms"), "end_ms", 1)
    _integer(window_ms, "reference_window_ms", 1)
    _number(cell_m, "reference_cell_m")
    if cell_m <= 0 or window_ms % period:
        raise ValueError("Reference size must be positive and query duration must align to sampling")
    coverage = _rectangle(replay.get("coverage", {}), "coverage")
    columns, rows = round(coverage[2] / cell_m), round(coverage[3] / cell_m)
    if (columns < 1 or rows < 1
            or not math.isclose(columns * cell_m, coverage[2], abs_tol=1e-9)
            or not math.isclose(rows * cell_m, coverage[3], abs_tol=1e-9)):
        raise ValueError("The fixed reference grid must tile the evaluation coverage exactly")
    rectangles = [(coverage[0] + column * cell_m,
                   coverage[1] + row * cell_m, cell_m, cell_m)
                  for row in range(rows) for column in range(columns)]
    batches = replay.get("batches")
    if not isinstance(batches, list):
        raise ValueError("Replay batches must be a list")
    measured = {}
    previous_time = 0
    for batch in batches:
        time = _integer(batch.get("observed_at_ms"), "observed_at_ms", 1)
        if time <= previous_time or time >= end or time % period:
            raise ValueError("Observation times must be increasing, scheduled, positive and before end_ms")
        previous_time = time
        status = batch.get("status")
        observations = batch.get("observations")
        if status not in ("measured", "unavailable") or not isinstance(observations, list):
            raise ValueError("Each batch needs a measured/unavailable status and observation list")
        if status == "unavailable":
            if observations:
                raise ValueError("Unavailable batches cannot contain observations")
            continue
        counts = [0] * len(rectangles)
        identities = set()
        for observation in observations:
            identity = observation.get("id")
            if not isinstance(identity, str) or not identity or identity in identities:
                raise ValueError("Observation IDs must be nonempty and unique within each sample")
            identities.add(identity)
            x = _number(observation.get("x"), "observation.x")
            y = _number(observation.get("y"), "observation.y")
            if not (coverage[0] <= x < coverage[0] + coverage[2]
                    and coverage[1] <= y < coverage[1] + coverage[3]):
                raise ValueError("Reference observation is outside the half-open evaluation coverage")
            column = min(columns - 1, math.floor((x - coverage[0]) / cell_m))
            row = min(rows - 1, math.floor((y - coverage[1]) / cell_m))
            counts[row * columns + column] += 1
        measured[time] = counts
    return period, end, coverage, columns, rows, rectangles, measured


def _prepare_public(result, replay, coverage, rectangles, end):
    if result.get("schema") != RESULT_SCHEMA:
        raise ValueError(f"Expected result schema {RESULT_SCHEMA}")
    source = result.get("source", {})
    for key in ("sampling_period_ms", "end_ms"):
        if source.get(key) != replay.get(key):
            raise ValueError(f"Result source {key} does not match the replay")
    if _rectangle(source.get("coverage", {}), "source.coverage") != coverage:
        raise ValueError("Result source coverage does not match the replay")
    for key in ("run_id", "sensor_id"):
        if key in replay and source.get(key) != replay[key]:
            raise ValueError(f"Result source {key} does not match the replay")
    releases = result.get("releases")
    if not isinstance(releases, list):
        raise ValueError("Recipient releases must be a list")
    prepared = []
    release_ids = set()
    public_rectangles = []
    sides, areas, durations, ages, delays = [], [], [], [], []
    sizes = Counter()
    for release in releases:
        release_id = release.get("release_id")
        if not isinstance(release_id, str) or not release_id or release_id in release_ids:
            raise ValueError("Release IDs must be nonempty and unique")
        release_ids.add(release_id)
        start = _integer(release.get("start_ms"), "release.start_ms")
        stop = _integer(release.get("end_ms"), "release.end_ms", 1)
        sealed = _integer(release.get("sealed_at_ms"), "release.sealed_at_ms")
        if stop <= start or stop > end or sealed < stop:
            raise ValueError("Release intervals or sealing time are invalid")
        cells = release.get("cells")
        if not isinstance(cells, list):
            raise ValueError("A release must contain a cell list")
        prediction = [0.0] * len(rectangles)
        supported_area = [0.0] * len(rectangles)
        for cell in cells:
            rectangle = _rectangle(cell, "released cell")
            if not _inside(rectangle, coverage):
                raise ValueError("Released geometry is outside the evaluation coverage")
            mean = cell.get("mean_sample_occupancy")
            if mean is not None:
                _number(mean, "mean_sample_occupancy", 0)
            public_rectangles.append((start, stop, rectangle))
            width, height = rectangle[2:]
            area = width * height
            areas.append(area)
            if math.isclose(width, height, rel_tol=1e-10, abs_tol=1e-10):
                sides.append(width)
            sizes[(width, height)] += 1
            if mean is None:
                continue
            for index, reference in enumerate(rectangles):
                overlap = _intersection_area(rectangle, reference)
                if overlap:
                    # Occupancy is a count on the released footprint, not a density.
                    prediction[index] += mean * overlap / area
                    supported_area[index] += overlap
        prepared.append((start, stop, prediction, supported_area))
        durations.append(stop - start)
        ages.append(sealed - start)
        delays.append(sealed - stop)

    # Reject overlapping released support instead of double-counting it. Temporal
    # overlap alone is legal when the spatial supports are disjoint.
    active = []
    for start, stop, rectangle in sorted(public_rectangles, key=lambda row: row[0]):
        active = [(prior_stop, prior) for prior_stop, prior in active if prior_stop > start]
        for _, prior in active:
            if _intersection_area(rectangle, prior) > 1e-9:
                raise ValueError("Recipient cells overlap in space and time")
        active.append((stop, rectangle))
    resolution = {
        "weighting": "one weight per released cell; one weight per release for time statistics",
        "released_cells": len(public_rectangles),
        "cell_side_m": _stats(sides),
        "cell_area_m2": _stats(areas),
        "cell_size_distribution": [
            {"width_m": width, "height_m": height, "cells": count}
            for (width, height), count in sorted(sizes.items())],
        "window_duration_ms": _stats(durations),
        "simulated_age_at_sealing_ms": _stats(ages),
        "simulated_post_window_sealing_delay_ms": _stats(delays),
        "timing_note": "Simulation-time sealing statistics; not measured CPU time or delivery latency.",
    }
    return prepared, resolution


def evaluate(replay, result, reference_cell_m=10, reference_window_ms=1000):
    """Evaluate a frozen replay against its recipient-visible release view.

    Missing or suppressed support is unknown, including empty cells absent from
    sparse public output. A prediction is answered only if public cells cover
    the entire reference footprint at every scheduled sample in the query. The
    conditional MAE uses answered queries with a complete measured reference;
    answered-query coverage always uses all full fixed reference queries.

    Only full reference intervals are scored. A trailing shorter interval is
    explicitly reported, so a variant cannot change the query by ending early.
    All variants must use the same frozen replay and end_ms.
    """
    period, end, coverage, columns, rows, rectangles, measured = _prepare_reference(
        replay, reference_cell_m, reference_window_ms)
    public, resolution = _prepare_public(result, replay, coverage, rectangles, end)
    query_end = end - end % reference_window_ms
    queries = []
    errors = []
    reference_available_count = answered_count = 0
    reference_area = reference_cell_m ** 2
    for start in range(0, query_end, reference_window_ms):
        stop = start + reference_window_ms
        # t=0 is initialization. An observation exactly on a boundary belongs
        # to the next half-open query interval, including t=1000, t=2000, ...
        samples = range(max(period, start), stop, period)
        sample_times = list(samples)
        available = all(time in measured for time in sample_times)
        reference_sums = [0] * len(rectangles)
        prediction_sums = [0.0] * len(rectangles)
        answered = [True] * len(rectangles)
        for time in sample_times:
            if available:
                reference_sums = [total + count for total, count
                                  in zip(reference_sums, measured[time])]
            values = [0.0] * len(rectangles)
            support = [0.0] * len(rectangles)
            for release_start, release_end, estimates, areas in public:
                if release_start <= time < release_end:
                    values = [total + value for total, value in zip(values, estimates)]
                    support = [total + area for total, area in zip(support, areas)]
            for index in range(len(rectangles)):
                if not math.isclose(support[index], reference_area,
                                    rel_tol=1e-9, abs_tol=1e-9):
                    answered[index] = False
                prediction_sums[index] += values[index]
        for index, rectangle in enumerate(rectangles):
            is_answered = bool(sample_times) and answered[index]
            reference_available = bool(sample_times) and available
            reference = (reference_sums[index] / len(sample_times)
                         if reference_available else None)
            prediction = (prediction_sums[index] / len(sample_times)
                          if is_answered else None)
            error = (abs(prediction - reference)
                     if is_answered and reference_available else None)
            if error is not None:
                errors.append(error)
            answered_count += is_answered
            reference_available_count += reference_available
            queries.append({
                "column": index % columns, "row": index // columns,
                "x": rectangle[0], "y": rectangle[1],
                "start_ms": start, "end_ms": stop,
                "scheduled_samples": len(sample_times),
                "reference_available": reference_available,
                "answered": is_answered, "reference": reference,
                "prediction": prediction, "absolute_error": error,
            })
    total = len(queries)
    return {
        "schema": EVALUATION_SCHEMA,
        "mode": result.get("mode"),
        "reference": {
            "cell_side_m": reference_cell_m, "window_ms": reference_window_ms,
            "sampling_period_ms": period, "columns": columns, "rows": rows,
            "query_end_ms": query_end, "excluded_trailing_ms": end - query_end,
            "initial_sample_excluded": True,
            "allocation": "uniform spatial allocation and constant occupancy within each public interval",
            "temporal_weighting": "one equal weight per scheduled discrete sample",
        },
        "summary": {
            "reference_queries": total,
            "reference_available_queries": reference_available_count,
            "answered_queries": answered_count,
            "scored_queries": len(errors),
            "reference_availability": _ratio(reference_available_count, total),
            "answered_query_coverage": _ratio(answered_count, total),
            "scored_query_coverage": _ratio(len(errors), total),
            "occupancy_mae": math.fsum(errors) / len(errors) if errors else None,
            "occupancy_mae_unit": "agents",
            "interpretation": "Conditional MAE must be read together with answered-query coverage; no privacy guarantee.",
        },
        "release_resolution_and_age": resolution,
        "queries": queries,
    }


def _region_rectangles(regions):
    """Validate named rectangular masks without changing the reference grid."""
    if not isinstance(regions, list):
        raise ValueError("Regions must be a list of named rectangles")
    prepared, identities = [], set()
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError("Each region must be a named rectangle")
        identity = region.get("id")
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError("Region IDs must be nonempty and unique")
        identities.add(identity)
        prepared.append((identity, _rectangle(region, "region")))
    return prepared


def _summarize_query_subset(queries):
    """Preserve the full-grid denominators for a selected fixed-query subset."""
    total = len(queries)
    available = [query for query in queries if query["reference_available"]]
    answered = [query for query in queries if query["answered"]]
    scored = [query for query in queries if query["absolute_error"] is not None]
    # Each complete reference mean was obtained from integer per-sample counts.
    # Round only the reconstructed reference total, never public estimates.
    reference_contributions = round(math.fsum(
        query["reference"] * query["scheduled_samples"] for query in available))
    answered_reference = round(math.fsum(
        query["reference"] * query["scheduled_samples"] for query in scored))
    reconstructed = math.fsum(
        query["prediction"] * query["scheduled_samples"] for query in answered)
    return {
        "reference_queries": total,
        "reference_available_queries": len(available),
        "answered_queries": len(answered),
        "scored_queries": len(scored),
        "reference_availability": _ratio(len(available), total),
        "answered_query_coverage": _ratio(len(answered), total),
        "scored_query_coverage": _ratio(len(scored), total),
        "occupancy_mae": (math.fsum(query["absolute_error"] for query in scored)
                          / len(scored) if scored else None),
        "occupancy_mae_unit": "agents",
        "reference_observation_contributions": reference_contributions,
        "answered_reference_observation_contributions": answered_reference,
        "reconstructed_answered_observation_contribution_equivalents": reconstructed,
    }


def summarize_queries(evaluation, regions):
    """Summarize unchanged fixed queries fully contained in named rectangles.

    A boundary-crossing reference footprint is excluded, not clipped or resized.
    Overlapping masks are allowed and their summaries are consequently not
    additive. Reference contribution totals include only complete measured
    queries; reconstructed contribution equivalents are public occupancy
    predictions integrated over scheduled samples, not retained source records.
    Coverage describes eventual answerability, not availability by a deadline.
    """
    if evaluation.get("schema") != EVALUATION_SCHEMA:
        raise ValueError(f"Expected evaluation schema {EVALUATION_SCHEMA}")
    side = _number(evaluation["reference"]["cell_side_m"], "cell_side_m", 0)
    if side <= 0:
        raise ValueError("Reference cell size must be positive")
    summaries = []
    for identity, region in _region_rectangles(regions):
        selected, boundary = [], 0
        for query in evaluation["queries"]:
            footprint = (query["x"], query["y"], side, side)
            if _inside(footprint, region):
                selected.append(query)
            elif _intersection_area(footprint, region) > 0:
                boundary += 1
        summaries.append({
            "id": identity,
            "rectangle": dict(zip(("x", "y", "width", "height"), region)),
            "excluded_boundary_queries": boundary,
            **_summarize_query_subset(selected),
        })
    return {
        "selection": "Fixed query footprints fully contained in each rectangle; boundary intersections excluded.",
        "availability_scope": "Eventual answerability from complete releases; no online deadline is assumed.",
        "contribution_note": "Reference totals cover complete measured queries; reconstructed equivalents are not retained source contributions.",
        "regions": summaries,
    }


def summarize_region_retention(replay, result, regions):
    """Count retained raw contributions by exact point/time membership.

    This is private source-based diagnostics. It never allocates a coarse
    public count uniformly to a region. Per-region numerators are counts of
    actual raw observations inside recipient-visible space-time support. This
    counts released records even if their occupancy value cannot answer a query.
    """
    if replay.get("schema") != REPLAY_SCHEMA:
        raise ValueError(f"Expected replay schema {REPLAY_SCHEMA}")
    coverage = _rectangle(replay.get("coverage", {}), "coverage")
    end = _integer(replay.get("end_ms"), "end_ms", 1)
    period = _integer(replay.get("sampling_period_ms"), "sampling_period_ms", 1)
    prepared_regions = _region_rectangles(regions)
    # Validate source matching, released metrics and nonoverlap using the same
    # recipient validation as the fixed-query evaluator, without a new grid.
    _prepare_public(result, replay, coverage, [], end)
    events = sorted(
        (release["start_ms"], release["end_ms"], _rectangle(cell, "released cell"),
         release["sealed_at_ms"])
        for release in result["releases"] for cell in release["cells"])
    counts = [[0, 0] for _ in prepared_regions]
    observation_ages = [Counter() for _ in prepared_regions]
    previous, next_event, active = 0, 0, []
    batches = replay.get("batches")
    if not isinstance(batches, list):
        raise ValueError("Replay batches must be a list")
    for batch in batches:
        time = _integer(batch.get("observed_at_ms"), "observed_at_ms", 1)
        if time <= previous or time >= end or time % period:
            raise ValueError("Observation times must be increasing, scheduled, positive and before end_ms")
        previous = time
        while next_event < len(events) and events[next_event][0] <= time:
            _, stop, rectangle, sealed = events[next_event]
            active.append((stop, rectangle, sealed))
            next_event += 1
        active = [(stop, rectangle, sealed) for stop, rectangle, sealed in active if stop > time]
        status, observations = batch.get("status"), batch.get("observations")
        if status not in ("measured", "unavailable") or not isinstance(observations, list):
            raise ValueError("Each batch needs a measured/unavailable status and observation list")
        if status == "unavailable":
            if observations:
                raise ValueError("Unavailable batches cannot contain observations")
            continue
        identities = set()
        for observation in observations:
            identity = observation.get("id")
            if not isinstance(identity, str) or not identity or identity in identities:
                raise ValueError("Observation IDs must be nonempty and unique within each sample")
            identities.add(identity)
            x = _number(observation.get("x"), "observation.x")
            y = _number(observation.get("y"), "observation.y")
            def contains(rectangle):
                return (rectangle[0] <= x < rectangle[0] + rectangle[2]
                        and rectangle[1] <= y < rectangle[1] + rectangle[3])
            if not contains(coverage):
                raise ValueError("Reference observation is outside the half-open evaluation coverage")
            matches = [sealed for _, rectangle, sealed in active if contains(rectangle)]
            if len(matches) > 1:
                raise ValueError("A raw observation belongs to overlapping public support")
            retained = bool(matches)
            for index, (_, region) in enumerate(prepared_regions):
                if contains(region):
                    counts[index][0] += 1
                    counts[index][1] += retained
                    if retained:
                        observation_ages[index][matches[0] - time] += 1
    return {
        "classification": "private_source_retention_diagnostics",
        "definition": "Exact raw observation point/time membership in public released support; no uniform allocation of public counts.",
        "availability_scope": "Eventual released support, independent of delivery deadlines.",
        "age_definition": "Exact retained raw contribution age: sealed_at_ms minus observed_at_ms; simulation time, not network delivery latency. Each observation contribution has one weight.",
        "regions": [dict(id=identity, input_observation_contributions=total,
                         released_observation_contributions=retained,
                         retained_observation_fraction=_ratio(retained, total),
                         simulated_observation_age_ms=weighted_distribution(ages.items()))
                    for (identity, _), (total, retained), ages
                    in zip(prepared_regions, counts, observation_ages)],
    }
