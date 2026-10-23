# Regional policy tree

Status: 2026-10-23. A04 numeric policies and strict composition of overlapping/nested
aligned rectangular Regions are implemented. The tree also accepts application-level
execution choices for the integrated A03/A05 path.
Metric computation remains in the evaluator; execution choices are interpreted by the
controller/publication adapter, not numerically intersected as metric requirements.

Canonical terms, symbols, units and code mappings are defined in
[TERMINOLOGY_AND_NOTATION.md](TERMINOLOGY_AND_NOTATION.md). Aggregation is bound to
a data cell and time interval; functional regions supply its requirements.

## Requirements and inheritance

An enabled aggregation stream may select either a uniform metric_policy or a policy_tree,
never both. Each tree has an ID, version, application ID and the stream's fixed square
coverage/max depth. Explicit metric requirements are inherited in this order:

```text
application root requirements
  -> selected Region's region_taxonomy metric_requirements
  -> that Region instance's metric_requirements
```

These are intersected hard bounds: maximum of all lower bounds, minimum of all upper
bounds, union of required metrics. An empty intersection within one region is a startup
configuration error. A child cannot relax a parent by specifying a weaker bound.
The tree provides requirements; MetricEvaluator still computes values from candidates.
The existing legacy granularities and k_anonymity/l_diversity fields are not activated or
reinterpreted. Express new requirements using the explicit metric IDs and units in METRICS.md.

Example: root support >= 3, region-type support >= 5, instance support >= 2 gives >= 5.
Two cells with support 4 can therefore pass in the default area and fail in that region.
Root duration <= 1000 ms and regional duration >= 1200 ms are a configuration error.

## Spatial contract and compilation

Use existing Region instances with explicit IDs and their SFML geometry. A selected region
must be inside the stream coverage, rectangular and aligned to the finest supported cells.
Selected regions may overlap or nest. Every positive-area intersection contributes
requirements; touching edges or corners alone do not. Distinct Regions may have identical
geometry. Duplicate Region IDs, inconsistent definitions of one Region type, unknown
references, unsupported boundaries and exhausted node budgets are explicit errors.
Unselected regions do not apply to this application/stream.
An omitted Region ID gets a configuration-order ID for legacy compatibility; explicit IDs
are recommended wherever a policy_tree references regions.

The policy tree is a separate, sparse quadtree compiled once before database initialization.
Its synthetic root covers the whole sensor square. Four children match the data tree's
base-cell convention (depth 1, IDs 12–15). Refine only where a region boundary requires it;
do not expand every maximum-depth data leaf. A node is homogeneous when all intersecting
Regions contain its entire footprint, including multiple overlapping Regions. Its
descendants share one immutable effective policy, and lookup walks only existing nodes.
Enforce max_nodes.
Small numeric comparison tolerances handle representation error, not arbitrary boundary
snapping. Candidate ID, depth, bounds, grid and application must match the compiled domain.

A region does not own an aggregation bucket or choose its interval. Its bounds apply to
each intersecting data-cell/interval candidate. Data cells remain whole quadtree squares;
this lookup does not clip them to region geometry or prohibit cross-region merges.

Each policy node also stores the intersection for its complete footprint. A candidate
crossing multiple selected regions must satisfy all their requirements, including those
over portions without observed agents. A child's lookup starts from its own inherited
regional requirements, not from the cross-region intersection cached for its parent.

If regions A and B permit cell sides [5,10] and [20,40] respectively, their own candidates
can be feasible while their combined footprint has incompatible bounds [20,10]. Preserve
that parent as explicitly infeasible; its metric check reports contradictory_policy_bounds.
Do not abort the whole valid regional configuration and do not contaminate child policies.
The same rule applies where otherwise individually valid Regions overlap: the intersection
may be infeasible even at a finest leaf. Any ancestor touching that contradiction also
inherits it; a larger cell cannot remove a local hard requirement. Exclusive neighboring
footprints keep their own requirements. Malformed individual ranges and a single Region
contradicting the root still fail startup validation. No weighting, priority override or
averaging reconciles incompatible hard bounds. Merge, split, waiting and suppression
remain controller decisions; no candidate may bypass an infeasible policy.

## Configuration

Add metric_requirements to relevant region_taxonomy entries and/or regions instances.
The rest of the existing Region schema remains unchanged. Under an enabled AGBS aggregation:

