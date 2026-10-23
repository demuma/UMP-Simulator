# Three functional-region scenarios: staged evaluation plan

Date: 2026-10-23. Status: planned, with proposed illustrative thresholds. No scenario result, attack improvement or baseline superiority is claimed here. Today's presentation can use this as its predeclared next test while keeping implemented evidence separate.

## Scope and order

1. Complete the current integrated diagnostic-cost measurement and preserve exact output behaviour.
2. Freeze the presentation structure and existing audited results today.
3. Implement one maintained-Simulator street scenario, verify Region → PolicyTree integration and recipient tasks, then add the second and third. Keep motion, policy, coordination and attacker changes in separate gates.
4. Evaluate privacy effectiveness with the agreed protected unit/secret and matched utility, after verifying policy compliance and source accounting.

Use **the maintained UMP Simulator**, not an unannounced replacement movement generator. A small route/portal/dwell addition to its existing agent execution is enough for a first controlled street proof of concept. ORCA, a real-city map importer, modifier-taxonomy migration and a global routing stack are not prerequisites. Required movement additions must be explicit, independently inspectable and named in the source manifest.

Current captures have random initial positions and straight-line destinations, no defensible building entry/dwell labels, no sustained replenishment and no frozen seed. They cannot be relabelled as shopping-street or residential visits. Existing seven production profiles remain the initial type vocabulary; no car class should be introduced silently. A road polygon can be contextual background even while the study population is restricted to VRUs.

## Shared experimental contract

- Use an 80 × 80 m domain at data depth 6, with 1.25 × 1.25 m finest cells. This preserves the audited code path and 4096 possible leaves. A selected region may cover only a few leaves and need not equal a quadtree node.
- Maintain 50-ms numerical simulation steps and 100-ms observed samples initially. Route demand, density and policy changes are controlled separately.
- Retain the seven supported behaviour profiles, their original names and truthful release tree. Type mixture and flow are scenario inputs, not post hoc tuning to improve results.
- Add a deterministic seed at the maintained Simulator's randomness boundary, or record each scenario trace once temporarily and replay it across all methods. Because present motion includes real-elapsed-time-dependent velocity variation, equal seed alone is not proof of byte-identical observations. Freeze and hash the actual observed stream used by every method; deterministic source generation needs a separate clock audit.
- Use continuous boundary arrivals and departures for a sustained-flow experiment, with explicit rates and warm-up. Population size is an outcome of demand and dwell, not just an initial count. Report active counts, arrivals, departures and observed density by region over time.
- Begin with one declared demand condition per scenario to prove integration; then add low/medium/high flow and independent seeds. Replication is by independent generated scenario, not by individual query, category or frame.
- Preserve complete measured coverage, half-open intervals, exact distinct identity unions, truthful semantic cuts, immutable nonoverlapping public support, explicit suppression and source conservation. Resource failure is distinct from policy infeasibility.
- Hold the default `policy_satisfied` trigger fixed. Temporal First preserves time, Spatial First preserves space, Semantic First preserves semantics. Study preference waiting separately rather than mixing it into the first scenario comparison.

Proposed shared root for the first design review: distinct total support ≥ 1; minimum distinct support per positive released category ≥ 5; cell side in [1.25, 20] m; duration in [400, 4000] ms; interval-start age ≤ 4000 ms; semantic maximum loss ≤ 1. These are **experimental settings**, not validated legal/privacy-safe thresholds. Every local requirement can only tighten this root. If an application needs faster than 400 ms later, change the declared minimum in a separate factor.

Four-second policies require compatible implementation budgets. The present
performance case retains only 2 s and must not be reused unchanged. Start with a
declared 6-s history and 64 sensor bins for the proposed 4-s window, then size
observation/identity limits from peak concurrent demand and validate controller
endpoints before execution. Record resource failures separately from policy
infeasibility; never allow silent expiry to masquerade as suppression. These
changed limits need their own timing measurements.

## Normal Region → PolicyTree path

Create named `Region` instances and region taxonomy requirements in the Simulator configuration. Select their IDs through the normal application's `policy_tree`. Use normal initialization, compilation and MetricEvaluator lookup. Do not inject constraints directly into the aggregator or patch candidates using scenario names. Record root, region type and region-instance sources in diagnostics.

Current selected policy regions must be disjoint axis-aligned rectangles inside the sensing square with boundaries on finest-cell edges. Positive-area overlaps and arbitrary polygons are unsupported. A sidewalk, frontage and crossing may overlap conceptually; initially partition them into disjoint rectangles with explicit combined types, rather than pretending the current compiler supports layered polygons. Portals and route edges are movement objects; a zero-area entrance segment is not by itself a positive-area policy region. Give each entrance a declared surrounding policy footprint.

