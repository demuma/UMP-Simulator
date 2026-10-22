# Causal membership and deadline utility: fixed protocol

Date: 2026-10-20. Status: predeclared before generating or examining the fresh primary
cohort. This protocol fixes an evaluation extension, not a new anonymization mechanism.
The repaired C++ aggregation controller and its five configurations remain unchanged.

## Question and protected fact

**When does an observer gain evidence of whole-source membership, and how do retained
public history and useful data available by a deadline affect that evidence?**

The earlier attacks already saw the complete final publication transcript. Their absence
of a general local privacy benefit remains a result. This experiment adds causal timing,
a recent-history comparison and an auxiliary-only control without replacing that secret.
The protected unit is one candidate's complete recorded contribution over 16 seconds.
IN includes those observations; OUT removes them, preserving the physically existing
candidate, all background observations and measurement opportunities. This is neither
physical-presence protection, person identification nor sensitive-visit inference.

The study uses a balanced paired game. Real-world prevalence, realistic environmental
knowledge and optimal-adversary performance remain outside its interpretation. Measuring
membership on aggregate location time series has an established basis; see
[Pyrgelis, Troncoso and De Cristofaro, *Measuring Membership Privacy on Aggregate Location
Time-Series*](https://arxiv.org/abs/1902.07456). That work motivates the inference question;
its results do not establish the performance of this implementation.

## Frozen population, mechanisms and execution

| Item | Fixed choice |
|---|---|
| Dataset | Fresh `long_corridors_v2`, seed **20261023**, horizon 16000 ms, source cadence 100 ms |
| Independent groups | 48 base TRAIN, 32 base CAL, 64 base TEST, 64 count-shift TEST; each group has one matched IN/OUT pair |
| Scenario families | Sparse, dense, handover and heterogeneous synthetic corridors, inherited generator; no real city or semantic visits |
| Geometry/policy | 80 m square, observation depth 6, support threshold 3, permitted 1.25–40 m cells, maximum 1000 ms age/window, base 400 ms and 100 ms extensions |
| Mechanisms | Fixed 20 m/1000 ms; common Temporal First/Spatial First; repaired local Temporal First/Spatial First |
| Controls | Exact-count public stream and no-output public stream; auxiliary-only attack additionally fitted once per knowledge/family/checkpoint |
| Checkpoints | 1000, 2000, 4000, 8000, 12000, 16000 ms |
| Recent public memory | Entire releases with logical availability in `(t-1000,t]` |
| Knowledge | Causal independent 25% Bernoulli sightings, exact or spatially/time-uncertain; details below |
| Attacks | Existing fixed logistic regression and pinned histogram gradient boosting configurations; no tuning on this TEST set |
| Uncertainty | 400 scenario-stratified paired source-group bootstrap resamples; pointwise 95% intervals conditional on fitted models/thresholds |

The preserved project convention is Temporal First = preserve temporal resolution by
trying spatial aggregation first; Spatial First = preserve spatial resolution by trying
temporal aggregation first. These names must not be silently reversed.

Execute each mechanism on the complete 16-second source exactly once, with the existing
independent policy/ownership audits and four deterministic repeats. Freeze a completed
robustness bundle (2080 audited mechanism executions). Its legacy final-history analyses
are ancillary; they cannot select new features, thresholds, mechanisms or checkpoints.
The new prefix runner reads and verifies that bundle and the source dataset. It does not
rerun truncated simulations, force early EOF, modify releases or deserialize its models.
All source/data/artifact hashes and the evaluation protocol are retained privately.

At logical time t a public record is available iff `sealed_at_ms <= t`. This explicitly
assumes instantaneous recipient delivery. Include or exclude an entire record; do not
clip its count or source interval at t. Use the declared public horizon of 16000 ms for
feature normalization, never a future-derived last-release time. Filtered aliases are
renumbered canonically. The 16000-ms checkpoint includes actual EOF effects and is labeled
separately from the interior checkpoints. No wall-clock or network-latency claim follows.

## Causal auxiliary knowledge and attack representations

For each actual candidate sighting at source time s, select it independently with
probability 0.25 using a deterministic key derived from the knowledge seed and s. Adding
future sightings cannot change earlier selections. Exact and noisy profiles use the same
selected sightings. Noisy coordinates add independent Gaussian noise with sigma 2 m;
reported time adds integer-uniform jitter in [-200,200] ms. Clip coordinates into the
half-open coverage and reported time into [1,H-1], recompute the public cell ID and remove
identical reported triples causally after their arrival.

Preserve acquisition time s in private provenance. The recipient receives the observation
at `max(s, reported_time)`, so negative jitter cannot reveal a future physical sighting.
This conservative delayed observation channel changes precision and sometimes arrival;
exact/noisy differences must not be attributed to precision alone. Only the public
reported time/coordinates/cell are passed to features. Both membership worlds and every
mechanism receive exactly the same permitted knowledge at each checkpoint.

This independent Bernoulli selection intentionally differs from the old fixed fraction
of the complete trace. Comparisons to old final-study AUCs are not controlled estimates
of a memory or timing effect.

K is a nine-element auxiliary-only vector: sighting count, mean x/y, standard deviation
x/y, minimum/maximum/mean reported time, and first-to-last Euclidean displacement sorted
by reported time. Empty knowledge has the declared all-zero vector. The three arms are:

- **Auxiliary:** K only (9 features).
- **Recent:** K plus the existing 31 public/matching features on recent releases (40).
- **History:** K plus those same 31 recent features plus 31 cumulative-prefix features (71).

History contains the entire recent representation. A finite learned classifier can still
perform worse after extra features are added; this is not a theorem that stored history
reduces an optimal attacker's knowledge. Both public arms keep all *causally acquired
auxiliary knowledge*: the memory contrast concerns release history, not auxiliary memory.
Private labels, scenario/distribution names, road-user IDs, acquisition provenance,
raw observations, debug state and future values are excluded from prediction features.

## Fitting, repeated decisions and reported statistics

Fit a separate model at every checkpoint using TRAIN only. There are 336 public-view
fits (7 streams x 2 views x 2 profiles x 2 families x 6 checkpoints) plus 24 auxiliary-only
fits, totaling **360**. Save all models/metadata, features, CAL score paths and TEST score
paths. This closes the previous missing saved HGB calibration-score audit step.

For each fixed stream/view/profile/family, take the maximum of a CAL subject's six scores.
Choose one threshold on these maxima using the existing maximum-TPR rule subject to
empirical **ever-positive** FPR <= 0.10. Freeze this threshold for both TEST populations.
This controls the observed CAL repeated-decision criterion, not a formal population FPR
bound; with 32 negative CAL groups it is necessarily coarse. No TEST recalibration,
checkpoint/model selection or pooling of independent TEST cohorts is allowed.

Report all six score AUCs, cumulative first-alarm TPR/FPR/advantage and first-alarm timing.
Also report max-score AUC and the final ever-alarm operating point. The cumulative alarm
indicator and its TPR/FPR are nondecreasing; score AUC and advantage need not be. Thresholds
are separate for each family/view/profile: no claim covers an observer who chooses among
all these attacks without joint calibration. The 60 score-path experiments yield 120
cohort assessments and 720 checkpoint assessments; all are retained, including controls.

Report paired history-minus-recent and release-view-minus-auxiliary AUC contrasts within
each cohort. Resample complete source groups, keeping paired worlds, checkpoints and
contrasted methods together; individual windows or release rows are not independent
replications. Confidence intervals are pointwise, not simultaneous, and condition on
training/calibration outcomes. The paired construction makes the auxiliary-only control
exactly label-invariant (AUC 0.5 and equal TPR/FPR); no-output plus knowledge must also
remain invariant. Exact-count is a diagnostic comparator, not a proven privacy bound.

## Deadline-aware occupancy utility

Use fixed 10 m spatial cells and 1000 ms query intervals, independently of adaptive output
cells/windows. Score each query using only releases available by its own end plus lag,
for lags **0, 200, 500, 1000 ms**. Reuse the declared occupancy estimator and reference:
complete spatial/time observation support is required; a partial answer or null mean is
unknown, while a measured zero is an answer. Never replace absent sparse output by zero.

The primary interior cohort is fixed across all lags: `query_end + max(lags) < H`, so query
ends are 1000 through 14000 ms, **896 queries per world**. Every primary deadline precedes
EOF. This avoids treating future/not-yet-due queries as misses or allowing later deadlines
to change the denominator. Queries ending at 15000/16000 ms are a separate boundary
analysis; deadlines beyond H are censored rather than counted as observed misses.

Report timely query coverage, answered-only MAE and matched-query MAE for common/local
comparisons, with their denominators. Coverage must be nondecreasing as a deadline relaxes
on a fixed cohort. Conditional MAE need not improve because the set of answered queries
changes. Logical release age and timely availability are distinct from execution time,
transport delay and actual client receipt. This is a replay evaluation, not a live service.

## Checks and decision rule

Before the primary run, test future-release exclusion, noisy-sighting causality, exact
boundary inclusion, alias/schema validity, immutable inputs, nested feature blocks,
IN/OUT knowledge invariance, TRAIN/CAL/TEST isolation, repeated-decision calibration,
complete persisted score paths, fixed deadline denominators, measured zero versus missing
support, censored EOF deadlines and malformed/tampered artifact rejection. Run the full
existing regressions. Independently recompute held-out metrics, calibration thresholds,
selected feature/control cases, source/hash provenance and deadline results from saved
raw inputs outside the completed bundles.

A useful result may expose timing risk, a utility trade-off or a failure of a bounded
attack to detect an effect. It is not guaranteed to demonstrate a local privacy advantage.
No outcome permits retuning this TEST set. Any next mechanism change or semantic-visit
experiment requires a new fixed contract and independent evidence. We introduce neither
a runtime risk guard nor a differential-privacy budget. Formal continual-observation
privacy is a separate mechanism/analysis problem; see
[Dwork et al., *Differential Privacy Under Continual Observation* (2010)](https://www.microsoft.com/en-us/research/publication/differential-privacy-under-continual-observation/).
