# Mixed urban traffic — implementation and test report, 2026-10-24

## Result and scope

The opt-in Mönckebergstraße source now supports closer pedestrian groups, concurrent same-direction building access, preferred and distributed pedestrian crossings, and cyclists/E-scooter riders on the carriageway. The frozen recorded 256-person source reaches 224 simultaneous visible tracks and completes all 360 GT episodes, with three subsequently diagnosed observability defects. The corrected generator separately passes a stricter gate requiring all 360 tracks to be measured. Its recorded input is reused unchanged by ten predeclared and four separately declared post-hoc C++ aggregation executions under two local Policy Trees.

The adaptive method retains more input observations than the four tested fixed configurations under each tree. The fixed 10 m / 1 s method answers more of the predeclared aligned 10 m / 1 s queries exactly. Therefore the experiment establishes policy-compliant retention benefits on this source, with a concrete recipient-utility and runtime limitation. It does not establish general superiority or a measured adversarial privacy gain. See [the policy results](URBAN_POLICY_RESULTS_2026-10-24.md) for the complete comparison and denominators.

## Movement implementation

- `--urban-traffic` is explicit and preserves the historical default generator and its digest. It cannot be combined with the older experimental narrow-passage source.
- Extra pedestrian clearance decreases from 0.10 m to 0.05 m. Body radii are unchanged. The minimum permitted center distance remains the sum of the two bodies' radii plus the extra clearance.
- Five four-meter synthetic pedestrian crossing corridors connect the frozen walking layers: one preferred Barkhof connection and four distributed connections. They are modeling assumptions, not inferred official crossings or legal access.
- Adult/Senior Cyclists and Adult E-Scooter Drivers use direction-specific carriageway center spaces. Every route, shortcut, local candidate, A* edge and boundary exit is checked against the selected space. Guide offsets alone do not enforce lane discipline.
- Default opposing rider spaces are at least 2.104 m apart. Existing cyclist and scooter radii remain 1.0 m and 0.65 m; rider speeds are explicitly synthetic 3–4 m/s. The source has eight terminal labels and three truthful release families. There are no added cars.
- Building doors optionally admit finite same-direction batches, six in this scenario. Requests arriving later cannot prolong the active batch; opposing requests wait until the occupied throat clears. Bodies still pass exact swept safety checks. This is a pipelined single throat, not independent bidirectional lanes.
- Domain exits accept valid boundary intervals. The realized terminal coordinate is retained privately and included in the independent final-step sweep audit. A blocked projected exit target is stabilized during replanning; directly visible exits retain nearest-point projection and broad outflow.

The same population can create multiple visible episodes because building reappearance creates a new track. Hidden private person identity is not supplied to the aggregator. Operational distinct-track support must not be presented as a distinct-person guarantee or classical trajectory k-anonymity.

## Source acceptance gates

All sources use an 80 × 80 m crop, seed 20261024, a 50 ms numerical movement step and unchanged body envelopes. D6 sensor leaves are 1.25 m; the movement grid is independently 0.5 m.

| Source | Initial request interval | Rider fraction | Episodes | Peak active | Completion | Remaining active / pending | Reported overlaps |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| Frozen recorded 256 people, before boundary repair | 150 ms | 20% | 360 | 224 | 203.80 s | 0 / 0 | 0 |
| Corrected 256-person observation gate | 150 ms | 20% | 360 | Not recorded by this gate | 201.20 s | 0 / 0 | 0 |
| Paced 500 total people | 500 ms | 20% | 703 | 147 | 400.15 s | 0 / 0 | 0 |
| Higher-pressure 500 people | 150 ms | 5% | 735 | 392 | Not completed within wall budget; simulated cutoff 513.15 s | 104 / 112 | 0 |

The pressure case fails the complete-drain acceptance gate: 42 active stall diagnostics remain, and the longest observed stop is 464.2 s. The result must remain visible rather than being presented as successful 500-person dense flow. The two 500-person sources change both arrival cadence and mode mix; they do not isolate one causal density factor. The accepted source's maximum stop is 14.95 s; completion does not prove calibrated pedestrian behavior or universal liveness.

The registered `mapped_urban_traffic_drain_tools` gate reconstructs the exact accepted 256-person fixture and requires every episode to start/end once, with no final active, pending, stalled or overlapping tracks. This native gate passed in 84.08 s. [Compact source evidence](verification/urban-traffic-source-gates-2026-10-24.json) includes configuration and log hashes for all three cases.

