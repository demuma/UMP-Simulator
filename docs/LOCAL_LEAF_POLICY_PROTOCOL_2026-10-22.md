# Local finest-leaf policy mechanism protocol — 2026-10-22

Status: predeclared before the four production replays and repeat. This protocol is immutable once the study starts.

## Question and scope

Can the existing compiled regional Policy Tree change semantic and spatial release decisions for a few finest leaves, while preserving truthful counts and hard requirements? This deterministic analytical fixture is a mechanism test, not a realistic traffic simulation, statistical effectiveness study, or empirical privacy experiment. It uses the existing C++ aggregation core through the offline replay adapter, no MongoDB and no changes to the normal simulator configuration, taxonomy implementation or controller.

## Frozen input

One source contains 20 stable identities observed at 100-ms cadence strictly inside (0, 2000 ms), in an 80 × 80 m area at depth 6 (4096 possible 1.25-m leaves). Small deterministic coordinate variations stay within the predeclared finest cells; identities and types never change. Every variant uses exactly this input and the same executable. There are no arrivals, tracking errors, unavailable samples or missing samples. The existing seven-profile release taxonomy is retained.

Six groups are deliberately separated by more than the root's 5-m maximum output side:

| Group | Members and position | Mechanism question |
|---|---|---|
| Control west | Four Adult Pedestrians near (2.8, 2.8) | Unaffected fine release |
| Semantic patch | Two Adult and two Child Pedestrians near (10.3, 10.3) | Exact subtypes pass the root; stronger local support requires Pedestrian |
| Spatial patch | Two Adult Cyclists near (20.3, 10.3), two Senior Cyclists near (21.6, 10.3) | Combine sibling leaves and generalize to Cyclist |
| Infeasible patch | Three Adult E-Scooter Drivers near (30.3, 10.3) | Root passes, local support four remains impossible |
| Empty-patch guard | One Adult Cyclist near (42.8, 10.3), another near (40.3, 12.8) | Root can combine them in a 5-m cell; an empty stricter leaf touched by that cell must also constrain it |
| Control east | Three Adult Pedestrians near (50.3, 10.3) | Unaffected fine release |

Expected input: 19 complete samples × 20 identities = 380 observation contributions. Repeated appearances never increase distinct-person support.

## Root policy and four local patches

Root: category distinct support at least 2; overall distinct support at least 1; semantic maximum loss at most 1; cell side in [1.25, 5] m; duration and interval-start age at most 1000 ms. Base probe 400 ms; extension 100 ms; common-window coordination; release trigger `policy_satisfied`. History is bounded to 2000 ms, 32 bins, 100000 observations, 16000000 identity bytes and 128 buckets; spatial search is bounded to 8192 evaluations and min depth 4.

| Region | Aligned geometry | Stronger requirements |
|---|---|---|
| semantic-patch | [10,12.5) × [10,12.5), four leaves | Category support ≥3, semantic loss ≤0.5 |
| spatial-patch | [20,22.5) × [10,12.5), four leaves | Category support ≥4, semantic loss ≤0.5 |
| infeasible-patch | [30,32.5) × [10,12.5), four leaves | Category support ≥4, semantic loss ≤0.5 |
| empty-guard-patch | [40,42.5) × [10,12.5), four leaves, no observations | Category support ≥5, side ≤1.25 m, duration and age ≤600 ms |

The patches cover 16 of 4096 finest leaves (0.390625%). They are disjoint. Region instance requirements combine with inherited root requirements by maximum lower bound and minimum upper bound on every positively intersected footprint. Zero-area boundary contact must not apply a region. The policy on an output cell applies even if the touched part of a region contains no observations.

## Four comparisons, declared expectations

1. Uniform root policy, Semantic First → Temporal Second.
2. Local patches, Semantic First → Temporal Second.
3. Uniform root policy, Semantic First → Spatial Second.
4. Local patches, Semantic First → Spatial Second.

The default immediate policy trigger is expected to make the two secondaries equal within each policy; equality is not a bug or a ranking. Root-only is expected to retain all input with 400-ms releases and exact categories. Local patches are expected to retain the 15 identities outside the infeasible and guard groups (75% of observations), generalize the semantic patch to Pedestrian, combine the cyclist siblings into a 2.5-m Cyclist cell, and suppress the three scooter and two guard contributions. Both control groups should retain exact types and 1.25-m cells.

The unresolved groups prevent an early complete cut under common-window coordination. The empty guard's 600-ms time bound is expected to cap the shared interval, including unaffected groups, despite containing no observations. This explicitly probes an existing limitation; the experiment does not introduce independent semantic cell windows. End-of-file may close a final interval shorter than the base probe. No claims depend on an optimal cut or on synthetic density matching a real street.

## Freeze, execution and independent checks

Before execution archive input, all four policies, this protocol, the runner and its imported audit dependencies, exact replay executable and implementation-source hashes; record commands. Refuse an existing output directory. Save stdout/stderr and exit status. Repeat the local Temporal Second variant and compare the complete result excluding runtime.

Independently rebuild published geometry, original observations, identity unions, complete truthful semantic antichains, support, declared weighted loss and region intersections. Enforce hard bounds from geometry-based regional resolution, including duration and age. Apply the established scalar replay oracle only after an explicit semantic projection. Independently inspect final private diagnostics for failure evidence. Count every retained or suppressed observation exactly once. Mutated semantic counts and prohibited coarse releases must fail the audits. Check the source is identical across policies and that the 16-leaf area and zero-area boundaries are exact.

Publish the small complete fixture, policies, production outputs, audit reports, repeat and hashes as a private research replay bundle suitable for cell inspection. These artifacts expose raw identities/types and are not an anonymized release product.
