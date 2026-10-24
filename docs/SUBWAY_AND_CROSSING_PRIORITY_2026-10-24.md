# Typed subway access and crossing priority

Date: 2026-10-24. This is an opt-in movement-source extension. Existing aggregation recordings, comparison results and privacy policies remain unchanged. Both switches default to off and require `--urban-traffic`.

## Source provenance and overhead context

`tools/osm_regions/data/moenckeberg/subway_surface_metadata.json` preserves the reviewed public OSM A1/A2 node identity, exact coordinates, versions, timestamps, stop-area membership, stairs/accessibility tags, and associated canopy/surface-way identities. It is tied to the original XML and frozen compact-source hashes documented in [the feasibility review](SUBWAY_ACCESS_PLAN_2026-10-24.md). `transit_access.py` checks the supplement's SHA-256, exact source hash and matching frozen geometry before use. Ordinary generation does not require the large temporary XML or a new network acquisition.

Only ways **425508816 and 425508817**, checked as `building=roof`, `layer=1`, are removed from the ground-obstacle union. Their separate original polygons remain in public map context with `overhead: true` and `ground_obstacle: false`. Unrelated roofs and uncertain/non-ground structures remain conservative obstacles. Underground stairs are not added as surface through-routes.

The station access coordinates remain the exact OSM nodes:

| Access | Source node | Local metres, x east / y south |
| --- | --- | --- |
| A1 Barkhof | 280355670 | 77.55428756435867, 61.90388976410031 |
| A2 Spitalerstraße | 348025368 | 64.45375276682898, 13.808432191610336 |

## Surface portal contract

A surface portal is explicitly typed and has no building ID or fabricated facade:

```yaml
kind: surface_access
id: subway-A1
point: [77.55428756435867, 61.90388976410031]
admission_segment: [[...], [...]]
approach: [...]
width_m: 1.2
provenance: osm
```

The supplied cross-section is centered on the source point and perpendicular to a 1.5 m approach in the direction of the exact connected surface way. Both segments must fit the existing body-safe movement geometry. The **1.2 m opening is a scenario assumption**, not a surveyed stairwell width. Existing facade portal configuration is unchanged.

Only trips explicitly referencing a surface portal start/end visibility there. Unrelated passers may traverse its neighborhood without disappearing. Existing finite same-direction door batches and physical source admission apply; opposite-direction batches cannot use the same occupied throat simultaneously. All center-space and swept circular-body checks remain active. No new wall-clearance exemption is granted to a surface portal.

The opt-in generator selects approximately 15% of the total cohort, at least four eligible people, using an independent seeded choice. These are independent single-episode boundary-to-station or station-to-boundary trips, distributed across A1/A2 and both directions. They are not forced to reappear after disappearance. Eligible classes are Adult, Child and Senior Pedestrian. Stroller and generic mobility-aid classes are excluded because the exact accesses have `wheelchair=no` and stairs with `ramp=no`; individual stair ability is not inferred from a generic label. Demand rates and widths are not calibrated station measurements.

Operational track IDs are fresh and unique, and private person identities remain absent from sensor/aggregator input. Existing shop-return hidden gaps still exceed retained aggregation history. Distinct-track support continues to be a track-level operational condition, not proof of distinct real people.

## Rider-priority crossing admission

`--rider-priority` adds five explicit conflict resources where the declared synthetic crossing corridors intersect the carriageway. Each contains a simple ground-space conflict ring, the two priority navigation-space IDs, and bounded settings:

| Setting | Current source value |
| --- | ---: |
| Rider guide lookahead | 4,000 ms |
| Pedestrian request age triggering fair closure | 8,000 ms |
| Pedestrian batch admission window | 2,000 ms |
| Maximum finite pedestrian batch | 6 tracks |
| Minimum subsequent rider service interval | 1,500 ms |

This is a **synthetic scenario priority rule**, not an assertion about legal right-of-way at the mapped location. OSM does not provide the behavior or demand calibration.

For body radius \(r_i\), hard clearance \(c\), conflict area \(C\), and proposed swept center segment \(S_i\), entry is tested using the conservative condition

