# TO-DO — UMP-Simulator

**Status: 2026-10-13. Current priority: build the missing aggregation foundation, including metrics and policy trees; show the first integrated path on October 14, evaluate it by October 18, and extend adaptation by October 25.**

This is the central task backlog. README describes current behavior; this file tracks
pending changes. The historical IMPLEMENTATION_PLAN remains a reference, not an instruction
to begin every listed phase. All project documentation is maintained in English.

## 1. Status and priorities

- `[x]` completed with a concrete verification result.
- `[ ]` open: not implemented or not yet decided.
- **P0:** required for correct data or the next small comparison.
- **P1:** required for adaptive aggregation, robust evaluation or the dissertation.
- **P2:** extension to start when its need is established.

For every implementation, record affected files, behavioral effect, verification,
results and remaining limits. A class or configuration field alone does not complete a task.

Read Section 2 from top to bottom. Task IDs remain stable when tasks move. A date milestone
does not override a missing prerequisite. Complete the current stage's smallest working
path and checks before opening a later expansion. Validation accompanies each stage;
crashes or corrupt input are blockers, not reasons to begin an unrelated redesign.

## 2. Chronological execution order

**Current position: Stage 1, planning the AGBS input and aggregate contract.** The detailed
[bucket lifecycle and release protocol](docs/BUCKET_LIFECYCLE.md) records the current
proposals, flow diagram, storage model and hand-worked cases. No bucket implementation
is implied by this planning work. The core is intended to be reusable across sensor types;
AGBS is the first integration target.
Separate sensor behavior/state is preserved. A generic API does not imply that every
sensor provides every metric input or supports arbitrary spatial refinement.

| Order | Work package | Main tasks | Completion evidence |
|---|---|---|---|
| 1 — now | Common evaluation area; input, count and output semantics | D01–D03, A01 | Concrete AGBS batch/aggregate examples and chosen units |
| 2 | Metric definitions and required statistics | E01, E02, E04 | Defined inputs, calculated values and evaluation references |
| 3 | Policy tree using existing Regions | A04 | Effective regional requirements, inheritance and conflicts |
| 4 | Active/preemptive buckets and history | A02 | Hand-worked windows, lifecycle and retention rules |
| 5 | Publication coordination, AGBS decisions and inspection | A05, A03, A07, A06 | Fixed release/suppress path, then merge/split, partial suppression, time extension and debug view |
| 6 | Complete-run checks and comparative evaluation | V01, B01, R01–R03, X02, E05 | Saved equal input, verified releases, result figures and preparation-cost study |
| 7 — later | Taxonomy brainstorming, renderer settings and control GUI | X01, X10, X11 | Separate design proposals and measured implementation scope |
| 8 — later | Map extraction, routes and collision avoidance | X04, X03, X05 | Controlled scenarios and realism/performance evidence |
| 9 — as justified | Further metrics, uncertainty, graphics and infrastructure | E03, X06–X09 | Research or measured engineering need |

F01 and S01–S04 are corrections alongside the active stage when its correctness
or execution depends on them. **S04/S01 are P0 before trusting the live sensor/aggregation
demo**; renderer repair does not block independent bucket contract work. F03 covers
persistence recovery beyond successful writes.
Completed audits and sensor fixes are collected at the end of this file.

The later simulator extensions improve input quality, realism and usability. They are lower
priority than aggregation, metrics, policy trees and evaluation, and do not by themselves
establish a better adaptive privacy/utility trade-off.

## 3. Delivery plan: October 14, 18 and 25

**Revised priority, October 13:** the user clarified that the main work is the missing
aggregation foundation. Sensor validation supports this work; it must not consume the
whole development period. Policy trees and the metric contract belong in the initial
pipeline, not in a late optional extension. The full dissertation narrative remains the
presentation format. Dates below are delivery targets, not claims of completed features
or promises of improved empirical privacy.

### Architecture review before implementation

The user requests that current sensor configuration and the presentation's bucket/merge/split
protocol guide the design, while preserving sensor independence and existing performance work.
See [Aggregation design review](docs/AGGREGATION_DESIGN.md) for the source review, proposals,
metric-definition issues and the decisions still required. No source or YAML changes were
made for this review.

- [ ] Prepare an evaluation configuration with equal ABS/GBS/AGBS areas and time basis;
  retain the separate-area configuration as a demo option.
- [ ] Specify the internal observation batch; do not treat renderer cell-ID snapshots as input data.
- [ ] Resolve active/preemptive interval ownership, publication states and bounded retention.
- [ ] Define sibling time alignment and already-published-data behavior for merge/split.
- [ ] Integrate existing Region instances into one application policy tree, with cached lookup
  and explicit inheritance/boundary rules; no full tree per individual metric.
- [ ] Define metric inputs/units and update triggers; distinguish per-observation statistics,
  deadline-based checks and offline evaluation. Correct the slide's ambiguous utility formulas.
- [ ] Establish a small performance baseline before adding a thread or changing data transport.

The first implementation targets AGBS with a reusable sensor-independent core. It starts
after these contracts are concrete enough for the hand-worked
cases in the design review. Deadline pressure does not make an undefined bucket or metric
contract implementation-ready.

### Foundation: first complete observation-to-release path

The existing quadtree is the spatial foundation. Source review confirms that makeCell and
getSplitSequence use maxDepth, while AGBS splits from current positions and writes counts.
AggregationManager has no active ingestion/decision/release path; bucket flush is empty.
Region attributes exist, but no active policy tree evaluates them. These are missing
components, not configuration adjustments to a functioning adaptive aggregator.

**Proposed flow:** sensor observation -> bounded history -> candidate cell/window aggregate
-> metric evaluation + effective policy lookup -> decision -> published aggregate.
The decision may select a parent/children, wait/extend a window, release, or suppress.
Database writing and rendering consume the resulting release rather than deciding its policy.

- [ ] **P1 — Observation and aggregate contracts (D03/A01).** Define observation time,
  internal identity, position/type, cell bounds/ID, interval [start,end), release time and
  each count's meaning. Select one initial sensor input path. Distinct contributors require
  identity-bearing internal observations before count-only serialization; they cannot be
  reconstructed from GBS/AGBS counts alone. Delayed complete ABS records also omit first
  observations, so using that stream must be an explicit semantic choice.
