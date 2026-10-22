# Recorded motion and release viewer

This local, dependency-free viewer synchronizes sampled simulator observations with actual `AggregationReplay` outputs. It neither runs a simulator nor connects to MongoDB. It adds no interpolated positions, inferred cells or fabricated merge/split transitions.

From the repository root:

```sh
python3 tools/replay_viewer/serve.py --bundle results/YOUR_RUN/viewer --port 8765
```

Open `http://127.0.0.1:8765/`. Stop the server with Ctrl+C. The server binds to localhost only and serves only its three viewer assets plus the explicitly declared bundle JSON files. It does not expose the repository directory.

## Bundle contract

The bundle directory contains `bundle.json`:

```json
{
  "schema": "ump.replay-viewer.v1",
  "title": "Recorded motion: fixed and adaptive release",
  "observations": "observations.json",
  "variants": [
    {"id": "fixed", "label": "Fixed grid / fixed window", "result": "fixed/result.json"},
    {"id": "semantic_first", "label": "Semantic First", "result": "semantic_first/result.json"}
  ]
}
```

Paths must be relative to that directory; parent traversal, external symlinks and arbitrary file types are rejected. The observations must use `ump.observation-replay.v1`, with finite XY coordinates for each observation. Results must use `ump.replay-result.v1`, with exactly matching run ID, sensor ID, coverage, cadence and horizon. Different policy/application IDs are permitted because those are experimental inputs. An optional `sha256` object maps declared relative filenames to their SHA-256 digests. A digest checks accidental changes; it is not an independent trust guarantee.

To validate without starting the server:

```sh
python3 tools/replay_viewer/serve.py --bundle results/YOUR_RUN/viewer --check
```

The viewer references existing JSON files rather than embedding large data in HTML or JavaScript. There is no npm build, external script, CDN or internet dependency.

## What the views mean

