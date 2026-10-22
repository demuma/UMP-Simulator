# Local finest-leaf policies: results and test report — 2026-10-22

The existing regional Policy Tree already changes numeric requirements on a few finest leaves. This experiment makes those changes inspectable together with original group composition, released categories, merges and suppression. No C++ aggregation algorithm, taxonomy model, motion simulator or MongoDB configuration was changed for this study.

The [protocol](LOCAL_LEAF_POLICY_PROTOCOL_2026-10-22.md) was fixed before production runs. Complete outputs are in `results/local-leaf-policy-2026-10-22/`; the compact reproducible fixture and four policies are in [simulator/examples/local-policies](../simulator/examples/local-policies/README.md). The runner is [run_local_policy_replay.py](../tools/evaluation/run_local_policy_replay.py).

## What the fixture represents

The source is an explicitly scripted analytical fixture: 20 stable synthetic identities, 19 complete samples at 100-ms cadence strictly inside a 2000-ms replay, 380 observation contributions. Small deterministic coordinate variations preserve the occupied finest cells. It does not represent validated walking behavior, realistic traffic, new agents arriving or a capture from the full simulator.

The 80 × 80 m area has depth 6, hence 4096 possible 1.25 × 1.25 m leaves. Four disjoint 2.5 × 2.5 m patches affect 16 leaves, or **0.390625%** of the possible finest area. Source groups are separated beyond the root's 5-m maximum output size. The same input and executable are used in every variant.

The root requires at least two distinct identities per published semantic category, permits declared loss up to one, and caps output side at 5 m and interval duration/age at 1000 ms. The initial probe is 400 ms, extension step 100 ms. Both Semantic First secondary orders use the immediate `policy_satisfied` trigger.

## Observed comparisons

| Policy | Second priority | Retained observations | Released cells | Published intervals in ms | Mean interval-start age | Observation-weighted semantic loss |
|---|---|---:|---:|---|---:|---:|
| Uniform root | Temporal | 380/380, 100% | 35 | 400, 400, 400, 400, 400 | 400 ms | 0 |
| Four local patches | Temporal | 285/380, 75% | 16 | 600, 600, 600, 200 | 557.895 ms | 0.266667 |
| Uniform root | Spatial | 380/380, 100% | 35 | 400, 400, 400, 400, 400 | 400 ms | 0 |
| Four local patches | Spatial | 285/380, 75% | 16 | 600, 600, 600, 200 | 557.895 ms | 0.266667 |

Cells are counted across all release intervals. Mean age and semantic loss are weighted by retained observation contributions, not by cells. The final 200-ms interval closes at EOF and is shorter than the base probe. The two secondary orders have exactly equal recipient `releases` arrays within each policy; their private strategy metadata differs as declared. The default immediate policy trigger can make these secondary preferences observationally equivalent. This is not evidence that the two strategies are generally equivalent.

### Decisions that can be inspected cell by cell

| Group / location | Uniform root | Local result |
|---|---|---|
| Four Adult Pedestrians near (2.8, 2.8) | Exact type in 1.25-m cell | All 76 observations retained; exact type and same fine cell |
| Two Adult + two Child Pedestrians near (10.3, 10.3) | Exact subtypes, each support two | Local support three and maximum loss 0.5 lead to **Pedestrian**, support four, in the same 1.25-m cell; all 76 observations retained |
| Two Adult Cyclists near (20.3,10.3) and two Senior Cyclists near (21.6,10.3) | Separate fine cells with exact type | Local support four and loss ≤0.5 require a **2.5-m sibling merge** with **Cyclist**, support four; all 76 observations retained |
| Three Adult E-Scooter Drivers near (30.3,10.3) | Exact type; all 57 observations retained | Support three remains below local four even after every permitted merge; 57 observations suppressed |
| One Adult Cyclist near (42.8,10.3), another near (40.3,12.8) | A 5-m parent truthfully represents both, support two | The parent intersects the empty strict patch [40,42.5) × [10,12.5), inheriting side ≤1.25 m and support ≥5; neither outside leaf reaches root support two alone; 38 observations suppressed |
| Three Adult Pedestrians near (50.3,10.3) | Exact type in 1.25-m cell | All 57 observations retained; exact type and same fine cell |

