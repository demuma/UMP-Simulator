# Paced replay and live pipeline test report

Date: 2026-10-23. Production source baseline: `5d3cc4b`.
Protocol: [PACED_LIVE_PROTOCOL_2026-10-23.md](PACED_LIVE_PROTOCOL_2026-10-23.md).
Compact evidence: [PACED_LIVE_RESULTS_2026-10-23.json](PACED_LIVE_RESULTS_2026-10-23.json).

## Result

The optimized aggregation core kept up with independently scheduled 100-ms input
on the existing 20-s moving recording, with exactly unchanged logical results.
The integrated Simulator path is slower: its dense first 20 s required 26.067 s
of step processing even without a renderer. The two-minute average conceals this
because population falls substantially. These are different workloads and paths;
neither a core throughput number nor overall simulator speed proves a live deadline.

No aggregation, policy, movement, publication or production renderer behavior was
changed. The new optional replay pacing and isolated live instrumentation measure
the existing behavior. The aggregation consumer is still single-threaded.

## Independently paced replay

The existing frozen recording contains 99,140 contributions in 199 measurements,
500 initial Road Users, 80 x 80 m, depth 6 and seven maintained profiles. The local
Semantic First controller uses Temporal First secondary, category support >= 5,
semantic loss <= 1, cell sides 1.25--10 m and 400--1,000 ms policy windows. The
unchanged `policy_satisfied` trigger applies. This is a homogeneous policy case.

An independent steady-clock producer schedules inputs and EOF against a fixed
epoch. A bounded FIFO accepts at most eight pending events. The consumer alone
owns aggregation state. A full queue fails explicitly instead of silently dropping
input or delaying the producer's schedule.

| Ordinary input event metric | p95 | Maximum |
|---|---:|---:|
| Source scheduling lateness | 10.03 ms | 10.25 ms |
| Queue wait | 0.048 ms | 0.087 ms |
| Consumer service | 73.90 ms | 87.97 ms |
| Scheduled arrival to completed service | 82.75 ms | 98.01 ms |

All 199 ordinary services and scheduled-to-completion intervals were below 100 ms.
Peak pending queue occupancy was 1/8. EOF is separate: 91.23-ms service and
101.27-ms scheduled-to-completion time. This is an empirical trace, not a hard bound.
The unpaced control took 9.169 s of core processing. Including startup/parser and
file work, the control and paced processes took 10.599 and 21.483 s respectively.
Intentional pacing waits are not algorithm cost.

Both complete outputs equal each other and the historical frozen output after
removing only `runtime`. This checks all private decisions and public fields, not
only total counts. There were 2,554 in-memory release acknowledgments; maximum lag
from scheduled logical seal to acknowledgment was 75.35 ms. These acknowledge
serialization into memory. The result file is written only after the run; no
external application receipt or MongoDB delivery is implied.

A deliberately excessive 1,000x rate with capacity 1 failed at logical 300 ms,
returned exit code 1 and created no result file. Queue and cancellation correctness
also have deterministic regression tests; this overload smoke is not a capacity
estimate.

Memory sampling found at most 21 retained history bins, 10,500 observations and
555,975 identity bytes. Replay RSS rose from 96.3 to 114.2 MiB while retained result
strings grew to 21.5 MiB. Process high-water RSS was 580.1 MiB, already reached
before the pacing origin during parsing/preflight. This tool preloads the full
recording and retains research outputs; its RSS is not a streaming-core memory bound.

## Live pipeline

Both live variants use the maintained Simulator, fresh stochastic movement,
500 initial Road Users, 120 logical seconds, 50-ms simulation steps and 100-ms
sensor measurements. They use the same semantic policy, synchronous MongoDB raw
and publication writes, and the production detailed diagnostics. Rendering uses
1x playback and an explicit capacity-8 buffer; the ordinary example still defaults
to 128. Instrumentation is applied to a copied source tree, not production files.

| Live measurement | Headless | Renderer enabled |
|---|---:|---:|
| Requested logical duration | 120 s | 120 s |
| Process wall duration | 122.262 s | 142.261 s |
| Source steps | 2,400 | 2,400 |
| Unique received/drawn agent frames | Not applicable | 2,400 |
| Acknowledged releases / matching committed journals | 9,314 | 8,943 |
| Population, initial to final | 500 to 28 | 500 to 7 |
| Sampled peak RSS | 116.4 MiB | 240.1 MiB |
| Observed history bins / observations | 21 / 10,500 | 21 / 10,500 |
| Source-to-draw p95 / maximum | Not applicable | 461.55 / 469.40 ms |

The rendered first-to-last-frame interval spans 119.95 logical seconds in 141.72
wall seconds: effective playback 0.8464x, about 21.77 s behind requested 1x playback.
All frames are retained, so this is accumulated progress delay rather than missing
frames. The renderer also performs 277 redraws of an already received frame.
Drawing itself takes p95 4.76 ms and maximum 22.66 ms; graphics work alone is not
this run's main bottleneck. PlaybackClock schedules from actual consumption and
does not catch up after a missed deadline.

The rendered agent queue reaches its configured capacity of 8; sensor queue peak
is 4. Agent writes spend 20.17 s in locking/copying/wait combined (p95 48.25 ms).
That scope is not pure waiting time. Independent stochastic movements and
wall-time-dependent velocity noise prevent interpreting 142.26 minus 122.26 s as
isolated renderer overhead. Source-to-draw begins at generation of an agent state;
it is distinct from lag against a globally scheduled real-time source.

