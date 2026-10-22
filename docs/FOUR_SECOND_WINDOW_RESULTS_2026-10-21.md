# Four-second maximum windows: results and verification

Date: 2026-10-21. Allowing up to 4 seconds increases retained observations on
these frozen moving sources, including under the strict 5 m output-cell cap.
It also delays release and introduces error when a 4-second aggregate is used
to estimate 1-second occupancy. Spatial First and Semantic First still produce
identical public releases in all six new cap/population combinations. This is
a measured policy trade-off, not a demonstration that longer windows always
improve utility or that one strategy is universally better.

Protocol: [frozen four-second protocol](FOUR_SECOND_WINDOW_PROTOCOL_2026-10-21.md).
Commands and interpretation: [four-second replay guide](FOUR_SECOND_WINDOWS.md).
Matched earlier results: [1-second cell-cap study](CELL_SIZE_CAP_RESULTS_2026-10-21.md).

## Scope and implementation

Reuse the original verified 20-second captures of 200, 500 and 1000 initial
Road Users in the same 80 m x 80 m area, with seven existing behavior profiles,
50 ms integration, 100 ms observations and depth-6 finest cells of 1.25 m.
Every method within a population uses exactly the same source bytes. There is
no new motion generation, simulator execution, MongoDB access or ordinary
simulator configuration change.

The new experiment changes the maximum duration, maximum interval-start age
at evaluation and controller maximum together from 1000 to 4000 ms. Base
adaptive duration remains 400 ms, extended in 100 ms increments. The spatial
caps remain 5 m or 10 m, minimum distinct support remains 5 for each nonempty
published category, and semantic loss up to 1 remains allowed. Policies have
new identifiers; the old 1-second results and protocol are preserved.

History is 5000 ms/64 bins, with 100000 observations, 16 MB identity strings,
128 bucket descriptors, 64 temporal endpoint checks and 8192 spatial evaluations
per proposal. The 400..4000 ms schedule needs 37 endpoint checks. These bounded
resource changes allow the longer admissible windows; they do not add a new
release action or change the hard support threshold.

Each cap/population combination contains nine fixed controls (three legal
uniform grid sizes crossed with 400/1000/4000 ms) and the three adaptive
strategies. This gives **72 outputs plus six deterministic repeats**. The fixed
controls permit the same semantic generalization and use the same hard policy
checks. There is no causal ablation of type count in this experiment.

## Verification gate

- All 72 outputs passed independent scalar/source-accounting and semantic
  reconstruction audits, including distinct identity unions, complete truthful
  semantic cuts, nonoverlap, spatial caps, duration and age limits.
- The independent artifact checker verified **540 artifact hashes, six
  deterministic repeats, 36 matched old/new fixed-control pairs, 40239 public
  cells and 41554 public semantic bins**. Matching fixed controls retain their
  output after normalizing only runtime, embedded configuration, policy IDs
  and the changed duration/age upper bounds. Release IDs and measurements are
  retained in the comparison.
- **7/7 focused CTest entries passed in 6.39 seconds**. The dedicated new-window
  test contains nine methods and 23 actual C++ replay executions. This is not a
  claim that all 57 registered CTest entries were rerun.
- Resource exhaustion and unavailable history remain execution failures. They
  are not converted into policy suppression. The executed sources, policies,
  binary, commands, audits and hashes are recorded in each bundle manifest.

The predeclared protocol remains immutable. Deterministic reruns verify one
frozen input; they are not independent simulation replications.

## Matched Spatial First results

The task remains mean sampled all-road-user occupancy on **10 m squares and
1-second intervals**. Eventual results use 1280 queries. Deadline results use
the unchanged 1152-query interior cohort, with query end + 1000 ms strictly
before the source horizon; 128 boundary queries remain separate. Deadline 0
means release by the query end, not zero execution latency.

Retention counts source observation contributions, not unique people or
preserved attributes. MAE is conditional on answered queries and measured in
Road Users. Missing support remains unknown. Values below floating-point
precision are shown as approximately zero; unavailable MAE is not zero.
Age is observation-weighted logical interval-start age at sealing.

### Primary 5 m output-cell cap

