# Sequential history-query and merge-feasibility runtime report

Date: 2026-10-23. Baseline: `a402479`. Protocol: [HISTORY_MERGE_OPTIMIZATION_PROTOCOL_2026-10-23.md](HISTORY_MERGE_OPTIMIZATION_PROTOCOL_2026-10-23.md). Aggregate evidence: [HISTORY_MERGE_OPTIMIZATION_RUNTIME_RESULTS_2026-10-23.json](HISTORY_MERGE_OPTIMIZATION_RUNTIME_RESULTS_2026-10-23.json).

## Result and interpretation

Both optimizations preserve the full logical outputs. The final native local replay needs **9.448 and 9.501 s**, compared with a fresh baseline of **11.430 s**: approximately **16.9–17.3% less core processing time** on this capture. The merge lookup supplies most of this benefit. No parallelism, policy, release timing or privacy rule changed.

The history-only gate reduces its target query scope, but its roughly 1% overall reduction is too small, with one native control per stage, to establish a reliable end-to-end improvement independently of host variation. It removes unrelated scanning without a persistent index and preserves bounded payload accounting. The final merge gate gives a materially larger observed reduction, including an independent native repeat.

| Measurement | Fresh baseline | History queries only | History and merge lookup |
|---|---:|---:|---:|
| Native local Temporal First core | 11.430 s | 11.289 s | 9.448 / 9.501 s |
| Native local Spatial First core | Not remeasured | 11.381 s | 9.447 s |
| Instrumented local core | 11.579 s | 11.486 s | 9.600–9.687 s |
| Input-step p95 | 77.39 ms | 78.30 ms | 66.02–68.04 ms |
| Input-step maximum | 86.10 ms | 86.14 ms | 77.34–86.19 ms |
| Input steps exceeding 100 ms | 0 / 199 | 0 / 199 | 0 / 597 |
| EOF service, separate from input steps | 89.80 ms | 94.12 ms | 83.57–85.75 ms |

Each range summarizes three final instrumented runs; the native final value has two runs. The maximum did not improve in every repetition. These measurements do not reconstruct the older 132-ms outlier or establish a hard latency bound.

## What changed and what the counters show

### Single-cell history queries

The history owns each incoming observation vector already. It now sorts that private copy by finest-cell ID once, after validation and before advancing or pruning history. A requested cell selects its contiguous descendant-ID interval by two binary searches, then constructs exactly the same statistics from matching rows. Measured empty and off-domain samples still count toward coverage. Returned caller geometry, exact identity unions, semantic validation, half-open time intervals, retention and validation/rejection behavior are preserved.

For 692,866 single-cell queries, scanned accumulation rows fall from **960,035,498 to 1,619,984**. This counter excludes binary-search comparisons and therefore is not a count of every operation. The profiled query scope falls from **1,879.63 to 1,590.80 ms** at the history-only gate. Append work rises from **18.27 to 24.49 ms** across 199 inputs because the private copies must be sorted. The final profiles measure query work at **1,546.28–1,565.56 ms** and append work at **22.44–22.72 ms**.

A bin with M rows changes from O(M) row inspection per query to O(log M + K) for K matching rows, at the cost of O(M log M) sorting once on append. There is no additional persistent index, copied identity set or history retention. For workloads with very few queries, sorting is a tradeoff rather than a universal speed guarantee. Candidate setup, geometry validation and exact evidence construction remain necessary; eliminating unrelated rows does not eliminate those costs.

### Merge feasibility

The previous `canMerge()` scanned the full frontier. The new implementation first checks proper ancestor IDs, then visits only the domain's descendant-ID range at each depth. Valid depth bands are disjoint, so matching owners retain the former ascending numeric-ID order. Original starts, strict end-after-start, complete area coverage and the four-base-cell boundary are unchanged. There is no cache or extra ownership index.

All runs execute **161,394 merge-feasibility calls**. Visited owner entries fall from **318,528,840 to 1,781,331**, with **523,061 ancestor map probes** and **445,251 depth-range lower-bound probes** added. Map comparisons within those probes are not counted as owner visits. The profiled merge scope falls from **1,710.22 ms** at baseline and **1,682.69 ms** after history optimization to **25.60–26.02 ms** finally. The algorithm changes from O(F) to O(D log F + K), where F is frontier size, D is depth and K is the matching owner count.

