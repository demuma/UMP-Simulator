# Bucket and history implementation status

Reviewed: 2026-10-21. Optional common-window A07 descendant rescue is now implemented;
see [its contract](SELECTIVE_DESCENDANT_RESCUE.md). It is not proactive preparation
or selective suppression of individual road users. Computation optimization is deferred.
This document resolves the distinction between implemented logical
bucket APIs, the actual adaptive controller, and planned proactive aggregation.

## Direct answer

`CandidateBucket`, `BucketRole::Active/Preemptive` and open/extend/query/discard operations
are implemented and regression-tested. The production adaptive controller does **not**
automatically create these records or maintain continuously aggregated parent/grandparent
buckets. The default controller owns one common interval; the new opt-in `CellLocalAggregation`
owns a sparse frontier of independent cell windows. Both reconstruct candidates directly
from bounded fine observation history. Automatic ancestor prewarming/caching remains E05.
See [CELL_LOCAL_COORDINATION.md](CELL_LOCAL_COORDINATION.md) and its test report.

| Component | Actual behavior |
|---|---|
| AGBS source | Produces identity/type/finest-cell observations at each scheduled sensor sample |
| Fixed accumulator | AggregationManager maintains current fixed-window per-cell counts/ID unions for diagnostics |
| Shared private history | Owns chronological sensor-sample bins with fine observations, statuses and bounded retention |
| Active adaptive state | Common mode: one pending grid interval; local mode: independent mixed-depth cell owners |
| Logical bucket API | Represents an arbitrary valid cell/interval/generation and Active/Preemptive role over that history |
| Parent/grandparent aggregate | Reconstructed on request from descendant fine observations over the requested interval |
| Attempt cache | Common selector proposal cache; local controller reuses owner checks per endpoint; no persistent ancestor statistic cache |
| Automatic preemptive ancestor preparation | Not implemented |
| Publication | Common cut or scoped local decision; only approved terminal output, no competing parent/child release |

## Where observations and history are created

1. `AdaptiveGridBasedSensor::update` uses the shared sampling gate. With 10 Hz it measures
   at 100, 200, ... ms; t=0 remains initialization.
2. Every observed road user is mapped to an AGBS cell at configured maximum depth. The
   adapter emits an ObservationBatch with timestamp/sequence/status and identity/type/cell
   geometry. Measured-empty samples also enter the manager.
3. `AggregationManager::ingest` validates input and passes an owned copy to
   `AggregationHistory::append` before closing eligible half-open intervals. A manager
   constructs history only when `aggregation.history` is enabled.
4. Each retained Bin holds one sample's fine observations and measurement status. This is
   one chronological history, not a duplicated history for every ancestor.
5. `advance` removes expired bins and bounded logical records. Missing/unavailable input
   never becomes a certified zero; measured-empty input is distinct.

The basis is the fixed finest input discretization, independent of the selected output cut.
For an 80-m square and depth 6, cell side is 80/64 = 1.25 m. The data representation has
four depth-1 base cells; it cannot publish the synthetic depth-0 root as one data cell.
Internal histories contain identity-bearing observations, not public trajectories or
renderer frames. They do not retain Agent/Quadtree pointers or copy the SharedBuffer.

The maintained temporal demo retains 2,000 ms, with a 32-bin resource bound and a maximal
1,000-ms aggregation window. Running for ten minutes does not make this history ten minutes
long. Output/diagnostic databases and files do grow with duration. Resource budgets and
retention completeness are separate requirements.

## How parents, grandparents and temporal extensions work

`history.query(C,[start,end))` selects descendant observations using the cell-ID prefix,
counts contributions, unions road-user IDs and computes measured-sample occupancy. It
includes all relevant siblings, including coverage of measured-empty ones. Exact identity
support cannot be obtained by summing child support counts because a road user may cross
cells or appear repeatedly over time.

Temporal First (preserve time, space first) checks the finest candidate, searches spatial
ancestors and extends time when unresolved and permitted. Each new endpoint reconstructs
the full interval from the same fine history and repeats selection. Spatial First preserves
space by extending before its spatial fallback. Provisional spatial coarsening does not
destroy fine history or force the next cut to remain coarse.

Passing siblings remain private until the common interval terminates. Already published
intervals cannot later be reaggregated as a privacy repair. The opt-in local controller now enforces compatible unpublished support, scoped retirement
and merge-group handoffs. The default whole-grid interval avoids that alignment problem.

A future preparation limit must count relative ancestor steps, separately from absolute
observation depth, legal merge extent and reserved support. Preparation can reduce repeated
work; an unprepared allowed candidate must remain queryable from eligible retained history.

## Roles, preparation triggers and resource bounds

There is one CandidateBucket structure with two role values, Active and Preemptive.
Collecting/Closed are observation-progress states, not additional bucket species or release
approval. Leaf CellAccumulator, timestamp Bin and provisional SpatialAttempt are different
data structures; calling all of them buckets conceals their different responsibilities.
The actual controller's Pending interval is not a registered CandidateBucket.

Every observed leaf accumulates fixed-window counts/ID support. This is ordinary input
summarization, not preemptive preparation of every possible parent. Unobserved leaves are
not allocated as accumulators. The selector builds occupied ancestor paths and computes
parents only when needed. Its temporary attempt cache can survive as diagnostic output,
but those old results are not consulted as a calculation cache at the next endpoint.

For a future preparation layer, a child's temporal extension or failed release check can
trigger an eligible parent alternative for the SAME original interval. This is an explicit
proposed trigger, not current behavior. A normal child collecting observations alone would
trigger preparation almost everywhere, so it is not a selective trigger. Do not recursively
materialize every ancestor by default. Cap relative ancestor steps, candidate windows and
maintenance work; leave on-demand reconstruction available. Exact support expiry requires
identity unions/reference accounting rather than adding/subtracting distinct child counts.

