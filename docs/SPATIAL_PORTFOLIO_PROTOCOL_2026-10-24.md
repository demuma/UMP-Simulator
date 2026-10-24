# Fixed 5/10/20 m and adaptive comparison protocol

## Purpose and current scope

This optional protocol compares actual C++ aggregation executions on a frozen, completed mapped sensor observation stream. It adds the requested fixed 20 m schedules at 400 ms and 1000 ms. The original six-case method matrix, ten-case support-policy matrix and separate four-case maximum-window sensitivity remain unchanged.

The protocol is declared before execution, including all configurations, the query bank and a local executable copy. Successful orchestration writes a verified summary only after every case and independent audit succeeds. Failed runs retain their predeclared protocol and diagnostics without producing a verified summary.

These experiments measure policy compliance, retained information, output detail, release latency and runtime. They do not measure a privacy gain or establish a population-level advantage from a single deterministic scene.

## Two explicitly different spatial contracts

The original mapped Policy Tree permits output cells up to 10 m, with some regions imposing 5 m. Fixed 20 m output cannot satisfy that contract. Its two original-policy executions are deliberate negative controls: zero output demonstrates rejection, not useful privacy-preserving coverage.

The separate `spatial20` contract changes every existing `cell_side_m.max` at the root, regional type and regional instance scopes to 20 m. A region without its own maximum inherits the root. This change applies equally to both adaptive strategies and every fixed baseline. All lower bounds, support constraints, semantic bounds, temporal bounds, region geometry and taxonomy remain. The exact scope, previous value and new value of every spatial change are recorded in `protocol.json`.

Compare methods within one contract. Between-contract differences reflect a changed spatial utility requirement. Relaxing a spatial bound does not demonstrate improved privacy.

For both contracts, the candidate-search minimum depth permits 20 m cells: depth 2 for the 80 m root. This is a common search setting, separate from hard policy bounds. The original policy still rejects its 20 m candidates. Fine data remain at depth 6, or 1.25 m. Without this shared search change, a depth-3 adaptive selector could never use a newly permitted 20 m cell.

Selective contribution suppression is disabled at the root for every case. The earlier suppression-on/off study remains separate; doubling this matrix would confound the initial spatial comparison and increase its cost.

## Predeclared 16-case matrix per source

Each contract receives these eight methods, using the same observations and observation clock:

| Method | Uniform cell side | Fixed interval | Release rule |
| --- | ---: | ---: | --- |
| Adaptive Semantic First | Variable | Policy-bounded | Publish when policy is satisfied |
| Adaptive Spatial First | Variable | Policy-bounded | Publish when policy is satisfied |
| Fixed grid | 5 m | 400 ms | Fixed complete interval; policy-valid cells only |
| Fixed grid | 5 m | 1000 ms | Fixed complete interval; policy-valid cells only |
| Fixed grid | 10 m | 400 ms | Fixed complete interval; policy-valid cells only |
| Fixed grid | 10 m | 1000 ms | Fixed complete interval; policy-valid cells only |
| Fixed grid | 20 m | 400 ms | Fixed complete interval; policy-valid cells only |
| Fixed grid | 20 m | 1000 ms | Fixed complete interval; policy-valid cells only |

In the project's convention, a `First` priority names the information dimension to preserve. Spatial First therefore tries temporal accumulation before sacrificing spatial detail. Semantic First preserves semantic detail according to its configured secondary strategy. Both have the same hard policy and access to the configured maximum temporal window, currently up to 4 s where regional constraints allow it. The fixed portfolio contains only 0.4/1 s schedules; it does not isolate the effect of adaptation from access to longer temporal windows or claim to contain the optimal uniform schedule.

Each case has a separate application ID and Policy Tree ID. Inherited hard bounds are otherwise shared within its contract. Geometry resolves exact depths from the source coverage; an unrepresentable requested side is rejected before execution.

## Source and comparison gates

A new spatial portfolio requires:

- A verified native mapped recording with all required artifact digests intact.
- `all_scheduled_episodes_completed: true`, with zero pending/active episodes when those counts are present.
- A complete `ump.source-sensor-episode-observability.v1` proof: `status: pass`, equal scheduled and observed track counts, and zero missing or unexpected tracks.
- A sensor sampling period divisible by the native whole-millisecond progress step.
- The strict original root maximum below 20 m, so the negative controls have their declared meaning.

The executable, all per-case policy files, the copied observation stream, capture proof and query bank are copied or written and hashed before the first native case. Their frozen copies are checked before and after each case. All methods consume the copied observation stream without regenerating motion. The native binary and original observation digest are also checked during execution.

