#!/usr/bin/env python3
"""Bounded E07/A08 candidate-choice study; no production controller mutation.

The same-interval reference and the fixed full-run receiver query bank are
different measurements. Neither supplies a global online optimum or attack risk.
Every output directory is new and private; MongoDB and the live simulator are unused.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from oracle import validate_result
from semantic_queries import evaluate_queries
from semantic_tradeoffs import reference_candidates, score_candidate, pareto_candidates

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = (2, 4, 5)
LOSSES = (0, .5, 1)
SIDES = (20, 40)
DURATIONS = (400, 800)
MODES = ("temporal_first", "spatial_first")
SCENARIOS = ("dense_exact", "rare_local", "temporal_turnover", "infeasible_support", "regional_detail")
SEMANTIC_METRICS = {"min_category_distinct_contributors", "semantic_max_loss", "semantic_mean_loss", "semantic_suppression_fraction"}
CELL_XY = {48: (1, 1), 49: (21, 1), 50: (1, 21), 51: (21, 21)}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def taxonomy():
    return {"id": "semantic-priority", "version": "1", "nodes": [
        {"id": "road_user", "loss": 1},
        {"id": "pedestrian", "parent": "road_user", "loss": 0, "input_types": ["pedestrian"]},
        {"id": "cyclist", "parent": "road_user", "loss": .5},
        {"id": "adult_cyclist", "parent": "cyclist", "loss": 0, "input_types": ["adult_cyclist"]},
        {"id": "child_cyclist", "parent": "cyclist", "loss": 0, "input_types": ["child_cyclist"]}]}


def observations(scenario, time):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown predeclared scenario")
    rows = []
    for cell, (x, y) in CELL_XY.items():
        if scenario == "dense_exact":
            counts = {"pedestrian": 5, "adult_cyclist": 5, "child_cyclist": 5}
        elif scenario in ("rare_local", "regional_detail"):
            counts = ({"pedestrian": 19, "adult_cyclist": 1} if cell == 48
                      else {"adult_cyclist": 5} if cell == 49 else {"pedestrian": 5})
        elif scenario == "temporal_turnover":
            counts = {"pedestrian": 19, "adult_cyclist": 1}
        else:
            counts = {"pedestrian": 1}
        for kind, count in counts.items():
            for index in range(count):
                identity = f"{cell}/{kind}/{index}"
                if scenario == "temporal_turnover" and kind == "adult_cyclist":
                    identity += f"/t{time}"
                rows.append({"id": identity, "type": kind, "cell_id": cell, "x": x, "y": y})
    return rows


def fixture(scenario):
    return {"schema": "ump.observation-replay.v1", "run_id": "semantic-priority-" + scenario,
            "sensor_id": "agbs", "coverage": {"x": 0, "y": 0, "width": 80, "height": 80, "leaf_depth": 2},
            "sampling_period_ms": 100, "end_ms": 2400, "batches": [
                {"sequence": time // 100, "observed_at_ms": time, "status": "measured",
                 "observations": observations(scenario, time)} for time in range(100, 2400, 100)]}


def policy(scenario, support, loss, side, duration, mode):
    if (scenario not in SCENARIOS or support not in SUPPORT or loss not in LOSSES
            or side not in SIDES or duration not in DURATIONS or mode not in MODES):
        raise ValueError("Parameters outside the predeclared study")
    regions = ([{"id": "strict-detail", "type": "crossing", "x": 0, "y": 0, "width": 20, "height": 20,
                 "requirements": {"semantic_max_loss": {"max": 0}}}]
               if scenario == "regional_detail" else [])
    return {"application_id": "semantic-priority", "window_ms": 400,
            "max_observations_per_window": 1000000,
            "history": {"retention_ms": 2000, "max_bins": 32, "max_observations": 100000,
                        "max_identity_bytes": 16000000, "max_buckets": 128},
            "spatial_selection": {"min_depth": 1, "max_evaluations": 4096, "preserve_valid_descendants": True},
            "temporal_adaptation": {"extension_step_ms": 100, "max_window_ms": duration,
                                    "max_evaluations": 16, "coordination": "common_window"},
            "semantic_taxonomy": taxonomy(),
            "policy_tree": {"id": "semantic-priority-policy",
                            "version": f"{scenario}/k{support}/l{loss:g}/s{side}/t{duration}/{mode}",
                            "max_nodes": 65536,
                            "execution": {"publication_model": "private_final_snapshot", "strategy": mode,
                                          "release_trigger": "priority_satisfied"},
                            "root": {"distinct_contributors": {"min": 1},
                                     "cell_side_m": {"min": 1.25, "max": side},
                                     "window_duration_ms": {"max": duration},
                                     "age_at_evaluation_ms": {"max": duration},
                                     "min_category_distinct_contributors": {"min": support},
                                     "semantic_max_loss": {"max": loss}},
                            "regions": [row["id"] for row in regions]},
            "policy_regions": regions}


def scalar_projection(config, actual):
    """Only the established scalar oracle is used here, not a semantic pass flag."""
    config, actual = deepcopy(config), deepcopy(actual)
    config.pop("semantic_taxonomy", None)
    requirements = [config["policy_tree"]["root"]]
    for region in config.get("policy_regions", []):
        requirements.extend([region.get("type_requirements", {}), region.get("requirements", {})])
    for bounds in requirements:
        for name in SEMANTIC_METRICS:
            bounds.pop(name, None)
    for window in actual["windows"]:
        for cell in window["cells"]:
            cell.pop("semantic", None)
            cell.pop("assessment_status", None)
            for name in SEMANTIC_METRICS:
                cell.get("metrics", {}).pop(name, None)
            cell["checks"] = [check for check in cell.get("checks", []) if check.get("metric") not in SEMANTIC_METRICS]
    for release in actual["releases"]:
        for cell in release["cells"]:
            cell.pop("semantic", None)
    return config, actual


def scientific(result):
    return {key: value for key, value in result.items() if key != "runtime"}


def signature(cells):
    """Counts, geometry and summaries all come from the independently rebuilt cut."""
    fields = ("cell_id", "depth", "x", "y", "width", "height", "observation_contributions")
    rows = []
    for cell in cells:
        semantic = cell["semantic"]
        rows.append([*[float(cell[key]) for key in fields],
                     cell.get("distinct_road_users", cell.get("distinct_contributors")),
                     float(semantic["min_category_distinct_contributors"]), round(float(semantic["semantic_max_loss"]), 12),
                     round(float(semantic["semantic_mean_loss"]), 12), semantic["taxonomy_id"], semantic["taxonomy_version"],
                     sorted((row["category_id"], row["observation_contributions"], row["distinct_contributors"])
                            for row in semantic["categories"])])
    return json.dumps(sorted(rows, key=lambda row: row[0]), sort_keys=True, allow_nan=False)


def compact(candidate):
    return {key: value for key, value in candidate.items() if key not in ("query20", "query40")}


def audit_choices(replay, config, result):
    audits = []
    for window in result["windows"]:
        start, end, now = [window[key] for key in ("start_ms", "end_ms", "evaluated_at_ms")]
        releases = [r for r in result["releases"] if r["start_ms"] == start and r["end_ms"] == end]
        if len(releases) > 1:
            raise ValueError("Duplicate common-window release")
        actual_cells = releases[0]["cells"] if releases else []
        if bool(window["selected_cells"]) != bool(actual_cells):
            raise ValueError("Selected output and immutable recipient release disagree")
        reference = reference_candidates(replay, config, start, end, now)
        matching = [c for c in reference["candidates"] if signature(c["cells"]) == signature(actual_cells)]
        if not matching:
            raise ValueError(f"Actual cut not in legal same-interval reference: {start}..{end}")
        actual = score_candidate(actual_cells, config, start, end, reference["source_contributions"])
        nondominated = pareto_candidates(reference["candidates"])
        # This only means nondominated for the declared metrics at this SAME interval.
        actual_is_nondominated = any(signature(c["cells"]) == signature(actual_cells) for c in nondominated)
        nonempty = any(c["retained_contributions"] > 0 for c in reference["candidates"])
        audits.append({"interval": reference["interval"], "candidate_class": reference["candidate_class"],
                       "candidate_count": len(reference["candidates"]), "nonempty_feasible": nonempty,
                       "source_contributions": reference["source_contributions"],
                       "actual": compact(actual), "actual_is_nondominated": actual_is_nondominated,
                       "nondominated": [compact(c) for c in nondominated],
                       "binding_failures": reference["binding_failures"]})
    return audits


def run_core(binary, input_path, config_path, output_path, mode):
    command = [str(binary), "--input", str(input_path), "--config", str(config_path),
               "--mode", mode, "--output", str(output_path)]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    return json.loads(output_path.read_text()), command


def summarize(result):
    cells = [(release, cell) for release in result["releases"] for cell in release["cells"]]
    retained = sum(cell["observation_contributions"] for _, cell in cells)
    age_sum = 0
    # This is conservative interval-start age, not mean age of individual samples.
    # It is logical simulation time, not measured processing/network latency.
    for release, cell in cells:
        age_sum += cell["observation_contributions"] * (release["sealed_at_ms"] - release["start_ms"])
    return {"source_contributions": result["input_observation_contributions"],
            "retained_contributions": retained,
            "retained_fraction": retained / result["input_observation_contributions"],
            "released_cells": len(cells), "released_windows": len(result["releases"]),
            "mean_interval_start_age_ms": age_sum / retained if retained else None,
            "mean_semantic_loss": sum(c["observation_contributions"] * c["semantic"]["semantic_mean_loss"]
                                      for _, c in cells) / retained if retained else None,
            "max_semantic_loss": max((c["semantic"]["semantic_max_loss"] for _, c in cells), default=None),
            "contribution_weighted_cell_side_m": sum(c["observation_contributions"] * c["width"]
                                                     for _, c in cells) / retained if retained else None,
            "first_window": {key: result["windows"][0][key] for key in
                             ("start_ms", "end_ms", "completion_reason", "temporal_extensions")}}


def run_study(binary, output, *, scenarios=SCENARIOS, limit=None):
    if not binary.is_file():
        raise ValueError("Build AggregationReplay first")
    if any(s not in SCENARIOS for s in scenarios) or len(set(scenarios)) != len(scenarios) or not scenarios:
        raise ValueError("Select distinct predeclared scenarios")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError("limit must be a positive integer")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    frozen = output / "AggregationReplay"
    shutil.copy2(binary, frozen)
    inputs = output / "inputs"; inputs.mkdir()
    cases = []
    plan = list(itertools.product(scenarios, SUPPORT, LOSSES, SIDES, DURATIONS, MODES))
    if limit is not None:
        plan = plan[:limit]
    protocol = ROOT / "docs/SEMANTIC_PRIORITY_PROTOCOL_2026-10-21.md"
    manifest = {"schema": "ump.semantic-priority-study.v1", "classification": "private_research",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "scope": "Bounded controlled mechanism fixtures; no empirical privacy-gain claim",
                "planned_executions": len(plan), "matrix_complete": limit is None and tuple(scenarios) == SCENARIOS,
                "binary_original": str(binary), "binary_sha256": digest(frozen),
                "protocol_sha256": digest(protocol), "python": platform.python_version(),
                "platform": platform.platform(), "source_hashes": {}}
    for name in ("run_semantic_priority_study.py", "semantic_tradeoffs.py", "semantic_queries.py", "oracle.py"):
        path = Path(__file__).with_name(name)
        manifest["source_hashes"][name] = digest(path)
    snapshot = output / "source"; snapshot.mkdir()
    for name in manifest["source_hashes"]:
        shutil.copy2(Path(__file__).with_name(name), snapshot / name)
    shutil.copy2(protocol, snapshot / protocol.name)
    manifest["source_snapshot"] = "source"
    write_json(output / "manifest.json", manifest)
    sources = {scenario: fixture(scenario) for scenario in scenarios}
    for scenario, replay in sources.items():
        write_json(inputs / (scenario + ".json"), replay)
    repeats = []
    for index, (scenario, support, loss, side, duration, mode) in enumerate(plan):
        name = f"{index:03d}-{scenario}-k{support}-l{loss:g}-s{side}-t{duration}-{mode}"
        directory = output / name; directory.mkdir()
        replay = sources[scenario]
        config = policy(scenario, support, loss, side, duration, mode)
        policy_path = directory / "policy.json"; write_json(policy_path, config)
        input_path = inputs / (scenario + ".json")
        result, command = run_core(frozen, input_path, policy_path, directory / "result.json", mode)
        scalar_config, scalar_result = scalar_projection(config, result)
        audit = validate_result(replay, scalar_config, scalar_result)
        if not audit["valid"]:
            raise ValueError(f"Scalar audit failed {name}: {audit['violations'][:3]}")
        choices = audit_choices(replay, config, result)
        write_json(directory / "scalar-audit.json", audit)
        write_json(directory / "choice-audit.json", choices)
        queries = {str(window): evaluate_queries(replay, config, result["releases"], window_ms=window)
                   for window in (400, 800)}
        write_json(directory / "queries.json", queries)
        bindings = Counter(check["metric"] + ":" + check["reason"]
                           for window in result["windows"] for cell in window["cells"]
                           for check in cell.get("checks", []) if check["status"] != "pass")
        case = {"id": name, "scenario": scenario, "support_min": support, "semantic_loss_max": loss,
                "cell_side_max_m": side, "duration_max_ms": duration, "mode": mode,
                "input_sha256": digest(input_path), "policy_sha256": digest(policy_path),
                "scientific_sha256": hashlib.sha256(json.dumps(scientific(result), sort_keys=True).encode()).hexdigest(),
                "command": command, "summary": summarize(result), "scalar_valid": True,
                "conditional_intervals": len(choices),
                "conditional_infeasible_intervals": sum(not a["nonempty_feasible"] for a in choices),
                "conditional_dominated_actual_intervals": sum(not a["actual_is_nondominated"] for a in choices),
                "binding_checks_final_diagnostics": dict(bindings)}
        # Fixed query summaries retain their cohorts, categories and exact denominators.
        case["query_summaries"] = {window: {scale: {lag: projection["summary"]
            for lag, projection in value["by_lag_ms"].items()}
            for scale, value in evaluation["by_scale"].items()} for window, evaluation in queries.items()}
        cases.append(case)
        write_json(directory / "case.json", case)
        if index % 30 == 0:
            again, _ = run_core(frozen, input_path, policy_path, directory / "repeat.json", mode)
            if scientific(again) != scientific(result):
                raise ValueError("Scientific output changed in deterministic repeat")
            repeats.append({"case": name, "identical_except_runtime": True})
        if (index + 1) % 36 == 0 or index + 1 == len(plan):
            print(f"Verified {index + 1}/{len(plan)} semantic priority cases", flush=True)
    summary = {"schema": "ump.semantic-priority-study-summary.v1", "executions": len(cases),
               "repeats": repeats, "scalar_audits_valid": all(c["scalar_valid"] for c in cases),
               "conditional_intervals_audited": sum(c["conditional_intervals"] for c in cases),
               "conditional_infeasible_intervals": sum(c["conditional_infeasible_intervals"] for c in cases),
               "conditional_dominated_actual_intervals": sum(c["conditional_dominated_actual_intervals"] for c in cases),
               "cases": cases}
    write_json(output / "summary.json", summary)
    manifest.update(completed_executions=len(cases), deterministic_repeats=len(repeats),
                    completed_at_utc=datetime.now(timezone.utc).isoformat())
    write_json(output / "manifest.json", manifest)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "simulator/build/AggregationReplay")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", action="append", choices=SCENARIOS)
    parser.add_argument("--limit", type=int, help="Smoke subset, explicitly marked incomplete")
    args = parser.parse_args()
    result = run_study(args.binary.resolve(), args.output.resolve(),
                       scenarios=tuple(args.scenario) if args.scenario else SCENARIOS, limit=args.limit)
    print(f"Complete: {result['executions']} cases, {result['conditional_intervals_audited']} same-interval audits, "
          f"{len(result['repeats'])} exact repeats: {args.output}")


if __name__ == "__main__":
    main()
