"""Deadline-aware fixed occupancy queries over immutable public releases.

This evaluator uses the same discrete-sample estimator as ``occupancy``. An
aggregate becomes usable as a whole at its simulated ``sealed_at_ms``; its
interval and counts are never clipped to an application deadline. Full public
spatial support is required at every scheduled sample. An absent or unknown
mean is unknown, while an explicit released zero is usable evidence.

The primary cohort is fixed before looking at releases: query end plus the
largest declared lag must be strictly before the observation horizon. Boundary
queries are reported separately, with deadlines beyond the horizon censored.
These are simulation-time availability measurements, not network/CPU latency.
"""

import math

import occupancy


SCHEMA = "ump.online-occupancy-evaluation.v1"
DEFAULT_DEADLINE_LAGS_MS = (0, 200, 500, 1000)


def _lags(values):
    if not isinstance(values, (tuple, list)) or not values:
        raise ValueError("deadline_lags_ms must be a nonempty list or tuple")
    result = [occupancy._integer(value, "deadline lag") for value in values]
    if result != sorted(set(result)):
        raise ValueError("Deadline lags must be strictly increasing and unique")
    return result


def _as_result(replay, public_or_result):
    """Adapt a validated public transcript without adding private predictions."""
    if not isinstance(public_or_result, dict):
        raise ValueError("The complete recipient result must be an object")
    if public_or_result.get("schema") == occupancy.RESULT_SCHEMA:
        return public_or_result
    if public_or_result.get("schema") != "ump.public-transcript.v1":
        raise ValueError("Expected a complete public transcript or replay result")
    # Reuse the established public-channel whitelist and geometry checks.
    from empirical_privacy import _validated_public
    public = _validated_public(public_or_result)
    source = {key: public[key]
              for key in ("coverage", "sampling_period_ms", "end_ms")}
    for key in ("run_id", "sensor_id"):
        if key in replay:
            source[key] = replay[key]
    return {"schema": occupancy.RESULT_SCHEMA, "source": source,
            "mode": "public_transcript", "releases": public["releases"]}


def _complete_queries(replay, result, cell_m, window_ms):
    """Compute fixed estimates and the last seal required for complete support.

    Nonoverlapping public support, validated by occupancy, makes the maximum
    required seal an exact readiness time. No later release can revise an
    already complete query under this immutable recipient-channel contract.
    """
    period, end, coverage, columns, rows, rectangles, measured = (
        occupancy._prepare_reference(replay, cell_m, window_ms))
    prepared, _ = occupancy._prepare_public(
        result, replay, coverage, rectangles, end)
    public = [(start, stop, predictions, areas, release["sealed_at_ms"])
              for (start, stop, predictions, areas), release
              in zip(prepared, result["releases"])]
    query_end = end - end % window_ms
    reference_area = cell_m ** 2
    queries = []
    for start in range(0, query_end, window_ms):
        stop = start + window_ms
        times = list(range(max(period, start), stop, period))
        available = bool(times) and all(time in measured for time in times)
        reference_sums = [0] * len(rectangles)
        prediction_sums = [0.0] * len(rectangles)
        answered = [bool(times)] * len(rectangles)
        ready = [None] * len(rectangles)
        for time in times:
            if available:
                reference_sums = [total + count for total, count
                                  in zip(reference_sums, measured[time])]
            values = [0.0] * len(rectangles)
            support = [0.0] * len(rectangles)
            for release_start, release_end, estimates, areas, sealed in public:
                if release_start <= time < release_end:
                    values = [total + value for total, value
                              in zip(values, estimates)]
                    support = [total + area for total, area
                               in zip(support, areas)]
                    for index, area in enumerate(areas):
                        if area > 0:
                            ready[index] = (sealed if ready[index] is None
                                            else max(ready[index], sealed))
            for index in range(len(rectangles)):
                if not math.isclose(support[index], reference_area,
                                    rel_tol=1e-9, abs_tol=1e-9):
                    answered[index] = False
                prediction_sums[index] += values[index]
        for index, rectangle in enumerate(rectangles):
            reference = (reference_sums[index] / len(times)
                         if available else None)
            prediction = (prediction_sums[index] / len(times)
                          if answered[index] else None)
            queries.append({
                "column": index % columns, "row": index // columns,
                "x": rectangle[0], "y": rectangle[1],
                "start_ms": start, "end_ms": stop,
                "scheduled_samples": len(times),
                "reference_available": available,
                "answered": answered[index], "reference": reference,
                "prediction": prediction,
                "absolute_error": (abs(prediction - reference)
                                   if answered[index] and available else None),
                "ready_at_ms": ready[index] if answered[index] else None,
            })
    reference = {
        "cell_side_m": cell_m, "window_ms": window_ms,
        "sampling_period_ms": period, "columns": columns, "rows": rows,
        "query_end_ms": query_end, "excluded_trailing_ms": end - query_end,
        "initial_sample_excluded": True,
        "allocation": "uniform spatial allocation and constant occupancy within each public interval",
        "temporal_weighting": "one equal weight per scheduled discrete sample",
    }
    return end, reference, queries


