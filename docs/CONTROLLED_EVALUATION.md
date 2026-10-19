# Controlled replay and first evaluation

Status: 2026-10-14. Current user-selected scope: utility and policy fulfilment first.
The original implementation contract preceded the first comparison; privacy evaluation
is now deferred. Existing exploratory artifacts remain preserved.

**October 19 follow-through:** the first independent oracle and controlled synthetic
empirical membership study are now implemented. See
[EMPIRICAL_PRIVACY_IMPLEMENTATION.md](EMPIRICAL_PRIVACY_IMPLEMENTATION.md) and the
[test report](TEST_REPORT_2026-10-19.md). This dated October 14 contract and its optional
`--privacy-targets` helper remain separate from that new calibrated study.


## Research question

Under which observation and regional-policy conditions does bounded adaptive aggregation
produce compliant releases, and what are the resulting occupancy error, answered-query
coverage, spatial resolution and simulated release age? A separate, explicit attacker
model is required to relate these operational outcomes to privacy.

The initial comparison holds observations, regional thresholds, legal depth, history
budgets and application query constant. It compares fixed grids/windows, spatial-only
selection, Temporal First (preserve time; try space first) and Spatial First (preserve
space; try time first). This is a controlled mechanism comparison, not evidence that one
strategy always dominates or that the simulator reproduces a real city.

The next study is specified in [RESEARCH_QUESTIONS_AND_EXPERIMENTS.md](RESEARCH_QUESTIONS_AND_EXPERIMENTS.md):
independent feasibility checks, controlled mechanism cases, policy sweeps and independent
replications. It is a design awaiting implementation, separate from the completed pilot.

## Frozen private input

`AggregationReplay` accepts a versioned JSON observation stream and a small YAML/JSON
policy configuration. It executes the existing aggregation, history, policy, selection,
adaptation and publication-coordinator cores without MongoDB or a renderer. The offline
sink immediately acknowledges each immutable release. Disk/network latency, retries and
live-frame scheduling are outside this experiment.

Input schema `ump.observation-replay.v1` stores run/sensor IDs, grid geometry, leaf depth,
sampling period, exclusive end time, and timestamped batches. Each observation contains
an internal road-user ID, type, finest cell ID and private GT coordinates. Coordinates
are checked against that half-open cell. Measured-empty, unavailable and absent batches
have different meanings. No measurement is scheduled at t=0. The frozen file and policy
are copied into each experiment, hashed with SHA-256 and reused unchanged across modes.
Private coordinates are used by the evaluator, not by the aggregation decision.

The first source is a deterministic, hand-inspectable synthetic stream. A captured
simulator stream may also be frozen after explicitly checking cadence and GT/sensor
alignment. Replaying it removes differences between strategies caused by random spawning
or runtime-dependent motion; it does not repair those simulation limitations.

## Fixed utility query and reconstruction

Use the contract in [METRICS.md](METRICS.md): a fixed 10-m reference grid and full 1-second
intervals, with arithmetic mean occupancy over scheduled 100-ms samples. The first
interval has nine samples and later intervals ten. The GT answer uses private positions.
The estimate uses only public release geometry, intervals and mean sampled occupancy,
allocated uniformly in space and held constant over its window.

A query is answered only if released support covers its entire reference cell at every
scheduled query sample. Suppressed or absent support is unknown, never zero. Sparse
publication omits empty cells, so even a truly empty reference cell can remain unanswered.
Report answered-query coverage over the entire fixed domain, reference availability,
scored coverage and conditional MAE together. A low MAE with little answered support is
not a general utility improvement. A trailing partial query interval is excluded and
reported. Overlapping public support is an error.

For available references and answered queries S:

    occupancy_MAE = sum(|estimated_q - reference_q| for q in S) / |S|
    answered_query_coverage = answered_queries / all_reference_queries

MAE is undefined when S is empty. Online `occupancy_mae` remains unavailable because the
online evaluator has no private GT input. Offline evaluation does not leak GT into policy
selection or add an oracle to the algorithm.

## Deferred optional privacy scope

The existing optional check is deterministic neighbouring-output distinguishability.
It is outside the current utility/policy milestone and is not enabled by the commands below. Remove
one target's observations from the frozen stream while retaining all other observations,
all sample times and measured-empty batches; rerun from the beginning. Compare the full
recipient-visible transcript, including counts, geometry, intervals and logical release
times. Internal diagnostics and run-generated release IDs are excluded.

