# Coordination refinement and privacy implementation test report

Date: 2026-10-19. Repository: `/Users/maxdemu/Developer/UMP-Simulator`.
This milestone implements the two measured coordination corrections, verifies them
against the saved matrix, then evaluates empirical privacy under a fixed independent
source-membership protocol. Main results are in the [refinement report](COORDINATION_REFINEMENT_2026-10-19.md)
and [privacy study](PRIVACY_COORDINATION_STUDY_2026-10-19.md).

## Changed implementation

| Files | Behavior and purpose |
|---|---|
| `simulator/src/CellLocalAggregation.cpp`, matching header | Pre-disclosure nearest-rescue endpoint planning; nonoverlapping nested-candidate resolution; concrete feasible parent holds; preflight temporal/ancestor budgets |
| `simulator/tests/CoordinationRegressionTests.cpp` | Seven focused cases added, 21 total; independent geometry/time/identity evidence and exact retirement checks |
| `simulator/tests/CoordinationStressTests.cpp` | Original 120 seeded cases preserved; 120 additional regional duration/size cases |
| `tools/evaluation/compare_coordination_studies.py`, matching tests | Hash/protocol/input/policy verification, unchanged-reference assertion and paired before/after utility/age results |
| `tools/evaluation/run_privacy_study.py`, matching tests | Opt-in nine mechanisms plus two controls, explicit effective policies, immutable pre-execution protocol/frozen binary, independent local auditing, paired attacks/query support |
| `tools/evaluation/empirical_privacy.py`, matching tests | Search all time-overlapping local release scopes until spatial support matches the candidate; avoid first-unrelated-release truncation |
| `tools/evaluation/plot_privacy_coordination.py`, matching tests | Deterministic immutable PNG/SVG export with actual test counts, all configurations/controls and scoped interpretation |
| CMake, README, TO-DO, architecture/privacy docs, canonical notation/LaTeX | Registered tests, chronological privacy priority, exact algorithm and empirical contracts, measured outcomes, nonoverlap argument and limitations |

The common-window controller, motion engine, input capture, publication model and
main simulator configuration were not changed. Existing local edits in
`UMP-Simulator.code-workspace`, `simulator/config.yaml` and
`simulator/src/AgentBasedSensor.cpp` are preserved and excluded from this commit.
Legacy seven-mechanism privacy/comparison behavior remains available without the new flag.

## Build and regression results

The final Release build completed for Simulator, AggregationReplay and all enabled
regression targets. The existing configuration uses SFML 3.0.2 and the local build
dependencies. Reproduction from the repository root:

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release \
  -DUMP_BUILD_REPLAY=ON -DUMP_BUILD_COORDINATION_TESTS=ON \
  -DUMP_BUILD_SENSOR_REGRESSION_TESTS=ON -DUMP_BUILD_PUBLICATION_STORE_TESTS=ON
cmake --build simulator/build -j 6
ctest --test-dir simulator/build --output-on-failure -j 6
MPLCONFIGDIR=/private/tmp/ump-privacy-mpl \
  python3 -B -m unittest discover -s tools/evaluation
