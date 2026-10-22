# Candidate metrics and threshold assessment

Status: 2026-10-21. Nine baseline online measures, three optional semantic measures
and the offline E01 occupancy evaluator are implemented. The new semantic product and
its exact interpretation are specified in [SEMANTIC_ADAPTATION.md](SEMANTIC_ADAPTATION.md).
Disabled scalar-only exports remain unchanged. This extends the [fixed aggregation contract](FIXED_AGGREGATION.md); A04
supplies requirements through [POLICY_TREE.md](POLICY_TREE.md). Spatial/temporal selection
and immutable publication are integrated. [Controlled evaluation](CONTROLLED_EVALUATION.md)
now compares identical inputs; [PRIVACY_EVALUATION.md](PRIVACY_EVALUATION.md) defines the
previously added optional deterministic stress test. Utility and policy evaluation now have an independent checker and a separate first
controlled synthetic empirical membership study; see
[EMPIRICAL_PRIVACY_IMPLEMENTATION.md](EMPIRICAL_PRIVACY_IMPLEMENTATION.md). The online
registry still contains no per-bucket empirical privacy-risk estimate or formal guarantee.

Canonical terms, symbols, units and code mappings are defined in
[TERMINOLOGY_AND_NOTATION.md](TERMINOLOGY_AND_NOTATION.md). Aggregation is bound to
a data cell and time interval; functional regions supply its requirements.

## Separation of responsibilities

The aggregator maintains counts and identity unions incrementally. At window closure,
the simulation passes its candidate to a standard-C++ MetricEvaluator, then passes the
candidate and assessment to the external diagnostic sink. The sink serializes results;
it does not select thresholds or decide what may be published. There is no new thread,
renderer queue consumer, database lookup or per-tick full metric scan.

Metric definitions specify quantities and units. A versioned MetricPolicy specifies
inclusive min/max requirements. The evaluator computes values from actual candidate
statistics and reports individual checks. An immutable regional PolicyTree can instead
supply effective requirements to this same evaluator; it does not manufacture values.
Choose one uniform policy or one regional tree per sensor/application stream. Explicit
Region metric_requirements are used only when selected by that tree. Legacy granularity
and `k_anonymity`/`l_diversity` settings are not reinterpreted as registered metrics.

## Initial metric registry

| ID | Unit | Definition and validity |
|---|---|---|
| observation_contributions | observations | Number of agent-observation contributions actually received in this cell/window. Available even with incomplete coverage. |
| distinct_contributors | contributors | Number of distinct internal agent IDs actually observed in this cell/window. Available with at least one measured sample; repeated observations do not increase it. |
| mean_sample_occupancy | agents | Contributions divided by measured samples, including measured-empty samples. Undefined with no measured samples. This is not a time-integrated average. |
| cell_side_m | m | Side length of square cell support. Undefined for non-square support. |
| cell_area_m2 | m2 | Width multiplied by height of cell support. |
| window_duration_ms | ms | end - start of the actual half-open interval, including a truncated final interval. |
| age_at_evaluation_ms | ms | evaluation time - window start. A conservative age of the interval; not wall-clock runtime or actual public release age. |
| post_window_delay_ms | ms | evaluation time - window end. |
| measured_sample_fraction | fraction | Measured / expected samples, in [0,1]. Undefined when no sample was scheduled. Unavailable/missing samples never count as measured. |
| occupancy_mae | agents | Offline error for the fixed occupancy query below. Unavailable in the online evaluator because it has no reference input. |
| min_category_distinct_contributors | road_users | Minimum exact distinct road-user support across nonempty released semantic categories; requires a configured taxonomy and private node evidence. Positive lower bound only. |
| semantic_max_loss | fraction | Maximum declared taxonomy-node loss among released categories; 0 exact leaves, 1 root. Upper bound in [0,1] only. |
| semantic_mean_loss | fraction | Observation-weighted mean declared node loss; upper bound in [0,1] only. Does not replace the maximum or a task-specific utility measure. |

