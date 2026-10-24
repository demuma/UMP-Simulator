# Strategy, timing and heterogeneous policy results — 25 October 2026

## Evidence status

The [predeclared protocol](STRATEGY_TIMING_LOCAL_POLICY_PROTOCOL_2026-10-25.md)
uses unchanged recorded inputs and the corrected executable. All 28 strategy/
long-window cases are independently verified. All nine paced-study invocations are recorded: eight validated executions and
one measured bounded-queue failure. All 44 paired regional-policy executions
and eight derived static regional utility controls are independently verified.
No engine source was changed during this sequence.

Generated movement and complete native outputs remain local and ignored. The
Git evidence package contains aggregate results, exact policies and receipts.

## A stronger fixed-window comparison changes the Original-policy claim

Fixed 5/10/20 m grids now cover 0.4, 1, 2 and 4 s. Long windows still obey every
local duration/age bound; Original 20 m remains an explicit rejection control.
Selective contribution suppression is OFF throughout this extension.

| Source / policy | Highest-retention adaptive | Retained (%) | Best fixed retention | Retained (%) | Adaptive / fixed J (%) |
| --- | --- | ---: | --- | ---: | ---: |
| Mixed / Original | Spatial First | 40.269 | 10 m / 4 s | 40.267 | 85.075 / 85.736 |
| Pedestrians / Original | Spatial First | 41.439 | 10 m / 4 s | 39.626 | 79.280 / 80.187 |
| Mixed / Spatial20 | Semantic First or Temporal First | 63.956 | 20 m / 0.4 s | 50.660 | 76.684 / 81.804 |
| Pedestrians / Spatial20 | Semantic First or Temporal First | 77.889 | 20 m / 1 s | 75.688 | 57.073 / 58.102 |

The table reports J for Semantic First in the final row: Temporal First has the
same retention but J=57.303%, slightly worse semantic loss and slightly finer
mean cells. Lower J is better. J assigns unit loss to every omitted input and
adds taxonomy loss for retained contributions, divided by the complete input.
It is a utility/distortion measure, not an attack-based privacy measure.

The stronger baseline nearly eliminates the Original mixed-source retention
advantage: 0.0024 percentage points is operationally negligible in this one
recording. The adaptive spatial representation is slightly finer and its J is
lower, but its mean delay remains about 2 s, close to the 4-s fixed control.
Temporal/Semantic First trade 0.323 points of Original mixed retention for a
mean delay of 558 ms instead of 2040 ms and lower J. Spatial20 retains a clearer advantage: +13.296 percentage points on mixed
traffic and +2.201 points on pedestrians for the best adaptive retention.
These are within-recording findings, not significance estimates across seeds.

Standalone Temporal First duplicates the Semantic First aggregate metrics on
three of the four source/policy pairs. On pedestrian Spatial20 it produces the
same counts and delay but a different semantic/spatial choice. The semantic
priority therefore has a small observable effect here, not a universal effect:
Semantic First retains 7173 exact-subtype contributions versus 6758 for Temporal
First in pedestrian Spatial20, with identical total retained count.
Policy-satisfied publication can resolve both strategies before their different
preferences matter. Naming continues to describe retained detail: Temporal First
preserves temporal detail and admits spatial aggregation before waiting.

Larger fixed windows do not necessarily retain more. A 2/4-s global schedule
cannot publish cells intersecting a 1-s local maximum. A finer short-window
schedule can therefore publish where a longer schedule must suppress. No fixed
variant receives an exemption from the Policy Tree.

The [complete method tables](verification/strategy-window-extension-2026-10-25/report.md) include retained-only semantic loss, mean cell size,
mean interval, delay tails and core time. A higher retained count can coexist
with coarser semantics, slower publication or more computation. Empty output has
zero retention and J=1; retained-only means and delay are undefined.

## Paced processing: two completed sources and one failed dense gate

The first full 300-s mixed-source run completes at 1x rate and queue capacity 8,
with exact public-output and complete typed retirement/release digest equality
to its independently audited unpaced control. Peak pending queue depth is one.
All 82,033 input contributions are accounted for.

