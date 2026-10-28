# Selective suppression: source-order verification addendum

Date: 28 October 2026. Scope: a pre-TEST correction to independent verification,
with unchanged scientific execution, sources, policy parameters and model bytes.
Read the original [frozen declaration](URBAN_SELECTIVE_SUPPRESSION_PROTOCOL_2026-10-28.md)
and [living execution report](URBAN_SELECTIVE_SUPPRESSION_TEST_REPORT_2026-10-28.md).

## Preserved stop and diagnosis

Utility publication `2748d120d1787f054fd5288621728b67fd787d56` precedes all fourteen
new fits. The one fitting attempt completed in 13.252 s. The original independent
model audit then stopped at `Model source assignments differ`. Its failed receipt
and logs are retained locally; this addendum does not label that original attempt
as passed. No new TEST predictions had been scored at the diagnostic boundary.

The producer's `expected_groups` lists are sorted lexicographically within TRAIN,
CAL and TEST. The frozen auditor instead reconstructs them in the manifest's
execution order. Two independent reviews confirmed identical, unique membership:
24 TRAIN, 16 CAL and 32 TEST groups, with disjoint split assignments. The model's
training and calibration IDs are the correct sorted lists. The comparison is
sensitive to an ordering convention that does not change which samples are used.

## Narrow additive correction

The new source-order addendum sorts a temporary copy of source-role metadata and
passes it to the original model-bundle verifier. It does not rewrite the source
manifest, protocol, TRAIN/CAL rows or fitted objects. It retains checks for source
uniqueness and split membership, complete row matrices, model digests, TRAIN-only
scaling and objective, CAL-only threshold selection and unchanged historical
models/controls. The original frozen auditor and its tests remain unchanged.

The model-stage verifier uses the original TRAIN/CAL-only loader. It does not
load TEST feature payloads. The final stage will retain the original independent
locked-score and fixed-threshold metric checks. No model is refitted or threshold
retuned. Bootstrap intervals and physical simulation are outside this independent
score auditor's scope.

A separate receipt identifies this addendum and both auditor hashes. Its verified
status applies to the additive check, while explicitly recording that the original
frozen audit attempt failed. The already fitted model, TRAIN/CAL-data and lock
hashes remain authenticated. Corrective verification and model-lock publication
must finish before new TEST scoring.

## Verification evidence

The compact verification packet linked from the living execution report records
the exact additive implementation/test hashes, preserved fitted-artifact hashes,
regression results and publication boundary. Tests must accept permutation within
a split and reject duplicate IDs, changed split membership and modified model or
training evidence. This verification correction changes no scientific hypothesis,
model budget, feature definition, source split or utility result.


Pre-execution verification is complete: **23 targeted tests pass**, including all
14 unchanged auditor tests and nine new ordering/guard regressions. Independent
review agrees with the narrow correction. The original 632-test affected suite
remains valid for the unchanged execution implementation; the nine additional
regressions bring the union to 641 tests, without claiming a new full-suite run.
Read the [compact correction evidence](verification/urban-selective-suppression-2026-10-28-v1/source-order-addendum/README.md).
