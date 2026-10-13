# Renderer pacing and spatial display

Status: 2026-10-13. S05 pacing correction implemented and tested; native interaction
and long-run/load profiling remain open. This applies to simulator/Renderer, not the
four separate MongoDB playback applications.

## Previous behavior and defect

Renderer::calculateSleepTime computed target FPS as playback_speed / time_step. It then
compared the target period with currentSimulationTimeStep and could overwrite the user's
playbackSpeed. That atomic's initial value was the configured simulation step, but later
values were measured wall-clock durations of a simulation iteration. Those durations
included database work and potentially blocking writes to bounded rendering queues.
Consequently renderer-induced backpressure could reduce its own requested playback speed;
this was not an independent measurement of the producer's computational capacity.

The loop also reset its timer after empty-buffer retries, omitting those waits from its
reported render time. Arithmetic averaging of instantaneous FPS obscured the actual
frames-per-elapsed-time rate, and the left-arrow control could reach nonpositive speeds.
The intent to handle a slower producer was reasonable, but requested and achieved speed
were conflated. Hardware cannot always meet a requested rate; that limitation must not
silently rewrite the user's setting.

## Implemented timing contract

- PlaybackClock uses elapsed seconds from std::chrono::steady_clock. The target period
  is time_step / requested_speed. At 50-ms steps, 0.5x/1x/2x target 10/20/40 newly consumed
  agent frames per wall-clock second; a 10-Hz sensor still samples at 10 Hz in simulation time.
- A successful frame read schedules the next read from the actual read-start time. Its
  geometry reconstruction and drawing count against that period. An empty queue leaves
  the deadline pending; it does not reset the measurement clock or consume a fake frame.
- Late frames, producer recovery, pause/resume and speed changes do not accumulate timing
  debt or skip queued frames. A slow source/render path lowers achieved speed while the
  requested speed remains unchanged. This is a no-catch-up policy; small scheduler delays
  can make achieved speed slightly lower than requested. It is not a hard real-time promise.
- The producer-runtime feedback atomic and old calculateSleepTime path are removed.
  Existing bounded queues continue to provide backpressure and cancellation.
- Event polling sleeps at most 5 ms between iterations (1 ms on a due-but-empty queue).
  Drawing/event costs may take longer. Pausing stops consumption; input and redraw requests
  still work. There is no second SFML frame limiter or VSync setting in the current code.
- New agent data triggers a draw. Interactions may redraw the held frame at at most 30 Hz
  without advancing simulation time, sensor timestamps, queue counters or observed geometry.
  An unchanged paused view is not continuously rebuilt.
- Agent FPS is the number of completed consumption intervals divided by their elapsed
  wall time, using up to 60 intervals. It includes producer waiting between frames and
  rendering cost, excludes pause, and resets on pause/speed changes. The UI labels this as
  Agent FPS and shows requested versus measured playback speed; first-frame rates are unknown.
  A source stall is labeled waiting for input; the displayed rate remains the most recent
  completed-interval estimate until another frame arrives.
- Active wall time includes initial waiting, retries, rendering and pacing; paused wall
  time is reported separately. The displayed simulation elapsed time comes from received
  timestamps relative to the first frame. It does not advance on redraws.
- Rendered runs reject non-finite/nonpositive speeds, sub-microsecond simulation steps
  and target periods below one microsecond before Simulation initializes its database.
  The left-arrow control stops at 0.1x (a smaller configured positive speed is retained),
  the right arrow increases by 0.1x within the representable period, and R resets to 1x.

Optional diagnostics, disabled by default, can be enabled under renderer:

```yaml
log_playback_timing: true
```

At normal exit/close, one line reports requested speed, consumed frames, redraw calls,
active seconds, paused seconds and the latest interval-based measured FPS when available.
No maintained config.yaml was changed to enable it.

## Quadtree versus QuadtreeSnapshot

The simulation AGBS owns a Quadtree: geometry, parent/children, cell IDs and agent placement.
Current subdivision follows observed positions to configured maxDepth, not metric-driven
release decisions. The renderer constructs a separate AGBS instance and its own Quadtree.
Immutable sensor frames carry timestamped typed cell data. AdaptiveGridDisplayState extracts
each sensor's cell-ID set; only a changed set triggers clear/splitFromCellIds on the renderer
tree. Origin, cell size and depth come from the shared run configuration. A held display
keeps its original measurement timestamp between observations.

QuadtreeSnapshot.hpp/.cpp currently define only a node with bounds, an isSplit flag and
four shared_ptr children. No active caller creates or transfers those nodes; references in
Main/Simulation/Renderer are commented out. Its .cpp is compiled through the source glob,
but that does not activate a tree-copying path. This legacy type is distinct from the
immutable sensor/agent frames that are actually used as snapshots. Neither tree type sets
the playback rate, although subdivision/reconstruction/drawing contributes execution cost.

Do not introduce full tree copies or a shared mutable Quadtree to fix pacing. Future variable
release geometry must get an explicit versioned rendering contract; the policy tree supplies
requirements and is a separate responsibility from geometry and playback.

## Verification and remaining work

PlaybackRegressionTests uses a deterministic clock for exact 0.5x/1x/2x cadence, overload,
producer gaps, pause/resume, speed changes, invalid settings and weighted FPS. A fixed integer
frame stream also runs through the production bounded queue (capacity two) and a real steady
clock at all three speeds. The timing acceptance is no faster than target and at most 10%
plus 5 ms slower over the complete first-to-last interval; every frame must arrive in order.
One standalone run measured 9.94/19.79/38.50 FPS with maximum per-interval lateness about 1.3 ms.
All five CTest suites passed, including existing sensor/frame/aggregation/metric regressions.

Three full windowed simulator runs each consumed all 40 frames with capacity-two queues,
30 agents and normal sensor/quadtree drawing. Requested 0.5x/1x/2x remained unchanged;
measured FPS was 9.970/19.900/39.010. Zero, negative and NaN playback settings failed explicitly
before database initialization. Only UUID-named temporary databases were used and removed.
These are small functional timing checks, not a general capacity or real-time benchmark.

Actual keyboard/button interaction, pause/resume appearance, early window close and long-run
jitter under representative load still need a native UI/manual check. The native app inventory
does not expose the standalone Simulator as a selectable app; windowed execution alone does
not establish visual correctness. R02's wall-clock-dependent movement remains separate, so
independent simulation runs must not be assumed to contain identical scientific input.
