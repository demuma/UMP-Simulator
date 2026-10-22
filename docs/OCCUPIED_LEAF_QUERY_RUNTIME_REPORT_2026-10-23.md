# Occupied-leaf query: runtime validation and slow-tick diagnosis

Date: 2026-10-23. Protocol: [OCCUPIED_LEAF_QUERY_PROTOCOL_2026-10-23.md](OCCUPIED_LEAF_QUERY_PROTOCOL_2026-10-23.md). Aggregate evidence: [OCCUPIED_LEAF_QUERY_RUNTIME_RESULTS_2026-10-23.json](OCCUPIED_LEAF_QUERY_RUNTIME_RESULTS_2026-10-23.json). Baseline source: `a304870`.

## Result

The optimized local coordinator processes the frozen 20 s recording in **11.339 s** core time; a final uninstrumented repeat takes **11.624 s**. The freshly measured prefix-only baseline takes **14.377 s**. This is **21.13% / 19.15% less core processing time**, respectively. Ten optimized variants, three isolated detailed profiles and a final repeat reproduce their complete frozen JSON result after removing only `runtime`: **14 / 14 equal**. Including the four new baseline runs, **18 / 18 full-output comparisons pass**.

Across the three optimized profiles, input-tick p95 is **76.919 / 77.601 / 77.507 ms**, maximum **90.610 / 96.363 / 87.245 ms**, and **none of 597 input services exceeds 100 ms**. The corresponding repeated prefix-only baseline has p95 **96.464 / 95.511 / 96.788 ms**, maxima **111.940 / 103.343 / 104.886 ms**, and **6 / 3 / 3** services above 100 ms. No independent mobility realizations or worst-case bound are implied by these repeats.

## What caused the old 132.69 ms sample?

The historical maximum was **132.6855 ms at logical time 15,200 ms**. The old profile did not collect per-tick function scopes or CPU time. Replaying unchanged code with detailed instrumentation measures the same logical tick at **89.704 / 89.027 / 92.324 ms**. Its precise historical cause is therefore **not recoverable**; it must not be presented as a deterministic 132-ms algorithmic branch or confidently blamed on OS scheduling.

Nevertheless, recurring workload pressure is real. The repeated baseline maximum in runs 2 and 3 consumes **103.262 / 104.871 ms of thread CPU**, respectively, alongside **103.343 / 104.886 ms wall service**. These misses are predominantly computation. The isolated run-1 outlier at 12,700 ms has 110.157 ms wall versus 102.211 ms CPU, showing an additional wall-time component not accounted for by thread CPU time.

Slow recurring endpoints include 3 s, 9 s, 11 s and 11.2 s. At 3 s the coordinator retires 176 terminal windows and evaluates metrics 5,968 times. At 9 s it retires 124 windows, evaluates metrics 5,280 times and handles seven distinct history starts in each of two refinement calls. Across baseline repeats, ticks divisible by 1 s average 93.80–94.92 ms and those divisible by 400 ms average 84.36–84.89 ms; these groups overlap. Ticks on neither boundary average 67.48–67.62 ms. This describes concentrated evaluation work, not a causal experiment changing window policy.

## Tested optimization

Refinement needs only the occupied finest-cell geometries for each relevant historical interval. The original path nevertheless created per-leaf observation/type counts, distinct-identity sets and semantic evidence, then discarded those statistics. The dedicated `queryOccupiedLeaves()` uses exact retained observations to return sorted unique geometries, preserving interval/status checks and global semantic identity/type validation. Other metric, selection and publication queries still reconstruct full evidence.

There are **2,247** replacement queries. The combined finest/occupied row visits remain **34,688,262**: **29,664,514** visits in the remaining 7,913 full finest queries, plus **5,023,748** visits in the new occupied-leaf queries. This change avoids unnecessary reconstruction; it does not skip observed rows or shorten history. All six detailed traces have identical per-tick workload counters and call counts after treating the replaced query as one category.

