# Coordination study implementation and test report

Date: 2026-10-19. Repository: `/Users/maxdemu/Developer/UMP-Simulator`.
The measured protocol, all reference tables, interpretation and exported figures are in
[the coordination study](COORDINATION_STUDY_2026-10-19.md).

## Implemented scope

This milestone adds a reproducible measurement path around the existing controller.
No aggregation, ownership, hold, merge/split, history, live motion or publication-core
implementation was changed. Main simulator configuration and the existing local edits
in `UMP-Simulator.code-workspace`, `simulator/config.yaml` and
`simulator/src/AgentBasedSensor.cpp` were preserved and excluded from this change.

| Files | Implemented behavior |
|---|---|
| `tools/evaluation/coordination_scenarios.py` | Six analytical cases and three seeded families, fixed reporting masks, source geometry/cadence validation and qualitative conditions |
| `tools/evaluation/run_coordination_study.py` | Nine configurations, explicit effective policies, pre-execution immutable protocol, source/executable snapshots, serial cyclic ordering, independent audits, four adaptive repeats per case, paired JSON/CSV and hash manifests |
| `tools/evaluation/occupancy.py` | Fixed-region query summaries and exact private point/time retention/age; existing public query reconstruction remains unchanged |
| `tools/evaluation/coordination_metrics.py` | Contribution-weighted public timing and separately labelled private terminal diagnostics; unavailable public-blocking counters stay null |
| `tools/evaluation/plot_coordination_study.py` | Deterministic PNG/SVG export, raw paired realizations/medians, null-pair annotations, explicit age/coverage conditioning and overwrite protection |
| `tools/evaluation/run_comparison.py` | Shared replay subprocess now has a configurable 120-second default timeout; legacy seven-mode CLI/schema are preserved |
| New metric/scenario/study/plot test modules and `test_occupancy.py` | Numerical, data-contract and actual replay integration checks described below |
| `simulator/CMakeLists.txt` | Four new Python test suites registered, study suite timeout 120 seconds |
| README, TO-DO, evaluation/research docs, canonical notation and LaTeX | Actual capabilities, formulas, reproduction, evidence, counterexamples and next priorities |

The dedicated study runner avoids changing the historical seven-mode comparison's
configuration identity or retrospective utility contract. All nine configurations use
the same frozen source and numerical policy. Fixed/spatial references explicitly select
common-window configuration, avoiding a local-mode oracle/config mismatch. Strategy
and coordination differ only where declared. Effective per-run files are saved and hashed.

## Actual verification

Fresh Release configuration/build completed successfully, including Simulator,
AggregationReplay and all enabled regression targets. Commands ran from the repository
root:

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release \
  -DUMP_BUILD_REPLAY=ON -DUMP_BUILD_COORDINATION_TESTS=ON \
  -DUMP_BUILD_SENSOR_REGRESSION_TESTS=ON -DUMP_BUILD_PUBLICATION_STORE_TESTS=ON
cmake --build simulator/build -j 6
ctest --test-dir simulator/build --output-on-failure -j 6
MPLCONFIGDIR=/private/tmp/ump-coordination-mpl \
  python3 -B -m unittest discover -s tools/evaluation
