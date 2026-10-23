# Whole-system review and regression report

Date: 2026-10-23. Reviewed baseline: `c550fde`.
Scope: maintained Simulator, sensor clocks, frame transport, mapped motion/identity,
aggregation history and cell-local coordination, numeric/semantic policies,
immutable publication and experimental/runtime reporting. Sources and static
records were inspected by four parallel reviewers. Changes are limited to
reproduced correctness/reporting defects; no privacy thresholds, source density,
movement routes or candidate-choice objective were weakened.

The [compact evidence](SYSTEM_REVIEW_RESULTS_2026-10-23.json) contains aggregate
counts, protocols and hashes. Full generated source/replay/profile data remain
local in ignored `results/` or `/private/tmp` and do not belong in Git.

## Why only one entrance and two adaptive variants?

The 80 × 80-m frozen map contains **six entrance nodes**, not one. The scene
intentionally connects one facade point to its visit-in/visit-out routes. POI shop
names are a separate context layer; the current model does not establish a
one-to-one shop/door relationship or assign per-shop visiting behavior.

| OSM entrance node | Local x/y, m | Snapshot tags | Current visit portal |
| --- | --- | --- | --- |
| 280355670 | 77.55 / 61.90 | entrance=yes, name=Barkhof | No |
| 348025368 | 64.45 / 13.81 | entrance=yes, name=Spitalerstraße | No |
| 4616972979 | 20.36 / 7.27 | entrance=main, level=1 | No |
| 6244468529 | 23.79 / 68.79 | entrance=main | **Yes** |
| 9370793427 | 35.25 / 28.58 | entrance=main | No |
| 11062053180 | 48.73 / 21.04 | entrance=secondary | No |

Facade incidence and the derived walking route are checked for the selected door.
It has no explicit level tag; ground-level accessibility remains a modeling
assumption. Six mapped points do not establish six valid, accessible shop targets.
Connecting more needs building association, level/walkable connectivity and route
validation, explicit destination/visit rates, and tests of interacting admission
resources. Concentrating every visit at one door is also a source of artificial
queueing and local density in the existing fixture; it must not become evidence
of an improved aggregation mechanism.

The existing six-case comparison was deliberately a release-trigger experiment:

| Case family | Primary priority | Secondary priority | Release trigger |
| --- | --- | --- | --- |
| adaptive immediate | Semantic First | Temporal First | policy_satisfied |
| adaptive semantic wait | Semantic First | Temporal First | priority_satisfied |
| four fixed references | Fixed 5/10 m × 400/1000 ms | Not an adaptive priority | Policy-approved output only |

These are two configurations of an implemented mechanism. The core also supports
**Temporal First**, **Spatial First**, **Semantic First + Temporal First** and
**Semantic First + Spatial First**, plus a spatial-only common-window reference.
The preservation convention is unchanged: Temporal First preserves temporal
accuracy and tries spatial coarsening first; Spatial First preserves spatial
accuracy and tries longer windows first; Semantic First protects semantic detail,
using its secondary to order the remaining dimensions.

`immediate` releases at the first legal endpoint even if a coarser category is
needed. `semantic wait` waits for its semantic preference while legal, then uses
permitted fallback at a limit. Both still enforce hard constraints. The current
small matrix does not compare every implemented priority. A broader priority
matrix should be separately predeclared; the frozen six-case results remain
unchanged and are not retrospectively relabeled as that experiment.

## Confirmed defects and corrections

### 1. Sensor float accumulation breaks an accepted 10-ms configuration

`Sensor::isSamplingDue` accumulated floating-point steps and reset to zero.
For a valid 10-Hz sensor with 10-ms source steps it measured at 110/220/330/440 ms,
not 100/200/300/400 ms. AGBS configuration accepted that exact divisor, but its
manager then rejected the off-cadence observations. With unaligned updates the
reset also discarded the requested sampling phase.

The common ABS/GBS/AGBS gate now derives integer microsecond slots from actual
observation timestamps and a fixed initial origin. A late source update measures
once at that actual time; it does not fabricate missed samples. Repeated times
produce no new sample, backwards time and invalid/changed frame rates fail clearly.
Generic periods are rounded to microseconds. AGBS aggregation retains its stricter
whole-millisecond/divisor requirement.

