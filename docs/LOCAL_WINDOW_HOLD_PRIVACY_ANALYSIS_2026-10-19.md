# Local windows: holds, future reservations, type diversity and privacy

Date: 2026-10-19. Status: implementation audit and post-hoc controlled ablations.
Production controller source and the completed privacy studies are unchanged. The new
experiments use isolated executables and new private result directories. They explain
mechanisms on previously inspected data; they are not new confirmatory privacy results.

Read alongside [the earlier diagnosis](LOCAL_COORDINATION_DIAGNOSIS_2026-10-19.md),
[the robustness study](PRIVACY_ROBUSTNESS_STUDY_2026-10-19.md),
[the scenario inventory](SCENARIO_INVENTORY_AND_GT_LOSS_2026-10-19.md) and
[the canonical notation](TERMINOLOGY_AND_NOTATION.md).

## Assessment

Independent local windows remain a useful design option. The current algorithm does
not establish a general privacy improvement over common windows. Its observed weakness
combines uniform test policies, finite legal aggregation support, irrevocable release
trade-offs and avoidable private coordination decisions. A sound policy check is not
a proof that the coordinator finds every legal release or an optimal schedule.

At the abstract scheduling level, allowing different cell boundaries can include the
choice of common boundaries, provided all other constraints remain identical and early
release is optional. This additional freedom alone cannot make the best attainable
objective worse. The implemented causal heuristic does not search that whole schedule
space. It makes irreversible decisions without future observations, and therefore need
not dominate a common schedule in latency, retention, resolution and privacy together.

A separate earlier eight-realization regional-latency family retained 100% of source
contributions locally versus 51.71% on average with common windows under that study's
configuration. It is a finite utility result, with accuracy trade-offs, not evidence of
improved privacy or a universal best baseline. See [the refinement report](COORDINATION_REFINEMENT_2026-10-19.md).

## Four different reasons for missing output

| Cause | Evidence | Interpretation |
|---|---|---|
| Uniform numeric policy | Current robustness fixture uses support >=3, side 1.25–40 m and duration/age <=1000 ms everywhere; the west region repeats the same support bound. | The study does not exercise the intended benefit of unequal regional deadlines. Local timing still changes release freshness. |
| Infeasible legal support | In test-00015/PRESENT, 315 car observations arise from only two identities above y=40. All pedestrians/cyclists remain below that boundary. No legal <=40-m quadtree cell spans it. | Neither controller can meet support 3 for those car observations, even using the complete horizon. This is a population/geometry/policy limit, not a scheduling failure. |
| Actual earlier disclosure | A fine child has already been published over part of a proposed parent's interval. | Reusing its support violates the current immutable, nonoverlapping release contract. Deleting a MongoDB document cannot erase the recipient's earlier knowledge. |
| Private coordination/retirement | A passing, fully owned parent is rejected because a contained future handoff remains reserved; private retirements can also desynchronize starts. | These causes must be distinguished from actual disclosure. The demonstrated future-plan conflict is an avoidable scheduling limitation. |

The same test-00015/PRESENT case has 2204 pedestrian and 945 bicycle observations.
Common TF releases 2204/2204 and 933/945; current local TF releases 1677/2204 and
228/945. The additional 1232 missing local contributions are distinct from the 315
unavoidably unsupported car observations. One proven passing-parent conflict does not
attribute the entire difference to a single defect.

## What a hold and a reservation currently mean

A coordination hold extends a passing or empty owner's source interval. It is not
merely delayed delivery of a completed, fixed payload. New observations enter the
candidate; counts, geometry choices, feasibility and eventual publication can change.
The current hold test accepts any reconstructable, future-feasible ancestor containing
the owner. Feasibility says that a later pass is possible; it does not predict enough
arrivals or demonstrate that the expected gain justifies the latency cost.

A future handoff is a private plan to align ownership at a later boundary. It is not
a CPU mutex or a second database-reader wait. Three relevant scheduling details are:

1. New handoffs are created inside the sequential due-owner retirement loop. Some
   owners may already have successor starts while other owners still expose old starts.
2. The chosen boundary is the maximum next endpoint in that mixed frontier. The request
   completes only when all descendant starts equal that exact boundary.
3. Both ancestor assessment and merge execution reject overlapping future reservations.
   A broader passing parent can therefore be rejected even after compatible private
   starts have already been restored earlier than the reserved boundary.

