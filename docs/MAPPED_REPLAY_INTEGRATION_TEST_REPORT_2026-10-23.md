# Mapped replay, policy overlap and identity evaluation: integration report

Date: 2026-10-23. Implementation baseline: `46ae8ef`.
Machine: Apple Silicon macOS, Apple Clang 17, Release CMake build.
The [aggregate evidence](MAPPED_REPLAY_INTEGRATION_RESULTS_2026-10-23.json)
contains counts, fixed protocols and hashes; generated observations, paths,
native records, full replay bundles and private identity audits remain locally
under ignored `results/`.

## Outcome and scientific scope

The maintained Simulator now produces a persistent, inspectable mapped replay
with its actual AGBS measurements and committed native releases. Overlapping
selected Regions compile into the strict conjunction of their bounds. A separate
identity intervention demonstrates that fragmented tracks can satisfy numeric
track thresholds without satisfying the same thresholds on modeled people.

These are implementation and measurement results. They establish neither
k-anonymity nor empirical attack resistance. The comparisons report retention,
semantic detail, interval duration, query coverage and error jointly. They do
not establish that adaptivity always beats a fixed grid.

## Implemented path

1. `run_scene.py` generates a fresh configuration, executes the maintained C++
   `Simulator` in its scene directory, and captures its executable/configuration
   hashes, exit code and wall time. Default output is persistent under `results/`.
   MongoDB namespaces are fresh UUID-scoped databases. No existing database is
   reused. Cleanup of only the three owned databases is an explicit option after
   successful capture; none of the recorded runs below was deleted.
2. `export_replay.py` reads the source, raw AGBS, recipient and committed private
   journal collections. It independently reconciles positions, cell IDs, types,
   counts, semantic categories, root/regional bounds, journal retirements and
   immutable published space-time support. Recipient records and nonempty
   committed journal entries must agree exactly.
3. An event-driven audit reconstructs the visible track set at every source step,
   using actual half-open episode intervals. Missing states at unsampled 50-ms
   steps, hidden/ended tracks, duplicate events, overlapping episodes for one
   modeled person and inconsistent summary counts are rejected. Empty sensor
   frames are established from this source evidence and the sensor clock;
   missing raw AGBS rows alone never establish an empty measurement.
4. The replay browser reads these recorded observations and outputs. It displays
   the map at the same coordinates, supplied street/building/POI names, separate
   geography/type/output legends, Region footprints, the PolicyTree ID, effective
   constraints and their provenance. Cell inspection distinguishes current sample
   membership from support over a historical aggregation window.
5. `analyze_tracks.py` evaluates track/person discrepancies and can run controlled
   identity-only interventions through `AggregationReplay`. `run_comparison.py`
   executes a predeclared six-method matrix on one frozen recording, preserves
   all hard policies, and audits each result independently.

The browser distinguishes **published cell-windows**, **unique spatial cell IDs**,
**visible historical aggregates** and **geometry fragments**. The native `G`
overlay still shows the latest local decision rather than cumulative publication
history; its text now states that scope. Observed failed-candidate checks absent
from a native capture are shown as unavailable, never fabricated.

## Strict overlap semantics

For candidate footprint C and numeric metric m, all root bounds and all selected
Regions with positive-area intersection contribute:

\[
 L_m(C)=\max_{r\in\{root\}\cup R(C)} L_{m,r},\qquad
 U_m(C)=\min_{r\in\{root\}\cup R(C)} U_{m,r}.
\]

The bounds are feasible iff every resulting lower bound is no greater than its
upper bound. A conflict introduced by otherwise valid overlapping Regions is
retained as an infeasible effective policy on the affected footprint. Selection
fails closed there while valid neighboring support remains usable. Malformed
individual bounds and an individually incompatible root/Region pair still fail
configuration validation. Touching edges do not overlap. A coarse output cell
inherits every intersecting Region, including strict patches containing no
observations in that sample.

