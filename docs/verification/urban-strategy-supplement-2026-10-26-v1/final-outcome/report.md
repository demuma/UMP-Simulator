# Supplementary strategy comparison on reused recordings

**Exploratory supplement. The original primary study remains unchanged.**

Phase: **mia**. Utility status: **complete**. MIA status: **complete**. Interpretation gate: **controls_pass**.

The same 24 TRAIN / 16 CAL / 32 TEST sources and matched IN/OUT target pairs are reused. TEST recordings were already evaluated in the original study; these added comparisons are not fresh confirmatory evidence.

All observed contributions of one operational track within [0,300 s) form the protected unit. Hard regional requirements remain identical. Only execution preferences and release rules differ.

## Execution and movement quality

| Split | Planned | Reported outcomes |
|---|---:|---|
| train | 24 | verified: 24 |
| calibration | 16 | verified: 16 |
| test | 32 | verified: 32 |

Planned recipient streams: 2160 = 1584 imported + 576 new. Native executions: 1872 = 1296 imported + 576 new; regional compositions remain 288. Missing/failed cases are retained, never replaced.

| Split | Quality reports | Sources active at H | Sources pending at H | Sources with reported stalls |
|---|---:|---:|---:|---:|
| train | 24 | 1 | 0 | 1 |
| calibration | 16 | 0 | 0 | 0 |
| test | 32 | 1 | 0 | 1 |

Quality counts are sources, not tracks or contributions. Movement quality does not filter enrollment or count as a privacy benefit.

## TEST utility and runtime

