# Support-only Policy Tree sensitivity protocol

Date: 2026-10-24. Implementation: `tools/mapped_scene/run_comparison.py --policy-comparison`. This extends the existing mapped comparison; the default six-case method comparison remains available and its policy is unchanged.

## Question and comparison boundary

On one validated recorded observation stream, what changes when the operational minimum distinct-track support is relaxed, while all spatial, temporal and semantic bounds remain fixed? Within each of those two Policy Trees, how do the adaptive controller and the declared fixed portfolio compare?

This is a policy-sensitivity experiment, not a privacy-improvement result. The relaxed tree makes a weaker support demand. Any additional coverage or detail cannot be interpreted as stronger privacy. A policy-adherence result likewise does not establish classical trajectory k-anonymity or attack resistance.

The source is generated and validated before comparison. Every case consumes the exact same `observations.json`, identified by SHA-256, and the same compiled replay binary. The runner verifies the complete recording digest set and validates its replay bundle before creating an output directory. It refuses an existing output directory. The recorded native output remains independent evidence and is never replaced.

## Two explicit Policy Trees

The original tree is adapted from the captured native configuration, preserving selected Region definitions, Region-type and Region-instance requirements, taxonomy and execution settings. The second tree has the same version and an explicit `-support60` ID suffix. For each declared minimum on either `distinct_contributors` or `min_category_distinct_contributors`, at the root and at every selected Region type/instance, apply

\[
q_{60}=\left\lceil\frac{3q}{5}\right\rceil.
\]

For example, a support floor of 5 becomes 3; the entrance floor of 10 becomes 6. Integer arithmetic defines the rounding. Zero stays zero and a positive integer stays at least one. Every changed scope, metric, original value and new value is recorded in the protocol before any replay result exists. A noninteger, negative or nonfinite support floor is rejected; a tree without a relaxable support floor is rejected.

Only those support minima and the tree ID change. Spatial footprint limits, minimum/maximum window duration, age limits, semantic ceilings/costs, temporal coordination, controller bounds, selected Region rectangles, semantic taxonomy and source observations remain equal. In particular, relaxing a root floor alone would leave a stronger local floor in force; the protocol therefore explicitly transforms both type and instance support floors too. Strongest-bound composition still applies at every released footprint: effective minima are maxima and effective maxima are minima over all intersected policies.

## Predeclared method portfolio

Each Policy Tree runs all five methods below, for ten actual replay executions:

| Method | Spatial setting | Temporal setting | Semantic handling |
| --- | --- | --- | --- |
| Adaptive immediate | Online quadtree selection | Independent local windows, captured bounds | Captured Semantic First and secondary preference; release when policy passes |
| Fixed 5 m / 400 ms | Depth 4 | Common 400-ms windows | Same truthful-cut support evaluator and taxonomy |
| Fixed 5 m / 1000 ms | Depth 4 | Common 1000-ms windows | Same truthful-cut support evaluator and taxonomy |
| Fixed 10 m / 400 ms | Depth 3 | Common 400-ms windows | Same truthful-cut support evaluator and taxonomy |
| Fixed 10 m / 1000 ms | Depth 3 | Common 1000-ms windows | Same truthful-cut support evaluator and taxonomy |

The named sides assume the current 80-m observation square. This fixed portfolio is deliberately bounded; it is not the best possible uniform grid/window. Illegal regional candidates remain suppressed rather than having their hard bounds silently changed. A fixed grid already performs spatial aggregation; it is not an unprotected raw baseline. The intentional semantic-wait variant remains in the historical default method matrix but is excluded from this support-sensitivity matrix so a second release rule does not obscure the support factor.

Semantic First retains the established project meaning: preserve semantic detail. The secondary preference is read from the recording. There are no hardcoded pedestrian-only source labels or output nodes; the captured catalog defines pedestrian, cyclist, scooter and future families.

## Independent checks and reported quantities

Every actual release undergoes the existing independent scalar/retirement audit plus a raw-source audit of geometry, identity unions, semantic antichains and effective regional requirements. Failed execution or audit aborts the verified summary. Zero policy violations with zero published cells is vacuous compliance and is displayed with zero retained coverage.

The compact summary/report includes:

- Observation retention and unpublished contributions against the entire input denominator, exact subtype contributions against the entire input, published category and spatial-size histograms, and released cell-window/unique-cell counts.
- Operational support profiles: distinct observed tracks per published cell-window (minimum, unweighted nearest-rank p50, observation-weighted mean) and distinct tracks per published semantic category bin (minimum, unweighted nearest-rank p50, category-observation-weighted mean). All are null for no published output. These describe the active protection constraints; they are not measured attack risk, a privacy gain or a trajectory k-anonymity guarantee.
- Observation-weighted semantic loss, cell side and source-interval duration, together with source-window-start age. These detail/age means condition on retained contributions.
- Actual observation-to-seal delay, computed from each matched source sample timestamp: mean, nearest-rank p50/p95/p99 and maximum. This differs from the age of the beginning of the aggregated interval.
- Retention by original source type, so rare cyclists or scooters cannot disappear from the evaluation denominator after semantic generalization.
- Retention by actual source-point Region membership, using half-open rectangles. Overlapping Region rows are nonexclusive and must not be summed; an outside-selected-regions row is also included. This descriptive accounting differs from conservative policy resolution, which includes every positive-area intersection of the entire published cell, including empty subareas.
- Source horizon and sampling period, peak simultaneously observed tracks, and available recorded lifecycle counts. A completed recording horizon can still contain pending/active episodes; finite-cohort drainage is a separate source test.
- Replay core processing time, native process wall time, and full comparison-pipeline wall time with their distinct scopes. The latter includes Python audits and query evaluation. None is a measured per-step live deadline guarantee.

