# Observed-track-window final execution and test report

Date: 26 October 2026. Status: **execution, final raw/archive verification,
statistical checks, provenance checks and actual-figure QA complete**. All 32
TEST families verify; all 22 attack variants are evaluated and the interpretation
gate is `controls_pass`. The primary privacy contrast remains inconclusive:
its confidence interval crosses zero. Adaptive retention and logical delay
improve descriptively against the predeclared regional 20 m reference; neither
privacy superiority nor equivalence is established.

This report concerns the declared fixed-model, fixed-window contribution game.
It is not a general privacy, realism, navigation-liveness or real-time guarantee.
The [technical amendment](URBAN_PRIVACY_TRACK_WINDOW_DIAGNOSTIC_REPAIR_2026-10-26.md)
preserves the original source-auditor failures and explains the diagnostic-only
repair. The [contract](PRIVACY_TRACK_WINDOW_CONTRACT_2026-10-26.md) defines the
protected unit and recipient channel. The final publication commit is recorded
by the packaging process; no scientific outcome is pending that commit.

## Scope and chronological barriers

The secret is whether all observed contributions of one operational track in
`[0,300000)` ms were included. OUT removes that complete observed contribution
from frozen IN. All background observations, ordering, measurement opportunities
and measured-empty batches remain unchanged; no movement is resimulated.
Targets require two observations, while short/unselected traces remain input.
The exact quarter-count auxiliary sample, rounded upward, is identical in both
worlds and contains approved time/position/public-cell sightings only.

The same 72 source groups retain 24 TRAIN / 16 CAL / 32 TEST roles. Valid active
or censored tracks remain included; movement quality does not filter enrollment.
Source clock, GT/sensor agreement, provenance, geometry, speed and body/swept
separation remain hard validity requirements.

The model lock was published in `3db24c5` before any TEST source generation.
The later diagnostic correction, complete qualification and readiness binding
were published in `7326d40` before TEST mechanisms. These are different barriers:
the repair did not precede TEST source capture. It followed the disclosed
source-diagnostic exception without access to TEST recipient performance.
Source C++, binaries, frozen Python, models, scalers and thresholds did not
change during TEST execution.

The original strict complete-episode study remains closed at 39/40 TRAIN/CAL
sources with no original primary mechanisms/models/TEST generation. The separate
windowed study retains all 32 original failed technical TEST qualifications and
the new corrected receipts. Those historical statuses are not overwritten.

## Actual workload and execution outcome

| Split | Source groups | Native method/world cases | Regional compositions | Method/world rows |
|---|---:|---:|---:|---:|
| TRAIN | 24 | 432 | 96 | 528 |
| CAL | 16 | 288 | 64 | 352 |
| TEST | 32 | 576 | 128 | 704 |
| Total | 72 | 1,296 | 288 | 1,584 |

All planned cases verify. There are no missing/failed cases, dependency-failed
regional streams or unavailable attack variants. Every method has 144 verified
world cases across all 72 sources. TEST supplies 32 complete IN/OUT pairs per
method and 64 rows per method/representation, not 704 independent sources.
Audited native published-cell policy violations are zero. Original 40 groups,
880 rows and 22 locked variants remain unchanged; refits, threshold retunes,
source replacements and source resimulations are zero.

All eleven methods use identical local400 hard requirements. **Selective
semantic contribution suppression is OFF**. Whole cell/window candidates that
cannot satisfy the policy can still be withheld; that omitted input is counted
in retention and full-input loss. Suppression OFF does not mean every observed
contribution is published. Regional-static streams are audited policy-only
compositions, not additional native or online executions.

| Actual command phase | Exit | Elapsed time | Scope |
|---|---:|---:|---|
| TEST method execution | 0 | 5,227.183 s | 32 complete families, native/audit/composition/archive work |
| Final raw/archive verification and assessment | 0 | 897.390 s | Complete final authentication before fixed-model scoring |
| Public numeric/figure export | 0 | 0.957 s | Aggregate presentation only |

These operational durations are not source acquisition time, mechanism-only
latency or a per-frame deadline guarantee.

## Completed automated and actual DEV checks

| Evidence | Actual outcome | Scope |
|---|---|---|
| Current-code suite | 373 pass; zero failures/errors/skips; 33.166 s | Synthetic/unit checks, not a complete native-repository rerun |
| Canonical portal regression | Six pass | Valid used/unused surface access and retained physical guards |
| Field-qualified compatibility guard | 29 tests, byte preflight and independent review pass | Exact approved diagnostic field only; legacy check unchanged |
| Actual city DEV window CLI | Verified, exit zero; 48.770 s | Existing excluded DEV recording; no new native source job or model fit |
| Source qualification | 72/72 verified | 40 authenticated legacy proofs plus 32 corrected physical audits |
| Pre-TEST readiness | Maintained check and independent metadata review pass | Exact roles, original outputs/models and zero TEST output at that checkpoint |

