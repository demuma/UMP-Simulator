# Observed-track window: implementation and validation report

Date: 26 October 2026. Profile: `observed_track_window_v1`.
Evaluation identifier: `urban-track-window-20261026-v1`.

**Checkpoint at the pre-execution freeze:** all 40 same-role TRAIN/CAL imports
pass the explicit window profile; they contain 6,792 observed track episodes and
3,478,736 contributions. All 344 affected tests pass, with zero failures, errors
or skips. All 22 retained DEV streams are independently reconstructed, including
66 archive round trips. Fresh primary mechanisms/models/TEST have not run at this
freeze. Read the [compact frozen evidence](verification/urban-track-window-2026-10-26-v1/pre-test-freeze/).
These engineering checks do not establish a privacy benefit.

## Scientific contract and historical boundary

The user selected **all recorded contributions of one operational track within a
fixed 300-second window**, with movement quality reported separately. The
[contract](PRIVACY_TRACK_WINDOW_CONTRACT_2026-10-26.md) defines the protected unit,
neighboring inputs, target eligibility and auxiliary knowledge mathematically.
A still-active track does not need an artificial end event at the window boundary.
All actual observations remain input, including stationary, censored, short and
unselected traces. Target eligibility alone requires at least two measurements.

The original source-v3 complete-episode study closed at **39/40** valid TRAIN/CAL
sources: 23/24 TRAIN and 16/16 CAL. Its gate stopped the study before any primary
mechanism execution, fitted model, TEST capture or TEST score. That outcome and
all original proof fields remain unchanged. Read the separate
[strict closure report](URBAN_PRIVACY_P25_4_SOURCE_V3_CLOSURE_2026-10-26.md).
A valid observed window is not retroactively a valid completed-journey recording.

The dataset assignment remains the original `urban-primary-20261026-v3` namespace:
72 groups, 24 TRAIN / 16 CAL / 32 TEST, and 216 unchanged role seeds. The evaluation
identifier is separate. All forty existing TRAIN/CAL captures are considered in
their original roles; movement quality does not select a favorable subset. TEST
capture is prospective and requires fresh actual TRAIN fits and CAL thresholds.

## Implementation

The new modules reuse the maintained source exporter, native replay/audits,
public transcript adapters, feature extraction, query evaluation and statistical
analysis. They provide explicit contract dispatch and provenance rather than
changing the native aggregation algorithm.

| Component | Responsibility |
|---|---|
| `track_window_source_validation.py` | Rebuild observations, results and proof facts from raw GT/sensor/lifecycle records; authenticate full clock, registry, provenance and physical evidence; return movement quality separately. |
| `run_urban_track_window_sources.py` | Import all 40 read-only same-role sources, preserve old strict statuses, freeze the import ledger and capture only preassigned prospective TEST slots after the new model gate. |
| `run_urban_track_window_primary.py` | Bind the evaluation/profile/imports/code; run paired methods; require full 40/full 32 source cohorts; authenticate group sidecars, fresh models, thresholds and typed validation evidence. |
| `report_urban_track_window_primary.py` | Export approved aggregate risk, utility, execution and movement-quality summaries; omit private identities, paths, rows and model parameters. |

Only two existing interfaces change. The physical checker accepts an explicit
windowed profile, under which destination/visit coverage becomes diagnostic;
geometry, source access, body/swept separation and speed/velocity checks remain.
Its default retains the legacy coverage rule and output. The generic primary
processor accepts an optional pair-selector callback; its default behavior is
unchanged. Original bytes were archived and authenticated before either edit.
Both hooks were applied only after the strict source batch closed.

Unknown or missing profile identifiers reject; no exception handler silently
falls back to a weaker validator. Successful historical physical reports retain
their original legacy provenance. Their source/configuration/report/execution and
original checker hashes are authenticated. A new physical audit, when needed,
gets a separate output; an old failed report is never overwritten or relabeled.

## Hard validity and separately reported movement quality

Hard requirements include the complete 300-second source horizon, exact integer
raw timestamps, the 50-ms numerical clock, actual 100-ms measurement schedule,
all 2,999 measurements from 100 through 299900 ms, consistent measured-empty batches,
GT-visible intervals, stable track/type associations and exact GT-to-sensor
projection. Configuration law, fixed map, source executable, native exit, capture
budget, raw files and independent physical evidence must authenticate.

The validator rebuilds the stored observation stream and native result from raw
recording data; a self-consistent replacement proof cannot conceal missing GT,
altered sensor counts, fabricated lifecycle events or a truncated clock. Original
sub-millisecond values reject before the maintained exporter's rounding parser.
The complete maintained dependency set must be frozen, rather than trusting an
arbitrarily shortened code map.

Journey completion, pending episodes, active tracks, stalls, waits and realized
visit coverage are quality observations. They do not excuse an unsafe physical
sample or malformed data. Missing quality counts stay unknown, not inferred zero.
The public quality table counts sources, not people or observations.

One real TRAIN recording verifies this distinction: its full window contains
96,747 contributions, 2,999 measurements and 169 observed/eligible tracks. The
lifecycle records 169 starts and 166 ends, with 3 active tracks, 2 reported stalled
tracks, 0 pending and 0 overlaps. Exact raw reconstruction and its authenticated
legacy physical audit pass under the new windowed unit. Its original completion
failure remains true. This is an integrity integration check, not attack evidence.

