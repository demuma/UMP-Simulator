# Native navigation capacity and policy-view labeling — 2026-10-24

This follow-up measures the source introduced in `74977a1`. It does not change
movement, policies, publication or frozen observations. The only product change
is more accurate replay labeling. Read the [compact aggregate evidence](NAVIGATION_SCALABILITY_RESULTS_2026-10-24.json)
and [ordered environment roadmap](MULTIMODAL_MAP_ROADMAP_2026-10-24.md).

## What the replay actually compares

A recorded result variant can change its PolicyTree, execution strategy, window
coordination, release trigger or several of these. A result variant is not itself
a distinct PolicyTree. The current storefront recording has one native result and
one tree, `mapped-entrance-illustrative-policy`, version `1`. Both selected panes
therefore show the same result.

Headings now display the actual tree ID/version. A separate line gives the
recorded method/strategy and output/window mode. Selectors, selected-cell focus,
inspectors, policy overview, event lanes and accessibility labels use that identity.
A notice distinguishes identical selections, a common declared tree/version and
different declared tree IDs. A shared name alone does not prove identical regional
constraints; their declarations remain inspectable. Unknown or mixed legacy
identities stay explicit. Internal A/B values remain stable view locators.

Policy identity is read from supplied metadata or uniquely recorded release/journal
rows. No missing version is invented. Frozen JSON bundles and movement are unchanged.

Validation: 73 JavaScript model checks and 63 Python viewer/server methods pass,
including identity/version fallback, mixed/missing identity and method separation.
Both affected viewer CTests pass in 2.01 s. Chrome inspection of the retained replay at
http://127.0.0.1:8787/ confirms tree `v1`, the Semantic First method, the same-result
notice, aligned maps and the unchanged 50-s sample (40 tracks/40 coordinates).
The local proof screenshot is `/private/tmp/ump-policy-tree-replay-20261024.jpg`;
it is excluded from Git. The prior full 86-suite result belongs to the preceding
checkpoint; only affected suites were rerun for this labeling change.

## Method and limits of the capacity probe

Host: Apple M4 Pro, 24 GiB RAM, macOS 15.7.7, Apple clang 17, serial native code
compiled with `-O3 -DNDEBUG`. Cases run sequentially with no concurrent full builds
or other benchmark cases. Seed is 20261023. The source uses the frozen 80-m domain,
0.5-m navigation lattice and unchanged pedestrian profiles/policies. D6 aggregation
cells are unrelated to the navigation grid.

The harness times `advanceTo` and `frameAt` separately at 50-ms source steps. It
has no sensor, aggregator, MongoDB, renderer or live scheduling loop. An empty
or unfinished tail cannot establish successful navigation. Every case records
starts, ends, active/pending/stalled tracks and censoring. Percentiles use nearest
ranks over the observed steps; they are measurements from one run, not capacity
confidence intervals or hard deadlines.

The requested horizon is 120 simulated seconds and the wall budget is 180 s per
case. A budget is checked after each complete motion step. A process watchdog also
bounds failures; an unfinished step is not silently counted as a successful sample.
The 500-person stress reaches 66.85 s and stops at its wall budget. It has not even
reached the final first-arrival request at 74.85 s.

A cohort is the total configured population; it is not simultaneous occupancy.
The two 500-person inputs share exact routes, geometry, profiles, speeds, policies
and horizon, differing only in 499 first-episode start timestamps. Across different
population sizes, seeded type/path streams depend on population. This matrix is a
diagnostic, not a controlled causal fit of cost against N.

## Measured source-step costs

| Configured people / request interval | Peak active | Mean step | p95 step | p99 step | Maximum | Steps >50 ms |
|---|---:|---:|---:|---:|---:|---:|
| 64 / 1,000 ms | 55 | 6.328 ms | 11.426 ms | 12.200 ms | 45.511 ms | 0 / 2,400 |
| 128 / 1,000 ms | 66 | 9.689 ms | 15.948 ms | 17.579 ms | 56.062 ms | 5 / 2,400 |
| 500 / 1,000 ms | 65 | 11.368 ms | 16.383 ms | 73.181 ms | 132.219 ms | 49 / 2,400 |
| 500 / 150 ms | 369 | 134.545 ms | 336.748 ms | 409.141 ms | 613.239 ms | 928 / 1,337 |

