# Semantic-action ablation: model lock before TEST

Locked and independently checked 28 October 2026, after the
[published utility results](../utility-outcome/README.md) in commit `eae5251`.
No new OFF TEST attack score exists at this lock.

All fourteen new OFF classifiers converge on 24 TRAIN recording pairs: 48 rows
per classifier, using TRAIN-only population scaling and fixed L2=0.1,
maximum 500 iterations and tolerance 1e-8. Thresholds use only sixteen CAL pairs
(16 positive and 16 negative cases), with empirical FPR target 0.1 and resolution
1/16. A CAL threshold target is not a population-FPR guarantee.

The seven OFF procedures each have Full111 and Scalar31 models. Fourteen ON
fitted objects and the original four controls are reused exactly; no original
fit or threshold is changed. The combined headline view has 28 objects and 1,120
TRAIN/CAL method/world rows. The lock auditor independently verifies 2,254 values
without reading TEST rows, refitting, retuning or calling maintained score or
calibration routines.

Six models have a legitimate constant balanced TRAIN optimum and converge at
iteration 1; the other eight converge within 41–56 iterations. This is a property
of these features and TRAIN samples, not evidence of universal indistinguishability.
All declared procedures remain in the assessment; none is selected, dropped or
refitted using TEST outcomes. The same TEST sources were already exposed in
prior studies, so the new comparisons remain exploratory.

- [Aggregate lock, hashes and convergence/CAL diagnostics](model-lock-public.json)
- [Completed gates](completed-gates-public.json)
- [Declared semantic-action protocol](../../../URBAN_SEMANTIC_ABLATION_PROTOCOL_2026-10-27.md)

Weights, scalers, intercepts, fitted thresholds, features and individual scores
remain local. Next assess the fixed models on the 32 TEST IN/OUT pairs, preserve
old ON/control/primary results and compute the seven predeclared paired OFF-minus-
ON AUC intervals separately for each representation.
