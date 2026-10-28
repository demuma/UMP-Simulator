# Semantic-generalization ablation: completed results

Completed 28 October 2026. All seven predeclared procedures are evaluated with semantic generalization ON and OFF, under the same observations and hard local400 policies. Utility precedes fourteen new TRAIN/CAL fits; the model lock was published before TEST scoring. No source, target, policy, old model or original primary result was replaced.

## Result for the 32 TEST IN recordings

| Procedure | Retained ON (%) | Retained OFF (%) | Full111 AUC ON | Full111 AUC OFF |
|---|---:|---:|---:|---:|
| Fixed 20 m / 0.4 s | 56.16 | 0.092 | 0.605 | 0.514 |
| Regional static 20 m | 60.60 | 0.157 | 0.565 | 0.500 |
| Temporal First | 68.53 | 0.157 | 0.579 | 0.508 |
| Spatial First | 66.30 | 0.153 | 0.580 | 0.500 |
| Semantic First / immediate | 68.53 | 0.157 | 0.578 | 0.508 |
| Semantic First → Temporal First / wait | 70.21 | 0.157 | 0.586 | 0.508 |
| Semantic First → Spatial First / wait | 70.33 | 0.153 | 0.582 | 0.500 |

Allowing truthful semantic coarsening retains 56.16–70.33% of observation contributions, versus 0.09–0.16% when original terminal labels must be kept. Full-input J is 72.78–78.67% ON and 99.84–99.91% OFF. OFF survivors have zero taxonomy distortion, but near-total omission dominates full-input loss. These are equal-recording macro means; conditional metrics retain their actual available Ns.

OFF Full111 AUC is 0.500–0.514, compared with 0.565–0.605 ON. Scalar31 gives 0.500–0.515 OFF and 0.579–0.608 ON. Every one of the fourteen predeclared paired OFF-minus-ON 95% intervals lies below zero. For immediate Semantic First, the Full111 difference is −0.06934, interval [−0.12991,−0.03271]. The original ON adaptive-versus-regional primary result remains unchanged: difference +0.01270, interval [−0.04397,+0.07227].

The lower measured membership discrimination with OFF accompanies omission of more than 99.8% of input. It is not a utility-preserving privacy improvement or a guarantee against other attackers. Six OFF models have constant balanced TRAIN optima; chance AUC for those classifiers is not information-theoretic indistinguishability. The frozen L2 logistic attack, known quarter-track exact position/time auxiliary information and observed-track 300-s protected unit define the scope.

All contrasts are exploratory reuse of already exposed TEST recordings, conditional on fixed TRAIN models/CAL thresholds. Intervals are marginal, not simultaneous, and no equivalence/noninferiority margin is tested. CAL empirical FPR target 0.1 is not a TEST guarantee: report the actual TEST TPR/FPR and their intervals from the full table. Full111 versus Scalar31 removes semantic and availability coordinates jointly; the ON/OFF mechanism comparison is made within each representation.

## What this supports

Truthful type coarsening is an important release actuator under this policy, class composition and motion regime. Spatial or temporal changes alone usually cannot meet support requirements while keeping every occupied original category exact. The earlier adaptive ON utility benefit remains, while an additional MIA benefit over regional-static ON or privacy equivalence is still not established by the unchanged primary interval. There is no universal claim that an adaptive procedure dominates every fixed workload.

Exact category-query coverage remains low and task dependent: 0.003–0.010% OFF versus 0.583–5.344% ON for the 20 m/400 ms taxonomy-node workload. Zero error on the few answered exact queries is read jointly with coverage; missing public support and semantic ambiguity stay unknown. Estimates are separate and allocate identifiable counts only in space/time. Counts mean observation contributions, not distinct people or instantaneous flow.

## Verification and retained diagnostic correction

All 1,296 new native cases and 144 regional compositions verify. Independent utility reconstruction checks 2,016 headline + 432 auxiliary rows through 1,129,452 comparisons. Independent model-lock audit verifies 1,120 TRAIN/CAL rows and 2,254 checks without reading TEST. Final independent scoring verifies 28 models, 896 TEST rows, 1,792 attack and 256 control scores, 64 exact binomial rate intervals and all 14 paired AUC intervals through 4,920 checks. Controls pass; old ON/control/primary outcomes are exact. Root visually checked all four actual PNGs. Counts of checks do not increase the 32 independent TEST sources.

The original maximum-delay diagnostic includes zero-weight scheduled timestamps in 28/2,448 streams. Means, p50, p95 and p99 are unchanged. The [retained-observation maximum correction](retained-delay-maximum-correction.json), published at the utility gate, is authoritative for that tail statistic; summary.json deliberately keeps the immutable legacy field. No scientific output, predictor, model or hard-policy limit changes.

The temporary Python environment lost files after native execution; its exact eighteen original package versions and 3,048 cached payloads were restored offline. All 140 surviving original payloads match. The old environment and import failure remain preserved; all 530 Python regressions pass again. No native case was rerun. Full capture hashes and unchanged GT/sensor reconstruction authenticate all 72 sources; all old/new archives are verified. This is not a new physical/source audit execution.

## Results and reproducibility

- [Complete by-method utility/MIA/rate/paired-interval tables](report.md)
- [Aggregate summary; fitted numeric thresholds omitted](summary.json)
- [Utility](urban-semantic-ablation-utility.png) · [category queries](urban-semantic-ablation-queries.png) · [MIA AUC](urban-semantic-ablation-attack.png) · [paired contrasts](urban-semantic-ablation-contrasts.png)
- [Completed gates and immutable hashes](completed-gates-public.json)
- [Maximum-delay correction](retained-delay-maximum-correction.json)
- [Pre-TEST public model lock](../model-lock/README.md)
- [Detailed implementation/test report](../../../URBAN_SEMANTIC_ABLATION_TEST_REPORT_2026-10-27.md)
- [Declared contract](../../../URBAN_SEMANTIC_ABLATION_PROTOCOL_2026-10-27.md)

Public summary publication omits 96 duplicate fitted classifier-threshold values to keep the declared model parameters local. All aggregate statistics, rates, confidence intervals and figure bytes are unchanged; [projection evidence](publication-projection.json) binds the original export and the published view. The original export manifest is retained as source-export-receipt.json. Raw movements, features, fitted parameters and individual scores stay local.
