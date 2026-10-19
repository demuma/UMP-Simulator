# Bounded temporal aggregation

**October 19 implementation update:** the descriptions of a single common interval below
refer to the retained baseline. The opt-in cell-local controller, scoped publication and
independent space-time audit are documented in [CELL_LOCAL_COORDINATION.md](CELL_LOCAL_COORDINATION.md).
The historical numerical pilot results are unchanged.

Implemented A03 baseline, 2026-10-14. `AdaptiveAggregation` chooses a variable common
interval and an eligible spatial cut from the existing bounded private observation
history. It supports Temporal First and Spatial First, early completion, regional time
caps, suppression, and a final flush. It is integrated with the AGBS manager, internal
JSONL diagnostics, renderer snapshots, and the optional durable publication path.

The scope is one run/sensor/application stream and one whole sensor grid as its
coordination domain. All footprints in a terminal cut use the same interval. Policy
requirements may vary by region, but execution priority is selected once at the policy
tree root. The current mode does not let cells or coordinated merge groups complete different
windows independently. A semantic region is not a window/bucket owner.

See [aggregation history](AGGREGATION_HISTORY.md),
[spatial selection](SPATIAL_SELECTION.md), and
[publication coordination](PUBLICATION_COORDINATION.md) for the underlying contracts.
The [adaptive publication implementation contract](ADAPTIVE_PUBLICATION_IMPLEMENTATION.md)
records the combined A03/A05 scope.

Canonical terms, symbols, units and code mappings are defined in
[TERMINOLOGY_AND_NOTATION.md](TERMINOLOGY_AND_NOTATION.md). Aggregation is bound to
a data cell and time interval; functional regions supply its requirements.

## Configuration and example

The maintained example is
[`simulator/examples/temporal-aggregation/config.yaml`](../simulator/examples/temporal-aggregation/config.yaml).
From the repository root, run the built simulator with that example as its working
directory:

```sh
cd simulator/examples/temporal-aggregation
../../build/Simulator
```

The program loads `config.yaml` from its working directory. The example uses a local
MongoDB server, 200 simulated agents, a 10 Hz AGBS stream, a 400 ms initial window,
100 ms extension steps, and a 1000 ms maximum. Its 80 m square has finest depth 6,
which gives 1.25 m leaf sides. It runs for 30 simulated seconds at 0.5x playback,
with completed output (G) and running progress (P) initially visible, and the black fine
sensor grid (H) hidden. Space pauses/resumes playback. The sidebar labels the latest
completed interval separately from the current collecting/extending interval, next check
and deadline. Pending dashed amber outlines are dated check results, never a release.
See [live progress](LIVE_AGGREGATION_PROGRESS.md) for the display/transport contract.

The example appends raw research data to `UMP_Temporal_Demo_Raw`, recipient releases
to `UMP_Temporal_Demo_Releases`, and private journal entries to
`UMP_Temporal_Demo_Private`. Database clearing is disabled. Internal JSONL files are
written under the example's `results/aggregation` directory. The normal
`simulator/config.yaml` is unaffected.

The adaptive settings live under the enabled sensor's `aggregation` block. This
excerpt shows the relevant structure; the complete example also supplies the sensor,
region definitions, history limits, and publication destination:

```yaml
aggregation:
  enabled: true
  application_id: occupancy-demo
  window_ms: 400
  spatial_selection:
    min_depth: 1
    max_evaluations: 4096
  temporal_adaptation:
    extension_step_ms: 100
    max_window_ms: 1000
    max_evaluations: 16
  history:
    retention_ms: 2000
    max_bins: 32
    max_observations: 100000
    max_identity_bytes: 16000000
    max_buckets: 128
  policy_tree:
    id: occupancy-regions
    version: '1'
    max_nodes: 65536
    execution:
      publication_model: private_final_snapshot
      strategy: spatial_first
    root:
      distinct_contributors: {min: 2}
      cell_side_m: {min: 1, max: 40}
      window_duration_ms: {max: 1000}
      age_at_evaluation_ms: {max: 1000}
    regions: [west, northeast]
```

