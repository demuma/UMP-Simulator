# P25.4 implementation validation and execution report

Status: implementation gate passed; v1 source-validity gate failed before primary
mechanisms/models/TEST; a separate source correction is under validation.
No completed primary urban privacy result is claimed at this checkpoint.
See the [protocol](URBAN_PRIVACY_P25_4_PROTOCOL_2026-10-25.md).

## Verified implementation

The final affected Python suite passes **176/176 methods**, zero failures,
errors or skips, in 16.203 operational seconds. This includes 95 new P25.4 methods:
statistics 14, exact/estimated occupancy queries 22, frozen analysis 18, primary
source wrapper 17 and primary execution wrapper 24. The remaining methods cover
unchanged source, split, fixture, semantic-channel and regional-adapter contracts.
Tests use synthetic or previously inspected DEV data; no primary TEST is used.
No C++ or native aggregation binary changed. CMake remains unchanged because the
source protocol hash-binds it; new tests are run explicitly rather than altering
the frozen source law during the experiment. Historical CTest pass counts are
not presented as a new full native regression run.

Meaningful negative checks reject source/metadata/background tampering, cloned or
misassigned groups, private/incorrect auxiliary fields, duplicate method/world
rows, modified models/thresholds, false TEST readiness, changed code/receipts,
source/native retries, premature output visibility, invalid semantic support,
archive corruption, low storage and concurrent runner ownership. Timeouts retain
owned-process receipts and dependent regional failures remain explicit.

Numerical interval validation compares all success counts for n=16 and n=32
against independent 60-digit Decimal binomial roots. Group bootstrap is checked
against independently computed tie-aware AUC and resampling. Analysis tests check
TRAIN-only scaling, CAL-only thresholds, no TEST direction flip, explicit
nonconvergence, fixed denominators, negative controls and coincident background.
Query tests independently exercise spatial/temporal tiling, mixed depths,
straddling intervals, unavailable means, absent/zero distinctions, boundaries and
world-specific references. The estimator is literally the unchanged maintained
`occupancy.evaluate` call.

## Existing-source DEV integration

The complete P25.1 DEV pair passes **18 native executions and four derived regional
compositions**, eleven methods and 22 recipient streams. Every native stream passes
independent raw scalar/semantic policy/accounting audits; each regional stream uses
all four audited same-grid native components. The final code reauthenticates all
raw/public archive hash chains, source/method/cadence/priority/trigger settings,
111/31 public-only features, paired controls and 19,200 fixed occupancy queries per
world. Lossless gzip round trips preserve original bytes. All eight auxiliary-only
summaries contain approved sightings only.

Native subprocess wall time summed over 18 DEV cases is 95.071 s. This excludes
additional Python audit, query and archival time and is an operational receipt,
not an isolated real-time benchmark. The input is previously inspected DEV and
has effective independent source count one; these cases are not a privacy test set.

## Frozen implementation supplement

The original main manifest remains
`5c12a45072da540f71d96115341b5f7fb1a6d9b5be84e8ba3922ac233586056a`.
The local supplement authenticates all ten new implementation/test files and the
unit/DEV receipts before primary TEST generation. Primary TRAIN/CAL generation may
precede the supplement; TEST cannot. The lock additionally authenticates 880 actual
TRAIN/CAL rows and 22 unique method/representation models before any TEST source.

Local evidence is retained under
`results/urban-privacy-p25-4-verification-2026-10-25`,
`results/urban-privacy-p25-4-dev-2026-10-25-v1`, and
`results/urban-privacy-primary-study-2026-10-25-v1`.
Private source observations, targets, labels, individual scores and model weights
are excluded from Git. Compact evidence: [implementation supplement](verification/urban-privacy-p25-4-2026-10-25/implementation-supplement.json),
[176-test receipt](verification/urban-privacy-p25-4-2026-10-25/unit-validation-receipt.json)
and [current-code DEV receipt](verification/urban-privacy-p25-4-2026-10-25/dev-integration-current-code-receipt.json).
The public supplement omits the private local freeze-directory path; the original
local supplement remains authoritative for runner authentication.

## Primary execution and pending interpretation

The 24 TRAIN /16 CAL /32 TEST source slots and eleven methods remain unchanged.
The first new TRAIN source passed full cohort, provenance, physical/access and
clone/exclusion checks. The serial source batch and subsequent frozen phases are
running. This section will be replaced by actual complete/failed counts and joint
risk/utility findings after execution; no pilot result is extrapolated to TEST.

P25.4 remains open until the final group outcomes, archive/source authentication,
control diagnostics, risk/utility estimates and compact public report are available.

## Source gate interruption — 2026-10-26

The first 24 TRAIN attempts produced 22 verified and two invalid captures. The native
clock/GT capture was complete, but coupled crossing queues left 49/56 active
tracks and 14/13 pending episodes at H. Both report zero body overlaps. This is a
source-motion/liveness defect, not a privacy or aggregator failure. The waiting
native/model/TEST driver was stopped; the predefined CAL source attempts continue
for complete failure accounting. No primary model or TEST source has been created.
See the [retained aggregate checkpoint](verification/urban-privacy-p25-4-2026-10-25/source-gate-checkpoint-2026-10-26.json)
and [mechanistic diagnosis and separate DEV correction](URBAN_PRIVACY_SOURCE_CROSSING_DRAIN_FIX_2026-10-26.md).

The original ten implementation/test files were byte/hash-archived before a small
main-runner clarification: model preparation now receives the current authenticated
manifest's exact groups/methods explicitly. A new synthetic regression passes with
an unavailable legacy default path; the main-runner suite is 25/25. The source
runner/self-bound files and old native source remain unchanged while v1 runs.
Any corrected primary run needs a fresh source/execution freeze and implementation
supplement; original v1 evidence is not overwritten or pooled into the new version.

## Corrected source v2 frozen and executing — 2026-10-26

The complete v1 batch is 37/40 valid (22 TRAIN, 15 CAL), with three invalid captures and
32 unattempted TEST slots. Its source-only report is closed before primary mechanisms,
fits or attack scores. The production finite-cohort correction and two native
regressions pass all 11 affected CTest groups (176.97 s). The new full Python check passes
177 methods; the prior 22 recipient DEV streams are reauthenticated. AggregationReplay
remains byte-identical.

All 48 known motion configs pass, 8,119/8,119 episodes, including all three old failure cases,
with independent physical/speed/displacement/cohort checks. A separate pre-TEST v2
manifest is frozen at `e3b4296674c95d407baf6bc2d3def0564cb77eca37286fdbf9b92ff48c82d5c0`,
with unchanged 72 groups, 216 role seeds, 17 exclusions, policy, methods, features and analysis.
Fresh serial sources/mechanisms/models/TEST execution is running. No final held-out
privacy estimate is claimed until the full outcomes and control gates are reviewed.
See the [formal amendment](URBAN_PRIVACY_P25_4_SOURCE_V2_AMENDMENT_2026-10-26.md),
[48-case motion evidence](verification/urban-privacy-p25-4-2026-10-26-v2/motion-preflight.json)
and [freeze receipt](verification/urban-privacy-p25-4-2026-10-26-v2/amendment-freeze.json).
