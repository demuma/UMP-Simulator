# Scenario inventory, production taxonomy and ground-truth loss

Date: 2026-10-19. This is an inventory of the completed 16-second robustness
benchmark, not a new experiment or a change to its results. Actual populations were
counted from all 208 frozen PRESENT inputs and matched to their recorded hashes.
Private details: `results/evaluation/2026-10-19/privacy-local-diagnosis-20261021/scenario-inventory.json`.

## Three is a release threshold, not the simulated population

The controlled benchmark requires at least three distinct contributing road users
in an eligible cell/time candidate. The number is neither the scenario's total
population nor necessarily three users present simultaneously: temporal aggregation
unions identities across its interval. A particular missed-merge example had exactly
three users in one candidate; other road users existed elsewhere.

Each case covers 80 × 80 m, samples at 100 ms, has 1.25-m finest cells (depth 6) and
lasts 16 s. The new dataset has 48 training, 32 calibration, 64 base-test and 64 shifted-
test groups. Every group contains paired IN/OUT sources with the same background.
The physical candidate exists in both worlds; OUT excludes its recorded contribution.

## Actual robustness populations

Ranges below describe **peak simultaneous observed road users in PRESENT inputs**.
Base includes 36 groups per scenario across training, calibration and test; the shifted
cohort has 16 held-out groups per scenario. Include the candidate in these counts.

| Scenario | Base peak population | Shift peak population | Controlled mechanism |
|---|---:|---:|---|
| Sparse | 2–7 | 3–10 | Low support, often below the release threshold in fine cells |
| Dense | 28–55 | 43–82 | Many pedestrians, smaller eligible aggregation footprints |
| Handover | 4–9 | 6–13 | Background identities replaced every 0.5/0.7/0.9/1.1 s; candidate remains |
| Heterogeneous | 9–31 | 19–45 | Simplified pedestrians, bicycles and cars in separate movement bands |

Handover has **33–228 distinct IDs** per base run and **56–351** per shifted run over
the full horizon. These totals accumulate different generations; they are not concurrent
population counts. Base held-out-only dense cases have 29–49 users and heterogeneous
cases 10–31; this differs from the wider all-base ranges above.

Only the heterogeneous scenario draws modes with nominal probabilities 60% pedestrian,
20% bicycle and 20% car. The other three scenarios contain pedestrians only. Across the
52 heterogeneous cases the realized identity mix is 742/246/243, approximately
60.28%/19.98%/19.74%. Pooling all scenarios would instead be strongly pedestrian-heavy,
especially when counting handover identities; it must not be described as a 60/20/20
study overall.

Movement is a controlled analytical fixture. Pedestrians use y=10–18 m and 0.9–1.9 m/s;
bicycles y=29–31 m and 3.5–6 m/s; cars y=48–52 m and 6–10 m/s. Some pedestrians turn
and dwell. Paths reverse at their ends to span the horizon. Mode, lane and speed are
therefore correlated; they are not independently isolated experimental effects. There
are no realistic turn dynamics, obstacles, visit semantics or interaction/collision
claims. The source is generated directly for replay rather than by the full simulator.

Earlier work also includes a 30-case coordination matrix, focused hand-worked/regression
cases, an eight-second 200-pedestrian actual-simulator capture and longer headless runs.
Those validate different properties and must not be mixed into the new membership
sample count. See the existing study, capture and endurance reports for their scopes.

## Production taxonomy: a separate current configuration

The active `simulator/config.yaml` specifies **100 agents** and seven named types:

| Configured type | Weight | Initial count in the default 100-agent mode |
|---|---:|---:|
| Child Pedestrian | 10% | 10 |
| Senior Pedestrian | 10% | 10 |
| Adult Pedestrian | 35% | 35 |
| Senior Cyclist | 10% | 10 |
| Adult Cyclist | 10% | 10 |
| Adult E-Scooter Driver | 20% | 20 |
| Adult Cargo Cyclist | 5% | 5 |

The parser treats these as a flat name-to-attribute map. Age and movement mode remain
part of the type string; it does not currently compile a general taxonomy inheritance
tree. Default initialization uses integer counts `int(num_agents * probability)`;
other population values need an actual-count check because rounding can change the
total. The separate `random` initialization branch uses Adult Cyclist directly.

The privacy fixture **does not import this taxonomy**. Its three labels and movement
laws are hardcoded, and its validator permits only those three labels. The C++ replay
parser itself accepts arbitrary nonempty type strings. Thus using the seven production
types does not inherently require rewriting the aggregation core or first completing
the larger taxonomy redesign. It requires an explicit generator/capture adapter and
versioned configuration provenance. The active production configuration has no car
class; a fixture car is one simulated entity, with no occupant/person mapping.

Live AGBS retains `agent.type` in private observations and per-type statistics exist
internally. Approved recipient releases deliberately clear type breakdowns because
separate type-level disclosure rules are not implemented. Current public utility is
**total occupancy**, not classification accuracy or hierarchical type generalization.
Publishing type counts would require a separate policy/visibility/attack contract.

