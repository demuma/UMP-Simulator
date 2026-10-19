#!/usr/bin/env python3
"""Plot paired coordination differences from a completed private study summary.

Matplotlib is optional and used only for exporting PNG/SVG figures. Each dot is
one seeded frozen realization, paired between local and common coordination.
Mechanism fixtures are deliberately excluded from the statistical display.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import median


STRATEGIES = ("temporal_first", "spatial_first")
STRATEGY_LABELS = {"temporal_first": "Temporal First", "spatial_first": "Spatial First"}
COLORS = {"temporal_first": "#2463a2", "spatial_first": "#8651a5"}
PANELS = (
    ("retained_observation_fraction", 100, "Retained observations", "Local minus common (percentage points)"),
    ("answered_query_coverage", 100, "Answered fixed queries", "Local minus common (percentage points)"),
    ("mean_observation_age_ms", 1, "Mean retained observation age", "Local minus common (simulated ms)"),
)
MATCHED_PANEL = ("matched_occupancy_mae", 1, "MAE on paired answered queries", "Local minus common (road users)")


def _number(value, context):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{context} must be finite or null")
    return value


def _text(value, context):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a nonempty string")
    return value


def prepare(summary):
    """Validate paired numerical records without importing plotting dependencies."""
    if not isinstance(summary, dict) or not isinstance(summary.get("pairs"), list):
        raise ValueError("Expected a study summary with a pairs list")
    rows, seen = [], set()
    for index, pair in enumerate(summary["pairs"]):
        if not isinstance(pair, dict):
            raise ValueError("Every pair must be a dictionary")
        if pair.get("kind") == "mechanism":
            continue
        if pair.get("kind") != "replicate":
            raise ValueError("Pair kind must be mechanism or replicate")
        case = _text(pair.get("case"), f"pairs[{index}].case")
        family = _text(pair.get("family"), f"pairs[{index}].family")
        strategy = pair.get("strategy")
        if strategy not in STRATEGIES:
            raise ValueError("Unsupported adaptation strategy")
        seed = pair.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("Replicate seed must be a nonnegative integer")
        key = (case, strategy)
        if key in seen:
            raise ValueError("Duplicate case and strategy pair")
        seen.add(key)
        raw_metrics = pair.get("metrics")
        if not isinstance(raw_metrics, dict):
            raise ValueError("Every pair requires a metrics dictionary")
        values = {}
        for metric, *_ in PANELS + (MATCHED_PANEL,):
            if metric not in raw_metrics:
                if metric == MATCHED_PANEL[0]:
                    values[metric] = None
                    continue
                raise ValueError(f"Required metric is absent: {metric}")
            raw = raw_metrics[metric]
            if not isinstance(raw, dict):
                raise ValueError(f"Metric {metric} must be a dictionary")
            common, local, delta = (_number(raw.get(name), f"{metric}.{name}") for name in
                                    ("common", "local", "delta_local_minus_common"))
            if any(value is not None and value < 0 for value in (common, local)):
                raise ValueError(f"Metric {metric} cannot be negative")
            if metric in ("retained_observation_fraction", "answered_query_coverage"):
                if any(value is not None and value > 1 for value in (common, local)):
                    raise ValueError(f"Metric {metric} must be in [0,1]")
            expected = local - common if local is not None and common is not None else None
            if ((expected is None) != (delta is None)
                    or expected is not None and not math.isclose(delta, expected, rel_tol=1e-9, abs_tol=1e-10)):
                raise ValueError(f"Metric {metric} has an inconsistent paired difference")
            values[metric] = delta
        rows.append(dict(case=case, family=family, strategy=strategy, seed=seed, values=values))
    if not rows:
        raise ValueError("No seeded replicate pairs are available to plot")
    rows.sort(key=lambda row: (row["family"], STRATEGIES.index(row["strategy"]), row["seed"], row["case"]))
    return rows


def jitter(row):
    """Stable visual displacement only; never resample observations or outcomes."""
    identity = json.dumps([row[key] for key in ("family", "case", "seed")], separators=(",", ":"))
    fraction = int(hashlib.sha256(identity.encode()).hexdigest()[:12], 16) / (16 ** 12 - 1)
    return (fraction - .5) * .36


def export(summary, output):
    rows = prepare(summary)
    output = Path(output)
    destinations = [output.with_suffix(suffix) for suffix in (".png", ".svg")]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise ValueError("Output files already exist; choose a new prefix")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise ValueError("Figure export requires the optional matplotlib package") from error
    groups = sorted({(row["family"], row["strategy"]) for row in rows},
                    key=lambda group: (group[0], STRATEGIES.index(group[1])))
    panels = list(PANELS)
    if any(row["values"][MATCHED_PANEL[0]] is not None for row in rows):
        panels.append(MATCHED_PANEL)
    labels = []
    for family, strategy in groups:
        count = sum((row["family"], row["strategy"]) == (family, strategy) for row in rows)
        labels.append(f"{family.replace('_', ' ').capitalize()}\n{STRATEGY_LABELS[strategy]} (n={count})")
    created = []
    figure = None
    with plt.rc_context({"svg.hashsalt": "ump-coordination-study-v1", "svg.fonttype": "none",
                         "font.family": "DejaVu Sans", "font.size": 10}):
        try:
            figure, axes = plt.subplots(1, len(panels), figsize=(4.05 * len(panels) + 2, max(6.8, len(groups) * .75 + 2.8)),
                                        sharey=True, squeeze=False)
            axes = axes[0]
            for axis, (metric, scale, title, xlabel) in zip(axes, panels):
                axis.axvline(0, color="#777777", linestyle="--", linewidth=1, zorder=1)
                for position, (family, strategy) in enumerate(groups):
                    selected = [row for row in rows if row["family"] == family and row["strategy"] == strategy
                                and row["values"][metric] is not None]
                    values = [row["values"][metric] * scale for row in selected]
                    total = sum(row["family"] == family and row["strategy"] == strategy for row in rows)
                    if len(selected) < total:
                        axis.text(.98, position + .29, f"{len(selected)}/{total} defined", color="#666666",
                                  ha="right", va="center", fontsize=7.5, transform=axis.get_yaxis_transform())
                    if values:
                        axis.scatter(values, [position + jitter(row) for row in selected],
                                     s=26, color=COLORS[strategy], alpha=.7, edgecolors="none", zorder=2)
                        axis.scatter([median(values)], [position], marker="D", s=38,
                                     color="#222222", edgecolors="white", linewidths=.7, zorder=3)
                    else:
                        axis.text(.5, position, "undefined", color="#777777", ha="center", va="center",
                                  transform=axis.get_yaxis_transform())
                axis.set_title(title, fontsize=11, pad=12)
                axis.set_xlabel(xlabel, fontsize=9, labelpad=8)
                axis.grid(axis="x", alpha=.18)
                axis.tick_params(axis="y", length=0)
                axis.spines[["top", "right", "left"]].set_visible(False)
                axis.set_ylim(len(groups) - .5, -.5)
                axis.margins(x=.12)
            axes[0].set_yticks(range(len(groups)), labels, fontsize=9)
            figure.suptitle("Cell-local versus common-window coordination", fontsize=16, y=.97)
            figure.text(.5, .915, "Paired differences on identical frozen inputs and policies; positive values mean larger local results.",
                        ha="center", fontsize=10)
            footer = ("Dots: seeded realizations paired between controllers; diamonds: medians, not confidence intervals. Mechanism fixtures excluded.\n"
                      "The same realization appears under both strategies and is not an additional independent sample.\n"
                      "Observation age is simulated and conditional on each controller's retained contributions; retained sets may differ.\n"
                      "Query coverage and MAE describe retrospective public-only reconstruction. No privacy claim or measured delivery latency.\n"
                      "Row labels give all realizations; panel annotations show defined pairs when fewer outcomes are available.")
            figure.text(.5, .035, footer, ha="center", va="bottom", fontsize=8.5, linespacing=1.5)
            figure.subplots_adjust(left=.19 if len(panels) == 3 else .16, right=.98, bottom=.23, top=.83, wspace=.27)
            output.parent.mkdir(parents=True, exist_ok=True)
            for destination in destinations:
                # Exclusive creation also protects against a file appearing after preflight.
                with destination.open("xb") as stream:
                    created.append(destination)
                    metadata = ({"Date": None, "Creator": "UMP coordination study"}
                                if destination.suffix == ".svg" else {"Software": "UMP coordination study"})
                    buffer = io.BytesIO()
                    figure.savefig(buffer, format=destination.suffix[1:], dpi=180, metadata=metadata)
                    payload = buffer.getvalue()
                    if destination.suffix == ".svg":
                        # Keep generated SVG source suitable for repository whitespace checks.
                        payload = b"\n".join(line.rstrip() for line in payload.splitlines()) + b"\n"
                    stream.write(payload)
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        finally:
            if figure is not None:
                plt.close(figure)
    return destinations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Completed study summary.json")
    parser.add_argument("--output", type=Path, required=True, help="New figure prefix; writes .png and .svg")
    args = parser.parse_args()
    try:
        outputs = export(json.loads(args.input.read_text(encoding="utf-8")), args.output)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print("Exported " + ", ".join(map(str, outputs)))


if __name__ == "__main__":
    main()
