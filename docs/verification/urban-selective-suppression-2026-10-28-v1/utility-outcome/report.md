# Selective suppression with semantic generalization enabled

**Exploratory paired reuse; suppression OFF versus ON (0.10).**

Utility: **complete**. MIA: **not_started**. Gate: **not_evaluated**.

## TEST utility, IN world

Each cell shows OFF → ON; metric-specific available recording counts are retained.

| Method | Retained (%) | Full-input J (%) | Retained taxonomy loss (%) | Retained cell side (m) | Logical delay (ms) |
|---|---:|---:|---:|---:|---:|
| Fixed 20 m / 0.4 s | 56.158 (n=32) → 61.074 (n=32) | 78.669 (n=32) → 75.617 (n=32) | 62.092 (n=32) → 60.096 (n=32) | 20.000 (n=32) → 20.000 (n=32) | 250.052 (n=32) → 250.026 (n=32) |
| Regional static 20 m | 60.603 (n=32) → 68.391 (n=32) | 77.248 (n=32) → 71.379 (n=32) | 62.538 (n=32) → 58.168 (n=32) | 20.000 (n=32) → 20.000 (n=32) | 1839.255 (n=32) → 1801.972 (n=32) |
| Temporal First | 68.526 (n=32) → 70.480 (n=32) | 73.807 (n=32) → 72.140 (n=32) | 61.803 (n=32) → 60.487 (n=32) | 17.933 (n=32) → 18.346 (n=32) | 347.665 (n=32) → 341.058 (n=32) |
| Spatial First | 66.300 (n=32) → 68.462 (n=32) | 73.306 (n=32) → 70.509 (n=32) | 59.762 (n=32) → 56.928 (n=32) | 17.318 (n=32) → 17.912 (n=32) | 1787.520 (n=32) → 1770.183 (n=32) |
| Semantic First / immediate | 68.526 (n=32) → 70.445 (n=32) | 73.802 (n=32) → 72.052 (n=32) | 61.796 (n=32) → 60.344 (n=32) | 17.935 (n=32) → 18.414 (n=32) | 347.665 (n=32) → 341.099 (n=32) |
| Semantic First → Temporal First / wait | 70.215 (n=32) → 72.952 (n=32) | 72.817 (n=32) → 69.342 (n=32) | 61.336 (n=32) → 57.989 (n=32) | 17.814 (n=32) → 18.609 (n=32) | 1804.370 (n=32) → 1787.179 (n=32) |
| Semantic First → Spatial First / wait | 70.331 (n=32) → 73.114 (n=32) | 72.781 (n=32) → 69.283 (n=32) | 61.347 (n=32) → 58.004 (n=32) | 17.840 (n=32) → 18.633 (n=32) | 1806.028 (n=32) → 1791.004 (n=32) |

J includes omitted input and retained taxonomy loss; lower is better. Conditional loss is undefined when no input survives. The selective 0.10 candidate cap does not bound total omission.

## Paired utility changes: ON minus OFF