The planned source pair is one corrected mixed 128-person scene and one genuinely regenerated pedestrians-only 128-person scene using the matched map, seed, horizon and source settings wherever applicable. The pedestrian scene must run as a separate simulation; deleting rider observations from the mixed recording would preserve their collision effects and would not be a genuine pedestrian-only simulation. Comparisons are paired within each source. Different source compositions can change motion interactions and simultaneous density, so report their realized observation counts, episode counts, peak observed tracks and type mix separately. A matched seed does not make the two observation streams identical.

No substantive comparison should start before the map-label, entrance-routing and source-completion corrections pass their acceptance gates.

## Common recipient queries and loss accounting

All methods answer the same 10 m spatial targets and 1 s temporal queries at lags of 0 and 1 s. Categories are the taxonomy root plus its immediate families; exact subtype preservation is separately measured against the full input. With 64 targets and four categories, a 300 s source produces 153,600 queries per case, below the 200,000-query guard.

Exact query support and separately scored uniform spatial/temporal estimates remain distinct. An absent output is never imputed as zero. Positive-reference and known-zero queries are reported separately. Coarser 20 m output can improve retention while weakening exact 10 m query support; this trade-off must remain visible.

Report, at minimum:

- Retained observation contributions divided by all input contributions, including per-type and per-region denominators.
- Exact semantic subtype contributions divided by all input contributions.
- Observation-weighted semantic loss and output cell side, both conditional on retained data.
- Observation-to-seal mean and p95 delay, plus interval duration.
- Full-input semantic distortion: `D = (N_in - N_retained + sum_b n_b * loss_b) / N_in`. Omitted contributions have unit cost; this is an explicitly defined utility score, not a privacy metric.
- Published cell-window counts and operational distinct-track/category support.
- Native core and process timings, with complete pipeline audit/query time separately labeled.
- Independent policy/ownership audit results. Zero violations with zero output is vacuous compliance.

## Offline validation capacity and the preserved initial failure

The first mixed-source portfolio stopped after its eight original-contract cases. Its first Spatial20 native result was produced successfully, but the independent offline oracle rejected its size before validating it: 473,197 private retirements plus 984 public releases exceed the previous 200,000-record guard. Only 13,567 diagnostic/public cells were present; empty retirements account for most of the difference. That failed portfolio is preserved unchanged and is not presented as a completed 16-case result.

The new portfolio explicitly predeclares `offline_audit_max_cells: 1000000`. `--audit-max-cells` may set an exact integer between 1 and 1,000,000; this bounds both the combined window/release count and the checked cell count. It changes offline validator capacity only. Every geometry, source-count, coverage, policy, selected-release, non-overlap and complete-retirement check still executes. Legacy calls retain their previous 100,000-record ordinary or 200,000-record selective-suppression defaults unless an explicit override is supplied. A complete fresh portfolio is rerun after the capacity correction, preserving failed native outputs and timing artifacts separately.

A targeted regression constructs 200,004 genuine empty space-time retirements. The legacy bound rejects them; an explicitly sufficient bound validates the entire support; a deliberately corrupted final retirement beyond the old limit still fails the independent checks. Invalid, fractional, Boolean or over-limit capacities fail before execution.

## Measured response curves, not fitted regression

`plot_spatial_portfolio.py` connects the actual fixed 5/10/20 m measurements separately for the 400 ms and 1000 ms schedules. Each contract has a separate figure. Horizontal adaptive references show the aggregate metric under that same contract; they do not imply uniform adaptive cell sizes.

The three fixed resolutions are discrete quadtree choices. Connecting them is a visual guide, not evidence for a regression model, significance, a continuous interpolation function or an intermediate attainable cell size. Missing conditional metrics remain `n/a`; actual zero retention remains zero. More density seeds or independently generated scenarios would be needed for a statistical response model.

## Invocation

```sh
python tools/mapped_scene/run_comparison.py \
  --recording results/NEW_CORRECTED_SOURCE/replay \
  --output results/NEW_SOURCE-spatial-portfolio \
  --spatial-portfolio --native-wall-budget-s 900

python tools/mapped_scene/plot_spatial_portfolio.py \
  --summary results/NEW_SOURCE-spatial-portfolio/summary.json \
  --output results/NEW_SOURCE-spatial-portfolio/figures
```

`--spatial-profiles original` or `--spatial-profiles spatial20` selects a predeclared eight-case subset for a bounded check. The full main study uses both. Output directories must be fresh. Raw observations, private diagnostics, executables and replays stay local under ignored `results/`; only compact summaries, figures and reports are candidates for Git.
