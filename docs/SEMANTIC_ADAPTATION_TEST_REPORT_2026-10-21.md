# Semantic adaptation implementation and test report

Date: 2026-10-21. Repository: UMP-Simulator. Implementation slice: A08, common-window
semantic release. Result: acceptance gate passed for the tested scope.

## Objective and scope

Add a truthful semantic representation as an online action alongside the existing spatial
and temporal adaptation. Every release must satisfy the effective Policy Tree constraints,
including the new category-support and semantic-loss bounds. Thresholds must not be relaxed
to obtain output. This gate verifies implementation and quantitative representation values;
a broad constraint-impact study and empirical privacy-gain study are separate tasks.

The exact model, formulas, configuration and assumptions are in
[SEMANTIC_ADAPTATION.md](SEMANTIC_ADAPTATION.md). Canonical notation is recorded in
[TERMINOLOGY_AND_NOTATION.md](TERMINOLOGY_AND_NOTATION.md), version 1.6.

This implementation supports the common-window spatial, Temporal First and Spatial First
paths, A07 selective descendant rescue, immutable publication and optional MongoDB storage.
Semantic configuration is opt-in. Cell-local semantic coordination rejects explicitly.
The existing scalar-only default and the maintained simulator configuration are unchanged
by this slice. Default behavior profiles are not extended by synthetic fixture labels.

## Acceptance conditions and evidence

| Condition | Verification | Result |
|---|---|---|
| Category labels remain truthful ancestors of the actual source classes | C++ taxonomy/pipeline tests and independent raw-observation audit | Pass |
| A complete nonoverlapping category cut retains every observation in a released cell once | Partition/overlap checks and exhaustive antichain enumeration | Pass |
| Distinct support counts identities, not repeated samples or sums of overlapping identity sets | History reconstruction across space/time, aliases and repeated identities | Pass |
| Regional support/loss bounds and all scalar constraints remain mandatory | Regional footprint, coverage, spatial and temporal rescue tests | Pass |
| Semantic detail costs are explicit catalog values | Non-depth-derived intermediate cost 0.37 and mixed-cut loss checks | Pass |
| Failed or missing evidence cannot become an approved output | Invalid input, missing evidence, incomplete coverage and unavailable-metric tests | Pass |
| Sealing recomputes the approved representation rather than trusting annotations | Deliberately corrupted diagnostic-bin test | Pass |
| Public output excludes raw types, identities and private node evidence | Recipient payload and MongoDB rejection/round-trip checks | Pass |
| Retry and acknowledgement preserve the immutable selected interval and values | Coordinator retry, retirement and store lost-ack/reconciliation tests | Pass |
| Generalized class queries return unknown when not exactly answerable | Exact rollup, disjoint zero, straddling unknown and unary-domain tests | Pass |
| Disabled semantics preserve existing behavior | 24 frozen before/after pairs and 48 independent scalar audits | Pass |

## Build and complete regression run

The CMake build completed successfully, including Simulator, AggregationReplay and all
configured test targets. The complete regression command was:

```sh
ctest --test-dir simulator/build --output-on-failure -j 6
```

All **47/47 CTest entries passed**, with no failed entries; reported wall time was 15.32 s.
The Python entries reported **312 methods: 300 passed and 12 skipped**. The skips belong
to existing optional matplotlib and pinned scikit-learn/histogram-environment tests.
They are not semantic acceptance skips. All **15 new semantic Python methods executed
and passed**, with no skips. These counts distinguish test methods from replay executions
and CTest entries; they must not be added together as one test count.

The complete per-entry output is retained in
[ctest-full.log](../results/verification/semantic-2026-10-21/ctest-full.log).
The [manifest](../results/verification/semantic-2026-10-21/manifest.json) records source/test
hashes and verification counts. Regression execution includes pre-existing privacy modules;
this slice did not introduce or run a new broad attack study.

## New targeted suites