def _summary(queries):
    observed = [query for query in queries if query["deadline_observed"]]
    return {
        **occupancy._summarize_query_subset(observed),
        "absolute_error_sum": math.fsum(query["absolute_error"] for query in observed
                                        if query["absolute_error"] is not None),
        "cohort_queries": len(queries),
        "deadline_observed_queries": len(observed),
        "censored_queries": len(queries) - len(observed),
        "deadline_at_eof_queries": sum(query["deadline_at_eof"]
                                       for query in observed),
        "interpretation": (
            "Conditional MAE requires deadline coverage; missing public support "
            "is unknown. Censored deadlines are excluded. Simulation-time "
            "availability is not delivery latency or a privacy guarantee."),
    }


def _at_deadline(query, lag, horizon):
    deadline = query["end_ms"] + lag
    observed = deadline <= horizon
    ready = query["ready_at_ms"]
    answered = observed and ready is not None and ready <= deadline
    return {**query, "deadline_ms": deadline,
            "deadline_observed": observed,
            "deadline_at_eof": deadline == horizon,
            "answered": answered,
            "prediction": query["prediction"] if answered else None,
            "absolute_error": query["absolute_error"] if answered else None}


def evaluate(replay, public_or_result, reference_cell_m=10,
             reference_window_ms=1000,
             deadline_lags_ms=DEFAULT_DEADLINE_LAGS_MS):
    """Evaluate a complete recipient history at fixed query deadlines.

    ``public_or_result`` accepts the approved public transcript or its complete
    replay result. Only recipient releases contribute predictions; source
    observations supply the independent fixed reference. ``ready_at_ms`` is
    private evaluation metadata calculated from that complete history. A late
    readiness never supplies a prediction or error at an earlier deadline.

    Every lag uses the same primary cohort, ``query.end + max(lags) < H``.
    Other full queries form the separate boundary cohort; deadlines exactly at
    H are labelled EOF and deadlines after H are censored, not failed answers.
    """
    lags = _lags(deadline_lags_ms)
    result = _as_result(replay, public_or_result)
    horizon, reference, queries = _complete_queries(
        replay, result, reference_cell_m, reference_window_ms)
    primary = [query for query in queries
               if query["end_ms"] + lags[-1] < horizon]
    boundary = [query for query in queries
                if query["end_ms"] + lags[-1] >= horizon]
    reference = {**reference, "observed_until_ms": horizon,
                 "maximum_deadline_lag_ms": lags[-1],
                 "primary_cohort_rule": "query.end_ms + maximum_deadline_lag_ms < observed_until_ms"}

    def projections(cohort, name):
        projected = {}
        for lag in lags:
            rows = [_at_deadline(query, lag, horizon) for query in cohort]
            projected[str(lag)] = {
                "schema": SCHEMA, "cohort": name,
                "reference": dict(reference), "deadline_lag_ms": lag,
                "summary": _summary(rows), "queries": rows,
            }
        return projected

    return {"schema": SCHEMA, "mode": result.get("mode"),
            "reference": reference, "observed_until_ms": horizon,
            "deadline_lags_ms": lags,
            "evaluations_by_lag_ms": projections(primary, "interior"),
            "boundary_by_lag_ms": projections(boundary, "boundary")}


def _validated_evaluations(evaluations):
    if not isinstance(evaluations, (list, tuple)) or not evaluations:
        raise ValueError("At least one online occupancy evaluation is required")
    first = evaluations[0]
    if not isinstance(first, dict) or first.get("schema") != SCHEMA:
        raise ValueError(f"Expected evaluation schema {SCHEMA}")
    lags = _lags(first.get("deadline_lags_ms"))
    for evaluation in evaluations:
        if not isinstance(evaluation, dict) or evaluation.get("schema") != SCHEMA:
            raise ValueError(f"Expected evaluation schema {SCHEMA}")
        if (evaluation.get("reference") != first["reference"]
                or evaluation.get("deadline_lags_ms") != lags
                or evaluation.get("observed_until_ms") != first["observed_until_ms"]):
            raise ValueError("Pooled evaluations need identical fixed query definitions")
        for name in ("evaluations_by_lag_ms", "boundary_by_lag_ms"):
            if set(evaluation.get(name, {})) != {str(lag) for lag in lags}:
                raise ValueError("Missing or unexpected deadline projection")
    return first, lags


