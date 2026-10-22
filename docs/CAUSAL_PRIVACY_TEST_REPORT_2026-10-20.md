# Causal privacy and deadline utility: test report

Date: 2026-10-20. Repository: `/Users/maxdemu/Developer/UMP-Simulator`.

The causal-prefix extension passes the complete regression suite and the independent
source, score and deadline-utility audits described below. These checks establish
consistency with the declared evaluation contract. They do not establish a general
privacy improvement, an optimal attack, or an online delivery guarantee. Scientific
findings belong in the [results report](CAUSAL_PRIVACY_REPORT_2026-10-20.md); the
[predeclared protocol](CAUSAL_PRIVACY_PROTOCOL_2026-10-20.md) and
[implementation description](CAUSAL_PRIVACY_IMPLEMENTATION.md) define the assessed behavior.

## Scope and frozen execution

This change adds causal recipient views, acquisition-aware candidate knowledge,
checkpoint-specific attacks with one repeated-decision calibration, and occupancy
queries evaluated at their own deadlines. It also factors the existing feature
arithmetic into a reusable private helper so a complete validated transcript can be
reused across checkpoints. The aggregation controller, sensor algorithms, numerical
policy settings and recipient schema are unchanged by this evaluation extension.

The main new suites are `test_causal_privacy.py`, `test_online_occupancy.py` and
`test_run_privacy_prefix_study.py`. CMake registers all three alongside the existing
sensor, frame, aggregation, publication, policy, replay, evaluation and coordination
regressions. Source and protocol hashes are frozen before primary execution, copied
into the private bundles, and checked again before a run may complete.

The fresh dataset uses seed **20261023** and 208 independent paired groups: 48 base
TRAIN, 32 base CAL, 64 base TEST and 64 background-count-shift TEST. Every group has
one IN and one OUT world. The generator's background and paired-world fingerprints
have zero overlap with the previous seed20261021 and seed20261022 datasets, as recorded
in `pre-run-inputs.json`. This check addresses reuse of generated groups; it is not a
claim that the inherited scenario generator is a new population model.

The source bundle contains complete 16-second executions. The prefix analysis filters
these completed immutable histories by actual logical sealing time; it does not
truncate/re-execute the mechanism at each checkpoint or manufacture intermediate EOF
releases. The six checkpoints are 1000, 2000, 4000, 8000, 12000 and 16000 ms, with the
last explicitly treated as EOF.

## Regression results

| Check | Result | Recorded elapsed time |
|---|---|---:|
| Full CTest run | **40/40 suites passed** | 17.24 s |
| Complete Python discovery in the pinned optional environment | **285/285 methods passed, zero skips** | 54.530 s |
| Newly added Python methods | **49 passed:** 20 causal views, 19 deadline utility, 10 prefix-runner integration | Included above |
| Focused causal/legacy-feature refactor check | **48 methods passed**, unchanged feature arithmetic AST | 0.117 s |
| Canonical notation export and LaTeX compilation | Passed; three pre-existing overfull-box warnings remain | See notation log |

The pinned complete run uses Python **3.13.2**, scikit-learn **1.9.1**, NumPy **2.5.4**,
SciPy **1.18.1**, joblib **1.6.0** and threadpoolctl **3.7.0**. The exact optional
requirements remain in `tools/evaluation/requirements-robustness-lock.txt`. CTest's
configured interpreter may omit optional dependency paths in another environment;
the separate 285-method run exercises them with the pinned dependencies installed.

The 20 causal-view methods cover independent per-timestamp Bernoulli sampling,
exact/noisy selection invariance, future-trace extension, acquisition gating under
negative timestamp jitter, bounded noise, causal deduplication, removal of private
provenance, immutable inputs and rejection of unknown channels. Public-view cases
verify whole-record admission at the exact seal, recent arrival intervals
`(checkpoint-1000, checkpoint]`, normalized retained aliases, future-record/payload
noninterference, known fixed-horizon normalization, legacy final-prefix equivalence,
and exact 9/40/71-feature nesting. Batch entry points must validate the complete input
once, reject malformed future records, match the strict entry points, and return no
mutable aliases to their inputs or other views.

