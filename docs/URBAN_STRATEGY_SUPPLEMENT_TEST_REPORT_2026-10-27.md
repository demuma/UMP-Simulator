# Supplementary strategy implementation and test report

27 October 2026. **Execution, utility, all 30 MIA assessments, independent final
numerical/metadata verification and four actual-figure reviews are complete.**
Final public-artifact and recorded lock-before-TEST chronology audits also pass.

This is an exploratory extension of an already inspected TEST study. It does not
replace the original primary result or create a fresh confirmatory sample. The
[protocol](URBAN_STRATEGY_SUPPLEMENT_PROTOCOL_2026-10-26.md) was frozen in
`85ed5b5` before execution. Utility and the hash-only model lock were published
in `91c257a` before supplementary TEST scoring.

## Implementation and policy invariants

New runner/reporter tools expose four variants; existing C++, binary, scientific
helpers, features and queries are unchanged. Only strategy, semantic secondary
preference and release trigger differ. Removing those keys leaves the entire
configuration canonically equal. Regional thresholds, taxonomy/costs, spatial
limits, sampling, 100-ms extension, 4-s maximum and resource/audit rules stay fixed.
Selective contribution suppression is OFF; invalid whole candidates may be withheld.

| Variant | Preserved detail and release rule |
|---|---|
| Semantic / immediate, imported | Temporal secondary; `policy_satisfied`, release a permitted candidate immediately. |
| Temporal First, new | Preserve time; spatial rescue before temporal extension; allowed semantic loss can release immediately. |
| Spatial First, new | Preserve space; temporal extension before terminal spatial rescue; allowed semantic loss can release immediately. |
| Semantic wait / Temporal, new | `priority_satisfied`; zero-loss preference, spatial rescue before waiting. |
| Semantic wait / Spatial, new | `priority_satisfied`; zero-loss/fine-geometry preference, waiting before terminal rescue. |

“First” means preserved detail. Zero loss is a soft preference; fallback may occur
at the local terminal, which coordination, handoff or EOF can shorten below 4 s.
Preferred output releases early. Immediate Semantic First / Spatial secondary
is excluded as duplicate behaviour.

## Data, enrollment and completeness

All 72 existing 300-s sources are reused: 24 TRAIN / 16 CAL / 32 TEST, with exact
IN/OUT targets, auxiliary sightings and roles. No resimulation, filtering,
reselection or replacement occurred. The protected unit is one operational track's
observed contributions within [0,300000) ms, not identity or all physical visits.
Distinct-track support is an operational condition, not person-level k-anonymity.

| Evidence | Imported | New | Combined |
|---|---:|---:|---:|
| Native method/world executions | 1296 | 576 | 1872 |
| Regional compositions | 288 | 0 | 288 |
| TRAIN/CAL recipient rows | 880 | 320 | 1200 |
| TEST recipient rows | 704 | 256 | 960 |
| All recipient rows | 1584 | 576 | 2160 |
| Method/representation MIA variants | 22 reused | 8 fitted | 30 evaluated |

**576/576 new native cases and 72/72 groups passed, with zero missing/failed
cases.** Every method has 144 verified method/world cases; all 15 methods use
the same source families. All 30 TEST method/world policy-violation means are zero
(N=32 each), documenting conformance rather than privacy effectiveness. Movement
quality is separate: one TRAIN and one TEST
source report stalls and remain active at the horizon; none has pending arrivals.
These diagnostics neither exclude enrollment nor count as privacy protection.

## Tests, audits and preserved failures

| Gate | Completed result |
|---|---|
| Full unit suite | 445 pass; zero failures/errors/skips; 41.800 s |
| Existing native groups | 22 pass; zero failures; 7.674 s |
| Excluded city DEV integration | 8/8 pass, four variants × IN/OUT; zero policy violations; 371.584 s |
| Independent utility arithmetic | 6334 checks pass on 2160 bound rows; no fitting/scoring |
| Independent model-lock arithmetic | 5142 checks pass on 1200 TRAIN/CAL rows; zero TEST rows read |
| Independent final arithmetic | 9206 checks pass; probabilities, locked thresholds, rates, intervals, paired contrasts and utility |
| Independent final metadata | Complete matrices, configuration/source identities, archive bindings and old objects/primary unchanged |
| Actual PNG QA | Four final figures reviewed; labels, axes, legends, NA markers and CI zero lines legible |

Scopes overlap; unit fits are synthetic. Guards reject changed policy/modes,
altered pairs/roles, incomplete matrices and TEST fitting. Persistent fit-attempt
receipts prevent retries. Native ordering checks are separate from policy tests.
The arithmetic checker does not refit or replay optimization; gradient is diagnostic.

