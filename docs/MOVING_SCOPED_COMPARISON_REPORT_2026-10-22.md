# Moving-input baseline comparison: results and test report

Date: 2026-10-22. Protocol:
[MOVING_SCOPED_COMPARISON_PROTOCOL_2026-10-22.md](MOVING_SCOPED_COMPARISON_PROTOCOL_2026-10-22.md).
Machine-readable aggregate results:
[MOVING_SCOPED_COMPARISON_RESULTS_2026-10-22.json](MOVING_SCOPED_COMPARISON_RESULTS_2026-10-22.json).

## Finding and scope

The matched-policy experiment verifies the mechanism's published counts and hard
requirements, but does not show an exact-query coverage advantage over the matched
fixed baselines. Local windows reduce logical delay relative to common adaptation
at a small retention cost. A fixed 10-m/400-ms baseline already achieves similar
retention and freshness on this source. This is a useful negative result: adaptation
must be evaluated against an appropriate fixed comparator, not only common-window
coordination.

All ten primary executions passed independent scalar and semantic audits. All four
adaptive repeats were identical after excluding runtime. Forty fixed-query
evaluations and twenty-four paired comparisons completed within the original
budgets. No algorithm, threshold, source or query mask was changed during the study.

Input is the existing C++ Simulator capture, not a new motion generator: 500 initial
Road Users, seven terminal profiles, 80 x 80 m, depth 6, 100-ms sampling and 20 s.
There are 99,140 observation contributions in 199 frames; the final frame has 495
Road Users. This is one stochastic recording with the existing random position /
straight-line destination model. Repeated runs verify determinism, not statistical
replication. No privacy gain, realistic-traffic superiority or global optimality is
established.

## Matched requirements and baseline interpretation

Every variant has category support at least 5, cell side 1.25–10 m, semantic loss
at most 1, source duration **400–1,000 ms**, and interval-start age at most 1,000 ms.
The explicit hard duration minimum closes the previous base-probe ambiguity; a
400-ms initial probe alone did not rule out shorter local rescues.

The six fixed baselines retain the same truthful semantic generalization and
suppression rules. They fix only spatial grid and temporal window. Common and local
adaptive variants each run Semantic First with Temporal First and Spatial First
secondary, using the default `policy_satisfied` release trigger. These priorities
preserve the named dimension. Here the two secondaries produce equivalent output
within each coordination mode; they are not independent evidence of four different
successful algorithms.

Hard requirements apply to released cells. Suppression is permitted, so zero
violations does not mean every source observation can be released or that the policy
is jointly feasible everywhere.

## Whole-run retention, detail and timing

All means below weight each retained observation contribution once. Semantic loss
is the declared 0 / 0.5 / 1 hierarchy scale among retained observations, not a privacy
score or the fraction of source observations suppressed. Delay is actual
`sealed_at_ms - observed_at_ms`, reconstructed from original source timestamps.

| Variant | Released observations | Retained | Mean cell side (m) | Mean semantic loss | Mean delay (ms) | Release events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed 2.5 m / 400 ms | 547 | 0.5517% | 2.5000 | 98.5375% | 248.995 | 18 |
| Fixed 2.5 m / 1,000 ms | 668 | 0.6738% | 2.5000 | 97.0060% | 555.988 | 9 |
| Fixed 5 m / 400 ms | 24,242 | 24.4523% | 5.0000 | 97.4053% | 249.542 | 50 |
| Fixed 5 m / 1,000 ms | 28,065 | 28.3085% | 5.0000 | 96.3389% | 547.258 | 20 |
| Fixed 10 m / 400 ms | 92,021 | 92.8192% | 10.0000 | 97.3723% | 249.217 | 50 |
| Fixed 10 m / 1,000 ms | 93,103 | 93.9106% | 10.0000 | 97.5253% | 547.517 | 20 |
| Common Semantic → Temporal | 93,103 | 93.9106% | 9.9660 | 97.5253% | 547.517 | 20 |
| Common Semantic → Spatial | 93,103 | 93.9106% | 9.9660 | 97.5253% | 547.517 | 20 |
| Local Semantic → Temporal | 92,481 | 93.2832% | 9.9580 | 97.3724% | 251.060 | 2,554 |
| Local Semantic → Spatial | 92,481 | 93.2832% | 9.9580 | 97.3724% | 251.060 | 2,554 |

Local versus common loses another 622 observations (0.6274 percentage points) while
reducing mean logical delay by 54.14%. Relative to fixed 10 m / 400 ms, local retains
460 additional observations (0.4640 percentage points), with about 1.843 ms more
mean delay. These conditional delay means refer to different retained sets; they
do not establish that each shared observation arrives 54% earlier. Query comparisons
below use an identical task cohort instead.

