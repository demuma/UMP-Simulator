# Implementation Plan — Adaptive Privacy-Preserving Urban Mobility Data Aggregation

> **Reference translation, 2026-10-08:** This is the English version of the historical
> plan supplied from `/Users/maxdemu/Library/Mobile Documents/com~apple~CloudDocs/Downloads/IMPLEMENTATION_PLAN.md`.
> The external original remains unchanged. Phases, priorities, examples and the embedded
> project prompt below are reference material, not current instructions to execute.
> Use [README](../../README.md) for actual status and [TO-DO](../../TO-DO.md) for priorities.
> Claims about novelty and architectural choices in this plan remain proposals requiring validation.

**Project:** Dissertation — Adaptive, Metric-Based and Privacy-Preserving Urban Mobility Data Sharing
**Technology:** C++17, SFML, OpenGL, MongoDB
**Architecture:** Agent-based simulation with sensor-local aggregation
**Objective:** A scientifically evaluable framework for adaptive spatial and temporal aggregation
under regional privacy and utility constraints.

> **Guiding principle:** Maintain a maximally resolved internal dataset and dynamically
> derive permissible spatial/temporal publications under privacy, utility and application constraints.
>
> **Scope:** Detection/classification are not the research subject. Preserve ground truth;
> model measurement uncertainty in a separate sensor layer if needed. The key challenge
> is correct temporal history under changing spatial aggregation.

## Priorities

| Priority | Meaning |
|---|---|
| P0 | Essential core functionality |
| P1 | Important for evaluation and dissertation |
| P2 | Extension that must not block the core |
| P3 | Future work outside the current research scope |

# 1. Fundamental target architecture

## 1.1 Overall structure

The existing simulation owns an agent vector and sensor instances. Sensors process agent
states and generate different representations. Preserve that overall organization.

```text
SIMULATION
  Agent Management / Ground Truth / Trajectories
                       │
                std::vector<Agent>
                       │
          ┌────────────┼─────────────────────┐
          ▼            ▼                     ▼
     AgentBased     GridBased         AdaptiveGridBased
       Sensor        Sensor               Sensor
          │            │                     │
          │            │               Sensor Model
          │            │                     │
          │            │               Max-Quadtree
          │            │                     │
          │            │              Temporal Storage
          │            │                     │
          │            │            AggregationManager
          │            │                     │
          │            │              Policy Evaluation
          │            │                     │
          │            │               Published Cells
          └────────────┴─────────────────────┤
                                             ▼
                                    Sensor Output / MongoDB
                                             │
                                        SharedBuffer
                                             │
                                          Renderer
```

**Proposed architecture decision:** AggregationManager belongs to each AdaptiveGridBasedSensor
pipeline, rather than being global. Each adaptive sensor owns its detection area, quadtree,
temporary observations, manager, policies/mapping and publication interface. Central
multi-sensor fusion remains a later option.

## 1.2 Responsibilities

| Component | Responsibility |
|---|---|
| Simulation | Create, move and update agents |
| Sensor | Coordinate the sensor pipeline and publish results |
| AgentBasedSensor | Agent-based reference data |
| GridBasedSensor | Fixed-grid benchmark |
| AdaptiveGridBasedSensor | Adaptive spatial/temporal aggregation |
| SensorModel | Abstract uncertainty and sensor parameters |
| Quadtree | Spatial hierarchy and cell geometry |
| TemporalStorage | Observation history and time windows |
| AggregationManager | Aggregation decisions and output scheduling |
| PolicyManager | Regional rules and constraints |
| MetricEvaluator | Privacy, utility and system metrics |
| SharedBuffer | Exchange across thread boundaries |
| Renderer | Visualization |
| MongoDB adapter | Persistence/transport of sensor results |

Each module has a clearly defined responsibility.

# 2. Phase 0 — Code audit and inventory

**Priority: P0.** Read actual code before changes; do not immediately rewrite large classes.

## Existing files

```text
Main.cpp
Simulation.hpp / Simulation.cpp
Renderer.hpp / Renderer.cpp
Region.hpp / Region.cpp
Quadtree.hpp / Quadtree.cpp
Sensor.hpp / Sensor.cpp
AdaptiveGridBasedSensor.hpp / AdaptiveGridBasedSensor.cpp
GridBasedSensor.hpp / GridBasedSensor.cpp
AgentBasedSensor.hpp / AgentBasedSensor.cpp
AggregationManager.hpp / AggregationManager.cpp
SharedBuffer.hpp / SharedBuffer.tpp
```