The compiler stops at homogeneous nodes covered in full by every relevant
Region, including multiple nested or coincident Regions. It remains sparse.
An independent D6 oracle checked **4,096 leaves and 1,364 nonroot ancestors**
(5,460 cells) per OSM export, with an additional overlapping Region. All three
frozen OSM exports retained their previous compiled node counts: 5,197 / 4,889 /
5,077 for overview/detail/close. Controller regression preserves nine valid
neighbor contributions and suppresses nine in the deliberately conflicting patch.

## Progress clock correction

A 50-ms simulator step and a 100-ms sensor measurement cadence are different
clocks. Previously, replay progressed only at sensor timestamps. Independent
local windows could therefore close differently even on identical observations.

Explicit `AggregationReplay --progress-step-ms 50` reproduces native ordering:
advance at zero; advance on each numerical tick; at measurement timestamps,
advance before ingesting the actual batch. It creates no new measurements or
position interpolation. Legacy replay behavior remains unchanged without the
option. The mapped identity/comparison tools use the actual source progress
step. The original-episode reference replay exactly matches native logical
releases, as does the GT identity oracle. The reference logical release SHA-256
is `422a238a32368b5e65706d51bc5e45d844fdb15df5891b37a35a05a8ef8d9175`.

## Bounded corridor motion and discovered failure

The new optional source uses the existing Simulator/Agent/sensor/publication
pipeline. Seeded individual polylines have bounded lateral variation and exact
portal endpoints; source requests are distributed over time. Geometry validation
uses the declared swept body plus clearance, with explicit exceptions for a
0.85-m facade transition disk and domain-edge clipping; it does not establish
physical doorway width or an indoor floorplan. Finite body radii,
clearance, source/door admission and conservative swept-polyline reservations
produce actual stops and velocities. Returns occur after an 8- or 10-s indoor
gap measured from the realized preceding arrival and receive a new visible ID.
The private stable modeled-person ID remains evaluator-only.

The first 128-person / 500-ms source developed a permanent building-exit merge
blockade. Its 180-s capture had 42 stalled active tracks, 24 pending episodes
and a 144.35-s maximum stop. That capture remains a diagnostic artifact; its
high retention is not evidence of an improved anonymization mechanism.

The fix reserves the branch/through-flow merge before conflicting bodies enter.
Requests use first eligible request time and opaque-ID ties; compatible through
traffic uses finite batches. An exiting track keeps its token until its complete
inflated body and swept path clear the zone. A dedicated fast-crossing regression
checks that crossing a whole zone in one step still latches and releases ownership.
The exact failing configuration now drains **160/160 episodes by 335.85 s**, with
zero body overlaps, missing episodes or remaining active/pending tracks. Normal
and ASan/UBSan runs agree. Maximum stop is still **64.5 s**.

This is a conservative bounded source model. Merge geometry is derived once
from an aligned portal-route join, using a 2-m zone plus body radius and clearance;
it is unrelated to a PolicyTree Region or Quadtree cell. It is not ORCA, free
lateral overtaking, calibrated pedestrian traffic or a globally complete crowd
solver. Arbitrary opposing paths, overlapping resources and infinite-inflow
starvation have no general liveness guarantee.

## Native source runs and same-source comparisons

The historical 90-s integration fixture is preserved. Fresh corrected corridor
runs use seed 20261023, 80 × 80 m, D6, 50-ms source steps and 100-ms sensing.
They have 64 people / 1,000-ms source requests and 128 people / 500-ms requests,
respectively; population is a finite scheduled cohort, not simultaneous occupancy.
The latter is censored at 180 s, although the separate 360-s core drain completes.
Preferred speeds are sampled uniformly from 1.1–1.5 m/s for every type. Body radii
are Adult 0.25 m, Child 0.20 m, Senior 0.225 m, Stroller 0.45 m and Mobility Aid
0.35 m; these prototype profile choices are not empirically calibrated.

