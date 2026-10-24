# Navigation geometry fast path and clean replay labels — 2026-10-24

## Result and scope

The first movement-cost reduction is implemented and verified against source
commit `d64842a`. The complete 500-person cohort retains identical raw-bit source
output and lifecycle. Its fresh source-only wall time decreases from **213.300 s
to 155.893 s (26.9%)**. All **86 CTest suites pass** in 225.33 s; the full configured
build passes. Replay cleanup is committed separately as `46ecb91`.

Read the [compact aggregate evidence](NAVIGATION_GEOMETRY_RESULTS_2026-10-24.json),
[CTest log](verification/navigation-geometry-ctest-2026-10-24.log) and
[ordered environment roadmap](MULTIMODAL_MAP_ROADMAP_2026-10-24.md).
No generated movement or GT is added to Git.

## Implemented change

`MappedScene.cpp::ringLocation` previously calculated point-to-segment distance
for every edge of every queried ring. A conservative edge bounding box now skips
that distance calculation when the point is far from the edge. Padding is the
existing 1e-8-m boundary tolerance plus coordinate-scaled floating-point slack.
The original strict distance predicate and ray-crossing arithmetic/order still
make the boundary/containment decision. Padding can cause an extra original check;
it never independently authorizes a point. Segment-cut intersection arithmetic,
physical clearance, routes, steering, collision reservations, doors, policies,
metrics and aggregation decisions are unchanged.

This is an inline boundary-distance prefilter, not a prepared spatial index or a
free-space cache. Ring traversal remains O(edges). Nearby-body indexing, threading
and GPU changes are not included. The small fast path adds no persistent geometry
state, configuration flag or public schema field.

## Equivalence verification

The new `tools/profiling/check_navigation_equivalence.py` builds the baseline and
working native source with identical current headers/configuration reader. It
SHA-256 hashes canonical binary stdout directly; raw oracle/motion records are
never written to disk. The frame stream includes every 50-ms sample, raw double
bits for positions/velocities, track/type/route/waypoint, all 15 diagnostics per
step and the complete private lifecycle. Configurations and source hashes are
checked for changes during execution. Both cohorts must finish.

| Fixed cohort | Horizon | Compared frames | Visible records | Completed episodes |
|---|---:|---:|---:|---:|
| 64 people, 1-s requests | 240 s | 4,801 | 85,207 | 96 / 96 |
| 500 people, 1-s requests | 750 s | 15,001 | 691,009 | 750 / 750 |

Every stream matches exactly. Last completions remain 186.900 and 630.950 s,
respectively. Both gates have zero active/pending/stalled tracks and no reported
physical overlap. Private person/visible-track separation and indoor return timing
remain unchanged. This is exact equality for these finite corpora, not a universal
proof over every floating-point input or an independent privacy guarantee.

Geometry probes also match: **399,480 ring classifications, 122,440 complete
segments and 160,000 polygon checks** for each actual/synthetic geometry set. The
same scene geometry is exercised in both cohorts; these are not two independent
maps. Coverage includes original rings/holes, boundary vertices, normal offsets,
values around the strict tolerance, next-representable coordinates, unions,
long segments and scales from 1e-6 to 1e12. A small native smoke and invalid-input
guards pass. No test-only hook is inserted into production code.

## Fresh source-only timing pairs

Host/compiler/harness match the prior [capacity report](NAVIGATION_SCALABILITY_REPORT_2026-10-24.md):
Apple M4 Pro, 24 GiB, Apple clang 17, `-O3 -DNDEBUG`, serial native execution.
The baseline binary is retained from the earlier cohort probe and verified against
its recorded binary/source/harness hashes. The working binary uses the identical
uninstrumented harness. Each exact saved configuration runs before then after,
with no other agent benchmarks/builds running concurrently. No route regeneration
or workload change is substituted for the timed input. This is one fresh pair per
case, not a counterbalanced repeated study or confidence interval.

| Cohort / horizon | Wall before → after | Mean step before → after | p95 before → after | p99 before → after |
|---|---:|---:|---:|---:|
| 64 / 240 s | 17.864 → 11.928 s | 3.716 → 2.478 ms | 11.539 → 7.879 ms | 12.678 → 8.926 ms |
| 500 / 750 s | 213.300 → 155.893 s | 14.201 → 10.376 ms | 22.034 → 16.754 ms | 84.414 → 55.500 ms |