The local retained source total is 15 × 19 = 285 observations. The loss 0.266667 follows directly from eight retained identities using loss-0.5 intermediate categories and seven using loss-zero exact categories: `(8 × 0.5 + 7 × 0) / 15`. It is a configured taxonomy abstraction cost, not a measured percentage of privacy protection or a calibrated information-theoretic loss.

Failed private diagnostic candidates may show Road User and loss one while exceeding a local loss limit. These are rejected candidates; they are not published semantic values. Only recipient `releases` contribute to the reported retained loss.

## Important algorithmic limitations exposed

**The 600-ms bound on the empty guard patch caps the whole shared window.** The first local finalization is `[0,600)` with `completion_reason: policy_deadline`, even though the guard itself contains no observations. Other intervals are `[600,1200)`, `[1200,1800)` and the EOF tail `[1800,2000)`. Valid control groups wait while the shared full cut remains impossible. Their effective spatial/type requirements stay unchanged, but their timing is coupled globally. This is a limitation of the current common-window semantic integration, not a new implementation of independent local temporal windows.

**A small patch can affect observations outside itself through an intersecting coarse footprint.** This is the declared conservative whole-footprint rule, not accidental policy inheritance between adjacent fine leaves. The guard's east and south neighbours merely touch its boundary and retain root bounds when evaluated alone. Their joint 5-m parent has positive-area overlap with the guard and must obey it. Since neither fine cell alone reaches support two, both contributions are suppressed. Future regional-policy work should explicitly evaluate this cost rather than assume that every point outside a patch has unchanged output.

The artificial fixture deliberately isolates these mechanics. It neither establishes a benefit over a strong uniform-grid baseline nor measures an attacker, optimality, real-world usefulness or simulator realism. Its 20 identities are sufficient for the hand-worked integration cases; it is not a population-size effectiveness study.

## Verification and tests

Four production C++ replays passed separate independent scalar and semantic audits. The scalar oracle rebuilds geometry, source observations, coverage, inherited numeric regional bounds, retirement and no-double-publication accounting after an explicit semantic-only projection. The semantic audit independently rebuilds each published category's observation count and identity union, truthful complete antichain, declared maximum and weighted losses, and strongest bounds from strict positive-area geometry intersections. It does not reuse C++ policy IDs or pass flags as its reference.

Across all four variants, **102 published cells and 112 published semantic bins** were checked. Every released cell obeys its independently resolved support, loss, spatial and temporal bounds. All 380 observations are accounted for in each variant. An extra local Temporal Second replay matches the complete scientific result exactly after removing runtime; its output is also re-audited.

[Five regression test methods](../tools/evaluation/test_local_policy_replay.py) passed, exercising six actual C++ replay calls:

1. Exact source cadence, counts, stable identity/type/cell membership, 16-leaf area and genuinely empty guard patch.
2. Strongest-bound resolution for a coarse footprint touching an empty patch, with no inheritance across zero-area boundary contact.
3. All four policy/secondary variants: hand-worked intervals, retained counts, control preservation, intermediate Pedestrian release, Cyclist sibling merge, suppression and identical recipient outputs between secondaries.
4. Rejection of corrupted semantic identity counts and rejection of the root's coarse release when assessed against the stricter local policy.
5. An unavailable sample cannot be relabelled as complete or create a release for the incomplete interval.

Run the targeted tests with:

```sh
python3 -B tools/evaluation/test_local_policy_replay.py -v
```

Inputs, four policies, exact commands, protocol, executable, runner/audit dependencies and implementation-source hashes were frozen in `pre-execution-manifest.json` before execution. `study-manifest.json` hashes 34 artifact files; it excludes itself to avoid a circular digest. There were five production calls including the determinism repeat, distinct from six calls made by the regression tests. The study never opens MongoDB and does not launch the normal Simulator.

## How to inspect the result

```sh
python3 -B tools/replay_viewer/serve.py \
  --bundle results/local-leaf-policy-2026-10-22 --check
python3 -B tools/replay_viewer/serve.py \
  --bundle results/local-leaf-policy-2026-10-22 --port 8771
```

Compare Uniform root and Local patches, seek to 600 ms, select a cell near (10,10) or (20,10), and inspect raw snapshot composition separately from published interval composition. The source snapshot at 600 ms is not the same object as `[0,600)`'s five samples. Enable private diagnostics for rejected footprints near (30,10) and (40,10), actual failed bounds and local region outlines. Raw identities and original types remain private debug information; they are not added to the recipient product.