For 5999 positive progress ticks before EOF, service mean/p95/p99/max is
8.104/35.756/43.363/56.171 ms. Scheduled-arrival-to-completion is
15.533/44.816/53.199/66.202 ms. There are 122/5999 (2.03%) response misses at the
50-ms cadence; all 2999 sensor steps meet the separate 100-ms response limit.
Only 12 service spans exceed 50 ms: response also includes producer scheduling
lateness and queue wait. Mean scheduling lateness is 7.382 ms; queue-wait mean
is 0.047 ms, sampled maximum 9.978 ms.

The consumer is busy for 48.622 s over the 300.012-s paced horizon. The unpaced
minimal control takes 31.545 s. These are distinct operating conditions, not a
claim that event service equals an unpaced whole-run average. Mean release
readiness-to-in-memory-ack delay is 31.744 ms, p95 40.253 ms, maximum 43.582 ms.
This is extra processing/scheduling delay after the intentional aggregation
interval; it is not the 320-ms observation-to-logical-release metric above.

Measurement includes per-step manager processing, typed debug hashing,
in-memory serialization and telemetry. Preloading, input parsing, core startup,
perception/inference, observation-to-leaf assignment, external transport/MongoDB,
renderer and final top-level output writing are outside the measured event
service boundary. EOF is separate; origin-zero setup is excluded from positive
progress-event sums. One observed successful run with deadline misses does not
establish hard real-time behavior.

| Source | Planned horizon | Complete paced output? | Peak queue | Service mean / p95 / max (ms) | Response p95 / max (ms) | 50-ms response misses | 100-ms sensor misses |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Current mixed | 300 s | Yes, exact control equality | 1 | 8.104 / 35.756 / 56.171 | 44.816 / 66.202 | 122 / 5999 | 0 / 2999 |
| Current pedestrians | 300 s | Yes, exact control equality | 1 | 8.136 / 33.099 / 63.108 | 42.712 / 73.139 | 64 / 5999 | 0 / 2999 |
| Historical dense source | 240 s | No: overflow at logical 26.85 s | 8 | 27.711 / 84.181 / 140.796 (prefix) | 213.510 / 470.493 (prefix) | 188 / 528 completed | 43 / 264 completed |

The dense failure has 536 enqueued events, 528 completed and eight pending or
uncompleted when logical 26,850 ms is rejected, from 4800 scheduled events.
Whole-run equality and complete latency/accounting claims are unavailable for
that cancelled run. Its new full unpaced control separately passes independent
raw-input/retirement/semantic/policy verification for all 187,745 observations
and 3202 public cells. Full/minimal controls have identical public fields and
complete decision digests; minimal unpaced processing is 121.116 s. The exact
historical input/policy hashes and queue/clock contract are unchanged. The older
failed trial also rejected logical 26.85 s after 528 completions. Prefix timing
fluctuations do not demonstrate a performance improvement on this dense gate.

The new dense failure spends 14,630.6 ms in inclusive consume spans, of which
211.95 ms is inclusive terminal work (1.45%). Private-window JSON is disabled;
public serialization is 8.54 ms and decision hashing 162.25 ms. These inclusive
spans overlap and must not be summed. Most cost remains in manager/history/
coordination/selection processing outside terminal callbacks. Debug hashing is
still enabled, so this is a measured failure of this instrumented adapter;
it does not prove that an optimized production implementation cannot meet a
specified load/deadline contract.

Current mixed/pedestrian process lifetime peak RSS is about 533/487 MiB,
including input parsing and retained diagnostics; sampled resident maxima are
about 96/88 MiB. Sampled history identity bytes are below 0.5 MiB in each, with
7637/7690 observations retained at peak. These counters describe different
memory scopes; history counts alone are not a total memory bound. Only the two
completed current runs have whole-run memory/release telemetry.

The [compact timing package](verification/current-paced-2026-10-25/study-summary.json)
preserves every case and the exact failed-gate contrast. This repeated-source
study measures the aggregator adapter after detections/tracks/leaf assignments;
it does not certify live sensing or external database delivery. The historical
dense source has previously disclosed boundary-observability limitations, so
it is used here as a fixed input-load gate rather than a new GT-completeness
claim. The two current sources have peaks of 126/127 active road users; their
success must not be generalized to higher density or another Policy Tree.

