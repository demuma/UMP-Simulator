# Spatial candidate selection and live inspection

Implementation scope agreed on 2026-10-14 for the supervisor demonstration.

## Contract before implementation

- Select a non-overlapping spatial cut for each already-closed, common fixed window.
- Start from observed finest cells. A failing child requires assessment of the full parent
  footprint, replacing all sibling choices together if the parent meets every requirement.
- Use retained identity-bearing history for parent counts; never sum distinct child counts.
- Reapply the regional policy to each entire candidate footprint, including empty parts.
- Stop coarsening at an explicit minimum depth, within the four existing base-cell domains.
  Suppress the entire unresolved domain at that cap; selective fallback remains A07.
- Missing coverage and unavailable required metrics cannot select an eligible candidate.
- Reassess each new window from finest cells. A smaller chosen cell in a later window is
  refinement at a common boundary; no historical output is edited.
- No contributor IDs leave history. Decisions and diagnostics remain internal research data.
  This is an initial A03 spatial slice, not A05 public release/acknowledgement coordination.
- Keep simulation input separate from immutable renderer snapshots. Show sensor geometry,
  chosen aggregation cells, suppressed footprints, exact closed-window time and transitions.
- Bound candidate evaluations and retain only the previous cut for transition labels.
- Validate exact unions, sibling replacement, depth bounds, refinement, conflicting/unknown
  metrics, missing coverage, bounded work and live renderer transport before the demo.

Variable temporal windows, automatic prewarming, public releases/retries, hysteresis and
comparison of preservation strategies remain separate tasks. The implemented spatial-only
search is the first branch of Temporal First (preserve temporal detail); it does not yet
fall back to temporal extension.

## Implemented behavior

`SpatialSelector` is a standard-C++ component invoked synchronously when the manager closes
a fixed window. The original finest candidates and diagnostics continue unchanged. The
optional selector builds a sparse set of occupied ancestor paths, starts with the finest
assessments and visits a parent only when a child cannot supply an eligible cut. A passing
parent replaces every provisional sibling choice in that footprint. Its contributor count
comes from the history's exact identity union, including agents that crossed child cells.

Completely unobserved branches produce no zero-count release. Their regional constraints
still apply when a parent footprint includes them. Each final footprint is either selected
or internally suppressed. Selected and suppressed footprints together account for every
input contribution exactly once. Suppressed counts remain visible only in trusted debug
data. The method is a bounded greedy baseline, not a globally optimal suppression policy.

All alternatives remain private until the whole window has been assessed. There is no
early sibling output in this mode. Across windows, selected cells are labelled unchanged,
coarsened, refined or new support by comparing with the previous selected cut. These are
future interval transitions, not edits to previous output. A first-window parent is labelled
initial even though its selection already required combining finer observations.

The selector holds only the previous selected geometry between calls. The evaluation budget
counts finest-cell checks plus reconstructed ancestors. Exceeding it raises an explicit
error; it does not silently approve or discard support. History queries currently scan
retained bins; no preemptive cache, spatial history index or additional thread was added.
Failed diagnostic writes remain fatal, as in the existing fixed diagnostics path. No durable
publication acknowledgement, retry, idempotency ledger or recipient access boundary is
claimed. Those remain A05/F03 work before application-visible release.

## Configuration and live demo

Build normally, then run the separate example:

```sh
cd /Users/maxdemu/Developer/UMP-Simulator/simulator/examples/spatial-selection
../../build/Simulator
```

The example uses `UMP_SpatialSelection_Demo`, clearing disabled, 200 agents, 30 simulated
seconds, 0.5x playback and finest depth 3. It appends data on every invocation. The maintained
`simulator/config.yaml` is not modified. The example's root support minimum is two and the
west region inherits five; the northeast's 200-ms duration bound deliberately conflicts with
the fixed 400-ms window to demonstrate an unsatisfied application constraint.

Opt-in settings within an existing, history-enabled aggregation configuration:

```yaml
aggregation:
  # Existing enabled/application/window/history/policy settings are still required.
  spatial_selection:
    min_depth: 1
    max_evaluations: 4096
```