Include other repository files and dependencies.

### 2.1 Trace data flow

Agent creation/update; sensor ownership; observation-to-cell assignment; current splits,
merges and maximum depth; cell-ID convention and reconstruction; MongoDB publishing for
each sensor; SharedBuffer between simulation and renderer.

### 2.2 Document ownership and threading

Identify owners of trees, sensors and buffers; copies versus references/pointers;
thread assignments; simulation/render timing and synchronization.

### 2.3 Preserve a reference

Secure a reproducible reference run and relevant checks before refactoring. Keep existing
sensor variants and visualization functional.

**Deliverable:** documented hierarchy, data flow, architectural issues, changes per file
and verification/migration strategy.

# 3. Phase 1 — Revise quadtree architecture

**Priority: P0.**

## 3.1 Fully resolved static quadtree

Current behavior: split dynamically from agent positions; empty regions may remain unsplit.
Proposed behavior: build topology to maximum depth once at initialization, then keep it fixed.

```text
Initialize full spatial hierarchy
    → fixed topology
    → assign observations
    → aggregation and policy evaluation
    → dynamic publication view
```

No structural runtime splits/merges. Parent/child nodes remain present. A spatial merge
creates an aggregated parent representation without changing topology. Renderer receives
published IDs and reconstructs geometry; it need not draw empty maximum-depth cells.

## 3.2 Configurable maximum depth

Parameters: simulation_width, simulation_height, maximum_tree_depth, minimum_cell_size.
For a square root of side L:

```text
s(d) = L / 2^d
For cell size at most s_target:
d = ceil(log2(L / s_target))
```

A physical minimum cell size requires a different bound; do not confuse maximum permitted
size with a minimum that must not be crossed.

## 3.3 Stable cell identities

Every cell has a unique ID/depth; parents/children are efficiently derivable; bounds can
be reconstructed. Preserve quadrant indices:

```text
0 = North-West
1 = North-East
2 = South-West
3 = South-East
```

IDs connect aggregation, storage, rendering, MongoDB, metrics and policy mapping.

## 3.4 Memory and structures

Complete single-root quadtree with maximum depth D:

```text
N_nodes = (4^(D+1) - 1) / 3
```

| Maximum depth | Nodes |
|---|---:|
| 5 | 1,365 |
| 7 | 21,845 |
| 8 | 87,381 |
| 10 | 1,398,101 |
| 12 | 22,369,621 |

Separate topology from temporal observations. Topology may be materialized fully; allocate
observation history only for relevant cells. Adapt examples to the actual cell convention.

```cpp
struct QuadtreeNode {
    CellId id;
    CellId parentId;
    std::array<CellId, 4> children;
    AABB bounds;
    uint8_t depth;
};
```

## 3.5 Bottom-up aggregation

```text
Leaf contributions: 2 + 3 + 1 + 4
Parent: 10 observation contributions
```

Aggregatable fields include counts, class frequencies, velocities, intervals and possibly
internal identities for privacy evaluation. Counts are additive; distinct-person sets
are not necessarily additive. Deduplicate repeated observations correctly.

**Acceptance:** invariant topology, correct position mapping and parent aggregation,
stable IDs, no unintended double counting and documented storage cost.

# 4. Phase 2 — Temporal storage

**Priority: P0.** Temporal aggregation is independent of spatial topology; this contains
major design decisions.

## 4.1 Concept history

Previous concept: active and buffer buckets for normal/preemptive aggregation. New proposal:
retrospectively reconstruct permitted parent windows from maximally resolved observations.
Determine whether two physical buckets suffice or general temporal storage is preferable.

## 4.2 Requirements

1. Ingest timestamped observations.
2. Support variable windows.
3. Extend windows.
4. Reconstruct spatial parent windows retrospectively.
5. Bound retention and clean up safely.
6. Support cell-specific windows.
7. Record publication time.

**Invariant:** every permitted window's parent aggregate is reconstructable from relevant
child/leaf observations.

## 4.3 Time bins / ring buffer

