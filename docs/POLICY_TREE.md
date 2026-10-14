# Regional policy tree

Status: 2026-10-13. A04 initial numeric policy tree implemented and verified.
This extends fixed-window candidate assessment, not public release,
adaptive merge/split, preservation priorities or publication-model selection.

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
Selected regions must not overlap in positive area; touching edges are allowed. Unknown
region IDs/types, duplicate IDs/types, unsupported boundaries and exhausted node budgets
are explicit errors. Unselected regions do not apply to this application/stream.
An omitted Region ID gets a configuration-order ID for legacy compatibility; explicit IDs
are recommended wherever a policy_tree references regions.

The policy tree is a separate, sparse quadtree compiled once before database initialization.
Its synthetic root covers the whole sensor square. Four children match the data tree's
base-cell convention (depth 1, IDs 12–15). Refine only where a region boundary requires it;
do not expand every maximum-depth data leaf. Homogeneous descendants share one immutable
effective policy, and lookup walks only the existing policy nodes. Enforce max_nodes.
Small numeric comparison tolerances handle representation error, not arbitrary boundary
snapping. Candidate ID, depth, bounds, grid and application must match the compiled domain.

Each policy node also stores the intersection for its complete footprint. A candidate
crossing multiple selected regions must satisfy all their requirements, including those
over portions without observed agents. A child's lookup starts from its own inherited
regional requirements, not from the cross-region intersection cached for its parent.

If regions A and B permit cell sides [5,10] and [20,40] respectively, their own candidates
can be feasible while their combined footprint has incompatible bounds [20,10]. Preserve
that parent as explicitly infeasible; its metric check reports contradictory_policy_bounds.
Do not abort the whole valid regional configuration and do not contaminate child policies.
Whether to merge, split or suppress is a later decision-layer responsibility.

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
and JSON serialization are outside the core. Runtime policy changes, overlapping/nested
selected regions, arbitrary polygons, temporal policy regions, preference/action conflicts,
multiple simultaneously published application views and adaptive decision selection remain open.
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
Nine invalid configurations (unknown Region/type, duplicate Region ID, overlap, unaligned
boundary, inherited contradiction, exhausted node budget, unknown metric, mixed policy modes)
failed before clearing or metadata writes. A sentinel created in a disposable database was
unchanged after every failure. A separate four-stream run checked twelve windows for uniform
pass/fail/unavailable and absent-policy compatibility with the new v3 fields.

Integration fixtures used only UUID-named databases, which were removed. Existing Simulation
data and the maintained config were untouched. These checks do not measure full-run policy
performance, empirical privacy or application utility; those studies remain in TO-DO.