- [ ] **P2 — Working aggregation/history (A01/A02).** Implement ingestion and one fixed
  cell/window mode first. Retain the observations or sufficient statistics needed for
  parent aggregation, child refinement and temporal extension. Test repeated observations,
  boundary times, empty windows and contributor-set unions. Describe active versus
  preemptive logical windows and retention before choosing physical bucket containers.
- [ ] **P3 — Metric contract and initial measures (E01/E02/D03).** Each metric must have
  a definition, inputs, units, validity and relationship to a constraint or objective.
  Start with distinct contributors, cell size/area, aggregation duration and release age.
  These support decisions; contributor support is not a general anonymity guarantee and
  resolution/delay alone do not establish application utility. Define a fixed application
  query and compute its error against GT in evaluation. Empirical attack evaluation remains
  a separate research measurement. Unavailable metrics must be reported, not invented.
- [ ] **P4 — Minimal actual policy tree (A04).** Implement a default/root policy with
  inherited regional child policies for one application. Keep policy content/resolution
  separate from the data quadtree even if they share geometry or cell identifiers. Start
  with two aligned, non-overlapping regions. Define effective constraints for a candidate
  cell and interval. Reject unsupported overlap/boundary cases initially rather than
  silently applying a weaker rule. Mark thresholds as demonstration parameters until justified.
- [ ] **P5 — Decision and publication (A03).** Evaluate a candidate with P3/P4 and record
  the decision and reason. First implement release/suppress on fixed candidates; then
  add parent/child selection and temporal extension. A maximum quadtree depth may remain
  fixed as a capacity/resolution bound while the selected release depth varies by region
  and time. Do not merely change global maxDepth per frame: existing ID/path logic depends
  on it. Preserve non-overlapping release coverage and compatible temporal support.
- [ ] **P6 — Explainable demonstration/evaluation (B01/V01).** Show which region/policy
  applied, measured values, selected cell/window and why data was released or suppressed.
  Store decision traces separately from public output. The fixed and adaptive variants
  must share observations, count semantics and metric definitions.

These are components of one small pipeline. Section 2 specifies the execution order;
metric/policy input requirements must be clear before finalizing bucket storage.
Start in the existing simulation thread; an extra aggregation thread is not a prerequisite.
GT is available for evaluation, but must not silently give an online policy access to
information unavailable in its declared observation stream.

| Date | Target | Evidence required |
|---|---|---|
| October 14: meeting | First integrated aggregation path with initial metrics and a minimal policy tree; existing simulator demo | Small hand-checkable cases, visible release decisions, accurate implemented/planned status |
| October 18: submission | Initial pipeline plus policy-controlled variable spatial resolution and fixed comparisons | Reproducible results, justified metric interpretation, full presentation |
| October 25: conference | Tested spatial/temporal adaptation with regional policies and comparative evaluation | Correct windows/merges/splits, sparse/dense cases, measured outcomes and limitations |

### M1 — Today, October 13, and the October 14 meeting

**Main target:** a narrow working path through P1–P5, not just declarations. Tomorrow's
prototype may use fixed candidate cells/windows while already applying regional policies
and metrics to release/suppress decisions. Dynamic depth and temporal extension remain
explicitly incomplete until demonstrated. This is an ambitious one-day target.

1. **Brief input preflight (R03/V01):** identify and preserve the current run/configuration;
   check a small representative input sample for time/identity/count consistency. Repair
   a blocking defect immediately; keep the broader full-run report as a continuing task.
2. **Define the concrete contract (P1/P3/P4):** choose one stream and count/window meaning,
   one initial metric set, root plus two regional policies, and 2–3 expected decisions.
   Write hand-worked examples before implementing those decisions.
3. **Implement the integrated path (P2/P3/P4/P5):** fixed aggregation, metric values,
   effective policy lookup, release/suppress and output with decision reasons. Verify that
   the same candidate can be treated differently under different regional constraints.
4. **Connect a demonstrable output (P6):** use saved output/decision traces or a simple
   view in the existing demo. Check conservation, unique contributors and window boundaries.
   Show actual regional decisions even if rendering integration is still minimal.
5. **Prepare the meeting:** rehearse the existing simulator plus the new path; record a
   short fallback and a status/architecture page. Reserve the end of the day for this.

- [ ] Verify live frame matching (S04/S01) before using sensor overlays as evidence;
  use timestamped saved output if that repair is not yet ready.
- [ ] One saved identifiable input and chosen input semantics.
- [ ] Concrete contracts and expected-result examples.
- [ ] An actual aggregation -> metrics -> policy -> output path.
- [ ] One application policy tree with a default and two regional children.
- [ ] Checks for contributor counting, policy inheritance and release/suppression.
- [ ] Rehearsed demo/fallback and explicit current limitations.

**Fallback if integration is incomplete:** show the working simulator, completed executable
parts and hand-worked pipeline examples; name the missing connections. Do not present a
scaffold or fixed-depth AGBS visualization as dynamic metric-driven aggregation.

**Meeting questions:** validate the application query, attacker knowledge, meaning and
priority of regional constraints, and acceptable evidence for the paper/presentation.

### M2 — Pipeline and first results by October 18

- [ ] Finish the minimum P1–P6 integration and the checks deferred from M1.
- [ ] Add metric/policy-based parent/child selection (A03) so release depth varies locally.
  Retain the existing quadtree as the hierarchy; make the release selection explicit.
- [ ] Use identical saved observations and detection area for fixed/adaptive comparisons.
  Current live ABS/GBS/AGBS regions differ and are not directly comparable populations.
- [ ] Freeze D03 window/count semantics and E01's fixed application query, including how
  coarse or delayed releases answer it and how suppression/missing data are handled.
- [ ] Run a small fixed space/time parameter matrix and the first spatial adaptive variant.
  Produce 1–2 figures and a result table covering application error, coverage, delay and
  support-rule compliance. Record input/configuration and avoid unsupported generalization.
- [ ] Specify E02's attack goal, visible releases, auxiliary knowledge and prior/no-output
  baseline. Run an empirical pilot only if the model and implementation are ready; label
  contributor counts and threshold compliance accurately if they are the available results.
- [ ] Prepare the full presentation on October 17 and submit on October 18. Preserve the
  overall dissertation narrative and distinguish tested functionality from planned work.