Preserved history includes the original source-qualification repair and new private
checker corrections: ignore descriptive CAL metadata while enforcing numerical
fields; require 64 distinct TEST rows/32 complete pairs before lookup; permit NA
native timing only for regional compositions. The corrected metadata checker passed
31 synthetics. Failed checkers/diffs remain local; no frozen study code, policy or
result changed. Assessment stderr was only an informational font-cache message.

Maintained final assessment revalidated raw-source proof chains, archives and
bindings without resimulation or new physical-audit jobs. Independent arithmetic
and metadata reviews complement that gate; they do not independently reconstruct
all physical/source evidence.

## Utility and runtime

TEST IN-world equal-recording means follow. Every available displayed metric has
N=32; regional runtime is unavailable. OUT is exported separately, never pooled
as 64 independent sources. Semantic loss, geometry and delay are conditional on
retained input. J combines omission and taxonomy loss, not spatial/temporal loss.

| Method | Retained % | J % | Retained semantic loss % | Side m | Delay ms | Core s |
|---|---:|---:|---:|---:|---:|---:|
| Fixed 20 m / 0.4 s | 56.158 | 78.669 | 62.092 | 20.000 | 250.052 | 0.531 |
| Regional static 20 m | 60.603 | 77.248 | 62.538 | 20.000 | 1839.255 | NA |
| Semantic / immediate | 68.526 | 73.802 | 61.796 | 17.935 | 347.665 | 32.846 |
| Temporal First | 68.526 | 73.807 | 61.803 | 17.933 | 347.665 | 32.397 |
| Spatial First | 66.300 | 73.306 | 59.762 | 17.318 | 1787.520 | 37.824 |
| Semantic wait / Temporal | 70.215 | 72.817 | 61.336 | 17.814 | 1804.370 | 36.759 |
| Semantic wait / Spatial | 70.331 | 72.781 | 61.347 | 17.840 | 1806.028 | 36.616 |

Wait/Spatial maximizes retention and minimizes J here: versus immediate release,
+1.805 retention points and −1.021 J points, costing 1.458 s more mean delay.
Spatial First preserves finer retained geometry/semantics but less input; Temporal
First closely reproduces immediate release. Versus regional static 20 m,
wait/Spatial gains 9.728 retention points and lowers J by 4.467 points. Fixed
20 m / 0.4 s remains much faster and lower latency; there is no universal winner.

Estimated coverage for regional20/immediate/wait-Spatial is 13.910/12.508/13.852%,
with conditional MAE 1.351/1.260/1.285. Unknown is not zero; exact coverage is near
zero for broad outputs. Of 3454 macro coordinates, 3450 have N=32; exact occupancy
MAE for immediate and Temporal First has N=14 IN / N=13 OUT. All Ns are explicit.

Serial utility took 27184.588 s including audits/I/O. New TEST subprocess means
were 33.829–39.232 s, p95 36.109–42.356 s. Core/wall scopes differ; old/new runs
occurred at different times. Regional native timing is NA. These offline timings
do not establish live delivery or per-step deadlines.

## MIA: fitted once, scored last

Eight new logistic objects converged in 7.879 s. TRAIN-only population scaling/fits
and CAL-only thresholds used the fixed budget: 500 iterations, regularization 0.1,
tolerance 1e-8. Full111 iterations were 78/88/88/98; Scalar31 43/50/48/47, in
Temporal/Spatial/wait-Temporal/wait-Spatial order. Original 22 objects and four
controls were reused exactly, with no retuning/reversal/exclusions. The derived
lock was published before TEST scoring; all 30 variants evaluated 32 complete pairs.

Full111 uses 111 declared recipient features. Scalar31 jointly removes semantic
and availability coordinates, not semantics alone. CAL FPR 0.1 is not a TEST or
population guarantee. The aggregate export includes exact binomial TPR/FPR
intervals; no individual-method AUC interval was declared.

| Method | Full111 AUC | Scalar31 AUC | Full111 TPR | Full111 FPR |
|---|---:|---:|---:|---:|
| Fixed 20 m / 0.4 s | 0.605 | 0.579 | 0.125 | 0.094 |
| Regional static 20 m | 0.565 | 0.581 | 0.406 | 0.375 |
| Semantic / immediate | 0.578 | 0.591 | 0.406 | 0.312 |
| Temporal First | 0.579 | 0.591 | 0.406 | 0.312 |
| Spatial First | 0.580 | 0.608 | 0.219 | 0.219 |
| Semantic wait / Temporal | 0.586 | 0.597 | 0.469 | 0.375 |
| Semantic wait / Spatial | 0.582 | 0.597 | 0.500 | 0.469 |

