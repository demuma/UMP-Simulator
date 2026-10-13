# UMP-Simulator — Urban Mobility Privacy Simulator

Research workspace for the dissertation on quantifying privacy and utility in urban
mobility data and adapting spatial and temporal aggregation under regional constraints.

**Status: 2026-10-13. Current work: define and build the missing aggregation pipeline,
metric evaluation and regional policy trees, starting with AGBS. Shared sampling
initialization, single-use ABS batches and local observation assembly are implemented
and regression-tested. Complete typed sensor frames, stable renderer identity routing and
bounded, nonblocking renderer consumption are implemented (S04/S01). The first A01 slice
now adds optional identity-bearing AGBS input, a dependency-free fixed-window core and
internal JSONL candidates. Policy trees, adaptive buckets and privacy release decisions
remain open, as do actual-interval velocities and reproducible research experiments.**

All maintained project documentation is written in English. The conversation may remain
in German. The historical implementation plan is kept as an English reference translation;
its original external file remains unchanged.

## 1. Start here

| Document | Purpose |
|---|---|
| [README.md](README.md) | Project overview, actual capabilities, architecture, data flow, build instructions and limitations |
| [TO-DO.md](TO-DO.md) | Chronological execution queue, dated milestones, task contracts, later extensions and completed work |
| [Fixed aggregation contract](docs/FIXED_AGGREGATION.md) | Implemented A01 input, count/window semantics, coverage, memory bounds and opt-in configuration |
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
these are specified strategies, not completed implementations.

The attacker model, auxiliary knowledge, application query and evaluation metrics still
need binding definitions. A minimum number of contributors per publication is initially
an operational release rule. It does not by itself establish formal k-anonymity or a
reduction in empirical attack success.

**Next milestone: October 14 supervisor meeting.** The main development target is the first
complete aggregation path: observations, cell/window aggregation, initial metrics, effective
regional policy lookup through a minimal policy tree, and release/suppress decisions.
Input checks and demo preparation accompany this work. Simulator startup works and sensor
regression tests passed. The fixed-window aggregation foundation is implemented; metric-driven
release decisions and the regional policy tree are the next missing components.

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
| AggregationManager | Optional AGBS ingestion, fixed windows, distinct contributor unions, sample occupancy and separate JSONL candidates | No policy checks, approved releases, merges or temporal extension |
| Regional rules | YAML/Region fields for granularities and k/l thresholds | No active policy evaluation, conflict handling or policy trees |
| Temporal history | Bounded active-window identity sets and counts | No reconstructable history, preemptive buckets or variable aggregation windows |
| Rendering | Combined typed frames on measurement steps, stable per-sensor routing, nonblocking pairing and bounded queues; four V3 DB renderers | Manual visual/long-run checks and policy-driven aggregation overlay remain pending |
| Evaluation | Earlier experiments in Data_analysis outside this import | Metric semantics, independent attacker evaluation and fair baselines missing |
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
  │        └── optional internal ID/cell batches → fixed-window manager → research JSONL
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

This first mode uses configured leaf depth and a fixed time window. It does not implement
privacy checks, suppression, release approval, regional policies, merges/splits or preemptive
history. Its identity sets are discarded when a window closes; A02 must add reconstructable
history before adaptive candidates can reuse those observations. Geometry, history,
policy evaluation and public release state remain separate responsibilities.

A static spatial hierarchy with a dynamic release view is a plausible design. A fully
materialized maximum-depth tree is not yet a requirement. The existing tree starts with
four base cells and has its own cell-ID/depth conventions.

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

### Run aggregation, frame and sensor regression tests

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
Normal builds leave the MongoDB integration target disabled. A force-killed test may leave its isolated database for cleanup.

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
file. Rows contain exact windows, completeness, stream/cell counts and sample means. This
output can be inspected immediately but is not a public release or evidence of privacy
improvement. Normal raw MongoDB output continues separately. The original sensor areas
remain adjacent: align them in an evaluation configuration before comparing sensor types.

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

## 10. Working process

1. Document existing behavior and add new evidence to TO-DO.md.
2. Select one small change and state its expected effect.
3. Implement only what that change requires.
4. Perform an appropriate reproducible check and record results and limits.
5. Update README status and TO-DO acceptance in the same step.

Keep baseline behavior, findings, proposals and implemented behavior distinct. Maps,
complex routing, broad taxonomy redesign and GPU optimization remain visible in the
backlog but do not block the first defensible data comparison.
