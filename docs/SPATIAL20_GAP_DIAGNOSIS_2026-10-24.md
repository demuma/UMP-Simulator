# Spatial20 gap: exact membership diagnosis and a lost handoff endpoint

## Outcome of the frozen-data investigation

The earlier Spatial20 disadvantage is not sufficiently explained by describing it as a generic price of adaptation. A concrete implementation defect was found: refinement can discard an already shortened rendezvous endpoint on a fresh private owner. The resulting children miss the rendezvous and can remain permanently out of phase with their siblings.

The original 32-case results and movement streams remain unchanged. The investigation reads their actual native diagnostic events and joins every source observation to the real fixed/adaptive releases. It does not regenerate movement, alter policies, infer empty public areas as zero, or rerun the controller to produce the diagnosis. Native correction and subsequent verification are separate steps; this report does not claim the correction has already recovered the original retention gaps.

## Exact contribution membership

Both joins use the full input denominator and the actual half-open spatial/time support. The relevant privacy/support policies and source observations are identical within each pair; selective contribution suppression is off.

| Recorded pair | Input observations | Both retain | Fixed only | Adaptive only | Neither retains | Net fixed advantage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Mixed: Semantic First vs fixed 20 m / 400 ms | 82,033 | 32,453 | 9,105 | 3,887 | 36,588 | 5,218 |
| Pedestrians: Spatial First vs fixed 20 m / 1000 ms | 90,045 | 58,980 | 9,173 | 4,138 | 17,754 | 5,035 |

These are exact memberships of observation contributions, not distinct people or a privacy risk measure. The sums independently agree with the verified native retained totals.

For every fixed-only observation, the tool locates its actual suppressed adaptive interval and independently evaluates the 20 m parent over that **same interval**, using the original observations, taxonomy and strict inherited regional requirements:

| Pair | Parent passes, archived owner starts differ | Parent exceeds regional time/age bound | Parent fails other requirements |
| --- | ---: | ---: | ---: |
| Mixed | 8,780 / 9,105 (96.4%) | 243 | 82 |
| Pedestrians | 8,932 / 9,173 (97.4%) | 43 | 198 |

This identifies a pronounced phase/ownership symptom. It is **not a measured recoverable fraction**: the hypothetical parent uses support that earlier child retirements may already have consumed. Changing that earlier schedule can change other releases as well. No global optimum or guarantee of recovering all these observations follows.

Among the mixed fixed-only observations, 8,226 retire at `coordination_handoff` and 879 at a policy/window deadline. The corresponding pedestrian counts are 6,969 and 2,204. Thus a large part of the observed loss occurs while trying to coordinate future publication, rather than solely in sparse cells with no adequate surrounding support.

## First phase divergence in central parent 60

The first source observation in parent 60 arrives at 6900 ms. Its initial observations are riders. The owners remain aligned through the intervals `[6800,10800)` and `[10800,14800)`; they fail support/semantic requirements and retire at their deadlines. Empty owners do not independently break the clocks during this initial phase.

At 15200 ms, the valid 10 m child 241 publishes 13 observations from `[14800,15200)`. Sibling 240 still owns an unresolved interval starting at 14800 ms. Empty siblings 242 and 243 retire after the accepted publication, once common-parent support is no longer reconstructable from one shared start. The resulting cut has 64 finest-cell units starting at 14800 ms and 192 starting at 15200 ms.

That initial asynchronous publication is permitted by the current `policy_satisfied` rule. It explains why a future rendezvous is needed; it does not itself establish a defect.

## Concrete endpoint loss during refinement

The actual native trace then records:

1. Private owner 3852, a 2.5 m cell, owns an empty interval `[19500,19900)`.
2. Its private decisions include `handoff_requested` at 19600 ms with a rendezvous boundary of **20000 ms**. A separate instrumented replay of the legacy controller confirms the exact target: parent **60, a 20 m cell**. The archived action format itself omits this target ID.
3. At 19900 ms the empty owner retires. Its fresh successor must preserve the earlier rendezvous endpoint rather than wait for a new full 400 ms interval.
4. The first new measurement in that previously empty owner arrives at the same 19900 ms timestamp, in leaf 15408. This forces the fresh coarse owner to refine into leaves 15408–15411.
5. Those children actually retire at **20300 ms**, then 20700 ms, 21100 ms, and so on. Other parts of parent 60 retire at 20000 ms, 20400 ms, 20800 ms, and so on.

