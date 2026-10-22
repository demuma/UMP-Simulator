# TO-DO — UMP-Simulator

**Status: 2026-10-22. Current priority: sequential algorithm and policy-compliance work.
A07 common-window valid-descendant rescue and A08 semantic common/local coordination
are implemented and verified within their reports. Review the full aggregator
requirements and stated limits before broadening the mechanism. Membership attacks and computation/cache optimization
remain deferred. October 18 is historical.**

**October 22 checkpoint:**

- [x] Make replay cell inspection explicit: keyboard-selectable cell list, selected
  outline, focus zoom, released categories and opt-in private original groups for
  exactly the displayed cell/window. Show local policy geometry separately from
  the effective checks. See [viewer guide](tools/replay_viewer/README.md).
- [x] Run the bounded [16-leaf regional-policy experiment](docs/LOCAL_LEAF_POLICY_RESULTS_2026-10-22.md)
  on identical observations: intermediate semantic groups, sibling merge, infeasible
  support, unchanged controls and a coarse footprint intersecting an empty strict patch.
- [x] Record the historical common-window temporal coupling explicitly. In that
  baseline a regional 600-ms limit constrains the complete semantic interval; the
  subsequent semantic local gate verifies independent owner windows instead.
- [x] Integrate these checks into the [four-step taxonomy/policy roadmap](docs/TAXONOMY_POLICY_ROADMAP_2026-10-22.md).
  Full modifier-based population generation, regional attribute restrictions and
  arbitrary/overlapping map geometry remain later work.
- [x] Inventory the 162 existing changed paths and prepare a compact, integrity-checked
  results-only package. Keep generated movement recordings, full replay streams,
  the 29-GB raw result tree and external papers out of Git.
  [Checkpoint](docs/RESEARCH_CHECKPOINT_2026-10-22.md), [package](docs/REPLAY_DATA_PACKAGE.md).
- [x] Complete the integrated build, 60-entry CTest run, real-artifact group checks,
  browser inspection and portable-data verification. See the
  [October 22 test report](docs/REPLAY_LOCAL_POLICY_TEST_REPORT_2026-10-22.md).
- [x] Implement semantic-aware cell-local ownership, current-endpoint rescue planning,
  independent regional deadlines and scoped publication/recovery. Follow the
  [contract](docs/SEMANTIC_CELL_LOCAL_CONTRACT_2026-10-22.md) and verify the identical
  leaf-policy fixture before drawing effectiveness conclusions.
- [x] Clarify analytical replay provenance and add reference-cell zoom, full-sample /
  viewport identity counts and exact-coordinate multiplicities. Four identities in
  cell 12300 are distinct even when their markers overlap at full-area scale.
- [x] Implement and verify the
  [asynchronous historical mosaic](docs/ASYNC_LOCAL_REPLAY_CONTRACT_2026-10-22.md)
  in the HTML replay: original cell/window provenance under clipping, event-time
  causality, independent public/private histories, empty scope retirement, rewind
  and bounded masks. See the [viewer test report](docs/ASYNC_LOCAL_REPLAY_TEST_REPORT_2026-10-22.md).
- [ ] Next: implement scope-aware semantic fixed-query utility. Preserve original
  cell/interval statistics and taxonomy semantics, unknown support, fixed query and
  deadline cohorts, and coverage alongside conditional error. The viewer is not
  this evaluator and does not complete it.
- [ ] Then compare common/local adaptation with legal fixed raster/window settings
  on the same existing moving input and hard policy. Declare minimum duration,
  query masks, EOF scope and release-event costs; common-window adaptive
  coordination is an ablation, not the fixed baseline.
- [ ] Review agreed aggregator requirements at each gate: hard eligibility versus
  preference, intermediate tiers, regional bounds, independent starts, current
  merges/future handoffs, irreversible publication, complete source retirement,
  missing measurements, budgets and retries. Separate verified cases from open scope.
- [ ] After those gates, design privacy evaluation with protected unit/secret,
  recipient information, measured privacy objective and appropriate policies/scenarios.
  No new utility optimizer, movement generator or attack matrix is started by
  the current visualization task.

**Current execution order (supersedes older next-step notes below):**

1. **Completed:** A07 preserves valid whole descendants after failed spatial merging.
2. **Completed:** A08 adds exact category support, declared semantic loss and complete
   truthful category cuts, regional checks and immutable recipient storage/recovery.
3. **Completed bounded review:** the [semantic priority study](docs/SEMANTIC_PRIORITY_STUDY_2026-10-21.md)
   audits 360 configurations / 1,929 actual intervals plus 12 repeats. Legal trade-offs
   remain between spatial detail, class detail and fixed-query answerability; production
   selection is unchanged. Support remains an operational minimum, not a completed QI model.
4. **Completed:** first [Semantic First controller](docs/SEMANTIC_FIRST_IMPLEMENTATION.md),
   with TF secondary priority, zero-loss preference and bounded terminal fallback. The
   [27-case comparison](docs/SEMANTIC_FIRST_RESULTS_2026-10-21.md) and
   [test report](docs/SEMANTIC_FIRST_TEST_REPORT_2026-10-21.md) pass: 52 CTest entries,
   361 passed Python methods/12 existing optional skips, 13 native cases and 30 unchanged
   legacy pairs. Its first waiting rule remains a historical baseline; the later
   semantic release update and next local-semantic gate below supersede this
   earlier fixed-secondary limitation.
5. **Completed - MR01, recorded moving-data comparison:** use the existing C++
   Simulator, verified GT/AGBS capture and the same frozen observations for all methods.
   Requested populations 200/500/1000, initially 20 simulated seconds, seven maintained
   profiles, 80 m x 80 m and depth 6. Compare six fixed settings (10/20/40 m crossed
   with 400/1000 ms) against TF/SF/Semantic First under the identical uniform-root
   requirements. See the [implementation/how-to](docs/MOVING_REPLAY.md) and
   [predeclared protocol](docs/MOVING_REPLAY_PROTOCOL_2026-10-21.md).
   - [x] Complete system verification: input evidence, scalar/semantic raw-data audits,
     source accounting, deterministic frozen-input repeat and viewer time gating.
   - [x] Record actual population/type evolution, retained observations, query coverage
     and conditional MAE, spatial/semantic detail and interval age. Separate system
     acceptance from measured effectiveness; no favorable-result promise.
   - [x] Inspect synchronized recorded motion/release replays and save a presentation
     fallback image or recording. No new live/network latency claim.
   Acceptance: 55/55 CTest entries; 27 independently audited method outputs, three
   deterministic repeats and browser playback inspection. See the [results](docs/MOVING_REPLAY_RESULTS_2026-10-21.md)
   and [test report](docs/MOVING_REPLAY_TEST_REPORT_2026-10-21.md).
6. **Completed - MR01b, maximum output-cell sensitivity:** hard 10 m and 5 m
   caps are available through `--max-cell-side-m`, with matching search depths and
   distinct policies. Reused all three frozen sources; no new motion or source-area
   change. The [protocol](docs/CELL_SIZE_CAP_PROTOCOL_2026-10-21.md) precedes all
   54 new method outputs; six deterministic repeats and independent cap/source/
   scalar/semantic checks pass. Seven focused CTest entries pass, including 81
   actual C++ cap regressions. The original 40 m data are unchanged.
   [Results](docs/CELL_SIZE_CAP_RESULTS_2026-10-21.md) record suppression and unknown
   task support explicitly. At N=500, retained contributions are 93.91%/28.31%
   for 10 m/5 m; the latter answers no complete fixed 10 m/1 s query.
   [Commands and replay](docs/CELL_SIZE_CAPS.md) include direct cross-cap views.
7. **Completed - MR01c, four-second window sensitivity and priority diagnosis:**
   separate `--max-window-ms 4000` policies couple duration, age and controller
   limits, with 5 s history and adequate bounded evaluation/bin capacity. The
   [protocol](docs/FOUR_SECOND_WINDOW_PROTOCOL_2026-10-21.md) predates 72 new outputs
   and six repeats; nine regression methods run the actual C++ core 23 times,
   and seven focused CTest entries pass. Independent reconstruction verifies
   40,239 public cells / 41,554 semantic bins, all 540 artifact hashes and
   36 overlapping fixed controls. Prior pilot/cap artifact hashes are unchanged.
   At the 5 m cap, SF retention rises 4.95 -> 10.90%, 28.31 -> 49.26%, and
   65.48 -> 81.66%; release age and short-deadline losses remain explicit.
   [Results and test report](docs/FOUR_SECOND_WINDOW_RESULTS_2026-10-21.md),
   [exact-equality diagnosis](docs/SEMANTIC_SPATIAL_EQUALITY_2026-10-21.md) and
   [paired playback](docs/FOUR_SECOND_WINDOWS.md) distinguish support below five
   from inability to retain detailed classes. Root pooling permits support five
   across all seven types; repeated samples of one identity count once.
8. **Completed - semantic release control:** `semantic_secondary_strategy` now
   supports Temporal First or Spatial First. Semantic `release_trigger` defaults
   to `policy_satisfied`; explicit `priority_satisfied` retains preference waiting.
   Both default secondaries can coincide because immediate legal release wins
   over optional waiting. Hierarchy intermediates remain truthful categories;
   max loss 1 permits Root but does not force every bin to Root. See the
   [contract](docs/SEMANTIC_RELEASE_CONTROL.md) and
   [test/result report](docs/SEMANTIC_RELEASE_TEST_REPORT_2026-10-21.md).
   Old experiment runners explicitly retain their historical preference trigger;
   frozen captures/results/protocols are unchanged.
9. **Completed integration - semantic cell-local coordination:** taxonomy-enabled
   TF/SF/Semantic First now share the existing ownership/handoff coordinator. Current
   legal parent rescues precede child disclosure; default eligible releases do not
   wait solely for speculative future merges. Explicit preference waiting remains
   bounded by each affected owner's regional deadline and handoff boundary. Scoped
   immutable publication, recovery, identity unions and source retirement are tested.
   See the [contract](docs/SEMANTIC_CELL_LOCAL_CONTRACT_2026-10-22.md) and
   [controlled comparison](docs/SEMANTIC_CELL_LOCAL_TEST_REPORT_2026-10-22.md).
   The [asynchronous viewer gate](docs/ASYNC_LOCAL_REPLAY_TEST_REPORT_2026-10-22.md)
   is now implemented and verified. Next adapt scoped semantic query utility, then
   compare the same moving input against legal fixed baselines, reviewing aggregator
   requirements at every gate. Privacy evaluation follows; do not infer global
   mean-loss optimality or privacy gains from policy compliance.
10. **MR02, presentation gate (narrative drafted, slide editing/rehearsal open):** prepare one coherent 20-minute narrative: question and
   conditional answer first; policy model, three adaptation dimensions, controlled
   trade-off, recorded replay and validated fixed-baseline comparison. Put simulator
   implementation, extra metric catalogs and old attack studies in backup. Mark
   future scenarios explicitly. Use the [18-minute narrative plus buffer](docs/PRESENTATION_NARRATIVE_20MIN_2026-10-21.md).
11. **MR03, subsequent evaluation design:** first adapt scoped semantic fixed-query
   utility and compare the same existing moving input with legal fixed baselines.
   Review aggregator requirements and evidence at each gate. Then specify the privacy
   objective, suitable policies and controlled scenarios before a new privacy matrix.
   Later consider independent captures, density/turnover and heterogeneous regions
   one factor at a time. Keep the
   same source, hard constraints and query/deadline cohort across legal fixed and
   adaptive comparisons. Scoped semantic queries are not implemented by the local
   mechanism gate. A one-type/seven-type control remains separate; the current
   fixed mix does not estimate a causal type-count effect. ALOQ reproduction is a
   later external comparison with different privacy guarantees, requiring a verified
   adapter, units, seeds and geometry. Do not automatically start these experiments.
12. Keep finest observation depth 6 unchanged. Maximum output size is a separate
   hard policy bound. Individual/type suppression, per-class utility priorities and
   broader simulation realism remain separate decisions.

The pre-implementation [A07 acceptance contract](docs/SELECTIVE_DESCENDANT_RESCUE.md)
defines the exact rule, examples and required verification. Existing privacy studies
remain historical evidence; new attacks, map realism, taxonomy redesign and caching
are not prerequisites for this bounded step.

This is the central task backlog. README describes current behavior; this file tracks
pending changes. The historical IMPLEMENTATION_PLAN remains a reference, not an instruction
to begin every listed phase. All project documentation is maintained in English.

**Review update, 2026-10-19:** functional street/shop regions and evidence scope are recorded in
[FUNCTIONAL_REGIONS_AND_EVIDENCE.md](docs/FUNCTIONAL_REGIONS_AND_EVIDENCE.md). The scenario,
not the exact mockup drawing, defines the next study. Region-to-policy compilation exists;
corridor-constrained motion remains open. Independent cell-local windows and coordinated
merge groups are now available in an opt-in mode; see [CELL_LOCAL_COORDINATION.md](docs/CELL_LOCAL_COORDINATION.md)
and [the coordination test report](docs/COORDINATION_TEST_REPORT_2026-10-19.md).

**Cell-local verification, later on October 19:** 27/27 CTest suites and 134 Python methods
pass; 14 coordination cases and 120 seeded stress scenarios also pass ASan/UBSan.
A complete 120-s headless run passes independent auditing of 160415 terminal domains.
The paired common/local effectiveness study is complete: 270 audited replays and 120
scientific repeats. It finds benefits under regional constraints and clear mixed-density
losses, plus concrete hold/publication counterexamples. A subsequent endpoint-planning
refinement now closes those examples and is verified on the identical matrix; all 210
untouched references match. Mixed-density SF retention matches common, TF differs by
-0.0732 pp on average. The user now prioritizes the [empirical privacy comparison](docs/PRIVACY_COORDINATION_STUDY_2026-10-19.md).
See the [refinement report](docs/COORDINATION_REFINEMENT_2026-10-19.md) for accuracy trade-offs.

**Previous completed milestone:** the independent 208-group robustness study passes
2080 audits and four repeats, with 28 fixed attack models and separate base/shift tests.
It does not establish a general local privacy advantage: 15/16 paired intervals contain
zero and one indicates greater attack success. Local retention/availability also fall.
[All results](docs/PRIVACY_ROBUSTNESS_STUDY_2026-10-19.md); [36-suite / 228-method test report](docs/PRIVACY_ROBUSTNESS_TEST_REPORT_2026-10-19.md).
The causal-prefix/deadline follow-up is now complete (October 20, below). Further
coordinator tuning follows explicitly measured needs; a semantic-visit experiment needs
a separate protection objective and ground-truth contract.

