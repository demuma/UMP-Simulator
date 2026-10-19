# Cell-local space-time coordination

Implementation date: 2026-10-19. The opt-in `cell_local` controller shares the existing
fine observation history and metric/policy evaluator. It adds independent cell windows,
mixed-depth ownership, unpublished parent takeovers and spatially scoped publication.
The `common_window` controller remains the default and the historical comparison baseline.
Verification results are recorded separately in [the coordination test report](COORDINATION_TEST_REPORT_2026-10-19.md).

## Cell counts, owners and history

For side length L and finest depth D, there are 4^D possible input cells, each of side
L/2^D. With L=80 m and D=6 this is 4096 cells of 1.25 m side. This is not a requirement
to allocate 4096 histories or prepare every ancestor. The data tree has four depth-one
base cells; its synthetic depth-zero root is not a legal publication footprint.

`AggregationHistory` still stores one bounded sequence of sensor samples. Identity-bearing
observations stay private at the configured finest depth. Parent counts and distinct
road-user unions are reconstructed from the requested cell and interval. Spatial output
coarsening does not remove fine input history.

`CellLocalAggregation` maintains a full, disjoint spatial ownership frontier. Each owner
has a cell, original interval start, next check, absolute deadline, evaluation/extension
counts and immutable latest check. Empty subtrees are represented by coarse owners.
Observed paths are refined without resetting their contribution start. Fresh sibling owners
with equivalent clocks coalesce privately; empty prefixes can be explicitly retired to
align idle clocks before coalescing. Subsequent observations expand fine support again. The selected
output cut and the private ownership frontier are different objects.

A bucket is a cell **and** an interval: b=(C,[s,e)). An owner can make several alternative
private proposals. A provisional proposal has no authority to publish until the complete
support is reserved and validated. The existing `CandidateBucket` record API remains a
separate optional history interface; the local controller's actual owners are
`CellLocalWindow` values, not automatically registered `CandidateBucket` records.

## Ownership invariants

For the current frontier F, every finest spatial cell belongs to exactly one owner in F.
Two owners cannot contain one another. Each owner starts at that area's retirement
frontier. Retirement includes approved output, explicit suppression and private empty
completion; it is independent of how long source observations remain in memory.

A terminal decision covers C x [s,e). Once acknowledged, this support cannot be consumed
by another terminal decision. Adjacent intervals use half-open boundaries. Different
spatial areas may have overlapping time intervals and different durations.

A parent P may replace a mixed frontier such as {a1,a2,a3,a4,B,C,D}, where a1..a4 are
children of A, without requiring all current owners to have equal depth. It must obtain
complete measurements over **one exact target interval** from every part of P. Counts
for unrelated durations cannot simply be added; distinct road users are an exact union.

The independent oracle audits both the public stream and private retirement. It recomputes
counts, distinct support, means, geometry, coverage and policies directly from raw samples.
Morton intervals detect space-time overlap. Exact finest-cell-time volume checks complete
retirement, including measured-empty areas, without enumerating the full deepest grid.
Contribution conservation is checked separately; empty spatial holes cannot hide behind
an otherwise correct count total.

## Independent windows and bounded sibling holds

Each cell's effective policy supplies its own duration/age limits. A low-latency regional
maximum no longer globally shortens every other region's interval. Minimum duration,
maximum duration, age at evaluation, complete coverage and all other mandatory checks
remain binding. Region polygons/rectangles are policy inputs, never owners or clocks.

The project convention is unchanged:

- Temporal First preserves temporal detail: attempt spatial aggregation before extending.
- Spatial First preserves spatial detail: attempt temporal extension before spatial fallback.

