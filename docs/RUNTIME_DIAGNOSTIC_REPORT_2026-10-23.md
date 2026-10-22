# Frozen replay runtime diagnostic — 23 October 2026

## Result and scope

The local adaptive replay remains slower than the 20 s input stream on this host: the unsampled run uses **25.656 s core processing** and **26.970 s complete process wall time**. The matching common adaptive run uses 6.357 s core processing; the fixed 10 m / 400 ms baseline uses 0.399 s. These reproduce the prior timing scale without changing the algorithm, policy or input.

This is a bounded diagnostic, not a dedicated hardware benchmark or a live end-to-end real-time test. The five runs were sequential. One planned unsampled run was made per method; two further common/local runs attempted stack sampling. Those attempts were denied by macOS and produced no traces. There are no statistical replications of the movement scenario and no confidence intervals for runtime. A subsequent isolated instrumentation stage added three fixed/common/local runs and one refined local diagnostic, for nine native runs in total. All nine preserve the full original logical output.

## Method and integrity

- Frozen source: the existing 500-initial-road-user capture, 199 sensor frames, 99,140 observation rows, 20 s simulated horizon, 100 ms sampling period, 80 m square, depth 6.
- Exact frozen `AggregationReplay` binary and original matched-study policy files, with existing fixed-depth/window overrides for the baseline.
- Policy: published cell side at most 10 m, window duration 400–1,000 ms, age at most 1,000 ms, category support at least 5, maximum semantic loss 1; adaptive release trigger `policy_satisfied`.
- No algorithm edits, new movement, live simulator or MongoDB access.
- All five complete result documents equal their original reference documents after removing only `runtime`. This includes private windows, decisions, counts, intervals, scopes, releases, configuration and semantic information.
- SHA-256 hashes of the binary, observation input, three policy files, three reference outputs and study manifest remain unchanged before/after. Hashes are recorded in the aggregate JSON.
- Complete process wall time is measured with `perf_counter`; native child CPU and maximum resident set size are obtained from Darwin `wait4` resource usage. Sampler resource usage is excluded from those native child counters. RSS units are bytes, converted below to MiB.

## Measurements

| Variant | Core processing (s) | Process wall (s) | Native CPU user + system (s) | Peak RSS (MiB) |
|---|---:|---:|---:|---:|
| fixed_10m_400ms | 0.399 | 1.755 | 1.705 | 595.8 |
| common_window | 6.357 | 7.637 | 7.620 | 556.8 |
| cell_local | 25.656 | 26.970 | 26.936 | 540.1 |
| common_window (sample attempted) | 6.386 | 7.716 | 7.689 | 563.9 |
| cell_local (sample attempted) | 25.728 | 27.075 | 27.036 | 564.2 |

`runtime.processing_ms` starts inside native replay after input/configuration parsing and validation. It includes aggregation, policy/publication work and per-event in-memory JSON serialization. It stops before final outer JSON assembly and output file writing. Complete process wall/CPU/RSS includes all of those stages. The difference between core and process wall time is an observed residual, not a separately instrumented phase measurement.

Peak RSS belongs to the offline adapter, which loads the complete JSON source through yaml-cpp and retains result strings. It is **not** an online history-memory measurement or the footprint of the complete simulator. CPU totals close to wall time are compatible with CPU-bound single-threaded work, but do not identify the dominant function.

The local unsampled run has 7,863 private terminal windows and 2,554 public events/cells; fixed 400 ms has 50 private windows, 50 public events and 2,525 public cells; common has 20 private windows, 20 public events and 1,045 public cells. Local result size is 21.89 MB versus 6.16 MB fixed and 2.59 MB common. This exposes a diagnostic/coordination workload difference, without proving that serialization causes the runtime gap.

## Sampling limitation

`/usr/bin/sample` was invoked for each owned common/local child with a 30 s maximum duration, 1 ms interval and `-mayDie`. Both calls returned 255, reporting that the process could not be examined. No stack output was created. No sudo, security-setting change or alternate attachment was attempted. The two runs retain timer/equivalence evidence only. **There are no OS stack samples or per-thread sample conclusions.** The following isolated instrumentation supplies aggregate function timings without attaching to a process.

## Isolated scoped instrumentation

Production sources remained unchanged. A separate temporary source/build copy uses the same AppleClang 17, arm64, C++17, `-O3 -DNDEBUG`, SFML 3.0.2 and yaml-cpp dependency environment. Fixed-size RAII counters are enabled only within core replay. The profiler reports aggregate scope timings and per-input-tick service durations to stderr after the core timer stops. No identifiers or observations are added to the public result. Source hashes and a reproducible instrumentation patch are retained separately.