**Current diagnosis:** [local coordination follow-up](docs/LOCAL_COORDINATION_DIAGNOSIS_2026-10-19.md)
shows TF freshness benefits on the same retained observations and better coverage at
strict logical deadlines, alongside eventual retention/availability losses. One passing
parent is blocked solely by a contained future handoff reservation. This measured
coordination limitation is now repaired and regression-tested. The fresh before/after
assessment follows the [fixed protocol](docs/HANDOFF_REPAIR_PROTOCOL_2026-10-19.md);
see the [repair report](docs/HANDOFF_REPAIR_REPORT_2026-10-19.md) and
[37-suite / 236-method test report](docs/HANDOFF_REPAIR_TEST_REPORT_2026-10-19.md).

**Previous completed milestone:** the [handoff repair](docs/HANDOFF_REPAIR_REPORT_2026-10-19.md)
passes 37 suites/236 Python methods, 27 focused functions and 240 sanitizer stress cases.
The fresh 208-group study confirms higher retention and query coverage with small utility
costs and no general privacy improvement. These measured limits, including two increased
attack-success contrasts, motivated the subsequent causal evaluation without changing
the protected whole-source membership fact.

**Latest completed milestone, October 20:** [causal privacy and deadline utility](docs/CAUSAL_PRIVACY_REPORT_2026-10-20.md)
passes 40 CTest suites, 285 Python methods and independent source/score/deadline audits.
The fresh 208-group study contains 2080 audited executions and 360 checkpoint models.
Local TF improves zero-lag coverage by 2.38/5.15 pp (base/shift), but not at a one-second
lag; local SF has lower coverage at every tested lag. All 16 local history-minus-recent
AUC intervals include zero, and their representation/regularization difference prevents
a pure memory-effect claim. The empirical CAL alarm cap does not guarantee TEST FPR.
The [test report](docs/CAUSAL_PRIVACY_TEST_REPORT_2026-10-20.md) records verification scope.
No new C++ controller change, semantic secret or live service was introduced.

**Editor diagnostic repair, October 20:** a fresh C++17 syntax check of
`simulator/src/Simulation.cpp` and the simulator build pass. The local VS Code
configuration selected x64 and `/usr/local` MongoDB driver headers, while CMake
uses arm64 and `/opt/homebrew`. The local C/C++ configuration now follows the
CMake compilation database, with matching Apple Silicon fallback paths. CMake
exports that database by default; README documents setup and cache reset.
The reported line-394 coverage initialization and line-406/409/411 constructor
calls match the current declarations and pass a fresh compiler syntax check.
Fallback include paths now name only source include directories, excluding frozen
header copies under `results/`. Editor cache refresh remains necessary if its
diagnostics continue to disagree with the compiler.
This changes build/editor configuration only; simulation behavior is unchanged.
Verification: fresh configuration, simulator build, compiler syntax check and
generated compile-command inspection. Remaining editor diagnostics require
their exact message/line to distinguish stale cache from another problem.

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

**Current position: the first integrated Stage 5 baseline is implemented. A05 now connects
policy-selected private final snapshots to a durable MongoDB release sink and private
journal. A03 adds Temporal First and Spatial First with bounded temporal extension,
regional deadlines and future handover. The common-window model is intentionally
conservative and remains the default. The opt-in cell-local controller adds independent
windows, mixed-depth handoffs and scoped publication. Other publication models and automatic restart
remain open. E01 fixed-query occupancy evaluation and R01 frozen replay are now implemented,
with four fixed baselines and spatial/Temporal First/Spatial First comparisons. E02 has a
complete-background diagnostic plus the first public-only controlled synthetic trained attack.
On 2026-10-19 EP01, seeded grouped datasets and E02-A–C were implemented and tested;
23 CTest suites and 126 Python tests passed, with three completed synthetic configurations.
Broader regional studies, real-world attacker realism and general A07 optimization remain open.** The detailed
[bucket lifecycle and release protocol](docs/BUCKET_LIFECYCLE.md) records the current
proposals, flow diagram, storage model and hand-worked cases. The
[fixed aggregation contract](docs/FIXED_AGGREGATION.md) records actual A01 behavior;
the [A02 history contract](docs/AGGREGATION_HISTORY.md) records implemented private
reconstruction and logical windows. Common-window and opt-in cell-local release coordination are implemented; other recipient-visible publication models remain proposals. The core is reusable across sensor types;
AGBS is the first integration target.
Separate sensor behavior/state is preserved. A generic API does not imply that every
sensor provides every metric input or supports arbitrary spatial refinement.

| Order | Work package | Main tasks | Completion evidence |
|---|---|---|---|
| 1 — foundation implemented | Common evaluation area; input, count and output semantics | D01–D03, A01 | Concrete AGBS batch/aggregate examples and chosen units |
| 2 — online slice implemented | Metric definitions and required statistics | E01, E02, E04 | Defined inputs, calculated values and evaluation references |
| 3 — initial numeric slice implemented | Policy tree using existing Regions | A04 | Effective regional requirements, inheritance and conflicts |
| 4 — private reconstruction implemented | Active/preemptive buckets and history | A02 | Hand-worked windows, lifecycle and retention rules |
| 5 — baseline implemented; extensions open | Publication coordination, AGBS decisions and inspection | A05, A03, A07, A06 | Fixed release/suppress path, then merge/split, partial suppression, time extension and debug view |
| 6 | Complete-run checks and comparative evaluation | V01, B01, R01–R03, X02, E05, E06 | Equal input, verified releases, publication/priority comparisons and preparation-cost study |
| 7 — later | Taxonomy brainstorming, renderer settings and control GUI | X01, X10, X11 | Separate design proposals and measured implementation scope |
| 8 — later | Map extraction, routes and collision avoidance | X04, X03, X05 | Controlled scenarios and realism/performance evidence |
| 9 — as justified | Further metrics, uncertainty, graphics and infrastructure | E03, X06–X09 | Research or measured engineering need |

F01 and S01–S05 are corrections alongside the active stage when its correctness
or execution depends on them. **S04 and the S01 transport correction are implemented and
regression-tested; manual live inspection remains pending.** Bucket contract work continues. F03 covers
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
- [x] Specify the internal observation batch; do not treat renderer cell-ID snapshots as input data (A01 fixed input).
- [ ] Resolve active/preemptive interval ownership, publication states and bounded retention.
- [ ] Define sibling time alignment and already-published-data behavior for merge/split.
- [x] Integrate existing Region instances into one application policy tree, with cached lookup
  and explicit inheritance/boundary rules; no full tree per individual metric (initial aligned,
  non-overlapping rectangle scope; see A04).
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
AggregationManager now ingests identity-bearing batches and emits bounded fixed-window
candidates through a separate sink. A04 compiles explicit root/type/Region requirements
into a sparse policy tree and E04 evaluates them for each candidate. Legacy k/l fields
remain inactive. A02 now retains bounded fine observations and reconstructs candidate
windows on demand. A03 now automatically chooses a private spatial cut per fixed window,
including sibling merging, future-window refinement and whole-domain suppression. Public
release coordination and temporal adaptation remain missing components.

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
  A01 now implements the input/count/window portion; release-time semantics remain A05.
- [ ] **P2 — Working aggregation/history (A01/A02).** Fixed candidate mode is implemented
  and tested for repeated observations, boundaries, empty windows and contributor unions.
  A02 now retains fine observation bins and reconstructs parent/child or extended candidates
  on demand. Active/preemptive logical records share that history, with explicit resource
  limits and deadlines. Coordination ownership and committed-output invalidation remain A05.
- [ ] **P3 — Metric contract and initial measures (E01/E02/D03).** Each metric must have
  a definition, inputs, units, validity and relationship to a constraint or objective.
  Start with distinct contributors, cell size/area, aggregation duration and release age.
  These support decisions; contributor support is not a general anonymity guarantee and
  resolution/delay alone do not establish application utility. Define a fixed application
  query and compute its error against GT in evaluation. Empirical attack evaluation remains
  a separate research measurement. Unavailable metrics must be reported, not invented.
  The E04 online registry/checks and E01 query contract are implemented/documented; the
  GT reconstruction experiment and independent attacker model remain pending.
- [x] **P4 — Minimal actual policy tree (A04).** Implemented a separate immutable tree with
  root/type/Region inheritance and a runnable two-region example. Compatible numeric hard
  bounds intersect; cross-region parent conflicts do not contaminate child requirements.
  Unsupported overlaps/unaligned boundaries and contradictory inherited rules fail explicitly.
  Tests cover geometry, inheritance, context and startup before DB writes. Thresholds are
  demonstration parameters; root strategy/model selection is now integrated, while regional execution overrides and live policy changes remain open.
- [x] **P5 — Initial decision and publication baseline (A03/A05).** Evaluate a candidate with P3/P4 and record
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
- [x] One application policy tree with a default and two regional children (A04 example/tests).
- [ ] Checks for contributor counting, policy inheritance and release/suppression.
- [ ] Rehearsed demo/fallback and explicit current limitations.

**Fallback if integration is incomplete:** show the working simulator, completed executable
parts and hand-worked pipeline examples; name the missing connections. Do not present a
scaffold or fixed-depth AGBS visualization as dynamic metric-driven aggregation.

**Meeting questions:** validate the application query, attacker knowledge, meaning and
priority of regional constraints, and acceptable evidence for the paper/presentation.

### M2 — Pipeline and first results by October 18

- [ ] Finish the minimum P1–P6 integration and the checks deferred from M1.
- [x] Add metric/policy-based parent/child selection (A03) so release depth varies locally.
  Retain the existing quadtree as the hierarchy; make the release selection explicit.
- [x] Use identical saved observations and detection area for fixed/adaptive comparisons.
  Current live ABS/GBS/AGBS regions differ and are not directly comparable populations.
- [x] Freeze D03 window/count semantics and E01's fixed application query, including how
  coarse or delayed releases answer it and how suppression/missing data are handled.
- [x] Run a small fixed space/time matrix and all implemented adaptive strategies.
  Export a result table covering application error, coverage, sealing age and policy compliance,
  with frozen input/configuration and explicit limitations (dated evaluation report).
- [ ] Prepare the utility/policy evidence: numerical error, query coverage, release compliance,
  output availability and binding constraints. E02 is deferred beyond this milestone by
  the current scope decision; support counts remain operational requirements.
- [ ] Prepare the full presentation on October 17 and submit on October 18. Preserve the
  overall dissertation narrative and distinguish tested functionality from planned work.

**Suggested sequence:** October 14: supervisor feedback and complete the first path.
October 15: dynamic spatial release selection and fixed baselines. October 16: experiments,
validation and figures. October 17: interpretation, slides and rehearsal. October 18: submission.
Temporal adaptation was brought forward and is implemented; comparative evidence remains due.

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
  equal inputs, reference queries and regional policies. Report measured outcomes even
  when adaptation loses; empirical privacy claims remain outside the current scope.
- [ ] Extend utility/policy evaluation to additional saved runs/scenarios and summarize
  variation. Measure processing latency/throughput separately from simulated time before
  making real-time performance claims. Revisit E02 after this milestone.
- [ ] Complete figures and results by October 23. Use October 24 for full rehearsal,
  playback checks and backup material; preserve a stable demo for October 25.

**Updated sequence:** the common-window temporal baseline is verified on October 14.
Use October 19–23 for controlled comparisons, regional edge cases and interpretation.
October 24: freeze/rehearsal. October 25: presentation. Keep any unimplemented
active/preemptive coordination visible in the backlog rather than treating it as completed.

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

**Additional absolute-time audit (2026-10-14):**

- [ ] Make the timezone convention explicit for `simulation.datetime` and audit DST handling.
  The capture configured `2026-10-14T10:30:00`, while authoritative Mongo metadata used
  `2026-10-14T09:30:00.000Z`. Relative GT/AGBS times were exactly aligned; do not infer the
  intended UTC offset from this timezone-free string or change old reference timestamps.

### D03 — Define aggregate counts and windows — P0 before temporal aggregation

Fixed-mode contract and a worked example: [FIXED_AGGREGATION.md](docs/FIXED_AGGREGATION.md).

- [x] Distinguish contributions, distinct people, instantaneous sample occupancy and sample
  mean occupancy. A continuous-time average still needs an interpolation/integration model.
- [x] Use explicit observationContributions, distinctContributors and typeObservationContributions.
- [x] Define fixed half-open [start,end) windows, integer milliseconds and sampling alignment.
- [x] Define complete coverage, no sample due, measured empty and unavailable observations.
- [x] Finalize fixed windows explicitly at the exclusive end; mark truncated final intervals.
- [ ] Keep original window start/deadline through spatial merges; distinguish duration
  from release age when the public release protocol is implemented.
- [ ] Distinguish Empty, Suppressed and Unavailable.
- [x] Separate internal identities from candidate output fields; public release metadata remains A05.

**Acceptance:** repeated observations of one person count once for distinct people but
multiple times for contributions. Small example data demonstrates every chosen definition.

### A01 — Define states and AggregatedCell — P0

**Implemented first slice (2026-10-13):** optional AGBS adapter, standard-C++ fixed-window
manager and external JSONL sink. See [FIXED_AGGREGATION.md](docs/FIXED_AGGREGATION.md).
The renderer path remains count-only and separate. This is internal candidate aggregation;
it neither approves publications nor implements adaptive bucket history.

- [x] Separate geometry/input, current-window state and output. Document missing history/release layers.
- [x] Use sensor-local optional ownership without MongoDB coupling in the core.
- [x] Define run/sensor/batch/cell/window/application keys and concrete count/time units.
- [ ] Define public release keys/generations and policy/decision fields with A05.
- [x] Implement ingest(batch), advance(now), synchronous completed-output consumption,
  finish(end) and read-only debug state; no-sample ticks still close elapsed windows.
- [x] Replace prototype collection/timestamp references with value input and an external sink;
  render-only AGBS instances do not instantiate an operational manager.
- [x] Choose direct value batches; the manager needs neither update(now, tree) nor a bound tree.
- [x] Implement an AGBS adapter and reusable core without Sensor, Agent, SFML, MongoDB or
  renderer-buffer dependencies. Reuse the existing quadtree mapping in the adapter.
- [x] Declare capabilities: internal identities, observed type and fixed leaf-cell support;
  count-only sources are rejected for this distinct-contributor mode.
- [x] Bound active-window state by an explicit observation budget and synchronous output sink.
- [x] Validate stream identity, duplicate/order/cadence, cell support and finalization.
- [x] Keep manager state independent per sensor/application; exercise two live AGBS rates.
- [ ] Add multiple application instances per configured sensor and ABS/GBS adapters later.
- [x] Add bounded reconstructable history and representable ancestor queries under A02.
- [ ] Add automatic dynamic candidate selection under A03 with A05 publication coordination.

