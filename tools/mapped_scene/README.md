# Mapped pedestrian visits in the maintained Simulator

This opt-in scene runs the actual C++ Simulator, sensors, normal Region → PolicyTree
adapter, semantic aggregation and durable publication. It uses the frozen
Mönckebergstraße OSM geometry already in the repository. No live OSM request or
sampled motion-file export is needed. See the [identity contract](../../docs/MAPPED_SCENE_IDENTITY_CONTRACT_2026-10-23.md)
and [implementation/test report](../../docs/MAPPED_SCENE_TEST_REPORT_2026-10-23.md).

## Start the native demo

From the repository root, with the normal Simulator dependencies installed and
MongoDB running on localhost:27017:

```sh
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release
cmake --build simulator/build -j 4
python3 -m venv /private/tmp/ump-mapped-venv
/private/tmp/ump-mapped-venv/bin/python -m pip install -r tools/mapped_scene/requirements.txt
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/run_scene.py --render
```

The launcher requires `mongosh` in PATH. It generates a fresh configuration, an
aligned background and a compact source manifest in a new temporary folder, then
starts `simulator/build/Simulator` from that folder. It prints the folder and three
owned database names. The repository's normal `simulator/config.yaml` is unchanged.
Omit `--render` for headless operation; `--duration-s 20` clips the source for a
short smoke test. The full default is 90 s with seed 20261023. The finite source
schedule is not repeated when requesting a longer duration.

Each invocation uses a fresh `UMP_Mapped_<32 lower-case UUID hex>` database base,
plus `_Releases` and `_Private`. The launcher confirms all three are empty before
running. It **keeps its own databases by default** for inspection. Add `--cleanup`
to remove only those three fresh namespaces after the run, including on simulator
failure. Existing `Simulation` data are not used. GT/observation collections and
`_Private` are private research data; only `_Releases` is the recipient product.

The usual live controls remain available: buffer zones, arrows, waypoints and
past/future trajectories. Mapped trajectories follow the actual route polyline;
the OSM map is aligned exactly with the sensing square. The rendered smoke test
passed, but no live-window screenshot/layout verification is claimed.

## Declared source scope

- 80 × 80 m, D6, 4,096 possible 1.25-m leaves. This is one local sensing footprint,
  not the entire shopping street. Boundary crossings are explicit source events.
- Four checked route polylines: two through directions and inward/outward building
  visits. Route centre lines lie in the derived walking geometry and have no
  positive-length intersection with building interiors. Motion is scheduled and
  kinematic; it bypasses the legacy collision solver. Body clearance, crowd
  interaction and a complete obstacle model remain open.
- OSM entrance node 6244468529 lies on building way 43117523, Rappolthaus. Its
  function is not claimed to be residential. No interior floorplan is simulated.
- Exactly 64 scheduled synthetic people: 16 Adult Pedestrian and 12 each Child
  Pedestrian, Senior Pedestrian, Pedestrian With Stroller and Pedestrian With
  Mobility Aid. Sixteen people visit the building, yielding 80 visible episodes.
- Explicit type-independent speeds in [1.1, 1.5] m/s, fixed arc-length routes and
  source times. These are experimental assumptions, not calibrated visitor data.
  Equipment radii are circular approximations; all priorities are identical.
- A stroller mover plus equipment is one modeled contributor. A stroller occupant
  is not separately counted unless separately simulated and observed.
- The final scheduled departure is 84.221 s for the default seed. A full 90-s run
  exercises every scheduled lifecycle; shorter runs deliberately clip the scene.

## Identity and semantic interpretation

The private source/evaluator retains stable synthetic person IDs. Sensor-facing
Agent objects carry only a fresh opaque track token per visible episode; no private
person map enters the aggregator. A returning visitor is not explicitly linked to
the earlier track. This is a private GT oracle for evaluation, not an implemented
person re-identification mechanism. Resetting IDs does not prevent inference from
spatial/temporal side information.

