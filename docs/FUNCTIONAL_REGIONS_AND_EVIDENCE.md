# Functional regions, scenario reconstruction and evidence

Review date: 2026-10-19. Scope: the residential street and shop-front scenarios represented
on printed presentation slides 26/27 (PDF pages 27/28). The goal is to reproduce their
functional scenario and measurable aggregation effects; the drawing geometry is not a
specification. No simulator source was changed by this review.

Canonical terms, symbols, units and code mappings are defined in
[TERMINOLOGY_AND_NOTATION.md](TERMINOLOGY_AND_NOTATION.md). Aggregation is bound to
a data cell and time interval; functional regions supply its requirements.

## Current foundation and missing pieces

The AGBS pipeline already supports finest-cell observations, exact private identity unions,
regional metric requirements, spatial selection, bounded temporal extension, immutable
publication and fixed-input offline utility comparison. The current pilots are documented
in [EVALUATION_RESULTS_2026-10-14.md](EVALUATION_RESULTS_2026-10-14.md). There have been no
additional implementation commits since the October 14 research-plan checkpoint before
this review. The existing independent oracle is still a plan, not an implemented reference.

Existing `Region` objects contain IDs, type, rectangular area, type-level metric requirements
and instance requirements. `PolicyConfiguration.cpp` adapts them into the immutable numeric
PolicyTree. Type names can represent carriageway, cycleway, footway or entrance without a
new quadtree implementation. The legacy granularity/k/l YAML values do not supply active
metric checks; explicit registered `metric_requirements` do.

The existing corridor references are preparatory. `PathGeneration.cpp` is a comment stub,
the renderer has a visibility flag, and collision avoidance contains corridor TODOs. Agents
do not currently obey functional-region movement rules. A meaningful street scenario thus
needs deliberate path generation or recorded synthetic paths that remain within the intended
surfaces. Real map extraction, a route network and advanced avoidance remain later realism work.

## Region semantics and geometry

Use a common scenario geometry with stable IDs. It has two consumers:

1. Motion generation: permitted surfaces, routes, starts, destinations and transitions.
2. Application policy compilation: requirements that apply to an aggregate footprint.

A movement corridor describes traversable space and connectivity. A functional region
supplies spatial meaning and local requirements. The same geometry can inform both;
policy changes do not move roads, and a data-tree merge does not change a region boundary.
The PolicyTree is a compiled constraint index; the data quadtree indexes observations.

Initial functional classes are carriageway, cycleway, footway and entrance area. Residential
or commercial context is a second semantic dimension. An entrance can belong to a footway
and lie in a residential frontage. The current selected-region adapter rejects overlap:
represent the initial experiment as disjoint rectangles, splitting the footway around the
entrance. For future overlapping layers, compile their intersections into disjoint pieces
or extend the geometry compiler with an explicit intersection rule. Do not add overlapping
YAML rectangles and assume their policies already compose.

Supported regions are axis-aligned, inside the sensor square, and aligned to finest cells;
they need not themselves be one square quadtree node. A long narrow road strip can span
many nodes. Oblique/curved roads and arbitrary polygons need a later geometry adapter and
an explicit rasterization/intersection-error contract. The first study can use exact straight
strips and known dimensions. Choose a finest grid compatible with those dimensions instead
of silently shifting a curb to fit it.

A publication cell may currently intersect several functional regions. It inherits all
requirements for its full footprint, including empty portions. This does not prohibit
cross-region mixing. A rule forbidding a cell from crossing road/footway boundaries would
be a new geometric constraint or a different aggregation-domain design; numeric minimum
support alone does not implement it. Compare such a rule only once implemented explicitly.

## Environment and demand brainstorm — proposed architecture, 2026-10-19

The richer environment, global/local motion planning and avoidance remain lower priority.
The immediate research path is EP01, a small controlled scenario and equal-input utility/
policy comparisons. A complete map import or replacement movement engine is not a
prerequisite for that path.

Keep a canonical environment source with coordinates, stable IDs and geometry provenance.
From it derive spatial indexes, functional-region/policy lookups and movement connectivity.
Do not make the maximum-depth aggregation grid the only surviving representation of the
map. Changing D must not move entrances, delete narrow passages or redefine route topology.

| Layer | Question it answers | First representation / future extension |
|---|---|---|
| Source geometry | Where are buildings, surfaces, boundaries and doors? | Manually authored exact rectangles/segments/points; later imported polygons with provenance. |
| Functional semantics | Is this a carriageway, cycleway, footway or entrance approach? | Stable region IDs/types sharing source geometry; later overlapping context layers. |
| Connectivity | Which spaces and portals connect for each road-user mode? | Explicit allowed transitions; later a route graph and richer access rules. |
| Spatial discretization | Which geometry/requirements intersect a candidate cell? | Derived lookup compatible with the existing finest grid; later an explicit polygon rasterization/intersection contract. |
| Demand and activity | Who arrives, chooses a destination, waits and leaves? | Prescribed source/target schedules; later shop-visit and dwell processes. |
| Motion | How does a chosen route become realized movement? | Prescribed valid waypoint paths; later global routing, local following and collision avoidance. |