The 19 deadline methods cover exact seal/deadline boundaries, delayed aggregates,
spatial pieces with different seals, partial spatial or temporal support, explicit
zero versus null/absent support, and aggregates crossing a query boundary. They verify
the original occupancy normalization and contribution accounting, the first interval's
nine discrete samples versus later ten-sample intervals, unavailable reference data,
whole-release filtering equivalence, monotone coverage under relaxed deadlines, fixed
denominators, separate EOF/right-censoring, and checkpoint summaries that exclude
not-yet-due queries and never backfill a missed deadline. Compact pooling, matched
query intersections, JSON-finite output, immutability and malformed input rejection
are also tested.

The 10 runner methods cover one CAL threshold on maximum checkpoint scores, first
crossings counted once, complete paired score paths, source/public/report provenance,
invalid schedules and dependency failures before output creation, TRAIN/CAL/TEST
isolation, auxiliary/control invariance, compact utility integration, source mutation
and failed-manifest handling. A real tiny HGB integration confirms that checkpoint
CAL scores are persisted without loading previous models or invoking the source
executable from the prefix analysis.

## Feature arithmetic and batch equivalence

`batch-implementation-validation.json` records that the abstract syntax tree of the
legacy feature arithmetic is identical before and after extraction into its private
helper. The change shares validation and subsets; it does not change the arithmetic
or its summation order. The strict public entry points retain full input validation.

A TRAIN-only dense case from the previous seed20261022 source was used for the
performance/equivalence check, before examining the fresh primary outcomes. Across
seven streams, two knowledge profiles, six checkpoints and three representations,
**252 feature vectors were bit-exact against the strict reference path**. The recorded
aggregate extraction time fell from **2.231713456 s** to **0.206882081 s**, a
**10.787-fold** improvement for that one workload. This is an offline feature-extraction
measurement, substantially influenced by the exact-count control; it is not simulator
speedup, controller processing latency, transport performance or a general benchmark.

Evidence is preserved in `batch-implementation-validation.json` and
`batch-performance-train-only.json`. `causal-batch-benchmark.json` contains the same
benchmark result and must not be counted as a second independent measurement.

## Completed primary bundles and numerical fits

The complete source study passes **2080 independent policy/ownership audits**, covering
208 groups × two worlds × five mechanisms. It contains **174607 mechanism-released
cells** and four successful deterministic adaptive repeats. Its 28 legacy final-history
attack fits are ancillary to the fixed causal-prefix experiment.

The primary prefix analysis contains **360 checkpoint models**: 180 logistic and
180 histogram-gradient-boosting fits. They form **60 bounded attack strategies**,
each with six checkpoint-specific classifiers and one frozen maximum-score CAL
threshold. There are 56 public-view strategies and four auxiliary-only strategies,
120 TEST-cohort assessments and 720 checkpoint assessments. The number 60 denotes
strategies, not the number of individual candidate score paths or independent subjects.

All **180 logistic fits** meet their recorded numerical convergence criterion in
**1–155 iterations**. HGB uses its fixed 64 boosting iterations with early stopping
disabled; no optimized-convergence claim is made for those fits. Models are fitted
on base TRAIN only; CAL sets one empirical ever-positive operating point; the two
independent TEST cohorts use the frozen models and thresholds.

The source study took **529.55 s** and the prefix analysis **222.39 s** in the recorded
offline executions. These totals include replay/analysis, validation, fitting,
uncertainty calculations and artifact handling as applicable. They do not measure
per-step controller latency, real-time factor, network delay or recipient receipt.
The wall-clock observations must not be converted into a live-service guarantee.

## Independent source and public-channel audit

`independent-source-fullcheck.py` and its separate verifier use standard-library
geometry, source coordinates, sampling times and identity sets. They import no
production selector, occupancy evaluator, causal-view implementation or public-export
helper. The complete-source pass checks:

| Evidence | Independently checked scope |
|---|---:|
| Source artifact files and manifest links | **5378 files** |
| Unique independent-oracle records and raw/public pairs | **2080** of each |
| Source worlds | **416** across all 208 groups |
| Public cells, including explicit exact-count controls | **4407823** |
| Deterministic assertions in this pass | **48239665**; zero failures |
| Elapsed verification time | **55.16 s** |