| Inclusive scope, whole 20 s replay | Prefix-only repeats (s) | Optimized repeats (s) | Interpretation |
|---|---:|---:|---|
| Complete refinement | 5.362–5.371 | 2.053–2.077 | Includes history query, temporary handling and occupied-path splitting |
| History query inside refinement | 4.711–4.719 | 1.807–1.834 | New query retains exact geometry and validation, omits unused per-leaf statistics |
| Single-cell history queries | 1.848–1.851 | 1.888–1.900 | 692,866 calls; full history filtering and exact evidence remain |
| Merge feasibility | 1.615–1.639 | 1.642–1.672 | 161,394 frontier-based feasibility checks |
| Metric evaluation | 1.169–1.182 | 1.205–1.216 | 871,229 calls; no tests skipped |
| Fresh-owner compaction | 0.845–0.852 | 0.875–0.891 | Coordination path remains unchanged |
| Terminal publication/diagnostics | 0.365–0.368 | 0.376–0.383 | Includes private-window and public-release serialization |

**Inclusive times overlap and must not be summed.** Refinement includes occupied-query time; metric/history checks are called inside other coordination scopes. Terminal includes publication and serialization. Only these measured scopes are reported; their sum is not a partition of all core time. The remaining full finest-query time is 0.217–0.220 s, and `refineToDomain` takes 0.135 s. The old linear owner scan remains absent.

The leading remaining candidates are the **960,035,498 row-position visits in single-cell history queries** and merge-feasibility/frontier scans, plus the preserved global validation inside occupied-leaf discovery. Any future indexing or evidence reuse needs a separate bounded change with expiry, distinct-union, semantic consistency, policy and ACK/retry checks. This gate implements none of those further changes.

## Native matrix and resource accounting

| Variant | Core (s) | Whole-process wall (s) | Native CPU user + system (s) | Peak RSS (MiB) | Full logical equality |
|---|---:|---:|---:|---:|---|
| `fixed_2p5m_400ms` | 1.021 | 2.506 | 2.379 | 604.2 | Yes |
| `fixed_2p5m_1000ms` | 0.561 | 1.878 | 1.873 | 571.7 | Yes |
| `fixed_5m_400ms` | 0.663 | 1.994 | 1.989 | 533.4 | Yes |
| `fixed_5m_1000ms` | 0.374 | 1.668 | 1.663 | 603.9 | Yes |
| `fixed_10m_400ms` | 0.426 | 1.767 | 1.761 | 563.8 | Yes |
| `fixed_10m_1000ms` | 0.269 | 1.593 | 1.581 | 504.2 | Yes |
| `common_window_temporal_first` | 6.604 | 7.932 | 7.925 | 547.7 | Yes |
| `common_window_spatial_first` | 6.568 | 7.907 | 7.900 | 571.9 | Yes |
| `cell_local_temporal_first` | 11.339 | 12.670 | 12.652 | 479.5 | Yes |
| `cell_local_spatial_first` | 11.462 | 12.816 | 12.799 | 563.9 | Yes |

The local final repeat takes 11.624 s core and 13.014 s whole-process wall time. Instrumented local cores are 11.579 / 11.624 / 11.557 s. Differences from the uninstrumented runs combine profiler perturbation and host/run variation; they are not isolated profiler-overhead measurements. Fixed/common paths retain their previous timing scale. Peak RSS includes the offline source, complete retained diagnostics and output serialization; these runs do not establish an online-memory improvement.

## Instrumented service and hypothetical queue

| Profile | Input p95 (ms) | Input maximum (ms) | Input service > 100 ms | EOF service (ms) | Hypothetical FIFO maximum wait (ms) |
|---|---:|---:|---:|---:|---:|
| Prefix 1 | 96.464 | 111.940 | 6 / 199 | 110.569 | 11.940 |
| Prefix 2 | 95.511 | 103.343 | 3 / 199 | 114.527 | 3.343 |
| Prefix 3 | 96.788 | 104.886 | 3 / 199 | 112.691 | 4.886 |
| Occupied 1 | 76.919 | 90.610 | 0 / 199 | 94.236 | 0.000 |
| Occupied 2 | 77.601 | 96.363 | 0 / 199 | 95.217 | 0.000 |
| Occupied 3 | 77.507 | 87.245 | 0 / 199 | 96.839 | 0.000 |

Quantiles use nearest rank `ceil(p*n)`. The FIFO calculation assumes an initially empty single-server queue and arrivals every 100 ms. It is a model applied to measured service times, not a live paced execution. EOF is outside the 199 periodic input services. The former maximum at 15.2 s now measures 74.449 / 74.393 / 76.398 ms.

