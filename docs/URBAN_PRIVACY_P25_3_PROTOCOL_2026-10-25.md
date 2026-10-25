# P25.3: independent urban sources and prospective experiment design

Date: 2026-10-25. Status: all-eight narrow motion preflight passed; v3 full captures in progress; the main design
below is a draft until the source-quality gate and immutable split freeze pass.
No main training/calibration/test recordings, fitted attack or privacy gain are
claimed by this document.

## Purpose and scientific boundary

The study evaluates contribution membership in the released urban data product.
A candidate is one complete visible observation episode within the fixed 300-s
horizon. IN includes that episode; OUT removes only its recorded observations.
Every background observation, measurement opportunity and measured-empty status
stays unchanged. OUT is not a resimulation and does not represent physical absence.
All episodes of one real person are not the protected unit.

The P25.1 contract remains unchanged. P25.2 supplies a semantic-aware recipient
channel with 111 fixed public-only feature coordinates. Features summarize
published cells, intervals, counts, category bins, category support, semantic loss
and availability. They are inputs to a bounded membership classifier, not 111
privacy metrics. No target type or identity is supplied with auxiliary knowledge.

Policy satisfaction, application utility and empirical attack success are separate
results. Passing exporter/source/split tests establishes measurement integrity;
it does not establish that the protected mechanism reduces inference risk.

## Predeclared eight-source development pilot

`run_urban_privacy_sources.py` freezes all commands before the first capture.
Seeds are exactly 2026102501 through 2026102508. Each runs the maintained
`tools/mapped_scene/run_scene.py` and native Simulator. No separate movement
simulator is introduced.

Each scene uses the same Mönckebergstraße map and public geometry, 80 × 80 m,
quadtree depth 6, 128 scheduled private people, 300 s, 150-ms arrivals, 50-ms
simulation steps and 100-ms sensor sampling. Flags preserve storefront motion,
urban traffic, subway access, expanded shop access, rider priority, configured
rider fraction 0.2, distributed crossing fraction 0.2 and pedestrian clearance
0.05 m. Seed-dependent routes, identities and realized class proportions vary;
realized density and counts are measured, not assumed equal.

Configuration-law comparison excludes only those seeded plans/identities,
probabilities matching the realized cohort, and fresh owned database names.
Map/access bytes, nonseeded parameters and all generator/native source files are
hashed. The executable and Python/package/mongosh environment are fixed for the
entire attempt matrix. Historical capture policy and subsequent replay policy
are distinct; source generation is not changed to favor the selected policy.

Each complete capture/export command has a 420-s wall limit. A separate maintained
physical audit also has a 420-s cap. The 2048-MiB capture bound is per bounded local
artifact, not a process-memory or total-study bound. Runs are serial, create three
fresh UUID MongoDB namespaces and retain their own data by default. The user's
`Simulation` database is not a destination. Generated movement remains under
ignored local `results/`; compact aggregate evidence belongs in Git.

Every seed has at most one attempt under this protocol. Failed, interrupted,
timed-out, censored and duplicate cases remain visible. There is no replacement
seed, silent retry, cohort trimming or favorable-seed selection. A later genuine
source correction requires a separately identified protocol/version; the
negative attempt remains evidence.

Source acceptance requires:

- A complete 300-s measurement clock and authenticated source/export receipts.
- Every scheduled visible episode started, ended and sensor-observed; zero active
  or pending episodes at the horizon. Horizon completion alone is insufficient.
- Independent physical checks for navigation surfaces, swept bodies, speed,
  boundary endpoints, enabled entrances and completed visits/returns.
- Unchanged public geometry and configuration law, matching executable/config
  hashes and successful native execution.
- Unique ID-independent route-plan and observed-trajectory fingerprints across
  accepted recordings. Renaming IDs is not a new recording.

