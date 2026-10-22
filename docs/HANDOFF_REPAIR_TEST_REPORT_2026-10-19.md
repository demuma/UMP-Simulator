# Handoff repair test report

Date: 2026-10-19. Repository: `/Users/maxdemu/Developer/UMP-Simulator`.
The [implementation and effectiveness report](HANDOFF_REPAIR_REPORT_2026-10-19.md) records
behavior and scientific results; the [predeclared protocol](HANDOFF_REPAIR_PROTOCOL_2026-10-19.md)
separates development witnesses from the independent privacy assessment.

## Changed files and responsibilities

| File | Change |
|---|---|
| `simulator/src/CellLocalAggregation.cpp` and matching header | Endpoint-consistent future intents, redundant-plan recognition, contained-plan supersession committed with ACK |
| `simulator/tests/CoordinationRegressionTests.cpp` | Six new public-API regression functions; automatic witness and same-endpoint failure/retry comparison |
| `tools/evaluation/run_privacy_robustness.py` | Optional frozen previous-study reference, separate old/new attacks, exact shared-source ages and matched-query repair contrasts |
| `tools/evaluation/test_privacy_repair.py` | Eight provenance, accounting and real integration tests, including optional nonlinear attacks |
| `simulator/CMakeLists.txt` | Register the new Python suite with the existing evaluation tests |
| README, TO-DO and linked English documentation | Updated contract, evidence, limitations and research order |

Existing user changes in `UMP-Simulator.code-workspace`, `simulator/config.yaml` and
`simulator/src/AgentBasedSensor.cpp` were preserved. The default simulation configuration
was not run. Production sensor behavior, MongoDB data, common-window controller and
policy thresholds were not changed by this repair. No commit or push was made.

## Build and regression results

- Full Release build: Simulator, AggregationReplay and all enabled regression targets succeeded.
- **37/37 CTest suites passed**, elapsed 11.42 s.
- Pinned complete Python environment: **236/236 methods passed, zero skips**, elapsed 42.184 s.
  This includes the legacy runner path and same-executable old/new identity controls.
- **27 focused coordination functions passed**, including six new functions. The same new
  suite against the frozen previous core gives **five expected failures and 22 passing
  guards/baselines**. The failures establish that the new tests detect the previous defects.
- Fresh **AddressSanitizer and UndefinedBehaviorSanitizer** builds pass all 27 focused
  functions and **240 seeded stress scenarios**, with no findings. LeakSanitizer was
  disabled. Strict `-Wall -Wextra -Wpedantic -Werror` suppresses only the pre-existing
  missing-field-initializer warning. All 48 frozen source/header/test hashes match.
- Canonical notation/LaTeX freshness check passes (v1.4). Task-owned source whitespace
  checks pass; the pre-existing user whitespace edit was left untouched.

The new cases cover mixed-depth descendants, measured-empty siblings, different deadlines,
contained/enclosing/unrelated requests, failed-policy/incomplete-evidence atomicity,
identical retry, expired retry, deferred intent continuation and exact observation conservation.
They do not claim automatic crash recovery or arbitrary globally optimal coordination.

The new Python tests verify old-study completeness and hash links, path traversal rejection
before output creation, no deserialization of old attack models, half-open support, duplicate
support rejection and same-observation ages that avoid suppression-selection bias. Real tiny
integration runs refit old/new attacks independently. Optional nonlinear integration completes
112 audited replays, 36 separate models and 72 cohort assessments; same-binary repair deltas
are zero. A development run correctly rejected completion when source changed concurrently;
the source-freeze guard was retained and the final stable runs passed.

## Commands

Run from the repository root:

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release
cmake --build simulator/build -j 4
ctest --test-dir simulator/build --output-on-failure -j 4
LOKY_MAX_CPU_COUNT=1 MPLCONFIGDIR=/private/tmp/ump-robustness-mpl \
  UMP_REPLAY_BINARY="$PWD/simulator/build/AggregationReplay" \
  /private/tmp/ump-privacy-robustness-venv/bin/python -B -m unittest discover \
  -s tools/evaluation -p 'test_*.py'