The headless source performs 2,400 steps. Its first 20-s segment costs 26.067 s
with population 500 to 487; the next 20-s segment costs 27.559 s with population
487 to 436. Population ends at 28. In the complete trace, step p95 is 180.51 ms,
maximum 390.39 ms, and 978/2,400 steps exceed their nominal 50-ms interval.
Mean service on sensor measurement steps is 92.06 ms (p95 238.94 ms); no-measurement
steps average 9.40 ms (p95 14.98 ms). These are inclusive scopes.

Headless aggregation advance totals 105.27 s and ingest totals 6.68 s. GT writes
total 5.81 s, raw sensor writes 3.11 s and motion/collision work 0.37 s. The 9,314
publication prepare/publish/commit sequences total 16.94 s, nested inside
aggregation. Do not add nested scopes to obtain total runtime. Detailed diagnostic
files total 958,504,250 bytes (914.1 MiB); generation/serialization/flush cost has
not yet been separately timed, so file volume alone is not causal attribution.

The live adapter advances aggregation every simulation step and ingests sensor
samples every 100 ms. Replay advances only the declared sensor cadence. Additional
live work includes diagnostic copies/serialization, synchronous durable publication,
raw data writes and, when rendering, progress snapshots. Skipping clock calls would
need semantic equivalence checks; it is not automatically a safe optimization.

## Tests, isolation and protocol changes

- Release build succeeded. The first integrated suite passed 71/71 entries in
  18.52 s; after adding the analysis helpers, the final suite passed **73/73** in
  **18.88 s**.
- Queue tests cover bounded FIFO order/drain, rejection without data corruption,
  waking both waiters on cancellation, preserving the first producer failure,
  interrupted future waits, event ordering and invalid schedule/rate/capacity bounds.
- Eight paced/unpaced complete-result comparisons cover all five core modes and
  three local adaptive modes, including missing/unavailable measurements, measured
  empties and off-cadence EOF at 850 ms. Invalid CLI flags are rejected.
- Six compact-summary tests check logical equality and timing/provenance validation.
  Eleven live helper tests check safe configuration, unchanged policy transcription,
  cadence, MongoDB count/timestamp matching, EOF ACK accounting and phase statistics.
- Two native complete-result comparisons preserve the frozen moving baseline.
  The explicit native overload check returns nonzero without a successful output.
- Both 120-s live traces pass their complete audits; all 12 owned databases across
  two smoke and two long runs were removed. Initial smoke movement files (38.77 MB)
  and all eight generated diagnostic files (2.004 GB) were removed after audit.
  Small numeric timing traces remain locally for inspection.

The live audit matches source timestamps and populations to MongoDB GT metadata,
matches inside-footprint totals to raw AGBS samples, verifies exact source and
renderer cadence, and reconciles acknowledged release payloads against committed
journal entries. EOF acknowledgment latency has its own boundary and separate
statistics; unmatched timing events are counted explicitly, and none occurred in
the verified long traces. Fresh UUID ownership markers guard creation and cleanup. The user's `Simulation` database was not changed.

The first smoke run passed simulation, publication and capture checks but its
cleanup command used unsupported mongosh underscore-property access. Explicit
`getCollection('_live_owner')` fixed the harness; ownership-checked cleanup was
completed. This was a test-harness error, not a publication failure.

The headless long run preceded the frozen paced pair while the longer input was
being prepared. A planned temporary 60-s movement export was rejected by automatic
approval review under the user's earlier movement-storage restriction. Therefore
the two-minute live tests ran without movement export. The requested explicit
permission for a temporary paired capture remains pending; no generated long
movement recording was retained or substituted. The paired moving replay remains
20 s, and the live tests are independent stochastic realizations. Initial smoke
movement exports were removed after securing compact audit evidence.

Raw input, releases, timing traces and large diagnostic files are not Git artifacts.
Compact results, source hashes, source tools and tests are sufficient to distinguish
what was measured from the untested longer identical-input case.

## Next gate

Measure detailed diagnostic construction/serialization/flush separately from
aggregation and publication, on the same live event ordering. Then introduce a
configurable bounded diagnostic path only if full logical equivalence is preserved.
Review rendering lag and producer backpressure separately from the scientific
aggregation windows. A larger queue merely stores more delay. Further controller
parallelism or skipped progress calls require their own correctness gate.

Keep semantic-cap effectiveness experiments and privacy claims separate from this
latency work. This gate establishes observed timing and conservation; it does not
establish a new privacy guarantee or sustained real-time capacity at 500 Road Users.

## Reproduction

`AggregationReplay` accepts optional `--pace-rate 1 --queue-capacity 8` in addition
to its existing input/config/mode/output arguments. Omitting these flags preserves
unpaced behavior. Use a fresh output path for each run. Parsing and preflight occur
before the arrival epoch; missing cadence slots still call advance, and EOF is a
separately scheduled event. Telemetry is under `runtime.pacing` only.

Use `tools/profiling/summarize_paced_replay.py --paced PACED.json --reference
REFERENCE.json --output NEW_SUMMARY.json` for complete-output comparison and compact
timings. Optional `--binary`, `--source` and `--protocol` record SHA-256 provenance.
The [live measurement guide](../tools/profiling/live/README.md) explains the copied
build, explicit policy, UUID databases and prepare-before-execute harness.
