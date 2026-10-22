# A07 common-window descendant rescue: test report

Date: 2026-10-21. Outcome: bounded implementation gate passed.

## Question and scope

Can the common-window selector preserve independently policy-valid whole descendants
when a spatial parent fails, without changing measurement support, hard requirements,
temporal deadlines or irreversible publication?

The rule was documented before implementation in
[SELECTIVE_DESCENDANT_RESCUE.md](SELECTIVE_DESCENDANT_RESCUE.md). This step adds only
optional common-window descendant fallback. The existing whole-candidate baseline
remains the default. Membership experiments, semantic/type/individual suppression,
map/trajectory redesign, cache preparation and changing depth are outside this step.
Existing experiments and user configuration edits were preserved.

## Implementation

- `SpatialSelection.hpp`: appended `preserveValidDescendants`, default false.
- `SpatialSelection.cpp`: retain the previously assessed disjoint child cut only when
  the whole parent fails and some descendant passes. The branch remains partially
  ineligible, preserving higher-parent and temporal alternatives. Failed branches stay
  in the private cut for source accounting; failed parents stay only in attempts.
- `AggregationConfiguration.cpp`: parse the optional Boolean, reject malformed/duplicate
  values, and reject enabled cell-local configuration during preflight.
- `CellLocalAggregation.cpp`: reject the same unsupported option in the direct API.
  No local ownership, merge, hold or handoff behavior changed.
- CMake: register focused C++ and independent Python replay acceptance suites.

No metric formula, policy threshold, publication schema or default simulator config
changed. Internal fallback selections use `valid_descendant_after_failed_merge` as
their private reason. The actual release boundary still independently reassesses every
selected cell and filters unapproved type breakdowns.

## Hand calculations and actual core results

All three repeated sample times are 100, 200 and 300 ms, over [0,400). Repeated
measurements are contributions, not additional people.

| Case | Input contributions | Baseline retained | Selective retained | Final suppression |
|---|---:|---:|---:|---:|
| Cell48: two people; cell49: one; minimum support 2, maximum side 20 m | 9 | 0 | 6 in 48 | 3 in 49 |
| Supports 1/2/2/2 in 48--51; requirements 10/2/2/2; parent inherits 10 | 21 | 0 | 18 in 49--51 | 3 in 48 |
| First case with legal 40 m parent | 9 | 9 | 9 in 12 | 0 |

The first case retains 66.67% of input contributions, the regional case 85.71%.
These are exact mechanism examples, not estimated population effects. The first
example exists as [runnable frozen inputs](../simulator/examples/selective-suppression/README.md).
The independently checked result is `results/selective-suppression/example.json`,
with its audit in `results/selective-suppression/audit.json` (ignored research artifacts).
The replay result includes private diagnostics; only its `releases` array models
recipient output.

## Focused C++ gate

Nine grouped cases in `simulator/tests/SelectiveSuppressionRegressionTests.cpp` pass:

1. Hand-worked partial rescue, default baseline and full-parent rescue.
2. Direct API: valid false-option local controller constructs four owners; enabling
   the common-window-only option rejects otherwise identical settings.
3. Regional 10/2/2/2 support requirements preserve only passing descendants.
4. A passing internal descendant survives a failed ancestor, then refines in a future
   disjoint window when its finer cells pass.
5. Moving/repeated identities cannot fabricate support; impossible geometry and
   minimum-depth bounds remain binding.
6. Missing/unavailable samples, unavailable required metrics and expired age fail closed.
7. Budget exhaustion and unavailable history do not advance selector state.
8. Both temporal strategies retain the original start/deadline and keep partial cuts
   private while extension is legal; later arrivals can still enable full retention.
9. Publication exception/Retry/ACK keeps the immutable cut reserved, prevents historical
   reopening, strips type details and rejects delivery after metric expiry.

An independent raw-observation scan checks geometry containment, half-open time
support, per-cell distinct identity unions, measured-sample occupancy denominators,
nonoverlap and exact contribution conservation. It does not obtain expected counts
from the production ancestor query.

The final direct-API assertion was added after the full suite run, then the affected
C++ target was rebuilt and its registered test rerun successfully. No production code
changed after the complete suite run.

## Independent replay and bounded oracle

All 12 methods in `tools/evaluation/test_selective_suppression.py` pass. Every successful
replay is validated from raw observations and policy definitions by the independent
`oracle.validate_result` implementation.