The relevant old implementation is `CellLocalAggregation::refineToDomain`: it calls `makeWindow(child, old.startMs)`, but preserves the old scheduled endpoint only when the parent has already accumulated temporal extensions. A fresh successor has zero extensions even when a handoff shortened its next endpoint. Refinement therefore restores the normal `start + 400 ms` endpoint and loses the 20000 ms rendezvous.

`applyHandoffs` requires the affected owners to acquire the exact common start at the recorded rendezvous boundary. The persistent 300 ms offset prevents that condition. A private intention can therefore repeatedly truncate/suppress individual prefixes without ever producing the intended common parent clock.

The correction must preserve a previously shortened endpoint during refinement, with the child's own deadline still enforced. It does not require relaxing any support, semantic, temporal or spatial policy constraint. Altering which ancestor is preferred is a different algorithmic change and is not the cause demonstrated by this trace. The instrumented legacy requests at 2000, 6800, 8900 and 19600 ms already target 20 m cells; the earlier hypothesis of small handoff reservations starving a larger ancestor is therefore not supported by this evidence.

## Bounded counterexample useful for a regression

A small state-machine regression can isolate the defect without reproducing the full city scene:

- Create different descendant starts and schedule a future parent rendezvous at time `b`.
- Let an empty coarse owner finish at `b - 100 ms`; its fresh successor receives the earlier endpoint `b`.
- Ingest the first observation inside that owner at `b - 100 ms`, forcing refinement before `b`.
- Require every refined child to preserve the endpoint no later than `b`, and require the rendezvous to establish the common start at `b`.
- Check contribution accounting, failed short-prefix requirements, immutable publication, and later valid parent release.

The old extension-count guard instead schedules those fresh children at `b + 300 ms`. This is the specific regression to distinguish the implementation repair from a broader heuristic redesign.

## A same-interval parent witness

A second compact witness explains the retention symptom. In the mixed run, leaf 15706 is suppressed over `[8900,9300)` at a handoff. It contains four observations from one track. The complete 20 m parent 61 over the **same interval** contains 25 observations from seven distinct tracks and can release the `Pedestrian` family at semantic loss 0.5. It satisfies the local 1000 ms duration/age maxima and every support requirement.

Its archived constituent starts are nevertheless 7900, 8900 and 9000 ms. The parent is unavailable to the controller's same-start merge rule. The actual fixed release of parent 61 over `[8800,9200)` passes independently and retains the observation at 8900 ms. This witness proves that policy-valid surrounding support exists; it does not authorize republishing already retired support.

## Evidence and validation

The maintained tool is `tools/evaluation/diagnose_spatial20_gap.py`. It streams the native arrays, checks the immutable source/result digests, matches releases without parent/child overlap, conserves the entire input and independently rebuilds actual fixed-release policy checks. It exports no individual identities or positions.

Four small tests pass: an exact 21-observation membership/clock fixture, stricter regional inheritance despite source points outside the region, ancestor-overlap rejection with half-open boundaries, and streaming JSON values split at a 64 KiB boundary. These tests validate the diagnostic, not the native correction.

Compact evidence:

- [Mixed join and parent witnesses](verification/spatial-gap-2026-10-24/mixed-diagnosis.json)
- [Pedestrian join and parent witnesses](verification/spatial-gap-2026-10-24/pedestrians-diagnosis.json)
- [Fresh-owner endpoint trace](verification/spatial-gap-2026-10-24/fresh-owner-endpoint-trace.json)

Privacy claims remain limited to independently checked operational policy compliance. This investigation does not measure attack resistance or change the privacy promise.
