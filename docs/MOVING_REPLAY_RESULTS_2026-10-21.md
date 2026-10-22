# Recorded moving-data pilot: results

Date: 2026-10-21. Protocol was frozen before capture. Source: the existing C++ Simulator; no replacement movement generator. Three independent stochastic sessions, nine methods per session, plus one deterministic replay repeat per session. These are mechanism-pilot findings, not population-level confidence intervals or measured privacy gains.

## Source and shared conditions

| Requested initial Road Users | Last sampled Road Users | Sampled identities showing displacement | Observation contributions |
|---:|---:|---:|---:|
|200|189|192|38930|
|500|495|405|99140|
|1000|988|658|198638|

Each source has199 sensor samples over20 simulated seconds,80x80m,D6,100ms sensor cadence,50ms numerical step, and the seven maintained type profiles. Actual initial counts match requested totals at these three sizes. Sources differ across populations; only within-source method contrasts are paired. No replenishment is implemented. Collision handling and real-time-dependent motion noise are unchanged; this is not a map-realistic flow benchmark.

All methods use the identical root policy: minimum5distinctRoadUsers per published semantic bin, cellside1.25..40m, maximum1000ms window/interval-start age, maximum semanticloss1. Fixed modes use the same semantic selector as adaptive modes. The rooted seven-profile taxonomy/loss scale is declared in policy.json. No regional overrides are introduced in this initial controlled pilot.

## Every measured method

Retention counts observation contributions, not preservation of all spatial, temporal or class details. Side/loss/age are contribution weighted. Query task is10m squares x1s mean sampled total occupancy. MAE is conditional on fully answered queries and must be read with coverage.

| Initial N | Method | Retained (%) | Mean side (m) | Mean semantic loss | Mean interval-start age (ms) | Eventual query coverage (%) | Conditional MAE |
|---:|---|---:|---:|---:|---:|---:|---:|
|200|fixed_10m_1000ms|57.31|10.00|0.979|1000|28.91|0.000|
|200|fixed_10m_400ms|53.21|10.00|0.980|400|22.11|0.020|
|200|fixed_20m_1000ms|97.84|20.00|0.822|1000|92.19|1.301|
|200|fixed_20m_400ms|97.54|20.00|0.823|400|89.69|1.320|
|200|fixed_40m_1000ms|100.00|40.00|0.402|1000|100.00|1.849|
|200|fixed_40m_400ms|100.00|40.00|0.408|400|100.00|1.849|
|200|semantic_first|100.00|30.90|0.612|1000|100.00|1.558|
|200|spatial_first|100.00|24.21|0.819|1000|100.00|1.419|
|200|temporal_first|100.00|24.94|0.800|400|100.00|1.445|
|500|fixed_10m_1000ms|93.91|10.00|0.975|1000|81.17|0.000|
|500|fixed_10m_400ms|92.82|10.00|0.974|400|76.88|0.025|
|500|fixed_20m_1000ms|100.00|20.00|0.468|1000|100.00|2.082|
|500|fixed_20m_400ms|100.00|20.00|0.476|400|100.00|2.082|
|500|fixed_40m_1000ms|100.00|40.00|0.039|1000|100.00|3.285|
|500|fixed_40m_400ms|100.00|40.00|0.039|400|100.00|3.285|
|500|semantic_first|100.00|31.77|0.188|1000|100.00|2.637|
|500|spatial_first|100.00|13.54|0.835|1000|99.61|1.120|
|500|temporal_first|100.00|13.85|0.828|400|99.38|1.212|
|1000|fixed_10m_1000ms|99.85|10.00|0.911|1000|99.14|0.000|
|1000|fixed_10m_400ms|99.83|10.00|0.914|400|98.98|0.033|
|1000|fixed_20m_1000ms|100.00|20.00|0.210|1000|100.00|3.197|
|1000|fixed_20m_400ms|100.00|20.00|0.220|400|100.00|3.197|
|1000|fixed_40m_1000ms|100.00|40.00|0.000|1000|100.00|4.553|
|1000|fixed_40m_400ms|100.00|40.00|0.000|400|100.00|4.553|
|1000|semantic_first|100.00|40.00|0.000|400|100.00|4.553|
|1000|spatial_first|100.00|9.54|0.911|1000|99.22|0.123|
|1000|temporal_first|100.00|9.74|0.912|400|98.91|0.158|