def rollup(evaluations):
    """Pool exact fixed-query counts/errors across worlds, never mean ratios.

    Select case/distribution/stream subsets before calling. This is descriptive
    utility pooling across supplied worlds, not an independent-sample CI or a
    mechanism comparison. Matched-error comparisons must still intersect query
    identities in corresponding per-world deadline projections.
    """
    first, lags = _validated_evaluations(evaluations)
    by_lag = {}
    for lag in lags:
        key = str(lag)
        by_lag[key] = {
            "primary": _pool_summaries([
                evaluation["evaluations_by_lag_ms"][key]["summary"]
                for evaluation in evaluations]),
            "boundary": _pool_summaries([
                evaluation["boundary_by_lag_ms"][key]["summary"]
                for evaluation in evaluations]),
        }
    return {"worlds": len(evaluations), "reference": dict(first["reference"]),
            "deadline_lags_ms": lags, "by_lag_ms": by_lag}


def _pool_summaries(summaries):
    """Pool sufficient statistics, preserving counts and error sums exactly."""
    count_keys = (
        "reference_queries", "reference_available_queries", "answered_queries",
        "scored_queries", "reference_observation_contributions",
        "answered_reference_observation_contributions", "cohort_queries",
        "deadline_observed_queries", "censored_queries", "deadline_at_eof_queries")
    pooled = {key: sum(summary[key] for summary in summaries)
              for key in count_keys}
    for key in ("absolute_error_sum",
                "reconstructed_answered_observation_contribution_equivalents"):
        pooled[key] = math.fsum(summary[key] for summary in summaries)
    total = pooled["reference_queries"]
    for key, count in (("reference_availability", "reference_available_queries"),
                       ("answered_query_coverage", "answered_queries"),
                       ("scored_query_coverage", "scored_queries")):
        pooled[key] = pooled[count] / total if total else None
    scored = pooled["scored_queries"]
    pooled["occupancy_mae"] = pooled["absolute_error_sum"] / scored if scored else None
    pooled["occupancy_mae_unit"] = "agents"
    pooled["interpretation"] = summaries[0]["interpretation"]
    return pooled


def compact(evaluation):
    """Keep rollup sufficient statistics, dropping per-query private details.

    Compute paired query intersections before compacting. This representation
    is accepted by ``rollup`` and lets a study discard each world's large query
    rows after extracting its matched-error comparison.
    """
    _validated_evaluations([evaluation])
    return {"schema": SCHEMA, "mode": evaluation.get("mode"),
            "reference": dict(evaluation["reference"]),
            "observed_until_ms": evaluation["observed_until_ms"],
            "deadline_lags_ms": list(evaluation["deadline_lags_ms"]),
            "compact": True,
            **{field: {lag: {"summary": dict(value["summary"])}
                       for lag, value in evaluation[field].items()}
               for field in ("evaluations_by_lag_ms", "boundary_by_lag_ms")}}


def summarize_at_checkpoint(evaluation, checkpoint_ms):
    """Summarize due query deadlines only, without retrospectively backfilling.

    A query that missed its own deadline remains a miss at later checkpoints.
    This is cumulative application-deadline utility, not an estimate that can
    be revised whenever another release arrives. No not-yet-due query enters
    reference, coverage, MAE, or contribution denominators.
    """
    first, lags = _validated_evaluations([evaluation])
    checkpoint = occupancy._integer(checkpoint_ms, "checkpoint_ms")
    if checkpoint > first["observed_until_ms"]:
        raise ValueError("Checkpoint exceeds the observed horizon")
    by_lag = {}
    for lag in lags:
        key = str(lag)
        cohorts = {}
        for name, field in (("primary", "evaluations_by_lag_ms"),
                            ("boundary", "boundary_by_lag_ms")):
            queries = first[field][key]["queries"]
            due = [query for query in queries if query["deadline_ms"] <= checkpoint]
            cohorts[name] = {**_summary(due),
                             "not_yet_due_queries": len(queries) - len(due)}
        by_lag[key] = cohorts
    return {"checkpoint_ms": checkpoint, "worlds": 1,
            "reference": dict(first["reference"]),
            "deadline_lags_ms": lags, "by_lag_ms": by_lag}


