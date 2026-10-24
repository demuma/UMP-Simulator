# Narrow-passage implementation and density test report

Date: 2026-10-24. Base revision: `f951e00`; exact source and binary hashes are in the [compact evidence](NARROW_PASSAGE_RESULTS_2026-10-24.json).

## Result and acceptance boundary

The optional native passage coordinator completes both declared 128-person cases within the unchanged 600 s simulation horizon and 180 s per-case wall budget. Each case produces all 192 visible episode starts and ends, clears all 81 controlled traversals and leaves zero active, pending or stalled tracks and zero reported physical overlaps. The two sources have identical routes, type assignments, speeds, radii, visits and opaque episode tokens; only initial admission-request times differ. Their normalized source hashes match.

The experimental flag remains **off by default**. These are bounded acceptance cases for one deliberately modeled map resource, not global crowd liveness, a 500-person acceptance result or a privacy result. The accepted default source stays the reference. The [contract](NARROW_PASSAGE_COORDINATION_2026-10-24.md) defines exact configuration, readiness, capacity and clearance restrictions.

## What changed

- Strict optional `navigation.narrow_passages` metadata: audited common guide, holding points, protection radius and finite batch cap.
- The oldest **physically staged** request chooses a direction. A finite compatible snapshot enters in request order; a preceding body must clear the mouth before the next approaches. Unready requests do not own the passage while trying to reach their holding position.
- Each request has a persistent holding point. A grant does not free that point for another waiter; it remains reserved until actual entry. Slots fill from the mouth outwards.
- Controlled traversal follows its exact guide from the first step leaving entry. Exact static geometry, speed limits, swept-body collision checks and overlap auditing remain active. No teleport, speed increase, forced occupied-resource timeout or geometry widening is used.
- Nonparticipating routes bypass the protected tube. Visibility shortcuts, dynamic A* and actual candidate motion use the same resource exclusions.
- The generator keeps holding bodies outside a 3.55 m endpoint exclusion and supplies enough declared holding capacity for its finite directional cohort. Native validation rejects unmanaged tube crossings, insufficient capacity, incorrect-side/unreachable holding points and coupled door/passage approaches.
- `MappedMotionProbe` provides maintained aggregate-only progress, completion status, peak concurrency and step timing. It returns nonzero for incomplete horizons or exhausted wall budgets. It stores no individual motion.

Movement resources remain separate from aggregation buckets, the D6 privacy quadtree and application Policy Trees. Privacy/utility constraints and release logic are unchanged.

## Paired complete runs

Both cases use seed 20261024, an 80 × 80 m area, 50 ms native steps, 128 total people, 64 building visits and 192 visible episodes. Profiles are 32 Adult Pedestrians and 24 each Child, Senior, With Stroller and With Mobility Aid. Building returns create new visible episodes after realized arrival and hidden dwell; episode counts are not person counts. The bounded source uses synthetic, declared demand rather than measured pedestrian flows.

| Measurement | Lower arrival pressure | Higher arrival pressure |
|---|---:|---:|
| Initial request interval | 2 s | 0.5 s |
| Peak simultaneously active tracks | 66 | 111 |
| Started / ended episodes | 192 / 192 | 192 / 192 |
| Complete at simulated time | 568.80 s | 568.30 s |
| Final active / pending / stalled | 0 / 0 / 0 | 0 / 0 / 0 |
| Reported physical overlaps | 0 | 0 |
| Maximum passage-request wait | 225.35 s | 304.85 s |
| Maximum unintentional consecutive stop | 2.50 s | 7.50 s |
| Direction batches / cleared traversals | 18 / 81 | 16 / 81 |
| Probe total wall time | 58.81 s | 90.17 s |
| Native step mean / p95 / p99 | 5.17 / 10.52 / 16.04 ms | 7.93 / 24.22 / 28.76 ms |
| Steps above 50 ms / all steps | 0 / 11376 | 25 / 11366 |
| Maximum native step | 47.86 ms | 92.52 ms |

These timing runs were executed sequentially, without overlapping heavy benchmarks/builds. Per-step timing covers `advanceTo` only; setup and total probe wall times are separate. Sensors, aggregation, MongoDB and rendering are excluded. A sample with no deadline misses does not establish a worst-case guarantee. The denser case still has 25 misses of the 50 ms source-step budget.

The long passage waits are a material limitation, not aggregation-window durations: this conservative, single-direction resource can queue pedestrians for minutes. Dense demand and the modeled neck are stress assumptions, not calibrated shopping-street behavior. Complete source drainage is a functional result; it does not demonstrate realistic waiting times or application utility. The slightly earlier high-pressure completion does not indicate better latency: its arrivals are earlier and its maximum waiting time is higher.

## Short observation prefixes

A 60 s prefix of each deterministic run shows the requested density contrast. These are censored views of the same finite cohorts; uncompleted episodes in a short prefix are not lost data.