This assumes exact knowledge of the target and every other trajectory and of the
algorithm. It is a deliberately strong stress test, not a trained membership attack,
not formal k-anonymity, and not differential privacy. Exact counts can make it saturate.
See [PRIVACY_EVALUATION.md](PRIVACY_EVALUATION.md) for the threat model and limitations.

## Verification and reporting requirements

- Hand-checkable utility counterexample: combining occupancies 4 and 0 gives estimates
  2 and 2 and MAE 2 on the unchanged reference grid.
- Missing public coverage stays unknown; input is identical across all mechanisms.
- CLI validation rejects malformed cadence, IDs, geometry, configuration and duplicate
  output paths before creating a final result. Replays agree apart from runtime fields.
- Every released cell passes its effective policy, and released support does not overlap.
- Report contribution retention separately from query coverage; it is not a privacy score.
- Record resolved configuration, input hashes, code revision/dirty state, commands and
  result paths. Processing time is an observation, not a real-time performance guarantee.
- Keep the complete result bundle private: it includes raw identities/positions and
  suppressed-window diagnostics even though the nested releases omit identities.

Independent scenarios/seeds, realistic attacker training/testing, confidence intervals,
additional application metrics and preparation/publication-model studies remain follow-up
work. A small demonstration cannot settle the dissertation's effectiveness question.

## Run the evaluation

Run from the repository root. Build dependencies remain those of the simulator project
(CMake >= 3.12); the new evaluation helpers use Python >= 3.9 and its standard library. Only the
optional figure exporter requires matplotlib. The capture helper additionally needs a
running localhost MongoDB and `mongosh`; frozen replay itself does not.

```sh
cmake -S simulator -B simulator/build
cmake --build simulator/build --target AggregationReplay ReplayRegressionTests -j6
ctest --test-dir simulator/build -R 'replay|evaluation' --output-on-failure

python3 tools/evaluation/make_fixture.py --output results/my-fixture-input
python3 tools/evaluation/run_comparison.py \
  --input results/my-fixture-input/observations.json \
  --config results/my-fixture-input/policy.json \
  --output results/my-comparison
python3 tools/evaluation/plot_summary.py results/my-comparison
```

Every output directory must be new. Use `--scenario handover` for the analytical action-order
fixture. The current commands and CLI default run utility/policy evaluation only; their
manifest records no privacy scope and zero privacy targets. If the deferred privacy work
is resumed, the optional `--privacy-targets N` flag selects the first N lexically sorted observed IDs and stores the exact list;
it is not a random population sample.

For an actual simulator source, the capture adapter uses only the maintained temporal
example, makes a private eight-second headless copy, disables aggregation, and writes to a
new UUID database. It verifies GT/sensor cadence, identities, geometry and cell/type counts,
exports the evidence, then drops only that owned database after successful verification.
Failures retain the database for investigation; `--keep-database` also retains it explicitly.
A completely empty GT frame has no frame record in the current raw schema, so the capture
adapter rejects that ambiguity rather than inventing a measured frame. Synthetic fixtures
can explicitly encode measured-empty batches.

```sh
python3 tools/evaluation/capture_simulator.py --output results/my-capture
python3 tools/evaluation/run_comparison.py \
  --input results/my-capture/observations.json \
  --config results/my-fixture-input/policy.json \
  --provenance results/my-capture/capture-manifest.json \
  --output results/my-capture-comparison
```

The normal simulator executable must already be built for capture. The adapter verifies
that its example template still has the expected settings and refuses unexplained drift.
Its purpose is a verified small capture, not a generic experiment-configuration editor.

A single mechanism can also be run directly:

```sh
simulator/build/AggregationReplay \
  --input results/my-fixture-input/observations.json \
  --config results/my-fixture-input/policy.json \
  --mode temporal_first --output results/single-temporal-first.json
```

Modes are `fixed`, `spatial`, `temporal_first` and `spatial_first`. Fixed mode additionally
accepts `--fixed-depth` and `--fixed-window-ms`; its cells still have to satisfy the same
policy. The seven-mode helper requires the stated 80-m/100-ms preset. The lower-level CLI
has a more general validated grid/cadence contract.

See [the dated report](EVALUATION_RESULTS_2026-10-14.md) for actual results. Generated bundles
contain private GT and suppressed diagnostics, even though the nested release arrays have
no raw road-user identities. The existing MongoDB recipient collections are not overwritten.