A spatial quadtree encodes hierarchical proximity/containment. It does not by itself encode
which side of a wall connects to which entrance or which road-user modes may cross a curb.
A movement graph and quadtree may share source IDs without being interchangeable structures.
Likewise, map discretization is an environment lookup stage; it is not the adaptive choice
of the cell/time blocks that will be published.

For the initial study, use geometry already aligned to the current policy compiler. For
more general geometry, retain every relevant intersection under a documented approximation
rule. A center-point-only label can miss a narrow region cutting a cell; a majority label
can silently drop a stricter policy area. Validate such approximations and their spatial
error before using them in a constraint guarantee. Build static lookups once where possible;
no repeated full-map geometry scan is needed for every frame.

### Entrances, destinations and shop flux

An entrance/exit portal is a movement boundary or connection, possibly represented by a
point/segment plus direction/access information. It is not automatically a positive-area
PolicyRegion. If constraints apply near a door, define a separate entrance-approach region
with nonzero area and link it to the same source ID.

A shop visit is an activity: choose the shop, reach its portal, optionally remain inside,
and later leave. The environment alone does not determine arrival rates or destination
probabilities. Begin with explicit schedules; choose stochastic laws only when defining a
specific experiment. Configured demand intensity and realized crossing flow are different
quantities; their planned notation is in the canonical reference.

For later hidden indoor dwell/re-entry, preserve the road-user identity across the visit.
Recreating the same person under a new identity would change distinct-support metrics.
Outdoor sensor visibility also needs an explicit contract; putting an agent behind a
building polygon does not yet make the current bounding-box sensor stop observing it.
If visits are conserved, departures must be consistent with prior entries, dwell and any
initial indoor population, rather than being unrelated spawn events.

### Dependency and priority order

1. **EP01 now:** implement the independent small-case feasibility/compliance reference and
   private loss diagnostics. No environment implementation is needed to answer those cases.
2. **Small SC01 fixture:** one street cross-section with stable functional-region IDs and
   prescribed mode-compatible paths. Named starts/exits suffice; detailed doors, indoor
   behavior and stochastic shop demand are optional later refinements.
3. **Regional utility and equal-input evaluation:** predeclare fixed query footprints for
   the regions; add the necessary query/mask support beyond the current regular 10-m grid.
   Freeze the stream and compare legal fixed/spatial/Temporal First/Spatial First variants.
4. **Targeted aggregation extension:** if the common-window cap or sibling suppression
   prevents the intended result, implement the specifically demonstrated cell-local
   coordination/A07 extension, then repeat the same frozen cases.
5. **Later realism:** canonical map import and portal/connectivity validation, destination/
   activity demand, global routes, local following/trajectory generation and avoidance.
   Select algorithms from the required workload and measured deficiencies at that stage.

The next concrete software deliverable is EP01's tiny independent reference with known
expected results. The next environment deliverable is a small scenario contract and fixture,
not a general city simulator. This order preserves the dissertation's focus on aggregation
conditions, utility and policy fulfilment.

## Application requirements by region

| Region | Initial application quantity | Candidate local requirements | Additional prerequisites |
|---|---|---|---|
| Carriageway | Sampled occupancy in a fixed road segment | Maximum release age/window and maximum cell side | Flow, speed and queue accuracy require their own queries and reconstruction, not just renaming occupancy. |
| Cycleway | Sampled occupancy on a separate strip | Spatial detail sufficient to distinguish it from adjacent road/footway | Separate region-level scoring exposes cross-boundary mixing. |
| Footway | Occupancy/density in a fixed pedestrian area | Support minimum, bounded coarsening and age | Legitimate empty space remains different from missing/suppressed output. |
| Residential entrance | Coarse occupancy near an entrance | Stronger support or coarser release requirements, with bounded wait | The sensitive home/visit association and actual privacy protection require separate definitions and evaluation. |
| Shop frontage | Occupancy near a display window | Desired spatial detail and maximum age | Individual dwell time and class-based advertising are separate application tasks not implemented by the present occupancy evaluator. |

These are experimental design choices. Pick numerical bounds from a stated application
requirement or label them as mechanism parameters; road/entrance labels alone do not justify
a particular privacy threshold. The first study should keep the same occupancy estimand
across regions and add more specialized tasks only with their own reference and estimator.

For a region smaller than or crossing the fixed evaluation grid, define the query footprint
explicitly (for example, a fixed rectangle entirely within the strip). The current occupancy
helper uses an equal regular reference grid; arbitrary region masks/clipped query shapes
and their public-only reconstruction are an additional evaluator extension. Scores that
use the public method's changing output cells as their reference would hide resolution loss.

