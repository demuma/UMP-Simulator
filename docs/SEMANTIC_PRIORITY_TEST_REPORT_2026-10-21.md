# Semantic candidate-choice study: implementation test report

Date: 2026-10-21. Scope: bounded E07/A08 decision-order inspection and fixed receiver queries.
Result: acceptance gate passed. Production C++ selection and release behavior are unchanged.

## Implemented components

- `semantic_tradeoffs.py`: independent raw-data reference for the SAME actual interval,
  evaluation time and parent12/four-leaf domain. Enumerates complete semantic antichains,
  parent-or-child spatial cuts and whole-cell suppression under scalar/regional/semantic
  constraints. Missing evidence fails closed; enumeration budgets never truncate silently.
- `semantic_queries.py`: a separate receiver-only fixed exact class-count evaluator.
  It validates the public structure, geometry, category partitions, provenance and
  nonoverlapping support, preserves unknowns, and separates interior/boundary/censored
  deadline cohorts. Private observations supply reference/error only.
- `run_semantic_priority_study.py`: frozen paired inputs, 360 predeclared configurations,
  independent scalar validation, candidate-membership verification, fixed query banks,
  12 exact scientific repeats and private manifests/artifacts. No MongoDB dependency.

The [protocol](SEMANTIC_PRIORITY_PROTOCOL_2026-10-21.md) was written before the study;
the [scientific report](SEMANTIC_PRIORITY_STUDY_2026-10-21.md) separates results and limits.

## Independent and integration tests

| Suite | Executed Python methods | Verified behavior |
|---|---:|---|
| semantic_tradeoffs | 12 | Same raw interval; exact identity unions; truthful complete cuts; regional/support/loss bounds; unknown spatial/class queries; Pareto trade-offs; no-output handling; explicit scope/resource rejection; nonmutation |
| semantic_queries | 19 | Fixed bank; receiver-only predictions; missing support vs zero; semantic unknowns; contained partitions; no clipping; deadlines/EOF/censoring; invalid provenance/counts/geometry; outside-domain rejection |
| run_semantic_priority_study | 14 | Correct 360-case matrix and 12 repeats; unchanged paired sources; stable vs arriving people; regional requirements; scalar-check preservation; count/loss tamper rejection; numeric JSON equivalence; fresh output and repeat guards; three actual replay integrations |

All **45 new methods executed and passed**, with no new skips. The orchestration matrix
unit test mocks the expensive scientific evaluators; separate real-binary tests run
actual scalar, semantic-reference and receiver-query checks. The actual 360-case study
also runs all those checks without mocks.

The first smoke caught JSON numeric spelling differences (`0` versus `0.0`) in reference
membership signatures. The comparison now normalizes equivalent numeric representations,
uses a 12-decimal normalization for loss summaries, and preserves counts/identities.
A regression accepts equivalent forms and rejects materially changed losses. This was
a verification-layer defect; the production output already held the correct values.
The incomplete smoke directory is preserved separately, never treated as study evidence.

## Full build and regression result

```sh
cmake -S simulator -B simulator/build
cmake --build simulator/build -j 6
ctest --test-dir simulator/build --output-on-failure -j 6
```

Configuration and the full build, including Simulator, completed successfully. All
**50/50 CTest entries passed** in 15.70 s. Python reported **357 methods: 345 passed,
12 skipped**. The skips are existing optional matplotlib/pinned scikit-learn histogram
tests, not acceptance skips for the new components. The new entries are registered in
CMake. No new sanitizer claim is made for these Python-only tools; the prior C++ semantic
sanitizer evidence is unchanged.

The complete output and source/test hashes are preserved in
[verification/semantic-priority-2026-10-21](../results/verification/semantic-priority-2026-10-21/manifest.json)
and [ctest-full.log](../results/verification/semantic-priority-2026-10-21/ctest-full.log).
Existing MongoDB integration tests use only their fresh UUID-owned databases. The normal
simulation was not launched and the user's Simulation database was not used.

## Actual study verification

- 360/360 declared configurations completed and passed independent scalar audits.
- 1,929/1,929 actual retired intervals matched a legal reference cut with exact geometry,
  category/observation/distinct counts, taxonomy version and semantic summaries.
- 252 intervals had no nonempty feasible reference candidate at that actual endpoint.
- None of the 1,929 actual choices was dominated under the six declared fixed-interval
  retention/query/detail criteria. This does not certify global scheduling optimality.
- 12/12 repeats matched every scientific result field, including configuration YAML,
  excluding only `runtime`.
- All scored answered receiver queries had zero absolute error. Unknown and censored
  cases remained unknown; positive-demand/known-zero/category strata remain separate.
- A frozen binary and exact source/protocol snapshots match the study manifest hashes.

## Review limits

The reference is deliberately limited to depth 2 within one quadrant and at most twelve
semantic nodes. It is not an implementation for arbitrary region layouts or a performance
benchmark. The five streams are controlled deterministic witnesses, not statistical
replicates or realistic trajectory data. Query answerability uses a declared conservative
rule, not every inference possible from the transcript. Conditional references for
actual intervals cannot decide whether an earlier/later endpoint or future release
schedule would be better. Category support is not a calibrated empirical privacy gain.

The next production selection change requires a declared application objective or
preference order and another acceptance gate. Broader E07 and cell-local semantics remain
open in TO-DO.md. No C++ controller, simulator configuration, maps or behavior taxonomy
were changed in this step.