Wall reductions are 33.2% and 26.9%. All recorded workload/finish counters match.
The 500-person pair retains peak 81 active, 709 replans/589 failed attempts and
3.150-s maximum zero-motion stop. All episodes ultimately finish. Over-50-ms steps
decrease from 389 to 332 of 15,000; maximum is still 110.570 ms after optimization.
The 64-person pair has no over-50-ms step. Both horizons include drain/empty periods;
the 500-person horizon includes 119.05 s after its last completion, so whole-run
means are lower than busy-period costs.

Do not combine the equality verifier's stream/serialization timing with this pure
source timing pair. The older 207.09-s baseline and this fresh 213.30-s baseline
are separate runs. The comparison excludes sensors, aggregation, MongoDB, rendering
and paced external receipt. It establishes a bounded source improvement, not a
full-pipeline or worst-case realtime guarantee. Full native MongoDB publication
capture was not repeated for this small geometry-only change; source equality and
the existing publication/aggregation regression suites are the gates here.

## Replay cleanup and language responsibilities

The numbered white shop-name boxes and entrance-to-label construction leaders
are removed. Shop names again use ordinary supplied-map typography and POI
positions, independently of entrance highlighting. Exact entrance markers,
original building outlines, modeled frontage edges and short divider ticks keep
their existing toggles. Normal displaced geography-label leaders remain part of
ordinary label collision avoidance. No map or observation bundle was regenerated.

74 JavaScript checks and 63 Python viewer/server methods pass; both viewer CTests
also pass within the full 86-suite run. A behavioral canvas regression checks the
actual renderer's ordinary shop name and independence from entrance markers.
Chrome inspection at 50 s shows 40 recorded tracks at 40 distinct positions,
normal shop labels and no numbered white entrance callouts in all three panels.
The local screenshot is `/private/tmp/ump-clean-shop-labels-20261024.jpg`.

JavaScript renders recorded data and computes display summaries, source-group
inspection, historical mosaics and declared-bound intersections. C++ runs native
motion/sensors, online metrics and aggregation/publication decisions. Python
prepares map/global routes and handles orchestration, export and offline studies.
The browser does not integrate trajectories or make online release decisions.

## Pending environment work

The user-identified upper-left and Elbphilharmonie Kultur Café entrances exist in
the frozen source but are absent from the four active shop portals. Their exact
nodes, positions, floor/access/connector gates and inferred destination association
are documented in the roadmap. Additional entrances, bidirectional door capacity,
Barkhof connectivity repair, distributed free crossings, wall/corner comfort and
mixed traffic remain explicit implementation tasks. No new entrance, crossing or
comfort behavior is claimed by this optimization report.

## Reproduce exact source equality

Create the frozen inputs with the mapped-scene Python environment described in
`tools/mapped_scene/README.md`; the source-only verifier itself uses standard
Python plus the existing native compiler/yaml-cpp. Choose fresh local directories.

```sh
MAPPED_PYTHON tools/profiling/benchmark_mapped_navigation.py \
  --output results/navigation-inputs-new --generation-only \
  --cases 64:1000,500:1000 --horizon-s 120 --seed 20261023
python3 tools/profiling/check_navigation_equivalence.py \
  --baseline-ref d64842a --output results/navigation-equivalence-new \
  --config results/navigation-inputs-new/people-64-arrival-1000ms/config.yaml \
  --config results/navigation-inputs-new/people-500-arrival-1000ms/config.yaml \
  --horizon-s 240 --horizon-s 750 --random-probes 10000 \
  --wall-budget-s 420 --require-complete
cmake --build simulator/build -j 4
ctest --test-dir simulator/build -j 1 --output-on-failure
```

Replace `MAPPED_PYTHON` by the mapped-scene Python executable. The 120-s generation
field is only the capture duration; the pure source harness explicitly advances
the same scene to the listed longer horizons. Aggregate evidence retains exact
configuration/compiler/source/binary/harness hashes and timing compile commands.
Keep instrumented component timings and output-stream verification timing separate
from uninstrumented source benchmarks.
