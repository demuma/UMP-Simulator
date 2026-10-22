# A coherent 20-minute presentation: candidate narrative

Date: 2026-10-21. Planning document, not a replacement slide deck. The bounded moving pilot is implemented and verified: three captures, 27 method outputs, three deterministic repeats and 55 passing CTest entries. Slide editing and rehearsal remain open. All assertions must be matched to the latest frozen run before presentation. Use 18 minutes of planned speech and 2 minutes of transition/demo contingency. Keep implementation details, full taxonomy, alternative attack studies and regression statistics in backup slides.

## One central question

**Under which regional policy requirements and traffic conditions can online spatial, temporal and semantic adaptation release useful mobility aggregates, and what information and delay does satisfying those requirements cost?**

This question does not presume universal policy feasibility, a globally optimal scheduler, or that distinct support alone proves an empirical privacy gain. A narrower testable primary question for the immediate experiment is whether adaptive release improves a predeclared task's availability/detail over fixed raster/window configurations **under identical operational constraints and identical captured observations**.

## Answer first, with boundaries

Suggested opening answer:

> The mechanism can enforce the declared regional release constraints by adapting spatial, temporal and semantic detail and suppressing unresolved output. Which information remains useful depends on density, type mix, policy limits and the chosen priority. The current controlled results expose these trade-offs; the recorded moving-data comparison shows an occupancy/spatial advantage in one setting with a semantic cost, and a high-density setting where a coarse fixed grid matches the semantic-priority output.

Use the [moving results](MOVING_REPLAY_RESULTS_2026-10-21.md) for the numerical scope. Do not generalize one paired pilot contrast into a universal fixed-grid win. A result of no advantage in uniform traffic is a valid condition on the question.

## Main deck: 11 slides, 18 minutes

| Slide | Time | Audience question and concrete content |
|---|---:|---|
| 1. Question and conditional answer | 1:00 | State the research question, current answer and bounded evidence. Avoid an agenda occupying a separate slide. |
| 2. Why local adaptation? | 1:00 | One road area with a sparse pedestrian zone and dense mixed traffic; two applications need different freshness/detail. Label scenario schematic if no measured map exists. |
| 3. What is protected and what is released? | 1:30 | Trusted sensing node, private identities/observations, recipient aggregates. Operational support is a policy condition; full identification resistance is a separate validation question. One location trajectory should not be confused with repeated independent people. |
| 4. Policy Tree defines the feasible region | 2:00 | Regional lower support bounds and upper space/time/semantic-loss/age limits; inherited strict effective requirements. Explain incompatibility and suppression as explicit outcomes. Policies provide requirements; metric evaluator computes values from candidates. |
| 5. Three controllable dimensions | 2:00 | Spatial parent merge, longer interval, truthful ancestor category. Define TF = retain temporal accuracy, SF = retain spatial accuracy, Semantic First = retain semantic accuracy. Show one 4/2/2 leaf example. |
| 6. Online decision loop | 1:45 | Observe current sample → update private history → candidate evaluation → release or extend/merge/generalize → bounded suppression. No future observations; published intervals immutable. Bucket/history details only as one sentence. Semantic controller currently common-window only. |
| 7. Controlled result: no universal winner | 2:00 | Medium source: fine Root vs coarser exact categories, with 20 m/40 m fixed-query availability. Low source: waiting cost without new identities. Higher source: all strategies coincide. These are stationary hand-controlled tests, not moving simulation results. |
| 8. Replay: same motion, different release | 1:30 | Short synchronized playback with private sampled XY and fixed/adaptive panels at the same timestamp. Show actual selected cuts, interval age, generalized category and private finalized suppression diagnostics. The first viewer does not display every pending intermediate state. State recorded playback, not measured live acquisition latency. Have screenshot/video fallback. |
| 9. Paired moving-data comparison | 2:30 | **Validated pilot:** existing C++ simulator; requested N=200/500/1000, 20 s, 80 m x 80 m, seven profiles, 100 ms samples. Six fixed grids/windows (10/20/40 m x 400/1000 ms) plus TF/SF/Semantic on byte-identical source per N and the same uniform-root policy. Show the 200-user equal-coverage occupancy contrast and its semantic cost, then the 1000-user fixed/Semantic-First match. Use one trade-off plot; keep the full 27-row table in backup. |
| 10. Meaning and limits | 1:30 | Policy satisfaction is distinct from a stronger privacy guarantee; no equivalence of support and epsilon. Explain no-superiority regime and suppression/age/semantics trade-offs. ALOQ: related continuous LDP frequency estimation, future external comparator, not untested bar in results plot. |
| 11. Answer and next decisive test | 1:15 | Return to exact research question with 2 measured findings and 1 open condition. Then future context-aware traffic and attacker validation, without making them prerequisites for today's mechanism result. |
| Planned speech | **18:00** | Leave 2:00 for transitions or playback contingency. |

## Optional policy-cap result for the same time budget

