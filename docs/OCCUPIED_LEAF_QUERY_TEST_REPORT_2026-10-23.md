# Occupied-leaf history query: implementation and verification

Date: 2026-10-23. Baseline: `a304870`. Follow the
[predeclared bounded protocol](OCCUPIED_LEAF_QUERY_PROTOCOL_2026-10-23.md).
[Test evidence and source/log hashes](OCCUPIED_LEAF_QUERY_TEST_RESULTS_2026-10-23.json)
and the [runtime comparison](OCCUPIED_LEAF_QUERY_RUNTIME_REPORT_2026-10-23.md)
record separate correctness and performance checks.

## Why this change

After prefix-based ownership lookup removed the linear frontier searches, repeated
per-tick profiling identified unnecessary full history reconstruction in
`CellLocalAggregation::refineDue`. That caller uses only occupied leaf geometry.
The old call nevertheless computed scalar counts, distinct-identity sets and full
per-leaf semantic evidence. See the
[per-tick diagnosis](TICK_RUNTIME_DIAGNOSTIC_REPORT_2026-10-23.md) for evidence and
why the former 132.6855-ms outlier cannot be attributed to one function afterward.

## Implemented behavior and equivalence

`AggregationHistory::queryOccupiedLeaves(startMs, endMs)` discovers occupied IDs
in the retained half-open interval and returns their canonical geometries in
ascending ID order. It visits only stored observations; it creates no dense leaf
array and no parent/preemptive buckets. Only `refineDue` uses this new API. Actual
candidate statistics, policy checks, diagnostics, releases, independent window
starts, expiry and ownership rules continue to use their existing paths.

The sparse result carries the existing history status. Future and evicted history
have no result vector; retained history has a vector that can be empty. Missing
and explicitly unavailable samples remain Incomplete even if other observations
supply occupied leaves. A measured empty interval differs from a missing sample.
The existing half-open scheduled-sample arithmetic and absent initial t=0 sample
are preserved. Geometry is reconstructed from canonical IDs, so tolerated tiny
input geometry deviations are not propagated.

One global `SemanticAccumulator` is deliberately retained. It validates a stable
canonical terminal type for each identity across all cells in the queried interval,
accepts aliases and retains exact semantic count-range checks. A per-leaf subset
cannot exceed the corresponding whole-interval semantic count. This permits
removing per-leaf accumulators and their evidence copies without weakening those
checks. The global validator still performs semantic work: this is not a claim
that all semantic processing has been removed. With taxonomy disabled, historical
raw-label changes remain accepted as before.

All distinct-start queries finish successfully before the temporary frontier is
refined, then committed. Invalid history still fails before partial refinement or
publication. The lighter query changes allocations and could therefore change
allocation-failure behavior; it does not promise identical bad-allocation timing.
No cache, policy relaxation, reduced sampling rate or altered anonymization action
is introduced.

## New behavioral regression coverage

The dedicated `occupied_history` CTest target includes six cases:

| Case | Contract |
| --- | --- |
| Sparse support and canonical geometry | Sorted occupied IDs, repeated/moving identities, input ownership, returned-vector ownership and canonical output despite accepted small input geometry offsets. |
| Sample boundaries and coverage | Half-open/off-cadence intervals, absent t=0, no scheduled samples, measured empty samples, missing samples and explicit unavailability. |
| Expiry and invalid requests | Inclusive retention boundary, Evicted-before-Future precedence, invalid-interval rejection and no history mutation. |
| Semantic validation | Cross-cell canonical-type conflict rejection, same-terminal aliases, disabled-taxonomy behavior and unknown-type rejection before append mutation. |
| Sparse depth 14 | Four base quadrants, maximum valid ID 1,073,741,823 and no dense 4^D allocation. |
| Independent mixed-history oracle | 500 time/row comparisons over depths 1, 2, 4, 6 and 14, bounded source retention and nonmutation. |

The oracle derives scheduled times and occupied support from separately retained
input rows rather than using `queryFinest` as its sole reference. A legacy-query
comparison additionally checks compatibility. An integration regression in
`SemanticCellLocalTests` rejects an identity changing terminal type across base
cells before frontier, clocks or outputs change; the suite now has 15 local gates.

The existing accumulator itself enforces the enormous exact-count limit; the tests
do not manufacture more than 2^53 observations to reach it.

## Full build and test run

The actual Simulator, AggregationReplay and all enabled test targets build in the
existing Release configuration. **69 / 69 CTest suites pass**, 0 failures, **20.20 s**
wall time with four test workers. The complete suite covers history/metrics/policies,
coordination and stress, semantic selection, publication and retry, replay,
recipient utility, renderer frames and viewer behavior. The four MongoDB integration
suites use isolated UUID test databases; the normal `Simulation` database is not
reset and the normal Simulator is not launched.

```sh
cmake --build simulator/build --parallel 4
ctest --test-dir simulator/build --output-on-failure --parallel 4
```

The primary agent separately reparsed all 18 complete baseline/new outputs and
recomputed all six input-tick distributions and FIFO traces from the detailed logs.
Only `runtime` was excluded from the output comparisons. The pinned parent manifest,
21 baseline artifacts and observation source were authenticated independently.

No build or CTest run overlaps the subsequent timed replay sequence. The runtime
report provides the complete ten-variant output-equivalence checks and measured
service times. Raw observations/releases, native build products and detailed local
logs remain outside Git. Historical protocols and reports remain unchanged.

## Limits and next gate

This optimization preserves the current mechanism rather than improving its
privacy or utility decisions. Passing tests and equal frozen outputs establish
behavior for the checked contracts and workloads; they do not prove arbitrary
input correctness or hard real-time operation. Longer paced replay and then the
live sensor/renderer/database path must measure actual queueing, receipt delay,
memory growth and overload behavior. Logical policy age remains separate from
wall-clock computation and transport latency.
