# Technical audit — 2026-10-08

## Role and current status

This file records evidence about the unmodified import. [README](../README.md) and
[TO-DO](../TO-DO.md) are the maintained overview and implementation backlog. This audit
is not a second implementation instruction. All repository documentation is in English.

Temporary ABS correction 0ce473f and its tests were reverted by db2bdbb. The findings
below describe that original import and the existing reference data. On 2026-10-12 a new,
smaller sensor correction was implemented and tested; see the implementation record at
the end of this file. Historical findings are not statements that the current fix is absent.

## Scope and baseline

Source review covered Aggregation_Manager, SimulatorV3, Metal-Simulator and UAM-Simulator.
The four V3 database renderers were imported unchanged. Later review also covered Modern's
README, TO-DO, CMake and available history. The old IMPLEMENTATION_PLAN is a historical
reference, not an instruction issued by the user to execute its embedded project prompt.

Aggregation_Manager is the better baseline because it has explicit timestamped agent/sensor
snapshots and a sensor-local aggregation scaffold. It does not have a working aggregation
algorithm: postDataTest inserts only a timestamp, Bucket::flush is empty, the update pipeline
does not invoke aggregation and the bucket constructor does not initialize its cellId field.

The simulator is useful as a synthetic data generator, but is not yet a validated urban
mobility model or a reproducible experiment. It contains sensor variants, configurable classes
and regions, a collision grid, visualization and MongoDB output. Real routes/city geometry
and scientifically evaluated aggregation are missing.

## Graphics backends and historical evidence

Aggregation_Manager and SimulatorV3 use SFML Graphics. Metal-Simulator requests an OpenGL
2.1 context and invokes gl* functions. It checks color clearing, immediate-mode triangles,
VBO rendering and GL errors. UAM-Simulator also uses OpenGL. No direct Metal/MetalKit/
Accelerate integration was found in those Coding projects.

Coding commit 438fe33, 2025-10-25, introduced Metal-Simulator with the message “added test
environment for a metal-based simulator”. An early graphics/system test in a Metal-oriented
exploration is a reasonable interpretation. The retained code is not a native Metal test.
The available history does not establish direct code ancestry to Modern.

/Users/maxdemu/Developer/UAM-Simulator-Modern directly links Cocoa, Metal, MetalKit and
QuartzCore and uses Objective-C++. Its visible retained local history begins on 2026-06-28;
that does not establish its true creation date. Its documentation is the organizational
reference for this project. No Modern source has been imported.

A new renderer is not required for the first privacy/utility comparison. No performance
advantage has been measured here. SFML is a higher-level windowing/multimedia library;
Metal is a graphics/compute API, so migration includes platform/window/input/resource work.
Modern may reduce that effort for a future Apple-specific 3D view. CPU simulation and
aggregation need dedicated compute changes to benefit from GPU execution.

## Timestamp sequence: corrected finding

An initial general claim of a GT/sensor time shift was too broad. Aggregation_Manager runs:

1. Store state X(t), timestamp t as agent snapshot and GT.
2. Increase simulationTime; the timestamp field initially remains t.
3. Sensors observe X(t) with timestamp t.
4. Set timestamp to t+dt and move agents to X(t+dt).
5. The next iteration stores GT for t+dt.

GT and sensor positions therefore agree in time on this path. ABS copies agent identity,
so matching on agent_id and timestamp is meaningful within its detection area and schedule.
Different frequencies do not require identical timestamp sets.

SimulatorV3 also stores GT before movement, but uses agent.timestamp rather than the already
increased simulationTime. ABS observes after movement; matching GT is stored on the next
iteration. This is not a universal timestamp shift, though a final sensor state may lack a
subsequent GT write. Do not combine conclusions from the two versions without checking their paths.

## ABS velocity and publication findings

The unmodified Aggregation_Manager contains these separate issues:

- previousPositions is seeded from X(0) during initialization.
- timeSinceLastUpdate increases already during the call for X(0).
- Velocity uses displacement * frameRate rather than stored observation times.
- At dt=0.05 s and 10 Hz, the first publication is for t=0.05 s but assumes a 0.10-s
  denominator; the first estimate is halved. Sampling immediately at t=0 would instead
  produce a zero displacement without a positive elapsed interval.