Every raw/public pair is compared through an independently reconstructed recipient
allowlist: normalized release identifiers, timing, policy/model identifiers and sorted
public cells. Private result fields do not become predictions. Finest source cell
IDs are independently derived from XY coordinates; released contribution counts,
distinct-identity unions and mean occupancies are recomputed from source samples.
Decoded public geometry and nonoverlap at every scheduled sample are checked, along
with input/accounted totals and the declared exact-count/no-output controls.

Of the 4407823 cells, **4233216** belong to the deliberately unprotected full-grid
exact-count control and **174607** to the five mechanisms. Thus these checks include
many explicit control zeros; the total is neither a unique-person count nor a count
of privacy-preserving releases. Existing oracle audit validity is checked and linked
to raw outputs; the separate XY pass independently reconstructs their public numerical
counts and ownership support, rather than implementing another complete policy engine.

## Independent deadline utility and matched errors

`independent-deadline-fullcheck.py` separately reconstructs public occupancy using
rectangle intersections, source XY positions and discrete sample times. A released
aggregate is admitted whole at its seal; no count or interval is clipped. A query
requires complete public spatial support at every scheduled sample, and readiness is
the latest required seal. Null or missing output remains unknown, while an explicit
released zero supplies valid support.

The complete pass covers **256 held-out worlds × seven streams × four deadline lags**,
with identical preselected 10 m/1 s reference queries. The strict primary rule
`query.end + 1000 < 16000` yields **896 queries per world**, or **114688 per TEST cohort,
stream and lag**. Queries ending at 15000/16000 ms are checked separately; deadlines
beyond the horizon are censored instead of becoming misses.

The verifier reconstructed **7340032 query/deadline projections**: 6422528 primary
and 917504 boundary projections. It also reconstructed **2097152 matched-query
projections** for common/local comparisons under both priorities, requiring identical
source-query identities and intersecting the actually scored support. These counts
reuse fixed queries across lags and mechanisms; they are not independent experimental
replications.

All **282768 stored per-world and pooled summary scalar comparisons** agree, including
coverage, conditional error, error sums, source/reference contribution totals,
reconstructed contribution equivalents, matched-error denominators and EOF censoring.
Pooling uses counts and error sums, not averages of conditional MAEs or coverage ratios.
The complete pass recorded **50624962 actual assertions**, zero failures, in **68.20 s**.
The reconstruction counters above are kept separate from assertion counts. This pass
also repeats the complete source/hash checks; its assertion total and the earlier
source-pass total must not be added as disjoint evidence.

Descriptive TEST IN population summaries are saved by distribution and scenario:
distinct recorded road users, contributions, mean users per measured sample and source
types. Handover's large whole-horizon identity count reflects turnover rather than
simultaneous density. The recipient schema exposes no per-type count field; these
source-type descriptions are private context, not additional public attack features.

## Independent score, calibration and uncertainty audit

`independent-causal-scores.py` performs a separate audit without deserializing models
or refitting estimators. The full completed-bundle audit passes **653770 assertions**,
zero failures, in **38.75 s**. Its scope includes:

| Check | Count |
|---|---:|
| Prefix artifact hashes | 879 |
| Declared consumed-source hashes / frozen snapshot hashes | 3670 / 121 |
| Saved feature blocks / nested source profiles | 180 / 2496 |
| First-checkpoint same-information checks | 5824 |
| Checkpoint model identities / maximum-score calibrations | 360 / 60 |
| Logistic CAL probabilities / TEST probabilities reconstructed | 11520 / 46080 |
| HGB model hashes checked | 180 |
| TEST-cohort / checkpoint assessments | 120 / 720 |
| Bootstrap assessments / paired contrasts reproduced | 840 / 168 |

The audit checks source/world feature masks, exact auxiliary/recent/history nesting,
paired score-path identities, checkpoint-model/CAL mappings and TRAIN-only logistic
scaling. Logistic probabilities are independently calculated from saved JSON
coefficients and independently reconstructed scaling. It recomputes maximum-over-look
CAL threshold selection, frozen use across both cohorts, tie-aware AUC, confusion
statistics, first-crossing CDFs and cumulative alarm monotonicity. Scenario-stratified
paired-group bootstrap intervals and paired max-score AUC contrasts are reproduced.

