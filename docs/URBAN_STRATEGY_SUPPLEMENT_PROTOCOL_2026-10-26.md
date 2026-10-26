# Supplementary strategy comparison before the Thursday presentation

Date: 26 October 2026. Status: **protocol declared; implementation and validation
in progress; no supplementary native results or new attack outcomes yet**.
The presentation on Thursday, 29 October, takes priority over a broader
policy-search or second-attack project. This supplement implements the agreed
sequence: define distinct strategies, validate implementation, run utility and
runtime comparisons, then fit and assess membership attacks last.

The completed [observed-track-window study](verification/urban-track-window-2026-10-26-v1/final-outcome/README.md)
and its [execution/test report](URBAN_PRIVACY_TRACK_WINDOW_EXECUTION_TEST_REPORT_2026-10-26.md)
remain unchanged. This is a separately versioned, supplementary **exploratory**
comparison: existing TEST results have already been inspected and informed the
choice of added strategies. It is not a new untouched confirmatory study.

## Distinct configurations and nomenclature

First means the dimension whose detail is preferentially preserved, not the
first dimension to coarsen. Hard feasibility always takes precedence over a soft
preference. Standalone Temporal First and Spatial First do not implement a
complete lexicographic ranking of all three dimensions. Semantic First is a
bounded local candidate preference, not global optimization over all cuts.

| Method ID | Configuration | Status and intended distinction |
|---|---|---|
| `adaptive_semantic_first` | Semantic First; Temporal First secondary; `policy_satisfied` | Exact imported reference. Prefer better semantics among currently available legal representations and release eligible owners immediately. |
| `adaptive_temporal_first` | Temporal First; `policy_satisfied`; no semantic secondary setting | New evaluation of existing kernel mode. Preserve time: attempt spatial rescue before further temporal extension. Permitted semantic generalization can make an owner eligible immediately. |
| `adaptive_spatial_first` | Spatial First; `policy_satisfied`; no semantic secondary setting | New evaluation of existing kernel mode. Preserve space: extend failed owners before deadline-driven spatial rescue. Permitted semantic generalization can make an owner eligible immediately. |
| `adaptive_semantic_wait_temporal` | Semantic First; Temporal First secondary; `priority_satisfied` | New evaluation of existing kernel mode. Prefer zero semantic loss; permit an exact-category spatial rescue before waiting. |
| `adaptive_semantic_wait_spatial` | Semantic First; Spatial First secondary; `priority_satisfied` | New evaluation of existing kernel mode. Prefer zero semantic loss and fine geometry; wait before deadline-driven spatial rescue/fallback. |

The final two configurations prioritize semantics above their secondary time/
space preference. They are not Temporal First or Spatial First main strategies
with an unexplained extra hold. In the current implementation, preference waiting
means **maximum semantic loss zero before a local terminal boundary**, not an
arbitrary preferred family-loss target such as 0.5. At a terminal boundary,
only policy-permitted semantic tiers/spatial rescues remain available; unresolved
support is withheld. The terminal can be caused by regional duration/age limits,
coordination/handoff or the end of the recorded stream. Passing the preferred
representation can permit early release; waiting is not always to 4 seconds.

Do not add Semantic First / Spatial secondary / immediate release as a sixth
nominal variant: the current immediate-release branch overrides that secondary
waiting preference, so it does not constitute an independent action comparison.
Do not rename Semantic First / Temporal secondary as a fully implemented
Temporal > Semantic > Spatial hierarchy.

## Fixed hard requirements, inputs and visibility

Use the exact original local400 hard requirements for every method and world.
Only `policy_tree.execution.strategy`, `semantic_secondary_strategy` and
`release_trigger` may differ in a new execution configuration. Remove those
three execution keys and require canonical equality with the original full
configuration. Keep publication model, regional geometry, type/instance rules,
thresholds, taxonomy and costs, spatial limits, sampling, base window, 100-ms
extension step, 4-s maximum, history/resource limits and independent audit rules
unchanged. No semantic-loss ceiling, support threshold or regional deadline is
relaxed. Selective semantic contribution suppression remains OFF; whole failed
footprints can still be withheld and count as omitted input.