Passing or known-empty same-start siblings may be held privately only for a concrete
compatible ancestor with feasible geometry and a possible common future interval.
An unrelated failure under the same minimum-depth ancestor is insufficient. Invalid
geometry, contradictory/unavailable requirements, irreparable count maxima and disjoint
time bounds prohibit the hold. Potential future support is not a guaranteed later pass.
Every held cell keeps its own deadline. At that deadline it must resolve locally rather
than wait indefinitely for a slower sibling. This can close a later historical parent
option. A coordination hold is recorded separately from a failed-cell extension.

This is a deterministic legal-action protocol, not a proof that the chosen output maximizes
retention or minimizes latency. Conflicting requirements may leave no releasable candidate.
Suppression prevents that release; it does not satisfy a mandatory availability constraint.

## Endpoint planning before disclosure

The refined automatic controller evaluates the current private endpoint before its
first disclosure. Each failed owner proposes its nearest permitted passing ancestor.
Containing proposals replace nested smaller proposals only when another failed branch
needs that broader rescue; separate finer rescues remain separate. This prevents an
earlier small publication from unnecessarily blocking a currently valid broader one.
Unique reconstructable ancestor assessments have a per-endpoint spatial budget; due-owner
temporal caps are preflighted before output. Accepted proposals are revalidated. This
is a causal deterministic heuristic, not globally optimal scheduling. See the measured
[refinement and before/after contract](COORDINATION_REFINEMENT_2026-10-19.md).

## Immediate parent takeover and retained suffixes

`requestMerge(domain,endMs,history)` attempts a parent over the active descendants'
common unpublished start and the requested closed end. Different planned next endpoints
are allowed. Geometry, complete coverage, temporal limits, full-footprint policy and
ownership must all pass. A rejected proposal leaves ownership and progress unchanged.

For example, a1 may be collecting [0,400) and B may next check at 200 ms. With complete
private support, P can be evaluated for [0,300). An accepted takeover retires P through
300 ms and starts its successor at 300 ms. Observations at or after 300 ms remain in
history and belong to the successor. The earliest remaining observation's age is not
reset: its start is the actual handoff boundary. Resulting short intervals still need
their own policy assessment; a base check interval is not automatically a policy minimum.

Parent publication replaces competing descendant publication for that interval. It does
not emit both parent and child results. Source history is retained according to its
existing limits and can support private alternatives until retirement makes them ineligible.

## Different retired starts and future handoff

If B already retired [0,200), P cannot retrospectively publish [0,300), even when all
observations are still in memory. Deleting/replacing a MongoDB document does not erase
what a recipient already learned.

`scheduleMerge(domain)` coordinates a common future boundary instead. Descendants finish
their earlier prefixes under their own policies and deadlines. Prefixes that cannot legally
be published are explicitly suppressed. Only after every part has reached the boundary
can the domain begin a common new interval. The future parent does not repair suppression
of an older prefix. Requests cannot overlap or escape their reserved domain.

The controller can refine a new parent ownership domain again to inspect finer output;
refinement preserves the shared start. A later passing parent can therefore still replace
that new private descendant frontier. No published support is reopened.

This protocol does not optimize arbitrary overlapping rolling windows or backtrack over
past releases. It does not allow arbitrary historical revisions of the recipient stream.
A globally optimal asynchronous planner remains a different research problem.

## Publication, acknowledgements and recovery

`PublicationCoordinator(...,cellLocal=true)` validates an explicit
`SpatialSelection.coordinationCell`. Its sparse `CellWindowLedger` tracks retirement
per spatial subtree, independently of history retention. Uniform sibling clocks coalesce.
Immutable tree nodes use path copying; a ledger snapshot is cheap and retirement changes
only the affected path. For D=6, all 4096 distinct finest clocks require 5460 logical
nodes; equal clocks compress back to four base nodes.

A terminal selection and its successor state are prepared before invoking the sink.
An exception holds the exact immutable proposal and blocks later work until retry.
Publication also prepares the successor retirement ledger before possible disclosure;
acknowledgement installs it without allocating. The sink must acknowledge an entire
immutable release and deduplicate by release ID. An ambiguous disclosure cannot be rolled
back. Retrying later rechecks time-sensitive requirements at the actual delivery time.