Root/type/instance lower bounds combine by maximum; upper bounds by minimum. A region instance cannot relax the root or its type. A parent cell that intersects several regions, including an empty region, must satisfy all applicable requirements. No area-weighted compromise is allowed. A combined parent can be infeasible while its children remain legal. Touching only an edge does not add a region's bounds.

Integration acceptance: use at least one small 2.5 × 2.5 m patch, one non-quadtree-aligned rectangle whose edges still align to 1.25 m, one empty strict footprint and one coarse candidate crossing two regions. Independently rebuild geometry intersections from the original configuration, rather than trusting serialized policy IDs or success flags.

## Scenario 1: residential frontage and entrances

**Purpose:** measure the cost of stricter requirements near entrances while retaining useful pedestrian/cyclist density elsewhere. This develops the residential mockup from the supplied presentation.

Suggested public layout: parallel north and south footways, separate cycle corridors, two or four building entrances, and a crossing connection. Building footprints are nontraversable context. Entry/exit portals connect only to allowed paths. Movement demand includes through traffic and declared residents/visitors entering or leaving; do not infer residence from proximity.

Suggested disjoint policy footprints on the 80-m grid:

| Region | Example footprint (m) | Additional requirements |
| --- | --- | --- |
| North entrance A | [10,15) × [7.5,10) | Category support ≥ 10; duration/age maxima 4000 ms; side remains ≤ 20 m. |
| North entrance B | [50,55) × [7.5,10) | Same as A; independent arrival schedule. |
| North footway west/centre/east | Disjoint rectangles covering [0,80) × [10,15) | Side ≤ 5 m, semantic loss ≤ 0.5, duration/age ≤ 1000 ms. Split further only where entrance policy footprints truly overlap; keep selected geometry disjoint. |
| Cycle corridor | [0,80) × [20,25) | Side ≤ 10 m, duration/age ≤ 1000 ms, semantic loss ≤ 0.5. |

The exact rectangles and requirements are proposed configuration values. Confirm traversable connectivity, target placement and policy footprint relationships before freezing them. North entrance rectangles touch the footway at y=10; a coarser parent may intersect both and inherit both requirements. A cross-footprint support/size/time conflict is an intended measured possibility, not a configuration bug to conceal.

**Recipient task now feasible:** mean sampled occupancy and Road User/Pedestrian/Cyclist counts on predeclared public footway/cycle footprints, with separate exact and estimated availability/error at fixed deadlines. Entrance-neighbourhood occupancy can also be measured.

**Additional GT needed for visit utility/privacy:** actual portal crossing and entry/exit/dwell events with stable person IDs. Occupancy near an entrance is not an entry count, home identity, visit or residence. A visit counter/decoder and visit-privacy experiment are separate gates.

**Hypotheses:** local adaptation may preserve fine non-entrance output while using larger/longer support near sparse entrances. The strict footway footprint may also prevent a useful parent and increase suppression. Both outcomes and neighbour spillover must be reported.

## Scenario 2: shopfront, through-flow and stopping

**Purpose:** separate sparse/dwelling frontage information from a high-flow path. This develops the supplied shopfront/window mockup without claiming validated retail behaviour.

Suggested public layout: a central through corridor, two shop windows with adjacent stopping bays, and one entrance per frontage. Route choices determine who passes and who stops. Define dwell start/end and dwell-time distribution before generation; preserve separate passers-by, window stoppers and actual entrants. Repeated samples during one person's dwell do not increase distinct identity support.

| Region | Example footprint (m) | Additional requirements |
| --- | --- | --- |
| West window bay | [10,20) × [10,15) | Side ≤ 2.5 m; semantic loss ≤ 0.5; duration/age maxima 4000 ms. |
| East window bay | [50,60) × [10,15) | Same bounds with independently specified demand. |
| Through corridor | [0,80) × [20,30) | Side ≤ 5 m; duration/age ≤ 1000 ms; semantic loss ≤ 0.5. |
| Small display guard | [30,32.5) × [10,12.5) | Side ≤ 1.25 m, category support ≥ 10, duration/age ≤ 1000 ms. Include an empty period deliberately and audit the resulting parent restrictions. |

No local footprint relaxes the proposed root. A long dwell of one person can remain infeasible at any temporal duration. High repeated occupancy must not be interpreted as high anonymity or new identities.

**Recipient task available initially:** occupancy in the stopping bays and category counts/occupancy along the through corridor. Mix fine slow queries and coarser urgent queries with predeclared weighting; report each task family separately as well.