ABS now divides displacement by the actual elapsed interval between consecutive
measured position sets. It never reads an Agent timestamp or a GT velocity.
Unknown/reentering tracks retain the two-observation warm-up. One previous sample
timestamp suffices because the position map contains exactly the preceding
measured set; no new per-person tracker or trajectory linkage was introduced.

Database-backed regressions confirm the corrected 10-ms cadence and complete AGBS
coverage. Irregular updates at 0,60,120,180,240,300,600,610,700 ms measure only at
120,240,300,600,700 ms and recover the known (2,1) m/s velocity. They do not invent
400/500-ms observations. Existing 50-ms, 10-/5-Hz, empty-area, warm-up/reentry,
duplicate-write, frame timestamp and private identity cases remain green.

### 2. Exact minimum = maximum duration could exhaust the evaluation budget

`CellLocalAggregation::makeWindow` recognized a minimum duration only when it was
strictly less than `maxWindowMs`. A policy allowing exactly 1000 ms therefore
started checking impossible 400-ms prefixes. With one permitted evaluation it
could throw before the sole legal endpoint.

The condition is now `<=`. Permanent tests exercise root/regional exact bounds
across all three priorities, success with one evaluation, an independent neighbor
that still releases at 400 ms, and an unreachable minimum that cannot extend the
configured maximum. **17 local semantic gates pass** normally and under
ASan/UBSan. The new suite fails against the original core with the expected early
budget failure. The mapped minimum is 400 ms versus maximum 4000 ms, so its
existing behavior is unchanged.

### 3. UTC markers/offsets and empty run origins were mishandled

Timestamp utilities previously interpreted `Z`/numeric-offset inputs through local
`mktime`, and the current-time string formatted local time with a literal `Z`.
Malformed trailing input could pass. An explicitly empty configured date also
reread wall time on every simulation step, causing drift from the nominal clock.

Explicit `Z` and `+/-HH:MM` input now identifies an absolute UTC instant. Both
BSON and origin conversion share strict calendar/fraction/offset validation.
UTC formatting uses reentrant conversion; negative-epoch milliseconds round-trip.
The Simulation resolves its epoch once and adds elapsed simulation time for all
source states/lifecycle records. Internal timestamps retain microseconds, while
BSON dates retain milliseconds. Fractional input is truncated to BSON precision.

Timezone-free settings intentionally preserve legacy `mktime(tm_isdst=0)` behavior
so old experiments' absolute origins do not silently change. They are still
host-timezone-dependent and are not an unambiguous DST specification. Use an
explicit zone for portable new inputs; no intended offset is inferred for an old
bare date. Missing/empty settings resolve current UTC once.

The utility regression runs under UTC, Europe/Berlin and America/New_York, checks
positive/negative offsets, leap days, fractions, pre-epoch output, invalid dates,
range/elapsed overflow and legacy-origin compatibility. It fails against the
original utility implementation (`Positive offset ignored`) and passes normally
and under ASan/UBSan.

A fresh actual 180-s native run with **empty datetime** independently verifies the
fixed origin: every GT position/velocity/track/relative timestamp, lifecycle event,
AGBS position/type/cadence and logical release matches the prior corrected
64-person source. Only the intentional absolute origin and owned namespaces differ.
Both have 95,443 GT rows, 1,799 complete sample opportunities, 47,706 contributions,
509 published cell-windows and 16 spatial IDs; all 80 episodes finish. The export
checks full per-step lifecycle coverage and all hard output constraints.

### 4. Runtime summarizer used the wrong event clock

The paced summary expected sensor-cadence telemetry even when replay explicitly
advanced every 50 ms between 100-ms sensor samples. It rejected the real trace and
would use the wrong offered interval for deadline statistics.

The corrected tool validates the explicit progress step/origin and origin-inclusive
budget. It separates sample/no-sample service distributions without inventing
measurements. The actual 180-s trace has 3599 ordinary progress events (1799
measurement events and 1800 intervening events), plus EOF. Direct initialization
at zero is outside the queued-event telemetry. **Eight tests pass**, including
malformed clocks and backwards/invalid telemetry; the original summarizer fails
the actual fine-progress trace.