- `semantic_taxonomy`: seven grouped C++ cases covering rooted-tree/resource validation,
  exact support, complete cuts, aliases, repeated/conflicting identities, malformed evidence,
  mixed loss, exact/unknown queries and unary category domains.
- `semantic_history`: six grouped C++ cases covering exact spatial/temporal identity unions,
  half-open boundaries, empty/incomplete windows, pre-mutation unknown-label rejection,
  conflicting terminal classifications, manager/history agreement and bounded-history needs.
- `semantic_pipeline`: six grouped C++ cases covering truthful generalization, insufficient
  support, hard loss bounds, regional constraints, spatial/temporal rescue, scalar coverage
  gates, publication revalidation and immutable retry/acknowledgement.
- `semantic_adaptation_evaluation`: 15 Python methods using the real replay binary and
  independent raw-data/antichain checks. There were **103 replay executions**: **100 successful
  outputs audited**, plus three expected rejects for unknown labels, conflicting labels and
  unsupported cell-local semantics. Successful audit includes valid no-release outputs.
- `semantic_publication_store`: actual MongoDB persistence, validation, byte budgets,
  idempotency, lost acknowledgement, reconciliation, commit and recovery. This includes
  a real manager/history/selector/coordinator pipeline, not only hand-constructed snapshots.

The 100 audited executions include **81 tiny population/support cases**. The reference
independently enumerates category-node subsets, filters them to complete nonoverlapping
cuts, evaluates support and loss from raw observations, and checks the implementation's
result. This validates fixed-candidate semantic selection for the enumerated cases;
it is not a proof of globally optimal online space/time scheduling.

## Actual persistence and recovery case

Two adult and two child cyclists are sampled three times in one cell/window. The real
core selects Cyclist with 12 observation contributions and four distinct road users,
minimum support 4 and maximum/mean semantic loss 0.5. The coordinator strips private
counts before sending the approved product to the store.

A simulated lost acknowledgement is reconciled against the actual stored release;
commit and a new store instance recover exactly the approved semantic values. Structural
malformations, private evidence, unsupported scoped semantic products and count/budget
violations reject. Test databases use fresh UUID-owned names and are cleaned by the tests.
The user's Simulation database is not used. No normal simulation or GUI session was started.

Storage/recovery trusts a coordinator-approved snapshot for taxonomy ancestry, declared
costs and policy approval. Recovery without the original trusted snapshot/policy is not a
fresh privacy assessment. The previously documented arbitrary post-ack allocation/recovery
issue remains separate F03 work; these tests do not claim general crash-proof recovery.

## Sanitizers

The focused native pipeline was separately compiled with Apple clang, C++17, strict warnings,
AddressSanitizer and UndefinedBehaviorSanitizer. The linked sources were SemanticTaxonomy,
AggregationManager, AggregationHistory, CandidateMetrics, PolicyTree, SpatialSelection,
AdaptiveAggregation and PublicationCoordinator. Compilation used `-O1 -g -Wall -Wextra
-Werror -Wno-missing-field-initializers -fsanitize=address,undefined -fno-omit-frame-pointer`.
The suppression is limited to existing aggregate-initializer warnings.

The resulting SemanticPipelineSanitized executable passed with **no ASan/UBSan findings**.
`ASAN_OPTIONS=detect_leaks=0` was used because leak detection is unavailable on this macOS
setup. No LeakSanitizer or MongoDB-library sanitizer claim is made.

## Disabled-mode before/after comparison

Two existing observation fixtures (`make_fixture`, `make_handover_fixture`) were each run
through 12 modes: fixed depth 5/6 at 400/1000 ms, spatial-only, common Temporal First/Spatial
First, cell-local Temporal First/Spatial First, and A07-enabled common spatial/Temporal
First/Spatial First. No semantic taxonomy was configured in these comparisons.

