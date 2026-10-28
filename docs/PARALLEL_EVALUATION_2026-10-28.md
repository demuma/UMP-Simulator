# Bounded parallel evaluation — implementation and DEV test report

Date: 28 October 2026. Status: six-worker scheduler implemented and verified;
the proposed semantic-ON/selective-suppression-ON study has not been started.

## Purpose and execution boundary

The user authorized six concurrent workers. The Mac reports 12 physical/logical
CPU cores and 24 GiB RAM. We parallelize independent recordings with spawned
Python worker processes. macOS schedules their execution; this is not CPU affinity
or a hard six-core CPU quota. Each worker executes one recording's IN/OUT worlds,
methods, regional dependencies, audits and archival serially. The native aggregator,
its event order, policies and publication decisions are unchanged.

The existing serial runner and completed study protocols/results are unchanged.
New files provide a reusable scheduler and a separate, versioned adapter:

- `tools/evaluation/parallel_recordings.py`: default and maximum six workers,
  bounded admission, parent callbacks and manifest-order results.
- `tools/evaluation/run_urban_semantic_ablation_parallel.py`: a concrete adapter
  for a **fresh** instance of the existing exact-only ablation, with a separately
  frozen execution plan. It is not the proposed suppression-ON experiment runner.
- The two corresponding `test_*.py` files cover scheduling and execution boundaries.

The reusable scheduler is ready for the new suppression study. That study still
needs its own declared method/policy configurations, retained-population query
accounting and audit adapters. Neither the old ablation nor an old completed
output directory should be repurposed or relabelled as that study.

## Concurrency and scientific controls

One parent holds the existing study-root lock and admits whole recording groups.
Workers own distinct `groups/<group_id>/` directories. Methods inside a recording
remain serial, and regional static composition waits for its fixed-window inputs.
The parent collects in manifest order after all workers and independent checks
succeed. TRAIN/CAL/TEST roles, old evidence and the utility-before-MIA gates remain.
The adapter does not fit or score attacks.

At most six tasks are admitted. On a worker, initializer, admission or callback
failure, new admissions stop, pending tasks are cancelled where possible and
running work is drained. Failure receipts preserve the attempt; there are no
automatic retries, silent seed replacements or partial success reports. Existing
completed or attempted studies are rejected before new execution artifacts are
written. Parent receipts are atomically published without replacement.

Before admission the parent checks the existing disk floor plus a declared
per-worker allowance (default 2 GiB for each potentially active worker). This is
a disk admission reserve, not an estimated artifact size or a RAM limit. Native
file/history budgets remain unchanged; the full Python/native process working set
can exceed a file-size limit. No automatic worker reduction is implemented.

## Commands and API

Only use the concrete adapter on a newly prepared, unused study with the existing
ablation schema/catalog. Its base protocol must already exist and authenticate.
The following are templates; `NEW_FRESH_PREPARED_STUDY` is not an existing result:

```sh
python3 tools/evaluation/run_urban_semantic_ablation_parallel.py \
  --prepare-execution results/NEW_FRESH_PREPARED_STUDY \
  --workers 6 --worker-disk-reserve-gib 2

python3 tools/evaluation/run_urban_semantic_ablation_parallel.py \
  --run-utility results/NEW_FRESH_PREPARED_STUDY
```

Worker count is frozen during preparation and cannot be overridden at execution.
For a new study runner, import `execute_recordings(groups, worker, workers=6)`.
The worker and initializer must be top-level spawn-picklable functions. Parent
callbacks are `before_submit(group)` and `on_result(group, result)`; returned
results follow manifest order. Wrap executable entry points in the usual
`if __name__ == '__main__':` guard.

## Verification

The final Python command passes **86 tests** in 5.606 seconds, with no failures
or skips: 12 real-spawn scheduler tests, 16 adapter tests and 58 existing semantic
ablation/query regressions.

```sh
cd tools/evaluation
PYTHONDONTWRITEBYTECODE=1 /private/tmp/ump-mapped-venv/bin/python -B -m unittest \
  test_parallel_recordings test_run_urban_semantic_ablation_parallel \
  test_run_urban_semantic_ablation test_urban_semantic_ablation_queries
```

Coverage includes real six-worker overlap, parent-only callbacks, bounded
admission, deterministic reduction, invalid/duplicate IDs, pickling and initializer
failures, abrupt worker exit, cancelling/draining without retries, immutable
protocol/plan bindings, the shared lock, disk admission, receipt-directory creation
failure, incomplete output and final-collection failure. Initializer tracebacks in
the negative tests are intentional; the suite passes.

## Actual native DEV pilot

One previously excluded and independently verified urban DEV recording supplied
an exact `[0, 60000)` prefix with **54,161 observation contributions**. Six repeated
computational tasks use this same prefix per arm; these are not six independent
recordings or new scientific observations. No motion was regenerated and no
TRAIN/CAL/TEST attack was executed.

Each task runs the unchanged native binary with Semantic First / waiting / Spatial
secondary, semantic generalization enabled, selective contribution suppression cap
0.10, full diagnostics and complete logical decision hashing. Each result passes
an independent raw-source policy/conservation audit.

| Execution | Tasks | Observed simultaneous tasks | Batch wall time |
|---|---:|---:|---:|
| One worker | 6 | 1 | 158.202 s |
| Six workers | 6 | 6 | 28.707 s |

The observed single-pair throughput ratio is **5.51**. All **12** outputs have
identical scientific payloads, public releases and complete retirement/release
hashes. Source, base configuration, binary and scheduler hashes remain unchanged.
Each result accounts for the same 54,161 contributions and passes the independent
audit. Runtime fields are deliberately excluded from scientific equality.

In the six-worker arm, the largest native peak RSS is 374.42 MiB and the largest
Python worker peak is 405.95 MiB. These are different processes' lifetime maxima,
not simultaneous per-task memory. The sum of the separate peaks across all six
jobs is 4,571.125 MiB, an upper-bound-style diagnostic, not a sampled aggregate
RAM measurement. Longer recordings, query banks and full study context may use
more memory.

## Interpretation and limits

This is one serial-then-parallel timing pair. Ordinary applications were active,
and final Python regression checks also overlapped part of the parallel arm.
The result demonstrates working concurrency and improved local throughput on this
DEV workload; it does not establish a statistically reliable speedup or a hard
real-time guarantee. Full recording import, aligned-query evaluation, compression
and final collection of all 72 study recordings were not benchmarked here.

Concurrent native/process timings must be labelled as batch diagnostics, not
compared with isolated historical runtimes as an algorithmic speedup. Live/paced
latency and real-time deadlines require their separate controlled benchmark.
The previous 11–12-hour serial estimate should therefore not simply be divided
by six as a guaranteed new runtime; the new study should estimate completion
from its first full recording groups.

Compact evidence is in
[`verification/parallel-evaluation-2026-10-28-dev-v1.json`](verification/parallel-evaluation-2026-10-28-dev-v1.json).
Raw prefix, policies, native outputs, audits and the pilot script remain local in
ignored `results/parallel-evaluation-2026-10-28-dev-v1/`. No generated movements,
individual scores, models or large outputs are included in Git.