**Suggested sequence:** October 14: supervisor feedback and complete the first path.
October 15: dynamic spatial release selection and fixed baselines. October 16: experiments,
validation and figures. October 17: interpretation, slides and rehearsal. October 18: submission.
Temporal adaptation can follow after the first submission, whose slides may still be updated.

**Scope:** initial metrics and the minimal policy tree are required foundation work. A full
taxonomy rewrite or multiple application trees are not. F01/D02 actual-interval handling is
required when the chosen input sampling becomes irregular/non-aligned; aggregation window
length and sensor sampling period are separate concepts. Frozen replay input permits fair
comparisons while R01/R02 simulation reproducibility improvements remain pending.

### M3 — Spatial/temporal adaptation and evidence by October 25

- [ ] Extend the same pipeline with bounded temporal decisions and specify the active/
  preemptive window lifecycle (A02). Keep sufficient history for permitted alternatives;
  test expiry, retention bounds and incomplete windows.
- [ ] Implement/test compatible spatial merge/split transitions, contributor unions,
  release coverage and no double counting. Past publications remain externally visible.
- [ ] Exercise the regional policy tree for sparse, dense and changing-density conditions.
  Define conflicts/boundary-crossing candidates before supporting them. Include impossible
  constraint combinations and explicit suppression or a documented fallback.
- [ ] Compare spatial/temporal adaptation with the fixed and spatial-only variants using
  equal inputs, reference queries and attacker assumptions. Report measured outcomes even
  when adaptation loses or no general privacy conclusion is supported.
- [ ] Extend to additional saved runs/scenarios, summarize variation and run the validated
  attack evaluation where ready. Measure processing latency/throughput separately from
  simulated time before making real-time performance claims.
- [ ] Complete figures and results by October 23. Use October 24 for full rehearsal,
  playback checks and backup material; preserve a stable demo for October 25.

**Suggested sequence:** October 19–20: temporal history and decisions. October 21:
merge/split and regional edge cases. October 22–23: comparative evaluation and interpretation.
October 24: freeze/rehearsal. October 25: presentation.

If temporal adaptation remains unverified, present the tested spatial-policy pipeline and
its comparison, with temporal adaptation clearly marked as pending. Keep unimplemented
active/preemptive behavior visible in the backlog rather than treating it as completed.

### Work deferred unless a milestone requires it

Native Metal migration, real maps/doors/roads, route generation, full taxonomy redesign and
broad collision-model replacement remain outside this work package. Minimal policy trees,
metric definitions and aggregation are explicitly inside it. Address existing correctness
defects when they invalidate input, aggregation or the chosen demo.

## 4. Stage 1 — Observation and aggregate contracts

### D01 — Define velocity and missing observations — P0

- [x] Distinguish instantaneous GT velocity from interval-based ABS velocity.
- [x] Define a first unknown observation as internal only; publish after the next consecutive sample.
- [x] Drop previous identities absent at a scheduled sample; require two observations after reentry.
- [x] Define the initial state as the internal t=0 reference, without a placeholder publication.

**Implemented rule, 2026-10-12:** ABS emits complete records only. A valid stationary estimate
means equal consecutive positions; an unknown agent is not encoded as zero velocity.
GBS/AGBS still count each currently observed agent, including an ABS identity not yet emitted.
Actual observation timestamps for interval robustness remain F01.

**Verification:** regression covers initial motion, new identities, absence and reentry.

### D02 — Define time and sampling semantics — P0

- [x] Identify timestamp as the time of the position state.
- [x] Describe the preceding interval represented by a velocity estimate.
- [ ] Separate simulation time, data time, publication time and wall-clock processing time.
- [ ] Define behavior when sensor periods do not align with simulation ticks.
- [ ] Review absolute-date/UTC handling; generateISOTimestamp uses mktime.

**Finding:** no universal GT/ABS time shift in the Aggregation_Manager import. Sensors observe
the same state/time as GT. simulationTime is increased before the timestamp field, which
makes the sequence harder to read but does not by itself make the records inconsistent.

**Acceptance:** a short timeline explains one complete tick and two sensor observations.
Do not shift timestamps merely to make records appear synchronized.

### D03 — Define aggregate counts and windows — P0 before temporal aggregation

- [ ] Distinguish observation contributions, distinct people, occupancy and average occupancy.
- [ ] Name class counts and totalAgents/totalCount unambiguously.
- [ ] Define window boundaries, preferably half-open [start,end), and base-bin alignment.
- [ ] Define complete coverage, no sample due, measured empty and unavailable observations.
- [ ] Keep original window start/deadline through spatial merges; distinguish duration
  from release age and finalize partial windows at end of run explicitly.
- [ ] Distinguish Empty, Suppressed and Unavailable.
- [ ] Separate internal identities from publication fields.

**Acceptance:** repeated observations of one person count once for distinct people but
multiple times for contributions. Small example data demonstrates every chosen definition.

### A01 — Define states and AggregatedCell — P0

- [ ] Describe geometry, history, release rules and publications separately.
- [ ] Specify sensor-local ownership; favor a manager without MongoDB coupling.
- [ ] Define every count/time/policy field and stable run/batch/cell/window/release keys.
- [ ] Specify ingest(batch), advance(now), completed output and read-only debug snapshot
  responsibilities. No-sample time advances must still trigger deadlines.
- [ ] Replace the prototype collection/timestamp references with explicit value input
  and an external publication sink; inspect AGBS member composition and render construction.
- [ ] Choose update(now, tree) versus a bound reference from actual requirements.
- [ ] Define one concrete AGBS input adapter and a core that does not depend on Sensor
  subclasses, SFML Agent objects, MongoDB or renderer buffers.
- [ ] Keep quadtree-specific candidate enumeration behind the spatial component; do not
  claim the initial spatial strategy is independent of its hierarchy.
- [ ] Declare input capabilities: positions, cell support, internal identities and attributes.
  A count-only source cannot promise distinct contributors or finer detail than its input.
- [ ] Keep independent per-sensor/per-application bucket state; share read-only definitions
  where useful. Add ABS/GBS adapters after the AGBS path is demonstrated.

**Acceptance:** small interfaces with clear ingestion and output; no empty abstraction hierarchy.

## 5. Stage 2 — Metric definitions and evaluation questions

### E01 — Define one utility application — P0

