# TO-DO — UMP-Simulator

**Status: 2026-10-13. Current priority: a validated demo for the October 14 meeting, first evaluation results for October 18, and a tested adaptive comparison for October 25.**

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

This section orders the existing backlog by the user's confirmed dates. Checkboxes describe
deliverables, not promises that an experiment will show improved privacy. The presentation
continues to cover the complete dissertation concept in a defence-style narrative. Each
feature and result must be identifiable as implemented, tested, experimentally evaluated,
or proposed. A current quadtree visualization is not evidence of metric-driven adaptation.

| Date | Deliverable | Evidence required |
|---|---|---|
| October 14: supervisor meeting | Reliable demo, current-status summary, complete-run data validation, next experiment specification | Saved run/configuration, validation report, rehearsed demo and fallback |
| October 18: presentation submission | Complete presentation with an initial fixed spatial/temporal comparison | Reproducible table/plots, stated utility query and privacy interpretation, limitations |
| October 25: conference | Rehearsed full presentation, stable demo and a small adaptive-versus-fixed comparison if verified | Identical evaluation inputs, explicit decisions/constraints, measured outcomes and failure cases |

### M1 — Ready for the October 14 meeting

**Minimum deliverable:** demonstrate the working measurement pipeline and show what has
been verified. Full-run validation is still open; the existing regression test alone does
not establish it. A new research result is a stretch goal for this meeting.

- [ ] **M1.1 — Preserve one identifiable demo dataset (R03/R01).** Use a dedicated run
  database for GT and every sensor, record its name, actual configuration, source revision
  and any local source changes. Keep a saved copy/export available for playback and analysis.
  Verify which dataset the user just generated before treating it as the reference.
- [ ] **M1.2 — Validate the complete run (V01/D01/D02).** Check ABS uniqueness by
  sensor/agent/timestamp, GT joins, positions and displacement over consecutive sensor
  observations. Check GBS/AGBS counts against GT within each sensor's actual area and cell
  geometry. Explain expected omissions for first observations, exits and empty areas.
  Report discrepancies and tolerances; do not silently discard failing records.
- [ ] **M1.3 — Rehearse the demo (S01/R03).** Check startup, normal completion, playback,
  early window closure and restart. Fix a reproducible shutdown/crash issue before adding
  features. Test database renderer startup against the saved run if it is part of the demo.
  Use the current supported 50-ms simulation step and 10-Hz sensor settings.
- [ ] **M1.4 — Prepare a short fallback.** Save screenshots or a short screen recording of
  the same verified run and keep a clear start command/configuration at hand. Target a
  3–5-minute demonstration; adjust to the actual meeting format.
- [ ] **M1.5 — Prepare the discussion material.** One status page or slide with working
  components, corrected defects, validation findings and remaining scientific questions.
  Include one timeline/count figure when the validated data supports it. These are data
  correctness results; an empirical privacy improvement has not yet been established.
- [ ] **M1.6 — Specify the first experiment (E01/E02/D03/B01).** Draft one application
  query, one attack question, the publication fields, and a small parameter matrix for
  supervisor discussion. Identify what will count as success, failure or an inconclusive result.

**Today, October 13 — execution order:**

1. Inspect the just-generated run and preserve/configure one identifiable dataset (M1.1).
2. Implement a reusable read-only validation report and inspect any failures (M1.2).
3. Repair only defects that invalidate that report or disrupt the selected demo (M1.3).
4. Rehearse and save the fallback, then write the status summary (M1.4/M1.5).
5. Specify the first experiment. If the demo and report are ready, attempt a small fixed
   aggregation pilot using the same saved observations (M1.6; B01 stretch).

**Stop rule for tonight:** secure the dataset, report and demo before starting an aggregator
feature. A tiny correct comparison is preferable to promising an untested adaptive system.
If a validation check fails, report the exact remaining issue and use the verified subset
only when its selection and limitations are explicit. Do not relabel a failed run as validated.

**Meeting decisions to seek:** application query, relevant attacker knowledge, interpretation
of regional constraints, and which evidence is sufficient for the October 18 submission.

### M2 — Presentation ready for October 18

**Required result:** a small, reproducible fixed space/time comparison plus an explicit
evaluation definition. Submission does not depend on completing policy trees or buckets.

- [ ] **M2.1 — Freeze experiment semantics (E01/E02/D03).** Select a fixed application
  query, e.g. occupancy in fixed application zones at specified query times. Define the GT
  reference, how coarse/delayed releases answer the query, missing/suppressed values and
  publication timing. Keep the reference query fixed across variants. Define occupancy
  separately from distinct contributing identities and accumulated observation counts.
- [ ] **M2.2 — Reuse identical inputs (R01/B01).** Evaluate every configuration over the
  same saved observations and detection area. The live ABS/GBS/AGBS regions currently differ;
  comparing their raw errors as if they saw the same population would be invalid. A frozen
  input stream is sufficient for this first comparison; central RNG seeding can follow.
