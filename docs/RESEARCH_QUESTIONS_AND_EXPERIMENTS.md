# Research questions, data requirements and experiment plan

Status: 2026-10-19. Utility and policy fulfilment remain the immediate experimental scope.
EP01 and the first E02-A–C controlled synthetic membership evaluation are implemented.
[EMPIRICAL_PRIVACY_IMPLEMENTATION.md](EMPIRICAL_PRIVACY_IMPLEMENTATION.md) and the
[test report](TEST_REPORT_2026-10-19.md) separate actual evidence from broader EP02–EP04
sweeps, sensitive-attribute studies and formal claims that remain pending.

This document distinguishes a current answer, a hypothesis and an experiment that still
needs to be implemented. The [pilot report](EVALUATION_RESULTS_2026-10-14.md) contains actual
results. The [replay contract](CONTROLLED_EVALUATION.md) defines the existing evaluation.

Canonical terms, symbols, units and code mappings are defined in
[TERMINOLOGY_AND_NOTATION.md](TERMINOLOGY_AND_NOTATION.md). Aggregation is bound to
a data cell and time interval; functional regions supply its requirements.

## Central question and what counts as an answer

Under which observation and regional-policy conditions can the adaptive algorithm produce
useful, policy-compliant releases within its permitted spatial and temporal bounds?

A complete answer needs three separate properties:

- **Compliance:** every emitted cell satisfies its applicable requirements.
- **Availability and utility:** enough of the fixed application query can be answered with
  acceptable error and age; suppressing everything is not a useful success.
- **Search effectiveness:** where a valid alternative exists, determine whether the chosen
  coordination model and search actually find it. Compliance alone cannot establish this.

The current pilots show compliance of emitted cells and differences in utility/coverage/age.
They do not prove search completeness, optimality, general superiority or empirical privacy.

## Question register

| ID | Question | Current answer | What settles the remaining part |
|---|---|---|---|
| Q1 | Do published cells meet their effective policy? | All emitted cells in the 21 pilot scenario/configuration combinations passed the configured checks. This is finite evidence, and publication is already gated on those checks. | Independent recomputation and small-case oracle; randomized boundary cases; formal soundness argument. |
| Q2 | When is no useful compliant output possible? | Sparse support, incompatible footprint requirements and hard size/time limits can prevent output. Current suppression does not prove that every alternative was infeasible. | Exhaustive small-case feasible-set calculation; distinguish impossible full retention from impossible partial output and from search/model limitations. |
| Q3 | Is adaptation more useful than fixed aggregation? | No universal winner in the pilots. The actual capture shows higher coverage/lower conditional error for Spatial First than Temporal First, with greater simulated age. The 10-m/1-s fixed baseline has nearly zero conditional error on a smaller answered subset. | Paired scenario/policy sweeps, fixed baselines over the same legal range, unchanged query and separate coverage/error/age reporting. |
| Q4 | Which preservation priority is useful under which conditions? | Handover changes the action order; one permanently unresolved branch can make both strategies extend the same shared window. | Controlled identity turnover at fixed occupancy, dense/sparse cases, and a single blocked branch; inspect complete interval sequences. |
| Q5 | How should missing and empty support be interpreted? | Current public absence is unknown. Internal measured-empty, missing input, suppression and incomplete public query support are distinct. | Diagnose private causes without supplying them to the recipient estimator; define an explicit policy/release contract before introducing public empty certificates. |
| Q6 | Do we need more data for additional utility/statistical metrics? | Exact finite-data errors/distributions can be computed on small fixtures. Broader conclusions need relevant variation, independent realizations and a fixed estimand. More frames from one trajectory do not supply independent runs. | Select application task and sampling unit first, then plan replication from pilot variability and desired precision. |
| Q7 | What data would make additional privacy metrics meaningful? | The historical full-background membership diagnostic has a unit/secret/transcript contract; realistic attacks and several other metrics still lack finalized contracts, reference data or labels. | Freeze E02-A, then implement E02-B/C after the utility/policy entry milestone; use the readiness table for other metrics. |
| Q8 | Can the implementation meet runtime requirements? | Replay core timings omit parsing, persistence, transport and rendering; they do not establish end-to-end real-time operation. | Separate repeatable profiling and processing-budget tests on frozen input, with stage timings and deadlines. |
| Q9 | Under which knowledge/scenario conditions does adaptive aggregation reduce contribution-membership inference, and at what utility cost? | A first controlled synthetic public-only benchmark is implemented and executed; see the October 19 test report. Real-world protection is unresolved. | Expand independent/scenario/attacker evidence from the frozen E02-A–C protocol; higher support or policy compliance alone does not settle the question. |

## Initial decisions for a comparable experiment

