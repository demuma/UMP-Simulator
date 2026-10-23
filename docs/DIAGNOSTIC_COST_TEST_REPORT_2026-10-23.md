# Diagnostic cost investigation and implementation test report

Date: 2026-10-23. Baseline: `9705eb8`. Protocol:
[DIAGNOSTIC_COST_PROTOCOL_2026-10-23.md](DIAGNOSTIC_COST_PROTOCOL_2026-10-23.md).
[Compact evidence](DIAGNOSTIC_COST_RESULTS_2026-10-23.json) and
[cleanup manifest](DIAGNOSTIC_COST_CLEANUP_2026-10-23.json) contain source, binary,
input and artifact hashes plus all measured stages and comparisons.

## Finding and implemented change

Private file diagnostics have measurable cost, but the original large file size
was insufficient to identify that cost. On the same frozen input, turning file
diagnostics off reduces mean measured processing from **13.129 to 11.411 s**:
**13.09% less time** across two full/off pairs. Both full output repetitions are
byte-identical to the old candidate and selection JSONL files. Every complete
logical replay result matches the baseline after removing only `runtime`.

The production Simulator now accepts explicit `aggregation.diagnostics.mode`
values `full` and `off`. Full remains the historical default, with synchronous
record visibility and error handling. Off avoids creating the two private JSONL
sinks and skips their diagnostic-only fixed-candidate evaluation. All controller
metric evaluation, regional policy checks, immutable publication, durable journals,
latest selection snapshots and renderer progress snapshots remain active. There
is no new thread, skipped clock call, weakened policy or controller change.

```yaml
aggregation:
  enabled: true
  # Other normal aggregation/policy/publication settings still apply.
  diagnostics:
    mode: off
```

Use `full` for detailed recorded inspector/audit files. Off retains live overlays
but creates no recorded diagnostic files for an offline inspector. This is a
startup configuration, not a GUI/runtime toggle. The maintained normal config is
unchanged; users must explicitly choose off for the lower-cost path.

## How costs were separated

The paired adapter loads the existing authenticated 20-s n500 recording, with
99,140 observation contributions, seven types, 80 x 80 m, depth 6 and 100-ms
sensor samples. The same local Semantic First / Temporal First secondary policy
and renderer progress snapshot work apply to both variants. No movement is
regenerated or exported for this gate.

It uses the actual live ordering: `advance(0)`, then advance every 50 ms before
a 100-ms sample ingest; ingest retains its own second advance at the same time.
It finishes at the exclusive endpoint. This ordering produces the same complete
logical result as the retained stock 100-ms-only replay on this input. This
finite equality does not authorize skipping clock calls in general.

Copied source instrumentation separates BSON construction, JSON serialization,
stream insertion, flush, candidate-only evaluation, selection copying, snapshot
creation and in-memory publication/serialization. Source/prepared-source hashes
are recorded. Each run is sequential, with no concurrent builds or benchmarks.
The paired adapter excludes MongoDB, motion generation and actual renderer drawing;
actual live probes measure these separately. Nested timings are inclusive and
must not be added as independent costs.

## Paired measurements

| Variant | Processing time | 100-ms sample-step p95 | Maximum sample step | EOF |
|---|---:|---:|---:|---:|
| Baseline full | 13.121 s | Recorded in compact stages | 108.96 ms | 160.42 ms |
| Measurement-only disabled control | 11.424 s | Recorded in compact stages | 76.51 ms | 83.23 ms |
| Production full, repeat 1 | 13.108 s | 93.54 ms | 107.81 ms | 154.60 ms |
| Production off, repeat 1 | 11.463 s | 67.54 ms | 76.17 ms | 83.05 ms |
| Production full, repeat 2 | 13.151 s | 96.60 ms | 109.09 ms | 152.82 ms |
| Production off, repeat 2 | 11.359 s | 66.98 ms | 76.51 ms | 83.15 ms |

The first baseline/control predated explicit sample-step classification; its
maximum is the maximum ordinary 50-ms source step. The optimized rows classify
199 sample steps separately from 201 no-sample steps. Four sample services exceed
100 ms in each optimized full run, and none in either off run. However 90--91
ordinary source steps exceed 50 ms even with off. These are unpaced service
measurements, not scheduled arrival/queue timing or a hard deadline guarantee.
The earlier 60-s paced trace still contains a 119-ms service and remains valid.

Paired profile quantiles select zero-based index `int((n-1)*p + 0.5)`; live harness
quantiles use nearest rank `ceil(p*n)-1`. They can differ by one sample. The
explicit processing scope in each compact record includes enabled diagnostic file
I/O. The first raw baseline inherited an older replay scope string excluding file
I/O; the compact scope note corrects that description without changing raw results.

Mean diagnostic components over the two production full repetitions:

| Component | Time over 20 logical seconds |
|---|---:|
| BSON construction, total | 380.9 ms |
| JSON serialization | 1,079.8 ms |
| Stream insertion | 104.3 ms |
| Per-record flush | 13.6 ms |
| Diagnostic-only candidate evaluation | 50.7 ms |
| Selection copying | 22.5 ms |
| Renderer progress snapshots | 59.2 ms |