Use all 72 original full 300-s sources in their same 24 TRAIN / 16 CAL / 32 TEST
roles. Reuse the exact source bytes, selected target track, matched IN/OUT pair,
auxiliary sightings, public map/taxonomy context and source-validation evidence.
No simulation, trajectory repair, source filtering, replacement seed, new target
selection or extra adversarial information is allowed. Observed track inclusion
within `[0,300000)` ms remains the secret; completion/stalls are separate quality
diagnostics and never enrollment filters. The protected unit is not a person,
physical presence, all visits or a complete journey.

The recipient sees the same public v2 product and retrospective snapshot at
H=300 s. Use the same Full111 and Scalar31 feature definitions; Scalar31 is a
joint semantic/availability ablation, not an isolated semantic-leakage estimate.
Raw observations, target identities, feature rows, model parameters and individual
attack scores stay local and ignored by Git. Only compact aggregate results,
protocols, figures and checksum evidence are published.

## Reuse and workload

Import all original eleven methods, their native/regional outputs, 1584 rows,
22 attack variants and controls through authenticated references. Never rewrite
their original protocols, failed source receipts, diagnostic-repair lineage,
sidecars, rows, model/scaler/threshold files or public packages. The original
primary contrast and its interpretation retain their completed historical scope.

| Evidence | Imported | New | Combined |
|---|---:|---:|---:|
| Methods | 11 | 4 | 15 |
| Source recordings | 72 same recordings | 0 new | 72 |
| Native method/world executions | 1296 | 576 | 1872 |
| Regional-static compositions | 288 | 0 | 288 |
| TRAIN/CAL method/world rows | 880 | 320 | 1200 |
| TEST method/world rows | 704 | 256 | 960 |
| All method/world rows | 1584 | 576 | 2160 |
| Method/representation attack variants | 22 | 8 | 30 |

Each new strategy uses 144 native executions (72 sources x IN/OUT). Existing
baselines, source quality, controls and model objects are exact imports, not new
executions or refits. Combined derived analysis/model views must explicitly
identify their imported and newly fitted objects. Actual outcomes, missing and
failed cases remain visible; no silent retries, replacement or available-case
headline is permitted. Preserve incomplete/nonconverged outcomes honestly.

## Ordered gates

1. **Implementation:** separate supplementary runner and aggregate reporter.
   Existing frozen evaluation helpers and C++/Simulator binaries remain unchanged.
   Validate mode-specific native metadata: standalone TF/SF do not emit Semantic
   First-only secondary/release fields. Use real per-variant configuration overrides,
   not renamed duplicate executions or mutable monkeypatches of frozen helpers.
2. **Synthetic and native correctness:** test invalid hard-policy deltas, exact
   method catalog, source/pair/role provenance, immutable imports, count/accounting
   failures, stage gates and exclusion of TEST from fitting. Native regressions
   must distinguish early spatial exact rescue, fine-space preference waiting,
   immediate generalized release and deadline-permitted intermediate fallback.
   Repeated observations of the same track must not raise distinct-track support.
3. **Excluded city DEV integration:** run every new variant in both worlds on
   one previously excluded city DEV recording using the same binary and hard
   policy. Check actual mode/config, source conservation, private/public arithmetic,
   geometry/time ownership and policy audits. This is plumbing evidence, not a
   new primary source or attack result. No actual-study fit is performed here.
4. **Freeze and execute utility:** bind protocol, code/tests, successful gates,
   per-variant configurations and immutable original inputs before supplementary
   native executions. Run all 576 new native cases, audit every publication and
   combine verified utility with the imported references. Keep model fitting and
   MIA scoring unavailable until all planned utility evidence is complete.
5. **Utility/runtime review:** summarize TEST IN/OUT separately with equal-source
   macro means, every metric's available-source denominator and all failed cases.
   Compare retention, full-input J, retained semantic loss, cell side, interval,
   logical delay/tails, query coverage and conditional error. Core/subprocess
   timings are offline replay diagnostics, not per-step RT certification. Regional
   composition online runtime remains unavailable. Publish utility first, with
   new MIA explicitly pending.
