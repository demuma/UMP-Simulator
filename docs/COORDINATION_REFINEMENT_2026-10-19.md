# Targeted cell-local coordination refinement

Date: 2026-10-19. This follows the measured weaknesses in the
[fixed common/local study](COORDINATION_STUDY_2026-10-19.md). The original study,
executable, observations and results remain intact. The common-window controller
is unchanged; the opt-in cell-local controller is revised and re-evaluated.

## Changed decisions

Previously a failed owner tried its nearest passing ancestor and published it
immediately. A different unresolved branch could need a broader parent containing
that earlier release. Even if that parent already passed at the same endpoint,
its historical release became forbidden after the first smaller disclosure.

The revised controller freezes current endpoint assessments before publishing:

1. Reconstruct and assess every current unresolved owner at the closed endpoint.
2. For each nonempty failed owner, find its nearest passing, common-start ancestor
   among legally reconstructable domains. Temporal First permits spatial rescue
   now; Spatial First first permits temporal extension and uses spatial fallback
   under a concrete candidate's deadline pressure or finalization.
3. Form the candidate set of those nearest rescues. If candidates nest, retain
   the containing candidate that another failed branch requires. Keep disjoint
   finer rescues separate. A passing coarse cell alone does not justify coarsening.
4. Publish the resulting nonoverlapping planned domains, then process remaining
   owner windows. Every accepted parent is independently revalidated before its sink.

For failed owners f with a permissible rescue r(f), write A={r(f)}. The planned cut
is the inclusion-maximal subset of A. Because data-quadtree cells are nested or
disjoint, this subset is nonoverlapping. This is a causal deterministic endpoint
heuristic. It is not an optimal asynchronous schedule, a global utility optimizer
or an assertion that coarser output improves every application query.

A passing or measured-empty owner is now held only for a concrete common-start
ancestor that remains potentially feasible. Geometry, intersected policy bounds,
complete coverage, all owned deadlines and sampling-aligned possible future ends
are checked. Contradictory/unavailable requirements and exceeded monotone count
maxima cannot justify a hold. Mean occupancy can vary nonmonotonically; no future
value or successful privacy check is invented. A legal opportunity may still fail
when later observations arrive. Holds continue to extend the aggregation interval;
they do not freeze a completed release for delayed delivery.

This removes the former minimum-depth-wide failure flag as the reason to delay
unrelated passing owners. A parent that violates the cell-side cap cannot justify
holding a child. Future parent reconstruction cannot reopen retired or public support.

## Bounds and retained contracts

`spatial.maxEvaluations` bounds unique reconstructable ancestor assessments in one
endpoint plan, including future-hold feasibility checks. Shared ancestor paths reuse
an assessment. Incompatible ancestry/start/handoff cache entries do not consume that
assessment counter; their number remains bounded by the finite ownership tree.
Diagnostic fine evaluations and accepted-parent revalidation remain separate existing
work. The field is not a counter of every metric operation in the complete algorithm.
Exhausted planning or due-owner temporal budgets fail before the endpoint's first sink.

The source observation history, exact identity unions, original interval starts,
full ownership frontier, mixed-depth takeover, future handoffs, immutable pending
sink retries and public APIs remain unchanged. No already disclosed result is deleted,
revised or reused. No extra input from future sample times enters an earlier candidate.

Seven focused regression cases cover illegal-parent holds under both priorities,
nested rescues in two independent base quadrants, separate finer rescues, spatial
caps, preservation order, half-open endpoint causality and pre-disclosure budget
failure. The original 120 stress seeds remain unchanged; 120 additional cases vary
regional minimum/maximum durations and legal spatial caps. Raw geometry/time/count
and ownership audits remain independent of the production history/selection code.

## Reproduction and recorded comparison

After the README build/test steps, replay the same predeclared 30-case matrix:

```sh
python3 -B tools/evaluation/run_coordination_study.py \
  --output results/evaluation/2026-10-19/coordination-study-19-26-v2
python3 -B tools/evaluation/compare_coordination_studies.py \
  --before results/evaluation/2026-10-19/coordination-study-19-26-v1 \
  --after results/evaluation/2026-10-19/coordination-study-19-26-v2 \
  --output results/evaluation/2026-10-19/coordination-refinement-comparison-v1
```

The comparator verifies source/executable/protocol/case/artifact hashes, identical
frozen observations and numerical/effective policies, complete independent audits,
and exact scientific output equality for all seven untouched references (runtime
excluded). It reports both local priorities before/after, full-domain coverage,
retention, conditional error, exact ages and matched-query error at both query scales
and full/interior horizons. Undefined support remains undefined. Independent complete
realizations are the replication unit; a lower age on a different retained subset is
not a matched-person freshness effect.

Privacy work follows the [predeclared source-membership protocol](PRIVACY_COORDINATION_STUDY_2026-10-19.md).

## Actual before/after results

The new matrix completed all 30 cases: 270 independently audited replays and 120 exact adaptive repeats. All audits passed across 23,177 released cells and 19,779 terminal windows. The comparator verified identical observations, numerical policies, effective policies and all 210 scientific outputs of the seven untouched references (runtime excluded). The prior matrix remains unchanged.

