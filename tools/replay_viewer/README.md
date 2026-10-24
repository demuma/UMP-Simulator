# Recorded motion and release viewer

This local, dependency-free viewer synchronizes recorded sampled observations with actual `AggregationReplay` outputs. It neither runs a simulator nor connects to MongoDB. It adds no interpolated positions, inferred cells or fabricated merge/split transitions.

From the repository root:

```sh
python3 tools/replay_viewer/serve.py --bundle results/YOUR_RUN/viewer --port 8765
```

Open `http://127.0.0.1:8765/`. Stop the server with Ctrl+C. The server binds to localhost only and serves only its three viewer assets, the explicitly declared bundle JSON files, and the one optional validated map PNG. It does not expose the repository directory.

## Common versus local semantic comparison

On the development machine the prepared comparison uses
`results/semantic-local-viewer-2026-10-22` and port 8773:

```sh
python3 -B tools/replay_viewer/prepare_local_bundle.py \
  --study results/semantic-cell-local-2026-10-22 \
  --output results/semantic-local-viewer-2026-10-22
python3 -B tools/replay_viewer/serve.py \
  --bundle results/semantic-local-viewer-2026-10-22 --check
python3 -B tools/replay_viewer/serve.py \
  --bundle results/semantic-local-viewer-2026-10-22 --port 8773
```

Open `http://127.0.0.1:8773/`. The preparation step requires a **new** output
directory; skip it when that bundle already exists and is validated. It checks
the frozen study manifest before copying observations and all eight actual result
variants. It does not run the Simulator, open MongoDB or modify the frozen study.
The first pair is regional common/local coordination with Temporal secondary;
other choices include Spatial secondary and uniform policies. The input is the
stationary scripted analytical fixture, not a moving street simulation.

On a fresh checkout, first reproduce that small study into a new directory with
`python3 -B tools/evaluation/run_semantic_local_policy.py --output results/semantic-cell-local-demo`,
then pass that directory as `--study` and a different new directory as `--output`.
The [viewer test report](../../docs/ASYNC_LOCAL_REPLAY_TEST_REPORT_2026-10-22.md)
is the completion record for this gate; commands alone are not proof of acceptance.

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