In the previously verified witness, parent 13 over [1800,2100) passes every numeric
check, has complete compatible private ownership and contains no prior public release.
A contained depth-five request reserved for 2200 ms still blocks it. The earlier trace
shows that compatible starts were already available before that reservation completed.
This motivates endpoint-complete planning, redundant-request reconciliation and safe
supersession of contained future plans, not unconditional removal of ownership checks.

The separate immutable pending-publication object protects recipient delivery/retries.
A sink failure currently blocks further processing globally while that object is pending.
This is an online backpressure issue; it cannot explain the completed replay findings,
whose sink acknowledges immediately.

Source references: `CellLocalAggregation.cpp:107` (pending output), `:195` (common-start
ownership), `:259` and `:531` (future-plan vetoes), `:340` (boundary choice), `:367`
(exact-boundary completion), `:609` (future-feasible hold domains), `:643` (sequential
retirement), `:665` (automatic handoff request), `:697` (hold), `:712` (extension).

## Controlled hold/handoff ablation

The four factorial cells are the current baseline plus three isolated interventions:

- **No optional hold:** do not extend passing/empty siblings merely for coordination.
  Failed candidates still extend, future handoffs remain, and current-endpoint parent
  planning still precedes publication. This is not unconditional immediate publication.
- **No future handoff:** disable creation of all future resynchronization plans. Current
  endpoint merges and coordination holds remain. This removes useful plans as well as
  defective ones; its effect is not an estimate of the proposed targeted repair.
- **Neither:** apply both interventions.

All 128 previously examined held-out groups, both source-membership worlds and both
preservation priorities are used: 1536 new replays with identical inputs and numeric
policies. Cohorts remain separate. Eight unmodified relink executions reproduce frozen
scientific results across four scenarios and two priorities. Independent raw-data audits
check every changed result for counts, support, policies, ownership and conservation.
Exact age comparisons use only observations released by both the baseline and that
intervention. Different interventions have different shared subsets; their age differences
cannot be combined into an interaction effect. Runtime from concurrent jobs is not a
performance benchmark. Conditional query MAE alone cannot rank accuracy on different
answered subsets. No attack was fitted for these interventions.

| Cohort / priority | Current local | No optional hold | No future handoff | Neither |
|---|---:|---:|---:|---:|
| Base / TF | 90.7694% | 79.8043% | 96.5313% | 74.3762% |
| Base / SF | 91.3153% | 4.3671% | 96.6483% | 3.5573% |
| Count shift / TF | 94.7629% | 83.9571% | 98.3634% | 75.7627% |
| Count shift / SF | 94.1250% | 9.8980% | 98.4634% | 8.3409% |

These are pooled retained source-observation fractions, not percentages of distinct
people or total GT information. Each cohort contains 128 case-worlds; its denominator
is 341830 (base) or 530976 (count shift). TF preserves temporal detail by trying spatial
coarsening first; SF preserves spatial detail by extending time first.

Disabling all future handoffs increases retention by 3.6005–5.7619 percentage points
in the four cohort/priority summaries, nearly reaching the corresponding common-window
retention. This is not universal per-case dominance: 3–11 case-worlds per summary lose
some contributions. On observations shared with the original local controller, TF mean
age increases by about 14–16 ms; SF changes by less than 1 ms. This intervention removes
resynchronization as well as harmful reservations. It demonstrates the current handoff
subsystem's net cost on this population, not the effect of a targeted repair or an
increase in privacy. Disabling optional holds has the opposite retention effect here.

[Base-cohort comparison figure](figures/local-window-ablation-2026-10-19.png)
([SVG](figures/local-window-ablation-2026-10-19.svg)).


## Separating passing-owner holds from empty-owner holds

The first no-hold intervention intentionally disables both. Early private retirement
of an empty footprint is not a public release, so its effect must not be described as
a pure early-publication effect. A second post-hoc follow-up therefore separates:

- **Hold empty owners only:** passing owners may publish at their normal legal endpoint;
  empty siblings can still preserve compatible time support for a later parent.
- **Hold passing owners only:** passing siblings retain coordination holds; empty owners
  retire normally. Future handoffs and current endpoint merge planning remain enabled.

The follow-up uses all 64 base TEST groups, both IN/OUT worlds and both priorities:
512 additional independently audited runs. It does not re-evaluate the shifted cohort.
These follow-up choices were motivated by the first ablation; they are explicitly
exploratory, not an independently predeclared efficacy test.

| Coordination holds retained | TF retained contributions | SF retained contributions |
|---|---:|---:|
| Passing and empty owners (current baseline) | 90.7694% | 91.3153% |
| Empty owners only; passing owners may release | 90.7694% | 73.3367% |
| Passing owners only; empty owners retire | 79.8043% | 4.6775% |