6. **MIA last:** fit the eight new Full111/Scalar31 attack objects using TRAIN only
   and calibrate thresholds using CAL only, with the unchanged fitting protocol.
   Lock bytes before supplementary TEST attack assessment. Reuse original control
   objects and old22 method objects byte-identically; no TEST score reversal,
   threshold retuning or outcome-driven removal. Preserve nonconvergence instead
   of repeatedly fitting until favorable. Assess all32 matched TEST recording
   groups per method and conduct independent numerical/provenance checks.
7. **Final publication:** inspect actual figures; export aggregate-only evidence
   with original diagnostic-repair and supplementary lineage, code/model hashes,
   stage receipts and detailed English results/test report. Update README/TO-DO
   with actual outcome. Do not overwrite the user's presentation edits or output
   folder. No second attack or policy-search implementation belongs to this block.

Independent policy/count/ownership audits establish hard conformance, not strategy
ordering. Dedicated native semantic/scheduling assertions establish the latter.
A quiet or empty output is not automatically useful or protected; evaluate its
lost coverage. Extra waiting may fail to improve semantics when no additional
suitable distinct tracks arrive, and may increase latency or eventual withholding.

## Numerical protocol and planned contrasts

Retain original TRAIN-only scaling, L2 logistic fitting (lambda=0.1, maximum500
iterations, tolerance1e-8), empirical CAL FPR target0.1, fixed score direction and
exact two-sided95% Clopper-Pearson rate intervals. The small CAL sample and earlier
TEST FPR generalization failure remain limitations; no threshold adjustment on
these supplementary TEST outcomes is allowed. Balanced-prior precision is not
operational positive predictive value.

Original AUC contrast Adaptive Semantic First minus regional static20, including
its conditional1000-replicate paired bootstrap seed20261025301, remains unchanged.
The following additional contrasts are declared **exploratory**, each for both
representations, using whole TEST-recording IN/OUT pairs jointly across methods,
1000replicates, linear percentile95% intervals and fixed fitted models/CAL thresholds:

| Seed | Left minus right |
|---|---|
| 20261026311 | Temporal First minus regional static20 |
| 20261026312 | Spatial First minus regional static20 |
| 20261026313 | Semantic wait / Temporal secondary minus regional static20 |
| 20261026314 | Semantic wait / Spatial secondary minus regional static20 |
| 20261026315 | Temporal First minus Spatial First |
| 20261026316 | Semantic wait / Temporal secondary minus original immediate Semantic First |
| 20261026317 | Semantic wait / Spatial secondary minus original immediate Semantic First |
| 20261026318 | Semantic wait / Temporal secondary minus Semantic wait / Spatial secondary |

No individual-method AUC intervals, noninferiority margin, automatic equivalence,
simultaneous-family guarantee or utility-difference confidence interval is claimed.
Utility differences are descriptive; conditional error must be read with coverage
and different answered subsets. J measures omitted input plus retained taxonomy
loss, not total spatial/temporal/application loss. AUC near0.5 is not a guarantee
against other attackers. An interval crossing zero resolves neither superiority
nor equivalence. All configurations are reported, regardless of which performs best.

## Original provenance anchors

| Original artifact | SHA-256 |
|---|---|
| Dataset manifest | `81e59a558acae956e8b38a9c1d58e18ef274d010e699659d56fd18ebf4d19567` |
| Completed repair execution protocol | `f8d15a0c40bbdfcf18888a25540f132763dc9b497fb0d18b0ff60eb2831f52a2` |
| Completed original private report | `70abeed6ff101fd51723a610a58120c5963db347510bfe630d882c5ad1509f71` |
| Original 22-variant model lock | `d0d56de7d89ba7c51135f88584ad533b1bcb4e1aa309eb1af8e233c059e9be81` |
| Original fitted-model artifact | `62b34bcd88737d601ef1f6eabae95ac9ae51fc102189d1062d532e798af18a77` |
| Original 880 TRAIN/CAL rows | `266b22c90303f62fce8644ba09d9c8da400ab6a3f141641f5a6058c3c6235a56` |

Later actual freeze/validation/results receipts must bind this protocol. Planning
counts above are not completed execution counts. Old published packages retain
their original scope, dates and hashes.
