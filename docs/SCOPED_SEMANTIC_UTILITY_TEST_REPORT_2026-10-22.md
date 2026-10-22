# Scope-aware semantic utility — results and test report

Date: 2026-10-22. Status: **verified within the declared analytical workload**.

The generalized evaluator and its frozen-study runner are implemented. They answer
fixed category-count queries from common or independently timed public releases.
The aggregator itself, its policies and all source/result artifacts are unchanged.
The [protocol and mathematical contract](SCOPED_SEMANTIC_UTILITY_PROTOCOL_2026-10-22.md)
were saved before this evaluation. This is a retrospective mechanism analysis of
an existing fixture, not an independent traffic or privacy-effectiveness study.

## Main finding

Local windows improve exact answerability under the fixture's regional policy for
some declared queries, while uniform-policy coordination gives equal results.
The benefit is conditional on spatial footprint, query duration and semantic task.
It does not establish general superiority or increased privacy.

The table reports the fixed **interior cohort at zero deadline lag**, using
Temporal First as the secondary preference. The Spatial First secondary gives
identical utility summaries in every bank, lag and cohort in this fixture.

| Policy | Query side | Window | Common answers / all tasks | Local answers / all tasks | Common / local answers to positive-reference tasks |
|---|---:|---:|---:|---:|---:|
| Uniform | 5 m, whole area | 400 ms | 30 / 7,680 | 30 / 7,680 | 9 / 57 and 9 / 57 |
| Uniform | 2.5 m, six regions | 400 ms | 0 / 180 | 0 / 180 | 0 / 48 and 0 / 48 |
| Uniform | 1.25 m, six regions | 400 ms | 180 / 720 | 180 / 720 | 54 / 54 and 54 / 54 |
| Regional | 5 m, whole area | 400 ms | 0 / 7,680 | 0 / 7,680 | 0 / 57 and 0 / 57 |
| Regional | 2.5 m, six regions | 400 ms | 0 / 180 | 21 / 180 | 0 / 48 and 6 / 48 |
| Regional | 1.25 m, six regions | 400 ms | 0 / 720 | 81 / 720 | 0 / 54 and 24 / 54 |
| Regional | 2.5 m, six regions | 1,000 ms | 0 / 60 | 7 / 60 | 0 / 16 and 2 / 16 |

All other declared 1,000-ms interior banks have zero exact answers for both
coordination modes. Lags of 200 and 400 ms do not change these interior results.
Boundary/EOF cohorts are retained separately in the compact data; they must not
be pooled into the table to improve a headline result.

The regional fine-bank improvement is **0% to 11.25% overall coverage** and
**0% to 44.44% coverage of positive-reference tasks**. Of the 81 local answers,
24 have positive reference counts and 57 are legitimate category-zero answers
inside complete public footprints. These are 81 query tasks, not 81 people.
Each footprint/time pair has ten category tasks, some hierarchically related;
they are not independent statistical replications.

Conditional count MAE is zero for every answered/scorable task in the evaluated
outputs. When there are no answers, MAE is null. Zero conditional error is expected
for an exact decoder of truthful whole aggregates and must be read with coverage.
The uniform 5-m bank's 30 answers are only 0.39% of its 7,680 fixed tasks; displaying
only their zero error would conceal nearly all of the workload.

## Why these results occur

The regional common controller releases intervals starting with `[0,600)` and
`[600,1200)`. Neither can be split into a 400-ms query without inventing a within-
interval distribution. Valid fine control cells therefore also miss those exact
400-ms tasks. The local controller releases the control cells on independent
400-ms boundaries while the 2.5-m cyclist cell subsequently publishes shorter
intervals. These records can tile some fixed queries exactly.

For example, cell 12300's local `[0,400)` aggregate contains 12 observations of
four adult pedestrians; `[400,800)` contains 16. The corresponding common intervals
cross the query boundaries. Cell 3168's local records can tile `[0,1000)` and
provide 36 road-user/cyclist observations. Its published `cyclist` category leaves
adult/senior/cargo cyclist counts unresolved, even when the private reference
knows their actual values.

A larger spatial query can remain unknown despite every observed person in it
being released: unpublished empty subcells do not certify zeros to the recipient.
Conversely, a coarser complete aggregate can answer a large-footprint task while
its finer subdivisions remain unknown. This explains why exact coverage is not
monotone in query cell size and why retention alone is insufficient.

The fine 1,000-ms tasks illustrate temporal mismatch: a `[800,1200)` aggregate
cannot supply only `[800,1000)`. Additional deadline allowance cannot repair that
irreversible boundary crossing. The separately published 100-ms cyclist intervals
can fit the 1,000-ms query, explaining the surviving coarse regional answers.

Uniform and regional policies are different requirements, so differences between
those rows are policy sensitivity, not a fair claim of one coordination mechanism
beating another. Within each matched policy, inputs, taxonomy, hard bounds and query
banks are identical. Retention remains 380/380 observations under uniform policies
and 285/380 under regional policies for both coordination modes. This utility gate
has not changed retention or supplied a privacy-risk measurement.

