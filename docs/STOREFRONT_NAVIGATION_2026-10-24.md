# Storefronts, boundary sources and native pedestrian navigation

Date: 2026-10-24. This document describes the implementation and its reproduction
contract. The [test report](STOREFRONT_NAVIGATION_TEST_REPORT_2026-10-24.md)
records completed native, independent and browser acceptance gates.
A completed generator or compilation is not evidence of completed trips, realistic demand, privacy protection or deadlines.

## Purpose and scope

The earlier `buildings` fixture exercises two exact synthetic wall-midpoint doors
on fixed checked access branches. `storefronts` keeps that reference and adds
separate shop destinations, individual map-edge endpoints and native local motion.
The maintained C++ Simulator remains the source. Python preprocesses the frozen
map and requests; it does not generate a replacement sampled motion stream.

The domain remains 80 × 80 m. AGBS D6 leaves remain 1.25 × 1.25 m. The source route
and native replan grids are 0.5 m: they are navigation infrastructure and do not
change the sensor's quadtree, published cell geometry or PolicyTree.

The implemented scene is a finite synthetic pedestrian cohort on derived real-map
geometry. Road/cycling geometry is displayed, but there are no new cycling or
motor-traffic actors. No shop demand, visit duration, equipment behavior or traffic
flow is claimed to be calibrated to the real street.

## Buildings, shops and exact entrances

The cached snapshot contains one original Rappolthaus building footprint holding
four POIs: Apollo, Ditsch, Adidas Originals and H&M HOME. The implementation keeps
that shared physical footprint and assigns each POI a separate destination.

For each selected POI, the generator considers original exterior wall segments,
projects the POI onto them and requires an in-domain accessible approach. It rejects
crop-border edges, projections too near a wall endpoint, blocked approaches and
unreachable targets. The modeled opening is 1.2 m wide and the public approach
extends 1.5 m along the outward facade normal. The exact point is a synthetic
scenario target, not a surveyed entrance or a claim about access permission.

Adjacent modeled shop fronts meet halfway between their door arclengths along the
connected original facade. Frontage polylines retain real wall joints instead of
drawing chords across them. Short 1.1-m inward dashed ticks mark assumed frontage
divisions. They do not create known internal walls or separate OSM buildings.

An optional `--shop-overrides FILE` replaces selected projected points. Its closed
schema binds overrides to the exact frozen source geometry hash:

```json
{
  "schema": "ump.shop-entrance-overrides.v1",
  "source_geometry_sha256": "afa2690e408f467af5ff679770bf872816cc568714d9171cf4efb493809e40ed",
  "entrances": [
    {"poi_osm_id": 10771056021, "point": [10.100691974047042, 73.40106582813941]}
  ]
}
```

This example retains the generated Apollo point; it is not a real-door assertion.
Overrides must still lie on reachable original walls, fit their opening and retain
distinct ordered shop fronts. They are identified as `manual_original_facade_override`.
An override does not edit OSM. A new frozen map hash requires a reviewed override.

## Functional zones, obstacles and boundary intervals

The generator reuses the existing derived walking, road, cycling and building
geometry, including its declared width assumptions. These are processed map
features, not surveyed kerb geometry. Buildings remain obstacles.

Walking space is conservatively eroded by a 0.55-m body-plus-clearance radius,
with a small numerical margin. Domain-edge padding permits bodies to be partly
outside the open map boundary during admission and exit; it does not erase actual
building obstacles beyond that edge. Narrow declared facade transitions admit an
intentional visitor's center to its exact door. The runtime prevents unrelated
tracks from using another shop's facade exception while steering or replanning.

Intersecting functional zones with each domain side produces positive-length
boundary intervals. Walking intervals are additionally restricted to center-safe
geometry. Source/sink points are sampled within 2–98% of the chosen interval's
arclength. Route construction requires a reachable endpoint pair. Road and cycling
intervals are retained for context and have `spawn_supported: false`.

