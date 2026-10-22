# First Semantic First controller: historical preference-waiting baseline

Current extension: [semantic release control](SEMANTIC_RELEASE_CONTROL.md) adds
a configurable Spatial First secondary and defaults new semantic execution to
`policy_satisfied`. The behavior below is retained with explicit
`release_trigger: priority_satisfied` and Temporal First secondary. It describes
the original completed experiments, not the new implicit default.

Date: 2026-10-21. Acceptance contract recorded before implementation. Status: implemented
and verified for the stated common-window scope. The original algorithm below is retained;
configuration, results and verification links follow.
This bounded first controller adds one opt-in common-window strategy, semantic_first.
Its secondary priority is Temporal First; no separate secondary-strategy switch is added.

## Objective and scope

Preserve declared semantic accuracy before generalizing classes. First seek a complete
zero-cost semantic cut over permitted spatial cells at the current observed endpoint.
If none exists, extend time without resetting the original interval start, bounded by
the existing immutable policy and temporal schedule. At a terminal endpoint, permit
positive-cost generalization only within every original hard requirement.

The preference quantity in this slice is the worst declared category loss across selected
cells/bins. Mean semantic loss remains measured and a hard constraint when configured;
it is not an additional optimized objective. Zero cost may include zero-cost internal
nodes in a valid catalog. Semantic First does not automatically mean exact terminal labels
for every possible catalog.

Only the existing taxonomy-enabled common-window path is supported. Configuration and
direct API reject missing/mismatched taxonomy or cell-local use. Existing fixed/spatial/
TF/SF and disabled-semantic paths must retain their scientific outputs exactly. The
maintained simulator configuration is not switched to the new mode.

## Per-endpoint algorithm

1. Query the original finest observations for [start,end), with half-open endpoints and
   the already-advanced history watermark. Enforce complete measurement coverage separately.
2. Ask the existing spatial selector for a private proposal with an additional preference
   ceiling 0. Hard requirements, metric checks, IDs and regional provenance remain unchanged.
3. A proposal is complete only if measurement coverage is complete, no observed footprint
   is suppressed, every selected cell passes the original hard checks, and the sum of
   selected observation contributions equals the original interval total. A merge can
   reduce cell count; completeness is not equality of selected and finest cell counts.
4. If complete, release immediately. Spatial merging before waiting supplies the Temporal
   First secondary priority. An actually measured-empty interval may close as the existing
   vacuous no-candidate case; it produces no public empty record or privacy evidence.
5. If incomplete and extension is still allowed, keep every proposal private and advance
   only the existing next endpoint. Never use future observations or reset the start.
6. A terminal endpoint is the existing duration/age cap, EOF/finalization, actual evaluation
   deadline pressure, or incomplete measurement coverage. For complete measurements only,
   test remaining distinct positive taxonomy loss levels in ascending order. Choose the
   first proposal that retains all observed support under the original policy.
7. If no proposal retains all support, compare the assessed partial cuts by retained
   observation contributions (largest first), then actual maximum selected loss (smallest),
   contribution-weighted mean cell side (smallest), then sorted selected cell IDs. This is
   a deliberate retention-first exception when full release is impossible. Existing A07
   configuration controls descendant rescue. No individual/type contribution is removed
   inside a selected cell. Empty output has undefined actual loss, not artificial loss 0.
8. Incomplete measurements skip positive-ceiling fallback; they cannot become a valid
   partial release. Budget/invalid-evidence errors throw rather than silently suppress.
9. Commit the chosen spatial transition only after its sink succeeds. All trial proposals
   are side-effect free. Reentrant or throwing sinks leave the original active cut intact.
   PublicationCoordinator independently reassesses selected cells with the original evaluator.

This compares bounded proposals from the existing selector, not all possible global
space/time/category schedules. At one ceiling it still prefers finer passing spatial
cells. It does not minimize mean semantic loss, predict arrivals or establish a global
lexicographic optimum. In particular it can wait without gain in a static population;
that is an explicit baseline cost to measure, not hidden adaptation knowledge.

## Preference diagnostics versus hard policy

SpatialSelector receives an optional semanticLossCeiling. Null preserves the old path.
A candidate may pass every hard requirement while being rejected for the preference;
its decision reason is semantic_preference_exceeded. Do not falsify a hard check or
rewrite semantic_max_loss.max to describe this soft preference.

Each new-strategy final window includes private semantic_priority metadata:

- schema ump.semantic-priority.v1; secondary_strategy temporal_first;
- preferred_max_loss 0; selected_max_loss_ceiling;
- actual_max_loss, null for no selected output;
- attempted_ceilings and terminal_fallback (true only if a positive ceiling was assessed).

Old windows omit this object. Recipient releases keep their existing schema and contain
only approved output bins/counts; no failed trials, private node evidence or preference
metadata is added. A waiting live progress snapshot can have passing hard metrics while
its phase is extending: waiting then reflects a preference, not an asserted policy failure.
No new renderer behavior is required for this slice.