python3 -B tools/export_notation.py --check
```

- **33/33 CTest suites passed**, final elapsed 11.00 seconds.
- CMake selected Python 3.13 without matplotlib: three optional render methods were
  skipped there. The complete Python 3.9.4 run below covers all three.
- **196/196 Python methods passed**, no skips, in 23.099 seconds.
- All **21 focused coordination cases and 240 seeded stress scenarios** passed.
- Fresh ASan/UBSan standalone builds passed both C++ targets, with exit zero and no
  sanitizer finding: focused 0.292 s; stress 3.460 s. Strict `-Wall -Wextra -Werror
  -pedantic` used the narrow `-Wno-missing-field-initializers` exception for an existing
  common-controller aggregate initializer. Initial compiler rejection and final commands
  remain preserved; no source change hid the warning.
- Canonical notation version 1.3 and generated LaTeX passed the freshness check.
- Both actual scientific figures were exported as PNG/SVG and visually inspected:
  labels, scales, conditional-interval captions and test-count metadata fit.

The new C++ cases cover: passing-child timeliness when a parent is illegal; competing
nested rescues across independent base domains; separate finer rescues; maximum spatial
extent; TF/SF priority; excluded-endpoint identities; and budget failure before disclosure.
Existing coverage includes mixed-depth prefixes/suffixes, incomplete source evidence,
future handoffs, immutable retries/expired acknowledgements and bounded ownership.
Additional stress cases retain raw geometry/identity/conservation/nonoverlap audits.

New Python comparison tests cover artifact/source tampering, changed observations/
policies/query definitions, changed supposedly untouched outputs, invalid stored audits,
unsafe manifest paths, null metrics and no-overwrite behavior. Privacy tests execute
108 actual opt-in replay/audit cases plus four repeats and preserve legacy integration.
A disjoint spatial/time-overlap feature case reproduces the local projection bug.
Plot tests verify data units, required projections, malformed records, byte-identical
exports and protection of existing files.

## Same-input coordination evidence

Completed `coordination-study-19-26-v2`:

- 30 cases, 270 valid independent audits and 120 exact scientific repeats.
- 23,177 released cells and 19,779 checked terminal windows.
- Identical observations, original/effective policies and 210 untouched reference outputs
  verified against v1, excluding runtime only.
- Before/after comparator verifies every recorded artifact and frozen source hash; its
  baseline self-comparison also returns all-zero defined differences.
- The recorded illegal-parent mean age improves 343.59 to 148.72 ms with unchanged
  156/195 retention. The prior parent-14 publication witness now releases that parent
  at 200 ms and no longer suppresses the recorded 934/[0,1000) window.
- Mixed-density SF retention matches common in the measured summaries; TF average gap
  is -0.0732 percentage points. Retention/coverage gains accompany some matched-error
  increases, as detailed in the report. No universal utility improvement is claimed.

Binary SHA-256: `17313ec82b2d50aa433fd0c0634edbad1fd7c0ef9744a05c3219c55bbda041e2`.
Protocol SHA-256: `11c2cb4bd870cee64f3f8d9b1f6b235b1df23899db3234ddaae55116e935fa4c`.
Summary SHA-256: `27ed8025eb4ae3648c3350a92534b54dc85d5604766aa6bb10f9a713e3626ce3`.

Verification logs, sanitizer commands/results, exact dense benchmark inputs/policies/
outputs and additional hashes are under
`results/evaluation/2026-10-19/coordination-refinement-comparison-v1/verification`.
The dense depth-six benchmark is descriptive: k=1 current 258.334 ms, k=2 old/new
283.142/291.870 ms; its scientific output matches the corresponding reference.
It does not establish city-scale or general real-time performance.

## Executed privacy assessment

Completed dataset `privacy-coordination-dataset-20261020` and study
`privacy-coordination-study-20261020-v1` under `results/evaluation/2026-10-19/`:

- 184 independent source groups: 64 training, 40 calibration, 80 held-out.
- Unique group IDs, identity-normalized backgrounds, paired realizations and auxiliary
  trace hashes; 16/10/20 groups per scenario in the respective splits.
- 3312 independently audited executions, all valid; 63,227 released cells; 206 no-output
  mechanism/world cases. No-output compliance is not useful availability.
- Four adaptive scientific repeats pass; frozen binary matches the coordination matrix.
- All 44 separately fitted attacks converge in 1–79 iterations with the declared model
  budget. Controls, knowledge fractions, feature sets and thresholds remain predeclared.
- Raw result/input/effective-policy hashes for all 3312 commands were independently
  rechecked, along with frozen Python source, executable, protocol and report hashes.
- Direct positive-by-negative score-pair recomputation (without `attack_metrics`) confirms
  **44 pooled and 176 scenario attack records**, confusion counts and all model/report
  thresholds. All 11 utility rollups and 320 paired priority/world support cases match.
- Exact-count control: AUC 0.66844 for full trace/31 features, coverage/retention one,
  occupancy error zero. No-output: AUC 0.5, coverage/retention zero, MAE undefined.

Privacy protocol SHA-256: `8f9264163571ad60d19293e12438bc8da86951fe1b83b8453653432adb8d9b89`.
Dataset manifest: `5f653f1ed5886d351a5ca02d8e01d6bcfa90a67c847511d72fc8d380cecba282`.
Report: `bfc3d066d2367929ae014aec7f4b42d9fc750924af95175c49e568f702af01e6`.
A supplementary `verification/manifest.json` closes the complete raw/public/model/
prediction evidence graph. All experimental evidence remains private and Git-ignored.

The scoped result is mixed: full-trace/31-feature SF AUC decreases 0.65609 to 0.61969
with paired conditional interval excluding zero; the TF interval includes zero. Both
local variants lose about one point of retention/availability on this separate population.
SF matched-query error is essentially unchanged (0.677859 to 0.677717); its own-support
conditional error increase alone does not show worse accuracy. Local SF handover AUC
rises within that stratum, and realized FPR can exceed the calibration target. These
limits prevent universal privacy or Pareto-superiority claims.

## Remaining scientific limits

The endpoint planner is bounded, causal and greedy; future holds do not guarantee later
success. This test report does not establish asynchronous global optimality, publication
regret, or formal privacy. The privacy task protects whole-horizon source participation,
not physical presence, identification or sensitive visits. It uses four-second synthetic
same-generator populations, exact partial candidate knowledge, one application and a
bounded summary/logistic attack. The source population is the utility reference.

Intervals are pointwise, scenario-stratified and conditional on fitted models and fixed
thresholds; training uncertainty, distribution shift and multiple-comparison adjustment
are absent. Larger/further-attacker protection is not inferred from classifier failure.
Support thresholds remain operational requirements; offline AUC is not a calibrated
per-cell online Policy Tree metric. The next priority is a newly declared independent
privacy follow-up with longer/noisy traces, shifted backgrounds and stronger public-only
attacks, preserving this held-out set as assessment evidence.