`temporal_adaptation` requires bounded `history`, `spatial_selection`, and an explicit
`policy_tree.execution.strategy`. Its three keys are required positive values;
unknown or duplicate keys are rejected. `window_ms`, `extension_step_ms`, and
`max_window_ms` must align to the integer sensor sampling period. The global maximum
must be at least `window_ms`, and history retention must cover that global maximum.
A regional policy can shorten the effective interval below `window_ms` as described
below. Invalid geometry, schedules, budgets, and execution settings fail startup
preflight before database initialization.

`policy_tree.execution` accepts the strategy names `temporal_first` and
`spatial_first`. `private_final_snapshot` is the supported publication model.
Publication additionally requires an explicit `aggregation.publication` block; the
model name by itself does not create a recipient sink. Without that destination,
adaptive selections remain internal diagnostics. See the publication document for
its destination, retry, and journal settings.

Region types and instances provide metric requirements through the existing policy
tree. Per-region execution strategies or publication-model overrides are rejected.
The legacy `granularities` and `privacy.k_anonymity` fields do not supply the metric
requirements used by this controller. Changing the application strategy requires
changing the root `execution.strategy` value.

## Strategy semantics

The names identify the dimension to preserve:

| Strategy | Preserved dimension | Order when the finest candidate fails |
| --- | --- | --- |
| Temporal First | Temporal detail | Try spatial coarsening at the current interval; extend time if the cut is still unresolved. |
| Spatial First | Spatial detail | Extend time while permitted; try spatial coarsening at the temporal bound, deadline, or final flush. |

Both strategies first evaluate the finest candidate. A complete, passing finest cut
finishes immediately at its scheduled evaluation boundary. Temporal First can also
finish at that boundary when spatial coarsening makes the whole cut eligible.
Spatial First keeps a failing finest cut private while another temporal extension
is legal, even if a parent would already pass.

For example, at `[0,400)` two sibling leaves each contain one distinct contributor
and their parent contains two. With a minimum of two and a legal parent size,
Temporal First can finish at 400 ms with that parent. If each leaf acquires its
second contributor at 400 ms, Spatial First can extend to `[0,500)` and finish with
two fine leaves. Both choices obey the same requirements; their priority differs.

This is a deterministic action order, not an optimization over a utility function.
An extension is an allowed attempt to obtain a passing candidate; it is not a
prediction that every metric will improve. Mean occupancy, for example, can fall
when additional measured samples are empty.

## Exact support and time semantics

All intervals are half-open `[s,e)` in integer simulation milliseconds. A sample at
`e` belongs to the following interval. Scheduled observations start at one sampling
period after zero; no sample is fabricated at `t=0`.

For a spatial footprint `C`, let `O(C,[s,e))` be its measured observation records,
`I(o)` an observation's internal contributor identity, and `m` the number of measured
sensor samples in the interval. The implemented statistics are:

```text
observation_contributions(C,[s,e)) = |O(C,[s,e))|
distinct_contributors(C,[s,e))     = |union { I(o) : o in O(C,[s,e)) }|
mean_sample_occupancy(C,[s,e))     = observation_contributions / m, if m > 0
```

Each measured-empty sample contributes to `m`. Missing and unavailable samples do
not establish empty occupancy. Type counts count observation contributions of each
type, not unique contributors of that type.

`AggregationHistory::queryFinest(s,e)` reconstructs the complete observed leaf cut
and its exact global identity union from retained bins. Ancestor queries reconstruct
parent support from those same bins. Neither operation sums child or earlier-window
distinct counts. If A and B both visit two cells, each cell can have two distinct
contributors while the global total is still two. If A appears in three samples and
B arrives in the fourth, the extended interval has two distinct contributors and
four observation contributions.

The original `s` stays fixed through every extension. After a successful terminal
sink, the next interval starts at the finalized `e`. Adjacent outputs therefore have
`e_i = s_(i+1)`. The controller never replaces a previously completed interval with
an expanded interval. Future refinement uses fresh support after that common boundary.

## Effective bounds and evaluation schedule

Let `P` be the sampling period, `W` the nominal initial `window_ms`, `S` the extension
step, and `M` the configured global maximum. The immutable evaluator resolves all
four depth-1 base footprints, including their empty areas. Their policy checks expose
the applicable maximum duration and age requirements. The common duration cap is:

```text
C = P * floor(min(M, all applicable duration maxima, all applicable age maxima) / P)
first_end = s + min(W,C)
next_end  = min(current_end + S, s + C)
```