Private bundles: `coordination-study-19-26-v2` and `coordination-refinement-comparison-v1` under `results/evaluation/2026-10-19/`. The executable SHA-256 is `17313ec82b2d50aa433fd0c0634edbad1fd7c0ef9744a05c3219c55bbda041e2`. The immutable protocol preceded execution; source hashes stayed fixed.

### Retained contributions and query availability

Per-family means use eight paired complete realizations. Differences below compare the revised local controller with its previous version; percentage points are absolute, not relative percent changes. Coverage uses the original 10-m / 1000-ms fixed query.

| Family | Priority | Local retention before | Local retention after | Coverage change (pp) | Mean age change (ms) | Matched MAE change |
|---|---|---:|---:|---:|---:|---:|
| mixed density | SF | 79.29% | 97.38% | +35.47 | +11.44 | +0.0545 |
| mixed density | TF | 81.43% | 97.25% | +34.89 | -29.25 | +0.0311 |
| regional latency | SF | 68.91% | 100.00% | +49.68 | -31.37 | +0.0045 |
| regional latency | TF | 64.02% | 100.00% | +52.86 | -5.88 | +0.0016 |
| turnover | SF | 97.72% | 100.00% | +16.99 | +6.17 | +0.0289 |
| turnover | TF | 95.76% | 100.00% | +36.52 | -58.07 | +0.1280 |

The previous mixed-density retention deficit is removed for SF (revised local equals common in the measured retention/coverage/age summaries). TF differs from common by -0.0732 pp retention and -0.1465 pp primary coverage on average, while retaining lower conditional mean age. In regional latency, both revised local priorities retain 100% of source contributions; the common controller retains 51.71% on average. Turnover retention reaches 100% for both local priorities. These finite synthetic cases do not establish global superiority.

The matched MAE column is positive in every family/priority mean: some formerly fine answered support is now reconstructed more coarsely to retain additional branches. Mean increases range from 0.0016 to 0.1280 road users; individual differences include both signs. The revised controller greatly improves retention and coverage here, but does not uniformly improve accuracy. Exact ages concern changing retained subsets and are not matched-user latency comparisons. Two query scales and full/interior evidence remain in every comparison pair.

### Proven mechanisms

In `parent_infeasible_valid_children`, both local priorities keep 156/195 contributions while exact mean age drops from 343.59 to 148.72 ms: the valid child is no longer held for an illegal parent. The blocked-branch, homogeneous, heterogeneous-deadline and hypothetical publication-barrier controls preserve their scientific retention/age outcomes.

For `mixed_density-seed-19`, revised local Temporal First actually releases parent 14 over [0,200), sealed at 200 ms, with nine contributions. The old 934/[0,1000) suppressed window no longer occurs. This closes the recorded early-commit witness. Whole-case TF retention rises from 2948 to 3633 contributions and SF from 2843 to 3637. It does not quantify all possible future publication regret.

Updated local/common figure: [PNG](figures/coordination-refined-2026-10-19.png) /
[SVG](figures/coordination-refined-2026-10-19.svg). This compares revised local with
common; the table above compares revised local with its previous version.

### Computation and verification

The new 30-case matrix ran from 18:48:01.910644 to 18:49:17.295812 UTC. Main private disk volume at completion was 893,844,165 bytes, versus 959,205,519 before; this includes full private query/audit/diagnostic evidence and snapshots, not online RAM. Terminal-window records fell from 57,905 to 19,779. Family/priority mean local core elapsed reductions range from 2.63 to 34.35 ms per entire replay. These are descriptive single executions, not a controlled CPU benchmark.

A frozen dense depth-six case confirms no evident planning blow-up: with support one, current core elapsed was 258.334 ms and output matched the prior reference; with support two the old/new values were 283.142/291.870 ms with identical scientific output excluding runtime. These single measurements do not prove city-scale performance. The 4096-leaf source and all budgets remain explicit.

All 33 CTest suites and all 196 Python methods passed. Fresh AddressSanitizer/UndefinedBehaviorSanitizer builds passed the focused regressions and all 240 stress cases. Strict compiler warnings required a narrow exception for an existing common-controller missing-field initializer; no source was changed to hide a warning. Commands, logs, hashes and full limitations are collected in [the verification report](REFINEMENT_PRIVACY_TEST_REPORT_2026-10-19.md).

## Remaining limits and transition to privacy

The planner is still a bounded causal heuristic. Future holds consider concrete feasible ancestors but do not optimize their expected value, and not every possible schedule is searched. The common controller still has its documented partial-child-rescue limitation. Publication-loss regret, proactive ancestor caches, automatic recovery and live dense-city benchmarking remain separate open work.

The user has now prioritized privacy evaluation over further coordinator optimization. The next completed comparison must ask what the changed availability/geometry/timing reveals about the declared source-membership secret, using the predeclared independent attack protocol. A retention gain and a passing distinct-support threshold do not answer that privacy question.
