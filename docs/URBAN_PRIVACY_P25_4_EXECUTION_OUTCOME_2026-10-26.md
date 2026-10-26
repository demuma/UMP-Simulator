# P25.4 execution outcome — 26 October 2026

**P25.4 implementation passed its validation gates; the main held-out privacy result is unavailable because source validity failed.** The source-v2 run attempted all 72 preassigned recordings. Seventy-one passed; one TEST recording failed the frozen completion requirement. The driver stopped before any TEST mechanism execution or prediction. This is neither a failed attack nor evidence of poor privacy, and it establishes no comparative privacy winner.

The public evidence consists of the [results overview](verification/urban-privacy-p25-4-2026-10-26-v2/final-outcome/README.md), [aggregate mechanism report](verification/urban-privacy-p25-4-2026-10-26-v2/final-outcome/summary.json), [source-capture outcomes](verification/urban-privacy-p25-4-2026-10-26-v2/final-outcome/source-outcomes.json) and [engineering audits](verification/urban-privacy-p25-4-2026-10-26-v2/final-outcome/engineering-audits.json). Read the source outcomes separately from the mechanism report: a recording can have been captured even when its aggregation and attack evaluations were never started.

## Source captures and mechanism executions are different stages

| Stage | TRAIN | CAL | TEST | Meaning |
|---|---:|---:|---:|---|
| Preassigned source recordings attempted | 24 | 16 | 32 | Every original source slot received one attempt. |
| Source recordings accepted | 24 | 16 | 31 | One TEST source failed the required lifecycle/completion gate. |
| Complete paired mechanism groups | 24 | 16 | 0 | Each completed group contains both IN/OUT worlds and all 11 methods. |
| TEST predictions or feature rows assessed | — | — | 0 | No held-out attack or utility assessment was performed. |

All 40 TRAIN/CAL groups completed their policy and source-accounting audits. They produced **720 native cases**, **160 derived regional-static streams**, and **880 recipient streams/feature rows** in total:

\[
40\times2\times9=720,\qquad
40\times2\times2=160,\qquad
720+160=880.
\]

The factors denote recordings, membership worlds and native or derived methods. A derived regional stream is not a separately timed native execution.

All **22 method/representation variants** converged within the frozen fitting budget, taking 32–250 iterations. These are 11 methods with the full 111-coordinate representation and the secondary 31-coordinate scalar representation. Models use 24 TRAIN recordings; thresholds use the separate 16 CAL recordings. The model lock was written before TEST source generation and remained unchanged. Optimizer convergence establishes that fitting completed; it does not establish attack effectiveness or privacy protection.

The frozen source gate required all 32 TEST recordings to pass before the TEST mechanism phase. Its result was **31/32**, so the driver rejected promotion of the incomplete family. The accepted 31 recordings were not substituted for the declared cohort. There were no replacement seeds, retries of the failed source, trimmed tracks, altered thresholds or available-case AUC estimates.

The unchanged report command subsequently authenticated the locked models, verified the completed TRAIN/CAL artifacts, and reported missing TEST pairs. It returned **NA for every TEST attack, control and utility estimate**, including the primary adaptive-versus-regional-static AUC contrast. No TEST scores were computed. Controls are unavailable because evaluation was prevented, rather than because a negative or positive control failed experimentally. The mechanism report correctly lists all 32 TEST execution groups as `not_attempted`; the separate source report records their actual capture outcomes.

## The remaining source failure

One preassigned TEST source failed. The local source summary and diagnostic receipt retain its exact group/seed mapping; the compact public evidence retains their hashes. Source-v2 preserves the original split assignments and role seeds, without replacing the failed slot.

The native process exited successfully and the measurement clock reached the full 300-second horizon. Nevertheless, the recorded lifecycle was:

| Scheduled episodes | Started | Ended | Still active | Still pending |
|---:|---:|---:|---:|---:|
| 169 | 161 | 153 | 8 | 8 |

A full clock and valid physical geometry are insufficient to meet the additional completion requirement. Seven incoming visitors remained at **Adidas Originals**, together with one Apollo-bound senior pedestrian. Ditsch is a separate portal and was an incorrect initial name for this doorway. The eight pending episodes were linked returns of the active visitors.

A lightweight independent static diagnosis supports a local motion-controller limitation:

- The senior–stroller center distance was approximately 0.727326 m, exceeding the required 0.725 m. A collision-free snapshot therefore existed, while progress remained blocked.
- Using the declared Apollo approach as the goal, all 14 native steering directions at full and half speed—28 moving candidates—were rejected by the recorded static geometry. Absolute map headings of −20°, −25° and −30° provided feasible local segments at both speeds.
- The native A* start connector uses a half-meter grid and a ±2-cell stencil. Its 25 local candidates contained no valid connector. A diagnostic ±3-cell stencil contained one valid connector.
- Six later visitors matched the analytic waiting positions within about 2.1 micrometers, consistent with recorded coordinate precision. The eight final observed positions were constant from no later than 71.3 s through the last sensor sample at 299.9 s.

This diagnosis used the recorded sensor coordinates, configured navigation surfaces, facade exclusions and current body disks. The Apollo approach was inferred from the declared route, not recovered as a recorded private runtime waypoint. No native replay, full reservation reconstruction, A* search or complete pairwise trajectory audit was performed for this diagnostic. A legal wider connector is **not proof of an end-to-end liveness fix**. The frozen implementation and eligibility rule were left unchanged. See the [engineering audits](verification/urban-privacy-p25-4-2026-10-26-v2/final-outcome/engineering-audits.json) for the compact receipt and its provenance.

## What this run establishes

The implementation can capture and authenticate independent synthetic recordings, construct matched complete-contribution IN/OUT pairs, execute and audit the full comparison family, produce semantic recipient streams, compute the declared features, and lock converged TRAIN/CAL models without TEST tuning. Independent spot checks also verified archive round trips, original counts and semantic bins, strongest regional policy bounds, exact regional payload selection, fixed query denominators and utility accounting.

These are engineering and measurement-chain results. The planned held-out comparison of empirical inference risk and utility remains unmeasured. Policy compliance and track/category support do not by themselves establish privacy improvement. The new source failure, despite passing the known-source regression matrix, also prevents a general source-liveness claim.

The threat contract remains a bounded **episode-contribution membership** question. Inputs are synthetic mobility observations from one modeled urban site, rather than calibrated real-world population data. Recipient availability is a **final snapshot at \(H=300\,\mathrm{s}\)**. Logical sealing times are retrospective metadata; this study supplies no live-delivery, online-deadline or hard real-time guarantee. No empirical result figure was generated from the unavailable TEST estimates.

## Recorded closure commands

The closure receipts record these unchanged commands, executed from the repository root. Source verification preserves incomplete/invalid outcomes; a successful command exit does not mean every source passed. The report and exporter created the final all-NA evidence without refitting or running TEST mechanisms.

```sh
/private/tmp/ump-mapped-venv/bin/python -B \
  tools/evaluation/run_urban_privacy_primary_sources.py --verify \
  /Users/maxdemu/Developer/UMP-Simulator/results/urban-privacy-primary-sources-2026-10-26-v2

/private/tmp/ump-mapped-venv/bin/python -B \
  tools/evaluation/run_urban_privacy_primary.py --report \
  /Users/maxdemu/Developer/UMP-Simulator/results/urban-privacy-primary-study-2026-10-26-v2

/private/tmp/ump-mapped-venv/bin/python -B \
  tools/evaluation/report_urban_privacy_primary.py \
  --report /Users/maxdemu/Developer/UMP-Simulator/results/urban-privacy-primary-study-2026-10-26-v2/final-report.json \
  --output /Users/maxdemu/Developer/UMP-Simulator/results/urban-privacy-primary-study-2026-10-26-v2/public-report \
  --no-figures
```

These are the executed command records. Their final report/export destinations already exist and deliberately refuse overwrite; they should not be deleted to repeat the commands. Source verification can create a new immutable verification snapshot. The local `failed-source-closure-receipt.json` binds the closure commands and outcomes; the public aggregate evidence binds the retained report and source receipts.

Raw movement, episode/person identifiers, feature rows, models and individual calibration scores remain in ignored local `results/`. No TEST scores exist. Only compact aggregate evidence, documentation and implementation/tests are intended for the repository.

## Next bounded step

Retain the failed doorway as an explicit regression case. Investigate its local motion and start-connector handling in a separate bounded source-correction step, then validate both known failures and a predeclared independently seeded DEV matrix, preserving every outcome. This does not require adding further aggregation heuristics or attacks.

Do not relax the present completion gate after observing its failure. A future streaming design may legitimately protect all observed contributions within a fixed horizon, including right-censored tracks, but it must explicitly define that protected unit, eligibility and a separate behavioral-validity gate before assessment. Persistent unintended gridlock should not be relabeled as ordinary boundary censoring or repaired by forced EOF exits.

The diagnosed TEST motion is now development knowledge. Any later corrected-source privacy study should freeze its source and eligibility design before fresh unseen evaluation realizations, retain this failed cohort and its model lock as historical evidence, and keep the same distinction between source validity, policy compliance and measured privacy benefit. The current P25.4 research acceptance criterion remains open.
