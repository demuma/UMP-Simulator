# P25.4 — Joint urban privacy and utility evidence

Analysis status: **incomplete_or_diagnostic**. Interpretation gate: **diagnose_controls_before_interpreting_lower_attack_success**.

**No held-out privacy result is available in this report.** Unmeasured or incomplete methods remain NA.

The predeclared comparison has 24 TRAIN, 16 CAL and 32 TEST recordings, one matched IN/OUT target pair per recording.

## Recording and execution outcomes

| Split | Planned | Reported outcomes |
|---|---:|---|
| train | 24 | verified: 24 |
| calibration | 16 | verified: 16 |
| test | 32 | not_attempted: 32 |

All planned cases stay in the denominator. No missing case is replaced by another seed.

## Held-out attack assessment

| Method | Full111 AUC | Scalar31 AUC | Full111 TPR [95% CI] | Full111 FPR [95% CI] | Complete TEST groups | Full111 status |
|---|---:|---:|---|---|---:|---|
| Fixed 10 m / 0.4 s | NA | NA | NA | NA | 0/32 | incomplete |
| Fixed 10 m / 1 s | NA | NA | NA | NA | 0/32 | incomplete |
| Fixed 10 m / 2 s | NA | NA | NA | NA | 0/32 | incomplete |
| Fixed 10 m / 4 s | NA | NA | NA | NA | 0/32 | incomplete |
| Fixed 20 m / 0.4 s | NA | NA | NA | NA | 0/32 | incomplete |
| Fixed 20 m / 1 s | NA | NA | NA | NA | 0/32 | incomplete |
| Fixed 20 m / 2 s | NA | NA | NA | NA | 0/32 | incomplete |
| Fixed 20 m / 4 s | NA | NA | NA | NA | 0/32 | incomplete |
| Regional static 10 m | NA | NA | NA | NA | 0/32 | incomplete |
| Regional static 20 m | NA | NA | NA | NA | 0/32 | incomplete |
| Adaptive Semantic First | NA | NA | NA | NA | 0/32 | incomplete |

TPR/FPR use the threshold locked on CAL with an empirical FPR cap of 0.1. This cap is not a population guarantee. AUC is reported without score-direction reversal. No individual-method AUC confidence interval was predeclared.

The primary contrast is AUC(Adaptive Semantic First) − AUC(Regional static 20 m):

- semantic111: NA.
- scalar31: NA.

A negative contrast means lower discrimination by this declared attack. It is not a universal privacy guarantee. The bootstrap is conditional on the fitted models and fixed CAL thresholds.

## Controls

| Control | AUC | TPR [95% CI] | FPR [95% CI] | Status |
|---|---:|---|---|---|
| prior_only | NA | NA | NA | incomplete |
| auxiliary_only | NA | NA | NA | incomplete |
| no_output | NA | NA | NA | incomplete |
| unprotected | NA | NA | NA | incomplete |

Pair-identical prior/auxiliary/no-output controls should have AUC 0.5. The unprotected control uses only exact approved time/position/cell matches; coincident background points can match in OUT. Diagnose failed controls before interpreting lower attack success.

## World-specific TEST utility

| Method | World | Available recordings | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell side (m) | Mean logical delay (ms) | Exact query coverage (%) | Estimated occupancy MAE | Estimated answered (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Fixed 10 m / 0.4 s | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 10 m / 0.4 s | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 10 m / 1 s | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 10 m / 1 s | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 10 m / 2 s | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 10 m / 2 s | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 10 m / 4 s | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 10 m / 4 s | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 20 m / 0.4 s | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 20 m / 0.4 s | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 20 m / 1 s | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 20 m / 1 s | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 20 m / 2 s | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 20 m / 2 s | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 20 m / 4 s | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Fixed 20 m / 4 s | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Regional static 10 m | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Regional static 10 m | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Regional static 20 m | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Regional static 20 m | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Adaptive Semantic First | IN | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |
| Adaptive Semantic First | OUT | 0/32 | NA | NA | NA | NA | NA | NA | NA | NA |

Utility values are equal-recording macro means; JSON includes the available-recording denominator for each metric. J assigns unit loss to omitted observations plus retained taxonomy loss. Conditional MAE is separate from exact query coverage.

## Interpretation limits

- Protected secret: inclusion of one complete visible episode contribution; not person identity, physical presence or all visits.
- Recipient availability: one retrospective final snapshot at H=300 s. Logical sealing delay is not measured live delivery latency.
- Same local400 hard requirements and suppression OFF for every comparator/world; operational track support is distinct from empirical privacy.
- Models and scaling use TRAIN only; operating thresholds use CAL only. No TEST-dependent score-direction flip, tuning or comparator selection.
- Rate intervals are two-sided exact 95% Clopper-Pearson. Primary AUC-difference interval is a 1000-replicate paired TEST-recording bootstrap conditional on fixed fitted models.
- Scalar31 is a joint representation ablation removing semantic and availability coordinates; it does not isolate semantic leakage.
- Utility macro means weight recordings equally and use each world's own sampled input. Conditional occupancy MAE must be read with answered/scored coverage; unknown output is not zero.
- No universal privacy guarantee, population FPR bound, person-level guarantee or real-time certification follows from these measurements.

## Provenance

- private_report_sha256: `2446da17c46047db7f44a80fad39162ceafca93d66b5d5bbd5666c56c83f8710`
- manifest_sha256: `e3b4296674c95d407baf6bc2d3def0564cb77eca37286fdbf9b92ff48c82d5c0`
- implementation_sha256: `40e58dbd20ae9a00dcdc1858cd7de405579778663177d45f50b2486a4d21648d`