JSON paths must be relative to that directory; parent traversal, external symlinks and arbitrary file types are rejected. The only additional file type is the optional literal `map_background.png` described below. The observations must use `ump.observation-replay.v1`, with finite XY coordinates for each observation. Results must use `ump.replay-result.v1`, with exactly matching run ID, sensor ID, coverage, cadence and horizon. Different policy/application IDs are permitted because those are experimental inputs. An optional `sha256` object maps declared relative filenames to their SHA-256 digests. A digest checks accidental changes; it is not an independent trust guarantee.

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
- Comparison A and B independently select a recorded result variant. Common-window variants keep their complete latest-snapshot behavior. Cell-local variants use a historical spatial mosaic: only releases whose `sealed_at_ms` is at or before the playhead can update their declared `coordination_cell`. Other areas retain their own dated historical entries. The local extension is implemented; its [test report](../../docs/ASYNC_LOCAL_REPLAY_TEST_REPORT_2026-10-22.md) records model, server and browser verification, including independent local updates and rewind.
- The displayed recipient data are **historical aggregates**, retained until a newer public event updates their scope. Every local entry has its own half-open source interval, sealing time and age since window end. These intervals need not coincide. Labels on complete cells describe mean sample occupancy over their original intervals, not current occupancy. No whole-cell count is assigned to a clipped display fragment.
- A blank recipient footprint is unknown. It is never interpreted as zero traffic or as proof that a person was absent.
- The private overlay displays **finalized diagnostic windows**, gated by `evaluated_at_ms`, with selected cells, hatched suppressed footprints, completion reasons and recorded policy checks. Common mode shows its latest whole snapshot; local mode replaces only each finalized private scope. A private empty scope clears its earlier private display. Suppression or empty retirement never clears recipient history, and toggling the overlay does not mutate recipient state.
- Click a visible map fragment or use the keyboard-accessible **Inspect cell** list for each comparison. Selection identifies the original event/cell, including its interval; a repeated cell ID in another interval is a different entry. The blue outline follows the selection, and a stale selection moves to an available entry. **Focus selected cell** uses the original footprint. **Reference viewport** can follow that original A/B footprint while still showing the current recorded position sample.
- The cell inspector gives the original half-open spatial bounds and source interval, recorded total observations, distinct road users, mean sample occupancy and a table of **released** semantic categories. For a clipped historical cell, these values belong to the whole original footprint; visible fragments are masks only, and their counts are unknown. A missing category breakdown is explicitly unknown; it is never reconstructed into the recipient section. The observed smallest category support and declared semantic loss are shown. Category support is an operational condition, not a demonstrated anonymity guarantee.
- **Inspect private source groups** is a separate, initially disabled research control. It adds an amber table of the exact recorded input types **within the same selected cell and full half-open window**, before semantic generalization. It never uses the current position sample as a proxy for the window. Distinct users are deduplicated within each type and across the footprint; raw identities are not rendered. A person whose classification changes can occur in multiple type rows, so their distinct counts cannot be summed.
- Source group averages divide by the measured samples in that interval, including measured-empty samples. Explicitly unavailable samples are counted separately. Missing scheduled samples are not reconstructed. These input averages and categories are private diagnostics, not published category estimates or additional recipient knowledge. They remain hidden before the displayed release seals or the diagnostic window finalizes, including after seeking backwards.
- Recorded policy checks are shown only in the private diagnostic view; unavailable checks remain explicitly unrecorded. The separate **Show declared policy regions** toggle draws dashed purple local-rule footprints in all three views, including the reference. It does not enable suppressed diagnostics or private source groups. Optional `variants[].policy_regions` metadata supplies those footprints and lists intersecting declarations in the inspector. A region has `id`, finite `x`, `y`, `width`, `height`, optional `type`, and optional `requirements: [{metric, min?, max?}]`. Metadata describes declared regions; it does not reconstruct the runtime policy compiler or its metric evaluations. Optional `variants[].policy_root_requirements` uses the same requirement list. The inspector combines root bounds with every region that intersects the original cell by positive area: lower bounds take the maximum and upper bounds take the minimum. It shows every source declaration and flags an empty bound intersection. Boundary contact alone does not count as intersection. The **Policy trees and declared regions** overview is available before any release. Older bundles without root metadata explicitly show that the complete effective declaration is unknown. Region metadata is validated before serving: at most 4096 regions per variant, unique nonempty IDs, finite positive rectangles inside coverage, and at most 64 well-formed finite requirement bounds per region. Lowercase metric identifiers describe declarations; they do not activate a metric implementation. Older bundles without this metadata keep their existing behavior.
- Event buttons and timeline lanes use actual availability timestamps; private-only finalizations are diagnostic events when that overlay is selected. Spatial displays change at recorded output events. There is no claim that every geometric difference is an explicitly logged merge or split operation.
- Cumulative released observations are shown against the **whole run's** input observation count. The denominator includes later data when the playhead is earlier; this is a replay progress summary, not a time-local retention estimate.

The whole bundle remains **private research material**, even when the recipient display filter is selected. It contains identities, raw positions and diagnostic thresholds. A sanitized recipient export is a different artifact.

## Optional mapped-scene metadata

The native mapped-scene exporter can add these fields without changing the
existing `ump.replay-viewer.v1` observation/result contract:

```json
{
  "identity_unit": "visible_episode_track",
  "input_provenance": "Native mapped source; sampled positions follow declared kinematic routes.",
  "map": {
    "image": "map_background.png",
    "bounds": {"x": 0, "y": 0, "width": 80, "height": 80},
    "attribution": "© OpenStreetMap contributors",
    "legend": [{"label": "Walking area", "color": "#e8dfce"}],
    "labels": [{"text": "Mönckebergstraße", "x": 40, "y": 50, "kind": "street"}]
  }
}
```