| Method | World | Available recordings | Retained (%) | J (%) | Retained semantic loss (%) | Mean side (m) | Mean logical delay (ms) | Core processing (s) | Exact coverage (%) | Estimated MAE | Estimated coverage (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Fixed 10 m / 0.4 s | IN | 32/32 | 32.597 | 87.257 | 60.913 | 10.000 | 250.011 | 0.726 | 0.000 | 0.028 | 1.944 |
| Fixed 10 m / 0.4 s | OUT | 32/32 | 32.285 | 87.411 | 61.008 | 10.000 | 250.014 | 0.726 | 0.000 | 0.028 | 1.917 |
| Fixed 10 m / 1 s | IN | 32/32 | 28.936 | 89.690 | 64.388 | 10.000 | 550.170 | 0.409 | 2.275 | 0.000 | 2.275 |
| Fixed 10 m / 1 s | OUT | 32/32 | 28.670 | 89.817 | 64.500 | 10.000 | 550.150 | 0.409 | 2.241 | 0.000 | 2.241 |
| Fixed 10 m / 2 s | IN | 32/32 | 32.841 | 88.562 | 65.191 | 10.000 | 1050.214 | 0.301 | 0.000 | 0.396 | 2.843 |
| Fixed 10 m / 2 s | OUT | 32/32 | 32.564 | 88.690 | 65.291 | 10.000 | 1050.226 | 0.299 | 0.000 | 0.394 | 2.805 |
| Fixed 10 m / 4 s | IN | 32/32 | 38.974 | 86.539 | 65.461 | 10.000 | 2047.921 | 0.243 | 0.000 | 0.650 | 3.941 |
| Fixed 10 m / 4 s | OUT | 32/32 | 38.759 | 86.648 | 65.547 | 10.000 | 2048.279 | 0.242 | 0.000 | 0.649 | 3.904 |
| Fixed 20 m / 0.4 s | IN | 32/32 | 56.158 | 78.669 | 62.092 | 20.000 | 250.052 | 0.531 | 0.000 | 1.513 | 10.411 |
| Fixed 20 m / 0.4 s | OUT | 32/32 | 55.954 | 78.790 | 62.164 | 20.000 | 250.052 | 0.531 | 0.000 | 1.507 | 10.333 |
| Fixed 20 m / 1 s | IN | 32/32 | 49.604 | 82.151 | 64.039 | 20.000 | 550.126 | 0.325 | 0.000 | 1.453 | 10.560 |
| Fixed 20 m / 1 s | OUT | 32/32 | 49.405 | 82.273 | 64.138 | 20.000 | 550.122 | 0.322 | 0.000 | 1.448 | 10.480 |
| Fixed 20 m / 2 s | IN | 32/32 | 50.827 | 81.789 | 64.189 | 20.000 | 1050.544 | 0.254 | 0.000 | 1.409 | 11.324 |
| Fixed 20 m / 2 s | OUT | 32/32 | 50.624 | 81.915 | 64.295 | 20.000 | 1050.566 | 0.252 | 0.000 | 1.404 | 11.242 |
| Fixed 20 m / 4 s | IN | 32/32 | 53.407 | 80.878 | 64.210 | 20.000 | 2051.524 | 0.215 | 0.000 | 1.336 | 12.893 |
| Fixed 20 m / 4 s | OUT | 32/32 | 53.201 | 81.000 | 64.298 | 20.000 | 2051.524 | 0.214 | 0.000 | 1.331 | 12.807 |
| Regional static 10 m | IN | 32/32 | 45.298 | 83.377 | 63.315 | 10.000 | 1796.532 | NA | 0.000 | 0.600 | 4.288 |
| Regional static 10 m | OUT | 32/32 | 45.017 | 83.519 | 63.397 | 10.000 | 1798.000 | NA | 0.000 | 0.599 | 4.247 |
| Regional static 20 m | IN | 32/32 | 60.603 | 77.248 | 62.538 | 20.000 | 1839.255 | NA | 0.000 | 1.351 | 13.910 |
| Regional static 20 m | OUT | 32/32 | 60.389 | 77.374 | 62.609 | 20.000 | 1838.645 | NA | 0.000 | 1.345 | 13.820 |
| Semantic First / immediate policy release | IN | 32/32 | 68.526 | 73.802 | 61.796 | 17.935 | 347.665 | 32.846 | 0.003 | 1.260 | 12.508 |
| Semantic First / immediate policy release | OUT | 32/32 | 68.279 | 73.944 | 61.862 | 17.946 | 347.867 | 32.714 | 0.003 | 1.254 | 12.439 |
| Temporal First | IN | 32/32 | 68.526 | 73.807 | 61.803 | 17.933 | 347.665 | 32.397 | 0.003 | 1.260 | 12.508 |
| Temporal First | OUT | 32/32 | 68.279 | 73.949 | 61.869 | 17.944 | 347.867 | 32.257 | 0.003 | 1.254 | 12.439 |
| Spatial First | IN | 32/32 | 66.300 | 73.306 | 59.762 | 17.318 | 1787.520 | 37.824 | 0.000 | 1.241 | 12.855 |
| Spatial First | OUT | 32/32 | 66.038 | 73.459 | 59.828 | 17.334 | 1787.287 | 37.657 | 0.000 | 1.237 | 12.768 |
| Semantic First → Temporal First / wait | IN | 32/32 | 70.215 | 72.817 | 61.336 | 17.814 | 1804.370 | 36.759 | 0.000 | 1.283 | 13.818 |
| Semantic First → Temporal First / wait | OUT | 32/32 | 69.925 | 72.981 | 61.408 | 17.828 | 1804.157 | 36.561 | 0.000 | 1.278 | 13.721 |
| Semantic First → Spatial First / wait | IN | 32/32 | 70.331 | 72.781 | 61.347 | 17.840 | 1806.028 | 36.616 | 0.000 | 1.285 | 13.852 |
| Semantic First → Spatial First / wait | OUT | 32/32 | 70.049 | 72.940 | 61.416 | 17.854 | 1805.731 | 36.445 | 0.000 | 1.281 | 13.759 |

Means weight recordings equally; each metric has its own available N in summary.json. J covers omission plus taxonomy loss, not spatial/temporal loss. Retained detail is conditional on retained input. Compare conditional MAE together with answered coverage; unknown queries are not zero.

| Native method | TEST runs | Mean subprocess wall (s) | p95 subprocess wall (s) | Maximum subprocess wall (s) |
|---|---:|---:|---:|---:|
| Fixed 10 m / 0.4 s | 64 | 2.119 | 2.240 | 2.339 |
| Fixed 10 m / 1 s | 64 | 1.746 | 1.856 | 1.941 |
| Fixed 10 m / 2 s | 64 | 1.622 | 1.719 | 1.801 |
| Fixed 10 m / 4 s | 64 | 1.560 | 1.665 | 1.738 |
| Fixed 20 m / 0.4 s | 64 | 1.892 | 2.019 | 2.150 |
| Fixed 20 m / 1 s | 64 | 1.657 | 1.826 | 1.855 |
| Fixed 20 m / 2 s | 64 | 1.576 | 1.681 | 1.770 |
| Fixed 20 m / 4 s | 64 | 1.534 | 1.651 | 1.715 |
| Regional static 10 m | NA | NA | NA | NA |
| Regional static 20 m | NA | NA | NA | NA |
| Semantic First / immediate policy release | 64 | 34.279 | 36.758 | 38.522 |
| Temporal First | 64 | 33.829 | 36.109 | 37.885 |
| Spatial First | 64 | 39.232 | 42.356 | 43.470 |
| Semantic First → Temporal First / wait | 64 | 38.153 | 41.644 | 42.554 |
| Semantic First → Spatial First / wait | 64 | 38.030 | 41.513 | 43.131 |

Core-processing and native-subprocess wall times have different boundaries. Old and new executions occurred at different times. Neither is a per-step deadline or live-delivery benchmark. Regional composition native runtime is unavailable.

## MIA assessment

The new models use TRAIN scaling/fits and CAL thresholds only. Original 22 locked variants and controls are imported without refitting; eight new method/representation variants are added. All additions are exploratory.

| Method | Full111 AUC | Scalar31 AUC | Full111 TPR [95% CI] | Full111 FPR [95% CI] | Complete TEST pairs | Full111 status |
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
| Semantic First / immediate policy release | 0.578 | 0.591 | 0.406 [0.237, 0.594] | 0.312 [0.161, 0.500] | 32/32 | evaluated |
| Temporal First | 0.579 | 0.591 | 0.406 [0.237, 0.594] | 0.312 [0.161, 0.500] | 32/32 | evaluated |
| Spatial First | 0.580 | 0.608 | 0.219 [0.093, 0.400] | 0.219 [0.093, 0.400] | 32/32 | evaluated |
| Semantic First → Temporal First / wait | 0.586 | 0.597 | 0.469 [0.291, 0.653] | 0.375 [0.211, 0.563] | 32/32 | evaluated |
| Semantic First → Spatial First / wait | 0.582 | 0.597 | 0.500 [0.319, 0.681] | 0.469 [0.291, 0.653] | 32/32 | evaluated |

The CAL FPR cap is empirical, not a TEST/population guarantee. No individual-method AUC CI was declared. Scalar31 removes semantic and availability coordinates jointly.

### Exploratory paired AUC differences

| Contrast (left minus right) | Representation | Difference | Paired 95% interval | Independent groups |
|---|---|---:|---|---:|
| Temporal First − Regional static 20 m | semantic111 | 0.014 | [-0.043, 0.080] | 32 |
| Temporal First − Regional static 20 m | scalar31 | 0.011 | [-0.060, 0.088] | 32 |
| Spatial First − Regional static 20 m | semantic111 | 0.015 | [-0.036, 0.066] | 32 |
| Spatial First − Regional static 20 m | scalar31 | 0.027 | [-0.039, 0.083] | 32 |
| Semantic First → Temporal First / wait − Regional static 20 m | semantic111 | 0.021 | [-0.022, 0.072] | 32 |
| Semantic First → Temporal First / wait − Regional static 20 m | scalar31 | 0.017 | [-0.043, 0.065] | 32 |
| Semantic First → Spatial First / wait − Regional static 20 m | semantic111 | 0.017 | [-0.022, 0.064] | 32 |
| Semantic First → Spatial First / wait − Regional static 20 m | scalar31 | 0.017 | [-0.039, 0.065] | 32 |
| Temporal First − Spatial First | semantic111 | -0.001 | [-0.052, 0.055] | 32 |
| Temporal First − Spatial First | scalar31 | -0.017 | [-0.086, 0.062] | 32 |
| Semantic First → Temporal First / wait − Semantic First / immediate policy release | semantic111 | 0.009 | [-0.030, 0.057] | 32 |
| Semantic First → Temporal First / wait − Semantic First / immediate policy release | scalar31 | 0.006 | [-0.067, 0.075] | 32 |
| Semantic First → Spatial First / wait − Semantic First / immediate policy release | semantic111 | 0.004 | [-0.039, 0.055] | 32 |
| Semantic First → Spatial First / wait − Semantic First / immediate policy release | scalar31 | 0.006 | [-0.075, 0.073] | 32 |
| Semantic First → Temporal First / wait − Semantic First → Spatial First / wait | semantic111 | 0.005 | [-0.022, 0.036] | 32 |
| Semantic First → Temporal First / wait − Semantic First → Spatial First / wait | scalar31 | 0.000 | [-0.019, 0.021] | 32 |

These eight exploratory contrasts are not a replacement for the original primary comparison. Intervals are conditional on fixed fits/CAL and are not simultaneous. An interval crossing zero establishes neither superiority nor equivalence.

### Preserved original primary contrast

- semantic111: 0.013; paired 95% interval [-0.044, 0.072].
- scalar31: 0.011; paired 95% interval [-0.062, 0.092].

### Imported controls

| Control | AUC | TPR [95% CI] | FPR [95% CI] | Status |
|---|---:|---|---|---|
| prior_only | 0.500 | 0.000 [0.000, 0.109] | 0.000 [0.000, 0.109] | evaluated |
| auxiliary_only | 0.500 | 0.000 [0.000, 0.109] | 0.000 [0.000, 0.109] | evaluated |
| no_output | 0.500 | 0.000 [0.000, 0.109] | 0.000 [0.000, 0.109] | evaluated |
| unprotected | 1.000 | 1.000 [0.891, 1.000] | 0.000 [0.000, 0.109] | evaluated |

## Interpretation scope

- Supplementary exploratory comparison selected after the original main TEST results; the reused TEST recordings are not a fresh confirmatory sample.
- Protected secret: inclusion of all observed contributions of one operational track within [0,300 s), not identity, physical presence, a complete journey or all visits.
- Same 24 TRAIN / 16 CAL / 32 TEST source roles, target pairs, auxiliary knowledge, local400 hard requirements and taxonomy; no source resimulation or replacement.
- Only execution strategy, semantic secondary preference and release trigger vary. Selective semantic contribution suppression is OFF; whole failed candidates can still be withheld.
- Semantic preference waiting seeks zero loss before the local terminal boundary; that boundary may be regional or coordinated, not always the nominal four-second maximum. Allowed fallback remains possible.
- Semantic First with immediate policy release is the imported reference. Its secondary switch alone is not an additional independent execution variant.
- New attack models/scaling use TRAIN only; thresholds use CAL only. No TEST-dependent retuning or score-direction reversal. Original fitted models and controls are reused without refitting.
- Exploratory paired AUC differences use 1000 source-pair bootstrap replicates, conditional on the fixed fitted models/CAL thresholds; intervals are not simultaneous and establish no equivalence margin.
- Scalar31 jointly removes semantic and availability coordinates; it does not isolate semantic leakage. The empirical CAL FPR cap is not a population or TEST guarantee.
- Utility is an equal-recording TEST macro mean using each world own input. Every metric retains its available-recording N. Conditional MAE must be read with query coverage; unknown is not zero.
- Full-input J combines omitted observations and retained taxonomy loss; it does not include spatial or temporal loss. Retained-only detail and delay are conditional on survival.
- One retrospective recipient snapshot at H=300 s. Logical seal delay and offline core/native throughput do not establish live delivery or per-step real-time guarantees.
- Full clock/provenance, GT/sensor and physical/data validity remain hard gates. Movement quality is separate and does not filter enrollment.
- No universal privacy, person-level protection, navigation-liveness or real-time guarantee follows from these finite experiments.

## Lineage

The original diagnostic repair is included in summary.json and repair-lineage-public.json. Hashes expose lineage, not private file paths or payloads. Keep both with the figures.

- private_report_sha256: `74d4bc6fc964f6112726a7924cef6ab3c2dbf388872b35aeb49b5b59a58efffd`
- supplement_id_sha256: `c3b1176168f9b4c330e38b376c431888ba4276cd70c11c3fe8a195edbea0e978`
- dataset_manifest_sha256: `81e59a558acae956e8b38a9c1d58e18ef274d010e699659d56fd18ebf4d19567`
- source_split_audit_sha256: `6e9ed0e5d2d4fe9bf563a9b3baf0e79fd414c83bd1055db3f148a2b17d998454`
- native_execution_summary_sha256: `4d6666b430758f50b77570df1b3bc393c2eddda07e6d756d4ebd65248406d87f`