Absent policy maxima do not add a bound. A cap with no positive aligned interval is
rejected. The four base cells have IDs 12 through 15; the synthetic depth-zero root
is not a representable data candidate.

The cap is deliberately conservative across the whole domain. A 500 ms limit in an
empty regional footprint can cap all neighbors at 500 ms. With `W=400`, `P=100`, and
a regional maximum of 350 ms, the first endpoint is 300 ms. This is a legal shorter
common window even though the configured global maximum must be at least 400 ms.
A stricter empty area cannot be ignored merely because no agent currently occupies it.

Every actual spatial proposal also resolves requirements for its complete footprint.
A parent covering an empty strict sibling inherits that sibling's applicable bounds.
The time cap does not bypass the full metric checks or make contradictory policies
feasible. Passing neighbors can be held while another footprint is unresolved, but
the common schedule stops at the earliest applicable time cap.

At each scheduled endpoint reached by manager progress, the controller:

1. Reconstructs `[s,e)` from the shared history and evaluates the finest cut at the
   actual current simulation time.
2. Follows the configured strategy, using a private spatial proposal when appropriate.
3. Finalizes early if the complete proposed cut passes, or schedules the next bounded
   extension while preserving `s`.
4. At the cap, an already reached deadline, or shutdown, attempts the remaining spatial
   fallback and finalizes selected and explicitly suppressed footprints together.

The controller does not assess every simulator frame or interpolate between extension
endpoints. For `W=400`, `S=200`, and `M=800`, its ordinary probes are 400, 600, and
800 ms. A pass at 600 ms completes the window before the configured maximum.

Duration and freshness remain distinct metrics:

```text
window_duration_ms   = e - s
age_at_evaluation_ms = now - s
post_window_delay_ms = now - e
```

A delayed progress call uses its actual `now`; it cannot backdate approval to a missed
endpoint. Current age and delay checks can therefore suppress a candidate whose
historical interval duration was legal. Publication rechecks selected requirements
again when sealing and delivering.

## Incomplete evidence, finalization, and publication

Missing or unavailable observation coverage cannot pass the coverage gate, regardless
of numeric counts. The controller finalizes such a closed interval with suppression;
a later extension cannot repair a missing prefix. A required metric that is unavailable
also cannot approve a cell. The spatial selector retains explicit failure evidence in
its private output. An evicted or future history interval returns no reconstructable
candidate and causes an explicit error before output, rather than plausible partial
counts. Complete measured-empty intervals finalize without fabricated zero-cell releases.

`SpatialSelector::propose` computes a cut without changing its previous selected geometry.
Only a successful terminal sink is followed by `commit`. A sink exception preserves the
controller's pending interval and the selector's previous transition state. The simulator
treats output failures as explicit failures; it does not silently advance past them.

The optional publication callback seals one immutable selected-only snapshot and performs
bounded synchronous durable delivery. After successful delivery or private retirement,
internal diagnostics record that result. Acknowledged intervals are retired as a whole;
suppressed footprints and global diagnostic totals are absent from recipient output.
No historical parent can subsequently reuse an interval already retired by the coordinator.
Retries preserve the same release ID and content. Detailed persistence and failure handling
are specified in [publication coordination](PUBLICATION_COORDINATION.md).

`finish(end)` resolves the last unfinished interval even when `end` is between scheduled
probes or exactly on a nominal fixed-window boundary. It preserves the original start,
marks the final candidate `truncated=true`, and uses `end_of_stream` as the completion
reason. The marker identifies terminal stream support even when the interval happens
to have a nominally full duration. It does not collect beyond the stream end or emit a
zero-length suffix. A planned extension canceled at the original endpoint contributes
zero to the reported temporal extension count; a collected partial extension counts once.
Further advance or finish calls are rejected after completion.

## Ownership, budgets, and diagnostics

The manager owns the sole bounded identity-bearing history. A synchronous progress callback
runs after its watermark advances; final shutdown supplies a separate finishing event.
A03 adds no observation copy store, SharedBuffer reader, background worker, or per-cell
payload bucket. Its persistent state consists of one pending common interval, its bounded
action trace, and the selector's previous geometry. History queries currently scan retained
bins, so a larger legal search can cost more computation.

The temporal evaluation budget is distinct from the spatial budget. Startup verifies that
the configured ordinary schedule fits:

```text
required_temporal_probes = 1 + ceil((M - W) / S)
required_temporal_probes <= temporal_adaptation.max_evaluations
```

