# Ordered map, doorway and multimodal-source roadmap — 2026-10-24

This is a design follow-up to the implemented storefront source (`74977a1`), not
an implementation claim. The [capacity report](NAVIGATION_SCALABILITY_REPORT_2026-10-24.md)
records measured motion costs; the replay now labels actual PolicyTrees and methods.
No traffic actors, permissions, map geometry or portal widths are changed here.

The clarified scaling target is 500 total people. At one arrival request per
second, the full native source cohort completes all 750 episodes with a peak of
81 concurrent tracks; this is distinct from a dense 500-concurrent stress target.
Source-only deadline tails remain open.

## Three separate kinds of constraints

Map access/connectivity and actor kinematics determine physically modeled movement.
Crossing/door coordination controls conflicting movements. The PolicyTree controls
which observed data may be released at which spatial, temporal and semantic
resolution. A road's map color or a privacy policy must not silently grant traffic
access. These layers should share traceable region geometry without becoming one
large rule engine.

## What the frozen scene actually contains

These facts describe the retained snapshot and processing assumptions, not a live
survey or a legal interpretation of current street access:

- The yellow corridor is Mönckebergstraße, way `127716469`: retained tags include
  `highway=residential`, `lanes=2`, `motor_vehicle=no`, `foot=use_sidepath`,
  `cycleway:both=no`, `sidewalk=both`, `surface=asphalt`. Its modeled 6-m width is
  inferred from the lane count. Absence of a dedicated cycleway is not a general
  bicycle access rule; cycling permissions need their own retained semantics.
- The southeastern shared cycling area is footway area `43053346`, with
  `bicycle=yes`, approximately 429.44 m². It is not a universal cycling permission
  for every green walking polygon.
- Explicit crossing-class area in this 80-m crop is zero. Barkhof footway
  `1015875382` nevertheless geometrically crosses the road; walking/road overlap
  is 15.050409929 m². This is imported as an ordinary footway with an assumed 2.5-m
  width, not an operational signal/yielding crossing.
- The accepted 64-person scene's 96 guidance routes have zero intersection length
  with the road polygon. A geometrically connected center-space polygon does not
  imply that the discrete navigation graph preserves every connection. The Barkhof
  junction's narrow neck is missed by 0.5-m and 0.25-m local lattice traversals;
  exact-segment traversal at 0.1 m connects the two sides. Current route queries
  from `[65,35]` to `[68,45]` fail. The original broad statement that existing
  pedestrians can already use this crossing requires this qualification: map
  connectivity exists, but current generated guidance does not use it.

Do not fix that artifact by globally increasing PolicyTree depth or blindly using
a 0.1-m navigation grid. Navigation and privacy discretization are separate; a
fivefold lattice refinement would multiply the two-dimensional grid size by 25.
Preserve actual map junction topology, test body-safe connections and use bounded
local refinement or visibility attachments with declared geometry assumptions.

## Simultaneous entry and exit need a doorway model

The current door has a declared width of 1.2 m, one exact center target, a 0.07-m
center-space strip and one intentional FIFO owner. Enlarging its rendered marker,
waiting radius or width field alone cannot permit two compatible simultaneous
movements. The exact point and exclusive reservation remain shared.

A proposed per-door contract is:

| Property | Meaning |
|---|---|
| Physical opening and provenance | Measured/tagged width, explicit synthetic assumption or unresolved width |
| Flow mode | `single_file` or explicitly modeled `bidirectional` |
| Logical destination | Stable shop identity independent of ingress/egress lane |
| Lane targets | Distinct points on the same original facade, with exact normal approaches |
| Admission compatibility | More than one owner only when full swept body corridors fit |
| Unknown geometry | Conservative single-file default and a reported assumption |

The logical destination is essential: the current local mode requires a return
through the same portal ID to avoid confusing shops in one building. A new ingress
and egress lane can have different point/portal identities while still referring
to the same shop. Relaxing validation to merely 'same building' would reintroduce
that ambiguity. Lifecycle, exporter, public geometry and viewer must agree on the
new logical destination/lane representation; this is a schema change to design
explicitly, not a cosmetic width adjustment.

For two equal circular bodies of radius r, the current model requires separation
`2r+c` between centers and `r+c` clearance from each outside wall. Thus a straight
opening needs at least `W >= 4r + 3c`. For the largest current pedestrian r=0.45 m
and c=0.10 m, that gives 2.10 m before extra operating margin. A synthetic 2.4-m
opening is a possible experimental setting, not a statement about actual shops.
Unequal bodies, turn geometry, door leaves and accessibility can tighten capacity.

Required tests: opposite simultaneous passage when space exists, narrow-door
serialization, no body/wall overlap, one-way door settings, fair mixed arrival/
return demand, exact lane endpoints, same-shop returns and no unbounded starvation
in the selected finite test cases. Existing single-file scenes remain unchanged.

## Automated import includes automated preprocessing

An area/bounding-box import can automate download, freezing, projection, geometry
repair, feature classification, topology building, clearance calculations, graph
construction, region/PolicyTree discretization and configuration output. The
preprocessing still exists; it runs before simulation and is cached. A generic
importer should not require hand-editing each street, yet missing widths, uncertain
access or ambiguous shop-to-door associations remain reported assumptions or
reviewed overrides.

