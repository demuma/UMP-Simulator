# Storefronts, boundary sources and local pedestrian navigation — protocol

Date: 2026-10-24. Acceptance protocol for the implemented scenario/navigation step.
This is the next scenario-generation step, not an effectiveness/Privacy result.
The previous fixed-lane `buildings` mode remains a bounded integration fixture.
All project documentation is English. Generated motion/replay data stay local.

## Source representation

Retain the shared original Rappolthaus footprint. Add independent destinations
for Apollo, Ditsch, Adidas Originals and H&M HOME using their frozen POI IDs.
Project POIs orthogonally onto an original street-facing facade, check an interior
projection parameter, facade membership, body access and connectivity. Label
entrances as synthetic. Model tenant frontages along the facade and short inward
separator ticks; do not invent structural building/indoor walls. Manual point
corrections must bind to the frozen source geometry hash and remain synthetic.

Extract positive-length continuous intervals where walking, road and cycling
geometry meets the sensing boundary. Record type and source/target eligibility.
Sample pedestrian endpoints only from body-safe connected walking intervals;
unsupported traffic modes remain map context. Preserve valid body clipping at the
domain edge rather than eroding away every boundary contact. No points created
by clipping a building may serve as a fabricated original facade.

## Individual paths and motion

New `storefronts` scene mode uses an explicit seeded origin/destination process,
shop choices and indoor durations. Produce distinct geometric routes and distinct
sampled endpoint positions, not just fresh route IDs. Reuse bounded A* and checked
simplification for global guidance, without fixed directional-lane exclusions.
Origin/destination choice may create uneven demand; it must not force homogeneous
occupancy or be tuned to favor the adaptive aggregator.

New native `local_navigation` is separate from legacy fixed-polyline progress.
It follows guidance in two dimensions, chooses safe local velocities, yields and
performs bounded replanning when blocked. Every accepted motion segment must
remain in allowed center geometry and respect swept body separation. Polygon
holes, narrow corners and sensing-edge clipping are explicit. Do not describe a
heuristic as ORCA or claim general arbitrary-crowd liveness.

Door entry requires actual arrival at the target facade point. Unrelated wall
contact cannot remove a track. Return follows realized arrival plus the sampled
indoor gap (above retained history for this controlled source), safe admission
and a new observed ID. Private person linkage never enters aggregation or motion
tie-breaking. Local motion stores its actual position and displacement velocity;
renderer guide polylines are not a promise of exact future movement.

## Acceptance gates

1. Geometry: four independent shop targets, projection/manual overrides, original
   wall preservation, tenant-frontage provenance, continuous usable boundaries,
   body clearance, compatible endpoints and seeded geometric route diversity.
2. Native navigation: head-on passing with available space, crossing flows,
   walls/corners/holes, independent doors, exact arrival/return, bounded search,
   true velocities, deterministic results and no teleporting or physical overlap.
   Check obsolete-guide recovery after waiting and replanning from legal close
   body positions: neither may impose unnecessary detours or exclude all moves.
3. New source: pure 64/128-person finite runs, report max stops, remaining active/
   pending/stalled tracks and rejected/replanned work. Fix counterexamples rather
   than hiding stalled tracks, dropping difficult people or enlarging lifetimes.
4. Normal native capture: GT/sensor cadence, complete lifecycle, semantic/policy
   constraints, immutable publication and journal verification. Independently
   audit all actual positions, sweeps, speeds, body separation and endpoints;
   arbitrary route deviation is legal only inside validated navigation geometry.
5. Public geometry: bounded closed schema; exact native/config/artifact agreement;
   source/tenant IDs and map provenance only, no person/track schedules or links.
6. Preserve old modes and frozen source/output equivalence. Run full configured
   tests, targeted sanitizer checks and actual browser visual acceptance. Keep
   compact test evidence and known model limits in the repository.

Privacy evaluation follows a declared protected unit, secret, observer knowledge
and full-stream comparison on identical recorded motion. Richer geometry and
successful navigation are not themselves measured privacy improvement.
