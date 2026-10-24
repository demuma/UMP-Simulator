# Mapped pedestrian visits, local recordings and comparisons

The maintained C++ Simulator, its sensors and normal Region → PolicyTree adapter
run this opt-in 80 × 80-m Mönckebergstraße source. The frozen OSM snapshot is local;
no live map request is needed. Native observations, actual immutable releases and
private journal retirements can now be retained under ignored `results/` and
replayed with the aligned map. Generated movement/identity streams never belong
in Git. See the [identity contract](../../docs/MAPPED_SCENE_IDENTITY_CONTRACT_2026-10-23.md),
[historical integration report](../../docs/MAPPED_SCENE_TEST_REPORT_2026-10-23.md)
and [current integration report](../../docs/MAPPED_REPLAY_INTEGRATION_TEST_REPORT_2026-10-23.md).

## Storefronts and individual pedestrian navigation (current default)

`run_scene.py` now defaults to `--motion-mode storefronts`. The original building
outline is retained; Apollo, Ditsch, Adidas Originals and H&M HOME become separate
modeled destinations with synthetic facade projections. Short divider ticks are
assumed shopfront divisions, not known indoor walls. Walking map-edge intervals
provide individual source/sink points. Seeded routes and native steering/replanning
replace shared fixed access lines. Road/cycling intervals are context only.

```sh
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/run_scene.py \
  --motion-mode storefronts --population 64 --duration-s 240 --arrival-interval-ms 1000 \
  --output results/storefront-run-new/scene --replay --port 8787
```

Choose a fresh output parent. The duration is an observation horizon; inspect
capture-proof active/pending/completed counts rather than assuming all requested
visits have finished. The [implementation guide](../../docs/STOREFRONT_NAVIGATION_2026-10-24.md)
defines source behavior, manual overrides, geometry/lifecycle boundaries and the
separate acceptance gates. All generated movement remains local and ignored.

## Map presentation layers and retained-background refresh

New `map_background.png` files contain functional geometry and original building
outlines only. Shop/building names, entrances and access debugging marks are not
baked into the raster: the replay draws its names and entrance markers once in
separate toggle-controlled vector layers. OpenStreetMap attribution remains in
PNG metadata and the map metadata used by the readable replay footer. The scene
manifest records `background_rendering`; PNG metadata contains the same contract
under `UMP.MapRendering`.

A retained recording with a legacy annotated background can be refreshed without
regenerating routes, running the Simulator or reading MongoDB:

```sh
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/refresh_background.py \
  --scene results/YOUR_RETAINED_RUN/scene \
  --replay results/YOUR_RETAINED_RUN/replay
```

The command requires a verified capture, identical scene/replay configuration and
public access geometry, matching frozen source/transform/map-builder provenance,
and all original artifact digests. Scene/replay folders must be distinct and
non-overlapping and must not contain the repository. It stages and validates the new presentation
before replacement. Original PNGs, scene manifest, replay bundle and capture proof
are archived under `presentation_history/` (inside `private/` for replay history).
Explicit presentation-refresh records retain the original provenance; only the
current PNG and its digest manifests change. Observations, native results, source,
configuration and access geometry keep their exact bytes. Existing history is
never overwritten; repeating an already-clean refresh is a no-op. This is a local
presentation repair, not a new simulation or new aggregation result.

See the [background cleanup test report](../../docs/REPLAY_BACKGROUND_CLEANUP_TEST_REPORT_2026-10-24.md).

## Earlier two-building fixture


Explicit `--motion-mode buildings` draws eight separate
cached OSM footprints and connects two buildings through **synthetic** exact
original-wall midpoint doors: Rappolthaus and MöGrill. Door widths are modeled,
not inferred from OSM. Actual route-end arrival controls entry; the former 3-m
approach disk is not an entry trigger. Body/angle-aware short door admission and
separated access/through paths retain swept collision checks.

```sh
/private/tmp/ump-osm-moenckeberg-2026-10-23/venv/bin/python tools/mapped_scene/run_scene.py \
  --motion-mode buildings --population 64 --duration-s 180 --arrival-interval-ms 1000 \
  --output results/YOUR_FRESH_BUILDING_RUN/scene --replay --port 8786
```

