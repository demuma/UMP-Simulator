# Urban traffic extension — staged acceptance contract

The requested order is movement correctness, a frozen source, profiling/optimization,
and then a policy sensitivity comparison on the same observations. All new source
settings are explicit scenario assumptions, not calibrated Hamburg traffic data.

1. Keep the existing pedestrian controls reproducible. Add opt-in dense urban traffic:
   pedestrian extra clearance 0.05 m instead of 0.10 m, without shrinking body radii;
   preferred and distributed road crossings; cyclists and E-scooter riders on the
   yellow carriageway. Separate route movement spaces must constrain guide shortcuts,
   local steering and replanning, not merely initial route generation.
2. Replace exclusive building admission with an optional bounded same-direction
   pipeline. Opposing flows wait until the occupied throat clears. Keep the default
   one-owner behavior as the historical control. Crossing width and shared occupancy
   are separate from interpersonal clearance.
3. Measure actual simultaneous activity, completion, queueing, stops, body overlaps,
   movement-space adherence and mode counts. A population setting alone is not density.
   Do not call a horizon-censored run a completed finite-source test.
4. Freeze a recorded source before optimization. Compare identical inputs and motion
   checksums; report source and aggregation costs separately. A deadline guarantee
   needs worst-case evidence and admission bounds; mean speedup is insufficient.
5. Compare the original Policy Tree with a predeclared support-only relaxation:
   each contributor/category lower bound becomes ceil(0.6 * original). Preserve
   regional geometry, semantic ceilings, window/age bounds and release trigger.
   Compare adaptive and fixed portfolios under both trees. Use identical observations
   and recipient queries; report independent release-policy audits, availability,
   detail, delay and exact/estimated query errors separately.

Lower support is a weaker operational requirement. It is not evidence of a privacy
improvement. The scenario remains a proof of concept; attack-based privacy validation
and calibrated pedestrian/rider behavior remain separate work.

## Acceptance evidence

Implemented and measured. The 256-person source completes all 360 visible episodes,
peak 224 active, and passes native plus independent recorded audits. Paced 500-total
flow completes; the higher-pressure 500-person case fails the bounded drainage gate.
Ten same-source C++ executions pass independent publication-policy checks. Adaptive
retention improves over the tested fixed portfolio, while fixed 10 m / 1 s remains
better for the predeclared aligned recipient queries. Source optimization preserves
motion digests but does not establish a hard real-time guarantee.

Read the [implementation/test report](URBAN_TRAFFIC_TEST_REPORT_2026-10-24.md) and
[policy comparison](URBAN_POLICY_RESULTS_2026-10-24.md). Generated motion/replay files
remain local and ignored; only compact aggregate evidence belongs in Git.