```text
Leaf 104:
0 ms    100 ms    200 ms    300 ms    400 ms
[B0]────[B1]──────[B2]──────[B3]──────[B4]
100-ms window → B0
300-ms window → B0+B1+B2
500-ms window → B0+B1+B2+B3+B4
```

Ordered bins or bounded ring buffers are candidate foundations, not a final untested choice.

## 4.4 Active and buffer buckets

Active covers the current open window. Buffer prepares the next window or a clearly defined
preemptive strategy. Historical bins support retrospective spatial/temporal aggregation.
Evaluate logical window states over shared storage rather than redundant per-node copies.

## 4.5 Window management

Define start, end, extension, closure, publication and rejection for every relevant area.
Example cell windows: A 100 ms, B 300 ms, C 700 ms, D 1000 ms.
Merging cells requires compatible temporal coverage. No contributions outside the selected
window, and no unintentional reuse across overlapping/already published windows.

## 4.6 Retention

Parameters: history_retention_ms, minimum_aggregation_window_ms,
maximum_aggregation_window_ms, time_bin_size_ms.
Remove observations only when no permitted open aggregation needs them.

**Acceptance:** variable windows, retrospective parent reconstruction, no duplicate
contributions, bounded storage and cell-specific schedules.

# 5. Phase 3 — Policy system

**Priority: P0.** Application rules constrain release granularity and privacy requirements.

## 5.1 Profiles / use cases

| Application | Example requirements |
|---|---|
| Traffic-flow analysis | Fine temporal, possibly coarser spatial resolution |
| Urban planning | Coarser spatial/temporal aggregation |
| Retail analysis | Regional visit statistics |
| Administrative analysis | Purpose-specific granularity |
| Police search | Separately defined access/privacy rules |

These are research scenarios, not assertions of legal access permissions.

## 5.2 Model

PolicyManager, Policy, PolicyRegion and PolicyConstraints.

```cpp
struct PolicyConstraints {
    uint32_t minK;
    uint8_t minDepth;
    uint8_t maxDepth;
    double minTemporalWindow;
    double maxTemporalWindow;
    double maxStaleness;
};
```

Extend modularly with privacy/utility criteria.

## 5.3 Regional mapping

Options: rectangles, polygons or an independent policy overlay tree. Keep policy hierarchy
conceptually separate from data quadtree. Policy changes should not require rebuilding topology.

## 5.4 Overlaps and conflicts

Handle global defaults, regional overrides, overlapping regions, cells spanning regions,
contradictory constraints and merges across boundaries. Explicitly reject conflicts or
resolve them by a documented rule. Never silently weaken requirements through a merge.

## 5.5 Runtime updates — P1

New policies can affect future aggregation. Already published data cannot be recalled.

**Acceptance:** global/regional policies, deterministic conflict handling, complete checks
before release and independence from data topology.

# 6. Phase 4 — Complete AggregationManager

**Priority: P0; highest functional importance in the proposed full system.** Connect spatial
hierarchy, history, privacy/utility, policies and strategies.

## 6.1 Responsibilities

Evaluate input, generate candidates, check constraints, perform aggregation, apply strategy,
release/withhold/suppress and update evaluation metrics.

## 6.2 Spatial First

```text
Violation → merge spatial cells → reevaluate
          → extend temporal window if still necessary
```

Favor freshness at the expense of spatial detail.

## 6.3 Temporal First

```text
Violation → extend temporal window → reevaluate
          → merge spatial cells if still necessary
```

Favor spatial detail when possible.

## 6.4 Metric-based adaptation — P1

Compare permissible candidates using a configurable objective:

```text
U = f(U_spatial, U_temporal, U_latency, U_fidelity)
```

Apply privacy and utility constraints. Do not assume a feasible solution always exists.

## 6.5 Release process

```text
Observations → temporal storage → candidate generation → constraint evaluation
  Valid → publish
  Invalid → adapt spatially/temporally → reevaluate
    Valid → publish
    Invalid → further adaptation possible?
      Yes → repeat
      No → suppress
```

## 6.6 Avoid redundant releases

Avoid contradictory parent/child releases in the same output interval, double counting and
possible differencing attacks. Account for repeated releases and overlapping windows.

## 6.7 Policy-specific views — P1