- Unknown identities still receive records. Local SFML 3.0.2 initializes Vector2 components
  to zero, so their velocity is a default (0,0), not a valid stationary-agent estimate.
- update clears agentData rather than the populated dataStorage batch.
- Simulation calls each sensor's postData every tick; non-capture ticks can reinsert old data.
- The second velocity calculation in Sensor populates a map that does not feed the BSON field.

Proposed next rule: retain an initial observation internally; publish velocity after another
suitable observation; calculate actual elapsed time and publish a batch once. Missing-velocity
output versus delayed full records remains a decision, not an implemented schema change.

### Why estimateVelocities does not protect output

Sensor::estimateVelocities iterates previousPositions and checks currentPositions. Unknown
agents are correctly excluded from that calculation. AgentBasedSensor::update calls it after
captureAgentData, which already calculated AgentData.estimatedVelocity separately and moved
records into dataStorage. postData writes those records, not the estimatedVelocities map.

Three independent questions matter:

1. Are two observations of the same identity available?
2. How much time actually elapsed between them?
3. Which calculation is published?

The first known estimate has both positions but only 50 ms elapsed. Recognition of the
identity cannot fix the wrong denominator. See D01/D02 and F01/F02 in TO-DO.

### Why one call site still duplicates output

At 20 simulation ticks/s and 10 captures/s, the same postData call site runs after every
sensor update, including updates that captured nothing. The working vector and retained
publication vector are different containers after std::move.

| Simulation state time | Capture | Retained batch | Publication |
|---|---|---|---|
| 0.000 s | None | Empty | None |
| 0.050 s | New | Timestamp 0.050 s | Insert |
| 0.100 s | None | Timestamp 0.050 s | Repeat insertion |
| 0.150 s | New | Timestamp 0.150 s | Insert |
| 0.200 s | None | Timestamp 0.150 s | Repeat insertion |

ABS does not invoke AggregationManager. AGBS constructs an aggregator object but has no
active aggregation call in its update path. No active postDataTest call was found.
Simulation::postData(agents) is GT output, not an additional ABS writer.

## Other source-level issues

- Random generators use random_device in multiple places; a shared configurable seed is missing.
  UUID generation and iteration order also need explicit treatment for reproducibility.
- updateVelocity receives simulationRealTime, influencing movement noise with CPU/DB/render cost.
- SharedBuffer::read waits only for data. end sets finished and notifies, but the predicate
  ignores finished; a waiting reader may never exit.
- Queues are unbounded. Headless operation disables the renderer, not snapshot generation.
- CollisionGrid width/height are not initialized by its constructor but are read by
  adjacent-cell checks. Neighbor pairs can be processed in both directions.
- Agent pointers are retained while vector::erase may invalidate earlier pointers.
- Quadtree::reset nulls child pointers without freeing their nodes, losing destructor reachability.
- Sensor timers reset to zero rather than preserving residual time; non-aligned frequencies
  can change actual sample spacing.

These are source-level findings. Runtime impact and performance have not been measured for
all of them. The example-agent data check is the separate empirical evidence below.

## Aggregation interface discussion

AggregatedCell is a plausible release record, but count semantics must come first:
contributions, distinct people and mean occupancy are different values.

Prefer a sensor-local manager without MongoDB dependency. Mandatory long-lived dependencies
can be references, for example a spatial hierarchy, temporal storage and policies. A nullable
Quadtree* adds no benefit without actual optionality. ingest(batch) and advance(time) could
separate ingestion from planning; update(now, tree) could be a small transition interface,
but needs history in addition to geometry. These are proposals, not new classes.

Use explicit simulation ticks/integer durations for future windows, define [start,end),
and identify releases by sensor, policy, release ID and publication time. Keep internal
agent identities separate from releases. A const output reference suits synchronous callers;
thread transport needs immutable snapshots. Consumption/draining can prevent repeated output.

## SharedBuffer discussion

Do not use a fixed access count of three. Reference counts track lifetime, not completion.
Existing read pops a frame, so independent readers consume different frames.

