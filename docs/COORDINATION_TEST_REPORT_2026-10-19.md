# Cell-local coordination test report — 2026-10-19

Status: verified. All 27 configured CTest suites passed, including 134 Python methods.
Both coordination targets also passed fresh ASan/UBSan builds with strict warnings. This report accompanies
[CELL_LOCAL_COORDINATION.md](CELL_LOCAL_COORDINATION.md). It distinguishes registered
regressions, independently recomputed evidence, stress/performance probes and real
headless simulator integration. Existing privacy pilot results remain common-window results.

## Implementation under test

- Independent cell-local starts, check endpoints and effective-policy deadlines.
- A complete sparse spatial ownership frontier with mixed-depth descendants.
- Same-start unpublished parent takeover, including unequal planned endpoints and retained suffixes.
- Bounded sibling holds and parent fallback before a sibling's earliest deadline closes support.
- Explicit and automatic future handoffs after different retired/public starts.
- Immutable, deadline-checked retries and allocation-free state installation after acknowledgement.
- Scoped publication IDs/BSON/journal recovery and bounded spatial retirement.
- Fresh/idle owner compaction, followed by refinement on subsequent fine observations.
- Actual Simulation and AggregationReplay integration behind `coordination:cell_local`.

## Regression and independent audit coverage

`CoordinationRegressionTests` uses hand-worked regional policies and an independent
rectangle/time/raw-identity scan. It checks sample coverage, contribution/type totals,
distinct road users, mean sample occupancy, full spatial coverage, pairwise space-time
nonoverlap and exactly one terminal owner per original observation. Cases include:

1. Siblings with 400-ms minimum versus 200-ms maximum duration.
2. Mixed-depth parent takeover with known-empty sibling footprints.
3. Different private check endpoints and adoption of a shorter unpublished prefix.
4. A previously public sibling blocking retrospective takeover.
5. Incompatible footprint policies and incomplete measurement coverage.
6. Future alignment with explicit resolution of earlier prefixes.
7. A short prefix violating minimum duration and being suppressed explicitly.
8. Sparse depth-six initialization and bounded ownership allocation.
9. A scheduled handoff preventing an ancestor from escaping its reserved domain.
10. An explicit merge exceeding the controller maximum even without a policy duration check.
11. A sink exception followed by an identical retry; expired retries retain the reservation.
12. Ownership-budget rejection without partial state mutation.
13. Motion across fine cells, idle compaction and correct refinement on repopulation.
14. Out-of-phase empty prefixes explicitly aligning before compression, without losing later data.

`CoordinationStressTests` makes 120 reproducible cases using seed 82561, depths 2–4,
both strategy priorities, moving identities, different regional time maxima, explicit
merge/handoff requests and fractional finalization at 1234 ms. It verifies full ownership
after each tick, exact raw counts and identity unions, nonoverlapping terminal support,
and exactly-once contribution accounting. Its policy recheck uses MetricEvaluator;
independent policy verification is provided separately by the Python oracle.

Eight Python integration methods execute the real replay binary. They cover independent
regional durations, both strategy orders, mixed-depth moving identities, missing and
unavailable samples, fractional finalization, measured-empty completion, strict public
export/features, corrupted results and a sustained 120-second analytical input. The
independent oracle reads the original observations and policy configuration; it does not
trust production pass flags, counts or geometry. Public and private retirement overlap
and complete finest-cell-time volume are checked separately.

`ScopedPublicationRegressionTests` checks ledger splitting/coalescing, immutable snapshots,
budget rejection, differing cell clocks, mixed depths, retry behavior, invalid scope/mode,
and local truncated finalization. The exhaustive depth-six ledger case gives all 4096
finest cells distinct clocks (5460 logical nodes), then aligns them back to four nodes.

Real MongoDB store tests use UUID-isolated namespaces and exercise scoped prepare, publish,
idempotent retry and recovery, including two different cells with the same time interval.
Existing v1 release behavior is tested alongside v2. Test-owned databases are removed only
under their established ownership checks.

## Dense depth-six diagnostic measurement