### 5. Reporting and current architecture descriptions

- Achieved speedup and average statistics use actual completed simulated time and
  frame count, with zero-count guards. Planned maximum frames overstate speedup
  after cancellation and yield zero for an unlimited run.
- New comparison results name `native_process_wall_seconds` separately from
  `comparison_pipeline_wall_seconds`. The former surrounds the subprocess; the
  latter includes independent auditing, recipient queries and writes. Historical
  `wall_seconds` fields retain their historical total-pipeline meaning; new files
  keep that field as an explicitly labeled compatibility alias.
- The canonical notation and bucket status no longer call cell-local publication,
  Spatial First secondary, valid-descendant rescue or implemented history lookup
  optimizations unimplemented. Logical Active/Preemptive records remain distinct
  from the sparse owner frontier; persistent eager ancestor prewarming is still open.

## Invariants reviewed and tested

The current source/sensor ordering is consistent: state t is stored in GT, sensors
observe that state using timestamp t, then agents advance. The agent frame for t
is exposed after its sensor contributions. No general one-step displacement,
private person mapping in operational input or missing-measurement renderer wait
was established in this review.

Two exploratory deterministic 500-case audits varied occupancy, types, priorities,
triggers, semantic secondaries, local duration/age/loss constraints and unavailable
samples. One additionally injected explicit merge/handoff requests. Source-derived
audits checked exact identity/category unions, selected hard bounds, no repeated
space-time retirement, complete input accounting and disjoint final ownership.
All **1000 cases pass** after the fix. These temporary exploratory harnesses reuse
the permanent semantic test fixture; they are additional review evidence, not an
exhaustive proof or a new maintained CTest suite.

Publication inspection confirms preflighted scoped retirement, fresh metric checks
at seal/delivery, durable private intent before possible disclosure, immutable
recipient payload IDs/content, reconciliation after ambiguous acknowledgements and
private retirement of empty scopes. Current code explicitly forbids restart under
the same run without recovery. A separate database is not an automatically
provisioned ACL, and the private replay bundle remains private even when its UI
filters recipient-visible fields.

All three historical/fresh mapped sources were rerun through the reviewed
AggregationReplay. **Complete output excluding runtime is identical** to their
frozen controls, and logical releases match the actual native recipient stream.
No existing recording, threshold, source route or six-case experimental protocol
was changed to make this comparison pass.

## Measured runtime and memory

Hardware: Apple M4 Pro, 24 GiB RAM, Darwin arm64. One frozen corrected 128-person
source, 180 logical seconds / 112,565 observation contributions; 50-ms numerical
progress, 100-ms sensing, 64-entry bounded FIFO. The two paced runs were sequential
with review builds/tests paused. Binary/source/config hashes stayed fixed. Both
complete logical outputs equal the frozen unpaced output outside runtime.

| Quantity | Nominal 1× | Accelerated 5× |
| --- | ---: | ---: |
| Offered progress interval | 50 ms | 10 ms |
| Ordinary service events | 3599 | 3599 |
| Service p95 | 25.674 ms | 16.381 ms |
| Service maximum | 34.334 ms | 27.045 ms |
| Services exceeding interval | 0 | 870 |
| Peak queue / capacity | 2 / 64 | 16 / 64 |
| Maximum queue wait | 14.987 ms | 151.283 ms |
| Maximum scheduled-arrival completion | 75.074 ms | 163.274 ms |

At nominal pace one scheduled completion exceeded 50 ms: the producer woke
60.074 ms late at logical 55.7 s, while that event required only 11.960 ms service.
No nominal actual-enqueue-to-completion exceeded 50 ms. Thus measured core service
fits the nominal interval for this case, but **a hard end-to-end deadline claim
would be false**. The service difference between rates is host/pacing variation,
not evidence that an algorithm changed.

The nominal child ran 181.849 s including intentional 180-s pacing, using 39.041 s
user + 0.679 s system CPU. Per-event service is wall time, not thread CPU. The
21.30% consumer busy fraction is wall-clock occupancy, not CPU utilization.

