"""Public-only features and a transparent, bounded-knowledge membership attack.

This module does not read replays, GT, candidate journals, target identities, labels
or private replay diagnostics while exporting/featurizing output. The attacker
knows a declared candidate trace independently of its inclusion label. Coordinates
are metres, logical times are milliseconds, intervals and rectangles are half open.
The entire permitted release history is summarized; no private suppression or
measured-empty information is used to fill gaps. A numeric zero placeholder always
has a separate availability feature, so sparse absence is never asserted to be a
zero occupancy measurement. Public cell mean occupancy is a cell-wide aggregate,
not recovered point occupancy. Unknown public means remain unknown.

``include_geometry=False`` projects out explicit geometry/timing features, while
still using public geometry/timing to align the same candidate observations. This
is a count-plus-availability ablation, not a causal isolation of count leakage.
There is no claim of attack optimality, formal anonymity or differential privacy.
The classifier is deterministic L2-regularized logistic regression, with feature
scaling fitted on training rows only. Calibration is separate from test metrics.
All artifacts are standard-library JSON serializable with no NaN/Infinity.
"""

from __future__ import annotations

import math
from typing import Any

from privacy import canonical_transcript


PUBLIC_SCHEMA = "ump.public-transcript.v1"
MODEL_SCHEMA = "ump.logistic-membership.v1"
_PUBLIC_KEYS = frozenset({"schema", "coverage", "sampling_period_ms", "end_ms", "releases"})
_COVERAGE_KEYS = frozenset({"x", "y", "width", "height", "leaf_depth"})
_KNOWLEDGE_KEYS = frozenset({"observed_at_ms", "x", "y", "cell_id"})
_COUNT_FEATURES = (
    "release_count", "public_cell_count", "public_mean_known_fraction",
    "public_contributions_sum", "public_distinct_support_sum",
    "public_mean_occupancy_sum", "public_mean_occupancy_mean", "public_mean_occupancy_max",
    "target_cell_matched_fraction", "target_mean_known_fraction",
    "target_mean_occupancy_mean", "target_mean_occupancy_max",
    "target_contributions_mean", "target_distinct_support_mean",
    "target_first_half_mean_known_fraction", "target_first_half_mean_occupancy_mean",
    "target_second_half_mean_known_fraction", "target_second_half_mean_occupancy_mean",
)
_GEOMETRY_FEATURES = (
    "release_duration_mean_ms", "release_duration_max_ms", "release_seal_delay_mean_ms",
    "public_cell_area_mean_m2", "public_cell_area_max_m2", "public_cell_depth_mean",
    "public_released_area_time_fraction", "public_last_release_end_fraction",
    "target_matched_cell_area_mean_m2", "target_matched_cell_depth_mean",
    "target_matched_window_mean_ms", "target_matched_release_age_mean_ms",
    "target_matched_seal_delay_mean_ms",
)


