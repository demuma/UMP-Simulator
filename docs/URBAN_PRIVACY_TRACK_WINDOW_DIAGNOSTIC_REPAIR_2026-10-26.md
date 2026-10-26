# Technical amendment before track-window TEST assessment

Date: 26 October 2026. **All 72 original inputs now pass the declared
hard-validity gate.** The source phase closed before the exact diagnostic
correction. All 32 corrected TEST physical audits, 40 authenticated legacy
proof reuses and 72 full raw-validation receipts pass. Independent provenance
review and the maintained readiness gate pass before any TEST mechanism,
feature extraction or scoring. Actual held-out privacy/utility results are
still pending. The [compact readiness evidence](verification/urban-track-window-2026-10-26-v1/diagnostic-repair/) records this pre-assessment checkpoint.

This is an operational qualification amendment to the existing
[track-window contract](PRIVACY_TRACK_WINDOW_CONTRACT_2026-10-26.md), not a new
protected unit, source simulation or fitted attack. “Before TEST assessment”
means before TEST recipient-feature extraction, scoring and method comparison;
TRAIN fitting and CAL threshold selection were already complete.

## Original evidence and source-phase closure

All 40 TRAIN/CAL method groups completed before TEST generation. Their
independently audited artifacts remain the exact originals:

| Artifact | Count |
|---|---:|
| Source groups | 24 TRAIN + 16 CAL = 40 |
| Native method/world executions | 720 |
| Regional-static method/world compositions | 160 |
| Method/world rows | 880 = 40 × 11 methods × 2 worlds |
| Converged and locked attack variants | 22 = 11 methods × 2 representations |

The additional auxiliary-only/no-output fitted controls and prior-only/
unprotected direct controls are also preserved. The
[public model-lock receipt](verification/urban-track-window-2026-10-26-v1/model-lock/summary.json)
was recorded in commit `3db24c5` before any TEST source generation. Its exact
private model-lock SHA-256 is
`d0d56de7d89ba7c51135f88584ad533b1bcb4e1aa309eb1af8e233c059e9be81`.
The independent audit checked TRAIN-only scaling, frozen model budgets and CAL
thresholds without refitting. Convergence is the frozen stopping-rule result,
not an exact stationarity guarantee.

The original prospective TEST source phase then closed **before** the canonical
auditor patch or promoted repair code was applied:

| Original phase outcome | Recorded value |
|---|---:|
| Planned TEST source slots | 32 |
| Attempted TEST captures | 32 |
| Completed native source-capture processes | 32 |
| TEST sources qualified under the original attempt | 0 |
| Original source-qualification failures | 32 |
| TEST mechanism groups | 0 |
| TEST model evaluations | 0 |

The capture phase returns normally after retaining all attempts. The subsequent
source gate requires 32 valid inputs, observes all 32 attempts and finds zero
qualified; it fails. The driver stops with TRAIN/CAL mechanisms, model locking
and source capture completed, before the TEST mechanism phase. No source is
replaced or silently retried. Original capture, audit-error, gate and driver
receipts remain unchanged.

The original failure wrapper reports that independent physical qualification
failed or did not complete; that status must not be relabeled as a physical
PASS. The diagnosed auditor exception is technical reporting failure. It is not
evidence that a substantive physical predicate rejected the recordings, and it
does not by itself prove those recordings physically valid. Completed native
capture is also distinct from completed source qualification or TEST attack
assessment.

## Diagnostic correction and actual validation

The returned `movement_coverage_quality.declared_building_count` diagnostic
originally indexed `building_id` on every declared portal. Valid
`surface_access` portals, including subway accesses, need not have a building
identity. The exception arises while constructing that diagnostic, after the
physical-check code path but before a complete audit result is returned.

The canonical correction now counts buildings only on non-surface portals:

```python
len({p['building_id'] for p in portals.values()
     if p.get('kind') != 'surface_access'})
```

The original auditor was archived and the exact one-field change was applied
only after original phase closure. Its SHA-256 changes from
`a4dd480680d9561579ae93be6d76c5a6e9af805dc6e24a839fd19aff26dce553`
to `f707c4adaa533cf610b238059d4ba583799ff2dff59f08eba40e159306e50269`.
It does not remove surface accesses from observation, geometry, speed,
lifecycle, entry/exit or collision checks. A non-surface building portal still
requires its building identity. Source C++, actual movements, physical
predicates, source law, input observations and profile/schema names are
unchanged; the profile remains `observed_track_window_v1`.

