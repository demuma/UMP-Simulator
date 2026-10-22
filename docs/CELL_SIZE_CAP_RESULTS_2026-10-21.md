# Maximum output-cell caps: results and verification

Date: 2026-10-21. This follow-up implements the confirmed maximum output-cell sizes of 10 x 10 m and 5 x 5 m. The 80 x 80 m source area, 1.25 m finest cells, identities, movement, sampling, type distribution, support threshold and time limits are unchanged. The earlier 40 m experiment remains an immutable reference.

## Execution and acceptance

- Six new comparison bundles: two caps x three previously captured sources; nine methods each, giving **54 independently scalar/semantic-audited outputs plus six deterministic repeats**. No new simulator run or MongoDB access.
- Hard Policy Tree `cell_side_m.max` is 10 or 5, accompanied by `spatial_selection.min_depth` 3 or 4. Each changed policy has its own ID. Every released and final diagnostic footprint was checked against the cap. Finest observation depth remains 6.
- Six valid fixed grid/window controls accompany each cap: 2.5/5/10 m at the 10 m cap; 1.25/2.5/5 m at the 5 m cap; each crossed with 400/1000 ms. Their allowed semantic selector is the same as for TF/SF/Semantic First.
- **7/7 focused CTest entries passed** in 5.46 s. The new cap test contains five Python methods and **81 actual C++ replay executions**, including cases where only a forbidden 10 m or 20 m parent would pass. The 14-method moving runner tests, native selector/controller/replay checks and viewer tests also pass in that focused run. This is not a claim that all 56 now-registered CTest entries were rerun.
- An independent review checked 432 new artifact hashes, all 269 old-pilot artifacts unchanged, 46,841 public and 463,845 diagnostic cell bounds, all six repeats, and 18 overlapping fixed-baseline pairs (matching after removal of policy/release identifiers). Source pairing, protocol and every result audit passed. Nine individual and three cross-cap viewer bundles validate. See per-run manifest.json and audit.json. The frozen protocol is [here](CELL_SIZE_CAP_PROTOCOL_2026-10-21.md).

## Main policy sensitivity: Spatial First

The query remains mean sampled occupancy on fixed **10 m squares / 1 s intervals**. Coverage is eventual answerability from recipient releases, with uniform allocation assumptions. Retention counts observation contributions, not unique people or preservation of every attribute. Conditional MAE is unavailable when no query can be answered.

| Initial Road Users | Maximum output side (m) | Retained observations (%) | Answered occupancy queries (%) | Conditional MAE (Road Users) | Weighted mean side (m) |
|---:|---:|---:|---:|---:|---:|
| 200 | 40 | 100.00 | 100.00 | 1.419 | 24.21 |
| 200 | 10 | 57.31 | 28.91 | 0.000 | 10.00 |
| 200 | 5 | 4.95 | 0.00 | unavailable | 5.00 |
| 500 | 40 | 100.00 | 99.61 | 1.120 | 13.54 |
| 500 | 10 | 93.91 | 80.78 | 0.000 | 9.97 |
| 500 | 5 | 28.31 | 0.00 | unavailable | 5.00 |
| 1000 | 40 | 100.00 | 99.22 | 0.123 | 9.54 |
| 1000 | 10 | 99.85 | 98.36 | 0.000 | 9.34 |
| 1000 | 5 | 65.48 | 7.81 | 0.000 | 5.00 |

At 500 initial Road Users, the cap change 40 -> 10 -> 5 m lowers retained observations from 100% to 93.91% to 28.31%. The finer output requirement removes the larger spatial rescues while keeping minimum category support 5 and the maximum 1000 ms window. Semantic generalization cannot manufacture additional distinct Road Users. These are measured outcomes of this policy/source combination, not proof of general mathematical infeasibility across other mechanisms.

Under the 5 m cap, the 200- and 500-user sources answer no complete 10 m occupancy query, although some observations are retained. A 10 m query requires its entire sampled space-time footprint to be supported by the released 5 m or smaller cells. Released isolated tiles do not fill gaps; suppressed and unreported support remain unknown, including physically empty support without an explicit public zero. Consequently conditional MAE is unavailable, not zero.

Stricter geometry is an application detail constraint. It does not automatically strengthen measured privacy: all cap variants retain the same operational support rule, and category generalization often becomes coarser. The original root-policy pilot and this follow-up include no new empirical privacy evaluation.

## All adaptive strategies