The largest optimized sample (96.363 ms at 18.8 s, run 2) uses 92.640 ms thread CPU. The first and third maxima use 90.582 / 87.165 ms CPU versus 90.610 / 87.245 ms wall. Instrumented service includes RAII timer overhead but excludes the extra per-tick counter snapshot, recorded-tick serialization, initial input parsing and final outer JSON/file write.

## Method, invariants and reproducibility

- Same authenticated 20 s source and ten policies as the moving study: observation SHA-256 `ab4fadf254bfb5432018ff4bd305cd16d82a7475ae3d934c14c4f9af67dd5cf1`; parent manifest SHA-256 `e81b724b673ac5f8e77ddd483b41b4ec2756206fbd32ccf2455e14bd234dc83f`. No new movement or MongoDB access.
- Baseline: one uninstrumented local control and three detailed profiles, sequentially before the implementation build. Optimized: six fixed variants, two common variants, two local variants, three detailed local profiles and a final local repeat. Repository build/tests were complete and other heavy agent tasks paused during each measurement block.
- Production sources and executable, study artifacts, capture and protocol hashes are checked before and after optimized runs. Detailed instrumentation applies only to a separate temporary source copy, built with AppleClang 17, arm64, C++17, `-O3 -DNDEBUG`, SFML 3.0.2 and yaml-cpp. The isolated patch preserves production includes, including `<set>`.
- Full output equality removes only the `runtime` object and compares all remaining JSON values. This includes all private candidate/decision records and public releases, not merely aggregate counts.
- Scope clocks are inclusive wall time. Thread CPU uses `CLOCK_THREAD_CPUTIME_ID` at tick start/end; the isolated probe does not check its syscall return, but all observed CPU values were positive finite and consistent with native CPU accounting. No CPU clock or extra timing operation is inserted inside row loops.
- `frontier_peak` is the maximum size sampled **before refinement** during a tick, not a continuously observed/intermediate-state maximum. Distinct-start totals count both refinement calls where applicable. Row counters count visited positions, not unique people.
- Preflight rejects a changed source hash and output inside the repository before creating the output directory. A positive prepare-only pass validates authentic inputs and patch applicability without native execution.
- The compact aggregate JSON contains the new source/binary/protocol/tool hashes, timing summaries, top ten detailed ticks for each profile, and equality results. Raw observations/results and copied source trees remain local under `/private/tmp/ump-tick-2026-10-23`.

From the repository root, use the current Release build and frozen local capture/study:

```sh
python3 tools/profiling/profile_occupied_runtime.py \
  --root "$PWD" \
  --output /private/tmp/ump-occupied-reproduction-check \
  --prepare-only
```

For all 14 native runs, choose a fresh output directory and omit `--prepare-only`. The optional `--wait-for-start` signal file lets compilation finish before a measurement block starts. Production sources must match `occupied_runtime_source_hashes.json`; changed source requires a reviewed new patch/manifest.

To reproduce the detailed prefix baseline, use a separate source checkout/build at `a304870`, the same frozen capture/study and this harness with `--baseline-only`. Point `--patch` to `tick_runtime_instrumentation.patch`, `--source-hashes` to the existing `prefix_runtime_source_hashes.json`, `--root` to that old checkout, and `--binary` to its Release executable. Supply `--study` and `--source` explicitly if the frozen files stay in the main checkout. That mode authenticates the old source and executes one local control plus three detailed local profiles; no raw data copies need to enter Git.

## Limits and next gate

All measured input services in the three optimized traces are below the 100-ms arrival period, with unchanged disclosures. This is not a hard real-time bound. These runs exclude live simulation, renderer, MongoDB and transport, and do not control all concurrent workload or operating-system scheduling effects; logical policy age does not include wall-clock queue delay. The smallest observed input margin is only about 3.6 ms in one repeat, so longer paced runs and explicit end-to-end queue/receipt timing remain necessary.

Before another optimization, run a longer paced replay with actual arrival/completion/backlog timestamps and a defined overload contract. Further work should preserve the exact output and metric decisions, and be selected from the measured remaining costs rather than from the historical one-off maximum.
