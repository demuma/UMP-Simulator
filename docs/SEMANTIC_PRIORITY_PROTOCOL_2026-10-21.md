# Semantic candidate choice and constraint impact: bounded protocol

Date: 2026-10-21. Protocol fixed before running the study. This is the first bounded
E07/A08 decision-order review, not a new controller or empirical privacy experiment.

## Question and comparison contract

Which truthful spatial/semantic alternatives satisfy the same regional constraints at
an actual decision, and what application-query detail does the current semantic-first
ordering retain or lose? Separate legal-output feasibility from mechanism choice.
A quantity called support counts distinct contributing road users in a cell/window or
category; it does not assert simultaneous presence or trajectory-level k-anonymity.

Freeze each observation stream before varying policy. Use the real AggregationReplay
common-window Temporal First and Spatial First controllers with A07 enabled. Never relax
a failed bound. Do not change the C++ controller, select a new weighted objective, run
membership attacks, alter maps or optimize computation in this step.

## Declared matrix and fixtures

Five deterministic mechanism scenarios use a public 100-ms schedule, an 80 m square
at depth 2 and a single 40 m quadrant with four 20 m leaves (IDs 48 through 51).
The horizon is 2400 ms; t=0 is initialization; measured samples occur at 100..2300 ms.
All four leaves are occupied at every sample. Stable identities/types are explicit.

1. Dense exact: each leaf has five pedestrians, five adult cyclists and five child
   cyclists, with the same identities at each sample.
2. Rare local type: leaf 48 has 19 pedestrians and one adult cyclist; leaf 49 has five
   other adult cyclists; leaves 50 and 51 each have five pedestrians.
3. Temporal turnover: each leaf has 19 fixed pedestrians and one adult cyclist with
   a new identity at every sample. New people, not repeated samples, increase support.
4. Infeasible support: one persistent pedestrian in each leaf; the parent has only
   four different road users despite repeated measurements.
5. Regional detail: the rare-local source, with an additional zero maximum semantic
   loss requirement over leaf 48. Its strict bound also applies to the parent footprint.

Vary exactly three category-support minima (2, 4, 5), three maximum semantic losses
(0, 0.5, 1), two maximum cell sides (20, 40 m), two maximum durations/ages (400, 800 ms)
and two preservation strategies. The base window is 400 ms, extension step 100 ms;
minimum data-cell depth is 1. This yields 360 paired-source executions, not 360 random
replicates. The catalog has exact-terminal loss 0, Cyclist loss 0.5 and RoadUser loss 1.
Each policy has a distinct recorded version. Repeat every thirtieth run exactly, giving
12 deterministic before/after-output checks excluding runtime only.

## Two different measurements

### Conditional candidate reference

For each actual retired interval [s,e), enumerate at that actual evaluation time all
allowed spatial cuts in the occupied quadrant: one parent OR any subset of leaves,
including whole-cell suppression. For each selected spatial cell enumerate all complete
nonoverlapping semantic antichains of observed categories. No observation in a selected
cell may disappear. Recompute exact identity unions and all scalar/semantic requirements
from the same original observations; intersect regional constraints for the whole cell.
The production release must match one admissible candidate, including its actual counts.

Compare retention, exact class-query coverage at 20/40 m, semantic loss and spatial detail
as separate objectives. Retain nondominated candidates rather than choosing arbitrary
weights. Empty output is not useful merely because its constraints hold. Reference
budgets fail explicitly. Invalid/missing evidence is distinct from a policy with no
nonempty legal output. The reference uses the SAME actual interval, evaluation time
and already retired start; it neither consumes future observations nor changes earlier
committed releases. It does not optimize window endpoints or a complete online schedule.
Scores conditional on different retired intervals are not directly comparable.

### Fixed receiver queries across full runs

Predeclare the same query bank for every variant: observation counts for RoadUser,
Cyclist, AdultCyclist and ChildCyclist, at each of the four 20 m leaves and their 40 m
parent, over fixed 400/800-ms windows. Evaluate deadlines at query end plus 0/400 ms.
The primary cohort obeys end + largest lag < observation horizon; report other windows
separately, mark deadlines at EOF and censor deadlines beyond the horizon.

Use only immutable recipient releases sealed by the deadline. Sum contributions only
from complete public spatial/time partitions whose aggregate supports fit wholly inside
the query. A crossing cell/window is not proportionally split. Every scheduled sample
and spatial tile needs complete public support. Absent/suppressed coverage is unknown;
a class disjoint from a complete public category cut is known zero. A category bin
straddling the requested class is unknown. No private observation fills a public hole.

This is deliberately conservative exact-query answerability. It does not solve all
possible public inference equations (for example zero specialization of crossing bins
or subtraction attacks). Report zero and positive-reference strata and per-category
coverage using the same fixed bank. Raw observations supply reference/error only.
Answered-only MAE should be zero: here it is a correctness check, while coverage and
readiness measure task availability. Count units are observations, never summed people.
No general occupancy-estimation or traffic-quality claim follows from this exact bank.

## Reproducibility and gate

Freeze a binary copy, source/policy/input hashes, commands, Python/platform information
and raw private outputs. Audit scalar production outputs independently; match semantic
release cuts/counts against bounded references. Record binding constraints, retained
contributions, loss, spatial detail and logical observation age. CPU time is not the
optimization target and logical release age is not measured network latency.

Accept this study only if all real outputs audit, all actual cuts belong to the legal
reference set, repeated scientific outputs match, independent tests pass, and the report
separates controlled witnesses from general results. Do not infer statistical confidence,
empirical privacy gain, global scheduling optimality, or a full semantic-classification
privacy model from these five fixtures. Review the resulting trade-offs before changing
selection priorities or introducing cell-local semantic coordination.
