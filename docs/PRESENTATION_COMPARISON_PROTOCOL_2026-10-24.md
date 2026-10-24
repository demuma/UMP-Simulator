# Presentation comparison protocol: policy, action availability and semantic families

Date: 2026-10-24. Status: proposed protocol following a read-only implementation audit. No new experiment, mixed-mode source or baseline superiority is claimed. This narrows the existing [three-scenario plan](THREE_SCENARIO_PLAN_2026-10-23.md); it does not replace frozen earlier experiments.

## 1. First question and sequential gates

Under the same input and hard regional requirements, when does online spatial, temporal and semantic adaptation retain more useful information than a fixed spatial/temporal release scheme, and when does it lose?

Proceed in order:

1. Finish map connectivity, entrance behavior and comfortable wall/corner clearance. Audit the resulting source before freezing any comparison.
2. On the current pedestrian source, establish one paired fixed/adaptive comparison and independently audit every published footprint, interval, category and source contribution.
3. Add mode-specific cycling/scooter geometry, profiles and routes; test source correctness and then freeze a separate mixed-mode source.
4. Add bounded action ablations and priority comparisons. Run the full declared matrix, including no-advantage cases.
5. Only after this mechanism/utility gate add a defined empirical privacy comparison. Category support is an operational protection constraint; it is not by itself a measured probability of identification or a proof of k-anonymity.
6. Add the residential and traffic scenarios separately, reusing the same evaluation contract rather than introducing all three environments at once.

## 2. Where classes are actually configured

The general simulator reads `agents.road_user_taxonomy` in `simulator/config.yaml`. Its current entries include Child/Senior/Adult Pedestrian, Senior/Adult/Cargo Cyclist and Adult E-Scooter Driver. Probability, radius, speed, acceleration and look-ahead are source behavior settings.

The mapped scenario does not simply inherit that list. `tools/mapped_scene/build_mapped_scene.py` defines `PROFILES`, builds `profiles()`, replaces the generated configuration's `agents.road_user_taxonomy`, and writes explicit people/types and explicit speeds into `mapped_scene.people`. In the current mapped source those five profiles are Adult/Child/Senior Pedestrian, Pedestrian With Stroller and Pedestrian With Mobility Aid. In storefront mode the generated profile probabilities describe the explicit cohort; editing probabilities afterwards does not regenerate its explicit people.

The release taxonomy is a second, separately versioned configuration: `sensors[].aggregation.semantic_taxonomy`. Every source label must map to one terminal. Adding a simulator profile without adding this mapping fails validation. Adding a cyclist label to the current pedestrian routes would not make a valid mixed-mode scenario: cycling/scooter movement envelopes, allowed geometry, boundary sources, speed behavior, junction access and release branches must agree first.

## 3. What 0.5 does and does not mean

Each release node has an explicitly declared cost `loss`, monotone toward ancestors. Terminals must have cost 0; the root must have cost 1. Costs are not inferred from tree depth. Different branch depths are supported.

