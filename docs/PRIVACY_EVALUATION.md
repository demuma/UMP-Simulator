# Privacy evaluation roadmap and membership stress-test contract

Status: 2026-10-19. **The first controlled synthetic empirical path is implemented.**
The user authorized the complete independent-check/data/attack implementation. The selected
E02-A–C contract, code and reproduction are in
[EMPIRICAL_PRIVACY_IMPLEMENTATION.md](EMPIRICAL_PRIVACY_IMPLEMENTATION.md); actual results
are in [TEST_REPORT_2026-10-19.md](TEST_REPORT_2026-10-19.md). Real-world attacker realism,
sensitive-attribute studies and formal guarantees remain open. E02-D is future work.

The roadmap below preserves the design rationale and initial proposal. Its first empirical
instantiation is now fixed: source-contribution inclusion, exact partial candidate knowledge,
independent seeded reference realizations, grouped splits, logistic classifier, calibration
and public-only held-out testing. The historical deterministic diagnostic remains separate.

**Current focus after coordination refinement:** a fixed 184-realization common/local
source-membership comparison now uses the corrected controller and spatially scoped public
features. See [the protocol and results](PRIVACY_COORDINATION_STUDY_2026-10-19.md). Its exact
candidate knowledge and synthetic background limit any real-world interpretation.

## What already exists and what remains open

| Requirement | Existing diagnostic | Remaining empirical-study work |
|---|---|---|
| Attacker model | Complete background and candidate-trace knowledge, deterministic algorithm | Limited and reproducible auxiliary knowledge; explicit public-only attack input |
| Protected unit | One simulated road user's complete recorded trace in the declared horizon | Freeze the horizon/sensor/application scope; do not reinterpret a vehicle as its occupants |
| Secret | Whether that trace was included in the recorded input to the mechanism | Confirm membership as the first primary secret; later visit/attribute secrets need separate contracts |
| Auxiliary/reference knowledge | Every background trace in the strong diagnostic | An independent reference-data source, target-knowledge sampling and uncertainty model |
| Training/calibration/test | Not required for exact transcript equality | Independent grouped splits and leakage checks for a learned attack |
| Attack | Ideal comparison of two known deterministic transcripts | Implement and validate a bounded-knowledge empirical attack |
| Metric | Known-background distinguishability and derived balanced-game success | Measured ROC-AUC/operating-point performance, baselines and independent uncertainty |

The table records the original readiness gaps. The first synthetic implementation now
supplies bounded knowledge, grouped splits, a calibrated attack and empirical metrics under
the linked implementation contract. The stronger diagnostic and its historical results
below remain separate evidence; neither study validates real-world protection.

## Proposed primary study: contribution membership

**Proposed research question:** under which scenario and attacker-knowledge conditions does
adaptive aggregation reduce contribution-membership inference relative to legal fixed
aggregation, and at what cost in application utility, availability and age?

This is a hypothesis to test. Larger cells, longer windows and larger support thresholds
are not assumed to improve empirical protection monotonically. Data-dependent selection
can change what the output geometry and timing reveal.

| Contract field | Proposed first empirical setting |
|---|---|
| Observer | External recipient of one application's approved AGBS aggregate stream |
| Protected unit | One simulated road user's entire recorded contribution within a fixed, predeclared evaluation horizon |
| Secret | Whether the target's contribution was included in that input; distinct from physical presence, identification or a sensitive visit |
| Neighbours | Add/remove the target from frozen observations; preserve every background trace, sampling opportunity and measured-empty batch |
| Visible information | Ordered public counts, cells, intervals, logical release times, policy metadata and observable no-release periods over the same horizon |
| Excluded information | GT, raw sensor collections, identity unions, private candidates/journal, suppression causes and debug/live-progress overlays |
| Auxiliary knowledge | Public algorithm/policies, a declared partial candidate trace and independently generated/collected reference traces from a specified scenario population |
| Target knowledge | Predeclared fractions or numbers of space/time observations, with explicit coordinate/time precision and noise; no access to the hidden target contribution label |
| Prior | Balanced IN/OUT cases for the first controlled game; deployment prevalence is separate and must be supplied before interpreting positive-prediction precision |
| First attack | A transparent binary classifier using declared public count, geometry and timing features; model/feature selection uses training/calibration data only |

