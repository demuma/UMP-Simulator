# A07: preserving valid descendants after a failed spatial merge

Date: 2026-10-21. Status: first common-window slice implemented and verified; acceptance contract recorded before changes.

## Scope and order

This is the next bounded algorithm step. It addresses common-window selective
suppression only. Existing cell-local ownership already preserves the passing leaves
in the two reference cases; its planning and ownership rules are not redesigned.
Computation/cache optimization, membership attacks, semantic generalization, individual
road-user suppression, taxonomy redesign and changing observation depth are deferred.
The current public scalar-count product and protected source data stay unchanged.

The new optional `aggregation.spatial_selection.preserve_valid_descendants` setting
(default false) retains the whole-candidate baseline for reproducible comparisons.
The common-window selector may preserve a provisional partial cut, but the adaptive
controller must continue permitted temporal extension until its existing terminal
condition. A fixed-window spatial run is terminal at its fixed window boundary.
Cell-local configuration must reject this common-window-only option when enabled,
rather than silently suggesting that a new local fallback was activated.

## Decision rule

For each occupied subtree over one exact private interval:

1. Keep the finer cut if every occupied child is eligible.
2. Otherwise assess the whole parent using all original observations and its complete
   effective footprint policy. If it passes, replace the entire child cut with it.
3. If it fails and the option is enabled, preserve the child cut if it contains at
   least one eligible cell. Keep ineligible branches as private suppression footprints.
   The subtree remains partially ineligible so a legal higher parent can still rescue it.
4. If no descendant is eligible, keep a compact suppressed parent footprint.

The failed parent remains in private assessment provenance, not in the final cut or
recipient totals alongside its descendants. Known-empty space may remain implicit.
No person is deleted from source history and no modified parent count is published.

## Invariants

- Every released descendant independently passes every effective hard metric bound
  at the actual evaluation/delivery time, with complete measurement coverage.
- Every final footprint is a whole canonical quadtree cell within legal depth/size
  bounds; selected and suppressed footprints do not overlap.
- Selected plus privately suppressed observation contributions equal the original
  interval input; distinct support uses exact identity unions, never summed observations.
- Start, extension schedule and absolute policy deadline are unchanged. A provisional
  partial cut cannot be misclassified as a fully eligible release.
- Suppression does not count as useful-data availability or successful full retention.
- Publication reserves one immutable selected cut and retires the whole common interval
  only on acknowledgement. No historical release can be reopened for a later parent.
- Missing history and evaluation-budget exhaustion remain explicit errors with no
  partial publication or selection-state advancement.
- Recipient records contain approved selected cells only, without a parent/global
  total, suppressed-cell counts, private road-user IDs or type breakdowns.

## Hand-worked acceptance cases

All examples use measured samples at 100, 200 and 300 ms and interval [0,400).
At depth 2 in an 80 m square, cells 48--51 are the 20 m children of 40 m cell 12.

| Case | Constraints and data | Required selective result |
|---|---|---|
| Size-blocked parent | Cell48: a,b; cell49: c; support >=2, side <=20 m | Retain 6 of 9 contributions in 48; suppress 3 in 49 |
| Regional support | Cell48:1 person with regional minimum10; cells49--51:2 each with root minimum2 | Retain 18 of 21 in 49--51; suppress 3 in 48 |
| Legal parent | Same first case, but parent side40 m allowed | Retain all 9 in parent 12; do not prematurely settle for 6 |
| Uniform insufficient support | Exact parent identity union below common minimum | No false descendant rescue |
| Internal descendant | Passing internal cell below failing ancestor; its own leaves fail | Preserve that whole internal cell |
| Incomplete/unavailable evidence | Missing/unavailable sample or required metric | No unsupported release |
| Temporal opportunity | Only partial support at first check, extension still allowed | Keep original start and wait; use partial fallback only at terminal condition |
| Publication/retry | Partial cut sealed, sink retries or loses acknowledgement | Identical reserved payload; no reopening or premature retirement |

Also check geometry bounds, repeated identities moving between siblings, late metric
expiry, budget rollback, future-window refinement and baseline compatibility.
An independent raw-observation oracle must validate actual replay output. Tiny
exhaustive cases bound claims to the tested fixed-interval spatial candidate class;
there is no claim of optimal online scheduling or a new privacy guarantee.

## Gate before the next implementation

Record the exact source changes, focused regression results, independent replay
checks, full applicable regression suite and remaining limits in a dated test report.
Review whether the stated invariants hold before starting semantic actions or a new
utility-based candidate scheduler. No requirement may be silently weakened to make
an example pass.


## Implemented option and inspection

```yaml
aggregation:
  spatial_selection:
    min_depth: 1
    max_evaluations: 4096
    preserve_valid_descendants: true
```

The default is false. Enabled use with cell-local configuration is rejected in both
YAML preflight and the direct C++ API. The fixed uniform replay mode does not use a
spatial selector. A surviving fallback decision has the private reason
`valid_descendant_after_failed_merge`; all original metric assessments remain available.
The old parent appears only in `attempts`. Existing JSONL/Mongo diagnostics and renderer
snapshots consume the final cut without a new renderer feature or recipient schema.
No explicit CandidateBucket lifecycle transition is added by this selector change.

A deterministic [replay example](../simulator/examples/selective-suppression/README.md)
requires no MongoDB. The [dated test report](SELECTIVE_DESCENDANT_RESCUE_TEST_REPORT_2026-10-21.md)
records actual verification and the remaining recovery/privacy/utility limits.
