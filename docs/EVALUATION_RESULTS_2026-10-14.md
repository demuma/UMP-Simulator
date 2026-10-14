# First controlled aggregation comparisons

Date: 2026-10-14. These are reproducible descriptive pilots, not a completed benchmark or
an empirical privacy guarantee. Methods: [CONTROLLED_EVALUATION.md](CONTROLLED_EVALUATION.md),
[METRICS.md](METRICS.md), and [PRIVACY_EVALUATION.md](PRIVACY_EVALUATION.md).

## What was implemented

The simulator already computed nine online quantities: observation contributions, distinct
road users, mean sampled occupancy, cell side, cell area, window duration, age at evaluation,
post-window delay and measured-sample fraction. This work adds offline fixed-query occupancy
MAE, answered/scored-query coverage, reference availability, resolution/age distributions,
contribution retention and a scoped deterministic neighbouring-output comparison.

The new CLI reuses the actual aggregation, shared-history, policy-tree, spatial selection,
temporal adaptation and publication-coordinator cores. Fixed baselines obey the same policy
and suppress failing fixed cells; they do not silently adapt. No renderer or MongoDB is
required for replay. The separate capture adapter uses a fresh UUID database and verifies
raw GT against raw AGBS before freezing its observations.

The live visualization was the first of the agreed three work items. The second and third
now have this working evaluation slice. A realistic attack study and broad comparative
claims are still pending.

## Common setup

- Coverage: 80 m by 80 m; finest depth 6 (1.25-m cells); 100-ms sampling, t=0 excluded.
- Query: all 10-m reference cells over full 1-second intervals. No reference coarsening;
  missing public support is unknown. The 8-second cases have 512 queries and 100% reference
  availability. Conditional MAE uses only answered queries; subsets differ by configuration.
- Root requirements: at least 2 distinct road users; side length 1.25–40 m; maximum window
  and evaluation age 1000 ms. The northwestern 40-m square inherits a type minimum of 5;
  its instance minimum of 2 cannot weaken that requirement. These are illustrative rules,
  not calibrated anonymity guarantees.
- Adaptive base window 400 ms, extension 100 ms, maximum 1000 ms; min depth 1; 4096 spatial
  evaluations, 16 temporal evaluations. Common windows and private final snapshots are used.
- History: 2000 ms, 32 bins, 100000 observations, 16000000 identity bytes, 128 bucket records.
- Seven modes: 10/20-m fixed cells crossed with 400/1000-ms windows, spatial-only,
  Temporal First (space first), Spatial First (time first). Input and policy files are copied
  and hashed. Exact counts/unions, policy passes and nonoverlapping support are checked.
- Privacy: remove each of the first N lexically sorted observed IDs from the same stream and
  replay from the beginning. This target selection is explicit, not representative sampling.
  Compare recipient-visible counts, geometry, intervals, logical release time and policy IDs.
  The observer knows every background trajectory and the target trace exactly.

## Actual simulator capture

One eight-second headless run of the maintained temporal example used 200 road users.
The verifier checked 160 GT frames at 50 ms, 79 AGBS frames at 100–7900 ms, 32000 GT rows,
15530 occupied AGBS cell records and 15800 observation contributions. Every sensor timestamp,
cell ID, geometry, total count and type count matched the GT-derived observation stream.
There were no missing sensor frames. The fresh capture database was removed only after the
raw exports, frozen input and proof were safely written. Existing databases were untouched.