## Findings supported by this pilot

1. All 27outputs satisfy the checked scalar/semantic constraints. Every adaptive mode retained all source observation contributions in these three sources. Fine fixed settings can suppress observations; coarse fixed settings can also retain everything. Thus full retention alone is not evidence of adaptive superiority.
2. At initialN=200, Spatial First and fixed 40 m/1000ms both answer100% of this fixed workload and retain100% of observations. Spatial First has conditionalMAE1.419 versus1.849 and weightedcellside24.21m versus40m, while declaredmeansemanticloss is higher(.819 versus.402). This is a measured occupancy/spatial benefit with a semantic cost, not dominance across all metrics.
3. At initialN=500, Spatial First produces a mean13.54m side versus fixed20m, and lower conditionalMAE(1.120 versus2.082), while querycoverage is99.61%versus100%and meansemanticloss.835 versus.468. The scored cohorts differ slightly, so do not interpret conditionalMAE alone as a matched-query improvement.
4. At initialN=1000, Semantic First selects40m exactcategory output with zero declared semantic loss. Fixed40m also achieves that output quality. Density enables feasibility; it does not guarantee a unique adaptive advantage.
5. Temporal First retains 400 ms windows here; Spatial First takes 1000 ms. Semantic First takes 1000 ms at N=200/500, but releases at 400 ms at N=1000 once zero-loss output is available. Logical age and fixed-query deadline availability must both be shown. The1squery workload is not aligned with every400msrelease boundary: full-query availability can require the next release even when individual releases are younger. Do not call this artifact measured network latency.

Eventual query results use 1280 queries (64 cells x 20 intervals). The deadline primary cohort uses 1152 queries over [0,18 s), with the final 128 boundary queries separate. Compare methods within the same cohort.

## Interpretation limits

- Occupancy estimates allocate a published count uniformly in space and hold occupancy constant across its published window. They are estimates, not recovered trajectories. Suppressed/absent support stays unknown and is never filled withGT.
- This total-occupancy query does not measure cyclist/pedestrian class-query utility. Semantic loss is a declared scale0/.5/1, not a measured privacy gain. The earlier tiny semantic study uses a different exact-count workload and must be presented separately.
- All 27runs share operational constraints, not a demonstrated common privacy level. No namedk-anonymity claim without aQI/equivalence-class contract, no new attack result, and noepsilon equivalence are established.
- One realization perN, uniform initial distribution, seven type profiles,20s, common windows and uniform policy only. Longer runs, regional heterogeneity, identity turnover and independent replication are subsequent experiments.
- Six fixed settings form a declared limited comparison set, not an exhaustive best-fixed frontier. No global optimization claim.

## Inspect and reproduce

The result directories are `results/moving-replay-2026-10-21/n{200,500,1000}/comparison`. Each contains observations, policy, frozen replay binary, exact commands, input/protocol/result hashes, independent audits, deterministic repeat, query tables and bundle.json. The runner archives validation sources; run orchestration from a repository checkout with the documented docs/layout, not directly from the sources archive. The initial200run preceded archive-at-start and stricter audit schema checks; its exactoriginalrunner is archived and every output was subsequently reaudited using the final validator, recorded in verification-final.json.

Run the viewer with `python3 -B tools/replay_viewer/serve.py --bundle results/moving-replay-2026-10-21/n500/comparison --port8765`; browse http://127.0.0.1:8765/. Choose fixed10m400ms vsSemanticFirst at4s for the spatial/semantic trade-off; choose fixed20m1000ms vsSpatialFirst for spatial/occupancy contrast. The viewer shows final decisions, not every private intermediate proposal.

Figures: [occupancy trade-offs](../results/moving-replay-2026-10-21/occupancy-tradeoffs.png), [spatial/semantic trade-offs](../results/moving-replay-2026-10-21/resolution-semantics.png).
