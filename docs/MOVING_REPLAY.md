# Recorded moving-data replay: implementation and usage

Date: 2026-10-21. Scope: one bounded moving-data mechanism pilot using the existing C++ Simulator, six fixed space/time baselines and three adaptive strategies. This document specifies the implemented tool path and interpretation contract. The [test report](MOVING_REPLAY_TEST_REPORT_2026-10-21.md) and [measured results](MOVING_REPLAY_RESULTS_2026-10-21.md) record the completed acceptance gate and its limits.

Protocol: [predeclared moving-replay pilot](MOVING_REPLAY_PROTOCOL_2026-10-21.md). Mathematical terms: [canonical terminology](TERMINOLOGY_AND_NOTATION.md). Controller: [Semantic First](SEMANTIC_FIRST_IMPLEMENTATION.md). The first experiment uses a uniform application-root policy, without regional overrides, new motion algorithms or membership attacks.

## 1. Input comes from the existing simulator

`tools/evaluation/capture_simulator.py` starts `simulator/build/Simulator` with a generated private configuration. It does not implement a separate movement simulator. The maintained temporal-aggregation example supplies one complete 80 m x 80 m AGBS area, observation depth 6 (4096 possible 1.25 m leaves), a 50 ms numerical simulation step and a 100 ms sensor cadence. Rendering and online aggregation are disabled for this capture so one immutable raw source can be replayed independently.

`--mixed-types` copies the seven existing behavior profiles and weights from `simulator/config.yaml` after checking them: Child Pedestrian 10%, Senior Pedestrian 10%, Adult Pedestrian 35%, Senior Cyclist 10%, Adult Cyclist 10%, Adult E-Scooter Driver 20%, Adult Cargo Cyclist 5%. It introduces no car class or new motion model. The simulator allocates `floor(N*p)` independently per type, so arbitrary requested N need not equal actual initial N. The proposed 200/500/1000 levels are exact under these weights, subject to independent initial GT verification.

Start/destination sampling, existing collision behavior and motion noise are retained. No new users enter after initialization; report the measured population decline. RNG seeding and elapsed-real-time motion noise are unchanged. A repeated simulator execution is not an identical source realization. Reproducibility of the comparison comes from preserving the one captured `observations.json` and replaying those same bytes through every method.

The capture exports full private GT and raw AGBS records. It reconstructs every scheduled sensor sample independently from GT and checks cell geometry and type counts against raw AGBS. Initial `t=0` is GT; sensor observations start at 100 ms. An absent GT record cannot by itself certify an empty global measurement. Incomplete/unverifiable input fails capture.

The GT-to-identity adapter provides privileged identities needed for distinct support; raw GBS/AGBS counts alone cannot establish distinct Road Users across frames. A later realistic sensor/tracking study needs its own identity uncertainty contract.

## 2. Capture commands and isolation

Prerequisites: built C++ simulator and replay binary, Python 3, local MongoDB and `mongosh` on PATH. Commands below run from the repository root. Output directories must not exist.

```sh
python3 -B tools/evaluation/capture_simulator.py \
  --num-agents 500 --duration-seconds 20 --mixed-types \
  --timeout 180 \
  --output results/moving-replay-2026-10-21/n500/capture
```

Repeat with requested N=200 and N=1000 into their own `n200/capture` and `n1000/capture` directories. These independent population-level captures are not paired stochastic realizations of one trajectory population. A 20-second capture is the initial bounded pilot, not the intended final long-session study.

New CLI arguments:

| Argument | Contract |
|---|---|
| `--num-agents N` | Requested starting population, integer 1..5000; default 200 |
| `--duration-seconds S` | Whole simulated seconds, integer 1..600; default 8 |
| `--mixed-types` | Use the seven maintained behavior profiles; without it the temporal example remains Adult Pedestrian only |
| `--output PATH` | New private capture directory; never overwrite |
| `--simulator PATH` | Optional executable override; default repository build |
| `--timeout S` | Positive wall-time limit for the simulator/export operations; distinct from simulated duration |
| `--keep-database` | Retain this capture's owned UUID database after successful verification |

The script creates an owned database named `UMP_Capture_<UUID-token>`, confirms an ownership record, and uses only the expected capture collections. It does not target the maintained `Simulation` database and does not edit the normal simulator configuration. Successful verification normally drops only that owned database; failed captures retain it and their evidence for inspection. `--keep-database` is optional because the exported frozen source is enough for subsequent comparisons and viewing.