| Configuration | Conditional MAE (road users) | Answered queries | Retained observations | Mean sealing age (ms) | Changed target pairs |
|---|---:|---:|---:|---:|---:|
| Fixed 10 m / 400 ms | 0.0238 | 56.84% | 81.78% | 400 | 2/3 |
| Fixed 10 m / 1000 ms | 0.0000 | 65.43% | 83.93% | 1000 | 2/3 |
| Fixed 20 m / 400 ms | 1.3396 | 100.00% | 100.00% | 400 | 3/3 |
| Fixed 20 m / 1000 ms | 1.3396 | 100.00% | 100.00% | 1000 | 3/3 |
| Spatial only | 0.9776 | 86.13% | 100.00% | 400 | 3/3 |
| Temporal First | 0.9776 | 86.13% | 100.00% | 400 | 3/3 |
| Spatial First | 0.9073 | 92.38% | 100.00% | 1000 | 3/3 |

The adaptive modes retained all observations in this capture, yet their query coverage is
below 100%: fine sparse footprints need not cover an entire 10-m query cell. The 20-m fixed
baseline covers the full domain by releasing occupied coarse cells, at larger numerical
error. The 10-m/1000-ms baseline aligns with the query, explaining its approximately zero
conditional error; the unanswered 34.57% of queries must still be considered.

Temporal First found a spatial solution at 400 ms throughout this run. Spatial First used
1000-ms windows, improving coverage/error here at the cost of greater sealing age. Mean age
is measured from window start at simulated sealing, not from an arbitrary observation and
not as actual network delivery latency. The age/error trade-off depends on the chosen query.

There are 251 queries answered by all seven configurations. On this common subset, spatial
only/Temporal First MAE is 0.8321, Spatial First 0.7810, fixed 20 m/400 ms 1.3833, and fixed
10 m/1000 ms approximately zero. This additional comparison helps separate differences in
answered subsets; it does not remove the need to report full-domain coverage.

For the three tested targets, both 10-m fixed baselines changed two public transcripts;
the other five configurations changed all three. The corresponding perfect-background
balanced successes (5/6 and 1) are mathematically derived from deterministic equality,
not trained-classifier accuracies. No privacy improvement of adaptation is established.
A matching transcript for one suppressed target is not a guarantee for other targets or
other forms of knowledge. Generalization and population confidence intervals are unwarranted.

The local figure is available as PNG, SVG and PDF in
`results/evaluation/2026-10-14/simulator/comparison.*`.

## Heterogeneous deterministic fixture

This hand-inspectable eight-second fixture contains 36 stable road-user identities in
clusters of different densities, deterministic cross-cell motion and a fully empty second.
It is a mechanism test rather than a realistic mobility model.

| Configuration | Conditional MAE (road users) | Answered queries | Retained observations | Mean sealing age (ms) | Changed target pairs |
|---|---:|---:|---:|---:|---:|
| Fixed 10 m / 400 ms | 0.0820 | 6.45% | 68.44% | 400 | 3/3 |
| Fixed 10 m / 1000 ms | 0.0000 | 8.79% | 72.42% | 1000 | 3/3 |
| Fixed 20 m / 400 ms | 1.5828 | 32.81% | 96.54% | 400 | 3/3 |
| Fixed 20 m / 1000 ms | 1.5323 | 34.38% | 96.98% | 1000 | 3/3 |
| Spatial only | 1.3547 | 14.45% | 97.22% | 400 | 3/3 |
| Temporal First | 1.2665 | 23.24% | 97.22% | 900 | 3/3 |
| Spatial First | 1.2665 | 23.24% | 97.22% | 900 | 3/3 |

Both adaptive priorities produce the same final public result here. An isolated branch
cannot reach the minimum support even at its maximum spatial extent; the common-window
coordination keeps extending before its final suppression. This exposes a limitation of
the current shared-window model: one unresolved branch can delay otherwise feasible areas.
It motivates, but does not yet implement, independent-window and selective-fallback studies.
Only 16 queries have scored support common to all configurations. At the stated strongest
knowledge level, all three tested targets changed the output for every configuration.

## Analytical handover fixture

Two pairs of identities alternate every 400 ms at two fixed finest cells within one 10-m
common ancestor. The first 400-ms window has one identity per fine cell but two across that
common ancestor. This
fixture intentionally isolates the action order; it makes no continuous-motion claim.