**Validation:** Release build, three CTest suites, and a one-second full executable smoke
run with isolated MongoDB. Six candidate windows from 10/5-Hz AGBS matched sampled GT
distinct IDs/contributions and raw AGBS contributions per cell/window. JSONL contains no
individual IDs. Existing Simulation data and maintained YAML were unchanged.

**Acceptance:** small interfaces with clear ingestion and output; no empty abstraction hierarchy.

## 5. Stage 2 — Metric definitions and evaluation questions

**Agreed three-part work, updated 2026-10-14:**

1. **Live understanding — implemented:** independent input grid, completed decisions and
   dated active-window progress (A06). This is visualization, not additional privacy.
2. **Metric/research contract — initial slice implemented:** nine online quantities plus
   fixed-query occupancy MAE, coverage and resolution/age, with effective-policy checks.
   The previously added optional neighbouring-output stress test is deferred; it is not
   part of the current utility/policy evaluation.
3. **Controlled experiments — initial slice implemented:** seven configurations on identical
   frozen input, four fixed size/window combinations, spatial-only, Temporal First and Spatial
   First. The active results cover policy compliance, observation conservation and utility. See [CONTROLLED_EVALUATION.md](docs/CONTROLLED_EVALUATION.md) and
   [the dated results](docs/EVALUATION_RESULTS_2026-10-14.md).

**Next chronological research steps — updated after implementation, 2026-10-19:**

The [question register](docs/RESEARCH_QUESTIONS_AND_EXPERIMENTS.md),
[implementation contract](docs/EMPIRICAL_PRIVACY_IMPLEMENTATION.md) and
[test report](docs/TEST_REPORT_2026-10-19.md) distinguish completed evidence from open work.

1. Keep absent public support unknown and extend private cause diagnostics for EP02's
   measured-empty, unavailable, suppression and partial-query cases.
2. Specify targeted A07 partial-child rescue from the independently demonstrated 9-input /
   0-current / 6-relaxed retention case; add cell-local coordination before claiming
   independently adapting local temporal windows. Cell-local correctness is now implemented;
   compare its retention/latency against the common-window baseline before claiming an improvement.
3. Add justified fixed functional-region queries/masks and the aligned SC01 regional-policy
   fixture. The seeded modal-corridor generator is implemented, but is not that full study.
4. Expand EP03/EP04 policy/scenario/independent-replication evidence and runtime measurement
   from the actual pilots and stated precision targets.
5. Extend E02 only under declared additional knowledge/attack conditions; E02-D/E03 sensitive
   attributes and formal metric mappings remain separate. E05/E06 and rich maps/routing follow.

- [x] Record the metric data-readiness matrix, question register and staged experiment design.
- [x] Implement EP01's independent oracle and hand-checked expected results; bounded model
  references and 162 exhaustive depth-2 patterns distinguish compliance from model loss.
- [x] Implement seeded paired data, public export, held-out calibrated attack and controls.
- [x] Run three predeclared configurations and report 3,360 independent compliance audits,
  108 fitted attack comparisons, uncertainty and fixed-query utility with explicit limits.
- [ ] Export expanded private suppression/binding-constraint diagnostics with denominators.
- [ ] Freeze the broader EP02/EP03 regional scenario and parameter manifest.
- [ ] Choose expanded EP04 replication and uncertainty scope from pilot variability.


### E02 coordination follow-through — current privacy focus

- [x] Freeze the protected unit/secret/observer: whole four-second source contribution,
  uncertain synthetic backgrounds and identical 25%/100% exact candidate knowledge.
- [x] Extend the runner to nine explicit common/local mechanisms and two controls, with
  immutable protocol, frozen executable, policy hashes, independent per-config audits,
  paired AUC contrasts and matched-query utility support.
- [x] Correct local public-feature matching: temporal overlap alone cannot stop the search;
  require actual spatial containment. Keep private diagnostics out of attack features.
- [x] Generate 184 independent paired realizations with seed 20261020: 64 train, 40
  calibration, 80 held-out test; preserve grouped scenarios and clone/provenance checks.
- [x] Complete the fixed 3312-replay / 44-model comparison: all independent audits pass,
  all models converge, four deterministic repeats pass. Report held-out TPR/FPR, AUC,
  paired conditional uncertainty, controls, availability/accuracy and failure cases.
- [x] Prioritize and complete the new independent follow-up before further coordinator
  tuning: seed 20261021, 16-second recorded units, 48 train/32 calibration/64 base-test/
  64 shifted-test groups, exact/noisy 25% knowledge, five mechanisms and two controls.
- [x] Add the optional pinned nonlinear attack family alongside logistic regression; fit
  only base TRAIN, calibrate only base CAL, preserve the same threshold for both test
  cohorts, and report all 28 models / 56 assessments without selecting a winner.
- [x] Complete 2080 independent audits, four repeats and group-paired conditional
  uncertainty; preserve all 16 contrasts, 224 scenario assessments and utility costs.
  The new evidence shows no general local privacy benefit. See the
  [robustness study](docs/PRIVACY_ROBUSTNESS_STUDY_2026-10-19.md).
- [x] Document QI/SA roles and environmental-context risks, semantic-visit prerequisites
  and the online-prefix contract in the [new reference](docs/PRIVACY_ATTRIBUTE_AND_ONLINE_CONTRACT.md).
  These are research/interface definitions, not implemented semantic labels or an online client.
- [x] Complete the predeclared seed20261022 old/new handoff assessment: 208 fresh groups,
  separate old/new TRAIN fits and CAL thresholds, 2912 audited mechanism executions,
  36 models/72 cohort assessments, paired membership contrasts, matched-query MAE and
  exact shared-observation ages. No seeds, models or scenarios were selected after results.
  All 2912 audits/six repeats/three shared controls pass; independent reconstruction verifies
  512 held-out utility pairs and all 72 attack assessments. Retention rises 2.72–5.21 pp,
  TF shared-age rises 8.54–10.28 ms, and two pointwise SF/shift/exact AUC contrasts worsen.
  No general privacy gain or local/common equivalence is established.
- [x] Persist checkpoint CAL score rows in the new prefix bundles. Independently verify
  LR/HGB maximum-score threshold selection without estimator deserialization/refitting;
  do not claim that HGB inference itself was independently rerun.
- [x] **E02 causal-prefix extension, completed 2026-10-20:** retain whole-source membership
  and the fixed repaired controller. Freeze the [protocol](docs/CAUSAL_PRIVACY_PROTOCOL_2026-10-20.md)
  before the fresh seed20261023 data: six causal checkpoints, exact/noisy Bernoulli
  knowledge, auxiliary/recent/history controls, whole-path CAL thresholds, persisted
  score paths and grouped uncertainty. Complete all 360 models / 120 cohort assessments,
  with no TEST-based tuning. All 16 local history-minus-recent intervals include zero.
- [x] **E01 causal deadline utility:** fixed 10 m/1 s queries at lags 0/200/500/1000 ms;
  complete public support, own-deadline readiness, fixed 896-query/world interior cohort,
  matched-query error and explicit EOF censoring. Independently reconstruct all
  7,340,032 query-deadline and 2,097,152 matched projections; report the conditional TF
  benefit alongside SF losses. This changes utility scoring, not publication or privacy.
- [x] Update canonical notation to v1.5, add causal/deadline equations and compile the
  LaTeX export. Save complete aggregate tables, four PNG/SVG figure pairs and
  [implementation](docs/CAUSAL_PRIVACY_IMPLEMENTATION.md)/results/test documentation.
- [ ] **Next, E02 presentation/protection objective:** state the application, whole-source
  secret and accepted privacy/utility criteria before selecting any further mechanism
  change. Present operational policy compliance separately from empirical attack success.
- [ ] **Next empirical control:** predeclare equal-representation/regularization memory
  comparisons using new independent groups. At 1 s recent and cumulative releases
  coincide; duplicated public features change LR's effective L2 penalty. The completed
  comparison does not isolate the information value of retaining history.
- [ ] **Next calibration study:** increase independent CAL negatives and quantify
  operating-point uncertainty/transfer under declared shifts. Current 32 negative CAL
  groups permit at most three false alarms, but TEST FPR reaches 0.40625. Preserve the
  current TEST cohorts and never retune a threshold on their outcomes.
- [ ] **After the prefix evidence, E02-D discussion:** choose a defensible semantic secret and visit ground truth
  (entry/dwell rather than building proximity); keep candidate source participation in
  both visit worlds, freeze backgrounds and withhold secret/guard intervals from knowledge.
- [ ] **Then, E02-D implementation:** build a minimal synthetic destination/access-path
  fixture and auxiliary-only/release-plus-knowledge controls, independent splits and
  frozen attack protocol. Real city maps remain a separate realism extension.
- [ ] **After logical-time evaluation, online prototype:** instrument measured wall-clock
  processing, queues and actual recipient receipt. Logical sealing under assumed immediate
  delivery does not establish network latency or bounded real-time processing.
- [ ] Test noise-aware matching/trajectory smoothing or probabilistic localization on a
  newly declared assessment; current uncertain points use direct matching. Preserve all
  completed test sets and avoid tuning these methods on their outcomes.
- [ ] Explore calibration based only on observable context, with adequate independent
  negative counts; private scenario IDs/distribution labels must not become attack features.
- [ ] Treat sensitive-attribute inference and formal k/l/t/DP mappings as separate contracts;
  do not turn road-user classes into sensitive attributes simply because they already exist.

### N01 — Canonical scientific terminology and notation — implemented reference

- [x] Define the authoritative English glossary, symbols, units and code mapping in
  [TERMINOLOGY_AND_NOTATION.md](docs/TERMINOLOGY_AND_NOTATION.md).
- [x] Correct the region/window distinction: cells and coordinated merge groups own
  aggregation decisions; functional regions induce the applicable constraints.
- [x] Specify trajectory phi, tree depth d, half-open cell intervals, count/union/occupancy
  formulas, policy intersections, lifecycle terms and both preservation priorities.
- [x] Separate support thresholds from formal k/l representation-specific definitions,
  observation coverage from answered-query coverage and simulation age from wall time.
- [x] Generate reusable LaTeX equations from the reference; verify freshness and syntax.
- [ ] Extend this reference first whenever a new metric, sensor capability, independent
  cell-window model, privacy representation or publication model is adopted.

**Execution priority updated, 2026-10-20:** EP01, cell-local coordination, targeted handoff
repair, independent membership comparisons and causal deadline evaluation are complete.
Present the measured conditional utility benefits and remaining privacy/calibration
limits, then predeclare the next attack controls before more controller optimization. Controlled
functional-region scenarios and regional utility extensions follow. Rich environment
import, destination-demand processes, global/local motion planning and avoidance remain
later X04/X03/X05 work. A demonstrated aggregation limitation may justify targeted
cell-local coordination or A07 before increasing environment realism.

### SC01 — Controlled functional street/shop scenario — P0 design, then implementation

- [x] Review Region/PolicyTree support and corridor stubs against the intended scenario.
- [x] Specify the mathematical admissibility model, current global-window limitation and
  evidence needed for presentation/paper/dissertation in the October 19 review.
- [x] Check a hand-calculated spatial/temporal probe through the existing replay core:
  40-m parent at 400 ms versus four 20-m cells at 500 ms; later refinement verified.
- [ ] Define the street cross-section, stable region IDs and movement paths for road,
  cycleways, footways and entrance patches, plus the shop-front variant.
- [ ] Use aligned disjoint rectangles first; explicitly decompose entrance/context overlap.
- [ ] Validate corridor/path containment and border transitions independently of aggregation.
- [ ] Define fixed per-region occupancy queries and extend the evaluator for required region
  masks/query shapes; never use private GT to fill absent public support.
- [ ] Compare the same functional policies/input across fixed, spatial-only and both
  adaptation priorities, with regional coverage/error/age and EP01 feasibility checks.
- [ ] Decide the future rule for cross-functional-region cells. Existing intersected numeric
  bounds permit mixing; prohibiting boundary crossings is an additional constraint.
- [x] Implement explicitly configured independent cell/merge-group windows before claiming local timing.
  The cell-local mode is now available; road/entrance effectiveness still needs the controlled scenario study.

### E01 — Define one utility application — P0

