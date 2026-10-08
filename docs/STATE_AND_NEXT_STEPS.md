# Technical audit — 2026-10-08

## Role and current status

This file records evidence about the unmodified import. [README](../README.md) and
[TO-DO](../TO-DO.md) are the maintained overview and implementation backlog. This audit
is not a second implementation instruction. All repository documentation is in English.

Temporary ABS correction 0ce473f and its tests were reverted by db2bdbb. Active source and
CMake match import 96fae5b. The defects therefore remain open. Historical test results
for the reverted change do not validate the active version. No further implementation
has begun during documentation work.

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
5. Start Spatial/Temporal First with one global policy before regional conflicts.
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
F01/F02 specify the small ABS corrections. All remain open. Documentation changes do not
reintroduce the reverted implementation or start a backend migration.