The checks include all three common selector modes, implicit/explicit false equivalence,
regional thresholds, internal descendants, coverage failures, terminal timing and the
recipient field allowlist. An adversarial mutation of a released count is rejected.

Two exhaustive groups compare actual retained contributions with the independent
fixed-interval spatial cut reference:

- 162 combinations: all 0/1/2-person populations in four depth-2 cells, with legal or
  size-prohibited parents.
- 32 combinations: all two-identity cell swaps with minimum support 2 or 3.

All 194 cases match their bounded reference retention. This is not a proof of global
optimality across future arrivals, multiple intervals or publication schedules.

## Compatibility and regression control

A saved pre-change binary and the rebuilt binary were run on the existing heterogeneous
and handover fixtures, under nine configurations each: four fixed-grid/window variants,
spatial, common Temporal First/Spatial First and local Temporal First/Spatial First.
All 18 before/after pairs are identical after removing only runtime measurements;
all 36 executions independently pass the raw-input compliance audit. Configuration,
recipient records and private decisions remain unchanged when the option is omitted.

The new C++ suite was also linked against the saved OLD spatial traversal, using the
current headers solely to accept the appended option field. It fails the exact
9-input/6-retained witness, while the changed traversal passes. This confirms that
the regression distinguishes the missing behavior rather than merely accepting both.

## Build, complete checks and sanitizer scope

Actual commands included:

```sh
cmake --build simulator/build -j 6
ctest --test-dir simulator/build --output-on-failure -j 6
ctest --test-dir simulator/build --output-on-failure -R '^selective_suppression_regression$'
```

- Full build: passed, including Simulator and AggregationReplay.
- Complete CTest run: **42/42 passed**, including all three opt-in MongoDB integration
  suites. Those tests create/remove only their own UUID test databases; the maintained
  Simulation database and main simulator were not run.
- Python summaries in that complete run: **297 methods passed**.
- Final focused target after the added direct-API guard assertion: passed.
- Focused AddressSanitizer/UndefinedBehaviorSanitizer build: passed without sanitizer
  findings. `-Wall -Wextra -Werror -Wno-missing-field-initializers` was used; the last
  exclusion avoids pre-existing aggregate-initializer warnings in shared code.
- LeakSanitizer is unavailable on this macOS platform: the initial request with
  `detect_leaks=1` was rejected by the sanitizer runtime. ASan/UBSan ran with
  `ASAN_OPTIONS=detect_leaks=0`; no leak-check claim is made.

Existing privacy unit/regression tests were exercised as part of the normal suite;
no new membership experiment or parameter tuning was performed.

## Invariant review and remaining limits

The independently reviewed implementation preserves the same exact interval and
complete source support. Whole parent counts are never altered by deleting a person.
Selected and private suppressed footprints partition the observed contributions; the
failed parent is not released alongside its children. Partial eligibility remains
false, preventing premature adaptive completion. A valid larger parent still wins
when it rescues all support.

Important limits remain:

- Operational support constraints are not formal k-anonymity, l-diversity or an attack
  risk guarantee. Additional valid releases can expose more information.
- Under uniform minimum distinct support, an insufficient parent implies insufficient
  descendants for the same interval. A07 helps heterogeneous requirements or other
  constraints, such as a prohibited parent size; it cannot create people.
- Local windows already preserve passing leaf owners in the reference cases. General
  asynchronous coarse-owner fallback needs its own reachable counterexample and design.
- Mean occupancy/query usefulness, selection bias and real traffic validity require a
  separate evaluation. Contribution retention alone is not complete utility.
- No semantic support metric, taxonomy hierarchy, individual/type suppression or
  utility-based candidate scheduler was introduced.
- Failed parents are private attempts; no new CandidateBucket lifecycle state machine
  or explicit SUPERSEDED record transition was implemented.
- Budget errors remain explicit errors, not automatic graceful degradation.
- The pre-existing common controller calls `selector.commit()` after the sink returns;
  that method allocates a vector. Arbitrary post-acknowledgement allocation-failure
  recovery is not proved by sink-retry tests. This F03 limitation is recorded in TO-DO.
- This step does not prove protection against all historical differencing, arbitrary
  background knowledge or multiple recipient streams.

**Review gate:** the bounded common-window A07 slice satisfies its stated acceptance
cases. The next work is to agree on semantic release products, precise metric meanings
and allowed actions before adding another implementation dimension. Computation
optimization and membership attacks remain deferred.