- [ ] Select a first query, such as mean occupancy/density over a time interval.
- [ ] Fix reference grid, reference times and missing/suppressed-data treatment.
- [ ] Define error against GT and use the same query for every variant.
- [ ] Measure resolution, staleness, coverage and numerical error separately.

**Acceptance:** a fixed question and its GT answer are defined. Coarsening the reference
must not automatically eliminate error. Do not label record retention as data fidelity without justification.

### E02 — Define attacker and privacy evaluation — P0

- [ ] Specify attack goal, auxiliary information and visible publications.
- [ ] Consider aggregate-occupancy membership inference and justify its relevance.
- [ ] Define a prior/no-output baseline and clear attack-success measure.
- [ ] Include repeated releases, overlapping windows and possible differencing attacks.
- [ ] Include observable adaptive geometry, publication timing and suppression patterns;
  evaluate all views visible to the attacker jointly.
- [ ] Distinguish k-threshold compliance from measured risk.

**Acceptance:** reproducible attacker knowledge and baseline. No general anonymity claim
based only on a distinct-contributor count.

### E04 — Define the online metric contract — P0

- [ ] Specify each metric ID, meaning, inputs, units, aggregation rule and valid/undefined cases.
- [ ] Separate metric definitions, selected requirements and measured values.
- [ ] Distinguish contribution support from a justified anonymity/equivalence-class metric.
- [ ] Reconcile presentation metrics with paper Tables 3–5, including definitions and
  reference populations. Do not transfer example thresholds as universally safe defaults.
- [ ] Select incremental statistics and cache invalidation triggers; verify before publication.
- [ ] Separate aggregation duration, sensor period, release age and wall-clock processing time.

**Acceptance:** one candidate has hand-computable metric values, one policy supplies the
corresponding allowed ranges, and a decision explains each passed/failed/unavailable check.
The metric evaluator requires no renderer or live database access.

## 6. Stage 3 — Policy tree and existing Regions

### A04 — Regional policy trees / application layer — P0

- [ ] Define default, regional and application-specific constraints.
- [ ] Reuse Region instances and region_taxonomy as policy inputs; validate type references.
- [ ] Store metric requirements/parameters and allowed bounds in the policy tree; calculate
  actual metric values in an evaluator from bucket statistics.
- [ ] Separate hard constraints, preferences/objectives, and measured candidate values.
  Maximum aggregation duration is a bound; current window duration is its measured value.
- [ ] Update the presentation architecture: Regions/application settings -> Policy Tree ->
  effective requirements; bucket statistics -> Metric Evaluator -> observed values;
  the AggregationManager consumes both and decides.
- [ ] Keep policy hierarchy independent of data hierarchy.
- [ ] Compile inherited effective policies at initialization for reachable cells and
  cross-region parents; share identical policies and measure full-tree versus sparse cost.
- [ ] Distinguish inherited configured defaults from constraints derived for a candidate
  footprint. Do not propagate a cross-region parent's combined bounds back into unrelated children.
- [ ] Apply strict compatible hard bounds: max of lower bounds, min of upper bounds,
  all mandatory metrics and intersections of allowed actions. Reject contradictions.
- [ ] Define min/max cell side in metres and coarsest allowed depth unambiguously;
  validate metric units, parameters and reference definitions before combining thresholds.
- [ ] Resolve Spatial First/Temporal First as preferences with explicit priority/ties;
  preferences never weaken hard constraints.
- [ ] Handle overlaps, boundary-crossing cells and conflicting requirements.
- [ ] Fix policies during initial runs; specify policy versions/cache invalidation
  and open-window behavior before permitting live policy changes.
- [ ] Add multiple views only after a correct single release pipeline.

**Acceptance:** spatial merges cannot silently weaken regional rules; conflicts have
explicit resolution or rejection.

## 7. Stage 4 — Active/preemptive buckets and bounded history

### A02 — Bounded history and active/preemptive windows — P0

- [ ] Specify retrospective parent aggregation from internal observations.
- [ ] Compare physical active/preemptive containers with logical windows over shared history.
- [ ] Define retention, open windows and cleanup, with bounded coordination/retry retention.
- [ ] Store owned fine time-bin history and reference it from sparse bucket records keyed
  by stream/application, cell/depth, window start and generation. No Agent*/Node* lifetimes.
- [ ] Treat leaf flags as work hints; verify full sibling coverage including known-empty cells.
- [ ] Separate legal merge extent, reserved unpublished extent and precomputation extent.
  Specify ancestor lookahead levels, finite temporal candidates and cache/memory budgets.
- [ ] Start with on-demand reconstruction; add one/two-level, full and selective preparation
  as E05 variants. An uncached candidate remains available when complete history permits it.
- [ ] Use exact contributor unions/reference counts and appropriate time weights; do not
  sum unique child counts or treat repeated observations as different people.
- [ ] Define COLLECTING/WAITING, READY, SEALED/PENDING_OUTPUT, COMMITTED, SUPERSEDED
  and SUPPRESSED. Keep temporal_exhausted separate from publication state.
- [ ] Invalidate competing preemptive candidates after a committed cut; reclaim history
  only after all bounded dependencies are resolved.
- [ ] Handle cell-specific windows and compatible temporal merge coverage.
- [ ] Reconcile the paper's interval-tree proposal with the presentation's active/preemptive
  buckets: specify whether an interval index is required by actual queries before choosing
  it over bounded bins/history. These structures have different roles.
- [ ] Distinguish closed, decision-ready, externally published and discarded states;
  define already-published-data behavior for retrospective reconstruction.

**Acceptance:** no double counting, bounded storage and reconstructable permitted windows.
Deleting a DB record cannot retract an already externally visible publication.

## 8. Stage 5 — AGBS integration and adaptation decisions

### A05 — Publication coordination and irreversible output — P0

- [ ] Define private observation/GT/checkpoint storage versus externally visible releases;
  keep the publication sink outside the manager and enforce the selected access boundary.
- [ ] Define reservations before any competing child release, and a ledger of reserved,
  committed and retired cell/interval coverage per application stream.
- [ ] Choose a small initial coordination domain and merge-depth cap. Compare holding its
  unpublished cut with early child release that makes historical ancestors unavailable.
- [ ] Require compatible complete temporal support for all sibling regions/descendants.
  A passing child can be held for coordination without being described as privacy-failing.