## Persistent capture and independent audit

The accepted source was recorded for 240 s at a 100 ms sensor cadence. Verification covers 375,758 GT rows, 720 lifecycle events, all 360 completed episodes and 256 realized boundary terminal positions. The input contains 2,399 measured sensor batches, 362 empty batches and 187,745 observation contributions. Positions, timestamps, source-space geometry, speeds, velocity, final sweeps, body separation, categories, raw cells and publication journal agreement are independently checked.

A later observability check finds only 357 distinct tracks in the measured sensor stream, despite 360 completed GT episodes. Two episodes last 50 ms with zero displacement because their origin belongs to their own boundary sink. A third lasts 1200 ms entirely on x = 80 m, outside the half-open sensor coverage, despite twelve nominal sensor timestamps. These are boundary source/sink defects before aggregation, not aggregator suppression or merely a clock mismatch. The comparison's actual 187,745-contribution input and all method denominators remain unchanged. The frozen capture/proof/results are preserved; a generator correction and a stronger complete-observation acceptance gate are evaluated separately below. [Recorded-flow evidence](verification/urban-recorded-flow-2026-10-24.json) separates measured samples, GT episodes and geometric occupancy masks.

At the 100-ms measurement cadence, center-based occupancy masks show up to eight pedestrians simultaneously in the preferred road-crossing connector and peaks of five, five, seven and five in the four distributed connectors. The road-intersected connector union reaches 21. Each shop's declared throat rectangle reaches four observed centers; the much thinner 15-cm facade band reaches one. These are geometric occupancy counts, not proof of simultaneous admission, bidirectional lanes or four people crossing one facade plane at exactly the same instant. The recorded-flow evidence defines the masks and keeps them distinct from wider three-meter entrance vicinity counts.

The native sink contains 3,199 published cell-windows over 84 unique spatial IDs. The original-policy offline execution reproduces the native release multiset, allowing delivery order/IDs to differ and using numerical tolerance 1e-10. Offline execution means the causal C++ core consumes the frozen recorded batches; it does not resimulate movement or optimize with future observations.

The native binary took 217.57 s for this 240-s recording, including startup, source motion, aggregation and database I/O. Other validation jobs overlapped this capture, so this is not an isolated end-to-end benchmark or a live per-step guarantee. [Capture recovery evidence](verification/urban-traffic-capture-recovery-2026-10-24.json) records the original 256 MiB export-cap failure and recovery of the same source without resimulation. The verified private source JSON is 273,924,309 bytes (261.23 MiB). Its original 512 MiB recovery proof remains unchanged. After verification, only the three fresh invocation-owned MongoDB namespaces were removed; the local replay remains intact and the user's original Simulation database was not modified.

## Exact source optimizations

Immutable facade exclusion geometry is prepared once. Conservative AABB rejection avoids distant exact geometry/body work, with original predicates retained as the authority. Neighbor lookup and radius resolution are reused within a step; TTC filtering and iteration retain deterministic ordering. Static A* grid-edge permission is memoized by navigation space, owning start/end door and ordered node pair. Off-grid edges, dynamic bodies and passage permissions are still checked. The cache has a deterministic 65,536-entry bound.

The final paired source experiment disables only the A* static grid-edge cache and replan body AABB rejection in its control. Both binaries otherwise use the same accepted movement rules, source and earlier optimizations. They ran serially, without competing source/capture jobs.

| Source-only measure | Control | Optimized |
| --- | ---: | ---: |
| Mean advance step | 17.460 ms | 15.318 ms |
| p95 step | 81.641 ms | 46.065 ms |
| p99 step | 121.222 ms | 115.381 ms |
| Maximum step | 201.139 ms | 226.251 ms |
| Steps above 50 ms / 4,076 | 336 | 183 |
| Total source advance | 71.169 s | 62.437 s |

Mean cost falls 12.27%; p95 falls 43.58%. All seven checkpoints, source counters and the complete motion digest match; both complete at 203.80 s. The digest folds each numerical step's time, ordered private identity, position, velocity and next guide. It is a regression oracle, not a formal equivalence proof. One timing pair does not establish a statistical speedup, and the maximum observed optimized step is worse. Aggregation/DB/browser costs are additional. [Final accepted-source profile](verification/urban-traffic-accepted-profile-2026-10-24.json) records exact values, source/build hashes and scope. Earlier shared-carriageway profiling is retained only as historical diagnosis.

## Policy and utility evaluation

