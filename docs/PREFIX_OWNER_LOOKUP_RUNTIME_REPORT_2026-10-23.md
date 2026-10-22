# Prefix owner lookup: frozen runtime validation

Date: 2026-10-23. Protocol: [PREFIX_OWNER_LOOKUP_PROTOCOL_2026-10-23.md](PREFIX_OWNER_LOOKUP_PROTOCOL_2026-10-23.md). Aggregate evidence: [PREFIX_OWNER_LOOKUP_RUNTIME_RESULTS_2026-10-23.json](PREFIX_OWNER_LOOKUP_RUNTIME_RESULTS_2026-10-23.json).

## Result

All ten optimized matched-study variants reproduce their complete original JSON outputs after removing only `runtime`. The extra original local control, three isolated instrumented controls and one optimized local repeat also pass this comparison: **15 / 15 native runs are logically identical to their respective references**. This covers all private candidates, decisions, windows and public releases, not only counts or headline utility metrics. The optimization changes lookup work without changing this study's recipient answers, policies or disclosure behavior.

The first optimized local run uses **14.881 s core processing**, versus **25.594 s** for the freshly repeated original binary: **41.86% less core time**, or **1.720× relative core throughput**. The optimized repeat uses 14.773 s. Processing the 20 s recording therefore has a core simulated-time/processing-time ratio of about **1.344×**, distinct from the relative optimization ratio. Whole-process wall time changes from 26.945 s to 16.241 s (repeat 16.122 s).

The local instrumented input-tick p95 is **98.29 ms**, maximum **132.69 ms**. **Seven of 199 input ticks still exceed the 100-ms input period.** The hypothetical FIFO model reaches 32.69 ms maximum waiting and 132.69 ms maximum completion delay; its last input completes 79.26 ms after arrival. The measured trace no longer accumulates seconds of backlog, but this is **not a hard real-time or live end-to-end guarantee**.

## Method, integrity and reproducibility

- Same frozen 20 s capture: 500 initial road users, 199 scheduled input frames at 100-ms cadence, 99,140 contributions, 80 m square, finest depth 6. No new movement or MongoDB access.
- Same ten variant policy files, fixed-grid depth/window command-line overrides and reference results as the verified moving study. The pinned parent manifest SHA-256 is `e81b724b673ac5f8e77ddd483b41b4ec2756206fbd32ccf2455e14bd234dc83f`; the observation SHA-256 is `ab4fadf254bfb5432018ff4bd305cd16d82a7475ae3d934c14c4f9af67dd5cf1`.
- The harness authenticates 21 parent artifacts (frozen executable, ten policies, ten reference results), the observation source, optimization protocol, optimized executable and source manifest. All remain unchanged after execution. The source-hash difference from the historical profile is confined to `CellLocalAggregation.cpp` and `.hpp`.
- The actual production executable was rebuilt in Release before validation. Instrumentation is added only in a separate temporary source tree, built with AppleClang 17, arm64, C++17, `-O3 -DNDEBUG`, SFML 3.0.2 and yaml-cpp. No profiler code enters production.
- The 15 runs execute sequentially, after the repository's build/tests complete. Order: original local control; ten optimized variants; instrumented fixed/common/local; optimized local repeat. No statistical confidence interval is claimed. Repeating native work on the same recording does not create independent mobility realizations.
- Wall time is native-process lifetime; CPU and maximum RSS come from Darwin `wait4`. Core time includes manager/aggregation/publication work and in-memory per-event JSON serialization, but excludes input parsing/validation, final outer JSON assembly and file output. RSS includes full offline source parsing and retained private diagnostics, not merely online history memory.
- Preflight checks were exercised against a changed manifest and changed policy; both fail before executable invocation. Explicit fixtures verify an empty FIFO, sustained overload, nearest-rank quantiles and rejection of a missing scheduled tick. All ten override pairs were checked against authenticated reference metadata.

The copied executable, raw result files, copied sources and build products stay in `/private/tmp/ump-prefix-2026-10-23/runs`. Only the compact aggregate results, harness, patch and source hashes belong in Git. Existing historical profiling artifacts are preserved.

From the repository root, with the local frozen capture/study and a current Release `simulator/build/AggregationReplay` available:

```sh
python3 tools/profiling/profile_prefix_runtime.py \
  --root "$PWD" \
  --output /private/tmp/ump-prefix-reproduction-check \
  --prepare-only
```

This authenticates and stages instrumentation without compilation or native replay. Use a **different fresh output directory** and omit `--prepare-only` for all 15 native runs. The harness rejects output inside the repository, an existing output directory, changed production source, changed frozen policy/reference/input, or a different parent manifest. `--wait-for-start` is an optional local signal-file gate after compilation, used in this validation to avoid contention with CTest. The recorded protocol/harness/patch/source/binary hashes identify this execution; later source changes require a reviewed new instrumentation manifest.

## Ten-variant optimized matrix