The [cap sensitivity follow-up](CELL_SIZE_CAP_RESULTS_2026-10-21.md) is now
verified. At N=500, 40/10/5 m caps retain 100%/93.91%/28.31% of observations
under Spatial First. The 5 m output answers no complete 10 m/1 s query, despite
retaining some contributions. This shows a requested detail constraint's cost;
it is not a new privacy guarantee. Use this as one alternative contrast on
slide9 or a backup, replacing another result rather than adding time. The
paired replay is http://127.0.0.1:8768/ while its local server runs.

## Optional window-limit result within the same time budget

The [four-second follow-up](FOUR_SECOND_WINDOW_RESULTS_2026-10-21.md) is verified.
At N=500 and maximum 5 m output cells, extending both duration and age limits
from 1 s to 4 s raises retained observations from 28.31% to 49.26%; eventual
10 m / 1 s query availability rises from 0% to 3.44%. Only 0.87% of the fixed
interior cohort is available at query end with the new policy. These figures
describe different declared cohorts and must not be subtracted as a paired
percentage-point loss. The direct replay is http://127.0.0.1:8769/.

Use this as an alternative to another slide-9 contrast or in backup; add no
main-deck time. The scientific point is that a policy changes the feasible
information/delay trade-off. SF and Semantic First have exactly equal public
streams at this cap in both limits: scarce pooled distinct support and the
current full-cut early-release requirement dominate their priorities. Seven
types reduce detailed-class support but do not require 35 people, since the
allowed Road User ancestor pools them. Distinct support remains an operational
condition, not a new measured privacy result.

## Mathematical content: three canonical displays

Copy symbol definitions and unavailable cases from `docs/TERMINOLOGY_AND_NOTATION.md` (v1.9), sections 3, 6-8, 12 and 24. These displays reuse that contract. Explain symbols orally and with one candidate picture, rather than introducing a new notation system.

1. **Support counts different Road Users, not repeated samples** (sections 6/24):

$$
n(C,I)=|\mathcal U(C,I)|,\qquad
n_{\mathrm{cat,min}}(C,I,K)=\min_{v\in K}|\mathcal U_v(C,I)|.
$$

C is a data cell, I its half-open time interval and K its selected truthful category cut. Ten observations of one identity still supply support one. A named k-anonymity claim additionally requires a precise QI/equivalence-class contract; the pilot calls this an operational minimum support of 5.

2. **Policy feasibility is a conjunction** (P2, section 7):

$$
\operatorname{Admissible}_a(b;t)=
\operatorname{Complete}(I_b)\ \land\
\bigwedge_{m\in\mathcal M_a(C_b)}
\left[v_m(b;t)\ne\bot\ \land\
\underline\theta_m^{(a)}(C_b)\le v_m(b;t)\le\overline\theta_m^{(a)}(C_b)\right].
$$

The Policy Tree supplies the bounds; the metric evaluator computes v_m. An unavailable required metric cannot pass. Passing eligibility is followed by publication coordination; it is not by itself a release event. This first moving pilot uses root-level bounds; heterogeneous regions are the next separate factor.

3. **Utility is availability together with conditional error** (U2, section 12):

$$
c_{\mathrm{ans}}=\frac{|\mathcal Q_{\mathrm{ans}}|}{|\mathcal Q|},\qquad
\operatorname{MAE}_{\mathrm{occ}}=
\frac{1}{|\mathcal Q_{\mathrm{score}}|}
\sum_{i\in\mathcal Q_{\mathrm{score}}}|\widehat y_i-y_i|.
$$

Q is the fixed query bank, Q_ans contains recipient-answerable queries and Q_score additionally requires valid reference evidence. Evaluate each against its declared logical deadline. Empty denominators are unavailable. The moving pilot asks mean sampled occupancy on 10 m squares/1 s intervals and reconstructs with explicit uniform-space/constant-time assumptions. It is **not the conservative exact semantic-count query bank** used by slide 7. Report each workload separately.

An appendix can give exact Semantic First preference/fallback rules and semantic loss definitions. A generic weighted utility argmin would misdescribe the currently implemented bounded heuristics and must not be presented as global optimization.

## Moving-pilot evidence for the main story

The [result report](MOVING_REPLAY_RESULTS_2026-10-21.md) and [test report](MOVING_REPLAY_TEST_REPORT_2026-10-21.md) are authoritative for this bounded matrix.

| Evidence item | Verified value | Source |
|---|---|---|
| Captures | 200/500/1000 initially, 20 s each, seven profiles, 80 m x 80 m | Each capture proof/manifest |
| Last sampled population | 189/495/988 | Frozen source population summaries |
| Nine methods per capture | 27 independently scalar/semantic-audited outputs | verification-final.json |
| Frozen-input repeat | One per source, equal outside runtime | determinism-repeat.json |
| Equal-coverage occupancy contrast | N=200: SF vs fixed40m/1000ms both 100% coverage and retention; MAE1.419 vs1.849, mean side24.21m vs40m | Actual result/query summaries |
| Cost of that contrast | Mean semantic loss.819 vs.402; same allowed maximum1 | Public bins and declared losses |
| No unique adaptive advantage | N=1000: Semantic First and fixed40m/400ms both exact categories at40m/400ms, zero semantic loss | Actual selected cuts |
| Timing | TF400ms; SF1000ms; Semantic First1000ms atN=200/500 and400ms atN=1000 | Interval-start-age summaries |
| Evidence limit | One stochastic realization perN, root-only policy, no new measured privacy gain | Predeclared protocol |