The original tree requires total and per-output-category track support of five. Only the total floor increases to ten near an entrance; the category floor there remains five. The second tree changes only support floors using `ceil(0.6 * floor)`: five becomes three and ten becomes six. All region geometry, spatial/temporal/semantic bounds and release triggers remain identical. Overlapping regional minima combine by maximum and maxima by minimum across the complete published footprint.

For a candidate cell/window, total support is the cardinality of observed track identities contributing to it. Category support is computed separately for each nonempty released semantic bin. Repeated samples from one identity do not increase either distinct count. Both checks are operational disclosure conditions; their empirical protection still needs an explicit adversary and evaluation.

Retention is `released observation contributions / all input observation contributions`. It is not a count of unique people. Conditional semantic loss is the observation-weighted taxonomy cost among retained contributions; leaves have cost 0, the three families 0.5 and Road User 1. Observation-to-seal delay is `publication time - observation time`. A positive-reference query is evaluated separately from a known-zero query. Missing data are not assigned zero. Public uniform spatial/temporal estimates have separate coverage and error from exact answers.

Both trees have zero independently detected publication-policy violations across the five predeclared methods and two added fixed-4-s methods. This must be read with their nonzero retained coverage, losses and delays. The two adaptive cases retain 61.77% and 78.70%, versus best fixed retention 52.68% and 66.85% in the predeclared 0.4/1-s portfolio. Adaptive may use windows up to 4 s, so this portfolio does not isolate adaptation from access to longer windows; the separate post-hoc fixed-4-s sensitivity in the policy results tests that limitation explicitly. Adaptive local intervals make aligned exact recipient queries difficult: fixed 10 m / 1 s remains better for that declared task. Adaptive core plus in-memory result serialization takes 124.20 s / 111.00 s; fixed cases take 0.76–1.85 s. Those measurements exclude validation and file I/O and do not establish per-step live deadlines. The complete adaptive result documents are 247,339,286 / 198,496,140 bytes (including private diagnostics), so the timed in-memory serialization is a material profiling target; total core time cannot be attributed entirely to aggregation decisions without a component trace. The post-hoc maximum-window check yields best fixed retention 58.73% / 70.54%, so the adaptive advantage shrinks to 3.04 / 8.15 percentage points. The relaxed fixed 10 m / 4 s method also preserves more exact subtype data than adaptive (7.815% / 3.388% of input). The next algorithm work must address query-compatible publication and the adaptive decision/retirement cost, with an unchanged-query control.

## Automated and browser verification

The full final native/source regression invocation passed all 89 then-registered CTest groups in 253.53 s. The newly added plotting group subsequently passed, giving 90 registered groups verified across these invocations. The final affected export/comparison/plot groups were rerun after the streaming changes. [Test evidence](verification/urban-traffic-tests-2026-10-24.json) distinguishes the invocations; no single 90-group run is claimed.

Focused regressions cover invalid/duplicate movement spaces, selected-space routes and radius constraints, same-direction door occupancy, opposing-direction exclusion and drainage, final boundary sweep positions, occluded-goal replanning, separate visible exit points, default-source digest stability, independent mode geometry audit, mapped export/viewer schema, policy-only parameter changes, support/delay accounting, missing metrics and plots. Export tests additionally cover UTF-8 byte accounting, failed/truncated/over-budget streams, temporary-file cleanup and exclusive artifact creation. A fresh small MongoDB smoke export verifies cursor streaming and Unicode/date/ObjectId conversion, followed by cleanup of only its owned namespaces. The final exporter suite passes 50 checks, including the command-size regression for unrelated scene configuration larger than 1 MiB.

The final replay was inspected in Chrome at `http://127.0.0.1:8790/`. At 48 s it shows 205 distinct current positions, all eight source types, the original and relaxed PolicyTree IDs and different historical release mosaics. Play advances current samples and publication events. Cell inspection exposes regional effective bounds, released groups and optional private source groups; a selected example has five contributing tracks from three input types generalized truthfully to Pedestrian. Switching to the fixed baseline works. Seeking to 240 s shows zero current positions while correctly retaining explicitly labeled publication history. Browser console storage errors include an extension content-script origin/context; no storage API occurs in the viewer source and no replay failure was observed. A local acceptance screenshot is retained under the ignored comparison directory. [Compact browser evidence](verification/urban-replay-browser-2026-10-24.json) records the inspected states.

## Boundary source repair and stronger observation gate

