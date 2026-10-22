# Moving-input common/local comparison against fixed baselines

Date: 2026-10-22. Frozen before executing this comparison. This is a bounded,
paired engineering pilot on an existing Simulator recording, not an independent
traffic population study or a privacy-effectiveness evaluation.

## Question and boundary

Under identical hard release constraints, how do fixed spatial/temporal grids,
common-window adaptation and cell-local adaptation differ in retained observations,
semantic/spatial detail, delay and the ability to answer fixed recipient queries?
A local or adaptive advantage is not presumed. No controller, motion generator,
metric threshold or query mask is tuned after observing this matrix.

The previous analytical 20-identity fixture and its regional policies remain
unchanged. This gate uses moving observations from the user's existing C++
Simulator. It adds experimental orchestration and independent verification only.
Membership attacks, new sensitive attributes, maps, motion realism improvements
and mechanism/cache optimization remain separate steps.

## Frozen source and provenance

Use `results/moving-replay-2026-10-21/n500/capture/observations.json`:

- SHA256: `ab4fadf254bfb5432018ff4bd305cd16d82a7475ae3d934c14c4f9af67dd5cf1`.
- Run: `simulator-capture-9eea9c4d70f84040849fd6de778d34ba`.
- Area: 80 x 80 m, finest quadtree depth 6 (1.25 m cells).
- Sensor cadence: 100 ms; horizon: 20,000 ms; 199 measured frames,
  t=100 through 19,900 ms. The initial t=0 state is not a sensor measurement.
- 99,140 observation contributions, 500 initially sampled Road Users, 495 in
  the final sample; seven configured terminal profiles. One canonical terminal
  type per identity over this source is a benchmark assumption that is checked.

Verify the capture proof/status and declared observation/proof hashes before use.
Hash source files before and after. Freeze protocol, experiment dependencies and
current AggregationReplay executable before running variants. Keep all movement,
identity-bearing records, raw releases and private diagnostics local in ignored
results directories. Only code, tests, documentation and compact aggregate results
enter Git. Do not copy database owner tokens or capture sample records into tracked
provenance. Do not run Simulator or change the normal Simulation database.

This capture is one stochastic realization, not a set of independent replicates.
It uses the existing initial-position/destination movement model, not a realistic
mapped shopping street or measured traffic. Do not treat repeated deterministic
executions as independent evidence or derive population confidence intervals.

## Matched policy and variants

All ten variants use the existing versioned seven-profile, ten-node semantic
taxonomy (terminal loss 0, Pedestrian/Cyclist family loss 0.5, Road User loss 1).
The taxonomy assigns the e-scooter terminal loss 0. This declared loss scale is a
representation measure, not a calibrated privacy score.

Shared hard root requirements:

| Metric | Bound |
| --- | --- |
| Distinct Road Users per cell | at least 1 |
| Distinct Road Users per published semantic bin | at least 5 |
| Maximum semantic hierarchy loss | at most 1 |
| Output cell side | 1.25 to 10 m |
| Source interval duration | 400 to 1,000 ms |
| Age at evaluation (endpoint minus original start) | at most 1,000 ms |

The explicit duration minimum is essential. `window_ms: 400` alone is the first
probe interval and does not prohibit shorter local parent rescues at other owners'
endpoints. Do not retrospectively relabel the old fixture as having this minimum.
No regional exceptions are introduced in this pilot. Identical support thresholds
mean identical policy conditions, not identical measured privacy protection.

Six fixed baselines: 2.5, 5 and 10 m cells crossed with 400 and 1,000 ms windows.
They use the same semantic cut evaluator, support checks and suppression rules.
Call them fixed spatial/temporal aggregation with semantic release rules, rather
than an unmodified GBS sensor or a baseline without privacy constraints.

Four adaptive variants: common-window and cell-local coordination, each using
Semantic First with Temporal First or Spatial First secondary priority. The terms
name the dimension to preserve: Temporal First preserves temporal precision;
Spatial First preserves spatial precision. All use `policy_satisfied`, a 400-ms
initial probe, 100-ms extensions and a 1,000-ms maximum window. Eligible cuts may
publish before the maximum. Common coordination uses its existing valid-descendant
preservation; local ownership uses its own preservation/handoff mechanism and must
set `preserve_valid_descendants: false`. Record this execution distinction.