Later: shared internal observations with independent policy evaluation and release states.
Initially use one active policy per sensor; compare policies in identically fed separate runs.

**Acceptance:** Spatial First, Temporal First, correct suppression, no invalid/unintended
double publications and reproducible decisions.

# 7. Phase 5 — Privacy metrics

**Priority: P0/P1.** Interchangeable evaluators.

## 7.1 k-anonymity / k-based minimum count — P0

```text
k(c,W) = number of distinct agents observed in cell c during window W
```

Do not count repeated observations as new people. A distinct-contributor threshold is
initially an operational k-based rule. Formal k-anonymity also requires specified adversary,
quasi-identifiers and linkability of repeated publications.

## 7.2 l-diversity — P1

Count relevant sensitive-attribute values. Agent classes are not automatically sensitive
attributes; define the semantics explicitly.

## 7.3 Further metrics — P2

Candidates: t-closeness, delta-presence, entropy, KL divergence and mutual information.

```text
PrivacyMetricEvaluator
  ├── KAnonymity
  ├── LDiversity
  ├── TCloseness
  ├── DeltaPresence
  └── InformationMetrics
```

Class counts cannot reconstruct every metric. Document required data for each evaluator.

# 8. Phase 6 — Utility and system metrics

**Priority: P0/P1.**

## 8.1 Spatial resolution — P0

Record published cell side/area/depth and, if appropriate, average effective spatial granularity.

## 8.2 Temporal resolution — P0

```text
Delta t = windowEnd - windowStart
```

Record per publication.

## 8.3 Lag / staleness — P0

```text
L = publicationTime - latestMeasurementTime
```

Subtract times on the same clock only. Report simulation-based data age separately from
wall-clock processing latency.

## 8.4 Processing time — P0

```text
T_processing = endTime - startTime
```

Measure per update/batch and cell decision. Distinguish inclusive/exclusive overlapping costs.
Count evaluated cells, merges, window extensions and constraint checks.

## 8.5 Data fidelity / suppression rate — P0

Historical proposed contribution-retention measure:

```text
F = 1 - N_suppressed / N_input
```

Compare observation contributions, not merely MongoDB record counts. Record InputMeasurements,
PublishedContributions, SuppressedContributions and SuppressionReasons. One publication can
represent many inputs. The current roadmap distinguishes retention from broader fidelity.

## 8.6 Localization accuracy — P1

Compare GT with measured positions and, separately, with a release representation such as
cell center. Report sensor and aggregation errors separately.

## 8.7 Classification accuracy — P1

Meaningful only with an active classification-error model. GT labels copied directly imply
100% simulated accuracy by construction, not a separate research result.

## 8.8 Additional metrics — P1/P2

Velocity error, OD flows/flow preservation, class-distribution error, aggregation overhead,
memory, CPU usage and publication rate.

# 9. Phase 7 — Sensor model and uncertainty

**Priority: P1.** Detection/classification are not the research subject. Do not build a
complete camera/LiDAR simulator for this core aggregation task.

## 9.1 Preserve GT

```text
GT position → measurement model → measured position → quadtree
```

Do not overwrite GT with noise.

## 9.2 LiDAR-oriented abstraction

Parameters: sensor_position, sensor_orientation, horizontal_fov, vertical_fov, maximum_range,
beam_divergence, angular_sampling_resolution, range_noise_sigma, angular_noise_sigma.

Beam divergence, angular spacing and angular noise are different. Do not directly infer a
standard deviation from divergence. Example polar noise:

```text
r_measured = r_GT + epsilon_r
theta_measured = theta_GT + epsilon_theta
```

Cartesian conversion gives distance/direction-dependent error.

## 9.3 Camera classification — P1

Initially use GT class labels. Optionally add a confusion matrix, class-specific error rates
and detection probabilities; real CNNs are unnecessary.

## 9.4 Sensor fusion — P2

Possible extensions: LiDAR + monocular camera, stereo or LiDAR + stereo. Complete fusion
is not required by the core algorithm.

## 9.5 Distance-dependent resolution — P1

Separate sensor resolution, localization uncertainty, application requirements and max tree
depth. Express sensor-induced minimum granularity through policies/utility where appropriate,
rather than rebuilding static topology for distance.

# 10. Phase 8 — SharedBuffer and threading