## Mathematical formulation and limits

Let r denote a functional region, C a candidate quadtree cell, I=[s,e) its aggregation
interval, and t_eval the time at which it is assessed. Let R(C) contain the regions with
positive-area intersection with C and the application default. Define the internal support
set from the observed samples:

    U(C,I) = {u : there is a measured observation of u in C at a time in I}
    n(C,I) = |U(C,I)|

This is distinct-road-user support, not automatically a formal anonymity equivalence class.
For the implemented lower/upper metric bounds:

    k_support(C) = max(k_support(r) for r in R(C))
    h_max(C)     = min(h_max(r) for r in R(C))
    T_max(C)     = min(T_max(r) for r in R(C))
    L_max(C)     = min(L_max(r) for r in R(C))

For this policy subset, an admissible candidate must have complete measured coverage and
satisfy all of:

    n(C,I) >= k_support(C)
    h(C) <= h_max(C)
    e - s <= T_max(C)
    t_eval - s <= L_max(C)

Other configured lower/upper bounds remain conjuncts too. Contradictory footprint requirements
make that candidate infeasible, while smaller children may remain feasible. The existing
compiler resolves numeric bounds this way. It provides thresholds; the evaluator computes
measurements and the controller decides which candidate to try.

The present temporal controller imposes the strictest duration/age upper bound across the
entire sensor coordination domain and uses a shared interval. A 200-ms road cap therefore
also restricts the entrance area, even when its own bound is 1000 ms. Different cells cannot yet complete short road-bound and longer entrance-bound windows
independently. These are cell windows under regional requirements, not windows owned by
regions. Execution priority is also root-level, not independently selected for each region. Both limitations belong in the
experimental model and current-capability description.

Support cannot be computed by adding distinct counts. For four sibling cells C_i sharing
one interval:

    U(parent,I) = union_i U(C_i,I)

Likewise, time extension takes the union over samples/intervals. The same road user can
visit several cells or time bins. Exact unions underpin the current implementation.

## What can be proved, and what needs measurement

Candidate proof targets, to be written and checked against the implementation:

- **Release soundness:** every emitted cell passes its effective requirements and coverage
  gate, assuming correct sufficient statistics and faithful policy compilation.
- **Temporal/spatial consistency:** intervals and chosen cuts do not reuse already published
  observation support; identity unions and observation totals are conserved as specified.
- **Bounded search:** the legal tree depth, extension steps and evaluation budgets bound each
  decision attempt. This does not guarantee that storage succeeds or every input gets released.
- **Scoped feasibility/completeness:** an independent exhaustive tiny-case reference can
  establish whether the search misses permitted alternatives within that explicitly defined
  coordination model. General search optimality is not established by passing thresholds.

An empirical advantage is a separate question: compare fixed and adaptive aggregation
under identical regional requirements, data, query and legal bounds. Report error, answered
coverage, age and suppression/retention. Expect trade-offs rather than a universal theorem
that adaptation simultaneously improves every metric on every dataset.

A local necessary-condition example: if even the largest permitted support and longest
permitted window contain fewer than the applicable minimum number of distinct road users,
there is no passing candidate for that support under that minimum. Regional policy changes
and alternative partial releases must still be accounted for before claiming that the whole
scene has no feasible output.

## Scenario study and statistical evidence

Start with one precisely specified street cross-section: carriageway, two cycleways, two
footways and entrance patches. Add a shop-front variant using the same region machinery.
Manually authored straight paths with explicit crossings/transitions are sufficient for
initial mechanism tests. Record agent
classes, travel directions, speeds, density and identity turnover per surface; don't use
unrestricted random placement to represent lane-constrained motion.

Use the following staged comparison:

1. Validate spatial labels, movement containment and border transitions independently.
2. Use EP01/EP02 hand cases for dense/sparse regions, arrivals, one impossible entrance,
   a strict deadline in another region, and cells that span two functional classes.
3. Hold the regional policy constant and compare legal fixed baselines, spatial-only,
   Temporal First and Spatial First on each identical frozen stream.
4. Vary density/support around the threshold, identity turnover, geometric alignment,
   spatial limits and time bounds. Change one factor first, then selected interactions.
5. Repeat on independent scenario realizations and report paired effects per region and
   overall, with stated weighting and interval-estimation assumptions.

If comparing uniform and functional policies, label that as a policy-design ablation.
A weaker uniform policy solves a different constraint problem; its output cannot be called
more effective without assessing it against a common target. A globally strict conservative
baseline is useful only if its combined requirements are actually consistent.

The outcome table should separate (a) violations among released cells, (b) useful output
availability, (c) conditional and common-support utility error, (d) age/resolution, and (e)
loss relative to a bounded feasibility reference. With no releases, compliance is undefined,
not a favorable 100%. Infeasibility requires an argument/reference, not just an empty result.