Scoped releases use `ump.release.v2` and IDs containing stream, interval, cell ID and depth.
Two different cells may publish the same time interval without an ID collision. BSON,
private durable journal and recovery parsing preserve `coordination_cell`. Existing
common-window `ump.release.v1` output is unchanged. A truncated local final interval does
not finish unrelated spatial domains. Empty/suppressed completion has no recipient-visible
empty record. By default its no-output retirement is checkpointed in the private journal.
The explicit `publication.journal_empty_retirements:false` option skips only these
no-recipient checkpoints; every actual recipient release still uses prepare/publish/commit.
Full private JSONL diagnostics and the in-memory retirement ledger remain enabled.
With this option the journal recovers disclosed releases, not a complete controller
retirement checkpoint. Automatic controller restart is unsupported in both modes.

Automatic simulation checkpoint/restart remains outside the contract. Journal recovery
supports immutable delivery recovery; it does not reconstruct agent motion or controller
state from a terminated simulation.

## Configuration and execution

```yaml
temporal_adaptation:
  coordination: cell_local
  max_active_cells: 8192
  extension_step_ms: 100
  max_window_ms: 1000
  max_evaluations: 16
```

`coordination` defaults to `common_window`. The local owner bound is distinct from
`history.max_buckets`, which limits optional logical bucket records. History observation,
bin, identity-payload, retention, spatial-search and temporal-evaluation budgets still
apply. Exhaustion is an explicit error, not silent approximation or unbounded allocation.
Recipient retirement has a separate bounded sparse ledger.

Build and run the separate example from the repository root:

```sh
cmake -S simulator -B simulator/build
cmake --build simulator/build -j 8
ctest --test-dir simulator/build --output-on-failure
cd simulator/examples/cell-local-coordination
../../build/Simulator
```

The example disables no-output journal checkpoints to avoid a database round trip for each
internal empty/handoff retirement. It has its own raw, release and private-journal databases, `clear_database:false`,
an 80 m square, depth-six fine input, 10 Hz observations, a 400 ms initial check and a
1000 ms global cap. Its northeastern region caps age/duration at 400 ms while other
regions may extend farther. Thresholds demonstrate mechanics; they are not validated
privacy guarantees.

The live progress snapshot lists actual per-cell intervals and dated checks. Its top-level
clocks are summary minima, not a common interval. Dashed outlines show local pending
checks. Idle coalescing clears obsolete display lineage, so transition labels may restart
as `initial` on later occupancy; previously recorded output is immutable. The completed-output overlay currently shows the **latest local decision**,
explicitly labelled; a persistent mosaic of every most recent regional decision is a
separate visualization extension. Renderer code makes no aggregation decisions.

## Evaluation and remaining limits

The actual local controller is integrated in both Simulation and AggregationReplay.
Replay selects it through configuration; existing mode names still choose Temporal First
or Spatial First. Results contain `parameters.coordination:cell_local`; every diagnostic
window and recipient release carries its spatial scope.

The occupancy evaluator supports disjoint space-time releases. The public-only empirical
export validates a local scope against its sole released cell, then normalizes this
redundant geometry copy away. Public counts, cell geometry and timing remain visible.
The existing published pilot numbers describe common-window runs and must not be relabelled
as local-window evidence. New comparative privacy/utility studies require frozen inputs
and explicitly recorded coordination settings.

The independent compliance audit supports local windows. Existing whole-domain feasibility
enumeration rejects local-mode comparisons explicitly because its reference class assumes
common windows; it is not an asynchronous optimality oracle.

Automatic multi-level preemptive **statistic caches** remain E05. Bounded coordination holds
and actual active windows establish ownership; caching can later accelerate eligible
reconstruction without changing the release protocol. Real maps, shop demand, trajectory
planning and additional privacy threat models are unchanged by this implementation.