**Priority: P0.**

## 10.1 Internal containers versus thread boundaries

Simulation owns agents/sensors; sensors can read agent states directly in the same execution
context. SharedBuffers serve thread boundaries, not every internal method call.

## 10.2 Simulation to renderer

```text
Simulation thread → SharedBuffer → renderer thread
```

Renderer needs agent debug data and sensor views. Do not share unsynchronized mutable state.

## 10.3 CombinedFrame — P1

```cpp
struct CombinedFrame {
    double simulationTime;
    std::vector<AgentVisualization> agents;
    std::vector<SensorVisualization> sensors;
};
```

Prefer adapting existing code with immutable snapshots. Sensors need not publish every
simulation tick. Capture time, window, publication time and sequence number are per-sensor data.

## 10.4 Immutable snapshots — P1

Evaluate shared_ptr<const T> for lower copy cost, explicit ownership and consistent snapshots.
Transport still needs synchronization; pointer lifetime alone does not prevent all data races.

## 10.5 Separate aggregation thread — P2

Initially run sensor aggregation in the simulation thread. Consider another thread only
after measurement, potentially with immutable measurement batches in a queue.

## 10.6 Unix domain socket — P3

Optional for process separation, crash isolation or interchangeable pipelines; not required
for current in-process operation.

# 11. Phase 9 — MongoDB and sensor output

**Priority: P0/P1.** The sensor owns publication and DB communication. The manager does not
know MongoDB.

```text
AdaptiveGridBasedSensor
    → AggregationManager
    → Aggregated Cells
    → Sensor Output Interface
        ├── MongoDB
        ├── SharedBuffer
        └── optional file export
```

## 11.1 Records

```cpp
struct AggregatedCell {
    CellId cellId;
    double windowStart;
    double windowEnd;
    uint32_t totalCount;
    ClassCounts classCounts;
};
```

Additional fields: sensor_id, policy_id, publication_timestamp, aggregation_strategy and
spatial_depth. Do not publish internal identities. Keep evaluation data separate when needed.

## 11.2 Output interface — P1

```text
ISensorOutput
  ├── MongoOutput
  ├── FileOutput
  └── NullOutput
```

Allows benchmarks without an external database.

## 11.3 Asynchronous publishing — P1

Consider a bounded queue to decouple DB I/O. Measure aggregation completion, queue handoff
and successful persistence separately.

# 12. Phase 10 — Improve simulation and agent distributions

**Priority: P1.**

## 12.1 Retain uniform distribution

Useful for debugging, scaling and reproducible reference checks.

## 12.2 Heterogeneous scenarios

Configurable Dense, Medium, Sparse and Empty regions; spawning rate, target density,
class distribution and bounds.

## 12.3 Spawn areas — P1

Optional building entrances, streets, sidewalks, stops and plazas rather than purely random starts.

## 12.4 Target areas — P1

Entrances, exits, stops, junctions and target corridors to create plausible flows.

## 12.5 Path planning — P2

Waypoints, routes, obstacle avoidance, class-specific speeds and possibly ORCA. Must not
block the aggregation core.

## 12.6 Agent classes — P1

Preserve existing types; optionally add pedestrian, cyclist, scooter, wheelchair user and
other vulnerable road users. Later separate base group, modality and mobility restrictions.

# 13. Phase 11 — Revise rendering

**Priority: P1.**

## 13.1 Cell reconstruction

Render published IDs and values; reconstruct bounds. Do not draw every internal max-depth cell.

## 13.2 Preserve views

GT/trajectory agent view, static-grid benchmark view and adaptive published-cell view.

## 13.3 Aggregation visualization — P1

Show cell size, merges, temporal windows, compliance, suppression and regional rules.
Optional overlays for depth, window length and privacy status.

## 13.4 Policy overlay — P1

Draw transparent policy regions over the map to inspect local adaptation.

## 13.5 OpenGL/3D rendering — P2

Improve SFML/OpenGL separately; the historical plan notes macOS OpenGL 4.1 Core support.
That is not equivalent to SFML Graphics support for that profile. The research core remains
usable with 2D rendering. Native Metal is a separate current discussion in README.

# 14. Phase 12 — Evaluation framework

**Priority: P1 in this historical plan.** Integrate evaluation rather than relying only
on manual MongoDB dump processing. The current task list moves essential evaluation earlier.

