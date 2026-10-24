# Frozen urban controller: first isolated paced replay

Date: 2026-10-24. Status: **failed bounded-queue acceptance**. This is a measured negative result, not a successful real-time demonstration.

## Experiment and frozen boundary

The existing 240-s urban observation recording was replayed at wall-clock 1x using the original Policy Tree and the existing Semantic First controller. It contains 2,399 measured batches and 187,745 observation contributions. Sensor sampling remains 100 ms. Native-style progress remains 50 ms, including advance-before-ingest calls and steps without a new measurement. The pending FIFO capacity is eight events. The source producer follows an independent steady-clock schedule; it neither waits for capacity nor moves later deadlines to hide overload.

The binary, observation file, policy, unpaced reference, replay adapter source and pacing helper were fingerprinted before and after the measurement. Every fingerprint remained unchanged. No movement generation, simulator, renderer, MongoDB, build or intentionally scheduled heavy test ran concurrently. Platform: macOS 15.7.7, arm64. The Git revision at measurement start was `a996165ac9fa178e00f067880488df608d3c2c08`. This test precedes the new suppression/controller/map/yield changes; later source files must not be described as the tested build.

## Observed result

| Item | Observation |
|---|---:|
| Native return code | 1 |
| Process wall time | 30.334 s |
| Logical event rejected | 27,350 ms |
| Scheduled wall arrival from epoch | 27,350.000 ms |
| Actual enqueue attempt from epoch | 27,353.275 ms |
| Producer lateness at rejected event | 3.275 ms |
| Pending FIFO peak / capacity | 8 / 8 |
| Successful replay result written | No |
| Queue enlarged or schedule relaxed afterward | No |

The maintained helper reports:

```text
AggregationReplay: Paced replay overloaded/cancelled: logical_time_ms=27350, queue_capacity=8, peak_queue_depth=8, scheduled_arrival_ms=27350.000000, enqueue_attempt_ms=27353.274541; no successful replay result was written
```

The average throughput of the earlier unpaced run therefore does not establish bounded live operation. This source-independent controller-plus-diagnostics path cannot sustain this offered schedule within its declared bounded queue for the complete run. The small source-scheduling lateness at the rejected event is separately visible; it is not a service-time measurement or an attribution of the controller cost to a specific component.

The helper in the measured baseline binary retained event timings only in memory and returned them after a successful run. On overflow it cancels and throws; the adapter writes no successful or partial result. Consequently per-event service/response p95/p99/max, the deadline-miss count, completed-event count and peak memory are **unavailable**, not zero. The maintained complete-output equality summarizer cannot validate a result file that does not exist. The report does not infer those missing measurements from total process time. Structured compact evidence parses only the native error that was actually emitted.

## What this measures

The pacing epoch starts after input parsing, validation and core construction. Inside the paced consumer are history/bucket updates, policy and metric assessment, semantic/spatial/temporal selection, coordination/publication consistency, and per-step private diagnostic/release serialization and telemetry. Releases acknowledge only the serialized **in-memory** sink. The input is already classified, tracked and assigned to observation leaves.

This excludes movement generation, neural inference, raw detection-to-cell mapping, rendering, MongoDB/network receipt, and final disk publication. The reported 30.334-s process time includes startup/setup and cancellation as well as partial paced processing; it is not a service-only duration. The diagnostic serializer belongs to this measured research path but may differ from the production handoff. A component profile is required before attributing overload entirely to algorithmic selection or entirely to diagnostics.

The prospective response contract is measured from each independently scheduled arrival to service completion, with a 50-ms cadence deadline and a separately reported 100-ms sensor-response view. Neither deadline slides with consumer delay. The 100-ms sensor interval and 50-ms progress interval are separate clocks. An upstream perception deadline and this downstream deadline would need a shared end-to-end budget before promising their sum to an application.

Logical aggregation delay, `sealed_at_ms - observation_timestamp_ms`, remains a different quantity. Optimizing service reduces computational/queue delay; changing a policy's allowed collection window changes intentional aggregation delay. Neither quantity replaces the other.

## Reproduction

From the repository root, use a fresh output path and the existing frozen artifacts:

```sh
mkdir results/urban-paced-repeat
./simulator/build/AggregationReplay \
  --input results/urban-traffic-2026-10-24-256/replay/observations.json \
  --config results/urban-traffic-2026-10-24-256-policy-comparison/original_adaptive_immediate-policy.json \
  --mode semantic_first --progress-step-ms 50 \
  --pace-rate 1 --queue-capacity 8 \
  --output results/urban-paced-repeat/original_adaptive_paced_1x.json
```

