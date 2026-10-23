# M01: bounded 80-m mapped-mobility and identity contract

Date: 2026-10-23. Implementation gate: one reproducible, map-constrained synthetic
scene in the maintained Simulator. **M01 is implemented and verified**; see the
[test report](MAPPED_SCENE_TEST_REPORT_2026-10-23.md) and [run guide](../tools/mapped_scene/README.md).
This precedes baseline/privacy-effectiveness claims and a renewed performance gate.
Existing legacy scenarios are preserved.

## Domain and route scope

Use the audited Mönckebergstraße close-detail footprint: 80 × 80 m, data depth 6,
4,096 possible 1.25-m leaves, x east / y south. It is a local sensing footprint,
not the whole shopping street. Keep deterministic scenario time at 50-ms steps
and initially use 100-ms sensors. Sources/routes model trips crossing the local
boundary; an 80-m square does not imply that real journeys are 80 m long.

For the first gate, use manually checked polylines within the derived walking
geometry, one verified building portal and explicit source schedules. Routing
uses the current Agent/Sensor/aggregation pipeline, not a replacement observation
generator. Do not require ORCA, A*, global city routing or the full modifier
taxonomy migration for this gate. Route centre lines must not cross building
interiors. A portal is an explicit transition at the facade, not teleportation
through another wall. Circular body/door passage remains an approximation.

Mapped entrance node 6244468529 reaches Rappolthaus building way 43117523. Its
function is not verified as residential, so name this an entrance/visit scenario.
Use explicit indoor dwell and an outward route. Inside the building, the person
is absent from the visible Agent vector and all sensors. No building interior
motion is claimed. Building footprints outside checked routes are not a complete
obstacle/collision model.

## Three information boundaries

1. **Private simulator and evaluator:** stable synthetic person ID, route plan,
   visit/arrival/departure/dwell labels and the person↔track mapping. This is a
   simulation oracle, not an implemented re-identification algorithm.
2. **Operational observations:** an independent track ID for each uninterrupted
   visible episode, observed profile/type, position and measurement time. After
   an indoor gap, mint a fresh track ID with no person-ID prefix. The Agent objects
   supplied to sensors contain only the track identifier. Never supply the private
   person map to a sensor, aggregation history or semantic evidence accumulator.
3. **Recipient release:** existing aggregate schema; no GT ID, track ID or
   person↔track mapping. Debug GT and observation collections are private research
   records, not recipient data.

The legacy `Agent.agentId` field remains the visible observation identifier in
the mapped scene. Stable person identity lives in a separate scenario registry.
Private GT can record both for evaluation. Older scenarios keep their existing
identity behavior. No appearance-based, biometric or behavioral re-identification
is introduced. Resetting IDs does not exclude inference from times or locations.

## Support meaning and first-scene restriction

Existing aggregation counts the union of internal contributor IDs. With new IDs
after a hidden gap, that is **distinct track support**, not automatically a count
of distinct people. A returning person can contribute two tracks within one
candidate. Silently deduplicating with the GT registry would give the mechanism
oracle information and is prohibited.

The motion/lifecycle core must allow a short-gap counterexample and test that it
contains one private person but two observation tracks. For the initial integrated
aggregation demonstration, require each indoor gap to be longer than every
enabled aggregation's retained-history horizon (which bounds its candidates).
Then the controlled scene cannot contain two episodes of one person in a retained
window. Validate this declared invariant before database initialization and audit
it privately. This does not solve arbitrary tracking fragmentation or establish
general person-level k-anonymity.

A future conservative person-support metric, e.g. maximum simultaneous support
under an explicit no-duplicate-per-frame tracking assumption, needs its own gate.
Until then, shorter-gap/general fragmentation studies must use a declared track
support contract or disable person-support claims. Private evaluation should
report actual-person support and track inflation alongside the operational value.

## Motion and lifecycle

Routes advance by arc length using simulation time, preserving corners and
handling large steps/overshoot. Speed and arrival schedules are explicit inputs,
so identical configuration produces identical positions independently of rendering
or wall time. Arrival at an entrance ends one visible episode; a declared hidden
duration precedes a separate outward episode with a fresh track. Collision stops
and indoor dwell are separate states. Initial source arrivals and final boundary
departures are explicit events. Keep the current legacy collision/motion path
unchanged; the first mapped route execution does not claim a new crowd-collision
solver, and its limitations must be visible.

## Pedestrian vocabulary