The suites overlap and are not summed into independent evidence. Earlier
344/371-test receipts retain their historical checkpoint meanings. The
[implementation report](URBAN_PRIVACY_TRACK_WINDOW_TEST_REPORT_2026-10-26.md)
describes the original source/DEV validation scope.

## Final raw/archive and independent verification

The completed maintained final-report command repeats all 72 raw validations,
reopens retained gzip archives from both the original 40 and new 32 groups,
checks compressed/uncompressed hashes and byte lengths, authenticates case
receipts and policy/source references, and verifies original/window/repair
sidecars. It verifies IN/OUT source pairs, role/clone exclusions and the exact
original 880-row digest before evaluating the original models.

The actual archive inventory contains **4,752 entries**. This is an observed
inventory count, not an assumed files-per-stream multiplier. The worker's
successful final invocation authenticates complete raw/archive reconstruction.
The separate provenance reviewer checks that invocation, its code/log/receipt,
all group/sidecar/inventory bindings and preserved artifacts; it does **not**
claim another independent decompression or physical reconstruction.

| Independent check | Actual outcome |
|---|---|
| Final provenance/execution review | `verified_actual_execution_complete`; no findings; all 72 groups, 1,584 rows and 4,752 archive entries accounted for |
| Statistical/numerical review | 9,244 comparisons pass; no refitting/retuning |
| Public aggregate projection review | 1,147 checks pass; hashes, numeric projection, private-key exclusion and repair lineage |
| Actual figure review | Both exported PNGs inspected; readable methods/axes/legends/NA/captions; no image edits |

The statistical review independently reproduces TRAIN scaling, fixed-model TEST
scores, tie-aware AUC, immutable-threshold rates, high-precision binomial interval
inversion, paired bootstrap and world-specific macro means. It does not repeat
raw source or archive reconstruction. Each review's scope is distinct.

## Actual attack assessment and uncertainty

Each evaluated variant has 32 positive and 32 negative worlds from 32 independent
paired sources. TPR/FPR use the CAL-locked threshold. Their intervals are
two-sided exact 95% Clopper–Pearson intervals with separate 32-world denominators.
Precision uses the balanced evaluation prior 0.5 and is not deployment PPV.

| Method | Full111 AUC | Scalar31 AUC | Full111 TPR (%) | Full111 FPR (%) |
|---|---:|---:|---:|---:|
| Fixed 10 m / 0.4 s | 0.672363 | 0.663574 | 18.750 | 6.250 |
| Fixed 10 m / 1 s | 0.622070 | 0.632812 | 37.500 | 9.375 |
| Fixed 10 m / 2 s | 0.620117 | 0.626953 | 31.250 | 18.750 |
| Fixed 10 m / 4 s | 0.590820 | 0.595703 | 28.125 | 15.625 |
| Fixed 20 m / 0.4 s | 0.604980 | 0.578613 | 12.500 | 9.375 |
| Fixed 20 m / 1 s | 0.601074 | 0.571777 | 15.625 | 9.375 |
| Fixed 20 m / 2 s | 0.567871 | 0.561035 | 15.625 | 12.500 |
| Fixed 20 m / 4 s | 0.566895 | 0.574707 | 18.750 | 18.750 |
| Regional static 10 m | 0.579102 | 0.637695 | 28.125 | 15.625 |
| Regional static 20 m | 0.564941 | 0.580566 | 40.625 | 37.500 |
| Adaptive Semantic First | 0.577637 | 0.591309 | 40.625 | 31.250 |

The primary contrast AUC(adaptive) − AUC(regional static20) is
**0.012695**, with paired 95% interval
**[-0.043970, 0.072266]**, N=32.
It crosses zero: these results demonstrate neither additional privacy protection
over that reference nor equivalence. The 1,000-replicate paired source bootstrap
is conditional on fixed TRAIN models/CAL thresholds and excludes their training
uncertainty. No individual-method AUC interval was predeclared.

The Scalar31 contrast is 0.010742, interval
[-0.061523, 0.091797]. It is also
inconclusive. Scalar31 removes semantic and availability coordinates jointly;
it does not isolate semantic leakage.

