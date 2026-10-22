# Semantic First terminology and a controlled density example

Date: 2026-10-21. Historical density/terminology gate: 18 cases, before controller work.
**Superseded current implementation status:** a dedicated Semantic First controller is
now implemented and verified; see the [contract](SEMANTIC_FIRST_IMPLEMENTATION.md) and
[new 27-case comparison](SEMANTIC_FIRST_RESULTS_2026-10-21.md). The statements below about
an unimplemented controller describe the state of this earlier experiment, whose inputs,
protocol and results remain unchanged.

## Preservation priorities

The name identifies the information to preserve:

| Name | Primary preservation objective | Current status |
|---|---|---|
| Temporal First | Temporal accuracy/freshness | Implemented; spatial merging precedes temporal extension after a failing finest candidate |
| Spatial First | Spatial accuracy | Implemented; temporal extension precedes spatial fallback |
| Semantic First | Semantic accuracy/category detail | Canonical adopted term; a dedicated action-selection mode is not implemented |

Semantic First may have a secondary Temporal First or Spatial First preference. Such
combinations describe a proposed preference hierarchy; they are not accepted YAML modes.
The present C++ enum and parser accept only temporal_first/spatial_first. Current early
semantic generalization inside every assessed space/time candidate is NOT Semantic First:
it can generalize classes to preserve fine space/time. Section 10 of the canonical
[notation](TERMINOLOGY_AND_NOTATION.md) records this distinction.

A hard maximum semantic loss of zero forbids positive-cost generalization, including at
a deadline. In this catalog that requires terminal categories; the general taxonomy API
also permits zero-cost internal nodes. Semantic First would instead prefer detailed
categories while still respecting
an independently specified hard loss maximum. Whether and when it can use that allowed
fallback needs an explicit online rule. No preference overrides a hard bound.

## Why isolate density

The prior bounded study changed several policy requirements on fixed source streams.
This example now varies the number of road users while holding type ratio, identities,
positions, source cadence, area and support requirements fixed. It tests a mechanism
relationship, not a realistic shopping-street population or empirical privacy gain.

The input is an 80 m square at depth 2, with four occupied 20 m leaves within parent12.
The occupied domain is 40x40 m. Every 100 ms from 100 to 2300 ms, each leaf observes
2m Pedestrian, m AdultCyclist and m ChildCyclist. The multiplier m is 1, 2 or 5. The
same identities remain in the same positions for the full 2400-ms horizon.

| Multiplier | Road users per 20 m leaf | Total distinct road users | Density over occupied 1600 m2 | Source observations |
|---|---:|---:|---:|---:|
| 1 | 2+1+1 = 4 | 16 | 0.01 road users/m2 | 368 |
| 2 | 4+2+2 = 8 | 32 | 0.02 road users/m2 | 736 |
| 5 | 10+5+5 = 20 | 80 | 0.05 road users/m2 | 1840 |

These are average densities over the specified occupied domain, not the entire 80 m
square or a statement about local personal spacing. Observation depth 2 is a bounded
hand-checkable reference; production depth 6 and the live config are unchanged.

Category support minimum is always 5; maximum cell side is 40 m, minimum depth 1,
base window 400 ms, extension step 100 ms and duration/age maximum 800 ms. Both common
TF/SF strategies run with A07 enabled. The only policy-profile variation is maximum
semantic loss 0, 0.5 or 1. The catalog costs are terminal 0, Cyclist 0.5 and RoadUser 1.
This gives 3 densities x 3 loss profiles x 2 strategies = 18 cases, plus three repeats.
The hard-loss profiles are separate policies, not measurements of Semantic First.

## Verified outputs

All support numbers in the table are DISTINCT ROAD USERS; repeated observations are
separate quantities. Parent means one 40 m output; leaf means each 20 m output.

| Density | Hard loss maximum | Released representation | Retention | First decision TF / SF |
|---|---:|---|---:|---:|
| m=1 | 0 | No release | 0% | 800 / 800 ms |
| m=1 | 0.5 or 1 | Parent: 8 Pedestrian + 8 Cyclist | 100% | 400 / 800 ms |
| m=2 | 0 or 0.5 | Parent: 16 Pedestrian + 8 AdultCyclist + 8 ChildCyclist | 100% | 400 / 800 ms |
| m=2 | 1 | Each leaf: 8 RoadUser | 100% | 400 / 400 ms |
| m=5 | 0, 0.5 or 1 | Each leaf: 10 Pedestrian + 5 AdultCyclist + 5 ChildCyclist | 100% | 400 / 400 ms |