Code references: `privacy_dataset.py:85`, `privacy_dataset.py:181`,
`Simulation.cpp:115`, `Simulation.cpp:273`, `AdaptiveGridBasedSensor.cpp:151`,
`PublicationCoordinator.cpp:126`, and `PublicationStore.cpp:127`.

## What the measured data-loss percentages mean

Existing retention counts one sampled source contribution per road user per timestamp.
A contribution is retained when its point/time lies inside a released aggregate's
support. This does not publish the original identity, point or trajectory. Private
reference files remain unchanged.

For the paired IN/OUT held-out test worlds, suppression loss is:

| Mechanism | Base source loss | Shifted source loss |
|---|---:|---:|
| Fixed 20 m / 1 s | 9.74% | 4.75% |
| Common Temporal First | 3.39% | 1.58% |
| Local Temporal First | 9.23% | 5.24% |
| Common Spatial First | 3.33% | 1.53% |
| Local Spatial First | 8.68% | 5.88% |

Base denominator: 341830 source contributions; shifted denominator: 530976. These
are the primary study's paired-world figures, not a count of lost people. The candidate's
intentional OUT omission is not attributed to the aggregator because each world's
own actual source is its denominator.

For PRESENT worlds only, the denominators are 176003/270576. Base losses are
9.57% fixed, 3.35% common TF, 9.62% local TF, 3.28% common SF and 8.99% local SF.
Shifted losses are 4.77%, 1.57%, 5.24%, 1.51% and 6.19%, respectively. These quantify
the same retention definition without pooling the source-absence attack worlds.

There is no single measured percentage of **all physical ground truth information**
retained. Several distinct effects must be recorded:

1. Coverage/cadence selection: only GT opportunities inside a sensor's footprint and
   at its measurement times are eligible. A 20-Hz GT stream and 10-Hz sensor stream
   do not have equal record denominators even with perfect sensing.
2. Sensing loss/error: eligible GT versus observed source, with explicit correspondence
   and false-positive/classification-error treatment when those are modeled.
3. Suppression: observed source contributions represented in public space/time support.
4. Resolution: exact positions, times, identity links and type detail lost by coarsening
   or omission. Source-contribution retention cannot measure this information loss.
5. Application utility: error, availability and deadlines of a declared query. A retained
   count need not answer a whole fixed query; absent sparse output remains unknown.

For an ideal one-to-one source/GT mapping, let E denote eligible GT opportunities,
O the captured source and R the source contributions represented by recipient output:

    sensing_loss = 1 - |O| / |E|
    suppression_loss = 1 - |R| / |O|
    eligible_GT_retention = |R| / |E|.

These are counts of measurement opportunities/contributions, not people or entropy.
The physical-GT denominator has not been independently measured for the new direct
fixtures. Future false positives require an explicit matching rule, not silent O⊆E.
Per-person representation (at least one released contribution), per-person temporal
completeness and class/region-specific retention remain additional measures.

The existing capture helper verifies GT-derived counts/types against actual raw AGBS
in one common area, then constructs its identity-bearing replay from trusted/private GT.
That is ideal sensing with identity correspondence, not proof that a real count-only
sensor provides persistent distinct-user IDs. The helper is fixed to an eight-second
200-pedestrian preset. The main simulator config currently has different ABS/GBS/AGBS
areas; comparing its unaligned collection totals would confound coverage with loss.

## Next scenario design

1. Close the confirmed future-handoff reservation limitation and preserve the existing
   difficult cases as regression/negative references.
2. Predeclare local-support regimes below/near/above the threshold within legal cell/time
   bounds, uniform versus heterogeneous regional deadlines, and low/high boundary crossing.
   A 3×2×2 mechanism matrix can isolate causes without requiring a real city importer.
3. Add production-type provenance and homogeneous/mixed-type ablations. Define each
   class's route, speed, density and policy role instead of changing all together.
4. Run longer sustained flows with warm-up and interior reporting, and freeze the attack's
   protected horizon/grouping separately. Many fragments from one run are not independent
   training/test realizations.
5. Separate density studies (vary N in one fixed domain) from scalability studies (scale
   area and N while holding physical resolution/density). For example, candidate scale
   points can be 100/300/1000 road users, after validating actual counts and motion capacity.
   At side L, finest width is L/2^D: expanding area at fixed D changes the experiment.
6. Freeze exact inputs/policies for fixed, common and local comparisons; report compliance,
   per-type/per-region retention, timing, task error/coverage, membership and resource cost.
   Include both declared application-ROI queries and full-domain results. Large empty areas
   must not silently change query denominators.

Higher N alone does not establish effectiveness: if every finest cell already passes,
there is little adaptation to evaluate. The useful question is when adaptive selection
improves timely useful output under fixed requirements, what costs it incurs, and when
there is no feasible release. Full production-taxonomy and large-scale effectiveness
are not yet established by the controlled fixtures.