| Initial N | Cap (m) | Strategy | Retained (%) | Mean side (m) | Mean semantic loss | Mean interval-start age (ms) |
|---:|---:|---|---:|---:|---:|---:|
| 200 | 40 | temporal_first | 100.00 | 24.938 | 0.800 | 400.0 |
| 200 | 40 | spatial_first | 100.00 | 24.211 | 0.819 | 1000.0 |
| 200 | 40 | semantic_first | 100.00 | 30.898 | 0.612 | 1000.0 |
| 200 | 10 | temporal_first | 57.31 | 10.000 | 0.979 | 1000.0 |
| 200 | 10 | spatial_first | 57.31 | 10.000 | 0.979 | 1000.0 |
| 200 | 10 | semantic_first | 57.31 | 10.000 | 0.979 | 1000.0 |
| 200 | 5 | temporal_first | 4.95 | 5.000 | 1.000 | 1000.0 |
| 200 | 5 | spatial_first | 4.95 | 5.000 | 1.000 | 1000.0 |
| 200 | 5 | semantic_first | 4.95 | 5.000 | 1.000 | 1000.0 |
| 500 | 40 | temporal_first | 100.00 | 13.854 | 0.828 | 400.0 |
| 500 | 40 | spatial_first | 100.00 | 13.535 | 0.835 | 1000.0 |
| 500 | 40 | semantic_first | 100.00 | 31.774 | 0.188 | 1000.0 |
| 500 | 10 | temporal_first | 93.91 | 9.966 | 0.975 | 1000.0 |
| 500 | 10 | spatial_first | 93.91 | 9.966 | 0.975 | 1000.0 |
| 500 | 10 | semantic_first | 93.91 | 9.966 | 0.975 | 1000.0 |
| 500 | 5 | temporal_first | 28.31 | 5.000 | 0.963 | 1000.0 |
| 500 | 5 | spatial_first | 28.31 | 5.000 | 0.963 | 1000.0 |
| 500 | 5 | semantic_first | 28.31 | 5.000 | 0.963 | 1000.0 |
| 1000 | 40 | temporal_first | 100.00 | 9.741 | 0.912 | 400.0 |
| 1000 | 40 | spatial_first | 100.00 | 9.536 | 0.911 | 1000.0 |
| 1000 | 40 | semantic_first | 100.00 | 40.000 | 0.000 | 400.0 |
| 1000 | 10 | temporal_first | 99.84 | 9.458 | 0.925 | 607.9 |
| 1000 | 10 | spatial_first | 99.85 | 9.344 | 0.922 | 1000.0 |
| 1000 | 10 | semantic_first | 99.85 | 9.344 | 0.922 | 1000.0 |
| 1000 | 5 | temporal_first | 65.48 | 4.999 | 0.978 | 1000.0 |
| 1000 | 5 | spatial_first | 65.48 | 4.999 | 0.978 | 1000.0 |
| 1000 | 5 | semantic_first | 65.48 | 4.999 | 0.978 | 1000.0 |

The tight caps make many strategy outcomes coincide because spatial and temporal limits leave few admissible choices. At N=1000/cap10, TF retains 99.8399% versus 99.8510% for SF/Semantic First; do not round this into exact equality or conclude that priority never matters. Full per-method fixed/adaptive statistics are in the individual summary.json files. Fixed portfolios differ across caps; directly pair only overlapping settings and the three adaptive strategies.

At N=1000/cap10, fixed 10 m/1000 ms and Spatial First retain the same 99.851% of observations, but eventual query coverage is 99.1406% versus 98.3594%. Adaptive finer cells can leave parts of a 10 m query unsupported even when all actual observed contributions within that parent are retained. Sparse releases do not certify the absent subcells as public zeros. This is a limitation of the current release/query contract, and a further reason to measure coverage separately from retention.

## Replays and reproduction

Run `tools/evaluation/run_moving_comparison.py` with `--max-cell-side-m 10` or `5`, a verified existing capture, and a new output directory. The default remains 40 and retains its original policy/matrix. See [commands](CELL_SIZE_CAPS.md). The ordinary simulator config and earlier result files were not changed.

Cross-cap bundles `results/cell-size-caps-2026-10-21/viewer-n200`, `viewer-n500`, and `viewer-n1000` contain the actual TF/SF/Semantic First outputs at 40/10/5 m on one identical source. Start `python3 -B tools/replay_viewer/serve.py --bundle results/cell-size-caps-2026-10-21/viewer-n500 --port 8768`; browse http://127.0.0.1:8768/. The first two choices directly compare the 10 m and 5 m caps with Temporal First. Each original per-cap bundle still includes its fixed controls.

Snapshots show whole historical releases only after sealing, with their original window/age. A separate private finalized-diagnostics overlay shows suppression and recorded bounds. No actual motion, release interval or intermediate merge animation is invented. The viewer does not expose every pending private proposal.

## Presentation interpretation

Use at most one cap contrast in the 20-minute story: the requested 5 m detail is technically enforceable, but can sacrifice most retained data and all answerability for the fixed task under the present support/time limits. Start with availability and suppression, then discuss error/detail and feasibility. Do not present a lower conditional error on a smaller surviving subset as an overall improvement.

There is still one stochastic realization per population, uniform initialization, a 20 s horizon, common windows and no regional overrides. Eventual occupancy uses 1280 queries; deadline primary uses 1152 fixed interior queries with 128 boundary queries separate. Independent sessions, heterogeneous flows/policies and class-query utility remain subsequent experiments. No new privacy guarantee, real-time latency claim or globally optimal action selection is established.

Browser QA: the N=500 cross-cap view was opened at4s; both 1s release windows,
10m/5m maximum footprints, private constraint bounds and suppressed diagnostics
were visibly checked. Screenshot: [paired cap replay](figures/cell-caps-500-at4s-2026-10-21.jpg).
Scientific plot: [cap trade-offs](../results/cell-size-caps-2026-10-21/cell-cap-tradeoffs.png).