Operational support counts distinct tracks. Indoor gaps are 8 or 10 seconds,
exceeding all configured history horizons (6 s) and candidate durations (4 s).
Startup checks this restriction. It prevents double-counting a returning person
within a candidate in this controlled source, with no other fragmentation. A
separate real-sensor regression deliberately demonstrates two tracks from one
person for a short gap. General person-support claims require another gate.

The seed fixes source schedules, speeds and pseudorandom opaque tokens; this is
not a cryptographic unlinkability claim. Stable person IDs can be renamed without
changing sensor/public output, as verified with two full native runs.

The scenario-local semantic tree preserves five zero-loss terminals under
`pedestrian` before `road_user`. Parent cost 0.5 and root cost 1 are configured
abstraction costs. The actual default scene publishes all retained observations
as Pedestrian: subtype queries remain unavailable. The separate semantic unit
test demonstrates terminal preservation where support permits it. Cost 0.5 is
not a measured percentage of lost privacy/information.

## Local policy experiment

Four disjoint D6-aligned rectangular patches pass through the normal
`region_taxonomy` → `regions` → `policy_tree.regions` path. These are explicitly
chosen experimental footprints, not the full OSM partition or automatically
derived protection rules:

| Patch | Bounds, metres | Additional requirements |
|---|---|---|
| Entrance vicinity | x=20..30, y=65..75 | Distinct track support ≥ 10 |
| West footway control | x=0..15, y=62.5..75 | Side ≤ 5 m; duration/age ≤ 1 s; semantic loss ≤ 0.5 |
| Central through footway | x=40..60, y=50..62.5 | Semantic loss ≤ 0.5 |
| East footway control | x=65..80, y=40..52.5 | Side ≤ 5 m; duration/age ≤ 1 s; semantic loss ≤ 0.5 |

Root requirements are distinct total/category support ≥ 5; cell side 1.25..10 m;
duration 400..4000 ms; age ≤ 4000 ms; semantic loss ≤ 1. The default is Semantic
First with Temporal First secondary, `policy_satisfied`, cell-local windows.
Compilation produces 117 nodes and eight effective policies. The local bounds
apply to any candidate intersecting the patch, including coarser cells.

The image is exactly 800 × 800 pixels for 80 × 80 metres, x east / y south. It has
no axes/padding; the Renderer displays attribution separately below the footprint.
It provides visual context rather than a complete obstacle map. The highlighted
portal is used by this source; other entrance buffers are inherited geometry.

## Reproduce checks

Use the Python environment above for generator tests and independent live audits:

```sh
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/test_build_mapped_scene.py -v
ctest --test-dir simulator/build --output-on-failure
/private/tmp/ump-mapped-venv/bin/python tools/mapped_scene/verify_scene.py \
  --output /private/tmp/ump-mapped-verification-new
```

Choose a new verifier output directory. It runs two complete 90-s native sources
with the same binary, changing only private GT names and fresh database namespaces.
A read-only independent MongoDB audit reconstructs source positions/visibility,
sensor counts, recipient supports/categories, local constraints, nonoverlap and
private journal agreement. It compares normalized sensor and recipient hashes.
The verifier removes its six owned databases, retaining only static inputs,
logs and compact evidence. It exports no sampled motion/observation files.

The offline `build_mapped_scene.py` can also generate configuration/background/
manifest only. Pass a new `--output` directory and an owned fresh `--database`
namespace; it never opens a database. `run_scene.py` handles that choice safely
for ordinary demos. The generator refuses existing output directories.

The [verified 90-s result](../../docs/MAPPED_SCENE_TEST_REPORT_2026-10-23.md) has
1,050 legal releases, 87.04% measured observation retention and multiple actual
spatial/temporal resolutions. No baseline advantage or measured privacy gain
follows from source/count/policy conformance. Fair same-observation comparisons,
quantitative query contracts and a renewed component-level performance review
are the next gates. No generated motion recordings belong in Git.
