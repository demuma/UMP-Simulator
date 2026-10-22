# Recipient contract: results and verification

Date: 2026-10-23. Protocol: [recipient query contract](RECIPIENT_CONTRACT_PROTOCOL_2026-10-23.md).
Compact numeric evidence: [results JSON](RECIPIENT_CONTRACT_RESULTS_2026-10-23.json).

## Outcome

The fixed raster's advantage is partly an alignment advantage for exact queries,
but it does not disappear when estimation is allowed. The recipient estimator can
recover many answers from local releases by estimating across publication boundaries. At immediate
query deadlines the matched fixed raster still answers more of the 10-m occupancy
queries, with zero reconstruction error on its answers. With an additional second
of allowed query lag, local adaptation slightly exceeds fixed 10-m/400-ms coverage,
with nonzero error. This is a conditional trade-off on one recording, not evidence
of general adaptive superiority or privacy improvement.

The producer, priorities, policies, releases, source recording and old exact scores
are unchanged. This gate adds a public-support diagnosis and an optional receiver
estimator. Estimates are a separately evaluated application option; they are not a
new default publication rule or a promise that a traffic application accepts them.

## Implemented contract

`tools/evaluation/recipient_support.py` wraps the existing exact decoder. It
partitions query support into disjoint finest-cell/sample intersections, labeling
spatial crossing, temporal crossing, semantic ambiguity and late sealing. Support
without a publication anywhere through EOF remains unpublished/unknown. It is not
assumed empty and is not assigned a private suppression reason.

The optional estimator distributes each publicly resolved category count uniformly
over the record's area and scheduled measurement samples. The first interval has
no t=0 observation. It requires complete, visible, semantically resolved query
support: no private zero imputation, category-proportion inference or extrapolation
from incomplete coverage. Every old exact answer remains an equal estimated answer.
The output includes exact/estimated coverage, estimated-only answers, contribution
MAE, mean-sample-occupancy MAE, category/positive/zero strata and paired errors.
Occupancy is an average number of Road Users over sampled times, not distinct users
over the interval, traffic flow or a continuous-time integral.

`run_recipient_contract_study.py` verifies the pinned parent manifest, capture,
policies, outputs and original forty exact evaluations. It freezes code and protocol,
runs the unchanged forty banks and twenty-four pairs, verifies exact-score equality
and checks complete source/parent directory integrity before marking the run verified.
Only compact summaries are written; no producer is executed.

## Frozen comparison and denominators

The source is the existing 20-s, 500-initial-Road-User recording over 80 x 80 m,
with 199 sensor frames and 99,140 observation contributions. Seven original profiles
map into ten taxonomy nodes. Policy requirements are unchanged: support >=5 per
published category, semantic loss <=1, cell side 1.25–10 m, interval duration
400–1,000 ms and logical age <=1,000 ms. The study has six fixed raster/window
combinations and four common/local adaptive combinations. The semantic secondary
priorities agree on this source; they are not independent repetitions.

Four full-area query banks use 5/10-m cells and 400/1,000-ms windows. Lags are
0/200/1,000 ms. Interior means `query_end + 1000 < 20000`; boundary/EOF-censored
queries are reported separately. Interior Road User query counts are 12,032;
4,608; 3,008; 1,152 respectively. The all-category bank is ten times larger and
contains overlapping taxonomy questions, not ten independent populations.

All reported MAEs below are conditional on answered queries and are in mean
sampled Road Users. They must be read with coverage. A smaller marginal MAE can
reflect a different answered subset; paired results address that limitation.

## Primary result: 10-m Road User occupancy

The table uses the same fixed query cohort for every row. “Exact” is the unchanged
conservative decoder; the optional estimator includes those exact answers.

