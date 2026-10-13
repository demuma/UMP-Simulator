# Candidate metrics and threshold assessment

Status: 2026-10-13. Initial E04 implementation and E01 baseline query contract. This extends the
[fixed aggregation contract](FIXED_AGGREGATION.md). It does not implement a regional
policy tree, adaptive search, a publication protocol or an empirical privacy claim.

## Separation of responsibilities

The aggregator maintains counts and identity unions incrementally. At window closure,
the simulation passes its candidate to a standard-C++ MetricEvaluator, then passes the
candidate and assessment to the external diagnostic sink. The sink serializes results;
it does not select thresholds or decide what may be published. There is no new thread,
renderer queue consumer, database lookup or per-tick full metric scan.

Metric definitions specify quantities and units. A versioned MetricPolicy specifies
inclusive min/max requirements. The evaluator computes values from actual candidate
statistics and reports individual checks. A future regional PolicyTree will supply
effective policies to this same evaluator; it must not manufacture measured values.
The first policy applies uniformly to one configured sensor/application stream. No Region
or legacy `k_anonymity`/`l_diversity` setting is silently reinterpreted in this slice.

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

Contributor IDs identify simulated agents, not necessarily individual humans (for example,
one vehicle agent does not count its occupants). Support is not a justified anonymity set.
Observed support remains a descriptive lower bound when observations are incomplete;
the mandatory coverage gate prevents a threshold pass from concealing that incompleteness.
No diversity or entropy formula is substituted for a missing attacker model.

Requirements use the registry's units; count and millisecond thresholds are nonnegative
integers, and sample-fraction bounds lie in [0,1]. Invalid/unknown/duplicate requirements,
non-finite bounds, empty ranges and min > max are configuration errors. Comparison is
inclusive. Policies are immutable for the initial run and carry an ID and version in output.

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

The GT query/reconstruction experiment and attacker evaluation remain unimplemented.
Online diagnostics deliberately return `offline_reference_required` for occupancy_mae.

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

This is a uniform demonstration policy, not the regional tree. Omitting the block gives
`not_configured`; an empty requirements map is rejected. No maintained production YAML
is altered automatically. The JSONL schema is versioned to `ump.fixed-candidate.v2` and
includes policy ID/version, evaluation time, quality gate, each metric's value/unit or
unavailable reason, each bound/check and the threshold summary. It remains internal
research output, including failed candidates and their counts; it is not a public dataset.


## Verification

MetricRegressionTests checks the worked example, inclusive and violated limits, delayed
evaluation, complete truncated intervals, absent/invalid policies, count/coverage/geometry
consistency, mandatory coverage, non-square support, unavailable GT references and per-cell
rather than stream-wide support. The metric core builds without SFML or MongoDB.

The full Release build and all four CTest suites passed. An isolated one-second headless
fixture used four AGBS streams with passing, failing, unavailable-reference and absent
policies. All twelve JSONL windows and per-cell metrics/checks matched the expected outcomes;
an unknown YAML metric produced an explicit nonzero startup failure. Only a UUID-named
test database was used and removed. This is functional validation, not an attacker study,
utility benchmark, regional-policy test or performance result.