Nominal sampled RSS rose from 91.30 to 116.34 MiB; process high-water 695.19 MiB
had already occurred before pacing during input parsing/preflight. History stayed
bounded at sampled maxima of 61 bins / 7491 observations. Approximately 58.78 MiB
of retained research-result diagnostics grew with duration. Neither preloaded
input nor full research outputs are part of the online-history payload quota.
This is not a whole-native-process RAM guarantee or evidence of an online history leak.

The measurements exclude live movement, renderer, raw sensor/GT MongoDB writes and
external recipient receipt. A code-derived no-retry store path performs four DB
operations per empty retirement and eight per nonempty release. That implies
approximately 190,460 calls for the corrected64 capture (98.92% empty retirements)
and 111,396 for corrected128 (89.64% empty). **These are call counts, not measured
DB durations.** Native-minus-replay wall time cannot isolate I/O because it also
contains startup, source and other work. Measure these components before changing
private checkpoint durability or adding threads.

## Final acceptance and reproduction

- Complete build: passed.
- **82/82 CTest suites passed**, 16.85 s with `-j 6`.
- Real MongoDB sensor regression, 17 semantic cell-local gates and new timestamp
  utility tests: passed; UTC and semantic suites also passed ASan/UBSan.
- Three frozen full-output/native-release equivalence cases: passed.
- Fresh empty-origin actual Simulator/capture/source-equivalence run: passed.
- Nominal/accelerated paced full-output equality and corrected summary: passed.
- 1000 exploratory coordination/accounting cases: passed.

The CMake build registers `timestamp_utilities` by default via
`UMP_BUILD_TIMESTAMP_TESTS=ON`; optional mapped Python dependencies remain isolated.
From the repository root:

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release \
  -DUMP_MAPPED_SCENE_PYTHON=/path/to/mapped-venv/bin/python
cmake --build simulator/build -j 6
ctest --test-dir simulator/build --output-on-failure -j 6
simulator/build/UtilitiesRegressionTests
simulator/build/SemanticCellLocalTests
```

For the runtime experiment, use a fresh output directory and the frozen source /
adaptive-immediate policy from the mapped comparison. Create the matching unpaced
control with the same arguments except `--pace-rate` and `--queue-capacity`:

```sh
simulator/build/AggregationReplay \
  --input results/mapped-2026-10-23-corridor128-final/replay/observations.json \
  --config results/mapped-2026-10-23-corridor128-final/comparison/adaptive_immediate-policy.json \
  --mode semantic_first --progress-step-ms 50 --pace-rate 1 --queue-capacity 64 \
  --output /private/tmp/fresh-paced.json
python3 tools/profiling/summarize_paced_replay.py \
  --paced /private/tmp/fresh-paced.json --reference /private/tmp/fresh-unpaced.json \
  --output /private/tmp/fresh-paced-summary.json
```

Existing generated artifacts are local, not shipped with the repository. The
[map guide](../tools/mapped_scene/README.md) reproduces sources and comparisons.
The empty-origin test set `simulation.datetime: ''` in its new generated scene
before execution, updated that scene's config hash, then used the normal native
Simulator and verified exporter. Its files are under
`results/system-review-empty-origin64-2026-10-23`; original recordings are unchanged.

## Remaining priorities

1. Instrument the actual native source, raw GT/sensor writes, private empty
   retirements and public MongoDB receipt separately; preserve full logical output
   when optimizing. Do not remove durability checks or parallelize the coordinator
   on the strength of total-wall comparisons.
2. Expand explicit visit targets and validate multi-portal motion/queues. Separate
   intended density from artificial gate congestion before scenario-effect claims.
3. Predeclare a wider priority matrix and the three substantive regional application
   scenarios with repetitions and fixed baselines. Preserve the original trigger
   matrix and report coverage/error/retention/detail/delay jointly.
4. Test raw sensor partial bulk-write faults. ABS may retry a partly inserted batch,
   while grid paths can lose failed raw rows. Successful-write duplication tests
   and the mapped source-consistency exporter do not establish fault-idempotence.
5. Define protected units, sensitive attributes and attacker knowledge before
   interpreting support constraints as measured privacy. This review changes no
   empirical-privacy, k-anonymity or general person-continuity guarantee.