```yaml
application_id: traffic-demo
policy_tree:
  id: traffic-regions
  version: "1"
  max_nodes: 65536
  root:
    distinct_contributors: {min: 3}
    cell_side_m: {max: 40}
    window_duration_ms: {max: 1000}
  regions: [west, northeast]
```

Root requirements are nonempty. Regional requirements may be absent/empty and then inherit.
For example, a type may set distinct_contributors: {min: 5}, while its region instance
sets age_at_evaluation_ms: {max: 1500}. These are demonstration thresholds, not validated
privacy/utility choices. Unknown tree options and unsupported action/preference settings
are rejected rather than accepted as inert configuration.

## Diagnostics and limits

Internal JSONL schema ump.fixed-candidate.v3 records uniform versus regional_tree mode,
tree/policy ID and version, per-cell effective-policy ID, contributing root/type/region
sources and structural feasibility. Existing numeric metrics, bounds and check reasons
remain visible. Conflicting parent bounds cannot pass. Missing observations still prevent
a successful overall assessment; unavailable reference metrics remain unavailable.

No new thread, SharedBuffer consumer, mutable data-tree reference or per-tick region scan
is introduced. The tree is immutable for the run. It uses standard C++; YAML/Region adaptation
and JSON serialization are outside the core. Construction-only Region geometry is
discarded after compilation; there is no per-timestep rectangle/polygon intersection.
Runtime policy changes, arbitrary polygons, temporal policy regions, regional execution
preferences and multiple simultaneously published application views remain outside this gate.
A02 now provides [bounded private reconstruction](AGGREGATION_HISTORY.md) for alternative
cell/interval candidates; this does not change policy or publication semantics.

## Implementation and runnable example

- `PolicyTree.hpp/.cpp`: standard-C++ immutable geometry, inheritance, sparse compilation
  and lookup. A homogeneous depth-14 quadrant needs five nodes; a single finest-leaf region
  needs 57 nodes, rather than enumerating 268,435,456 finest cells.
- `PolicyConfiguration.hpp/.cpp`: strict YAML parsing and value adaptation from Region.
- `Simulation.cpp`: initialize Region metadata and compile each enabled stream's evaluator
  before database initialization. Other pre-existing sensor setup validation is not moved
  wholesale into this policy preflight.
- `CandidateMetrics.cpp`: resolve per-cell requirements, calculate values and report checks.
- `AggregationDiagnostics.cpp`: serialize v3 assessments, including policy provenance.

The complete `simulator/examples/regional-policy/config.yaml` has one root and two selected
regions. Since A02 it also enables bounded private history with explicit resource limits. Run it from its directory using `../../build/Simulator` after the normal build.
It requires local MongoDB and uses `UMP_PolicyTree_Demo` with clearing disabled. Repeated
runs append raw data; each run receives a new JSONL candidate file. It starts headless;
the optional renderer still shows sensor cells, not policy decisions.

The default support minimum is 1. Region `west` inherits minimum 5 from `demo_residential`;
its instance minimum 2 cannot weaken 5. Region `northeast` inherits duration <= 200 ms from
`demo_traffic`, so its 400-ms fixed candidates fail that check. Areas outside both selected
regions use the root. All thresholds are illustrative. Agent placement is not reproducibly
seeded, so exact occupied-cell counts vary; deterministic unit fixtures establish the rules.

## Strict overlapping Region gate — 2026-10-23

The focused policy regression covers partial, nested and identical overlaps; edge/corner
contact; strict root/type/instance bounds; complete ancestor footprints including empty
strict patches; contradictory overlaps with feasible exclusive neighbors; Region-order
stability; immutable lookup and sparse D14 construction/node budgets. An independent
physical-rectangle oracle checks every D6 leaf (4,096) and every nonroot ancestor (1,364),
including infeasible intersections and the complete provenance set.

A persistent standard-C++ cell-local controller fixture places observations in one
infeasible overlap and one legal adjacent leaf. It checks that all nine neighboring
contributions are selected, all nine conflict contributions are suppressed, windows finish
within their 400-ms cap and terminal retirement footprints do not overlap in space-time.
This tests mechanism correctness; it does not establish a privacy gain or optimality.
The focused Release-style binary and its AddressSanitizer/UBSan build both pass.
All three unchanged real-map exports also pass the updated production probe, with
5,460 ordinary and 5,460 additional-overlap resolutions per footprint. Their compiled
node counts remain 5,197 / 4,889 / 5,077 for overview / detail / close detail.

