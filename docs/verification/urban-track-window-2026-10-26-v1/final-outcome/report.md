# Fixed-window track contributions: joint privacy and utility evidence

Analysis status: **complete**. Interpretation gate: **controls_pass**.

These are held-out results for the declared observed-track-window contribution-membership attack.

Protected unit: all observed contributions of one operational track within [0,300 s), including valid active/censored tracks. The secret concerns contribution inclusion, not a completed journey, physical presence or a person.

The declared comparison has 24 TRAIN, 16 CAL and 32 TEST source recordings, one matched IN/OUT target pair per source. Source quality is reported separately and does not filter enrollment.

## Source and execution outcomes

| Split | Planned | Reported outcomes |
|---|---:|---|
| train | 24 | verified: 24 |
| calibration | 16 | verified: 16 |
| test | 32 | verified: 32 |

All planned cases stay in the denominator. No missing case is replaced by another seed.

## Movement quality, separate from validity and membership

Quality-summary availability: **reported**. Profile: `observed_track_window_v1`. Counts below are sources, not tracks. Unknown counts remain NA.

| Split | Planned sources | Window-verified sources | Quality reports | Sources with active tracks at H | Sources with pending tracks at H | Sources with reported stalls |
|---|---:|---:|---:|---:|---:|---:|
| train | 24 | 24 | 24 | 1 | 0 | 1 |
| calibration | 16 | 16 | 16 | 0 | 0 | 0 |
| test | 32 | 32 | 32 | 1 | 0 | 1 |

Full-clock/provenance, GT-visible-interval agreement and physical/data checks remain hard gates. Journey/visit completion and reported stalls are quality diagnostics. A pathology is not a privacy benefit; no trace is dropped or given an artificial EOF exit to improve these results.

## Held-out attack assessment

| Method | Full111 AUC | Scalar31 AUC | Full111 TPR [95% CI] | Full111 FPR [95% CI] | Complete TEST groups | Full111 status |
|---|---:|---:|---|---|---:|---|
| Fixed 10 m / 0.4 s | 0.672 | 0.664 | 0.188 [0.072, 0.364] | 0.062 [0.008, 0.208] | 32/32 | evaluated |
| Fixed 10 m / 1 s | 0.622 | 0.633 | 0.375 [0.211, 0.563] | 0.094 [0.020, 0.250] | 32/32 | evaluated |
| Fixed 10 m / 2 s | 0.620 | 0.627 | 0.312 [0.161, 0.500] | 0.188 [0.072, 0.364] | 32/32 | evaluated |
| Fixed 10 m / 4 s | 0.591 | 0.596 | 0.281 [0.137, 0.467] | 0.156 [0.053, 0.328] | 32/32 | evaluated |
| Fixed 20 m / 0.4 s | 0.605 | 0.579 | 0.125 [0.035, 0.290] | 0.094 [0.020, 0.250] | 32/32 | evaluated |
| Fixed 20 m / 1 s | 0.601 | 0.572 | 0.156 [0.053, 0.328] | 0.094 [0.020, 0.250] | 32/32 | evaluated |
| Fixed 20 m / 2 s | 0.568 | 0.561 | 0.156 [0.053, 0.328] | 0.125 [0.035, 0.290] | 32/32 | evaluated |
| Fixed 20 m / 4 s | 0.567 | 0.575 | 0.188 [0.072, 0.364] | 0.188 [0.072, 0.364] | 32/32 | evaluated |
| Regional static 10 m | 0.579 | 0.638 | 0.281 [0.137, 0.467] | 0.156 [0.053, 0.328] | 32/32 | evaluated |
| Regional static 20 m | 0.565 | 0.581 | 0.406 [0.237, 0.594] | 0.375 [0.211, 0.563] | 32/32 | evaluated |
| Adaptive Semantic First | 0.578 | 0.591 | 0.406 [0.237, 0.594] | 0.312 [0.161, 0.500] | 32/32 | evaluated |

TPR/FPR use the threshold locked on CAL with an empirical FPR cap of 0.1. This cap is not a population guarantee. AUC is reported without score-direction reversal. No individual-method AUC confidence interval was predeclared.

Primary contrast: AUC(Adaptive Semantic First) − AUC(Regional static 20 m).

- semantic111: 0.013; paired 95% CI [-0.044, 0.072], N=32.
- scalar31: 0.011; paired 95% CI [-0.062, 0.092], N=32.