Contributor IDs identify simulated agents, not necessarily individual humans (for example,
one vehicle agent does not count its occupants). Support is not a justified anonymity set.
Observed support remains a descriptive lower bound when observations are incomplete;
the mandatory coverage gate prevents a threshold pass from concealing that incompleteness.
No diversity or entropy formula is substituted for a missing attacker model.

Requirements use the registry's units; count and millisecond thresholds are nonnegative
integers, and sample-fraction bounds lie in [0,1]. Invalid/unknown/duplicate requirements,
non-finite bounds, empty ranges and min > max are configuration errors. Comparison is
inclusive. Policies are immutable for the initial run and carry an ID and version in output.
Contradictory inherited root/type/instance requirements are configuration errors. A coarse
footprint combining individually valid regions can instead be infeasible; its conflicting
check reports `contradictory_policy_bounds`, without invalidating those regions' children.

## Semantic candidate assessment

An enabled versioned hierarchy requires root category-support and maximum-loss bounds.
Regions strengthen the same numeric requirements through the existing Policy Tree.
The evaluator first resolves that cell's effective requirements, reconstructs the finest
complete semantic cut meeting the support minimum, then assesses its losses and every
scalar constraint together. Missing private evidence is unavailable. Malformed evidence,
unknown labels or contradictory raw-class/node counts reject explicitly.

These quantitative support/detail values are first-stage operational outcomes. A semantic
class is not automatically a sensitive attribute or an anonymity equivalence class.
Exact class queries are available only when the public cut resolves the requested class;
a generalized straddling bin gives unknown. The complete-partition contract prevents
inventing a zero for that unresolved class. See the semantic contract and E07 in TO-DO
for subsequent task-utility and constraint-impact evaluation.

## Assessment semantics

Each cell reports its metric values, unavailable reasons and configured checks:
`pass`, `fail` or `unavailable`. A violated available bound is a failure; an unavailable
required metric is never silently skipped. Failure takes precedence over unavailable
checks within an otherwise complete candidate, while every check remains visible.

Every assessment also includes a mandatory observation-coverage gate. A complete measured
interval passes this gate; missing/unavailable observations or no scheduled samples make
it unavailable. This gate cannot be weakened by configuring a sample-fraction threshold.
Malformed candidate geometry, impossible counts/times or inconsistent coverage metadata
raise an error rather than producing a plausible assessment.

The window-level summary is `not_configured` without a policy, `unavailable` when the
coverage gate cannot pass, `no_candidates` for a complete but entirely empty sparse window,
otherwise `fail`, `unavailable` or `pass` across its occupied-cell assessments. This is
configured-threshold compliance, **not** release approval or a privacy guarantee. Sparse
unoccupied leaves are not enumerated or individually approved. Empty, suppressed and
unavailable public support still belong to the later publication protocol.

Example: a 5-m square cell in [0,400) observed A, then A+B, then A. At evaluation time
450 ms it has 4 contributions, 2 distinct contributors, sample mean 4/3, area 25 m2,
duration 400 ms, age 450 ms, delay 50 ms and coverage 1. A support minimum of 3 fails;
maximum age 500 ms passes. Requiring occupancy_mae <= 1 is unavailable until an explicit
offline reference is supplied. These bounds demonstrate mechanics, not scientific choices.

## First utility question (E01 baseline contract)

Use mean sampled occupancy in a **fixed** 10-m square reference grid over non-overlapping
1-second query intervals, with the source's aligned 100-ms observation times. Anchor the
reference grid at the evaluation area's origin, use a common 80-m square area for sensor
comparisons, exclude t=0 under the existing schedule, and keep [start,end) boundaries.
The first query interval therefore contains nine samples; subsequent full intervals contain
ten. This is the first baseline application choice, not a claim of traffic-flow utility.