**Additional GT/metric required:** number of distinct stoppers, dwell duration, window exposure and entry rate are not automatically derivable from aggregate occupancy. Record explicit start/end labels and implement their estimators before claiming those utilities. The initial occupancy experiment cannot show how many different people looked at a shop window.

**Hypotheses:** heterogeneous local timing may preserve frontage detail without slowing the through corridor; fixed region-specific windows may already capture most of this advantage. Semantic generalization can retain truthful Cyclist/Pedestrian counts but remove age distinctions. Show this cost rather than treating retention as full information preservation.

## Scenario 3: crossing with burst arrivals and a waiting area

**Purpose:** test whether bounded privacy requirements and strict freshness can coexist during transient low occupancy, then observe recovery during dense bursts. This is the required failure/latency case, rather than a third demonstration designed only to favour adaptation.

Suggested public layout: orthogonal pedestrian/cycle routes, an explicit crossing and separate waiting pockets. Use piecewise arrival demand or a fixed periodic signal schedule; the public schedule and phase relationships are predeclared. Do not call this a safety controller or collision-risk result: present sensing supports occupancy, not validated near-miss reconstruction.

| Region | Example footprint (m) | Additional requirements |
| --- | --- | --- |
| Crossing core | [35,45) × [35,45) | Side ≤ 5 m; duration/age ≤ 400 ms; semantic loss ≤ 0.5. With a 400-ms hard minimum, this is a fixed permitted interval duration. |
| West waiting pocket | [25,35) × [35,45) | Side ≤ 5 m; duration/age ≤ 4000 ms; semantic loss ≤ 0.5. |
| East approach | [45,80) × [35,45) | Side ≤ 10 m; duration/age ≤ 1000 ms; semantic loss ≤ 0.5. |
| Small strict corner | [35,37.5) × [32.5,35) | Category support ≥ 10; side ≤ 2.5 m; duration/age ≤ 1000 ms. |

The selected rectangles touch but do not overlap. Their edges align to the finest 1.25-m cells even where the rectangle as a whole is not a single quadtree node. Other approach geometry can be added as disjoint patches after the first integration test.

**Recipient task:** count/occupancy in the crossing core at its declared short deadline and waiting-pocket occupancy on a longer deadline. Complete exact answers, explicit estimates, missing support and suppression are all measured. Use no private GT to fill recipient gaps.

**Hypotheses:** low-flow crossing intervals may be jointly infeasible under support five and short freshness; suppressing them is a safety-of-release outcome with a real utility cost. A dense burst may enable fine legal output. Delaying a crossing result beyond the deadline is not a successful answer merely because a later aggregate contains enough identities.

## Fair baselines and factor isolation

Run all methods on byte-identical measured observations, the same domain, taxonomy, scalar bounds, privacy/recipient boundary and task bank. Freeze the input and configuration manifest before execution. A fixed-grid comparator must also use truthful supported semantic generalization and suppression; otherwise the experiment mixes semantic capability with spatial/temporal adaptivity.

1. **Uniform fixed grid and fixed window:** legal quadtree-aligned cell sides 1.25, 2.5, 5, 10 and 20 m and windows 400, 1000 and 4000 ms, retaining every declared combination in the report. Local violations cause suppression; do not quietly weaken regional bounds to make the baseline publish. Exclude a combination only by a predeclared structural rule, never because its result is poor.
The three fixed window lengths are a predeclared subset of the permitted 100-ms-aligned durations. Call their frontier the best tested fixed frontier, not a globally best fixed schedule. Densify the calibration sweep near observed trade-offs before a strong superiority claim.

2. **Static region-specific grid/window:** choose geometry and intervals once from public region requirements and a separate calibration cohort. Keep footprint intersection and source ownership consistent. This asks whether the policy map alone explains a benefit, without reacting to each sample. It is a planned comparator and may require a bounded adapter; do not claim it already exists.
3. **Common-window adaptive:** isolates the value/cost of local timing from adaptive space/semantics.
4. **Cell-local adaptive:** primary controller, with declared Semantic → Temporal and Semantic → Spatial preferences. Report identical output preferences as identical, not as two independent successes.
5. **Raw/agent-based or fine unfiltered counts:** optional informative upper-utility reference. They are not a policy-compliant privacy baseline if they violate the release contract. An agent-based comparator becomes fair only after declaring and implementing a comparable protection mechanism.

ALOQ is not required to interpret this first experiment. Its output/protection contract must be aligned before it can be a fair external privacy comparator; an unrun implementation is not a result bar.