Raw exports and replay JSON each have a 256 MiB serialized budget. Exports stream the Mongo cursor into bounded artifacts, but Python validation still loads those bounded arrays. Larger/longer captures must fit the declared limits or fail explicitly; this is not an unlimited streaming archival system. The scenario, population/type counts, GT/AGBS verification, source/binary hashes and configuration copies are recorded in `capture-proof.json` and `capture-manifest.json`.

## 3. Nine release variants on identical observations

```sh
python3 -B tools/evaluation/run_moving_comparison.py \
  --capture results/moving-replay-2026-10-21/n500/capture \
  --output results/moving-replay-2026-10-21/n500/comparison \
  --timeout 180
```

The runner requires a verified capture with matching observation and capture-proof hashes, the declared 80 m/depth-6/100 ms source and a horizon of 2..120 seconds. It freezes the executed replay binary, original input, root policy, protocol and commands. Every variant receives the same observation bytes.

| Variant | Geometry | Time |
|---|---|---|
| `fixed_10m_400ms` | Uniform 10 m, depth 3 | Fixed 400 ms |
| `fixed_10m_1000ms` | Uniform 10 m, depth 3 | Fixed 1000 ms |
| `fixed_20m_400ms` | Uniform 20 m, depth 2 | Fixed 400 ms |
| `fixed_20m_1000ms` | Uniform 20 m, depth 2 | Fixed 1000 ms |
| `fixed_40m_400ms` | Uniform 40 m, depth 1 | Fixed 400 ms |
| `fixed_40m_1000ms` | Uniform 40 m, depth 1 | Fixed 1000 ms |
| `temporal_first` | Adaptive, preserving temporal accuracy | Base 400 ms, extension in 100 ms steps |
| `spatial_first` | Adaptive, preserving spatial accuracy | Base 400 ms, extension in 100 ms steps |
| `semantic_first` | Adaptive, preserving semantic accuracy; TF secondary | Base 400 ms, extension in 100 ms steps |

Fixed baselines use the same Policy Tree evaluator and allowed semantic generalization. A failing fixed cell is suppressed. They model a policy-checked fixed-grid product derived from the shared source, rather than comparing an unprotected GBS stream with a constrained adaptive stream. No globally adaptive uniform-grid algorithm is added here. Six fixed settings are a predeclared grid, not proof of the best possible fixed configuration.

Shared policy: category-specific distinct support at least 5; maximum semantic loss 1; cell side 1.25..40 m; duration and interval-start age at evaluation at most 1000 ms. Every variant uses common-window coordination. No local regions override these first root-level limits.

Release taxonomy `ump-seven-profile-release`, version 1: Road User root loss 1; Pedestrian and Cyclist groups loss 0.5; seven exact profile terminals loss 0. Adult E-Scooter Driver is its own terminal under Road User. This is a release hierarchy over existing labels, separate from simulated movement behavior. The loss values are declared preferences, not calibrated attack probabilities.

History is bounded at 2000 ms, 32 bins, 100000 observations, 16 MB identity strings and 128 bucket descriptors. Each spatial proposal permits 8192 evaluations, above the depth-6 data-tree's 5460-node complete traversal. Resource errors remain system failures, never evidence that a policy was infeasible.

## 4. Verification gate versus measured outcomes

System gate:

- Complete verified input; missing/unavailable versus measured-empty evidence is preserved.
- Independent raw-data reconstruction of scalar counts, distinct identity unions, geometry, nonoverlap and source accounting.
- Independent reconstruction of each released semantic bin, complete truthful category cut, support and loss checks.
- Actual hard constraints remain unchanged across the three adaptive strategies and six baselines.
- Frozen-input deterministic rerun excluding runtime only; source/config/binary/result hashes archived.
- Viewer schema/time/geometry compatibility and future-release gating checked independently.

These establish implementation correctness within the declared scope. They do not establish that adaptive output is more useful or more private.

Measured mechanism/utility outcomes:

- Retained observation contributions / source contributions, suppression, weighted cell side, declared semantic loss and interval-start age.
- Source population/type evolution and realized displacement, rather than requested count alone.
- Fixed 10 m square / 1000 ms all-road-user mean sampled occupancy queries; query availability and conditional MAE together.
- Logical deadlines at query end + 0, 200 and 1000 ms, with a fixed interior cohort and separate boundary/EOF treatment.