- [ ] Publish one non-overlapping selected cut; reject parent/child reuse of the same
  committed or pending-output support. Future adaptation uses a common handover boundary.
- [ ] Seal immutable output with a stable release ID; preserve reservations on sink failure.
  Coordinate retry/idempotency and bounded pending output with F03.
- [ ] Settle any A07 descendant fallback before retiring support; suppress only the final
  unreleasable remainder. Whole-candidate suppression remains the initial baseline.
- [ ] Keep internal reasons separate from raw history cleanup. Do not delete visible
  records as a purported privacy repair, or publish totals that reconstruct suppressed parts.

**Acceptance:** demonstrate the additive-count subtraction counterexample, a rejected
merge over a published child, and an allowed future transition. Pending writes cannot
reopen coverage for a competing candidate. Disjoint release coverage is not a privacy proof.

### A03 — Start with simple adaptive strategies — P0

- [ ] Integrate fixed candidate release/suppress with the initial regional policy tree.
- [ ] Specify and implement one first adaptive decision order; compare Spatial First and
  Temporal First only after the initial path is correct.
- [ ] Define sibling/parent/child checks, merge, split and suppression using A05 reservations.
- [ ] Evaluate one complete parent at a time and expand to its siblings only when the
  next ancestor is needed and allowed. Avoid an automatic cascade to the depth cap.
- [ ] Recompute effective regional policy and all mandatory metrics for every candidate.
  More aggregation is not assumed to improve every metric monotonically.
- [ ] Allow early completion only after hard minimum/maximum bounds and release
  coordination pass. Temporal exhaustion permits only remaining legal actions.
- [ ] Bound retries/search; wait for new evidence or a deadline rather than polling
  unchanged candidates. Preserve original start time through every merge.
- [ ] Apply changes to an already published spatial selection at future common boundaries.
  Distinguish those transitions from A07 selecting unpublished descendants as final fallback;
  prevent split/merge oscillation within one unresolved window.
- [ ] Handle impossible constraint combinations explicitly.
- [ ] Compare against B01 baselines.

**Acceptance:** decisions are explainable and spatial/temporal releases agree. Measure a
better privacy/utility trade-off rather than assuming it.

### A07 — Selective suppression after permitted adaptation is exhausted — P1

- [ ] Check remaining temporal options when the coarsest spatial cell fails; never reset
  window start/deadline. Define final fallback before marking the whole region suppressed.
- [ ] Select valid whole descendant cells over the same unpublished interval; recheck their
  policies, metric inputs, completeness, fine-resolution bounds and publication history.
- [ ] Suppress only the unreleasable remainder; mark abandoned parents SUPERSEDED. Do not
  remove observations from a parent while retaining its original full-area semantics.
- [ ] Define deterministic selection/ties and the coverage/detail objective. Do not claim
  globally minimal suppression from a greedy traversal without a supporting argument.
- [ ] Prune only with valid metric-specific bounds: under a uniform support threshold,
  a parent with too few distinct people implies its descendants also fail for that interval.
- [ ] Test heterogeneous regional thresholds where the parent fails but some children pass;
  require no overlapping totals that reveal the suppressed part.
- [ ] Evaluate missing coverage separately from zero occupancy, selection bias, utility error
  and disclosure through the visible suppression/geometry pattern.

**Acceptance:** uniform-threshold failure suppresses the infeasible subtree; the documented
10/2/2/2 threshold example preserves eligible children; no output silently changes support.
Keep whole-candidate suppression as a correct simpler baseline until this fallback is tested.

### A06 — Live aggregation state overlay — P1, after S04

- [ ] Define a read-only debug snapshot separate from sensor cell-ID measurements.
- [ ] Show collecting/ready candidates, proposed parents, committed output and suppressed
  intervals with distinct labels/styles and correct observation/window/release times.
- [ ] Expose policy ID and decision reason on inspection; cache unchanged geometry.
- [ ] Separate trusted GT/internal inspection from the application's release-only view.
  Internal counts, failed candidates and debug details must not leak through public output.

**Acceptance:** a hand-worked merge can be followed visually without stale frames or
the renderer influencing aggregation. A06 is targeted inspection, not the later X11 GUI.

## 9. Stage 6 — Validation and comparable experiments

Checks accompany each implementation. This stage collects the complete-run evidence
and comparisons once the first path is executable.

### V01 — Verify reference data and the later correction — P0

- [ ] Preserve the example-agent inspection as a reproducible report.
- [ ] Optionally extend matching/duplicate checks to all agents and sensor identities.
- [x] Select a separate controlled dataset for the sensor regression test.
- [x] Add and pass a sensor regression test with the chosen correction.
- [ ] Validate a complete new simulator run against GT across all agents/sensors.

**Existing result:** agent C0B64FE1-740C-486C-A2D1-00E030269E71: GT 200 records, ABS 199,
100 sensor timestamps; no missing GT joins or position differences; 99 duplicate keys;
first velocity halved; the next 99 estimates match displacement over 100-ms intervals.

**Correction verification, 2026-10-12:** known synthetic observations in an isolated MongoDB
database pass startup, interval velocity, unique keys, entry/reentry, counts and empty-area
cadence checks. This is direct sensor-pipeline validation, not a complete simulator run.

**Acceptance:** documented before/after identity, position, timestamp, duplicate and interval
velocity comparisons. Keep reference data unchanged. One checked agent does not validate all runs.

### B01 — Compare fixed space/time baselines — P0

- [ ] Select a small set of fixed cell sizes and temporal windows.
- [ ] Use identical observations, detection areas and application queries.
- [ ] Process counts/windows according to D03.
- [ ] Export utility error, empirical privacy measure, coverage, staleness and runtime.

**Acceptance:** reproducible table/figure with configuration and explicit limits. A complete
policy tree or real city map is not required for this first comparison.

### R01 — Generate or reuse a reproducible measurement stream — P0

- [ ] Inventory random sources: spawning, targets, velocity, noise and identities.
- [ ] Evaluate one configurable seed and stable scientific identities.
- [ ] Feed identical observations to all compared aggregation variants.
- [ ] Record parameters, time basis and run identity.

**Finding:** multiple random_device/mt19937 initializations; no shared seed.
**Acceptance:** equal configuration/seed produces equal scientific states, or a fixed saved
stream feeds all variants. Wall-clock performance need not be bit-identical.