The first instrumented runs reproduce all logical output for fixed/common/local. Core time changes relative to the unsampled controls are +3.58%, +1.90% and +3.59%, respectively. A sharper local decomposition changes local core time by +6.05% relative to the original control. These differences combine instrumentation perturbation and ordinary run-to-run variation; they are not a calibrated pure-overhead estimate.

| Local scope, first instrumentation | Calls | Inclusive time (s) |
|---|---:|---:|
| Entire local process | 200 | 26.410 |
| Refinement (`refineDue`) | 398 | 16.940 |
| Finest history reconstruction | 10,160 | 5.097 |
| Single-cell history query | 692,866 | 1.900 |
| Merge-feasibility frontier scans | 161,394 | 1.674 |
| Metric evaluation | 871,229 | 1.190 |
| Terminal publication and diagnostics | 7,863 | 0.378 |
| Private window JSON serialization | 7,863 | 0.295 |

**Times are inclusive and overlap; do not sum them.** Refinement accounts for about 63.7% of the 26.578 s instrumented core run. Terminal work, which includes output serialization, accounts for about 1.4%. Serialization is therefore not the dominant measured local cost in this run.

The sharper local run measures 27.209 s core time and isolates the following:

| Refinement component | Calls | Inclusive time (s) |
|---|---:|---:|
| Complete refinement | 398 | 17.110 |
| Copy ownership frontier | 397 | 0.031 |
| Find owner and refine occupied leaves | 397 | 11.297 |
| `refineToDomain` (nested in that loop, also callable elsewhere) | 209,102 | 2.023 |

There are **1,272,742 occupied-leaf owner searches visiting 2,182,123,527 ownership-map entries**. `refineDue` reconstructs global occupied leaves for each distinct start and searches the owner map linearly for each. This demonstrates a major avoidable search cost. Copying the map itself is small in this workload. Finest-history reconstruction still costs 5.420 s across all contexts in the sharper run and must not be added to refinement time because much of it occurs inside refinement.

Common coordination has a different measured pattern: 140 temporal evaluations invoke 420 spatial proposals and 297,886 single-cell history queries. Those queries scan 1,038,811,065 raw-row positions. Its spatial proposals account for 4.877 s of 6.477 s instrumented core time, including history and metric evaluation. Local single-cell queries scan 960,035,498 row positions and finest queries scan 34,688,262. These are repeated row visits, not numbers of new observations.

## Input-tick service and a bounded queue model

The first instrumented series measures 199 input ticks; EOF processing is reported separately. Service includes synchronous manager/aggregation/publication/diagnostic work for each tick, without input-file parsing or final output-file writing.

| Variant | Median (ms) | p95 (ms) | Maximum (ms) | Tick service > 100 ms |
|---|---:|---:|---:|---:|
| Fixed 10 m / 400 ms | 0.19 | 7.89 | 8.92 | 0 / 199 |
| Common adaptive | 40.61 | 57.64 | 86.85 | 0 / 199 |
| Local adaptive | 134.62 | 176.84 | 205.91 | 171 / 199 |

For a hypothetical FIFO server with these measured service durations, an initially empty queue and arrivals every 100 ms, the local final input completes about **6.980 s after its arrival**; maximum waiting before service is 6.822 s. Of 199 local inputs, 191 have modelled completion delay above 100 ms. Fixed/common accumulate no waiting in this bounded model. EOF adds 7.18 ms fixed, 57.16 ms common and 201.82 ms local service in the first instrumentation series.

This is a queue calculation, not a live paced benchmark. It excludes sensor generation, renderer contention, live database/transport, long-run memory pressure and OS-load changes. It demonstrates why the local implementation currently falls behind this input cadence. Policy timestamps currently use logical simulation time, so they do not account for this additional wall-clock queue delay.

## Source interpretation and remaining hypotheses

The following code paths explain the measured counters and identify further work; they are not OS-sampled rankings:

1. `CellLocalAggregation::process` reconstructs every active owner at an endpoint, including owners not yet due (`simulator/src/CellLocalAggregation.cpp`, around line 621). Each `AggregationHistory::query` loops over all observations in the requested time bins before filtering spatial membership and rebuilds identity and semantic evidence (`AggregationHistory.cpp`, around line 166). This repeats work as the number of owners and endpoints grows.
2. Local refinement calls whole-domain `queryFinest` once for each distinct start, then copies the frontier and searches it linearly for each occupied leaf (`CellLocalAggregation.cpp`, around line 196). The underlying finest query reconstructs exact identity unions and semantic accumulators from raw rows.
3. `selectionFor` reconstructs finest diagnostic history and metrics again per terminal owner (`CellLocalAggregation.cpp`, around line 239). This includes private retirements without public output.
4. Parent planning caches evidence within an endpoint, but an accepted `tryMerge` queries/evaluates the parent again. Publication retry, seal and delivery also re-evaluate candidates. These checks protect retry and publication-time invariants; removing them indiscriminately would change the correctness contract.
5. Common Semantic First runs `SpatialSelector::propose` at ordered loss ceilings. The evidence cache is local to each call, so the same spatial history can be reconstructed across ceilings (`AdaptiveAggregation.cpp`, around line 203; `SpatialSelection.cpp`, around line 95).
6. The aggregation manager still constructs base-window semantic output before the adaptive sink immediately returns without using it (`AggregationManager.cpp`, around line 151; `AggregationReplay.cpp`, around line 403).