Current temporal-demo resource settings are: retention 2,000 ms, at most 32 history bins,
100,000 retained observations, 16,000,000 ID/type string-payload bytes, and
128 logical bucket records. The last bound concerns the optional logical-record table,
not the number of leaves or automatically active parent aggregates. The fixed accumulator
has a separate observation-per-window bound. Spatial proposals cap evaluated attempts at
4,096 and temporal adaptation at 16 endpoints in that example. Budget rejection raises
an error; automatic backpressure/degradation is not implemented.

`max_identity_bytes` measures ID/type string payload length. It excludes object/vector/map/
set allocations, geometry, duplicated fixed-window ID sets, candidates, rendering snapshots,
publication objects and allocator overhead. It is not a whole-process RAM cap. Detailed
output files and MongoDB storage are also outside retained-history quotas.

For average observed population N, sample frequency f and retention H, retained observation
count scales approximately as N*f*H, with endpoint and entry/exit effects. At 200 road users,
10 Hz and 2 s this is about 4,000 observations (an inclusive retained endpoint can add another
sample). The count is unrelated to total elapsed simulation duration once retention is full.
Spatial sparsity avoids allocating every one of 4^D possible leaves. However, each current
parent query scans interval observations again; many parent attempts/endpoints multiply
work. Large-area scalability is not established by the small-domain endurance runs.

At fixed depth, increasing domain side also coarsens input cells: h=L/2^D. Preserving h
requires more depth and potentially more occupied cells/road users. Relevant open work is
sparse spatial indexing, compact reusable identity/geometry storage, measured selective
caches, explicit total-memory accounting and larger-workload tests. Very large domains may
need partitioning with explicit cross-boundary aggregation/coordination semantics. Current
depth/attempt/history/policy-node budgets are finite limits, not a scaling solution.

## Existing statistics and speedup scope

The existing STATS_MSG output can support performance reporting. In the tested build STATS
is not defined (its CMake compile-definition line is commented), so the endurance reports
used external process wall time. Existing fields need explicit scopes before scientific use:

- Speedup currently divides planned maxFrames*timeStep by accumulated loop wall time.
  Completed-step simulated duration is required for interrupted/unbounded runs.
- Loop wall accumulation excludes final aggregation flush and other process lifecycle work;
  it is not the same denominator as external process wall time.
- Frame rate is simulation-step throughput, not renderer FPS. The average wall time per
  step is not the configured numerical integration step or a tail-latency guarantee.
- Average write buffer time is measured around preparation of the agent-frame snapshot,
  before the actual buffer write/swap; it does not isolate queue backpressure.

For the verified runs, 300/7.623626542 = 39.35135 and 600/9.382591083 = 63.94822 using
external process wall time. Dividing rounded 7.62/9.38 values gives about39.37/63.97.
These are valid scoped throughput numbers. Both live populations drain around110s, so they
do not establish sustained 200-road-user speedup, per-step deadlines or timely release.
Aggregation waiting age and process throughput are distinct quantities. R02's wall-clock
influence on motion remains another reason to use frozen input for paired cost comparisons.

## Long runs and numerical timestep

Duration, numerical integration step, sensor sampling period and aggregation-window duration
are separate parameters. At 50-ms steps a 10-Hz sensor measures every second step; at
100-ms steps it measures every step. The current aggregation adapter requires a positive
whole-millisecond step dividing the sampling period. A 200-ms numerical step with a 10-Hz
sensor is unsupported without additional observation substeps or a changed sensor rate.

For a fixed step count, doubling the numerical step doubles the simulated duration; it
does not double the number of update/aggregation cycles. Larger steps also change movement/
interaction discretization. The live random/wall-clock dependence means fresh live runs
cannot be treated as paired numerical-accuracy comparisons. Use controlled initial states/
paths and a fine-step reference for such a separate convergence study.

The requested endurance checks use 6,000 steps each: 300 s at 50 ms and 600 s at 100 ms,
with the 10-Hz sensor and aggregation enabled. See the accompanying endurance report for
actual completion, counts, isolation and limits. A long run with declining population is
not evidence of sustained dense-load capacity. Mean whole-run speed is not a per-step
p95/p99 deadline guarantee; stage timings, queue/backpressure and peak resource use need
explicit instrumentation.

## Presentation priority for October 25

1. Explain this implemented architecture and bound claims precisely: dynamic selected cut,
   common temporal interval, regional requirements, on-demand reconstruction, optional
   logical bucket APIs, and pending automatic preemptive preparation.
2. Present the research question, mathematical candidate/policy definitions and finite
   compliance/utility/empirical-attack results with their denominators and limitations.
3. Add credible duration/cadence/end-state evidence and distinguish simulation time,
   wall-clock processing, renderer playback and aggregation waiting age.
4. Review the implemented optional A07 common-window partial-child rescue and its
   verification gate, then specify one controlled functional-region/query scenario
   with a clear visual effect. They address demonstrated utility/model limits.
5. Evaluate the implemented cell-local coordination against common windows before claiming improved local retention/latency.
   Otherwise explicitly present the current common-window baseline.
6. If proactive preemptive preparation is claimed as an implemented contribution, implement
   and measure at least one bounded variant against on-demand reconstruction. Otherwise
   label it planned. Cache variants do not by themselves establish improved privacy.
7. Keep real city imports, shop demand, taxonomy overhaul, general routing/avoidance and
   broad additional sensitive-attribute metrics outside the presentation-critical path.

Full preparation/selective caching remains a performance study unless measured deadlines
make it necessary. The first empirical benchmark is an implemented research path, not
completion of every feature in the original architectural proposal.