The existing verified local capture can be reopened with:

```sh
python3 -B tools/replay_viewer/serve.py --bundle results/building-access-2026-10-24-64/replay --port 8786
```

Building/entrance highlights and the door inventory are separate from policy
rectangles. A small public geometry artifact survives export/comparison; private
identity schedules remain unserved. The first fixture has 64 people, 32 visits
(16 per building) and 96 visible episodes; all finish in the verified 180-s run.
Use explicit `corridor`/`integration` to reproduce the historical sources below.
See the [implementation contract](../../docs/MULTI_BUILDING_ACCESS_2026-10-24.md)
and [test report](../../docs/MULTI_BUILDING_ACCESS_TEST_REPORT_2026-10-24.md).

## Build and prepare the Python environment

From the repository root, with normal Simulator dependencies and MongoDB running
on localhost:27017, and `mongosh` in PATH:

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release
cmake --build simulator/build -j 4
python3 -m venv /private/tmp/ump-mapped-venv
/private/tmp/ump-mapped-venv/bin/python -m pip install -r tools/mapped_scene/requirements.txt
```

Use that Python for the scene tools. The replay HTTP server itself needs only the
Python standard library. The checked-in `simulator/config.yaml` is unchanged.

## Run and retain a native recording

The historical four-route source remains an explicit reproducible reference:

```sh
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/run_scene.py \
  --motion-mode integration --duration-s 90 \
  --output results/mapped-integration-new/scene --replay --port 8780
```

Choose a **new parent directory** each time. The launcher writes `scene/` and a
sibling `replay/`, prints their paths, runs the native executable, exports a
verified recording after successful completion, and then starts the local viewer.
`--render` additionally shows the native live window; `--open` asks the launcher
to open the browser when `--replay` starts. Without `--replay`, capture still occurs
and the command prints how to view it later. Without `--output`, the default is
`results/mapped-visits/<UTC timestamp>-<token>/scene`. Seed defaults to 20261023.

Every invocation allocates a fresh `UMP_Mapped_<32 lower-case UUID hex>` base,
plus `_Releases` and `_Private`, and refuses a namespace collision. Its three
MongoDB databases are kept by default. `--cleanup` deletes only those owned
namespaces **after** a successful verified recording; the files remain playable.
Failed/cancelled sources are retained for diagnosis and do not get a verified
replay. `--no-record` explicitly disables capture and cannot be combined with
`--replay`. Existing `Simulation` data are never reused or deleted.

A duration is an observation horizon, not a promise that all requested trips
finish. Short horizons clip movement; corridor arrivals can remain queued or
active at EOF. Inspect the source/lifecycle summary rather than equating scheduled
population, admitted tracks and current visible population.

## Corridor motion extension

`--motion-mode corridor` retains the previous single-door corridor source; both
it and historical integration are now selected explicitly. The corridor implementation adds:

- One seeded smooth lateral path variant per visible episode, within checked
  directional walking corridors. Portal/boundary endpoints remain fixed. There
  is no independent per-frame position jitter or unconstrained random walk.
- Explicit arrivals spread across the requested horizon; `--arrival-interval-ms`
  can override their spacing in positive multiples of 50 ms. `--population` accepts
  5..2048 planned people. The five pedestrian shares use exact integer allocation.
- Realized path progress with conservative swept-body following, stops and
  boundary/door admission. A derived local route-join gate coordinates FIFO body
  tokens and compatible through batches; it is source traffic coordination, not
  an aggregation merge or policy Region. Waiting does not reset a track. Return
  episodes begin
  after realized entrance arrival plus the declared indoor gap.
- Full body-envelope checks against the frozen derived walking/building geometry
  before the generated configuration is accepted. A 0.85-m facade transition
  disk and clipped domain boundary are explicit geometry exceptions; no physical
  doorway width or indoor floorplan is inferred.

For example, after building the current implementation:

```sh
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/run_scene.py \
  --motion-mode corridor --population 128 --duration-s 180 \
  --output results/mapped-corridor-new/scene --render --replay --port 8780
