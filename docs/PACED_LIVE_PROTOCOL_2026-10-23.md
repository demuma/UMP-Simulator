# Paced replay and live pipeline protocol

Date: 2026-10-23. Source baseline: `5d3cc4b`.
Declared before native measurements. This gate validates arrival timing and the
existing live path after the history/merge optimizations; it does not change
aggregation decisions, policies, motion generation or controller parallelism.

## Workloads and order

1. Run deterministic queue/cancellation tests and complete repository tests.
2. Reuse the frozen 20-s, 500-initial-Road-User recording from the moving scoped
   comparison. Run an unpaced reference and a paced 1x replay with capacity 8.
   Compare complete logical output, omitting only `runtime`.
3. Run the existing Simulator headlessly for 120 logical seconds with 500 initial
   Road Users, the maintained seven behavior profiles, an 80 x 80 m area, depth 6,
   50-ms simulation steps and 100-ms sensor samples. Capture a declared 60-s prefix
   as genuine longer movement input, verifying GT against raw AGBS cell/type counts.
   Do not invent empty observations from absent MongoDB records. If complete
   coverage cannot be established, report the failure and the available evidence.
4. Repeat that 60-s input unpaced and paced at 1x, queue capacity 8, with exact
   logical-output comparison. No concurrent builds or benchmarks during timing.
5. Run a separate 120-s live realization with renderer playback 1x, buffer capacity
   8 and synchronous MongoDB publication. Different random movement realizations
   prevent a paired headless-versus-renderer performance inference.

All runs use the unchanged local Semantic First / Temporal First secondary policy
from `results/moving-scoped-comparison-2026-10-22/cell_local_temporal_first/policy.json`:
category support >= 5, total distinct support >= 1, semantic loss <= 1,
1.25--10 m cell sides, 400--1,000 ms intervals, age <= 1,000 ms,
100-ms extensions, and `policy_satisfied` release. No regional constraints are
introduced in this gate. Any deviation or capacity failure must be recorded.

## Measurement contract

Paced replay has an independent steady-clock producer and one unchanged consumer.
Scheduled deadlines never move because processing is slow. The bounded FIFO fails
visibly on overflow; it never silently drops data or backpressures the source.
Record scheduled arrival, enqueue attempt/acceptance, service start/end, peak queue
depth, and EOF separately. A successful result requires interval retirement and
observation conservation. Cancellation must wake and join the producer.

Measure p50/p95/p99/max source lateness, queue wait, service and scheduled-to-finish
lag. Replay release callbacks acknowledge private in-memory serialization only;
the final file is written after the run. Live MongoDB acknowledgment and renderer
receipt/display timings are separate observations, not external client delivery.

Sample process RSS and retained history bins/observations/identity bytes/buckets.
Replay preloads all input and retains research output: process RSS growth alone
cannot diagnose a history leak. Live instrumentation overhead and its event
storage must be disclosed. Report population decline and nonempty/busy periods;
120 logical seconds does not imply 120 seconds with 500 Road Users.

The existing live simulator is paced by renderer backpressure, not by an independent
external sensor. Its default 128-frame queue can buffer 6.4 s at 50 ms per frame;
the experimental capacity of 8 is explicitly configured. PlaybackClock schedules
from actual consumption and does not catch up after missed deadlines. Throughput
above real time does not by itself establish bounded end-to-end latency.

## Isolation, artifacts and interpretation

Use fresh UUID-owned raw/release/journal databases and a private temporary cwd.
Never run or reset the user's `Simulation` database. Remove only owned test
databases after successful audit/export, checking ownership before cleanup.
Keep raw observations, logs, captures and per-frame telemetry outside Git. Commit
source, tests, protocol, compact summaries and an English report with source/input
hashes. Input and output replay budgets remain 256 MiB. Native measurements are
finite empirical observations; no hard real-time or general privacy guarantee is
inferred. Record errors and overload instead of changing policies to force success.