The map bounds must exactly equal recorded observation coverage. The PNG is
clipped and transformed in world coordinates when focusing a selected cell; it
is not stretched to fill the zoomed cell. Attribution remains outside the
clipped canvas. The map, observed track types, and output-state legends are
separate. Street, building, shop, entrance and place names are rendered only
from supplied metadata, never inferred from paths or guessed from geography.
The map-name toggle is independent of the policy-region toggle.

The server accepts one literal map filename, bounded to 16 MiB and 4096 pixels
per side. It verifies noninterlaced 8-bit RGB/RGBA PNG dimensions, chunk checksums,
complete image termination and bounded decompressed scanline length. It rejects
external symlinks, arbitrary image paths, animations, truncated files, bad pixel
sizes and unsupported formats. Metadata is bounded to 32 geography legend items,
200 labels inside the world bounds, 160 characters per label/legend entry,
512 attribution characters and 1024 provenance characters. Geography colors are
ordinary `#RRGGBB` values; no CSS or URLs are accepted there. A map digest may be
included in the existing `sha256` table. Old bundles without maps remain valid.

For `identity_unit: "visible_episode_track"`, support labels explicitly say
**tracks**. A new visible episode can belong to a previously observed person;
the viewer does not link those episodes and receives no stable private person
mapping. Its type tables describe recorded tracks and classification labels,
not verified counts of different people. Other or absent identity-unit metadata
uses the conservative term **observed IDs**.

Each comparison distinguishes six quantities at the current playhead:

- Visible original historical aggregates, each with its own interval.
- Cumulative actual published **cell-windows** (every original released cell once).
- Unique published spatial cell IDs (a repeated cell in a later window counts once).
- Released observation contributions against the full-run input count.
- Actual release events (an event can contain several cells).
- Visible geometry fragments (display masks, never additional publications).

These are historical accounting quantities, not a simultaneous population and
not a privacy guarantee. Rewinding removes later publications from the totals.
Overlapping regional declarations are retained for inspection, including
cross-region contradictions; a contradiction is a finding about the supplied
bounds, not a fabricated observed metric failure.

## Local mosaic interpretation

The [asynchronous replay contract](../../docs/ASYNC_LOCAL_REPLAY_CONTRACT_2026-10-22.md) defines `mosaicAt(result, time, privateMode)`. Local entries retain original cells and release/diagnostic rows plus clipped display fragments. A child update can cover part of an older parent while the rest of that parent remains visible with its original interval and whole-cell counts. A later parent update can replace the child entries. Boundary-only contact does not replace an adjacent footprint.

Latest means **available event time, then original array index**, not the greatest source-window end. Rewind reconstructs the earlier event prefix. The model never changes input geometry, divides parent counts by visible area, or creates synthetic child bins. A clipped parent is an old whole-cell aggregate with part of its drawing hidden; its remaining fragment is not an independently measured subcell.

Private source-group inspection uses the original cell and full source interval, even when only a fragment remains visible. Current reference positions are a separate sample. Cumulative observation/release statistics count original records once, not once per display fragment; asynchronous occupancies are not summed into a claimed current population. Blank areas remain unknown.

The model bounds visible masks with `MAX_VISIBLE_FRAGMENTS = 65536`. Exceeding that limit raises `RangeError` and resets the channel cache; the failed view must clear instead of showing stale or truncated data. Only one incremental state per result/channel is retained, and rewind rebuilds its event prefix. There is no expansion to every possible finest-depth leaf. Completed acceptance checks belong in the [test report](../../docs/ASYNC_LOCAL_REPLAY_TEST_REPORT_2026-10-22.md).

This extension is visualization only. It does not change local release schedules, policy bounds, the aggregation controller or stored observations. The [scope-aware semantic query adapter](../../docs/SCOPED_SEMANTIC_UTILITY_TEST_REPORT_2026-10-22.md) and the [same-input moving baseline comparison](../../docs/MOVING_SCOPED_COMPARISON_REPORT_2026-10-22.md) are now implemented and verified. The new private comparison at http://127.0.0.1:8774/ shows fixed 10-m/400-ms, local/common semantic, and fixed 10-m/1,000-ms outputs from the original n500 Simulator capture. Its historical mosaics do not imply that every fixed current-time query can be answered exactly. Review the recipient time-bin/coverage contract before changing the mechanism; privacy evaluation needs a declared protection objective. No new scenario generator, utility optimizer or attack matrix is started by this viewer.

