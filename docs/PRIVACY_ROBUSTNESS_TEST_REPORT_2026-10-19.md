# Privacy robustness implementation and test report

Date: 2026-10-19. Repository: `/Users/maxdemu/Developer/UMP-Simulator`.
This milestone follows the authorized GitHub publication with an independent extension
of the empirical source-membership assessment. The fixed protocol and scientific
interpretation are in [the study](PRIVACY_ROBUSTNESS_STUDY_2026-10-19.md).

## Implementation

| Files | Change and purpose |
|---|---|
| `tools/evaluation/privacy_dataset.py`, matching tests | Backward-compatible v2 independent long-corridor groups, separate candidate/background RNG, population-count shift, uncertain auxiliary points, streaming pair generation and strict provenance/clone validation |
| `tools/evaluation/robustness_attacks.py`, matching tests | Existing transparent logistic attack plus pinned histogram gradient boosting; fixed parameters, finite/shape checks, owner-only exclusive model artifacts and integrity-checked in-process prediction |
| `tools/evaluation/run_privacy_robustness.py`, matching tests | Predeclared five-mechanism/two-control protocol, frozen inputs/executable/policies/source, two independent test cohorts, base-only fitting/calibration, paired bootstrap and full private evidence |
| `tools/evaluation/plot_privacy_robustness.py`, matching tests | All 28 model projections across both separate cohorts, actual group counts, conditional intervals, query coverage and source retention, deterministic immutable PNG/SVG exports |
| `tools/evaluation/requirements-robustness*.txt` | Direct optional attack dependency and exact tested optional environment lock |
| `simulator/CMakeLists.txt` | Register three additional evaluation suites, including real-core integration |
| README, TO-DO, privacy contracts and canonical notation/LaTeX | Actual scope, prerequisites, formulas, reproduction, attributes/context, online-prefix contract and honest interpretation limits |

This stage changes the offline evaluation, not the C++ aggregation algorithm, movement
engine or main simulation configuration. The frozen Release replay executable is the
same one verified in the previous [refinement test report](REFINEMENT_PRIVACY_TEST_REPORT_2026-10-19.md).
The controlled fixtures use an operational support threshold of three; this does not
change the interactive simulator's configured policy or establish k-anonymity.
Existing local edits in `UMP-Simulator.code-workspace`, `simulator/config.yaml` and
`simulator/src/AgentBasedSensor.cpp` remain preserved and are excluded from our commits.

## Regression results

- **36/36 CTest suites passed**, final elapsed 11.55 seconds. CMake selected the existing
  Python 3.13 interpreter; optional dependency-specific methods can skip there.
- **228/228 Python methods passed with no skips** in the isolated pinned Python 3.13
  attack/plot environment, elapsed 35.682 seconds.
- The dependency-free legacy Python 3.9.6 environment ran the same **228 methods** in
  30.256 seconds: **222 passed and six optional HGB methods skipped** as intended.
- Canonical notation 1.4 and its generated equation fragment passed the freshness check.
- Before the scientific run, one dense 16-second training case passed all five actual
  replay/oracle configurations in about one second combined. This is a feasibility
  smoke check, not an end-to-end or real-time performance benchmark. The shell timing
  wrapper could not query a sandboxed kernel clock; the five actual runs/audits passed.
- V1 compatibility was checked against HEAD: all four legacy scenario cases and a
  six-case legacy bundle remained byte-identical. The new study requires v2 explicitly
  rather than silently reusing the previous held-out dataset.

The first CTest invocation registered the plot suite while its parallel implementation
was still being completed, and reported no tests for that suite. After the file was
finished, the focused suite and the final full 36-suite run passed. No failed scientific
assessment was discarded or used to choose the new protocol.

Reproduction after building the existing replay/test targets:

```sh
cmake -S simulator -B simulator/build
ctest --test-dir simulator/build --output-on-failure -j 4
LOKY_MAX_CPU_COUNT=1 MPLCONFIGDIR=/private/tmp/ump-robustness-mpl \
  /private/tmp/ump-privacy-robustness-venv/bin/python -B -m unittest discover \
  -s tools/evaluation -p 'test_*.py'
python3 -B -m unittest discover -s tools/evaluation -p 'test_*.py'
python3 -B tools/export_notation.py --check
```

The isolated environment and dataset/study reproduction commands are in the study.
No new C++ implementation requires another sanitizer build; the unchanged controller's
previous ASan/UBSan evidence remains explicitly associated with its prior report.

