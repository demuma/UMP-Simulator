# Explicit multi-building access — 2026-10-24

The mapped source now has a `buildings` mode with separate original OSM building
footprints, exact facade entrance points, distributed visit targets and actual
entry/return lifecycle. It runs through the maintained C++ Simulator, sensors,
Region/PolicyTree adapter and immutable publication pipeline. It does not add a
privacy mechanism or change aggregation policies/taxonomy.

## Geometry and source construction

The retained 80 x 80-m Mönckebergstraße crop contains eight displayed building
footprints, including two roof-tagged shapes. Geometry retains separate IDs,
exteriors and holes instead of treating all buildings as one merged grey mask.
Display clipping never creates an eligible artificial wall at the domain border.
The first bounded fixture connects two different building IDs:

| Target | OSM building | Exact local door x / y (m) | Width |
|---|---|---|---|
| Rappolthaus | way 43117523 | 40.884645877 / 62.870024323 | 1.2 m |
| MöGrill | way 613989270 | 64.136246842 / 21.623987959 | 1.2 m |

Both doors are **synthetic midpoints of complete original wall segments**. They
are not claimed to be real OSM-mapped doors, current shop entrances or evidence of
public access rights. Their width is a scenario assumption. Names come from the
retained snapshot. Other footprints remain visible; rejected/unselected targets
have explicit reasons in the generated manifest. Roofs are not visit targets.

A finite 1.25-m navigation lattice connects outward facade approaches to sensing
boundaries. Each graph edge and final simplified polyline is checked against the
retained walking/building geometry. Inbound/outbound approaches are separated
outside a short door throat. All access paths avoid the full through-flow envelope,
including the bounded variation of individual through paths. MöGrill traffic uses
the north walking area; Rappolthaus and through traffic use separated southern
paths. No route teleports across the road. This is a small static scenario router,
not a general dynamic city or crowd solver.

Exact route and swept circular-body checks allow only the explicitly declared
0.85-m facade transition disk for the referenced door and clipping at the sensing
boundary. The disk is a geometry-clearance exception, **not** an entry trigger.
Original wall membership, exact midpoint, nonpenetrating centerline and full-route
walkability are independently checked. Source profiles use radius up to 0.45 m
plus 0.1 m clearance; the route audit uses 0.55 m throughout.

## Runtime door behavior

`mapped_scene.portals` declares ID, building ID, point, facade endpoints, width and
`osm`/`synthetic` provenance. Native configuration rejects invalid/duplicate IDs,
nonfinite geometry, off-facade points, openings extending beyond walls, routes
missing their declared door and bodies wider than the opening. Relative hidden
returns must use a portal in the same declared building.

A visitor follows its route to the exact facade endpoint. Only reaching the route
end produces the entry event and ends outdoor visibility. Contact with an
unrelated wall or approach circle cannot end a track. A return waits its declared
indoor gap measured from the **realized** entry, waits for safe outdoor admission,
then starts at the precise door point with a new opaque visible track ID. Stable
person linkage remains private GT and never enters sensor/aggregator support.

Explicit portals replace the historical exclusive 3-m approach disk with a short
body- and approach-angle-aware admission throat. The bound accounts for closest
approach between incident inbound/outbound rays, not just body diameter. Physical
swept reservations still include passers and all active tracks. Nearby independent
doors can operate independently. The conservative center-target model serializes
conflicting doorway movements; declared width validates body fit and the displayed
opening, not a calibrated multi-lane doorway capacity.

Old scenes without explicit portals keep the previous motion/admission branch.
Historical integration/corridor generation and background images remain identical.

## Visualization and data boundary

The native background draws individual outlines, selected building names and
physical door-width strokes, with OSM attribution and synthetic-door labeling.
The browser adds toggles for building-boundary and entrance highlights in all
three panels and focused-cell zoom. Diamonds identify synthetic doors; squares
identify explicit OSM entrances when present. The inventory associates each
building with its routable entrances, exact coordinates, width and provenance.

`building_access.json` contains public map context only. Replay validation caps its
size and complexity, rejects unknown/private fields and restricts file access.
Export checks its portal declarations against the actual executed configuration,
checks scene bounds and generated geometry/config/background hashes, then copies
and hashes the artifact. The comparison adapter carries the same asset forward.
No private schedules, person IDs or track/person mapping enter the served artifact.
Existing bundles without it remain valid. Building shapes are context, distinct
from the unchanged illustrative D6-aligned policy rectangles.

## Run and view

From the repository root, after the normal build and with local MongoDB running:

```sh
/private/tmp/ump-osm-moenckeberg-2026-10-23/venv/bin/python tools/mapped_scene/run_scene.py \
  --motion-mode buildings --population 64 --duration-s 180 --arrival-interval-ms 1000 \
  --output results/YOUR_FRESH_BUILDING_RUN/scene --replay --port 8786
```

Use a fresh output path. `--render` also opens the native live view. The launcher
now defaults to buildings mode; explicit `--motion-mode corridor` or `integration`
reproduces the historical modes. `simulator/config.yaml` is not overwritten.
The launcher retains source databases and local recordings, verifies completed
captures, and prints the replay reopening command. Generated movement stays under
ignored results/ and never enters Git.

Use the independent actual-source gate after export:

```sh
/private/tmp/ump-osm-moenckeberg-2026-10-23/venv/bin/python tools/mapped_scene/audit_building_access.py \
  --scene results/YOUR_FRESH_BUILDING_RUN/scene --replay results/YOUR_FRESH_BUILDING_RUN/replay \
  --output /private/tmp/ump-fresh-building-access-audit.json
```

It checks all recorded route positions and pairwise circular body/clearance,
precise door exits, final inbound step, realized hidden gaps and actual entry plus
return at two distinct buildings. Configured but unvisited doors do not pass this
acceptance gate. Normal export separately validates complete source/lifecycle,
sampling, counts, semantics, policies, ownership and journal/recipient equality.

## Limits and next work

Visit shares, doors, widths, preferred speeds and routes are modeled assumptions.
The 64-person fixture has 32 visits, 16 to each building, and 96 visible episodes.
Source request spacing and finite horizons can still queue or censor denser runs;
report actual admitted/completed populations and waiting, not only planned counts.
No general arbitrary-route deadlock guarantee, ORCA, overtaking, indoor navigation,
real door recognition or empirically calibrated shopping model is claimed.

The regional policy rectangles are unchanged, so the old entrance-vicinity patch
is not automatically attached to every new synthetic door. Designing door-specific
functional policies is a separate declared experiment. More geometry and truthful
entry/exit do not establish measured privacy. The next privacy study must declare
its protected unit, observer knowledge, secret and stream-level evaluation first.