All methods keep the same root support/category support of five, 400–4,000-ms
candidate durations, 1.25–10-m output sides, six-second history, semantic taxonomy
and four regional overrides. Entrance support is ten; west/east control Regions
require at most 5-m cells and one-second duration/age with semantic loss at most
0.5; the central through Region caps semantic loss at 0.5. These are illustrative
application policies, not empirically validated privacy guarantees.

The matrix consists of adaptive immediate release, adaptive semantic-priority
waiting, and fixed 5-/10-m grids with 400-/1,000-ms windows. Fixed methods retain
permitted semantic generalization. They do not receive weaker policies, so a
fixed 10-m output cannot bypass a local 5-m cap.

The recipient workload is fixed before results: all 64 D3 cells, all seven
semantic nodes, one-second intervals and lags 0/1,000 ms. It contains 80,640
queries for the 90-s source and 161,280 for each 180-s source. The 200,000-query
resource cap is checked before running a method in the current runner. The
historical 90-s matrix used the earlier 100,000-query cap, sufficient for its
80,640 queries; increasing the cap does not change query selection or outcomes. Exact answers use conservative
complete public-tile containment. Uniform spatial/temporal estimates are scored
separately. Missing output stays unknown, including in empty source areas.

### Executed native counts

| Source | Measured contributions | Published cell-windows | Unique spatial IDs | Native retention | Completed episodes / scheduled |
| --- | ---: | ---: | ---: | ---: | ---: |
| Historical integration, 90 s | 38,709 | 1,050 | 77 | 87.04% | 80/80 |
| Corridor 64, 180 s | 47,706 | 509 | 16 | 32.57% | 80/80 |
| Corridor 128, 180 s | 112,565 | 2,615 | 42 | 80.23% | 118/160 |

The corrected 64-person capture has zero pending/active/stalled tracks at its
horizon, a 9.35-s maximum stop, and zero reported body overlaps. The corrected
128-person capture has 151 starts, 118 ends, 33 active and nine not-yet-started
episodes at its horizon; no active track is marked stalled there and reported
body overlaps are zero. It is explicitly labeled censored. Native and offline
immediate logical release hashes match for **all three sources**.

### Actual fixed/adaptive outcomes

Coverage below refers to all interior queries at the 1,000-ms lag, including all
seven categories and areas with zero source occupancy. MAE is evaluated only
where a separate uniform estimate is available. Coverage and cohort size must
accompany MAE; different methods can answer different subsets.