| Initial Road Users | Maximum window (s) | Retained (%) | Eventual coverage (%) | Eventual MAE | Deadline-0 coverage (%) | Deadline-0 MAE | Mean age (s) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 200 | 1 | 4.95 | 0.00 | unavailable | 0.00 | unavailable | 1.00 |
| 200 | 4 | 10.90 | 0.00 | unavailable | 0.00 | unavailable | 4.00 |
| 500 | 1 | 28.31 | 0.00 | unavailable | 0.00 | unavailable | 1.00 |
| 500 | 4 | 49.26 | 3.44 | 0.842 | 0.87 | 1.100 | 4.00 |
| 1000 | 1 | 65.48 | 7.81 | approximately 0 | 7.47 | approximately 0 | 1.00 |
| 1000 | 4 | 81.66 | 28.44 | 0.801 | 6.51 | 1.044 | 4.00 |

At N=500 the longer limit raises retention by **20.95 percentage points**, but
only 44/1280 eventual queries and 10/1152 deadline-0 queries become answerable.
Many additional retained tiles still do not complete an entire 10 m/1-second
query footprint. At N=1000, eventual coverage rises by 20.63 percentage points,
yet deadline-0 coverage falls and conditional error increases. The additional
availability arrives later and has coarser temporal information.

At N=200, retention more than doubles but no complete occupancy query becomes
answerable. This is useful evidence that retained observations and task
availability are different quantities. It is not sufficient to report only
retention or sound release checks.

### Contextual 10 m output-cell cap

| Initial Road Users | Maximum window (s) | Retained (%) | Eventual coverage (%) | Eventual MAE | Deadline-0 coverage (%) | Deadline-0 MAE | Mean age (s) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 200 | 1 | 57.31 | 28.91 | approximately 0 | 29.17 | approximately 0 | 1.00 |
| 200 | 4 | 73.90 | 45.63 | 0.589 | 10.68 | 0.741 | 4.00 |
| 500 | 1 | 93.91 | 80.78 | approximately 0 | 81.08 | approximately 0 | 1.00 |
| 500 | 4 | 96.16 | 85.63 | 0.639 | 19.27 | 0.801 | 4.00 |
| 1000 | 1 | 99.85 | 98.36 | approximately 0 | 98.52 | approximately 0 | 1.00 |
| 1000 | 4 | 99.90 | 99.06 | 0.688 | 22.14 | 0.891 | 4.00 |

The N=500/10 m case is a particularly clear latency cost: the small retention
gain of 2.25 percentage points accompanies a fall in deadline-0 coverage from
81.08% to 19.27%. Eventual and deadline percentages use different declared
cohorts, so compare each column across policies rather than subtracting the two
columns as if their denominators were identical. The 200/1000 ms deadline
results remain available in each `deadline-occupancy.json`; the primary bank
and cohort have not been relaxed to make longer windows look favorable.

A 1-second aggregate aligned to the 1-second query can yield an essentially
exact estimate on supported tiles. A 4-second aggregate only supplies a longer
interval mean. The estimator's declared temporal-constancy assumption then
loses changes within the interval, explaining nonzero 1-second query error.
This is an information-loss trade-off, not a failed support check.

## Why the priority outputs can coincide

The present study uses **common windows**, rather than independently sealed
cell-local semantic windows. Before a terminal endpoint, the controller seals
a window early only if its relevant complete cut meets the strategy's release
condition. Passing parts are not immediately published while other observed
parts remain unresolved. At the time cap, a valid partial cut can be released
and the unresolved observations suppressed.

For Semantic First the early preferred cut must additionally preserve zero
declared semantic loss. At a terminal endpoint it considers the allowed
positive loss levels, preferring a complete cut where possible and otherwise
using the documented retention-first partial fallback. The original hard
Policy Tree checks still apply. A selected ceiling is a private search
preference; it is not evidence that every bin uses that loss. Empty cuts also
must not be interpreted as nonempty root generalizations.

On these sources and tight caps, early complete cuts are often unavailable.
Spatial First and Semantic First both reach the 4-second terminal endpoints
and select the same surviving public representation. Their complete public
`releases` arrays are equal in every one of the six new combinations; their
private decision traces and strategy metadata remain different. All three
strategies coincide at the 5 m cap. At the 10 m cap they also all coincide for
N=200 and N=500.

The exception is Temporal First at N=1000/10 m:

