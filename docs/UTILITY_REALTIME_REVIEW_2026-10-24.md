# Interpreting adaptive utility, policy limits and real-time cost

Date: 2026-10-24. Read-only code/results review after commit `3f92f8f`.
No controller rule, policy threshold or frozen experiment result changes in this review.

## What the current figures establish

The plotted spatial side and semantic loss condition on retained observations. Methods retain different sets; an adaptive method can rescue difficult observations that a fixed baseline suppresses and thereby increase its conditional mean loss. Retention must accompany these means. Compare detail on the common retained observation set as an additional paired analysis; preserve full-input denominators for overall availability and subtype preservation.

Original adaptive output has 3199 cell-windows: 2691 at 10 m, 504 at 5 m and four at 2.5 m. Its observation-weighted mean side is therefore still 9.38 m versus 10 m fixed. Support60 reaches 8.68 m. The output is predominantly coarse, despite D6 input. Repeated observations of the same track do not increase distinct support. Neither high cohort size nor long residence automatically makes every fine cell eligible.

Original adaptive semantic mean is 0.642 versus 0.651/0.652 for fixed10m0.4s/1s; Support60 is 0.588 versus 0.597/0.592. Leaf, family and root costs are the specified 0/0.5/1 taxonomy costs, not measured privacy risk or fractions of all information lost. About 28.5% of original adaptive retained contributions are root-only; most others are already family-level. Very little exact subtype information survives.

## Verified controller mechanisms, and what remains a hypothesis

`simulator/src/CellLocalAggregation.cpp:764–816` chooses currently legal ancestor rescues by semantic-loss tiers. Nearest geometry wins at the first available tier; overlapping nested rescues retain the broader domain before child disclosure. This preserves legal rescue/ownership consistency, but can consume fine siblings along with the failed branch. How much of the measured coarsening each rule causes requires decision tracing or a controlled ablation.

The current source uses Semantic First, Temporal First secondary and `policy_satisfied` release. `CellLocalAggregation.cpp:777–786` admits immediate coarsening under this trigger; `891–916` removes preference waiting. Changing only the secondary priority may therefore have no effect in some paths. The controller does not evaluate a global optimum or explicitly compare "fine after another sample" against "coarse now". Semantic First is a local preservation preference, not a guarantee that the global contribution-weighted semantic mean dominates all baselines. Parent choice uses maximum loss; the figure reports mean loss.

`simulator/src/SemanticTaxonomy.cpp:162–177` requires every occupied semantic child to pass before retaining that partition. With category support five, 20 pedestrians plus one cyclist cannot be published as two supported bins. A legal complete cut can collapse to 21 Road Users. Selective semantic-bin suppression is not an action in this evaluator. More samples of the same cyclist do not create more distinct cyclists.

## Policy changes and mechanism changes are different experiments

A `semantic_max_loss <= 0.5` bound forbids the Road User root and preserves at least the mode-family information for any nonempty approved release. Loss zero requires exact terminal labels. These bounds can lower published semantic loss while increasing spatial coarsening, waiting or suppression. They cannot manufacture support. Apply the same changed tree to every method and report retention, type preservation and delay together.

If mode-resolved occupancy is the application, a family-level ceiling is a meaningful utility requirement. If only total occupancy matters, a root count can remain useful despite taxonomy loss one. The application must justify the metric/cap. Lowering contributor support changes the operational protection contract; it is not an implementation repair or evidence of privacy gain.

Sequential controlled questions:

1. Trace why each selected output uses a parent, waits, generalizes or suppresses; add common-retained-set detail alongside the existing complete-input coverage.
2. Compare `policy_satisfied` and `priority_satisfied` on identical source/tree/query inputs. Keep current output as the control. Explicitly measure the quality/delay cost of early release versus preference waiting.
3. Then compare the secondary priorities, confirming that the tested release trigger actually allows them to differ.
4. Independently compare semantic ceilings 1 versus 0.5 under matched baselines. Do not silently weaken support to obtain finer output.
5. Only afterward consider bounded task-aware candidate search or selective semantic suppression. The latter requires a recipient-consistency analysis including totals/residuals and complementary suppression.

## Logical release delay is not processor runtime

