# Narrow-passage coordination contract

Date: 2026-10-24

## Scope and status

The optional passage coordinator controls opposing pedestrian movement through an explicitly declared narrow passage. It is a source-model movement resource, independent of the aggregation quadtree, aggregation buckets and application Policy Trees. Its direction and admission rules do not establish privacy guarantees or change the aggregator's release constraints.

The default generator path remains unchanged. The experimental path requires `--experimental-narrow-passages` when building or running the mapped scene. This flag enables the exact-topology routing fallback and supplies explicit Barkhof passage metadata; declaring the resource in a native configuration enables its runtime coordination. A missing `navigation.narrow_passages` list leaves the historical local-navigation path in use.

This document records the implementation contract. Measured density cases, regression checks and the acceptance decision are recorded separately in the [test report](NARROW_PASSAGE_TEST_REPORT_2026-10-24.md). A local safety or synthetic completion check does not imply that an arbitrary surrounding crowd will drain.

## Configuration boundary

The optional list belongs to `mapped_scene.motion.navigation` and is accepted only with `mode: local_navigation`. Each entry has this closed schema:

```yaml
narrow_passages:
  - id: barkhof-walking-neck
    centerline: [[x0, y0], [x1, y1]]
    holding_points_a: [[ax0, ay0], [ax1, ay1]]
    holding_points_b: [[bx0, by0], [bx1, by1]]
    protection_radius_m: 1.15
    max_batch_size: 6
```

The coordinates above illustrate the field structure; they are placeholders, not runnable map geometry. Coordinates use local metres with x east and y south. The native representation is `MappedNavigationPassage` in `simulator/include/MappedScene.hpp`; parsing is in `simulator/src/MappedSceneConfiguration.cpp`.

`id`, `centerline`, `holding_points_a` and `holding_points_b` are required. The two numeric fields default to 1.15 m and six tracks. Unknown or duplicate mapping keys are rejected, and each point must contain exactly two scalar coordinates. Native construction then validates the complete configuration before simulation or database opening.

The native constructor requires:

- At most 64 passage resources, with unique nonempty identifiers.
- A centerline of 2–128 nondegenerate, center-safe vertices. Every centerline segment must remain within the allowed center geometry.
- A protection radius of at least twice the largest configured body radius plus motion clearance plus 0.05 m.
- A finite batch size in the range 1–64.
- Between 1 and 256 center-safe holding points on each side, outside the protected tube with at least 0.05 m additional margin. Holding points on one side must have body-clear spacing.
- Every holding point must have direct center-safe visibility to its own passage endpoint, be strictly nearer to that endpoint than the far endpoint, and have endpoint distance greater than `protection_radius_m + 2 * largest_body_radius_m + clearance_m + 0.05 m`. This preserves a body-clear exit area as a native invariant, in addition to the stronger Barkhof staging rule below.
- Nonoverlapping protected passage resources and route endpoints outside their protection tubes.
- Declared building doors at least `protection_radius_m + 7.5 m` from the centerline. The current model deliberately rejects shared door and passage approach resources instead of attempting to coordinate that more complicated case.

## Route participation and finite-cohort restriction

Participation is compiled from route geometry. A participating route must include the **complete declared centerline**, in its original or reversed vertex order, as an interior part of the route. There must be a route segment before entry and after exit. A route may traverse a given resource only once. Matching uses the native geometric tolerance; merely passing near the centerline does not enroll a route.

A route that touches the protected tube without the complete centerline is rejected. The Barkhof generator reroutes such nonparticipants around the protected resource; it does not leave them on an unmanaged path that would later be blocked permanently by native entry guards. If a safe bypass cannot be constructed, generation fails.

The current source model supports a declared **finite cohort**, not an unbounded arrival process. For each passage direction, the constructor counts all scheduled episodes using that direction and requires that count to fit the corresponding declared holding-point list. This is a deliberately conservative capacity check over the full run, not a bound derived from expected concurrent occupancy. Returning episodes count separately. The generator rejects a required capacity above 256 per direction or geometry with insufficient safe holding positions.

This restriction can limit a large experiment even when its instantaneous traffic density is low. Increasing the cohort or changing route demand therefore requires checking capacity; silently enlarging a native queue, dropping tracks or treating scheduled tracks as completed is not supported.

## Runtime sequence

The fixed native movement step remains at the configured value, normally 50 ms. Passage state is updated before candidate movement in each step.

