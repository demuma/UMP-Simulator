# Ordered map, doorway and multimodal-source roadmap — 2026-10-24

This is a design follow-up to the implemented storefront source (`74977a1`), not
an implementation claim. The [capacity report](NAVIGATION_SCALABILITY_REPORT_2026-10-24.md)
records measured motion costs; the replay now labels actual PolicyTrees and methods.
No traffic actors, permissions, map geometry or portal widths are changed here.

The clarified scaling target is 500 total people. At one arrival request per
second, the full native source cohort completes all 750 episodes with a peak of
81 concurrent tracks; this is distinct from a dense 500-concurrent stress target.
Source-only deadline tails remain open. The first boundary-distance fast path
now preserves raw-bit 64/500-source output and reduces the fresh 500-person
wall pair from 213.30 to 155.89 s; all 86 suites pass. Read the
[optimization test report](NAVIGATION_GEOMETRY_TEST_REPORT_2026-10-24.md).

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

## Additional observed entrances are not active destinations yet

The frozen map contains the entrances the user identified. The current four-shop
source activates only its four synthetic Rappolthaus portals; a background entrance
or a building label does not imply an active trip destination.

| Building / source node | Local target x / y (m) | Retained evidence | Activation gate |
|---|---|---|---|
| Upper-left retail building `322716237`, node `4616972979` | 20.36375 / 7.27353 | `entrance=main`, **`level=1`**; exact original facade | Exterior approach is body-safe and connected. Resolve floor/access meaning explicitly before treating this as a ground-floor destination. |
| Cafe building `32529387`, node `9370793427` | 35.24756 / 28.58382 | `entrance=main`; exact original facade | Door is 5.702 m from current derived walking geometry. Model and audit a traceable connector before routing visits here. |
| Same cafe building, node `11062053180` | 48.73195 / 21.03941 | `entrance=secondary`; exact original facade | Exterior approach is body-safe and connected; confirm or explicitly assume destination association. |

The named POI `442443891`, "Elbphilharmonie Kultur Café Starbucks", is inside the
cafe building. Building membership alone does not establish which entrance belongs
to that business. Use the original supplied name, including its spelling/diacritics,
for display. Do not silently replace the main door by the secondary door or claim
that either is a surveyed cafe-specific entrance. Preserve source IDs/tags,
geometry hashes, provenance, activation status and reasons in the next inventory.
The previous two-building fixture also omitted both buildings; this is a bounded
scenario-selection limitation rather than absent source data.

## Preferred and distributed pedestrian crossings

Repair Barkhof as a preferred connection, then allow crossing at multiple locations
within explicitly declared crossable road surfaces. The intended scene does not
force every pedestrian through one crossing. Crossable surface, barriers, grade
separation and mode access belong to the movement/scenario model, not the
PolicyTree's data-release constraints. Distributed crossing is an explicit scenario
assumption; neither map color nor a blanket union of every road and walking polygon
establishes that permission. Keep blocked and incompatible areas excluded.

Route choice can prefer Barkhof while allowing a bounded road-traversal cost and
seeded, spatially distributed alternatives. Native guidance shortcuts and local
movement must preserve that preference instead of bypassing its cost through
hard-visibility shortcuts alone. With moving riders/vehicles, both preferred and
free crossings additionally need gap/yield decisions, conflict
reservations, waiting space and a clear exit. Pedestrian swept-body separation alone
is not a traffic-priority model. Report crossing-position distributions and demand;
adding free crossings must not covertly change a matched aggregation comparison.

## Wall and corner comfort is a separate movement objective

Current wall hugging follows the implemented objective: hard center geometry is
eroded by 0.552 m (largest radius 0.45 m + clearance 0.10 m + numerical allowance),
global A* minimizes route length and visibility simplification removes intermediate
points. Native navigation again skips to farthest hard-visible guidance and scores
progress, speed/velocity continuity and predicted person conflicts. It has no
preferred wall-distance term. A more spacious planned route can therefore be cut
back to the hard boundary during execution.

Keep mandatory swept-body clearance and preferred comfort separate. Use original
building-wall geometry as the comfort obstacle layer: center-space boundaries also
include map edges, walking-region edges and door strips, which are not all walls.
A soft wall-distance penalty can prefer space around corners while allowing a
valid narrow passage. Do not globally increase hard erosion and disconnect doors
or Barkhof. Apply compatible costs to global A*, simplification, native waypoint
shortcuts, local candidate choice and replanning. A later corner lookahead/turning
model must remain distinguishable from this first comfort preference.

For a proposed planned path P parameterized by arclength s, an initial experimental
cost could be length plus
`lambda * integral(max(0, c_preferred - (d_wall(P(s)) - radius))^2 ds)`.
Here c_preferred is preferred body-to-wall clearance in metres, d_wall is center-to-
wall distance and lambda has units m^-2 if the total cost is in metres. This is a
proposed movement objective, not an implemented release-utility metric or a calibrated
human-behavior model. Keep the realized trajectory notation phi_u(t) unchanged.

Taper the preference only along the owning track's declared normal door approach;
the finite route-specific physical facade exception and exact entry/exit endpoint
remain mandatory. Unrelated passers must not borrow another destination's throat.
Required gates: improved actual convex-corner clearance, a valid narrow passage
still completing, no native shortcut undoing the improvement, exact door lifecycle,
no swept wall/body overlap and complete finite-cohort drain. Report actual wall-
distance distributions outside intentional door transitions, route length, travel
time, stops and per-step cost alongside source/aggregation quality.

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
2. First bounded fast path implemented: conservative edge boxes skip distant
   boundary-distance checks while retaining the original boundary/ray predicates.
   Continue prepared geometry/nearby-body indexing only where profiling justifies it.
   Preserve geometry decisions, opaque-ID tie order, source and publication outputs.
   Repeat the clarified 500-total scenario with full-pipeline timing and measured
   active population. Controlled 250/500 simultaneous-active fixtures are later
   optional headroom tests, not the current user requirement.
3. Preserve map topology/access metadata and fix the Barkhof graph-connectivity
   artifact with a reproducible regression and explicit geometry assumptions.
4. Inventory and activate additional upper-left/cafe accesses only after explicit
   floor, destination-association and connector gates. Add per-door single-file/
   bidirectional capacity and logical destinations, with physical/lifecycle/export/
   replay tests before replacing any existing fixture.
5. Add consistent soft wall/corner comfort across planning and native execution;
   retain exact physical clearance and route-specific door transitions.
6. Add cyclist/scooter profiles, per-mode graphs and semantic branches in a bounded
   mixed-mode scene. Keep demand and policy changes separately controlled.
7. Activate road traffic plus preferred and distributed crossings with inter-mode
   conflict tests and declared crossable surfaces.
8. Generalize arbitrary-area acquisition/configuration and quality reporting using
   the validated components; cache immutable inputs for result reproduction.

These additions improve the source and expose useful rare-type/region scenarios.
The privacy study still needs a protected unit, secret, observer knowledge and
matched baseline/release history. Simulation richness is not a privacy result.
