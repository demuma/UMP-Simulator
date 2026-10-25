# P25.4: grouped urban protection and utility assessment

Status: implementation validated and frozen before TEST; primary execution in progress.
This document records implementation of the unchanged [P25.3 design](verification/urban-privacy-p25-3-2026-10-25/primary-design.json).
It does not replace that design or change its source seeds, policy or analysis.

## Question and protected contribution

Does the adaptive mechanism reduce the declared recipient's ability to infer the
inclusion of one complete visible observation episode, relative to the policy-aware
regional static reference, and what utility accompanies that risk? Policy support
is an operational release condition, not a substitute for this attack assessment.
The protected unit is an episode contribution within 300 seconds. It is not a
physical person's presence, identity, sensitive visit, or all visits of one person.

The source law is the existing native Mönckebergstraße simulator: 80 × 80 m,
depth 6, 128 configured people, 50-ms motion and 100-ms measured sensor samples.
The Original source-capture policy remains separate from the shared `local400`
evaluation policy. Source-generation and mechanism-evaluation stages are distinct.
A recording is saved once; every compared method uses its exact IN/OUT bytes.

## Fixed study and methods

The prospective manifest fixes 24 TRAIN, 16 CAL and 32 TEST recordings. Each source
has one eligible target selected with the committed source hash and target-role
seed. OUT removes that episode only, preserving background, batch clocks, empty
measurements and all metadata. A separate role seed selects exactly ceil(n/4)
coordinate/time/cell sightings, shared by both worlds. No candidate type or ID is
an attack input. All dependent worlds, methods and excerpts stay in their source split.

The eleven reported methods are fixed 10-m and 20-m grids at each of
400/1000/2000/4000 ms, regional static 10-m and 20-m references, and adaptive
Semantic First with Temporal First secondary and `policy_satisfied` release.
Priority names preserve the corresponding precision. Every method uses the same
hard `local400` policy and suppression OFF. Long fixed windows do not relax the
local 400-ms duration/age cap. Regional schedules use public policy and geometry
only; all four underlying native executions are independently audited, including
unused components. Regional composition has no native runtime measurement.

The native aggregation executable and all previously frozen feature, audit,
fitting and calibration helpers remain unchanged. P25.4 adds orchestration,
exact-query coverage, exact rate intervals and reporting around those components.

## Implementation and TEST gate

New implementations are deliberately separate from the hash-bound helpers:

- `run_urban_privacy_primary_sources.py`: exact frozen source slots, lifecycle,
  physical/access audits, source law and clone gates; serial captures without
  retries, replacement seeds or database deletion.
- `run_urban_privacy_primary.py`: exact matched pairs, nine native and two derived
  methods per world, full public-channel validation, raw policy/accounting audits,
  compact private feature/utility rows and lossless local archives.
- `urban_privacy_analysis.py`: TRAIN-only fits/scaling, CAL-only thresholds,
  controls, unmodified TEST score direction and grouped comparisons.
- `urban_privacy_statistics.py`: exact Clopper–Pearson intervals and paired
  recording bootstrap; no external statistics dependency.
- `urban_privacy_queries.py`: exact root-occupancy answers separated from the
  unchanged `occupancy.evaluate` estimator.

The supplement hashes these implementations and their tests, plus authenticates
176 passing tests and all 22 existing-source DEV recipient streams. It was written
with no primary TEST source or score generated. Source-generation and execution
runners reject changed supplement code, missing validation receipts or a different
manifest. They require actual hash-bound TRAIN/CAL rows and models before TEST.

The model lock checks all 40 recording groups × eleven methods × two worlds:
880 unique rows, correct splits/labels, complete pairs, and 22 method/representation
models. It checks the actual model bundle and source fingerprints, not just a
self-reported count. Nonconverged models are retained as explicit negative outcomes;
the fixed fitting budget is never increased. Missing TRAIN/CAL families do not
unlock TEST. Source-only or native failures remain in the experimental denominator.

## Attack inputs, controls and interpretation

The primary representation has 111 public-only coordinates: 31 scalar, six semantic
summaries, 72 taxonomy coordinates and two availability summaries. The 31-coordinate
scalar comparison jointly removes semantics and availability; it cannot isolate
semantic leakage. These are predictors, not 111 privacy metrics.