| Strategy, 4 s maximum | Retained (%) | Eventual coverage (%) | Eventual MAE | Deadline-0 coverage (%) | Mean side (m) | Mean semantic loss | Mean age (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Temporal First | 99.864 | 97.97 | 0.227 | 32.90 | 9.077 | 0.931 | 1.568 |
| Spatial First | 99.896 | 99.06 | 0.688 | 22.14 | 8.082 | 0.917 | 4.000 |
| Semantic First | 99.896 | 99.06 | 0.688 | 22.14 | 8.082 | 0.917 | 4.000 |

Temporal First can seal some full spatial cuts earlier, so its actual mean age
is well below the permitted maximum. The other two retain slightly more and
use finer mean spatial detail, with longer age and higher conditional occupancy
error. None of these columns alone defines a universal winner.

For the 5 m cap, each adaptive strategy's public releases also equal the fixed
5 m/4000 ms control on all three sources. Thus **this bounded cap study shows
no adaptive advantage over that fixed control**. It identifies a regime where
the permitted options collapse to the same outcome. Smaller fixed grids retain
less, but selecting only those as the comparator would hide this result.
These observations motivate studying the common-window gating and heterogeneous
local requirements separately; they do not prove that priority never matters.

## Do seven types cause the low support?

Seven profiles make exact class detail harder to retain, especially for rare
classes. They do **not** require 5 x 7 = 35 Road Users in each output cell. The
support condition is applied only to nonempty categories in the published
semantic antichain. With maximum semantic loss 1, all profiles can be pooled
truthfully into the Road User root. That bin needs five distinct Road Users,
regardless of their input mix.

Longer windows help when additional identities enter the same spatial support.
Repeated samples of an existing identity do not increase distinct support.
They cannot rescue a cell that never obtains five distinct Road Users within
any permitted interval and spatial merge. The slightly lower mean semantic
loss at 5 m/4 seconds (0.935 for N=500, versus 0.963 at 1 second) is compatible
with some better-supported category groups; it is not a measured privacy gain.

The type distribution is unchanged in this paired experiment. It therefore
cannot establish how much of the result is caused by having seven profiles.
A separate controlled type ablation would hold XY trajectories and identities
fixed while changing only the release labels/taxonomy and declaring its task.
No behavioral relabeling, fabricated class or new sensitive attribute is used
here.

## Reproduction and presentation use

Use `--max-window-ms 4000` with `--max-cell-side-m 5` or `10`, the already
verified capture and a new output directory. See the [replay guide](FOUR_SECOND_WINDOWS.md).
Each bundle is under
`results/window-duration-2026-10-21/window4000/cap<CAP>/n<N>/comparison`;
its `summary.json`, per-method query files, `audit.json` and `manifest.json`
provide the unrounded results and provenance.

For the 20-minute presentation, one direct 1-second/4-second comparison is
sufficient: **the same movements and support rule allow more retained data
when more delay is permitted, but a fine and timely traffic query can still
lose availability or accuracy**. State the spatial cap and fixed task first.
Show coverage with error and age, including the unfavorable deadline result.
Do not present a larger retained fraction as an established privacy gain.

There remains one stochastic source per population, uniform initialization,
20 seconds of motion, no replenishment, no local policy overrides and no
class-specific query workload in this experiment. Operational category support
is not a formal anonymity guarantee or empirical attack-risk measurement.
Logical age is not sensor-to-application latency. Statistical superiority,
formal privacy, global scheduling optimality, realistic maps and externally
comparable LDP guarantees remain outside this result.

## Archived verification and visual inspection

The independent checker and its JSON report are archived under
`results/window-duration-2026-10-21/verification/`. This directory also contains
the focused CTest log, the exact nine-method regression file, the source-data
diagnosis script/JSON and the paired-bundle/figure assembly script. The
`previous-studies-unchanged.json` check confirms all 269 original pilot and
482 previous cap-study artifact hashes remain unchanged. Individual manifests
freeze their executed runner, auditors, policy, protocol and replay binary.

All six individual method portfolios and all three paired replay bundles
validate. The paired `viewer-n200`, `viewer-n500` and `viewer-n1000` bundles each
contain 12 actual adaptive outputs: both time limits, both caps and all three
priorities. `public-release-equality.json` records exact SF/Semantic equality
in all 12 old/new cap/population pairs; `paired-adaptive-summary.csv` preserves
the unrounded adaptive metrics for all 36 matched entries. The all-method
tables remain available in each individual comparison directory.

Browser QA opened the 500-user paired bundle at simulation time 8 s with
private finalized diagnostics enabled. The left result covers [7,8), the
right [4,8); both have maximum side 5 m and the inspector visibly confirms
1000 versus 4000 ms duration/age bounds. The longer result retains more cells
for its historical interval; it is not a current 100-ms snapshot. Saved
fallback: [paired window replay](figures/windows-500-at8s-2026-10-21.jpg).
Scientific figure: [window trade-offs](../results/window-duration-2026-10-21/window-tradeoffs.png),
with an [SVG export](../results/window-duration-2026-10-21/window-tradeoffs.svg).