The public eligibility flag describes supported pedestrian source/sink geometry;
it is not an arrival count, a direction schedule or a promise that every interval
is chosen by a finite cohort. Admission may be delayed by another body's space.
Actual source density must be measured from realized frames, not scheduled totals.

## Reproducible trip requests and route geometry

A fixed seed determines type ordering, individual preferred speed, source/sink
choices, geometric detours and opaque track/route tokens. Random streams are
explicit and reproducible; no frame-by-frame positional jitter is added.

For this experimental source, every second scheduled person requests one shop
visit, cycling uniformly over the four destinations. Other people request a
boundary-to-boundary trip using distinct connected intervals. This is an explicit
50% visit scenario assumption, not empirical visitor behavior. Origins and exits
are chosen from connected intervals and sampled along their interiors. Arrival
requests use the configured interval; actual admissions follow available space.

The generator routes through center-safe geometry using bounded-grid A* and
line-of-sight simplification. Seeded intermediate goals produce bounded geometric
detours rather than merely renaming one path. A visible episode keeps its original
route identifier even when native local steering or a temporary replan changes
its realized path. The generated route limit is 64 vertices.

The five existing source profiles remain Adult, Child and Senior Pedestrian,
Pedestrian With Stroller, and Pedestrian With Mobility Aid. Preferred speeds are
individually drawn from 1.1–1.5 m/s, independent of type. Circular radii remain
prototype assumptions. Age is still unmodeled for the stroller/aid categories;
this extension does not implement the proposed modifier taxonomy.

## Native local movement and door coordination

`mapped_scene.motion.mode: local_navigation` is opt-in at the C++ source level.
It advances at 50 ms in the generated scene. The outer capture step must match
the motion step; unsupported fractional or different steps are rejected before
opening a database. AGBS still samples at 100 ms. These
clocks remain separate and extra motion steps do not invent sensor measurements.

On each motion step the runtime considers target-directed angular/speed candidates
and waiting. A score combines progress, preferred speed, turning/inertia and a
short-horizon closest-approach penalty using current visible motion. Candidate
paths must stay inside supplied center-safe polygons and clear conservative swept
body reservations. Opaque-track planning priority rotates across steps. Actual
position differences determine velocity and progress; the source does not snap
everyone back onto a shared line or teleport a waiting person to a queue slot.

After a configured period without progress or while stopped, bounded A* may create
a temporary detour around current bodies. Defaults in the generated scene are
0.5-m replan cells, at most 20,000 expanded nodes, a 1,500-ms trigger and a 1,000-ms
retry interval. Failure retains safe waiting and is counted. A search budget is
not a guarantee of finding a route through arbitrary moving crowds.

Each shop has its own intentional entry/exit reservation. Incoming visitors
request access near that door; a return requests it only after the prior actual
entry plus its indoor dwell. FIFO timing and opaque track IDs break ties. The
owner retains its door approach while entering, or until an exiting body clears
it. Other intentional arrivals receive distinct valid temporary public-space
waiting targets around that approach. They still move through the normal steering
and swept-reservation checks. Arbitrary facade contact never ends a trip.

A visit ends its visible episode only at the exact route-end door. The requested
return begins after the realized entry plus 8 or 10 s, and may wait longer indoors
for safe admission. It gets a new observation-track ID. These hidden gaps exceed
the current retained 6-s history by construction. They do not establish a general
solution to cross-gap identity ambiguity.

The implementation is not ORCA, a general deadlock-free crowd solver, a pedestrian
behavior calibration or a hard realtime scheduler. Conservative reservations and
finite waiting targets can reduce throughput. Longer observation horizons can be
censored by active/pending trips; all-frame checks and finite drain tests are
separate from a source-clock completion check.

## Data, policies and privacy boundaries

The existing Region → PolicyTree adapter and illustrative regional bounds remain
unchanged. Shop fronts, exact doors, navigation cells and map-edge intervals do
not automatically become PolicyTree Regions. Functional/visit-specific constraints
need a separate reviewed scenario design and the normal spatial discretization.