The first version was stopped after a confirmed crossing starvation failure:
one accepted source, one censored source, one interrupted source and five
unattempted seeds remain in its eight-slot negative matrix. Two pedestrians were
stationary for over 216/238 s. Crossing admission used nominal route goals while
movement used a projected boundary goal, repeatedly losing a necessary request.
The broader v2 attempt combined that correction with retained detour/staging
behavior; it fixed seed1 but introduced an oscillation in seed2 (168/169 ended).
Its partial negative matrix is retained. A subsequent body-contact/admission/apron
prototype worsened source completion and was rejected in aggregate-only preflight.

The selected correction is deliberately narrower: one pure terminal-goal resolver
is shared only by actual movement and crossing-request retention. Legacy detour,
staging, center-entry/admission, receiving-apron and rider-lookahead behavior stays
unchanged, as do all final physical predicates. All eight unchanged-seed motion
preflights pass with exactly this source: 1359/1359 episodes complete by H=300s,
zero final active/pending/stalled/overlap counters. The latest end is 218.55 s.
These are motion-only probes, not Simulator captures or privacy/runtime evidence.
The next capture protocol is separately versioned v3; no earlier outcome is
relabeled as a later success. General detour/body-contact scheduling and global
liveness remain known limitations, outside this narrow source correction.

Pending ungranted requests now contribute to maximum crossing wait. The active
stall diagnostic also includes ungranted request ages of at least 10 s; this can
include movement toward staging, not only literal stationary duration. The
controller's consecutive-stop timer still excludes controlled waits. Complete
lifecycle, observability and physical gates remain authoritative.

The eight recordings are inspected DEV pipeline evidence and are excluded from
all later TRAIN/CAL/TEST groups. They establish neither real-world representativeness
nor sufficient statistical power. A failed gate keeps P25.3 open.

## Draft main design, pending source acceptance

The prospective design contains 24 TRAIN, 16 CAL and 32 TEST independent full
recordings, one complete target episode per recording. Source-generation,
target-selection and auxiliary-selection seeds are domain-separated hash-derived
identifiers. Assignment is fixed before source generation. All IN/OUT worlds,
methods, conditions, targets and excerpts of a recording remain in its split.
Historical mixed/pedestrian sources, the inspected P25.1 fixture and all eight
pilot seeds/fingerprints are excluded. An authenticated manifest also rejects
renamed/numerically reserialized clones and reused target/background trajectories.

Candidate selection follows P25.1 hash ranking over complete eligible episodes
with at least two observations, before any mechanism output is inspected.
Auxiliary knowledge is the identical exact retrospective sample of ceil(n/4)
position/time sightings in both worlds, including derived cell IDs. It contains
no candidate class, track ID, person ID or private background. This is full-horizon
knowledge, not a causal prefix acquisition model.

One application condition, `local400`, holds all hard bounds and taxonomy fixed
across protected methods. Root support is at least five distinct visible tracks
and five per published category, with ten near the declared entrance region.
Maximum cell side is 20 m; the central through region limits duration/age to
400 ms; other declared root/local semantic constraints remain effective. Track
support is an operational condition, not established person-level k-anonymity.
Selective contribution suppression is OFF.

The complete comparator family is:

- Adaptive Semantic First, secondary Temporal First, release when policy satisfied.
- Fixed 10 m and fixed 20 m, each at 400, 1000, 2000 and 4000 ms.
- Regional static 10 m and 20 m, each choosing the longest declared policy-allowed
  window per cell, using all four independently audited fixed components.

Long fixed windows do not relax local bounds. Every output must pass the same
hard-policy and source-accounting audit. All failed/incomplete cases remain in
the report. Regional composition has no measured native online runtime.
The primary risk contrast is adaptive minus regional static20 ROC-AUC; fixed20
at 400 ms and regional static10 are explicit secondary comparators. The complete
family is reported without selecting a winner on TEST.

## Fitting, controls and uncertainty

