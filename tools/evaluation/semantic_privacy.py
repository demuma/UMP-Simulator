"""Strict semantic recipient channel and public-only feature plumbing (P25.2).

The channel retains every approved scalar/semantic field and coordination scope.
It is a file-format boundary, not access control. The default availability model
assumes a private final snapshot is available at the declared horizon, including EOF.
``logical_sealing`` is an explicit instantaneous-delivery assumption; neither
model certifies wall-clock delivery or live deadlines. Public counts cannot prove
identity support or raw-input truth: those require a separate private source audit.

The scalar projection below is labelled and used only to reuse scalar validation
and feature arithmetic. It never defines or narrows this recipient channel.
Category features describe explicitly published bins only. A published ancestor
never supplies a zero for a missing descendant. Numeric placeholders always have
separate availability coordinates. Support sums are sums, not unique populations.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

import empirical_privacy as scalar

PUBLIC_SCHEMA = "ump.public-transcript.v2"
SEMANTIC_SCHEMA = "ump.semantic-release.v1"
AVAILABILITY_MODELS = ("final_snapshot_at_horizon", "logical_sealing")
EXACT_MAXIMUM = 2**53 - 1
_PUBLIC_KEYS = frozenset({"schema", "coverage", "sampling_period_ms", "end_ms",
                          "taxonomy", "availability_model", "releases"})
_RELEASE_KEYS = frozenset({"release_id", "start_ms", "end_ms", "sealed_at_ms",
                           "available_at_ms", "model", "policy_id", "policy_version", "cells"})
_CELL_KEYS = frozenset({"cell_id", "depth", "x", "y", "width", "height",
                        "observation_contributions", "distinct_road_users",
                        "mean_sample_occupancy", "effective_policy_id", "semantic"})
_SCOPE_KEYS = frozenset({"cell_id", "depth", "x", "y", "width", "height"})
_SEMANTIC_KEYS = frozenset({"schema", "taxonomy_id", "taxonomy_version", "categories",
    "min_category_distinct_contributors", "semantic_mean_loss", "semantic_max_loss"})
_BIN_KEYS = frozenset({"category_id", "observation_contributions", "distinct_contributors"})
_SEMANTIC_FEATURES = ("public_min_category_support_mean", "public_semantic_mean_loss_mean",
    "public_semantic_max_loss_max", "target_min_category_support_mean",
    "target_semantic_mean_loss_mean", "target_semantic_max_loss_max")
_CATEGORY_FEATURES = ("public_published_cell_fraction", "public_contributions_sum",
    "public_distinct_support_sum", "target_published_fraction",
    "target_contributions_mean", "target_distinct_support_mean")
_AVAILABILITY_FEATURES = ("release_availability_delay_mean_ms", "target_availability_age_mean_ms")


def _object(value: Any, where: str) -> dict:
    return scalar._object(value, where)


def _keys(value: dict, expected: frozenset, where: str) -> None:
    scalar._keys(value, expected, where)


def _integer(value: Any, where: str, minimum: int = 0) -> int:
    value = scalar._integer(value, where, minimum)
    if value > EXACT_MAXIMUM:
        raise ValueError(f"{where} exceeds the exact integer range")
    return value


def _number(value: Any, where: str, minimum: float | None = None) -> float:
    try:
        return scalar._number(value, where, minimum)
    except OverflowError as error:
        raise ValueError(f"{where} exceeds finite numeric range") from error


def _coverage(value: Any) -> dict:
    value = _object(value, "coverage")
    _keys(value, frozenset({"x", "y", "width", "height", "leaf_depth"}), "coverage")
    for key in ("x", "y", "width", "height"):
        _number(value[key], "coverage." + key)
    return scalar._coverage(value)


def _text(value: Any, where: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > 128
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise ValueError(f"{where} must be bounded nonempty public text without control characters")
    return value


def _taxonomy(value: Any, *, public: bool) -> tuple[dict, dict]:
    value = _object(value, "taxonomy")
    _keys(value, frozenset({"id", "version", "nodes"}), "taxonomy")
    identity = _text(value["id"], "taxonomy.id")
    version = _text(value["version"], "taxonomy.version")
    if not isinstance(value["nodes"], list) or not 1 <= len(value["nodes"]) <= 256:
        raise ValueError("taxonomy.nodes must contain 1--256 nodes")
    nodes = {}
    for original in value["nodes"]:
        original = _object(original, "taxonomy.node")
        expected = frozenset({"id", "parent", "loss"})
        if not public:
            expected = (expected - ({"parent"} if "parent" not in original else set())) | (
                {"input_types"} if "input_types" in original else set())
        _keys(original, expected, "taxonomy.node")
        identity_node = _text(original["id"], "taxonomy.node.id")
        parent = original.get("parent", "")
        if parent != "":
            _text(parent, "taxonomy.node.parent")
        elif not isinstance(parent, str):
            raise ValueError("taxonomy.node.parent must be a string")
        loss = _number(original["loss"], "taxonomy.node.loss", 0)
        if loss > 1 or identity_node in nodes:
            raise ValueError("Taxonomy has duplicate node IDs or loss outside [0,1]")
        nodes[identity_node] = {"id": identity_node, "parent": parent, "loss": loss}
    roots = [node for node in nodes.values() if not node["parent"]]
    if len(roots) != 1 or roots[0]["loss"] != 1:
        raise ValueError("Taxonomy requires exactly one root with loss one")
    children = {identity_node: [] for identity_node in nodes}
    for node in nodes.values():
        parent = node["parent"]
        if parent:
            if parent not in nodes or nodes[parent]["loss"] < node["loss"]:
                raise ValueError("Taxonomy has unknown parent or increasing descendant loss")
            children[parent].append(node["id"])
    reached = set()
    def visit(identity_node, depth):
        if identity_node in reached or depth > 32:
            raise ValueError("Taxonomy has a cycle or exceeds depth 32")
        reached.add(identity_node)
        for child in children[identity_node]:
            visit(child, depth + 1)
    visit(roots[0]["id"], 0)
    if len(reached) != len(nodes):
        raise ValueError("Taxonomy contains a disconnected component or cycle")
    if any(not children[key] and node["loss"] != 0 for key, node in nodes.items()):
        raise ValueError("Every taxonomy terminal must have zero loss")
    ordered = [nodes[key] for key in sorted(nodes)]
    if public and [node["id"] for node in value["nodes"]] != sorted(nodes):
        raise ValueError("Public taxonomy nodes must have canonical ID order")
    return {"id": identity, "version": version, "nodes": ordered}, nodes


def public_taxonomy(taxonomy: dict) -> dict:
    """Sanitize declared taxonomy; raw input-type mappings never enter the channel."""
    return deepcopy(_taxonomy(taxonomy, public=False)[0])


def _semantic(value: Any, cell: dict, taxonomy: dict, nodes: dict) -> None:
    value = _object(value, "cell.semantic")
    _keys(value, _SEMANTIC_KEYS, "cell.semantic")
    if (value["schema"] != SEMANTIC_SCHEMA or value["taxonomy_id"] != taxonomy["id"]
            or value["taxonomy_version"] != taxonomy["version"]):
        raise ValueError("Public semantic schema or taxonomy identity/version mismatch")
    bins = value["categories"]
    if not isinstance(bins, list) or not bins:
        raise ValueError("A public semantic cell must have nonempty category bins")
    contributions = _integer(cell["observation_contributions"], "cell.observation_contributions", 1)
    distinct = _integer(cell["distinct_road_users"], "cell.distinct_road_users", 1)
    if distinct > contributions:
        raise ValueError("Cell distinct support exceeds contributions")
    seen, counts, supports, losses = set(), [], [], []
    for item in bins:
        item = _object(item, "semantic.category")
        _keys(item, _BIN_KEYS, "semantic.category")
        category = _text(item["category_id"], "semantic.category_id")
        if category not in nodes or category in seen:
            raise ValueError("Semantic bins contain unknown or duplicate categories")
        seen.add(category)
        count = _integer(item["observation_contributions"], "category.observation_contributions", 1)
        support = _integer(item["distinct_contributors"], "category.distinct_contributors", 1)
        if support > count or support > distinct:
            raise ValueError("Semantic category distinct support is inconsistent with cell support")
        counts.append(count)
        supports.append(support)
        losses.append(nodes[category]["loss"])
    for category in seen:
        parent = nodes[category]["parent"]
        while parent:
            if parent in seen:
                raise ValueError("Published semantic categories must form a taxonomy antichain")
            parent = nodes[parent]["parent"]
    if sum(counts) != contributions or sum(supports) != distinct:
        raise ValueError("Semantic contributions or distinct-support bounds disagree with cell totals")
    # The v2 episode contract assumes a stable category for every track. The
    # required support sum is necessary under that partition, but these counts
    # alone cannot prove stable types or identity disjointness; audit raw input.
    expected = (min(supports), math.fsum(count * loss for count, loss in zip(counts, losses)) / contributions,
                max(losses))
    for key, correct in zip(("min_category_distinct_contributors", "semantic_mean_loss", "semantic_max_loss"), expected):
        number = _number(value[key], "semantic." + key, 0)
        if not math.isclose(number, correct, rel_tol=0, abs_tol=1e-12):
            raise ValueError("Public semantic metric disagrees with published bins/taxonomy: " + key)


def _scalar_projection(public: dict) -> dict:
    """Explicit scalar validation/feature arithmetic projection, never an export."""
    projected = {"schema": scalar.PUBLIC_SCHEMA, **{key: deepcopy(public[key]) for key in
        ("coverage", "sampling_period_ms", "end_ms")}, "releases": []}
    for release in public["releases"]:
        copied = {key: deepcopy(value) for key, value in release.items()
                  if key not in ("available_at_ms", "cells", "coordination_cell")}
        copied["cells"] = [{key: deepcopy(value) for key, value in cell.items() if key != "semantic"}
                           for cell in release["cells"]]
        projected["releases"].append(copied)
    return projected


def validate_public(public: dict) -> dict:
    """Validate the complete v2 channel without modifying the caller's object."""
    public = _object(public, "public transcript")
    _keys(public, _PUBLIC_KEYS, "public transcript")
    if public["schema"] != PUBLIC_SCHEMA:
        raise ValueError(f"Expected public schema {PUBLIC_SCHEMA}")
    taxonomy, nodes = _taxonomy(public["taxonomy"], public=True)
    model = public["availability_model"]
    if model not in AVAILABILITY_MODELS:
        raise ValueError("Unknown declared availability_model")
    coverage = _coverage(public["coverage"])
    _integer(public["sampling_period_ms"], "sampling_period_ms", 1)
    horizon = _integer(public["end_ms"], "end_ms", 1)
    if not isinstance(public["releases"], list):
        raise ValueError("Public releases must be an array")
    previous_available = -1
    for index, release in enumerate(public["releases"]):
        release = _object(release, f"releases[{index}]")
        keys = _RELEASE_KEYS | ({"coordination_cell"} if "coordination_cell" in release else set())
        _keys(release, keys, f"releases[{index}]")
        for key in ("start_ms", "end_ms", "sealed_at_ms", "available_at_ms"):
            _integer(release[key], "release." + key)
        for key in ("model", "policy_id", "policy_version"):
            _text(release[key], "release." + key)
        available = release["available_at_ms"]
        if (available < release["sealed_at_ms"] or available > horizon or available < previous_available
                or available != (horizon if model == "final_snapshot_at_horizon" else release["sealed_at_ms"])):
            raise ValueError("Release availability violates the declared model, order or horizon")
        previous_available = available
        if not isinstance(release["cells"], list) or not release["cells"]:
            raise ValueError("Public releases must contain cells")
        for cell in release["cells"]:
            cell = _object(cell, "release.cell")
            _keys(cell, _CELL_KEYS, "release.cell")
            _text(cell["effective_policy_id"], "cell.effective_policy_id")
            for key in ("x", "y", "width", "height"):
                _number(cell[key], "cell." + key)
            if cell["mean_sample_occupancy"] is not None:
                _number(cell["mean_sample_occupancy"], "cell.mean_sample_occupancy", 0)
            _semantic(cell["semantic"], cell, taxonomy, nodes)
        if "coordination_cell" in release:
            scope = _object(release["coordination_cell"], "release.coordination_cell")
            _keys(scope, _SCOPE_KEYS, "release.coordination_cell")
            for key in ("cell_id", "depth"):
                _integer(scope[key], "coordination_cell." + key, 1)
            for key in ("x", "y", "width", "height"):
                _number(scope[key], "coordination_cell." + key)
            depth, identity = scope["depth"], scope["cell_id"]
            if depth > coverage["leaf_depth"] or identity >> (2 * depth) != 3:
                raise ValueError("Coordination scope has invalid quadtree identity/depth")
            expected = scalar._cell_geometry(identity, depth, coverage)
            if any(not math.isclose(scope[key], correct, rel_tol=1e-10, abs_tol=1e-9)
                   for key, correct in zip(("x", "y", "width", "height"), expected)):
                raise ValueError("Coordination scope geometry disagrees with its quadtree ID")
            for cell in release["cells"]:
                cell_depth = _integer(cell["depth"], "cell.depth", 1)
                cell_identity = _integer(cell["cell_id"], "cell.cell_id", 1)
                if cell_depth < depth or cell_identity >> (2 * (cell_depth - depth)) != identity:
                    raise ValueError("Public cell lies outside its coordination scope")
    # Existing scalar validator checks true ID-derived geometry, disjoint space-
    # time support, canonical aliases, all scalar values and EOF/horizon bounds.
    scalar._validated_public(_scalar_projection(public))
    return public


