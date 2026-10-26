# Urban source correction: coupled crossing closure

Status: the v1 batch is closed at 37/40 valid sources; the production correction
and two native regressions are applied. All 11 affected CTest groups and 177
Python methods pass. All 48 serial known-configuration motion preflights now pass: 8,119/8,119
episodes, including all three original invalid cases. Source v2 is frozen and
fresh primary execution is running.
This is a source-motion issue discovered by P25.4, not an aggregation or attack result.
The [P25.4 protocol](URBAN_PRIVACY_P25_4_PROTOCOL_2026-10-25.md) remains the analysis reference.

## Observed failure and retained evidence

The 24 prospective TRAIN sources contain 22 verified captures and two invalid
captures. CAL contains 15 verified and one invalid capture. All 40 attempts are
closed, cryptographically reauthenticated under the original implementation and
retained; 37 pass and three fail the source gate. No primary mechanism execution,
attack fit, calibration score or TEST source has been produced. The waiting
execution driver was stopped before it could proceed with incomplete TRAIN data.
All 72 slots and their attempted/unattempted states remain in v1's denominator.

| Role / slot | Scheduled episodes | Started | Ended at 300 s | Active | Pending | Reported stalled | Body overlaps |
|---|---:|---:|---:|---:|---:|---:|---:|
| 17 | 169 | 155 | 106 | 49 | 14 | 43 | 0 |
| 23 | 168 | 155 | 99 | 56 | 13 | 51 | 0 |
| CAL 13 | 165 | 157 | 118 | 39 | 8 | 36 | 0 |

The source clock and captured GT/observation intervals are complete. Native exit
zero and a successful geometry audit do not establish completion of all scheduled
movement. The stricter cohort/liveness gate correctly rejects all three recordings.
Maximum reported pedestrian waits are 283.45 s, 286.25 s and 287.85 s. The second case's
pending episodes are building returns waiting for preceding visible episodes.

Retained local evidence includes complete scene configuration, capture proof,
native execution, recorded observations and GT, independent physical audit,
stdout/stderr and the source-attempt summary. No failed source is trimmed or
replaced, and no stalled road user is silently removed. Final positions in all three cases show priority-rider queues occupying adjacent
crossing areas. Captured output lacks per-resource phase flags, so the common
mechanism in the second/third case remains a hypothesis until the corrected
motion preflight is run.

## Mechanistic explanation and minimal reproduction

Independent crossing controllers close rider admission when pedestrians have
waited beyond the configured fairness trigger. Pedestrian admission still requires
the crossing to be clear of priority riders and near-term conflicts. With queues
between neighboring crossings, a rider can occupy the previous crossing while
waiting behind a leader stopped at the next closed crossing. Opposing queues can
then keep both crossings occupied: neither admits riders, neither can admit its
pedestrians, and neither queue drains. Physical separation can remain valid
throughout this circular wait.

An isolated DEV map reproduces the issue with two four-meter-wide crossings,
separate opposing rider lanes, four riders in each direction and one pedestrian
per crossing. Both resources become occupied and closed for fairness. The original
code ends zero of ten episodes after 60 s, with zero body overlaps. This reproduces
the control dependency without MongoDB, urban map import or privacy policies.

Allowing only riders whose own bodies are currently inside another crossing does
not fix the case: queue leaders can already be in the road space between the
crossings and still block those riders. This negative alternative is retained.

## Bounded cohort candidate

The candidate detects an occupied closure while another occupied crossing is
also closing. It snapshots the currently active priority road-user IDs once for
that closure, including intervening queue leaders. Only those IDs may drain into
the closing resource, and only while no pedestrian batch owns it. New arrivals
and later observation episodes cannot join the cohort. The cohort resets after
the normal pedestrian batch ends or no request/grant remains.

The existing body, swept-body, navigation-surface, speed and displacement checks
remain in force. The candidate changes admission at a closure, not physical
clearance or pedestrian ownership. The configured wait value remains a fairness
closure trigger; it is not a pedestrian completion deadline.

This is conservative recovery, not a complete dependency-graph coordinator. Its
trigger can include unrelated occupied crossings, and the snapshot can include
priority riders elsewhere in the modeled area. A finite cohort does not prove
finite waiting or general liveness: a blocked cohort member or receiving apron
can still prevent progress. These limits require reporting rather than a new
hard guarantee.

## DEV evidence so far

Five isolated regressions pass, including existing complete `MappedSceneTests`.
The ten-episode reproduction completes under the candidate. With twenty riders
per direction and two pedestrians, all 42 episodes end by 39.3 s; pedestrians end
at 26.5/27.15 s despite later rider arrivals. Instrumentation checks that cohort
membership never expands during a closure. Independent review found no
pedestrian-ownership bypass or cohort-reset/expansion defect.