The existing OSM exports stay unchanged as disjoint raster tilings. Their production probe
now separately verifies acceptance of an identical additional Region and independently
resolves all 5,460 cells with its extra provenance. Duplicate Region IDs remain a negative
case. This keeps raster-export tiling validation distinct from Region overlap support.

No movement generator, map scene policy, metric formula, controller priority or publication
schema changes are part of this gate. Numeric feasibility remains distinct from observed
metric success. Run the focused `policy_regression` test after the normal build; the
historical verification below describes the earlier nonoverlapping implementation.

## Verification — 2026-10-13

The full Release build and all seven CTest suites passed. `PolicyRegressionTests` covers
root/type/instance inheritance, provenance, source-order stability, independent applications,
coverage, cross-region conflicts with feasible children, geometry errors and sparse/node-budget
behavior. `PolicyConfigurationTests` covers actual Region adaptation, strict YAML options,
legacy-field isolation and uniform/no-policy compatibility. Neither new suite opens a window
or database. The policy core also compiled and ran with C++17, `-Wall -Wextra -Werror` and
no SFML/YAML/MongoDB linkage.

```bash
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release
cmake --build simulator/build -j 4
ctest --test-dir simulator/build -R 'policy_' --output-on-failure
```

The existing sensor integration suite is enabled with `-DUMP_BUILD_SENSOR_REGRESSION_TESTS=ON`
and requires local MongoDB. The full seven-suite run used an isolated build with that option.
The normal `simulator/build/Simulator` was also rebuilt.

A complete headless regional run using 200 agents, 50-ms simulation steps, 100-ms sensor
sampling and 400-ms windows verified five v3 windows and 308 occupied-cell assessments.
An independent geometry-based expectation checked all four bounds, observed values, status
and sources per cell: 172 passed, 136 failed. These counts describe that fixture only.
At that earlier date, nine invalid configurations (unknown Region/type, duplicate Region
ID, overlap, unaligned boundary, inherited contradiction, exhausted node budget, unknown
metric, mixed policy modes)
failed before clearing or metadata writes. A sentinel created in a disposable database was
unchanged after every failure. A separate four-stream run checked twelve windows for uniform
pass/fail/unavailable and absent-policy compatibility with the new v3 fields.

Integration fixtures used only UUID-named databases, which were removed. Existing Simulation
data and the maintained config were untouched. These checks do not measure full-run policy
performance, empirical privacy or application utility; those studies remain in TO-DO.


## Application execution policy

```yaml
policy_tree:
  # Existing id/version/root/regions apply.
  execution:
    publication_model: private_final_snapshot
    strategy: spatial_first
```

`publication_model` is required when `aggregation.publication` is enabled; only
`private_final_snapshot` is implemented. `strategy` is required with
`aggregation.temporal_adaptation`; supported choices are `temporal_first` (try spatial
coarsening first to preserve time) and `spatial_first` (try time extension first to preserve
space). Execution choices are root/application-level only. Regional strategies and other
model names are explicitly rejected; they are not inherited as numeric bounds. Storage
names/retry limits belong to `aggregation.publication`, not the tree.

Regional time requirements remain intersected numeric bounds. The initial controller uses
the strictest whole-domain time maximum, including empty base footprints. Thus one region
can constrain the shared window for all cells. This is an explicit conservative coordination
choice, not independently scheduled regional adaptation. See
[TEMPORAL_AGGREGATION.md](TEMPORAL_AGGREGATION.md).


## Current integration scope (2026-10-23)

The shared-window paragraph above describes the original controller.
Taxonomy-enabled `semantic_first`, `semantic_secondary_strategy` and
`release_trigger` are specified in [SEMANTIC_RELEASE_CONTROL.md](SEMANTIC_RELEASE_CONTROL.md).
The verified cell-local integration follows
[SEMANTIC_CELL_LOCAL_CONTRACT_2026-10-22.md](SEMANTIC_CELL_LOCAL_CONTRACT_2026-10-22.md)
and its [test report](SEMANTIC_CELL_LOCAL_TEST_REPORT_2026-10-22.md).
Regions supply numeric requirements; cells own independent intervals. Application
execution choices remain root-level, with no regional strategy override.