An attacker can know where a target travelled without knowing whether a separate data source
included its observations. This makes contribution membership a meaningful first secret.
If the sensor is assumed to capture every physically present target and the attacker already
knows that fact, the proposed membership question can become trivial. Declare capture/
inclusion assumptions; do not call this experiment physical-presence protection.

Neither membership inference nor this first study requires an invented sensitive attribute.
The aggregate-location literature motivates this choice: see the primary references below.
A synthetic controlled study establishes evidence under its generator and knowledge model;
it does not by itself validate real-world attacker realism.

## E02 staged work packages and entry criteria

### E02-A — Freeze the scientific and visibility contract

The first offline instantiation is fixed in the linked implementation contract. Before a
live/external extension, finalize its unit, horizon, secret, prior, auxiliary source,
knowledge levels and public schema. Check that an assumed external recipient actually has
no access to raw MongoDB collections, debug overlays or the private journal; collection
separation alone is not access enforcement. State the logical-time/transport scope and
which application views are visible. The first study uses one immutable application stream;
multiple visible Policy Trees/views require a later joint-transcript extension.

### E02-B — Build labelled cases after the minimal utility/policy milestone

Entry: independently checked release semantics (EP01), a controlled utility/policy comparison
and a frozen recipient schema/query. Reuse frozen input and capture provenance; realistic
maps, shop demand and a general route planner are not prerequisites. Broader EP03/EP04
studies can reuse the same independent realizations once the utility-first milestone is met.

Select targets independently of release/suppression outcomes. For each case preserve paired
IN/OUT inputs without rerunning movement; otherwise changed interactions can alter background
traces. Hash/validate background equality. Create independent source realizations for
training, calibration and final testing. Keep all windows, IN/OUT variants and mechanism
outputs from one source realization in the same split. Group reused or cloned traces/people
where required by the claimed generalization; random IDs do not make copies independent.
For a target-specific attack, explicitly permit the same candidate target across independent
background cases and scope the claim accordingly. No test release label may enter training,
feature design, calibration or reference fitting.

### E02-C — Implement one empirical attack and paired comparison

Start with declared, inspectable features and a simple classifier. Public reconstruction
must use a common feature/query coordinate system, retain unknown/missing masks, and never
fill gaps from GT or private measured-empty/suppression diagnostics. Feed the attacker all
permitted history; compare count-only against count-plus-geometry/time features as a
leakage diagnostic. Projection differences are not additive causal privacy contributions.

Train/calibrate fairly for each known mechanism with equivalent reference-data budgets;
training only against an unprotected mechanism can underestimate an adaptive-aware attack.
Use the existing legal fixed baselines, spatial-only, Temporal First (space aggregated
first) and Spatial First (time aggregated first), on identical held-out inputs and policies.
Include prior-only, exact-count and no-output controls. A no-output mechanism has no
release information in this protocol but zero answered-query coverage.

Predeclare ROC-AUC and TPR/FPR operating points. Choose score direction, hyperparameters
and thresholds on training/calibration data, then freeze them. Report observed test FPR
alongside TPR; a very low FPR claim needs enough independent negative cases to resolve it.
If reporting advantage, define it at the selected threshold as TPR minus FPR. Report the
membership prior and suitable precision/base-rate interpretation separately from balanced
accuracy. Failed attacks show resistance only to the evaluated attack and knowledge model.

Report paired mechanism differences and uncertainty using independent source realizations
as the top-level sampling/resampling unit; targets/windows within a realization are dependent.
Choose replication from pilot variability and desired precision, not an arbitrary run count.
Show attack outcomes together with fixed-query occupancy error, full-domain/common-support
coverage, retained contributions and simulated release age. Compare trade-off curves and
include cases with no privacy improvement or utility loss. Do not define a universal privacy
score as one minus attack accuracy.

Exit: a reproducible frozen test report with a versioned threat model, split manifest,
validated public-only features, controls, uncertainty and utility trade-offs. If the method
fails to lower attack success, report that result and examine the release mechanism rather
than replacing the secret or metric after seeing final tests.

### E02-D — Extend only from an explicit research need