| Query window | Method | Extra query lag | Exact answers | Estimated answers | Estimated coverage | Occupancy MAE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 400 ms | Fixed 10 m / 400 ms | 0 ms | 2,383 | 2,383 | 79.22% | 0 |
| 400 ms | Common adaptive | 0 ms | 0 | 466 | 15.49% | 0.27436 |
| 400 ms | Local adaptive | 0 ms | 2,055 | 2,060 | 68.48% | 0.00087 |
| 400 ms | Common adaptive | 1,000 ms | 0 | 2,425 | 80.62% | 0.24386 |
| 400 ms | Local adaptive | 1,000 ms | 2,055 | 2,396 | 79.65% | 0.01523 |
| 1,000 ms | Fixed 10 m / 1,000 ms | 0 ms | 939 | 939 | 81.51% | 0 |
| 1,000 ms | Common adaptive | 0 ms | 934 | 934 | 81.08% | 0 |
| 1,000 ms | Local adaptive | 0 ms | 4 | 417 | 36.20% | 0.02413 |
| 1,000 ms | Local adaptive | 200 ms | 4 | 874 | 75.87% | 0.02508 |
| 1,000 ms | Local adaptive | 1,000 ms | 4 | 907 | 78.73% | 0.02565 |

The matched fixed answers do not change with extra lag. A 400-ms publication that
straddles a 1-s query can contribute an estimate once it seals, but cannot generally
be split into an exact count. Even fixed 10-m/400-ms output exhibits this: for 1-s
queries it estimates 446/1,152 answers immediately and 892/1,152 with 200-ms lag.
Independent local windows are therefore not inherently defective; the application
must specify whether interval alignment, fast receipt or bounded estimation error
matters most. Hard eligibility currently does not guarantee that application contract.

At 10 m/400 ms with 1-s lag, fixed and local share 2,359 answered Road User queries;
fixed alone answers 24, local alone 37. The net gain is 13/3,008 queries (0.432
percentage points). On the shared subset, fixed occupancy MAE is 0 and local is
0.01165. At zero lag, fixed alone answers 324 and local alone 1; 2,059 are shared.
These paired counts prevent presenting the small late coverage gain as a free win.

Across all ten categories, 10-m/400-ms immediate estimated coverage is 3,253/30,080
(10.81%) fixed versus 2,714/30,080 (9.02%) local. With 1-s lag local reaches
3,275/30,080 (10.89%). The large gap from root-category coverage reflects unresolved
fine categories as well as unavailable spatial/temporal support.

## Fine queries: compare against coarse fixed estimates too

For 5-m/400-ms Road User queries at zero lag:

| Public method | Estimated answers / 12,032 | Coverage | Occupancy MAE |
| --- | ---: | ---: | ---: |
| Fixed 5 m / 400 ms | 1,006 | 8.36% | 0 |
| Fixed 10 m / 400 ms | 9,532 | 79.22% | 1.08731 |
| Local adaptive | 8,274 | 68.77% | 1.09608 |

Local looks much better than the native 5-m raster on estimated coverage, but the
legal coarse fixed raster can also estimate 5-m queries and already offers more
coverage with similar marginal error. Observed occupancy error is much larger for these 5-m queries than for the
10-m queries, which need only temporal allocation. Different answered cohorts
prevent isolating a causal spatial-error component from this comparison. On the 961 Road User queries jointly
answered by fixed 5-m/400-ms and local, local occupancy MAE is 2.16673 versus fixed
0. Selecting only the favorable marginal comparison would hide that cost.

## What explains the baseline advantage here?

1. **Alignment:** the matched fixed grid/window is constructed to align with the
   declared query. This is a meaningful baseline for that product, but cannot show
   universal superiority for arbitrary applications. Local crossing intervals lose
   exact answerability even after every needed publication has arrived.
2. **Deadline:** at 10 m/400 ms, 350 of 3,008 local Road User queries contain some
   late public support at zero lag; 336 of these have no unpublished remainder.
   They become estimable at 1-s lag. Waiting changes the recipient deadline, not the
   controller or its spatial detail. It must be charged as application latency.
3. **Coverage:** at 10 m/400 ms, unpublished support is 20.822% of fixed support
   volume and 19.661% of local support volume. Local has slightly less missing
   volume but can still answer fewer complete queries. A single unresolved part
   blocks the query; missing support is not a public zero certificate.
