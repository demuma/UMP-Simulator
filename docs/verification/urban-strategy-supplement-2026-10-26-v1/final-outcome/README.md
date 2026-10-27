# Strategy comparison: completed results

Completed 27 October 2026. All four additional strategy configurations have been evaluated on the same 72 recordings, with unchanged hard policies. The sequence was implementation validation, full utility/runtime execution and review, eight new TRAIN/CAL attack fits, a published model lock, then TEST MIA. The original primary study and its models remain unchanged.

This is a supplementary **exploratory** comparison. The existing TEST results had already informed strategy selection; these recordings are not a fresh confirmatory sample.

## What was compared

The five adaptive configurations are:

- **Semantic First / immediate policy release:** imported reference, Temporal First secondary. Release eligible output as soon as the hard policy passes.
- **Temporal First:** preserve temporal detail; attempt spatial rescue before temporal extension. Allowed semantic generalization can permit immediate release.
- **Spatial First:** preserve spatial detail; extend failed owners before terminal spatial rescue. Allowed semantic generalization can permit immediate release.
- **Semantic First → Temporal First / wait:** prefer zero semantic loss; try an exact-category spatial rescue before waiting.
- **Semantic First → Spatial First / wait:** prefer zero semantic loss at fine geometry; wait before terminal rescue/fallback.

“First” identifies the detail to preserve. These are bounded local preferences, not all six global lexicographic orders. Preference waiting does not relax a hard constraint: it seeks zero semantic loss before the local terminal, with policy-permitted fallback at that boundary. A boundary can occur before the nominal four-second limit. Immediate Semantic First with only its secondary switch changed is not a separate effective strategy and was excluded.

All ten imported baselines are included: fixed 10 m and 20 m grids with 0.4/1/2/4 s windows, plus regional static 10 m and 20 m compositions. The [full report](report.md) contains every method, IN/OUT world and attack representation. The frozen [protocol](../../../URBAN_STRATEGY_SUPPLEMENT_PROTOCOL_2026-10-26.md) records the exact execution rules, contrast seeds and declaration-time status.

## Results that can be presented

TEST IN-world means give each of the 32 recordings equal weight. Detail and delay concern retained contributions; AUC is for the fixed Full111 attacker and smaller is favorable to privacy. AUC point estimates alone do not establish a ranking.

| Method | Retained input | J | Retained semantic loss | Mean cell side | Mean logical delay | Full111 AUC |
|---|---:|---:|---:|---:|---:|---:|
| Regional static 20 m | 60.60% | 77.25% | 62.54% | 20.00 m | 1.839 s | 0.565 |
| Semantic First / immediate | 68.53% | 73.80% | 61.80% | 17.94 m | 0.348 s | 0.578 |
| Temporal First | 68.53% | 73.81% | 61.80% | 17.93 m | 0.348 s | 0.579 |
| Spatial First | 66.30% | 73.31% | 59.76% | 17.32 m | 1.788 s | 0.580 |
| Semantic First → Temporal First / wait | 70.21% | 72.82% | 61.34% | 17.81 m | 1.804 s | 0.586 |
| Semantic First → Spatial First / wait | 70.33% | 72.78% | 61.35% | 17.84 m | 1.806 s | 0.582 |

**Constraint compliance:** all 576 new native method/world cases and all 72 groups verify, with zero audited publication-policy violations. The complete family contains 1872 native executions and 288 regional compositions, including unchanged imports. Compliance is distinct from privacy effectiveness.

**Utility trade-offs:** waiting with Spatial secondary retains 9.73 percentage points more input than regional static 20 m, with finer retained cells and similar delay. Relative to immediate Semantic First, it gains only 1.81 retention points and about 0.45 semantic-loss points while adding 1.46 s of logical delay. Spatial First preserves more retained spatial/semantic detail but loses more input. Temporal First is almost identical to the existing immediate reference on these recordings. No strategy dominates every metric.

**MIA outcome:** all 30 method/representation attacks are evaluated; controls pass. Every interval for the eight added paired AUC contrasts in both representations includes zero. Neither an additional privacy benefit, a privacy winner, nor equivalence is established. For example, waiting with Temporal secondary minus regional static 20 m has Full111 AUC difference +0.02148, paired 95% interval [-0.02249,+0.07229]. More retention is not itself a privacy gain. The original primary result is preserved exactly.

The empirical CAL FPR target of 10% is not a TEST guarantee: the new Full111 TEST FPRs are 31.25% (Temporal First), 21.88% (Spatial First), 37.50% (semantic wait/Temporal) and 46.88% (semantic wait/Spatial), each based on 32 negatives with broad exact intervals. Scalar31 jointly removes semantic and availability coordinates; it does not isolate semantic leakage.

## Application and runtime limits

J combines omitted observations and retained taxonomy loss; it does not measure spatial or temporal loss. Main utility means have N=32. Exact occupancy MAE exists for only 14 IN / 13 OUT recordings for immediate Semantic First and Temporal First; unavailable answers are not zero. Regional static 20 m and waiting/Spatial have estimated coverage 13.91% and 13.85%, with conditional MAE 1.351 and 1.285 on different answered subsets. This is not a claim of universal query superiority.

Mean new adaptive core processing is 32.40–37.82 s per 300-s recording. Native subprocess means are 33.83–39.23 s; regional composition native runtime is unavailable. These are offline replay measurements, not per-step deadlines or live-delivery guarantees. Old and new executions took place at different times. Logical seal delay is a separate simulated-time measure.

The protected secret is inclusion of all observed contributions of one operational track within [0,300 s), not identity, physical presence, a complete journey or all visits. The recipient sees one retrospective snapshot at H=300 s. One TRAIN and one TEST source have reported stalls/active tracks at the horizon; quality is reported separately and does not filter enrollment.

## Suggested presentation claim

> Under identical regional hard constraints, adaptive execution provides measurable choices between retained information, spatial/semantic detail and delay. The tested adaptive operating points retain more input than the regional 20 m baseline. The exploratory membership study quantifies residual risk but does not establish an additional privacy benefit from waiting or distinguish the adaptive strategies statistically.

Use the utility figure to show these operating points, then the attack and paired-difference figures to separate measured risk from unsupported privacy claims. Broader policy optimization, a second attack and a live real-time benchmark require separate follow-up designs.

## Figures and evidence

- [Utility and logical delay](urban-strategy-supplement-utility.png), [SVG](urban-strategy-supplement-utility.svg)
- [Retained cell size and offline runtime](urban-strategy-supplement-detail-runtime.png), [SVG](urban-strategy-supplement-detail-runtime.svg)
- [MIA AUC and exact TPR/FPR intervals](urban-strategy-supplement-attack.png), [SVG](urban-strategy-supplement-attack.svg)
- [Exploratory paired AUC differences](urban-strategy-supplement-contrasts.png), [SVG](urban-strategy-supplement-contrasts.svg)
- [Complete aggregate tables](report.md) and [machine-readable summary](summary.json)
- [English implementation/execution test report](../../../URBAN_STRATEGY_SUPPLEMENT_TEST_REPORT_2026-10-27.md)
- [Pre-execution freeze](../pre-execution-freeze/) and [published pre-TEST model lock](../model-lock/), commit `91c257a`

The original diagnostic-repair lineage accompanies the figures in [repair-lineage-public.json](repair-lineage-public.json). The original [primary outcome](../../urban-track-window-2026-10-26-v1/final-outcome/README.md) remains separate. Raw movements, identities, feature rows, fitted parameters and individual attack scores remain local and are excluded from Git.