Possible next secrets are a sensitive-region visit, trip purpose or trajectory linking.
Each needs its own label, time scope, attacker prior and baseline. A shop or corridor is
not inherently sensitive; semantic labels and physical maps do not supply that argument.
For a visit secret, the attacker must not already know the visit being tested.

Formal k-anonymity/l-diversity/t-closeness require a justified record/QI/group/attribute
mapping; current distinct-ID support is not such a proof. An offline attack score is also
not automatically a per-bucket online metric: the Policy Tree can select implemented
release requirements, but cannot infer calibrated attack risk from a local count alone.
A future online risk estimator would need separate calibration and out-of-sample validation.

A differential-privacy mechanism would be a separate design decision, including protected
contribution bounds, privacy accounting over repeated releases and the disclosure of adaptive
partition/timing decisions. Adding noise to a count after a data-dependent partition does
not by itself justify a DP claim. DP is not currently implemented or required by this plan.

## Existing diagnostic contract

The remaining sections document the implemented deterministic stress test. They are kept
separate from the proposed empirical study above.

## Question and protected unit

The initial question is: **can a recipient with complete knowledge of the background
observations distinguish whether one target road user's recorded trajectory was included
in the mechanism's input?** Membership in the recorded input is the secret; an IN target
remains an IN target even if all of its contributions are suppressed. This does not by
itself measure identification, the target's exact physical location, or a sensitive
attribute. A road user is one simulator agent; a vehicle agent does not represent all
of its occupants.

Let D be one recorded sequence of observation batches and D-minus-i be the same
sequence with every contribution of target i removed. This is an add/remove,
whole-recorded-trajectory neighbouring relation. Observation timestamps, sequences,
measured/unavailable status, coverage, sampling period, evaluation horizon, policy,
strategy and initial aggregator state remain equal. A measured batch that becomes
empty remains measured-empty. Other road users keep their recorded trajectories.
Do not rerun the motion simulator without the target: changed collision avoidance
would alter other people's input as well.

The attacker knows the aggregation algorithm, policies, the target's candidate trace,
and every background trace. The attacker can therefore compute the two deterministic
candidate transcripts. A fair hidden coin selects which input generated the observed
transcript. The no-output baseline success probability is one half under this specified
prior. This deliberately strong knowledge model is useful for detecting residual
information; it is not an assumption about every real recipient.

## Compared information

Compare the entire ordered recipient release sequence over the same fixed horizon,
including all released scalar counts, cell geometry, interval boundaries and logical
release time. Changing the number of releases or their absence is observable. A
privacy test on counts alone would miss data-dependent aggregation geometry and timing.

The comparison excludes internal candidates, progress frames, suppression counts,
identity unions, journal records and private empty-window retirement. These are not
recipient releases. It also normalizes run-specific random identifiers and canonical
cell ordering. Policy/model identifiers remain when the replay output exposes them.
It does not model wall-clock runtime, transport latency, network packet sizes or
multiple applications viewed together. Such channels need a separate protocol and
study; ignoring them does not establish that they are harmless.

The Python helper accepts the explicit replay output schema, rather than arbitrary
MongoDB/debug documents. Unexpected fields within a release or cell are rejected so
that adding a new public field cannot silently bypass the comparison.

## Measures and interpretation

For deterministic aggregation M and the canonical public transcript T, define

```
d_i = 1 if T(M(D)) != T(M(D-minus-i)), otherwise 0
R_known_background = sum(d_i) / number_of_tested_targets
```

`R_known_background` is the **known-background distinguishability rate** on the
explicitly tested traces and targets. For one neighbouring pair, an ideal observer
with the stated complete knowledge succeeds with probability `(1 + d_i) / 2`.
If both transcripts match, either hidden input produces the same observation. If they
differ, the observer identifies the hidden input exactly. Averaging gives
`(1 + R_known_background) / 2` for the balanced game. This is a mathematical consequence
of deterministic equality, not measured classifier accuracy. No AUC is calculated.

The helper also compares the count projection and the geometry/time projection.
These are diagnostic differences, not independent or additive privacy contributions.
For example, a changed spatial partition can also change the sequence of count tuples.
The full transcript comparison is authoritative.

