"""Frozen-study uncertainty for one matched IN/OUT episode per source recording.

No fitting, calibration or score-direction selection happens here. Binomial rate
intervals are exact Clopper--Pearson inversions. The AUC-difference bootstrap is
conditional on already fitted models and resamples complete source pairs jointly
across methods, rather than treating observations or worlds as independent units.
Only the Python standard library and the maintained attack metrics are used.
"""

from collections import defaultdict
from collections.abc import Mapping
import math
import random

from empirical_privacy import attack_metrics


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _confidence(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence must be finite and strictly between zero and one")
    if not math.isfinite(value) or not 0 < value < 1:
        raise ValueError("confidence must be finite and strictly between zero and one")
    return float(value)


def _binomial_tail(trials, probability, first, last):
    """Sum a selected tail directly in log space, without subtracting from one.

    Direct small-tail evaluation matters at the interval boundaries: computing
    1-CDF can lose precision. Log-sum-exp avoids overflowing combinations and
    underflow of all but a representable tail. This inversion is intended for
    finite study counts (16/32), and also covers larger ordinary binomial samples.
    """
    if probability <= 0:
        return float(first == 0)
    if probability >= 1:
        return float(last == trials)
    log_p, log_q = math.log(probability), math.log1p(-probability)
    log_factorial = math.lgamma(trials + 1)
    terms = [log_factorial - math.lgamma(k + 1) - math.lgamma(trials - k + 1)
             + k * log_p + (trials - k) * log_q for k in range(first, last + 1)]
    peak = max(terms)
    return min(1.0, math.exp(peak) * math.fsum(math.exp(term - peak) for term in terms))


def _tail_root(trials, first, last, target, increasing):
    low, high = 0.0, 1.0
    # Bisection stops when the midpoint has no distinct binary64 representation.
    for _ in range(1100):
        middle = low + (high - low) / 2
        if middle == low or middle == high:
            break
        value = _binomial_tail(trials, middle, first, last)
        if (value < target) == increasing:
            low = middle
        else:
            high = middle
    return low + (high - low) / 2


def clopper_pearson(successes, trials, confidence=0.95):
    """Return a two-sided exact binomial interval, including endpoint cases.

    Lower: solve P_p[X >= successes] = alpha/2. Upper: solve
    P_p[X <= successes] = alpha/2. All-zero/all-one endpoints use closed forms.
    With no trials the estimate is undefined and the interval is [0,1], not zero.
    Exact refers to binomial coverage; numeric endpoints are binary64 inversions.
    """
    successes = _integer(successes, "successes")
    trials = _integer(trials, "trials")
    confidence = _confidence(confidence)
    if successes > trials:
        raise ValueError("successes cannot exceed trials")
    tail = (1.0 - confidence) / 2
    if trials == 0:
        lower, upper = 0.0, 1.0
    else:
        lower = (0.0 if successes == 0 else
                 math.exp(math.log(tail) / trials) if successes == trials else
                 _tail_root(trials, successes, trials, tail, True))
        upper = (1.0 if successes == trials else
                 -math.expm1(math.log(tail) / trials) if successes == 0 else
                 _tail_root(trials, 0, successes, tail, False))
    return {"method": "two_sided_exact_clopper_pearson", "confidence_level": confidence,
            "successes": successes, "trials": trials,
            "estimate": successes / trials if trials else None,
            "lower": lower, "upper": upper}


def attack_metrics_with_intervals(scores, labels, threshold, confidence=0.95):
    """Add exact marginal TPR/FPR intervals to unchanged fixed-threshold metrics.

    One positive and one negative episode per independent recording are required
    by the caller's study design. These are individual binomial-rate intervals,
    not a simultaneous interval or an interval for threshold advantage.
    """
    confidence = _confidence(confidence)
    result = attack_metrics(scores, labels, threshold)
    result["tpr_interval"] = clopper_pearson(
        result["true_positive"], result["positive_cases"], confidence)
    result["fpr_interval"] = clopper_pearson(
        result["false_positive"], result["negative_cases"], confidence)
    return result


def _paired_predictions(rows, name):
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{name} must be a nonempty prediction-row array")
    grouped = defaultdict(dict)
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{name} prediction row must be an object")
        group = row.get("group_id")
        label, score = row.get("label"), row.get("score")
        if not isinstance(group, str) or not group:
            raise ValueError("group_id must be a nonempty string")
        if type(label) is not int or label not in (0, 1):
            raise ValueError("Each prediction label must be integer zero or one")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("Prediction probability must be finite and in [0,1]")
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Prediction probability must be finite and in [0,1]")
        if label in grouped[group]:
            raise ValueError("Duplicate source-group/membership prediction")
        grouped[group][label] = float(score)
    if any(set(pair) != {0, 1} for pair in grouped.values()):
        raise ValueError("Each source group needs exactly one IN and one OUT prediction")
    return dict(grouped)


def _percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def paired_source_auc_difference(left, right, replicates=1000, seed=20261025301,
                                 confidence=0.95):
    """Compare AUC(left)-AUC(right), resampling the same source pairs jointly.

    Inputs are arrays of {group_id: str, label: 0/1, score: probability}. Every
    recording must occur exactly twice, once in each world, and the two methods
    must contain identical group sets. Additional row metadata is ignored.
    Percentiles use linear interpolation at (N-1)*q. No score flipping or model
    refitting occurs. One source gives no bootstrap interval; it is not replaced
    by an artificially precise degenerate interval.
    """
    replicates = _integer(replicates, "replicates", 1)
    seed = _integer(seed, "seed")
    confidence = _confidence(confidence)
    left = _paired_predictions(left, "left")
    right = _paired_predictions(right, "right")
    if set(left) != set(right):
        raise ValueError("Paired methods must contain identical source groups")
    groups = sorted(left)

    def difference(selected):
        labels = [label for _ in selected for label in (0, 1)]
        first = [left[group][label] for group in selected for label in (0, 1)]
        second = [right[group][label] for group in selected for label in (0, 1)]
        return (attack_metrics(first, labels, 0.5)["roc_auc"]
                - attack_metrics(second, labels, 0.5)["roc_auc"])

    result = {"method": "paired_source_group_percentile_bootstrap",
              "auc_difference": difference(groups), "interval": None,
              "confidence_level": confidence, "independent_groups": len(groups),
              "replicates": 0, "requested_replicates": replicates, "seed": seed,
              "resampling_unit": "recording_with_both_worlds_and_both_methods",
              "scope": "Conditional on fitted models; excludes training/calibration uncertainty"}
    if len(groups) < 2:
        result["reason"] = "insufficient_independent_groups"
        return result
    rng = random.Random(seed)
    samples = [difference([rng.choice(groups) for _ in groups]) for _ in range(replicates)]
    tail = (1 - confidence) / 2
    result.update(interval=[_percentile(samples, tail), _percentile(samples, 1-tail)],
                  replicates=replicates)
    return result