## Implemented contract

- Public-only predictions over immutable, nonoverlapping whole records; local scopes
  constrain ownership but do not fill omitted support. No latest-map reconstruction,
  clipping, proportional allocation or GT-based repair is used.
- Generic declared taxonomy, terminal-domain category reasoning and canonical cell
  IDs/geometry. Unary ancestor chains can answer exactly; straddling categories cannot.
- Fixed masks and half-open intervals with original cadence, explicit unsampled t=0,
  missing reference measurements, zero-sample queries and excluded trailing duration.
- Publication time and deadline lag may be arbitrary integer milliseconds; they
  need not align with the sensor cadence. Source interval boundaries remain aligned.
- Fixed interior cohorts across lags; separate EOF and censored deadlines. Recipient
  coverage is independent of reference availability; error scoring is not.
- Paired observed-query coverage, exclusive answers and errors on the shared scored
  intersection. Compact summaries contain no raw observations or per-query rows.
- Explicit bounded query/record/comparison work and sparse Morton support, avoiding
  expansion of the complete depth-14 grid. Stable canonical source classes are a
  declared benchmark restriction; type-changing simulation is not added here.

The existing `semantic_queries.py` remains byte-for-byte unchanged. Its bounded
legacy workload and historical outputs retain their meaning. The new exact category
count task also differs from the older scalar occupancy estimator's explicit
uniform allocation; the two estimators must be labeled separately in comparisons.

## Verification

| Check | Result |
|---|---|
| New independent evaluator tests | 46 passed |
| New runner/provenance tests | 9 passed |
| Legacy semantic query tests | 19 passed; four-case output equivalence included in new suite |
| Related registered CTest suites | 8/8 passed in 5.69 s; finalized query/runner suites checked again after added geometry cases |
| Actual workload | 48 evaluations and 24 paired comparisons verified |
| Independent published-data audit | 234 cells and 254 semantic bins checked against frozen raw contributions and identity unions |
| Independent query-summary audit | 24 regional workload/mode/lag checks reproduced with explicit spatial/sample sets, without importing the new evaluator |
| Exact repeat | All 75 files, including manifests, byte-identical |
| Original study integrity | All 56 recorded artifact hashes unchanged |

Tests include asynchronous children/parent tilings, missing spatial/time support,
semantic generalization and unary domains, intentionally incorrect public counts,
private-reference independence, exact-deadline/one-millisecond-late publication,
50-ms lags, EOF/censoring, aliases and canonical-type changes, high-depth sparse
queries, overlap and scope failures, bounded expansion, compact output and paired
coverage with unavailable references. Numerical tests reject a meaningful geometry
shift at a large coordinate origin while accepting harmless ordinary rounding.

Review identified and corrected the initial sensor-cadence restriction on publication
times and ensured paired coverage also counts publicly answered tasks with unavailable
GT. Such tasks have no scored error. The runner verifies all 17 selected frozen input
hashes before output, preserves an unverified manifest on failure, and checks source,
implementation and protocol hashes again after execution. Failed runs cannot appear
as verified studies. A bounded taxonomy walk also rejects malformed cyclic input.

No new native aggregator code was introduced. The related regression suites exercise
the existing C++ replay where applicable; a full Simulator/renderer build or normal
MongoDB run was unnecessary for this Python evaluation gate.

## Artifacts and reproduction

Local results: `results/scoped-semantic-utility-2026-10-22`.
Independent repeat: `results/scoped-semantic-utility-2026-10-22-repeat`.
A [56,996-byte aggregate-only summary](SCOPED_SEMANTIC_UTILITY_RESULTS_2026-10-22.json)
is tracked with this report. Generated movement data and full release streams were
not copied into either evaluation directory or Git.

Evaluation manifest SHA-256:

```text
b71a9bd57166f72e3ace224ce890500b83b952eac8eea2058c637e3e9e536d46
```

From the project root:

```bash
ctest --test-dir simulator/build -R '^(scoped_semantic_queries|run_scoped_semantic_utility|semantic_queries)_evaluation$' --output-on-failure
python3 -B tools/evaluation/run_scoped_semantic_utility.py \
  --study results/semantic-cell-local-2026-10-22 \
  --output results/scoped-semantic-utility-demo
```

The output directory must be new. Reproduction requires the existing frozen study;
its generation command is documented in the README. No live Simulator, MongoDB or
browser is required for the evaluation.

## Next step

Run a separately declared comparison on the same existing moving input against
legal fixed grid/window baselines and common-window adaptation. Keep policies,
category tasks, query masks and deadline cohorts matched; account for release-event
costs and explicit minimum duration. Review feasibility and alignment failures
before changing the aggregator to favor the chosen workload. This mechanism fixture
is sufficient for acceptance, but cannot establish realistic urban utility or
privacy effectiveness. The protected-secret/recipient model remains a subsequent gate.