Frozen input: 80-m square, depth six, all 4096 finest cells occupied by one distinct road
user at 100 ms, final time 200 ms, 200-ms initial window and support threshold one.
Both recorded runs produced identical 4096 terminal windows and releases, accounted for
all 4096 contributions and passed independent auditing with zero violations.

| Quantity | Initial implementation | Scoped-query / delta-commit implementation |
|---|---:|---:|
| Reported core processing | 5619.860583 ms | 262.677542 ms |
| Process wall time | 5.887206750 s | 0.374176458 s |
| Peak process RSS | 122093568 bytes | 103858176 bytes |
| Result JSON | 8836688 bytes | 8836688 bytes |

The change removes repeated whole-grid diagnostic reconstruction and full-frontier copies
per single-cell acknowledgement. Both counts/timing decisions and recipient payloads are
identical. These are single diagnostic measurements with concurrent test workloads,
not a controlled comparative runtime study or a throughput guarantee. The 200-ms dense
batch still takes approximately 263 ms of core processing in that measured version.
The version measured precedes the later idle-owner cleanup; it is not substituted for
final live integration evidence.

Artifacts under `results/coordination/2026-10-19/`:

- `scaling-d6-f1abce1987f34ec4bf375d6c2fe13a32/`
- `scaling-d6-optimized-224712c05d9945cab31c32def43770eb/`

They retain input/configuration, binary hashes, process logs, result JSON, summaries and
independent audits. A separate ledger reconstruction over this uniform retirement
sequence peaks at 24 logical nodes and ends at four; it is not an instrumented process
memory counter. The 5460-node figure applies to the separate distinct-clock ledger test.

## Real simulator integration and corrected performance defect

The first 120-second attempt used 32 initial road users, a 50-ms numerical step, 10-Hz
AGBS and isolated raw/recipient/private-journal databases. It was stopped after
195.904 seconds of wall time with the latest terminal decision at 58.5 simulated seconds
and the minimum retirement frontier at 58.1 seconds. It had generated 49961 private
terminal/journal records, 287 public releases and 119893617 bytes of selection diagnostics.
It is **incomplete**, and is not counted as a successful 120-second correctness run.

The structural review found persistent visited fine owners: after road users left,
empty owners could continue to create individual private retirement records. The controller
now coalesces eligible fresh siblings and explicitly aligns idle prefixes before compression.
Fine source history remains available; new occupancy is refined and tested again.
Dedicated regressions cover idle cleanup, out-of-phase alignment and repopulation.

A second live profile showed that coordinated handoff prefixes dominated the remaining
no-output records, rather than idle alignment itself. Each such record still caused two
durable MongoDB operations under the legacy checkpoint setting. The new explicit
`publication.journal_empty_retirements:false` option bypasses only no-recipient journal
checkpoints. Actual selected releases retain the same durable prepare/publish/commit path.
Private diagnostics and the complete in-memory retirement ledger still account for all
support. The default remains true; automatic controller checkpoint/restart is unsupported.

The aborted run is retained as
`live-50ms-bb59cc98af53415abe9201baa8690aa2/`. Complete compressed exports of all three
test databases were count-verified before owner-checked cleanup. The report/receipt mark
it as partial. Its four pre-compaction source snapshots are retained; equivalence between
those later snapshots and the original running binary is not asserted. Subsequent runs
freeze the exact executable, all production sources and hashes before launch.

The second interrupted run, `live-50ms-ccb3935cac784ce5b20d28ea96bb8a85/`, reached
35.3 simulated seconds in 156.724 seconds wall time. It retained 38786 terminal diagnostic
records, 38787 journal records (one in flight at interruption) and 237 recipient releases.
It is also explicitly incomplete. All test data were exported and owner-checked cleanup
completed. Its frozen executable and full production-source snapshot are retained.

## Final rebuilt integration result

The completed run is `live-50ms-4270bced531545e989567752cfa0b3b3/summary.json`.
Its exact executable and production sources were frozen before launch. Configuration:
120 simulated seconds, 2400 steps of 50 ms, 10-Hz AGBS, depth-six input, 32 initial road
users and `journal_empty_retirements:false`. Every actual release remained durable.

