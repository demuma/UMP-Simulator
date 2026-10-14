# UMP-Simulator — Urban Mobility Privacy Simulator

Research workspace for the dissertation on quantifying privacy and utility in urban
mobility data and adapting spatial and temporal aggregation under regional constraints.

**Status: 2026-10-14. Current work: define and build the missing aggregation pipeline,
metric evaluation and regional policy trees, starting with AGBS. Shared sampling
initialization, single-use ABS batches and local observation assembly are implemented
and regression-tested. Complete typed sensor frames, stable renderer identity routing and
bounded, nonblocking renderer consumption are implemented (S04/S01). S05 now paces
agent-frame consumption independently of producer runtime and displays requested/measured speed. The first A01 slice
now adds optional identity-bearing AGBS input, a dependency-free fixed-window core and
internal JSONL candidates. E04 now adds measured cell metrics, explicit unavailable values
and versioned threshold checks. A04 now compiles immutable regional policy trees from
existing Regions, with strict numeric inheritance and per-cell provenance. A02 now adds
opt-in bounded private history, on-demand ancestor/time reconstruction and logical active/
preemptive bucket records. A local aggregation inspector now visualizes recorded metrics,
regional requirements and check results, with an optional separate MongoDB debug copy.
An initial A03 spatial selector now chooses mixed-depth cells for common fixed windows,
with exact history unions, policy checks, suppression and future-window refinement. The
live renderer and recorded inspector show those internal decisions. An initial standalone
A05 coordinator now tests immutable output, reservations, acknowledgement and future
handover. Policy/pipeline/sink integration and durable recovery remain open, along with
temporal adaptation, actual-interval velocities and research experiments.**

All maintained project documentation is written in English. The conversation may remain
in German. The historical implementation plan is kept as an English reference translation;
its original external file remains unchanged.

## 1. Start here

| Document | Purpose |
|---|---|
| [README.md](README.md) | Project overview, actual capabilities, architecture, data flow, build instructions and limitations |
| [TO-DO.md](TO-DO.md) | Chronological execution queue, dated milestones, task contracts, later extensions and completed work |
| [Publication coordination core](docs/PUBLICATION_COORDINATION.md) | Tested standalone fixed-window reservations and immutable output; integration and durable recovery remain open |
| [Spatial selection and live demo](docs/SPATIAL_SELECTION.md) | Actual private parent/child selection, live overlay, recorded replay, configuration and tested limits |
| [Aggregation inspector](docs/AGGREGATION_INSPECTOR.md) | Ready-to-open meeting demo, recorded cell metrics/thresholds, timeline, optional MongoDB debug copy and reproduction |
| [Bounded history and buckets](docs/AGGREGATION_HISTORY.md) | Implemented A02 private reconstruction, logical windows, resource limits, deadlines and verification |
| [Regional policy tree](docs/POLICY_TREE.md) | Implemented root/type/region inheritance, sparse compilation, conflict semantics and runnable example |
| [Candidate metrics](docs/METRICS.md) | Implemented online metric registry, threshold assessment, configuration and first fixed utility-query contract |
| [Fixed aggregation contract](docs/FIXED_AGGREGATION.md) | Implemented A01 input, count/window semantics, coverage, memory bounds and opt-in configuration |
| [Renderer timing](docs/RENDERER_TIMING.md) | Implemented pacing, requested/measured speed, timing checks and tree/snapshot roles |
| [Sensor frame contract](docs/SENSOR_FRAMES.md) | Implemented typed payloads, step completion, identity routing, queue bounds and validation |
| [Technical audit](docs/STATE_AND_NEXT_STEPS.md) | Source-level findings and the recorded database check |
| [Aggregation design review](docs/AGGREGATION_DESIGN.md) | Configuration/presentation review, bucket semantics, transport, policy trees and metric scheduling before implementation |
| [Bucket lifecycle and release protocol](docs/BUCKET_LIFECYCLE.md) | Detailed planning: state diagram, storage, compiled policies, coordinated releases and renderer correctness |
| [Historical implementation plan](docs/reference/IMPLEMENTATION_PLAN.md) | Reference specification; not an instruction to execute every phase |

Read the current status, then follow TO-DO Section 2 in execution order. Section 5 of
this README explains the current sensor behavior and known limits. Detailed task stages
follow the dated milestones in TO-DO, and completed work is collected at the end. Existing
behavior, verified defects and undecided proposals are explicitly separated. The first
aggregator integration targets AGBS with a reusable core; later simulator extensions have
lower priority.

## 2. Research objective and next milestone

The dissertation addresses two related questions:

1. How does spatial and temporal aggregation change measurable privacy and usefulness
   for a specifically defined urban mobility application?
2. Can local constraints and adaptive spatial/temporal windows achieve a better trade-off
   than fixed aggregation under comparable conditions?

The planned dissertation comparisons now include publication models (final-snapshot,
immediate approved release, bounded hold and visible revisions), preservation priorities,
regional feasibility bounds, and full versus selective precomputation. E06 tracks model/
priority comparisons; E05 tracks preparation cost. Publication models may be selected by
application policy once their behavior is implemented and tested.