4. **Semantic generalization:** 68.352% of fixed and 69.322% of local support volume
   is in records whose published bins do not resolve the requested category, when
   counting all ten category questions. These fractions repeat physical support
   for each category and overlap temporal/deadline flags; they are not percentages
   of people or additive causes. Uniform interpolation cannot recover hidden types.
5. **Limited adaptive opportunity:** the uniform policy allows the same 10-m scale
   everywhere. Prior outputs average 9.958 m locally and 9.966 m in common mode.
   Local retains only 460 more observations than fixed 10-m/400-ms output. This is
   consistent with a pilot in which a simple coarse grid is already well matched.
   It does not isolate a causal density/policy effect: controlled regional and
   scenario variations are still required.

The diagnosis establishes representation restrictions, not the producer's causal
reason for every withheld record or a proof of optimality. The conservative exact
decoder can reject some inferable zeros in crossing public tiles; its frozen
scores are not maximal transcript inference. Neither estimator nor more waiting
proves that the disclosed trajectory information is private.

## Verification

- 35 new support tests cover mixed masks, disjoint conservation, late/unpublished
  separation, semantic hierarchy, source-independent predictions, nonzero allocation
  errors, no gap/category imputation, EOF, malformed/overlapping records and budgets.
  A depth-14 sparse fixture represents 805,306,368 leaf-samples arithmetically.
- 19 new runner tests cover frozen manifest/artifact/config/result checks, exact
  equivalence failures, matrix/output validation and verified/failure lifecycle.
- All 54 new tests pass on system Python 3.9. The configured CMake/CTest Python 3.13
  run passes all eight relevant suites, including existing exact/online occupancy,
  scoped semantic and moving-comparison tests (1.86 s).
- All forty old exact compact evaluations are unchanged. All forty new evaluations
  and twenty-four pairs complete; exact answers remain a subset of estimates with
  equal values. Independent review also verifies all 24 old exact paired summaries,
  all 80 study artifact hashes and all 5,472 packaged aggregate rows field by field.
  Complete parent and capture directory hashes remain unchanged.
- CMake registers both new suites; `AggregationReplay` builds. No production C++
  controller, sensor, publication or MongoDB code changed in this gate.

Study manifest SHA256:
`6bce5fea94d2773d7f292554ecaca22c663f11046e824d145cf0308a1f1fc856`.
The compact results package preserves aggregates, provenance hashes, all four
workloads, ten variants, all lags, boundary counts, category results and paired
scores; generated movements, raw releases and individual query rows stay outside Git.

With the original local capture and parent study available, reproduce into a new
directory from the repository root:

```sh
python3 -B tools/evaluation/run_recipient_contract_study.py \
  --comparison results/moving-scoped-comparison-2026-10-22 \
  --output results/recipient-contract-repeat
ctest --test-dir simulator/build --output-on-failure -j4 \
  -R 'recipient|scoped_semantic|moving_scoped|occupancy'
```

The public repository intentionally does not contain the original capture. A fresh
clone can run unit fixtures and inspect the aggregate evidence, but hashes cannot
reconstruct the moving recording. This is one source realization; no confidence
interval or multi-seed effectiveness claim is justified.

## Next gates

The [runtime diagnosis](RUNTIME_DIAGNOSTIC_REPORT_2026-10-23.md) separates measured
native service cost from logical release delay. First optimize the proven owner
lookup bottleneck without changing releases or policy decisions, then repeat
service-time/backlog tests and measure the live pipeline. No performance claim
follows just from good simulated timestamps.

Before a new effectiveness matrix, explicitly choose application time bins,
acceptable estimation error and deadline/coverage requirements. Then predeclare
matched fixed baselines and regional-policy/density variations, including this
uniform pilot as an unfavorable reference. Do not tune a scenario to guarantee an
adaptive win. A measured privacy evaluation remains a separate subsequent gate.