## 14.1 Reproducible configuration

```yaml
simulation:
  width: 120
  height: 60
  duration: 300
  timestep: 0.05
  agents: 100
  random_seed: 42
quadtree:
  max_depth: 5
aggregation:
  strategy: spatial_first
  min_window_ms: 100
  max_window_ms: 1000
privacy:
  k: 5
sensor:
  noise_enabled: false
```

Example parameters, not final scientific choices. A 0.05-s step gives 20 updates/s.

## 14.2 Scenarios

| Scenario | Purpose |
|---|---|
| Uniform density | Reference and scaling |
| Dense region | High density |
| Sparse region | Privacy under low density |
| Mixed density | Heterogeneous conditions |
| Dynamic density | Changing distribution |
| Regional policies | Different local requirements |
| Strict privacy | Strong aggregation pressure |
| Sensor noise | Uncertainty effects |

## 14.3 Baselines

Agent-based reference, fixed grid, spatial-only, temporal-only, Spatial First, Temporal
First and metric-based adaptation. Implement missing baselines or justify their exclusion.

## 14.4 Metrics

Privacy compliance, spatial/temporal resolution, staleness, processing time, fidelity,
localization/velocity error, publication/suppression rates, memory and CPU usage.

## 14.5 Headless experiment runner

Load configuration, run deterministic input and save observations/results:

```text
experiment_001/
  config.yaml
  metadata.json
  metrics.csv
  publications.csv
```

## 14.6 Statistics

Multiple seeds; mean, median, standard deviation, quantiles and appropriate confidence
intervals. Do not base scientific conclusions on one run.

# 15. Phase 13 — Tests and scientific correctness

**Priority: P0/P1.**

## 15.1 Quadtree

IDs, parent/child relations, bounds, initialization, mapping and invariant topology.

## 15.2 Temporal storage

Window start/extension/closure, retrospective aggregation, cleanup, overlaps and repeated identities.

## 15.3 Privacy

```text
Distinct agents = 3, k = 5 → no publication
Parent distinct agents = 8, k = 5 → permitted only if all other constraints also hold
```

## 15.4 Policy

Two regions, overlap, conflict, cross-boundary merge and impossible requirements.

## 15.5 Aggregation

Spatial First, Temporal First, suppression, no double counting, correct parent statistics
and documented loss reasons.

## 15.6 Reproducibility

Equal seed/configuration gives equal scientific decisions. Wall-clock runtime need not be identical.

# 16. Phase 14 — Performance and scalability

**Priority: P1. Correctness before optimization.**

## 16.1 Profiling

Measure quadtree access/mapping, history, parent aggregation, policy lookup, metrics and output.

## 16.2 Candidate optimizations

Contiguous node storage, indices rather than pointer chasing, precomputed hierarchy links,
active-cell lists, incremental statistics and bounded ring buffers.

## 16.3 Process active areas

A static hierarchy does not require traversing all nodes every tick. Active leaves and
ancestors may suffice.

## 16.4 Separate memory accounting

Topology, history, privacy helper states, queues and shared buffers.

## 16.5 Separate runtime costs

Simulation, sensor processing, aggregation, policy evaluation, publication and DB transfer.
Do not promise unmeasured speedups.

# 17. Phase 15 — Extensions outside the critical path

**Priority: P2/P3.**

| Feature | Priority | Purpose |
|---|---|---|
| LiDAR/camera fusion | P2 | Further measurement uncertainty |
| Complete stereo simulation | P3 | Camera depth using baseline |
| ORCA collision avoidance | P2 | Realistic movement |
| OSM/CityGML import | P2 | City geometry |
| Buildings/entrances | P2 | Semantic start/target areas |
| 3D renderer | P2 | Additional visualization |
| Multi-sensor fusion | P3 | Shared observation basis |
| Central aggregation manager | P3 | Multiple sensors |
| Unix domain socket | P3 | Process communication |
| GPU acceleration | P3 | Performance |
| Distributed processing | P3 | Distributed architecture |
| Further privacy metrics | P2 | Additional formal criteria |

# 18. Proposed implementation order in the historical plan

This sequence is preserved as reference; current TO-DO priorities differ.

