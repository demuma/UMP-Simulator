# Mönckebergstraße: real-map Region / D6 feasibility test

Date: 2026-10-23. Status: **geometry and production PolicyTree compilation verified**.
This is a bounded preprocessing experiment. No movement, sensor observations,
adaptive releases, baseline advantage or privacy improvement are claimed.

## Presentation figures

- [Whole-area map and D6 comparison](figures/osm_moenckeberg/monckeberg_regions_d6.png)
  ([editable SVG](figures/osm_moenckeberg/monckeberg_regions_d6.svg)).
- [Local detail and resolution comparison](figures/osm_moenckeberg/monckeberg_regions_detail.png)
  ([editable SVG](figures/osm_moenckeberg/monckeberg_regions_detail.svg)).

The figures show real projected OpenStreetMap geometry, declared functional
corridors and conservative rasterisation. They show the maximum-resolution data
grid, **not** the adaptive published frontier or a running simulation. A red box
locates the next smaller footprint. Each raster panel has its **own D6 root**;
the local panels are not extra refinement inside the full-area D6 tree.

## Resolution is determined by footprint as well as depth

For a square domain with side length L and depth D:

    leaf side = L / 2^D; possible leaves = 4^D.

At D6, each domain has 64 × 64 = 4,096 possible leaves:

| Case | Square coverage | Finest cell | Exported disjoint rectangles | Compiled policy nodes |
| --- | --- | --- | --- | --- |
| Overview | 1,024 × 1,024 m | 16 × 16 m | 1,745 | 5,197 |
| Detail | 160 × 160 m | 2.5 × 2.5 m | 492 | 4,889 |
| Close detail | 80 × 80 m | 1.25 × 1.25 m | 384 | 5,077 |

**Interpretation:** a kilometre-scale domain at D6 is too coarse to cleanly
separate many narrow paths and entrance footprints. Smaller sensing domains are
one option. A deeper shared data tree is another, with different memory/runtime
requirements that were not measured here. Do not infer equal physical precision
from equal depth, or infer that an entire city must fit in one D6 tree.

## Source and modelling assumptions