Common adaptation offers only a small spatial-detail difference from fixed 10 m /
1,000 ms here. Local coordination creates many more release documents, while each
fixed event can batch multiple cells. Event counts are a communication/coordination
cost indicator, not independent observations or a benchmark of transport bytes.

The high semantic loss is real under this policy and population. Local releases
87,898 of 92,481 retained observations (95.0444%) as the Road User root, 4,266 as
Pedestrian, 40 as Cyclist, 163 as Adult Pedestrian and 114 as Child Pedestrian.
A source type can remain counted inside a generalized bin even when its specific
label is absent. The result does not mean that cyclist observations were all removed.
Per-input-type retention and published category totals are separate in the JSON.

## Fixed recipient queries

Queries count observation contributions for all ten taxonomy nodes. These nested
category queries are a declared task bank, not statistically independent traffic
measurements. Entire public cells and intervals must tile each query, with enough
semantic detail; private empty areas cannot close public holes.

The shared interior excludes EOF influence: `query_end + 1000 < 20000`. Every
interior reference is available. The following numbers are answered / total
queries at zero deadline lag. All interior counts are unchanged at lags 200 and
1,000 ms. The named fixed baseline matches the query's cell side and interval.
Both secondary priorities have the displayed common/local results.

| Query footprint / interval | Total | Matched fixed | Common adaptive | Local adaptive |
| --- | ---: | ---: | ---: | ---: |
| 5 m / 400 ms | 120,320 | 1,363 | 0 | 34 |
| 5 m / 1,000 ms | 46,080 | 749 | 11 | 0 |
| 10 m / 400 ms | 30,080 | 3,253 | 0 | 2,703 |
| 10 m / 1,000 ms | 11,520 | 1,242 | 1,237 | 4 |

For 10 m / 400 ms, fixed answers comprise 2,537 positive-reference and 716 known-zero
queries; local answers comprise 2,163 positive and 540 zero queries. For 5 m /
400 ms, fixed answers include 1,066 positive and 297 zero queries; all 34 local
answers have positive references. An answer count must not be described as an equal
number of positive traffic detections. Every adaptive answer set is a subset of
its matched fixed comparator in this pilot: there are no adaptive-only answers in
those pairings.

For the simpler **total Road User** query alone, 10 m / 400 ms coverage is
2,383/3,008 = **79.22%** for fixed, and 2,055/3,008 = **68.32%** for local. At
10 m / 1,000 ms, fixed achieves 939/1,152 = **81.51%**, common 934/1,152 =
**81.08%**, and local 4/1,152 = **0.35%**. This separates total-count utility
from finer category utility; pooling ten category levels can otherwise obscure it.

Every scorable exact answer has MAE 0. This is conditional accuracy under truthful
whole-support decoding, not perfect utility: unavailable answers remain unavailable,
and MAE is null when none can be scored. Boundary/EOF/censored results are retained
separately in the aggregate package and are not combined with the interior table.

### Why more waiting does not repair these queries

A 400-ms publication spanning [800,1200) crosses the boundary of [0,1000). Its
subinterval count cannot be reconstructed exactly from its total. Waiting another
second reveals more records but does not reveal that missing split. Fixed 400-ms
baselines also answer zero of these 1,000-ms exact queries. This limitation belongs
to the chosen exact-query/output contract and is not uniquely caused by local
coordination.

Similarly, a 10-m cell cannot exactly answer a 5-m query. Fine cells do not always
reconstruct a larger query either: missing or suppressed subcells leave unknown
space-time support. A complete occupied coarse cell can cover that footprint. No
unreported area is retrospectively certified empty, and no private GT is used to
improve recipient predictions.

## Verification and execution cost

- Existing complete regression run: **64/64 CTest entries passed**, 17.75 s.
- New audit: **30 Python tests** for counts/unions, exact source delay, truthful
  generalization, antichains, class stability, source nonreuse, bounds, malformed
  values, empty output and EOF.
- New runner: **20 Python tests** for matched requirements, fixed-output geometry
  and exact interval partition, pinned input hashes, source immutability, compact
  audit output, budgets, failures/timeouts, semantic repeat differences and the
  exact forty-evaluation/twenty-four-pair orchestration. All fifty tests passed on
  Python 3.9; both new CTest entries also passed with the configured Python 3.13.
- Build: existing Release `AggregationReplay` target is current. After registering
  the two new test entries, **7/7 relevant CTest entries passed**, 1.80 s.
  No production C++ implementation was modified in this gate.
- Ten independent scalar audits verify source accounting, cell geometry, support,
  hard scalar policy, scopes, retirement and public consistency. Ten independent
  semantic audits rebuild counts/unions, complete truthful cuts and loss/support
  bounds from indexed original rows. All have zero violations.
- Four adaptive determinism repeats match all fields except runtime. TF/SF
  secondaries agree after their secondary labels/configuration/runtime are excluded.
