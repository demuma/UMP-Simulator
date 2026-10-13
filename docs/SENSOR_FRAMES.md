# Complete sensor frames and renderer synchronization

Implemented on 2026-10-13 for S04 and the renderer-related part of S01.
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

Simulation builds exactly one complete sensor frame for each rendered simulation step:

```text
step time   AGBS-A (10 Hz)   AGBS-B (5 Hz)   complete sensor map
0 ms        initialize      initialize     {}
50 ms       not due         not due        {}
100 ms      sample          not due        {A: sample}
150 ms      not due         not due        {}
200 ms      sample          sample         {A: sample, B: sample}
```

This example uses the existing aligned 50-ms simulation step. ABS and GBS contribute
under their own IDs on their own due steps. No sensor waits for a later observation from
another sensor. Non-aligned sampling remains D02/F01.

- Missing ID: this sensor has no sample at this step.
- Present empty grid payload: the sensor measured an empty area.
- Empty frame map: the step is complete and no sensor sampled.
- Empty transport queue: the next frame may still be in flight; it is not evidence of
  an empty measurement. End/stop plus drained queues is explicit end of stream.

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
It publishes the complete sensor frame before exposing the corresponding agent snapshot.
The agent snapshot was copied from the same X(t). Two queues remain, but completion is
explicit and ordering is guaranteed by the single simulation producer. Headless runs skip
both render queues and use an independent completed-step counter.

An aggregation manager can receive owned observation batches directly in the simulation
thread. It must not consume the renderer queue: reads remove frames, and a second reader
would compete with rendering. AGBS contributor-aware input is still needed before distinct
support metrics can be computed. The combined count payload is not that missing identity
stream and does not complete A01.

## Renderer behavior

`SensorFrameCursor` consumes chronological frames, discards old entries, selects an exact
match once, and retains at most one future entry. Matching an already selected timestamp
supports pause/redraw without consuming another frame. Duplicate or out-of-order incoming
timestamps, or backwards target times, are rejected; replay/rewind needs a fresh cursor.

The renderer holds at most one pending agent frame while a genuine sensor frame is in
flight. Reads use tryRead and return to event polling rather than blocking on a missing
measurement. A completed step with no matching measurement clears the current measurement
view. A paused repaint retains its matched view. There is no implicit last-known display.

Each AGBS render instance looks up its own ID and checks the payload type. Its geometry is
rebuilt once when the agent frame advances, using Quadtree::clear to delete old child nodes,
not on paused repaints. No sensor ID is overwritten during drawing. ABS/GBS payloads travel
in the frame, but new measured-agent/count heatmap displays are separate renderer work.

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

- FrameRegressionTests: complete/empty steps; two AGBS IDs plus ABS/GBS types; old/exact/
  future selection; pending vs EOF; pause; malformed frame order; bounded queues; concurrent
  FIFO order; final-frame drain; blocked reader/writer shutdown. No MongoDB or window needed.
- SensorRegressionTests: actual ABS, GBS and two AGBS at 10/5 Hz; entry/reentry, empty areas,
  counts, timestamp identity, single-use sample handoff, existing ABS velocity/DB-duplicate
  checks. Uses only a fresh UUID-named database and removes it on exit.
- Full executable smoke check: isolated headless configuration, 20 steps, four sensors,
  generated distinct IDs and agreement between metadata and measurement IDs.
- Manual visual interaction, long-run performance and the wider S02/S03 simulator issues
  are not established by these tests. Policy-driven live aggregation overlays remain A06.

Next foundation slice: define the identity-bearing internal AGBS observation adapter and
the fixed-cell/window count contract (D03/A01), then implement the smallest observation-to-
decision path with explicit metrics and policies. Preserve sensor independence and keep
the manager out of the renderer transport.