| Method | Retention (pp) | J (pp) | Taxonomy loss (pp) | Cell side (m) | Interval (ms) | Logical delay (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Fixed 20 m / 0.4 s | 4.916 [4.203, 5.690] (n=32) | -3.052 [-3.485, -2.647] (n=32) | -1.996 [-2.366, -1.677] (n=32) | 0.000 [0.000, 0.000] (n=32) | 0.000 [0.000, 0.000] (n=32) | -0.025 [-0.033, -0.018] (n=32) |
| Regional static 20 m | 7.788 [6.928, 8.713] (n=32) | -5.869 [-6.430, -5.352] (n=32) | -4.370 [-4.978, -3.833] (n=32) | 0.000 [0.000, 0.000] (n=32) | -69.368 [-104.231, -37.066] (n=32) | -37.283 [-54.801, -21.136] (n=32) |
| Temporal First | 1.954 [1.687, 2.237] (n=32) | -1.667 [-1.872, -1.467] (n=32) | -1.316 [-1.545, -1.110] (n=32) | 0.413 [0.345, 0.478] (n=32) | -13.918 [-17.881, -9.732] (n=32) | -6.607 [-8.603, -4.521] (n=32) |
| Spatial First | 2.163 [1.844, 2.465] (n=32) | -2.797 [-3.184, -2.424] (n=32) | -2.834 [-3.349, -2.353] (n=32) | 0.593 [0.474, 0.706] (n=32) | -30.793 [-46.856, -16.346] (n=32) | -17.338 [-25.281, -10.236] (n=32) |
| Semantic First / immediate | 1.919 [1.642, 2.198] (n=32) | -1.750 [-1.989, -1.525] (n=32) | -1.452 [-1.794, -1.180] (n=32) | 0.480 [0.388, 0.575] (n=32) | -13.834 [-17.962, -9.422] (n=32) | -6.566 [-8.601, -4.336] (n=32) |
| Semantic First → Temporal First / wait | 2.737 [2.405, 3.074] (n=32) | -3.475 [-3.829, -3.132] (n=32) | -3.348 [-3.869, -2.908] (n=32) | 0.795 [0.680, 0.928] (n=32) | -31.498 [-48.494, -17.844] (n=32) | -17.191 [-25.635, -10.141] (n=32) |
| Semantic First → Spatial First / wait | 2.783 [2.454, 3.102] (n=32) | -3.498 [-3.841, -3.168] (n=32) | -3.343 [-3.824, -2.904] (n=32) | 0.793 [0.683, 0.910] (n=32) | -26.769 [-44.280, -12.119] (n=32) | -15.023 [-23.604, -7.650] (n=32) |

Intervals use available paired recordings; these are marginal exploratory 95% intervals, not simultaneous comparisons.

## Per-type selective omission

The omission figure shows every registered source type and method. Summary JSON retains each type retention, selective omission fraction and contribution counts with its available N. Missing historical cohort fields remain NA; no missing field is replaced by zero.

## MIA pending

MIA has not started for the new methods. Historical attack results are omitted from this utility-stage report. Utility and hard-policy compliance do not establish a privacy gain.

## Scope and provenance

- Exploratory reuse of 72 already exposed recordings: 24 TRAIN, 16 CAL and 32 TEST. Previously exposed TEST evidence is not a fresh holdout.
- Semantic generalization is enabled throughout. The comparison changes selective suppression from OFF to ON with a per-candidate 0.10 input-contribution cap; whole failed footprints may still be withheld.
- The 0.10 selective cap is not a cap on total omitted traffic, each source type, or an empirical privacy guarantee. Read total retention and per-type omission together.
- J=(1-retained fraction)+retained fraction times retained taxonomy loss. It includes omission, excludes spatial and temporal distortion, and is not a privacy metric.
- Utility uses equal-recording TEST means and each world own input. Each metric and paired interval retains its available recording count; undefined conditional loss and absent historical cohorts remain unavailable.
- Per-type selective omission fractions divide omitted original contributions by that type original contributions in each recording, then average recordings. They are not ratios of macro-mean counts.
- MIA protects inclusion of all observed contributions of one operational track in [0,300 s), not identity, an entire journey or every visit. New scaling/fits use TRAIN only and operating choices use CAL only.
- Full111 versus Scalar31 is a joint representation comparison; it does not isolate semantic leakage. A lower observed attack AUC does not establish a universal privacy guarantee.
- AUC intervals resample paired TEST recordings 1000 times, conditional on fixed TRAIN fits and CAL choices. Utility intervals use available paired recordings. All intervals are marginal, exploratory and non-simultaneous; crossing zero establishes neither superiority nor equivalence.
- Native runs use six concurrent recording workers. These times describe batch throughput and are not isolated runtime benchmarks. Logical sealing delay is not measured live-delivery latency or a per-step guarantee.

Lineage is exported as hashes only. Source IDs, paths, scores, features, model parameters and CAL thresholds are excluded.