_validated_public = validate_public


def export_releases(*, coverage: dict, sampling_period_ms: int, end_ms: int, releases: list,
                    taxonomy: dict, availability_model: str = "final_snapshot_at_horizon") -> dict:
    """Allowlist approved native records; materialize no private execution metadata."""
    if availability_model not in AVAILABILITY_MODELS:
        raise ValueError("Unknown declared availability_model")
    if not isinstance(releases, list):
        raise ValueError("releases must be an array")
    public = {"schema": PUBLIC_SCHEMA, "coverage": deepcopy(coverage),
        "sampling_period_ms": sampling_period_ms, "end_ms": end_ms,
        "taxonomy": public_taxonomy(taxonomy), "availability_model": availability_model, "releases": []}
    for index, original in enumerate(releases):
        original = _object(original, "release")
        expected = (_RELEASE_KEYS - {"available_at_ms"}) | (
            {"coordination_cell"} if "coordination_cell" in original else set())
        _keys(original, expected, "release")
        if not isinstance(original["release_id"], str) or not original["release_id"]:
            raise ValueError("Private release_id must be a nonempty string before alias normalization")
        release = deepcopy(original)
        release["release_id"] = f"release-{index:06d}"
        release["available_at_ms"] = end_ms if availability_model == "final_snapshot_at_horizon" else release["sealed_at_ms"]
        if isinstance(release["cells"], list):
            # Sort only after type/integer validation, avoiding bool/mixed-key aliases.
            for cell in release["cells"]:
                _object(cell, "release.cell")
                _integer(cell.get("cell_id"), "cell.cell_id", 1)
                semantic = _object(cell.get("semantic"), "cell.semantic")
                if not isinstance(semantic.get("categories"), list):
                    raise ValueError("semantic.categories must be an array")
                for category in semantic["categories"]:
                    _object(category, "semantic.category")
                    _text(category.get("category_id"), "semantic.category_id")
                semantic["categories"].sort(key=lambda item: item["category_id"])
            release["cells"].sort(key=lambda cell: cell["cell_id"])
        public["releases"].append(release)
    validate_public(public)
    return public