## Local freshness: what adaptivity adds beyond a regional fixed schedule

The control removes the west/east 1-s time/age maxima but retains every other
Spatial20 metric bound. The treatment adds window and logical age maxima of
400 ms to the existing central-through-footway rectangle `(40,50,20,12.5)` m.
This is one freshness factor represented by two linked bounds, not a change to
support thresholds or taxonomy. The 250-square-meter region is 3.90625% of the
80-by-80-meter domain. Root bounds remain 0.4–4 s, 1.25–20 m, total/category
support at least five, semantic loss at most one and selective suppression zero.
The entrance requires total support ten; west/central/east retain semantic loss
at most 0.5. Every method receives the same hard constraints within each policy.

Whole-cell positive-area intersection determines effective constraints. The
central rectangle intersects two 20-m cells (800 square meters) or four 10-m
cells (400 square meters). Thus an observation outside the rectangle can still
inherit its constraint through a coarse output footprint. This is the declared
policy semantics for all methods; point-region cohorts are reporting groups.

The static regional reference fixes grid and per-cell schedule before reading
motion. For each cell it chooses the longest admissible member of
`{400,1000,2000,4000}` ms from public size/duration/age/delay bounds. Control uses
4 s everywhere. Treatment uses 0.4 s in intersecting cells and 4 s elsewhere.
Each original observation belongs to exactly one cell/half-open interval.
Every nonempty group must match a private record from its chosen independently
audited native fixed run; publication, support, semantics, coverage and all hard
bounds are independently recomputed. Uniform controls exactly reproduce native
4-s utility, per-type/per-region counts and delay. Empty groups are explicitly
covered by the complete mathematical space-time partition.

This is derived utility for a predeclared policy-only schedule, not a new online
implementation. Runtime is `null`; no sum of four separate runtimes is reported.
Choosing the longest feasible window is not a claim of optimal static utility.