Only the opt-in urban generator changes: a valid boundary source/sink pair now requires at least one meter to the nearest allowed sink projection and at least 0.05 m progress into the crop from the source edge. Different boundary IDs alone are insufficient: intervals can share an edge or meet at a corner. Invalid pairs are repaired with an independent seeded RNG and an exact connected walking-route suffix. Public geometry, body sizes, sensor coverage, all people/types/tokens/speeds/schedules/visits, policies/taxonomy, all rider guides and every already-valid route remain unchanged. The exact 256-person correction changes 29 pedestrian through-routes: this includes the three invisible episodes and other edge-skimming routes visible only because the lower coverage edges are included.

The native test CLI optionally samples `frameAt` at positive 100-ms timestamps while advancing at 50 ms, counts identities only within `[0,width) × [0,height)`, and requires the observed set to equal all scheduled/realized tracks. Lifecycle completion alone cannot pass this guard. Tiny transverse/lower-edge fixtures pass; maximum-edge tangent and unsampled 50-ms fixtures fail. The three real extracted old counterexamples also pass the legacy drain condition and fail the new observation requirement with zero observed tracks. [Negative-control evidence](verification/urban-observability-negative-control-2026-10-24.json) fingerprints these checks.

The corrected full 256-person fixture passes the stricter native gate: **360 scheduled, 360 starts, 360 ends and 360 observed tracks**, zero final active/pending/stalled tracks and zero reported overlaps. Last completion is 201.20 s, maximum consecutive stop 8.55 s; the logged gate takes 80.01 s wall time. Thus the 240-s guide example covers this exact corrected cohort. [Corrective source evidence](verification/urban-boundary-source-correction-2026-10-24.json) records the actual counters, source/configuration hashes and unchanged-field proof. Final router checks pass 21/21; the fast builder group passes its 26 executed checks and intentionally skips four separately registered native-drain cases. The corrected dense gate runs separately. The frozen old capture, fourteen comparisons, source-only profiling and screenshot are preserved as their original control; their measured benefit must not be transferred to the corrected source without a fresh recorded comparison.

## 2 GiB recording allowance

The default serialized source capture and general JSON artifact allowance is now 2 GiB. Explicit capture choices are 256/512/1024/2048 MiB. MongoDB cursors stream through approximately 1 MiB chunks into a temporary file; JSON artifacts also use a chunked encoder. UTF-8 byte accounting, bounded record count and a 360-second read timeout remain enforced. The direct AggregationReplay and track-analysis consumers also accept files up to 2 GiB; their independent guard/regression check is recorded in [direct-consumer evidence](verification/direct-replay-consumer-2gib-2026-10-24.json). The frozen fourteen-case replay binary identity remains historical; the later guard-only binary is separately fingerprinted. Map images, geometry and compact archival packaging keep their separate smaller limits. The validators still parse complete JSON objects, so 2 GiB is a file allowance, not a RAM bound or a tested 2 GiB browser-playback claim. Existing verified recordings/proofs are preserved. [Streaming evidence](verification/capture-streaming-2gib-2026-10-24.json) records focused tests and the live smoke check.

## Reproduction and next gate

```sh
# Run from repository root, using the mapped-scene Python environment.
python tools/mapped_scene/run_scene.py \
  --motion-mode storefronts --urban-traffic --population 256 \
  --arrival-interval-ms 150 --road-user-fraction 0.2 \
  --distributed-crossing-fraction 0.2 --pedestrian-clearance-m 0.05 \
  --seed 20261024 --duration-s 240 \
  --output results/urban-traffic/new-run/scene --cleanup

python tools/mapped_scene/run_comparison.py \
  --recording results/urban-traffic/new-run/replay \
  --output results/urban-traffic/new-run-policy-comparison \
  --policy-comparison --native-wall-budget-s 900

python tools/replay_viewer/serve.py \
  --bundle results/urban-traffic-2026-10-24-256-policy-comparison --port 8790
```

Use fresh output paths. The retained current replay requires neither a running Simulator nor MongoDB. Generated motion and replay files remain local and ignored; only source, tests, documentation, aggregate measurements and a compact plot go to Git.

Continue in this order: preserve this control and repeat the frozen protocol on a fresh corrected-source recording; diagnose recipient-compatible temporal boundaries and adaptive per-step costs; test one coordinated change against the same queries; broaden seeds and demand regimes; then add the residential/traffic scenarios and attack-based privacy work. Dense crowd deadlock/fairness, realistic yielding/signals, additional cafe/upper-left entrances, comfort around walls, general map import and tracking uncertainty remain separate open tasks.