Baseline contract: [METRICS.md](docs/METRICS.md#first-utility-question-e01-baseline-contract).

- [x] Select mean sampled occupancy in fixed reference cells/time intervals as the first baseline query.
- [x] Define a common 80-m evaluation square, 10-m reference cells, 1-second intervals and
  aligned 100-ms sample times; missing/suppressed predictions are not zeros.
- [x] Define conditional MAE and answered-query coverage separately; keep reference support
  fixed and document uniform reconstruction assumptions for coarser aggregate support.
- [x] Implement private-position reference extraction and public-only prediction reconstruction;
  replay all variants on one frozen input, including the coarsening counterexample.
- [x] Measure resolution, simulated sealing age, coverage and numerical error separately.
- [ ] Extend to additional application queries, independent scenarios and a justified policy sweep.

**Acceptance:** a fixed question and its GT answer are defined. Coarsening the reference
must not automatically eliminate error. Do not label record retention as data fidelity without justification.

### E02 — Define attacker and privacy evaluation — P1, first synthetic slice implemented

**Implemented, 2026-10-19:** after the independent baseline checks, the user authorized
the full first empirical path. Controlled synthetic E02-A–C is now executed; real-world
protection and later E02-D remain open. See [implementation](docs/EMPIRICAL_PRIVACY_IMPLEMENTATION.md),
[test report](docs/TEST_REPORT_2026-10-19.md) and [threat model](docs/PRIVACY_EVALUATION.md).

- [x] Specify the historical whole-recorded-trajectory membership diagnostic under complete
  deterministic background knowledge, including its balanced prior and public transcript.
- [x] Implement/test transcript equality and its derived ideal-observer success; retain
  no-output/exact-count controls and historical evidence separately from empirical attacks.
- [x] Record the E02-A–D roadmap and proposed bounded-knowledge contribution-membership study.
- [x] **E02-A:** finalize unit/horizon, secret, inclusion assumptions, recipient-visible schema,
  auxiliary/reference source, partial-trace knowledge levels and membership prior.
- [x] Enforce offline public-only field allowlists, candidate knowledge and fixed protocol
  constants; exclude IDs, private totals/windows/runtime and labels from attack features.
- [ ] Verify actual external-recipient MongoDB/GT/debug access controls before live deployment;
  offline field separation does not certify permissions. Joint application views remain later.
- [x] **E02-B:** after EP01/minimal controlled utility checks, generate independent paired
  frozen IN/OUT cases and a grouped training/calibration/test manifest; validate background
  equality, avoid copied-trace/split leakage and sample targets before release outcomes.
- [x] **E02-C:** implement a transparent public-only membership attack, declared count/
  geometry/time features, missing-data masks and fair mechanism-specific training budgets.
- [x] Select operating thresholds on calibration only; report ROC-AUC, test TPR/FPR and
  declared-prior interpretation with independent-run uncertainty and explicit finite-sample
  resolution; larger low-FPR studies remain future work.
- [x] Compare legal fixed/spatial/Temporal First/Spatial First releases on identical cases;
  pair attack results with occupancy error, coverage, retained contributions and age.
- [x] Retain prior-only, exact-count and no-output controls; test whether adaptive geometry/
  timing adds usable information. Do not count projection differences as additive leakage.
- [ ] **E02-D/E03, later:** define sensitive-visit/attribute/linking secrets and justified
  QI/group/reference models before adding k/l/t/entropy criteria or a new attack target.
- [ ] Study repeated-release differencing, multiple visible views and any future overlapping/
  revision model under an explicit joint-transcript contract once those views are implemented.
- [x] Separate operational support compliance, empirical attack outcomes and formal guarantees.

**Acceptance:** reproducible versioned threat model, public-only attack input, split/control
checks and a frozen held-out comparison with utility trade-offs and uncertainty. An unchanged
historical diagnostic or a distinct-ID threshold does not complete this milestone. A null or
negative protection result remains valid evidence; no general anonymity claim follows.

### E04 — Define the online metric contract — P0

- [x] Specify the initial registry's metric IDs, inputs, units and defined/unavailable cases
  in [METRICS.md](docs/METRICS.md); additional presentation metrics remain subject to review.
- [x] Separate registry definitions, versioned uniform requirements, measured values and checks.
- [x] Distinguish observed contributor support from a justified anonymity/equivalence-class metric.
- [x] Evaluate complete fixed candidates at closure, expose every failed/unavailable requirement
  and enforce an observation-coverage gate that thresholds cannot bypass.
- [x] Validate policy names, versions, duplicate/unknown requirements, numeric bounds and input
  consistency. No configuration means no implicit thresholds or approval.
- [x] Integrate actual metrics/assessments into v2 internal diagnostics, outside the serializer.
- [x] Test worked examples, inclusive limits, missing data, unavailable references, per-cell
  support, truncated windows and a complete YAML-to-JSONL simulation path.
- [x] Review supplied presentation PDF pages 6–8 against the implemented registry;
  record useful candidates, formula corrections and prerequisites in
  [METRICS.md](docs/METRICS.md#presentation-metric-review). This is a review, not implementation
  or final scientific selection of the presentation metrics.
- [ ] Reconcile presentation metrics with paper Tables 3–5, including definitions and
  reference populations. Do not transfer example thresholds as universally safe defaults.
- [x] Reuse A01 incremental counts/unions; measure fixed candidates only at closure. Re-evaluate
  at actual decision/release time once delayed publication is implemented.
- [x] Separate sensor period, actual duration, age at evaluation and post-window delay;
  wall-clock runtime and public release age are not inferred from these values.
- [ ] Extend metrics to actual release-time evaluation and adaptive-history candidates.

**Acceptance:** one candidate has hand-computable metric values, one policy supplies the
corresponding allowed ranges, and a decision explains each passed/failed/unavailable check.
The metric evaluator requires no renderer or live database access.

## 6. Stage 3 — Policy tree and existing Regions

### A04 — Regional policy trees / application layer — P0

**Initial implementation complete:** [POLICY_TREE.md](docs/POLICY_TREE.md) records the
contract, example and evidence. `aggregation.policy_tree` compiles root/type/Region numeric
requirements for one application stream and feeds E04's evaluator. It is an alternative
to the existing uniform `aggregation.metric_policy`. Legacy k/l and granularity fields
are not mapped implicitly. Adaptive decisions and the remaining policy features below
are not completed by this slice.

- [x] Define explicit default, regional and application-scoped numeric constraints.
- [ ] Distinguish maximum window duration, age at release, post-window delay, optional
  output cadence and processing time; specify hard bounds versus preferences for traffic
  and other applications. Never interpret a short window as a guarantee of low latency.
- [x] Reuse Region instances and region_taxonomy as policy inputs; validate IDs/type references.
- [x] Store registered metric requirements and inclusive bounds in the policy tree; calculate
  actual metric values in an evaluator from candidate statistics.
- [ ] Add richer metric parameters/reference selections only with implemented evaluators.
- [ ] Separate hard constraints, preferences/objectives, and measured candidate values.
  Maximum aggregation duration is a bound; current window duration is its measured value.
- [ ] Update the presentation architecture: Regions/application settings -> Policy Tree ->
  effective requirements; bucket statistics -> Metric Evaluator -> observed values;
  the AggregationManager consumes both and decides.
- [x] Keep policy hierarchy independent of data hierarchy.
- [x] Compile inherited effective policies at initialization for reachable cells and
  cross-region parents; share identical bounds/provenance, stop homogeneous subtrees and
  enforce a node budget. Depth-14 single-leaf-region regression requires only 57 nodes.
- [ ] Measure full-tree versus sparse construction, memory and lookup cost.
- [x] Distinguish inherited configured defaults from constraints derived for a candidate
  footprint. Do not propagate a cross-region parent's combined bounds back into unrelated children.
- [x] Apply strict numeric hard bounds: max of lower bounds, min of upper bounds and all
  mandatory metrics. Reject inherited contradictions at startup; mark contradictory
  cross-region candidate footprints infeasible with an explicit check reason.
- [ ] Define/intersect allowed actions when the corresponding decisions are implemented.
- [ ] Define min/max cell side in metres and coarsest allowed depth unambiguously;
  validate metric units, parameters and reference definitions before combining thresholds.
- [ ] Use the adopted preservation-priority labels: Temporal First -> spatial aggregation
  before temporal extension; Spatial First -> temporal aggregation before spatial coarsening.
- [ ] Resolve competing preservation priorities explicitly; preferences never weaken hard bounds.
- [ ] Add an application/stream publication-model choice separate from preservation priority
  and hard bounds. Expose only implemented/tested modes; validate capabilities/combinations.
- [ ] Resolve conflicting inherited model choices or reject them; models are not ordered
  by one numeric strictness rule. Keep model fixed per initial run and preserve release history.
- [x] Handle cells crossing aligned region boundaries by intersecting all affected
  requirements, even over unoccupied portions. Keep finer feasible children usable.
- [ ] Extend beyond non-overlapping rectangular regions; specify nesting/overlap semantics.
- [x] Fix policies during initial runs; retain tree ID/version and per-cell effective ID,
  sources and structural feasibility in v3 internal diagnostics.
- [ ] Specify cache invalidation and open-window behavior before permitting live changes.
- [ ] Add multiple views only after a correct single release pipeline.

**Verification:** all seven CTest suites passed. New core/adapter suites cover inherited
bounds, independent application contexts, valid children under infeasible parents,
unsupported geometry/options, provenance and sparse depth-14 compilation. The core also
builds with standard C++17 and strict warnings. A full run verified five regional windows
and 308 cell assessments; nine startup errors preserved a disposable database sentinel.
Twelve additional uniform/no-policy windows retained existing assessment behavior in v3.
Normal `simulator/build/Simulator` was rebuilt; maintained config and existing data were untouched.

**Acceptance:** candidate lookup cannot silently weaken regional rules; conflicts have
explicit resolution or rejection. Applying this contract to actual spatial merge/release
decisions remains A02/A03/A05 work.

## 7. Stage 4 — Active/preemptive buckets and bounded history

### A02 — Bounded history and active/preemptive windows — P0

**Initial private-history implementation complete, 2026-10-14.**
[AGGREGATION_HISTORY.md](docs/AGGREGATION_HISTORY.md) records storage, API, deadline semantics,
configuration, worked examples and verification. History is opt-in; the maintained config
is unchanged. The regional example enables it. Bucket creation/extension is available via
the manager API. A03 now performs spatial selection and variable-window reconstruction.
Automatic prewarming and the general active/preemptive lifecycle remain open.
The controllers do not open CandidateBucket records: common mode tracks one pending
interval, while cell-local mode owns a sparse frontier of independent cell windows. Both query fine history directly. Parent/grandparent statistics are reconstructed
on demand. [BUCKET_IMPLEMENTATION_STATUS.md](docs/BUCKET_IMPLEMENTATION_STATUS.md) is the
precise implementation/status reference. Decision
and publication status belong to A03/A05, not an arbitrary history progress flag.

- [x] Specify retrospective parent aggregation from internal observations.
- [x] Compare physical active/preemptive containers with logical windows over shared history.
- [x] Define bounded sample retention, logical open windows and cleanup. Bucket deadlines
  fit the fixed retention horizon; expired records are removed before their support expires.
- [x] Integrate bounded common-window publication coordination and synchronous retry retention under A05; automatic restart remains F03.
- [x] Store owned fine time-bin history and reference it from sparse bucket records keyed
  by stream/application, cell/depth, window start and generation. No Agent*/Node* lifetimes.
- [x] Reconstruct complete parent footprints using coverage metadata, including known-empty
  siblings without physical bucket records; missing/unavailable samples never become zeros.
- [ ] Treat future leaf flags as work hints rather than completeness/publication ownership.
- [ ] Separate legal merge extent, reserved unpublished extent and precomputation extent.
  Specify ancestor lookahead levels, finite temporal candidates and cache/memory budgets.
- [x] Implement on-demand reconstruction independently of prepared buckets. An uncached
  representable ancestor remains reconstructable when the interval is retained and closed.
- [ ] Add one/two-level, full and selective preparation as E05 variants with measured budgets.
  Define triggers as failed checks/temporal extension with the original interval, rather
  than every leaf collecting normally; bound ancestor/window work and preserve on-demand fallback.
- [x] Use exact contributor unions across space/time; do not sum unique child counts or
  repeated observations as people. Preserve A01's equal measured-sample weights, including
  measured-empty bins. Continuous-time occupancy integration is not claimed.
- [x] Implement private COLLECTING/CLOSED observation progress, bounded extension, discard
  and deadline expiry. CLOSED does not imply metric readiness, approval or publication.
- [ ] Implement decision/publication states WAITING, READY, SEALED/PENDING_OUTPUT, COMMITTED,
  SUPERSEDED and SUPPRESSED under A03/A05. Keep temporal_exhausted separate.
- [ ] Invalidate competing preemptive candidates after a committed cut; reclaim history
  only after all bounded dependencies are resolved.
- [x] Handle different sibling starts/durations with interval-specific history queries.
  A sibling starting a new bucket does not block a parent over complete private history.
- [x] Transfer only the unpublished prefix needed by a parent; preserve later suffixes,
  minimum-window rules and exactly one publication owner per cell/interval.
- [x] Define three relative ancestor steps as 64 equal base-cell areas, not 64 copied
  buckets; verify mixed-depth geometry and current four-base-node/implicit-root convention.
- [x] Test uncached ancestors, geometry/root limits, evicted/future support and A04 metric
  evaluation of reconstructed candidates. Queries return incomplete coverage explicitly.
- [x] Gate actual release on full coverage, policy bounds and unpublished availability (A05).
- [x] Use bounded chronological bins for the first interval queries and small logical
  records for active/preemptive alternatives. An interval tree is not needed for correctness;
  indexing/caching remains an E05 performance choice with separate ownership semantics.
- [ ] Distinguish closed, decision-ready, externally published and discarded states;
  define already-published-data behavior for retrospective reconstruction.

**Verification:** all eight CTest suites passed, plus strict C++17 compilation without
SFML/MongoDB for the history core. Tests check exact unions, geometry, coverage, sibling
windows, deadlines, budgets and rejection without side effects. A 300-step oracle verifies
1,200 cell/interval queries with at most five retained bins/twenty observations. Actual AGBS
input reconstructs nine contributions/two distinct contributors across three closed windows.
A full history-enabled regional run checked five windows/316 cells; fourteen invalid
policy/history configurations failed before DB clearing or metadata writes. Test DBs removed.

**Acceptance:** no double counting, bounded storage and reconstructable private windows.
Whether that support remains legally unpublished is A05's responsibility. Deleting a DB
record cannot retract an already externally visible publication.

## 8. Stage 5 — AGBS integration and adaptation decisions

### A05 — Publication coordination and irreversible output — P0

**Integrated first model, 2026-10-14.** The simulator now uses the coordinator with
`private_final_snapshot`, separate recipient/private databases and durable idempotency.
See [PUBLICATION_COORDINATION.md](docs/PUBLICATION_COORDINATION.md), the
[implementation contract](docs/ADAPTIVE_PUBLICATION_IMPLEMENTATION.md) and
[verification record](docs/ADAPTIVE_PUBLICATION_VALIDATION.md). The broader A05 research
package remains open for other models and automatic checkpoint/resume.

- [x] Implement a bounded, single-pending private-final-snapshot coordinator for complete
  closed fixed windows, with a whole-grid reservation and monotonic retirement watermark.
- [x] Recheck selected cells with the immutable evaluator at sealing and each delivery;
  reject overlapping cuts, mismatched geometry/stream, incomplete selected support and
  resource-budget overflow. Keep expired/ambiguous output reserved.
- [x] Seal immutable selected-only payloads with stable release IDs; omit suppressed
  statistics, whole-window totals and private debug evidence. Preserve payload/reservation
  on Retry or exception; retire empty/suppressed windows privately.
- [x] Test subtraction, pending/committed ancestor rejection, lost acknowledgement and
  idempotent sink contract, deadline expiry, future merge/split and malformed input.
- [x] Wire this core into the actual sensor -> selector -> publication path using an explicit
  supported policy model and a separate recipient boundary. Add startup validation.
- [x] Implement whole-document MongoDB idempotency, durable prepared/committed journal,
  read-only recovery and reconciliation of already-visible identical writes; retire empty
  cuts privately. Preserve ambiguity and abort on exhausted bounded retries.
- [ ] Implement automatic checkpoint/resume with the full reservation/retirement ledger and
  fresh policy/time evidence (F03). Do not restart the in-memory ledger with the same run ID.

- [ ] Implement publication models as independently testable policy-selected behaviors:
  private final-snapshot, immediate approved, bounded-hold and recipient-visible revisions.
  Start with one supported model; each additional mode needs actual lifecycle/sink semantics,
  visibility/deadline handling and tests. No stub mode or silent substitution.
- [ ] Compare these models under E06/RQ-PUB; the preferred application mode remains open,
  including traffic freshness/latency needs.
- [x] Separate current private observation/GT/diagnostic storage from externally visible releases;
  keep the publication sink outside the manager and enforce the selected access boundary.
- [ ] Permit retrospective changes to private working data with reproducible provenance;
  assess every recipient-visible version when revisions are exposed. Provisional labels
  do not retract disclosure. Consider mutable internal storage plus an explicit release API.
- [ ] Define reservations before any competing child release, and a ledger of reserved,
  committed and retired cell/interval coverage per application stream.
- [ ] Choose a small initial coordination domain and merge-depth cap. Compare holding its
  unpublished cut with early child release that makes historical ancestors unavailable.
- [ ] Require compatible complete temporal support for all sibling cells/descendant footprints.
  Query interval availability instead of waiting unconditionally for childFinished.
- [ ] A sibling's temporal extension alone does not freeze all neighbors. Define which
  publications are held by reservations and which independent releases close merge options.
- [ ] Bound waits by every affected policy; when no legal output can meet privacy and
  mandatory availability together, report infeasibility instead of silently weakening either.
  A passing child can be held for coordination without being described as privacy-failing.
- [x] Publish one non-overlapping selected cut in the common-window model; reject parent/child reuse of the same
  committed or pending-output support. Future adaptation uses a common handover boundary.
- [x] Seal immutable output with a stable release ID; preserve reservations on sink failure.
  Coordinate retry/idempotency and bounded pending output with F03.
- [ ] Settle any A07 descendant fallback before retiring support; suppress only the final
  unreleasable remainder. Whole-candidate suppression remains the initial baseline.
- [ ] Keep internal reasons separate from raw history cleanup. Do not delete visible
  records as a purported privacy repair, or publish totals that reconstruct suppressed parts.

**Acceptance:** demonstrate the additive-count subtraction counterexample, a rejected
merge over a published child, and an allowed future transition. Pending writes cannot
reopen coverage for a competing candidate. Disjoint release coverage is not a privacy proof.

### A03 — Start with simple adaptive strategies — P0

**Spatial and temporal baseline integrated, 2026-10-14.**
[SPATIAL_SELECTION.md](docs/SPATIAL_SELECTION.md) and
[TEMPORAL_AGGREGATION.md](docs/TEMPORAL_AGGREGATION.md) describe actual behavior.
Both preservation priorities now run through A05 using one common unpublished interval.
Regional maxima conservatively cap the common interval. The opt-in cell-local controller
now uses per-footprint clocks, bounded sibling holds, immediate private-prefix takeovers,
future common-boundary handoffs and scoped publication. Comparative effectiveness remains open.

- [x] Select a non-overlapping cut from fine observations; replace whole sibling groups
  with eligible parents using exact retained identity unions and full-footprint policy checks.
- [x] Bound the search by minimum depth and evaluation count; suppress the whole unresolved
  domain at the cap, and reject missing coverage/unavailable required metrics.
- [x] Reassess from fine observations at each future common window boundary, recording
  coarsening/refinement without modifying past diagnostics.
- [x] Test merge/refine/merge, unions, sibling replacement, unknown/missing evidence,
  footprint policies, bounded work, transport and configuration; verify an actual 75-window run.

**Release and temporal implementation, followed by remaining extensions:**

- [x] Integrate fixed candidate release/suppress with the initial regional policy tree.
- [x] Implement Temporal First by trying spatial aggregation before temporal extension,
  and Spatial First by trying temporal aggregation before spatial coarsening. Start with
  both verified strategies; comparative experiments remain under E06/RQ-ORDER.
- [x] Test label-to-action mapping with a failing candidate for which both actions are legal;
  record the preservation priority and chosen action in experiment/decision metadata.
- [x] Extend in declared bin increments and recheck on relevant events; permit early
  eligible release. Always waiting for the maximum window is a separate baseline.
- [x] Define sibling/parent/child checks, merge, split and suppression using scoped A05 reservations.
- [x] Evaluate one complete parent at a time and expand to its siblings only when the
  next ancestor is needed and allowed. Avoid an automatic cascade to the depth cap.
- [x] Recompute effective regional policy and all mandatory metrics for every candidate.
  More aggregation is not assumed to improve every metric monotonically.
- [x] Allow early completion only after hard minimum/maximum bounds and release
  coordination pass. Temporal exhaustion permits only remaining legal actions.
- [x] Bound retries/search; wait for new evidence or a deadline rather than polling
  unchanged candidates. Preserve original start time through every merge.
- [x] Apply changes to an already published spatial selection at future common boundaries.
  Distinguish those transitions from A07 selecting unpublished descendants as final fallback;
  prevent split/merge oscillation within one unresolved window.
- [x] Handle impossible constraint combinations explicitly in candidate checks; suppress unreleasable support without treating suppression as availability fulfilment.
- [x] Compare against B01 baselines in the October 19 frozen nine-configuration study;
  report retention, coverage and conditional error rather than a universal winner.

**Cell-local implementation, 2026-10-19:**

- [x] Add actual per-cell original starts, next checks and absolute policy deadlines.
- [x] Keep a sparse complete ownership frontier; accept mixed-depth descendant takeovers.
- [x] Reserve exact unpublished space-time support; retain immutable sink retries.
- [x] Reject historical parents overlapping retired/public support; coordinate future boundaries.
- [x] Preserve private prefixes/suffixes, known-empty coverage and source contribution accounting.
- [x] Give scoped releases collision-free IDs, durable journal/recovery and bounded spatial retirement.
- [x] Integrate the new controller into Simulation and AggregationReplay behind explicit configuration.
- [x] Extend independent raw-data compliance auditing to local space-time retirement.
- [x] Verify 27 CTest suites / 134 Python methods, 14 coordination cases, 120 seeded stress
  cases and fresh ASan/UBSan checks. Complete a real 120-s headless run with independent
  auditing of 160415 terminal domains, exact conservation and 302 durable releases.
- [ ] **P1 — Next performance step:** reduce no-output `coordination_handoff` decision churn
  and offer bounded/summary diagnostics without changing recipient output. The verified
  120-s run produced 312.5 MiB of private diagnostics; disabling no-output Mongo checkpoints
  improved execution but does not solve algorithmic/diagnostic volume. Keep durable public
  publication and default legacy journal behavior unchanged.
- [x] Run the paired common/local regional-policy effectiveness study on frozen inputs:
  six analytical cases + 24 independent realizations, nine configurations, 270 audited
  replays and 120 exact repeats. Record all references, two query scales, regional
  retention, exact contribution age and matched-query MAE.
- [x] Add regressions for illegal-parent holds and the early-publication barrier (parent
  14 versus descendant 56); plan competing nearest rescues before output and restrict
  holds to feasible common-start ancestor opportunities. Seven focused cases plus
  240 stress cases, fresh ASan/UBSan and same-input 30-case comparison pass.
- [x] **P0 — Handoff correction, completed 2026-10-19:** repair the proven
  future-handoff conflict with endpoint-consistent planning, redundant-plan reconciliation
  and atomic supersession of compatible private plans. Preserve immutable publication,
  deadlines, unrelated plans, budgets and retry/rollback guarantees. Add the exact passing
  parent witness and nested/sink-failure regressions; this is A03/A05, not A07.
  Six new functions pass; the previous core fails five. The 42-observation automatic
  witness retains 33 instead of zero. All 27 focused cases/240 sanitizer stress cases,
  37 suites/236 Python methods and original 30-case comparison pass.
- [ ] Distinguish passing-owner holds from private measured-empty ownership retention.
  Test a certified-empty alignment contract before changing retirement semantics; never
  reopen published, unavailable or terminal nonempty support. Current empty compaction
  does not resolve an extending nonempty sibling beside an advanced empty owner.
- [ ] Compare bounded holds with earliest eligible release under application deadlines.
  Keep matched-point age, retention and empirical privacy separate; do not interpret
  the current heuristic as a globally optimal scheduler.
- [ ] Extend whole-domain feasibility enumeration to a justified asynchronous reference class.
- [ ] Add a persistent live-renderer mosaic of latest decisions from every local
  domain. This remains separate from the HTML replay's asynchronous historical view.
- [ ] Implement E05 precomputed statistic caches separately from ownership/coordination holds.

See [CELL_LOCAL_COORDINATION.md](docs/CELL_LOCAL_COORDINATION.md) for exact semantics and
[COORDINATION_TEST_REPORT_2026-10-19.md](docs/COORDINATION_TEST_REPORT_2026-10-19.md) for verification.

**Acceptance:** decisions are explainable and spatial/temporal releases agree. Measure a
better privacy/utility trade-off rather than assuming it.

### A07 — Selective suppression after permitted adaptation is exhausted — P1

**Initial common-window slice implemented and verified, 2026-10-21.**
The optional `spatial_selection.preserve_valid_descendants` flag defaults false,
retaining the original baseline. See the [acceptance contract](docs/SELECTIVE_DESCENDANT_RESCUE.md)
and [test report](docs/SELECTIVE_DESCENDANT_RESCUE_TEST_REPORT_2026-10-21.md).

- [x] Preserve remaining temporal options and the original start/deadline; a partial
  proposal remains private until the existing terminal condition.
- [x] Preserve valid whole descendants over the same unpublished common interval;
  recheck effective policy, metric inputs, completeness, geometry and publication age.
- [x] Keep a legal higher-parent rescue available. If it fails, publish selected descendants
  only; retain failed parent assessments privately and suppress the remaining branches.
  Do not remove observations from a parent while retaining its full-area semantics.
- [x] Keep the disjoint private cut complete for contribution accounting. Exact distinct
  support remains an identity union; no parent/global total accompanies suppressed parts.
- [x] Specify deterministic finer-cut preference when all children pass, whole-parent
  rescue when needed and legal, and partial fallback only when that parent fails.
- [x] Verify 9-input/6-retained and regional 21-input/18-retained examples, passing internal
  descendants, uniform support impossibility, missing/unavailable/expired evidence,
  budget/history rollback, temporal opportunity, sink retries and publication barriers.
- [x] Keep cell-local planning unchanged; it already preserves passing leaf owners in
  the reference cases. Reject enabling this common-window-only flag for cell-local use.
- [ ] Evaluate broader query utility, class/region selection bias and disclosure through
  the visible suppression/geometry pattern. More retained data is not a privacy guarantee.
- [ ] Add metric-specific pruning only if justified later; no computation optimization now.
- [ ] Generalize asynchronous coarse-owner fallback only after demonstrating a separate
  reachable gap, with original coordination scope and atomic complete-scope retirement.

**Gate:** the common-window slice is verified. Review its behavior and metric adequacy
before starting semantic generalization, road-user/type suppression or a utility scheduler.
Do not interpret tiny fixed-interval oracle agreement as globally optimal online scheduling.

### A08 — Semantic resolution under regional constraints — P1

**First common-window slice implemented and verified, 2026-10-21.**
[Model/formulas](docs/SEMANTIC_ADAPTATION.md),
[test report](docs/SEMANTIC_ADAPTATION_TEST_REPORT_2026-10-21.md).

- [x] Add an immutable versioned release hierarchy with explicit raw-label aliases;
  preserve existing behavior profiles and default scalar output.
- [x] Reconstruct exact per-node identity support privately, including moving/repeated
  road users; reject unknown/conflicting terminal classifications within queried windows.
- [x] Register `min_category_distinct_contributors`, `semantic_max_loss` and
  `semantic_mean_loss`; enforce strict regional support/loss bounds with every scalar gate.
- [x] Select a complete truthful category antichain within each spatial/time candidate;
  semantic failure continues through existing TF/SF/A07 without resetting time.
- [x] Independently reassess approved bins at publication; remove private node/type counts.
  Persist/recover the exact versioned product, including lost acknowledgement handling.
- [x] Add exact/unknown class-query semantics, five frozen examples, independent raw-data
  and exhaustive antichain checks, sanitizer and disabled-mode compatibility evidence.
- [x] Review class-specific query utility and early semantic generalization in a bounded
  independent candidate study (360 cases, same actual intervals, fixed receiver bank).
- [x] Adopt **Semantic First = preserve semantic accuracy**, matching Temporal First and
  Spatial First. Rename current processing-order descriptions to early semantic generalization.
- [x] Implement first Semantic First mode: TF secondary, zero-cost preference until terminal,
  ascending maximum-loss ceilings at terminal, original hard bounds, private diagnostics.
- [x] Specify partial fallback: highest retained observation count, then lowest actual maximum
  loss, then finer weighted cell size and canonical IDs. Mean remains a hard constraint/report.
- [x] Verify source accounting, unavailable coverage, EOF, budgets/rollback, original-policy
  publication/recovery, legacy compatibility and the max-versus-mean counterexample.
- [x] Add and verify Semantic First + Spatial First, then semantic cell-local
  coordination under their separate acceptance contracts and reports.
- [ ] Review trade-offs before mean-loss optimization, predictive waiting or regional
  strategy overrides. These extensions remain unimplemented.
- [ ] Define application preferences before adding a joint utility scheduler or
  per-category release priorities; fixed-interval nondominance is not online optimality.
- [x] Implement semantic cell-local coordination after the separate
  [scope/acceptance review](docs/SEMANTIC_CELL_LOCAL_CONTRACT_2026-10-22.md);
  the [test report](docs/SEMANTIC_CELL_LOCAL_TEST_REPORT_2026-10-22.md) records the
  completed gate. The historical common-only rejection no longer describes current code.
- [ ] Study individual contribution/type suppression and complementary suppression as
  separate actions. Do not falsify labels or silently discard a rare semantic remainder.
- [ ] Expand to independent age/mode/vehicle classification dimensions only when justified;
  the current rooted release taxonomy does not complete behavioral taxonomy redesign X01.

**Gate:** 47 CTest entries pass; Python reports 312 methods: 300 passed and 12 optional
skips. All 15 new semantic methods execute and pass. This verifies the tested bounded
cases and measured representation/support values, not a general privacy-risk reduction.

### A06 — Aggregation inspection and live state overlay — P1, after S04

**Live progress slice implemented and verified:** expose dated running-window progress
separately from the latest completed selection; independently toggle sensor grid (H),
output (G), and progress (P). Existing metric checks are reused without additional per-frame
history queries. Fourteen CTest suites and native-window layer checks passed. See
[LIVE_AGGREGATION_PROGRESS.md](docs/LIVE_AGGREGATION_PROGRESS.md).


**Offline inspection slice implemented, 2026-10-14.** Brought forward for the supervisor
demo; A05 and temporal A03 are now integrated in separate opt-in examples. The [inspector guide](docs/AGGREGATION_INSPECTOR.md)
documents the prepared recording, reproduction, local MongoDB debug copy and limitations.

- [x] Show recorded candidate geometry, metric values, regional thresholds and policy
  provenance in a self-contained HTML inspector with cell selection and timeline playback.
- [x] Distinguish violated, met and unavailable assessments, including a failed coverage
  gate; do not reuse a selected cell's old values when no candidate is present.
- [x] Support an explicit export of existing diagnostics into a dedicated `UMP_Debug...`
  MongoDB collection, without additional database writes in the simulation loop.
- [x] Prepare and inspect a real 30-window recording; verify regional bounds and database
  totals, builder fidelity/safety checks, and Safari interaction. This is recorded replay,
  not live adaptive behavior or empirical privacy/utility evidence.

- [x] Show collecting/extending state, next check, hard deadline and explicitly dated last
  check independently from completed releases; clear prior checks at a new window.
- [x] Separate H fine sensor grid, G completed output, P active checks and S sensor areas;
  label pending failed/unavailable checks with dashed amber, never final suppression.
- [x] Verify immutable typed progress transport, pause/measurement times, sensor isolation,
  release labels and native independent toggles. Keep the renderer free of policy decisions.

**Live spatial slice implemented, 2026-10-14:**

- [x] Attach an immutable, dated spatial-selection snapshot separately from instantaneous
  cell counts. Preserve sensor identity routing and bounded transport; add regression checks.
- [x] Show chosen/suppressed footprints, depth/support and closed-window times over the
  sensor grid, with G to toggle and distinct coarsening/refinement colors. Verify native UI.
- [x] Extend the offline inspector with same-window finest/selected comparison, actual
  transition navigation and triggering child checks. Keep raw diagnostics separate.

**Remaining live integration:**
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
- [x] Validate one complete 8-second controlled run against GT for all 200 agents and AGBS:
  79 sensor timestamps, 15800 observations, all cell/type counts and geometry matched.
- [ ] Extend complete-run validation to ABS/GBS and additional scenarios; one AGBS run does
  not validate every sensor, configuration or movement regime.

**Existing result:** agent C0B64FE1-740C-486C-A2D1-00E030269E71: GT 200 records, ABS 199,
100 sensor timestamps; no missing GT joins or position differences; 99 duplicate keys;
first velocity halved; the next 99 estimates match displacement over 100-ms intervals.

**Correction verification, 2026-10-12:** known synthetic observations in an isolated MongoDB
database pass startup, interval velocity, unique keys, entry/reentry, counts and empty-area
cadence checks. This is direct sensor-pipeline validation, not a complete simulator run.

**Acceptance:** documented before/after identity, position, timestamp, duplicate and interval
velocity comparisons. Keep reference data unchanged. One checked agent does not validate all runs.

### V02 — Multi-minute endurance and numerical-step compatibility — P0/P1

- [x] Run actual aggregation-enabled headless simulation for 6,000 steps at 50 ms (300 s)
  and 100 ms (600 s), preserving a 10-Hz sensor and isolated owned databases.
- [x] Verify GT/sensor cell-time/type/geometry equality, no duplicate keys, complete coverage,
  selected-policy/public-payload agreement, contribution totals and final journal retirement.
- [x] Record population over time, whole-run walltime and maximum RSS; disclose that both
  live scenes become empty around 110–114 s and do not prove sustained dense load.
- [x] Independently audit a 600-s frozen persistent 32-road-user analytical workload through
  both priorities: all 191,968 contributions accounted for/released and final end preserved.
- [x] Confirm 200-ms simulation steps with a 10-Hz sensor fail preflight before DB writes.
- [x] Archive configurations, hashes, logs, recovered audit-tool issues and cleanup evidence in
  [LONG_RUN_REPORT_2026-10-19.md](docs/LONG_RUN_REPORT_2026-10-19.md).
- [ ] Reuse and correct STATS telemetry with explicit scopes: actual completed simulated
  duration, main-loop versus full-process wall time, flush inclusion, early-stop/unbounded
  behavior, simulation throughput versus renderer FPS, and real queue-wait measurement.
- [ ] Report actual logical-record counts separately from leaf accumulators, history bins
  and queried parent attempts; string-payload limits are not a total process-memory budget.
- [ ] Instrument individual stage/step p50/p95/p99/max, queue/backpressure, history occupancy
  and diagnostic/DB I/O before claiming end-to-end realtime or a measured memory plateau.
- [ ] Perform a short visible renderer/demo rehearsal; headless endurance excludes GUI pacing.
- [ ] For numerical accuracy, define controlled initial states/noise and a fine-step reference;
  current independent stochastic live runs cannot establish convergence or timestep effects.

### B01 — Compare fixed space/time baselines — P0

- [x] Compare 10-m/20-m cells crossed with 400-ms/1000-ms windows, plus three adaptive modes.
- [x] Use identical frozen observations, detection area, policies and 10-m/1-s application query.
- [x] Process counts/windows through the same D03 aggregation/publication cores.
- [x] Export conditional utility error, coverage, simulated sealing age, contribution retention,
  processing time and a labelled known-background distinguishability diagnostic.
- [ ] Add realistic empirical attacks, a wider parameter sweep and independent replications.

**Acceptance:** reproducible table/figure with configuration and explicit limits. A complete
policy tree or real city map is not required for this first comparison.

### E07 — Policy constraints and mechanism effectiveness — P1 design, then evaluation

**First bounded common-window study completed, 2026-10-21:**
[protocol](docs/SEMANTIC_PRIORITY_PROTOCOL_2026-10-21.md),
[results](docs/SEMANTIC_PRIORITY_STUDY_2026-10-21.md),
[test report](docs/SEMANTIC_PRIORITY_TEST_REPORT_2026-10-21.md).
360 configurations, 1,929 legal actual-interval cuts, 12 identical repeats;
50 CTest entries pass (345 Python passes, 12 optional skips). No controller change.
This completes the initial bounded review; the broader tasks below remain open.

- [x] Freeze five paired deterministic scenarios, class-count query bank and protocol.
- [x] Sweep category support/semantic loss/spatial bound/duration-age cap in this scope.
- [x] Enumerate legal same-interval candidates and expose nondominated query/detail choices.
- [x] Separate receiver missing/unknown/known-zero values and logical deadline cohorts.
- [x] Isolate density at fixed 2:1:1 class ratio and static identities in 18 real replays.
  Verify the fine-space/coarse-semantics transition and that repeated sampling alone
  adds no distinct support. Hard loss-zero is not a Semantic First mode.

- [ ] Predeclare input replays, query workload, action/candidate class and policy versions.
- [ ] Sweep support minima, spatial/temporal/age bounds and semantic loss separately,
  then predeclared combinations; hold all unrelated settings and source data fixed.
- [ ] Record binding/conflicting requirements, unavailable evidence and invalid inputs.
- [ ] Quantify feasible-case fraction under a justified reference, compliance, retention,
  timely query coverage/error, spatial/temporal/semantic detail and release age.
- [ ] Separate policy-imposed infeasibility from bounded-reference search/coordination gaps.
  Do not treat all-suppression as useful fulfillment or automatically relax constraints.
- [ ] Evaluate the quantitative privacy gain separately on those fixed mechanism/policy
  versions; support proxies and representation loss remain explicit first-stage metrics.

**Scope:** mechanism effectiveness under constraints, not current computational optimization.
The broad sensitivity study is not yet run. The bounded completed study couples age
and duration maxima; vary them independently in the broader experiment. Fixed-interval
feasibility is not global schedule feasibility, and no actual privacy gain is inferred.

### R01 — Generate or reuse a reproducible measurement stream — P0

- [ ] Inventory random sources: spawning, targets, velocity, noise and identities.
- [ ] Evaluate one configurable seed and stable scientific identities.
- [x] Feed identical saved observations to all compared aggregation variants with AggregationReplay.
- [x] Record input/config/binary/source hashes, parameters, time basis, run identity and commands.
- [x] Verify repeated replay equality after excluding the explicitly measured runtime field.

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
- [x] Implement offline saved-observation processing without database or GUI runtime access.
  The existing CMake project still discovers its normal build dependencies.

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
- [ ] Include cache misses beyond the configured preparation depth and distinguish
  base-cell coverage, cached ancestor count and exact metric-maintenance cost.
- [ ] Compare several permitted merge extents and independent versus coordinated
  releases as separate policy experiments, not unnoticed cache-comparison changes.
- [ ] Review materialized-view selection and streaming aggregation literature before claiming
  novelty; document the mobility/policy/deadline-specific question and measured crossover.

**Acceptance:** equivalent scientific outputs for the unconstrained execution comparison,
reproducible cost/memory curves and a stated workload range where each strategy wins or loses.
No assumed winner; this study does not block the first aggregation demo.

### E06 — Dissertation study: publication models and preservation priorities — P1

- [ ] RQ-PUB: measure privacy, application utility, coverage and freshness across private
  final-snapshot, immediate approved, bounded-hold and recipient-visible revision models.
- [ ] RQ-ORDER: compare Temporal First (spatial aggregation first) with Spatial First
  (temporal aggregation first); the label names the dimension being preserved.
- [ ] RQ-BOUNDS: vary regional duration, release-age and spatial bounds; examine sibling
  coordination, infeasible requirements and partial suppression across density scenarios.
- [ ] Implement and validate each selected model/strategy through A03/A04/A05 before evaluating
  it. Verify that policy selection changes execution, not merely an output label.
- [ ] Specify each observer's access: final approved snapshot versus all visible versions,
  timing and geometry. Include combined application views when the threat model permits it.
- [ ] Hold saved observations, query and comparable hard constraints constant; vary one axis
  first, then selected model-by-priority interactions. Keep E05's cache comparison separate.
- [ ] Report attack outcomes, application error, released coverage, spatial/temporal detail,
  latency distribution, infeasibility and compute/memory cost, with explicit limitations.

**October 19 measured subset:** the immutable private-final-snapshot common/local
comparison is implemented and executed, with both preservation priorities and four fixed
references. Results do not complete the other publication-model or privacy comparisons.

- [x] Add exact retained-observation ages, batching-invariant public timing, fixed regional
  diagnostics, primary/fine fixed queries, paired support and independent-realization summaries.
- [x] Preserve a verified post-study publication-overlap witness without claiming total regret.
- [ ] Instrument otherwise-valid candidates rejected solely by actual public overlap; distinguish
  private retirement, policy, budget, coverage and history failures. Deduplicate candidates.
- [ ] Define a bounded asynchronous counterfactual for publication opportunity loss. Compare the
  best feasible schedule with versus without a commit under the same prior public prefix,
  policies, data, deadlines, resource limits and utility objective. Do not add overlapping
  parent/ancestor potential or interpret hindsight optimum as an online guarantee.
- [ ] Repeat this frozen baseline after a targeted controller change; require no regression in
  compliance, conservation or deterministic ownership and explain every utility trade-off.

**Acceptance:** reproducible model/strategy comparisons with verified implementations,
explicit observer assumptions and the adopted terminology in every figure/configuration.
The research questions are recorded; results, a preferred model and novelty remain open.

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

### S01 — SharedBuffer shutdown and consumption — transport correction implemented

- [x] Include end/stop and both queues in data availability and wake conditions.
- [x] Verify empty-queue shutdown, final write-queue drain and blocked-writer cancellation.
- [x] Bound renderer queues (default 128 frames each); apply backpressure without dropping.
- [x] Skip render queues in headless runs; separate simulation progress from queue counters.
- [x] Document aligned mixed-rate production and consumptive, non-broadcast reads.
- [ ] Measure complete-run performance and manually exercise early window close/pause.

**Verification:** FrameRegressionTests covers concurrent FIFO order, capacity and reader/
writer wake-up. A full executable headless smoke check covers 20 steps and four sensors.
The wider simulation memory issues remain S02/S03. Aggregation stays in the simulation
thread and receives values directly; no additional shared-buffer consumer is introduced.

### S04 — Complete sensor frames and chronological matching — implemented

**Baseline:** the imported renderer retained consumed local frames, reused stale data,
read the queue before local matching and processed only the first sensor ID. Aggregation_Manager
had the same code; SimulatorV3 did not have an active sensor-frame matching path.

- [x] Assemble one immutable timestamped sensor-ID map per rendered step with actual measurements.
- [x] Carry distinct ABS/GBS/AGBS payloads; non-due sensors contribute nothing.
- [x] Preserve IDs for due empty measurements; allocate/send no frame when no sensor sampled.
- [x] Finish sensor work and enqueue any measurement frame before exposing the agent snapshot;
  agent-frame arrival confirms completion, so no empty completion frame or sensor wait is needed.
- [x] Consume exact matches once, discard older frames and retain at most one future frame.
- [x] Clear the exact-step measurement view on an unmatched new step; preserve pause/redraw.
- [x] Fix grid flicker: retain separate latest-measurement geometry per AGBS between
  samples, display its original sample age and clear subdivisions on a measured-empty sample.
- [x] Rebuild display geometry only when the measured cell-ID set changes; initialize
  with base cells and a waiting label, without inventing a t=0 sample.
- [x] Reject duplicate/out-of-order stream timestamps and mismatched/duplicate builder contributions.
- [x] Assign run-stable sensor IDs once and route each AGBS to its own typed payload.
- [x] Use nonblocking renderer reads; cancel both queues on close and drain on normal end.
- [x] Test old/exact/future/end cases, several IDs, mixed 10/5-Hz sensors and measured-empty input.
- [x] Test bounded two-queue runs with long measurement gaps or no measurements at all;
  distinguish no frame from measured empty, including a no-sample tail before EOF.
- [ ] Perform a manual visual check of two AGBS, pause/resume and early close before the live demo.

**Contract and evidence:** [Sensor frames](docs/SENSOR_FRAMES.md). Frame and isolated MongoDB
regressions pass. User observation exposed flicker from clearing geometry at 20 Hz while
the sensor measures at 10 Hz. Geometry now persists with its sample time, independently of
exact-step data matching. Tests cover mixed IDs, empty captures, startup and real quadtree
cell bounds. ABS/GBS heatmaps and policy-driven aggregation visualization remain separate.
The native UI tool could not bind the standalone Simulator executable for visual inspection;
the manual visual/interaction check above therefore remains open.

### S05 — Audit renderer frame-rate and playback control — initial correction implemented

Requested and implemented 2026-10-13. [RENDERER_TIMING.md](docs/RENDERER_TIMING.md) records
the defect, pacing contract, Quadtree/QuadtreeSnapshot roles and verification. Remaining
interaction/load validation is P1 before live-demo or performance claims. S04 frame matching
and X10's broader settings redesign remain separate.

- [x] Separate simulation step/sensor sampling, consumed agent FPS, redraws and requested/
  measured speed; retain the request under producer/render overload.
- [x] Remove the producer-runtime feedback channel, including its backpressure feedback.
- [x] Introduce one monotonic consumption scheduler; include rendering cost and producer
  gaps, avoid catch-up bursts after overload/resume, and preserve every queued observation.
- [x] Validate playback settings before database initialization; prevent nonpositive keyboard
  speed settings. Retain event handling during short waits and redraw only on data/interaction.
- [x] Replace arithmetic mean FPS with frames/elapsed intervals. Report active/paused wall
  time separately and derive displayed simulation time from received timestamps.
- [x] Test exact cadence, pause/resume, speed changes, slow producers/rendering and gaps with
  a controlled clock. Replay identical frames through capacity-two queues at 0.5x/1x/2x.
- [x] Run full windowed simulations at all three rates with 30 agents and capacity-two
  queues: all 40 frames consumed, measured 9.970/19.900/39.010 FPS, requested speeds unchanged.
  Reject zero/negative/NaN startup settings; remove only the UUID test databases.
- [ ] Manually verify keyboard/button controls, pause/resume, panning, very slow playback,
  visible FPS labels, empty scenes and early close; automated clock/queue tests are not UI tests.
- [ ] Profile representative long runs: producer compute versus queue/DB wait, rendering
  cost, jitter distribution and achieved speed at different agent counts/depths. Use saved
  input for comparisons; R02's wall-clock-dependent movement otherwise confounds results.

**Acceptance for the implemented slice:** with 50-ms steps and sufficient throughput,
0.5x/1x/2x target 10/20/40 consumed agent FPS. Real-clock bounded replay is no faster than
target and within 10% + 5 ms of expected first-to-last duration; exact fake-clock cases
verify logic separately. Every frame remains ordered and the requested speed is unchanged.
Long-run performance and native UI acceptance remain open rather than inferred from this test.

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

### F04 — MongoDB driver lifetime — corrected during renderer validation

- [x] Declare mongocxx::instance before the client so reverse member destruction destroys
  sensors, collections and the final client before shutting down the driver.
- [x] Verify normal full-executable completion both with a window and headless using only
  disposable UUID-named databases.

**Finding:** a windowed regression attempt aborted in the MongoDB C driver's handshake
mutex. Simulation declared client before instance, causing the instance to die first.
This violated the lifetime requirement documented in the installed instance.hpp. After
reordering, isolated windowed and headless runs both exited 0 without stderr. This fixes
object lifetime; it does not establish recovery from network or partial-write failures.

### F03 — Persistence failure recovery — P1 when required

- [ ] Design/test retry ownership and idempotent writes for failed or partially successful batches.
- [ ] Decide whether a new capture may replace an unsent batch or requires a bounded queue.
- [ ] Audit arbitrary allocation failure after external acknowledgement: the current common
  controller calls `selector.commit()` after its sink returns, and that method allocates
  a vector. A07 sink-retry tests do not establish process-wide allocation-failure recovery.
  Keep this pre-existing F03 limit explicit; no such recovery claim is made.

**Current limit:** legacy sensor persistence still has no general durable batch recovery.
The separate A05 release sink now implements whole-document idempotency, private intent/
commit journaling and bounded retries. Read-only recovery can reconcile existing output;
automatic simulator checkpoint/resume and restoration of pending policy evidence remain open.

## 11. Later simulator improvements — lower priority

These items start after the aggregation/metric/policy foundation and first evaluation.
Order below reflects dependencies, not a commitment to implement them before October 25.
Brainstorm and define acceptance criteria before selecting libraries or algorithms.

### X01 — Flexible taxonomy: brainstorm and redesign — P2

- [x] Add a separate versioned release hierarchy and explicit source-label mapping under
  A08. This does not change behavior-profile composition or complete the tasks below.
- [ ] Identify what makes new agent types and combinations difficult in the current YAML.
- [ ] Discuss separating identity/classification, age, transport mode, accessories,
  appearance, behavior and distributions; compare composition, defaults and inheritance.
- [ ] Define stable type IDs and how combined attributes feed sensors, metrics and policies.
- [ ] Preserve existing scenarios through a documented configuration migration.

**Acceptance:** adding an agreed new class/attribute does not require editing unrelated
renderer, movement and metric code. Choose the model after the brainstorming session.

### X10 — Simplify the real-time renderer settings — P2

- [ ] If needed later, expose separate past/future trajectory toggles (currently T toggles
  both); keep this below aggregation and evaluation work.

Frame pacing correctness is tracked separately in S05 and may be brought forward.

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
- [ ] Preserve canonical source geometry, stable IDs and provenance; derive spatial
  discretization and policy lookup without making maximum-depth cells the source map.
- [ ] Keep geometric features, functional labels, movement connectivity and policy
  requirements distinct while referencing shared environment IDs.
- [ ] Model entrance/exit portals separately from positive-area entrance policy zones.
- [ ] Specify geometry-to-grid intersection/approximation rules and validate narrow
  features instead of silently using center/majority labels.
- [ ] Build connectivity and traversability rules for the relevant agent categories.
- [ ] Define reusable environment components and inspect UAM-Simulator-Modern as a reference.

**Acceptance:** one small map produces valid geometry and a connected routing model;
rendered appearance and movement constraints refer to the same environment.

### X03 — Routes and trajectories: A*, D* Lite and replanning — P2

- [ ] Discuss destination selection and demand distributions before increasing route complexity.
- [ ] Define shop-visit choice, entry/exit schedules and dwell/re-entry behavior when a
  study needs them; keep persistent road-user IDs and explicit sensor visibility.
- [ ] Distinguish configured demand intensity, realized crossing flow and occupancy;
  keep departures consistent with visits/dwell and any initial indoor population.
- [ ] Use explicit paths and schedules in the first controlled fixture before adding
  general stochastic demand, routing or local planning algorithms.
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

Data prerequisites and future sensitive-attribute design are recorded in
[RESEARCH_QUESTIONS_AND_EXPERIMENTS.md](docs/RESEARCH_QUESTIONS_AND_EXPERIMENTS.md).
The first synthetic membership attack is implemented. Sensitive-attribute and formal-metric
extensions still require separate contracts; see the October 19 implementation/test report.

- [x] Separate additional attributes, background/reference distributions and independent
  experimental realizations; more sensor rows alone do not satisfy those requirements.
- [ ] Specify each proposed secret, protected unit, public representation, attribute time scope,
  equivalence/group model and attacker knowledge before implementing a privacy metric.
- [ ] Specify synthetic attribute assignment and independent/correlated/skewed controls;
  keep latent labels private and separate from sensor-visible information.

- [ ] Evaluate k/l/t/delta/entropy metrics for actual data and attack scenarios.
- [x] Document candidate QI/SA roles and why road-user classes are not automatically
  sensitive; see [the attribute contract](docs/PRIVACY_ATTRIBUTE_AND_ONLINE_CONTRACT.md).
- [ ] Select an actual sensitive secret, semantic label and observer before implementing
  the next attribute-inference game; the documented role table is not generated ground truth.
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
- [x] **X09 — GitHub remote:** publish the audited committed project and history to
  `https://github.com/demuma/UMP-Simulator`; track `origin/main`, exclude private results
  and build artifacts, preserve existing local worktree changes.
- [ ] **X09 — Packaging (P2):** decide license and distributable asset/data selection separately.

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

### Demo refinement and terminology — completed 2026-10-14

- [x] Use finest depth 6 in the separate 80 m demo (1.25 m leaves), show road-user buffers
  initially and set the northeast duration limit to 400 ms, compatible with its fixed window.
- [x] Use distinct road users, road-user observations and mean road-user occupancy in
  visible inspector labels; retain existing serialized keys for compatibility.
- [x] Verify 75 depth-6 windows, mixed selected depths 1..6 and both coarsening/refinement;
  refresh the offline inspector and inspect the live renderer with buffers enabled.

## 14. Working process

Follow the chronological queue in Section 2 and the dates in Section 3. Keep task IDs
stable and mark completion only with evidence. Before coding, state the contract and
small scope; afterwards record behavior, verification and limitations. Update the active
stage when its acceptance criteria are met. Preserve user changes and current sensor
modularity. All repository documentation remains in English.


## Implementation record — integrated A05 and temporal A03, 2026-10-14

- Shared history now reconstructs finest occupied cuts and exact whole-domain identity
  unions for arbitrary half-open intervals. The manager supplies per-tick/final progress;
  fixed-window raw diagnostics remain independent.
- Policy execution selects the supported publication model and preservation strategy.
  Strict preflight covers temporal alignment, resource bounds, sensor geometry and all
  raw/recipient/journal destinations before database initialization.
- MongoDB publishes one immutable selected-only document per release. Private intent and
  commit records support bounded retries and read-only recovery. Per-type counts are
  withheld because no separate disclosure policy currently assesses them.
- Temporal First attempts spatial aggregation before time extension. Spatial First attempts
  time extension before spatial fallback. Original starts, regional caps, exact unions,
  final flush and common future handover are tested.
- Thirteen CTest suites and six inspector tests passed. Three four-second headless runs
  verified public output against diagnostics, conservation of 7,800 observation contributions
  per run and disjoint intervals; invalid geometry/empty diagnostic settings caused no DB writes.
- The main config, workspace file and pre-existing ABS edit were preserved. Dedicated
  `publication` and `temporal-aggregation` examples provide opt-in demonstrations.
- Next: bind the threat model and meaningful privacy/utility metrics, then compare fixed
  baselines and both strategies on identical input. Automatic restart, independent sibling
  windows, A07 selective rescue, other publication models and proactive caches remain open.

## Implementation record — controlled evaluation, 2026-10-14

- Added the offline AggregationReplay CLI using actual aggregation/policy/publication cores.
- Added deterministic fixtures, private verified GT/AGBS capture, seven-mode orchestration,
  provenance hashes, public-only occupancy reconstruction and known-background neighbour checks.
- Ran heterogeneous, analytical-handover and verified-simulator pilots. Results and limits:
  [EVALUATION_RESULTS_2026-10-14.md](docs/EVALUATION_RESULTS_2026-10-14.md).
- Captured 15800 observations from one real eight-second simulator run; all cell/time counts,
  type counts and geometry matched GT. Only the fresh owned capture database was removed.
- Added an exportable result figure, summary CSV/JSON and 44 Python tests plus replay-core
  regressions; all 19 CTest suites passed.
- No online GT metric oracle or general privacy guarantee was introduced. Remaining priority:
  application missing-support semantics and independent utility/policy scenario sweeps.
  The subsequently received user preference defers privacy evaluation until after this milestone.

## Scope decision — utility and policy fulfilment first, 2026-10-14

- The user selected utility and policy fulfilment as the current evaluation focus. E02 is
  deferred; support thresholds remain operational policy requirements, not measured privacy.
- Active result tables and reproduction commands now cover utility/policy evaluation only.
  Existing optional privacy code and historical pilot artifacts are retained.
- The comparison CLI already defaults to zero privacy targets; its manifest now explicitly
  records `privacy_scope: null` and `privacy_target_count: 0` when no privacy test runs.

## Terminology clarification — cell windows and region constraints, 2026-10-19

Aggregation remains bound to data cells and half-open intervals. Regions can intersect
cells without matching them one-to-one and supply the intersected requirements. They do
not become bucket owners or publication clocks. History reconstruction already supports
cell-local intervals; independently scheduled cells/merge groups still need controller,
reservation and retirement work beyond the current whole-grid common-window model.
The canonical reference and generated LaTeX are linked in README; runtime APIs are unchanged.

## Environment and movement priorities — brainstorm, 2026-10-19

The source environment determines physical geometry and connectivity; the quadtree/grid is
a derived spatial representation for lookup/aggregation. Functional regions induce policy
constraints on cell/time candidates. Portals and demand/activity processes determine where
road users start, visit, dwell and leave. Their implementation remains lower priority than
EP01 and the controlled utility/policy evaluation; the small SC01 fixture uses prescribed
paths/schedules. Detailed architecture and open choices are recorded in the functional-region
review and the canonical notation reference. No environment or motion code was changed.

## Privacy roadmap clarification — 2026-10-19

The historical membership diagnostic already defines a protected unit, secret, complete
background attacker and transcript. Realistic empirical privacy remains unevaluated. Privacy
planning is active through E02-A; E02-B/C explicitly follows the minimal independent utility/
policy milestone, ahead of optional rich map/routing work. The proposed first secret is
contribution membership, with limited auxiliary knowledge, grouped independent splits and
calibrated public-only attacks. Sensitive attributes and formal k/l/t/DP choices remain
separate research decisions. This update changes documentation only, not execution or results.

## Implementation record — independent oracle and first empirical privacy, 2026-10-19

- Implemented EP01 raw compliance checks, bounded whole-sibling/partial-rescue references,
  explicit endpoint enumeration and a private JSON CLI with budget/overwrite checks.
- Implemented seeded modal-path populations, exact IN/OUT source-inclusion neighbours,
  grouped independent splits, target knowledge, clone detection and provenance validation.
- Implemented strict public transcript export, 18/31-feature projections, deterministic
  training-only-scaled logistic regression, calibration and held-out attack metrics.
- Added real-core seven-mode study orchestration, controls, scenario-stratified paired
  bootstrap, conditional/common-support occupancy utility and complete private artifacts.
- Release build, all 23 CTest suites and 126 Python methods passed. Three fixed protocols
  ran on 160 unique realizations / 240 group-configuration pairs; 3,360 audited replay results
  and 46,901 released cells passed independent compliance; all 108 fitted models converged.
- Tiny cases demonstrate current retention 0 versus relaxed A07 retention 6 of 9 contributions.
  This is a coordination-model gap, not an established violation of the implemented contract.
- Evidence, formulas, reproduction commands, figure and limitations are in
  [TEST_REPORT_2026-10-19.md](docs/TEST_REPORT_2026-10-19.md). No general privacy guarantee,
  new live movement engine or independent local-window scheduler was introduced.

## Endurance and bucket-status clarification — 2026-10-19

The first evaluation milestone did not implement automatic preemptive ancestor buckets.
Logical APIs exist; actual adaptive selection reconstructs from retained finest-cell samples.
Two real headless runs (300 s at 50 ms;600 s at 100 ms) and one 600-s persistent analytical
replay through both priorities passed their documented checks. Numerical 200-ms /10-Hz
sampling is rejected. Scope and presentation-critical priorities are in the new bucket-status
and endurance reports; full prewarming/cell-local coordination remains open.

## Controlled common/local study — 2026-10-19

The controller stayed unchanged during a fixed 30-case / nine-configuration comparison.
All 270 primary replays passed independent auditing; 120 adaptive executions reproduced
identical scientific output. Regional latency improves mean local retention by 12.31/17.20
percentage points (TF/SF), while mixed-density retention falls by 15.90/18.10 points.
A blocked branch retains the same data with mean age 538.46 to 148.72 ms. These conditional
findings, all nine references, the publication-overlap witness, formulas and figure are in
[the study report](docs/COORDINATION_STUDY_2026-10-19.md). All 31 CTest suites and 179 Python methods pass; the English study test report and
canonical notation 1.2 are updated. The measured baseline now precedes
further coordinator changes; realistic maps and precomputed ancestor caches remain later work.

## Coordination refinement and current privacy focus — later October 19

Endpoint planning and concrete feasible holds close the proven local coordination
counterexamples. All 210 untouched references match; the revised 30-case study passes
270 audits and 120 repeats. On the original mixed-density families local SF retention
matches common; TF differs by -0.0732 pp on average, with explicit accuracy trade-offs.

The user then prioritized privacy. The fixed 184-realization source-membership study
completes 3312 audits, four repeats and 44 converged attack models. Full-trace/31-feature
SF AUC is 0.65609 common versus 0.61969 local; its paired conditional interval excludes
zero, while the TF interval includes zero. Local utility is slightly lower on this
separate population; residual membership signal, scenario dependence and realized FPR
above the nominal calibration cap remain. Do not claim general protection or universal
advantage. The new independent attack/noisy-knowledge/shift protocol is the next priority;
formal privacy and sensitive-attribute definitions remain separate research contracts.


## Privacy robustness and GitHub publication — later October 19

- Published the audited committed project/history to `demuma/UMP-Simulator` with
  `main` tracking `origin/main`; private data/builds and pre-existing local edits excluded.
- Added independent v2 long-path groups, auxiliary uncertainty, population-count shift
  and a pinned optional boosted-tree attack without changing the simulation engine.
- Passed 36 CTest suites and all 228 Python methods in the complete optional environment;
  legacy Python runs 222 methods with six optional HGB skips. The current fixed study
  completes 2080 audits / 178649 released cells / four repeats / 28 fitted models.
- Independent review recomputes all 56 AUCs, 224 scenario assessments, 16 paired
  bootstrap intervals, utility denominators and 5371 artifact hashes. No general local
  privacy advantage is established; retention/query-availability losses are explicit.
- Exported all aggregate comparisons and a visually inspected scientific PNG/SVG.
  [Study](docs/PRIVACY_ROBUSTNESS_STUDY_2026-10-19.md),
  [test report](docs/PRIVACY_ROBUSTNESS_TEST_REPORT_2026-10-19.md),
  [QI/SA/environment/online contract](docs/PRIVACY_ATTRIBUTE_AND_ONLINE_CONTRACT.md).
- Next are the explicit semantic-secret and online-prefix discussions; maps, SA labels,
  noise-aware attacks and an online application are still unimplemented.


## Local coordination diagnosis — later October 19

- [x] Distinguish causal aggregation during replay from post-run utility and full-history
  attack evaluation; record immediate-ACK, EOF and wall-clock limitations.
- [x] Attribute 76–93% of current net retention loss to mixed-mode cases; inspect source
  types and identical retained points rather than comparing unpaired release batches.
- [x] Measure TF shared-point mean age gains of 117/88 ms and p95 800→400 ms, plus
  exploratory deadline coverage. Preserve original primary study and all its results.
- [x] Prove the passing parent13/[1800,2100) reservation conflict in test-00015 using
  actual production checks and an instrumented copy with identical scientific output.
- [x] **A03/A05 — Subsequently completed handoff repair:** regression for a passing broad parent blocked
  by a contained future handoff. Atomically supersede compatible contained future plans;
  preserve immutable recipient commitments, unrelated reservations and rollback safety.
  Recheck both assessParent and tryMerge; audit ownership/conservation/deadlines.
- [x] **E01 — Subsequently completed:** exact shared-observation sealing age (repair study)
  and causal deadline occupancy (October 20), with predeclared deadlines and EOF scope.
- [ ] **E05 — Remaining live timing:** measure processing/transport separately before
  end-to-end real-time claims.
- [ ] **EP02/EP03:** new independent before/after comparison and uniform/regional deadline
  factorial study, with both utility and membership outcomes; preserve current held-out
  evidence and avoid tuning against it. Full city/visit semantics remain separate work.
- [x] Save a local HTML viewer, PNG/SVG figures, scenario tables, independent prefix
  checks and private source-hashed evidence in the ignored diagnostic directory.


## Scenario and ground-truth scope audit — later October 19

- [x] Inventory all 208 source PRESENT cases: threshold 3 is a cell/window requirement,
  peaks reach 82 observed road users; turnover reaches 351 distinct IDs across a run.
  Record exact per-family ranges, cohort/split scope and source-loss denominators in
  [the inventory](docs/SCENARIO_INVENTORY_AND_GT_LOSS_2026-10-19.md).
- [x] Audit fixture versus production types: fixture uses three hardcoded labels; only
  mixed-mode cases contain bicycle/car. The active 100-agent config has seven named
  types, no cars, and is not imported by this privacy generator. Public releases omit
  type breakdowns; existing utility evaluates total occupancy only.
- [ ] **EP02/EP03 — Production-type adapter:** versioned generator/capture settings with
  the existing seven type names/profiles and actual-count assertions. Keep this separate
  from the later X01 flexible taxonomy redesign; explicitly record any coarse mapping.
- [ ] **D01/E01 — Loss decomposition:** aligned sensor coverage/cadence; eligible GT → source
  matching→released support. Add per-type/region/person completeness and resolution/task
  metrics; do not call source-contribution retention a percentage of all GT information.
- [ ] **EP03/R01 — Capture extension:** configurable duration/population/taxonomy, common
  GT/AGBS area, verified private identity correspondence and isolated capture provenance.
  Existing capture remains 8 seconds/200 Adult Pedestrians; do not silently broaden it.
- [ ] **EP04/B01 — Density and scale:** predeclare below/near/above support, regional
  deadlines and crossings; longer flows/warm-up/interior; separate N-density from area
  scalability with fixed physical cell width. Recheck initialization rounding and actual
  population before accepting requested counts such as 100/300/1000.


## Local holds, reservations and privacy investigation — later October 19

- [x] Audit the uniform numeric policy, sequential future-handoff scheduling and
  exact-boundary reservation veto; distinguish public disclosure, private empty retirement
  and future plans. Document the known two-car geometry/support infeasibility separately.
- [x] Run 1536 policy-fixed diagnostic interventions on all prior held-out source worlds:
  optional holds off, future handoffs off and both off. Every independent audit passes;
  eight unmodified relinks reproduce frozen scientific output. Full results stay private.
- [x] Separate passing versus empty holds with 512 additional base-cohort interventions
  and eight relink controls. SF retention is 91.32% current, 73.34% without passing holds,
  and 4.68% without empty holds. TF passing-hold removal preserves retained sets and ages.
- [x] Check nominal type diversity with eight audited runs: one versus seven labels,
  fixed 22 identities and kinematics, exactly identical recipient output and 31 features.
- [x] **A03/A05:** targeted handoff repair implemented and independently assessed; blanket
  handoff/hold deletion was not adopted. Certified-empty support remains a separate proposal.
- [ ] **EP02/EP03:** freeze corrected code and compare on independent source groups with
  mechanism-specific TRAIN/CAL attacks, full-history and deadline-prefix outcomes,
  uniform/heterogeneous regional deadlines and sensible common-window references.
  Include utility/retention/freshness; a support pass or higher retention is not privacy.
- [ ] **E06:** isolate fixed payload delay from interval extension and distinguish private
  coordination from global pending-output backpressure. Measure actual online delivery.

[Analysis, controlled comparisons and verification scope](docs/LOCAL_WINDOW_HOLD_PRIVACY_ANALYSIS_2026-10-19.md).
A07 remains selective descendant suppression; the previous diary label for the future
handoff repair has been corrected to A03/A05. The diagnosis itself left production
unchanged; the later documented handoff repair changed the controller. The October 20
causal evaluation reuses that repaired controller unchanged.


## Causal membership and deadline utility — completed October 20

- [x] Keep the original whole-source secret and unchanged repaired C++ mechanism; freeze
  fresh seed20261023 groups before outcomes, with no pair/background overlap against the
  previous two primary datasets. All 2080 release audits and four repeats pass.
- [x] Implement causal public/knowledge gates and repeated-look calibration. Complete
  360 models, 60 strategies, 120 cohort and 720 checkpoint assessments; retain every
  model/control/outcome, including negative or inconclusive findings.
- [x] Independently verify source geometry/counts/identity unions, LR probabilities,
  saved-score threshold selection and grouped uncertainty, all deadline and matched
  utility projections. All 40 CTest suites and 285 Python methods pass.
- [x] Document the real conditional TF timeliness benefit, absence of an isolated
  history advantage, first-look representation confounding and CAL-to-TEST FPR transfer
  limitation. Do not equate operational support with measured privacy protection.
- [x] Archive protocol, complete English results/test reports, aggregate tables,
  notation and four PNG/SVG figures. Primary scientific bundles remain immutable/private.
- [ ] Finish presentation integration, then predeclare the matched-memory and
  calibration follow-ups listed under E02. Semantic visits, heterogeneous deadline
  factorials and actual recipient timing remain separately scoped work.


## Sequential algorithm gate — A07 common-window fallback, 2026-10-21

- Recorded the rule and invariants before implementation; introduced one optional action
  only, preserving the existing baseline and all hard requirements.
- Independent references confirm retained contributions increase from 0 to 6 of 9 and
  from 0 to 18 of 21; a valid parent still retains all 9. These are mechanism tests.
- 42 CTest suites / 297 Python methods pass, including 194 bounded exhaustive spatial
  cases, plus independent pre/post compatibility and sanitizer checks.
- Stop at this review gate. Next discuss semantic products, exact metric meanings and
  allowed actions; membership, mapping, taxonomy implementation and caching remain deferred.


## Sequential semantic gate — A08, 2026-10-21

- The acceptance contract preceded implementation. Added one bounded common-window
  semantic action: truthful complete category generalization with all contributions kept
  inside a released spatial cell. No individual/type suppression or false relabeling.
- Online regional bounds now use exact minimum category support and maximum/mean declared
  semantic loss. Other scalar constraints, TF/SF, A07 and publication remain binding.
- 47 CTest entries; 300 passed Python methods and 12 optional skips; all 15 semantic
  methods passed; 81 exhaustive semantic cases, actual MongoDB recovery,
  sanitizer and 24 unchanged before/after baseline pairs pass. Five audited examples show
  the effects of permitting/forbidding semantic detail loss and insufficient support.
- E07 records the user's requested constraint-impact study. Stop at the review gate before
  broadening coordination, action selection, simulation realism or privacy attacks.


## Semantic priority review gate — E07/A08, 2026-10-21

- Completed a predeclared bounded candidate-choice study with independent raw-data
  enumeration and fixed receiver-only exact queries. No production policy weakening.
- All 360 configurations pass; all 1,929 actual cuts are legal; all 12 repeats match.
  There are 252 actual intervals with no nonempty legal candidate, not 252 impossible
  online schedules. None is dominated on all six declared conditional criteria.
- Fine occupancy and coarse exact class totals are incomparable without task priorities.
  Longer windows can retain all observations while losing exact short-window answers.
- 50 CTest entries pass; Python: 345 passed, 12 existing optional skips. All 45 new
  methods executed. Source/protocol/binary snapshots and detailed results are preserved.
- Next: choose application requirements/preferences before any priority-controller change.
  Local semantics, empirical attacks, maps and computation optimization remain deferred.


## Semantic First terminology and density isolation — 2026-10-21

- Adopted Semantic First = preserve semantic accuracy, consistent with TF/SF. Current
  early semantic generalization is explicitly distinguished; parser/controller unchanged.
- Completed 18 real cases plus 3 exact repeats, 90 independent legal-cut interval audits,
  six conditionally infeasible intervals and 127 checked artifact hashes. No new CTest
  methods or production behavior were added. See the controlled density report.
- At equal policy, more density can yield finer space while initially losing type detail;
  high enough per-class support then retains both. Static waiting produces no new support.
- Next gate: secondary TF/SF preference, bounded waiting/fallback and partial-output rules
  before Semantic First implementation. Identity-turnover isolation precedes map realism.


## Semantic First implementation gate — 2026-10-21

- Added opt-in common-window semantic_first with Temporal First secondary priority.
  Required catalog/history/policy bounds remain explicit; default configuration unchanged.
- Full 52-entry build/regression passes: 361 Python passes, 12 existing optional skips;
  all 16 new Python methods and 13 native cases execute, including ASan/UBSan.
- Actual MongoDB new-mode parent with 96 observations/32 IDs pipeline survives lost ACK,
  reconciliation, commit and recovery without exposing preferences or private evidence.
- All 30 frozen legacy pairs match outside runtime, including 6 semantic old-mode pairs;
  60 independent scalar audits pass. Additional 27 controlled strategy/density cases
  pass 135 actual-interval audits and retain the 18 old outputs byte-for-byte outside runtime.
- Maximum-loss priority can increase mean loss; static waiting can add delay without gain.
  These measured limitations are part of the gate, not hidden tuning targets.
- Next is review of application priorities and turnover/waiting costs. No second Semantic
  First combination, local-semantic controller, map work or new attacks begins automatically.

## Follow-up research questions from semantic coordination review

- [ ] Quantify the opportunity cost of irreversible early release against bounded
  holding, using identical inputs and policy constraints; current release eligibility
  does not promise the best later merge.
- [ ] Compare worst-category-loss selection with an observation-weighted mean-loss
  objective. A Root-only region can open a global common-window loss ceiling while
  another region could still preserve a useful family category. This is an objective
  limitation, not evidence that max loss 1 forces every output to Root.
- [ ] Preserve a separate chronology for analytical fixtures and actual Simulator
  captures. The 20-identity leaf fixture deliberately keeps positions in their leaves;
  it cannot support claims about realistic walking, density or collision behavior.

- [ ] Separate base probe cadence from hard minimum duration in the next comparison.
  The 400-ms base probe allows current legal parent rescues with shorter intervals
  at other owners' endpoints; compare an explicit `window_duration_ms.min` without
  retrospectively changing the frozen October 22 fixture.
