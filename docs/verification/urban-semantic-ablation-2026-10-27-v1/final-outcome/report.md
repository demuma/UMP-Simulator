# Paired semantic-generalization action ablation

**Exploratory reuse of the same recordings. Historical ON evidence remains unchanged.**

Phase: **mia**. Utility: **complete**. MIA: **complete**. Gate: **controls_pass**.

Seven headline ON/OFF pairs use identical observations and hard policies: 72 recordings (24 TRAIN / 16 CAL / 32 TEST), 2016 headline method/world rows. Three OFF fixed-window dependencies add 432 rows; they are not extra headline methods.

## TEST utility (IN world; every metric retains its available N)

| Method | Generalization | Retained (%) | J (%) | Retained semantic loss (%) | Logical delay (ms) | Aligned exact coverage (%) | Aligned exact count MAE | Aligned estimate coverage (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Fixed 20 m / 0.4 s | ON | 56.158 (n=32) | 78.669 (n=32) | 62.092 (n=32) | 250.052 (n=32) | 5.344 (n=32) | 0.000 (n=32) | 5.344 (n=32) |
| Fixed 20 m / 0.4 s | OFF (exact only) | 0.092 (n=32) | 99.908 (n=32) | 0.000 (n=7) | 246.900 (n=7) | 0.010 (n=32) | 0.000 (n=7) | 0.010 (n=32) |
| Regional static 20 m | ON | 60.603 (n=32) | 77.248 (n=32) | 62.538 (n=32) | 1839.255 (n=32) | 0.622 (n=32) | 0.000 (n=32) | 6.698 (n=32) |
| Regional static 20 m | OFF (exact only) | 0.157 (n=32) | 99.843 (n=32) | 0.000 (n=6) | 1469.897 (n=6) | 0.003 (n=32) | 0.000 (n=3) | 0.019 (n=32) |
| Temporal First | ON | 68.526 (n=32) | 73.807 (n=32) | 61.803 (n=32) | 347.665 (n=32) | 1.746 (n=32) | 0.000 (n=32) | 5.895 (n=32) |
| Temporal First | OFF (exact only) | 0.157 (n=32) | 99.843 (n=32) | 0.000 (n=15) | 1108.738 (n=15) | 0.008 (n=32) | 0.000 (n=5) | 0.016 (n=32) |
| Spatial First | ON | 66.300 (n=32) | 73.306 (n=32) | 59.762 (n=32) | 1787.520 (n=32) | 0.583 (n=32) | 0.000 (n=32) | 6.307 (n=32) |
| Spatial First | OFF (exact only) | 0.153 (n=32) | 99.847 (n=32) | 0.000 (n=10) | 1741.664 (n=10) | 0.003 (n=32) | 0.000 (n=3) | 0.016 (n=32) |
| Semantic First / immediate | ON | 68.526 (n=32) | 73.802 (n=32) | 61.796 (n=32) | 347.665 (n=32) | 1.746 (n=32) | 0.000 (n=32) | 5.895 (n=32) |
| Semantic First / immediate | OFF (exact only) | 0.157 (n=32) | 99.843 (n=32) | 0.000 (n=15) | 1108.738 (n=15) | 0.008 (n=32) | 0.000 (n=5) | 0.016 (n=32) |
| Semantic First → Temporal First / wait | ON | 70.215 (n=32) | 72.817 (n=32) | 61.336 (n=32) | 1804.370 (n=32) | 0.593 (n=32) | 0.000 (n=32) | 6.483 (n=32) |
| Semantic First → Temporal First / wait | OFF (exact only) | 0.157 (n=32) | 99.843 (n=32) | 0.000 (n=15) | 1108.738 (n=15) | 0.008 (n=32) | 0.000 (n=5) | 0.016 (n=32) |
| Semantic First → Spatial First / wait | ON | 70.331 (n=32) | 72.781 (n=32) | 61.347 (n=32) | 1806.028 (n=32) | 0.590 (n=32) | 0.000 (n=32) | 6.507 (n=32) |
| Semantic First → Spatial First / wait | OFF (exact only) | 0.153 (n=32) | 99.847 (n=32) | 0.000 (n=10) | 1741.664 (n=10) | 0.003 (n=32) | 0.000 (n=3) | 0.016 (n=32) |

OFF zero retained semantic loss does not mean zero full-input loss. J includes omission plus taxonomy loss; lower is better. Aligned errors count observation contributions, not instantaneous occupancy. Unknown is not zero. Full IN/OUT, per-class, per-region and per-taxonomy-node values with available Ns are in summary.json. Existing 10 m / 1 s occupancy queries remain separate.

## Source-class and regional omission (Fixed 20 m / 0.4 s, IN world)

| Input cohort | ON retained (%) | OFF retained (%) | ON omitted contributions | OFF omitted contributions |
|---|---:|---:|---:|---:|
| Adult Pedestrian | 56.891 (n=32) | 0.105 (n=32) | 8026.438 (n=32) | 18584.656 (n=32) |
| Child Pedestrian | 56.618 (n=32) | 0.094 (n=32) | 5925.031 (n=32) | 13665.875 (n=32) |
| Senior Pedestrian | 57.556 (n=32) | 0.088 (n=32) | 5863.469 (n=32) | 13755.406 (n=32) |
| Pedestrian With Stroller | 53.985 (n=32) | 0.119 (n=32) | 7393.969 (n=32) | 16004.281 (n=32) |
| Pedestrian With Mobility Aid | 56.126 (n=32) | 0.092 (n=32) | 7206.406 (n=32) | 16322.344 (n=32) |
| Adult Cyclist | 53.816 (n=32) | 0.000 (n=32) | 1291.656 (n=32) | 2789.781 (n=32) |
| Senior Cyclist | 59.453 (n=32) | 0.000 (n=32) | 1139.781 (n=32) | 2807.656 (n=32) |
| Adult E-Scooter Driver | 56.806 (n=32) | 0.000 (n=32) | 1077.750 (n=32) | 2487.531 (n=32) |
| entrance-vicinity | 14.498 (n=32) | 0.050 (n=32) | 966.469 (n=32) | 1131.812 (n=32) |
| west-footway-control | 51.588 (n=32) | 0.000 (n=32) | 2013.594 (n=32) | 4213.312 (n=32) |
| central-through-footway | 47.974 (n=32) | 0.323 (n=32) | 4624.875 (n=32) | 8826.875 (n=32) |
| east-footway-control | 44.294 (n=32) | 0.000 (n=32) | 4124.812 (n=32) | 7523.125 (n=32) |
| outside_policy_regions | NA (n=0) | NA (n=0) | NA (n=0) | NA (n=0) |

## Native runtime boundaries

| Method | Generalization | TEST native runs | Mean wall (s) | p95 wall (s) | Core processing (s) |
|---|---|---:|---:|---:|---:|
| Fixed 20 m / 0.4 s | ON | 64 | 1.892 | 2.019 | 0.531 |
| Fixed 20 m / 0.4 s | OFF | 64 | 1.905 | 2.024 | 0.536 |
| Regional static 20 m | ON | NA | NA | NA | NA |
| Regional static 20 m | OFF | NA | NA | NA | NA |
| Temporal First | ON | 64 | 33.829 | 36.109 | 32.397 |
| Temporal First | OFF | 64 | 44.379 | 48.155 | 42.859 |
| Spatial First | ON | 64 | 39.232 | 42.356 | 37.824 |
| Spatial First | OFF | 64 | 44.274 | 47.911 | 42.752 |
| Semantic First / immediate | ON | 64 | 34.279 | 36.758 | 32.846 |
| Semantic First / immediate | OFF | 64 | 44.138 | 47.993 | 42.661 |
| Semantic First → Temporal First / wait | ON | 64 | 38.153 | 41.644 | 36.759 |
| Semantic First → Temporal First / wait | OFF | 64 | 44.126 | 48.017 | 42.668 |
| Semantic First → Spatial First / wait | ON | 64 | 38.030 | 41.513 | 36.616 |
| Semantic First → Spatial First / wait | OFF | 64 | 44.025 | 47.453 | 42.556 |

Offline native subprocess wall diagnostics; core and logical delay have different boundaries. Historical ON and new OFF run at different times; regional composition native runtime unavailable; no per-step/live guarantee.

## Measured OFF adaptive transcript duplicates

Only release IDs are excluded from comparison; all remaining recipient content/order is preserved. Equality here is not a universal algorithm-equivalence claim.

| Left | Right | Compared streams | Equal streams | All 144 equal? |
|---|---|---:|---:|---|
| adaptive_temporal_first_exact_only | adaptive_spatial_first_exact_only | 144 | 99 | false |
| adaptive_temporal_first_exact_only | adaptive_semantic_first_exact_only | 144 | 144 | true |
| adaptive_temporal_first_exact_only | adaptive_semantic_wait_temporal_exact_only | 144 | 144 | true |
| adaptive_temporal_first_exact_only | adaptive_semantic_wait_spatial_exact_only | 144 | 99 | false |
| adaptive_spatial_first_exact_only | adaptive_semantic_first_exact_only | 144 | 99 | false |
| adaptive_spatial_first_exact_only | adaptive_semantic_wait_temporal_exact_only | 144 | 99 | false |
| adaptive_spatial_first_exact_only | adaptive_semantic_wait_spatial_exact_only | 144 | 144 | true |
| adaptive_semantic_first_exact_only | adaptive_semantic_wait_temporal_exact_only | 144 | 144 | true |
| adaptive_semantic_first_exact_only | adaptive_semantic_wait_spatial_exact_only | 144 | 99 | false |
| adaptive_semantic_wait_temporal_exact_only | adaptive_semantic_wait_spatial_exact_only | 144 | 99 | false |

## MIA: fixed models, CAL thresholds, 32 TEST pairs per method

| Method | Generalization | Full111 AUC | Scalar31 AUC | Full111 TPR [95% CI] | Full111 FPR [95% CI] | Status |
|---|---|---:|---:|---:|---:|---|
| Fixed 20 m / 0.4 s | ON | 0.605 | 0.579 | 0.125 [0.035, 0.290] | 0.094 [0.020, 0.250] | evaluated |
| Fixed 20 m / 0.4 s | OFF | 0.514 | 0.515 | 0.094 [0.020, 0.250] | 0.062 [0.008, 0.208] | evaluated |
| Regional static 20 m | ON | 0.565 | 0.581 | 0.406 [0.237, 0.594] | 0.375 [0.211, 0.563] | evaluated |
| Regional static 20 m | OFF | 0.500 | 0.500 | 0.000 [0.000, 0.109] | 0.000 [0.000, 0.109] | evaluated |
| Temporal First | ON | 0.579 | 0.591 | 0.406 [0.237, 0.594] | 0.312 [0.161, 0.500] | evaluated |
| Temporal First | OFF | 0.508 | 0.509 | 0.062 [0.008, 0.208] | 0.031 [0.001, 0.162] | evaluated |
| Spatial First | ON | 0.580 | 0.608 | 0.219 [0.093, 0.400] | 0.219 [0.093, 0.400] | evaluated |
| Spatial First | OFF | 0.500 | 0.500 | 0.000 [0.000, 0.109] | 0.000 [0.000, 0.109] | evaluated |
| Semantic First / immediate | ON | 0.578 | 0.591 | 0.406 [0.237, 0.594] | 0.312 [0.161, 0.500] | evaluated |
| Semantic First / immediate | OFF | 0.508 | 0.509 | 0.062 [0.008, 0.208] | 0.031 [0.001, 0.162] | evaluated |
| Semantic First → Temporal First / wait | ON | 0.586 | 0.597 | 0.469 [0.291, 0.653] | 0.375 [0.211, 0.563] | evaluated |
| Semantic First → Temporal First / wait | OFF | 0.508 | 0.509 | 0.062 [0.008, 0.208] | 0.031 [0.001, 0.162] | evaluated |
| Semantic First → Spatial First / wait | ON | 0.582 | 0.597 | 0.500 [0.319, 0.681] | 0.469 [0.291, 0.653] | evaluated |
| Semantic First → Spatial First / wait | OFF | 0.500 | 0.500 | 0.000 [0.000, 0.109] | 0.000 [0.000, 0.109] | evaluated |

### Paired AUC changes: OFF minus ON

| Pair | Representation | Difference | Paired 95% interval | Independent groups |
|---|---|---:|---|---:|
| Fixed 20 m / 0.4 s | semantic111 | -0.091 | [-0.148, -0.067] | 32 |
| Fixed 20 m / 0.4 s | scalar31 | -0.063 | [-0.122, -0.026] | 32 |
| Regional static 20 m | semantic111 | -0.065 | [-0.117, -0.035] | 32 |
| Regional static 20 m | scalar31 | -0.081 | [-0.137, -0.051] | 32 |
| Temporal First | semantic111 | -0.070 | [-0.128, -0.033] | 32 |
| Temporal First | scalar31 | -0.082 | [-0.163, -0.020] | 32 |
| Spatial First | semantic111 | -0.080 | [-0.147, -0.037] | 32 |
| Spatial First | scalar31 | -0.108 | [-0.176, -0.062] | 32 |
| Semantic First / immediate | semantic111 | -0.069 | [-0.130, -0.033] | 32 |
| Semantic First / immediate | scalar31 | -0.082 | [-0.168, -0.025] | 32 |
| Semantic First → Temporal First / wait | semantic111 | -0.078 | [-0.127, -0.060] | 32 |
| Semantic First → Temporal First / wait | scalar31 | -0.088 | [-0.165, -0.044] | 32 |
| Semantic First → Spatial First / wait | semantic111 | -0.082 | [-0.128, -0.068] | 32 |
| Semantic First → Spatial First / wait | scalar31 | -0.097 | [-0.157, -0.057] | 32 |

Lower AUC is favorable for this attack; a change may reflect omitted information. Every interval is exploratory and non-simultaneous. An interval crossing zero establishes neither superiority nor equivalence. The CAL 10% FPR cap is not a TEST guarantee. Full111/Scalar31 is not the ON/OFF action comparison.

## Interpretation scope

- Exploratory semantic-action ablation on already exposed recordings; the original primary study and strategy supplement remain unchanged.
- Same source observations, target/auxiliary pairs, taxonomy and hard regional policies. ON allows truthful taxonomy generalization; OFF permits input-leaf categories only. Whole failed candidates may be suppressed; selective contribution suppression remains OFF.
- Seven ON/OFF pairs are headline comparisons. Three additional OFF fixed-window methods are dependencies of regional composition, not extra headline strategies.
- Regional cohort attribution uses source-point membership; hard policies apply to the whole candidate footprint and may intersect several regions. Overlapping cohort summaries are not new independent populations.
- Exact-only zero semantic loss is conditional on surviving input. Always read retention, full-input J and per-source-class/region omission alongside it.
- J=(1-retained fraction)+retained fraction times retained taxonomy loss. It includes omission and semantic distortion, excludes spatial/temporal distortion, and is not a privacy metric.
- Aligned 20 m / 400 ms taxonomy queries count observation contributions. Ancestor/descendant workloads overlap and must not be summed as distinct traffic. Missing public support and semantic ambiguity remain unknown, not zero.
- Exact and estimated query answers are separate. Estimates allocate identifiable category counts uniformly in sampled space/time only; they never distribute coarse labels among semantic descendants or use private cohort frequencies.
- Each world uses its own sampled reference. Utility uses equal-recording TEST macro means with metric-specific available Ns; conditional error must be read with answered coverage.
- MIA protects inclusion of all observed contributions of one operational track within [0,300 s), not identity, a complete journey or every visit. TRAIN fits/scaling and CAL thresholds stay separate from TEST.
- Full111 versus Scalar31 is a joint representation ablation, not a semantic-action ablation or an isolated semantic-leakage measure.
- OFF-minus-ON AUC intervals use 1000 paired-source bootstrap replicates conditional on fixed fits/CAL; intervals are exploratory, non-simultaneous, and establish no equivalence margin.
- A duplicate recipient transcript is an observation under these inputs, not universal equivalence of the algorithms. Every declared strategy remains in the execution/model family.
- One final recipient snapshot at H=300 s; logical sealing delay and offline native/core times do not establish live delivery or per-step real-time guarantees. Movement quality remains separate from privacy.

## Provenance

Original diagnostic-repair history and immutable historical bindings are retained in summary.json and ablation-lineage-public.json. No source IDs, seeds, model parameters, features or individual scores are exported.