The occupancy estimator assumes uniform allocation within a released cell and constant occupancy within its interval, following the existing fixed-query utility contract. These estimates use public releases only. Missing public coverage is unknown, never zero. This moving workload is different from the earlier conservative **exact semantic count** query bank: do not mix those coverage percentages or infer class-query utility from all-road-user occupancy.

One capture per N and one deterministic replay repeat are not statistical repetitions. No new membership attack, privacy gain, equal-privacy comparison with LDP, global scheduling optimum or sensor-to-application latency is measured. Suppression of everything can satisfy release soundness while failing usefulness; report denominator-zero cases explicitly.

## 5. View the recorded motions and release decisions

Validate the complete bundle, then launch the local viewer:

```sh
python3 tools/replay_viewer/serve.py \
  --bundle results/moving-replay-2026-10-21/n500/comparison --check

python3 tools/replay_viewer/serve.py \
  --bundle results/moving-replay-2026-10-21/n500/comparison --port 8765
```

Open `http://127.0.0.1:8765/`; stop with Ctrl+C. No MongoDB is needed for viewing. The server binds to localhost and exposes only the viewer assets and declared bundle JSON files, not the repository directory. No npm build or external network assets are required.

The bundle's `bundle.json` names one `ump.observation-replay.v1` source and nine `ump.replay-result.v1` outputs. Run ID, sensor ID, coverage, cadence and horizon must match; file references are relative and path traversal/external symlinks are rejected. The browser provides shared play/pause, seek and release-event navigation with independently selected comparison variants.

Interpretation contract:

- The private reference displays actual sampled XY positions at the 100 ms sensor cadence, not every 50 ms integration step. It holds a sample only until the next expected sample, clears it if unavailable/missing and performs no interpolation.
- Recipient panels reveal a release only at or after its recorded `sealed_at_ms`. They retain the latest complete historical snapshot until a later sealing event, with the original interval and age shown. The label is mean sampled occupancy, not instantaneous traffic.
- Blank recipient areas are unknown. A private overlay shows finalized diagnostic windows and suppressed footprints gated by `evaluated_at_ms`; those diagnostics are not recipient output and do not show every intermediate pending evaluation.
- Cell inspection shows real stored geometry, counts and semantic bins. Policy checks appear only in private diagnostics. Cuts change at recorded events; no invented merge/split animation is added.
- Cumulative release totals use the whole-run input denominator, so at an early playhead they are replay progress, not a time-local retention estimate.
- The first viewer supports common-window snapshots. Independently timed cell-local streams need a separate spatial validity view before being added.

The bundle contains raw identities/positions and diagnostic thresholds. It remains private research material even when the recipient display filter is selected; a sanitized public export is a separate artifact.

## 6. Presentation and next research steps

For the 20-minute talk, show one synchronized recorded comparison, one fixed-query outcome plot and one information/delay trade-off. State the question and conditional answer before architecture. Use the older stationary 27-case results only with their own source/utility labels. New moving results belong in slides only after the system gate and artifact audit pass.

Next questions, in order:

1. On this frozen moving source, where do adaptive modes improve or lose against the six fixed settings, and what cost in delay, spatial detail and semantic detail explains it?
2. Does that pattern persist across independently captured sessions, occupancy density and identity turnover? Predeclare replication/seeds before interpreting stability.
3. Do heterogeneous spatial densities and stricter regional requirements create local opportunities or unavoidable infeasibility? Add one factor at a time, retaining identical method inputs.
4. Does semantic generalization preserve useful class-specific tasks? Add a declared class-query workload; all-road-user occupancy does not answer it.
5. Only then evaluate stronger privacy claims/attack models and an external ALOQ comparator. ALOQ's longitudinal LDP and noisy frequency product require a separate adapter and guarantee comparison, not an epsilon-to-support conversion.

Maps, new movement planners, cell-local semantic coordination, further priority combinations, proactive caching and computational optimization remain separate backlog items. They are not prerequisites for recording, inspecting and comparing this first moving pilot.

## 7. Maximum output-cell variants

The optional `--max-cell-side-m {40,10,5}` selects a hard Policy Tree maximum
and compatible search depth. Default 40 retains the original policy/matrix.
The [cap-study commands](CELL_SIZE_CAPS.md), [frozen follow-up protocol](CELL_SIZE_CAP_PROTOCOL_2026-10-21.md)
and [measured results](CELL_SIZE_CAP_RESULTS_2026-10-21.md) describe the separate
10 m/5 m matrices. Existing recorded sources and original 40 m outputs stay frozen.