python3 -B tools/export_notation.py --check
```

- **31/31 CTest suites passed**, final elapsed 6.94 seconds.
- CMake selected Python 3.13, which has no matplotlib: two optional figure-rendering
  methods were skipped there. This is explicitly supplemented by the complete run below.
- **179/179 Python methods passed under Python 3.9.4**, including both actual figure
  exports, in 17.906 seconds, with no skips.
- The five final plot tests additionally passed as a focused check. PNG and SVG exports
  are byte-identical across repeated exports; existing output files are rejected.
- Canonical notation export regenerated and `--check` passed.
- Exported scientific figure was visually inspected at its actual generated resolution.
  Labels, axes and footnotes fit; the regional-latency matched-MAE panels explicitly
  show 6/8 defined pairs instead of implying eight scored outcomes.

New/extended tests cover: fixed boundary-mask selection, excluded boundary queries,
reference versus answered contribution totals, unknown/undefined public support,
exact raw point/time membership, coarse cells crossing masks, age quantiles and
retained-only weights, batching invariance, zero weights, invalid/overlapping output,
separate terminal/public evidence, deterministic seeded inputs, actual known policy
conditions, source/policy nonmutation, explicit nine-mode effective configs, paired
query alignment/null cases, independent-realization denominators, duplicate selections,
no overwrite, pre-execution protocol/source/binary freeze, audits, artifact hashes and
scientific determinism excluding only runtime.

The study-specific integration tests execute 39 actual replay processes on three
small cases, including both coordination models and both priorities. Existing tests
continue to exercise the legacy seven-mode runner and prior privacy-evaluation code;
those regression executions are not part of this utility/policy study's outcome matrix.

## Executed study

Private bundle:

```text
results/evaluation/2026-10-19/coordination-study-19-26-v1
```

- Protocol created: 2026-10-19 17:52:00.712548 UTC.
- Completion recorded: 2026-10-19 17:53:20.041012 UTC.
- Six mechanism cases + 24 seeded independent complete realizations.
- Nine configurations each: **270 primary replays**.
- Both adaptive priorities repeated under both coordination models: **120 repeats**.
- **270/270 independent audits valid**, with 24,028 released cells and 57,905 checked
  terminal windows; no reported policy, observation-conservation, coverage or ownership
  overlap violation.
- All 120 repeats match their first execution exactly after excluding runtime.
- Source hashes remained unchanged throughout execution.
- Main bundle at completion: 959,205,519 bytes, including private diagnostics, full query
  evidence, independent audits and snapshots. Later post-study witness/verification
  artifacts are separate additions. This is disk volume, not measured online RAM.

| Artifact | SHA-256 |
|---|---|
| Frozen AggregationReplay | `7236b204ec311c4a5c407c53e89daac73f28d87b9711cd9cd806b753bd04b574` |
| Protocol | `caf3af79ef7927c125f506b31d60acde3438773cd4c165f1647dbde193831dda` |
| Summary | `d0433b676995ed835eb8ad503b39bbb94c0843a2103374da56e2210b8d266980` |

Complete artifacts remain private and are excluded from Git. The protocol records
platform/Python versions and the pre-study Git state; the source snapshot preserves the
actual files even though the measurement scripts were not yet committed at execution.
The later plot-only refinement annotates missing paired outcomes without changing any
recorded observations, aggregate outcomes or controller execution. Verification logs,
post-study witness and final figure/script hashes are preserved alongside the bundle.

## Additional independent checks and measured limits

All 54 mechanism outputs were separately recomputed from elementary raw point × released
rectangle × half-open interval membership, independently of the new retention helper.
Released counts, exact mean ages and nearest-rank p95 ages matched in every case.

A post-study witness was independently rechecked for `mixed_density-seed-19`:
parent 14 passes at 200 ms (9 contributions / 9 identities) and 1000 ms (123 / 15),
while a published descendant over [0,200) blocks its later retrospective release.
Cell 934 loses nine contributions in the actual local run. The common controller
actually publishes parent 14 at the earlier endpoint. The preserved witness includes
raw oracle assessments, the actual suppression/public overlap/reference releases and
source hashes. This is an explanatory example, not total opportunity regret.

Measured outcomes include improvements and failures. A blocked branch keeps the same
retention with mean age 538.46 to 148.72 ms. Regional-latency mean retention rises by
12.31/17.20 percentage points (TF/SF), but mixed-density retention falls by 15.90/18.10
points and is lower in all eight seeds. Avoidable holds occur even where a parent
violates the spatial size cap. These are candidate regressions for the next controller
revision; this milestone deliberately leaves that controller unchanged.

The following are not established: formal/empirical privacy improvement; a realistic
urban traffic model; online application availability; performance at depth six or city
scale; complete asynchronous search; global optimality; aggregate publication-loss
regret; a universally superior preservation order. Retained-only ages, conditional MAE,
strict full-query support, omitted empty support, finite EOF boundaries and diagnostic
serialization are explicit limits. Eight synthetic realizations per family support an
exploratory paired description rather than population claims or significance conclusions.