Keep the present occupancy task: fixed 10-m spatial cells and 1-second query intervals on
an 80-m square, using scheduled 100-ms samples. Keep all reference queries in the coverage
denominator, including truly empty ones. Report errors only where the prediction and
reference are defined. An unanswered query is not an error of zero.

Keep current sparse-publication semantics as the first baseline. For diagnosis only,
record whether absent support stems from a measured-empty area, incomplete observations,
policy suppression or a released footprint that only partly covers the query. These causes
may coexist within one query; a reason breakdown must therefore declare whether it counts
samples, area-time support or multiple flags. Private GT never fills public prediction gaps.

A future empty certificate needs an explicit approved representation and disclosure rule.
It cannot silently bypass a minimum-support requirement, which an empty cell does not meet.
An offline reconstruction using hidden GT zeros would answer a different experiment.

Support thresholds remain operational constraints. Use `k_support` for a minimum number
of distinct road-user IDs, reserving formal k-anonymity for an explicit record/QI model.
Road-user IDs describe simulated entities; a vehicle ID does not count its occupants.

## Evaluation quantities and denominators

Let R be emitted cell/window records and Q the fixed reference queries. For each q, y(q)
is the GT mean sampled occupancy and y_hat(q) is the public-only reconstructed answer.

    release_compliance = passing released cells / number of released cells
    query_coverage = answered queries / number of fixed reference queries
    occupancy_MAE = mean(|y_hat(q) - y(q)| over answered, reference-available queries)
    contribution_retention = released observation contributions / input contributions

Release compliance is undefined when there are no released cells; report `no_release`,
not 100%. MAE is undefined when no query can be scored. Retention is undefined with no
input contributions. Record those cases explicitly rather than inventing favorable scores.
These quantities already have implementations or direct inputs, except for the proposed
expanded no-output/cause summaries and the oracle comparisons below.

Also report per-region coverage, suppression counts/reasons, release side/window-size
summaries and simulated sealing-age median/p95/max (planned beyond the current mean/range).
Declare weighting: one weight per emitted cell, per release document or per input sample
answers different questions. Do not calculate a percentile over an unspecified mixture.

For paired algorithm comparisons report both each method's full-domain coverage and error
on their common answered/reference-available query set. A smaller common set is visible in
its own denominator. Do not collapse error, missingness and age into a single score unless
an application has supplied the relative costs. Use separate trade-off plots instead.

## EP01 — Independent compliance and feasibility reference

Purpose: distinguish a correct refusal from an unnecessary loss under the declared model.
Start with one depth-1 domain, four finest children (leaf depth 2), a short sequence and
three to six legal candidate endpoints. Hand-work the expected outcomes first.

The independent oracle reads raw frozen observations and directly recomputes identity unions,
contributions, coverage, cell sizes, time bounds and root/type/region requirements. It must
not call the production selector/evaluator or trust their pass flags. Its first supported
policy subset is minimum distinct support plus maximum side/window/age and complete coverage;
claims about other registry metrics require corresponding independent checks.

For the same fixed interval enumerate nonoverlapping cuts. In the general partial-release
reference a node may be suppressed, released if passing, or replaced by its children.
Calculate whether full observed-support retention is feasible and the maximum number of
releasable contributions. Empty intervals are reported separately. No publication overlap,
retroactive retraction or reuse of already retired support is allowed.

Two reference classes must be kept distinct:

1. The current whole-grid/common-window and whole-sibling coordination rules.
2. A relaxed partial-child-rescue model that can retain passing siblings (future A07).

A gap to the second class identifies a model limitation, not automatically a coding defect.
Likewise, compare the current whole-grid deadline with a local-deadline alternative only as
a separate model. The present implementation applies the strictest duration/age cap across
the whole coordination domain, including empty regions.

Enumerate permitted endpoints instead of assuming monotone feasibility. Exact ID support
cannot decrease when extending fixed-start support, but other metric bounds, newly touched
regions, size limits and changing candidate choices can defeat monotonicity of the whole
policy predicate. An upper bound using future observations is an offline reference, not an
online competitor with the same information.

Outputs: violation list, full-retention feasibility, any-output feasibility, best feasible
retained contributions, algorithm retention gap and binding requirements. A zero-gap result
is scoped to the enumerated domain, intervals and supported policy subset.

Acceptance: exact hand cases for sufficient support, impossible support, handover, a strict
regional crossing, one failing sibling, missing input, and deadline/size boundaries.
Implemented in `tools/evaluation/oracle.py` with bounded references and raw compliance
recomputation; tests include exhaustive depth-2 patterns and actual seven-mode replay.
See the test report for evidence and the demonstrated partial-rescue model gap. Larger
search/online-optimality and independent cell-window claims remain outside this reference.

## EP02 — Controlled mechanism cases