- [ ] **M2.3 — Implement the fixed aggregation baseline (B01).** Start with a small
  configurable matrix, provisionally 3 spatial sizes x 2 temporal windows. Select concrete
  values after inspecting density and duration. Define half-open windows, incomplete final
  windows, empty cells and release times. Use aligned periods for the first pilot.
- [ ] **M2.4 — Produce the first results (E01/B01).** Export a configuration/result table
  and 1–2 readable figures: application error versus resolution/window, alongside coverage
  and delay. Record input identity, sample support and measurement method. Do not claim
  generality from one run or mix repeated observations with independent replicates.
- [ ] **M2.5 — Make the privacy evaluation precise (E02).** Choose an attack goal,
  auxiliary knowledge, visible releases and a prior/no-release baseline. Implement a small
  pilot attack if the model is sufficiently clear. If only distinct-contributor counts or
  threshold compliance are available, label them as structural indicators, not measured
  anonymity or proven privacy gain. Carry an unvalidated attack as an open experiment.
- [ ] **M2.6 — Prepare and submit the full presentation.** Retain motivation, threat model,
  taxonomy/policy concept, architecture, adaptation concept and evaluation. Add verified
  results and clearly distinguish planned functionality. Rehearse the full narrative and
  retain the stable M1 demo/fallback. Prepare the submission version on October 17.

**Suggested sequence:** October 14 after the meeting: incorporate decisions and freeze
the evaluation specification. October 15: fixed aggregation and reference query.
October 16: parameter sweep, checks and result plots. October 17: interpretation, slides
and rehearsal. October 18: final checks and submission; later revisions remain possible.

**Technical scope control:** F01/D02 actual-interval handling becomes required if an
experiment introduces non-aligned/variable sampling. Otherwise retain and state the tested
fixed setup for this milestone. Address R02 before claiming reproducible new simulation
runs; replaying saved input already ensures equal input for aggregation comparisons.

### M3 — Conference ready for October 25

**Implementation target:** one small adaptive release pipeline compared with the M2 fixed
baselines. The paper's full architecture remains the research direction; only tested parts
are presented as running functionality.

- [ ] **M3.1 — Specify one adaptive policy (A01/A03).** Choose one decision order, such
  as spatial-first with bounded temporal extension, and one initial global policy. State
  input/output fields, minimum support rule, spatial/temporal bounds and behavior when no
  permitted release is possible. Support counts are release rules, not a privacy guarantee.
- [ ] **M3.2 — Implement one complete adaptive path (A01/A02/A03).** Ingest observations,
  maintain the history required by that policy, decide, and emit a timestamped aggregate.
  Verify distinct contributors, compatible merge intervals, no double counting, splits,
  retention bounds and suppression. For a first offline experiment, shared bounded history
  can support logical windows; full active/preemptive container infrastructure is not a gate.
- [ ] **M3.3 — Compare adaptive and fixed variants (B01/A03/E02).** Use equal observations,
  release information, reference query and attacker assumptions. Include sparse/dense and
  changing-density conditions with sufficient samples. Report error, coverage, delay, rule
  violations and cost; add attack outcomes only for a validated attack implementation.
  An adaptive approach may lose to a fixed baseline; report that outcome and its conditions.
- [ ] **M3.4 — Extend evidence rather than scope.** Repeat comparisons over additional
  frozen scenarios/runs and summarize variation appropriately. Distinguish a one-run pilot
  from replicated evidence. If real-time performance is claimed, measure processing latency
  and throughput separately from simulated time and playback speed.
- [ ] **M3.5 — Regional policy example (stretch, A04).** After the global policy passes,
  demonstrate two regions with different rules, including a boundary-crossing case. Specify
  overlap/conflict resolution first. A simple region lookup can precede the full policy tree.
- [ ] **M3.6 — Freeze and rehearse.** Prepare final results by October 23; use October 24
  for full rehearsal, playback checks and backup material. Avoid feature work on October 25.

**Suggested sequence:** October 19: adaptive contract and hand-worked examples.
October 20–21: implement and verify the single policy. October 22: comparative experiments
and attack pilot, if ready. October 23: repetitions, interpretation and updated slides.
October 24: freeze and rehearsal. October 25: presentation.

**Fallback if adaptation is not validated by October 23:** present the verified fixed
comparison, explicit adaptive design and documented remaining experiment. Keep the demo
on the stable implementation. Do not represent the current fixed-depth AGBS as a working
privacy/utility optimizer. Regional trees and full buckets remain open if not completed.

### Work deferred unless a milestone requires it

Full taxonomy redesign, native Metal migration, real city maps/doors/roads, realistic route
generation, broad collision-model replacement, multiple application policy trees and the
complete active/preemptive bucket architecture are outside today's delivery scope.
Existing correctness defects become urgent when they affect the chosen run or experiment.
Keep these items in the backlog and connect each future implementation to an evaluation need.

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

## 9. Adaptive aggregation: subsequent development stage

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
F00/F02 and initial D01 rules are implemented; M1/V01 complete-run validation and demo
readiness come next. Keep the simulator lean by correcting its existing pipeline.