**Adopted strategy terminology:** Temporal First prioritizes temporal detail/freshness and
tries spatial aggregation first. Spatial First prioritizes spatial detail and tries temporal
aggregation first. The name identifies the dimension to preserve. Hard bounds still apply;
the spatial-only branch of Temporal First is implemented for fixed windows; full strategy/fallback comparison remains open.

The first application query is now mean sampled occupancy on a fixed 10-m reference grid
over 1-second intervals; [METRICS.md](docs/METRICS.md) defines its reference, reconstruction
assumptions and missing-data treatment. Its GT experiment is still pending. The attacker
model, auxiliary knowledge and empirical privacy evaluation still need binding definitions. A minimum number of contributors per publication is initially
an operational release rule. It does not by itself establish formal k-anonymity or a
reduction in empirical attack success.

**Next milestone: October 14 supervisor meeting.** The main development target is the first
complete aggregation path: observations, cell/window aggregation, initial metrics, effective
regional policy lookup through a minimal policy tree, and release/suppress decisions.
Input checks and demo preparation accompany this work. Simulator startup works and sensor
regression tests passed. Fixed-window aggregation, initial metrics and the minimal regional
policy tree and bounded reconstructable history are implemented. Next are publication
coordination (A05) and temporal/release extensions of A03. Internal spatial selection and its live overlay are now implemented.

