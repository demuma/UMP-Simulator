# P25.3: source independence, crossing correction and split tests

Date: 2026-10-25. Status: **P25.3 complete**. Eight v3 full captures pass fresh
source/physical/independence verification. The primary manifest is frozen and
reverified; main recordings and attack fits remain zero. Negative v1/v2 captures
and rejected prototypes are retained. No privacy-benefit estimate is claimed.
See the [protocol](URBAN_PRIVACY_P25_3_PROTOCOL_2026-10-25.md).

## What the attack features mean

P25.2 implements a strict recipient product with actual semantic output. The
classifier receives 111 fixed coordinates, all computed from public releases and
the permitted auxiliary sightings:

| Family | Coordinates | Examples and interpretation |
|---|---:|---|
| Scalar representation | 31 | Published counts/support, space-time coverage and geometry, including support at known position/time sightings. |
| Semantic summaries | 6 | Published minimum category support and mean/maximum semantic loss, globally and at matched sightings. |
| Public taxonomy categories | 72 | Six quantities for each of 12 public taxonomy nodes: explicit-bin availability, contributions and support, globally and at matched sightings. |
| Availability summaries | 2 | Declared recipient availability relative to interval ends and known sightings. These use the explicit clock model, not measured live delivery. |

These are explanatory variables for a learned attack, not 111 privacy metrics.
The candidate's exact type and private track/person identity are not auxiliary
knowledge. A parent category does not imply an unpublished child has zero count;
explicit-bin availability separates absent detail from a reported value. The
public-only boundary excludes GT, private source unions, suppression reasons,
seeds, source hashes and internal runtime.

The protected secret is inclusion of one visible episode's recorded contribution.
IN includes it; OUT removes exactly that episode while preserving the background
and measurement clock. It is not the secret of physical presence or real identity.
The later attacker learns on TRAIN, selects its threshold on CAL and is evaluated
on untouched TEST. AUC measures ranking discrimination; TPR is detection of IN,
FPR is an incorrect IN decision on OUT. TPR−FPR is threshold advantage. Neither
one-minus-AUC nor the operational track-support floor is a universal privacy score.

## What the tests establish

The new Python tests include 11 source-runner methods and 22 split methods. They
exercise behavior rather than supplying evidence of privacy improvement:

- Freeze all seeds/parameters/provenance before native capture; allow only serial
  owned processes and preserve failed/interrupted/timeout outcomes without retries.
- Reject censored/missing episodes, missing observability, altered source hashes,
  changed geometry/configuration laws and failed physical audits.
- Reject renamed source/route clones and incomplete clock excerpts masquerading
  as new independent recordings.
- Keep every target, world, method, policy and excerpt of one recording together;
  reject background and target-trajectory reuse across recording groups.
- Authenticate historical exclusions and exact OUT filtering, preserving measured
  empty batches; reject path escapes, changed files and invalid numerical input.
- Freeze actual policy/generator evidence bytes, retain private permissions and
  distinguish planned future slots from generated/evaluated data.

Existing recipient tests also reject extra private fields, inconsistent semantic
counts and premature visibility. None of these assertions trains a classifier or
shows lower attack success.

## Negative v1 source pilot

The v1 protocol was frozen before the first seed, SHA-256
`37100f1949ee3c130519ec201a86dcb13f3d366696345be23a30662f826e4e1f`.
Its original Simulator SHA-256 is
`1b8db7607fb504cd857edd45bc87eb7e381a45ef92c66abce2d4ab6ff2ae502d`.
It was stopped after confirming a genuine source defect. The full eight-slot
matrix remains visible: one invalid, one verified, one interrupted and five
unattempted cases. No failed seed was replaced or converted into a success.
The original executable, captures, logs and partial report remain local.

Seed 2026102501 starts and observes all 172 episodes but ends only 170 by 300 s.
Two pedestrians remain stationary for 216.05 and 238.35 s, even though the last
other episode finishes at 176.15 s. Nominal route goals used for crossing admission
disagree with projected boundary goals used for actual movement. A required
request can be pruned repeatedly; the stationary pedestrian then blocks an
opposite receiving apron. This is starvation, not merely insufficient horizon.
Old stall/maximum-wait summaries exclude this pending wait. The full lifecycle
gate correctly rejects the recording despite a successful capture/export.

