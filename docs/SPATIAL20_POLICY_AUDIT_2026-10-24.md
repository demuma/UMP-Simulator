# Spatial portfolio policy and suppression audit — 24 October 2026

## Findings

Selective category/contribution suppression was **off in all 32 executed cases** of the two completed `v2-portfolio` studies. Every exact case configuration has `semantic_suppression_fraction: {max: 0}` at the root, and its SHA-256 matches the verified case summary. Both native mapped-source configurations omit this optional feature, which also means off. This differs from the earlier six-case suppression study, which explicitly tested both 0 and 0.1.

The fixed baselines enforce the same hard root and regional metric bounds as the adaptive methods within each contract. They also use semantic taxonomy generalization and suppress policy-invalid whole cells. They are therefore policy-aware fixed spatial/temporal baselines, rather than raw GBS without anonymization. No fixed-specific hard-constraint bypass was found in the reviewed code, exact configurations, completed independent audit summaries, or the eleven fresh analytical checks below.

The fixed controller does not implement adaptive search order: its prescribed grid and window replace the adaptive controller. “Same policy” here means the same hard metric bounds, taxonomy, and region geometry, with execution method deliberately varied. It does not mean a fixed method reproduces adaptive `Semantic First` or `Spatial First` decision sequences.

## Exact executed contracts

Reviewed directories:

- `results/expanded-access-mixed-2026-10-24-v2-portfolio/`
- `results/expanded-access-pedestrians-2026-10-24-v2-portfolio/`
- Their original source configurations under `results/expanded-access-{mixed,pedestrians}-2026-10-24-v1/scene/config.yaml`.

Each portfolio contains eight methods under Original and the same eight methods under Spatial20: two adaptive strategies plus fixed 5/10/20 m crossed with 400/1000 ms. For each source and each contract, all eight configurations have identical numeric root requirements, every regional requirement, and the semantic taxonomy. Method/application/policy identifiers and execution strategy are intentionally distinct. All 32 summaries report independently verified scalar/semantic policy checks and zero published-policy violations. This audit checked the exact configuration hashes and those existing independent audit records; it did not rerun the complete scientific portfolio or reparse every large result.

| Requirement | Original | Spatial20 |
| --- | --- | --- |
| Root distinct observed IDs | At least 5 | At least 5 |
| Minimum support per released semantic category | At least 5 | At least 5 |
| Root output side | 1.25–10 m | 1.25–20 m |
| Root window duration | 400–4000 ms | 400–4000 ms |
| Root age at evaluation | At most 4000 ms | At most 4000 ms |
| Root semantic maximum loss | At most 1 | At most 1 |
| Selective suppression fraction | At most 0, disabled | At most 0, disabled |
| Entrance-vicinity distinct IDs | At least 10 | At least 10 |
| West/east footway side | At most 5 m | At most 20 m |
| West/east footway window and age | At most 1000 ms each | At most 1000 ms each |
| West/east/central footway semantic loss | At most 0.5 | At most 0.5 |

Spatial20 explicitly relaxes the root maximum from 10 to 20 m **and the west/east regional maxima from 5 to 20 m**. All methods receive the same relaxation. The corresponding protocol documents it before execution. It is a changed spatial utility contract, not evidence that a 20 m fixed grid satisfies Original or that a privacy benefit has been measured. Original fixed 20 m correctly releases no observations at either tested interval, for both sources.

The candidate-search minimum depth is separately set to permit 20 m candidates for every method. Search permission does not override the hard output-size metric. The fixed 400/1000 ms CLI windows replace the baseline's execution interval but do not replace policy `window_duration_ms` bounds.

Policy coverage is conservative over the whole cell footprint. Every region with positive-area intersection contributes bounds; stricter inherited minima/maxima govern a coarse cell even if its currently observed road users lie outside the intersected subregion. This differs from clipping a cell's observations to only the regional part.

## Enforcement path

Relevant maintained source locations:

- [`run_comparison.py`](../tools/mapped_scene/run_comparison.py): `relaxed_spatial20` applies the declared spatial changes; `settings_for` explicitly writes suppression cap 0 for the controlled portfolio. Consequently, changing only the source config to cap 0.1 would **not** enable suppression in this portfolio; its protocol/controller construction would still override it to 0.
- [`AggregationReplay.cpp`](../simulator/tools/AggregationReplay.cpp), `fixedSelection` around line 295: reconstructs fixed-depth support from the same history, calls the shared metric evaluator, and selects a cell only when observation coverage is complete and the assessment is `Pass`.
- [`CandidateMetrics.cpp`](../simulator/src/CandidateMetrics.cpp), around lines 210–297: resolves the effective regional policy per cell, evaluates every configured requirement, and treats absent metrics as `Unavailable`, which cannot be published as passing. Semantic taxonomy selection and optional selective suppression are inside this common evaluator, not restricted to adaptive modes.
- [`CandidateMetrics.cpp`](../simulator/src/CandidateMetrics.cpp), around lines 297–361: optional suppression runs only when the effective cap is positive. It recomputes retained counts, semantic support, occupancy and all hard checks, then requires an improvement in the full-input distortion objective. Removed observations cannot continue to satisfy a support floor.
- [`PolicyTree.cpp`](../simulator/src/PolicyTree.cpp), `intersect`, `compile`, and `resolve`: takes the maximum of lower bounds and minimum of upper bounds across all intersecting regions. A child cannot override root suppression cap 0 with a larger cap. If only a region mentions suppression, the implementation inserts a root prohibition unless the root explicitly grants permission.
- [`PublicationCoordinator.cpp`](../simulator/src/PublicationCoordinator.cpp), around lines 103–151: independently re-evaluates the candidate at sealing, rejects selected invalid cells, copies only approved retained counts/semantics, and rechecks requirements at delivery. It does not trust a caller's recorded “pass” flags.
- [`PolicyConfiguration.cpp`](../simulator/src/PolicyConfiguration.cpp) and the metric registry in `CandidateMetrics.cpp`: reject unknown metrics or malformed bounds during configuration parsing. A recognized metric can still be unavailable online; that blocks release instead of being ignored.

Age and delay checks use the supplied simulation/evaluation clock: `age_at_evaluation_ms = now - start` and `post_window_delay_ms = now - end`. They are not measurements of wall-clock CPU backlog or external network delay. Offline policy compliance therefore does not establish real-time deadline compliance. Existing publication regression coverage also checks that a delayed delivery expires rather than reopening a held reservation.

`occupancy_mae` is recognized but deliberately unavailable to the online evaluator without its offline reference. It was not a hard requirement of these 32 case policies. Configuring it as a required bound would block release; the present algorithm does not actively optimize an online MAE metric.

## Earlier suppression-on/off experiment

The independent six-case study is `results/semantic-suppression-2026-10-24-60s-v2/`. It has 90,619 identical source observation contributions and separately audited filtering-aware accounting:

| Method | Cap | Retained observations | Selectively removed observations |
| --- | ---: | ---: | ---: |
| Semantic First | 0 | 59,597 | 0 |
| Semantic First | 0.1 | 60,147 | 50 |
| Spatial First | 0 | 49,853 | 0 |
| Spatial First | 0.1 | 50,218 | 53 |
| Fixed 10 m / 1 s | 0 | 50,204 | 0 |
| Fixed 10 m / 1 s | 0.1 | 50,950 | 65 |

Thus selective suppression is implemented for fixed methods too. It was intentionally excluded from the new spatial portfolio, not silently absent from the native mechanism. The dedicated `tools/evaluation/run_suppression_study.py` and its suppression-aware audit/report remain the maintained path for paired on/off studies. A new source study must record filtering as a changed product contract: retained counts are not exact full-input traffic totals. The ordinary native mapped capture exporter currently rejects positive selective-suppression caps rather than granting its complete-source-footprint proof to filtered counts.