\[
 d(S_i,C) \le r_i+c+10^{-7}\,\mathrm m.
\]

The small final term is a numerical comparison tolerance. Physical body radii and hard clearance are not reduced. Admission remains an additional restriction; it never replaces center-space containment or the authoritative swept-body collision predicate.

The lifecycle is:

1. A pedestrian about to enter requests admission and waits **before its body enters the carriageway conflict area**.
2. New pedestrians yield while a priority rider is inside or its guide-projected path could reach the conflict area within lookahead. Projection uses configured speed, even for a temporarily stopped rider; it is a conservative source prediction, not inferred intent.
3. When clear, a finite oldest-request-first pedestrian batch is granted. New riders wait before entry while this batch clears. A pedestrian already crossing is always allowed to finish, subject to physical collision checks.
4. Continuous rider demand cannot extend initial priority indefinitely: after the configured request age, admission of **new** riders closes. Riders already inside may clear. Only when the area is empty does the finite pedestrian batch begin.
5. Unentered grants expire after the admission window. Completed/abandoned requests are removed, and a cleared batch reopens a minimum rider service interval before another pedestrian batch. Expired or cancelled demand cannot leave a stale road closure.

Candidate steering checks do not create requests: only the intended entry attempt does. This prevents an unused alternate steering candidate from closing a crossing for a pedestrian that never intended to enter it.

The maximum wait parameter is a **phase-switch trigger**, not an unconditional pedestrian service deadline. An existing physically blocked body cannot be erased or teleported to satisfy it. Fairness therefore remains conditional on occupied bodies clearing and a feasible downstream route. No global deadlock proof, traffic signals, calibrated braking dynamics, ORCA or hard real-time guarantee is claimed. Existing dense-source capacity limits remain separate acceptance questions.

Per-step work adds a scan over active bodies for each configured crossing and simple ring/guide tests; configuration permits at most 16 resources, 16 priority spaces per resource and 64 tracks per batch. The current source uses five resources and six-track batches. This is movement-source work outside the isolated aggregation deadline measurement.

## Diagnostics and verification

The native source summary, `MappedMotionProbe` JSON and native drainage output expose:

- `crossing_pedestrian_wait_steps` and `crossing_rider_wait_steps`;
- `crossing_batches` and `crossing_fairness_closures`;
- `max_crossing_pedestrian_wait_ms` measured to grant;
- existing starts/ends, active/pending/stalled bodies, speed, geometry and overlap diagnostics.

The focused native tests cover typed portal rejection, exact surface arrival/departure, unrelated passers, preserved speed/displacement/body clearance, rider free-flow preservation in an uncongested crossing fixture, already-crossing pedestrian completion, finite continuous-rider demand and deterministic caller cadence. A malformed or inaccessible source cannot silently acquire a fabricated building entrance.

Source tests verify provenance mismatch rejection, conservative canopy classification, exact admission geometry, both station directions, excluded stair-incompatible profiles, unique episode tokens, unchanged radii, deterministic generation and a complete historical source/context/construction/audit golden digest with both switches off.

The initial, pre-staging combined 64-person source, seed 20261024 and 500 ms first-arrival spacing, produces **85 visible episodes**, all observed at the 100 ms sensor cadence and all finished by **151,000 ms**. It has zero final active/pending/stalled tracks and zero body overlaps. It records 22 pedestrian batches, eight fairness closures, 3,014 pedestrian waiting steps, 614 rider waiting steps and a 14.1 s maximum request-to-grant wait. The measured wait explicitly demonstrates why the 8 s age threshold is not a service deadline. This is a finite correctness fixture, not a general density or real-time claim. The larger independent capture and final commands are recorded in the parent implementation test report.

## Dense negative control and receiving-apron correction

The first 128-person, 150 ms arrival version did **not** pass finite-source acceptance: at 300 s it had 159 of 171 starts, 97 ends, 62 active tracks, 12 pending episodes and 26 stalled tracks. Recorded body overlaps remained zero. The consistent local capture is preserved as `results/urban-transit-priority-2026-10-24-v2/replay`; its proof explicitly states `all_scheduled_episodes_completed: false`. A successful export verifies recording consistency, not drainage. The [compact negative evidence](verification/transit-priority-dense-negative-2026-10-24.json) retains this failed result.