| At simulated t = 60 s | Lower arrival pressure | Higher arrival pressure |
|---|---:|---:|
| Started / ended | 31 / 4 | 123 / 14 |
| Active / pending | 27 / 161 | 109 / 69 |
| Reported physical overlaps | 0 | 0 |

Probe prefixes include the state at t = 60 s. A Simulator recording ending exactly at 60 s uses an exclusive capture end; its final frame is 59.95 s. Short visual recordings therefore extend to 61 s so the 60 s frame can be inspected directly.

## Defects exposed during verification

The first local rules were insufficient on the actual dense map. Development diagnostics exposed simultaneous targeting of one entry, premature release of staging slots, unready requests holding the resource, an off-guide first entry step at a narrow corner, and forbidden shortcuts through planned bypasses. The source-completion gate was kept failing until the final readiness-based run completed. Selected failed aggregate endpoints are retained in the evidence; they are not presented as a controlled optimization benchmark.

Synthetic regressions cover opposing flow and heterogeneous radii, per-step body separation and lane geometry, finite compatible batches, private-ID/person-order/caller-cadence independence, deliberate holding, invalid metadata, safe unrelated bypasses, bent entry, and an older slow unready request versus younger ready traffic. The readiness test also checks speed and per-step displacement, so passing it cannot depend on accelerated or teleported staging.

## Regression verification

The complete CTest run passed **88 / 88 groups** with no failures (183.40 s).

The probe contract additionally covers malformed arguments, numeric JSON, no identity leakage, aligned short-horizon failure and complete finite-cohort termination. Geometry tests retain the frozen default-source digest and audit generated routes and staging positions. The original default 64/128-person drain cases remain in CTest. All native target builds were completed before the suite.

## Reproduction and next gates

Generate each source locally with `tools/mapped_scene/build_mapped_scene.py`: `--motion-mode storefronts --experimental-narrow-passages --population 128 --seed 20261024 --duration-s 600`, using `--arrival-interval-ms 2000` or `500`, a fresh `--output` under ignored `results/` and a fresh owned `UMP_Mapped_<uuid>` database name. The builder does not write to MongoDB. Then run:

```sh
./simulator/build/MappedMotionProbe results/<scene>/config.yaml --end-ms 600000 --wall-budget-s 180
```

Build the probe with `cmake --build simulator/build --target MappedMotionProbe`. Run the full suite with `ctest --test-dir simulator/build --output-on-failure -j 2` after building all targets. The probe's exit codes are 0 complete, 2 wall budget, 3 unfinished horizon, 64 invalid input and 1 runtime error. Config hashes include the fresh DB namespace; mapped-source and normalized-source hashes support comparisons independently of that namespace.

Remaining gates: the separate 500-total experimental cohort; further densities/seeds and full-pipeline/recipient latency; wider map and navigation topology; calibrated/distributed crossings; and later multimodal crowd behavior. The current finite capacity bound applies to total directional episodes, not only simultaneous waiters, so it is not an unbounded stream or scalability proof. The map remains synthetic-motion OSM geometry, and this work supplies no new privacy guarantee or attack evaluation. Only compact aggregate results enter Git; generated configurations, recordings and movement remain local.

## Short local replays and browser verification

Two independent 61 s captures were generated by the maintained Simulator, verified by the recorder and served locally. They use the same illustrative Policy Tree and its constraints. They remain separate bundles because their observation schedules differ; they are not two policy variants on one observation stream. Each bundle's two policy panes explicitly disclose that they show the same recorded result.

| Recording | Current sample at 54.90 s | Total published cell-windows in 61 s | Unique published spatial IDs |
|---|---:|---:|---:|
| Lower pressure | 25 tracks / 25 distinct XY | 0 | 0 |
| Higher pressure | 102 tracks / 102 distinct XY | 470 | 23 |

The low-pressure prefix has no admissible released cells under these unchanged constraints. Its motion reference remains available. Empty recipient areas mean unavailable information, not released zero traffic. In the higher-pressure browser view, mixed 5 m and 10 m historical cells, their own time intervals, actual category support and policy bounds were inspected. The selected cell 228 had five distinct tracks, category pedestrian, and semantic loss 0.5; this is an operational support result, not a k-anonymity or attack guarantee.

Both browser tabs were checked at 54.90 s and retained. Map names, entrance symbols, recorded type tables and current source counts were visible. The higher-pressure view showed 340 historical publication events by that point and 470 over the full recording. Captures stop before the full cohort drains, as expected; their proof explicitly distinguishes completed recording horizon from completed scheduled episodes. Full-cohort evidence is the separate probe above.

Restart the recordings without MongoDB or a running simulator:

```sh
python3 tools/replay_viewer/serve.py --bundle results/narrow-passage-2026-10-24-low/replay --port 8788
python3 tools/replay_viewer/serve.py --bundle results/narrow-passage-2026-10-24-high/replay --port 8789
```

The `results/` bundles and screenshots remain local and ignored. Only compact capture summaries/hashes are in the committed evidence. Each fresh run's three owned MongoDB namespaces were removed after its verified export; unrelated databases were not reused or cleared.