Use deliberately small frozen streams before increasing simulation complexity. Start with
five named cases: stationary dense support, stationary sparse support, constant occupancy
with changing identities, a dense area plus one blocked branch, and a measured-empty interval
contrasted with an explicitly unavailable interval. Add the strict-region crossing as the
policy-boundary case. These cases can be implemented without realistic maps or new attributes.

For each case compare identical observations under fixed aggregation, spatial-only,
Temporal First and Spatial First. Keep the current seven modes for continuity; the handover
case should reproduce the known early-parent versus later-fine-cell behavior. Add symmetric
regional cases to isolate policy effects from density and movement differences.

The first outputs answer Q1/Q2/Q4/Q5: what is published, which constraint prevents more,
which interval changes, and whether the common-window model delays unrelated support.
No statistical confidence interval is attached to a deterministic hand case.

## EP03 — Policy and utility parameter study

After EP01/EP02 pass, use a staged sweep instead of changing every parameter simultaneously.
Initial mechanism levels are illustrative and predeclared, not validated privacy choices:

- Uniform `k_support` in {2, 5, 10}; add {k-1, k, k+1} hand cases at each threshold.
- Maximum allowed cell side in {10, 20, 40} m, on the same finest input grid.
- Maximum window/age in {400, 700, 1000} ms; adaptive base 400 ms and step 100 ms.
- Vary one bound at a time from the existing baseline, then selected interactions near
  observed transitions. Record an explicit case list and its size before execution.
- After uniform rules are understood, add regional stricter support and tighter deadlines
  separately, then combine them. Keep the same policy for every mechanism in a comparison.

Fixed baselines must cover the permitted operating range. The current 10/20-m by 400/1000-ms
matrix is a useful initial subset, not the best fixed strategy by definition. For extended
comparisons include additional legal grid sides/windows or explicitly limit the claim to
the evaluated subset. A fixed window violating a 700-ms cap is a labelled infeasible control,
not an admissible competitor used to inflate adaptation's apparent benefit.

Select or report policies against application costs without using the final evaluation set
to choose favorable thresholds. The 10-m/1-s fixed baseline matches the application query;
its zero conditional error is explainable alignment, not an unfair comparison to discard.
If a different application query is studied, label it separately and keep it common to all
methods. Do not change the query to whichever resolution a method happened to release.

Output: observed release/no-release regions of the parameter space, coverage-error-age
trade-offs, retention, per-region losses and paired strategy differences. Claim infeasibility
only where the bounded oracle or a supporting argument establishes it. Identify cases where
adaptation loses or both priorities coincide. This matrix has not been executed yet.

## EP04 — Replication and runtime evidence

Generate distinct frozen captures/realizations under each selected scenario, then replay all
strategies on each one. The independent realization is the initial statistical unit; its
frames, cells and seven algorithm outputs are dependent measurements. Replaying identical
input is a determinism check, not another independent data sample.

