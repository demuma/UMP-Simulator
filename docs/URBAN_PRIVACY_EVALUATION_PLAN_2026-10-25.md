# Urban privacy evaluation: the next four implementation gates

Date: 2026-10-25. Status: **P25.1, P25.2 and P25.3 complete**. The [frozen urban contract](URBAN_PRIVACY_MEMBERSHIP_CONTRACT_2026-10-25.md)
and [verified development fixture](URBAN_PRIVACY_P25_1_TEST_REPORT_2026-10-25.md) are
implemented. The [semantic recipient adapters and DEV pilot](URBAN_PRIVACY_P25_2_TEST_REPORT_2026-10-25.md)
are also verified. No urban attack assessment or held-out result is claimed. This is the implementation
sequence for the four agreed privacy tasks. The dissertation research questions
organize the interpretation; they do not add parallel implementation work.

## 26 October amendment: observed-track window

The user selected **every observed contribution of one operational track within
300 seconds**, with movement quality reported separately. The
[explicit contract](PRIVACY_TRACK_WINDOW_CONTRACT_2026-10-26.md) governs the NEW
`observed_track_window_v1` evaluation. The original complete-episode contracts and
failed source-family outcomes remain unchanged. A still-active, stalled or pending
journey alone is not a hard failure of the new observation-window unit; complete
source/GT/sensor clock, provenance and physical validity still are.

Finish/close the original strict forty-source TRAIN/CAL phase first. Independently
validate ALL forty existing captures read-only in their same roles under the new
profile, preserving original statuses and physical-audit provenance. Bind the new
evaluation manifest, immutable import ledger, code/test evidence and unchanged
original dataset assignment. Run fresh paired mechanisms/TRAIN fits/CAL locking,
then generate the original thirty-two untouched TEST slots in separate outputs.
No old lock, quality-selected subset, repaired route or replacement seed is valid.
The methods, policies, features, fitting/calibration, query/statistical analysis and
final-snapshot availability contract remain unchanged. Privacy results are pending.

The older gate descriptions below retain their historical P25.1–P25.3 scope;
completion-only requirements do not silently carry into the new declared unit.

## Goal and fixed scope

The goal is privacy-preserving sharing with useful urban mobility information.
Metrics guide protective release decisions and quantify their effects. Operational
track/category support, empirical inference risk and application utility remain
separate measurements. Current policy compliance alone does not establish the
protection delivered to a recipient.

Reuse the current mapped site, unchanged aggregator, taxonomy and existing attack
framework. Retain all historical datasets and results. Additional sites, a globally
adaptive uniform grid, new routing/GUI features, sensitive-visit attacks and new
aggregation heuristics are outside this block. The dense runtime issue remains
open under RT03 and is not a prerequisite for a logical offline privacy assessment.
Offline evidence does not certify live delivery performance.

## P25.1 — Define and verify the first urban membership contract

Start from the existing contribution-membership experiment. The first
unit is one visible observation episode within a fixed declared horizon. The
secret is whether that episode's source contribution was included, not physical
presence, identity, a building visit or all episodes of one physical person.
Fix the horizon, candidate selection, auxiliary knowledge, prior, public map/
taxonomy/policy knowledge and EOF treatment before executing the study. This
contract is the first concrete deliverable, preceding implementation of new
attack features and the main experiment.

Specify the entire recipient-visible product: approved counts, semantic category
labels/counts, geometry/cell IDs, intervals, release availability, public policy
metadata and observable no-release periods. Keep source IDs, GT, private unions,
suppression reasons, debug overlays and private runtime inaccessible to the attack.

Create OUT by removing the target episode's observations from a frozen IN source.
Preserve every background observation, batch timestamp and measured-empty status.
Do not resimulate traffic after removing the candidate. Candidate auxiliary
knowledge must be identical in IN and OUT and selected independently of publication
outcomes. Declare logical sealing versus actual wall-clock delivery explicitly.

Acceptance: a versioned threat/visibility contract and a verified matched IN/OUT
fixture, with unchanged background and explicit protected-unit limits.

## P25.2 — Close the two recipient/attack adapter gaps

1. Extend the strict scalar public-transcript path in `privacy.py` and
   `empirical_privacy.py` to validate and use actual semantic release fields.
   Use a versioned schema; retain old scalar-study compatibility. Never silently
   discard semantic output when claiming to evaluate the complete channel.
2. Produce a deterministic public recipient transcript for the regional static
   baseline. Its current audited composer exports only aggregate utility.
   Reuse its predeclared policy-only schedule and original audited public cells;
   verify causal availability, disjoint support and complete source partition.
   Do not manufacture a native execution or online runtime.
3. Extend public-only attack features, maintaining unknown-versus-zero semantics,
   and reuse existing causal release gating. Declare the feature set and fitting
   budget before held-out assessment. Audit any new public metadata or filter-
   aware product explicitly rather than adding private fields to the exporter.

Acceptance: validated semantic-aware recipient streams for every included method;
negative tests reject private-field leakage, altered semantic counts and premature
release visibility. A small plumbing pilot validates the new channel without a
privacy-benefit claim or tuning against final TEST outcomes.

## P25.3 — Record independent sources and freeze the experiment manifest

Completed: eight fresh native captures pass source/physical/independence checks;
the main 24/16/32 grouped design is prospectively frozen with zero generated
primary sources and zero attack fits. A source starvation defect was corrected
narrowly; failed source versions and broader prototypes remain negative evidence.
See the [P25.3 protocol](URBAN_PRIVACY_P25_3_PROTOCOL_2026-10-25.md) and
[test report](URBAN_PRIVACY_P25_3_TEST_REPORT_2026-10-25.md).

