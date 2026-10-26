# Doorway source correction: bounded attachment to the local navigation grid

Date: 26 October 2026. Status: **implemented and validated in the declared DEV
scope: 92/92 motion configurations, 15,590/15,590 completed episodes, and a verified
production capture of the diagnosed configuration.** All 12 affected CTest groups
pass. The prior primary privacy study remains closed; this is source-correction
evidence, not a new privacy result.

The correction lets a road user attach to the existing local A* grid when all
nearby start connectors are obstructed but a farther legal connector exists. It
addresses a source-motion defect exposed by the [closed P25.4 source-v2
study](URBAN_PRIVACY_P25_4_EXECUTION_OUTCOME_2026-10-26.md). It is development
evidence for a corrected source implementation, not a new primary privacy result.

Compact aggregate receipts belong in the [validation
package](verification/doorway-start-attachment-2026-10-26/). Raw configurations,
movement, traces, models and complete operational logs remain local in ignored
research output. Original source files,
headers, tests and executables were archived and hashed before implementation.
The regression fixture is small synthetic C++ source, with no production track
identifiers or recorded trajectory embedded in it.

## Failure and cause

The original replan searches for grid attachment in a 5 × 5 stencil centered on
the rounded current position. A connector is the straight segment from the
continuous position to a candidate grid node. The same exact static geometry,
current-body separation and passage permissions used by the existing planner
must accept that segment.

A physically valid continuous position can have no accepted connector among
those 25 candidates. In the diagnosed doorway queue, the local grid stencil was
empty even though a wider diagnostic search found a legal connector. The A*
frontier therefore had no starting node; the planner could not explore the
reachable route beyond it. Repeated replanning reproduced the attachment failure.
This differs from exhausting the A* node-expansion budget after a search starts.

## Implemented behavior and work bounds

`MappedScene::replanNavigation()` retains the original initial stencil and its
candidate order. Only if that stencil leaves the frontier empty does it examine
successively larger square rings, starting at radius three grid cells. Ring
perimeters have a fixed clockwise order. It finishes the first successful ring
within the remaining connector budget, then uses the existing A* search.

Let \(N\) be the configured `maxReplanNodes`, \(I\) the number of in-bounds initial
connector checks, \(E\) the extra connector checks and \(X\) the expanded A* nodes
for one replan. Then

\[
0\le I\le25,\qquad
E=0\ \text{if the initial frontier is nonempty},
\]

\[
0\le E\le\min(N,256),\qquad
C=I+E\le25+\min(N,256),\qquad
0\le X\le N.
\]

Connector checks and expanded nodes are separate work quantities. With the
existing \(N=20{,}000\) setting, a replan performs at most 281 start-connector
checks; it does not scan the full grid to obtain a starting point. With \(N=5\),
the connector bound is 30. These are operation-count bounds, not wall-clock
bounds: a connector predicate can inspect geometry and nearby current bodies.

The fallback uses the existing exact geometry/body/passage predicate. Actual
movement retains the existing per-step door, crossing, static geometry and swept
body guards. The steering direction set, physical clearance, preferred speeds,
route topology and resource ownership rules do not change.

Three diagnostics make this distinction observable:

| Diagnostic | Meaning |
|---|---|
| `navigationStartConnectorChecks` | Cumulative initial and extra connector checks across replans. |
| `navigationExpandedStartSearches` | Replans whose initial frontier was empty and entered the fallback. |
| `navigationMaxStartConnectorChecks` | Maximum connector checks in a single replan. |

`navigationMaxSearchNodes` continues to report the independent A* expansion
maximum. Serialization/export tests cover the new diagnostics. The complete
production capture below also retains these fields through stored/exported
artifacts and verifies the 281-check bound.

## Focused validation

### Synthetic RED/GREEN regression

The public-API fixture is a 10 × 10 m center-space union: two end rooms joined by
a narrow strip and a wider upper bypass. The strip occupies
\(y\in[5.1,5.5]\) m, while the replanning grid has 1 m spacing. Two pedestrians
with radius 0.2 m approach from opposite domain boundaries. Their required center
separation is \(0.2+0.2+0.05=0.45\) m, so they cannot pass inside the 0.4 m strip.
At their central meeting positions, the initial stencil cannot attach; a farther
connector into an end room and the upper bypass remain legal.