```

Fresh native corridor capture, route/body/lifecycle checks, same-clock replay
and browser inspection pass for the bounded reference; the current integration
report records the exact evidence. The denser finite-horizon case remains
explicitly censored, while its longer drain fixture finishes the planned episodes.
Do not substitute historical integration metrics for corridor results. This is a
bounded deterministic corridor model, not ORCA,
overtaking, free goal choice, a globally complete crowd solver, calibrated shopping
behavior or an empirical visit distribution. Large requests can cause admission
queues/stalls. The original four-route mode stays kinematic and bypasses the
legacy collision solver. Legacy simulation motion is preserved in both cases.

## Export or reopen an existing native run

The capture adapter reads only the three owned namespaces declared by a generated
configuration. It does not rerun aggregation:

```sh
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/export_replay.py \
  --scene results/YOUR_RUN/scene --output results/YOUR_RUN/replay-new
python3 -B tools/replay_viewer/serve.py \
  --bundle results/YOUR_RUN/replay-new --check
python3 -B tools/replay_viewer/serve.py \
  --bundle results/YOUR_RUN/replay-new --port 8780
```

Open `http://127.0.0.1:8780/`. A saved bundle remains playable after its databases
are removed. Existing output directories are never overwritten. Capture requires
a completed source summary, GT metadata, matching GT/raw AGBS cells, the native
release schema/stream identity, and a committed private-journal/recipient bijection.
It independently checks source counts, categories, hard policies and space/time
geometry. A lifecycle-event audit verifies the full visible GT set at every
source step, including times between sensor samples. The proof distinguishes
`source_horizon_completed` from `all_scheduled_episodes_completed`, records final
active/pending/stalled counts, and leaves historical missing diagnostics unknown.
Measured-empty samples rely on this coverage evidence and the sensor clock;
absent raw grid rows alone do not establish a measurement.

The browser allowlist serves observations, result JSON, manifest and the one
bounded local map PNG. Stable GT IDs, person↔track mappings, native raw records and
configuration are retained in `replay/private/`, outside that HTTP allowlist.
The bundle as a whole remains private research material: a recipient display
filter does not sanitize observations or thresholds for distribution.

## What to inspect

- Map geography, observed track types and output states have separate legends.
  Names come from frozen street/building/POI metadata. They are not verified current
  tenants, inferred destinations, entrance associations or automatic policy rules.
- **Show declared policy regions** overlays the configured rectangles in all three
  panels. OSM map colors and entrance circles are different context layers.
  Native live rendering still lacks the equivalent region-boundary/legend inspector.
- The policy overview lists root and regional declarations before any release.
  A selected cell shows the strict intersection of every positively intersected
  region, including provenance and conflicting bounds. These are declarations;
  unrecorded observed metric checks remain explicitly unavailable.
- Published **cell-windows**, unique spatial IDs, release events, visible original
  aggregates and clipped fragments are different quantities. Repeated publication
  of the same cell in another interval increases the first count, not the second.
  Native integration's historical 1,050 cell-windows use 77 spatial IDs.
- Released categories and separately enabled private source groups refer to the
  selected historical cell and its full interval. Current reference dots refer to
  the current sampled positions, not that historical window.
- Native journal capture exposes committed retirements, including empty private
  retirements. It does not contain active/rejected candidates; no failed-check,
  suppression or merge/split history is fabricated from their absence.

Focus zoom preserves world alignment. Rewind respects sealing/evaluation times,
clears future entries and never interpolates motion. Consult the detailed
[viewer contract](../replay_viewer/README.md) for asynchronous historical mosaics.

## Domain, identity and semantic scope

D6 in an 80-m sensing square gives 4,096 possible 1.25-m leaves. This footprint is
not the whole shopping street. The following single-door details describe the
historical modes; the current buildings mode is specified in the contract above. OSM entrance node 6244468529 lies on Rappolthaus
building way 43117523; residential use is unverified. No interior floorplan or
indoor movement is claimed. A visit temporarily removes the observed unit from
all sensors.

