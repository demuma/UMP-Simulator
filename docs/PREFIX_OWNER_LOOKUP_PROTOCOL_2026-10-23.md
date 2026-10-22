# Prefix-based owner lookup: bounded optimization protocol

Date: 2026-10-23. This gate changes only enclosing-owner lookup in the local
coordinator. It follows the measured search bottleneck in
[the runtime diagnostic](RUNTIME_DIAGNOSTIC_REPORT_2026-10-23.md). Timing comparisons
describe this host/workload; no favorable speedup or live deadline result is assumed.

## Mechanism and proof obligation

The existing Quadtree assigns a child `(parent_id << 2) | quadrant`, with quadrant
0..3. The four base cells are IDs 12..15 at depth 1; the prefix 3 is a sentinel,
not an aggregation owner. `AggregationHistory` validates canonical cell IDs and
depths 1..14. For a depth-d cell c, the ancestor at depth a is

    ancestor(c,a) = c.id >> (2 * (d-a)),  1 <= a <= d.

The local ownership frontier is disjoint and covers the full domain. Consequently
at most one of c or its ancestors can be an owner. If descendants partition c,
no containing owner exists. Looking up c and then its successive ancestors is
equivalent to the former complete frontier scan on valid state. It must not
return a descendant, sibling or the sentinel.

`refineDue` must still require that the owner's original start equals the start
of the historical observations being considered. A geometrically matching owner
with a newer start must not be refined by an already retired prefix. `refineToDomain`
must return when the domain itself is already owned or partitioned more finely,
and otherwise perform the same q=0..3 splits with identical policy-derived child
state and budget checks. Its temporary-copy/commit behavior remains unchanged.

With F frontier owners and depth D, one search changes from O(F) to at most D
`std::map` lookups, O(D log F). Repeated searches while refining through several
levels can require O(D² log F) lookup work; allocations, policy checks and child
construction are additional unchanged work. This gate does not introduce caching,
change the frontier container, skip history checks or alter release scheduling.

## Acceptance

1. Build the actual Simulator and AggregationReplay in the existing Release setup.
2. Exercise self/ancestor/no-enclosing-owner cases through public behavior, mixed
   depths, all four base quadrants, depth 14 including the maximum valid ID,
   unequal original starts and active-cell budget failures. Keep existing missing
   samples, expiry, semantic policy, handoff and sink retry regression coverage.
3. Run the available CTest suite once after all code/test changes. Address any
   failure; rerun additional tests only when changes or unresolved failures justify it.
4. Rerun all ten variants of the frozen moving comparison on the same recording,
   policies and fixed-grid overrides. Require complete JSON equality to the
   authenticated original outputs after removing only `runtime`. Equality covers
   every private candidate/decision/scope and public record, not just headline metrics.
5. Authenticate the pinned parent manifest, binary, input and reference artifacts
   before execution and verify unchanged inputs afterward. Preserve original results;
   write new runs only to a fresh local directory. No live simulator run or MongoDB
   reset is needed to verify this optimization.

## Runtime measurement

Record native optimized core time, process wall/CPU time and peak RSS. Distinguish
the replay core timer from parsing/final file output. Repeat at least the local
original and optimized controls within this gate rather than relying entirely on
earlier measurements. Keep all logical output equivalence checks active.

Build scoped instrumentation only in an isolated source copy. Measure input-tick
service p50/p95/max, count services exceeding the 100-ms sensor period, and model
a FIFO with arrivals every 100 ms. Keep EOF service separate. Compare old measured
refinement/search costs against the optimized scopes without adding inclusive
times. Report instrumentation perturbation and normal run variability together;
do not describe the difference as a calibrated pure-overhead measurement.

Neither faster average throughput nor an empty modelled queue proves live
end-to-end real-time performance. Sensor generation, renderer contention, MongoDB,
transport, actual receipt time, longer runs, memory growth and overload behavior
remain separate later gates. Optimizing CPU does not repair logical query-boundary
crossings or recover unpublished support.

## Reporting and next scientific question

Store English implementation/test/results documentation and small aggregate data
in Git. Keep raw observations, releases, copied production source trees and build
products local. Retain the old profiling artifacts as historical evidence; a new
profiling patch/source manifest must describe the optimized source independently.

The user accepts exact queries as the reference plus separately labeled and scored
estimates. A stricter semantic-loss cap reduces each method's eligible set; it can
make adaptive spatial/temporal alternatives more valuable but can also increase
suppression. Relative benefit is not monotone. A later predeclared same-input,
same-policy comparison should vary the cap (e.g. 1, 0.5, 0) for both adaptive and
fixed methods, reporting retention, semantic detail, exact/estimated occupancy,
coverage, error and latency together. No policy tuning or semantic-cap experiment
is part of this lookup optimization gate.