## Measurement and correctness gates

The authenticated original moving capture is unchanged: 20 s, 199 inputs at 100-ms cadence, 99,140 contributions, 500 initial Road Users, 80 x 80 m and depth 6. The same ten frozen variants cover six fixed-grid/window configurations and four common/local adaptive configurations. No extra movement data are generated.

The sequential gates are:

1. Fresh baseline: one native local control and one isolated detailed profile, **2 complete output equalities**.
2. History-only: full native ten-variant matrix and one detailed local profile, **11 equalities**; full CTest passed before this measurement gate.
3. History plus merge: full native ten-variant matrix, three detailed local profiles and one native local repeat, **14 equalities**; full CTest passed before this measurement gate.

Each equality compares the entire parsed result JSON, removing only `runtime`. All serialized public releases, private decisions, suppression, metrics, coordination scopes and terminal decisions therefore remain included. Native controls and instrumented programs both match the same authenticated frozen references. All **27 comparisons** pass. The separate test report records the independent geometry/time oracle, semantic cases, mixed-depth coordination oracle and complete test suite.

Builds and tests were paused during each timing block. Core time excludes initial file read and final JSON write. Process wall time, CPU and maximum RSS include the whole executable and are preserved in the compact JSON. Native baseline local process wall was 12.955 s, versus 10.773 and 10.896 s finally. RSS fluctuates across runs, so this report does not infer memory savings from process peaks.

Scopes are inclusive and overlap; they must not be added. Diagnostic per-entry counters perturb the hot loops differently when the number of visited entries changes. The separate native measurements are therefore the evidence for overall speedup, rather than interpreting the profiled scope ratio as an exact production speedup. Unaffected common-window controls varied from about 6.37 s at the history gate to 6.16–6.19 s finally, illustrating host variation.

## Reproduction and limits

`tools/profiling/profile_history_merge_runtime.py` reuses the existing authenticated-study and full-output comparison helper. It accepts `--stage baseline|history|merge`, an explicit native `--binary`, optional frozen `--source-root`, and a fresh `--output` outside the repository. Use `--local-repeat` for the final stage. The default detailed profile counts are 1, 1 and 3. `--wait-for-start` permits the isolated build to finish before the quiet measurement period begins. Each stage has its own `history_merge_<stage>_source_hashes.json` and `history_merge_<stage>_instrumentation.patch`.

From the repository root, verify current-stage inputs and patch applicability without executing a replay:

```sh
python3 tools/profiling/profile_history_merge_runtime.py \
  --root "$PWD" --stage merge --local-repeat \
  --output /private/tmp/ump-history-merge-reproduction-check --prepare-only
```

Choose a fresh directory and omit `--prepare-only` for the final 14 native runs.

Baseline source is commit `a402479`. The history-only profiled source is the final source with `simulator/src/CellLocalAggregation.cpp` restored from that baseline. Final source matches the installed production implementation. The stage manifests authenticate every copied source; patches apply only to the isolated copies, and `RuntimeProfile.hpp` remains absent from production.

Baseline/history measurements used the initially explicit-argument harness. The final harness changes only argument defaults, equivalent stage-condition spelling and preflight repeat metadata; measurement, equality and authentication code are unchanged. The exact earlier bytes are reconstructible by applying `history_merge_initial_harness.patch` to the final harness in an isolated directory. Both hashes and the reverse-patch hash are preserved in the result JSON. The original full private runs remain under `/private/tmp/ump-history-merge-2026-10-23/runs-{baseline,history,merge}`; only aggregate reports, source manifests and profiling tools belong in Git.

There are no observed input-step overruns in these profiles. The hypothetical 100-ms FIFO consequently has zero waiting time, but it is a model of these measured services, not a live queue test. Longer paced runs, renderer/database integration, other densities, other retention horizons and larger regions remain separate evaluation tasks. These optimizations establish no new privacy guarantee and do not change the semantics of published data.