Controls passed: prior/auxiliary-only/no-output AUC=0.5 and TPR=FPR=0;
unprotected AUC=1, TPR=1, FPR=0. Their N is 32 pairs, never multiplied by methods.

Eight exploratory AUC contrasts follow (left minus right): 1000 whole-recording
pair replicates, fixed fits/CAL, 32 groups, seeds 20261026311–318 in table order.
All 16 conditional 95% intervals include zero; intervals are not simultaneous.

| Contrast | Full111 difference [95% interval] | Scalar31 difference [95% interval] |
|---|---|---|
| Temporal First − Regional static 20 m | 0.014 [-0.043, 0.080] | 0.011 [-0.060, 0.088] |
| Spatial First − Regional static 20 m | 0.015 [-0.036, 0.066] | 0.027 [-0.039, 0.083] |
| Semantic wait / Temporal − Regional static 20 m | 0.021 [-0.022, 0.072] | 0.017 [-0.043, 0.065] |
| Semantic wait / Spatial − Regional static 20 m | 0.017 [-0.022, 0.064] | 0.017 [-0.039, 0.065] |
| Temporal First − Spatial First | -0.001 [-0.052, 0.055] | -0.017 [-0.086, 0.062] |
| Semantic wait / Temporal − Semantic / immediate | 0.009 [-0.030, 0.057] | 0.006 [-0.067, 0.075] |
| Semantic wait / Spatial − Semantic / immediate | 0.004 [-0.039, 0.055] | 0.006 [-0.075, 0.073] |
| Semantic wait / Temporal − Semantic wait / Spatial | 0.005 [-0.022, 0.036] | 0.000 [-0.019, 0.021] |

The original primary contrast is preserved exactly: Full111 +0.012695
[−0.043970, 0.072266], Scalar31 +0.010742 [−0.061523, 0.091797], using the
original seed 20261025301. No supplementary contrast replaces it.

Utility improvements are descriptive trade-offs. These MIA intervals prove neither
lower leakage nor equivalence/unchanged privacy. Higher AUC means stronger observed
attack discrimination; several adaptive point AUCs exceed regional static 20 m.
All tested aggregations have lower point discrimination than unprotected output
for this attack, without universal/person-level privacy guarantees.

## Reproduction, artifacts and publication gate

Utility preceded fitting; published lock preceded scoring. Assessment/export
completed successfully in 953.359/1.534 s. Commands/settings are in the protocol;
local outputs: `results/urban-strategy-supplement-2026-10-26-v1`. Do not rerun
reviewed phases. Publish aggregates/figures only; raw movements, targets, individual
features/labels, fitted parameters and scores remain local.

The [final verification packet](verification/urban-strategy-supplement-2026-10-26-v1/final-outcome/README.md)
records reports, figures, scopes and checksums. The independent public scan covered
12 exported files (1239103 bytes) and 13 copied packet files including its README
(1247206 bytes): all 12 exports copied byte-exactly, no forbidden private JSON keys,
and zero hits among 434 known private-token candidates. This is a scoped known-token
check, not arbitrary-secret detection; later documentation is bound separately.

Git/phase receipts confirm lock publication at 05:55:36 UTC preceded assessment
at 05:56:10.565 UTC. An extra ad hoc check initially demanded SVG byte identity
between separate exports; creation timestamps/internal IDs can differ. Both
corresponding utility PNGs are identical, numerical projections unchanged, and
each export/copy matches its own manifest. The rejected expectation remains in
lineage; no canonical result was corrected.

| Evidence | SHA-256 |
|---|---|
| Private final report | `74d4bc6fc964f6112726a7924cef6ab3c2dbf388872b35aeb49b5b59a58efffd` |
| Final numerical audit | `37cd6489fe170cf35e14ad3bc046364b9a8f1be1224bef379a439b8865ee6e40` |
| Final metadata audit | `fb3a5df6bdcc756cbdbbd8f5a54bde0efa00c5cd881541744346b6efbb11fae6` |
| Four-figure visual QA | `20a6df8168ee787c617c611bbb8ada1801cf717b3118ff8379ce252e7b38b106` |
| Final public/chronology audit | `3e8ae8d72eedb5d6618570011a9e41382cf1ce1be49eb059f8743be4ce9711b3` |