At m=1, no leaf even has five people. At the parent, the adult/child cyclist classes
have only four each, while their Cyclist parent has eight. Its maximum loss is 0.5
and observation-weighted mean loss is 0.25. With loss maximum 0, there is no complete
legal representation. Publishing only the eight pedestrians would silently suppress
a semantic remainder; that action is not implemented.

At m=2, exact classes are possible in the parent. If root generalization is allowed,
each fine leaf's eight RoadUser already pass, so current selection stops there. At m=5,
every terminal category passes in every fine leaf, making generalization unnecessary.

### More density need not improve every output property

Under the SAME loss maximum 1 and support minimum 5, increasing density from m=1 to m=2
changes current selection from a 40 m Pedestrian/Cyclist representation to 20 m RoadUser.
Space becomes finer, but maximum/mean semantic loss rises from 0.5/0.25 to 1/1. The
fixed 40 m class-query coverage falls from 50% to 25% for the TF runs. At m=5 it reaches
100%, with fine space and zero semantic loss. This is a selection-order effect in the
controlled example, not monotonic improvement in every utility dimension.

The m=2/loss1 first [0,400) interval also has a verified legal parent alternative under
identical data, policy and evaluation time: observation bins Pedestrian 48 / AdultCyclist 24 / ChildCyclist 24,
with distinct supports 16/8/8, loss 0 and 96/96 contributions retained. The current fine
cut and that parent are both nondominated under the declared different task/detail goals.
A future Semantic First + Temporal First rule could prefer the exact parent immediately;
that is a candidate design conclusion, not an executed Semantic First result.

### Waiting needs new support to help here

All identities in this example are static. Extending the window increases observation
counts but never distinct support. Where spatial merging is needed, SF waits until 800 ms
and returns the same spatial/semantic representation that TF could release at 400 ms.
The extra wait produces no representation gain in this controlled source.

The fixed receiver bank separately measures four category counts over 400/800-ms windows
at 20/40 m, with logical deadline lags 0/400 ms. Complete contained public support is required;
missing or unresolved answers remain unknown. An 800-ms count is not split into exact
400-ms counts. Thus the delayed SF parent can answer 800-ms queries but not the 400-ms bank.
This conservative exact-answer rule is not all possible transcript inference and does
not replace the separate approximate occupancy evaluator.

## Verification and provenance

All 18 scalar audits and all 90 actual-interval candidate checks pass. Six intervals have
no nonempty feasible representation, exactly the two m=1/loss 0 runs. All three repeats
match every scientific output field except runtime. None of the actual choices is
conditionally dominated on the six declared objectives; this is not global optimality.

The protocol was written before any core execution. The frozen binary, four evaluator
modules, runner, inputs, policies, outputs and audits are preserved with 127 checked hashes
under [results/semantic-density-2026-10-21](../results/semantic-density-2026-10-21/manifest.json).
[Summary](../results/semantic-density-2026-10-21/summary.json) and
[post-run verification](../results/semantic-density-2026-10-21/verification.json) retain exact
query denominators, category counts, timestamps and the original run commands. Absolute
/private/tmp paths record the execution location; copied artifacts are not rewritten.

This turn changes documentation only in the maintained codebase. No controller, simulator
configuration, behavior taxonomy or online metric is modified. The frozen C++ binary and
helpers are the ones covered by the prior 50-entry regression gate; this does not claim a
new full regression run. The 18 real replays plus three repeats are additional experiment
executions, not additional CTest entries. MongoDB and the live renderer are not used.

To replay a stored case from the repository root into a NEW file:

```sh
./results/semantic-density-2026-10-21/AggregationReplay \
  --input results/semantic-density-2026-10-21/inputs/density-m2.json \
  --config results/semantic-density-2026-10-21/10-density-m2-k5-l1-s40-t800-temporal_first/policy.json \
  --mode temporal_first \
  --output /private/tmp/ump-density-m2-new-result.json
```

## Next bounded decisions

Semantic First is now valid terminology. Before implementing it, specify:

1. Its secondary time/space preference. Semantic First + Temporal First is a concrete
   first candidate because the m=2 exact parent is already available at the first check.
2. How long to wait when no sufficiently detailed candidate currently passes, given
   that future identities are unknown. Use a declared bound and deterministic fallback;
   do not treat future observations as current evidence.
3. How maximum versus mean semantic loss and retained partial output are ranked. A
   valid exact subset and a more complete generalized output need an explicit rule.

A subsequent controlled source can add identity turnover while holding instantaneous
occupancy/type ratio fixed. That separates the effect of new people from density and
repeated sampling. No street geometry or new motion planner is required for that test.
Shopping-window presence, unique visits and dwell events remain different later tasks;
a stop/event definition comes before map/trajectory work for that use case.