The catalog bounds the number of distinct ceiling trials to 256 per endpoint. Each proposal
retains the existing spatial evaluation budget; combined worst-case spatial work is bounded
by catalog levels times that budget, in addition to the existing temporal probe bound.
There is no new eager bucket cache, thread or unbounded search.

## Required acceptance examples

- Medium density, same policy: four leaves each 4 Pedestrian + 2 AdultCyclist + 2 ChildCyclist, category minimum 5, loss cap 1.
  Existing TF can release fine RoadUser8 per leaf at 400 ms. Semantic First must instead
  release the 40 m parent with exact supports 16/8/8 at 400 ms, keeping 96 first-window observations.
- High density: each leaf 10 Pedestrian + 5 AdultCyclist + 5 ChildCyclist; exact fine output at 400 ms without waiting.
- Low static density: each leaf 2 Pedestrian + 1 AdultCyclist + 1 ChildCyclist; no zero-cost full output. Wait to 800ms,
  then choose 40 m Pedestrian 8 + Cyclist 8 at ceiling 0.5, not fine/root loss 1. Repeats create no IDs.
- Turnover: enough newly observed people can produce a zero-cost full cut before the cap;
  release then, preserving the original start and excluded-endpoint semantics.
- Hard regional size/loss/mean/age and coverage bounds remain mandatory at every trial.
- Strictly incomplete evidence produces no release. EOF uses only observations already
  available and may invoke bounded positive-cost fallback before the ordinary duration cap.
- If full release is impossible, retain the best assessed legal partial cut before choosing
  a smaller exact subset solely for its lower loss. Clearly document that priority.
- Zero-cost internal nodes are legal; no assumption that only terminals have cost0.
- Sink failure/retry, contiguous windows, source retirement and approved immutable payloads
  are unchanged. No preference or private evidence reaches recipient storage.
- Missing taxonomy/cell-local/invalid configuration rejects before external side effects.

## Verification plan

Add independent C++ branch/state/publication tests and Python real-core replay audits.
Use original raw observations and bounded antichain references, not production pass flags.
Verify actual private diagnostic metadata separately from the recipient channel. Exercise
one actual MongoDB persistence/recovery case for a new-strategy selected cut in an isolated
UUID test database; never launch the normal database-clearing simulator configuration.

Build all targets, run the complete CTest regression, and use focused ASan/UBSan for the
new native controller path. Compare frozen pre/post binaries for at least 24 unchanged
legacy-mode pairs, excluding runtime only, including semantic-enabled old strategies and
cell-local scalar modes. Provide runnable opt-in examples, a bounded old/new case table,
precise test accounting (including optional skips), source/binary hashes and a dated report.
After that gate, discuss results before adding another strategy or local coordination.

## Implemented interfaces and configuration

`AdaptationStrategy::SemanticFirst` maps to `semantic_first`. The optional fourth
`SpatialSelector::propose` argument is the preference ceiling. `SpatialSelection` appends
optional `semanticPriority` metadata; existing callers omit it. `MetricEvaluator` and
PolicyTree requirements are not rewritten. Final native JSONL and replay windows contain
the new private object only for this strategy; recipient schema/content is unchanged.

Select the mode through the existing root execution setting, with a configured semantic
catalog, required semantic bounds, bounded history and temporal adaptation:

```yaml
aggregation:
  policy_tree:
    execution:
      publication_model: private_final_snapshot
      strategy: semantic_first
    # Keep the declared root/region requirements and taxonomy from the full config.
  temporal_adaptation:
    coordination: common_window
    extension_step_ms: 100
    max_window_ms: 800
    max_evaluations: 16
```

This is an excerpt, not a complete simulator configuration. The
[three complete replay examples](../simulator/examples/semantic-first/README.md) provide
all required fields. Missing taxonomy, missing temporal settings and cell-local use reject
before the normal simulator's external side effects. The maintained config remains unchanged.

## Completed gate

The [implementation test report](SEMANTIC_FIRST_TEST_REPORT_2026-10-21.md) records
52 passing CTest entries; 361 passed Python methods and 12 existing optional skips;
13 native acceptance cases under ASan/UBSan; real MongoDB lost-ACK/recovery; and
30 unchanged pre/post legacy-mode pairs. The [27-case comparison](SEMANTIC_FIRST_RESULTS_2026-10-21.md)
uses identical numeric hard requirements within each strategy triplet.

This gate implements the one declared maximum-loss preference. It does not implement
Semantic First + Spatial First, a mean-loss optimizer, regional strategy overrides,
cell-local semantics, prediction-based waiting or a new privacy model. The native
max-versus-mean counterexample is documented in both reports; no overall utility
improvement is inferred from reducing only maximum loss.