| Step | Task | Priority | Requires |
|---|---|---|---|
| 1 | Audit and architecture documentation | P0 | None |
| 2 | Reference checks and runs | P0 | 1 |
| 3 | Separate topology from observations | P0 | 2 |
| 4 | Static max-depth quadtree | P0 | 3 |
| 5 | IDs and parent aggregation checks | P0 | 4 |
| 6 | Temporal storage | P0 | 5 |
| 7 | Retrospective aggregation | P0 | 6 |
| 8 | Policy data model | P0 | 4 |
| 9 | Policy overlay and regional mapping | P0 | 8 |
| 10 | k-based checks | P0 | 6, 8 |
| 11 | Spatial First manager | P0 | 7–10 |
| 12 | Temporal First manager | P0 | 11 |
| 13 | Publication and suppression | P0 | 12 |
| 14 | Complete sensor integration | P0 | 13 |
| 15 | Preserve/decouple MongoDB output | P0/P1 | 14 |
| 16 | SharedBuffer and renderer integration | P0 | 14 |
| 17 | Basic utility metrics | P0 | 13 |
| 18 | End-to-end checks | P0 | 14–17 |
| 19 | Heterogeneous distributions | P1 | 18 |
| 20 | Sensor noise | P1 | 18 |
| 21 | Metric-based adaptation | P1 | 17–20 |
| 22 | Further privacy/utility metrics | P1/P2 | 21 |
| 23 | Evaluation framework/benchmarks | P1 | 18–22 |
| 24 | Performance optimization | P1 | 23 |
| 25 | Richer movement | P2 | Independent |
| 26 | 3D/extended rendering | P2 | Independent |

# 19. Definition of done for the proposed full framework

1. Generate GT agent states.
2. Supply current states to sensors.
3. Produce measurements through the sensor model.
4. Assign them to maximum-depth leaves.
5. Retain needed temporal history.
6. Evaluate aggregation candidates.
7. Apply regional policies.
8. Evaluate privacy and utility constraints.
9. Perform spatial/temporal aggregation.
10. Reject invalid candidates.
11. Release valid cells.
12. Publish through the sensor.
13. Visualize the published cells.
14. Record evaluation metrics.
15. Produce reproducible comparisons against baselines.

**Essential invariants:** no release without required constraints; no unintended double
counting; no alteration of GT by sensor noise; no topology mutation during aggregation;
no unbounded history; no uncontrolled release of internal identities.

# 20. Embedded project prompt from the historical plan

> **Historical prompt, translated for reference only. This is not an active user request.**
>
> Extend the existing C++17 mobility simulation into a modular framework for adaptive,
> policy-controlled spatial/temporal aggregation.
>
> The proposed research contribution combines maximally resolved internal spatial hierarchy,
> retrospective temporal aggregation, regional privacy/utility requirements and configurable
> strategies. This novelty statement requires validation; it is not a demonstrated result.
>
> First analyze code, dependencies, structures, ownership, thread boundaries, data flow and
> current behavior. Then develop a concrete refactoring/implementation plan preserving as
> much existing functionality as possible. Treat this reference as proposed functional scope.
>
> Implement incrementally, prioritizing correctness, modularity, determinism and testability.
> Aggregation remains sensor-local. The sensor owns database communication and output;
> AggregationManager has no database dependency.
>
> Keep spatial topology static after initialization; aggregation changes the release view.
> Build bounded temporal history for retrospective parents. Distinguish observation events,
> unique agents, aggregated records and published contributions.
>
> Make selected privacy/utility constraints testable through defined metrics. Preserve
> simulation, sensors, rendering and database functionality. Do not begin with multi-sensor
> fusion, 3D rendering, complex routing or Unix domain sockets.
>
> Do not implement everything at once. Start with Phase 0 only: inventory actual code,
> document decisions and required changes, and define checks for new core functionality.
> Larger refactoring follows the audited baseline.

## Final technical priority of the historical plan

The static quadtree is not considered the largest risk in this proposal. Correct temporal
history under changing spatial aggregation is the critical path for compatible windows,
retrospective parents, privacy checks, contribution accounting and reproducible evaluation.

The plan's immediate next action was Phase 0: establish actual architecture from repository
code without broad changes. The current README and TO-DO specify what has since been audited,
reverted and left pending.
