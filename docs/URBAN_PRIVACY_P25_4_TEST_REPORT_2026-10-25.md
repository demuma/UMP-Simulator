# P25.4 implementation validation and execution report

Status: implementation gate passed; frozen primary execution in progress.
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