| Source / policy | Method | Retained (%) | J (%) | Retained semantic loss (%) | Mean delay (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| Mixed / control | Semantic First | 65.419 | 76.066 | 63.415 | 340.104 |
| Mixed / control | Best global fixed: 20 m / 4 s | 55.218 | 80.399 | 64.503 | 2051.917 |
| Mixed / local400 | Semantic First | 64.887 | 76.161 | 63.261 | 345.547 |
| Mixed / local400 | Best global fixed: 20 m / 0.4 s | 50.660 | 81.804 | 64.083 | 250.039 |
| Mixed / local400 | Static regional 20 m (derived) | 54.110 | 81.265 | 65.377 | 1876.401 |
| Pedestrians / control | Semantic First | 78.611 | 56.712 | 44.933 | 311.124 |
| Pedestrians / control | Best global fixed: 20 m / 4 s | 81.024 | 53.408 | 42.496 | 2049.640 |
| Pedestrians / local400 | Semantic First | 78.316 | 56.859 | 44.914 | 305.796 |
| Pedestrians / local400 | Best global fixed: 20 m / 0.4 s | 74.306 | 58.931 | 44.730 | 250.038 |
| Pedestrians / local400 | Static regional 20 m (derived) | 80.654 | 54.625 | 43.742 | 1748.213 |

On mixed treatment data, Semantic First improves retention by 10.777 percentage
points and reduces J by 5.105 points against the stronger static regional 20-m
schedule, while releasing earlier. This demonstrates value beyond regional
window flexibility within this declared comparator family and realization.
The comparison also includes adaptive spatial sizes versus a uniform static
size; it does not isolate the causal value of data-dependent decisions. Static
regional mixtures of spatial sizes and other policy-only cadences remain untested.

On pedestrian treatment data, the static regional schedule retains 2.338 points
more and has J lower by 2.233 points. Semantic First instead releases about
1442 ms earlier on average. Its mean spatial cell size is also slightly finer.
Consequently, a general claim that adaptivity improves retention or semantic
utility is not supported. A comparison using only global schedules would have
hidden this counterexample. Native fixed execution is much cheaper than adaptive
execution; the derived scheduler itself has no timing measurement.

The 400-ms cap reduces Semantic First retention by only 0.531 points (mixed)
and 0.294 points (pedestrians), versus 6.302/13.824 points for global Fixed20/4.
The regional static schedule absorbs most of that fixed-grid loss too:
-1.108/-0.370 points. Spatial First even improves pedestrian retention from
74.889% to 76.980% under the stricter local policy, while reducing J. A changed
constraint can alter coordination and partition choices; algorithm outcomes
need not be monotone even though the set of legal products becomes smaller.

The measurements are consistent with the declared immediate-release rule:
a currently valid product may be emitted before later arrivals could improve
support, taxonomy detail or merge opportunities. They do not independently
attribute every lost contribution to that rule. Proving that causal mechanism
would require dedicated decision traces or an ablation, not just these totals.
Semantic First ranks available representations; it does not guarantee minimum
whole-stream J or intentionally wait whenever future semantics might improve.

Point-region counts expose spillover: mixed Semantic First loses 460 central
contributions but gains 121 in the east cohort and loses 97 outside all regions,
for a net loss of 436. The pedestrian counterpart loses 264 centrally and one
outside. Global Fixed20/4 loses 3077 central plus 2093 outside contributions on
mixed data, and 10,146 central plus 2302 outside on pedestrians. The static20
schedule reduces those losses to 272+637 and 301+32 respectively. Cohorts can
overlap in general and must not be summed indiscriminately. These counts locate
effects; attributing the adaptive east change requires a decision trace.

The [44-case tables and paired cohort deltas](verification/temporal-region-study-2026-10-25/report.md)
and [eight regional static controls](verification/static-regional-schedule-2026-10-25/report.md)
retain all variants, including both 10-m and 20-m references. These exploratory
requirements were chosen after earlier examination of these sources. They are
not independently validated application/privacy thresholds. The two source
recordings differ in motion as well as class mix, so their contrasting outcomes
do not isolate a causal effect of class diversity. Logical age ≤400 ms
is not a wall-clock delivery guarantee; Phase-2 timing uses its own unchanged
policy and cannot certify this new policy's load.

## Figures and presentation claim

Three figures include exact plotted data, input hashes and a reproducible generator:

- [Strategy/fixed-window comparison](verification/strategy-policy-figures-2026-10-25/strategy-retention-distortion.svg).
- [Retention under local freshness](verification/strategy-policy-figures-2026-10-25/temporal-region-retention.svg).
- [Full-input semantic distortion](verification/strategy-policy-figures-2026-10-25/temporal-region-full-input-loss.svg).

PNG copies support direct slide insertion; SVG copies preserve vector quality.
These show measured points/bars, not regressions or interpolated performance.
A defensible presentation statement is: **The mechanism releases products that
satisfy regional metric constraints and exposes a measurable tradeoff among
retention, semantic detail, spatial resolution, delay and processing cost. It
retains more mixed-source observations with lower full-input semantic
distortion and lower delay than the regional 20-m reference, while that
reference retains more pedestrian data at substantially greater delay.**
This is a tested mechanism/utility result, not a proof of universal optimality
or an empirical privacy-gain claim.

## Verification and interpretation limits

Every new Phase-1 result passes independent full-input accounting, source/leaf
geometry, semantic category/support and hard-policy recomputation with an
explicit one-million-cell audit limit. Historical fixed and corrected adaptive
references retain separate source/config/result/binary receipts. Reference
runtime recordings are not paired speed comparisons with this extension.

Operational support is counted using distinct visible observation-track IDs.
It is not a proof of general k-anonymity, identity protection, l-diversity or
resistance to inference from a published stream. No attack-based privacy gain
is established by these experiments. Application-specific privacy-model experiments remain a separate step; the
existing [controlled synthetic E02 implementation](EMPIRICAL_PRIVACY_IMPLEMENTATION.md)
and its evidence are preserved and are not results of this new matrix.