Each column uses 128 paired case-worlds and 341830 source contributions. Removing only
passing-owner holds preserves the exact TF retained set and matched ages in all 128
worlds. Under SF it loses 17.9785 percentage points; the matched-point mean age improves
only from 541.42 to 534.38 ms on 250589 shared contributions. These are logical ages,
not measured delivery latency, and no attacks were evaluated for either intervention.

Dropping empty-owner holds causes the largest observed SF loss despite there being no
public release from those empty footprints. Current `compactFreshOwners` only joins four
fresh untouched siblings after proving complete empty prefixes, excludes overlapping
handoffs, and does not reconcile an advancing empty sibling beside an extending failed
sibling. The result identifies a strong dependence on private ownership synchronization.
It does not prove that empty data must intrinsically delay recipients for privacy.

One possible later design is reclaimable certification of measured-zero history while
empty owners advance computationally. A parent could include those certified zero
prefixes only after checking actual public overlap, unique nonempty ownership, retained
coverage and every current duration/age/policy bound. That changes the ledger and
independent oracle contract: it cannot be implemented by reopening published data,
unavailable samples or terminal nonempty suppression. It remains unimplemented.


## Privacy consequences

The implemented condition n(C,I)>=3 counts the union of identities in a cell and a
window. Three identities can appear sequentially while only one is present at each
sample. The condition does not define recipient equivalence classes or prove resistance
to membership, linkage, sensitive-attribute inference or combined release histories.

A local window can reduce exposure by avoiding unnecessary releases or by combining
otherwise revealing observations. It can also expose fresher or finer signals, change
which observations are retained, and reveal information through data-dependent geometry,
timing and publication absence. The current controller optimizes neither membership
AUC nor a formal privacy objective. The completed robustness experiment finds no general
local advantage: 15/16 paired intervals contain zero and one exploratory pointwise
contrast indicates higher attack success. These outcomes must accompany utility.