The receiving-apron diagnosis is concrete: a waiting pedestrian frozen at the curb can block the exit of an already admitted pedestrian from the opposite side. The admitted body then cannot clear its resource; revoking its occupied grant would be unsafe. The correction assigns bounded, directly reachable staging goals off the receiving apron when waiting is necessary. A receiving center path extends 1 m beyond the directed road exit; actual separation includes both body radii plus the hard clearance and a 0.1 m operational margin. Holding targets use the same pair-aware apron with an additional 0.15 m staging margin. Goals are selected on a 0.5 m candidate lattice within 6 m, with exact movement permissions, current body occupancy and body-aware spacing. A holding point must satisfy the same directed entry-distance eligibility as its finite admission grant; it is revalidated when the route guide changes. Failed placement retries at most once per second. Waiting bodies move normally towards these goals, and no teleportation, smaller body or new walking surface is introduced. Admission checks each candidate's directed receiving apron against every relevant ungranted active body. A blocked or unstageable requester cannot veto an unrelated ready candidate. A singleton may cross a clear road directly even when its narrow entry sidewalk has no backwards staging room. Sources without sufficient staging room remain an explicit capacity limitation.

Stale entry intent is checked against the remaining route guide; cancelled requests cannot retain closure or parking targets. Independently scheduled conflict rings must have disjoint logical body-plus-clearance inflations: their separation must exceed twice the maximum body radius plus twice the hard clearance (and the comparison tolerance). Overlapping, nested and body-close rings are rejected. Fresh pedestrian and rider sources are also forbidden inside a controlled conflict area, so an active phase cannot be bypassed by a newly spawned body. They are rejected instead of introducing hidden multiple-resource dependencies. The current five rings satisfy this bound (minimum separation approximately 4.81 m).

A deterministic opposite-apron regression requires the waiting body to remain outside the receiving apron while the admitted opposite body crosses; both pedestrians and riders must then complete. The corrected source passes the same 128-person finite native gate: all 171 episodes finish by 190.4 s, peak active population 121, with zero final active/pending/stalled bodies and zero reported overlaps. An otherwise identical control with only crossing declarations removed finishes all 171 by 180.85 s. These [serial source controls](verification/transit-priority-source-controls-2026-10-24.json) separate the initial priority bug from map/demand effects. Priority is a behavioral rule with measured costs, not a claim of universally faster traffic. The corrected run records 36 finite batches, 13 fairness closures and 17.4 s maximum request-to-grant wait. The fresh 128-person end-to-end replay passes the independent physical and sensor-clock audit: all 171 episode tokens are observed and completed, with 6,111,306 swept-body pair checks and zero reported overlaps. A1/A2 contribute 10 independent entries and nine independent exits. See [the detailed test report](SUBWAY_AND_PRIORITY_TEST_REPORT_2026-10-24.md) and [compact accepted evidence](verification/transit-priority-accepted-source-2026-10-24.json).

## Reproduction

```sh
cmake --build simulator/build --target MappedSceneTests MappedSceneConfigurationTests MappedMotionProbe -j 2
./simulator/build/MappedSceneTests
./simulator/build/MappedSceneConfigurationTests
python tools/mapped_scene/test_transit_access.py
UMP_TRANSIT_DRAIN_TEST_BINARY="$PWD/simulator/build/MappedSceneConfigurationTests" \
  python tools/mapped_scene/test_transit_access.py \
  TransitAccessTests.test_native_combined_source_drains_and_all_tracks_are_observed
```

Use the mapped-scene Python environment from `tools/mapped_scene/requirements.txt`. A new recorded source can be requested with `run_scene.py --urban-traffic --subway-access --rider-priority`; it receives a fresh owned UUID namespace. Generated movement recordings remain local ignored artifacts, and do not replace the frozen benchmark.