- The private reference shows the sampled XY input stream and does not unconditionally claim simulator provenance. In a verified simulator capture, those positions are taken from GT at the sensor cadence and checked against raw AGBS cells. This panel is not a replay of every numerical simulator step. The frozen local-policy bundle explicitly declares “scripted mechanism test” in its title; the reference repeats that declaration. Other bundles use generic wording rather than guessing their generation method from run IDs.
- **Reference viewport** selects the full recorded area or the currently selected cell of comparison A/B. Its axes use that cell’s true geometry. The positions and type counts remain those of the **current recorded sample**, not the historical aggregation interval from which the footprint was selected. Before a finalized cell exists, focus safely falls back to the full area. No zoom alters coordinates, interpolates movement or adds jitter.
- Reference statistics distinguish the full sample’s road-user IDs, exact distinct XY coordinates and the IDs within the current viewport. Its type table gives full-sample and viewport counts. A numbered marker represents IDs with exactly coincident recorded positions; colored sectors show their types. Nearby distinct positions remain separate observations even when their markers overlap on screen. Small deterministic movements can be invisible on a large full-area map and become visible under cell focus.
- Positions are held until the next expected sample, with the sample timestamp and age shown. A missing or unavailable current sample clears old positions; a measured-empty sample is displayed as measured empty. There is no interpolation.
- Comparison A and B independently select a recorded result variant. The recipient view shows only the most recent release whose `sealed_at_ms` is at or before the playhead. The entire previous snapshot is replaced at the next sealing event.
- The displayed recipient cut is a **historical aggregate**, explicitly retained on screen until a later release. Its half-open source interval, sealing time and age since window end are shown. The cell label is mean sample occupancy over that interval, not current occupancy.
- A blank recipient footprint is unknown. It is never interpreted as zero traffic or as proof that a person was absent.
- The private overlay switches each comparison to its latest **finalized diagnostic window**, gated by `evaluated_at_ms`. It displays selected cells, hatched suppressed footprints, completion reason and recorded policy checks. It does not mix private suppressed footprints from a newer window with an older recipient snapshot.
- Click a map cell or use the keyboard-accessible **Inspect cell** list for each comparison. The list identifies cell ID, depth, dimensions and lower-left XY coordinates. The blue outline follows the selected cell; a stale selection moves to the first cell of the newly shown cut. **Focus selected cell** magnifies that footprint so even 1.25 m leaves can be inspected. The source positions panel keeps its full-area view.
- The cell inspector gives the exact half-open spatial bounds and source interval, recorded total observations, distinct road users, mean sample occupancy and a table of **released** semantic categories. A missing category breakdown is explicitly unknown; it is never reconstructed into the recipient section. The observed smallest category support and declared semantic loss are shown. Category support is an operational condition, not a demonstrated anonymity guarantee.
- **Inspect private source groups** is a separate, initially disabled research control. It adds an amber table of the exact recorded input types **within the same selected cell and full half-open window**, before semantic generalization. It never uses the current position sample as a proxy for the window. Distinct users are deduplicated within each type and across the footprint; raw identities are not rendered. A person whose classification changes can occur in multiple type rows, so their distinct counts cannot be summed.
- Source group averages divide by the measured samples in that interval, including measured-empty samples. Explicitly unavailable samples are counted separately. Missing scheduled samples are not reconstructed. These input averages and categories are private diagnostics, not published category estimates or additional recipient knowledge. They remain hidden before the displayed release seals or the diagnostic window finalizes, including after seeking backwards.
- Policy checks are shown only in the private diagnostic view. Optional `variants[].policy_regions` metadata draws dashed purple local-rule footprints there and lists intersecting region declarations in the inspector. A region has `id`, finite `x`, `y`, `width`, `height`, optional `type`, and optional `requirements: [{metric, min?, max?}]`. Metadata describes declared regions; the recorded effective checks determine actual decisions. Region metadata is validated before serving: at most 4096 regions per variant, unique nonempty IDs, finite positive rectangles inside coverage, and at most 64 well-formed finite requirement bounds per region. Lowercase metric identifiers describe declarations; they do not activate a metric implementation. Older bundles without this metadata keep their existing behavior.
- Event buttons and timeline lanes use actual sealing timestamps. Spatial cuts change at recorded output events. There is no claim that every geometric difference is an explicitly logged merge or split operation.
- Cumulative released observations are shown against the **whole run's** input observation count. The denominator includes later data when the playhead is earlier; this is a replay progress summary, not a time-local retention estimate.

The whole bundle remains **private research material**, even when the recipient display filter is selected. It contains identities, raw positions and diagnostic thresholds. A sanitized recipient export is a different artifact.

This viewer currently compares common-window snapshot streams. A global “latest snapshot” is not a correct visualization of independently finalized cell-local windows; those need a separate validity/coverage view before being added here.

## Verification

```sh
node tools/replay_viewer/test_model.js
python3 -B -m unittest discover -s tools/replay_viewer -p 'test_viewer.py' -v
node tools/replay_viewer/verify_source_groups.js PATH_TO_REPLAY_BUNDLES
```

The 35 pure-JavaScript tests cover timeline behavior plus cell selection, explicit private opt-in, seal/evaluation gating even after cache reuse, exact half-open spatial and temporal grouping, distinct identity deduplication, observed sample averages, empty footprints and bounded summary caching. A one-time spatial/time index retains references to the existing observations. Its grid is capped at 256 × 256 buckets and its summary cache at 32 count-only entries; it does not retain additional identity sets or rescan the whole run on every render. The 28 Python tests cover source compatibility, malformed/non-finite inputs, window timing, coverage, digests, path/symlink rejection, accessible cell controls, default-private opt-in, optional region metadata shape/geometry/bound limits, truthful reference provenance, reference-focus accessibility and the real HTTP allowlist. The HTTP test starts a short-lived localhost server.

`verify_source_groups.js` recursively finds viewer bundles below the required directory argument. It independently scans raw XY observations for the first/last cells of each variant’s first/last nonempty recipient release, removing duplicate selections. It compares exact per-type observations, distinct users and measured-sample means with the indexed inspector, checks recorded public cell totals, and checks private opt-in and sealing gates. This is a sampled real-artifact check, not an exhaustive audit of every cell. It has no hardcoded repository or data paths.