This is consistent with the attack surface studied by
[Pyrgelis et al., NDSS 2018](https://www.ndss-symposium.org/wp-content/uploads/2018/02/ndss2018_05B-5_Pyrgelis_paper.pdf):
aggregate location data can disclose membership, with effectiveness dependent on auxiliary
knowledge, population and time aggregation. Their numerical results are not UMP results.

A known fixed delivery delay applied to otherwise identical payloads does not improve
full-transcript privacy after every payload arrives: the complete observations can be
mapped back by that known time shift. It can reduce information available at a finite
recipient deadline. Current holds are a different intervention because they change the
aggregate itself. Data-dependent timing must remain part of the observable attack surface.
Neither more retention nor more suppression is by itself a measure of privacy.

A threshold-edge example makes the distinction concrete. Suppose an attacker knows that
two other road users contribute to a fixed candidate. If including the target changes
that candidate from suppression to a visible threshold-3 release, publication itself
reveals membership in this simplified setting. Alternative parent releases could change
the observation, so this is an explanatory counterexample, not a measured UMP attack
success rate. It shows why merely passing a support check is insufficient.

For example, if a snapshot's child count is 3 and its parent count is subsequently 4,
the residual count in the other children is 1. Additional knowledge can make that residual
revealing. This illustrates why later publication cannot generally erase earlier fine
information; the current no-overlap rule is a safeguard, not a complete privacy proof.

## More road-user types do not automatically worsen the result

A separate controlled test keeps 22 road-user identities, 384 source observations over
two seconds, positions, timestamps, policies and five auxiliary points fixed. Only
nominal type labels change: one class versus seven classes. Eight real replays across
common/local and both priorities pass independent auditing. The complete public
transcripts and all 31 attack features are exactly identical in every paired comparison.

This follows the current contract: distinct support pools all road-user identities;
public releases remove type breakdowns. Policy `type_requirements` applies to functional
region types, not road-user classes. The result concerns label-only changes within the
tested resource bounds, not genuinely different movement populations or runtime costs.

Mode-dependent speed, lanes, dwell and turnover change which identities can meet within
one legal cell/window. The heterogeneous fixture couples type, lane and speed strongly;
its losses cannot be attributed to category count alone. The current two-car infeasibility
example is about isolated local support, not the word "car".

Future public class counts need a separate disclosure contract. Total support 10 does
not make a subcount of one cargo cyclist safe. If each published class must meet the
same support minimum, splitting a fixed population into more classes can make those
requirements harder. Taxonomy generalization may help, but is not implemented. If type
instead becomes the declared sensitive attribute in an l-diversity experiment, greater
within-group diversity can help that condition; it still needs an explicit QI/SA model.
The original [l-diversity paper](https://www.cs.cornell.edu/johannes/papers/2006/2006-icde-publishing.pdf)
distinguishes background-knowledge and attribute-homogeneity risks from group size alone.
Neither classwise k nor l-diversity is implemented by the present support threshold.

## Recommended next implementation and evaluation

1. Repair coordination as an A03/A05 task: make future-plan decisions from a coherent
   endpoint state; reconcile redundant reservations; safely supersede contained future
   plans for a fully owned, passing current merge. Keep actual recipient commitments,
   deadlines, bounded search, retries and rollback invariants. Add the exact witness and
   nested/unrelated/failed-candidate/pending-sink regressions before changing behavior.
2. Keep optional holds explicit and bounded. Specify the benefit being preserved and
   the region/application deadline. Passing data should not wait for a stale private
   plan; conversely, publishing every passing child immediately can destroy a legal
   rescue option. Separate this scheduling policy from delaying a completed payload.
3. Freeze corrected code and then create independent assessment groups. Compare common,
   current local and corrected local under uniform and genuinely different regional
   deadlines, both preservation priorities, and controlled support/crossing regimes.
   Include a sensible fast-deadline common reference; do not manufacture local gains by
   giving common an avoidably late initial check. Preserve all existing negative cases.
4. Fit/calibrate an adaptive attacker separately for each mechanism using independent
   TRAIN/CAL groups. Assess full-history and predeclared recipient prefixes, with only
   then-available auxiliary knowledge. Report AUC/realized FPR together with deadline
   coverage, matched-query error, retention and shared-point age. A previously trained
   attack transferred unchanged to new outputs tests transfer, not adaptive privacy.
5. Introduce actual type-dependent movement and any public taxonomy fields as separate
   factors. Keep a label-only control. Sensitive attributes, classwise support and
   formal protection mechanisms require explicit additional contracts.

A07 remains selective descendant suppression after adaptation is exhausted; it is not
the task identifier for repairing the A03/A05 local-window coordinator.

## Artifacts and verification scope

Private directories under ignored `results/evaluation/2026-10-19/`:

- `privacy-hold-handoff-ablation-20261021-v1/`: intervention source copies, executables,
  build commands, protocol, raw outputs, independent audits, source/result hashes,
  observation-matched ages and rollups.
- `privacy-hold-subtype-ablation-20261021-v1/`: the passing-versus-empty hold follow-up, isolated builds,
  source copies, fixed policies, independent audits and paired base-cohort results.
- `privacy-type-label-invariance-20261021-v1/`: fixed-kinematics type-label inputs, commands,
  exact public-transcript/feature equality checks and eight independent audits.
- `privacy-local-diagnosis-20261021/hold-handoff-review.json` and the adjacent `.py`:
  independent streaming verification of the main ablation. `plot-hold-handoff-analysis.py`
  regenerates the exported comparison figure from the completed reports.

Both completed ablation bundles record 2048/2048 valid independent raw-data audits and
16 unchanged-relink scientific equality checks. The separate type-label control adds
eight valid audits and four exact public-transcript/31-feature equality comparisons.
The main run verifies unchanged production controller and original study-report hashes.
An additional independent streaming review passes 7019000 assertions over the main
1536-run bundle: all 1560 artifact hashes, all retained/lost/gained source-point sets,
exact matched age sums, 60 rollups and 20 retention interactions. It processes the large
full-audit JSON incrementally; the recorded elapsed time is 73.94 seconds. The interactions
confirm that hold and handoff effects are not additive. The scientific figure was visually
inspected. New outputs include no fitted attack and establish no privacy improvement.
Source-copy interventions are diagnostic switches, not supported production configurations.

A separate streamed review of the passing/empty follow-up passes 7508 assertions:
534 artifact hashes, all 512 recorded audits/raw contribution partitions and 20 rollups.
It does not repeat the main review's per-point age reconstruction. Its report and helper
are `privacy-local-diagnosis-20261021/hold-subtype-review.json` and `.py`; recorded time
is 18.25 seconds. These checks supplement the independent oracle run for every replay.


No production controller edits, simulator configuration changes, database writes or
GitHub publication were performed for this investigation. New evidence is documented
in English; code corrections and fresh privacy assessment remain outstanding.