The native source writes actual GT and raw sensor records to its owned MongoDB
namespaces. The aggregator's bounded history remains internal RAM; it does not
reread MongoDB to construct candidates. Publication integrity/recovery reads remain
separate. A verified exporter reads native records after the run and checks GT,
raw observations, actual recipient releases and committed private retirements.

Private stable person identities, schedules and cross-episode correspondence are
not inputs to the sensor/aggregation mechanism or browser serving allowlist. The
public geometry artifact contains OSM/destination geometry identifiers, not private
person IDs or planned identity schedules. The whole replay remains private research
material because its observation stream contains visible track IDs and positions.

All full GT, movement, observation and replay artifacts remain local under ignored
`results/`; they must not enter Git. Only compact aggregate reports and source/
configuration logic belong in the repository. Better geometry and more varied
movement are not evidence of stronger privacy or adaptive superiority. A privacy
study still needs a protected unit, secret, observer knowledge, complete release
history and a fair baseline on identical physical observations.

## Replay geometry and export agreement

`ump.building-access.v2` retains the v1 building/portal representation and adds
`store_fronts`, `facade_separators`, `boundary_intervals` and a navigation summary.
The strict closed schema excludes source schedules and private identities at every
level. The navigation summary contains a polygon digest and clearance, not the
native configuration. Bounds and original facade/entrance relationships are checked.

Export requires exact portal agreement with the native configuration, matching
center-safe polygon digest/clearance, valid route endpoints at declared eligible
walking intervals or exact doors, and generated config/background/geometry digests.
The same-source comparison copies the validated public geometry byte-for-byte.

The browser draws original building boundaries, separately colored shop fronts,
short assumed divider ticks, named exact entrance targets and eligible boundary
arrows in all three panels. World coordinates remain aligned under selected-cell
focus. Walking source/sink arrows are distinct from context-only cycling/road
intervals. The inventory lists buildings, shop destinations and boundary eligibility
separately. Ordinary supplied shop names use the normal map font and POI anchors;
numbered white entrance callouts and their construction lines were removed in the
October 24 cleanup. Physical doorway symbols remain independent of map names.
No renderer marker changes physical admission geometry. The two shop/boundary
controls highlight additional overlays: the frozen background retains its map
context. Long reference provenance does not change canvas alignment; supplied
map labels use bounded screen-space placement with geographic leader lines.

## Reproduction and acceptance gates

From the repository root, use the environment from the mapped-scene README:

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release
cmake --build simulator/build -j 4
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/run_scene.py \
  --motion-mode storefronts --population 64 --duration-s 240 \
  --arrival-interval-ms 1000 --seed 20261023 \
  --output results/storefront-run-new/scene --replay --port 8787
```

Choose a fresh parent directory. The accepted 64-person source drains by 186.9 s;
240 s retains its complete lifecycle plus an empty tail. Other seeds and demand
levels need their own drainage check. Inspect `capture-proof.json`
for lifecycle coverage and remaining trips. Reopen an existing retained replay
without rerunning the Simulator or opening MongoDB:

```sh
python3 -B tools/replay_viewer/serve.py \
  --bundle results/storefront-run-new/replay --port 8787
```

CTest gives the full seeded geometry/config suite 120 s (other mapped tool
suites retain 60 s). Three native finite
drain methods are registered separately and run serially to avoid test contention:
corridor (150 s), earlier two-building source (300 s) and storefront source (420 s).
Those are wall-clock test timeouts; the simulated horizons and per-subprocess
limits are explicit in the test methods. They are not realtime deadlines.

Before reporting final acceptance, record the exact code/config/binary hashes and
complete: native capture and independent all-step geometry/lifecycle checks;
64/128 finite-source drain checks; legacy output compatibility; relevant sanitizer
checks; viewer rewind/focus/toggles; and actual source/runtime measurements. Record
censored horizons and failed searches as such. Implementation details in this note
must not be substituted for those results.
