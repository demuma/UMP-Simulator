# Opt-in mixed urban traffic

`--urban-traffic` extends the frozen 80 × 80 m Mönckebergstraße scene with pedestrians, cyclists and E-scooter riders. It is a separate experimental scenario from `--experimental-narrow-passages`; the two options cannot be combined. Existing scene defaults, the original pedestrian source and its regression digest remain unchanged.

The scenario imports frozen building and transport geometry. Its demand, crossing corridors, carriageway directions and speeds are declared modeling assumptions. They do not establish legal access, real crossing markings, signals, priority rules, empirical demand or calibrated human behavior.

## Source controls

Use the maintained runner, for example:

```sh
python tools/mapped_scene/run_scene.py \
  --motion-mode storefronts --urban-traffic \
  --population 256 --arrival-interval-ms 150 \
  --road-user-fraction 0.2 --distributed-crossing-fraction 0.2 \
  --pedestrian-clearance-m 0.05 --seed 20261024 \
  --duration-s 240 --output results/urban-traffic/example/scene --cleanup
```

Use the Python environment documented for the mapped-scene tools. Output directories must be fresh. Generated movement, private ground truth and replay artifacts stay local under ignored `results/`; compact evaluation results can be committed separately. `--cleanup` removes only this run's three fresh owned MongoDB databases, after successful verification.

`population` counts synthetic people across the run. `arrival_interval_ms` controls first visible-episode requests, not guaranteed admission or the concurrent population. Actual peak active road users, queueing and finite-cohort completion must be measured. Boundary sinks accept a body-safe line interval rather than forcing all arrivals through one sampled endpoint. The exact realized terminal coordinate is recorded privately and independently checked, including the final source-step sweep. For building visitors the return request is anchored to realized entry and the configured hidden dwell. People and visible track identities remain distinct.

## Geometry and movement

The root navigation space is pedestrian-only. Five pedestrian categories retain their declared radii, including 0.45 m for a pedestrian with stroller. The default urban hard separation is 0.05 m in addition to the two bodies' radii; it is not their full center-to-center distance. The pedestrian static center-space erosion uses the largest pedestrian radius plus this clearance and a 0.002 m numerical margin.

Four distributed four-meter crossing corridors supplement a four-meter preferred Barkhof corridor. They are intersected with the crop and exclude frozen buildings. Connectors explicitly span residual curb gaps between the separately buffered road and walking layers. Pedestrians do not receive unrestricted access to the complete carriageway. A seeded subset of through-pedestrian requests is routed through a distributed connector; other paths can also use the connected crossing space when it provides a valid route. The requested fraction therefore does not equal the final fraction of observed crossings.

Riders use two separate named navigation spaces, `carriageway-east` and `carriageway-west`. Each half of the frozen carriageway is eroded for the largest rider and hard clearance before crop clipping; the centerline is an obstacle boundary for that erosion. The resulting opposing center spaces are separated by at least 2.104 m for the default parameters. Per-route `navigation_space` constrains native route validation, shortcuts, steering, replanning and the entire exit interval. Seeded 1.2–1.5 m route offsets alone were insufficient because local steering could otherwise cross to the opposing direction; the independently enforced spaces close that gap. Riders receive no general walking or storefront access. These are synthetic scenario directions, not inferred lane permissions or traffic law.

The rider subset includes Adult Cyclist, Senior Cyclist and Adult E-Scooter Driver. Cyclist radii remain 1.0 m and the scooter radius remains 0.65 m. All use explicitly declared 3–4 m/s synthetic source speeds. Each rider direction is conservatively eroded for the largest rider plus hard clearance. Lower pedestrian spacing does not shrink body envelopes.

Boundary-to-boundary source requests now require at least 1 m from the sampled origin to its nearest allowed sink and at least 0.05 m of progress into the source edge's interior. Different interval names alone are insufficient: intervals on the same edge, or adjacent intervals reaching a common corner, can otherwise finish immediately or remain entirely on an excluded maximum boundary. Only invalid urban pedestrian pairs are repaired, using a separate seeded random stream and a connected destination. Source positions, identities, profiles, speeds, schedules, building visits, rider routes and valid pedestrian routes remain unchanged. Half-open sensor coverage remains unchanged. The static rule prevents the identified geometric degeneracy; the native acceptance gate separately checks actual observation at the configured sensor cadence.

The local solver preserves its conservative pairwise and swept-body collision checks. It is not ORCA and has no global deadlock-freedom, traffic-priority or hard real-time guarantee. Passing the generator's static route audit is not evidence that a dense finite cohort drains. Native drain tests and independent recorded-motion audits are required separately.

## Aggregation and semantics

Motion permissions remain independent of application Policy Trees and the D6 observation quadtree. A movement route chooses a static navigation space; a Policy Tree constrains publication from the resulting observation stream.

The release taxonomy adds `cyclist` and `e_scooter_rider` families alongside `pedestrian`. All family nodes have declared loss 0.5; input categories have loss 0 and `road_user` has loss 1. These costs are experimental definitions rather than measured privacy guarantees. The scenario continues to use the normal regional constraint adapter and aggregator.

Compare stricter and less strict Policy Trees by replaying the same captured observation stream. Independently generated traffic is useful for source robustness, but cannot isolate a policy effect. Report category support, semantic/spatial/temporal loss, coverage, delay, suppression and violations separately. Operational distinct-track support is not by itself a demonstrated k-anonymity guarantee against a specified adversary.

## Verification boundaries

Generation checks each route against its selected center space, the declared physical mode surface, frozen buildings and bounded facade exceptions. Public map metadata fingerprints all named center spaces. Export rejects a different space geometry, clearance or incompatible source interval. The independent motion auditor checks stored positions, actual sweeps, speed/velocity, pairwise separation, lifecycle events and mode-compatible boundary endpoints.