Compute paired differences per realization. Keep scenario strata visible and report their
chosen weighting before pooling. Use a pilot to estimate variation, then choose replication
from the precision required for a declared effect/estimand and available budget. There is no
universal sufficient number such as 30 runs. For interval estimates state independence/model
assumptions and the resampling unit; do not bootstrap individual frames as independent cases.
NIST describes how replication estimates variability and how confidence intervals depend on
sample size and variance: [replication](https://itl.nist.gov/div898/handbook/pri/section5/pri5971.htm),
[confidence intervals](https://itl.nist.gov/div898/handbook/prc/section1/prc14.htm).

Keep performance measurement separate. Use repeated timing on identical input, varied run
order and fixed build/machine context for core profiling. A live real-time claim additionally
needs persistence, queue and renderer stages with their actual deadlines. Existing wall-clock
influence on motion (R02) prevents equivalent fresh simulator runs based on configuration
alone; freezing input preserves a fair replay comparison but does not correct that limitation.

## Future privacy metric readiness

These are prerequisites and research questions for E02/E03, not additional current experiment
runs. Privacy contract planning is active; implementation has an explicit entry milestone in
[PRIVACY_EVALUATION.md](PRIVACY_EVALUATION.md#e02-staged-work-packages-and-entry-criteria).
The first proposed empirical secret is contribution membership, which needs no invented
sensitive attribute. Classical k/l/t criteria were formulated for released/generalized person
records; our aggregate count stream needs a justified mapping before those labels describe
its guarantees.

| Candidate | Required contract/data | What current data cannot establish |
|---|---|---|
| k-anonymity | Protected entity, released record, quasi-identifiers, equivalence relation and repeated-release semantics. | Distinct IDs per cell/window provide support, not a demonstrated person-level equivalence class. |
| l-diversity | Meaningful sensitive attribute S, entity/group membership, domain/time scope, and a selected diversity definition. | Type contribution counts are neither a justified sensitive secret nor a deduplicated entity distribution. |
| t-closeness | The l-diversity setup plus reference population/table and time scope, weighting and distribution distance; categorical distances if required. | Regional traffic-composition differences alone are not evidence of sensitive-attribute disclosure. |
| delta-presence | Public population, private membership subset, release/knowledge model and the resulting conditional membership probabilities. | A local count or empirical classifier score is not the formal membership-probability bound. |
| Entropy or information measures | Explicit random variable, probabilities and conditioning. Type heterogeneity and uncertainty about a target are different estimands. | High traffic-type entropy by itself does not quantify privacy. |
| Membership / trajectory linking | Target secret, visible release history, auxiliary traces/knowledge and labelled evaluation cases; disjoint training/test cases if learned. | These attacks do not inherently require an extra sensitive attribute, but their success is not determined by cell counts alone. |

These distinctions follow the original definitions of
[k-anonymity](https://dataprivacylab.org/dataprivacy/projects/kanonymity/kanonymity.pdf),
[l-diversity](https://www.cs.cornell.edu/johannes/papers/2006/2006-icde-publishing.pdf),
[t-closeness](https://www.cs.purdue.edu/homes/ninghui/papers/t_closeness_icde07.pdf) and
[delta-presence](https://www.cerias.purdue.edu/assets/pdf/bibtex_archive/p665-nergiz.pdf).
Their applicability to this aggregate release schema is a research decision, not established
merely by calculating a formula. The separate [privacy contract](PRIVACY_EVALUATION.md)
describes the existing optional membership stress test and staged empirical attacker study.

For entity-based attribute statistics, count each protected entity once per defined group/
window. A pedestrian observed 100 times and a cyclist once produce observation weights
100:1 but entity weights 1:1. Both are computable; they answer different questions. If an
attribute is time-varying or trip-based, define its unit and transitions rather than silently
assigning one label to an entire person or trajectory.

A future sensitive-attribute contract should name the secret, why its disclosure matters,
whether it is known to the attacker, how it relates to mobility, and whether it appears in
public output or is inferred from movement. A synthetic trip-purpose/visit category may be
useful for implementation tests, but an arbitrary label independent of every route can make
diversity easy without exercising the intended inference problem. Compare controlled
independent, correlated and skewed assignments without presenting synthetic correlations as
observed facts about real populations. Keep latent labels in private scenario metadata and
provide only the declared sensor information to the aggregation algorithm.

An attribute tied to a place may already be revealed by destination knowledge. The prior
baseline must include that knowledge; an attribute copied from the exact published cell
would make the experiment circular. Likewise, realistic maps alone do not provide a
population model, sensitive labels or a validated attacker.

## Implementation progression

October 19 update: the small independent oracle, seeded paired datasets and first public-only
empirical study below are now implemented. The earlier sequence is preserved as design
context; full EP02–EP04 regional-policy sweeps and advanced coordination remain open.


Start EP01 with the smallest independent compliance/feasibility cases and add private
suppression-cause diagnostics needed for EP02. Preserve the current public release protocol
and existing utility query while these checks are established. Then run EP02, followed by
the explicit EP03 matrix and EP04 replications. E02-A freezes the privacy contract alongside
this design work; E02-B/C starts after the minimal independent utility/policy checks and
public-schema contract are in place. Broad
map/routing realism is not a prerequisite. Sensitive-attribute extensions remain separate
E02-D/E03 decisions; the historical stress test is not the empirical privacy milestone.

## Measured common/local comparison — October 19 follow-through

The first controlled coordination comparison is now complete: six mechanism cases and
three synthetic families with eight independent realizations each, nine configurations,
270 independent audits and 120 exact adaptive repeats. The controller was frozen. This
implements a bounded utility/policy subset of the research program; it does not establish
an asynchronous optimum, general privacy or realistic traffic validity. [Protocol, complete
references, formulas, results and figure](COORDINATION_STUDY_2026-10-19.md).

The evidence is conditional. Local windows remove unrelated delay in a blocked-branch
case and increase mean retained support under regional latency constraints, but reduce
retention across all tested mixed-density seeds. An illegal-parent hold and an actual
early-publication overlap provide concrete next regression cases. Empty/missing support
and fixed query scale materially affect utility. Further coordinator changes must be
compared against this saved baseline rather than judged only by a live visualization.

Publication opportunity loss remains a separate open metric. First identify otherwise-valid
candidates rejected specifically by public overlap, with private retirement, constraints,
coverage/history and budgets as separate causes. A utility regret reference must compare
feasible schedules with/without a chosen commit under the same prior public prefix and
bounds; overlapping ancestor alternatives cannot simply be summed. The recorded actual
witness is an explanatory example, not an aggregate regret estimate.