For each reference cell R and interval I, the GT answer is the arithmetic mean of GT agents
inside R at those fixed sample times. The prediction must answer that same query. Do not
coarsen the reference along with the aggregate. A future reconstruction from coarser
published support must declare its spatial/temporal allocation model. The first comparison
will use uniform spatial allocation and uniform occupancy within an aggregate interval,
weighted over the query's discrete sample times; that is an estimate, not recovered detail.

For example, neighboring reference cells with GT means 4 and 0 receive estimates 2 and 2
from a combined uniform aggregate: MAE is (2+2)/2 = 2 agents. Comparing only the parent
total would hide this lost detail. Missing/suppressed/unavailable predictions are missing,
not zero. Report answered-query coverage and conditional MAE separately, plus resolution
and age; do not interpret improved conditional MAE after dropping hard cases as better
overall utility. Equal-weight query scoring and the reference stay fixed across variants.

The offline query/reconstruction experiment is implemented in `tools/evaluation/occupancy.py`
and exercised by `run_comparison.py` on frozen private GT input and recipient releases.
It reports conditional `occupancy_mae`, `answered_query_coverage`, `scored_query_coverage`,
`reference_availability`, cell-side/area/window distributions, and simulated sealing age.
A query needs complete public spatial support at every scheduled sample; missing sparse
cells cannot be inferred to contain zero. All fixed reference cells, including empty ones,
remain in the coverage denominator. Incomplete reference intervals are unscorable.

Online diagnostics deliberately continue to return `offline_reference_required` for
`occupancy_mae`. The online aggregator does not receive private GT as a decision oracle.
Operational support/threshold checks and the offline known-background distinguishability
stress test remain different quantities; neither establishes a general privacy guarantee.

The [question register and experiment plan](RESEARCH_QUESTIONS_AND_EXPERIMENTS.md) now
separates current answers from untested hypotheses and lists the required data for future
metrics. Defining those prerequisites does not activate the deferred privacy experiments.

## Presentation metric review

Reviewed on 2026-10-13 against the supplied AutSys 2025 presentation, PDF pages 6–8
(printed slides 5–7), including the displayed formulas. This is a scoped assessment of
that source, not a completed comparison with all paper tables or a decision to implement
every metric. The registry currently computes descriptive statistics and constraint
inputs. The online registry has no empirical privacy-risk score or GT error input;
the separate offline evaluator now computes GT occupancy MAE and answered-query coverage.

| Presentation metric | Usefulness and required change | Current implementation |
|---|---|---|
| k-anonymity | A possible structural criterion after specifying the released record, protected entity, quasi-identifiers and equivalence classes. Distinct agents in a cell/window are only an observed support proxy. Repeated releases and published type subdivisions can invalidate a naive anonymity interpretation. | Distinct contributor support only; no k-anonymity claim. |
| l-diversity | Relevant when a meaningful sensitive attribute and corresponding equivalence groups exist. The slide shows distinct-value diversity; more types alone do not establish protection. Agent type must not silently serve as both a fixed quasi-identifier and a varying sensitive attribute within the same group. | Not implemented. Type contribution counts alone are not a distinct-person sensitive-value distribution. |
| t-closeness | Potentially useful for attribute inference once the sensitive attribute, reference population/time range and distribution distance are fixed. Ordinary region-to-global traffic-mix differences are not automatically a privacy defect. | Not implemented; no sensitive-attribute/reference contract. |
| delta-presence | Presence inference is relevant to mobility. A formal delta-presence calculation needs a specified population, released information and attacker knowledge; a local agent count cannot supply a membership probability. | Not implemented. E02 will define an empirical presence/membership attack separately. |
| Classification accuracy | Useful for an actual classification task with predictions and truth. Copying agent types from GT makes an agent-type classification test trivial. A future congestion classifier would be a different application task. | Not implemented. |
| Temporal granularity | Keep sampling period, aggregation duration and freshness separate. The displayed S + A adds scans/time to accumulated data points and is not dimensionally consistent. | Actual window duration, age at evaluation and post-window delay; sensor period is a separate input. |
| Data Fidelity Accuracy | The displayed lost counts / cell count is average loss per cell, not normalized accuracy. Retain the motivation through fixed-query error and answered-query coverage; specify units, weighting and missing-output handling. | Offline occupancy MAE and answered-query coverage are implemented; the online MAE value remains unavailable. Input sample coverage is a separate online measure. |
| Overall Localization Accuracy | Useful as spatial reconstruction error when locations matter to the application. The displayed sum is unaveraged and normalized by changing cell size; it need not track physical detail loss across runs. Specify the estimator (e.g. cell center), report mean/quantiles in metres with fixed observation weighting and report suppressed coverage separately. | Cell dimensions only; no GT position-error calculation. |
| Latency | Essential for timely applications. Measure processing time and observation-to-release delay separately, including waiting/queues. The displayed linear expression is a model requiring fitted coefficients and validation. | Online evaluation age and post-window delay; offline simulated sealing age and core processing time. Actual delivery latency is not measured. |