Fit one deterministic L2 logistic model per method/representation on TRAIN only,
including TRAIN-only normalization: L2 0.1, maximum 500 iterations, tolerance
1e-8. Report convergence; an unconverged fit cannot become a successful result
through TEST-dependent tuning. The primary representation has 111 coordinates.
The secondary 31-coordinate scalar representation drops both semantic and two
availability coordinates: it is a joint representation ablation, not an isolated
estimate of semantic leakage. Preserve score direction, including AUC below 0.5.

Use the existing `empirical_privacy.calibrate_threshold` on CAL: maximize observed
TPR subject to empirical FPR ≤ 0.1, breaking ties by lower FPR then higher threshold.
Classification uses score ≥ threshold and includes the conservative threshold
just above the maximum calibration score. Lock the threshold before TEST.
Report ROC-AUC, observed TPR/FPR, TPR−FPR advantage and integer confusion counts.

CAL has 16 independent OUT units: one false positive is 6.25%, two are 12.5%.
TEST rates move in steps of 3.125%. Report two-sided exact 95% binomial intervals
for rates; zero of 32 errors still has an approximately 10.89% upper limit.
Use 1000 paired source-group bootstrap replicates, fixed seed 20261025301, for
conditional percentile 95% AUC-difference intervals, preserving method/world
pairing. These intervals condition on fitted models/thresholds and do not measure
training uncertainty. Secondary intervals are pointwise exploratory, without a
multiple-comparison guarantee. Forty-eight TRAIN rows for 111 regularized features
define a limited attacker; low success does not establish strong privacy.

Controls are prior-only, auxiliary-only, no-output and unprotected observations.
Pair-identical negative controls should give AUC 0.5. The unprotected positive
control scores the fraction of exact permitted auxiliary position/time points
present in its observation transcript. It uses no private candidate class/ID.
Coincident background points can match in OUT, so perfect positive-control AUC
is not forced. Diagnose failed controls before interpreting lower attack success.

## Utility, clocks and resources

Recipient availability is a final snapshot at H = 300 s, including EOF. Logical
seal timestamps remain visible metadata; they are not actual delivery times.
This experiment supplies retrospective utility and inference evidence, not an
online deadline or real-time guarantee.

Report world-specific input retention, full-input J and semantic loss, retained
spatial/semantic detail and logical seal delay. A fixed 10-m/1-s occupancy workload
uses all 64 cells and 300 windows (19,200 scalar all-road-user queries per world),
with measured empty periods retained and t=0 initialization excluded. Exact answer coverage requires complete space-time
support; coarse reconstruction is separately labeled estimation. Reuse the
existing uniform spatial/constant-interval occupancy reconstruction, reporting
its MAE together with answered/scored coverage. Unknown output is not a zero.
Use the included IN or OUT observation population as the corresponding reference.

The draft entails 72 primary recordings, 144 worlds, 1296 native cases and 288
regional compositions before controls. Generation, audits, native cases and
storage need bounded staged execution in P25.4; caps are not runtime forecasts.
Raw/private data and full replays stay local. Only compact design/aggregate
receipts, tests, reports and scientific figures should be published.

## Commands and next gate

Prepare and execute the immutable DEV protocol using the explicit mapped Python:

```sh
/private/tmp/ump-mapped-venv/bin/python tools/evaluation/run_urban_privacy_sources.py \
  --output results/urban-privacy-sources-pilot-2026-10-25-v3 --prepare-only
/private/tmp/ump-mapped-venv/bin/python tools/evaluation/run_urban_privacy_sources.py \
  --resume results/urban-privacy-sources-pilot-2026-10-25-v3
```

`--verify OUTPUT` reauthenticates captured artifacts and writes a new report
snapshot. It does not run the simulator. `urban_privacy_split.py` freezes the main
manifest only with a verified eight-source pilot and authenticated exclusion and
policy evidence. Its future slots explicitly say `planned_not_generated`.
P25.4 begins after the source and immutable design gates pass.