Persisting HGB CAL scores closes the earlier missing numerical-calibration audit:
threshold optimality and all downstream HGB score-based statistics can now be checked.
**HGB estimator inference itself is not independently reproduced.** Its saved score
paths, metadata and fresh-model artifact hashes are checked; the verifier does not
load the serialized estimator. It also does not independently regenerate every public
feature or noisy auxiliary event. Those contracts are covered by focused regressions,
strict/batch equivalence and selected independent checks, not by a second complete
feature-generation implementation. Logistic optimizer fitting is likewise not rerun
by the score verifier.

At 1000 ms recent and cumulative public records contain the same information. The
5824 equality checks retain this fact explicitly: the history representation duplicates
its recent block there. A fitted classifier can nevertheless change because dimension
and regularization change. Passing the audit therefore supports the declared bounded
representation/learner comparison; it does not isolate the information-theoretic
value of memory or prove an optimal attack's behavior.

## Notation, figures and preserved workspace checks

The canonical notation export freshness check passes. A `pdflatex` check of the
exported equations completes successfully and produces a three-page PDF. The log
retains **three pre-existing overfull-box warnings**; this is a successful compilation,
not a zero-warning layout claim. The new equations are defined with their evaluation
scope in [notation section 23](TERMINOLOGY_AND_NOTATION.md#23-causal-public-views-repeated-alarms-and-deadline-utility).

Four PNG/SVG figure pairs are derived from the completed report, with report/protocol,
plot-script and image hashes in `plot-causal-prefix-v2.json`. The figures were visually
checked; the previous rendering and its provenance remain in the private verification
directory. Plotting changes do not alter the completed primary bundles.

Final post-work verification confirms all seven protected/frozen hashes match their
pre-run values: the user-owned workspace file, simulation configuration and ABS source,
the replay binary, controller source/header, and predeclared research protocol. All 48
current evaluation source files represented in the frozen prefix bundle remain byte-identical
to that bundle. Both completed report hashes still match their manifests. All 190 local
file links in the reviewed documentation resolve; scoped whitespace and notation freshness
checks pass. The root review also inspected all four final PNG layouts, and a separate
read-only review checked all 144 displayed history/coverage entries, source inventories,
main numerical claims and seven provenance hashes in the results report.

HEAD remains `4f41865c80c5874b8134c247f6e18b42234ef6a4`; this work was not committed or
pushed. Existing unrelated/user changes were preserved. Research bundles remain ignored
by Git. The known pre-existing whitespace in the user's ABS edit was not rewritten.
No primary experiment invokes the default live configuration or uses a database-clearing
path. Final checks are recorded in `final-repository-review.json`.

## Reproduction and evidence

From the repository root, using the existing built Release targets:

```sh
ctest --test-dir simulator/build --output-on-failure -j 4
LOKY_MAX_CPU_COUNT=1 MPLCONFIGDIR=/private/tmp/ump-robustness-mpl \
  UMP_REPLAY_BINARY="$PWD/simulator/build/AggregationReplay" \
  /private/tmp/ump-privacy-robustness-venv/bin/python -B -m unittest discover \
  -s tools/evaluation -p 'test_*.py'
python3 -B tools/export_notation.py --check
```

Primary-run commands and dependency setup are linked from the
[implementation description](CAUSAL_PRIVACY_IMPLEMENTATION.md). A new primary run
must use fresh output directories; completed source and analysis bundles are not
overwritten. All raw inputs, labels, models and independent-verification details
remain private Git-ignored research artifacts under `results/evaluation/2026-10-20/`:

- `privacy-prefix-dataset-20261023`: immutable paired source data and generation manifest.
- `privacy-prefix-source-study-20261023-v1`: frozen full-horizon mechanism/source audit bundle.
- `privacy-prefix-study-20261023-v1`: frozen causal protocol, features, models, CAL/TEST score
  paths, compact utility summaries and completed primary report.
- `privacy-prefix-verification-v1`: complete regression logs, pre-run hashes, arithmetic/
  batch evidence, independent source/score/deadline scripts and JSON reports, execution
  timings, notation compilation log and figure provenance.

The checks support reproducibility and compliance with this bounded synthetic
membership/deadline experiment. Real maps and sensitive visits, unrestricted trajectory
attacks, person-level formal anonymity, differential privacy, population FPR guarantees,
training-uncertainty coverage and live delivery performance remain outside this report.
