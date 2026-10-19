"""Batching-invariant public timing and separately labelled private diagnostics.

Each released observation contribution weights its cell's interval statistics.
A distinct person observed several times contributes several weights; this is
not an identity-weighted statistic. Sealing uses simulation time and does not
measure wall-clock processing or network delivery.
"""

import math


def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def weighted_distribution(values):
    """Nearest-rank weighted quantiles; zero-weight rows have no influence."""
    rows = []
    for value, weight in values:
        _count(weight, "distribution weight")
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise ValueError("Distribution values must be finite nonnegative numbers")
        if weight:
            rows.append((value, weight))
    rows.sort()
    weight = sum(count for _, count in rows)
    if not weight:
        return dict(count=0, total_weight=0, min=None, mean=None,
                    p50=None, p95=None, p99=None, max=None)
    def quantile(fraction):
        threshold, accumulated = fraction * weight, 0
        for value, count in rows:
            accumulated += count
            if accumulated >= threshold:
                return value
        return rows[-1][0]
    return dict(count=len(rows), total_weight=weight, min=rows[0][0],
                mean=math.fsum(value * count for value, count in rows) / weight,
                p50=quantile(.5), p95=quantile(.95), p99=quantile(.99),
                max=rows[-1][0])


def _reason_rows(counter):
    return [dict(reason=reason, **counts) for reason, counts in sorted(counter.items())]


def summarize(result):
    """Summarize a validated replay; do not infer missing rejection causes.

    Timing uses only recipient releases. Private terminal evidence is kept in
    its own object and is never used to impute public occupancy or availability.
    Generic retirement labels cannot establish that an actual disclosure, as
    opposed to a private suppression/empty retirement, blocked a later merge.
    """
    releases = result.get("releases")
    if not isinstance(releases, list):
        raise ValueError("Recipient releases must be a list")
    durations, ages, delays = [], [], []
    contributions, zero_cells = 0, 0
    for release in releases:
        start = _count(release.get("start_ms"), "release.start_ms")
        end = _count(release.get("end_ms"), "release.end_ms")
        sealed = _count(release.get("sealed_at_ms"), "release.sealed_at_ms")
        if end <= start or sealed < end:
            raise ValueError("Release intervals or sealing time are invalid")
        cells = release.get("cells")
        if not isinstance(cells, list):
            raise ValueError("A release must contain a cell list")
        for cell in cells:
            weight = _count(cell.get("observation_contributions"), "cell.observation_contributions")
            contributions += weight
            zero_cells += weight == 0
            durations.append((end - start, weight))
            ages.append((sealed - start, weight))
            delays.append((sealed - end, weight))
    public = {
        "weighting": "One weight per released observation contribution, not per release or distinct road user.",
        "observation_contribution_weight": contributions,
        "zero_weight_cells": zero_cells,
        "window_duration_ms": weighted_distribution(durations),
        "simulated_age_upper_bound_ms": weighted_distribution(ages),
        "simulated_post_window_sealing_delay_ms": weighted_distribution(delays),
        "quantile_definition": "Smallest value whose cumulative contribution weight reaches the requested percentile.",
        "timing_note": "Age is sealed_at_ms minus interval start: an interval age upper bound, not exact per-observation age or wall-clock delivery latency.",
    }
    windows = result.get("windows")
    private = {
        "classification": "private_coordination_diagnostics",
        "available": isinstance(windows, list),
        "publication_blocking": {
            "available": False,
            "actual_public_overlap_candidates": None,
            "private_retirement_overlap_candidates": None,
            "reason": "Replay diagnostics do not expose candidate-level public-versus-private retirement rejection causes; generic labels are not interpreted as disclosure blocks.",
        },
    }
    if isinstance(windows, list):
        completion = {}
        cell_reasons = {}
        categories = {name: dict(cells=0, observation_contributions=0)
                      for name in ("selected", "suppressed", "zero_contribution_retirement")}
        for window in windows:
            weight = _count(window.get("input_observation_contributions", 0),
                            "window.input_observation_contributions")
            reason = window.get("completion_reason", "unspecified")
            if not isinstance(reason, str):
                raise ValueError("Completion reasons must be strings")
            row = completion.setdefault(reason, dict(windows=0, observation_contributions=0))
            row["windows"] += 1
            row["observation_contributions"] += weight
            cells = window.get("cells", [])
            if not isinstance(cells, list):
                raise ValueError("Private terminal cells must be a list")
            for cell in cells:
                weight = _count(cell.get("observation_contributions"), "cell.observation_contributions")
                selected = cell.get("selected")
                if not isinstance(selected, bool):
                    raise ValueError("Terminal cell selected flags must be Boolean")
                category = ("zero_contribution_retirement" if not weight
                            else "selected" if selected else "suppressed")
                categories[category]["cells"] += 1
                categories[category]["observation_contributions"] += weight
                reason = cell.get("reason", "unspecified")
                if not isinstance(reason, str):
                    raise ValueError("Cell reasons must be strings")
                key = (category, reason)
                row = cell_reasons.setdefault(key, dict(cells=0, observation_contributions=0))
                row["cells"] += 1
                row["observation_contributions"] += weight
        private.update(
            terminal_windows=len(windows), categories=categories,
            completion_reasons=_reason_rows(completion),
            terminal_cell_reasons=[dict(category=category, reason=reason, **counts)
                                  for (category, reason), counts in sorted(cell_reasons.items())],
            reason_note="Terminal reason labels are reported as recorded; they do not identify counterfactual merge utility or causal publication loss.")
    return dict(public_release_timing=public, private_coordination_diagnostics=private)
