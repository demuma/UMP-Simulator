# Asynchronous local replay contract

Date: 2026-10-22. This contract is implemented for the HTML replay viewer.
Model, server and browser verification are recorded in the
[test report](ASYNC_LOCAL_REPLAY_TEST_REPORT_2026-10-22.md). The extension changes
visualization only; the aggregation algorithm, release decisions, policy
thresholds, input observations and frozen results remain unchanged.

## A historical spatial mosaic

The pure model API is `mosaicAt(result, time, privateMode)`. Its entries retain
an original recorded `cell`, the original release/diagnostic `row`, a stable
origin key, and disjoint clipped display fragments. Fragments are rendering
masks, not new aggregation cells, inferred measurements or published records.
They must not acquire invented cell IDs, counts, category bins or intervals.

For a cell-local stream, each event's `coordination_cell` defines the footprint
whose display is updated. Scope must not be inferred from occupied cells: an
empty retirement has a scope too. A public release replaces only that scope
in the recipient mosaic; a private finalized window replaces only that scope
in the private mosaic. Cells or fragments outside it keep their own original
source intervals and availability timestamps.

A common-window or fixed-window reference continues to use its complete
recorded snapshot. Its implicit scope is the declared coverage, and a new
snapshot replaces the preceding snapshot in full. Common and local variants
may be compared on the same source; this does not create a new fixed baseline.

## Availability, event order and rewind

A recipient event becomes available only at `sealed_at_ms`; a private event
becomes available only at `evaluated_at_ms`. The exact timestamp is visible;
one millisecond before it is not. Only events available at the playhead may
participate in a mosaic or inspector lookup.

For each display position, the latest available event wins. Equal event times
are resolved by their original array index. This is delivery/finalization order,
not an optimization for the greatest source `end_ms`. An available later event
with an older source interval still has its recorded place in delivery history;
the viewer must not silently reorder it by apparent freshness.

Seeking backwards reconstructs the earlier event prefix. A cache must not
retain later replacements, private overlays or source-group summaries as
though they were available before their recorded event. Event time, source
interval and age remain distinct. No playback operation changes input data.

## Separate recipient and private histories

The recipient mosaic uses **only** public `releases`. A suppressed, unavailable
or empty private retirement does not erase a previously released recipient
aggregate. That aggregate can remain visible as an explicitly dated historical
value; it is not a current measurement and it has not been revoked.

The private mosaic uses finalized `windows`. A new private scope first replaces
its previous private display, including when `cells` is empty. Its recorded
selected and suppressed cells may then be displayed. Suppression is private
and never becomes a recipient record or a published zero. Empty regions and
missing public support are distinguished from an observed count of zero.

Switching the private overlay on and off must not mutate recipient state.
Private-only events may be included in the diagnostic timeline while the
private overlay is enabled; they must not fabricate recipient release events.
The bundle remains private research material in either display mode.

## Clipped original cells

Suppose a 40-m parent from `[0,400)` was published at 400 ms. At 800 ms a
20-m child publishes `[400,800)`. The child replaces its own display footprint.
The remaining parent display can be clipped around it, but every parent
fragment still refers to the **whole original 40-m cell and `[0,400)` interval**.

The parent's whole-cell count cannot be divided by visible area or repeated as
if it described each remaining fragment. The map must not put the whole count
inside a clipped fragment as its local occupancy. The inspector identifies the
original footprint, original interval, availability time, visible fragment(s)
and original category counts. Private source-group inspection also uses the
original cell and full original interval, not the clipped mask.

A later parent event can replace several child fragments. Positive-area
intersection determines replacement; sharing a boundary alone does not.
Clipped entries are visibly identified as historical remnants, not inferred
fine-resolution data. Selection keys distinguish an original event/cell from
the same cell ID in another interval. Source focus uses recorded geometry.

Cumulative released observations still count original public events once.
Fragment multiplicity must not increase cell totals, released observations or
release-event counts. Occupancies from asynchronous intervals must not be
summed into an asserted current-area population.

## Bounds and validation

Validate local scope IDs, depths, canonical geometry, containment, source
compatibility and event timing before accepting the bundle. Common/local mode
mismatches fail explicitly. Rendering must reject malformed scope or cell data
rather than infer replacement from a bounding box of occupied support.

Mask construction is bounded. Do not materialize every possible depth-14 leaf
or allocate an unbounded fragment collection. Exceeding the explicit model
budget produces a clear error; it must not silently drop old valid regions,
replace the mosaic with a latest-global frame or merge original statistics.
The model exports `MAX_VISIBLE_FRAGMENTS = 65536`. Exceeding it raises
`RangeError` and resets that incremental cache. The UI must clear the failed
view rather than display a stale or truncated mosaic. At most one incremental
state is retained per result/channel; rewinding rebuilds that channel from
its available event prefix.

## Required acceptance cases

1. Unrelated local owners update independently at different timestamps; both
   remain inspectable with their own original intervals.
2. A child clips an older parent, with all original parent counts unchanged;
   a later parent replaces its child displays.
3. Boundary-only contact does not clear an adjacent cell. Visible fragments
   are non-overlapping and remain inside their original footprints.
4. Public display is unaffected by private suppression, unavailable windows
   and empty retirements. Private empty retirement clears its own old scope.
5. Exact availability timestamps, stable equal-time event order and rewind
   are correct; the model never sorts by source freshness instead of event order.
6. Inspector selection and source groups stay tied to the correct original
   cell/window, including clipped cells and repeated IDs across intervals.
7. Fragment creation does not mutate source objects, duplicate release totals
   or fabricate zero counts; the mask budget fails explicitly.
8. Common-window snapshots, existing baseline replays, source controls and
   private opt-in retain their previous behavior.
9. Validate actual common/local results through the server and inspect a real
   browser comparison, including an independent local update, suppression,
   original interval labels and a backwards seek.

## Research sequence after this viewer gate

Review the aggregator's agreed requirements at every gate: eligibility,
semantic tiers, regional bounds, independent starts, merge/handoff coordination,
source retirement, budgets and publication retries. Record verified behavior
and remaining limits before interpreting the next result.

The next bounded step is **scope-aware semantic fixed-query utility**. It must
reconstruct answers from asynchronous recipient releases under declared spatial,
temporal and taxonomy rules, preserve unknown support, and report coverage with
conditional error and deadline availability. It is unfinished; the viewer does
not implement it.

Then compare common/local adaptation and legal fixed raster/window settings on
the **same existing moving input**, under the same hard policy and fixed query
cohort. A fixed raster/fixed window is an existing baseline; common-window
adaptive coordination is a separate ablation. Explicit duration minima, release
event costs and EOF scope must be declared rather than tuned after results.

Privacy evaluation follows those gates with a precise protected unit/secret,
recipient information and measured objective. The results can inform suitable
policies and scenarios. This sequence does not automatically start a new utility
optimizer, richer movement generator or attack matrix. Policy compliance,
category cost and improved utility alone do not establish privacy effectiveness.
