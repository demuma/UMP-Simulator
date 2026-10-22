# Maximum output-cell size: predeclared paired replay protocol

Date: 2026-10-21. Freeze this protocol before executing the new 10 m and 5 m
comparisons. The [original moving-pilot protocol](MOVING_REPLAY_PROTOCOL_2026-10-21.md)
and its completed 40 m results remain unchanged.

## Question and input

How does restricting the largest permitted output cell to 10 m or 5 m affect
policy-feasible release, retained information and the declared occupancy task?
These are **maximum cell-side limits**, not smaller simulation areas or changes
to the finest sensor resolution. No improvement is presumed: stricter limits can
prevent useful spatial merges and increase suppression.

Reuse the three verified, frozen captures from the original moving pilot:
200, 500 and 1000 initial Road Users, 20 simulated seconds, 80 m x 80 m, seven
existing behavior profiles, 50 ms numerical step and 100 ms sensor cadence.
The finest depth remains 6, with 4096 possible 1.25 m cells. Preserve each source
byte-for-byte and record its hash; generate no new movements. Independent
captures at different population levels remain distinct stochastic realizations.
Population decline, existing motion noise and the absence of replenishment are
unchanged. This is a paired mechanism pilot, not a replicated efficacy study.

## Methods and changed limits

For each population, execute nine methods under each cap:

| Maximum side | Fixed uniform-grid sides | Fixed windows | Adaptive methods |
|---|---|---|---|
| 10 m | 2.5, 5, 10 m (depths 5, 4, 3) | 400 and 1000 ms | Temporal First, Spatial First, Semantic First |
| 5 m | 1.25, 2.5, 5 m (depths 6, 5, 4) | 400 and 1000 ms | Temporal First, Spatial First, Semantic First |

This produces 54 new outputs. The former 40 m matrix remains the contextual
reference; its six fixed settings differ. Compare adaptive methods across caps
and overlapping fixed settings where available. Do not describe the full
different baseline portfolios as matched individual methods.

The hard Policy Tree bound `cell_side_m.max` becomes 10 or 5. Adaptive search
`spatial_selection.min_depth` becomes 3 or 4, respectively. Both must agree with
the 80 m source geometry. All other declared requirements remain unchanged:
category-specific distinct support at least 5, maximum semantic loss 1, minimum
cell side 1.25 m, maximum window/interval-start age 1000 ms, base window 400 ms,
100 ms extension steps, common-window coordination and the same seven-profile
release taxonomy. Fixed baselines permit the same semantic generalization.
No regional overrides, seed changes, new privacy attack or parameter tuning.

Keep the original bounded history and resource budgets: 2000 ms retention,
32 bins, 100000 observations, 16 MB identity strings, 128 bucket descriptors,
8192 spatial evaluations per proposal and existing serialized-artifact limits.
Resource exhaustion is an execution failure, not policy infeasibility.

## Verification and outcomes

Independently verify source accounting, identity unions, cell geometry, temporal
intervals, nonoverlap, semantic antichains and all hard bounds. Explicitly check
that no released cell exceeds its cap. Re-run one adaptive method per population
and cap; require identical output except runtime. Archive protocol, source,
configuration, binary, commands and artifact hashes. Validate each viewer bundle.

Retain the original task: mean sampled occupancy on fixed **10 m squares and
1000 ms intervals**, with the same declared reconstruction assumptions, logical
deadlines and interior/EOF cohorts. Do not shrink the query cells alongside the
policy cap. Report coverage and conditional MAE together, plus retained source
contributions, suppression, weighted spatial/semantic detail and logical age.
Missing coverage stays unknown. With no published contributions, conditional
detail/error summaries are unavailable, not zero; release soundness alone is
not useful output.

Changes compare feasible representations under different policies, not equal
privacy guarantees or measured privacy gain. Retain unfavorable and all-suppressed
cases. Do not select a preferred cap from this single realization as a universal
recommendation. Add results to the talk only after verification, with the changed
constraint and conditional scope stated.