The same new `MappedSceneTests.cpp` suite was compiled against both the archived
original implementation and the correction. The original fails the new
completion assertion; the corrected full mapped-scene suite passes. A retained
small diagnostic probe records:

| Implementation | Completed by 60 s | Replans / failures | Maximum expanded nodes |
|---|---:|---:|---:|
| Archived original | 0/2 | 366 / 366 | 0 |
| Corrected | 2/2, both complete by 25 s | 34 / 1 | 23 |

The positive regression requires actual use of the upper bypass. Independent
checks cover current-body and swept-segment clearance, declared speed, per-step
displacement and the allowed center-space union. Renaming private people,
reordering their configuration and changing caller cadence preserve visible
frames and lifecycle events.

Two additional cases remove the bypass and rooms, leaving a genuinely blocked
strip with no usable grid nodes. For \(N=5\) and \(N=20{,}000\), both pedestrians
remain active, searches fail explicitly, body separation is preserved and A*
expands zero nodes. The maximum connector checks are exactly 30 and 281,
respectively. The fallback therefore neither fabricates a path nor escapes its
separate connector cap. The pre-existing blocked-corridor regressions remain in
the suite.

### Diagnosed source configuration

A native motion probe used the same complete recorded configuration before and
after the correction. The original implementation reached the full 300 s clock
with 153 episodes ended, eight active and eight pending. The correction completes
all 169 scheduled episodes; its last episode ends at 215,050 ms.

| Outcome | Original | Corrected |
|---|---:|---:|
| Scheduled episodes | 169 | 169 |
| Ended episodes | 153 at 300 s | 169 by 215.05 s |
| Active / pending at final probe state | 8 / 8 | 0 / 0 |
| Reported stalled tracks at corrected completion | — | 0 |
| Reported body overlaps at corrected completion | — | 0 |
| Expanded-start attempts | Not instrumented | 46 |
| Maximum start-connector checks | Not instrumented | 281 |

This focused probe establishes progress for the diagnosed configuration under
the corrected implementation. Its reported motion counters do not substitute for
the broader independent safety matrix or a full production capture. Operational
elapsed timings cover different amounts of simulated work: the original runs to
300 s while the corrected probe stops at completion. They support no speedup,
hard real-time or worst-case execution-time claim.

### Affected test groups

All **12 affected CTest groups pass in 177.688 s**. This includes the mapped-scene
regressions, configuration and probe contracts, sensor/source and finite-drain
checks, and the replay-export group with **55 passing export tests**. This is an
affected-scope result; it is not a claim that every repository test was rerun.
The production Simulator and maintained motion probe were built with the
correction. The aggregation replay executable remains byte-identical to the
closed study.

## Broader acceptance gates completed

| Gate | Declared scope | Verified outcome |
|---|---|---|
| Serial 92-case DEV motion matrix | All 72 closed source-v2 configurations, eight original DEV configurations and 12 fresh independent DEV configurations; one attempt each. | **92/92 pass; 15,590/15,590 episodes complete.** |
| End-to-end production DEV capture | The diagnosed configuration through the production Simulator, MongoDB recording, replay export and independent physical/access audit. | **169/169 observed episodes; 89,591 contributions; 2,999 measured samples; all declared checks pass.** |

### Development matrix and independent verification

All 92 configurations are DEV, including the 32 historically held-out source
configurations. Their former roles remain documented: 24 TRAIN, 16 CAL and 32
TEST from the closed study, plus eight original DEV and 12 fresh independent DEV
configurations. The additional configurations follow the same 128-person,
300-second mixed-storefront law. They are source validation, not a new held-out
privacy sample.

The runner preserves all 92 planned outcomes with no retries, replacements or
post hoc eligibility changes. Each serial probe has a 60-second wall budget and
an owned-process timeout of 70 seconds. It stops at full cohort completion or the
300-second simulation horizon. A separate verification reopens the frozen input
bindings and reparses every retained stdout/stderr log, rather than accepting
the aggregate status alone.