Keep aggregation in the simulation thread initially. A protected latest-snapshot channel
could serve rendering when skipped frames are permitted. Lossless measurement/release
consumers need bounded queues and overload rules. Multiple such consumers need their own
queues or read cursors. Distinguish snapshot lifetime from delivery completeness.

## Review of the historical plan

Useful principles: sensor-local aggregation, separate topology/history, regional constraints,
DB-free manager, bounded retention, clear count semantics, release view and GT separation.

Adjustments proposed for the actual roadmap:

1. Put reproducibility, experiment output and fixed baselines early.
2. Define application utility and independent empirical attacker evaluation early.
3. Treat k-threshold compliance as a release rule, not a complete anonymity proof.
4. Static hierarchy does not require full materialization. Consider implicit Morton structure
   and sparse measurement storage; account for four base cells at depth 1.
5. Historical recommendation: start the alternative action orders with one global policy.
   The current roadmap includes initial regional policies. Current terminology (October 13):
   Temporal First preserves time via spatial aggregation; Spatial First preserves space
   via temporal aggregation. Follow TO-DO for the active scope and these updated labels.
6. Retrospective reconstruction applies internally. Deleting a DB record cannot retract an
   externally observed release; assess overlap and differencing across the whole stream.
7. Retained contribution fraction is coverage/retention, not a complete fidelity measure.
8. Add maps, ORCA, sensor noise and taxonomy redesign when experiments need them.
9. Treat the plan's novelty claim as a hypothesis requiring literature and empirical evidence.

## Import verification and read-only database evidence

The simulator and ABS/GBS/AGBS/GT renderers each built successfully in Release mode.
Builds were placed under /private/tmp/diss-review/import-build. 101 component files matched
the originals byte for byte. Import validation did not run the simulator. Subsequent DB
queries were read only; no records, indexes or collections were changed.

Database: localhost:27017/Simulation. Agent:
C0B64FE1-740C-486C-A2D1-00E030269E71. Sensor:
40F5B238-1457-499C-A2CF-499BD5BF8AF6.

| Check | Result |
|---|---:|
| GT records / distinct GT timestamps | 200 / 200 |
| ABS records / distinct sensor timestamps | 199 / 100 |
| Missing GT matches on agent identity + timestamp | 0 |
| Position mismatches | 0 |
| Type mismatches | 0 |
| Duplicate ABS keys / extra records | 99 / 99 |
| Conflicting duplicate contents | 0 |
| Subsequent distinct ABS observation intervals | 99 × 100 ms |

GT range: 2025-04-09T09:30:00.000Z to 09:30:09.950Z.
ABS range: 09:30:00.050Z to 09:30:09.950Z.

First displacement over 50 ms implies (5.1058959961, 1.2913703918) m/s;
stored velocity is (2.5529479980, 0.6456851959) m/s, exactly halved. All subsequent
99 estimates match displacement/100 ms. GT contains 183 position-changing intervals;
this was not an exclusively stationary-agent check. Some early examples include stops.

This evidence confirms matching time/position and two ABS issues for this agent/dataset,
not universal correctness of every sensor or run. Compare interval velocity against movement
over the same interval, not instantaneous GT velocity at its endpoint.

## Next step

Priorities are maintained only in [TO-DO.md](../TO-DO.md). D01/D02 define data rules;
F00/F02 are implemented as recorded below. F01 actual-interval velocity handling and
full-run validation remain open. No graphics backend migration has been started.

## Cross-sensor baseline sampling review — 2026-10-12

Timer advancement precedes the sampling threshold in ABS line 51, GBS line 66 and AGBS
line 74. Each receives the current state/timestamp before agent movement. With the current
configuration, populated areas first capture at t=50 ms, the second simulation timestamp.
The initial timestamp at t=0 does not emit a sensor batch at 10 Hz.

ABS alone uses the seeded t=0 position for velocity. GBS/AGBS counts remain instantaneous
observations at their actual timestamp. GBS clears dataStorage at line 63 and AGBS at
line 67, preventing the specific ABS stale-batch reinsert path. Both reset the sampling
timer only for hasAgents, which makes empty-area sampling processing a further cadence case.
The current F00 task covers all sensors and empty/repopulated areas. This review changed
only documentation, not source code or database data.