Each method/representation gets its own deterministic L2 logistic model, fitted
on TRAIN with l2=0.1, 500 iterations and tolerance 1e-8. CAL maximizes TPR under
empirical FPR ≤0.1; ties prefer lower FPR and then the higher threshold. TEST never
selects model direction, thresholds, baselines or hyperparameters.

Controls are prior-only, auxiliary-only, no-output and unprotected observations.
Auxiliary-only uses eight fixed summaries: sighting count, minimum/maximum/mean
normalized time, normalized mean x/y, and normalized x/y range. They are identical
within each IN/OUT pair. No-output uses the same 111-coordinate schema with no
releases. These pair-identical controls should give AUC 0.5. The unprotected score
is the fraction of exact permitted sighting points present in source observations;
matching uses neither type nor identity. Coincident background points can match OUT,
so perfect positive-control AUC is not imposed.

Report ROC-AUC, TPR/FPR, threshold advantage and integer confusion counts. The
primary difference is AUC(adaptive) − AUC(regional static20), with a paired 1,000-draw
recording bootstrap and fixed seed. Its 95% interval is conditional on the fitted
models and CAL thresholds. Rate intervals are two-sided exact Clopper–Pearson.
For example, observing 0 false positives in 32 OUT cases still gives an upper 95%
FPR endpoint of approximately 10.89%. This is exploratory evidence for one bounded
attacker, not a population FPR guarantee or universal privacy score.

## Utility and clocks

Each world is compared to its own included source observations. Report retention,
full-input loss `J=(N_input−N_retained+Σ_retained taxonomy_loss)/N_input`, retained-only
semantic loss and spatial detail, and per-observation logical sealing delay.
Full-input semantic loss including unit omission cost and J are the same quantity
here, not independent objective dimensions.

There are exactly 19,200 scalar all-road-user queries per world: 64 fixed 10-m
footprints ×300 one-second intervals. t=0 is initialization; a boundary sample
belongs to the next half-open interval. An exact answer requires complete public
space-time support from whole contained tiles with known occupancy means. Spatial
or temporal proportional allocation is an estimate, not exact coverage. Missing
output is unknown, including empty places absent from sparse publication. The
unchanged estimator's conditional MAE must be read with its answered/scored coverage.
A conservative exact decoder can therefore have zero coverage across methods.

Recipient availability is the final snapshot at H=300 s, including EOF handling.
Logical seal timestamps are metadata. This study supplies retrospective risk and
utility evidence, not actual live receipt times, deadline utility or real-time
performance. RT03 remains a separate dense-load question.

## Resources, archival and failures

Captures and native cases are serial. Source capture/export and physical audit
have separate 420-s caps; native execution has a 180-s cap. At least 3 GiB must be
free before a new source/native case starts. Per-artifact capture budget is 2 GiB,
not a process RSS guarantee. Pilot capture-plus-audit times imply roughly four
hours for 72 sources, with native replay/audit/archival additional; this is not an
instantaneous benchmark or a cap-based duration forecast.

Full source movement, GT, raw private journals, native results, feature rows,
models and individual scores remain ignored under `results/`. Created temporary
native result/audit/public files are gzip-archived only after all regional uses;
original and compressed hashes are verified, and final reporting reopens archives.
No motion recording or owned MongoDB database is deleted. Git receives aggregate
receipts/results and scientific figures only. Incomplete and failed cases remain
visible; no hidden replacement, source trimming or TEST-driven tuning is allowed.

## Reproducible entry points

Use `/private/tmp/ump-mapped-venv/bin/python -B`. The ignored primary directories are
`results/urban-privacy-primary-sources-2026-10-25-v1` and
`results/urban-privacy-primary-study-2026-10-25-v1`. The latter retains the supplement,
local driver protocol/logs, model lock and eventual final report.

Preparation and implementation freeze were already performed. Repeating them into
the same directory is rejected. Source resume skips attempted slots; native resume
skips existing group directories, preserving interruptions as incomplete evidence.
Never run a second driver while the current one is active. Frozen CLIs enforce
exclusive locks, no source/native retries and TEST authentication independently of
the local sequencing driver. Do not modify hash-bound files during execution.

The driver order is TRAIN/CAL sources → TRAIN/CAL mechanisms → model lock → TEST
sources → TEST mechanisms → final archive/split authentication and assessment.
See the [validation report](URBAN_PRIVACY_P25_4_TEST_REPORT_2026-10-25.md).
