# Bucket and history implementation status

Reviewed: 2026-10-19. This document resolves the distinction between implemented logical
bucket APIs, the actual adaptive controller, and planned proactive aggregation.

## Direct answer

`CandidateBucket`, `BucketRole::Active/Preemptive` and open/extend/query/discard operations
are implemented and regression-tested. The production adaptive controller does **not**
automatically create these records or maintain continuously aggregated parent/grandparent
buckets. It owns one pending common interval and reconstructs candidates directly from
bounded fine observation history. Automatic ancestor prewarming/caching remains E05.

| Component | Actual behavior |
|---|---|
| AGBS source | Produces identity/type/finest-cell observations at each scheduled sensor sample |
| Fixed accumulator | AggregationManager maintains current fixed-window per-cell counts/ID unions for diagnostics |
| Shared private history | Owns chronological sensor-sample bins with fine observations, statuses and bounded retention |
| Active adaptive state | AdaptiveAggregation owns one pending interval over the sensor grid |
| Logical bucket API | Represents an arbitrary valid cell/interval/generation and Active/Preemptive role over that history |
| Parent/grandparent aggregate | Reconstructed on request from descendant fine observations over the requested interval |
| Attempt cache | Local to one SpatialSelector proposal; not maintained across candidate endpoints/windows |
| Automatic preemptive ancestor preparation | Not implemented |
| Publication | One approved terminal cut/interval; no intermediate provisional parent/child publication |

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
intervals cannot later be reaggregated as a privacy repair. Future independently scheduled
cell windows therefore need explicit compatible unpublished support, reservation/retirement
and merge-group coordination; the current whole-grid interval avoids that alignment problem.

A future preparation limit must count relative ancestor steps, separately from absolute
observation depth, legal merge extent and reserved support. Preparation can reduce repeated
work; an unprepared allowed candidate must remain queryable from eligible retained history.

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
4. Prioritize targeted A07 partial-child rescue and one controlled functional-region/query
   scenario with a clear visual effect. They address demonstrated utility/model limits.
5. Implement cell-local coordination before claiming independent local temporal windows.
   Otherwise explicitly present the current common-window baseline.
6. If proactive preemptive preparation is claimed as an implemented contribution, implement
   and measure at least one bounded variant against on-demand reconstruction. Otherwise
   label it planned. Cache variants do not by themselves establish improved privacy.
7. Keep real city imports, shop demand, taxonomy overhaul, general routing/avoidance and
   broad additional sensitive-attribute metrics outside the presentation-critical path.

Full preparation/selective caching remains a performance study unless measured deadlines
make it necessary. The first empirical benchmark is an implemented research path, not
completion of every feature in the original architectural proposal.
