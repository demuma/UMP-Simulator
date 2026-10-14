#!/usr/bin/env python3
"""Capture one actual headless simulator run into a private, verified replay file.

Only the maintained temporal-aggregation example is used. The script creates a
fresh UUID database, disables aggregation, compares GT-derived finest counts to
the raw AGBS output, and drops only its owned database after verified export.
It deliberately refuses to infer measured-empty GT frames from missing rows.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid


SCHEMA = "ump.observation-replay.v1"
SENSOR_ID = "temporal-aggregation-agbs"
GRID = {"x": 0, "y": 0, "width": 80, "height": 80, "leaf_depth": 6}
END_MS = 8000
PERIOD_MS = 100
STEP_MS = 50
DATABASE_PREFIX = "UMP_Capture_"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        file.write("\n")
    path.chmod(0o600)


def replace_once(text: str, old: str, new: str, expected: int = 1) -> str:
    if text.count(old) != expected:
        raise ValueError(f"Maintained example changed: expected {expected} occurrences of {old!r}")
    return text.replace(old, new)


def capture_config(template: str, database: str) -> str:
    # These assertions make a future example edit fail closed instead of silently
    # capturing another footprint, cadence, database or simulator configuration.
    if not re.fullmatch(r"UMP_Capture_[0-9a-f]{32}", database):
        raise ValueError("Capture database must have the owned UUID naming pattern")
    sensor_section = template.split("sensors:\n", 1)[-1].split("region_taxonomy:\n", 1)[0]
    if len(re.findall(r"^  - id:", sensor_section, re.MULTILINE)) != 1:
        raise ValueError("Capture requires exactly one sensor in the maintained example")
    for expected in (
        "  time_step: 0.05\n", "    frame_rate: 10.0\n", "      max_depth: 6\n",
        "      cell_size: 40\n", "  clear_database: false\n",
        "  width: 80\n", "  height: 80\n", "  num_agents: 200\n",
        "  - id: temporal-aggregation-agbs\n", "    type: adaptive-grid-based\n",
        "      x: 0.0\n", "      y: 0.0\n", "      width: 80.0\n", "      height: 80.0\n",
    ):
        if template.count(expected) != 1:
            raise ValueError(f"Maintained example no longer has the verified capture setting {expected!r}")
    text = replace_once(template, "  show_renderer: true\n", "  show_renderer: false\n")
    text = replace_once(text, "  duration_seconds: 30\n", "  duration_seconds: 8\n")
    text = replace_once(text, "UMP_Temporal_Demo_Raw", database, expected=2)
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line == "    aggregation:\n"]
    if len(starts) != 1:
        raise ValueError("Expected exactly one aggregation block in the maintained example")
    start = starts[0]
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end].startswith("      ")):
        end += 1
    lines[start:end] = ["    aggregation:\n", "      enabled: false\n", "\n"]
    text = "".join(lines)
    if "UMP_Temporal_Demo_" in text or "publication:" in text or "enabled: true" in text:
        raise ValueError("Capture configuration still refers to an active demo/publication destination")
    if text.count(database) != 2 or "  clear_database: false\n" not in text:
        raise ValueError("Capture database isolation failed")
    if len(re.findall(r"^\s+db_name:", text, re.MULTILINE)) != 2:
        raise ValueError("Capture configuration contains another raw database destination")
    return text


def mongo(shell: str, script: str, timeout: int = 60) -> object:
    completed = subprocess.run(
        [shell, "mongodb://localhost:27017/?serverSelectionTimeoutMS=5000", "--quiet", "--eval", script],
        check=False, text=True, capture_output=True, timeout=timeout,
    )
    if completed.returncode:
        raise RuntimeError(f"mongosh failed ({completed.returncode}): {completed.stderr.strip() or completed.stdout.strip()}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("mongosh did not return exactly one JSON value") from error


def utc_milliseconds(text: str) -> int:
    stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Exported timestamps must have an explicit timezone")
    value = stamp.astimezone(timezone.utc)
    delta = value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    if delta.microseconds % 1000:
        raise ValueError("Sub-millisecond timestamp in a millisecond replay")
    return delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000


def cell_for(x: float, y: float) -> tuple[int, float, float, float]:
    if not math.isfinite(x) or not math.isfinite(y) or not (0 <= x < 80 and 0 <= y < 80):
        raise ValueError("Position is outside the finite, half-open sensor area")
    cell_id = 3
    left = top = 0.0
    side = 80.0
    for _ in range(6):
        side /= 2
        east = x >= left + side
        south = y >= top + side
        quadrant = int(east) | (int(south) << 1)
        cell_id = (cell_id << 2) | quadrant
        if east:
            left += side
        if south:
            top += side
    return cell_id, left, top, side


def verify_and_replay(agents: list[dict], sensor: list[dict], run_id: str) -> tuple[dict, dict]:
    gt_meta = [row for row in agents if row.get("data_type") == "metadata"]
    sensor_meta = [row for row in sensor if row.get("data_type") == "metadata"]
    if len(gt_meta) != 1 or len(sensor_meta) != 1:
        raise ValueError("Exactly one GT and one AGBS metadata record are required")
    origin = utc_milliseconds(gt_meta[0]["timestamp"])
    metadata = sensor_meta[0]
    if (utc_milliseconds(metadata["timestamp"]) != origin or metadata["sensor_id"] != SENSOR_ID
            or metadata["max_depth"] != 6 or metadata["cell_size"] != 40 or metadata["frame_rate"] != 10
            or metadata["position"] != {"x": 0, "y": 0}
            or metadata["detection_area"] != {"width": 80, "height": 80}
            or gt_meta[0]["frame_rate"] != 20
            or gt_meta[0]["simulation_area"] != {"width": 80, "height": 80}):
        raise ValueError("Export metadata does not match the requested origin, geometry or cadence")
    by_time: dict[int, list[dict]] = defaultdict(list)
    for row in agents:
        if row.get("data_type") == "metadata":
            continue
        if row.get("data_type") != "agent data":
            raise ValueError("Unexpected GT document type")
        time = utc_milliseconds(row["timestamp"]) - origin
        if time < 0 or time >= END_MS or time % STEP_MS:
            raise ValueError(f"Unexpected GT timestamp {time}")
        by_time[time].append(row)
    if sorted(by_time) != list(range(0, END_MS, STEP_MS)):
        raise ValueError("GT frame coverage is incomplete; missing rows cannot prove measured-empty frames")
    expected: dict[tuple[int, int], dict] = {}
    batches = []
    sampled_outside = 0
    for time in range(0, END_MS, STEP_MS):
        rows = by_time[time]
        identities: set[str] = set()
        for row in rows:
            identity = row["agent_id"]
            if not isinstance(identity, str) or not identity or identity in identities or not row["type"]:
                raise ValueError("GT contains an empty or duplicate identity/type in one frame")
            identities.add(identity)
        if not time or time % PERIOD_MS:
            continue
        observations = []
        for row in rows:
            x, y = row["position"]["x"], row["position"]["y"]
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("Non-finite GT position")
            if not (0 <= x < 80 and 0 <= y < 80):
                sampled_outside += 1
                continue
            cell_id, left, top, side = cell_for(x, y)
            key = (time, cell_id)
            value = expected.setdefault(key, {"count": 0, "types": Counter(), "x": left, "y": top, "side": side})
            value["count"] += 1
            value["types"][row["type"]] += 1
            observations.append({"id": row["agent_id"], "type": row["type"], "cell_id": cell_id, "x": x, "y": y})
        observations.sort(key=lambda row: row["id"])
        batches.append({"sequence": time // PERIOD_MS, "observed_at_ms": time,
                        "status": "measured", "observations": observations})
    actual: dict[tuple[int, int], dict] = {}
    for row in sensor:
        if row.get("data_type") == "metadata":
            continue
        if row.get("data_type") != "adaptive grid data" or row["sensor_id"] != SENSOR_ID:
            raise ValueError("Unexpected AGBS document type or sensor")
        time = utc_milliseconds(row["timestamp"]) - origin
        key = (time, row["cell_id"])
        if time <= 0 or time >= END_MS or time % PERIOD_MS or key in actual:
            raise ValueError("Off-cadence or duplicate raw AGBS cell record")
        types: dict[str, int] = {}
        for item in row["agent_type_count"]:
            if item["type"] in types or not isinstance(item["count"], int) or item["count"] <= 0:
                raise ValueError("Invalid AGBS type-count breakdown")
            types[item["type"]] = item["count"]
        if not isinstance(row["total_agents"], int) or row["total_agents"] <= 0 or sum(types.values()) != row["total_agents"]:
            raise ValueError("Invalid AGBS total count")
        actual[key] = {"count": row["total_agents"], "types": types,
                       "x": row["cell_position"]["x"], "y": row["cell_position"]["y"], "side": row["cell_size"]}
    if set(actual) != set(expected):
        missing, extra = sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected))
        raise ValueError(f"GT/AGBS cell-time support mismatch: missing={missing[:8]}, extra={extra[:8]}")
    for key in sorted(expected):
        if actual[key] != expected[key]:
            raise ValueError(f"GT/AGBS count, type or geometry mismatch at {key}: {expected[key]} != {actual[key]}")
    proof = {
        "schema": "ump.capture-proof.v1", "status": "verified", "origin_utc": gt_meta[0]["timestamp"],
        "origin_epoch_ms": origin, "end_ms": END_MS, "gt_cadence_ms": STEP_MS,
        "sensor_cadence_ms": PERIOD_MS, "gt_frames": len(by_time), "sensor_frames": len(batches),
        "gt_records": len(agents) - 1, "agbs_records": len(actual),
        "sampled_observation_contributions": sum(len(batch["observations"]) for batch in batches),
        "sampled_gt_outside_sensor": sampled_outside,
        "measured_empty_frames": sum(not batch["observations"] for batch in batches),
        "checks": ["clean simulator exit", "complete GT cadence", "unique identity per GT timestamp",
                   "shared metadata origin", "sensor cadence", "unique AGBS cell per timestamp",
                   "exact GT-derived per-cell counts", "exact per-cell type counts", "canonical cell ID and geometry"],
        "per_frame": [{"observed_at_ms": batch["observed_at_ms"], "road_users": len(batch["observations"]),
                       "occupied_cells": sum(time == batch["observed_at_ms"] for time, _ in expected)} for batch in batches],
        "empty_frame_evidence": "Complete scheduled sensor execution plus full GT frame; raw AGBS does not persist empty cells.",
    }
    replay = {"schema": SCHEMA, "run_id": run_id, "sensor_id": SENSOR_ID, "coverage": GRID,
              "sampling_period_ms": PERIOD_MS, "end_ms": END_MS, "batches": batches}
    return replay, proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New private capture directory")
    parser.add_argument("--simulator", type=Path, help="Defaults to this repository's simulator/build/Simulator")
    parser.add_argument("--keep-database", action="store_true", help="Keep this capture's owned UUID database after verification")
    parser.add_argument("--timeout", type=int, default=120, help="Simulator wall-time limit in seconds")
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[2]
    template = repository / "simulator/examples/temporal-aggregation/config.yaml"
    executable = (args.simulator or repository / "simulator/build/Simulator").resolve()
    output = args.output.expanduser().resolve()
    if output.exists() or not executable.is_file() or not os.access(executable, os.X_OK) or args.timeout <= 0:
        parser.error("Require a new output directory, executable simulator and positive timeout")
    shell = shutil.which("mongosh")
    if not shell:
        parser.error("mongosh must be available on PATH")
    token = uuid.uuid4().hex
    database = DATABASE_PREFIX + token
    if not re.fullmatch(r"UMP_Capture_[0-9a-f]{32}", database):
        raise ValueError("Invalid owned database name")
    configuration = capture_config(template.read_text(encoding="utf-8"), database)
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    (output / "config.yaml").write_text(configuration, encoding="utf-8")
    (output / "config.yaml").chmod(0o600)
    shutil.copyfile(template, output / "source-example-config.yaml")
    (output / "source-example-config.yaml").chmod(0o600)
    ownership_created = False
    database_dropped = False
    started = datetime.now(timezone.utc).isoformat()
    try:
        owned = mongo(shell, f"""