def _object(value: Any, where: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be an object")
    return value


def _keys(value: dict, expected: frozenset, where: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{where} has missing or unknown fields: "
                         f"missing={sorted(expected - value.keys())}, unknown={sorted(value.keys() - expected)}")


def _number(value: Any, where: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{where} must be finite numeric data")
    if minimum is not None and value < minimum:
        raise ValueError(f"{where} must be >= {minimum}")
    return float(value)


def _integer(value: Any, where: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{where} must be an integer >= {minimum}")
    return value


def _coverage(value: Any) -> dict:
    value = _object(value, "coverage")
    _keys(value, _COVERAGE_KEYS, "coverage")
    numbers = {key: _number(value[key], f"coverage.{key}") for key in ("x", "y", "width", "height")}
    if (numbers["width"] <= 0 or numbers["height"] <= 0
            or not math.isclose(numbers["width"], numbers["height"], rel_tol=1e-12)
            or not math.isfinite(numbers["x"] + numbers["width"])
            or not math.isfinite(numbers["y"] + numbers["height"])
            or not math.isfinite(numbers["width"] * numbers["height"])):
        raise ValueError("coverage must have finite square positive dimensions and bounds")
    depth = _integer(value["leaf_depth"], "coverage.leaf_depth", 1)
    if depth > 14:
        raise ValueError("coverage.leaf_depth exceeds supported quadtree depth 14")
    return {**numbers, "leaf_depth": depth}


def _cell_geometry(cell_id: int, depth: int, coverage: dict) -> tuple[float, float, float, float]:
    x, y, width, height = (coverage[key] for key in ("x", "y", "width", "height"))
    for level in reversed(range(depth)):
        quadrant = (cell_id >> (2 * level)) & 3
        width, height = width / 2, height / 2
        x += (quadrant & 1) * width
        y += ((quadrant >> 1) & 1) * height
    return x, y, width, height


def _validated_public(public: dict) -> dict:
    public = _object(public, "public transcript")
    _keys(public, _PUBLIC_KEYS, "public transcript")
    if public["schema"] != PUBLIC_SCHEMA:
        raise ValueError(f"Expected public schema {PUBLIC_SCHEMA}")
    coverage = _coverage(public["coverage"])
    period = _integer(public["sampling_period_ms"], "sampling_period_ms", 1)
    end = _integer(public["end_ms"], "end_ms", 1)
    if end <= period:
        raise ValueError("end_ms must include at least one sensor observation opportunity")
    # Reuse the public whitelist, scalar and sequence checks of the diagnostic.
    canonical_transcript({"schema": "ump.replay-result.v1", "releases": public["releases"]})
    for index, release in enumerate(public["releases"]):
        if release["release_id"] != f"release-{index:06d}":
            raise ValueError("Public release IDs must use normalized sequential identifiers")
        if release["end_ms"] > end or release["sealed_at_ms"] > end:
            raise ValueError("Public release exceeds the declared observation horizon")
        for cell in release["cells"]:
            if cell["depth"] > coverage["leaf_depth"]:
                raise ValueError("Public cell is deeper than the declared finest grid")
            expected = _cell_geometry(cell["cell_id"], cell["depth"], coverage)
            actual = tuple(cell[key] for key in ("x", "y", "width", "height"))
            if any(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-9) for a, b in zip(actual, expected)):
                raise ValueError("Public cell geometry disagrees with its quadtree ID")
        # Parent and child cells cannot both describe a public cut in one interval.
        cells = sorted((cell["depth"], cell["cell_id"]) for cell in release["cells"])
        seen = set()
        for depth, cell_id in cells:
            if any(cell_id >> (2 * (depth - ancestor)) in seen for ancestor in range(1, depth)):
                raise ValueError("Public release contains overlapping ancestor/descendant cells")
            seen.add(cell_id)
    return public


def export_public(result: dict) -> dict:
    """Copy only the approved recipient channel from a private replay result.

    This is an allowlist, not a redaction. Private source IDs, configuration,
    windows, input/accounted totals and runtime are never copied. Unknown public
    release/cell fields fail so additions require an explicit channel review.
    Policy identifiers remain public under the declared threat model. This function
    is a file-format boundary, not database access control.
    """
    transcript = canonical_transcript(result)
    source = _object(result.get("source"), "result.source")
    coverage = _coverage(source.get("coverage"))
    releases = []
    for index, (start, end, sealed, model, policy_id, policy_version, cells) in enumerate(transcript):
        releases.append({"release_id": f"release-{index:06d}", "start_ms": start, "end_ms": end,
                         "sealed_at_ms": sealed, "model": model, "policy_id": policy_id,
                         "policy_version": policy_version, "cells": [dict(zip(
                             ("cell_id", "depth", "x", "y", "width", "height", "observation_contributions",
                              "distinct_road_users", "mean_sample_occupancy", "effective_policy_id"), cell))
                             for cell in cells]})
    public = {"schema": PUBLIC_SCHEMA, "coverage": coverage,
              "sampling_period_ms": source.get("sampling_period_ms"),
              "end_ms": source.get("end_ms"), "releases": releases}
    _validated_public(public)
    return public


def feature_names(include_geometry: bool = True) -> list[str]:
    """Return the fixed feature coordinate system, independent of release/trace length."""
    if not isinstance(include_geometry, bool):
        raise ValueError("include_geometry must be boolean")
    return list(_COUNT_FEATURES + (_GEOMETRY_FEATURES if include_geometry else ()))


def _mean(values: list) -> float:
    return math.fsum(values) / len(values) if values else 0.0


def _maximum(values: list) -> float:
    return max(values) if values else 0.0


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def feature_vector(public: dict, knowledge: list[dict], include_geometry: bool = True) -> list[float]:
    """Summarize releases and declared candidate points without consulting private data.

    Candidate ``cell_id`` is checked against its coordinate at the public finest
    depth; it is not itself a feature. Repeated identical knowledge points are
    rejected rather than silently overweighted. The supplied knowledge may be
    empty. Query matches use both spatial and temporal half-open containment.
    ``*_mean_known_fraction`` and ``*_cell_matched_fraction`` distinguish missing
    output, unknown mean and an explicitly released zero. First/second-half features
    refer to the fixed public horizon, not the data-dependent release sequence.
    ``public_distinct_support_sum`` sums per-cell/window supports, never a unique
    whole-history population. Geometry/timing features describe logical release
    semantics, not wall-clock/transport performance.
    """
    _validated_public(public)
    names = feature_names(include_geometry)
    if not isinstance(knowledge, list):
        raise ValueError("knowledge must be an array")
    coverage, end = public["coverage"], public["end_ms"]
    seen_points, points = set(), []
    for index, point in enumerate(knowledge):
        point = _object(point, f"knowledge[{index}]")
        _keys(point, _KNOWLEDGE_KEYS, f"knowledge[{index}]")
        time = _integer(point["observed_at_ms"], "knowledge.observed_at_ms", 1)
        x, y = (_number(point[key], f"knowledge.{key}") for key in ("x", "y"))
        cell_id = _integer(point["cell_id"], "knowledge.cell_id", 1)
        depth = coverage["leaf_depth"]
        if (time >= end or cell_id >> (2 * depth) != 3
                or not coverage["x"] <= x < coverage["x"] + coverage["width"]
                or not coverage["y"] <= y < coverage["y"] + coverage["height"]):
            raise ValueError("Candidate knowledge point is outside public coverage, horizon or finest grid")
        cx, cy, cw, ch = _cell_geometry(cell_id, depth, coverage)
        if not (cx <= x < cx + cw and cy <= y < cy + ch):
            raise ValueError("Candidate knowledge cell_id does not contain its coordinate")
        key = (time, x, y)
        if key in seen_points:
            raise ValueError("Duplicate candidate knowledge point")
        seen_points.add(key)
        points.append((time, x, y))
    releases = public["releases"]
    cells = [cell for release in releases for cell in release["cells"]]
    means = [cell["mean_sample_occupancy"] for cell in cells if cell["mean_sample_occupancy"] is not None]
    matched, known, halves = [], [], [[], []]
    half_counts = [0, 0]
    for time, x, y in points:
        half = int(time >= end / 2)
        half_counts[half] += 1
        for release in releases:
            if not release["start_ms"] <= time < release["end_ms"]:
                continue
            cell = next((cell for cell in release["cells"]
                         if cell["x"] <= x < cell["x"] + cell["width"]
                         and cell["y"] <= y < cell["y"] + cell["height"]), None)
            if cell is not None:
                matched.append((time, release, cell))
                if cell["mean_sample_occupancy"] is not None:
                    known.append(cell["mean_sample_occupancy"])
                    halves[half].append(cell["mean_sample_occupancy"])
                # Independent local windows overlap in time but not in space.
                # A time match without this candidate's cell cannot end the search.
                break
    values = [
        len(releases), len(cells), _ratio(len(means), len(cells)),
        sum(cell["observation_contributions"] for cell in cells),
        sum(cell["distinct_road_users"] for cell in cells),
        math.fsum(means), _mean(means), _maximum(means),
        _ratio(len(matched), len(points)), _ratio(len(known), len(points)),
        _mean(known), _maximum(known),
        _mean([cell["observation_contributions"] for _, _, cell in matched]),
        _mean([cell["distinct_road_users"] for _, _, cell in matched]),
        _ratio(len(halves[0]), half_counts[0]), _mean(halves[0]),
        _ratio(len(halves[1]), half_counts[1]), _mean(halves[1]),
    ]
    if include_geometry:
        durations = [release["end_ms"] - release["start_ms"] for release in releases]
        areas = [cell["width"] * cell["height"] for cell in cells]
        area_time = math.fsum((release["end_ms"] - release["start_ms"])
                             * math.fsum(cell["width"] * cell["height"] for cell in release["cells"])
                             for release in releases)
        values += [
            _mean(durations), _maximum(durations),
            _mean([release["sealed_at_ms"] - release["end_ms"] for release in releases]),
            _mean(areas), _maximum(areas), _mean([cell["depth"] for cell in cells]),
            area_time / (coverage["width"] * coverage["height"] * end),
            releases[-1]["end_ms"] / end if releases else 0.0,
            _mean([cell["width"] * cell["height"] for _, _, cell in matched]),
            _mean([cell["depth"] for _, _, cell in matched]),
            _mean([release["end_ms"] - release["start_ms"] for _, release, _ in matched]),
            _mean([release["sealed_at_ms"] - time for time, release, _ in matched]),
            _mean([release["sealed_at_ms"] - release["end_ms"] for _, release, _ in matched]),
        ]
    if len(values) != len(names) or any(not math.isfinite(value) for value in values):
        raise ValueError("Feature arithmetic produced nonfinite values")
    return [float(value) for value in values]


def _rows(rows: Any, dimension: int | None = None, nonempty: bool = True) -> list[list[float]]:
    if not isinstance(rows, list) or (nonempty and not rows):
        raise ValueError("rows must be a nonempty array" if nonempty else "rows must be an array")
    checked = []
    for index, row in enumerate(rows):
        if not isinstance(row, list) or not row:
            raise ValueError(f"rows[{index}] must be a nonempty feature array")
        if dimension is None:
            dimension = len(row)
        if len(row) != dimension:
            raise ValueError("Feature dimensions differ")
        checked.append([_number(value, "feature") for value in row])
    return checked


def _labels(labels: Any, count: int) -> list[int]:
    if not isinstance(labels, list) or len(labels) != count:
        raise ValueError("labels must have one binary integer per score/row")
    if any(isinstance(label, bool) or not isinstance(label, int) or label not in (0, 1) for label in labels):
        raise ValueError("labels must contain only integer 0 or 1")
    return labels


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1 + exponential)


def fit_classifier(rows: list[list[float]], labels: list[int], *, l2: float = 0.1,
                   max_iterations: int = 500, tolerance: float = 1e-8) -> dict:
    """Fit deterministic logistic regression on *training data only*.

    Objective: mean binary log loss plus ``l2/2 * sum(weight**2)``; the intercept
    is unpenalized. Population means/scales are fitted here and frozen in the JSON
    model. Constant training features receive scale 1 and zero fitted coefficient.
    Backtracking full-batch descent has no random state or external dependency.
    A single-class training set is rejected; an all-constant balanced control
    legitimately predicts the prior. No calibration or test data enter this API.
    """
    rows = _rows(rows)
    labels = _labels(labels, len(rows))
    if set(labels) != {0, 1}:
        raise ValueError("Training requires both membership classes")
    l2 = _number(l2, "l2", 0)
    max_iterations = _integer(max_iterations, "max_iterations", 1)
    tolerance = _number(tolerance, "tolerance", 0)
    if tolerance == 0:
        raise ValueError("tolerance must be positive")
    count, dimension = len(rows), len(rows[0])
    means = [_mean([row[index] for row in rows]) for index in range(dimension)]
    scales = []
    for index, mean in enumerate(means):
        variance = _mean([(row[index] - mean) ** 2 for row in rows])
        scales.append(math.sqrt(variance) if variance > 0 else 1.0)
    scaled = [[(value - mean) / scale for value, mean, scale in zip(row, means, scales)] for row in rows]
    if any(not math.isfinite(value) for row in scaled for value in row):
        raise ValueError("Training feature scaling overflowed")
    prior = sum(labels) / count
    intercept, weights = math.log(prior / (1 - prior)), [0.0] * dimension

    def objective(candidate: list[float], bias: float) -> float:
        loss = []
        for row, label in zip(scaled, labels):
            logit = bias + math.fsum(weight * value for weight, value in zip(candidate, row))
            loss.append(max(logit, 0) - logit * label + math.log1p(math.exp(-abs(logit))))
        return _mean(loss) + l2 / 2 * math.fsum(weight * weight for weight in candidate)

    loss, converged, iterations = objective(weights, intercept), False, 0
    for iterations in range(1, max_iterations + 1):
        residuals = [_sigmoid(intercept + math.fsum(weight * value for weight, value in zip(weights, row))) - label
                     for row, label in zip(scaled, labels)]
        bias_gradient = _mean(residuals)
        gradient = [_mean([residual * row[index] for residual, row in zip(residuals, scaled)]) + l2 * weights[index]
                    for index in range(dimension)]
        norm_squared = bias_gradient * bias_gradient + math.fsum(value * value for value in gradient)
        if math.sqrt(norm_squared) <= tolerance:
            converged = True
            break
        step = 1.0
        for _ in range(60):
            new_weights = [weight - step * value for weight, value in zip(weights, gradient)]
            new_intercept = intercept - step * bias_gradient
            new_loss = objective(new_weights, new_intercept)
            if new_loss <= loss - 1e-4 * step * norm_squared:
                break
            step /= 2
        else:
            break
        improvement = loss - new_loss
        weights, intercept, loss = new_weights, new_intercept, new_loss
        if improvement <= tolerance * max(1.0, abs(loss)):
            converged = True
            break
    model = {"schema": MODEL_SCHEMA, "feature_count": dimension,
             "training_rows": count, "training_prior": prior, "means": means, "scales": scales,
             "weights": weights, "intercept": intercept, "l2": l2,
             "iterations": iterations, "converged": converged, "training_objective": loss}
    _validate_model(model)
    return model


def _validate_model(model: dict) -> None:
    model = _object(model, "model")
    expected = frozenset({"schema", "feature_count", "training_rows", "training_prior", "means", "scales",
                          "weights", "intercept", "l2", "iterations", "converged", "training_objective"})
    _keys(model, expected, "model")
    if model["schema"] != MODEL_SCHEMA:
        raise ValueError(f"Expected model schema {MODEL_SCHEMA}")
    dimension = _integer(model["feature_count"], "feature_count", 1)
    _integer(model["training_rows"], "training_rows", 2)
    prior = _number(model["training_prior"], "training_prior")
    if not 0 < prior < 1:
        raise ValueError("training_prior must lie strictly between zero and one")
    for key in ("means", "scales", "weights"):
        if not isinstance(model[key], list) or len(model[key]) != dimension:
            raise ValueError(f"model.{key} has wrong feature dimension")
        for value in model[key]:
            _number(value, f"model.{key}")
        if key == "scales" and any(value <= 0 for value in model[key]):
            raise ValueError("model scales must be positive")
    _number(model["intercept"], "intercept")
    _number(model["l2"], "l2", 0)
    _number(model["training_objective"], "training_objective", 0)
    _integer(model["iterations"], "iterations", 1)
    if not isinstance(model["converged"], bool):
        raise ValueError("model.converged must be boolean")


def predict_scores(model: dict, rows: list[list[float]]) -> list[float]:
    """Predict using frozen training scaling; this function never modifies the model."""
    _validate_model(model)
    rows = _rows(rows, dimension=model["feature_count"], nonempty=False)
    result = []
    for row in rows:
        scaled = [(value - mean) / scale for value, mean, scale in zip(row, model["means"], model["scales"])]
        if any(not math.isfinite(value) for value in scaled):
            raise ValueError("Prediction feature scaling overflowed")
        logit = model["intercept"] + math.fsum(weight * value for weight, value in zip(model["weights"], scaled))
        result.append(_sigmoid(logit))
    return result


def _scores(scores: Any) -> list[float]:
    if not isinstance(scores, list):
        raise ValueError("scores must be an array")
    checked = [_number(score, "score", 0) for score in scores]
    if any(score > 1 for score in checked):
        raise ValueError("Probability scores must be <= 1")
    return checked


def attack_metrics(scores: list[float], labels: list[int], threshold: float) -> dict:
    """Tie-aware ROC-AUC and fixed-threshold metrics, with undefined values as null.

    A positive decision uses ``score >= threshold``. Advantage is TPR minus FPR,
    not one minus accuracy. Precision uses the evaluated case prior; it must not be
    interpreted as deployment precision when membership prevalence differs.
    No score direction or threshold is chosen from these labels.
    """
    scores = _scores(scores)
    labels = _labels(labels, len(scores))
    threshold = _number(threshold, "threshold")
    positives, negatives = sum(labels), len(labels) - sum(labels)
    tp = sum(label == 1 and score >= threshold for score, label in zip(scores, labels))
    fp = sum(label == 0 and score >= threshold for score, label in zip(scores, labels))
    fn, tn = positives - tp, negatives - fp
    tpr, fpr = (tp / positives if positives else None), (fp / negatives if negatives else None)
    auc = None
    if positives and negatives:
        ordered = sorted(zip(scores, labels))
        index, rank_sum = 0, 0.0
        while index < len(ordered):
            stop = index + 1
            while stop < len(ordered) and ordered[stop][0] == ordered[index][0]:
                stop += 1
            average_rank = (index + 1 + stop) / 2
            rank_sum += average_rank * sum(label for _, label in ordered[index:stop])
            index = stop
        auc = (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)
    return {"roc_auc": auc, "tpr": tpr, "fpr": fpr,
            "balanced_accuracy": (tpr + 1 - fpr) / 2 if tpr is not None and fpr is not None else None,
            "advantage": tpr - fpr if tpr is not None and fpr is not None else None,
            "precision_at_evaluation_prior": tp / (tp + fp) if tp + fp else None,
            "evaluation_prior": positives / len(labels) if labels else None,
            "positive_cases": positives, "negative_cases": negatives,
            "true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn,
            "threshold": threshold}


def calibrate_threshold(scores: list[float], labels: list[int], target_fpr: float = 0.1) -> dict:
    """Choose a conservative empirical operating point using calibration data only.

    Among thresholds with calibration FPR <= target_fpr, maximize calibration TPR;
    ties choose smaller FPR then higher threshold. The all-negative decision is a
    valid candidate. Discrete calibration FPR resolution is explicitly reported.
    A calibration set without either class cannot select the intended operating
    point and is rejected. This is not a confidence-bound or deployment guarantee.
    """
    scores = _scores(scores)
    labels = _labels(labels, len(scores))
    target_fpr = _number(target_fpr, "target_fpr", 0)
    if target_fpr > 1 or set(labels) != {0, 1}:
        raise ValueError("Calibration requires both classes and target_fpr in [0,1]")
    thresholds = sorted(set(scores) | {math.nextafter(max(scores), math.inf)}, reverse=True)
    candidates = [attack_metrics(scores, labels, threshold) for threshold in thresholds]
    permitted = [metrics for metrics in candidates if metrics["fpr"] <= target_fpr]
    selected = max(permitted, key=lambda metrics: (metrics["tpr"], -metrics["fpr"], metrics["threshold"]))
    return {"schema": "ump.attack-calibration.v1", "threshold": selected["threshold"],
            "target_fpr": target_fpr, "negative_case_fpr_resolution": 1 / selected["negative_cases"],
            "selection": "maximize calibration TPR subject to empirical calibration FPR cap; ties prefer lower FPR",
            "calibration": selected}


def precision_at_prior(tpr: float, fpr: float, prior: float) -> float | None:
    """Bayes precision at a supplied deployment membership prior, or null if no positives."""
    values = [_number(value, name, 0) for value, name in ((tpr, "tpr"), (fpr, "fpr"), (prior, "prior"))]
    if any(value > 1 for value in values):
        raise ValueError("tpr, fpr and prior must lie in [0,1]")
    numerator = values[0] * values[2]
    denominator = numerator + values[1] * (1 - values[2])
    return numerator / denominator if denominator else None