`spatial_selection.max_evaluations` bounds a spatial proposal's finest-cell and ancestor
checks. History independently bounds retention duration, bins, observations, identity/type
string bytes, and logical bucket records. Publication has its own output-size and retry
bounds. Exceeding a budget raises an error; it does not weaken requirements or discard
support while claiming completeness. Retention must still cover the active original start
when a progress call runs; a large jump that evicts it fails explicitly.

Raw AGBS capture, existing raw MongoDB output, and fixed-window candidate diagnostics retain
their existing meanings. Adaptive terminal selections are written separately to
`selection-*.jsonl`, using `ump.spatial-selection.v1`. Fixed raw-window candidates continue
in `candidates-*.jsonl` using `ump.fixed-candidate.v3`; their endpoints need not match the
adaptive endpoints. Both files are internal research data.

Selection diagnostics include:

| Field | Meaning |
| --- | --- |
| `start_ms`, `end_ms`, `closed_at_ms`, `truncated` | Exact selected interval, actual evaluation/closure time, and final-stream marker. |
| `spatial_selection.mode` | `temporal_first`, `spatial_first`, or the fixed spatial-only mode. |
| `spatial_selection.temporal_extensions` | Number of collected extension steps, including a partial final step. |
| `spatial_selection.completion_reason` | `requirements_met`, `max_window`, `policy_deadline`, `coverage_unavailable`, or `end_of_stream`. |
| `temporal_decisions` | Typed `evaluate_finest`, `coarsen_spatially`, `extend_window`, and `finalize` actions with interval, evaluation time, and assessment status. |
| `source_cells`, `attempts`, `cells` | Final interval's finest evidence, spatial attempts, and terminal cut including suppressed diagnostic footprints. |
| `spatial_selection.publication`, `release_id` | `disabled`, `committed`, or `retired_without_release`, with the release identifier when publication is enabled. |

`source_cells` and `attempts` describe the final interval's spatial search. The temporal
trace records earlier actions and statuses; it does not retain a full per-cell candidate
copy for every probe. Internal selected/suppressed counters and refinement/coarsening
transitions remain available in the immutable renderer attachment. The renderer reads
that snapshot and does not query history or influence decisions. Final output produced
only during shutdown is persisted to diagnostics even if no later frame displays it.

## Verification and remaining work

`AdaptiveAggregationRegressionTests` and the existing `SpatialRegressionTests` passed
with the implemented core. The adaptive suite uses deterministic observations and covers:

- Repeated identities across samples, moving identities across cells, exact global unions,
  measured sample denominators, and preservation of the original start.
- Temporal First selecting a legal parent at 400 ms while Spatial First selects fine cells
  at 500 ms; early completion before the global maximum and explicit extension-step probes.
- Maximum-window fallback and suppression, regional duration/age caps in empty footprints,
  passing neighbors, and a regional cap below the nominal initial window.
- Missing and unavailable coverage, late evaluation with current age, evicted history,
  foreign application history, and invalid schedules or budgets.
- Shared-manager shutdown at 400, 450, and 500 ms, including exact boundaries; unchanged
  fixed diagnostics; sink exceptions without premature commit; and repeated progress
  without duplicate support.
- Mixed-depth cuts, later refinement, contiguous terminal intervals, and bounded retained
  state over a longer replay.

From the repository root:

```sh
ctest --test-dir simulator/build --output-on-failure -R 'adaptive_aggregation_regression|spatial_regression'
```

These tests establish implemented mechanics and invariants. Distinct contributor thresholds
remain support proxies. This implementation does not establish a formal anonymity property,
differential privacy, reduced re-identification risk, measured utility gains, or performance
improvements. The example thresholds demonstrate behavior and are not validated privacy
parameters.

Independent sibling/region windows, smaller coordination domains, early child publication,
region-specific strategy conflicts, concurrent policy contexts, selective descendant rescue,
and alternative publication models remain future work. Automatic ancestor prewarming,
selective/full preemptive caches, and spatial history indexes are also deferred. They need
bounded equivalence and cost tests before adoption. Strategy, privacy, utility, latency, and
prepare-cost comparisons require controlled experiments; no experimental outcome is claimed
by this baseline. Durable publication reconciliation does not provide a simulator checkpoint
or automatic process restart with the same run ID.