The figure plots the 95th percentile of `sealed_at_ms - observation.at_ms`. These are source/logical timestamps, computed in `tools/mapped_scene/run_comparison.py:145–163`. CPU speed is not used to calculate this metric.

| Original-policy method | Mean observation-to-seal delay | p95 |
| --- | ---: | ---: |
| Adaptive | 391 ms | 1400 ms |
| Fixed10m0.4s | 250 ms | 400 ms |
| Fixed10m1s | 550 ms | 1000 ms |

Support60 adaptive has mean 332 ms and p95 800 ms, both better than fixed1s. Longer permitted adaptive windows create a tail, while early release can improve the mean. This does not diagnose queueing or computation. A slow implementation can add actual delivery lag even when the recorded logical delay is unchanged.

## Isolated real-time contract after perception

Assume a separate perception/tracking/classification system delivers timely batches containing visible-track identity, position, timestamp and category. The aggregation boundary should then include the detection adapter/cell assignment, ingestion, history and bucket updates, policies/metrics, candidate selection, ownership/publication consistency and the required output handoff. Exclude movement generation, neural inference, rendering and offline analysis from this isolated boundary. Measure a synchronous database/network ACK if it is part of the declared delivery promise; an in-memory handoff alone cannot prove recipient delivery.

For event i let `a_i` be its independently scheduled wall-clock arrival, `q_i` its accepted enqueue time, `b_i` its service start and `f_i` its completion. Report producer lateness `q_i-a_i`, queue wait `b_i-q_i`, service `f_i-b_i`, and scheduled response `R_i=f_i-a_i`. Declare the deadline D_i and require R_i <= D_i when claiming that deadline. Also report misses, queue peaks/overflow, sustained backlog, memory and worst observed/tail times. Average throughput alone is insufficient. A finite measured run is empirical evidence, not a hard worst-case guarantee.

The maintained adapter already preloads frozen observations, removes movement generation and has independent steady-clock paced replay (`simulator/tools/AggregationReplay.cpp:489–541`). Current urban comparisons use 50-ms advance-before-ingest progress but are unpaced. Their core totals include in-memory diagnostic serialization; they do not establish a deadline. The current urban recording has not yet been measured at wall-clock1x.

A proper next run uses `--pace-rate 1 --queue-capacity 8 --progress-step-ms 50`. Retain 100-ms sensor arrivals and the real 50-ms no-measurement progress steps; deadlines must not slide when the consumer is slow. The existing summarizer verifies complete output equality excluding runtime against the unpaced control. Input parsing and geometry preparation occur before the epoch; raw detection-to-cell mapping and a real output sink need their own included measurement or separate declared budget.

```sh
./simulator/build/AggregationReplay \
  --input results/urban-traffic-2026-10-24-256/replay/observations.json \
  --config results/urban-traffic-2026-10-24-256-policy-comparison/original_adaptive_immediate-policy.json \
  --mode semantic_first --progress-step-ms 50 \
  --pace-rate 1 --queue-capacity 8 \
  --output results/urban-traffic-2026-10-24-256-policy-comparison/original_adaptive_paced_1x.json

python3 tools/profiling/summarize_paced_replay.py \
  --paced results/urban-traffic-2026-10-24-256-policy-comparison/original_adaptive_paced_1x.json \
  --reference results/urban-traffic-2026-10-24-256-policy-comparison/original_adaptive_immediate.json \
  --output results/urban-traffic-2026-10-24-256-policy-comparison/original_adaptive_paced_1x_summary.json \
  --binary simulator/build/AggregationReplay \
  --source results/urban-traffic-2026-10-24-256/replay/observations.json
```

These commands are proposed, not executed in this review. Choose fresh output paths. The old frozen source has the three disclosed source/sink defects; use its actual measured input for this paired timing control. A corrected-source validation is a separate dataset and should not silently replace it.

## Map and U-Bahn follow-up

See [the source/portal plan](SUBWAY_ACCESS_PLAN_2026-10-24.md). The custom map uses functional polygons and assumed buffered widths rather than the web map's style; its center/crop differs. There is also a concrete roof-versus-ground-obstacle defect around A1/A2. Correct geometry classification and preserve public OSM entrance/ref/access/stop-area metadata before implementing explicit transit surface sources/sinks. Keep these environment changes separate from the frozen controller/timing experiment.