[Compact negative matrix](verification/urban-privacy-p25-3-2026-10-25/negative-v1.json).

## Correction and regression evidence

The final selected correction shares a pure terminal-goal resolver between
movement and crossing-request retention. It reproduces the existing projected
boundary target and cached occluded target. Detour lifetime, staging targets,
center-entry admission, receiving aprons and rider lookahead retain the original
behavior. Navigation geometry, preferred speed, body radii and final swept-body
checks remain unchanged. The aggregation executable and policies are unchanged.

New scoped regressions cover terminal boundary projection with body-only crossing
contact, an opposite pedestrian's receiving apron, speed/displacement, swept-body
separation, caller-cadence determinism and pending wait telemetry. The projection
regression fails against the old source and passes with the correction. Broader
detour and first-body-contact prototypes are not shipped or claimed solved.
Their code and failed receipts are retained privately; the [negative body-contact
preflight](verification/urban-privacy-p25-3-2026-10-25/negative-body-contact-preflight.json)
shows why expanding the scheduler was rejected (seed2 only 134/169 completed).

All eight unchanged-seed native motion preflights pass with the selected minimal
source: 1359/1359 completed episodes, no final active/pending/stalled/overlapping
tracks, last-end times 171.45–218.55s. The [aggregate preflight summary](verification/urban-privacy-p25-3-2026-10-25/motion-preflight.json)
and [artifact receipt](verification/urban-privacy-p25-3-2026-10-25/motion-preflight-receipt.json)
bind the exact source/header/probe hashes. Actual stdout/stderr and configuration
hash receipts are retained locally, not reconstructed from narrative. This is
motion-only; full sensor capture and independent physical audit remain separate.

Pending ungranted requests now contribute to maximum crossing wait. An ungranted
request age of at least 10 s also contributes to active-stall diagnostics; this can
include staging motion. The controller stop timer still excludes controlled
waits. These counters do not prove literal stationary duration or global liveness.

## Build and complete regression suite

```sh
cmake -S simulator -B simulator/build \
  -DUMP_MAPPED_SCENE_PYTHON=/private/tmp/ump-mapped-venv/bin/python
cmake --build simulator/build -j 4
ctest --test-dir simulator/build --output-on-failure
```

The earlier v2 checkpoint passed **110/110 CTest groups**, zero failures, 448.17 s. This included the then 32 new
Python methods, mapped source drains and existing sensor, aggregation, policy,
history, publication, privacy, semantic and replay tests. The mapped native unit
group also contains the new composed source regressions. A final focused run of
the two new Python groups passed in 7.01 s. `git diff --check` passes.
Full logs remain local; the [compact regression receipt](verification/urban-privacy-p25-3-2026-10-25/regression-receipt.json)
contains the log hash and commands. Suite runtime is not an algorithm benchmark.

Rejected v2 Simulator SHA-256:
`f4947cbf658db6e99e7f90c6a0145c638098523b4daf6badc157eb8cbbefcb3c`.
AggregationReplay remains byte-identical:
`72fc0aff452ee036d7dfdd8bd8ca7bd343c7462923ec00ccb39f904ee655502f`.

## Rejected v2 source gate and retained negative evidence

The v2 protocol SHA-256 is
`2c81fb5bb53c09d5ac07b971adb41fa72d88de60fd462d59defef9673574868e`.
It repeats seeds 2026102501 through 2026102508 with the same capture parameters
and quality requirements. Its native/source version is distinct from v1.
No v2 case is accepted using a v1 success or failed partial capture.

V2 seed1 passes its full capture and physical audit, but seed2 completes only
168/169 episodes. A lone Senior Pedestrian oscillates between half-metre staging
candidates near Barkhof while a crossing request remains pending for 237.65 s.
The revised diagnostics correctly flag it. Actual and hypothetical staging
origins can disagree about the preserved detour, invalidating a holding point
exactly on arrival. This is a second source defect; the matrix was stopped and
retained with 2 verified, 1 invalid, 1 interrupted and 4 unattempted
cases. [Compact negative v2 matrix](verification/urban-privacy-p25-3-2026-10-25/negative-v2.json).
The corrected all-eight aggregate preflight passed before the separately
frozen v3 capture matrix. Source results and final prospective-freeze
receipts are recorded in the completed v3 section below. Raw motion, IDs, database names
and public/private native streams remain outside Git under ignored `results/`.