| Validation evidence | Verified outcome |
|---|---|
| Original positive surface-access fixtures | Two expected `building_id` errors |
| Corrected isolated regression/guard suites | 56 pass: 6 new, 19 physical, 11 legacy-source and 20 window-validator tests |
| Canonical portal regression | 6 pass; zero failures/errors |
| Latest current-code unit suite | 373 pass in 33.166 s; zero failures, errors or skips |
| Corrected compatibility-guard suite | 29 pass; exact actual auditor-byte preflight passes |
| Actual city DEV opt-in window-profile CLI | Exit zero, complete verified audit; no new native source job or model fit |

These are overlapping validation scopes and are not summed into a count of
independent observations or distinct tests. The earlier 371-test receipt is
retained as historical evidence; the current receipt is the later 373-test run.
Operational test/audit timings are not a mechanism latency or real-time bound.

The actual city DEV smoke closes the previously disclosed integration gap.
Earlier city DEV revalidation reused authenticated legacy physical proof and
did not exercise every explicit window-profile auditor CLI branch. The new
smoke invokes that opt-in CLI on an actual, already excluded production DEV
recording and returns a full corrected report, with two declared buildings and
eight destinations. It takes 48.770 s and creates no new source simulation.
This is DEV integration evidence, not TEST validation or privacy-benefit
evidence; it does not establish realistic movement or general crowd liveness.

## Safe preparation failure and field-qualified compatibility guard

The first promoted repair preparation stopped safely before creating its output
directory. Its code-compatibility guard searched for the original unqualified
`building_id` counting expression and expected one occurrence. The same old expression also
appears in an unchanged legacy-coverage check, so there are two occurrences in
the real original auditor. The guard rejected that ambiguity rather than
accepting an unverified code delta. No source requalification, native TEST job
or model fitting resulted from that failed preparation.

The corrected guard matches the exact `declared_building_count` field context.
An actual byte preflight confirms one qualified original field, one qualified
corrected field, the exact single-field replacement and preservation of the
separate legacy coverage expression. The 29 focused tests and independent
read-only code review pass. This is a correction to a false rejection in the
compatibility reader; it does not expand the allowed auditor change or weaken
the original legacy acceptance check.

The final helper and test SHA-256 values are
`d0d1f536106640f9b8b4a720d3bcd001f7d8cd8c489acf8f1f880d78263a818b`
and `80f1fa43ca1a40bf1a2a3dc1db6151f0b91457dfa60e43ffe2fd89b8251aee29`.
Preparation then succeeds under a separate repair-execution protocol, fixed
after the original source phase. That protocol prohibits source generation,
model fitting and TRAIN/CAL re-execution. The subsequent complete qualification
and readiness checks now pass; their actual evidence is recorded below.

## Unchanged inputs, models and held-out interpretation

The amendment uses all 72 original inputs in their original roles and with their
original source/target/auxiliary assignments. It preserves raw captures, old
failures, sidecars, original 880 rows, outputs, model weights, scales and CAL
thresholds. There is no movement resimulation, source replacement, target
reselection, refit, recalibration, score-direction change or performance-driven
comparator choice. Policies, methods, semantic/scalar features, controls,
query workload, retrospective availability and statistical definitions remain
unchanged.

Held-out attack assessment can remain valid under this explicitly disclosed
technical amendment because:

1. Models, scales and operating thresholds were locked before all TEST source
   generation and are imported byte-identically.
2. The repair responds to source-diagnostic schema exposure, not TEST recipient
   features, predictions, attack/control scores or method-performance results.
   Source diagnostics were exposed; the claim is not that nobody processed
   TEST source metadata.
3. The deterministic correction restores the existing meaning of a surface
   access. It changes no observations or substantive physical/data condition.
4. Every original input receives the same full raw-validation requirements.
   All 32 TEST inputs must pass before any TEST mechanisms; no helpful subset
   is selected and no available-case headline substitutes for the cohort.
5. The versioned repair reader, allowed delta, original locks and qualification
   ledger/readiness gate are authenticated before TEST output or scoring.

This is neither an untouched original software pipeline nor a new independent
population. Its statistical rationale is conditional on those auditable
preservation and no-tuning requirements. Any further substantive acceptance,
source-selection or model change is outside this amendment.

## Completed qualification and remaining assessment

The corrected worker completed successfully. Its ledger and independent
metadata audit authenticate these actual outcomes:

| Evidence | Verified outcome |
|---|---:|
| Original TRAIN / CAL / TEST roles | 24 / 16 / 32 |
| New full raw-validation receipts | 72 / 72 verified |
| New corrected TEST physical audits | 32 / 32 completed successfully |
| Reauthenticated original legacy proof chains | 40 / 40, truthfully labelled reused |
| Missing or failed new qualifications | 0 |
| Original imported method groups / rows | 40 / 880, unchanged |
| Original locked attack variants | 22, unchanged |
| Source replacements / resimulations / model refits / threshold retunes | 0 / 0 / 0 / 0 |
| TEST mechanism groups / TEST model evaluations at readiness | 0 / 0 |