These costs are for motion alone. They do not reserve time for aggregation or
external writes. The stress run needs 180.017 wall seconds for 66.850 simulation
seconds, about 0.371× throughput. During its 40–66.85-s segment, all 537 steps
exceed 50 ms, with mean 249.05 ms. A claim of realtime operation with 500 concurrent
actors is unsupported; substantial overruns already occur before that occupancy.

At the stress cutoff: 452 episodes started, 83 ended, 369 remain active and 298
are pending. Pending includes future scheduled first episodes and returns, not
only an admission queue. Eight active tracks satisfy the source's stall diagnostic;
maximum consecutive zero-motion stop is 11.7 s. No body-overlap violation was
reported. This is a censored stress observation, not a finite-drain acceptance or
an independent all-position audit such as the prior 64-person capture.

The 500/1-s case exercises only the early part of that cohort. Its low peak of 65
cannot demonstrate 500 simultaneous actors. Differences from the 128-person case
also involve routes/types and 109 versus 24 replans; they are not evidence of a
pure pending-track overhead effect.

## Where the computation occurs

Global guidance is built before native execution. It includes frozen-map loading,
functional geometry, body-safe erosion, a navigation lattice, endpoint reachability,
A* routing, seeded variation, simplification and exact route audits. It takes about
5 s for 64 people and 21 s for 500 here. A separate generation-only repeat for 500
records 750 varied routes and 2,291 route calls: route methods consume 12.57 s and
final route audit 6.30 s within a 21.25-s total. These are inclusive timers: varied
routes invoke route methods, so their times must not be added. Imports, cached
source reads and machine state are part of these particular measurements; no map
download is timed.

Online motion evaluates 29 velocity/wait candidates per active track, exact map
containment, conservative swept-body reservations and predicted encounters. The
map has 528 serialized ring vertices, including three repeated closing vertices;
the normalized runtime has 525 edges. Pair checks and prediction loops grow with
active population; current loops do not use a movement-neighborhood spatial index.
A blocked agent can invoke bounded dynamic A*, up to 20,000 expanded nodes. Each
search edge still performs geometry/body checks; a node bound is not a time bound.

A separate instrumented 64-person run spends 12.127 s in 2,342,803 navigation
segment checks within 16.19 s total, approximately 75%. Replanning consumes
0.484 s and door updates 0.047 s, both inclusive of nested geometry work. The
instrumentation adds overhead and is not an optimized variant. Its configuration
and all 19 recorded discrete workload/counter fields agree with the pristine run.
It does not separately attribute the dense case's pair costs.

`frameAt` is small: approximately 0.0033 ms mean for the 64-person case and
0.0382 ms in stress. YAML/adaptation/constructor costs are separately recorded.
Adaptation includes validation through a temporary scene construction; the explicit
constructor timer measures another construction, not an isolated field-copy cost.

The first optimization candidate is an exact static-geometry broad phase or a
conservatively certified free-space cache, followed by nearby-body indexing.
Fast paths must agree with the current full geometry oracle around walls, holes,
door transitions and boundaries; dynamic body results cannot be cached as static.
Candidate/tie ordering and all frozen source/publication outputs must remain stable.
Motion/route changes, denser demand and different policies are separate experiments.

## Reproduce

Use the existing mapped-scene Python environment and current compiler/yaml-cpp.
The benchmark's native build currently targets the maintained macOS/Homebrew setup.
Use a fresh ignored directory; configs and temporary binaries remain local.

```sh
/private/tmp/ump-mapped-venv/bin/python tools/profiling/benchmark_mapped_navigation.py \
  --output results/navigation-capacity-new \
  --cases 64:1000,128:1000,500:1000,500:150 \
  --horizon-s 120 --wall-budget-s 180
```

`--generation-only` isolates preprocessing; `--instrument-components` stages a
separate temporary native source copy with inclusive timers. Never substitute
instrumented timings for the pristine matrix. The exact original harness/binary
hashes and the later current reproducer hash are labeled separately in the evidence:
the runner gained component wrappers, dependency metadata and reuse guards after
the pristine measurements. No earlier result is relabeled as generated by that
later revision. Production dependencies remain unchanged.

The final five-person/one-second smoke passes in generation-only and native modes
with equal config hashes. Nonfinite/nonpositive budgets, overwrites, changed binaries
and stale harnesses are rejected. Full sampled motion or GT is not exported or
committed; only aggregate evidence accompanies the reusable tool.