const name = {json.dumps(database)};
const token = {json.dumps(token)};
if (db.getSiblingDB('admin').runCommand({{listDatabases:1,nameOnly:true}}).databases.some(x => x.name === name))
  throw new Error('Fresh capture database already exists');
const capture = db.getSiblingDB(name);
capture.getCollection('_capture_owner').insertOne({{token, created_at:new Date(), purpose:'verified-offline-replay'}});
print(JSON.stringify({{database:name,token}}));
""")
        if owned != {"database": database, "token": token}:
            raise RuntimeError("Database ownership confirmation failed")
        ownership_created = True
        with (output / "simulator.stdout.log").open("x", encoding="utf-8") as stdout, (output / "simulator.stderr.log").open("x", encoding="utf-8") as stderr:
            completed = subprocess.run([str(executable)], cwd=output, stdout=stdout, stderr=stderr,
                                       text=True, timeout=args.timeout, check=False)
        if completed.returncode:
            raise RuntimeError(f"Simulator returned {completed.returncode}; database retained")
        logs = "\n".join((output / name).read_text(encoding="utf-8", errors="replace")
                         for name in ("simulator.stdout.log", "simulator.stderr.log"))
        if re.search(r"\b(error|failed|exception|fatal)\b", logs, flags=re.IGNORECASE):
            raise RuntimeError("Simulator logs report a possible error; database retained for inspection")
        collections = mongo(shell, f"print(JSON.stringify(db.getSiblingDB({json.dumps(database)}).getCollectionNames().sort()));")
        if collections != sorted(["_capture_owner", "Agents", "AGB_Sensor_Data_V3"]):
            raise RuntimeError(f"Unexpected capture collections: {collections}")
        exports = {}
        for collection, name in (("Agents", "raw-agents.json"), ("AGB_Sensor_Data_V3", "raw-agbs.json")):
            rows = mongo(shell, f"print(JSON.stringify(db.getSiblingDB({json.dumps(database)}).getCollection({json.dumps(collection)}).find().sort({{timestamp:1,_id:1}}).toArray()));")
            if not isinstance(rows, list):
                raise RuntimeError("Collection export was not an array")
            write_json(output / name, rows)
            exports[collection] = rows
        replay, proof = verify_and_replay(exports["Agents"], exports["AGB_Sensor_Data_V3"], "simulator-capture-" + token)
        configured_time = re.findall(r"^  datetime: '([^']+)'$", configuration, re.MULTILINE)
        proof["configured_datetime"] = configured_time[0] if len(configured_time) == 1 else None
        proof["timestamp_origin_note"] = (
            "The configured datetime has no explicit timezone. Mongo metadata is authoritative for this "
            "capture's relative timestamps; absolute timezone/DST interpretation requires a separate audit."
        )
        write_json(output / "observations.json", replay)
        write_json(output / "capture-proof.json", proof)
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, text=True, capture_output=True, check=True).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repository, text=True, capture_output=True, check=True).stdout
        manifest = {
            "schema": "ump.capture-manifest.v1", "classification": "private_identity_bearing_research_input",
            "status": "verified", "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(),
            "database": database, "database_owner_token": token, "database_dropped": False,
            "source_example": str(template), "simulator": str(executable), "simulator_sha256": digest(executable),
            "capture_script_sha256": digest(Path(__file__).resolve()),
            "git_revision": revision, "git_worktree_status": status,
            "source_code_sha256": {str(path.relative_to(repository)): digest(path)
                                   for path in sorted((repository / "simulator/src").glob("*.cpp"))},
            "artifacts_sha256": {path.name: digest(path) for path in sorted(output.iterdir()) if path.is_file()},
            "origin_utc": proof["origin_utc"], "end_ms": END_MS,
            "sampling_period_ms": PERIOD_MS, "simulation_step_ms": STEP_MS,
            "limitations": ["One stochastic simulator realization; rerunning does not reproduce positions.",
                            "Frozen observations.json is the common replay input for subsequent comparisons.",
                            "GT positions provide privileged identities; the AGBS count export itself has no identities.",
                            "The simulator binary hash records the executed artifact; source hashes do not prove a clean rebuild."],
        }
        if not args.keep_database:
            dropped = mongo(shell, f"""
