# Why the 5 m Spatial First and Semantic First streams coincide

Read-only independent audit, 2026-10-21. Inputs: archived cap-5-m replay results and frozen raw captures for 200, 500 and 1,000 Road Users in the 80 m × 80 m area. No mechanism or source changes, no C++ reruns. `results/window-duration-2026-10-21/verification/diagnose_one_second.py` and its complete `one-second-diagnosis.json` document the checks.

## Exact equality, not merely equal summary values

For all three populations, the entire `releases` arrays of Spatial First and Semantic First compare exactly equal: interval boundaries, release IDs, seal times, selected cell geometry, observation counts, distinct counts and semantic category bins. Private window diagnostics also compare exactly after excluding only `strategy`, `temporal_decisions` and `semantic_priority`. There are 20 nonoverlapping 1,000-ms windows in each run.

The controllers remain different. Semantic First first looks for a complete zero-loss cut, extends the window when that cannot be obtained, and at the terminal boundary tests semantic generalization levels. Its retention-first partial fallback then selects the same hard-feasible cut as Spatial First here. Every Semantic First window reports terminal fallback after three attempted ceilings (0, 0.5, 1). Nonempty selected cuts here require a ceiling of 1; an empty cut can retain metadata with selected ceiling 0 and actual maximum loss null. The metadata does not imply that every window selected ceiling 1.

## Necessary support obstruction

At every scheduled early endpoint, 400, 500, …, 900 ms after each of the 20 starts (120 candidates per population), at least one occupied 5 m cell contains fewer than five distinct Road Users. Therefore a complete allowed cut is impossible even if every type can be generalized to `road_user`. In particular, a complete zero-loss cut cannot exist.

At the final 1-second endpoints, every suppressed diagnostic cell is exactly 5 m wide, has reason `requirements_failed_at_depth_cap`, and fails only `min_category_distinct_contributors`. The numbers of these suppressed cell/window footprints are 2,906 / 3,713 / 2,774 for 200 / 500 / 1,000 initial Road Users. No other hard constraint is failing in these footprints.

For every individual window, released observations equal exactly the source observations lying in 5 m cells with at least five pooled distinct identities. This independently establishes the limiting mechanism for this particular configuration.

| Initial Road Users | Released observations / input | Retained | Published cells with maximum semantic loss 0 / 0.5 / 1 |
|---:|---:|---:|---:|
| 200 | 1,927 / 38,930 | 4.95% | 0 / 0 / 39 |
| 500 | 28,065 / 99,140 | 28.31% | 1 / 46 / 493 |
| 1,000 | 130,062 / 198,638 | 65.48% | 5 / 100 / 2,110 |

## What the seven types change

The policy requires at least five distinct Road Users per **published semantic category**, not five Road Users of each of the seven raw types in every cell. Because `semantic_max_loss.max=1`, the taxonomy permits pooling all types into `road_user`. Consequently, seven raw types are not the reason these observations are ultimately suppressed under the current constraints. Total distinct support below five already prevents release.

The types strongly affect the semantic accuracy retained: 26,045 of the 28,065 released observations in the 500-user stream are labeled only `road_user`; 1,985 retain `pedestrian` and 35 retain the exact `adult_pedestrian` class. If a future policy forbids `road_user` pooling (for example maximum loss 0.5 or 0), class-specific support becomes an additional feasibility bottleneck.

The area contains 256 cells of 5 m × 5 m. The initial area-average population per cell is only 0.78 / 1.95 / 3.91 respectively. These are descriptive means, not uniform guaranteed occupancy or support counts over windows.

## What a 4-second limit may change

An independent raw-data calculation over nonoverlapping intervals [0,4000), [4000,8000), …, [16000,20000) gives the fraction of observations inside 5 m cells whose **pooled distinct** support reaches five:

| Initial Road Users | 1-second pooled-support eligible observations | 4-second pooled-support eligible observations |
|---:|---:|---:|
| 200 | 4.95% | 10.90% |
| 500 | 28.31% | 49.26% |
| 1,000 | 65.48% | 81.66% |

These 4-second figures are source-data feasibility diagnostics, **not measured 4-second mechanism outputs** or deadline utility results. Different controller window boundaries could change the result. Independent actual replay runs are required.

More samples of the same identity do not increase distinct support. In the first [0,4000) interval of the 500-user stream, several cells have 39 observations of one Road User; another cell has 146 observations but only four distinct Road Users. Neither can satisfy five distinct identities. Longer windows help through additional different Road Users entering the cell, not by repeatedly counting one Road User.

A 4-second experiment must consistently update the Policy Tree duration and evaluation-age limits, temporal adaptation maximum, history retention/capacity, and sufficient temporal evaluation budget (base 400 ms and 100-ms extensions require 37 endpoint evaluations to reach 4,000 ms). Existing query deadlines need explicit treatment; a 4-second output cannot be presented as satisfying a 1-second deadline. Keep the original 1-second policy and outputs unchanged for paired comparison.

## Subsequent actual 4-second replay evidence

The completed mechanism runs are documented in `docs/FOUR_SECOND_WINDOW_RESULTS_2026-10-21.md`. Their cap-5-m retention values are 10.90%, 49.26% and 81.66% for the three populations; Spatial First and Semantic First still coincide. The independent calculation above remains identified as a raw-source feasibility prediction, preserving its separation from the later measured replay outputs.
