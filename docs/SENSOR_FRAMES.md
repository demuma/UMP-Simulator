# Complete sensor frames and renderer synchronization

Implemented on 2026-10-13 for S04 and the renderer-related part of S01. Updated to
send frames only on measurement steps, using agent-frame arrival to confirm step completion.
This document describes the current implementation. Aggregation policies, buckets and
privacy decisions remain separate work; this frame is an internal measurement/debug object.

## Contract

`sensorFrameType` owns a timestamp and a map from a run-stable sensor ID to a typed
`SensorSample`. The transport handle is `shared_ptr<const sensorFrameType>`. It contains
owned values, not pointers into agents, quadtree nodes or MongoDB documents.

| Payload | Contents | Limits |
|---|---|---|
| AgentSensorSample | Existing complete ABS observations: ID, type, position, interval velocity; detected-agent count | First sightings/reentries remain excluded from complete observations until a second sample; detectedAgents includes them |
| GridSensorSample | Fixed-grid indices, instantaneous total occupancy and per-type counts | No contributor identities or temporal distinct-person count |
| AdaptiveGridSensorSample | Quadtree cell IDs, instantaneous total occupancy and per-type counts | No contributor identities, aggregation history or release decision |

Cell counts describe one observation, not unique people accumulated over time. An ABS
payload can contain no complete records despite detecting newly entering people; consult
detectedAgents before interpreting that as an empty detection area.

Simulation sends one combined sensor frame only when at least one sensor measured in
a rendered simulation step. The frame contains all actual contributions for that timestamp:

```text
step time   AGBS-A (10 Hz)   AGBS-B (5 Hz)   sensor frame sent
0 ms        initialize      initialize     none
50 ms       not due         not due        none
100 ms      sample          not due        {A: sample}
150 ms      not due         not due        none
200 ms      sample          sample         {A: sample, B: sample}
```

This example uses the existing aligned 50-ms simulation step. ABS and GBS contribute
under their own IDs on their own due steps. No sensor waits for a later observation from
another sensor. Non-aligned sampling remains D02/F01.

- Missing ID: this sensor has no sample at this step.
- Present empty grid payload: the sensor measured an empty area.
- No sensor sampled: no sensor frame is allocated or enqueued. Builder::finish returns
  a null handle, which Simulation does not write to the queue.
- Empty transport queue after receiving agent frame t: no measurement for t is pending,
  because the producer finished all sensor work for t before exposing that agent frame.
- Empty transport queue before receiving the agent frame: completion is not yet known.
  End/stop plus drained queues is explicit end of stream, not required to resolve a
  no-sample step whose agent frame has already arrived.

The builder rejects duplicate IDs and contributions with another timestamp. Main assigns
missing IDs once in the in-memory YAML configuration, then shares those IDs with simulation
and rendering. Optional `sensors[].id` values must be nonempty and unique. Generated UUIDs
are stable within a run; they are not persistent cross-run sensor identities. Metadata and
measurements use the same ID. The on-disk YAML is not rewritten.

## Ownership and production order

Sensors no longer depend on SharedBuffer. Each update resets its optional pending sample,
captures only if due, and makes an owned payload available through `takeSample()`. Taking
a sample consumes that handoff once. Existing DB batches remain separate and keep their
existing schema and publication behavior. The handoff currently copies the captured values
once into the sample; it does not retain whole Agent objects or quadtree pointers.

Simulation collects the contributions while all sensors still observe X(t), before movement.
It enqueues any resulting measurement frame before exposing the corresponding agent snapshot.
The agent snapshot was copied from the same X(t). Receiving this agent frame therefore
confirms that all sensor work through t is complete, including steps without measurements.
There is no separate empty frame or completion message. "Publish" here means queue handoff
to the internal renderer, not public release of anonymized data or a MongoDB write.

This ordering is guaranteed by the single simulation producer and synchronous sensor updates.
The renderer is the sole consumer of each queue. Moving sensors to independent threads or
adding consumers requires an explicit completion protocol; selectCompletedStep must not be
called before the corresponding agent frame arrives. Headless runs skip both render queues
and use an independent completed-step counter.

An aggregation manager can receive owned observation batches directly in the simulation
thread. It must not consume the renderer queue: reads remove frames, and a second reader
would compete with rendering. A01 now provides a separate contributor-aware AGBS adapter
for fixed-window statistics. The combined count payload is not that identity-bearing input.

## Renderer behavior

`SensorFrameCursor` consumes chronological frames, discards old entries, selects an exact
match once, and retains at most one future entry. Matching an already selected timestamp
supports pause/redraw without consuming another frame. Duplicate or out-of-order incoming
timestamps, or backwards target times, are rejected; replay/rewind needs a fresh cursor.

After reading an agent frame, the renderer calls selectCompletedStep. It uses tryRead
and resolves a missing measurement immediately, including while the producer is still running
and during long gaps or a run with no sensor measurements. There is no pending-agent wait
state and no need to wait for a future sensor frame or EOF. A new step without a matching
measurement clears the current measurement view. A paused repaint retains its matched view.
Waiting for the next agent frame remains nonblocking so event handling can continue.