## Verification

```sh
node tools/replay_viewer/test_model.js
python3 -B -m unittest discover -s tools/replay_viewer -p 'test_viewer.py' -v
node tools/replay_viewer/verify_source_groups.js PATH_TO_REPLAY_BUNDLES
```

The pure-JavaScript model tests cover timeline behavior plus cell selection, explicit private opt-in, seal/evaluation gating even after cache reuse, exact half-open spatial and temporal grouping, distinct identity deduplication, observed sample averages, empty footprints and bounded summary caching. A one-time spatial/time index retains references to the existing observations. Its grid is capped at 256 × 256 buckets and its summary cache at 32 count-only entries; it does not retain additional identity sets or rescan the whole run on every render. The Python server tests cover source compatibility, malformed/non-finite inputs, window timing, coverage, digests, path/symlink rejection, accessible cell controls, default-private opt-in, optional region metadata shape/geometry/bound limits, truthful reference provenance, reference-focus accessibility and the real HTTP allowlist. The HTTP test starts a short-lived localhost server. Local-mode acceptance additionally checks scope replacement, clipping provenance, event order, independent public/private state, rewind and budget failure; final counts are recorded in the dated test report.

`verify_source_groups.js` recursively finds viewer bundles below the required directory argument. It independently scans raw XY observations for the first/last cells of each variant’s first/last nonempty recipient release, removing duplicate selections. It compares exact per-type observations, distinct users and measured-sample means with the indexed inspector, checks recorded public cell totals, and checks private opt-in and sealing gates. This is a sampled real-artifact check, not an exhaustive audit of every cell. It has no hardcoded repository or data paths.


## Storefront and map-edge extension

`ump.building-access.v2` preserves original building footprints and the six-field
portal representation from v1. It adds a closed, bounded geometry-only schema:

- `store_fronts` associates public POI names with scenario destinations, exact
  synthetic entrance targets and frontage polylines along original facade
  segments. A frontage can follow a wall joint; its vertices are not replaced
  with a chord.
- `facade_separators` contains short assumed frontage-divider ticks. They are
  displayed dashed and never described as known indoor walls or separate OSM
  buildings.
- `boundary_intervals` identifies functional-zone intersections with each map
  edge. Solid green walking intervals with paired arrows permit both source
  and sink endpoints. Cycling/road intervals provide context only; this source
  has no cycling or motor-traffic model. Unsupported walking intervals are
  listed as context only.
- `navigation` contains only body clearance, a digest of native center-safe
  polygons, and a bounded scope statement. It contains no person schedules,
  stable private identities or full native configuration.

The **Highlight modeled shop fronts** and **Highlight source / sink intervals** controls
work in the reference and both comparison panels, including cell focus. The frozen background keeps its existing map context when a highlight
is disabled; these controls affect the additional overlays only. Colored
fronts distinguish shops sharing one actual footprint. Exact doors keep their
physical width and use named screen-space callouts; labels may move for
legibility but a leader remains anchored to the physical target. Matching raw
shop labels are hidden to avoid duplicate POI labels. The inventory separates
actual building context, modeled shop destinations and boundary eligibility.

The server validates public geometry before serving it, rejects unknown fields
at every new level, and checks bounded coordinates, relationships, supported
source modes and map-edge membership. The exporter additionally checks exact
portal agreement, native navigation polygon digest/clearance, original route
endpoints against eligible boundaries/doors, and generated config/background/
geometry digests. Validation does not regenerate motion. Same-source comparison
bundles copy the public geometry byte-for-byte and never copy private source
sidecars or the native configuration. Existing v1 bundles remain accepted with
their previous contract.
