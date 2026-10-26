# Privacy contract: observed track contributions within a fixed window

Date: 26 October 2026. Contract identifier:
`ump.privacy-track-window-contract.v1`. Status: **user-selected scientific contract;
prospective implementation and study binding required**. This document does not
modify a frozen experiment or certify that its current helpers already implement
the revised source gates.

The protected unit is **all observed contributions of one operational track
within a fixed 300-second recording window**. Movement quality is measured and
reported separately. A still-active track is a valid candidate under this unit
when its recorded observations and their physical/data provenance are valid;
its journey need not finish inside the window.

The current frozen source-v3 series continues unchanged under its original
rules. Historical source statuses, protocols, recordings and results remain
immutable. In particular, a source that fails its original scheduled-completion
gate stays invalid for that original study. Applying this contract requires a
separate, explicitly versioned protocol and authenticated validation receipts.

## Protected data, neighboring inputs and secret

Let the public horizon be \(H=300000\,\mathrm{ms}\), with observation support
\([0,H)\). Let \(\mathcal T_H\) contain the actual measured timestamps within
that support. The frozen observation input is

\[
D_H=((m_t,O_t))_{t\in\mathcal T_H},
\]

where \(m_t\) retains the original batch sequence, timestamp and measurement
metadata, and \(O_t\) is its ordered observation list. A valid source record
\(o\) has an operational track token \(\operatorname{id}(o)\), observation time
\(t_o\), position and the existing sensor attributes. Define the selected
track's complete **observed window contribution** by

\[
C_e^H=\{o\in O_t:t\in\mathcal T_H,\ \operatorname{id}(o)=e\},
\qquad n_e^H=|C_e^H|.
\]

The neighboring inputs are

\[
D_H^{\mathrm{IN}}=D_H,
\qquad
D_H^{\mathrm{OUT}(e)}=
\bigl((m_t,[o\in O_t:\operatorname{id}(o)\ne e])\bigr)_{t\in\mathcal T_H}.
\]

OUT removes **every** observation bearing token \(e\) inside the window,
including contributions preceding an unfinished/censored ending. It does not
remove only a last sample, a cell contribution or the auxiliary-known subset.
No movement, collision, interaction, route, queue, classification or measurement
timestamp is resimulated. Every background observation retains its value and
order. All measured batches remain, including original empties and batches made
empty by target removal. A missing measurement is not converted into an empty
measurement. IN remains the authenticated original source.

For a balanced experiment, \(B\in\{0,1\}\) selects OUT or IN with
\(P(B=1)=1/2\). The secret is whether \(C_e^H\) was included in the mechanism's
input. This is **contribution membership**, not whether the road user physically
occupied the scene. Removing recorded contributions does not create a new
physically simulated counterfactual.

This unit promises no protection for an entire journey, a physical person, a
building visit, all visits of one person or a track beyond \(H\). A later track
token, even for the same synthetic person, remains background. Private GT
association must not merge tokens into a person-level unit. Track fragmentation,
linkability and tracking errors remain limitations of this operational scope.

## Target eligibility and auxiliary knowledge remain fixed

The target set is

\[
\mathcal E_H=\{e:n_e^H\ge2\}.
\]

Valid observations of a track that is active at \(H\) are eligible on the same
terms as observations of a track that ended before \(H\). Completion, an EOF
end event, destination arrival, type, motion quality, policy satisfaction,
release success or attack score does not select or reject a target. A track
with fewer than two samples is ineligible **as the selected attack target**;
its observations remain in every background input. All other unselected tracks
also remain. An eligible set with no member is an explicit attack-construction
failure, not permission to draw a replacement source.

Retain the existing `target-v1` hash ordering, source-observation hash and
independently assigned target-selection role seed. Select the minimum hash over
eligible operational tokens, with the original token as tie-breaker. Do not
change the ranking after inspecting outputs. Hashes, tokens and ranking receipts
are private audit material, not attacker features.

The approved auxiliary record remains an exact quarter-count sample with upward
rounding from \(C_e^H\):

\[
k_e=\max(1,\lceil n_e^H/4\rceil).
\]

Use the existing independent auxiliary-selection role seed and `aux-v1` hash
ordering, canonical point-byte tie-break and final chronological order. This is
not independent 25% Bernoulli sampling. Approved fields remain exact
`observed_at_ms`, `x`, `y` and public finest-grid `cell_id` only. IN and OUT use
byte-identical auxiliary records. No type, person identity, route, lifecycle,
destination, quality flag, private source identifier or post-window observation
is added to attacker knowledge. Auxiliary sampling uses the full observed
window, including a censored track's retained samples; it is not a causal-prefix
knowledge contract.

