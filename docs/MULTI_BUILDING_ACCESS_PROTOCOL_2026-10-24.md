# Multi-building access: implementation and acceptance protocol — 2026-10-24

Status: acceptance gate passed for the declared sources. Measured results and
resolved failures are recorded in the [test report](MULTI_BUILDING_ACCESS_TEST_REPORT_2026-10-24.md). Sources, code and public geometry may enter Git. Generated
movements, full native source records and replay histories stay local.

## Requested behavior and scope

The new `buildings` mapped-source mode uses the retained 80 x 80-m OSM extract,
individual building footprints and explicitly targeted facade portals. Do not
interpret arbitrary wall contact, a nearby POI label or entry into a 3-m disk as
building admission. A planned visitor reaches the declared facade point, leaves
outdoor visibility and may return after the realized arrival plus its indoor gap.
Only the private evaluation source links the returning track to its person.

Use real OSM building geometry, but label inferred wall-midpoint doors as
synthetic. An outline alone does not establish access rights, tenant occupancy,
door location, doorway width or a ground-floor connection. The initial mode is
an explicit modeled access assumption, not an assertion about actual entrances.
No indoor floorplan, road-user taxonomy change, new privacy mechanism or universal
crowd-navigation solver is part of this gate.

## Geometry and routing requirements

- Retain separate building IDs and polygons, including holes where present.
  Clipping for display must not create an eligible artificial facade at the crop.
- Select original facade segments adjacent to reachable derived walking geometry.
  Use their exact midpoints as source/destination coordinates and record facade,
  width, provenance and parent building ID. Reject unsuitable candidates rather
  than routing through obstacles or inventing connectivity.
- Reach at least two different building IDs. Distribute deterministic explicit
  visits across them; target diversity must be observable in the resulting source.
- Validate route centerlines against walking geometry, sensing bounds and building
  interiors. Validate circular body plus clearance along the full route, except
  explicitly bounded facade transitions and declared domain-edge clipping.
- Avoid source/return points in unrelated walls. Keep route endpoints and admission
  resources distinct: exact physical target versus collision/queue coordination.
- Independent doors must be independently usable. Swept-body checks still prevent
  overlaps near a shared door or path. Shrinking/removing an exclusive approach
  circle must not trade false queues for collisions or unresolved head-on deadlock.
- Preserve deterministic seeds, opaque per-episode IDs, realized entry/return
  timing and bounded candidate history. Do not use private person linkage for
  runtime support or aggregation decisions.

## Visualization and public/private boundary

Draw individual building boundaries, building labels and precise facade door
markers over the aligned map. Distinguish modeled doors from mapped OSM entrances
and explain the symbols in English. The replay must show the same geometry in all
panels and allow its overlay to be toggled. Generated public geometry may contain
buildings, portals and provenance; never person/track correspondence or future
individual visit schedules. Legacy bundles without the optional geometry stay
valid. Existing policy rectangles remain distinct from contextual building shapes.

## Acceptance sequence

1. Generator tests: deterministic portal/route choice, at least two buildings,
   midpoint/facade checks, obstruction rejection, body geometry, unique visit
   targets and no changes to historical modes.
2. Native tests: malformed portal configuration fails before DB initialization;
   route endpoints must use their declared portal; independent doors, realistic
   body admission, no wall-contact disappearance, actual lifecycle/hidden gaps,
   overlap and bounded-drain checks.
3. Native capture in fresh owned namespaces: run multiple targets, preserve full
   journal verification, inspect actual starts/ends at each portal, queues and
   active/pending/stalled populations. State finite-horizon censoring explicitly.
4. Full configured regression suite and a legacy source/output equivalence check.
   Run performance measurements separately from builds/other benchmarks.
5. Browser visual inspection: boundaries, doorway symbols/legend, playback, source
   movement and policy overlay distinction. Native map background must show the
   same exact building/door coordinates.
6. Record compact metrics, hashes and limitations. Publish a working local replay
   command and keep generated movement out of Git. Do not infer privacy gains from
   more realistic geometry or successful policy checks.
