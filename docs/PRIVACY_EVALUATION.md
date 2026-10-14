# Initial membership evaluation contract

Status: 2026-10-14. **Deferred:** the user selected utility and policy fulfilment first.
E02 already has a narrowly defined optional deterministic neighbour comparison, implemented
before that scope preference arrived. The helper and historical evidence are retained;
this document does not put further privacy experiments in the current work queue.
This is an offline stress test of recipient-visible releases. It is not a trained
membership attack, a general privacy score, or a proof of anonymity.

## Question and protected unit

The initial question is: **can a recipient with complete knowledge of the background
observations distinguish whether one target road user's recorded trajectory contributed
to the release?** Membership in the recorded input is the secret. This does not by
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