One successful bounded request retrieved real data from the
[official OSM map API](https://api.openstreetmap.org/api/0.6/map?bbox=9.9925,53.5455,10.0165,53.5565).
The primary Overpass request failed and an alternate timed out; neither supplied
the figures. The source manifest records the successful URL, acquisition time,
raw XML hash and retained snapshot hash. No rendered map tiles were downloaded.

The retained compressed snapshot contains 3,383 relevant public source features,
including a 32-m boundary margin. It omits user names and unrelated map elements.
Coordinates are projected from EPSG:4326 to EPSG:25832 with longitude first.
The source file uses projected, legacy-style GeoJSON with an explicit CRS
description; it is not RFC 7946 longitude/latitude GeoJSON. Per-case coordinates
use metres, x east and y south, consistent with the simulator's screen axes.

| Functional layer | Derivation / limits |
| --- | --- |
| Buildings | Actual mapped polygon footprints, including complete multipolygon relations. Buildings are map context; they have not been installed as collision obstacles. |
| Walking | Explicit walking/pedestrian areas and buffered mapped paths. |
| Cycling/shared | Dedicated mapped cycleways and explicitly permitted shared paths/areas. A shared corridor retains both walking and cycling requirements on the same geometry. Permission does not establish a physically separate cycle lane. |
| Roads | Mapped road centrelines buffered using explicit widths where available or declared defaults. No car agents were added. |
| Crossings | Explicit crossing-tagged footway corridors. This is not a complete crossing inventory. |
| Entrance vicinity | A declared 3-m-radius footprint around a mapped ground-level entrance node. The location is OSM data; the radius and privacy significance are modelling choices. |

For lines, explicit numeric OSM `width` is used where supported. Otherwise default
widths are 2.5 m for walking/cycling, 3 m for crossing, 10 m for pedestrian streets,
4 m for service roads and 6 m for other roads; road lane counts can increase the
default to 3 m per lane. Compound/ambiguous widths are not silently parsed as
exact measurements. Per-feature assumptions are recorded in the compact summary.

Attribute-only `sidewalk=*` and `cycleway=*` information remains unresolved;
separate geometry is not invented at an assumed offset. Explicit underground,
indoor and nonzero/mixed-level routes and entrances are filtered. Four nearby
bridge-tagged route features without an explicit layer remain in the overview's
2D projection and are flagged; this is not a verified ground-level routing graph.
Eight incomplete multipolygon relations in the downloaded XML were skipped.
Unknown areas remain unclassified. Source counts include nearby features in the
32-m processing margin, not just objects strictly inside the displayed square.

## Functional geometry to existing PolicyTree

1. Project, clip and construct the functional geometry before simulation starts.
2. Mark every finest cell with **all** functional layers with positive intersection
   area (numerical area tolerance 1e-8 m²); touching an edge alone does not count.
3. Combine all applicable illustrative bounds by maximum lower bound and minimum
   upper bound. Keep the full class bitmask; display colour never removes a rule.
4. Coalesce cells with identical masks into exact, disjoint, grid-aligned rectangles.
   Background cells are included, so the rectangles tile all 4,096 leaves once.
5. Feed these rectangles and type requirements to the actual production PolicyTree.

This satisfies the current rectangular Region geometry contract without polygon
queries during aggregation. The polygons are a preprocessing concern. Rasterising
an entrance conservatively enlarges its effective footprint; this is explicitly
measured in `class_areas`, not disguised as exact geometry. At overview scale,
2,145 leaves contain multiple functions; detail has 856 and close detail 741.
These are different physical footprints, not a controlled density comparison.

The numeric bounds are **illustrative compilation inputs**: total distinct support
at least one, positive category support at least five, 400–4,000-ms duration,
4,000-ms maximum age, semantic loss at most one and cell sizes scaled to the
chosen domain. Local demonstration requirements raise entrance support to ten
and tighten size/time bounds for selected functions. They are assigned by us,
not read from OSM. Different physical scales have different illustrative size
bounds; the three probes are not a fair privacy/utility comparison.

The exported `policy.json` is a small core-probe schema. It is **not** a directly
loadable `simulator/config.yaml`. The probe compiles the real PolicyTree and
production metric parser; loading these patches through Simulator Region taxonomy
configuration, map rendering and routed motion is a later integration step.

## Verification and practical limits

All three actual exports pass the standalone production-code probe:

- Each tiles 4,096 leaves exactly once, including background, with unique IDs
  12,288..16,383 and correct `id >> 2` ancestry.
- Every one of 5,460 valid cells at depths 1–6 is checked against an independently
  calculated intersection of regional bounds and provenance. This includes 1,364
  nonroot ancestors. Depth-zero root ID 3 is intentionally not a released cell.
- Invalid ID, mismatched ID/geometry, overlapping regions and unaligned boundaries
  are rejected. Input hashes accompany the results.
- An independent geometry audit checks all 24,576 class bits per domain, exact
  rectangle/raster agreement and source building/entrance geometry.
- 3,363 source node/way features match independently reconstructed XML geometry
  with zero Hausdorff discrepancy. Twenty relation features were not independently
  reconstructed in that particular source check; their raster bits are still
  included in the vector-to-raster checks.
- Both figures were visually inspected. Geometry/policy outputs reproduce exactly
  from the retained snapshot without another network request.

The probe's `feasible_bounds_cells` only means the inherited numeric bound ranges
are not contradictory. It does not mean a candidate of that size/time has enough
people or passes all metrics. No people were simulated. Production aggregation
code is unchanged; no new claim about the full CTest suite is made by this gate.
MongoDB was not used.

Full machine-readable evidence, the compressed source and three exported cases
are under [the compact data package](../tools/osm_regions/data/moenckeberg/).
Reproduction commands and the actual production-code probe are in
[tools/osm_regions](../tools/osm_regions/README.md).

## Next step and scope

Keep the [three controlled scenarios](THREE_SCENARIO_PLAN_2026-10-23.md) as the
next implementation work, starting with residential entrances. Their tests can
isolate policy/movement effects. This optional OSM gate establishes a viable
future map-input path; it does not replace those scenarios, a traffic model,
destination/visit labels or the subsequent empirical privacy study.

Suggested presentation wording: “Real OSM geometry can be converted into functional
regions and compiled into the existing PolicyTree. Physical resolution depends
on the sensing footprint; a local 80-m domain retains 1.25-m D6 cells.”

Map data © OpenStreetMap contributors, available under ODbL 1.0.
[Attribution and licence](https://www.openstreetmap.org/copyright).