| Configuration | Conditional MAE (road users) | Answered queries | Retained observations | Mean sealing age (ms) | Changed target pairs |
|---|---:|---:|---:|---:|---:|
| Fixed 10 m / 400 ms | 0.0000 | 1.56% | 100.00% | 400 | 4/4 |
| Fixed 10 m / 1000 ms | 0.0000 | 1.56% | 100.00% | 1000 | 4/4 |
| Fixed 20 m / 400 ms | 0.7500 | 6.25% | 100.00% | 400 | 4/4 |
| Fixed 20 m / 1000 ms | 0.7500 | 6.25% | 100.00% | 1000 | 4/4 |
| Spatial only | 0.0000 | 1.56% | 100.00% | 400 | 4/4 |
| Temporal First | 0.0000 | 1.56% | 100.00% | 400 | 4/4 |
| Spatial First | undefined | 0.00% | 100.00% | 400 | 4/4 |

Temporal First's first release covers the common ancestor at 400 ms. Spatial First waits to 500 ms,
then releases two fine cells after the identity handover supplies the required support.
Later windows and the truncated tail differ, so the overall mean age happens to be 400 ms
for both; the full interval sequences, not that mean alone, show the distinction.

Spatial First retains every observation but answers no complete 10-m/1-s query because
most of each reference cell has no public zero-support certificate. Its MAE is therefore
undefined, not zero. This is an explicit consequence of the chosen application and sparse
publication semantics. The other scenarios must not be ranked using this case alone.

## Evidence and reproducibility

All 19 CTest suites passed, including the existing MongoDB integration tests, replay-core
regressions and the new occupancy, privacy, comparison and capture-adapter Python tests.
The Python modules contain 44 tests in total. Comparison integration runs all seven modes
twice and verifies equality apart from runtime. The replay core tests additionally distinguish
Temporal First/Spatial First, parent unions, regional strictness, missing/unavailable input,
empty intervals, truncation, invalid configuration, conservation and no-overwrite output.

The standalone figure was rendered and visually inspected. The main configuration,
workspace file and pre-existing AgentBasedSensor edit were preserved. No live GUI behavior
was changed in this work.

Each local result directory contains frozen observations/policy, per-mode private diagnostic
results, public release projections, occupancy queries, summary CSV/JSON, counterfactual
inputs and outputs, and a provenance manifest. Manifests record SHA-256 of input, policy,
binary and relevant sources, repository revision plus dirty state, and exact commands.
Core processing time excludes validation, file I/O, database persistence and renderer work;
it is not an end-to-end real-time benchmark. Raw/private artifacts stay under ignored
`results/`, rather than becoming a public dataset.

Input SHA-256 values:

- Heterogeneous fixture: `317a6053e44cd01bf71b8bc0a84e2e9b09a130392d2ef434ba05c9c751db2012`
- Handover fixture: `1f81ef9bfd974437ab8c9063a1b66ddff4708cc7081e068b2d2a7e0433f4269d`
- Simulator capture: `623a9974bfe307979874cfcbc6fedf302522e905615abf0fb534f14e19cf85f0`

The capture's Mongo metadata provides the authoritative relative-time origin. The timezone-free
configured datetime and its UTC interpretation need a separate DST/timezone audit (D02);
this did not affect the verified relative GT/AGBS alignment or replay cadence.

## What remains before dissertation-level claims

Choose explicit empty-support publication semantics for the intended application; study
thresholds, regional caps, density/motion regimes and infeasible policies over independent
runs; design and validate a realistic attacker with separated training/testing; and add
other utility tasks only when their application is defined. Formalize release soundness
separately from search completeness or optimality. The current greedy/common-window
algorithm can suppress support despite alternatives a future coordinator might find.
Independent sibling windows, selective suppression, other publication models, multiple
recipient views and preemptive caching comparisons remain separate implementation work.