Private GT retains a stable synthetic person; sensors and aggregation receive a
fresh opaque track ID per visible episode. Neither appearances nor private person
links enter aggregation. Distinct tracks are not generally distinct people, and
resetting IDs does not exclude inference from location/time knowledge. The current
native source requires indoor gaps of 8/10 s to exceed retained history (6 s) and
candidate limits (4 s), with no additional native track fragmentation. Separate
identity interventions deliberately remove that simplifying identity assumption
without changing physical observations.

Adult, Child, Senior, Stroller and Mobility Aid terminals all truthfully generalize
to Pedestrian before Road User. Parent loss 0.5 and root loss 1 are configured
abstraction costs, not measured privacy percentages. All five profiles use
synthetic preferred speeds of 1.1–1.5 m/s. Their body radii differ: Adult 0.25 m,
Child 0.20 m, Senior 0.225 m, Stroller 0.45 m and Mobility Aid 0.35 m. These are
prototype assumptions, not calibrated demographic behavior. A mover plus equipment is one modeled
observed unit; a stroller occupant is not separately counted unless separately
modeled and observed. The historical source has exactly 64 people, 80 episodes
and 16 visits; these historical totals do not describe arbitrary corridor runs.

## Regional policy and overlap behavior

The scene uses four normal type/instance policy patches:

| Patch | Bounds, metres | Additional requirements |
|---|---|---|
| Entrance vicinity | x=20..30, y=65..75 | Track support ≥ 10 |
| West footway control | x=0..15, y=62.5..75 | Side ≤ 5 m; duration/age ≤ 1 s; semantic loss ≤ 0.5 |
| Central through footway | x=40..60, y=50..62.5 | Semantic loss ≤ 0.5 |
| East footway control | x=65..80, y=40..52.5 | Side ≤ 5 m; duration/age ≤ 1 s; semantic loss ≤ 0.5 |

Root requirements are total/category track support ≥ 5; cell side 1.25..10 m;
duration 400..4000 ms; interval-start age ≤ 4000 ms; semantic loss ≤ 1. Default
execution is Semantic First, Temporal First secondary, cell-local windows and
`policy_satisfied`. Any positive-area intersection applies a patch to the whole
candidate; even empty portions of the candidate carry regional requirements.

The compiler now accepts nested, identical and partially overlapping **D6-aligned
rectangles**. It combines every source, taking maximum lower bounds and minimum
upper bounds. Individually malformed rules or a root/type/instance contradiction
within one region still fail startup. Contradictions caused only by the conjunction
of individually valid regions are retained as infeasible spatial policies; they
cannot release data, while unaffected cells remain usable. There is no winning
region or area-weighted relaxation. Arbitrary polygons/misalignment still need
explicit preprocessing; the four default scene patches remain disjoint.

## Exact progress-clock fidelity

The native source progresses every 50 ms but measures every 100 ms. At a sample
time the native AGBS sensor first advances aggregation, then ingests the due batch;
ingestion appends history and advances again at that same logical time. The first
progress call is at zero, with no sensor observation at zero.

The replay CLI now supports explicit `--progress-step-ms 50` to reproduce this
call order, including ticks without measurements. The default CLI behavior stays
the historical sensor-cadence path. The explicit step must be a positive divisor
of the sensor period, not exceed it, and align the horizon; event counts are
bounded. Paced replay uses the same chosen progress clock. Extra progress ticks
never create measured-empty samples or additional observations. Both comparison
and identity tools derive this option from the saved native configuration.

## Same-input identity and method comparisons

Use fresh ignored output directories:

```sh
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/analyze_tracks.py \
  --recording results/YOUR_RUN/replay --output results/YOUR_RUN/identity-new \
  --binary simulator/build/AggregationReplay
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/run_comparison.py \
  --recording results/YOUR_RUN/replay --output results/YOUR_RUN/comparison-new \
  --binary simulator/build/AggregationReplay
python3 -B tools/replay_viewer/serve.py \
  --bundle results/YOUR_RUN/comparison-new --port 8781
```

The direct identity analyzer and `AggregationReplay` allow input and result documents
up to 2048 MiB (2 GiB), matching the mapped recorder allowance. Both still load
complete parsed documents; this is a file budget, not a constant-memory or browser
playback guarantee. The separate archival/Git-package helper
`tools/evaluation/replay_data.py` keeps its 256 MiB budget.

