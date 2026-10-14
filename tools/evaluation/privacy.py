"""Deterministic neighbour distinguishability for explicit recipient transcripts.

This is a complete-background stress test, not a trained membership attack.
See docs/PRIVACY_EVALUATION.md for its protected unit, assumptions and limitations.
Only standard-library dependencies are used.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any


_REPLAY_SCHEMA = "ump.observation-replay.v1"
_RESULT_SCHEMA = "ump.replay-result.v1"
_RELEASE_KEYS = frozenset({
    "release_id", "start_ms", "end_ms", "sealed_at_ms", "model", "policy_id",
    "policy_version", "cells",
})
_CELL_KEYS = frozenset({
    "cell_id", "depth", "x", "y", "width", "height", "observation_contributions",
    "distinct_road_users", "mean_sample_occupancy", "effective_policy_id",
})


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be an object")
    return value


def _integer(value: Any, where: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{where} must be an integer >= {minimum}")
    return value


def _number(value: Any, where: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{where} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{where} must be >= {minimum}")
    return value


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where} must be a nonempty string")
    return value


def _keys(value: dict[str, Any], expected: frozenset[str], where: str) -> None:
    missing, extra = expected - value.keys(), value.keys() - expected
    if missing or extra:
        raise ValueError(f"{where} has missing fields {sorted(missing)} or unknown fields {sorted(extra)}")


def neighbouring_replay(replay: dict[str, Any], target_id: str) -> dict[str, Any]:
    """Remove one target's whole recorded trace without changing any batch metadata.

    The returned input is independent of the original object. In particular, measured
    batches that become empty are preserved. An absent target is an error, preventing
    a mislabeled membership comparison. The C++ replay reader remains responsible for
    complete geometry, schedule and coverage validation before either run.
    """
    source = _object(replay, "replay")
    if source.get("schema") != _REPLAY_SCHEMA:
        raise ValueError(f"Expected replay schema {_REPLAY_SCHEMA}")
    _string(target_id, "target_id")
    if not isinstance(source.get("batches"), list):
        raise ValueError("replay.batches must be an array")
    result = deepcopy(source)
    removed = 0
    for index, batch in enumerate(result["batches"]):
        batch = _object(batch, f"batches[{index}]")
        if batch.get("status") not in ("measured", "unavailable"):
            raise ValueError(f"batches[{index}] has an unsupported status")
        _integer(batch.get("sequence"), f"batches[{index}].sequence")
        _integer(batch.get("observed_at_ms"), f"batches[{index}].observed_at_ms")
        observations = batch.get("observations")
        if not isinstance(observations, list):
            raise ValueError(f"batches[{index}].observations must be an array")
        kept = []
        for observation in observations:
            _object(observation, "observation")
            identity = _string(observation.get("id"), "observation.id")
            if identity == target_id:
                removed += 1
            else:
                kept.append(observation)
        batch["observations"] = kept
    if removed == 0:
        raise ValueError(f"Target {target_id!r} has no observations in this replay")
    return result


def canonical_transcript(result: dict[str, Any]) -> tuple:
    """Return a validated immutable representation of recipient-visible releases.

    Release IDs contain run-specific namespaces and are normalized away. Cell order
    is canonicalized by ID. Release sequence, logical timing, geometry, every public
    scalar count, and policy/model identifiers remain. Private result fields are never
    used as recipient information. Unknown release/cell fields fail explicitly.
    """
    _object(result, "result")
    if result.get("schema") != _RESULT_SCHEMA:
        raise ValueError(f"Expected result schema {_RESULT_SCHEMA}")
    if not isinstance(result.get("releases"), list):
        raise ValueError("result.releases must be an array")
    transcript = []
    previous_end = 0
    for index, release in enumerate(result["releases"]):
        where = f"releases[{index}]"
        release = _object(release, where)
        _keys(release, _RELEASE_KEYS, where)
        _string(release["release_id"], f"{where}.release_id")
        start = _integer(release["start_ms"], f"{where}.start_ms")
        end = _integer(release["end_ms"], f"{where}.end_ms")
        sealed = _integer(release["sealed_at_ms"], f"{where}.sealed_at_ms")
        if start < previous_end or end <= start or sealed < end:
            raise ValueError(f"{where} has overlapping, unordered or invalid interval times")
        previous_end = end
        model = _string(release["model"], f"{where}.model")
        policy_id = _string(release["policy_id"], f"{where}.policy_id")
        policy_version = _string(release["policy_version"], f"{where}.policy_version")
        if not isinstance(release["cells"], list) or not release["cells"]:
            raise ValueError(f"{where}.cells must be nonempty; empty retirements are private")
        cells = []
        seen_ids = set()
        for cell in release["cells"]:
            cell = _object(cell, f"{where}.cell")
            _keys(cell, _CELL_KEYS, f"{where}.cell")
            cell_id = _integer(cell["cell_id"], "cell.cell_id", 1)
            depth = _integer(cell["depth"], "cell.depth", 1)
            if depth > 14 or cell_id >> (2 * depth) != 3 or cell_id in seen_ids:
                raise ValueError("A public cell has an invalid or duplicate quadtree ID")
            seen_ids.add(cell_id)
            x, y = (_number(cell[key], f"cell.{key}") for key in ("x", "y"))
            width, height = (_number(cell[key], f"cell.{key}", 0) for key in ("width", "height"))
            if width == 0 or height == 0:
                raise ValueError("A public cell must have positive width and height")
            contributions = _integer(cell["observation_contributions"], "cell.observation_contributions")
            distinct = _integer(cell["distinct_road_users"], "cell.distinct_road_users")
            if distinct > contributions:
                raise ValueError("Distinct road users cannot exceed observation contributions")
            mean = cell["mean_sample_occupancy"]
            if mean is not None:
                _number(mean, "cell.mean_sample_occupancy", 0)
            effective_policy = _string(cell["effective_policy_id"], "cell.effective_policy_id")
            cells.append((cell_id, depth, x, y, width, height, contributions, distinct, mean, effective_policy))
        cells.sort(key=lambda cell: cell[0])
        transcript.append((start, end, sealed, model, policy_id, policy_version, tuple(cells)))
    return tuple(transcript)


def _context(result: dict[str, Any]) -> dict[str, Any]:
    """Collect fixed experimental settings, never data-dependent private diagnostics."""
    source = _object(result.get("source"), "result.source")
    required_source = ("sensor_id", "application_id", "coverage", "sampling_period_ms", "end_ms")
    if any(key not in source for key in required_source):
        raise ValueError("Result source lacks fixed replay metadata")
    mode = _string(result.get("mode"), "result.mode")
    configuration = _string(result.get("configuration_yaml"), "result.configuration_yaml")
    parameters = _object(result.get("parameters"), "result.parameters")
    return {"source": {key: source[key] for key in required_source}, "mode": mode,
            "configuration_yaml": configuration, "parameters": parameters}


def compare_pair(present_result: dict[str, Any], absent_result: dict[str, Any]) -> dict[str, Any]:
    """Compare an explicitly paired run with unchanged settings and one removed target.

    Callers must construct the absent input with ``neighbouring_replay``; output-only
    validation cannot prove that all background observations were held fixed.
    ``counts_changed`` and ``geometry_or_time_changed`` are projections, not causal
    attributions. Policy metadata is separately compared and also included in the full
    transcript. Success probability is derived for complete-background knowledge and a
    balanced hidden bit; it is not fitted or empirically measured attack accuracy.
    """
    present = canonical_transcript(present_result)
    absent = canonical_transcript(absent_result)
    if _context(present_result) != _context(absent_result):
        raise ValueError("Neighbouring runs must have identical mode, configuration, parameters and fixed source metadata")
    def counts(transcript: tuple) -> tuple:
        return tuple(tuple(cell[6:9] for cell in release[6]) for release in transcript)
    def geometry_time(transcript: tuple) -> tuple:
        return tuple((release[:3], tuple(cell[:6] for cell in release[6])) for release in transcript)
    def policies(transcript: tuple) -> tuple:
        return tuple((release[3:6], tuple(cell[9] for cell in release[6])) for release in transcript)
    changed = present != absent
    return {
        "schema": "ump.neighbour-comparison.v1",
        "threat_model": "deterministic_complete_background_membership",
        "public_transcript_changed": changed,
        "counts_changed": counts(present) != counts(absent),
        "geometry_or_time_changed": geometry_time(present) != geometry_time(absent),
        "public_policy_metadata_changed": policies(present) != policies(absent),
        "derived_perfect_knowledge_balanced_accuracy": 1.0 if changed else 0.5,
        "accuracy_interpretation": "Derived ideal success for this pair; not measured classifier accuracy",
    }
