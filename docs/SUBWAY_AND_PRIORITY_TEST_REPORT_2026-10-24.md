# Subway surface access and crossing priority test report

Date: 2026-10-24. Repository: UMP-Simulator. Generated motion is local only. This report covers the opt-in movement source, not an aggregation/privacy superiority claim.

## Implemented contracts

- Exact A1/A2 public metadata is frozen and hash-bound; only the two verified `building=roof,layer=1` canopies lose ground-obstacle status. Visible overhead polygons remain.
- Surface accesses are typed visibility interfaces with checked 1.5 m approaches and 1.2 m assumed admission cross-sections, without a fake building/facade.
- Independent seeded station trips use stair-eligible pedestrian classes, unique observed tokens and no operational hidden-person linkage.
- Explicit rider-priority crossings retain all body envelopes and swept collision checks. Waiting pedestrians can stage off receiving aprons, and admission checks each candidate's actual directed receiving area.
- Finite batches, request aging, expired/cancelled request cleanup and source/ring-gap validation are explicit. No entered occupied grant is revoked on a timer.

## Focused gates

`MappedSceneTests` passes after adding the typed portal, rider free-flow, already-crossing pedestrian, continuous finite rider stream, opposite receiving-apron and impossible-entry-staging singleton regressions. Every actual move remains subject to preferred-speed/displacement and physical overlap checks. The late-rider test derives its start from a reference pedestrian's actual entry, avoiding a guessed timestamp that can become invalid when admission changes.

`MappedSceneConfigurationTests` passes strict kind-specific YAML checks, malformed surface geometry rejection, forbidden fake-facade fields, unknown priority spaces and bounded finite settings. The probe contract test also passed with additional crossing telemetry.

The Python `test_transit_access.py` source suite passed six tests; its optional native integration test was executed separately. It checks source hashes, exact nodes/roofs/approaches, unknown-roof conservatism, both station directions, excluded stair-incompatible profiles, untouched body radii, repeatability and the historical full source/context/construction/audit digest with both switches disabled:

`054fcf2dbdfdbf7826fc67c798239b2327aa294002efea7581f006960fe61e67`.

The initial 64-person, 500 ms fixture passed 85/85 observed/ended tracks before the later receiving-apron correction. The final integrated repetition is reported below; historical counts are not silently reused for the corrected binary.

## Negative dense result retained

The first 128-person/150 ms version finished its 300 s numerical horizon but failed drainage: 159 starts, 97 ends, 62 active, 12 pending and 26 stalled tracks; zero reported body overlaps. Its consistent capture is intentionally retained as a negative result, with `all_scheduled_episodes_completed: false` in the proof. Its three isolated UUID databases were cleaned after export. Original user databases were untouched.

[Compact negative source evidence](verification/transit-priority-dense-negative-2026-10-24.json) records this result. A successful export is evidence of capture consistency, not proof of complete source drainage.

The diagnosed receiving-apron cycle was reproduced in a dedicated regression: an ungranted pedestrian frozen at the exit curb blocked an admitted opposite pedestrian, whose occupied grant then prevented all new crossing admissions. Corrections did not delete the stuck body or reduce its radius. A second test prevents replacing this with a global staging barrier: a single pedestrian must cross an empty road even when its one-metre entry sidewalk cannot hold an off-apron parking target.

## Matched corrected source controls

Both runs use the exact same 128 people, 171 episodes, seed, 150 ms first-arrival schedule, route geometry, labels, body radii, speeds and A1/A2 access. Only crossing declarations are removed in the control. Both use the same C++ probe, 50 ms numerical steps and a finite 360 s horizon with a 120 s wall budget. They run serially without MongoDB or aggregation.

| Outcome | No priority declarations | Corrected priority |
| --- | ---: | ---: |
| Starts / ends | 171 / 171 | 171 / 171 |
| Last end | 180.85 s | 190.40 s |
| Peak active tracks | 121 | 121 |
| Final active / pending / stalled | 0 / 0 / 0 | 0 / 0 / 0 |
| Reported overlaps | 0 | 0 |
| Pedestrian batches | 0 | 36 |
| Fairness closures | 0 | 13 |
| Maximum request-to-grant wait | 0 | 17.40 s |
| Source-only wall time | 17.23 s | 20.97 s |

These single runs establish finite completion for the tested workload and isolate the initial rule bug. They do not establish an unconditional liveness theorem or a statistically estimated performance effect. The priority rule adds behavioral constraints and costs. The 8 s age threshold is a closure trigger, not a hard service deadline. Source simulation cost is excluded from the isolated aggregator real-time test.

[Compact matched source controls](verification/transit-priority-source-controls-2026-10-24.json) include source/probe hashes and full aggregate diagnostics.

## Final end-to-end capture

The final corrected-binary capture is accepted for the tested finite workload: **128 people, 171 visible episodes, peak 121 observed tracks, every episode started and ended by 190.4 s**, with zero final active/pending/stalled bodies. The recorded horizon is 300 s at 50 ms numerical cadence and 100 ms sensor cadence.

Exact token-set equality independently verifies **all 171 configured episodes appear in the exported sensor observations**, with no missing or unexpected tracks. There are 2,999 measured batches and 79,617 observation contributions. The recording proof verifies 159,292 GT rows, all 342 lifecycle events, actual interval terminal positions and native raw-cell/journal/release agreement. The default aggregation policy publishes 1,176 cell-windows over 42 distinct cell IDs; these counts are a source integration check, not an algorithm comparison.

The independent body audit passes **6,111,306 position-pair and 6,111,306 swept-body pair checks**, 159,292 actual navigation/static-body checks, 159,121 velocity checks and all 171 terminal sweeps against the declared ground/mode geometry. The minimum observed swept clearance margin above configured body-plus-hard-clearance requirements is positive (approximately 0.0000478 m). All six targeted portals receive their planned entries: A1 has five independent entries and five independent exits; A2 has five entries and four exits. All station trips use stair-eligible classes. The four shops complete all 43 visits/returns, with a minimum hidden gap of 8 s. Geometry checks preserve the two overhead canopies as context while actual bodies remain outside unrelated ground buildings.

The new capture uses the exact same `mapped_scene` configuration as the retained failed dense recording; only the corrected native source implementation and fresh database namespace differ. Config SHA-256: `2d2390ce7f778c97e7bebd2a063f79df2e596b6f269c8b97ebcf0b8a1365bb92`; Simulator SHA-256: `4d69a20892fc7806e902793de27e133af0cd28893e8d2219da6f8275fb5e5204`.

Local replay: `results/urban-transit-priority-2026-10-24-v3/replay`. The runner removed only its three fresh owned UUID databases after verified export. Raw motion remains outside Git. The 96.05 s native wall time includes source motion, aggregation, database I/O and concurrent regression tests; it is not an isolated real-time result.

[Compact final source/sensor/body evidence](verification/transit-priority-accepted-source-2026-10-24.json) records the exact hashes and aggregate checks. The tested case is accepted; denser/different demand, access widths, arrivals, acceleration/braking behavior, staging capacity and global liveness remain separate evaluation questions.
