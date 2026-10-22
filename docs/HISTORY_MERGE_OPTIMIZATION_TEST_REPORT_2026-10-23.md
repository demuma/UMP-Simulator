# Sequential history-query and merge-feasibility verification

Date: 2026-10-23. Baseline: `a402479`. The user explicitly selected these two
computation optimizations before parallelization. The
[protocol](HISTORY_MERGE_OPTIMIZATION_PROTOCOL_2026-10-23.md) preceded production
changes. See [runtime evidence](HISTORY_MERGE_OPTIMIZATION_RUNTIME_REPORT_2026-10-23.md)
and [test/source hashes](HISTORY_MERGE_OPTIMIZATION_TEST_RESULTS_2026-10-23.json).

## Stage 1: exact history ranges

Each sample owns its observations privately. Append still validates stream,
sequence, time, capacity, identity uniqueness, semantic labels and canonical cell
geometry before mutation. It then copies and sorts those private rows by finest
cell ID before advancing/evicting history. The caller's rows are never reordered.
No extra retained index, cache, identity copies or new resource budget is added.
The existing payload/observation/bin bounds retain their meaning; they do not
claim to be a complete allocator-RSS limit.

For a validated cell ID c at depth d, finest depth D, its finest descendants lie in

    [c * 4^(D-d), (c+1) * 4^(D-d)).

Two binary searches select that range in each retained measured sample. Only
matching rows enter the original exact identity/type/semantic accumulators.
Coverage still counts measured empty and off-domain samples; missing/unavailable
measurements and half-open time boundaries are unchanged. Requested geometry is
preserved, including previously accepted floating tolerance. Full finest/occupied
queries still validate their complete requested identity scope.

Per-sample identities are unique. Reordering within a sample cannot change stable
canonical-type consistency across time; chronological bin order remains unchanged.
Counts are exact integers and exposed semantic evidence uses deterministic keys.
Raw type aliases, distinct unions and all original checks remain active.
Validated depth is at most 14, so the largest exclusive bound is 2^30, within int.

The cost changes from scanning n rows on every query to one O(n log n) sort when
appending and O(log n + m) selection/accumulation per queried sample, where m is
the matching count. Bin/time traversal and exact accumulator costs remain. Sorting
can cost extra for tiny workloads or few queries; measured net benefit is required.

## Stage 2: exact merge ownership ranges

The frontier remains a disjoint ownership partition in the existing std::map.
`canMerge` rejects proper enclosing owners using prefix lookups, then visits only
matching descendant owners through one numeric range per depth. All depth-d IDs
lie in [3*4^d, 4^(d+1)), so depth bands are disjoint and increasing. Descendants at
depth h occupy [c*4^(h-d), (c+1)*4^(h-d)). Traversing these ranges by increasing
depth preserves the original matching-owner order, first-start assignment and
early mismatch rejection. Proper ancestors precede all descendant depth bands.

The original conditions remain: at least one owner, identical original starts,
end strictly after start, and complete coverage measured in finest-leaf units.
No ownership index, cached decision or extra allocation is introduced. All other
merge planning, regional policy checks, handoffs, reservations, publication and
ACK/retry paths remain unchanged. Complexity becomes O(D log F + K), rather than
O(F) over all frontier owners, for depth D, F owners and K matching owners. Tiny
frontiers may not benefit; this is not a universal speedup claim.

## Independent regression coverage

`HistoryQueryRangeTests` adds 7,728 comparisons with original unsorted rows using
rectangle containment and explicit sample times. The oracle independently builds
identity sets, raw-type counts and semantic ancestor evidence. Depths 1, 2, 6 and
14, all four base roots, both sides of root boundaries and the maximum cell ID
are exercised. Additional cases check input permutations across full-query APIs,
caller/result ownership, geometry tolerance, scoped versus global type conflicts,
invalid late appends, sequence retry and expiry precedence. The focused test also
passes UndefinedBehaviorSanitizer, including the highest exclusive integer bound.

The coordination extension adds 120 deterministic public-API cases over depths
1, 2, 4, 6 and 14. Eligibility is derived independently from rectangle intersections,
original owner clocks and raw observations, rather than the new ID ranges.
Mixed-depth and proper coarse owners, unrelated roots, maximum IDs, fine/root
retirements and mismatched starts are included. Accepted results have their exact
domain/start/end checked and undergo the existing conservation audit; rejected
requests must leave frontier and outputs unchanged. Existing handoff, sparse
ownership, policy/budget and ACK/retry tests remain part of the full suite.

## Sequential acceptance

| Gate | Full CTest result | Wall time | New focused coverage |
| --- | --- | ---: | --- |
| History only | 70 / 70 passed | 20.68 s | 7,728 independent history queries and scoped semantic/failure cases |
| History plus merge | 70 / 70 passed | 18.58 s | Additional 120 public-API coordination oracle cases |

The history-only native matrix and detailed profile passed all 11 full-output
comparisons before the merge change was installed. Final full-output comparison
and timing evidence is recorded separately in the runtime report. The primary
agent independently reparsed all 27 native result documents, recomputed the five
profile distributions/FIFO traces and authenticated the pinned manifest, 21
reference artifacts and original observation source. All checks passed. Test wall times
are verification durations, not performance measurements of the mechanism.

The actual Simulator and AggregationReplay build in the existing Release setup.
The normal Simulator is not launched. Four MongoDB integration suites use isolated
UUID test databases; the user's normal Simulation database is not reset.

```sh
cmake --build simulator/build --parallel 4
ctest --test-dir simulator/build --output-on-failure --parallel 4
```

Builds and tests are paused during native timing blocks. Complete frozen JSON
comparisons exclude only runtime; they include private decisions/diagnostics and
public releases. Raw observations, releases, source snapshots and native binaries
stay local. Historical reports/profilers remain unchanged.

## Limits

These changes reduce computation under the existing mechanism. They do not alter
policy eligibility, semantic priorities, publication scheduling or privacy utility
results, and do not introduce concurrency. Longer paced replay and the live
sensor/renderer/database path still need actual queueing, delivery, memory and
overload measurements. Repeated timing on one 20-s input is not a worst-case or
live end-to-end real-time guarantee.