Both settings are required. `min_depth` is the coarsest allowed search depth (one through
the sensor's leaf depth). Policy bounds can be stricter; every candidate is checked again.
There is no representable depth-zero data root. An explicit uniform or regional metric
policy and bounded history are mandatory. Invalid selection settings fail in startup
preflight before database initialization.

Set `renderer.show_aggregation: true` to initially show the overlay. **G** toggles it,
**Space** pauses/resumes, and the existing left/right controls change playback speed.
The overlay also requires the sensor grids to be visible. The demo starts with the large
general info display hidden to keep the map readable; its Infos button remains available.

- Thin sensor boundaries remain visible beneath the chosen aggregation geometry.
- Green outlines identify selected footprints; labels show depth and distinct support.
- Orange outlines indicate coarsening relative to the previous selected window.
- Blue outlines indicate refinement; red footprints are internally suppressed.
- The label states the exact closed interval in milliseconds and the transition counts.

`AdaptiveGridSensorSample.aggregationDebug` is a separate immutable shared attachment. It
contains the last closed aggregation window, not instantaneous sensor occupancy. Each
renderer instance routes it by sensor ID and holds it with its explicit interval until the
next snapshot arrives. Geometry need not change for the diagnostic snapshot to update.
No renderer code reads history or participates in decisions. Snapshots contain no contributor
identities or pointers into live simulation objects. The existing bounded transport limits
in-flight snapshots. A final window closed only during shutdown is saved to diagnostics;
without a later sensor frame, it is not separately delivered to the live renderer.

## Recorded replay and MongoDB

The prepared offline demonstration opens without a server:

```sh
open /Users/maxdemu/Developer/UMP-Simulator/results/demos/spatial-inspector.html
```

Select **Finest input cells** versus **Selected aggregation cut** for the same interval.
**Next coarsening** and **Next refinement** jump to actual recorded transitions and select
an affected cell. A selected parent explains which failed child checks triggered its
assessment. A red footprint explains why it was suppressed at the search cap.

New files use schema `ump.spatial-selection.v1`, role `internal_spatial_selection`, and the
`selection-*.jsonl` filename prefix. They retain the original window/sample metadata, final
`cells` with per-cell `decision`, `source_cells` for the finest inputs, and `attempts` for
the evaluated leaves/parents. `spatial_selection` records the mode, depth cap, evaluation
count and selected/suppressed/transition counts. `counts` covers the whole internal window,
including suppressed footprints; it is not a public selected-output total.

The first verified capture is stored in `results/demos/spatial-selection.jsonl`, with its
finest baseline in `spatial-source.jsonl` and configuration in `spatial-capture-config.yaml`.
It has 75 windows, 1,329 selected cell-window records, 75 suppressed footprints, 27 coarsened
and 94 refined cells. Its run ID is `FB0BD2EE-EE52-4A07-B3DC-D404F78379AB`. The debug copy is
in `UMP_Debug_AutSys.aggregation_candidates`; filter by this run ID or the new schema.
Transition counts are counts of resulting cells, not unique people or complete sibling
operations. New randomized runs produce different counts.

To create another replay:

```sh
cd /Users/maxdemu/Developer/UMP-Simulator
python3 tools/aggregation_inspector/build_report.py \
  simulator/examples/spatial-selection/results/aggregation/selection-*.jsonl \
  --output results/demos/spatial-replay.html
```

## Verification and limits

All nine CTest suites passed, including the new standard-C++ spatial suite, extended frame
attachment tests and configuration tests. The spatial suite also passed `-Wall -Wextra
-Werror`. Cases cover merge → refine → merge, exact cross-cell unions, measured-empty bins,
replacement of passing siblings, depth/size limits, missing coverage, unavailable metrics,
evaluation-budget failure without state advancement, repeat-window rejection and a stricter
policy in an empty sibling footprint. A measured-empty following window clears the cut.

A separate full 30-second capture verified all 75 windows for non-overlap, exactly one final
owner of every observed leaf, contribution conservation and consistency between decisions
and assessments. Both coarsening and refinement occurred. Its temporary capture database
was removed after export. The production simulator configuration and reference data were
not used. Native inspection verified the live overlay, G toggle and pause/resume; Safari
inspection verified the recorded geometry and transitions. These checks establish functional
behavior, not a measured privacy benefit or general real-time performance guarantee.

Next: A05 public-release coordination, then temporal extension and policy-selected strategy
comparison. Automatic prewarming, committed-output invalidation, hysteresis, selective
suppression fallback and the separate MongoDB AGBS renderer remain open. The private spatial
baseline is the spatial branch of Temporal First; a full Temporal First implementation also
needs the remaining legal temporal fallback. Spatial First is not implemented here.