python3 -B tools/export_notation.py --check
```

The pinned optional environment and package versions are documented in the previous
[robustness test report](PRIVACY_ROBUSTNESS_TEST_REPORT_2026-10-19.md). CTest may skip optional
Python dependencies when using a different interpreter; the complete run above covers them.
Sanitizer commands, frozen source, old failing cases and logs are preserved under
`results/evaluation/2026-10-19/handoff-repair-verification-v1/sanitizer/`.

## Same-input development matrix

The original 30-case matrix was rerun without selecting cases or changing numerical policies.
All **270 independent audits**, **120 deterministic repeats**, and **210 unchanged reference
outputs** pass. Every original input/policy/artifact hash is checked by the strict comparator.

Across 60 local before/after pairs, all **126466 retained source points** are shared; none are
gained or lost. Retention, query coverage and matched-query MAE are unchanged in every pair.
Four mixed-density Temporal First cases reduce same-point mean simulated age by 0.3885,
1.1106, 5.7637 and 3.6481 ms (seeds 20–23); other cases and all p95 ages are unchanged.
This matrix demonstrates no observed regression and a small freshness improvement. The
separate 42-observation witness demonstrates the repaired retention defect.

Private bundles are `coordination-handoff-repair-19-26-v1`,
`coordination-handoff-repair-comparison-v1` and `coordination-handoff-repair-verification-v1`
under `results/evaluation/2026-10-19/`.

## Independent privacy assessment

The seed20261022 assessment completed **2912 audited replays**, **264236 released cells**,
**six adaptive deterministic repeats**, **three unchanged shared-mechanism controls**, and
**36 fitted attacks / 72 cohort assessments**. Both original and repaired executables were
frozen; all source/policy/data integrity checks pass. The old executable is reused only as
an aggregation mechanism. Old trained models are not loaded.

Independent utility/provenance verification uses raw source coordinates and rectangle
containment, separately from the production prefix/history/evaluation helpers:

- 512 held-out world/priority pairs and 1024 raw local results independently reconstructed.
- 123924 published-cell contribution and distinct-identity counts checked.
- Full lost/gained/shared observation partitions, age histograms and matched-query MAE
  agree with the primary report; nonzero losses and individual regressions remain explicit.
- All 7173 artifact hashes (4918992723 bytes), 2912 command/result provenance records,
  229 frozen source snapshots and 624 dataset files verified.
- All 2912 independent-oracle records streamed and confirmed valid; the large oracle file
  was not loaded whole. Fresh-data fingerprints are disjoint from the previous study.
- Elapsed verification: 22.44 s. Evidence: `utility-independent.json` and the archived
  `verify-utility-independent.py` in the separate verification bundle.

Independent attack verification uses direct score-pair/rank calculations, reconstructed
public feature vectors and separately recomputed bootstrap samples:

- **282482 assertions, zero failures**, elapsed 20.86 s.
- All 7488 public-only feature vectors and 416 auxiliary profiles reconstructed.
- 18 logistic numerical CAL thresholds and 4608 logistic TEST predictions reconstructed
  from saved JSON weights and fresh source/feature rows.
- 36 model metadata files and 18 HGB artifact hashes checked without deserialization.
- All 72 cohort and 288 scenario assessments, 360 bootstrap metric intervals and 32
  paired common/reference AUC contrasts reproduced, including all unfavorable results.
- HGB numerical calibration optimality was not independently replayed: CAL score rows
  are not stored separately. Hashes, metadata and the identical frozen threshold in both
  test cohorts are verified. Persisting CAL scores is a future audit improvement.

No formal privacy guarantee, statistical equivalence, online latency guarantee or general
Pareto improvement follows. The actual result is higher pooled retention/coverage, small
matched-error costs, a TF shared-age increase, and no demonstrated privacy improvement.
Two shifted SF/exact-knowledge comparisons show higher attack AUC with pointwise intervals
excluding zero. All intervals and limitations remain in the main report.

The PNG and SVG evidence figure were generated from the completed report; the PNG was
visually inspected, a legend overlap corrected, then inspected again. Figure provenance
and the exact plotting script are stored with verification. No experimental artifact changed.

## Evidence locations

Under `results/evaluation/2026-10-19/`:

- `privacy-handoff-repair-dataset-20261022`: newly generated source groups and immutable manifest.
- `privacy-handoff-repair-study-20261022-v1`: completed frozen protocol, executable pair,
  raw/public output, models, predictions, primary audit and report.
- `handoff-repair-verification-v1`: test/sanitizer logs, independent utility and attack
  verifiers/results, figure script/provenance and primary execution log.
- The three coordination comparison bundles listed above preserve the development evidence.

These private artifacts remain Git-ignored. README and TO-DO link the maintained English
report, test report, protocol and exported aggregate figures.
