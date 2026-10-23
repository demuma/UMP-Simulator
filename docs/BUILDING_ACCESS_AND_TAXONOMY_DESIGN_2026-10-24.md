# Building access, source attributes and release taxonomy — 2026-10-24

Status: design discussion and inspected current implementation. No new doors,
source classes or semantic release hierarchies are implemented by this note.

## Building access

OSM building outlines and explicitly mapped `entrance=*` nodes are distinct inputs.
See [OSM buildings](https://wiki.openstreetmap.org/wiki/Buildings) and
[OSM entrance tagging](https://wiki.openstreetmap.org/wiki/Key:entrance).
An outline does not establish a separate storefront or entrance for every POI.
The retained 80-m scene contains six entrance nodes, but only the Rappolthaus
portal currently has validated source routes. One entrance has an explicit upper
level; other doors still need facade, accessible walking connectivity and level
checks. Labels alone are not evidence of connected, ground-level access.

Proposed next source extension:

1. Prefer a mapped, reachable entrance with compatible access/level assumptions.
2. Otherwise choose a street-facing facade bordering reachable walking space and
   create a **synthetic** portal. A facade midpoint is a reasonable initial model,
   provided it is reachable; the geometrically nearest road is insufficient.
3. Record building ID, facade segment, `osm`/`synthetic` provenance, deterministic
   seed and assumptions. Do not present the inferred portal as an actual OSM door.
4. Only a road user explicitly targeting this building may enter there. A frontage
   segment or small portal interval may replace a point, with an explicit arrival
   criterion. Arbitrary wall contact must not consume passing/queued road users.
5. Keep the outdoor body envelope and queue/admission rules consistent. No indoor
   navigation is required for a hidden visit. Re-emergence gets a fresh visible
   track; stable synthetic person identity remains private evaluation evidence.

Multiple shop destinations and visit rates are a later, separate source gate.
Validate every new route against building/walking geometry and check queues,
completed visits, remaining active episodes and density before effectiveness work.

## MongoDB rereads

The online AggregationHistory retains bounded sample bins and identity evidence
in RAM. Candidate and ancestor queries read this history, not MongoDB. Native GT
and sensor writes persist research evidence. PublicationStore also performs real
MongoDB reads: immutable payload reconciliation, intent/conflict checks and
explicit read-only recovery. Offline recording/export and replay analysis reread
persisted source and releases. These are different paths, not historical database
queries inside the aggregation search.

## Current source and release semantics

The mapped source has five disjoint input labels: Adult Pedestrian, Child
Pedestrian, Senior Pedestrian, Pedestrian With Stroller, Pedestrian With Mobility
Aid. The last two have **no modeled age**, and map directly to terminal release
nodes at configured loss zero. They are not age-specific observations that the
aggregator has already generalized. Zero loss means no loss relative to this
coarse source vocabulary, not complete description of a person. Speeds currently
share the same sampling interval across these categories; their body radii differ.

The current release tree is Road User -> Pedestrian -> five terminal categories.
Each raw input maps to exactly one terminal; a released cut is a disjoint complete
partition. The accumulator requires a stable terminal per visible identity within
its candidate interval. Unknown source attributes cannot be reconstructed later.

## Proposed modifier model and hierarchy tradeoff

Keep the source description separate from the chosen release hierarchy:

- Movement mode: walking, wheelchair, cycling, etc., with an explicit definition.
- Age group: child, adult, senior, unknown.
- Mobility aid: none observed, cane, crutches, walker, unspecified aid, etc.
- Mobility accessory: stroller, shopping trolley, etc.; allow combinations where
  the source/observation model actually supports them.
- Wheelchair subtype: manual, powered, unknown, when observed/modelled.

Equipment does not justify inferring medical diagnoses or unobserved age.
A stroller operator and a child occupant are not automatically two observed road
users: counting units must be explicitly modeled and consistent with support.

The proposed age-first tree is structurally feasible:
Road User -> Pedestrian -> Adult Pedestrian -> Adult With Mobility Aid -> Adult
With Walker. However, Adult With Walker and Child With Walker then have only
Pedestrian as a shared ancestor. This tree cannot hide only age while retaining
Walker. An aid-first tree has the symmetric limitation. A general multiattribute
lattice would permit both choices but requires new candidate, loss, partition and
support rules. The current one-parent tree does not implement that lattice.

Internal nodes must include their complete descendant population. An internal
Adult Pedestrian node cannot simultaneously mean only an unaided adult input
leaf; use an explicitly defined terminal for the latter. Unknown/unspecified
attributes need their own truthful representation.

For wheelchair use, avoid defining the parent as "walking with an aid". Either
use an explicitly broader Pedestrian Mobility category containing walking and
wheelchair modes, or place Wheelchair User alongside Pedestrian under a neutral
personal-mobility parent. This is a modeling choice, not a traffic-law assertion.
Age and equipment remain separate attributes in either case.

Next taxonomy gate: agree definitions, unknown handling, actual input categories,
permitted generalization order and loss weights on a small example, then test
support/partition/count conservation. Do not add a large taxonomy merely to make
one benchmark favor adaptation. Freeze source and policy across method comparisons.