Exact counts commonly make this strong test saturate even after aggregation. A low
support threshold or a larger cell is not enough to imply membership indistinguishability.
A different transcript for a tested pair demonstrates distinguishability under the
specified knowledge. Identical transcripts for tested pairs do not prove a guarantee
for all possible datasets or protection against other attacks. In particular, this
experiment does not establish k-anonymity, formal delta-presence or differential privacy.

Report the target list and scenario, changed-pair numerator and denominator, input
hash, policy parameters and aggregation mode. Sample targets independently of whether
they were released or suppressed; selecting only surviving releases would bias the
result. Treat results from one replay as descriptive. Road users from the same replay
are dependent; do not attach a population confidence interval by pretending they are
independent simulation runs.

## Controls and comparison protocol

1. Use the same saved observation input for fixed aggregation, spatial selection,
   Temporal First and Spatial First. Change only the declared mechanism parameters.
2. For each selected target, replay the full input and its target-removed counterpart
   from the same initial state through the same exclusive end time.
3. Assert that removing the target changes no other observation or batch metadata.
4. Confirm that changing only run identifiers does not change the canonical transcript,
   and that count, geometry and logical timing changes are detected.
5. Confirm that private diagnostic changes do not change the public comparison.
6. Include an unprotected exact-count control and a no-output control. No output yields
   zero distinguishability in this model but also zero answered-query coverage.
7. Report the fixed-query occupancy error and answered-query coverage alongside this
   privacy stress test. Suppressing more data must not be described as an overall
   improvement without its utility cost.

## Subsequent empirical attack study

A weaker, more realistic attacker will need an explicit auxiliary-data model: for
example, a partial target trace plus independently collected background traces.
A trained classifier needs disjoint training/calibration/test scenarios, with all
related windows and paired variants of one run kept in the same split. Thresholds
must be selected without the test labels. Report ROC-AUC and operating-point TPR/FPR,
together with the prior-only baseline, the target distribution and uncertainty over
independent runs. Such a classifier study remains future work. Its accuracy cannot be
inferred from the deterministic neighbour comparison.

## Primary research context

[Pyrgelis, Troncoso and De Cristofaro, *Knock Knock, Who's There?* (NDSS 2018)](https://www.ndss-symposium.org/wp-content/uploads/2018/02/ndss2018_05B-5_Pyrgelis_paper.pdf)
formulate membership inference on aggregate location time series as a distinguishing
game and evaluate learned classifiers under several knowledge assumptions. Their
AUC-derived privacy-loss measure belongs to that classifier experiment; we do not
reuse its name for an equality indicator.

[The same authors, *Measuring Membership Privacy on Aggregate Location Time-Series*](https://arxiv.org/abs/1902.07456)
evaluate several defenses and mobility utility tasks, supporting the need to pair
privacy measurements with a declared application rather than assume one universal
privacy/utility ranking.

[Guan et al., *A Zero Auxiliary Knowledge Membership Inference Attack on Aggregate
Location Data* (PoPETs 2024)](https://www.petsymposium.org/popets/2024/popets-2024-0108.pdf)
show that aggregate mobility membership attacks need not rely on a large auxiliary
dataset of real traces. Their threat model still specifies target knowledge and a
synthetic reference-generation method. Our full-background test is simpler and
stronger in background knowledge; it is not a replication of their attack.

[Dwork and Roth, *The Algorithmic Foundations of Differential Privacy*](https://www.microsoft.com/en-us/research/publication/algorithmic-foundations-differential-privacy/)
provides the separate formal-mechanism framework; the present deterministic aggregation
pipeline makes no differential-privacy claim.

The deterministic equality test and balanced-success formula above are our scoped
experimental design and elementary derivation, not a new empirical result attributed
to these papers.

## Historical exploratory pilot, outside the current milestone

Before the scope preference arrived, the optional helper ran alongside the first utility
pilots. In the heterogeneous fixture all three tested targets changed the public transcript
for all seven configurations; in the handover fixture all four did. In the simulator capture,
both 10-m fixed baselines changed two of three target transcripts; the other five modes
changed all three. These are descriptive strongest-background checks, not realistic attack
accuracies or population estimates. Raw results remain in the original private bundles under
`results/evaluation/2026-10-14/`; the active utility/policy report omits these columns.