For each independent generated scenario, show the fixed Pareto frontier in the relevant utility/age/detail coordinates. If choosing one fixed setting, choose it on training/calibration scenes and evaluate untouched test scenes. Do not compare an adaptive test result only to the weakest fixed setting or select the best baseline on the same test after looking at outcomes without disclosure.

## Privacy focus and privacy improvement are different claims

**Stage P0, available mechanism measures:** audit the minimum/category-support constraints, report distinct support distributions, suppression, semantic abstraction and geometry/time detail on the same source. These establish policy enforcement and its cost. They are not calibrated privacy probabilities. Repeated users, large type entropy and long intervals are not automatically privacy gains.

**Stage P1, proposed common empirical risk contract:** use one source-membership/passage-presence experiment across all three scenarios before creating three unrelated attacker games. A protected unit is one road user's observed passage during a declared horizon. The secret is whether that unit's source contribution is included. Keep the candidate and all background motion fixed between IN and OUT; change source inclusion only. Define candidate sightings, map knowledge, timestamp/position uncertainty, horizon and causal recipient transcript in advance. Train/calibrate/test on independent scene groups, keeping paired worlds and all methods together. Existing membership code must be checked against the actual current semantic release schema and geometry/timing channels before reuse.

This is a proposed protection contract for discussion, not a decision to resume the deferred attack implementation before the scenario and policy gates. Freeze the protected secret and attacker knowledge before reusing historical attack code.

Report auxiliary-knowledge-only and no-release controls, release-plus-knowledge AUC, calibrated TPR at predeclared FPR, attack advantage and confidence intervals over independent groups. Include all public counts, truthful categories, cell geometry, intervals and availability timing. A smaller AUC achieved by releasing almost nothing needs its coverage cost beside it. Report whether methods differ in target retention; do not score only the easiest retained targets. An inconclusive interval is not evidence of equal risk or successful protection.

**Stage P2, context-specific visit inference:** once real entry/dwell labels exist, protect a hidden entrance/shop visit with the candidate present in both worlds. The attacker knows the public map and declared prefix/suffix sightings; no hidden interval or visit label may leak into features. This is a different secret from source membership and needs its own data contract, not a renamed membership label. A visit to a building is not an inferred diagnosis or identity.

For a fair claimed privacy/utility gain, use one of two comparisons:

- At matched operational policy **and comparable measured attack risk**, compare deadline-aware task availability, detail, error and suppression.
- At matched utility/coverage/freshness, compare measured attack success on the same protected units and independent test scenes.

Identical support requirements alone do not prove identical attack risk. A useful adaptive result can be higher utility at the same measured risk; lower risk is not mandatory in every coordinate. Conversely, an adaptive scheme may leak through its geometry or release timing, which must count against it.

## Result sheet and acceptance gates

Each scenario's compact result sheet contains: source provenance and independent sample count; population/flow/type mix by region; effective-policy coverage; complete source accounting; violations and infeasibility reasons; observation retention and per-type/per-region suppression; output-side, duration, logical age and semantic-loss distributions; exact query availability; separate estimated-query error and coverage; wall-clock service/queue/ACK cost; and the defined privacy result when implemented.

Do not combine unrelated metrics into a single uncalibrated privacy/utility score. Keep exact and estimated outputs separate, with a common fixed query denominator. In particular, a 400-ms record crossing a 1000-ms query boundary cannot supply an exact subinterval count; a larger cell cannot exactly answer a smaller spatial query. Adding more waiting does not reveal the missing partition. Predeclare application queries, then report this mismatch rather than redesigning queries after seeing output.

Acceptance gates, in order:

1. **Environment and source:** visible route/portal/dwell behaviour matches its labels; per-region density/flow is measured; no accidental wall-clock or seed claim. One frozen source is usable by every method.
2. **Policy integration:** normal Region adaptation and compiled PolicyTree are used; independent geometry audit covers strict local patches, touching edges, empty footprints and cross-region parents.
3. **Release correctness:** no hard-constraint violation, overlapping public support, hidden input loss, false zero or retired-source reuse; resource failures are explicit.
4. **Utility comparison:** full declared comparator matrix and task banks complete; results include failure regimes and no-advantage cases. A baseline win is retained.
5. **Privacy comparison:** protected unit, secret, attacker knowledge, schema, causal timing, splitting and held-out attack test are frozen. Only then claim empirical privacy improvement, with uncertainty and utility cost.
6. **Presentation claim:** a positive result must name the exact scenario, comparator, metric and conditions. If no superiority is established, present the compliance result and quantified limitations honestly; do not tune the test to manufacture a win.
