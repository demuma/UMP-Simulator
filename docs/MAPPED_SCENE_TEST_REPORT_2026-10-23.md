# Mapped 80-m scene: implementation and verification

Date: 2026-10-23. Status: **M01 complete within the bounded contract**.
See the [identity/source contract](MAPPED_SCENE_IDENTITY_CONTRACT_2026-10-23.md)
and [run guide](../tools/mapped_scene/README.md).

## Implemented increment

The maintained Simulator has an opt-in `simulation.scenario: mapped_visits`.
It reads explicit routes, schedules and observed profiles before any database is
opened. Its deterministic standard-C++ source follows each polyline by arc length,
handles corners and arrivals, hides visitors indoors, and starts a new observation
track when they return. Legacy random motion and collision handling are unchanged.

The mapped scene uses existing Agent objects, all existing sensor interfaces,
the normal Region taxonomy / PolicyTree adapter, semantic selection and durable
publication. It does not generate a substitute stream of observations outside
the Simulator. In this first mapped source, motion is scheduled and kinematic;
the legacy collision solver is not used to alter the prescribed routes/schedules.
Crowd interaction, body clearance, interior movement and calibrated visitor rates
are not established by this increment.

The live Renderer can show the aligned map background and actual polyline past /
future segments. It keeps existing overlay, arrow and buffer toggles. Explicit
UTF-8 decoding fixes the Cocoa window-title crash triggered by the new
Mönckebergstraße title and correctly decodes the OSM attribution.

## Source and illustrative policies

| Source property | Setting |
| --- | --- |
| Sensing domain | 80 × 80 m, D6, 1.25 × 1.25-m finest cells |
| Clock | 50-ms simulation step; 100-ms AGBS measurements |
| Full verification duration | 90 s / 1,800 numerical steps |
| Scheduled modeled people | 64 |
| Visible episodes / observation tracks | 80 |
| Building visits | 16 |
| Types | 16 Adult Pedestrian; 12 each Child, Senior, Stroller and Mobility Aid |
| Routes | Two through directions, one arrival and one departure route |
| Actual OSM portal/building | Node 6244468529 / way 43117523, Rappolthaus |
| Indoor gap | 8 or 10 s; minimum 8 s |
| Retained history / maximum candidate | 6 s / 4 s |

Route geometry is checked against the frozen real OSM walking and building
geometry. Each centre line has zero positive length inside building interiors
and zero length outside the derived walking geometry, within documented floating
point tolerances. The portal is on the mapped facade. The building's function is
not verified as residential. The background and corridor widths retain the
assumptions from the [OSM feasibility test](OSM_MOENCKEBERG_FEASIBILITY_2026-10-23.md).

Four disjoint raster-aligned policy patches use the actual `region_taxonomy`,
`regions` and `policy_tree.regions` configuration path. Root distinct total and
positive-category support is at least five; cell side 1.25..10 m; duration
400..4,000 ms; age at most 4,000 ms; semantic loss at most one. The entrance raises
total support to ten. Independent footway patches tighten maximum size, time and
semantic loss. These are illustrative experimental requirements, not protection
values inferred from OSM or validated legal/privacy thresholds. Compilation
produces 117 nodes and eight effective policies.

Speeds are explicit type-independent synthetic inputs in [1.1, 1.5] m/s. No age,
diagnosis or legal precedence is inferred from aid/equipment labels. Circular
equipment radii are model assumptions. The modeled mover plus equipment is one
contributor; a stroller occupant is not counted as a second observed unit.

## Identity boundary and support interpretation

- The private simulator/evaluator retains stable synthetic person identity and
  lifecycle events. This is ground truth, not a re-identification implementation.
- Sensor-facing Agent objects carry only fresh visible-episode track IDs in the
  existing `agentId` field. The private person registry is not passed to sensors
  or aggregation. Private GT records contain a separate `private_person_id` for
  later evaluation.
- Recipient releases contain neither individual ID namespace nor their mapping.

Operational support is distinct **track** support. For this specific long-gap
scene it equals modeled-person support within every audited published candidate:
the hidden gap exceeds the entire retained history. Startup validates that
assumption for every enabled aggregation. This is not a general solution for
fragmented tracking.

A real-sensor counterexample intentionally uses a shorter gap: one private person
produces two tracks inside one 2-s AGBS window. The candidate reports two tracks,
not an oracle-deduplicated person. ABS also performs velocity warm-up on the new
return track, rather than connecting it to the earlier episode. Shorter-gap
person-level claims require a separate conservative-support/uncertainty gate.
Resetting IDs does not prevent inference from public geometry and timing.

