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

## 2. Completed organization and audit work

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

**Still open:** actual-interval velocity handling, full-run validation, reproducible experiments,
actual adaptation, metric definitions and evidence of improved privacy. Historical reverted
work remains in Git; the 2026-10-12 correction is a new implementation.

## 3. Delivery plan: October 14, 18 and 25

**Revised priority, October 13:** the user clarified that the main work is the missing
aggregation foundation. Sensor validation supports this work; it must not consume the
whole development period. Policy trees and the metric contract belong in the initial
pipeline, not in a late optional extension. The full dissertation narrative remains the
presentation format. Dates below are delivery targets, not claims of completed features
or promises of improved empirical privacy.

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

These are dependency-ordered parts of one small pipeline, not six framework rewrites.
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

## 4. Observation and data semantics

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
- [ ] Define window boundaries, preferably half-open [start,end).
- [ ] Distinguish Empty, Suppressed and Unavailable.
- [ ] Separate internal identities from publication fields.

**Acceptance:** repeated observations of one person count once for distinct people but
multiple times for contributions. Small example data demonstrates every chosen definition.

## 5. Sensor corrections: implemented scope and remaining work

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
- [ ] Design/test failure recovery and idempotent writes if required by experiments.

**Existing data:** no reference database cleanup or replacement was performed.

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

## 6. Reproducibility and lean experiment operation

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

## 7. Simulation and transport checks

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

## 8. Research questions, metrics and baselines

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
- [ ] Distinguish k-threshold compliance from measured risk.

**Acceptance:** reproducible attacker knowledge and baseline. No general anonymity claim
based only on a distinct-contributor count.

### B01 — Compare fixed space/time baselines — P0

- [ ] Select a small set of fixed cell sizes and temporal windows.
- [ ] Use identical observations, detection areas and application queries.
- [ ] Process counts/windows according to D03.
- [ ] Export utility error, empirical privacy measure, coverage, staleness and runtime.

**Acceptance:** reproducible table/figure with configuration and explicit limits. A complete
policy tree or real city map is not required for this first comparison.

### E03 — Select additional metrics scientifically — P1/P2

- [ ] Evaluate k/l/t/delta/entropy metrics for actual data and attack scenarios.
- [ ] Clarify sensitive attributes and the meaning of agent classes.
- [ ] Define multiple seeds/scenarios and suitable statistical summaries.

**Acceptance:** each metric has a justified meaning and specified internal inputs.
Class counts alone cannot reconstruct every privacy metric.

## 9. Aggregation and policy foundation: current development stage

### A01 — Define states and AggregatedCell — P1

- [ ] Describe geometry, history, release rules and publications separately.
- [ ] Specify sensor-local ownership; favor a manager without MongoDB coupling.
- [ ] Define every count/time/policy field.
- [ ] Choose update(now, tree) versus a bound reference from actual requirements.

**Acceptance:** small interfaces with clear ingestion and output; no empty abstraction hierarchy.

### A02 — Bounded history and active/preemptive windows — P1

- [ ] Specify retrospective parent aggregation from internal observations.
- [ ] Compare physical active/preemptive containers with logical windows over shared history.
- [ ] Define retention, open windows and cleanup.
- [ ] Handle cell-specific windows and compatible temporal merge coverage.

**Acceptance:** no double counting, bounded storage and reconstructable permitted windows.
Deleting a DB record cannot retract an already externally visible publication.

### A03 — Start with simple adaptive strategies — P1

- [ ] Specify Spatial First and Temporal First under one global policy.
- [ ] Define sibling/parent/child checks, merge, split and suppression.
- [ ] Handle impossible constraint combinations explicitly.
- [ ] Compare against B01 baselines.

**Acceptance:** decisions are explainable and spatial/temporal releases agree. Measure a
better privacy/utility trade-off rather than assuming it.

### A04 — Regional policy trees / application layer — P1

- [ ] Define default, regional and application-specific constraints.
- [ ] Keep policy hierarchy independent of data hierarchy.
- [ ] Handle overlaps, boundary-crossing cells and conflicting requirements.
- [ ] Add multiple views only after a correct single release pipeline.

**Acceptance:** spatial merges cannot silently weaken regional rules; conflicts have
explicit resolution or rejection.

## 10. Extensions outside the next work package

- [ ] **X01 — Taxonomy (P1/P2):** separate identity/class, behavior, distribution and appearance;
  define YAML compatibility before redesign.
- [ ] **X02 — Heterogeneous scenarios (P1):** reproducible dense, sparse, empty and dynamic areas;
  retain uniform distribution for debugging.
- [ ] **X03 — Paths/trajectories (P2):** corridors, spawn/target areas and waypoints;
  add real routing when the research/attacker scenario needs it.
- [ ] **X04 — Maps/buildings/entrances (P2):** define sources, coordinates and required semantics;
  evaluate UAM-Simulator-Modern as a technical reference.
- [ ] **X05 — Collision model (P2):** assess after S02; do not automatically require ORCA
  or a replacement model for aggregation development.
- [ ] **X06 — Sensor uncertainty (P2):** preserve GT and model errors separately;
  avoid a full camera/LiDAR simulator without specific need.
- [ ] **X07 — Metal/3D/GPU (P2):** Modern has a native backend. Keep SFML initially;
  revisit migration after separate rendering/CPU/DB measurements or a defined 3D need.
  Record that Metal-Simulator was introduced as a Metal-oriented test environment but its
  retained application code uses OpenGL. Renderer migration does not move CPU aggregation to GPU.
- [ ] **X08 — Shared libraries/build (P1/P2):** reduce duplication selectively;
  preserve working independent builds as references.
- [ ] **X09 — Packaging/remote (P2):** retain the UMP-Simulator name; decide remote, license,
  publication and data/asset selection separately.

## 11. Process for subsequent changes

Before editing source, name the selected task, data rule and small scope. Afterwards update
status, verification and remaining limits. Follow Section 3 for the current delivery order.
F00/F02 and initial D01 rules are implemented. P1–P6 define the current aggregation
foundation; V01 validation and demo preparation accompany that work. Keep the simulator lean by correcting its existing pipeline.