The publication retirement ledger is already an immutable persistent tree. Copying it shares four root pointers; retirement path-copies O(depth) nodes (`CellWindowLedger.hpp`). It does **not** copy the complete retirement frontier, so that should not be proposed as a missing optimization.

## Next bounded measurement and optimization gate

The immediate production optimization candidate is **prefix-based ownership lookup**. Because the frontier is disjoint and cell IDs encode ancestry, find a leaf's owner by looking up the leaf and then its ancestors through depth 1 (six map lookups for a depth-6 leaf, O(depth) lookups generally; with `std::map`, O(depth × log owner_count) lookup work) instead of scanning every owner. Check the owner's original start exactly as before, and preserve leaf iteration, split order, policies and publication order. Use the same principle for finding the enclosing owner in `refineToDomain`. This changes search cost, not candidate eligibility, aggregation rules or disclosed data. It is not implemented in this gate.

Then measure fixed/common/local again using the same frozen evidence and an instrumentation-disabled optimized build. A measured speedup is still required; the expected benefit is not a real-time guarantee. Retain the scoped timing harness to ensure that work is not simply moved elsewhere. Only afterwards consider bounded history indexing or evidence reuse for the remaining reconstruction costs.

A real-time claim requires per-tick service-time quantiles/maxima, simulated queue backlog under 100 ms paced arrivals, process memory over a longer run, and eventual live sensor/renderer/database/transport costs. Current policy ages use the logical simulation clock, so wall-clock queue delay is not represented by those policy metrics. Mean speedup alone is insufficient.

If instrumentation confirms reconstruction dominates, first consider bounded immutable spatial indexing of retained batches or reuse of exact `(cell, start, end, watermark)` evidence. Do not sum distinct road users from child counts, discard missing-sample coverage, bypass expiry/retry checks, use unbounded caches, or change release ordering to obtain speedups.

Acceptance for any later optimization: all ten matched-study outputs equal the originals after removing only runtime; all source accounting, semantic policy, public nonoverlap and retirement audits pass; targeted history expiry, missing/unavailable samples, stable-type violations, unequal local starts, handoffs, EOF and sink retry tests remain valid. Report speed and memory together and preserve the original experiment artifacts.

## Artifacts

Raw private outputs, copied production sources, isolated build products and run logs remain in the local temporary directory. The small reproduction harness, instrumentation patch and source-hash manifest are maintained under `tools/profiling/`. `RUNTIME_DIAGNOSTIC_RESULTS_2026-10-23.json` contains only aggregate timings/counts, equality flags and hashes; it contains no road-user identities, positions, trajectories, public/private output records or local capture manifest payload.

The companion `profile_frozen_runtime.py` and `runtime_instrumentation.patch` reproduce the final instrumentation in a fresh temporary source/build directory. Before any native execution, the harness pins the verified study manifest to SHA-256 `e81b724b673ac5f8e77ddd483b41b4ec2756206fbd32ccf2455e14bd234dc83f`, checks its declared binary/policy/reference hashes, authenticates the frozen observation source, and checks production source hashes. It then applies the patch only to the isolated copy, runs uninstrumented fixed/common/local controls and instrumented counterparts, and compares complete outputs excluding only runtime. The patch contains only diagnostic additions; no copied production tree or movement data belongs in Git.

Run from the repository root, with the existing local frozen capture/study available:

```sh
python3 tools/profiling/profile_frozen_runtime.py \
  --root "$PWD" \
  --output /private/tmp/ump-runtime-reproduction-2026-10-23 \
  --prepare-only
```

This verifies and prepares the isolated patch without compilation or replay execution. For the complete six-run reproduction, use a **different fresh output directory** and omit `--prepare-only`:

```sh
python3 tools/profiling/profile_frozen_runtime.py \
  --root "$PWD" \
  --output /private/tmp/ump-runtime-reproduction-full-2026-10-23
```

Both commands require macOS, the locally retained frozen capture/study and installed native build dependencies. The harness deliberately rejects output inside the repository, an existing output directory, changed source, a different study manifest or an artifact that disagrees with its pinned manifest. The reproduction does not retry OS sampling or access MongoDB.