## Independent checks

The five new pipeline methods exercise tiny independent cohorts through the real replay
binary: 80 primary audits with 14 logistic fits, and a separate default-family run with
80 audits and all 28 model fits. Tests reconstruct every public-only feature vector,
refit logistic models from TRAIN only, recalibrate from base CAL only and independently
check saved scores/metrics in both disjoint test cohorts at the same frozen threshold.
They reject a v1 dataset, tampered input, invalid attack families and reused outputs.
The optional test checks pinned model version, 64 iterations, single-thread limits,
file SHA-256 and mode 0600. No external model pickle loading interface is exposed.

The 13 additional dataset methods cover long paths/full candidate support, independent
RNG streams, shift preservation, clone/hash checks, invalid parameters, bounded noise,
identical selected indices, recomputed cell IDs, cadence-independent timestamps and
exclusive output generation. Ten attack-family methods cover deterministic fits,
nonlinear interactions, malformed input, metadata/model tampering, version provenance
and model-path/permission boundaries. Four plot methods check all required projections,
nonfinite/invalid intervals, cohort denominators, deterministic exports and no-overwrite,
including a dangling symlink.

Read-only scientific review found no methodological blocker. It identified explicit
limits now included in the study: direct matching of noisy points, bounded summary
features, generated population counts rather than exact instantaneous density,
conditional pointwise intervals, and the need to retain scenario-specific outcomes.

## Completed scientific execution

The fixed study completed **2080 valid primary replay audits**, covering **178649
released cells**, plus four identical adaptive scientific repeats. All 14 logistic
models converged (1–81 iterations); all 14 boosted models completed their fixed 64
iterations. The complete manifest hashes 5371 artifacts.

An independent post-run validator performed **16612 assertions**, without importing
UMP training/statistics helpers. It rechecked all 5371 artifact hashes and 114 frozen
source hashes; explicitly compared every positive/negative score pair for all 56 AUCs;
recomputed all 224 scenario assessments, TPR/FPR and threshold consistency; independently
reproduced all 16 paired 400-resample intervals; verified 14 model-file hashes; checked
2080 oracle records/raw-artifact links and all 14 utility rollups/paired denominators.
It passed in 9.83 seconds. Evidence is saved privately as
`results/evaluation/2026-10-19/privacy-robustness-verification-20261021/independent-review.json`.

A supplemental independent evaluator reconstructed **1835008 actual held-out query
instances** from raw points and public cell/time integrals, without UMP evaluator imports.
It verified **512 actual common/local support intersections** and conditional/matched
MAE across 1792 variant-worlds, passing 1883392 assertions in 9.60 seconds. This closes
the gap between checking saved paired denominators and checking the underlying query
masks. `independent-query-masks.json` preserves the evidence. All **310 aggregate CSV
rows** were independently compared with the report (4692 assertions); the LF-only
publication form is checked separately from the original CSV writer's CRLF bytes.

The source binary SHA-256 remains
`17313ec82b2d50aa433fd0c0634edbad1fd7c0ef9744a05c3219c55bbda041e2`.
Protocol SHA-256:
`536f40d3bb8cc5ed4e17969779d8387292241188c2019a084a31c8ccf84a359f`.
Report SHA-256:
`0af5db289ad53bf2065c3ccf34df39a25e0aecf26f88294da11088fac6d19543`.

All models/cohorts and every pointwise paired contrast are reported, including lower
local retention/availability and the absence of a general local privacy advantage.
The scientific figure was exported as PNG/SVG and visually inspected; four CSVs contain
56 attack, 224 scenario, 16 contrast and 14 utility aggregate rows. Their values are
derived from the completed report; individual data and model artifacts are excluded.
Reproduction commands, exact study paths and interpretation limits are in the linked study.

## Delivery and scope

The audited committed history was initially published to
[demuma/UMP-Simulator](https://github.com/demuma/UMP-Simulator), branch `main`.
Results, raw observations, traces, scores, trained model files and build products remain
local and ignored by Git. Only reviewed implementation, aggregate scientific figures/
tables and documentation belong in the next push. No license or third-party asset
redistribution assumption was invented.

Sensitive-attribute semantics, a visit-generation environment, formal k/l/t/DP guarantees,
noise-aware probabilistic attacks and an online recipient application remain separate
work packages. The new [attribute/context and online contract](PRIVACY_ATTRIBUTE_AND_ONLINE_CONTRACT.md)
records their prerequisites; documenting them is not their implementation.