Add scenario-local observed profiles `Pedestrian With Stroller` and
`Pedestrian With Mobility Aid` as zero-loss semantic terminals under `pedestrian`,
alongside the existing pedestrian profiles. These are configured labels, not new
C++ class hierarchies. They can truthfully generalize to Pedestrian before Road
User. Aid/accessory does not imply age, diagnosis or a particular legal priority.

Use declared synthetic speed/radius assumptions. Do not claim calibrated stroller
or mobility-aid behavior. The first model counts the observed mover plus equipment
as one modeled Road User; a stroller occupant is not an additional support
contributor unless explicitly simulated and observed. Keep type fixed per modeled
unit in this gate. Population assignments must be exact, including small groups.

## Sequential acceptance gates

- M01a: private/operational identity contract and independent route/lifecycle core.
- M01b: integrate opt-in mapped scene into the maintained Simulator; sensors see
  visible tracks only; configure the actual Region → PolicyTree path.
- M01c: add scenario-local pedestrian profiles and test truthful intermediate
  semantic cuts, count conservation and unknown omitted subtype queries.
- M01d: audit real map/route geometry, lifecycle events, sensor absence/warm-up,
  GT renaming invariance, repeatability and no GT fields in aggregation output.
- M02: compare policies and fair fixed/adaptive baselines on identical observations.
  Freeze task/privacy contracts before calling any result a privacy improvement.
- M03: revisit performance on this scene: source motion, sensor capture, policy and
  semantic checks, history queries, merge checks, diagnostics and publication.
  Preserve output before/after any optimization and report deadlines/queueing.

Do not mix a movement change, a policy change and an optimization when interpreting
an experiment. The upcoming performance gate is explicitly retained; the present
gate establishes correct, inspectable source behavior first.


## Follow-up protocol: observations, visits and physical people

Planning clarification, 2026-10-23. No runtime metric or source contract changes
are made by this section. Local movement recordings are now authorized for replay
under ignored `results/`, with no movement/identity streams committed to Git.

An observation track is the operational counterpart of an object ID maintained
by a multi-object tracker across associated observations. It is not a persistent
physical-person identifier. Real tracking implementations have finite lost-target
lifetimes and optional re-association; a returning target can receive a new ID.
The [NVIDIA tracker documentation](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvtracker.html#target-re-identification)
provides one concrete example. This is conceptual context, not a dependency or a
proposal to add Re-ID to this project.

With detection presence, geometry, observed labels and cadence fixed, replacing
one track by consecutive track fragments leaves AGBS observation contributions,
per-sample occupancy and class counts unchanged. It can increase interval union
support and category support. Unique-person counts, repeat-visitor counts and
linked indoor dwell cannot be inferred by assuming every new track is a new
person. Boundary/building crossings can still be counted as events, with a
separate event definition and detection completeness assumptions. ABS velocity
estimation additionally needs a fresh warm-up after a track break; AGBS invariance
does not imply that every sensor's exported rows remain unchanged.

Keep physical movement fixed in the first fragmentation comparison. Retain the
stable mapping only in private evaluation. Measure n_track, n_GT and delta n from
section 29 of the [notation reference](TERMINOLOGY_AND_NOTATION.md), including the
fraction of released cell/windows whose operational support passes while true
modeled-person support fails the same threshold. Report class-specific cases and
zero-denominator metrics explicitly. This diagnoses the consequences of identity
assumptions rather than correcting operational counts with the GT oracle.

One proposed separate metric is

$$
n_{\mathrm{sim}}(C,I)=\max_{t\in\mathcal T_{\mathrm{meas}}\cap I}N(C,t),
$$

where N(C,t) counts observed units in C at an actually measured time. With no
duplicate detections/tracks or false positives within a sample, n_sim is a lower
bound on distinct physical people observed over I. A per-category version needs
the same conditions and an explicit classification model. This mathematical
bound is conditional; it is not an anonymity or unlinkability guarantee. Five
people passing one after another may yield n_sim=1, so it can lose much of the
benefit of temporal distinct-person pooling. An interval with no measured sample
has unavailable support, not a fabricated zero.

The metric is not implemented. Compare it under a separately named policy with
current track union support, measuring retention, detail and delay. Do not
silently redefine `distinct_contributors`. A compatibility-based minimum-person
model might use more tracklet timing/motion information later, but belongs to a
separate research gate. The existing long-gap integration fixture remains a
controlled regression source, not a realistic solution to arbitrary re-entry.