The [delivery plan in TO-DO](TO-DO.md#3-delivery-plan-october-14-18-and-25) now prioritizes
that foundation immediately, dynamic spatial release selection and initial comparisons by
October 18, then temporal adaptation and stronger comparative evidence by October 25.
The existing quadtree remains the spatial foundation. Its maximum depth may stay bounded
while the chosen publication cells change according to metrics and policies. The complete
dissertation narrative remains in the presentation; improved empirical privacy is an
experimental question. Paper submission remains due in mid-November and the dissertation
at year-end. See TO-DO for targets, acceptance checks and fallback scope.

## 3. Origin and repository layout

Local repository: `/Users/maxdemu/Developer/UMP-Simulator`.

Moved on 2026-10-09 from `Coding/UrbanMobilityPrivacy` into the user-created
`UMP-Simulator` directory. The repository name is **Urban Mobility Privacy Simulator**.
Git history was preserved; simulation source, configuration and behavior were unchanged.
The original simulator and renderer projects remain in Coding as references.

Open this directory as the VS Code workspace. The included
[UMP-Simulator.code-workspace](UMP-Simulator.code-workspace) opens the repository root.
Imported on 2026-10-08 from the local `Coding` repository at commit
`d1e3dde748c6565ca4a44514d5e9e86016b67de3`.

```text
UMP-Simulator/
├── README.md
├── TO-DO.md
├── .gitignore
├── simulator/                    # Imported from Aggregation_Manager
│   ├── CMakeLists.txt
│   ├── config.yaml
│   ├── include/
│   └── src/
├── renderers/                    # Separate MongoDB playback applications
│   ├── abs/                      # ABS_Renderer_database_V3
│   ├── gbs/                      # GBS_Renderer_database_V3
│   ├── agbs/                     # AGBS_Renderer_database_V3
│   └── gt/                       # GT_Renderer_database_V3
└── docs/
    ├── STATE_AND_NEXT_STEPS.md
    ├── AGGREGATION_DESIGN.md
    ├── BUCKET_LIFECYCLE.md
    └── reference/
        └── IMPLEMENTATION_PLAN.md
```

The original projects remain unchanged. Build artifacts and old VS Code configurations
were excluded. Components are independently buildable; no shared library or root CMake
superproject has been introduced. No remote has been configured.

### Git history and rollback

| Commit | Meaning |
|---|---|
| `96fae5b` | Unmodified import of the simulator and four renderers |
| `ed4dc14` | Initial audit |
| `0ce473f` | Temporary ABS correction and regression tests; no longer active |
| `db2bdbb` | Revert of that correction, preserving history |
| `9f8fde1` | Detailed project documentation and task backlog before translation |

The earlier temporary fix remains reverted. A new sensor correction and opt-in regression
test were committed as d520daf on October 12; startup error reporting followed in 93c5ec3
on October 13. Their verified scope and remaining limits are described below. The old
reverted test results do not establish correctness of the current implementation.

## 4. Actual capabilities

| Area | Present | Missing or limited |
|---|---|---|
| Simulation | Agents, class attributes, movement, regions and configurable timestep | No central seed; movement noise partly depends on wall-clock time |
| Ground truth | Agent identity, position, velocity and timestamp stored in MongoDB | Completeness across all runs and boundary cases not systematically validated |
| ABS | Position, type, identity and velocity from consecutive observations; first complete output at 100 ms for the current 10-Hz setup | Nominal-period velocity requires aligned fixed intervals; publication after DB errors is not guaranteed |
| GBS | Fixed cells, class counts and total count per observation | No full temporal aggregation or privacy-based release decision |
| AGBS | Quadtree, position mapping, counts and cell IDs | Splitting follows positions/max depth, not metrics or policies |
| AggregationManager | Optional AGBS ingestion, fixed windows, contributor unions and JSONL candidates assessed against uniform or regional requirements | Internal spatial selection is opt-in; no approved public releases or temporal extension |
| Regional rules | Immutable sparse PolicyTree; explicit root/type/region metric requirements, strict numeric inheritance and footprint conflicts | Aligned, non-overlapping rectangles only; legacy granularity/k/l fields inactive; no action/model selection or live updates |
| Temporal history | Opt-in bounded sample history; exact ancestor/time queries and logical active/preemptive windows with finite deadlines | Private reconstruction only; no automatic preparation, release reservations or commit-driven invalidation |
| Rendering | Combined typed frames, nonblocking pairing, bounded queues and dated latest-measurement AGBS geometry and independent playback pacing; four V3 DB renderers | Live spatial overlay and offline replay implemented; collecting/preemptive/release lifecycle views and long-run tests remain open |
| Evaluation | Online metric registry, uniform/regional threshold assessments and a defined first occupancy-query baseline | GT utility experiment, independent attacker evaluation and comparative baselines remain open |
| Movement | Start/target, straight-line waypoints, noise and collision avoidance | No street routing; TTC/lookahead behavior not validated |
| Taxonomy | Type, behavior, appearance and distribution in one configuration | Strong coupling; modular redesign not yet specified |

Existing source does not imply all edge cases are correct. Adaptive aggregation and
core research evaluation remain pending. Fixed candidates are internal research data,
not privacy-approved publications.

## 5. ABS timestamps, velocity estimation and duplicate writes

### 5.1 Do GT and ABS describe different times?

In the current simulator, Simulation::run/update follows this sequence:

```text
State X(t), timestamp t
    → store GT and copy the agent snapshot
    → increment simulationTime internally; timestamp still remains t
    → sensors observe X(t) with timestamp t; assemble the complete sensor frame
    → publish a combined sensor frame only if at least one sensor measured
    → set timestamp to t + dt and move agents to the next state
    → expose the copied agent snapshot for t; this confirms sensor processing is complete
```

On this path, matching timestamps describe the same position state. Requiring a second
observation for velocity does not require shifting the position timestamp. Different sensor
frequencies may produce different observation timestamp sets; ABS need not publish every GT tick.

The initial broad claim of a universal GT/sensor time shift was corrected. Matching positions
and timestamps were also verified for the example agent in the existing database.

### 5.2 Current sampling and initial observations

All three sensors use Sensor::isSamplingDue(timeStep). The first update observes the
initial state and initializes the schedule without adding elapsed time. Later updates
add the completed simulation step. A due observation resets the timer regardless of
whether any agents are in the area.

| State time, relative to initial observation | ABS | GBS / AGBS |
|---|---|---|
| 0 ms | Retain initial positions internally; no output | Initialize schedule; no output |
| 50 ms | No capture | No capture |
| 100 ms | Capture; estimate over 0–100 ms | Count current occupancy |
| 150 ms | No capture | No capture |
| 200 ms | Capture; estimate over 100–200 ms | Count current occupancy |

This table assumes the current 50-ms simulation step and 10-Hz sensor configuration.
Time zero means the first state seen by that sensor, not the system clock epoch.
ABS owns its initial-position capture in its first update; Simulation no longer seeds
previousPositions by accessing the derived sensor's state during construction.

GBS/AGBS keep their existing DB output policy: an entirely empty area writes no count
documents. The combined frame now contains an identified empty payload for a due empty
measurement. When no sensor is due, no sensor frame is sent; the subsequent agent frame
confirms that sensor processing is complete. A newly populated area is counted on the next
scheduled sample. Public Empty/Suppressed/Unavailable semantics remain D03;
the internal frame states are defined in [Sensor frames](docs/SENSOR_FRAMES.md).

### 5.3 One velocity calculation and the new-agent rule

captureAgentData checks each observed identity against previousPositions, records the
current position for the next observation, and publishes only identities with both positions.
The velocity calculation is:

```cpp
observation.estimatedVelocity = (agent.position - previous->second) * frameRate;
```

This is an interval average, not the instantaneous GT velocity at the endpoint. It is
correct when consecutive samples are exactly 1/frameRate apart. The initial schedule
now satisfies that condition for 50-ms ticks and 10-Hz sensors. No agent timestamps are
read to calculate this velocity. Non-aligned periods, varying steps and irregular
observations still require the actual-interval work in F01/D02; the timer currently resets
to zero at a due sample and does not implement fractional-period scheduling.

An unknown identity's first position is retained internally; its first complete ABS record
appears on the next consecutive sensor observation. An agent absent at a scheduled
observation is removed from the previous-position set. Reentry then requires two observations
again. A valid zero velocity means the observed position did not change over that interval.
Agents entering and leaving between samples may be unobserved. GBS/AGBS count a newly observed
agent immediately, so their counts need not equal the number of complete ABS records.

The unused Sensor::estimateVelocities method and ABS estimatedVelocities map were removed.
There is now one calculation feeding the BSON field instead of two independent calculations.

### 5.4 Local assembly and retained output

The former class member agentData was unnecessary shared working state. captureAgentData
now assembles a local vector called observations, then moves it into dataStorage.
postData reads that output vector through a local reference called pendingObservations.
These names no longer conceal a class member with the same name.

ABS dataStorage remains a pair of timestamp and observation vector, not a vector of batches.
The pair itself has no clear()/empty() methods. The applicable operations are
dataStorage.second.clear() and dataStorage.second.empty(). GBS/AGBS use vectors of
batches, which explains their different clear()/empty() syntax.

printData reads the pending output batch. Call it before postData if the records should
be printed; successful publication consumes that batch.

### 5.5 Successful ABS publication consumes the batch

Simulation still calls postData after every sensor update. ABS now clears dataStorage.second
immediately after insert_many returns successfully. Non-capture ticks and additional
postData calls therefore cannot reinsert that successful batch.

| State time | New ABS capture? | Effect of postData after a successful preceding write |
|---|---|---|
| 0 / 50 ms | No | No agent records |
| 100 ms | Yes | Insert, then clear output vector |
| 150 ms | No | Output vector empty; no insert |
| 200 ms | Yes | Insert new batch, then clear |

On a MongoDB exception the vector remains available for another attempt before the next
capture. The next capture replaces the pending batch, so this is not a durable retry queue.
An ambiguous/partial insert_many failure can already have persisted some records; retrying
may duplicate them. No idempotent-write or exactly-once guarantee is implemented. These
failure cases were documented, not injected in the current regression test.

The baseline bug had cleared only the working vector and retained the already-written
output vector. The historical database check below records that old behavior; existing
Simulation data has not been repaired or replaced.

**The prototype aggregator is not involved.** ABS does not invoke AggregationManager.
AGBS now optionally invokes its fixed-window manager on a separate internal path; it does not rewrite or combine raw ABS records.

### 5.6 Historical baseline database check

The pre-fix read-only inspection of localhost:27017, database Simulation, agent
`C0B64FE1-740C-486C-A2D1-00E030269E71`:

| Check | Result |
|---|---:|
| GT records in Agents | 200 |
| ABS records | 199 |
| Distinct ABS sensor observation timestamps | 100 |
| ABS records without matching GT timestamp | 0 |
| Position mismatches at matching identity/time | 0 |
| Duplicate keys: sensor ID, agent ID, timestamp | 99 |
| Additional records from these duplicates | 99 |
| Conflicting contents within duplicate groups | 0 |

First ABS timestamp: 2025-04-09T09:30:00.050Z. Over the preceding 50 ms, GT positions imply
(5.105896, 1.291370) m/s; ABS stores (2.552948, 0.645685) m/s. The following 99 distinct
ABS velocities match displacement divided by their actual 100-ms intervals.
This validates one agent in this dataset, not all agents or runs.

Instantaneous GT velocity and interval-based ABS velocity are different quantities. An agent
may already be stopped at the interval endpoint despite movement within the preceding interval.
Compare velocities over the same interval rather than requiring endpoint equality.

## 6. Architecture: baseline versus proposals

### Current data flow

```text
Simulation thread
  ├── agent state → GT / MongoDB
  ├── ABS → position / velocity / MongoDB
  ├── GBS → fixed-cell counts / MongoDB
  ├── AGBS → quadtree-cell counts / MongoDB
  │        └── optional ID/cell batches → fixed-window manager → metric evaluator → research JSONL
  │                                      └── optional history + spatial selector → private cut/diagnostics
  │                                                                              └── immutable live overlay
  └── complete typed sensor frame + matching agent snapshot → bounded queues → renderer

Separate V3 renderers → read stored data from MongoDB
```

### Implemented fixed aggregation and the remaining adaptive path

An enabled simulation AGBS owns one manager; rendering instances do not instantiate it.
Its adapter copies IDs, types and leaf geometry in the existing capture pass. The core uses
only standard C++ and accepts values through ingest/advance/finish, without a tree reference,
MongoDB coupling, renderer queue access or additional thread. An external synchronous sink
writes candidate JSONL. See the [concrete contract](docs/FIXED_AGGREGATION.md).

Counts explicitly distinguish observation contributions, distinct contributors and sample
mean occupancy. Stream distinct counts union IDs across cells. The core tracks measured,
missing and unavailable samples, closes fixed half-open windows even on non-sampling ticks,
and marks truncated final intervals. One active window and an observation budget bound
retained state. Output contains no individual IDs; it is still internal research data.

The metric evaluator now computes per-cell support, contribution counts, sample occupancy,
geometry, duration, age, post-window delay and sample coverage. An optional versioned uniform
policy or regional PolicyTree supplies min/max requirements. Root, region type and Region
instance constraints intersect; a regional child cannot weaken its inherited rules.
Missing reference-dependent metrics are explicitly unavailable;
incomplete coverage prevents a successful overall assessment. The writer only serializes
the candidate and assessment. See [METRICS.md](docs/METRICS.md) for meanings and units.

This first mode uses configured leaf depth and a fixed time window. Its threshold assessments
alone do not implement empirical privacy measurement or release approval. The optional
[spatial selector](docs/SPATIAL_SELECTION.md) adds private sibling merges, suppression and
refinement at later fixed-window boundaries. Publication coordination remains separate. Its accumulator identity sets are discarded
when a fixed window closes. With A02 history enabled, owned fine observations remain for a
bounded horizon and can reconstruct ancestors or extended/offset intervals. Logical active/
preemptive records share that history and never publish independently. See
[AGGREGATION_HISTORY.md](docs/AGGREGATION_HISTORY.md). Geometry, history,
policy evaluation and public release state remain separate responsibilities.

A static spatial hierarchy with a dynamic release view is a plausible design. A fully
materialized maximum-depth tree is not yet a requirement. The existing tree starts with
four base cells and has its own cell-ID/depth conventions.

### Renderer pacing and quadtree display

The live renderer uses a monotonic playback clock. At the current 50-ms simulation step,
1x requests 20 new agent frames per second; the 10-Hz sensor cadence remains separate.
Producer delays and expensive drawing lower measured speed without rewriting the requested
speed. Pause, source gaps and overload do not cause catch-up bursts or dropped observations.
The overlay distinguishes Agent FPS from redraws and requested from measured playback speed.
See [RENDERER_TIMING.md](docs/RENDERER_TIMING.md) for controls, optional timing logs and limits.

The simulation AGBS and renderer own separate Quadtree instances. Timestamped sensor cell
data travels through the queue; the renderer reconstructs geometry only when its cell-ID
set changes. QuadtreeSnapshot is an unused legacy node type, not an active tree-copy path.

### SharedBuffer

read removes one frame from a queue. Two independent readers would consume different
frames. A fixed access count of three does not implement broadcast. Reference counts describe
object lifetime, not completed processing.

Initially keep aggregation in the simulation thread. Shared buffers are needed at actual
thread boundaries. Rendering may use the newest snapshot, whereas evaluation/persistence
may require every batch. Define these requirements before changing transport or adding threads.

## 7. SFML, Metal and related projects

### Existing projects and historical evidence

This simulator and the V3 renderers use C++17, SFML 3, yaml-cpp and the MongoDB C++ driver.
Aggregation_Manager has no native Metal backend. Coding/Metal-Simulator requests an
OpenGL 2.1 context and tests background colors, immediate-mode triangles and VBO rendering.
It prints OpenGL version/renderer/vendor information despite its Metal-related name.

Its introduction commit in Coding is `438fe33`, dated 2025-10-25, with the message
“added test environment for a metal-based simulator”. This supports interpreting it as an
early graphics/system test in a Metal-oriented exploration. It does not establish native
Metal API usage in the retained source, or prove a direct code lineage to Modern.

The separate project /Users/maxdemu/Developer/UAM-Simulator-Modern directly links Cocoa,
Metal, MetalKit and QuartzCore and uses Objective-C++. Its README describes a C++ core,
sensor snapshots and native 3D rendering. Its visible local Git history begins on 2026-06-28;
that is the first retained commit, not proof of its actual project creation date.

The Modern README and TO-DO serve as documentation references: current milestone,
build/run, export behavior, limitations and next steps. No renderer, map or sensor geometry
code has been imported from Modern.

### SFML versus native Metal for this project

SFML is a C++ multimedia/windowing library; Metal is a graphics and compute API. Replacing
SFML therefore also requires deciding how windowing, input, text and presentation will work.
Modern already contains part of that Apple-specific infrastructure.

| Criterion | Current SFML path | Native Metal path |
|---|---|---|
| Immediate effort | Existing 2D application and playback renderers remain usable | Port/reuse rendering, window/input and overlays |
| Platform coverage | SFML supports macOS, Linux and Windows | Native Apple-platform backend; other platforms need another backend |
| Graphics scope | Convenient 2D visualization; current macOS Graphics path uses legacy OpenGL | Direct GPU control for custom 2D/3D pipelines |
| Maintenance on macOS | Relies on Apple's deprecated OpenGL API | Apple's current native graphics/compute API |
| Compute | Changing renderer does not move simulation/aggregation to GPU | Compute is possible, but requires dedicated kernels and suitable data layouts |
| Existing assets | Current SFML views and shapes | Modern offers city/terrain/drone rendering as a potential reference |
| Research benefit now | Adequate for inspecting cells, agents and experiments | Benefit depends on concrete 3D/sensor needs or measured GPU bottlenecks |

Sources: [SFML overview and platforms](https://www.sfml-dev.org/faq/general/),
[SFML 3.0 OpenGL integration](https://www.sfml-dev.org/tutorials/3.0/window/opengl/),
[Apple Metal overview](https://developer.apple.com/metal/) and
[Apple's OpenGL deprecation notice](https://developer.apple.com/library/archive/documentation/GraphicsImaging/Conceptual/OpenGL-MacProgGuide/opengl_intro/opengl_intro.html).

**Current recommendation, not an implemented migration:** retain SFML for the first
privacy/utility comparison. Keep Metal as a viable later visualization/backend option,
using Modern as a reference. Measure simulation, DB I/O and rendering separately first.
Changing the renderer alone does not fix duplicate writes, improve movement realism or
accelerate CPU aggregation. A headless evaluation path reduces dependence on either backend.

## 8. Build and operation

### Dependencies

C++17 compiler, CMake, SFML 3, yaml-cpp and mongocxx/bsoncxx. This machine successfully
built the import with SFML 3.0.2. Existing CMake files contain Homebrew paths; full
portability has not yet been configured.

### Build the simulator

From the repository root:

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release
cmake --build simulator/build -j4
```

### Build a database renderer

```sh
cmake -S renderers/abs -B renderers/abs/build -DCMAKE_BUILD_TYPE=Release
cmake --build renderers/abs/build -j4
```

Replace abs with gbs, agbs or gt for the other applications. Each target is named Visualizer,
so the renderers remain separate CMake projects for now.

### Run history, policy, metric, playback, aggregation, frame and sensor regression tests

HistoryRegressionTests is enabled by default (UMP_BUILD_HISTORY_TESTS), uses standard C++
only, and checks exact unions, asynchronous windows, empty/missing support, expiration,
budget failures and an independent geometry/time replay oracle. SensorRegressionTests
also verifies reconstruction from actual AGBS observations across fixed-window closure:

```sh
ctest --test-dir simulator/build -R history_regression --output-on-failure
```


PolicyRegressionTests and PolicyConfigurationTests are enabled by default
(UMP_BUILD_POLICY_TESTS). The former uses standard C++ only; the latter links YAML and
Region/SFML types. Both run without a window or MongoDB and check inheritance, footprint
conflicts, sparse compilation, input validation and compatibility:

```sh
ctest --test-dir simulator/build -R 'policy_' --output-on-failure
```

PlaybackRegressionTests is enabled by default (UMP_BUILD_PLAYBACK_TESTS). It checks
monotonic pacing and identical frame replay through bounded queues without a window or DB:

```sh
ctest --test-dir simulator/build -R playback_regression --output-on-failure
```

MetricRegressionTests is enabled by default (UMP_BUILD_METRIC_TESTS) and uses standard C++
only. It verifies hand-computed values, units, inclusive/invalid bounds, unavailable inputs,
coverage gates and the difference between window duration and age at evaluation:

```sh
ctest --test-dir simulator/build -R metric_regression --output-on-failure
```


AggregationRegressionTests is enabled by default (UMP_BUILD_AGGREGATION_TESTS). Its core
and test executable depend only on standard C++:

```sh
ctest --test-dir simulator/build -R aggregation_regression --output-on-failure
```

It checks distinct unions across time/cells, half-open boundaries, zero-versus-missing data,
partial/no-sample intervals, stream/cadence validation, budget failures and state bounds
across 100 windows. The simulator's CMake configuration still locates the application
dependencies; the core can alternatively be built directly with a C++17 compiler.


FrameRegressionTests is enabled by default and needs neither MongoDB nor a window:

```sh
ctest --test-dir simulator/build -R frame_regression --output-on-failure
```

It verifies pairing, multi-ID routing, no-sample steps without placeholder frames, pause,
chronological validation, bounded concurrent FIFO consumption and shutdown. Sparse two-queue
runs cover long gaps and an entirely unsampled run without waiting for a sensor frame.
Grid-display checks verify initial waiting, geometry retention on non-sampling ticks,
separate sensor ages, measured-empty clearing and no accumulation of obsolete cell IDs.
Exact-step measurement selection still clears missing samples; only dated geometry persists.
Disable it with UMP_BUILD_FRAME_TESTS=OFF only when a build without the test executable
is specifically needed.

The sensor integration test remains opt-in:

The opt-in test requires MongoDB on localhost:27017. It creates a fresh
UMP_sensor_regression_<UUID> database and removes only that database on normal exit.
It does not load simulator/config.yaml or use the existing Simulation database.

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release -DUMP_BUILD_SENSOR_REGRESSION_TESTS=ON
cmake --build simulator/build -j4
ctest --test-dir simulator/build --output-on-failure
```

The test checks known motion, first capture, repeated ABS publication, new identities,
reentry, empty areas, grid counts, combined frame timestamps and two AGBS at different rates.
Both AGBS now also feed independent fixed-window managers; the test verifies their candidate
contributions, distinct IDs, empty-sample completeness and final partial interval.
Actual quadtree reconstruction is checked against the captured cell bounds; intermediate
ticks preserve subdivisions and measured-empty samples restore the four base cells.
Normal builds leave the MongoDB integration target disabled. A force-killed test may leave its isolated database for cleanup.

The live AGBS overlay shows the latest measured geometry with a sample-age label. Before
the first observation it shows the base grid and a waiting label. The current 10-Hz sensor
first observes at 100 ms, then refines only observed branches. A non-sampling 50-ms agent
tick does not clear that geometry. An actual empty measurement clears its subdivisions.
This display policy does not invent measurements or feed held values into aggregation.

Optional transport settings: sensors[].id provides a stable configured identity; otherwise
Main generates a UUID once per run. renderer.buffer_capacity defaults to 128 frames per
queue and must be positive. Headless runs do not enqueue render frames. See the
[frame contract](docs/SENSOR_FRAMES.md) for payloads and exact empty-step behavior.

### Enable the fixed aggregation foundation

Aggregation is opt-in; the maintained config.yaml is unchanged. Add the documented
`aggregation` block to an AGBS entry in an experiment copy of config.yaml; see
[configuration and semantics](docs/FIXED_AGGREGATION.md#configuration). For the current
10-Hz AGBS, a 1000-ms window is a suitable functional demonstration parameter. Its existing
80-m square area and 40-m base-cell size satisfy the adapter's coverage requirement.

Each enabled stream prints the path to a new `results/aggregation/candidates-<UUID>.jsonl`
file. Schema `ump.fixed-candidate.v3` records per-cell metric values/units, a coverage gate,
individual threshold checks, policy mode, effective policy IDs and contributing rule sources.
Omitting both `metric_policy` and `policy_tree` produces `not_configured`; choose at most one.
Uniform checks use the block in [METRICS.md](docs/METRICS.md#configuration-and-diagnostic-output);
regional configuration and conflict behavior are in [POLICY_TREE.md](docs/POLICY_TREE.md).
The results can be inspected immediately but are not public releases or evidence of privacy
improvement. Normal raw MongoDB output continues separately. The original sensor areas
remain adjacent: align them in an evaluation configuration before comparing sensor types.

### Run the regional policy example

After building, run the complete [example configuration](simulator/examples/regional-policy/config.yaml):

```bash
cd /Users/maxdemu/Developer/UMP-Simulator/simulator/examples/regional-policy
../../build/Simulator
```

This runs a two-second headless AGBS demonstration with a default/root policy, two
regional policies and a 2000-ms private history, using MongoDB database `UMP_PolicyTree_Demo` with clearing disabled.
Each invocation appends raw data and creates a separate candidate JSONL file under that
directory's `results/aggregation`. It does not use the maintained `Simulation` database.
The west region requires at least five contributors; the northeast permits at most 200-ms
windows, deliberately failing the configured fixed 400-ms candidates. Inspect each cell's
`policy`, `checks` and `threshold_status`. These demonstrate assessment, not adaptive correction.
Set `renderer.show_renderer: true` in the example to show the ordinary sensor grid; policy
selection is disabled in that example. Use the spatial example below for the new overlay.
The example has no shared random seed and is not
a comparative research experiment.

### Inspect aggregation metrics and regional thresholds

The prepared supervisor demo opens directly as a local file:

```sh
open results/demos/aggregation-inspector.html
```

It contains 30 actual 400-ms windows from a separate 12-second, 200-agent run. Select a
cell to see metric values, applied bounds and policy sources; use the timeline or Play
to inspect changes. The example buttons select support failure, duration failure and
passing cases. The same recording is available in local MongoDB under
`UMP_Debug_AutSys.aggregation_candidates` (internal diagnostics only).

The [inspector guide](docs/AGGREGATION_INSPECTOR.md) provides a three-minute walkthrough,
input/output paths and the Python report/export command. Generated recordings remain
local under ignored `results/`; the builder and template are versioned. This is recorded
fixed-candidate assessment. For the newer mixed-depth selection use
`results/demos/spatial-inspector.html`, described below.

### Show actual spatial aggregation in the live renderer

```sh
cd /Users/maxdemu/Developer/UMP-Simulator/simulator/examples/spatial-selection
../../build/Simulator
```

This separate example enables private spatial selection and the live overlay. **G** toggles
the overlay; **Space** pauses/resumes. Green cells are selected, orange cells became coarser,
blue cells became finer and red footprints are suppressed. Fine sensor boundaries remain
visible underneath. Counts and the last closed window are labelled explicitly.

The [spatial selection guide](docs/SPATIAL_SELECTION.md) explains the algorithm and limits.
`results/demos/spatial-inspector.html` provides recorded before/after comparison and buttons
for the next coarsening/refinement. These are real metric/policy decisions on common fixed
windows; they remain internal diagnostics until A05 supplies public-release coordination.

### Configuration and startup

Applications load config.yaml relative to their working directory. Run each from its
component directory. After reviewing the database configuration, the simulator command is:

```sh
cd simulator
./build/Simulator
```

Starting ./simulator/build/Simulator from the repository root does not change the working
directory and therefore cannot find simulator/config.yaml. Startup config errors now print
to stderr even when optional ERROR logging is disabled (corrected on 2026-10-13).

The unmodified simulator configuration sets clear_database: true and targets Simulation.
Its initialization deletes the configured GT and sensor collections. A new run must not
accidentally replace the inspected reference series. Choose a separate experiment database
and appropriate settings before running. Documentation work has not changed configuration.

For a database renderer, run ./build/Visualizer from its directory. Review its configuration
and initialization path before use as well. Font paths are still macOS-specific.
show_renderer: false disables the window, but not DB I/O or snapshot production.

### Selected simulator controls

From the existing source; not revalidated interactively here:

| Key | Effect |
|---|---|
| Space | Pause/resume playback |
| Left / Right | Change playback speed |
| R | Reset playback speed to 1 |
| A / B / C | Toggle direction arrows / buffer zones / collision grid |
| S | Toggle sensor display |
| T / W | Toggle trajectories / waypoints |
| Esc / Q | Close the window and set the stop flag |

Pausing playback does not necessarily pause the simulation thread.

## 9. Verification and limitations

The unmodified simulator and all four renderers previously built successfully in Release
mode; 101 imported component files matched their originals. The historical MongoDB
inspection was read only and establishes the baseline findings for the example agent.

On 2026-10-12 the corrected simulator and SensorRegressionTests built in Release mode.
CTest passed its MongoDB integration test with a non-epoch initial timestamp, constant
known movement, repeated postData calls, empty scheduled observations and entry/reentry.
It verified ABS identity/position/time, interval velocity and unique measurement keys,
GBS/AGBS per-time occupancy, and AGBS renderer cadence. The isolated test database was
removed. The full simulator was not run; existing Simulation data and configuration
were not modified. This test is not full-run or all-configuration validation.

Actual-interval velocities, non-aligned scheduling and DB failure recovery remain open.
SharedBuffer shutdown and bounded transport were corrected under S04/S01. Remaining
findings include missing shared seeds, wall-clock noise, collision-grid bounds/pointers
and quadtree ownership. See the audit and task list for priorities and remaining verification.

On 2026-10-13, the A01 Release build and all three CTest suites passed. A full one-second
headless run used an isolated UUID-named database, 20 GT steps, two AGBS at 10/5 Hz and
400-ms windows. Its six output windows matched sampled GT identities/contributions and raw
AGBS contributions per window and cell; no contributor IDs appeared in JSONL. The fixture
used equal 80-m sensor areas in a temporary config. Test databases were removed. The existing
Simulation database and maintained config were not modified. This is functional validation,
not a performance benchmark, manual GUI check or empirical privacy result.

The subsequent grid-flicker correction passed all three CTest suites. A windowed test
additionally exposed an existing MongoDB instance/client destruction-order defect, now
corrected so the driver outlives the client. Isolated full runs with and without a window
then exited successfully without stderr. The UI tool could not select the standalone
Simulator window, so direct visual/pause/resume inspection remains open.

The E04 metric slice subsequently passed all four CTest suites and a full isolated
headless run. Four AGBS policies produced twelve windows exercising pass, fail, unavailable
reference and no-policy outcomes; numeric metrics/checks matched their candidate data.
Unknown YAML metrics fail explicitly at initialization. No maintained YAML or existing
Simulation data was changed. This E04 verification preceded the regional implementation below;
GT/attacker evaluation remains open.

A04 subsequently passed all seven CTest suites, including the two new policy suites and
the existing MongoDB sensor regression. The standard-C++ policy core also built with
`-Wall -Wextra -Werror`. A full regional run checked five windows and 308 cell assessments
against independently derived regional bounds and provenance. Nine invalid configurations
failed before database clearing or metadata writes, verified with a disposable sentinel.
A further four-stream run checked twelve v3 windows for uniform and absent-policy compatibility.
Only UUID-named test databases were used and removed. The normal simulator build was updated.
These are functional checks; regional policy runtime/memory benchmarks and empirical privacy
or utility improvements have not been measured. See [POLICY_TREE.md](docs/POLICY_TREE.md).

On 2026-10-14 SharedBuffer comments and DEBUG_MSG traces were restored against the current
FIFO behavior. The frame suite passed with DEBUG enabled. A02 passed all eight suites and
strict standard-C++ compilation. Its replay oracle checked 1,200 queries over 300 steps;
retention stayed within five bins/twenty observations in that fixture. AGBS integration
reconstructed nine contributions/two distinct contributors across three closed windows,
including measured-empty samples. The full history-enabled example produced five windows
with 316 independently checked regional cell assessments; fourteen startup failures preserved
a disposable database sentinel. Only test databases were used and removed. The normal build
was updated. These are correctness checks, not a performance or privacy/utility experiment.

The offline A06 inspection slice was verified on a separate 12-second simulation with
30 windows and 1,725 cell assessments; the regional bounds were independently checked.
The 30-window MongoDB debug copy matched the capture totals. Five Python builder checks
passed, JavaScript syntax was checked and Safari interaction verified local-file loading,
cell selection, timeline navigation and playback completion. No simulator C++ behavior
was changed for this tool. See [AGGREGATION_INSPECTOR.md](docs/AGGREGATION_INSPECTOR.md).

The subsequent A03/A06 spatial slice passed all nine CTest suites, including exact union,
merge/refine/merge, whole-sibling replacement, missing evidence, policy conflicts and bounded
search checks. A 75-window capture verified non-overlap and contribution conservation and
recorded both coarsening and refinement. Native live-renderer and Safari interaction were
checked. See [SPATIAL_SELECTION.md](docs/SPATIAL_SELECTION.md) for scope and evidence.

## 10. Working process

1. Document existing behavior and add new evidence to TO-DO.md.
2. Select one small change and state its expected effect.
3. Implement only what that change requires.
4. Perform an appropriate reproducible check and record results and limits.
5. Update README status and TO-DO acceptance in the same step.

Keep baseline behavior, findings, proposals and implemented behavior distinct. Maps,
complex routing, broad taxonomy redesign and GPU optimization remain visible in the
backlog but do not block the first defensible data comparison.

The S05 playback correction passed all five CTest suites and three full windowed runs
at 0.5x/1x/2x. Small-fixture measured FPS was 9.970/19.900/39.010 for 10/20/40 targets,
with all frames consumed and requested speeds preserved. Native interaction and long-run
load verification remain open; these results do not establish general real-time capacity.