This is 40 legacy-proof reauthentications plus 32 new corrected physical audits,
not 72 fresh physical audits or simulations. Full recording, GT, sensor,
configuration, source provenance, split/clone and physical requirements remain
mandatory. Movement completion, active/pending tracks, reported stalls and known
oscillations remain separate quality diagnostics. They neither filter enrollment
nor count as privacy benefits. No artificial EOF exit repairs an unfinished journey.

The maintained `--check` gate exits zero. An independent reviewer authenticates
all 72 receipts, role assignments, both physical-proof paths, original 40 sidecars,
880 rows and model-file hashes, and the zero-TEST-output state. That metadata
review does not claim an additional raw/physics reconstruction: those actual
checks were executed by the qualification worker. All previous failed receipts
remain unchanged.

| Remaining gate | Status at this readiness checkpoint |
|---|---|
| Complete 72-source qualification and immutable readiness binding | **VERIFIED** |
| Original TEST method families and fixed-model scores | **NOT RUN; next authorized step** |
| Joint privacy/utility/quality report with original-failure lineage | **PENDING; no result claimed** |

TEST execution and assessment must use the exact original sources, frozen
models/CAL thresholds, methods, features, query workload and statistical rules.
Any later results receive their own receipts; readiness alone establishes no
privacy benefit, utility advantage, realistic motion or real-time guarantee.

## Provenance anchors

The following hashes bind the completed correction, qualification and readiness
checkpoint. They do not claim an unseen TEST assessment result. The original
[profile/test report](URBAN_PRIVACY_TRACK_WINDOW_TEST_REPORT_2026-10-26.md)
and pre-TEST model-lock evidence retain their historical scopes.

| Anchor | SHA-256 |
|---|---|
| Original exact model lock | `d0d56de7d89ba7c51135f88584ad533b1bcb4e1aa309eb1af8e233c059e9be81` |
| Original fitted-model artifact | `62b34bcd88737d601ef1f6eabae95ac9ae51fc102189d1062d532e798af18a77` |
| Original 880-row artifact | `266b22c90303f62fce8644ba09d9c8da400ab6a3f141641f5a6058c3c6235a56` |
| Original source-phase closure | `1e6aecdd5d9ed8c0b115439b7499fa0eddadcf2686d09dc5e21965cd6af84002` |
| Original failed TEST source gate | `03bdaba8f2d6297dbf8bacf4c80d7fa3c2a75d87b70c75e4c6dd77cfc8188015` |
| Original auditor | `a4dd480680d9561579ae93be6d76c5a6e9af805dc6e24a839fd19aff26dce553` |
| Corrected canonical auditor | `f707c4adaa533cf610b238059d4ba583799ff2dff59f08eba40e159306e50269` |
| Canonical six-test portal receipt | `994ce3ea91e1491ec17e3b2e0ddaea86200f1cea4dc573467515c39881749139` |
| Current 373-test receipt | `bdf8287b455c24beab46e41f5d29598f584e5f5667855f7f1c79a1e20fff352e` |
| Actual city DEV CLI receipt | `9bacb2df9888c7ffd456dceef0b8f88e07874dfcd1c34bbf63f3e03887bad3cc` |
| Actual city DEV corrected audit | `9c469d6489a0ac1f3d28e868fc45fa68fdfc7fdb298a08840e9aab3a12255c7c` |
| 29-test guard receipt | `66f3b8f86fa5b34741df3196ec07577b344b219356e2b6a5eb9fa9828db2c08a` |
| Actual field-qualified byte preflight | `e7b2f5826ddc052687c30421727a6226e47aacdfd7eb4c5677a1ad2630313fa4` |
| Independent final guard review | `0903ad8392ab237d890b5574d5dcb7faa7a5355d5ae2ec16f5f24c4b57094cbb` |
| Prepared repair-execution protocol | `f8d15a0c40bbdfcf18888a25540f132763dc9b497fb0d18b0ff60eb2831f52a2` |
| Completed 72-source qualification ledger | `201890456e4b21b0f19bf7720c848bd2632d01d0a3935144b0e04f5d582c1f3e` |
| Independent completion metadata audit | `bd1a9883060caf6ebb93cb6a0c197221970a4e92e454bcf8424335dba843543d` |
| Maintained gate / pre-TEST readiness receipt | `f47676157daebfba9e7971d55a4bda48880e6433ff764e9906c423d0457caafb` |

Public evidence may expose fixed contract/profile names, aggregate outcomes and
hashes. It must exclude raw source/target/group identities, seeds, private paths,
configurations, movement, model coefficients, case labels and score rows. A
metadata correction is not a measured privacy gain, and no failed or absent
TEST assessment is presented as an attack result.
