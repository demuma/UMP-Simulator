# Urban privacy evaluation: the next four implementation gates

Date: 2026-10-25. Status: **P25.1, P25.2 and P25.3 complete**. The [frozen urban contract](URBAN_PRIVACY_MEMBERSHIP_CONTRACT_2026-10-25.md)
and [verified development fixture](URBAN_PRIVACY_P25_1_TEST_REPORT_2026-10-25.md) are
implemented. The [semantic recipient adapters and DEV pilot](URBAN_PRIVACY_P25_2_TEST_REPORT_2026-10-25.md)
are also verified. No urban attack assessment or held-out result is claimed. This is the implementation
sequence for the four agreed privacy tasks. The dissertation research questions
organize the interpretation; they do not add parallel implementation work.

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

**P25.4 is open: its v1 source-validity gate failed before primary analysis.** The primary runner, exact root-query coverage and exact
rate intervals pass 176 affected Python tests and all 22 existing-source DEV
recipient streams. Their implementation supplement is frozen before TEST.
The frozen TRAIN/CAL source attempt batch is completing its failure accounting.
A separately validated source-motion correction requires an explicit pre-TEST
version; groups/seeds/policy/analysis remain unchanged, all 40 TRAIN/CAL must be
regenerated, and models/thresholds locked before TEST sources. The inspected
pilot remains DEV only; completed primary privacy-benefit estimates are pending.
See the [P25.4 protocol](URBAN_PRIVACY_P25_4_PROTOCOL_2026-10-25.md) and
[validation/execution report](URBAN_PRIVACY_P25_4_TEST_REPORT_2026-10-25.md).