def export_public(result: dict, taxonomy: dict, *,
                  availability_model: str = "final_snapshot_at_horizon") -> dict:
    """Export fixed context and the complete semantic product; ignore private top fields."""
    result = _object(result, "result")
    if result.get("schema") != "ump.replay-result.v1":
        raise ValueError("Expected replay result schema ump.replay-result.v1")
    source = _object(result.get("source"), "result.source")
    return export_releases(coverage=source.get("coverage"),
        sampling_period_ms=source.get("sampling_period_ms"), end_ms=source.get("end_ms"),
        releases=result.get("releases"), taxonomy=taxonomy, availability_model=availability_model)


def canonical_transcript(public: dict) -> tuple:
    """Immutable complete-channel representation, including fixed public constants."""
    validate_public(public)
    def freeze(value):
        if isinstance(value, dict):
            return tuple((key, freeze(value[key])) for key in sorted(value))
        if isinstance(value, list):
            return tuple(freeze(item) for item in value)
        return value
    canonical = deepcopy(public)
    for release in canonical["releases"]:
        release["cells"].sort(key=lambda cell: cell["cell_id"])
        for cell in release["cells"]:
            cell["semantic"]["categories"].sort(key=lambda category: category["category_id"])
    return freeze(canonical)


def _feature_taxonomy(public_or_taxonomy):
    value = _object(public_or_taxonomy, "public transcript or taxonomy")
    return _taxonomy(value["taxonomy"] if "taxonomy" in value else value, public=True)[0]