The AGBS grid is a separate, explicit **latest-measurement geometry display**. Clearing it
on every unmatched agent step caused visible flicker with 20-Hz agent frames and 10-Hz
measurements. AdaptiveGridDisplayState now retains only the latest cell IDs and their
original measurement time per sensor. Absence of a new sample keeps that geometry; a due
measured-empty sample removes its subdivisions. Exact-step measurement matching, counts,
aggregation and database data are unchanged. Held geometry never becomes a new sample.

Each AGBS render instance looks up its own ID and checks the payload type. Its geometry is
rebuilt with Quadtree::clear only when a new measurement changes the cell-ID set, not on
intermediate agent steps, repeated identical cell sets or paused repaints. The grid label
shows the age of its latest measurement in simulation milliseconds. Before the first
measurement, it says it is waiting; only the four base cells and area boundary exist.
The current 10-Hz schedule first measures at 100 ms. Subsequent subdivisions follow
observed cells; empty/unvisited regions are not pre-expanded to maximum depth. At run end,
any retained geometry remains explicitly dated rather than claimed to be current.

No sensor ID is overwritten during drawing. ABS/GBS payloads travel in the frame, but new
measured-agent/count heatmap displays are separate renderer work.

## Buffer bounds and shutdown

The two render queues default to 128 frames each. Optional `renderer.buffer_capacity`
must be positive. A full queue pauses the producer until consumption or cancellation;
no frames are silently dropped. This bounds queued frames, not bytes per frame or the
memory used by simulation/DB/history. Performance evaluation should use headless runs so
renderer pacing/backpressure does not enter the timing result.

SharedBuffer can promote a remaining write queue when the read queue empties, including
after end. End and requestStop wake waiting readers and writers. Normal end drains queued
frames; window close requests cancellation on both queues. No access-count scheme is used.

## Verification and remaining work

- FrameRegressionTests: no allocation on unsampled steps; measured-empty identity; two AGBS
  IDs plus ABS/GBS types; old/exact/future selection; immediate no-match while producer is live;
  pause; malformed frame order; bounded queues; concurrent sparse two-queue production with
  long gaps and with no measurements at all; final-frame drain; reader/writer shutdown.
  Display-state coverage adds initial waiting, retained geometry with unchanged original
  time, mixed-rate IDs, unchanged cell sets, measured-empty clearing and repopulation.
  No MongoDB or window needed.
- SensorRegressionTests: actual ABS, GBS and two AGBS at 10/5 Hz; entry/reentry, empty areas,
  counts, timestamp identity, single-use sample handoff, exactly 9 combined measurement
  frames for 19 simulation steps, and existing ABS velocity/DB-duplicate checks. Uses only a
  fresh UUID-named database and removes it on exit. The render-only quadtree is also
  reconstructed from captured IDs and checked against the sensor's cell bounds; no-sample
  steps retain subdivisions and empty measurements remove them.
- Full executable smoke check: isolated headless configuration, 20 steps, four sensors,
  generated distinct IDs and agreement between metadata and measurement IDs.
- Manual visual interaction, long-run performance and the wider S02/S03 simulator issues
  are not established by these tests. Policy-driven live aggregation overlays remain A06.

Next foundation slice: define the identity-bearing internal AGBS observation adapter and
the fixed-cell/window count contract (D03/A01), then implement the smallest observation-to-
decision path with explicit metrics and policies. Preserve sensor independence and keep
the manager out of the renderer transport.


## Separate A01 aggregation input

An optionally enabled AGBS now supplies identity-bearing cell observations directly to
its sensor-local fixed-window AggregationManager. This path does not read or expand the
renderer queue. AGBS/GBS SensorSample payloads remain count-only; their schemas and sparse
frame cadence are unchanged. Measured-empty AGBS captures reach the manager as explicit
empty batches, and non-sampling ticks call advance without fabricating a sample. See
[Fixed aggregation contract](FIXED_AGGREGATION.md) for input/count/window semantics.


## SharedBuffer comments and debug traces — 2026-10-14

Restored explanatory English comments and DEBUG_MSG calls in SharedBuffer.hpp/.tpp,
following the current bounded FIFO implementation rather than the obsolete swap/wait
logic. Traces identify the buffer name, accepted frame index, physical read/write roles,
capacity/data waits, promotion and end/stop with pending counts. Empty tryRead polling is
normal and does not produce repeated log messages. Queue behavior is unchanged.

Logging.hpp compiles these calls only when the DEBUG preprocessor symbol is defined.
The normal Release build keeps them disabled. The existing commented
`target_compile_definitions(Simulator PRIVATE DEBUG)` line in CMakeLists.txt enables them;
verbose logging can affect measured timing and should stay off for performance experiments.
The complete FrameRegressionTests suite passed when compiled with `-DDEBUG`, covering
bounded backpressure, concurrent FIFO order, sparse measurement pairing and shutdown.