| Source | Method | Retention | Mean interval ms | Mean semantic loss | Exact query coverage | Exact + estimate coverage | Estimate occupancy MAE |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Historical integration, 90 s | `adaptive_immediate` | 87.04% | 521.6 | 0.5000 | 0.0000% | 0.3399% | 0.1000 |
| Historical integration, 90 s | `adaptive_semantic_wait` | 89.20% | 2888.9 | 0.4901 | 0.0000% | 0.1040% | 1.4204 |
| Historical integration, 90 s | `fixed_5m_400ms` | 74.33% | 400.0 | 0.5000 | 0.0000% | 0.0000% | unavailable |
| Historical integration, 90 s | `fixed_5m_1000ms` | 78.07% | 1000.0 | 0.5000 | 0.0000% | 0.0000% | unavailable |
| Historical integration, 90 s | `fixed_10m_400ms` | 39.26% | 400.0 | 0.5000 | 0.0000% | 0.5377% | 0.0538 |
| Historical integration, 90 s | `fixed_10m_1000ms` | 40.47% | 1000.0 | 0.5000 | 0.6443% | 0.6443% | 0.0000 |
| Corridor 64, 180 s | `adaptive_immediate` | 32.57% | 994.0 | 0.5000 | 0.0000% | 0.4590% | 0.1059 |
| Corridor 64, 180 s | `adaptive_semantic_wait` | 48.17% | 3853.6 | 0.5000 | 0.0000% | 0.2257% | 0.7067 |
| Corridor 64, 180 s | `fixed_5m_400ms` | 15.14% | 400.0 | 0.5000 | 0.0000% | 0.0000% | unavailable |
| Corridor 64, 180 s | `fixed_5m_1000ms` | 18.64% | 1000.0 | 0.5000 | 0.0000% | 0.0000% | unavailable |
| Corridor 64, 180 s | `fixed_10m_400ms` | 29.92% | 400.0 | 0.5000 | 0.0000% | 0.4038% | 0.0298 |
| Corridor 64, 180 s | `fixed_10m_1000ms` | 32.21% | 1000.0 | 0.5000 | 0.5267% | 0.5267% | 0.0000 |
| Corridor 128, 180 s | `adaptive_immediate` | 80.23% | 562.1 | 0.5000 | 0.0000% | 1.1136% | 0.0819 |
| Corridor 128, 180 s | `adaptive_semantic_wait` | 80.89% | 3096.4 | 0.4976 | 0.0000% | 0.4427% | 0.6708 |
| Corridor 128, 180 s | `fixed_5m_400ms` | 51.56% | 400.0 | 0.5000 | 0.0000% | 0.0226% | 0.0222 |
| Corridor 128, 180 s | `fixed_5m_1000ms` | 57.75% | 1000.0 | 0.5000 | 0.0426% | 0.0426% | 0.0000 |
| Corridor 128, 180 s | `fixed_10m_400ms` | 37.72% | 400.0 | 0.5000 | 0.0000% | 0.9305% | 0.0349 |
| Corridor 128, 180 s | `fixed_10m_1000ms` | 39.04% | 1000.0 | 0.5000 | 1.0759% | 1.0759% | 0.0000 |

Immediate adaptivity retains 80.23% in the dense corridor source versus 57.75%
for fixed 5 m / 1 s, while the latter preserves some exact one-second answers
and the adaptive output answers none of this conservative exact workload. Fixed
10 m / 1 s reaches 1.0759% exact query coverage versus 1.1136% exact-plus-estimate
coverage for immediate adaptivity, with nonzero estimation error for the latter.
This is a retention/representation tradeoff, not a blanket utility victory.
Large empty portions of the full-area workload and unpublished zero cells make
absolute query coverage low; absent public support must not be imputed as zero.
A corridor-focused application workload is a subsequent experiment, not a
replacement chosen retrospectively to improve these results.

Semantic-priority waiting improves retention but substantially lengthens
intervals. The dense variant preserves a small amount of terminal detail; most
outputs remain `pedestrian` with declared taxonomy cost 0.5. This ordinal cost is
not a measured privacy risk or a claim of 50% anonymous information.

## Controlled track-fragmentation evaluation

Only observation identity labels change. Positions, types, batches, coverage,
cadence and occupancy hashes remain fixed. Global 500-/1,000-ms fragmentation
boundaries are an artificial stress intervention, not measured tracker errors.
The GT person-ID variant is a privileged evaluator reference and is never fed
back into operational sensing or aggregation.

| Identity variant | Published cell-windows | Retention | Cells with track/person support inflation | Person-threshold false-pass cells |
| --- | ---: | ---: | ---: | ---: |
| Original episodes / native | 1,050 | 87.04% | 0 | 0 |
| 1,000-ms fragments | 1,395 | 93.90% | 674 | 432 |
| 500-ms fragments | 1,811 | 92.37% | 1,377 | 910 |
| GT evaluation oracle | 1,050 | 87.04% | 0 | 0 |

Category-level false-pass bins are 460 and 925 for the two fragment conditions.
Their maximum track/person support ratios are three and five. These remain valid
operational **track** checks; a false pass means the same numeric threshold would
fail if evaluated on modeled people. It does not mean a real person was attacked
or identified. The observed retention increase can therefore accompany inflated
support and must not be interpreted as a privacy improvement.