Current one-run pilots are descriptive. Independent realizations supply the replication
unit; frames and neighboring cells within a run are dependent. Use run-level paired effects,
report scenario-specific variation and plan replication from the precision needed. Runtime
claims need separately measured persistence/transport/rendering, beyond core replay timings.

## QIs and sensitive attributes in these scenarios

Formal k-anonymity requires a protected record/entity and the published quasi-identifier
mapping. For a declared person-level representation, E_q groups records with the same
visible QI tuple q; k is the minimum group size, with distinct-entity counting where that
is the protected unit. For l-diversity, define a meaningful secret S and its values within
those same groups. See the primary [k-anonymity](https://dataprivacylab.org/dataprivacy/projects/kanonymity/kanonymity.pdf)
and [l-diversity](https://www.cs.cornell.edu/johannes/papers/2006/2006-icde-publishing.pdf) papers.

Possible visible QI components depend on the actual release: generalized space, time,
and any published direction, speed or class. Exact home/visit destination or trip purpose
could be an experimental secret; define why it is hidden and what auxiliary information
already reveals. Road-user type may be a visible segment, an auxiliary fact or an unknown
individual attribute, depending on the task. Those roles cannot be assigned independently
of the output/attacker contract. Aggregate type utility and secrecy of an individual type
association also need to be distinguished.

The current public output is aggregate counts, not a table of generalized individual records.
Its n(C,I) can be evaluated now as support, but does not by itself demonstrate classical k.
Private AGBS aggregation currently uses simulator IDs. A real counts-only sensor cannot
supply exact unique-person support without an additional justified tracking/input model.
Current type histograms count repeated observations rather than distinct people per type.
Actual l evaluation needs a deduplicated group/attribute contract and the relevant input.
The maintained temporal example contains only adult pedestrians, so its class diversity
would be one if class were chosen as the secret. This is not a representative attribute study.

## Integration into presentation, paper and dissertation

Use the same sequence of claims and evidence at increasing depth:

1. State the conditional research question and provisional answer: the implemented strategy
   produces compliant output in demonstrated cases, while coverage/error/age trade-offs
   depend on scene, policy and strategy. Whether it finds every available legal alternative
   is an open completeness question. Distinguish measured pilot outcomes from proof goals.
2. Show the functional street/shop geometry and the regional application requirements.
3. Present the admissibility predicate and exact support unions; show one hand-checkable
   space/time decision and one impossible/partially recoverable case.
4. Give equal-input comparisons and per-region outcomes, retaining fixed baselines and
   missing-support denominators. Include cases where adaptation loses or two strategies coincide.
5. State limits: common windows, missing oracle/independent repetitions, aggregate-support
   versus k/l guarantees, and simplified motion. Keep implementation details in backup material.

The presentation needs a readable region diagram, a short measured transition and one
coverage-error-age figure. The paper adds the explicit model, algorithm, proof scope,
controls and statistical method. The dissertation adds detailed assumptions, proofs,
sensitivity analyses, privacy/attribute contracts and alternative coordination models.
The simulator is the experimental instrument and proof of concept for those claims.

## Verified mechanism probe during this review

The existing replay binary was exercised on a small analytical stream, not a reconstruction
of either full scene. Four children of a 40-m parent initially contain distinct sets
{A}, {B}, {C,D}, {E,F}, measured at 100, 200 and 300 ms. At 400 ms, G joins the first cell
and H the second. Policy: minimum support 2, maximum side 40 m, maximum window/age 1000 ms.

The binary exactly matched the independent hand calculation:

- Temporal First emits the 40-m parent over [0,400): 6 distinct road users, 18 contributions,
  three measured samples, mean sampled occupancy 6.
- Spatial First emits four 20-m cells over [0,500): support 2 in each, 26 total contributions,
  four measured samples, cell means 1.25, 1.25, 2 and 2.
- Temporal First refines its next output interval to the four 20-m cells after the arrivals.

Input, policy, result JSON, command/binary hashes and verification assertions are in
`results/review/2026-10-19/mockup-mechanism/`. A standalone PNG/SVG figure displays private
input separately from released aggregate panels. This verifies the basic mechanism on
that case; it is not the full independent oracle, a corridor study, or empirical privacy evidence.

## Next bounded implementation

Specify the functional geometry, shared region IDs, movement paths and per-region occupancy
queries first. Reuse Region/PolicyTree for aligned disjoint rectangles. Add a controlled
street fixture with region/path validation and policy-boundary cases, alongside EP01's
independent reference. Then execute the staged utility/policy study. Independent cell/merge-group
time windows, overlapping semantic layers, polygons and actual k/l studies remain explicit
follow-up work rather than implicit claims of the first corridor experiment.