Candidate/spatial sinks emit 7,913 records and 190,258,761 bytes per full run.
Selected/source/attempt BSON spans are nested within the BSON total. Flush is
about 1% of the diagnostic sink cost here, so removing it is not the justified
first optimization. Selection copying and progress snapshots are also small in
this workload and remain unchanged.

## Actual live probe

Two separate maintained-Simulator realizations run for 20 logical seconds with
500 initial Road Users. Full is headless; off has the renderer enabled. These
are integration probes, not a paired causal speed comparison: motion is random,
populations differ and renderer pacing/backpressure changes execution.

| Check | Full, headless | Off, renderer |
|---|---:|---:|
| Process wall time | 28.588 s | 20.918 s |
| Source steps | 400 | 400 |
| Recipient releases / matching committed journal records | 2,494 | 2,499 |
| Population, initial to final | 500 to 486 | 500 to 492 |
| Diagnostic files / bytes | 2 / 189,313,047 | 0 / 0 |
| Rendered agent frames | Not applicable | 400 / 400 |

The full live run attributes **6.650 s** to diagnostic sinks, including **5.344 s**
inside stream insertion, 0.448 s BSON construction, 0.738 s JSON serialization and
0.103 s flush. The same stream-insertion scope costs about 0.104 s in the paired
offline adapter. Stream insertion measures copying, stream/OS work, waiting and
scheduling together; filesystem/journal contention is plausible but not isolated
causally by these unpaired runs. File volume alone cannot predict that cost.

The full live prepare/publish/commit operations total **5.016 s**. Individual DB
calls account for about **4.961 s**:

| DB operation | Calls | Total time |
|---|---:|---:|
| Journal lookup | 7,482 | 1.756 s |
| Journal insert | 2,494 | 0.742 s |
| Journal commit update | 2,494 | 0.988 s |
| Recipient lookup | 4,988 | 0.915 s |
| Recipient insert | 2,494 | 0.560 s |

The three public store phases perform eight DB operations per successful release
in this no-retry run: five reads and three writes. Their durability/idempotence
checks are unchanged. Rebuilding release BSON three times per release costs only
32.8 ms in total, and private journal BSON construction 13.8 ms. A BSON cache is
therefore not the measured high-value next change here. DB calls are inside store
phase timings and store phases are inside aggregation; do not double-count them.

The off renderer probe has 199 sensor snapshots: 196 with a completed selection
(the first three precede the 400-ms minimum window) and all 199 with progress.
Actual drawing records show 118 nonempty aggregation overlays and 388 progress
overlays with checks. All 400 agent frames are received and drawn. Measured draw
rate is about 19.58 FPS for requested 1x playback. Thus disabling files demonstrably
preserves the existing live cell/metric/progress channel. Source-to-draw p95 is
462.35 ms with the configured eight-frame queue; a good draw rate does not imply
zero source-to-display delay.

## Tests and configuration boundary

Release build and all **74 CTest entries pass in 17.94 s**. New artifact tests read
the actual JSONL while the sink is alive, checking synchronous visibility, counts,
metrics/unavailable values, thresholds, semantics, selected/suppressed decisions,
local scope and provenance. Malformed decision/source/attempt arrays reject before
writing a record, avoiding unchecked source-array indexing. Valid records retain
their exact old bytes. Configuration tests cover defaults, full/off, empty/invalid
paths, null/wrong types, unknown keys and duplicates. Invalid settings are checked
before database initialization.

Both live audits independently match GT/sample cadence and source counts, verify
recipient/journal payload equality, and complete ownership-checked cleanup. An
initial sandboxed mongosh startup failed before namespace creation; its authorized
retry used fresh names. All nine checked test namespace names are absent: six
created during successful runs were removed, and the first three were not created.
The user's Simulation database and retained movement recording are unchanged.

After preserving compact hashes and comparisons, **24 newly generated full
outputs, diagnostics and detailed traces were removed**, totaling
**968,453,320 bytes**. No new motion recording was exported. Source/build tooling,
compact evidence and configuration/log summaries remain. Raw releases and
per-frame data are not committed.

## Presentation and next gate

Today's [presentation structure](PRESENTATION_STRUCTURE_2026-10-23.md) has eleven
slides and 18 minutes of speech. Runtime details stay in backup. The
[three-scenario plan](THREE_SCENARIO_PLAN_2026-10-23.md) develops residential
entrances, shopfront stopping and a crossing, with all local requirements supplied
through the normal Region → PolicyTree path. The finest legal fixed grid and a
static region-specific comparator are retained in the design.

This implementation gate proves finite output equivalence and isolates observed
costs. It does not establish empirical privacy improvement, global optimality or
hard real-time capacity. The next mechanism study must use identical source and
fair fixed comparators, report local compliance and utility, then freeze a privacy
contract before claiming lower attack risk. A future same-input MongoDB experiment
could isolate the interaction of private logging and durable publication; do not
infer that interaction's causal size from the two unpaired live times.

## Reproduction

See [tools/profiling/diagnostics/README.md](../tools/profiling/diagnostics/README.md)
for copied-source builds, exact input hash, actual production-mode adapter, scopes,
quantiles and complete logical/JSONL comparison commands. Generated artifacts stay
outside Git and must be cleaned only after successful compact evidence capture.
