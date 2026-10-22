# Semantic First: controlled old/new comparison

Date: 2026-10-21. Status: first common-window Semantic First controller implemented
and verified. [Algorithm contract](SEMANTIC_FIRST_IMPLEMENTATION.md),
[test report](SEMANTIC_FIRST_TEST_REPORT_2026-10-21.md),
[runnable examples](../simulator/examples/semantic-first/README.md).

## Result

Semantic First now prioritizes declared semantic accuracy, with Temporal First as its
fixed secondary priority. At each observed endpoint it seeks a full zero-cost spatial
cut before waiting. If no such output exists by a terminal endpoint, it tries the
catalog's positive loss levels in ascending order under the ORIGINAL hard requirements.
The default simulator configuration and existing modes are unchanged.

The 27-case comparison reuses the exact three static-density source files from the
[earlier 18-case example](SEMANTIC_FIRST_AND_DENSITY_2026-10-21.md). It crosses three
densities, three hard loss maxima and three strategies (TF, SF, Semantic First). Every
triplet uses identical numeric requirements, catalog, observations and cadence; only
execution strategy/provenance changes. This is a deterministic mechanism experiment,
not population sampling or a new privacy study.

The four occupied 20 m leaves each contain 2m Pedestrian, m AdultCyclist and m ChildCyclist,
with m=1/2/5 and the same identities at every sample. The occupied domain is their 40 m
parent within an 80 m depth-2 grid. Samples occur every 100 ms from 100 to 2300 ms; horizon
2400 ms. Category minimum 5, maximum side 40 m, base window 400 ms and maximum age/duration
800 ms are fixed. Production depth 6 is unchanged. All category counts below are distinct
road users; observation counts additionally depend on samples/window duration.

## Same hard loss maximum 1

| Density | Strategy | First interval end | Output side | Maximum / mean semantic loss | Exact 400-ms query coverage 20 m /40 m |
|---|---|---:|---:|---:|---:|
| Low, 16 road users | TF | 400 ms | 40 m | 0.5 / 0.25 | 0% / 50% |
| Low | SF | 800 ms | 40 m | 0.5 / 0.25 | 0% / 0% |
| Low | Semantic First | 800 ms | 40 m | 0.5 / 0.25 | 0% / 0% |
| Medium, 32 road users | TF or SF | 400 ms | 20 m | 1 / 1 | 25% / 25% |
| Medium | Semantic First | 400 ms | 40 m | 0 / 0 | 0% / 100% |
| High, 80 road users | All three | 400 ms | 20 m | 0 / 0 | 100% / 100% |

Every feasible case retains 100% of source observation contributions. Low density with
hard loss maximum 0 remains infeasible for all three strategies and emits no public data.
The generalization preference never weakens that bound. At hard maxima 0 or 0.5, medium
density uses exact parent classes for all strategies; Semantic First and TF release at
400 ms while SF waits to 800 ms. At high density all three remain exact/fine at 400 ms.

### Medium density: intended changed choice

For the first [0,400) interval, every fine leaf has supports 4/2/2 and eight road users.
Ordinary TF/SF can meet category minimum 5 by saying RoadUser 8 per 20 m leaf, so they stop
there. Semantic First instead discovers a legal 40 m parent with supports Pedestrian 16,
AdultCyclist 8 and ChildCyclist 8. The public observation bins are 48/24/24; all 96 original
observations remain represented. It releases immediately with maximum/mean loss 0.

The difference is useful for the predefined 40 m class-count task: coverage increases
from 25% to 100%. The predefined 20 m task instead loses coverage from 25% to 0%, because
exact fine spatial counts cannot be recovered from the parent. Semantic First performs
its declared preference; it is not uniformly more useful for every application.

### Low density: explicit waiting cost

Every leaf has only four different road users. A parent can represent eight pedestrians
and eight cyclists at maximum loss 0.5, but no zero-cost full representation is possible
with these static identities. Semantic First waits until 800 ms, then selects that 0.5
representation rather than a higher-loss root representation. TF can already release
the same class/space detail at 400 ms. The extra delay has no representational benefit
in this particular static source. New people can change that trade-off; the independent
turnover acceptance test verifies early zero-loss release once those people are observed.

The exact 400-ms query bank cannot split an 800-ms count. Those unknown answers are not
interpreted as zero traffic or proof that an 800-ms representation has no usefulness.
The 800-ms query bank remains separately available in the artifacts.

## What semantic accuracy means in this first mode

The primary preference is maximum declared category loss, not mean loss. Mean loss
remains reported and enforced wherever it has a hard bound. A native counterexample
keeps 315 observations in either representation but changes maximum/mean loss from
1 / 0.04762 to 0.5 / 0.48095. Reducing the worst loss can increase average information loss.
The test records both values and prevents silently describing this mode as a mean-loss
or universal utility optimizer. A hard mean bound can reject the preferred maximum-loss
alternative and remains binding.

If no full cut exists at any tested ceiling, the mode deliberately retains the largest
observation total among its assessed partial cuts, then prefers lower actual maximum
loss and finer weighted spatial support. That retention-first exception is part of the
contract; it is not global search over every possible mixed-depth/semantic combination.

## Verification and artifacts

All 27 actual executions pass independent raw scalar audits. Every one of 135 actual
retired intervals matches a legal independently enumerated same-interval category/spatial
cut. Nine intervals have no nonempty legal cut at their actual endpoints. None of the
actual choices is dominated on all six declared conditional criteria; this does not
prove global online scheduling optimality. All 18 prior TF/SF outputs match the earlier
18-case experiment byte-for-byte outside runtime.

The fixed receiver bank is unchanged: four class counts, 20/40 m target geometry,
400/800-ms windows, deadlines at end plus 0/400 ms, fixed interior and separate boundary/
EOF/censored cohorts. Predictions use recipient output only. Missing cells, crossing
aggregate supports and straddling categories are unknown under the declared conservative
exact-answer rule. Answered-only zero error is a correctness check, not sufficient
usefulness by itself. Source observations never fill recipient holes.

[Manifest](../results/semantic-first-2026-10-21/manifest.json),
[summary](../results/semantic-first-2026-10-21/summary.json),
[compact table](../results/semantic-first-2026-10-21/table.json) and
[independent verification](../results/semantic-first-2026-10-21/verification.json)
preserve 182 checked artifact hashes, frozen sources/binary, protocol, identical inputs,
all policies, raw outputs and audits. Configuration files were written before core calls.
The six fixture files in the example directory match those recorded in the manifest.

The controller uses only observations available at each evaluation. No new maps, motion
planner, tracking-error model, membership attack, public revision or cell-local semantic
coordination was added. Support thresholds and loss measures are quantitative operational
outcomes; these results establish no new empirical privacy gain or end-to-end latency.
Review the task and waiting trade-offs before implementing another priority combination.