On the exact failed TRAIN-17 configuration, the separate motion-only DEV probe
now ends all 169 episodes at 178.4 s, with no active/pending/stalled tracks or body
overlaps. Independent checks cover 6,402,076 current-body pairs, 6,402,076 swept
pairs, 165,436 speed checks and 165,437 displacement checks. Minimum separation
margins remain positive; 1,748 cohort-immutability checks pass. This is a diagnostic
counterfactual, not a replacement primary capture or a measured privacy effect.

The first custom DEV safety checker incorrectly combined finished and newly
admitted bodies at a half-open lifecycle boundary. That diagnostic failure is
retained. Its corrected checker uses active bodies for current positions and the
appropriate preceding-step visibility for swept segments; the production motion
code and physical thresholds were not weakened to obtain a pass.

The prepared native regression patch uses the normal private production header.
It adds public-API tests for finite drainage, later arrivals, pedestrian progress,
physical safety and caller-cadence determinism. The full prepared native suite
passes with the candidate and fails at the new circular-wait check with the
original motion code. Production CMake remains unchanged.

All prototype files, exact patches, binaries, before/after hashes, raw logs,
positive/negative receipts and independent checks are initially retained locally
under `/private/tmp/ump-p254-two-crossings-dev`. They must be copied into ignored
repository results before production application. The full prototype package and original source/binary/test bytes are now also
retained under ignored `results/urban-privacy-source-correction-2026-10-26-v2`.
Production source/header/test hashes and both native executable hashes are recorded.
`AggregationReplay` is unchanged at
`72fc0aff452ee036d7dfdd8bd8ca7bd343c7462923ec00ccb39f904ee655502f`.
The 48-case motion check uses all eight original DEV and all forty TRAIN/CAL
configurations, including the three failed cases: 8,119 episodes, zero TEST cases.
Each case has one serial attempt and finite 60/70-s internal/process caps.

## Required pre-TEST amendment

A corrected primary run requires an explicit new source version, not a relaxed
v1 gate or a replacement seed. Preserve all 72 group IDs, splits, 216 role seeds,
24/16/32 counts, policy, taxonomy, methods, features, fitting/CAL rules, utility,
uncertainty and limits. Bind the corrected source code/binary and validation
receipts before any TEST generation. The configuration law and geometry remain
unchanged; realized motion dynamics change and must be labeled accordingly.

All 40 TRAIN/CAL recordings must be regenerated under the corrected source
implementation. Original TRAIN/CAL exposure stays in those roles. V1 and v2 are
never pooled as independent evidence. The original 32 TEST realizations remain
unseen until the fresh implementation supplement and actual TRAIN/CAL model lock
pass. The v1 source-validity failure remains an explicit negative result.

## Native implementation verification

The actual Simulator, native scene/configuration tests and maintained motion probe
build successfully. All 11 affected CTest groups pass in 176.97 s, including sensor
regressions and the complete transit/corridor/building/storefront/urban-traffic
finite-drain checks. Two new public-API tests cover the ten-episode crossing loop
and a 42-episode later-arrival case with physical/cadence checks. The final affected
Python suite passes 177 methods, including explicit current-manifest model binding.
The prior 22-stream DEV recipient integration is reauthenticated with current code.
These are implementation/source gates, not held-out privacy or real-time results.

The complete v1 source-only outcome report retains all 72 slots and all 11 unavailable
comparison methods, with no fabricated attack values or figures:
[aggregate v1 report](verification/urban-privacy-p25-4-2026-10-25/v1-source-gate/report.md).

The exact version/exposure/freeze rules are recorded in the
[pre-TEST v2 amendment](URBAN_PRIVACY_P25_4_SOURCE_V2_AMENDMENT_2026-10-26.md).

## Complete motion preflight

All 48 cases and 8,119 episodes pass/reverify, with 332,986,278 body and the same number
of swept-body checks, 8,268,132 speed and 8,268,180 displacement checks, 45,941 cohort
membership checks across 183 drain phases. No failure, retry, TEST access or input
hash drift occurs. Last episode endpoints range 159.35–218.90 s. Minimum body
clearance margin is 8.90e-7 m; minimum swept margin is 0 at required clearance.
This is motion-only DEV/TRAIN/CAL validation; every fresh primary capture must
still pass full sensor/GT/provenance/physical gates. The [compact receipt](verification/urban-privacy-p25-4-2026-10-26-v2/motion-preflight.json)
contains all 48 case outcomes and the three repaired negative cases.