## Verification

- Release build passes.
- **77/77 CTest suites pass**, final run 20.42 s. This includes the augmented
  UUID-isolated ABS/GBS/AGBS regression and three new mapped-scene suites.
- **8/8 offline generator tests pass**: frozen geometry, exact groups, deterministic
  schedules/tokens, normal regional configuration, interval separation, invalid
  routes, isolated destinations and exact background dimensions.
- Final standard-C++ route/lifecycle tests pass **AddressSanitizer and UBSan**.
- Two full native 90-s runs use the **same binary**. Only private GT names and the
  necessarily isolated database namespaces change. Independently audited raw sensor
  contents and recipient contents have identical normalized SHA-256 hashes.
- A separate **20-s rendered smoke test exits successfully** after the UTF-8 fix.
  The 800 × 800 background was visually inspected. Computer Use could not bind the
  unbundled CLI application, so no live-window screenshot/layout verification is
  claimed. The earlier title crash is fixed, not counted as a successful run.

The independent read-only audit reconstructs source visibility, positions, hidden
absence, lifecycle events, every raw occupied D6 cell/type count and every released
cell's support, occupancy and semantic partition. It independently combines root
and intersected region bounds, checks nonoverlapping public space-time support,
checks identity separation and verifies durable journal/recipient agreement.
Its position tolerance is 20 micrometres; observed maximum source/reference error
was 4.183 micrometres due to float conversion.

## Actual results on the frozen scene

Both paired runs produce the same results:

| Audit quantity | Result |
| --- | --- |
| GT visible-state rows | 77,453 |
| Private lifecycle events | 160 |
| Measured sample slots | 899 |
| Measured observation contributions | 38,709 |
| Raw occupied sensor-cell records | 22,084 |
| Recipient documents / cells | 1,050 / 1,050 |
| Published observation contributions | 33,692 |
| Retained observation fraction | 87.0392% |
| Checked policy violations | 0 |
| Overlapping public space-time cells | 0 |
| Published track/person support inflation | 0 within the long-gap source contract |
| Published category | Pedestrian for all retained contributions |
| Maximum configured semantic abstraction cost | 0.5 |

The retention denominator is **all measured observation contributions**, not only
published cells. Retention is not query availability or a privacy score. All
published data generalize to Pedestrian, so detailed subtype query answers are
unavailable; loss 0.5 is the configured hierarchy cost, not a measured percentage
of lost privacy/information. No baseline superiority or privacy gain is inferred.

The output actually uses multiple spatial resolutions: 181 cells at 10 m,
514 at 5 m, 317 at 2.5 m and 38 at 1.25 m. Aggregation durations span 400–4,000 ms;
983 of the 1,050 releases use 400 ms. These are actual selected cells/windows,
unlike the earlier static D6 map figure.

Private journaling includes **10,581 committed documents**: 1,050 nonempty payloads
exactly match the recipient, and 9,531 are private empty-retirement checkpoints.
Those empty checkpoints are not public empty statements or duplicate releases.
The independent audit was corrected to distinguish these roles after initially
assuming all journal entries should correspond to recipient documents. Mechanism
and policies were unchanged.

Native headless binary wall time was 9.783 s and 10.071 s for 90 s of source time
(gross speedup 9.20 and 8.94). This includes startup and DB I/O. It is not a
per-step deadline bound, a renderer speed comparison or an optimization result.

Machine-readable [paired results](MAPPED_SCENE_RESULTS_2026-10-23.json),
[resolution statistics](MAPPED_SCENE_AGGREGATE_STATISTICS_2026-10-23.json) and
[cleanup record](MAPPED_SCENE_CLEANUP_2026-10-23.json) accompany this report.

## Cleanup and next gates

All 15 explicitly owned live-test database names are absent after verification.
The paired runner removed its six namespaces; the rendered tests removed theirs;
the initial source's three remaining namespaces were removed after its audit.
No `Simulation` database or pre-existing dataset was touched. No sampled motion
or observations were exported to files or committed. Static routes, schedules,
backgrounds and compact results are the reproducible source definition/evidence.

Next review this source's flow, kinematic limitations and illustrative task/policy
requirements. Then compare fixed grid/window, static regional settings and adaptive
settings on identical observations. Preserve unfavorable results as well.

The subsequent performance gate is explicitly retained: profile route/Agent-frame
assembly, sensor capture, policy/semantic checks, history and merge queries,
diagnostics and publication. The 9,531 private empty checkpoints are a concrete
I/O workload to inspect; their runtime share and durability trade-off have not
been isolated here. Optimize one cost at a time with unchanged output evidence.
