# Endurance and numerical-timestep report

Date: 2026-10-19. This supplements the [first evaluation report](TEST_REPORT_2026-10-19.md)
and [precise bucket/history status](BUCKET_IMPLEMENTATION_STATUS.md). No production source
or maintained configuration was changed. Tests used the existing simulator/replay binaries,
private generated configurations and new evidence directories.

## Executed live simulations

Both actual headless Simulator runs start with 200 road users and use 10-Hz AGBS sensing,
Spatial First, 400-ms initial / 1,000-ms maximal windows, 2,000-ms history and dedicated
UUID-owned raw/release/journal databases. Each executes exactly 6,000 numerical steps.

| Quantity | 50-ms step | 100-ms step |
|---|---:|---:|
| Simulated duration | 300 s | 600 s |
| Process wall time | 7.6236 s | 9.3826 s |
| Maximum process RSS (`time -l`) | 89.30 MiB | 114.89 MiB |
| GT observations | 220,201 | 110,420 |
| Raw AGBS cell records | 107,446 | 107,351 |
| Expected / measured sensor samples | 2,999 / 2,999 | 5,999 / 5,999 |
| Retired intervals | 584 | 1,329 |
| Public release documents | 104 | 103 |
| Selected policy checks passed | 8,536 | 7,860 |
| Input observation contributions | 109,392 | 109,576 |
| Released observation contributions | 109,041 | 108,935 |
| Final retired endpoint | 300,000 ms | 600,000 ms |
| Detailed diagnostic files | 185.73 MiB | 188.28 MiB |

Verified on both original runs:

- Exit code zero and no error-like simulator log lines.
- Every populated sensor cell/time count, type breakdown and geometry exactly matches
  sampled GT; no duplicate GT identity/time or sensor cell/time keys.
- Correct numerical/sensor cadence and complete diagnostic measurement coverage.
- Contiguous, nonrepeated retired intervals through the exact final endpoint.
- Equal input-contribution totals in fixed candidates and adaptive selections.
- Every public cell/count/geometry matches selected passing diagnostic evidence.
- Every journal record is committed and matches the complete retired sequence.
- Released spatial depths span **1 through 6**. The selected resolution is dynamic.
- The 300-s final interval `[299800,300000)` is a valid truncated 200-ms empty interval;
  the 600-s run ends with `[599600,600000)`.

The numerical step affects how often movement is integrated. At 50 ms the sensor measures
every second step; at 100 ms every step. With a fixed 6,000-step count, the latter covers
twice the simulated duration. These independent stochastic live runs are not paired
numerical-accuracy experiments: initialization and wall-clock-dependent motion remain
uncontrolled. The runtime/RSS difference is not attributed causally to timestep alone.

### Population and realtime limits

Population falls from 200 to 72/77 at 60 s and to zero after the final nonempty GT frames
at 110.35/113.8 s. The remaining duration exercises empty-stream cleanup and interval
continuity. It does not establish sustained 200-road-user throughput for five/ten minutes.
The runs are headless: renderer queues/pacing are excluded. Whole-run speed and maximum
RSS do not establish per-step p95/p99 deadlines, a memory plateau or external delivery
latency. A constant recent-history horizon also does not bound accumulated output files.
Detailed JSONL diagnostics are a substantial output/I/O workload.

A third preflight with a **200-ms numerical step and unchanged 10-Hz sensor** correctly
exits 1 before database writes, with the aligned-ticks validation error. No test database
is created. Producing 100-ms observations directly from 200-ms simulation states requires
additional substeps/interpolation semantics or a different sensor rate; it is not currently
supported by this adapter.

## Sustained analytical aggregation load

To avoid interpreting an empty live scene as persistent load, an additional frozen replay
contains **32 observations at every one of 5,999 sensor samples over 600 simulated seconds**:
191,968 input contributions. Positions occupy fixed fine cells; IDs turn over every 500 ms.
This is an analytical aggregation stress case, not physical trajectories or independent
population evidence. Both strategies process exactly the same saved input and policy.

| Quantity | Temporal First (space first) | Spatial First (time first) |
|---|---:|---:|
| Full subprocess wall time | 2.6398 s | 2.5158 s |
| Reported replay-core time | 501.804 ms | 334.063 ms |
| Retired intervals | 1,500 | 600 |
| Released cells | 15,000 | 6,000 |
| Released contributions | 191,968 | 191,968 |
| Final endpoint | 600,000 ms | 600,000 ms |
| Independent oracle | Valid | Valid |

All contributions are accounted for and released without overlap, and both final endpoints
match the requested horizon. The explicit oracle budget is 200,000 checked cells. Core
time includes in-memory result serialization; it excludes replay input parsing/validation
and output file I/O. Subprocess wall time includes those stages but excludes the independent
Python audit. Neither number gives worst-case individual decision latency. This case tests
persistent aggregation work without rerunning a different physical simulation per strategy.

The generator's normal empirical CLI still caps its horizon at 60 seconds. This longer
analytical fixture was produced by an archived one-off script, not by silently bypassing
that CLI's documented bound. It is a duration/load check, not another independent privacy
experiment or an additional learned attack result.

## Evidence, recovery and isolation

Evidence root: `results/endurance/2026-10-19/` (private and Git-ignored).

- `live-50ms-a38e9d9943d547b199d7eb666c9833dd/summary.json`
- `live-100ms-3009450ca19f4e0bbb4973f64cb602b4/summary.json`
- `live-200ms-rejected-e836adc5b7bb4f2a9e97c1236529721d/`
- `persistent-replay-0e97e556f3a54b88b403e70a23b8b950/summary.json`

Bundles retain configurations, binaries' SHA256 hashes, logs, audit exports, checks,
diagnostics and the executed private runner scripts. All six successful-run databases
were deleted only after verified export and owner-token/role checks. Existing Simulation
and demonstration databases were never selected or cleared.

The first live postprocessing encountered runner-only mongosh underscore-collection access
and BSON integer serialization issues. The audit was corrected and resumed against the
original unchanged data; the simulator was not rerun. Original failure evidence remains
alongside the final verified summary. This recovery is not a production simulator defect.

## Follow-up and presentation claims

The endurance evidence supports correct cadence, hierarchy selection, publication lifecycle
and clean end handling in these configurations. It adds persistent-load throughput evidence
for the aggregation core. It does not establish a hard realtime guarantee or full preemptive
bucket implementation.

For October 25 prioritize a precise architecture/status figure, the research question and
canonical formulas, fixed/adaptive utility/attack trade-offs, the demonstrated A07 retention
gap, and one controlled functional-region result. Add cell-local coordination before
claiming independent local temporal windows. Keep automatic prewarming explicitly planned
unless a bounded measured implementation is added. Full maps/shop demand/navigation and
additional sensitive-attribute metrics remain later work. Profile per-stage/per-step tails,
queue wait and diagnostic/database I/O before selecting a performance optimization.
