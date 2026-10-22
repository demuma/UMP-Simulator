# Semantic adaptation under regional policy constraints

**October 22 extension:** [semantic cell-local coordination](SEMANTIC_CELL_LOCAL_CONTRACT_2026-10-22.md)
now supports taxonomy-enabled independent owners and both Semantic First secondary
priorities. Earlier scope exclusions below describe the original implementation
gate; see the [new verification report](SEMANTIC_CELL_LOCAL_TEST_REPORT_2026-10-22.md)
for current behavior and remaining visualization/effectiveness limits.

Date: 2026-10-21. Status: first common-window implementation verified. The acceptance
contract was recorded before implementation; this document now includes its exact
interfaces, formulas, results and limits.

## Scope and research order

The current objective is to satisfy declared Policy Tree constraints and quantify
category support, semantic detail, retained data and useful-query availability.
The constraints' effect on achievable outputs belongs to a subsequent controlled
sensitivity study. Their thresholds are not silently weakened during selection.
Membership attacks and computational optimization remain deferred.

This step adds truthful semantic generalization within common-window spatial,
Temporal First and Spatial First candidate assessment. It integrates with A07,
immutable publication, JSONL diagnostics and optional MongoDB storage/recovery.
The existing scalar-only product remains the default. Enabled cell-local semantics
are explicitly rejected. Individual/type suppression, false relabeling, a new motion
model, compositional behavior profiles and a joint utility optimizer are separate work.

## Immutable classification hierarchy

`aggregation.semantic_taxonomy` contains `id`, `version` and `nodes`. Each node has
`id`, optional `parent`, `loss` and optional `input_types`. Raw simulation labels map
explicitly to terminal categories. There is no string parsing or inferred parent.

```yaml
semantic_taxonomy:
  id: road-users
  version: '1'
  nodes:
    - {id: road_user, loss: 1}
    - {id: pedestrian, parent: road_user, loss: 0, input_types: ['Adult Pedestrian']}
    - {id: cyclist, parent: road_user, loss: 0.5}
    - {id: adult_cyclist, parent: cyclist, loss: 0, input_types: ['Adult Cyclist']}
    - {id: child_cyclist, parent: cyclist, loss: 0, input_types: ['Child Cyclist']}
```

This excerpt maps only the named source types; an experiment must map every input
label it supplies. It does not add Child Cyclist to the default live behavior profiles.
Aliases may map to the same terminal. A separate public catalog supplies IDs, parents
and costs without private source identities. Its ID/version must bind one immutable
catalog; changing it requires a new version.

Validation requires exactly one root, connected acyclic parent relations, unique IDs,
unambiguous raw mappings, at most 256 nodes, depth at most 32 and at most 4096 aliases.
Node IDs/version text are bounded to 128 bytes, aliases to 256. Every leaf has at least
one alias and loss 0; the root has loss 1. Costs are finite in [0,1] and cannot decrease
toward ancestors. These costs are declared representation costs, not attack probabilities
or automatic measures of traffic usefulness. They are independent of quadtree depth.

The source behavior profile and the released category are separate: an Adult Cyclist
can retain its behavior while its release says Cyclist. No road user becomes a pedestrian.

## Exact private evidence

For an evaluated domain and half-open interval, each identity must map to one terminal
category. A different alias for the same terminal is allowed; conflicting terminals
reject. `queryFinest` enforces this over its complete queried domain/interval, which
is the whole grid in common mode. This can be stricter than checking only eventual
output cells. It is a bounded reconstruction assumption, not a permanent identity registry.

`SemanticAccumulator` counts observations and exact identities for every taxonomy node,
including zero nodes. History rebuilds these statistics from raw observations; it does
not sum distinct supports from spatial children. The semantic fixed-window manager also
reconstructs its finest candidate from the same history, requiring bounded history.
Unknown labels reject before aggregation input mutation. Missing/expired history fails
explicitly rather than inventing evidence.

`AggregateCounts.semanticEvidence` is private and contains no identity strings. It still
contains hidden fine-category counts, so it must never reach a recipient. The evaluator
checks node partitions, root totals, exact count range and agreement with raw type
contribution histograms before choosing a representation.