The equivalence-class and sensitive-attribute prerequisites follow the original
[l-diversity paper](https://www.cs.cornell.edu/johannes/papers/2006/2006-icde-publishing.pdf)
and [t-closeness paper](https://www.cs.purdue.edu/homes/ninghui/papers/t_closeness_icde07.pdf).
The original [delta-presence paper](https://www.cerias.purdue.edu/assets/pdf/bibtex_archive/p665-nergiz.pdf)
addresses disclosure of dataset membership under an explicit data/knowledge model.
The applicability decisions and utility-formula critiques above are our assessment of
the simulator and supplied slides, not claims of those papers.

Current first evaluation scope: fixed-query occupancy MAE plus answered-query coverage,
resolution and freshness, together with effective-policy compliance, suppression and output
availability. The user selected utility and policy fulfilment before privacy evaluation.
Contributor support remains an operational requirement; meeting it is not a measured-risk result.

A first synthetic contribution-membership study is now implemented separately from the
online registry. Its motivation and limits remain in [PRIVACY_EVALUATION.md](PRIVACY_EVALUATION.md)
and the implementation/test report. Neither
utility measurements nor policy compliance establish formal anonymity or reduced attack success.

Example motivation: a window containing ten different agents over ten instants can
still contain only one agent at each instant. The union count ten says nothing by
itself about whether an attacker can identify a target's contribution using time-specific
auxiliary knowledge. The release contents and attacker knowledge decide that question.

## Configuration and diagnostic output

Existing aggregation-enabled runs receive metric values without implicit thresholds.
To exercise checks, add this optional block under an AGBS's `aggregation` settings:

```yaml
metric_policy:
  id: support-and-freshness-demo
  version: "1"
  requirements:
    distinct_contributors: {min: 3}
    cell_side_m: {max: 10}
    window_duration_ms: {min: 200, max: 1000}
    age_at_evaluation_ms: {max: 1500}
```

This is a uniform demonstration policy. For the regional alternative use `policy_tree`
as described in [POLICY_TREE.md](POLICY_TREE.md); selecting both is an error. Omitting both
gives `not_configured`; an empty uniform/root requirements map is rejected. No maintained
production YAML is altered automatically. Current JSONL schema `ump.fixed-candidate.v3`
retains the v2 metric/check fields and adds `assessment.policy_mode` (`none`, `uniform`,
`regional_tree`) and each cell's `policy` object with `effective_id`, `sources`, `feasible`.
Without a policy, the per-cell policy object is empty and assessment policy ID/version are null.
Evaluation time, quality gate, values/units, unavailable reasons, bounds/checks and threshold
summary remain visible. This is internal research output, including failed candidates and
their counts; it is not a public dataset. Consumers must check the schema version.


## Verification

MetricRegressionTests checks the worked example, inclusive and violated limits, delayed
evaluation, complete truncated intervals, absent/invalid policies, count/coverage/geometry
consistency, mandatory coverage, non-square support, unavailable GT references and per-cell
rather than stream-wide support. The metric core builds without SFML or MongoDB.

The original E04 Release build and all four then-existing CTest suites passed. An isolated one-second headless
fixture used four AGBS streams with passing, failing, unavailable-reference and absent
policies. All twelve JSONL windows and per-cell metrics/checks matched the expected outcomes;
an unknown YAML metric produced an explicit nonzero startup failure. Only a UUID-named
test database was used and removed. This is functional validation, not an attacker study,
utility benchmark, regional-policy test or performance result.

A04 subsequently passed all seven suites and exercised this evaluator with root/type/Region
requirements. The four-stream fixture was rerun against schema v3, verifying uniform and
absent-policy modes and provenance along with all twelve windows' existing numeric checks.
Separate regional/conflict and startup-validation evidence is in POLICY_TREE.md.

## Offline verification added on 2026-10-14

The occupancy evaluator tests uniform coarsening, fixed denominators, first-nine/later-ten
sample weighting, temporal boundaries, missing/empty support, unavailable references,
public-only predictions, overlap rejection and final partial queries. Replay regressions
exercise the actual policy/selection/adaptation/publication cores, all modes, stricter
regional inheritance, exact count conservation, determinism and invalid-input rejection.
See [the comparison report](EVALUATION_RESULTS_2026-10-14.md) for the measured pilot; these
are descriptive cases, not a completed privacy/utility benchmark.

## Bounded semantic query and candidate-choice evaluation

The [completed E07/A08 study](SEMANTIC_PRIORITY_STUDY_2026-10-21.md) adds offline
exact-query coverage for a declared class-count bank and same-interval nondominated
candidate inspection. These are evaluation quantities, not new online release metrics.
All 360 configurations and 1,929 actual intervals audit. Detailed support/QI meaning,
fixed cohorts, conservative answerability and limits are specified in that report
and notation section 26. Zero answered-only error must be reported alongside query
coverage; no source observations fill missing recipient support.


## Recipient-support and occupancy estimation diagnosis (2026-10-23)

The [recipient contract](RECIPIENT_CONTRACT_PROTOCOL_2026-10-23.md) adds an optional
offline decoder for existing releases. This does not introduce a new online
eligibility metric or policy threshold. For query region/time/category `(R_Q,T_Q,g)`,
each resolved public record contributes its category count multiplied by its
intersected area fraction and intersected scheduled-sample fraction. Divide the
sum by `|T_Q|` for mean sampled occupancy. The initial t=0 slot is not a sensor
sample. Counts are observation contributions, not unique people across time.

An estimate is available only with complete, semantically resolved public support
sealed by the query deadline. Missing records stay unknown; broad categories do
not imply fine-type proportions. Every old exact answer remains an equal estimated
answer. The original exact decoder is conservative whole-tile containment, not
maximal inference from the public transcript (some crossing certified zeros could
be inferred by a stronger decoder).

Always report fixed-cohort coverage together with conditional contribution/occupancy
MAE and errors on the paired answered intersection. Estimated-only answers are
counted separately. Query-support diagnostics partition finest-leaf/sample volume
by joint spatial crossing, temporal crossing, semantic ambiguity and lateness masks,
plus an unpublished remainder. These are representation restrictions, not causal
producer failure counts or privacy-risk metrics. Category questions repeat support.

See [results and tests](RECIPIENT_CONTRACT_REPORT_2026-10-23.md): forty unchanged
exact evaluations, forty additional diagnoses and twenty-four paired comparisons.
After the study, on 2026-10-23 the user selected exact answers as the reference
plus clearly labeled estimates evaluated separately for error, coverage and latency.
This accepts the two-product evaluation approach, not a numerical error tolerance,
minimum coverage or receipt deadline. Those application limits remain undecided.
The [runtime report](RUNTIME_DIAGNOSTIC_REPORT_2026-10-23.md)
separately measures per-input service and a hypothetical queue; logical policy age
does not include wall-clock processing/transport delay.