Start with eight independent same-site recordings as the reproducibility/source
pilot (the agreed 5–10 range). Keep map, configured demand/class distribution and
policy conditions fixed; vary declared trajectory-generation seeds. Record actual
class counts, active density and completion. Save each observation stream once
and replay exactly it for all compared mechanisms.

Those eight recordings are not automatically a sufficient TRAIN/CAL/TEST privacy
dataset. Use the pilot to set a bounded primary protocol and the additional
independent training/calibration/test source counts and uncertainty requirements.
Freeze this design before final test generation/evaluation; preserve pilot
results separately. Do not claim statistical power from the recording count alone.

All target episodes, IN/OUT worlds, policy/method variants and dependent excerpts
of one source realization stay in one split. Renamed IDs or nearby slices are
not independent realizations. Check source and background fingerprints.

Predeclare the comparator family using legal global fixed grids/windows, the
regional static reference and the adaptive method(s), all with identical hard
requirements within a policy condition. Fix baseline selection using declared
rules or development/calibration only, never final TEST results. The regional
static window rule remains independent of observations. State dimensions that
differ between methods; do not attribute a joint space/time/semantic change solely
to spatial adaptation.

Acceptance: completed source checks, grouped manifest, frozen methods/policies,
attack knowledge/features, analysis metrics, clocks/horizons and selection rules.

## P25.4 — Execute and report joint protection and utility evidence

Fit the declared attacks on TRAIN, set thresholds on CAL and evaluate untouched
TEST. Report ROC-AUC, observed TPR/FPR and threshold advantage with uncertainty
respecting source-group dependence. Include prior/auxiliary-only, unprotected and
no-output controls as appropriate to the fixed threat contract. Attack-control
failures must be diagnosed before interpreting lower success as protection.

Report risk beside retained-input coverage, full-input semantic distortion,
retained-only detail, fixed application-query utility where available, and logical
release delay. Do not treat equal track-support thresholds as equal measured
privacy or call one-minus-AUC a universal privacy measure. Preserve negative,
null and mixed-objective results.

Acceptance: one independently checked report and presentation-ready comparisons,
including all failed or incomplete cases, experimental limits and reproducible
receipts. Raw movement/private labels remain local; Git receives compact aggregate
evidence only. A second site is a later transfer question after this gate.

## Existing work reused

- [Current utility/timing results](STRATEGY_TIMING_LOCAL_POLICY_RESULTS_2026-10-25.md).
- [Existing empirical attack implementation](EMPIRICAL_PRIVACY_IMPLEMENTATION.md).
- [Threat-model roadmap](PRIVACY_EVALUATION.md).
- [Causal visibility implementation](CAUSAL_PRIVACY_IMPLEMENTATION.md).
- [Attribute and online contract](PRIVACY_ATTRIBUTE_AND_ONLINE_CONTRACT.md).

**P25.4 implementation is validated; the source-v2 main run is closed incomplete.**
All 72 source slots were attempted once: TRAIN 24/24 and CAL 16/16 valid, TEST
31/32 valid. All 40 TRAIN/CAL mechanism families and 22 model variants passed
verification and were locked before TEST source generation. A new doorway
local-navigation deadlock invalidated one TEST recording. The frozen source gate
stopped all TEST mechanisms and predictions; attack/control/TEST utility estimates
and the primary contrast remain unavailable. No seed replacement, available-case
AUC or substitute TRAIN/CAL headline was used. The main held-out research gate
remains open.

The next prerequisite is a bounded doorway-navigation regression/correction and
independently seeded DEV validation, followed by a fresh frozen evaluation cohort.
This source failure is not evidence of a failed attack, poor privacy or adaptive
inferiority. Keep all completed engineering evidence and both failed source
versions without pooling. See the [final outcome](URBAN_PRIVACY_P25_4_EXECUTION_OUTCOME_2026-10-26.md),
[compact source and mechanism outcomes](verification/urban-privacy-p25-4-2026-10-26-v2/final-outcome/README.md),
[pre-TEST amendment](URBAN_PRIVACY_P25_4_SOURCE_V2_AMENDMENT_2026-10-26.md) and
[validation/execution report](URBAN_PRIVACY_P25_4_TEST_REPORT_2026-10-25.md).

The source prerequisite now passes: the [doorway correction](URBAN_PRIVACY_DOORWAY_START_ATTACHMENT_FIX_2026-10-26.md)
completes 92/92 DEV cases and a verified production capture. Fresh unit validation
passes 177 methods, and the new 22-stream recipient integration with complete
archive/public/policy/feature/utility reconstruction passes. The accepted fresh
`urban-primary-20261026-v3` draft preserves scientific choices and excludes all
exposed sources; it has not generated new primary TEST data. The next gate is
reviewed fresh source/implementation binding, new TRAIN/CAL fits and locked
thresholds, followed by untouched TEST. The older incomplete result stays intact.

The [fresh source-v3 restart](URBAN_PRIVACY_P25_4_SOURCE_V3_RESTART_2026-10-26.md)
is now frozen and executing after independent source/manifest review, unchanged
freeze verification and all fresh validation gates. New TRAIN/CAL sources run
first, followed by new model/CAL locks, then new TEST sources and complete source
gates before evaluation. Scientific choices stay fixed; actual risk/utility
results remain pending. The earlier source-v2 result remains closed historical
evidence, rather than a current claim that the corrected source is still blocked.