A separate diagnostic peak simultaneous-person support would reject 67 native
cell-windows. It measures something different from distinct support accumulated
over a window and is not installed as an online policy metric by this change.
The mapped source still requires hidden gaps longer than retained history; it
does not solve arbitrary reappearances within one retained window.

## Verification

| Gate | Result |
| --- | --- |
| Complete CMake build | Passed, all enabled targets including Simulator and AggregationReplay |
| Final complete CTest run | **81/81 passed**, 15.89 s elapsed, `-j 6` |
| Mapped geometry/generator Python tests | 12 passed, including generated exact dense-config drain via the compiled core |
| Export/source/journal/lifecycle Python tests | 31 passed |
| Track-support analyzer Python tests | 12 passed, including four real C++ interventions |
| Same-recording comparison Python tests | 15 passed; orchestration failure/provenance/budget tests use a mocked executable |
| Viewer model / HTTP validation | 63 JavaScript + 50 Python tests passed |
| Actual native source/capture runs | Historical integration + fresh 64/128 corridor sources verified independently |
| Actual method comparison | 18 C++ method executions across three frozen sources; all independent audits pass |
| Actual identity interventions | Four reference-source C++ executions; preserved physical/count invariants |
| Policy overlap checks | Independent exhaustive leaf/ancestor oracle, normal controller regression and ASan/UBSan pass |
| Corridor motion sanitizers | Core, YAML adapter and exact dense-config drain pass ASan/UBSan |
| Browser acceptance | Native mapped replay and dense same-source comparison inspected in Chrome |
| Whitespace/diff checks | Passed before staging |

The final 81-suite run includes the four optional mapped Python suites and the
existing core, sensor, frame, timing, publication, semantic, history, coordination,
privacy-tool and replay regressions. This does not turn historical/offline privacy
tests into a new privacy guarantee for the mapped source.

New overlap tests cover partial/nested/identical Regions, touching edges, input
order, full provenance, empty strict patches, ancestor footprints, cross-region
conflicts, unaffected neighbors and sparse high-depth compilation. Replay clock
tests compare directly with native-style CellLocal calls, reject invalid clocks,
check measured-coverage conservation and compare paced/unpaced results.

Recorder tests reject source omissions at sensor and non-sensor timestamps,
incorrect half-open boundaries, duplicate/mismatched lifecycle events, journal
and recipient mismatches, count/category/policy violations, and record motion
censoring separately from source-horizon completion. Shared viewer tests cover
bounded PNG decoding, geometry/provenance inspection, rewind and private gating.

ASan/UBSan used `-std=c++17 -O1 -g -fno-omit-frame-pointer
-fsanitize=address,undefined -fno-sanitize-recover=all` on the executed mapped
standard-C++ core/adapter and policy regression paths. The three mapped sanitizer
executions exited zero without diagnostics. The linked Homebrew yaml-cpp itself
was not rebuilt with sanitizers. No TSan, whole-native multithreaded sanitizer
run, exhaustive geometric proof or separate leak guarantee is asserted.

Browser acceptance at 72 s in the dense comparison showed **122 current tracks
at 122 distinct coordinates**. Adaptive A displayed 1,225 published cell-windows
so far using 34 spatial IDs; fixed 10 m / 1 s B displayed 209 cell-windows using
six IDs. Selected adaptive cell 930 correctly showed west-footway limits of 5 m
and 1 s with root/Region provenance. At EOF, adaptive totals were 2,615 windows,
42 spatial IDs and 90,307/112,565 retained contributions; fixed B totals were
431 windows, six IDs and 43,943/112,565 contributions. Rewinding removed later
releases. At EOF there is no sensor sample at the horizon itself; zero displayed
current sample IDs must not be interpreted as completed journeys.

## Runtime and process review

Recorded native wall times were 27.159 s for the 180-s 64-person run and 49.268 s
for the 128-person run: end-to-end simulated-time/wall-time ratios of 6.63 and
3.65. These include startup and MongoDB I/O, and some verification processes ran
concurrently. They are recorded execution characteristics, **not controlled
benchmarks or per-step realtime deadline guarantees**. Offline immediate-core
processing was 14.316 / 21.328 s for these recordings, likewise not a native
sensor-to-recipient latency claim.

