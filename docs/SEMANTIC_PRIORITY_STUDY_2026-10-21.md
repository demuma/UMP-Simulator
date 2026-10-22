# Semantic candidate choice: bounded mechanism study

Date: 2026-10-21. Status: completed first E07/A08 decision-order review.
[Predeclared protocol](SEMANTIC_PRIORITY_PROTOCOL_2026-10-21.md),
[test report](SEMANTIC_PRIORITY_TEST_REPORT_2026-10-21.md).

## Main finding

The current selection with early semantic generalization satisfies the declared constraints in all tested
outputs. It can preserve fine spatial occupancy while making some class queries unknown.
A coarser legal output can preserve those class queries instead. Neither representation
is universally better without application requirements. This study does not change the
production controller or introduce a weighted utility objective.

Across 360 configurations, every actual cut belongs to an independently enumerated legal
same-interval candidate set. None of the 1,929 actual decisions is dominated on all six
declared criteria simultaneously. This is a bounded statement about the tested fixed
intervals, not proof of global optimality, a general privacy improvement or superiority
over other online schedules. Fine spatial detail can keep a choice nondominated even
when another application would strongly prefer a different class representation.

## What the current support means

Two separate online statistics exist:

- `distinct_contributors`: exact different road users in the whole cell/window.
- `min_category_distinct_contributors`: the minimum exact distinct support across the
  nonempty published categories in that cell/window.

The measured values change with observations. Their required minima are configured and
immutable during one run, with stricter regional values inherited through the Policy Tree.
The category minimum currently applies uniformly to the categories of one candidate;
independent per-category minima are not implemented. Five is an example, not a hardcoded
constant. A longer window counts the union of identities, not repeated observations or
necessarily simultaneous road users.