1. An active track requests its next passage when it comes within 8 m of that route's entry point. Requests record simulated request time, direction and the opaque track identifier. Passage ordering does not use private person identity or cross-episode re-identification.
2. All requesting tracks receive persistent, distinct holding goals outside the passage, allocated from the mouth outwards. A track must physically visit its own holding point before it becomes eligible for a grant. Tracks reach their goals through ordinary geometry- and collision-checked movement, with no teleports or instantaneous queue placement. The staging visit is explicitly recorded; a request alone is insufficient.
3. When the resource has no granted tracks, only staged requests enter the eligible set. They are ordered by `(request time, track ID)`, and the oldest eligible request chooses the next direction. Up to `max_batch_size` staged requests already waiting in that direction receive a grant. An older request still approaching its holding point cannot acquire the resource and block physically ready waiters behind an occupied approach.
4. That batch is a finite snapshot. A later same-direction arrival cannot extend the current batch indefinitely. Opposite-direction requests remain queued for a subsequent empty-resource decision. Age order applies within the staged eligible set; there is no unconditional global FIFO promise across unready and ready requests or across individual requests in different directions.
5. Granted tracks approach the entry in request order. A following track must wait until each preceding granted track has passed its entry waypoint and cleared the entry mouth by the required body separation. A direction grant does not authorize all six tracks to target the same entry point simultaneously. Each holding slot remains reserved until its track actually enters; granting access alone must not let a later waiter take that approach position.
6. Inside the controlled centerline, granted tracks follow the audited guide as a single-file lane. Arbitrary steering deviations and repeated local replanning are disabled there. Ordinary free-space steering resumes after the controlled guide. Waiting tracks already at their holding goal do not repeatedly trigger no-progress replanning simply because admission is intentionally delayed.
7. A grant is released only after actual entry, advancement beyond the final passage waypoint and movement outside the protected tube, or after the track has actually finished its route. The resource is never released merely because a timer expires. A new direction cannot be admitted while an earlier granted body still occupies the resource or its protected exit area.

Oldest-ready selection avoids acquiring the resource on behalf of an unready track, while a finite batch prevents unlimited extension by newly arriving same-direction demand. Fairness is conditional on a requester successfully reaching its staging point and on the granted batch subsequently clearing. These rules do not prove bounded travel or waiting time in arbitrary surrounding congestion. An unready track can remain blocked in an approach; a granted track that cannot physically reach or leave the passage keeps its grant and may delay the opposite direction. Such cases must appear as unresolved motion in the diagnostics and finite-drain gate, rather than being hidden by forcibly clearing ownership.

## Barkhof geometry and exit protection

The generator derives the controlled centerline from the existing exact walking topology. It does not widen walking permissions, open building walls or make the entire carriageway walkable to force a successful route.

The current Barkhof generation rules use a 1.15 m protected centerline tube. Holding candidates must be in center-safe walking space, more than 1.30 m from that centerline, and more than 3.55 m from their corresponding endpoint. The endpoint exclusion combines a 2.4 m outgoing apron with the 1.15 m protection allowance. The holding lattice spacing is 1.1 m and each selected holding point must have a directly center-safe segment to its endpoint. The staging areas on the two sides are distinct map-side candidate regions.

These stronger staging rules are generator requirements for this map. Generic native validation checks its own tube, point, spacing and geometry invariants; it does not infer the complete Barkhof 3.55 m endpoint exclusion rule from an arbitrary user-supplied point list. Other imported passages therefore require equivalent deliberate staging design and validation.

## Safety and model boundaries

The existing exact center-segment geometry test and conservative swept-body separation remain authoritative for every accepted movement. A passage grant never bypasses them. The same passage exclusion predicate applies to candidate motion, bounded A* edges and route visibility shortcuts, so a geometrically visible later waypoint cannot silently bypass an idle or oppositely owned resource. The native physical-overlap audit also remains in place. Resource coordination introduces waiting and directional ownership; it does not increase speed, replace trajectories with jumps, or suppress colliding bodies from the simulation.

A waiting point assignment reserves a goal, not an empty corridor to that goal. Agents approaching staging positions can still interact with other pedestrians. A single-file spine and protected exit reduce one identified source of opposing-flow conflict; they are not a complete pedestrian dynamics model, an ORCA implementation or a proof of global deadlock freedom. Multiple passages, nearby unrelated queues and highly congested external approaches need separate analysis. Door/passage overlap and unmanaged passage routes are rejected rather than silently approximated.