## Complete semantic cut and quantitative measures

For cell C and interval I, a cut K is a nonoverlapping set of taxonomy nodes. Every
observed terminal belongs to exactly one selected node's subtree. All observations of
a released spatial cell remain represented exactly once; no semantic remainder is dropped.
Thus 20 RoadUser can be valid, whereas 19 Pedestrian + 1 RoadUser overlaps in category
space and is forbidden. Suppressed spatial footprints remain the existing A07 mechanism.

With the canonical notation from [the notation contract](TERMINOLOGY_AND_NOTATION.md),
let O_v(C,I) contain observations whose terminal is below category v, and U_v the exact
union of their road-user identities. The category support statistic is

$$
n_{\mathrm{cat,min}}(C,I,K)=\min_{v\in K}|\mathcal U_v(C,I)|.
$$

It is registered as `min_category_distinct_contributors` in road users. Repeated samples
of one person do not increase it. It is a quantitative operational disclosure measure;
its interpretation is not replaced with formal k-anonymity or l-diversity.

For declared category cost gamma_sem(v), the detail measures are

$$
L_{\mathrm{sem,max}}(K)=\max_{v\in K}\gamma_{\mathrm{sem}}(v),\qquad
L_{\mathrm{sem,mean}}(C,I,K)=
\frac{\sum_{v\in K}|\mathcal O_v(C,I)|\gamma_{\mathrm{sem}}(v)}
{|\mathcal O(C,I)|}.
$$

They are `semantic_max_loss` and `semantic_mean_loss`, both in [0,1]. The mean is
observation-weighted; the maximum prevents a small class's severe detail loss from
being concealed by the mean. These are representation measures. Task utility is also
examined through fixed class-count queries and their answerability.

Enabling the taxonomy requires these explicit root bounds:

```yaml
policy_tree:
  root:
    min_category_distinct_contributors: {min: 4}
    semantic_max_loss: {max: 0.5}
    # Optional additional hard constraint:
    semantic_mean_loss: {max: 0.5}
```

Support uses a positive integer lower bound only; semantic loss uses upper bounds only.
Regions can strengthen support minima or tighten loss maxima through the existing
strict inheritance/intersection. A spatial parent receives requirements for its entire
footprint, including intersecting stricter regions. Existing scalar size/support/time/
age/coverage requirements remain mandatory. Missing evidence is unavailable, never a pass.
Counts stay within the existing exact numeric metric range 0 through 2^53-1.

## Selection and existing adaptation

Within EACH spatial/time candidate:

1. Find the finest complete semantic cut meeting its effective category-support minimum.
2. Keep occupied child cuts if all pass; otherwise test their actual parent using all
   original observations. Continue to the root if necessary.
3. Measure the selected cut's support and losses; assess them alongside every scalar
   hard requirement. An impossible support cut reports the actual root support so the
   numeric failure remains visible.
4. If any requirement fails, existing TF/SF/A07 spatial/temporal progression continues.
   Semantic success alone cannot end an otherwise invalid window.

This is early semantic generalization within a spatial/time candidate. It is not the
adopted **Semantic First** preservation strategy and is not joint
optimization over semantic resolution, space, time, suppression and future arrivals.
For the declared uniform per-category minimum within one candidate and monotone node
costs, preserving a valid finer cut does not increase either loss measure. Tiny exhaustive
checks independently test this fixed-candidate behavior; no global scheduling optimality
is claimed.

A provisional A07 partial spatial cut remains private while temporal extension is legal.
The new semantic dimensions do not reset starts, deadlines, retirement or source coverage.

## Approved output, persistence and queries

`CellMetricAssessment.semantic` holds the computed private assessment. At sealing,
PublicationCoordinator recomputes it with its own evaluator and exact immutable catalog;
it does not trust diagnostic flags or a caller's attached bins. It clears raw type counts
and private node evidence, then attaches only the approved `ReleasedCell.semantic` value.
Delivery reassesses all selected cells at actual time. Retry retains the same snapshot.

The additive per-cell object has schema `ump.semantic-release.v1`, taxonomy ID/version,
approved categories, their observation/distinct counts and the three measured summaries.
No hidden terminal counts, identities, failed alternatives or spatial suppression totals
are included. Existing scalar-only v1/v2 payloads remain byte-compatible when semantics
are absent. Semantic output currently requires common-window v1 coordination.