Use the canonical notation from [the notation contract, Section 24](TERMINOLOGY_AND_NOTATION.md#24-semantic-release-hierarchy-and-quantitative-constraints): K is the nonempty released category cut for C,I, gamma_sem(v) is the declared node cost, and N_obs counts retained observation contributions. The implemented summaries are

\[
L_{\mathrm{sem,max}}(K)=\max_{v\in K}\gamma_{\mathrm{sem}}(v),\qquad
L_{\mathrm{sem,mean}}(C,I,K)=
\frac{\sum_{v\in K}|\mathcal O_v(C,I)|\gamma_{\mathrm{sem}}(v)}{N_{\mathrm{obs}}(C,I)}.
\]

These are hierarchy abstraction measures on retained observations. They are not calibrated privacy scores, percentages of all information destroyed or percentages of users suppressed. A measured maximum of 1 means at least one bin reached the root cost; it does not mean every bin did.

The current mapped tree has exact profile leaves at 0, Pedestrian at 0.5 and Road User at 1. A future common mixed-mode taxonomy can explicitly assign Pedestrian, Cyclist and E-Scooter Rider the same cost 0.5. An Adult E-Scooter leaf under an E-Scooter parent is useful for a consistent schema, but pooling only one observed scooter subtype supplies no additional support relative to that leaf. Age diversity and sufficient local class support must be measured, not assumed.

`semantic_max_loss.max: 0.5` permits costs at most 0.5 and prohibits Road User output. It does not force every output into its 0.5 family. The evaluator retains the finest supported truthful taxonomy cut; exact and generalized branches can coexist in one cell.

In the current all-pedestrian mapped source, Pedestrian at 0.5 and Road User at 1 pool exactly the same observed-track identities. Under the existing numeric support rules the root therefore cannot rescue a candidate that Pedestrian could not rescue. A shared ceiling of 1 versus 0.5 should produce the same releases here: this is a useful negative control, not evidence of missing adaptivity. A meaningful mode-family boundary at 0.5 needs an actual mixed-mode source.

Distinguish three interventions:

- **A shared hard ceiling of 0.5:** constrains every method's feasible output, while permitting exact labels.
- **A family-only release action:** deliberately projects all input into Pedestrian/Cyclist/E-Scooter families before choosing space/time. Counts remain truthful, but detail is intentionally discarded. This is a separate action restriction/projection, not the existing Semantic First strategy.
- **Semantic First:** preserves semantic detail by preferring cost 0 before successively higher costs, possibly using a coarser spatial parent to keep exact labels.

Do not relabel family-only projection as Semantic First: the project's established convention names the dimension to preserve.

## 4. Strategy and release timing contract

Temporal First preserves temporal detail, normally trying spatial rescue before extending time. Spatial First preserves spatial detail, normally extending time before spatial rescue. Semantic First preserves semantic detail and declares a Temporal First or Spatial First secondary preference.

With `release_trigger: policy_satisfied`, legal current merges are planned before disclosing their children and remaining eligible local owners publish immediately. Positive semantic tiers can be selected at the current endpoint. The two Semantic First secondaries can therefore produce identical results. Do not present identical output as two independent successes or promise a visible ordering effect where the immediate-release rule removes it.

With explicit `priority_satisfied`, intentional waiting may preserve preferred exact semantics before the deadline. Temporal secondary can merge now to retain exact labels; Spatial secondary can wait at fine spatial resolution. This changes the release rule and must be recorded as its own comparison. Hard age/duration limits always dominate preferences.

A hard ceiling is not an instruction to wait for the largest permitted window. The base interval is a first probe; a hard duration minimum must be declared separately if shorter local parent rescues are forbidden.

## 5. Implemented comparators and remaining ablation work

A fixed grid already performs spatial aggregation by assigning contributions to cells. Label a fixed reference without further action as “no additional temporal/semantic adaptation,” rather than “no aggregation”; reserve unfiltered/raw output for an explicitly labeled diagnostic reference.

Existing `AggregationReplay` supports `fixed`, `spatial`, `temporal_first`, `spatial_first` and `semantic_first`; fixed mode accepts explicit depth and fixed window. Fixed output still uses the same category-support evaluator and can generalize semantics, then suppress candidates that fail any hard bound. It is not an unmodified GBS output without protection checks.

`tools/evaluation/run_moving_scoped_comparison.py` already declares six fixed spatial/temporal schemes (2.5/5/10 m crossed with 400/1000 ms) and four common/local Semantic First variants. The related recipient-contract study retains exact-query evaluation and adds separately scored uniform estimates. These runners freeze particular historical inputs, catalogs and manifests; a new mapped comparison needs an explicit new adapter/protocol rather than overwriting historical inputs or claiming the old runner accepts arbitrary mixed-mode data.

The following matrix is a proposed capability decomposition, not a claim that all switches have already been implemented:

| Variant | Spatial choice | Temporal choice | Semantic choice | Purpose |
| --- | --- | --- | --- | --- |
| Fixed reference | One fixed legal grid | One fixed legal interval | Same supported cut evaluator | Fair main baseline |
| Temporal-only ablation | One fixed grid | Online extension | Exact-only or declared family-only action | Isolate temporal decisions |
| Temporal + semantic ablation | One fixed grid | Online extension | Truthful permitted cuts | Measure semantic contribution |
| Spatial-only ablation | Online spatial cut | One fixed interval | Same semantic action set | Isolate spatial decisions |
| Full controller | Online spatial cut | Independent local windows | Truthful permitted cuts | Main adaptive method |
| Semantic-preservation preference | As full controller | As full controller | Semantic First, declared secondary | Priority sensitivity |
| Family projection | Fixed or adaptive, declared in ID | Fixed or adaptive, declared in ID | Forced 0.5 family representation | Test user's proposed semantic-first action |

Hold the source, hard policy, category support, query bank and release/recipient boundary constant when interpreting an action ablation. An exact-only action restriction needs a real verified controller restriction; changing the policy's hard semantic ceiling to 0 instead creates a different feasible policy contract and must be labeled as a policy-sensitivity experiment. Likewise fixed spatial depth in a true temporal-only controller requires explicit verification that no other depth is selected; mode `fixed` does not by itself implement adaptive timing.

Start with the fair fixed portfolio and one full cell-local controller. Add the other rows one at a time with correctness gates; do not cross every factor in the first presentation experiment.

## 6. Bounded first mapped matrix

Freeze one validated source, all seeds and per-region flow/type statistics. Keep 500 total people as a cohort size, not a concurrent-density claim. Measure actual concurrency and class support in space/time. One source is one realization, however often deterministic replay is repeated.

For the first mapped comparison keep the existing 400-ms minimum and 4000-ms maximum source window, local region constraints and allowed output sides. Use a predeclared fixed grid portfolio of 2.5, 5 and 10 m, crossed with 400, 1000 and 4000 ms; leave structurally disallowed regional outputs suppressed and visible in the report. Use the same release taxonomy and category support as the adaptive method. Clearly report that these nine settings are a tested subset, not the globally best uniform schedule. After source and policy gates, compare one cell-local Semantic First controller with `policy_satisfied`; add other strategies only after the first audited paired result.

A fixed fine grid with one sensor sample and no protection checks can be shown as an upper-utility reference. Under the current mapped 400-ms hard minimum, a 100-ms release is noncompliant; it cannot be the fair privacy baseline. If instantaneous release becomes an experimental condition, define a separate shared policy with that minimum for every method.

A shared hard semantic ceiling of 0.5 is a useful predeclared sensitivity test. It can prevent root collapse and make spatial/temporal trade-offs visible, but can also increase suppression. It benefits fixed and adaptive methods alike; it does not imply the adaptive controller must win. Compare the tested fixed frontier, or choose a fixed configuration on a separate calibration cohort and evaluate unchanged test cohorts.

## 7. Implementation audit references

These references describe the audited implementation; later edits can move line numbers.

| Contract | Current implementation |
| --- | --- |
| General configured source classes | `simulator/config.yaml`, `agents.road_user_taxonomy`, lines 164–276 |
| Mapped source profiles and explicit cohort | `tools/mapped_scene/build_mapped_scene.py`, `PROFILES` at 33, `profiles()` at 287, `make_config()` at 357; storefront cohort replacement at 394 |
| Mapped policy and release tree | Same file, region bounds at 334–354, execution/root at 381–387, taxonomy at 388–391 |
| Explicit monotone node costs and terminal requirements | `simulator/src/SemanticTaxonomy.cpp`, constructor at 32–83 |
| Weighted semantic loss and supported truthful cut | Same file, `representation()` at 137–153, `select()` at 156–181 |
| Exact identity deduplication through every ancestor | Same file, `SemanticAccumulator::add()` at 229 onward |
| Category-support selection and hard bound checks | `simulator/src/CandidateMetrics.cpp`, lines 215–274 |
| Policy region adaptation and strict bound composition | `simulator/src/PolicyConfiguration.cpp`, lines 53–74; `simulator/src/PolicyTree.cpp`, `intersect()` and `resolve()` |
| Current semantic release ordering | `simulator/src/AdaptiveAggregation.cpp`, lines 191–242; `simulator/src/CellLocalAggregation.cpp`, lines 757–800 |
| Fixed-grid policy evaluator and suppression | `simulator/tools/AggregationReplay.cpp`, `fixedSelection()` through 312; mode dispatch at 463–470 |
| Existing frozen fixed/common/local matrix | `tools/evaluation/run_moving_scoped_comparison.py`, `variants()` and `config_for()` at 57–84 |
| Separate estimator on unchanged exact cohorts | `tools/evaluation/run_recipient_contract_study.py`; [recipient contract](RECIPIENT_CONTRACT_PROTOCOL_2026-10-23.md) |

## 8. Mathematical and presentation evidence

For a released footprint C and interval I=[a,b), publish only if every effective requirement from every intersected policy patch passes. The strict composition is an intersection of bounds: effective lower bounds are maxima, upper bounds are minima. Contradictory bounds have an empty feasible set. These geometry/interval tests include policy-covered portions without observed users.

For a semantic bin g, distinguish observation support N_g(C,I) from distinct observed-track support D_g(C,I). Repeated samples from the same track add to N_g but not D_g. A category-support bound D_g>=q is an operational requirement. It is not automatically classical k-anonymity of trajectories and does not account for all auxiliary knowledge.

Truthful generalization pools descendants rather than relabeling a cyclist as a pedestrian. For descendant categories g_i under ancestor a,

\[
\mathcal U_a(C,I)=\bigcup_i\mathcal U_{g_i}(C,I),\qquad
|\mathcal U_a(C,I)|\geq\max_i|\mathcal U_{g_i}(C,I)|.
\]

The same observed-track identity is deduplicated, including after spatial or temporal unions. Adding repeated frames of one track cannot manufacture category support. Under the current stable-type-within-candidate assumption the child category identity sets partition the parent, but spatial/time cell counts still cannot simply be summed because one track can traverse several cells or frames. Generalization can improve the supported category partition at the price of semantic detail; it does not increase the total number of source tracks or prove privacy gain.

The advantage hypothesis is conditional: heterogeneous local density, flow, class mix and policy bounds can make a global fixed grid/window either coarsen already-sufficient areas or suppress insufficient areas. Adaptation may retain useful local detail while rescuing sparse neighboring areas. The countercases remain part of the report: dense near-homogeneous traffic may favor a well-chosen fixed grid; insufficient flow with short hard limits may make both infeasible; independent local windows and irreversible early publication can block later merges or increase delay. A semantic ceiling of 0.5 narrows feasibility for both sides and must not be selected only after seeing that it makes one test look favorable.

Every result sheet includes:

- Independent policy violations, completeness and source accounting; resource failures are distinct from infeasible constraints.
- Retained observation fraction, per-source-type and per-region suppression, public category histogram and semantic max/weighted-mean loss.
- Spatial side distribution, source-window distribution, observation-to-seal delay and deadline misses.
- Fixed, public recipient queries for total and family-level occupancy; fine-label queries remain separate. Exact answers require complete whole-cell/whole-interval/category resolution, without GT filling or treating missing publication as zero.
- Separately labeled estimates using the predeclared public-data estimator, with coverage and conditional error on the same fixed query denominator. A larger public cell or time interval cannot reveal an exact smaller partition.
- Processing p50/p95/p99/max, live queue behavior and delivery cost separately from logical release latency. Offline evaluation of causal online decisions is not a live throughput guarantee.

Do not optimize only the error among released answers: a method suppressing difficult regions could look artificially good. Always show coverage and error together, plus suppression and class-specific costs. Policy compliance is a result; empirical privacy gain needs its later defined threat model and evaluation.

A compact presentation can use: (1) precise research question and admissible claim; (2) same source/map and local PolicyTree; (3) action/eligibility diagram with the established preservation terminology; (4) one audited fixed/adaptive side-by-side replay; (5) coverage/detail/delay trade-off with the tested fixed frontier; (6) failure regimes and next privacy test. Housing and traffic extend this evidence after shopping-street validity, rather than replacing the first comparison.