The approved public recipient channel, semantic/scalar feature representations,
control attacks, fitting budget, calibration rule, method family, policy
conditions and grouped uncertainty analysis remain unchanged unless a separate
prospective amendment explicitly identifies a necessary compatibility change.
This protected-unit revision is not authorization to tune them against results.
The [original membership contract](URBAN_PRIVACY_MEMBERSHIP_CONTRACT_2026-10-25.md)
and [evaluation plan](URBAN_PRIVACY_EVALUATION_PLAN_2026-10-25.md) retain their
historical meanings; their complete-episode source requirement is not imported
into this new windowed unit.

## Hard validity gates and independent movement-quality diagnostics

The full source clock must reach \(H\) under the declared fixed timestep and
measurement schedule. Observation support still uses \([0,H)\); a lifecycle
event or summary at \(H\) does not fabricate a sensor batch at \(H\). The
existing 100-ms sensor schedule contains its actual 2,999 measurements at
100 through 299900 ms. Neither a zero-time measurement nor an additional EOF
measurement is manufactured.

| Item | Hard validity requirement | Separately reported quality information |
|---|---|---|
| Execution and clock | Authenticated native exit zero; full 300-second numerical horizon; expected source steps, sampling times and measurement statuses. A crash, timeout, truncated clock or missing required batch fails. | Operational source/audit elapsed time, with its actual scope; no mechanism-only real-time inference. |
| Provenance and source law | Frozen binary/configuration/geometry/generator hashes, source law, seed/split binding, configured demand and recording/export agreement. | Realized observed population, class contributions, active density and entry/exit counts. |
| Recorded visible intervals | Every stored sample agrees with valid native GT and the track's recorded visible interval intersected with \([0,H)\); stable token/attributes and lifecycle ordering; expected-versus-recorded observations agree. | Observed trace lengths and durations; right-censored active tracks; scheduled episodes that never started within the window. |
| Geometry and motion | Actual recorded positions/sweeps satisfy the declared allowed geometry, access permissions, speed/displacement rules and physical separation, under fixed audited numerical tolerances. A physical overlap or invalid sample fails. | Reported blocked/stalled steps, wait durations, replanning failures, oscillations and congestion; these do not excuse physical/data violations. |
| Journey/visit completion | No requirement that every scheduled episode starts or ends by \(H\). No artificial exit or completed visit is inserted. | Scheduled, started, ended, active and pending episode counts; completed visits/returns; uncompleted intended trips. |
| Attack construction | At least one valid observed track has two samples; target removal, background preservation and auxiliary equality pass. | Eligible versus short/unobserved trace counts and selected-track length/censoring/quality summaries. |

An active track with a valid start and no observed end is right-censored at
\(H\); its expected GT/sensor interval extends to the actual recording boundary.
It must not be rejected merely for lacking an in-window end event. A scheduled
episode that has not started contributes no invented observations; report it as
pending. Proper starts, recorded ends where present, no post-end samples and
consistent visible-interval coverage remain mandatory. Censoring is not a
license for malformed lifecycle data or missing observations.

All-scheduled-journeys completion, all-visits completion and zero reported
stalls are therefore **not hard privacy-source gates in this contract**. The
old validator's completion-only checks cannot simply be ignored at runtime:
a separately implemented, versioned window-validity validator must retain the
independent physical/provenance checks while classifying completion and movement
quality explicitly. Its tests must distinguish valid censoring, pending demand,
malformed lifecycle, incomplete recordings and genuine physical violations.

No observations are dropped because they are slow, stationary, oscillating,
censored, difficult to aggregate or unfavorable to an attack. Do not trim a
recording to its successful prefix, selectively remove pathological agents,
resimulate OUT, force a destination arrival, synthesize an EOF exit or silently
filter a source based on its quality. Preserve every planned source attempt and
explicit invalidity reason. Predeclare any later sensitivity subset and retain
the full-input primary result; a post hoc subset remains exploratory.

## Scientific interpretation and sensitivity reporting

Movement pathology is **not a privacy benefit**. A stationary or oscillating
source can produce different support, redundancy, release coverage, utility and
attack difficulty from realistic urban movement. Including its valid observations
under this unit does not establish realism, ordinary boundary censoring or
successful navigation. A low measured attack score on such a source is scoped
to that source distribution and must not be advertised as general protection.