Rebuilds or changed policies/source require a new fingerprinted experiment. Preserve a failure instead of increasing the queue or silently lowering the source rate. If a later run completes, use `tools/profiling/summarize_paced_replay.py` to require complete logical equality excluding `runtime` against the corresponding unpaced control, then report service, queue, response, finish and memory statistics with their scopes.

Raw execution metadata and stdout/stderr remain local under ignored `results/urban-paced-2026-10-24/`. No generated movements or private per-event observations were added to Git. The compact [failure evidence](verification/urban-paced-2026-10-24.json) includes artifact hashes, exact command, scope and unavailable fields.

## Supporting checks and next gate

After measurement completion, the existing `paced_replay` and `paced_replay_summary` CTest groups passed. The maintained Python summary suite passed all eight tests, including logical-output mismatch rejection, native progress/sensor clock separation, causal timestamps, missing/invalid telemetry, bounded queue metadata and no-overwrite behavior. These checks validate the helper contract; they do not turn the failed urban experiment into a pass.

The next useful timing measurement uses structured partial failure telemetry and a component trace on this same frozen source. Separate core selection/history/publication from diagnostic serialization, retain the same independent offered schedule and queue, and validate complete logical equality for successful optimized controls. Then repeat the paced test before claiming a live deadline. Adding CPU parallelism or enlarging the queue without locating the cost would not establish the required bound. Corrected roofs, A1/A2 transit access and pedestrian yielding belong to a separately recorded source validation, so timing and scenario changes stay attributable.

## Optional minimal diagnostic path added after the failed baseline

The historical `full` default remains unchanged. New `--diagnostics minimal` omits private per-retirement window JSON while keeping exact recipient release serialization, all policy revalidation, ownership/retirement checks and observation conservation. It is an isolated adapter boundary: input cell mapping and a production external sink remain outside scope. Minimal diagnostics still include the complete logical audit and profiling overhead.

Both `minimal` and explicit `full --decision-digest sha256` incrementally hash every logical selection and public snapshot, including finest/attempt assessments, suppressed and measured-empty retirements, semantic representations, policy checks, exact support counts and selective-suppression decisions. Canonical typed SHA-256 uses length/presence/type tags and exact IEEE-754 bits. No large private JSON is constructed to compute this hash. The sole excluded structure field is suppression evaluation nanoseconds, which is timing rather than a decision. Hashing occurs inside measured service. A matching hash is an equality audit with cryptographic collision resistance, not a formal proof or privacy mechanism.

Opt-in phase spans distinguish inclusive consume/terminal/publication delivery from private JSON, public JSON, digest and telemetry spans. Nested spans must not be added as disjoint costs. The default unaudited full path does not acquire hashing or phase timing overhead.

`--failure-output NEW_FILE` now preserves bounded completed-prefix telemetry in a separate `ump.paced-replay-failure.v1` sidecar after cancellation. It reports scheduled/enqueued/completed counts, saturated queue and rejected-event timing without creating a successful result. The maintained summarizer supports `--failure` and marks complete-output equality unavailable. Completed-prefix miss counts and tails exclude pending/rejected/future work and cannot be reported as whole-run values. Sidecar serialization occurs outside paced service.

Focused checks pass: SHA-256 empty/abc/multiblock/million-a vectors; more than 100 logical-field mutation checks; exact full/minimal public and digest equivalence across all five strategies and common/local coordination; legacy full payload compatibility; strict CLI/no-overwrite checks; intentional bounded helper overflow with causal completed events; and all 11 Python summarizer tests. These implementation checks do not replace the measured baseline failure. The subsequent quiet urban controls and minimal paced result are recorded below.

## Quiet full/minimal controls and actual minimal 1x trial

All three native cases ran serially without a source, renderer, export, build or other intentionally scheduled heavy job. A local executable snapshot freezes the tested binary (`fa82c62bfd589f764671545579ab1ae5c1739722bd67a33e7d18d53d7dfa03b9`). The original observation and policy files are unchanged. Exact fingerprints of the executable, input, policy, historical reference, controller/instrumentation sources and summarizer remained unchanged throughout the study. Full and minimal runs both enabled the same typed decision audit; minimal omitted only private window JSON.

The historical full payload comparison **passes for every field outside runtime**, and the new full/minimal controls have identical public/common fields and complete typed retirement/release SHA-256 audits. Both account for all 187,745 input contributions. They have 69,392 retirements and 3,199 public releases; measured-empty and suppressed retirements are included. This prevents a faster result from silently dropping empty/private algorithm work.