def feature_names(public_or_taxonomy: dict, include_geometry: bool = True) -> list[str]:
    """Fixed taxonomy-ID order; independent of labels, output or knowledge length."""
    taxonomy = _feature_taxonomy(public_or_taxonomy)
    names = ["scalar." + name for name in scalar.feature_names(include_geometry)]
    names += ["semantic." + name for name in _SEMANTIC_FEATURES]
    for node in taxonomy["nodes"]:
        names += ["category[" + node["id"] + "]." + name for name in _CATEGORY_FEATURES]
    if include_geometry:
        names += ["semantic." + name for name in _AVAILABILITY_FEATURES]
    return names


def feature_vector(public: dict, knowledge: list[dict], include_geometry: bool = True) -> list[float]:
    """Public-only features; explicit-bin availability guards every absent category."""
    validate_public(public)
    try:
        return _feature_vector_validated(public, knowledge, include_geometry)
    except OverflowError as error:
        raise ValueError("Semantic feature arithmetic exceeds finite numeric range") from error


def _feature_vector_validated(public: dict, knowledge: list[dict], include_geometry: bool) -> list[float]:
    names = feature_names(public, include_geometry)
    # This strict, labelled projection reuses candidate/grid and duplicate checks
    # and the historical scalar arithmetic, retaining semantic output separately.
    values = scalar.feature_vector(_scalar_projection(public), knowledge, include_geometry)
    cells = [cell for release in public["releases"] for cell in release["cells"]]
    matched = []
    for point in knowledge:
        for release in public["releases"]:
            if not release["start_ms"] <= point["observed_at_ms"] < release["end_ms"]:
                continue
            cell = next((cell for cell in release["cells"]
                if cell["x"] <= point["x"] < cell["x"] + cell["width"]
                and cell["y"] <= point["y"] < cell["y"] + cell["height"]), None)
            if cell is not None:
                matched.append((point, release, cell))
                break
    target_cells = [cell for _, _, cell in matched]
    values += [scalar._mean([cell["semantic"]["min_category_distinct_contributors"] for cell in cells]),
        scalar._mean([cell["semantic"]["semantic_mean_loss"] for cell in cells]),
        scalar._maximum([cell["semantic"]["semantic_max_loss"] for cell in cells]),
        scalar._mean([cell["semantic"]["min_category_distinct_contributors"] for cell in target_cells]),
        scalar._mean([cell["semantic"]["semantic_mean_loss"] for cell in target_cells]),
        scalar._maximum([cell["semantic"]["semantic_max_loss"] for cell in target_cells])]
    for node in public["taxonomy"]["nodes"]:
        def bins(items):
            return [category for cell in items for category in cell["semantic"]["categories"]
                    if category["category_id"] == node["id"]]
        global_bins, target_bins = bins(cells), bins(target_cells)
        values += [scalar._ratio(len(global_bins), len(cells)),
            sum(item["observation_contributions"] for item in global_bins),
            sum(item["distinct_contributors"] for item in global_bins),
            scalar._ratio(len(target_bins), len(knowledge)),
            scalar._mean([item["observation_contributions"] for item in target_bins]),
            scalar._mean([item["distinct_contributors"] for item in target_bins])]
    if include_geometry:
        values += [scalar._mean([release["available_at_ms"] - release["end_ms"] for release in public["releases"]]),
            scalar._mean([release["available_at_ms"] - point["observed_at_ms"] for point, release, _ in matched])]
    if len(values) != len(names) or any(not math.isfinite(value) for value in values):
        raise ValueError("Semantic feature arithmetic produced nonfinite values or dimension mismatch")
    return [float(value) for value in values]