MongoDB validates count/metadata structure and budgets, preserves the exact semantic
payload through prepare/write/reconcile/commit/recovery and rejects private evidence.
It trusts the coordinator for catalog ancestry/cost and policy approval: journal recovery
is not a fresh privacy assessment without the original trusted snapshot and policy.

`SemanticTaxonomy::exactQuery` answers a class count by exact rollup only when the approved
bins are wholly inside or disjoint from the requested class. A bin that spans the class
and another possible class makes the answer unknown. Under the complete partition,
a wholly disjoint category is a measured class zero in this released cell/window.
An absent public spatial cell is still unknown. Distinct counts must not simply be added
across different spatial cells/windows, because road users can move or recur.

## Hand cases and verification gate

- 19 pedestrians + 1 cyclist, category minimum 5: 20 RoadUser if root loss 1 is permitted.
- Same data with maximum loss 0.5: no semantic solution within the fixed example limits.
- 2 adult + 2 child cyclists, minimum 4: 4 Cyclist with declared loss 0.5.
- Same four repeatedly measured, minimum 5: fails; no fifth person is fabricated.
- Every terminal passes: exact categories and loss 0.
- Additional matching people in another cell or later samples can allow spatial or
  temporal aggregation to retain the finer semantic classes.

The [test report](SEMANTIC_ADAPTATION_TEST_REPORT_2026-10-21.md) records 47 passing CTest
entries, 300 passed Python methods (12 optional skips), 81 independently enumerated
tiny semantic cases, actual
MongoDB recovery, sanitizer checks and 24 unchanged scalar-only before/after pairs.
The [frozen examples](../simulator/examples/semantic-adaptation/README.md) require no MongoDB.

The gate applies to this common-window product. Local semantic coordination, class-specific
utility priorities, per-taxon bounds, individual/type suppression, joint candidate search
and empirical privacy changes remain separately scoped work.

## Later constraint-impact study (E07)

Use identical frozen inputs, application queries and candidate/action definitions. Vary
category/overall support minima, maximum cell size, duration/age and semantic loss, first
separately and then in declared combinations. Record binding constraints and version every
policy; do not silently relax a failing condition.

Measure feasible-case fraction within a declared reference class, compliance violations,
retained contributions, timely query coverage/error, space/time/semantic detail and release
age. Distinguish unavailable evidence and invalid input from policy infeasibility. Compare
actual choices with a bounded exhaustive reference where available, separating unavoidable
policy cost from a search/coordination gap. Suppressing everything cannot count as successful
usefulness merely because the remaining releases comply.

For the same candidate class, stricter constraints shrink the feasible set. An online
heuristic's observed utility need not be monotonic because its release history can change.
The impact study precedes broad tuning; quantitative empirical privacy gain is subsequently
measured on the same mechanism/policy versions. Current support and detail measures remain
explicit quantitative outcomes without claiming a perfect privacy guarantee.

## Completed bounded decision-order review

The first [E07/A08 study](SEMANTIC_PRIORITY_STUDY_2026-10-21.md) now verifies legal
same-interval candidates and fixed receiver query availability for 360 configurations.
It demonstrates an explicit spatial/category detail trade-off and distinguishes interval
feasibility from query utility. No production priority is changed. The broader sensitivity
and empirical privacy studies above remain open; support/QI interpretation is clarified
in the new study.

## Preservation-priority terminology

**Semantic First means preserving semantic accuracy**, consistently with Temporal First
and Spatial First. Ordinary TF/SF attempt allowed class generalization early inside each
candidate. The dedicated common-window [Semantic First mode](SEMANTIC_FIRST_IMPLEMENTATION.md)
now instead uses a zero-cost preference and bounded terminal fallback, with TF secondary.
It minimizes the tested ceiling for worst semantic loss, not mean semantic loss or all
application error. Nomenclature section 10 fixes this distinction. A hard zero loss maximum
forbids positive-cost generalization (terminal categories in this example catalog).
That is a different policy from preferring exact classes while allowing bounded fallback.