Contribution accounting independently finds the published ancestor and half-open release interval of each source observation using quadtree bit shifts. It rejects duplicate cell intervals, overlapping ancestor/descendant publication of the same contribution, and disagreement between matched and declared released counts. Track IDs remain local and are never included in compact summaries.

## Recipient task and errors

The policy-sensitivity matrix predeclares the same 64 depth-3 cells, 1000-ms queries and lags 0/1000 ms for every case. Queries cover the captured taxonomy root and its immediate children, so total/family occupancy can be compared on longer mixed-mode recordings within the existing 200,000-query budget. Fine-label preservation is reported separately through subtype retention and semantic loss. The default method matrix still queries every declared catalog node.

Use the existing conservative exact decoder and separately scored uniform spatial/temporal estimates. Estimates never invent a missing semantic partition or replace unpublished support with zero. Query coverage and conditional occupancy error are shown together, with positive-reference queries distinguished from known-zero queries and source-boundary windows separated from interior windows. The query bank is written before executing the first case and remains identical even if all methods suppress their output.

## Run and artifacts

Run from the repository root after the new source capture is frozen:

```sh
PYTHONDONTWRITEBYTECODE=1 /private/tmp/ump-osm-moenckeberg-2026-10-23/venv/bin/python \
  tools/mapped_scene/run_comparison.py \
  --recording results/NEW-SCENE/replay \
  --output results/NEW-SCENE-policy-comparison \
  --policy-comparison
```

Use a fresh output path. Each native process has a predeclared 240-second wall budget by default. For longer captures, `--native-wall-budget-s 900` may be selected before execution; the permitted integer range is 1–3600 seconds. The budget is recorded in `protocol.json` and only limits execution, without changing observations, queries, policies or controller settings. `protocol.json`, `summary.json` and `report.md` are compact aggregate evidence suitable for a deliberately selected repository evidence package. The complete output also contains local observation copies, actual per-case results, configs, logs, private audits and a directly viewable replay bundle. It remains under ignored `results/`. Do not add that directory to Git.

The replay labels, tree IDs/versions and root/Region overlays are rebuilt from each actual executed config. The relaxed tree is therefore visibly distinct from the original; copied native-policy overlays cannot silently label it with the old thresholds. The first two viewer panels show `original_adaptive_immediate` and `support60_adaptive_immediate`, comparing the same controller under the two policies. This presentation order does not change the predeclared execution matrix. Every panel is explicitly described as an offline execution of causal online decisions on identical recorded observations.

## Tool validation at implementation

`test_run_comparison.py` has 27 passing checks with the compiled `AggregationReplay` enabled. The new checks cover all-scope support relaxation with every other config value preserved, captured mixed taxonomy and actual replay metadata, predeclared identical query banks even under total suppression, per-type/nonexclusive Region accounting, timestamp-based delay quantiles, cell/category support union distinctions and weighting/median definitions including empty output, duplicate contribution rejection, and an actual C++ example with three observed users: all original support-5 methods suppress, all relaxed support-3 methods publish, and every output independently passes its own policy audit. This fixture proves the comparison plumbing and a mechanism distinction; it is not evidence that the mapped adaptive controller outperforms its fixed baselines.

## Aggregate-only scientific figure

After comparison, create a fresh local figure directory:

```sh
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/private/tmp/ump-policy-plot-matplotlib \
  /private/tmp/ump-osm-moenckeberg-2026-10-23/venv/bin/python \
  tools/mapped_scene/plot_policy_comparison.py \
  --summary results/NEW-SCENE-policy-comparison/summary.json \
  --output results/NEW-SCENE-policy-comparison/figures
```

The helper opens only the compact verified summary. It emits a 2 × 2 paired original/relaxed comparison of retained input fraction (%), observation-weighted semantic loss of retained data (%), mean output cell side (m) and actual observation-to-seal p95 delay (s). It writes PNG, editable-text SVG and aggregate metric provenance including the summary digest. Missing metrics have no bar and are explicitly marked `n/a`; genuine zero metrics keep a zero label. All original/relaxed bars remain adjacent for the same five methods. The caption explicitly states that changing support changes the protection contract and does not measure privacy gain.

The three small `test_plot_policy_comparison.py` checks cover unit conversion/missing values, rejection of nonfinite/invalid metrics or incomplete/unaudited experiments, and real PNG/SVG rendering with `n/a` plus refusal to overwrite an existing figure directory. Matplotlib is already part of the isolated mapped-scene requirements; the helper introduces no network calls or raw-source dependency.

## Separately classified post-hoc maximum-window check

The main adaptive controller can use windows up to 4000 ms while the original predeclared fixed portfolio contains only 400/1000-ms settings. A retention advantage over that subset cannot isolate adaptation from access to longer permitted windows. After seeing the ten-case results, a separately labeled sensitivity checks fixed 5/10-m grids at 4000 ms under both trees:

```sh
python tools/mapped_scene/run_comparison.py \
  --recording results/urban-traffic-2026-10-24-256/replay \
  --output results/urban-traffic-2026-10-24-256-max-window-sensitivity \
  --max-window-sensitivity --native-wall-budget-s 900
```

The new four-case protocol is classified `post_hoc_fixed_max_window_sensitivity`, with analysis status `post_hoc_sensitivity_after_ten_case_results`. It uses identical frozen observations, the same family query bank and unchanged policy bounds. A 4000-ms candidate cannot satisfy the local 1000-ms duration/age ceiling and must remain suppressed there. The original ten-case result, manifest and protocol stay untouched. Do not combine these four exploratory cases into an allegedly predeclared fourteen-case study, claim an exhaustive fixed optimum, or remove any fixed-reference win. A regression verifies four actual 4000-ms commands under the two support contracts and rejects combining both study selectors.