def public_view(public: dict, now_ms: int, *, recent_window_ms: int | None = None) -> dict:
    """Gate whole immutable records by availability, keeping the fixed EOF horizon.

    The view at ``now_ms == end_ms`` is final_including_eof. Interior checkpoints
    never force an earlier EOF. Recent arrival blocks are (now-window, now].
    """
    validate_public(public)
    _integer(now_ms, "now_ms")
    if now_ms > public["end_ms"]:
        raise ValueError("Checkpoint exceeds the fixed public horizon")
    if recent_window_ms is not None:
        _integer(recent_window_ms, "recent_window_ms", 1)
    result = deepcopy({key: value for key, value in public.items() if key != "releases"})
    result["releases"] = []
    for release in public["releases"]:
        available = release["available_at_ms"]
        if available > now_ms or (recent_window_ms is not None and available <= now_ms - recent_window_ms):
            continue
        copied = deepcopy(release)
        copied["release_id"] = f"release-{len(result['releases']):06d}"
        result["releases"].append(copied)
    validate_public(result)
    return result


def causal_feature_names(public_or_taxonomy: dict, view: str) -> list[str]:
    from causal_privacy import AUXILIARY_NAMES, VIEWS
    if view not in VIEWS:
        raise ValueError("Unknown causal feature view")
    names = ["auxiliary." + name for name in AUXILIARY_NAMES]
    if view != "auxiliary":
        names += ["recent." + name for name in feature_names(public_or_taxonomy)]
    if view == "history":
        names += ["cumulative." + name for name in feature_names(public_or_taxonomy)]
    return names


def feature_views(public: dict, events: list[dict], now_ms: int) -> dict:
    """Reuse existing knowledge provenance; gate semantic output by available_at_ms."""
    from causal_privacy import RECENT_WINDOW_MS, auxiliary_features, knowledge_at
    known = knowledge_at(events, now_ms)
    auxiliary = auxiliary_features(known)
    recent = public_view(public, now_ms, recent_window_ms=RECENT_WINDOW_MS)
    cumulative = public_view(public, now_ms)
    recent_values = auxiliary + feature_vector(recent, known)
    return {"auxiliary": auxiliary, "recent": recent_values,
            "history": recent_values + feature_vector(cumulative, known)}