“Suppression off” here means selective type/contribution filtering is off. Whole-cell suppression of invalid fixed or adaptive outputs remains active, and semantic generalization remains active.

## Eleven fresh native analytical checks

The audit executed the already frozen verified `AggregationReplay` binary; it did not build or change native code. All generated fixture inputs/results were under a temporary directory and were removed after checking. The fixture used a 2 s horizon, 100 ms samples, 50 ms progress, fixed 10 m cells and 1 s windows. Twenty distinct Adult Pedestrians and one distinct Adult Cyclist occupy the same cell at each of 19 samples: 399 original observations in total. The taxonomy and basic policy were taken from the maintained suppression-study configuration, with explicit small test regions where needed.

| Analytical case | Observed result | Expected condition |
| --- | --- | --- |
| Cap 0 | 399 retained, semantic mean loss 1 | Ordinary full-data generalization, no selective removal |
| Cap 0.1 | 380 retained, 19 removed, semantic loss 0 | Rare-class removal allowed and reassessed |
| Root cap 0.1, intersecting region cap 0 | 399 retained, no removal, loss 1 | Regional prohibition wins |
| Region side maximum 5 m | No publication; `cell_side_m:fail` | Fixed 10 m cannot bypass regional size |
| Region window maximum 400 ms | No publication; `window_duration_ms:fail` | Fixed 1 s cannot bypass regional time |
| Region age maximum 400 ms | No publication; `age_at_evaluation_ms:fail` | Fixed 1 s cannot bypass regional age |
| Region total support minimum 22 | No publication; `distinct_contributors:fail` | Twenty-one distinct IDs are insufficient |
| Semantic maximum loss 0, cap 0 | No publication; `semantic_max_loss:fail` | Disallowed generalization is rejected |
| Semantic maximum loss 0, cap 0.1 | 380 retained, 19 removed, loss 0 | Approved filtering can meet the semantic bound |
| Required `occupancy_mae.max = 1` | No publication; `occupancy_mae:unavailable` | Missing reference metric is not silently passed |
| Unknown metric name | Configuration rejected; no result created | Unsupported metric cannot be ignored |

All eleven assertions passed. These are deterministic contract checks, not new urban simulations, performance repetitions, or empirical privacy experiments. The temporary read-only audit script and compact receipt remain locally at `/private/tmp/ump-spatial20-policy-audit.py` and `/private/tmp/ump-spatial20-policy-audit-result.json`; they are not generated motion committed to Git. Existing maintained tests additionally cover strict overlapping suppression caps, repeated tracks not manufacturing support, retained-total checks, full-window retirement and publication retry expiry.

## Evidence identities and limits

```text
Mixed v2 verified summary SHA-256:
429f41572f4a377662c9698141f00a8aa928ad129c95e4779a76335ca4f2d3e0
Pedestrian-only v2 verified summary SHA-256:
86c2c3c83838783c7b32d57697a1f9ad63d5b809971ac9f5f2d47aa8381a5f1e
Historical six-case suppression summary SHA-256:
c5d61bc1ff7c63570e2c15541a524668bc90b55fe831da52b759ca940400e6a6
Frozen native replay binary SHA-256:
fa82c62bfd589f764671545579ab1ae5c1739722bd67a33e7d18d53d7dfa03b9
Fresh eleven-case audit receipt SHA-256:
70ecce69c4e8a70051e37a68c0333b7d7b15394335ef91190238a62490a315b9
```

The findings concern the currently supported hard metrics and these exact contracts. Track/category support is an operational disclosure condition, not a general proof of k-anonymity for arbitrary quasi-identifiers, person-level identity protection, or resistance to trajectory/membership attacks. Empty output is vacuous compliance and must remain reported alongside coverage. No perfect-privacy or universal-baseline-superiority claim follows from this audit.