Classical k-anonymity specifies equivalence classes of released records under a declared
quasi-identifier projection. See [Sweeney's original model](https://dataprivacylab.org/dataprivacy/projects/kanonymity/).
The current aggregate stream has no completed person/record/trajectory equivalence-class
contract. Its support is therefore reported as an operational minimum-group condition.
A limited deduplicated person-membership interpretation might establish a group-size
condition for one release once every public QI and the protected unit are fixed; that
would require its own explicit model/proof. It would not automatically establish
trajectory-level anonymity. No sensitive attribute or l-diversity is introduced here.

## Controlled inputs and constraints

Five deterministic streams use an 80 m square at depth 2, one occupied 40 m quadrant,
four occupied 20 m leaves, 100-ms sampling and 2,400-ms horizon. Depth 2 deliberately
bounds enumeration; production depth 6 is unchanged. These are mechanism witnesses,
not road-network trajectories or independent samples from a real mobility population.

| Scenario | Source contributions | Different road users over the run | Controlled mechanism feature |
|---|---:|---:|---|
| Dense exact | 1,380 | 60 | Every terminal class has support 5 per leaf |
| Rare local type | 805 | 35 | One local cyclist becomes sufficiently supported after spatial merging |
| Temporal turnover | 1,840 | 168 | New cyclists enter each sample; existing pedestrians recur |
| Infeasible support | 92 | 4 | Repetition cannot create the fifth road user |
| Regional detail | 805 | 35 | Same rare-local observations; leaf 48 additionally forbids semantic loss |

Each source is reused unchanged across category minima 2/4/5, semantic-loss maxima
0/0.5/1, maximum cell sides 20/40 m, duration/age maxima 400/800 ms and common Temporal
First/Spatial First. Base windows are 400 ms with 100-ms extensions; A07 is enabled.
The product contains 360 executions, plus 12 deterministic repeats. It has no random
replicates, sampling confidence intervals or new attack fits.

| Scenario | Observed run retention range | Actual intervals with no nonempty legal reference output |
|---|---:|---:|
| Dense exact | 100% | 0 |
| Rare local type | 42.86–100% | 0 |
| Temporal turnover | 0–100% | 36 |
| Infeasible support | 0–100% | 216 |
| Regional detail | 42.86–100% | 0 |

The 252 infeasible intervals are conditional on actual chosen endpoints. They are not
252 globally impossible future schedules. Other intervals can have a nonempty valid
subset while the entire source cannot be retained. All suppression remains explicit loss.

## Same-interval trade-off witness

Use rare-local input, category minimum 5, allowed loss 1, maximum side 40 m and the actual
first interval [0,400) ms. The source has 35 different road users and 105 observations.
Leaf 48 contains 19 pedestrians and one adult cyclist, leaf 49 five other adult cyclists,
and leaves 50/51 five pedestrians each.

| Legal output for the identical interval | Current fine cut | Alternative parent |
|---|---:|---:|
| Retained observations | 105/105 | 105/105 |
| Spatial side | 20 m | 40 m |
| Mean declared semantic loss | 0.57143 | 0 |
| Maximum declared semantic loss | 1 | 0 |
| Exact 20-m class-query coverage | 13/16 = 81.25% | 0/16 |
| Exact 40-m class-query coverage | 1/4 = 25% | 4/4 = 100% |

The fine output represents 20 distinct RoadUser in leaf 48, five AdultCyclist in leaf 49
and five Pedestrian in each remaining leaf. Its observation bins are 60 RoadUser, 15
AdultCyclist and 15 Pedestrian twice. The parent instead represents 29 distinct Pedestrian
and six AdultCyclist, with observation counts 87 and 18. No labels are falsified and no
semantic remainder is deleted. Both meet
all bounds. Fine occupancy and parent class totals constitute different useful outputs.
The declared class bank includes known-zero queries; positive-demand and per-category
strata are also retained in the artifacts.

A strict maximum loss can express a hard application requirement today. With the same
minimum 5 and side 40 m, setting loss maximum 0 forces spatial/time alternatives rather
than the RoadUser representation. With maximum side 20 m, that semantic requirement
makes leaf 48 unpublishable in the persistent rare-local source; A07 preserves the other
15/35 road users' observations, producing 42.86% retention. These are measured effects
of declared constraints, not evidence that a lower support or higher loss is acceptable.

## Temporal choice and fixed application queries

Reference alternatives above share the ACTUAL interval and evaluation time. A second,
separate evaluator uses a fixed receiver query bank across whole runs: four class counts
at each 20 m leaf or their 40 m parent, over 400/800-ms query windows, deadlines at end
plus 0/400 ms. Primary queries obey end + largest lag < source horizon. EOF/boundary
queries and censored deadlines are reported separately with exact denominators.

For rare-local input, minimum 5, loss maximum 0, side maximum 40 m and duration maximum
800 ms, Temporal First emits passing 40 m outputs every 400 ms. Spatial First prioritizes
spatial detail, waits until 800 ms, and then emits 40 m outputs. Both retain 100% with zero
semantic loss. The 400-ms parent class bank is 100% exactly answerable for TF and 0% for
SF: an 800-ms count cannot generally be divided into exact 400-ms counts. The 800-ms
parent bank is exactly answerable for both. This is a workload-resolution effect, not
proof that SF contains no useful information.

For temporal-turnover input under these strict semantic constraints, TF can merge
spatially at 400 ms; SF first obtains enough different cyclists at 600 ms and retains
20 m detail in that interval. Later intervals differ. The original temporal start is
not reset and repeats do not manufacture identity support.

Only immutable recipient releases sealed by a query deadline determine a prediction.
No public hole is filled with private source data. Crossing cells/windows are not split;
generalized categories straddling the requested class are unknown. This is a conservative
certified exact-answer rule, not a complete solver for all inferable answers (such as
zero specialization or subtraction). Answered-only MAE is zero in every scored case,
as expected for exact answers; the measured utility differences are coverage and detail.
Approximate occupancy allocation remains a different existing evaluator, not this bank.

## Reproduction and artifacts

From the repository root, with a built replay binary:

```sh
python3 -B tools/evaluation/run_semantic_priority_study.py \
  --output results/semantic-priority-new-run
ctest --test-dir simulator/build --output-on-failure -R 'semantic|run_semantic_priority'
```

Output directories must not already exist. `--limit 1` creates an explicitly incomplete
smoke run; it is not the 360-case study. MongoDB and the renderer are not required.

The completed private artifacts are under
[results/semantic-priority-2026-10-21](../results/semantic-priority-2026-10-21/summary.json).
Each case retains policy/input hashes, the actual recipient/diagnostic replay, independent
scalar audit, conditional candidate audit and fixed-query records. The
[manifest](../results/semantic-priority-2026-10-21/manifest.json) includes a frozen binary
hash and exact study-source/protocol snapshots. The study ran with that preserved runner;
a later comment correction and automatic source-snapshot packaging do not change its
scientific code or results. No existing output was overwritten.

`binding_failures` lists rejected candidate metric checks, while final-diagnostic counters
list checks observed in actual final decisions. Neither claims minimal infeasible cores
or a causal allocation of total loss to individual constraints.

## Next gate

The bounded implementation and comparison pass. Do not change controller priorities simply
to make one aggregate score look better. First specify the application's class/space/time
requirements or a justified preference order. Existing semantic-loss, cell-size and
freshness bounds already express hard requirements. Then test a scoped selection change
against the same frozen bank and report gains and losses together.

Broader E07 work remains: realistic workloads, independently varied age versus duration,
more complex spatial bounds/regions, depth-6 or larger domains, justified approximate
utility, local semantic coordination and empirical privacy gain on frozen versions.
Membership attacks, individual/type suppression and computation optimization remain
outside this step.

## Terminology clarification after the study

The adopted **Semantic First** strategy name means preserving semantic accuracy. It was
not a tested controller mode here. The frozen protocol's lowercase “semantic-first”
describes the old processing-order wording for early generalization inside each
space/time candidate. The original protocol remains immutable for provenance. This
editorial clarification changes no policy, binary, input, measurement or result.
