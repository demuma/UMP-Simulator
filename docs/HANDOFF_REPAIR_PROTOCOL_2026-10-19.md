# Handoff repair: implementation and independent assessment protocol

Protocol declared 2026-10-19 before examining new assessment outputs. Status: completed; results and all trade-offs are in the
[implementation/evidence report](HANDOFF_REPAIR_REPORT_2026-10-19.md) and
[test report](HANDOFF_REPAIR_TEST_REPORT_2026-10-19.md). This work follows the [hold/empty/handoff diagnosis](LOCAL_WINDOW_HOLD_PRIVACY_ANALYSIS_2026-10-19.md).
Documentation and evidence will record negative results as well as improvements.

## Implementation scope and invariants

Repair the A03/A05 future-handoff subsystem while preserving measured-empty coordination
holds and the current immutable retirement/publication contract. The three changes are:

1. Schedule automatic future handoffs using the complete successor frontier of an endpoint.
2. Reconcile obsolete private plans when their descendants already share a compatible start,
   without resetting the active interval's deadlines, checks or evaluation budgets.
3. Allow a fully owned, passing parent to supersede contained private future plans atomically.
   Commit their cancellation only after the immutable pending publication is acknowledged.

Actual public disclosure and immutable pending recipient output remain binding. Enclosing
and unrelated plans must not disappear. A failed candidate must not mutate ownership;
coverage, observation conservation, metric/policy checks, source causality and resource
bounds remain independently auditable. Measured-empty support remains distinct from
unavailable samples. Reclaimable certificates for already retired zero support would be a
separate ledger/oracle extension and are not required for this targeted correction.

## Verification and development evidence

Add focused regressions for the known passing-parent conflict, redundant plans, contained
versus enclosing/unrelated requests, failed candidates, bounded deadlines and identical
sink retries. Demonstrate relevant regressions fail against the previous source. Run the
full CTest/Python suites, focused sanitizer builds and seeded coordination stress checks.

Use the original 30-case coordination matrix and the already examined 16-second robustness
population only as development comparisons. Preserve their frozen artifacts. Compare identical
inputs and numeric policies, audit raw source accounting, and verify unchanged common/fixed
references. Examine contribution retention, answered queries, paired-query error and exact
age on shared retained observations. Improvements on those data do not establish new privacy.

## Independent source-membership assessment

Freeze final controller/evaluator code and the following protocol before evaluating new
mechanism outputs. Generate a new v2 long-corridor dataset with seed **20261022**:

| Item | Fixed value |
|---|---|
| Independent groups | 48 base TRAIN, 32 base CAL, 64 base TEST, 64 count-shift TEST |
| Source horizon / cadence | 16000 ms exclusive end / 100-ms samples |
| Geometry | 80-m square, finest depth 6 |
| Scenarios | Sparse, dense, handover, heterogeneous; same v2 generator law |
| Shift | Background generated population multiplier 1.5; candidate law unchanged |
| Protected unit / secret | Candidate's whole recorded 16-s source contribution / source inclusion |
| Membership pair | Same background and sensor schedule; target contribution included versus excluded |
| Numeric policy | Support >=3, cell side 1.25–40 m, duration/age <=1000 ms |
| Input window / extension | 400 ms / 100 ms |
| Mechanisms | Fixed20m/1s, common TF/SF, corrected local TF/SF, frozen previous local TF/SF |
| Controls | Exact-count and no-output streams, separately labelled |
| Known points | Same random 25% candidate points across mechanisms/worlds |
| Knowledge profiles | Exact; independent xy Gaussian sigma2m and time jitter ±200ms, existing clipping rule |
| Attack families | Existing fixed logistic and pinned histogram gradient boosting, same31features |
| Fits | Separate TRAIN-only model per mechanism/profile/family; no test selection |
| Calibration | Base CAL only, empirical FPR<=0.1 operating point, unchanged on both TEST cohorts |
| Uncertainty | 400 scenario-stratified paired source-group bootstrap repeats; cohorts separate |
| Primary repair contrast | Corrected local minus previous local AUC, within priority/profile/family/cohort |
| Other comparisons | Corrected local versus common; all families/profiles retained |
| Utility | Source contribution retention, fixed10m/1s query coverage, matched-query MAE |
| Timing | Exact source-point age on old/new shared retained observations; logical sealing, not network latency |

The previous executable and source snapshot come from the completed seed20261021 robustness
study and are verified/frozen separately. The new assessment does not reuse its attack
models or thresholds. Every release is independently checked from raw input. Shared
common/fixed mechanism controls compare old/new executables for scientific equality.

This design measures the repair under the same population law with independently generated
realizations; it does not create a realistic city, type-conditioned releases or a different
sensitive secret. Regional-deadline effectiveness remains assessed by the separate controlled
coordination matrix. Full-history membership attacks do not measure recipient-prefix privacy.

## Interpretation criteria

The defect is repaired when the concrete passing-parent regressions succeed while all
publication/ownership/deadline invariants remain valid. Empirical effectiveness is reported
with actual utility/freshness/error trade-offs and conditional uncertainty, not assumed from
passing support checks. Any additional membership exposure must accompany a retention gain.
Pointwise intervals are not a simultaneous significance guarantee across all comparisons.
A result without a general privacy advantage must be reported as such; no seed, model,
threshold or preferred scenario will be selected after seeing these new test outcomes.