- Forty query evaluations and twenty-four pairs pass the original limits. Maximum
  indexed candidate work is 374,040 checks, below the 20-million limit.
- Separate handwritten reconstruction of five bounded query cases across four
  methods, without calling the query/audit functions, confirmed exact answers,
  unknown spatial/semantic support and certified zeros. Examples: cell 193
  [0,400) gives Road User 27; cell 819 at 5 m gives 15; a complete Pedestrian
  publication at cell 814 certifies Cyclist 0; cell 229 [800,1200) gives
  Pedestrian 31 while Adult Pedestrian stays unknown despite a private reference 20.
- The original capture's complete file hashes match before/after. All final study
  artifact hashes were verified again before producing the aggregate package.

Core processing is separate from simulated release delay. Common runs take
6.382–6.395 s for 20 s input (about 3.13x core-only speedup); local runs take
25.701–25.860 s (about **0.77–0.78x**). Local repeats take 25.601 and 25.878 s.
These runs therefore do **not** demonstrate real-time local throughput. Timing
includes native replay and in-memory serialization but excludes validation, file
I/O, live transport and the simulator. The workload is not a dedicated hardware
benchmark; there is no new optimization in this gate. Keep performance work visible
without confusing it with the conceptual query mismatch.

## Replay, provenance and reproduction

A new private replay is available at **http://127.0.0.1:8774/** while its server runs.
Title: `Matched policy: fixed versus adaptive | 500 initial Road Users | 400-1,000 ms`.
It contains fixed 10 m / 400 ms, local Semantic → Temporal, common Semantic →
Temporal, and fixed 10 m / 1,000 ms. The other secondary produces the same output
here and is retained in the experiment artifacts. Existing older replay servers
and source recordings remain unchanged.

The bundle validates successfully. Independent source-group checks pass for
14 sampled public cells across all four views. Chrome inspection at 400 ms confirms
500 recorded identities/positions and the fixed/local cell-193 count 27; at 8 s,
local historical cells retain their own intervals. The viewer is historical, not a
synchronized current occupancy map. Screenshots and the full private bundle remain
local and are not pushed. The generic viewer provenance line does not recognize
Simulator generation metadata; the source origin is established by the capture
hash and this protocol, not inferred from the run ID.

From the repository root, rerun into a **new** output directory:

```sh
python3 -B tools/evaluation/run_moving_scoped_comparison.py \
  --capture results/moving-replay-2026-10-21/n500/capture \
  --output results/moving-scoped-comparison-repeat

python3 -B tools/replay_viewer/serve.py \
  --bundle results/moving-scoped-viewer-2026-10-22 --port 8774
```

The frozen source recording is intentionally not in Git. A clone needs that local
capture to reproduce these exact results. The aggregate JSON is 524,679 bytes and
contains no movement rows, source identities or raw releases. It retains all
variant statistics, audit outcomes, interior category/positive/zero summaries,
boundary totals, and aggregate paired intersections; full boundary category and
paired category detail remain in ignored local study artifacts.

- Study directory: `results/moving-scoped-comparison-2026-10-22`.
- Manifest SHA256: `e81b724b673ac5f8e77ddd483b41b4ec2756206fbd32ccf2455e14bd234dc83f`.
- Input SHA256: `ab4fadf254bfb5432018ff4bd305cd16d82a7475ae3d934c14c4f9af67dd5cf1`.
- Binary SHA256: `0ade9da4b2ca424420ec8d045484b59ba2fa022a6f643f13d02ff6dd4155143e`.
- Frozen Python/protocol digests and all variant commands are recorded in the manifest.

## Requirements review and next gate

Verified for this gate: identical input, matched hard bounds including duration
minimum, distinct category support, intermediate truthful semantic tiers,
common/local ownership and complete source retirement, immutable nonoverlapping
public support, fixed-grid baseline behavior and deadline-aware recipient decoding.
The previous analytical regional-policy evidence remains separate; this uniform
moving-input pilot does not establish benefits for arbitrary regions or scenarios.

Before another optimizer or attack matrix, review the intended recipient task:
which temporal bins must be answerable, whether approximation is acceptable, and
whether an explicit public coverage statement is permissible. Publishing empty
coverage would disclose additional information and needs its own release/privacy
contract; it cannot simply be assumed free. A separately declared estimator would
need measured error and the same fixed query denominator. Neither change is made
here.

Then declare a bounded policy/scenario sensitivity study that tests where spatial,
temporal and semantic detail can genuinely vary, including failures. Keep this
pilot as an unchanged baseline. Privacy evaluation follows with a protected unit,
secret, auxiliary knowledge and recipient history tied to the actual released
product. Support compliance alone is not k-anonymity or measured attack resistance.