## Diagnostics and validation requirements

The native motion diagnostics expose passage waiting steps, batch count, cleared tracks and maximum observed passage wait, together with existing blocked steps, replans, failed replans, maximum stop duration, active/pending/stalled tracks and overlap violations. `MappedSceneConfigurationTests --drain-config <config.yaml> --end-ms <horizon>` includes the passage counters in its aggregate output. These counters describe motion behavior; none is a privacy metric.

The maintained aggregate-only diagnostic executable can be built with `cmake --build simulator/build --target MappedMotionProbe` and called as follows:

```sh
./simulator/build/MappedMotionProbe <local-config.yaml> --end-ms 600000 --wall-budget-s 180 --report-every-ms 10000
```

It emits cumulative JSONL progress and a final record without track IDs or positions. Numeric arguments must be positive decimal integers; the horizon and report interval must align with the native motion step. The report interval defaults to 10000 ms. It stops when the complete finite cohort has ended, at the simulated horizon, or at the wall budget, and returns 0, 3 or 2 respectively. Invalid input returns 64; a runtime motion exception returns 1. The budget is checked between advances, so one native advance cannot be interrupted halfway through its safety update.

The probe measures each `advanceTo` call separately and reports cumulative mean, nearest-rank p50/p95/p99, maximum and the number exceeding 50 ms. It also reports peak active tracks sampled after every native step and the latest realized end time. `setup_wall_ms` includes YAML parsing, validation and construction; `constructor_wall_ms` measures the final scene construction separately. `total_wall_ms` additionally includes diagnostics and reporting overhead. These timing scopes must remain distinct in performance comparisons. If setup alone consumes the budget, the timing sample count is zero and quantiles are reported as zero rather than treated as measurements.

Validation should distinguish three questions:

- **Safety:** Does every accepted segment remain center-safe, do swept bodies remain separated, and are opposing grants excluded until full clearance?
- **Finite completion:** Does every scheduled episode produce exactly one realized start and end within the declared simulated horizon, with no active, pending or stalled tracks left and no overlaps?
- **Computational cost:** What wall time and per-step latency were measured for this exact source, configuration and machine, including repeated search costs and queue behavior?

For an opposing-flow regression, check finite batches, ordered entry, a late same-direction arrival, a waiting opposite direction, occupied exit clearance and all-track lifecycle completion. Configuration tests also check legacy omission, numeric defaults, strict parsing and rejection of invalid geometry or capacities. A passing synthetic case is necessary evidence for local rules, but is insufficient evidence for actual-map performance or source validity.

Use the same finite source, routes, types, speeds, seed and demand schedule for an on/off coordination comparison wherever the unmanaged input remains meaningful. Enabling the experimental topology can change which routes are reachable and reroute approaches; such a source change must be recorded rather than attributed solely to runtime coordination. Policy comparisons must use the same realized observation stream after source validation.

## Density, short runs and real-time claims

A cohort size is the number of modeled people over the run. Episode count can be larger because building visits split visible trajectories. Neither number alone states density. Report the arrival interval/rate, observed peak simultaneous active tracks, directions, body/type mix, simulated duration and region area. A larger finite cohort with the same arrival interval mainly extends demand duration; a shorter interval increases concurrent pressure and may increase queue occupancy.

Short diagnostic runs are useful for finding immediate admission or collision defects. They are right-censored when scheduled or active episodes remain at the stop time. Report starts, ends, active and pending tracks separately, and do not interpret uncompleted work at a deliberately short horizon as lost data or as a successful drain. A finite-drain run uses a horizon long enough to test completion of the complete declared cohort and still has an explicit wall-time budget.

Compare low and higher arrival pressure without changing time step, speed, clearance or geometry to make the dense case pass. Retain the accepted default source as a reference. The first dense actual-map gate must pass before the experimental resource can be treated as an accepted replacement for that reference.

Liveness remains conditional on reachable, sufficiently clear approaches and exits, an admissible finite cohort, and successful surrounding motion. Measured wall time below a simulated step is an empirical performance observation, not a hard real-time guarantee. No worst-case execution-time bound, scheduling guarantee or end-to-end application deadline guarantee is claimed by this coordinator.