## Main-study interpretation and next gate

All eight final v3 sources now pass, and the immutable prospective split is
verified. Its 24 TRAIN/16 CAL/32 TEST recordings are additional
sources, with one candidate each; the inspected eight are DEV only. All family
methods share the same hard local400 policy and suppression OFF. Full111 logistic
regression is a fixed bounded attacker; scalar31 is a joint representation
ablation. Main generation, fits, calibration and held-out assessment are P25.4.

The current code supplies provenance, independence and channel integrity, not
new measured privacy. Later reports must preserve null or adverse contrasts,
source failures, attack-control failures, uncertainty and utility tradeoffs.

## Final narrow source validation before v3 capture

The maintained Simulator rebuild succeeds with SHA-256
`c17a458690f0332b10f47c51586b8973568cdeed06558755dd689c89f7cb7bc8`.
After the eight-source motion preflight, all 11 affected source/sensor/split groups
pass again (175.51 s), including every finite source drain. The latest Python
suite has 33 new methods (11 source-runner +22 split), including numeric-header
reserialization clone rejection. See the [final affected-test receipt](verification/urban-privacy-p25-3-2026-10-25/final-source-regression.json).
The full 110-group checkpoint above remains historical evidence, not a repeated
full-suite claim for every rejected candidate.

V3 protocol SHA-256:
`d36f2677c9b50e8e2d8830c12148cfe7810a315e0e7fef3cd30b1dea36b98f61`.
It freezes the final narrow source, same eight seeds, parameters and acceptance
gates. All eight full captures and independent physical audits pass; the main design
is now frozen and reverified.

## Completed v3 source results and primary freeze

All **8/8** original seeds pass full 300-s Simulator capture, observability,
configuration/executable provenance, exact cohort completion and independent
physical audits. Fresh verification reopens every authenticated artifact. All
normalized trajectory and route-plan fingerprints differ across the eight;
none overlaps the inspected historical source fingerprints. Each source has
128 configured private people and 2999 measured sensor batches. Those people/
episodes/observations are not additional independent statistical source groups.

| Seed | Episodes completed | Observation contributions | Peak observed tracks |
|---|---:|---:|---:|
| 2026102501 | 172/172 | 83,119 | 124 |
| 2026102502 | 169/169 | 90,066 | 127 |
| 2026102503 | 170/170 | 88,069 | 125 |
| 2026102504 | 165/165 | 88,003 | 124 |
| 2026102505 | 171/171 | 90,926 | 123 |
| 2026102506 | 169/169 | 84,556 | 123 |
| 2026102507 | 173/173 | 89,882 | 125 |
| 2026102508 | 170/170 | 93,625 | 126 |

Total: **1,359 visible episodes; 708,246 observation contributions; 40 simulated
minutes; 8 independent modeled source groups**. Realized type/density counts and
source hashes are in the [compact pilot receipt](verification/urban-privacy-p25-3-2026-10-25/source-pilot.json).
Raw movement, IDs, full GT/native streams and database namespaces remain local.
The source-capture policy is distinct from the later shared local400 replay
condition; no capture policy was tuned to produce an adaptive/privacy win.

The main manifest is independently verified, SHA-256:
`5c12a45072da540f71d96115341b5f7fb1a6d9b5be84e8ba3922ac233586056a`.
It preassigns 24 TRAIN, 16 CAL and 32 TEST groups, one target each, and excludes
all inspected sources. The full native family has 1,296 planned IN/OUT cases;
288 regional compositions give 1,584 planned recipient streams before controls.
These are planned counts: **0 actual primary recordings and 0 attack runs**.
The [freeze receipt](verification/urban-privacy-p25-3-2026-10-25/primary-freeze.json),
[frozen design](verification/urban-privacy-p25-3-2026-10-25/primary-design.json),
[policy](verification/urban-privacy-p25-3-2026-10-25/policy-local400.json) and
[prospective groups](verification/urban-privacy-p25-3-2026-10-25/prospective-groups.json)
are compact research metadata, excluded from evaluated recipient features.

P25.4 still needs the urban orchestration, exact root-query coverage and exact
rate-interval implementations. Validate and hash-bind that supplement before
TEST generation/inspection, then perform the declared TRAIN/CAL/TEST assessment.
Low success of a bounded attacker cannot establish universal privacy, and this
source/split gate itself produces no attack-success estimate.