## Sensor correction implementation — 2026-10-12

Authorized scope: correct startup and repeated successful ABS writes, clarify working/output
storage, and keep the nominal sampling-rate velocity approach for the current aligned setup.

- Added one protected Sensor::isSamplingDue helper. Its first call initializes without
  adding elapsed time; later calls advance the timer. Each due sample resets it even if empty.
- ABS retains initial positions on its first update. Removed Simulation's dynamic-cast
  initialization of previousPositions; sensor observation history now belongs to ABS.
- Replaced the class agentData working vector with captureAgentData's local observations.
  postData calls its local output reference pendingObservations. printData reads that batch.
- Successful ABS insert_many consumes dataStorage.second. Exceptions keep the vector
  pending only until another attempt or the next capture; no durable retry/idempotency promise.
- Removed the unused base estimateVelocities calculation and the separate ABS velocity map.
- Unknown/reentering identities are kept internally until two consecutive observations.
  Absent identities drop out at scheduled observations. Counts may include identities not yet
  present in the complete ABS stream. Nominal-rate estimation remains limited to aligned ticks.

Verification: simulator and opt-in SensorRegressionTests built in Release. CTest passed
against localhost MongoDB in a new UMP_sensor_regression_<UUID> database. The test exercised
19 simulation states from 0 to 900 ms, an absolute non-epoch initial timestamp, known motion,
three ABS postData calls per tick, new entry, empty samples, reentry, grid occupancy and
AGBS renderer timestamp/cadence. ABS emitted seven complete records with unique keys;
grid observations matched expected occupancy at each scheduled timestamp. The first
velocity was (2,1) m/s over 0–100 ms. The test database was removed on exit.

Existing Simulation data/configuration was unchanged; the full simulator was not run.
Variable steps, non-aligned periods, failure injection and full-run reproducibility remain
unverified. Current rules and build/test commands are maintained in README and TO-DO.


## Implementation record — 2026-10-13: S04/S01

The renderer defects described in the original import have now been corrected. SensorFrame
owns typed ABS/GBS/AGBS values, with stable IDs and explicit empty-step completion. Sensors
handoff samples without a SharedBuffer dependency. Simulation assembles one frame before
publishing the corresponding copied agent state. The renderer selects chronological frames
without blocking, clears missing measurements, retains one future frame and routes each AGBS
by its own ID. Geometry is rebuilt on frame advance, not on repeated paused draws.

SharedBuffer now drains both queues, wakes readers/writers on end/stop and supports bounded
capacity. Main uses 128 frames per queue by default; headless runs do not enqueue render
data. Queue changes do not introduce another consumer or an aggregation thread.

Verification: Release build; FrameRegressionTests; expanded isolated MongoDB sensor regression
with two AGBS at 10/5 Hz; full executable headless smoke test with 20 timestamps and four
distinct sensor IDs consistent with their metadata. Tests use and remove only their own
UUID-named databases. The first sandboxed MongoDB attempt timed out; rerunning with local
network access passed. Existing Simulation data and the user's YAML were not changed.

Manual GUI inspection and long-run performance are not covered. AGBS counts still cannot
establish distinct contributors across time. Actual buckets, metrics and policy trees remain
open. See [Sensor frames](SENSOR_FRAMES.md) and the chronological TO-DO for the next slice.


### S04 follow-up: omit frames on non-sampling steps

The initial 4b769dc implementation used empty sensor frames as completion markers. The
agreed follow-up removes that redundancy: synchronous sensor processing and any sensor-queue
writes happen before the corresponding agent frame becomes available. Its arrival is the
completion guarantee. Builder::finish now returns no frame when there are no sensor
contributions; due measurements with empty results retain their IDs and are still sent.

SensorFrameCursor::selectCompletedStep requires that the agent frame has been received.
It resolves an empty sensor queue immediately without waiting for a future measurement or
end of stream. The renderer no longer retains a pending agent while polling sensor arrival.
The ordering requirement applies to renderer queues; it does not change measurement times
or introduce a public data-release decision.