### R02 — Remove wall-clock influence from movement — P0

- [ ] Review updateVelocity receiving simulationRealTime and correct it narrowly.
- [ ] Separate movement time from profiling/playback time.

**Finding:** Agent::updateVelocity uses its time argument in noise, while Simulation passes
measured runtime. DB/CPU/render costs can therefore alter the movement stream.
**Acceptance:** identical scientific input stays identical at different processing/playback speeds.

### R03 — Safe reference run and output without constant DB dependency — P0/P1

- [ ] Choose an experiment database before rerunning the simulator.
- [ ] Make clear_database behavior explicit and configure it for experiments.
- [ ] Decouple headless operation from snapshot production and DB I/O as needed.
- [ ] Evaluate minimal file/null output or offline processing of saved observations.

**Acceptance:** a small comparison runs without GUI, creates controlled artifacts and does
not overwrite references. Add a broad output interface only if multiple outputs justify it.

### X02 — Heterogeneous evaluation scenarios — P1

- [ ] Prepare reproducible sparse, dense, empty and changing-density cases.
- [ ] Use identical observations/areas across compared variants; retain simple scenarios
  with hand-checkable outcomes before increasing movement realism.

### E05 — Study full versus selective preemptive preparation — P1, after lifecycle correctness

- [ ] Define "all": the finite set of eligible spatial candidates and temporal windows.
  Distinguish internal preparation from always publishing the coarsest aggregate.
- [ ] Compare on-demand reconstruction, fixed one/two-level lookahead, full preparation
  and a budgeted selective heuristic; include selector/maintenance/expiry/eviction cost.
- [ ] Hold input replay, policies, legal depth, reservations, history, candidate decisions,
  metric definitions, fallback and tie rules constant. First verify equivalent outputs
  without processing deadlines; do not attribute changed privacy to a caching optimization.
- [ ] Use sparse/dense/mixed inputs, moving hotspots and abrupt changes; vary request rate,
  depth, window set/duration, contributor movement and metric cost in a small initial matrix.
- [ ] Measure total CPU cost, p50/p95/p99 update/request latency, peak memory, throughput,
  candidate count, hit rate, unused preparation, reconstruction and deadline misses.
- [ ] Separate setup/warmup/steady operation and use repeated paired runs with identical
  DB/renderer conditions. Count history/cache/ledger memory in the budget.
- [ ] Then apply explicit real-time arrival/processing budgets and measure coverage, delay,
  application error and empirical privacy; distinguish compute misses from metric failures.
- [ ] Compare several permitted merge extents as a separate policy experiment, not an
  unnoticed change of candidate universe between cache variants.
- [ ] Review materialized-view selection and streaming aggregation literature before claiming
  novelty; document the mobility/policy/deadline-specific question and measured crossover.

**Acceptance:** equivalent scientific outputs for the unconstrained execution comparison,
reproducible cost/memory curves and a stated workload range where each strategy wins or loses.
No assumed winner; this study does not block the first aggregation demo.

## 10. Conditional corrections supporting the active stage

Bring these forward when they block the current contract, demo or experiment. Do not
replace the core work package with a general simulator rewrite.

### F01 — Use actual elapsed observation time for velocity — P0

- [ ] Retain earlier position and its observation time together.
- [ ] Calculate velocity as DeltaPosition / DeltaTime.
- [ ] Handle zero/negative elapsed time.
- [x] Consolidate duplicate calculations; remove unused estimateVelocities and its ABS map.
- [x] Implement delayed complete records for unknown/reentering agents as selected in D01.

**Affected code:** simulator/src/AgentBasedSensor.cpp (observation history and capture),
simulator/src/Sensor.cpp (sampling gate), and their headers. estimateVelocities was removed
by the 2026-10-12 consolidation; initial observations now belong to ABS, not Simulation.

**Historical defect (now fixed by F00):** initial position at t=0; first ABS capture at t=50 ms. Multiplication
by 10 Hz assumes 100 ms and halves the first value. Recognizing the identity does not
solve the time-interval error.

**Minimum scope:** associate two observations with time correctly. No new transport layer,
extra thread or generic tracking framework. A previous sample timestamp might suffice for
synchronously observed agents; use per-agent timestamps only if entry/dropout rules need them.
Choose the data structure after D01/D02.

**Acceptance:** after F00, known constant motion produces the correct first velocity
over 0–100 ms and subsequent 100-ms intervals. A separate deliberately supplied 50-ms
observation interval must also be calculated using its actual duration. Different spacing remains correct. Identity,
position and timestamp still match GT. Unknown agents follow D01.

**Status:** actual elapsed-time calculation remains open. The 2026-10-12 correction
fixes aligned startup, consolidates calculation and implements D01; it deliberately retains
nominal frameRate estimation. The older 0ce473f implementation remains reverted.

### S01 — SharedBuffer shutdown and consumption — P0 before larger runs

- [ ] Include finished/stop and data availability in the wait condition.
- [ ] Check empty-queue shutdown, final frames and early renderer closure.
- [ ] Measure/bound growth with absent or slow consumers.
- [ ] Describe synchronization of snapshots at different sensor frequencies.

**Finding:** end notifies, but read's wait predicate only checks queue non-emptiness.
Headless operation still produces snapshots. An access count of three implements neither
broadcast nor backpressure; existing read removes a frame.

**Proposal:** keep aggregation in the simulation thread initially. Rendering may skip frames;
evaluation may require every batch. Define requirements before choosing queue/snapshot transport.
**Acceptance:** no shutdown hangs and bounded memory for the selected operation mode.

### S04 — Match chronological complete sensor frames to agent frames — P0 for live correctness

**Verified in source:** Renderer::readLocalSensorBufferFrame returns the first exact match
without consuming it, and no-match paths can retain currentSensorFrame. The direct path
blocks in SharedBuffer::read before local lookup. The AGBS render loop breaks after the
first sensor-map entry and overwrites the render instance's sensor ID with that entry.
Currently AGBS is the sensor-buffer producer. This is a correctness issue distinct from
later renderer settings/GUI work; coordinate queue changes with S01.

- [ ] Combine actual contributions for step t into one complete timestamped sensorId ->
  cell-ID-set frame. Non-due sensors must not wait for later measurements to join t.