Identity analysis compares original episodes, 500/1000-ms fragments and an explicit
private GT-oracle reference. Positions, labels, sample opportunities and physical
movement stay fixed. It reports track/person support, inflation, threshold false
passes and a diagnostic concurrent-support alternative. The oracle is never a
runtime correction; concurrent support is not an online policy metric yet.
Original-episode reruns with the matching 50-ms clock reproduce native logical
releases in the checked integration source.

The method matrix is declared before result execution: two adaptive release
triggers and fixed 5/10-m × 400/1000-ms baselines. Hard root/region requirements and
taxonomy remain identical. A predeclared 10-m/1-s query bank evaluates exact answers
and separately marked uniform occupancy estimates at declared deadlines. Suppressed
support is unknown, never zero. The comparison viewer explicitly labels its
outputs as offline reruns rather than native recipient-stream capture. A single
seed/source is a bounded mechanism comparison, not statistical generalization,
a privacy gain, a universal baseline victory or a hard real-time guarantee. In the
checked historical mapped reference, immediate adaptation retains more observations
than the tested fixed settings, while a fixed grid/window answers more exact
queries in the predeclared bank. Large empty parts of that query domain remain
unknown without released support. These are different objectives; the current
integration report provides the full table.

## Reproduce checks and retain the next gates

```sh
/private/tmp/ump-mapped-venv/bin/python -B -m unittest discover \
  -s tools/mapped_scene -p 'test_*.py'
node tools/replay_viewer/test_model.js
python3 -B -m unittest discover -s tools/replay_viewer -p test_viewer.py
ctest --test-dir simulator/build --output-on-failure
```

The earlier `verify_scene.py --output NEW_DIRECTORY` remains a two-run native
integration audit: it renames only GT identities, checks full source/count/policy
agreement and cleans its owned six databases. It does not export motion files;
ordinary `run_scene.py` now intentionally retains local replay data.

The bounded fresh corridor acceptance is complete. Inspect actual density,
queued/active trips and stop tails before interpreting a larger population. Keep empirical privacy,
protected-unit/secret definitions, the three substantive scenarios and a renewed
whole-system correctness/performance review as separate gates. M03 specifically
retains history/merge checks, diagnostics and private empty-retirement publication
costs. Preserve logical output across optimization. Only compact aggregate reports
may be committed; full replay/GT/observations stay local under ignored `results/`.

## Experimental narrow-passage routing

Default storefront generation preserves the accepted coarse-lattice source. The
optional `--experimental-narrow-passages` flag (generator and `run_scene.py`,
storefronts only) enables a bounded exact polygon-visibility fallback after a
failed lattice query. It repairs static Barkhof connectivity without changing
hard clearance, road permissions, d6 or native movement. Construction metadata
records its mode, limits and unresolved native coordination gate.

Both frozen Barkhof directions and sparse 64-person native drainage pass. The
dense experimental 128-person gate exceeds its existing wall budget; a bounded
diagnostic shows prolonged local stops/repeated failed replans. Keep this mode
out of accepted comparisons until native opposing-flow coordination is validated.
The opt-in is a source change and requires a new recording. Existing recordings
and default source generation retain their old trajectories.

## Source classes and release categories

The general simulator uses `agents.road_user_taxonomy` in `simulator/config.yaml`.
This mapped fixture creates its own five `PROFILES` and `profiles()` in
`build_mapped_scene.py`; `corridor_people()` applies weights `[16,12,12,12,12]`.
Explicit `mapped_scene.people` determines generated types/speeds. Editing a
profile probability after generation does not regenerate those people. Cyclists
and scooters need their own supported movement geometry/behavior before inclusion.
The separate `aggregation.semantic_taxonomy` maps these inputs to release nodes;
its node costs are explicit, not inferred from depth. See the
[presentation protocol](../../docs/PRESENTATION_COMPARISON_PROTOCOL_2026-10-24.md)
for policy-matched baseline/ablation definitions and the meaning of a 0.5 ceiling.