| Unpaced matched control | Full | Minimal |
|---|---:|---:|
| Core replay and in-memory diagnostics | 125.102 s | 122.784 s |
| Process wall time including setup/output | 128.771 s | 125.802 s |
| Result artifact | 247,340,808 bytes | 2,922,035 bytes |
| Private window JSON span | 3,567.210 ms | 0 ms |
| Complete decision hashing span | 1,211.622 ms | 1,222.996 ms |

The artifact shrinks by **98.82%**, whereas the measured core time falls only **1.85%** in this single pair. Private JSON is 2.85% of the full consume span. It is therefore **not the dominant runtime bottleneck** on this source. The earlier large artifact was a reasonable profiling suspicion; the component measurement corrects that suspicion rather than treating file size as CPU attribution.

In the minimal control, inclusive consume takes 122,783.497 ms and all terminal callbacks together take 1,572.686 ms. Their difference is **121,210.811 ms (98.72%)**: work in manager/history/coordination/candidate selection outside the retirement callback. Inside the terminal path, complete hashing takes 1,222.996 ms, publication sealing 153.703 ms, delivery 198.123 ms inclusive of 64.460 ms public release JSON. These nested spans must not be summed. This trace localizes the next profiling region; it does not yet distinguish history from coordination or candidate evaluation within that region.

The minimal paced 1x run **also fails**. It rejects the logical 26,850-ms event at wall offset 26,855.010 ms with eight pending events and capacity eight. Native return code is 1; no successful replay result is written. Process wall time is 29.619 s, including setup and cancellation. The completed event prefix ends at logical 26,400 ms; 528 events finish, 536 were enqueued, eight remain uncompleted and the full declared source has 4,800 scheduled events. The phase span includes initialization at zero (529 consume calls); queued event telemetry begins at the first positive tick (528 completed events).

| Completed prefix only | Mean | p95 | p99 | Maximum |
|---|---:|---:|---:|---:|
| Service | 27.674 ms | 85.088 ms | 102.821 ms | 139.058 ms |
| Scheduled arrival to completion | 58.099 ms | 234.791 ms | 373.047 ms | 505.423 ms |
| Queue wait | 26.088 ms | 179.093 ms | 301.123 ms | 382.811 ms |

There are **170/528 completed-prefix responses above 50 ms**. Among the 264 completed sensor-arrival steps, **42 responses exceed the separate 100-ms sensor-period budget**. Those sensor steps have service p95 94.185 ms and maximum 139.058 ms. The other 264 no-measurement progress steps have service p95 22.445 ms and maximum 28.548 ms, but they can still wait behind expensive sensor steps. Source scheduling lateness is separately measured (p95 5.030 ms, maximum 5.409 ms); it is included in scheduled response and must not be mistaken for controller service. Quantiles use nearest rank, `ceil(p*n)`.

These are **cancelled-prefix measurements**, not complete-run miss rates or successful endpoint delivery. No equality result is claimed for the incomplete paced output. Exact full/minimal equivalence is established only by the two completed unpaced controls. No larger queue, slower source or shifted deadline was used to obtain a pass. The final rejected logical time differs from the historical full trial, but these are single measurements under different diagnostic builds; their difference is not evidence that omitting JSON makes the controller slower.

The complete compact [study evidence](verification/urban-minimal-paced-2026-10-24.json) contains the protocol, case commands/hashes, complete-equivalence checks, inclusive phases, prefix summaries and sampled memory counters. Raw records remain ignored under `results/urban-paced-2026-10-24/minimal-study/`. Its native failure sidecar is 137,833 bytes and explicitly incomplete. The local binary snapshot remains alongside it.

For reproduction, add `--diagnostics full --decision-digest sha256` to a fresh unpaced control, then repeat with `--diagnostics minimal --decision-digest sha256`. For the timed case use the same minimal flags plus `--pace-rate 1 --queue-capacity 8 --progress-step-ms 50 --failure-output NEW_FAILURE_FILE`. On success compare against the audited unpaced control with `tools/profiling/summarize_paced_replay.py --paced ... --reference ...`. On overflow use `--failure NEW_FAILURE_FILE --output NEW_SUMMARY_FILE`; it preserves the explicit failure classification.

The next optimization target is the nonterminal controller/history/coordination region, with per-operation or event-level profiling and unchanged-source decision-digest controls. Re-evaluating only after new observations or an exact policy/window deadline may be worth investigating. Simply dropping 50-ms progress calls would change the logical algorithm and cannot be presented as a transparent speed optimization without equality evidence. Raw perception-adapter and recipient-sink budgets remain additional work before an operational end-to-end deadline claim.