| Variant | Core (s) | Process wall (s) | Native CPU user + system (s) | Peak RSS (MiB) | Full logical equality |
|---|---:|---:|---:|---:|---|
| `fixed_2p5m_400ms` | 0.996 | 2.471 | 2.341 | 587.6 | Yes |
| `fixed_2p5m_1000ms` | 0.545 | 1.851 | 1.844 | 563.7 | Yes |
| `fixed_5m_400ms` | 0.654 | 1.962 | 1.955 | 518.7 | Yes |
| `fixed_5m_1000ms` | 0.366 | 1.660 | 1.655 | 579.6 | Yes |
| `fixed_10m_400ms` | 0.426 | 1.730 | 1.725 | 563.6 | Yes |
| `fixed_10m_1000ms` | 0.267 | 1.531 | 1.526 | 534.9 | Yes |
| `common_window_temporal_first` | 6.523 | 7.833 | 7.820 | 579.9 | Yes |
| `common_window_spatial_first` | 6.471 | 7.783 | 7.775 | 579.9 | Yes |
| `cell_local_temporal_first` | 14.881 | 16.241 | 16.194 | 518.5 | Yes |
| `cell_local_spatial_first` | 14.807 | 16.148 | 16.135 | 571.8 | Yes |

The original fresh local control reaches 571.6 MiB peak RSS; the optimized local first run reaches 518.5 MiB and repeat 604.0 MiB. These variations do not support a memory-reduction claim. Fixed/common runtime remains on the previous measurement scale, consistent with their unchanged coordinator paths.

## Scoped explanation

The optimized local instrumentation uses 15.020 s core time, **0.94% above** the first uninstrumented optimized run and 1.67% above its repeat. These differences combine instrumentation perturbation and ordinary host/run variability; they are not isolated profiler-overhead estimates. Instrumented fixed/common core times are 0.433 / 6.622 s, versus 0.426 / 6.523 s uninstrumented.

| Scope or counter | Historical sharper local profile | Optimized local profile |
|---|---:|---:|
| Complete refinement, inclusive time | 17.110 s | 5.568 s |
| Copy ownership frontier | 0.031 s | 0.029 s |
| Owner lookup and occupied-path refinement loop | 11.297 s | 0.182 s |
| `refineToDomain`, inclusive time | 2.023 s | 0.134 s |
| Finest-history reconstruction, all contexts | 5.420 s | 5.103 s |
| Single-cell history queries, all contexts | 2.031 s | 1.884 s |
| Occupied-leaf owner searches | 1,272,742 | 1,272,742 |
| Entries visited by old linear owner scan | 2,182,123,527 | No linear scan |
| New prefix helper calls, both contexts | Not applicable | 1,514,046 |
| New prefix `map.find` calls, both contexts | Not applicable | 2,098,200 |

The historical sharper instrumentation is from the previous diagnostic, not a fresh paired instrumented control. Its 27.209 s core time differs from today's uninstrumented control because of both instrumentation and ordinary variation. **Inclusive scope times overlap and must not be summed.** Map `find` probes are not internal tree-key comparisons, so their count must not be treated as the same unit as old linear map entries visited or as a proportional total-speedup claim.

There are still exactly 10,160 finest-history calls, 692,866 single-cell history calls, 161,394 merge-feasibility checks, 871,229 metric evaluations, 209,102 `refineToDomain` calls, 7,863 terminal windows and 2,554 public events. Finest-history scans visit 34,688,262 row positions; single-cell queries visit 960,035,498. These counts match the historical diagnostic. The lookup change has not skipped history evidence, metric evaluations or publications.

Measured remaining inclusive local costs include finest-history reconstruction (5.103 s), single-cell history queries (1.884 s), merge-feasibility frontier scans (1.655 s), metric evaluation (1.200 s) and owner compaction (0.876 s). Terminal publication/diagnostics uses 0.376 s, including private-window serialization at 0.294 s. The cost is now concentrated more strongly in evidence reconstruction and coordination work; serialization remains comparatively small in this workload. The next bounded optimization candidate is immutable indexing or safe reuse of exact history evidence, with the same full-output, union, coverage, expiry and retry checks retained.

## Tick service and modelled waiting

Quantiles use nearest rank, `ceil(p*n)`, over 199 input services; EOF is reported separately. Service includes the synchronous replay manager, aggregation, publication and diagnostic processing for each input, excluding initial file parsing and final output-file writing.

| Optimized instrumented variant | p50 (ms) | p95 (ms) | Maximum (ms) | Service > 100 ms | FIFO maximum waiting (ms) |
|---|---:|---:|---:|---:|---:|
| `fixed_10m_400ms` | 0.20 | 8.32 | 8.88 | 0 / 199 | 0.00 |
| `common_window_temporal_first` | 42.11 | 59.59 | 63.57 | 0 / 199 | 0.00 |
| `cell_local_temporal_first` | 74.10 | 98.29 | 132.69 | 7 / 199 | 32.69 |

EOF service is 7.82 ms fixed, 59.08 ms common and 117.97 ms local. In the local FIFO model, seven input completion delays exceed 100 ms; the final input delay is 79.26 ms. The previous first local instrumentation had p95 176.84 ms, 171 services above 100 ms, 6.822 s maximum waiting and 6.980 s last-input completion delay. These are bounded measurements on the same recording, not a scheduler guarantee.

A live real-time claim still requires longer paced runs, wall-clock queue/receipt timestamps, bounded overload behavior and live sensor, renderer, database and transport measurements. Existing policy ages are logical-simulation-time constraints; they do not automatically include wall-clock queue waiting. Average throughput being above 1× does not guarantee every deadline. This optimization also leaves the scientific fixed-grid advantage and query-boundary losses unchanged; those require separate same-input policy and estimator comparisons.