- [ ] Preserve source identity for measured-empty sets; distinguish them from no sample due.
- [ ] Define step completeness: proposed step packet couples agent data and an optional
  sensor map after capture, or explicit presence/completion metadata if queues stay separate.
  An empty queue/tryRead miss alone cannot prove that no measurement exists.
- [ ] Treat local frames as an ordered FIFO: discard older entries, pop one exact match,
  keep future entries, and clear current measurement data when the agent frame advances
  without a match. Repainting/pausing the same agent frame may retain its matched view.
- [ ] Guarantee producer order/completeness; define duplicate/out-of-order handling and
  bounded buffering when frames are skipped.
- [ ] Route every sensor-map entry to the correct render instance using stable IDs; removing
  the first-entry break alone must not merge all sensors into every displayed AGBS grid.
- [ ] Avoid blocking on nonexistent measurements; keep UI events responsive for in-flight
  frames and complete shutdown/draining with S01.
- [ ] Verify measured steps, between-sample steps, no match, old/exact/future FIFO entries,
  multiple sensors at different rates, measured-empty frames, pause/redraw and end of stream.

**Acceptance:** one complete matching frame is consumed once; older data are not displayed
as current; future data remain buffered; all sensor IDs reach their own visualizations;
missing measurements cause neither unintended waiting nor stale reuse. Last-known display,
if later desired, must explicitly show its original time/age. Use saved timestamped output
instead of claiming a correct live overlay until these cases pass.

### S02 — Collision grid and pointer lifetime — P1 before more realistic scenarios

- [ ] Initialize width/height and validate adjacent-cell checks.
- [ ] Examine double checks of neighboring agent pairs.
- [ ] Separate vector::erase from retained Agent* pointers.
- [ ] Define grid assignment consistently before/after movement.

**Finding:** constructor leaves grid dimensions unset while neighbor checks read them;
vector erasure can invalidate previously retained pointers.
**Acceptance:** known neighborhoods and exiting agents work without invalid pointers.
Do not replace the whole collision algorithm merely to fix these defects.

### S03 — Quadtree memory and identities — P1

- [ ] Review reset/clear/destructor for lost child pointers.
- [ ] Document four base cells, depth and Morton-ID convention.
- [ ] Verify bounds, position mapping and renderer reconstruction.

**Finding:** reset nulls child pointers without freeing them. Generic complete-tree formulas
must be adapted to the actual base-cell convention.
**Acceptance:** clear ownership and valid unchanged identities. Do not replace the spatial
structure before defining requirements.

### F03 — Persistence failure recovery — P1 when required

- [ ] Design/test retry ownership and idempotent writes for failed or partially successful batches.
- [ ] Decide whether a new capture may replace an unsent batch or requires a bounded queue.

**Current limit:** F02 fixes repeat publication after successful writes. It does not supply
durable retries or exactly-once behavior after ambiguous/partial database failures.

## 11. Later simulator improvements — lower priority

These items start after the aggregation/metric/policy foundation and first evaluation.
Order below reflects dependencies, not a commitment to implement them before October 25.
Brainstorm and define acceptance criteria before selecting libraries or algorithms.

### X01 — Flexible taxonomy: brainstorm and redesign — P2

- [ ] Identify what makes new agent types and combinations difficult in the current YAML.
- [ ] Discuss separating identity/classification, age, transport mode, accessories,
  appearance, behavior and distributions; compare composition, defaults and inheritance.
- [ ] Define stable type IDs and how combined attributes feed sensors, metrics and policies.
- [ ] Preserve existing scenarios through a documented configuration migration.

**Acceptance:** adding an agreed new class/attribute does not require editing unrelated
renderer, movement and metric code. Choose the model after the brainstorming session.

### X10 — Simplify the real-time renderer settings — P2

- [ ] Inventory settings and controls, including overlap with database playback renderers.
- [ ] Separate scenario, sensor/policy, rendering and playback configuration responsibilities.
- [ ] Define clear defaults, presets and dependencies between display options.
- [ ] Check synchronized sensor/aggregate display and expose decision/metric views needed
  for understanding the pipeline without moving aggregation logic into the renderer.
- [ ] Profile display costs and preserve useful existing batching/optimizations.

**Acceptance:** a documented demo preset is easy to reproduce and settings have one clear
owner. Targeted demo controls can be brought forward only when the current milestone needs them.

### X11 — Missing control GUI — P2

- [ ] Specify controls for simulation start/pause/step/reset, playback speed and run selection.
- [ ] Distinguish pausing simulation from pausing playback; define thread-safe commands.
- [ ] Decide which sensor/policy settings can change live and which require a new run.
- [ ] Show applied versus pending configuration and minimal runtime/status information.
- [ ] Select a GUI approach after the renderer/settings model is clear.

**Acceptance:** controls have predictable simulation semantics, and GUI changes do not
silently invalidate the saved experiment configuration or timing model.

### X04 — Map component extraction and environment model — P2

- [ ] Discuss source/import choices and coordinate conversion into simulator metres.
- [ ] Extract or represent buildings, entrances/doors, roads, sidewalks, cycle paths,
  crossings and navigable/free space, with provenance for unavailable or inferred details.
- [ ] Build connectivity and traversability rules for the relevant agent categories.
- [ ] Define reusable environment components and inspect UAM-Simulator-Modern as a reference.

**Acceptance:** one small map produces valid geometry and a connected routing model;
rendered appearance and movement constraints refer to the same environment.

### X03 — Routes and trajectories: A*, D* Lite and replanning — P2

- [ ] Discuss destination selection and demand distributions before increasing route complexity.
- [ ] Compare A* and D* Lite for the intended routing/replanning workload.
- [ ] Define waypoints, route following and reactions to blocked/changing passages.
- [ ] Specify the interface between global route planning and local collision avoidance.

**Acceptance:** agents reach destinations through valid map components and can recover
from the selected obstruction scenarios. The route planner choice remains open.

### X05 — Real-time collision avoidance and ORCA — P2

- [ ] Compare the current TTC/lookahead approach with ORCA and suitable alternatives.
- [ ] Define how local avoidance combines with A*/D* Lite route following; evaluate these
  roles separately instead of treating routing and local avoidance as interchangeable.
- [ ] Include heterogeneous agent sizes/speeds, yielding rules, narrow passages and deadlocks.
- [ ] Measure collisions, completion, motion plausibility and processing cost on identical inputs.