All **24/24 pairs matched in every output field except `runtime`**, including the complete
`configuration_yaml` string. All **48/48 raw-observation scalar audits passed**. Comparison
used frozen before/after binaries, preventing a rebuild from changing a binary during
verification. The detailed report with fixture/configuration/result hashes is retained in
[baseline-compatibility.json](../results/verification/semantic-2026-10-21/baseline-compatibility.json).

- Before binary SHA-256: `617f63f8a59af221f9b0b912b8375d89de2aefed22b21371e38e68f65d13049a`.
- Final binary SHA-256: `cfdd2a0b68a4185f42afc4f8f19fc8cbf94d1d84f98edfe47e469296a7e64400`.

These are regression results for the declared fixtures, not a guarantee for all inputs.

## Reproducible hand cases and quantitative outcomes

The [five frozen examples](../simulator/examples/semantic-adaptation/README.md) run without
MongoDB or a renderer. They use an 80 m square, depth 2, one occupied cell, three samples
and interval [0,400) ms. The depth restriction deliberately isolates semantic selection;
it does not change the maintained depth-6 simulator. All five outputs passed independent
scalar and semantic audits.

| Case | Observed road users | Support minimum | Loss maximum | Public category result | Retained contributions |
|---|---|---:|---:|---|---:|
| rare | 19 pedestrians + 1 adult cyclist | 5 | 1 | 20 RoadUser | 60/60 |
| cyclists | 2 adult + 2 child cyclists | 4 | 0.5 | 4 Cyclist | 12/12 |
| strict-loss | Same 19+1 input | 5 | 0.5 | No release within these limits | 0/60 |
| strict-support | Same 2+2 input | 5 | 1 | No release: only four identities | 0/12 |
| exact | 2 pedestrians + 2 adult + 2 child cyclists | 2 | 0 | Three exact terminal categories | 18/18 |

These examples demonstrate the constraint trade-off directly. Generalizing to RoadUser
keeps all occupancy observations but makes cyclist counts unknown. Generalizing to Cyclist
preserves the cyclist total while losing the adult/child split. A bound forbidding the
required generalization prevents release in the deliberately restricted example.
Separate pipeline cases verify that allowed spatial or temporal extension can instead
retain finer semantic classes; no threshold is weakened.

The private [summary](../results/semantic-adaptation/summary.json) also records exact-query
coverage for the four declared queries RoadUser/Cyclist/AdultCyclist/ChildCyclist: 1/4, 2/4,
0/4, 0/4 and 4/4 respectively. This denominator is a toy class-query workload, not population
coverage or general traffic utility. Contribution totals count samples, not people.
Support and declared representation loss are quantitative operational measures, not
calibrated attack probabilities or a formal k-anonymity/l-diversity guarantee.

## Review gate and next work

An independent read-only design and documentation review found no blocking violation
of the bounded contract. This gate accepts the tested common-window semantic product.
It does not accept a joint utility optimizer or cell-local semantic scheduling by implication.

The next review should fix class-specific task requirements and candidate priorities before
expanding coordination. The current selector chooses the finest support-valid semantic cut
within each spatial/time candidate, then checks all loss/scalar bounds; TF/SF/A07 determine
subsequent space/time progression. Exact terminal classification is stable within the
reconstructed query domain/interval, currently the full grid in common-window reconstruction.
Changing class during that interval is rejected rather than silently reconciled.

E07 in [TO-DO.md](../TO-DO.md) separately plans a constraint-impact study with frozen input,
query workload and mechanism versions. It distinguishes a policy's feasible-output cost
from a search/coordination gap using bounded reference enumeration where possible. Measure
compliance, retention, timely query coverage/error, release age and space/time/semantic
detail together; record binding constraints and unavailable evidence separately. A stricter
policy can reduce achievable usefulness even when every emitted record is compliant.
Empirical privacy gain is subsequently evaluated on those same frozen versions.

Not included: independent local semantic windows, individual/type or complementary
suppression, per-category priorities, compositional behavior-taxonomy redesign, new maps
or trajectories, tracking-error models, a new membership study, or compute optimization.