All 15,590 scheduled episodes start and end. Final active, pending, stalled and
reported body-overlap counts are zero in every case. The latest episode ends at
221,850 ms. Peak simultaneously active road users range from 123 to 128.

| Independent check | Count across 92 cases |
|---|---:|
| Current-body clearance | 641,320,625 |
| Swept-body clearance | 641,320,625 |
| Declared speed | 15,912,907 |
| Per-step displacement | 15,912,999 |
| Crossing-cohort invariance | 86,435 |

The independent probe records a minimum current-body clearance margin of
approximately 0.000000890 m and a minimum swept margin of zero; no violation
exceeds its fixed numerical tolerances. It observes 4,959 expanded-start
searches and 1,613,829 total connector checks. The maximum per-replan connector
count is 281; the maximum A* expansion is 15,760 nodes, below its separate
20,000-node cap. Exact case-ordinal outcomes and log hashes are in the
[matrix receipt](verification/doorway-start-attachment-2026-10-26/development-matrix.json).

The matrix independently checks body/swept-body separation, declared speeds,
displacements and crossing-cohort invariance. It is not an independent audit of
every polygon or resource permission. Production movement predicates remain
authoritative; the separate stored-data audit below checks the source pipeline
and declared access/geometry conditions.

### Production capture and stored-data audit

The production Simulator records the complete 300,000 ms horizon at a 100 ms
sensor period. The verified export contains 2,999 measured samples, including
849 empty samples, and 89,591 observation contributions. All 169 episodes for
128 scheduled people are observed and end; no episode remains active or pending.
The final stored diagnostics retain 15,352 connector checks, 46 expanded-start
searches, a maximum of 281 checks per replan and a maximum A* expansion of 15,597.
Reported active stalled tracks and body overlaps are zero.

The independent recorded-data audit passes 7,285,742 current-body and 7,285,742
swept-body pair checks, 179,260 static-body and motion-segment checks, 179,091
velocity checks, 169 terminal segments and 237 boundary endpoints. All planned
entries complete. The audit confirms the fixed geometry, configuration law,
recorded lifecycle, source observability and access checks. See the
[production-capture receipt](verification/doorway-start-attachment-2026-10-26/production-capture.json).

The capture/export operation takes 147.511 s and the separate independent audit
49.583 s in this run. These operational measurements have different scope from
the motion probes and include storage/export or audit work. They are not a
mechanism-only benchmark, worst-case execution-time bound or real-time guarantee.

The [compact package](verification/doorway-start-attachment-2026-10-26/README.md)
contains explicit aggregates, case ordinals and code/protocol/log hashes. It
omits source/target identities, seeds, configurations, raw movement and fitted
artifacts. Original archives and the closed study remain unchanged. Separate
source/analysis DEV integration is outside this correction proof.

## Limits and scientific status

The fallback addresses an empty initial frontier only. If the initial stencil
contains a valid but disconnected node, the larger attachment search is not
invoked. A valid continuous route may also lack a usable grid path, or its legal
connector may lie beyond the finite budget. Those failures remain unsupported
rather than being converted into a liveness promise. Dynamic obstruction,
resource coordination and other navigation limitations can still prevent
completion. There is no general crowd-liveness, maximum waiting-time or
real-time guarantee.

P25.4 source-v2 remains closed with its original 71/72 source outcome and all
TEST mechanism/attack/utility estimates unavailable. This correction does not
replace its failed source or reinterpret its trained/calibrated models as
held-out results. All historical TEST configurations are now exposed development
evidence for this source fix. The fresh cases in the 92-case matrix are also DEV
validation, not a new primary privacy study. Any future primary comparison needs
an explicit protocol with genuinely unexposed evaluation data. A future study
protocol is currently a DRAFT; it has generated no primary sources or new fitted
models.

The present results concern source behavior and measurement-chain readiness.
They establish no new privacy gain, adaptive-versus-baseline winner or empirical
attack result. Raw source data and fitted artifacts stay local; the repository
receives implementation/tests, this report and compact aggregate validation
receipts.