| Check / measurement | Observed result |
|---|---:|
| Process exit | 0 |
| Simulated duration | 120000 ms |
| Process wall time | 7.794672875 s |
| Nominal simulated-time / wall-time ratio | 15.3951 |
| Peak simulator RSS | 31997952 bytes (30.52 MiB) |
| Independently audited terminal domains | 160415 |
| Independent violations | 0 |
| Input contributions, GT/raw/fixed/local agreement | 15370 |
| Released contributions | 8143 |
| Recipient releases / committed journal records | 302 / 302 |
| Selected individual policy checks | 1208, all pass |
| Finest possible / actually released depths | 6 / 1–6 |
| Fixed candidate windows | 300 |
| Private diagnostic output | 327683601 bytes (312.5 MiB) |

The raw AGBS cell counts, type counts and geometry match sampled GT. Original observation
contributions are accounted for exactly once across the complete, nonoverlapping space-time
retirement through 120000 ms. Recipient cells, policy checks and committed journal records
match the selected diagnostics exactly. Suppressed/no-output IDs occur in neither recipient
storage nor the journal under the explicit option, while their complete diagnostics remain
available. All three UUID-owned databases were exported, verified and safely removed.

The population falls from 32 initially to 26 at 30 s, 9 at 60 s and zero after the last GT
observation at 81.8 s. This is not a sustained 32-road-user workload or a GUI latency test.
Wall time includes startup, sensor/aggregation work, MongoDB writes, diagnostic I/O and
shutdown; independent post-run audit time is excluded. The old common-window speedup
figures cannot be transferred to this controller or used as paired evidence.

Private decision volume remains a real limitation: 157863 decisions have zero observation
support, 154316 are labelled `coordination_handoff`, and only six are `idle_alignment`.
The new journal option removes needless durable writes but does not solve this decision
churn or bound total diagnostic output. Reducing coordination work/diagnostic verbosity
is recorded as the next performance task; the bounded source history is a separate bound.

## Final regression record

- Complete configured CTest run: **27/27 passed**, 14.61 s process wall time.
- Python methods: **134 passed** across nine Python suites; the CLI replay suite is C++.
- Hand-worked coordination cases: **14 passed**.
- Reproducible stress cases: **120 passed**, seed 82561.
- Fresh ASan + UBSan checks: both coordination targets passed without diagnostics.
- Strict compiler flags: `-Wall -Wextra -Wpedantic -Werror`; only the legacy aggregate
  trailing-default-field warning is disabled with `-Wno-missing-field-initializers`.
- Canonical notation export check and LaTeX draft compilation passed.

The full CTest log, executable/source hashes and summary are retained in
`results/coordination/2026-10-19/final-verification/`. No simulator source changed after
that final build/test. English documentation was finalized afterward.

## Reproduction

```sh
cmake -S simulator -B simulator/build -DUMP_BUILD_SENSOR_REGRESSION_TESTS=ON -DUMP_BUILD_PUBLICATION_STORE_TESTS=ON
cmake --build simulator/build -j 8
ctest --test-dir simulator/build --output-on-failure
python3 tools/export_notation.py --check
```

The independent local replay methods are in `tools/evaluation/test_coordination.py` and
use `UMP_REPLAY_BINARY` when supplied. The default binary is `simulator/build/AggregationReplay`.
Sanitizer checks compile the coordination core/tests with AddressSanitizer and
UndefinedBehaviorSanitizer. The notation fragment also passes a LaTeX draft compilation;
this is syntax validation, not slide layout review.

## Limits of the evidence

Passing these checks establishes the tested ownership, accounting and release constraints.
It does not prove completeness or optimality of every asynchronous schedule, statistical
privacy, a formal anonymity guarantee, or realtime behavior for every workload. Suppression
is recorded separately from meeting availability requirements. Preemptive statistic caches,
paired local/common effectiveness experiments, the persistent renderer mosaic and automatic
simulation checkpoint/restart remain separate work.
