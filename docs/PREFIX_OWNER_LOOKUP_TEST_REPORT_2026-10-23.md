# Cell-ID owner lookup: implementation and verification

Date: 2026-10-23. Protocol:
[bounded owner-lookup optimization](PREFIX_OWNER_LOOKUP_PROTOCOL_2026-10-23.md).
Compact test verification: [source/log hashes](PREFIX_OWNER_LOOKUP_TEST_RESULTS_2026-10-23.json).
Runtime evidence and reproduction:
[measurement report](PREFIX_OWNER_LOOKUP_RUNTIME_REPORT_2026-10-23.md).

## Implemented behavior

`CellLocalAggregation::enclosingOwner` now finds a domain's unique containing
owner by searching the domain ID and successive parents (`id >>= 2`). Both
`refineDue` and `refineToDomain` use this lookup instead of scanning the complete
ownership frontier. No ancestor buckets or additional history are materialized.

This reuses the existing Quadtree encoding, not a new spatial index:

- `simulator/src/Quadtree.cpp` constructs children with `(id << 2) | quadrant` and
  initializes base IDs 12..15 at depth 1.
- `simulator/src/AggregationHistory.cpp` validates depth 1..14 and canonical IDs,
  and `historyAncestor` already derives ancestors by shifting two bits per level.
- Example: depth-6 ID 12300 has parents 3075, 768, 192, 48 and 12. Sentinel 3 is
  outside the four-base-cell ownership model and is never searched as an owner.

For a canonical cell, its self/ancestor chain is exactly the possible set of
containing owners. A valid disjoint frontier has at most one such owner. If the
domain is partitioned into finer owners, no containing owner is returned. This
establishes equivalence to the former scan without depending on map iteration
order or a density assumption.

The original-start comparison remains essential: old fine observations from
`[0,t)` must not refine a successor whose private window now starts at t. The
lookup first finds the geometric owner and then checks that its original start
matches the queried historical start. Child order, inherited progress, policy
evaluation, active-owner budget, temporary frontier and commit/ACK behavior are
unchanged. Exact self ownership returns without further splitting.

A single lookup takes at most D map searches rather than F frontier visits:
O(D log F) with `std::map`. Repeated lookup along an entire refinement path can
take O(D² log F), plus unchanged child construction and policy work. The code
does not claim constant-time traversal or optimize unrelated frontier scans.

## New behavioral regressions

Four public-API cases were added to `CoordinationRegressionTests.cpp`; the
existing independent geometry/source oracle remains the reference.

| Case | Requirement verified |
| --- | --- |
| Sparse depth-14 paths in all four quadrants | The maximum valid ID 1,073,741,823 is supported; four paths use exactly 160 owners instead of a dense leaf array; repeated advancement does not refine an existing leaf again; published support remains exact. |
| Different original starts | A retired coarse owner stays unrefined when another start's history still contains old fine observations in its footprint; the pending neighbour is refined under an exact 10-owner budget. |
| Descendant-only frontier followed by exact owner | Explicit takeovers work when a domain has finer owners and later when it is an owner itself; repeated same-end requests do not reuse a retired prefix. |
| Budget failure after partial temporary splitting | Neither frontier nor output commits partially; repeated failures preserve the original state and a subsequent legal coarse takeover still succeeds. |

The added cases pass against the original implementation as well as the optimized
one. Three deliberately broken temporary variants fail: removing original-start
equality, omitting depth-1 base cells from lookup, and mutating the live frontier
before refinement succeeds. These mutation binaries and source copies stay outside
the repository. No private-method exposure or production test switch was added.

## Build and complete regression run

The actual Simulator, AggregationReplay and all enabled targets build in the
existing Release configuration. All **68 CTest suites pass**, 0 failures, **18.03 s**
wall time with four test workers. The suite includes native history, metrics,
regional policy, coordination/stress, semantic local selection, publication/retry,
replay, receiver utility and transport/viewer checks. The four MongoDB integration
suites use fresh UUID-owned test databases; the normal `Simulation` database is
not reset by these fixtures.

```sh
cmake --build simulator/build --parallel 4
ctest --test-dir simulator/build --output-on-failure --parallel 4
```

After this run no further builds or tests ran concurrently with the native timing
sequence. All 15 native runs (including the ten optimized variants) also match
their complete frozen reference documents excluding only `runtime`; the primary
agent independently reparsed those outputs and authenticated the 21 parent artifacts.
Timing and equivalence measurements are reported separately in the linked runtime report. The former profiler artifacts remain unchanged as historical
evidence; their source hashes intentionally require the corresponding old revision.

## Estimation and the semantic-cap question

The user's selected application approach keeps exact answers as the reference and
evaluates clearly labeled estimates separately. The estimator changes the
recipient's reconstruction, not the source observations or published aggregates.
For example, a public 10-m square with 20 observation contributions supplies a
uniform estimate of five contributions for each of its four 5-m children. The
actual child counts are not disclosed. Temporal allocation similarly uses the
fraction of scheduled samples, excluding the unobserved initial t=0 slot.

Unknown public support remains unknown. Publishing only `road_user` does not let
this estimator reconstruct pedestrian/cyclist proportions. Those semantic counts
are unavailable unless the published category partition resolves them.

A tighter semantic-loss cap can make adaptive space/time choices more useful
relative to a fixed configuration. It also removes fallback candidates: each
published category still needs sufficient distinct support, within maximum cell
size and window/age bounds. The result can be longer waiting, coarser cells or more
suppression. For a fixed candidate/history the stricter eligible set is a subset
of the previous one; a stateful heuristic's overall output need not vary monotonically.

The next scientific comparison should apply the same cap to all fixed and adaptive
methods on the same observations. Proposed levels 1, 0.5 and 0 respectively test
the current root fallback, allowed intermediate groups and unchanged terminal
categories in this taxonomy. Report semantic detail, retained observations,
exact/estimated category-query coverage, paired error and receipt delay together.
Keep the existing uniform-policy case as a reference; do not tune policies merely
to force an adaptive win. This gate implements no semantic policy change.

## Remaining real-time gate

Use the measured optimized per-tick service and queue model to decide the next
runtime action. A longer paced replay and then the live sensor/renderer/database
pipeline must measure actual receipt latency, queue growth and memory over time.
Logical publication age does not include wall-clock backlog. CPU optimization
cannot repair a query that crosses a logically future release or has no public
support. The measured privacy-effectiveness study remains a separate later task.