def paired_rollup(evaluation_pairs):
    """Pool conditional errors on exactly matched observed fixed queries.

    Each pair represents the same source world under two release mechanisms.
    The denominator includes all observed/due queries, while MAE intersects only
    queries scored under both mechanisms. No unmatched errors are substituted.
    """
    if not isinstance(evaluation_pairs, (list, tuple)) or not evaluation_pairs:
        raise ValueError("At least one pair of online evaluations is required")
    evaluations = []
    for pair in evaluation_pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("Each comparison needs two corresponding evaluations")
        evaluations.extend(pair)
    first, lags = _validated_evaluations(evaluations)
    by_lag = {}
    identity = ("column", "row", "start_ms", "end_ms", "deadline_ms",
                "deadline_observed")
    for lag in lags:
        cohorts = {}
        for name, field in (("primary", "evaluations_by_lag_ms"),
                            ("boundary", "boundary_by_lag_ms")):
            errors = []
            denominator = 0
            for before, after in evaluation_pairs:
                a = before[field][str(lag)]["queries"]
                b = after[field][str(lag)]["queries"]
                if len(a) != len(b):
                    raise ValueError("Paired fixed query counts differ")
                for left, right in zip(a, b):
                    if any(left[key] != right[key] for key in identity):
                        raise ValueError("Paired fixed query identities differ")
                    if not left["deadline_observed"]:
                        continue
                    denominator += 1
                    if (left["absolute_error"] is not None
                            and right["absolute_error"] is not None):
                        errors.append((left["absolute_error"],
                                       right["absolute_error"]))
            count = len(errors)
            first_mae = (math.fsum(a for a, _ in errors) / count
                         if count else None)
            second_mae = (math.fsum(b for _, b in errors) / count
                          if count else None)
            cohorts[name] = {
                "reference_queries": denominator,
                "matched_scored_queries": count,
                "matched_query_coverage": (count / denominator
                                           if denominator else None),
                "first_absolute_error_sum": math.fsum(a for a, _ in errors),
                "second_absolute_error_sum": math.fsum(b for _, b in errors),
                "first_mae": first_mae, "second_mae": second_mae,
                "delta_second_minus_first": (second_mae - first_mae
                                             if count else None),
                "occupancy_mae_unit": "agents",
            }
        by_lag[str(lag)] = cohorts
    return {"world_pairs": len(evaluation_pairs),
            "reference": dict(first["reference"]),
            "deadline_lags_ms": lags, "by_lag_ms": by_lag}



def pool_paired_rollups(comparisons):
    """Pool compact per-world matched-query sufficient statistics."""
    if not isinstance(comparisons, (list, tuple)) or not comparisons:
        raise ValueError("At least one paired rollup is required")
    first = comparisons[0]
    lags = _lags(first.get("deadline_lags_ms"))
    for comparison in comparisons:
        if (comparison.get("reference") != first["reference"]
                or comparison.get("deadline_lags_ms") != lags):
            raise ValueError("Paired rollups need identical fixed query definitions")
    by_lag = {}
    for lag in lags:
        cohorts = {}
        for name in ("primary", "boundary"):
            rows = [comparison["by_lag_ms"][str(lag)][name]
                    for comparison in comparisons]
            total = sum(row["reference_queries"] for row in rows)
            scored = sum(row["matched_scored_queries"] for row in rows)
            first_sum = math.fsum(row["first_absolute_error_sum"] for row in rows)
            second_sum = math.fsum(row["second_absolute_error_sum"] for row in rows)
            cohorts[name] = {
                "reference_queries": total, "matched_scored_queries": scored,
                "matched_query_coverage": scored / total if total else None,
                "first_absolute_error_sum": first_sum,
                "second_absolute_error_sum": second_sum,
                "first_mae": first_sum / scored if scored else None,
                "second_mae": second_sum / scored if scored else None,
                "delta_second_minus_first": ((second_sum - first_sum) / scored
                                             if scored else None),
                "occupancy_mae_unit": "agents",
            }
        by_lag[str(lag)] = cohorts
    return {"world_pairs": sum(comparison["world_pairs"] for comparison in comparisons),
            "reference": dict(first["reference"]),
            "deadline_lags_ms": lags, "by_lag_ms": by_lag}