The present tool is deliberately a bounded fixture: fixed centers/sizes, 80-m
source extent, four shop names and one parent building. It reads a frozen snapshot
or separately acquired OSM XML; it does not yet fetch arbitrary city areas. POIs
come from a separate named shop/amenity-node extraction. Generalization must remove
those location assumptions and include relevant way/relation POIs.

The current freeze whitelist drops `oneway`, `maxspeed`, conditional mode/access
information, crossing/signal details and turn-restriction relations. Node retention
keeps entrances but omits standalone crossing/traffic-signal nodes. Derived polygon
unions alone cannot recover the directed routable road graph or those restrictions.
The next import schema should preserve required node/way IDs, connectivity and
source tags before reducing them to display/region layers.

A useful output is a versioned scenario package containing both routable geometry
and functional regions, a source hash, every inferred value/provenance, graph-versus-
vector connectivity checks, body-clearance checks and an unresolved-feature report.
A projected POI entrance remains synthetic. A real `entrance=*` node identifies an
entrance and still needs width, access and destination association where available.

Primary documentation: [OSM Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API),
[entrance](https://wiki.openstreetmap.org/wiki/Key:entrance),
[entrance width](https://wiki.openstreetmap.org/wiki/Key:entrance:width),
[pedestrian areas/access](https://wiki.openstreetmap.org/wiki/Tag:highway%3Dpedestrian),
[footway connections/crossings](https://wiki.openstreetmap.org/wiki/Key:footway) and
[cycleway infrastructure](https://wiki.openstreetmap.org/wiki/Key:cycleway).
These describe data semantics, not confirmation of present local permissions.

## Adding cyclists, scooters and road traffic

The general simulator configuration already defines Senior/Adult Cyclist, Adult
E-Scooter Driver and Adult Cargo Cyclist. The mapped generator replaces these with
five pedestrian profiles and a pedestrian-only semantic release tree. Child Cyclist,
Senior E-Scooter Driver and other age variants are not currently defined there.
New age categories should be deliberate source attributes, with behavioral
variation modeled separately; age does not automatically define a route permission.
Scooter propulsion/vehicle mode also needs an explicit meaning.

Existing general-config radii are 1.0 m for cyclists, 0.65 m for the E-Scooter and
1.25 m for the cargo cyclist. These conservative circular-envelope assumptions
cannot use the mapped source's 0.55-m center clearance unchanged. Merely adding
labels would place riders in pedestrian paths/doors with inappropriate clearances,
speeds and turning behavior. Physical dimensions and safety margin must be reviewed
separately from a taxonomy label.

A bounded first extension needs:

1. Per-mode allowed areas and connected directed routes, preserving mode/access
   tags and explicit scenario overrides with provenance.
2. Compatible source/sink intervals; shop/indoor destinations only for actors whose
   modeled route can use them. A pedestrian door is not a default bicycle entrance.
3. Type-specific speed, body envelope, acceleration/braking and turning limits;
   interactions must still pass continuous inter-mode swept checks.
4. Explicit semantic hierarchy/metric handling for age → cyclist/scooter parent →
   road user. Expanding taxonomy depth must not silently change the meaning of
   semantic-loss bounds in a comparison.
5. Controlled mode mixes and spatial demand on identical saved observations for
   aggregator/PolicyTree experiments. More classes may make category-support
   bounds harder; density is an experimental factor, not a guaranteed improvement.

Traffic on the yellow corridor then needs route direction/lane and source rules.
Pedestrian crossing connectors need an operational conflict model: entry decision,
yielding/gaps or declared signals, waiting areas, priority and no-blocked-exit
checks. Optional delivery actors require explicit behavior and allowed periods;
the existing snapshot's `motor_vehicle=no` is not evidence of a delivery exemption.
Do not invent an unrequested general car class or infer exceptions from map color.

## Ordered implementation gates

1. Completed: accurate PolicyTree/method replay identity and isolated motion profiling.
2. Next: accelerate exact static geometry checks; then index nearby bodies. Preserve
   all geometry decisions, opaque-ID tie order, source and publication outputs.
   Repeat the clarified 500-total scenario with full-pipeline timing and measured
   active population. Controlled 250/500 simultaneous-active fixtures are later
   optional headroom tests, not the current user requirement.
3. Preserve map topology/access metadata and fix the Barkhof graph-connectivity
   artifact with a reproducible regression and explicit geometry assumptions.
4. Add per-door single-file/bidirectional capacity and logical destinations, with
   physical/lifecycle/export/replay tests before replacing any existing fixture.
5. Add cyclist/scooter profiles, per-mode graphs and semantic branches in a bounded
   mixed-mode scene. Keep demand and policy changes separately controlled.
6. Activate road traffic and explicit controlled crossings with inter-mode tests.
7. Generalize arbitrary-area acquisition/configuration and quality reporting using
   the validated components; cache immutable inputs for result reproduction.

These additions improve the source and expose useful rare-type/region scenarios.
The privacy study still needs a protected unit, secret, observer knowledge and
matched baseline/release history. Simulation richness is not a privacy result.