**Acceptance:** a measured improvement on agreed movement scenarios without unbounded
runtime cost. Correct S02 safety/lifetime defects before evaluating a replacement model.

## 12. Further research and optional infrastructure

### E03 — Select additional metrics scientifically — P1/P2

- [ ] Evaluate k/l/t/delta/entropy metrics for actual data and attack scenarios.
- [ ] Clarify sensitive attributes and the meaning of agent classes.
- [ ] Define multiple seeds/scenarios and suitable statistical summaries.

**Acceptance:** each metric has a justified meaning and specified internal inputs.
Class counts alone cannot reconstruct every privacy metric.

- [ ] **X06 — Sensor uncertainty (P2):** preserve GT and model errors separately;
  add classification/localization uncertainty when the evaluation needs it.
- [ ] **X07 — Metal/3D/GPU (P2):** keep SFML initially; revisit after profiling or a defined
  3D requirement. Modern has a native Metal backend; the older Metal-Simulator test uses
  OpenGL. Renderer migration does not accelerate CPU aggregation automatically.
- [ ] **X08 — Shared libraries/build (P2):** selectively reduce duplication while preserving
  independent builds. Avoid a broad infrastructure project before it is needed.
- [ ] **X09 — Packaging/remote (P2):** retain the UMP-Simulator name; decide remote,
  license, publication and data/asset selection separately.

## 13. Completed organization, audit and sensor corrections

- [x] Create the local repository, initially named UrbanMobilityPrivacy; no remote.
- [x] Move it outside Coding to ~/Developer/UMP-Simulator on 2026-10-09, preserving Git history.
- [x] Adopt the name Urban Mobility Privacy Simulator and update location/workspace documentation.
- [x] Import Aggregation_Manager and four separate V3 database renderers.
- [x] Preserve import commit 96fae5b as the baseline.
- [x] Build the unmodified simulator and all four renderers successfully.
- [x] Compare 101 imported component files byte for byte with the originals.
- [x] Archive the historical implementation plan under docs/reference.
- [x] Document classes, data flow and major source-level risks.
- [x] Inspect the local MongoDB connection and collections read only.
- [x] Check the example agent's GT/ABS matches, duplicates and velocity intervals.
- [x] Revert the temporary ABS fix and its test target with db2bdbb.
- [x] Establish detailed README and TO-DO files as the central project overview.
- [x] Read UAM-Simulator-Modern documentation and identify its native Metal backend.
- [x] Translate all repository documentation into English, including the reference plan.
- [x] Record the exact duplicate-write sequence and prototype-aggregator non-involvement.
- [x] Record SFML/Metal trade-offs and available history of the graphics test project.

- [x] Correct shared ABS/GBS/AGBS sampling initialization and empty-area timer reset.
- [x] Consume successful ABS batches and replace class working state with local observations.
- [x] Remove the unused second velocity calculation; define delayed full records for new/reentering agents.
- [x] Build the corrected simulator and pass the isolated MongoDB sensor regression test.
- [x] Make missing/invalid startup config errors visible without optional ERROR logging (2026-10-13); verify wrong-directory exit before DB initialization.

### F00 — Fix initial sampling across ABS, GBS and AGBS — P0 — implemented

- [x] Exclude the initial call from completed-step accounting.
- [x] Use one shared sampling gate for ABS, GBS and AGBS.
- [x] At 10 Hz / 50-ms ticks, capture at 100 ms, then 200 ms, 300 ms, etc.
- [x] Retain the initial ABS position internally; preserve matching state timestamps.
- [x] Reset the sampling timer even when the detection area is empty.
- [x] Verify startup, counts, empty renderer snapshots and repopulation.

**Baseline finding:** all three sensors added 50 ms while observing X(0), then captured
X(50 ms) at the next call. ABS used X(0) as its reference but assumed a 100-ms interval,
halving the first estimate. GBS/AGBS reset only when populated, altering empty-area cadence.

**Implementation, 2026-10-12:** Sensor::isSamplingDue initializes once without adding time,
then advances by simulation steps and resets at every due sample, independent of occupancy.
ABS owns the initial-position observation; Simulation no longer seeds its map externally.
GBS/AGBS still omit empty DB count batches. AGBS emits empty renderer snapshots on schedule.

**Affected files:** Sensor.hpp/.cpp, all three sensor update methods and Simulation.cpp.
**Verification:** Release build and isolated MongoDB regression passed, including non-epoch
initial time, first correct known velocity and state/time matching at 100 ms.
**Limits:** fixed aligned intervals only. Non-aligned/fractional scheduling remains D02/F01.

### F02 — Publish each ABS measurement batch once — P0 — implemented for successful writes

- [x] Assemble a local observations vector; remove the class member agentData.
- [x] Name the output reference pendingObservations to eliminate shadowing.
- [x] Consume dataStorage.second after a successful insert_many.
- [x] Verify repeated postData calls, non-capture ticks, empty samples and final output.
- [x] Document the failure policy and partial-write limitations.

**Baseline finding:** update cleared the working vector while postData read a different,
retained vector in dataStorage. Repeated loop calls reinserted a successful batch. The
reference agent had 199 rows for 100 observation timestamps and 99 extra identical rows.
The prototype aggregator was not involved.

**Implementation:** the local observations vector is moved into the timestamped output pair.
postData checks pendingObservations and clears the pair's vector after success. printData
reads the pending batch before publication. The pair itself has no clear()/empty() method.

**Verification, 2026-10-12:** regression calls ABS postData three times per tick and verifies
unique sensor measurement identities/timestamps, correct position/time and final publication.

**Failure policy:** an exception leaves the pending vector available until another attempt
or the next capture, which replaces it. This is not a durable retry queue. Partial/ambiguous
DB failures can cause duplicates on retry; exactly-once persistence is not guaranteed.
Further failure recovery and idempotent-write work is tracked separately as F03.

**Existing data:** no reference database cleanup or replacement was performed.

## 14. Working process

Follow the chronological queue in Section 2 and the dates in Section 3. Keep task IDs
stable and mark completion only with evidence. Before coding, state the contract and
small scope; afterwards record behavior, verification and limitations. Update the active
stage when its acceptance criteria are met. Preserve user changes and current sensor
modularity. All repository documentation remains in English.