**Operating-point limitation:** the empirical CAL FPR cap of 10% is not a
population guarantee and does not carry over to this TEST cohort. Full111
adaptive FPR is 10/32 = 31.25%, exact interval [16.118%, 50.008%]; regional20
is 12/32 = 37.5%, interval [21.100%, 56.308%]. Both TPRs are 13/32 = 40.625%.
This is a calibration/generalization limitation, not a publication-policy
violation. CAL has 16 negative sources and empirical resolution 1/16. Thresholds
remain unchanged; no TEST retuning, clipping of finite reject-all thresholds or
score-direction reversal repairs the result.

### Controls

| Control | AUC | TPR (%) | FPR (%) | Status/sample |
|---|---:|---:|---:|---|
| auxiliary_only | 0.500000 | 0.000 | 0.000 | evaluated; 32 paired sources |
| no_output | 0.500000 | 0.000 | 0.000 | evaluated; 32 paired sources |
| prior_only | 0.500000 | 0.000 | 0.000 | evaluated; 32 paired sources |
| unprotected | 1.000000 | 100.000 | 0.000 | evaluated; 32 paired sources |

The three negative controls have pair-identical scores and AUC 0.5. The
unprotected exact approved-sighting control retains every IN sighting and has
AUC 1.0. The frozen control interpretation gate passes. Deduplication preserves
64 rows per control and 32 independent groups, not method-multiplied counts.
Zero observed control FPR has an exact 95% interval [0,10.888%]; unprotected
TPR=1 has interval [89.112%,100%].

Relative to this unprotected control, aggregation lowers observed ranking
performance for this declared attack/source distribution. That does not bound
other attacks, establish person/visit protection or supply differential privacy.
The adaptive-versus-regional20 primary privacy comparison remains unresolved.

## Utility, fixed queries and available denominators

These are equal-source TEST macro means. The listed retention, J, retained
semantic detail, cell size and mean delay each have N=32 in every row:

| Method | World | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell side (m) | Mean logical delay (ms) |
|---|---|---:|---:|---:|---:|---:|
| Regional static 20 m | IN | 60.603 | 77.248 | 62.538 | 20.000 | 1839.255 |
| Regional static 20 m | OUT | 60.389 | 77.374 | 62.609 | 20.000 | 1838.645 |
| Adaptive Semantic First | IN | 68.526 | 73.802 | 61.796 | 17.935 | 347.665 |
| Adaptive Semantic First | OUT | 68.279 | 73.944 | 61.862 | 17.946 | 347.867 |

For IN, adaptive retains 7.923 percentage points more input than regional20,
reduces J by 3.446 points and has a much shorter mean logical delay. These are
descriptive paired-study mean differences; no confidence interval for utility
differences was predeclared. J combines omitted observations and retained
taxonomy loss, not spatial/temporal loss. Semantic loss among retained adaptive
contributions remains about 61.8%; high retention does not preserve every class
distinction. Retained-only detail/delay must be read with full-input coverage.

The fixed workload contains 19,200 10 m/1 s root-occupancy queries per source
and world. IN and OUT use their own sampled references. The first second has
nine sensor measurements and later seconds ten; initialization is not a
fabricated t=0 measurement. Exact answers require complete sampled support
from whole contained public tiles. The estimator separately assumes uniform
spatial allocation/constant temporal occupancy; unknown output is never zero.

| Method | World | Exact coverage (%) | Exact MAE and available-source N | Estimated coverage (%) | Estimated MAE and N |
|---|---|---:|---|---:|---|
| Regional static 20 m | IN | 0.00000 | NA; no exact answers | 13.910 | 1.351; N=32 |
| Regional static 20 m | OUT | 0.00000 | NA; no exact answers | 13.820 | 1.345; N=32 |
| Adaptive Semantic First | IN | 0.00309 | 0.000; N=14 | 12.508 | 1.260; N=32 |
| Adaptive Semantic First | OUT | 0.00277 | 0.000; N=13 | 12.439 | 1.254; N=32 |

All estimated metrics shown use N=32. Exact coverage also uses all 32 sources,
but exact MAE is conditional on having an exact answer. Adaptive exact MAE=0
exists in only 14 IN sources and 13 OUT sources; regional20 has no defined exact
MAE because no queries are answered exactly. The adaptive exact coverage is
only 0.00309% IN. Fixed 10 m/1 s answers 2.275% exactly but retains 28.936%
of IN input, exposing a different application tradeoff.