A negative contrast means lower discrimination by this declared attack, not universal protection. Bootstrap uncertainty is conditional on fitted models and fixed CAL thresholds.

## Controls

| Control | AUC | TPR [95% CI] | FPR [95% CI] | Status |
|---|---:|---|---|---|
| prior_only | 0.500 | 0.000 [0.000, 0.109] | 0.000 [0.000, 0.109] | evaluated |
| auxiliary_only | 0.500 | 0.000 [0.000, 0.109] | 0.000 [0.000, 0.109] | evaluated |
| no_output | 0.500 | 0.000 [0.000, 0.109] | 0.000 [0.000, 0.109] | evaluated |
| unprotected | 1.000 | 1.000 [0.891, 1.000] | 0.000 [0.000, 0.109] | evaluated |

Pair-identical prior/auxiliary/no-output controls should have AUC 0.5. The unprotected control uses exact approved time/position/cell matches; background points can also match in OUT. Diagnose failed controls before interpreting lower attack success.

## World-specific TEST utility

| Method | World | Available recordings | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell side (m) | Mean logical delay (ms) | Exact query coverage (%) | Estimated occupancy MAE | Estimated answered (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Fixed 10 m / 0.4 s | IN | 32/32 | 32.597 | 87.257 | 60.913 | 10.000 | 250.011 | 0.000 | 0.028 | 1.944 |
| Fixed 10 m / 0.4 s | OUT | 32/32 | 32.285 | 87.411 | 61.008 | 10.000 | 250.014 | 0.000 | 0.028 | 1.917 |
| Fixed 10 m / 1 s | IN | 32/32 | 28.936 | 89.690 | 64.388 | 10.000 | 550.170 | 2.275 | 0.000 | 2.275 |
| Fixed 10 m / 1 s | OUT | 32/32 | 28.670 | 89.817 | 64.500 | 10.000 | 550.150 | 2.241 | 0.000 | 2.241 |
| Fixed 10 m / 2 s | IN | 32/32 | 32.841 | 88.562 | 65.191 | 10.000 | 1050.214 | 0.000 | 0.396 | 2.843 |
| Fixed 10 m / 2 s | OUT | 32/32 | 32.564 | 88.690 | 65.291 | 10.000 | 1050.226 | 0.000 | 0.394 | 2.805 |
| Fixed 10 m / 4 s | IN | 32/32 | 38.974 | 86.539 | 65.461 | 10.000 | 2047.921 | 0.000 | 0.650 | 3.941 |
| Fixed 10 m / 4 s | OUT | 32/32 | 38.759 | 86.648 | 65.547 | 10.000 | 2048.279 | 0.000 | 0.649 | 3.904 |
| Fixed 20 m / 0.4 s | IN | 32/32 | 56.158 | 78.669 | 62.092 | 20.000 | 250.052 | 0.000 | 1.513 | 10.411 |
| Fixed 20 m / 0.4 s | OUT | 32/32 | 55.954 | 78.790 | 62.164 | 20.000 | 250.052 | 0.000 | 1.507 | 10.333 |
| Fixed 20 m / 1 s | IN | 32/32 | 49.604 | 82.151 | 64.039 | 20.000 | 550.126 | 0.000 | 1.453 | 10.560 |
| Fixed 20 m / 1 s | OUT | 32/32 | 49.405 | 82.273 | 64.138 | 20.000 | 550.122 | 0.000 | 1.448 | 10.480 |
| Fixed 20 m / 2 s | IN | 32/32 | 50.827 | 81.789 | 64.189 | 20.000 | 1050.544 | 0.000 | 1.409 | 11.324 |
| Fixed 20 m / 2 s | OUT | 32/32 | 50.624 | 81.915 | 64.295 | 20.000 | 1050.566 | 0.000 | 1.404 | 11.242 |
| Fixed 20 m / 4 s | IN | 32/32 | 53.407 | 80.878 | 64.210 | 20.000 | 2051.524 | 0.000 | 1.336 | 12.893 |
| Fixed 20 m / 4 s | OUT | 32/32 | 53.201 | 81.000 | 64.298 | 20.000 | 2051.524 | 0.000 | 1.331 | 12.807 |
| Regional static 10 m | IN | 32/32 | 45.298 | 83.377 | 63.315 | 10.000 | 1796.532 | 0.000 | 0.600 | 4.288 |
| Regional static 10 m | OUT | 32/32 | 45.017 | 83.519 | 63.397 | 10.000 | 1798.000 | 0.000 | 0.599 | 4.247 |
| Regional static 20 m | IN | 32/32 | 60.603 | 77.248 | 62.538 | 20.000 | 1839.255 | 0.000 | 1.351 | 13.910 |
| Regional static 20 m | OUT | 32/32 | 60.389 | 77.374 | 62.609 | 20.000 | 1838.645 | 0.000 | 1.345 | 13.820 |
| Adaptive Semantic First | IN | 32/32 | 68.526 | 73.802 | 61.796 | 17.935 | 347.665 | 0.003 | 1.260 | 12.508 |
| Adaptive Semantic First | OUT | 32/32 | 68.279 | 73.944 | 61.862 | 17.946 | 347.867 | 0.003 | 1.254 | 12.439 |

Utility values are equal-recording macro means; JSON retains the available-recording denominator for each metric. J assigns unit loss to omitted observations plus retained taxonomy loss. Conditional MAE must be read with query coverage.

## Interpretation limits

- Protected secret: inclusion of all observed contributions of one operational track within [0,300 s), including valid censored/active tracks; not a full journey, person identity, physical presence or all visits.
- Source validation profile: observed_track_window_v1. Full clock, hashes, source law, recorded-visible-interval agreement and physical/data validity remain hard gates. Scheduled journey/visit completion and reported stalls are separate quality diagnostics.
- Movement quality does not filter enrollment. A pathology or oscillation is not a privacy benefit; interpret measured risk and utility for the recorded source distribution.
- Targets require at least two observations; all short/unselected traces remain input. Auxiliary knowledge is the unchanged exact quarter-count sample with upward rounding, identical in IN and OUT.
- Recipient availability: one retrospective final snapshot at H=300 s. Logical sealing delay is not measured live delivery latency; mechanism EOF does not manufacture a road-user exit.
- Same local400 hard requirements and suppression OFF for every comparator/world; operational track support is distinct from empirical privacy.
- Models and scaling use TRAIN only; operating thresholds use CAL only. No TEST-dependent score-direction flip, tuning or comparator selection.
- Rate intervals are two-sided exact 95% Clopper-Pearson. Primary AUC-difference interval is a 1000-replicate paired TEST-recording bootstrap conditional on fixed fitted models.
- Scalar31 is a joint representation ablation removing semantic and availability coordinates; it does not isolate semantic leakage.
- Utility macro means weight recordings equally and use each world's own sampled input. Conditional occupancy MAE must be read with answered/scored coverage; unknown output is not zero.
- Source artifacts, old status and original TRAIN/CAL roles are preserved under the new binding. A former exposed TEST source/model is not new held-out evidence.
- No universal privacy guarantee, population FPR bound, person-level guarantee, navigation-liveness guarantee or real-time certification follows from these measurements.

## Provenance

Source split audit status: **verified**. Private references are represented only by hashes.

- private_report_sha256: `70abeed6ff101fd51723a610a58120c5963db347510bfe630d882c5ad1509f71`
- private_evaluation_id_sha256: `6f3c6fe85c7ce4b9ab71fe1a3c65faa1c14872c3214e3940f3f69a65ead1c18c`
- dataset_manifest_sha256: `81e59a558acae956e8b38a9c1d58e18ef274d010e699659d56fd18ebf4d19567`
- evaluation_manifest_sha256: `faf818098ad2a4ab6e9b5a3eebb6c94c5b084397523ce74228439576e9c4ac50`
- source_profile_sha256: `6c32952356d028267e434864fc31b2f05f61ce8b051a5fb5d746a431c864bccf`
- import_ledger_sha256: `f761849f5b29e775418771fe5d1271e15728200cfd5fe5d7fc4d82d962643f8c`
- source_protocol_sha256: `574aaeed43514a14e5a0beeda2ef979b881be75abab72a6bbb0535782001f4eb`
- implementation_sha256: `618bdf1a3de2bafeed15cd9e031921755764bdda252335ca10fce662754bbafc`
- source_split_audit_sha256: `6e9ed0e5d2d4fe9bf563a9b3baf0e79fd414c83bd1055db3f148a2b17d998454`