const name = {json.dumps(database)};
const token = {json.dumps(token)};
if (!/^UMP_Capture_[0-9a-f]{{32}}$/.test(name)) throw new Error('Unsafe database name');
const capture = db.getSiblingDB(name);
const owners = capture.getCollection('_capture_owner').find().toArray();
if (owners.length !== 1 || owners[0].token !== token) throw new Error('Database ownership mismatch');
const result = capture.dropDatabase();
if (result.ok !== 1) throw new Error('Capture database cleanup failed');
print(JSON.stringify({{dropped:name}}));
""")
            if dropped != {"dropped": database}:
                raise RuntimeError("Unexpected database cleanup response")
            database_dropped = True
        manifest["database_dropped"] = database_dropped
        write_json(output / "capture-manifest.json", manifest)
        for path in output.iterdir():
            if path.is_file():
                path.chmod(0o600)
        print(json.dumps({"status": "verified", "output": str(output), "database": database,
                          "database_dropped": database_dropped,
                          "gt_frames": proof["gt_frames"], "sensor_frames": proof["sensor_frames"],
                          "agbs_cell_records": proof["agbs_records"],
                          "observation_contributions": proof["sampled_observation_contributions"]}, indent=2))
        return 0
    except Exception as error:
        failure = {"status": "failed", "error": str(error), "database": database,
                   "database_created": ownership_created, "database_dropped": database_dropped,
                   "instruction": "Inspect the retained capture artifacts/database; this script does not delete unverified evidence."}
        write_json(output / "capture-failure.json", failure)
        print(json.dumps(failure, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