Report privacy and utility together for every predeclared source/method, with
source-group dependence and the original TRAIN/CAL/TEST separation. At minimum,
accompany them with:

- Source-level scheduled/started/ended/active/pending counts and the full-window
  completion flag; observed density and contribution/class totals.
- Reported stalls, crossing/door waits, replans and known oscillations, clearly
  distinguishing native counters from independently audited measurements.
- The target's observed length/duration and censoring status in private audits;
  compact public distributions and counts without track/person identifiers.
- The number of physically/data-invalid attempts and every excluded source,
  including whether exclusion preceded target selection and model fitting.
- Any prospectively declared sensitivity comparison by completion or quality,
  its source counts and uncertainty. Exploratory source exclusions must be named
  and cannot replace the primary all-valid-window estimate or calibrate TEST.

Final-snapshot membership evaluation still includes actual EOF sealing at
\(H\). Mechanism EOF publication is distinct from a simulated road user's
exit: it must not manufacture lifecycle completion. Retain causal availability,
unknown-versus-zero semantics and the same horizon in IN/OUT. Offline results
do not certify incremental delivery, deadlines or real-time performance.
Operational track/category support is not automatically k-anonymity or
l-diversity. This empirical membership game is not differential privacy and
does not establish resistance to every adversary or protection of sensitive
visits/attributes. Separate trajectory or attribute inference studies need
their own secret, unit, knowledge and evaluation design.

The diagnosed eastern-crossing steering oscillation is a **future source-quality
TODO**, alongside recovery-timer behavior and receiving-apron dependencies.
Keep its retained recording and diagnosis visible in quality reporting. It is
not reclassified as a completed journey or used as an automatic privacy
eligibility filter. This contract requests no source C++ correction during the
currently frozen capture series. The earlier
[bounded start-attachment correction](URBAN_PRIVACY_DOORWAY_START_ATTACHMENT_FIX_2026-10-26.md)
remains valid within its declared DEV scope; its 92-case pass was never a
general crowd-liveness guarantee.

## Separate binding, reuse limits and release gate

Before any newly contracted assessment:

1. Preserve the current frozen source-v3 batch, its original gate decisions and
   all attempt receipts. Finish its predeclared execution without changing the
   validator or replacing seeds. This document does not reopen the closed
   source-v2 study or rewrite source-v3 status.
2. Bind this contract, a tested window-validity validator, unchanged source
   implementation, source artifacts, attacker/method choices and implementation
   receipts to a **new study/protocol identity**. Record the amendment history
   and the development knowledge that motivated it.
3. The 40 current TRAIN/CAL capture slots may potentially supply authenticated
   raw observations to that separately bound study **only in their same original
   24 TRAIN and 16 CAL roles**, after all window-validity gates pass. Reuse is
   conditional, not established by this document. Retain the original source
   status and add a distinct new-contract validation result; do not mutate the
   original receipt or call an old invalid source retrospectively valid. Bind an
   explicit private mapping from the original source/protocol hashes and source
   slot to the new study slot, with original and new roles. Preserve the assigned
   source, target-selection and auxiliary-selection role-seed values; a new
   study identity must not silently rederive them or alter split membership.
4. Reconstruct pairs/features and fit/calibrate new artifacts under the new
   binding. Never import old-study fitted models, thresholds or results as new
   held-out evidence. No source from an earlier exposed TEST cohort can become
   fresh TEST, and no TEST artifact may be moved into TRAIN/CAL to repair a gap.
5. The current 32 planned TEST slots remain ungenerated and unseen. Keep them
   sealed until the new protocol, implementation checks and TRAIN/CAL model lock
   are authenticated. Recheck and record that all 32 proposed TEST source slots
   are still ungenerated and unseen when the new binding is authenticated;
   this document's current-state statement is not a substitute for that gate.
   No TEST-driven eligibility, model/threshold tuning, seed
   replacement or available-case headline is permitted. Preserve all planned
   attempts and the prospectively declared failure/NA rule.

The old study's outcomes and any new track-window results answer different
contracts and must be named separately. Successful implementation of this
contract would permit measurement of contribution-membership risk and utility
for valid observed track windows. It would not prove source realism, completed
journeys, person-level protection or that the adaptive method outperforms a
baseline. Those conclusions require their own evidence.