Keep explicit bounded resource settings: retained history 2,000 ms, 32 bins,
100,000 observations, 16 MB identity bytes, optional bucket registry 128;
spatial evaluations 8,192; temporal evaluations 16; local active cells 4,096.
The history registry is distinct from local owners. Core replay keeps its existing
256-MiB serialized-output budget. A per-execution wall-clock timeout is 300 s.
Resource failures are reported separately from policy infeasibility; do not silently
raise limits or drop failed variants. Repeat all four adaptive executions and require
identical parsed results after excluding only the measured runtime object.

## Fixed recipient workloads and comparisons

Use the unchanged scope-aware semantic query evaluator. Queries count observation
contributions, not distinct people. For every variant evaluate all ten declared
categories on four full-area query banks:

| Query cell | Query interval | Queries including all three lags |
| --- | --- | ---: |
| 5 m (256 cells) | 400 ms | 384,000 |
| 5 m (256 cells) | 1,000 ms | 153,600 |
| 10 m (64 cells) | 400 ms | 96,000 |
| 10 m (64 cells) | 1,000 ms | 38,400 |

Deadline lags are 0, 200 and 1,000 ms. The shared interior cohort satisfies
`query_end + 1000 < 20000`: 47 intervals for 400-ms queries and 18 for 1,000-ms
queries. Keep EOF-observable and beyond-EOF censored queries in separate boundary
summaries. A forced final decision at EOF is not evidence of steady online latency.

Only whole public cells and whole source intervals may tile a query. No clipping,
proportional allocation, private count substitution, or inference that an unpublished
area is empty is allowed. An occupied fixed cell can cover a query footprint where
adaptive fine cells leave publicly unknown holes. Retain and explain that outcome;
do not change the query masks or interpret every unknown as numerical inaccuracy.

For each workload, the preregistered named fixed comparator has exactly its cell
side and interval: fixed 5m/400ms, 5m/1000ms, 10m/400ms or 10m/1000ms respectively.
Pair all four adaptive variants with that comparator and compare common/local for
each secondary priority: six paired comparisons per workload, 24 in total. Also
report compact results for every fixed variant. Do not select a different best
baseline retrospectively for each metric or claim a globally optimal fixed grid.

The evaluator's existing per-call budgets remain unchanged: 500,000 expanded
queries, 100,000 public cell records and 20 million tile/query checks. Process
bounded workloads/pairs and store compact summaries, not all 6.72 million rows.

## Measurements, verification and decision gate

Report source retention (observation-weighted), public cells/release events,
contribution-weighted spatial side and semantic loss, actual source-observation
delay to sealing, source-interval duration and interval-start age. Semantic loss
among retained data must be read alongside suppression. Logical simulation-time
sealing and core processing time are separate; neither measures live database or
network delivery latency. Compare retained source classes with released semantic
bins without calling generalized observations missing source observations.

For fixed queries report answer coverage, positive-reference and known-zero strata,
per-category coverage, conditional MAE and absolute-error totals, plus matched
both/only-a/only-b/neither outcomes and intersection errors. Null errors mean no
scorable answer. Truthful exact answers commonly have zero error by construction;
coverage and detail loss remain essential outcomes. No privacy score is inferred
from utility or support compliance.

Independently audit all ten results against original observations: exact counts,
identity unions, truthful complete semantic cuts, support/loss bounds, geometry,
interval retirement, ownership and no duplicate source disclosure. Use indexed raw
support for practical audit cost without altering the mechanism. Test audit mutation
rejection and orchestration fairness, provenance, resource/failure handling and
repeat normalization. Run the relevant core/evaluator regressions. Record code and
source hashes and all failures in the test report.

The review gate is an honest account of where adaptation helps or fails under this
output contract. A sparse-publication/query mismatch may motivate a later explicit
coverage or estimator contract; it is not silently repaired here. Privacy evaluation
then needs its own protected unit, secret, auxiliary knowledge and recipient model.