The initial review found and fixed three consequential process problems:
replay/native progress ordering, overlapping-policy compilation, and motion merge
liveness. It also found that numerical completion alone overstated source quality;
event/GT audits and explicit lifecycle/motion fields now expose that distinction.
The large number of private empty retirements remains a measured next profiling
target: 46,597 of 47,106 retirements in the corrected 64-person capture are empty.
No storage/history optimization or policy weakening was used to improve these
numbers. Export byte/row limits are bounded serialized-artifact checks; the
exporter materializes collections and does not promise a hard process-RSS cap.

## Reproduction

Use a Python environment satisfying `tools/mapped_scene/requirements.txt`, called
`PYTHON` below, with local MongoDB and `mongosh` available. Pick new output parents;
existing captures are immutable and never overwritten.

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release \
  -DUMP_MAPPED_SCENE_PYTHON="$PYTHON"
cmake --build simulator/build -j 6
ctest --test-dir simulator/build --output-on-failure -j 6

"$PYTHON" tools/mapped_scene/run_scene.py --motion-mode corridor \
  --duration-s 180 --population 64 --arrival-interval-ms 1000 \
  --seed 20261023 --output results/fresh-corridor64/scene
"$PYTHON" tools/mapped_scene/run_scene.py --motion-mode corridor \
  --duration-s 180 --population 128 --arrival-interval-ms 500 \
  --seed 20261023 --output results/fresh-corridor128/scene

"$PYTHON" tools/mapped_scene/run_comparison.py \
  --recording results/fresh-corridor128/replay \
  --output results/fresh-corridor128/comparison
python3 -B tools/replay_viewer/serve.py \
  --bundle results/fresh-corridor128/comparison --port 8784

simulator/build/MappedSceneConfigurationTests \
  --drain-config results/fresh-corridor128/scene/config.yaml --end-ms 360000
```

Identity stress interventions use the 90-s historical integration recording:

```sh
"$PYTHON" tools/mapped_scene/run_scene.py --motion-mode integration \
  --duration-s 90 --seed 20261023 --output results/fresh-integration/scene
"$PYTHON" tools/mapped_scene/analyze_tracks.py \
  --recording results/fresh-integration/replay \
  --output results/fresh-identity-study \
  --binary simulator/build/AggregationReplay
```

The local accepted artifacts are `results/mapped-2026-10-23-corridor64-final`,
`results/mapped-2026-10-23-corridor128-final`, the frozen historical
`results/mapped-2026-10-23-integration/comparison-clock50` and
`results/mapped-track-support-clock50-2026-10-23`. Older failed or mismatched-clock
captures remain diagnostic evidence and must not be presented as these final runs.
The [run guide](../tools/mapped_scene/README.md) documents re-export, explicit DB
cleanup, visualization, local storage and optional test dependencies.

## Remaining priorities

1. Review correctness, timing and state/retirement accounting across the entire
   current mechanism, then profile empty-retirement DB I/O, candidate/history
   work, per-tick tails and memory with isolated repeated workloads.
2. Define a predeclared corridor/application query mask and three substantive
   scenario protocols with repetitions, localized policies and matched fixed-grid
   references. Report suppression, semantic detail, delay, error and coverage
   together; retain the current full-area outcomes as an honest reference.
3. Decide the protected unit, sensitive attributes, attacker knowledge and actual
   disclosure metric before interpreting policy-support counts as privacy gain.
   Person continuity remains unavailable to the operational sensor after a visit;
   private GT can evaluate that limitation without silently repairing it.
4. Calibrate pedestrian influx/visits and address corridor capacity before stronger
   realism claims. Arbitrary polygon rasterization, city routing, ORCA, native
   regional overlays and a configurable GUI remain separate extensions.