These checks validate the specified synthetic mechanism and its data contracts. Empirical realism, traffic access, comprehensive tracking uncertainty and adversarial privacy remain separate evaluation questions.

## Dense native acceptance gate

`mapped_urban_traffic_drain_tools` runs the exact 256-person, seed-20261024 source with 150 ms between initial requests, 20% riders, 20% targeted distributed crossings and 0.05 m hard clearance. Its 360 visible episodes must each produce exactly one start and end; final active, pending, stalled and overlap counts must all be zero within 900 simulated seconds. Every episode must also appear at least once inside the half-open sensor domain at a positive 100 ms timestamp, with native movement advancing every 50 ms. The optional test-only CLI flag `--require-observed-period-ms 100` enables this additional check; t=0 is not treated as a sensor observation. This source exposed northern-boundary projection loops even after the smaller 128-person source had completed. The larger gate therefore checks behavior that the smaller test does not establish.

A finite drain alone missed a source-quality defect in the frozen 256-person recording: 360 episodes completed but only 357 appeared in the 100 ms observation reference. Two sources lay on their own permitted sink and moved less than a micrometer before ending after 50 ms. A third episode traveled along the excluded maximum-x boundary for 1.2 s, including twelve aligned sensor instants. The new nearest-sink rule repairs 29 invalid boundary pairs in this seed, including the three missed episodes and 26 other tangent trips. It preserves all valid routes and all other configuration fields. The original recording and its policy comparison remain immutable historical evidence; they are not silently replaced by the corrected source. See [the recorded-flow audit](verification/urban-recorded-flow-2026-10-24.json), [the actual three-episode negative control](verification/urban-observability-negative-control-2026-10-24.json) and [the corrective acceptance evidence](verification/urban-boundary-source-correction-2026-10-24.json).

The corrected exact cohort passes the stronger gate: 360 starts, 360 ends and 360 tracks observed at 100 ms, with zero final active, pending, stalled or overlapping tracks. It finishes at 201.2 simulated seconds; its longest recorded stop is 8.55 s. The source configuration in the 240 s guide example has the identical movement scene, so that specific horizon leaves completion headroom for this seed and cohort. These are finite test outcomes, not universal liveness, comfort or real-time guarantees. The native test wall time was 80.01 s; the 21-case router suite, 26 fast builder cases and 50 exporter checks also pass. Four native drain cases are intentionally skipped in the fast builder suite and run through their separate registrations.

The gate writes only a temporary source configuration and invokes `MappedSceneConfigurationTests`; it does not use MongoDB or store sampled movement. CTest runs it serially with a 300-second wall budget. Its internal native subprocess budget is 240 seconds, leaving bounded setup headroom. These budgets are acceptance limits, not a real-time or per-track latency guarantee.

```sh
ctest --test-dir simulator/build \
  -R '^mapped_urban_traffic_drain_tools$' --output-on-failure
```

The ordinary fast builder suite unsets `UMP_MAPPED_CORE_TEST_BINARY` and skips native drainage. The dedicated CTest registration explicitly supplies that binary and executes the gate. Passing the fast generator tests or a smaller source cannot substitute for this dense acceptance check. Results must be recorded against the final binary; registration alone is not a passing result.

## Bounded local capture size

The recorder now defaults to **2048 MiB (2 GiB)** for serialized source captures and JSON artifact files. `run_scene.py` and `export_replay.py` accept `--max-capture-mib` values of 256, 512, 1024 or 2048; the selected value bounds the MongoDB transfer and private source file. Other JSON artifacts support up to 2 GiB. Specific map, geometry and image limits remain separate and unchanged.

MongoDB records are consumed through an explicitly awaited cursor and serialized individually. Output is buffered in approximately 1 MiB chunks into an automatically removed temporary file. The exporter does not build one aggregate JavaScript JSON string or one Python `subprocess.capture_output` string. Both MongoDB-side UTF-8 accounting and the Python-side temporary-file size check enforce the selected byte budget. The former fixed one-million-record ceiling is replaced by a finite byte-budget-derived record bound; it cannot reject a valid capture merely because it contains more than one million small records. The MongoDB read has a bounded 360-second timeout.

The mapped exporter's JSON artifact writing also streams encoder chunks, checks the file budget before each write and removes only its own incomplete new file if encoding or size validation fails. Existing files remain protected by exclusive creation. Normal lifecycle, policy, ownership, map and publication verification still apply.

A completed source whose earlier export reached a smaller file cap does not need to be simulated again. Export the same retained owned databases into a fresh local replay directory. The original native configuration and execution record remain unchanged. New capture proofs record the selected byte budget, actual private source-file size, source configuration digest, transport method, chunk target and read timeout. Previously verified replay files and proofs retain their historical recorded budgets.

The direct downstream consumers `tools/mapped_scene/analyze_tracks.py` and `simulator/build/AggregationReplay` also allow 2048 MiB inputs and analysis/replay results. The separate archival/Git-package helper `tools/evaluation/replay_data.py` retains its 256 MiB limit. Raising these direct-consumer guards does not alter aggregation or policy decisions. Earlier comparison reports retain the binary digests used for their original executions; rebuilding this guard-only change creates a new binary digest without rerunning those historical comparisons.

**These are serialized file-size limits, not memory guarantees.** Python still loads the completed JSON object for the existing validators, and the replay tools also need memory for their parsed data. The streaming change removes the aggregate Node string and subprocess output-string bottlenecks; it does not establish constant-memory validation or a tested 2 GiB playback guarantee.

Generated raw movement and private replay sidecars remain local under ignored `results/`. The increased file allowance does not add generated motion to Git or relax source, lifecycle, policy, public-map or publication verification.