Updated verification covers completely unsampled bounded two-queue runs, long measurement
gaps and no-sample tails while the producer remains live. The mixed-rate sensor fixture
expects 9 combined sensor frames for 19 simulation steps, including measured-empty samples.
The current maintained contract is docs/SENSOR_FRAMES.md.

Release builds and both updated CTest regressions passed. The normal simulator/build/Simulator
was rebuilt; manual visual inspection remains a separate open check.


## Implementation record — 2026-10-13: A01 fixed-window foundation

Replaced the unused DB-dependent AggregationManager scaffold with an independently
testable standard-C++ core. Optional simulation AGBS instances copy internal contributor
IDs, types and existing leaf geometry during capture. Direct synchronous ingestion avoids
another SharedBuffer consumer. Render instances and configurations without aggregation
do not instantiate the manager or copy identities for it.

Fixed half-open windows use integer run-relative milliseconds and aligned sampling.
Counts distinguish contributions, contributor unions and sample mean occupancy. Expected,
measured, unavailable and missing samples remain separate. No-sample ticks advance window
deadlines; normal/cancelled completion flushes the exclusive final interval explicitly.
The adapter currently requires a square full-quadtree extent and aligned millisecond ticks.
An observation budget bounds active state; the external synchronous JSONL sink has no
unbounded output queue. Internal IDs never enter the candidate output schema.

Verification: Release build and all three CTest suites passed. Core tests cover a worked
count/movement example, 100 consecutive windows, invalid/late/duplicate input, missing and
empty coverage, budget rejection and partial intervals. The MongoDB fixture exercises two
live AGBS at 10/5 Hz, including empty captures, entrants and reentry. A full headless smoke
run adds config parsing, file output and end-of-run finalization: 30 initial agents,
20 GT steps, equal 80-m sensor areas and six 400-ms/partial candidate windows. Per-cell and
per-window counts/distinct contributors matched sampled GT; contributions also matched
raw AGBS MongoDB data. JSONL contained no individual contributor IDs. Only UUID-named test
databases were used and removed; maintained YAML and existing Simulation data were untouched.

This implements fixed candidate statistics, not metric-driven privacy approval, policy
trees, public release, merge/split, preemptive buckets or reconstructable history. No speed
claim or empirical privacy improvement follows from these functional checks. The next
research contract is E01/E02: one fixed utility query/reference and justified initial
constraint metrics, followed by A04's minimal regional policy tree.


## Renderer correction — 2026-10-13: persistent dated grid geometry

The user reported blinking and partially absent startup grids. Source inspection confirmed
that Renderer::readNextFrame cleared the AGBS tree at every 50-ms agent tick, whereas the
current sensor delivers a measurement only every 100 ms. Every intervening tick therefore
removed subdivisions. This was an unintended display consequence of the S04 exact-match fix.

Exact-step matching remains unchanged. AdaptiveGridDisplayState now keeps only each sensor's
latest cell-ID set and original measurement time, separately from currentSensorFrame.
No sample leaves geometry intact; a measured-empty payload clears subdivisions. A new
measurement refreshes its time, and only changed cell sets rebuild the renderer tree.
The overlay explicitly labels sample age. Initial base cells are visible before the first
100-ms measurement; subsequent subdivision follows observed branches, not a pre-expanded
full-depth grid. This explains expected coarse/unvisited areas but is not evidence that
every reported startup visual artifact has been reproduced.

Verification: all three CTest suites passed, including new display-state regression cases
and an actual sensor-to-render-quadtree bounds check. Existing exact-step no-match tests
still pass. A separate visual test was launched with two AGBS and a disposable test database,
but the native UI tool could not select the standalone Simulator executable by path or
name. Manual screenshot/pause/resume verification therefore remains open. No existing
Simulation data, production config, sampling cadence or aggregation semantics were changed.

The first windowed attempt also exposed a MongoDB C-driver handshake-mutex assertion.
Simulation declared its client before mongocxx::instance, so reverse member destruction
shut down the driver before destroying the final client. The installed instance.hpp
explicitly requires the instance to outlive every other driver object. Moving the instance
declaration before the client corrects that lifetime. Subsequent one-second, two-AGBS
full-executable runs with a window and headless both exited 0 with empty stderr; their
isolated databases were removed. This execution check does not replace visual inspection.