Adaptive estimated MAE is lower while estimated coverage is also lower than
regional20. This is not proof of better query answering on a common answered
set. Full-input retention and J alone miss the sparse exact-query service.
All present public macro means use N=32 except the adaptive exact-MAE N=14/13.
Other undefined exact-MAE entries remain absent/NA, not zero. Fixed10m/1s exact
MAE is defined on all 32 sources. Derived regional online/core runtime is
unavailable rather than zero.

Adaptive whole-recording core processing averages 32.846 s IN and 32.714 s OUT
for 300-s inputs, each N=32. This is offline batch processing. Logical seal delay
is aggregation/sealing time, not measured delivery latency. Neither measure
establishes per-step deadlines or live/real-time readiness.

## Movement quality and unchanged enrollment

| Split | Verified sources | Quality reports | Sources active at H | Sources pending at H | Sources with reported stalls |
|---|---:|---:|---:|---:|---:|
| train | 24 | 24 | 1 | 0 | 1 |
| calibration | 16 | 16 | 0 | 0 | 0 |
| test | 32 | 32 | 1 | 0 | 1 |

These are source counts, not numbers of affected people/tracks. Quality does not
filter enrollment; active/stalled movement remains in the risk and utility
inputs. It is not a privacy benefit. All sources pass the hard clock, GT/sensor,
provenance and physical/data requirements, while broader source realism and
navigation liveness remain limitations.

## Actual public-artifact QA and lineage

The public numeric/Markdown projection, actual PNGs and SVGs have bound artifact
hashes. Both actual PNGs were visually inspected after execution: all eleven
methods, representation/rate legends, units, source counts, captions and axes are
readable; no manual image edit changes data. The utility figure is the IN view;
OUT is retained in the full report. Independent public-projection checks match
the source values and reject private rows/IDs/paths/weights. Raw movement, model
payloads, individual labels and scores remain local.

The generated `repair-lineage-public.json` must accompany the numerical report,
its artifact receipt and both figures. Standalone numeric export does not carry
that amendment history. The outer publication packet binds the original failed
qualifications, corrected ledger, original model/row references, interpretation
and numeric artifacts. The final Git publication commit is packaging metadata,
not an unfinished numerical/validation gate.

## Final evidence hashes

| Artifact | SHA-256 |
|---|---|
| Original model lock | `d0d56de7d89ba7c51135f88584ad533b1bcb4e1aa309eb1af8e233c059e9be81` |
| Original model artifact | `62b34bcd88737d601ef1f6eabae95ac9ae51fc102189d1062d532e798af18a77` |
| Original 880-row artifact | `266b22c90303f62fce8644ba09d9c8da400ab6a3f141641f5a6058c3c6235a56` |
| Complete qualification ledger | `201890456e4b21b0f19bf7720c848bd2632d01d0a3935144b0e04f5d582c1f3e` |
| TEST execution receipt | `bbc7fd39673a3768d55ca5c6b633450c98e7bdb865e7d7aa4cd34d6abb58dbac` |
| Final raw/archive/report receipt | `450d73b801513420f1c7728c2d602ede742a806c1b3346cc9446d2ca7e877c0f` |
| Final private report | `70abeed6ff101fd51723a610a58120c5963db347510bfe630d882c5ad1509f71` |
| Statistical review, 9,244 comparisons | `08d13d5efa4d568b2f356b163687c22a502b432ee8777ff6ad45ddb27370f4a2` |
| Final provenance/execution audit | `28cec61ed99f45ed6b02ae6afb358ef2635407885a30198b95a1b1c590aadd72` |
| Public projection review, 1,147 checks | `25ef93bc21e34bdd78e904c63c1c2d3d14cc73a4c310bf4ecdaad68571180187` |
| Actual figure visual review | `94851cdbec8f5047345e814d60b296d9099063ff620566d50866c943710a42dc` |
| Aggregate public summary | `cfed694b1a34d97bc2aa99817f7cbde122cbec13bffd3c07199fa22f1e28ae72` |
| Numeric public artifact receipt | `ed37a59236b7586458e629f190f4606813af5726092363a1a21f6113fcc44b8f` |
| Required public repair lineage | `913e44823cbb85fd9d8242868ae3d27d5b0ae9bed503d07cfaa54923c1fd026e` |

## Conclusion

The declared execution and verification are complete. This supplies actual
held-out risk/utility evidence with passing controls and preserved repair
lineage. Additional privacy improvement over the predeclared regional20
baseline is **not demonstrated**, and equivalence is not established. Adaptive
mean retention, omission/taxonomy loss and logical delay improve descriptively
against that reference, while query coverage/error and retained semantics show
important remaining tradeoffs. These limits and the calibration failure to
generalize must remain alongside any presentation of the gains.
