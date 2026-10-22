#!/usr/bin/env python3
"""Curate small result summaries, policies and hashes; never include trajectories."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import tempfile


def build(repository: Path, output: Path, helper: Path) -> dict:
    spec = importlib.util.spec_from_file_location("replay_data", helper)
    data = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(data)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Archive output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    groups = {}
    temporary = tempfile.TemporaryDirectory()
    scratch = Path(temporary.name).resolve()

    def add(group, destination, source):
        groups.setdefault(group, []).append((destination, source))

    def derived(group, destination, payload):
        source = scratch / destination
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        add(group, destination, source)

    def compact_audit(path):
        audit = json.loads(path.read_text())
        scalar = audit.get("scalar", {})
        semantic = audit.get("semantic", {})
        windows = scalar.get("checked_windows", [])
        return {"scalar_valid": scalar.get("valid"), "scalar_violation_count": len(scalar.get("violations", [])),
                "checked_window_count": len(windows), "released_cell_count": scalar.get("released_cell_count"),
                "input_observation_contributions": scalar.get("input_observation_contributions"),
                "released_observation_contributions": scalar.get("released_observation_contributions"),
                "semantic_status": semantic.get("status", audit.get("status")),
                "semantic_published_bins": semantic.get("published_bins", audit.get("semantic_published_bins")),
                "semantic_published_cells": semantic.get("published_cells", audit.get("semantic_published_cells")),
                "regional_recomputation_count": len(audit.get("regional_recomputations", [])),
                "source_audit_sha256": data.sha256(path)}

    def source_hashes(root, variants, observation):
        hashes = {"source_directory": str(root.relative_to(repository)),
                  "observation_input_sha256": data.sha256(observation),
                  "result_sha256": {name: data.sha256(path) for name, path in variants.items()}}
        for name in ("manifest.json", "study-manifest.json", "pre-execution-manifest.json", "summary.json"):
            if (root / name).is_file():
                hashes[name.replace(".json", "_sha256")] = data.sha256(root / name)
        return hashes

    contexts = []
    for study, prefix, variants in (
        ("moving-replay-2026-10-21", "pilot", [(f"n{n}/comparison", n) for n in (200, 500, 1000)]),
        ("cell-size-caps-2026-10-21", "cell-caps", [(f"cap{cap}/n{n}/comparison", n) for cap in (10, 5) for n in (200, 500, 1000)]),
        ("window-duration-2026-10-21", "four-second", [(f"window4000/cap{cap}/n{n}/comparison", n) for cap in (10, 5) for n in (200, 500, 1000)]),
    ):
        for context, population in variants:
            root = repository / "results" / study / context
            destination = "moving/" + prefix + "/" + context
            for name in ("summary.json", "summary.csv", "policy.json", "protocol.md"):
                if (root / name).is_file():
                    add("moving", destination + "/" + name, root / name)
            methods = {p.parent.name: p for p in sorted(root.glob("*/result.json"))}
            derived("moving", destination + "/audit-totals.json",
                    {name: compact_audit(path.parent / "audit.json") for name, path in methods.items()})
            derived("moving", destination + "/provenance-hashes.json",
                    source_hashes(root, methods, repository / f"results/moving-replay-2026-10-21/n{population}/capture/observations.json"))
            contexts.append({"context": destination, "summarized_results": len(methods)})

    semantic = repository / "results/semantic-release-2026-10-21"
    methods = {p.parent.name: p for p in sorted(semantic.glob("*/result.json"))}
    for name in ("summary.json", "protocol.md"):
        add("semantic", "semantic/" + name, semantic / name)
    for name, path in methods.items():
        add("semantic", "semantic/policies/" + name + ".json", path.parent / "policy.json")
    derived("semantic", "semantic/audit-totals.json", {name: compact_audit(path.parent / "audit.json") for name, path in methods.items()})
    derived("semantic", "semantic/provenance-hashes.json", source_hashes(semantic, methods, semantic / "observations.json"))

    local = repository / "results/local-leaf-policy-2026-10-22"
    names = ("uniform_temporal", "local_temporal", "uniform_spatial", "local_spatial")
    methods = {name: local / (name + ".json") for name in names}
    summary = json.loads((local / "summary.json").read_text())
    for record in summary.values():
        if isinstance(record, dict):
            intervals = record.pop("release_intervals_ms", [])
            durations = {}
            for start, end in intervals:
                durations[str(end - start)] = durations.get(str(end - start), 0) + 1
            record["release_duration_histogram_ms"] = durations
    derived("local", "local/summary.json", summary)
    for name in names:
        add("local", "local/policies/" + name + ".json", local / (name + "-policy.json"))
    add("local", "local/protocol.md", local / "provenance/LOCAL_LEAF_POLICY_PROTOCOL_2026-10-22.md")
    derived("local", "local/audit-totals.json", {name: compact_audit(local / (name + "-audit.json")) for name in names})
    derived("local", "local/provenance-hashes.json", source_hashes(local, methods, local / "observations.json"))

    archives, files = [], []
    for group, members in sorted(groups.items()):
        archive, inventory = data.write_archive(output / ("results-" + group + ".tar.gz"), members)
        archives.append(archive)
        files.extend(inventory)
    manifest = {"schema": data.SCHEMA, "classification": "aggregate_results_only",
                "data_origin": "Aggregate results from synthetic simulator and scripted mechanism studies; no movement records included",
                "archives": archives, "files": sorted(files, key=lambda row: row["path"]), "copies": [], "bundles": [],
                "counts": {"moving_comparison_contexts": 15, "moving_results_summarized": 153,
                           "semantic_release_results_summarized": 8, "local_policy_results_summarized": 4},
                "contexts": contexts,
                "excluded": ["All observation/movement datasets", "Raw GT/AGBS and capture exports", "Full replay/result streams",
                             "Individual IDs, positions and trajectories", "Per-query records", "Repeat output streams",
                             "Compiled binaries", "External papers and extracted/rendered paper content"],
                "interpretation": "Tables and audit totals do not establish formal privacy, motion realism or an adaptive advantage. Replay requires separate local ignored inputs."}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.cleanup()
    return data.verify(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--helper", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.repository, args.output, args.helper or args.repository / "tools/evaluation/replay_data.py"), indent=2))