## Automated verification

The combined current-code run passes **344/344 tests**, with zero failures,
errors or skips, in 34.23 s. It uses synthetic fixtures; no native simulation,
recorded-data classifier fit, source replacement or current TEST access occurs.

| Coverage | Methods | Result |
|---|---:|---|
| New windowed integrity/physical-profile tests | 20 | PASS |
| New source import, provenance, cohort and TEST-capture gates | 25 | PASS |
| New evaluation, sidecar, validation-receipt and model-lock gates | 21 | PASS |
| New aggregate-only reporting, labels and quality/NA handling | 17 | PASS |
| Existing analysis/source/channel/split/query/statistics methods | 177 | PASS |
| Existing strict reporter | 10 | PASS |
| Existing independent physical checker | 19 | PASS |
| Existing native-recording exporter | 55 | PASS |
| **Total** | **344** | **PASS** |

Negative fixtures cover missing GT or sensor records, raw clock gaps and fractional
timestamps, inconsistent registry/type/proof/result/configuration/map/native
hashes, altered physical evidence, unsafe geometry/sweeps/speeds/velocities,
unknown profiles, missing dependencies, forged legacy provenance, wrong source
roles, duplicate inputs, malformed original receipts, failed audits, incomplete
40/32 cohorts and attempted TEST reuse.

Further tests reject old-scope locks despite identical group identifiers, changed
execution budgets despite a coherently rewritten protocol digest, stale or
incomplete validation receipts, missing/changed group sidecars and locked rows,
and mismatched source-protocol bindings before an individual TEST attempt.
Missing cases stay in the declared denominator. Censored/pending/stalled but
otherwise valid synthetic windows are positive cases; short traces remain input.

The two report figures have been inspected on synthetic fixtures. Method labels,
axes, legends, NA handling and the observed-window captions are readable. Actual
study figures require a separate inspection after execution.

## Recorded DEV integration and source import

The retained DEV reconstruction uses its originally authenticated production
source, exact IN/OUT pair and identical target/auxiliary role seeds. The new
window selector produces the same OUT and auxiliary bytes while reporting
`eligible_observed_tracks` instead of completed-episode metadata. Eighteen
retained native results and four derived regional streams are revalidated;
**zero new native executions and zero recorded-data model fits** are claimed.

All 66 archives reopen with matching compressed and original hashes. Current
code reaudits the native source/policy accounting, exports the actual semantic
recipient transcripts, recomposes both regional baselines in both worlds, and
recomputes all 22 rows: 111/31 public features, approved-sighting controls and
19,200 fixed queries per world. Current lower native/math primitives match the
archived original functions; the reviewed processor hook is the explicit change.
The receipt authenticates code, source, policy, raw/archive and row hash chains.

Every one of the forty preassigned TRAIN/CAL recordings receives a separate
windowed validation receipt and an immutable import-ledger entry. All 40 pass
full raw reconstruction and physical/data provenance under this profile. Their
original strict statuses remain 39 verified and 1 invalid. All original inputs
remain read-only; no path, track, failed case or role is replaced to obtain the
new verdict. The original thirty-two TEST source directories remain absent at
this freeze. The new lock must authenticate actual fresh 880 paired rows and
22 method/representation models before a TEST capture can begin; an independent
review barrier additionally checks that actual lock before the serial driver
continues.

## Reproduction and artifact policy

From the repository root, use a Python environment with the project's mapped-scene
and evaluation dependencies. The new focused suites are:

```sh
PYTHONPATH=tools/evaluation:tools/mapped_scene python3 -B -m unittest \
  test_track_window_source_validation \
  test_run_urban_track_window_sources \
  test_run_urban_track_window_primary \
  test_report_urban_track_window_primary
```

The complete run additionally includes `test_urban_privacy_analysis`,
`test_urban_privacy_fixture`, `test_urban_privacy_queries`,
`test_urban_privacy_split`, `test_urban_privacy_statistics`,
`test_run_urban_privacy_primary_sources`, `test_run_urban_privacy_primary`,
`test_semantic_privacy`, `test_regional_public_transcript`,
`test_run_urban_privacy_channel_pilot`, `test_run_urban_privacy_sources`,
`test_report_urban_privacy_primary`, `test_audit_building_access` and
`test_export_replay`.

Generated motion, full GT, original configurations, paired observations, features,
fitted weights and individual scores remain under ignored local `results/`.
Only compact aggregate evidence and provenance hashes belong in Git. Exact
recorded-data revalidation requires those retained local artifacts; unit tests
use synthetic fixtures and do not require sharing raw recordings.

The prospective study compares the same 11 methods under the same local400 policy,
with suppression OFF, 111/31 public-only representations, TRAIN-only fitting,
CAL-only thresholds and grouped TEST uncertainty. Final-snapshot risk, logical
release delay and mechanism runtime have different meanings. Operational distinct-
track support is not a person-level k-anonymity guarantee. No universal privacy,
population FPR, navigation-liveness or hard real-time guarantee follows from these
engineering checks.