Do not compare conditionalMAE across differently answered cohorts as if all queries were matched. The N=200 contrast above is deliberately chosen because both answer the full fixed workload; still report its semantic cost. The occupancy task reconstructs under explicit uniform-space/constant-time assumptions and does not evaluate class-query utility. Do not select only a flattering baseline: keep all six settings visible in the plot or backup.

Local replay launch:

```sh
python3 tools/replay_viewer/serve.py \
  --bundle results/moving-replay-2026-10-21/n500/comparison --port 8765
```

Open `http://127.0.0.1:8765/`. Use the actual sealed release events and selected variants, not a synthetic animation. This is private research material containing positions/identities even when the recipient filter is active. ALOQ remains related work and a later comparator; no unrun result belongs in the quantitative table.

## Existing result that can already carry a scientific point

Source: `docs/SEMANTIC_FIRST_RESULTS_2026-10-21.md`, 27 deterministic cases, three hand-constructed stationary inputs with 16/32/80 total Road Users. Four occupied 20 m leaves, category minimum 5; 400 ms base and 800 ms maximum. These data are not generated by the motion simulator.

At medium density, a 20 m leaf has supports 4 pedestrian / 2 adult cyclist / 2 child cyclist. Existing TF/SF can publish Root/RoadUser 8 at 20 m; Semantic First can merge to 40 m and publish exact 16/8/8. At the same first 400 ms endpoint, maximum/mean semantic loss changes 1/1 → 0/0. In the predeclared conservative exact count query bank, 40 m query availability changes 25% → 100%, while 20 m availability changes 25% → 0%. The mode honors its priority and shifts utility; it does not improve every task.

At low density and hard max loss 1, TF already releases the legal generalized parent at 400 ms. Semantic First waits to 800 ms before falling back to the same semantic detail because static identities provide no further support. This is an important weakness to show honestly. Moving identity turnover is the next measured factor, not an assumed remedy.

At high density, all strategies produce fine exact output in these sources. Thus more traffic does not by itself prove adaptation superior. At hard semantic loss zero, some low-density cases remain infeasible. Passing releases satisfy operational constraints; this experiment measures no new attack resistance.

All feasible controlled cases retain 100% of source observation contributions, but that is not retention of all original spatial/temporal/type information. Keep these different metrics separate.

## Plots and replay states that explain the comparison

- Primary plot: 10 m/1 s occupancy query availability by deadline, paired by capture; show all six predeclared fixed settings against the three strategies, rather than one arbitrarily weak fixed setting. This is not an exhaustive optimal fixed frontier.
- Secondary plot: space/time/semantic loss and suppression or data age. Choose the two most explanatory axes for the observed effect; retain the rest in backup.
- Replay color legend: published historical support/geometry and finalized private selected/suppressed diagnostics. Display source identities only in the private research view. Label output window support and receipt/simulated time so historical accumulation cannot be mistaken for instantaneous occupancy.
- Show enough road users to make density visible, but do not let a full point cloud hide the adaptive cells. A zoomed region and shared time cursor are more explanatory than thousands of arrows.

## Edits needed to the supplied 32-page deck

- Main research question is currently page 3. Put it and a conditional answer at the start; avoid four pages of unconnected privacy metric catalog before the actual mechanism.
- Page 14 (printed slide 13) architecture needs an explicit Policy Tree, metric evaluator and outgoing recipient boundary. Metric values are computed by evaluation, not emitted by a Policy Tree. Add semantic granularity if it is part of the shown contribution.
- Pages 18-20 contain historical bucket/database merge/split descriptions. Replace in the main story by the actual bounded release loop. The current immutable recipient stream is not retroactively made private by deleting already published data.
- Pages 27-28 are scenario mockups (residential/shopfront), not results. Their average local k-anonymity=2 captions should not be reused as measured evidence. Place one as a clearly labeled future context-aware case or replace with a measured replay.
- Simulator feature inventory, SFML and byte layouts belong in backup. The contribution is the policy-constrained release decision and its quantified behavior.
- Remove claims that currently unimplemented sensitive-attribute diversity or end-to-end real-time latency has been established. A simulation speedup ratio and logical window age are not measured sensor-to-application latency.

## Presentation readiness gate

Before freezing slides: one fixed trace manifest; same-method input hashes; exact participant counts by sample; explicit area and time units; no resource failure mislabeled policy infeasibility; query bank and deadlines fixed; metrics sourced from recipient output; playback screenshot fallback; results and limitations traceable to frozen run. Test inventory can be one backup line, not the primary evidence of scientific effectiveness.
