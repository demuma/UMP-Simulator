# Controlled selective-contribution suppression study

Declared: 28 October 2026, before new study execution or fitting.
Status: implementation and excluded-DEV validation. This declaration stays immutable;
execution status and results belong in a separate test report.

## Question and comparison

Does bounded selective contribution suppression improve retained information when
semantic generalization is already permitted, and how does the resulting public
stream affect the existing measured membership-inference risk?

The comparison changes one action permission: selective suppression OFF (cap zero)
versus ON (cap 0.10). Semantic generalization is enabled in **both** conditions.
The seven disabled references and their already evaluated attacks are imported
exactly. Seven new permitted variants use the same source recordings, target
tracks, auxiliary information, taxonomy, hard support/geometry/time/loss bounds
and strategy definitions. No source replacement, new trajectory or TEST-driven
policy/threshold tuning is allowed.

| Base method ID | New method ID |
|---|---|
| fixed20_400ms | fixed20_400ms_selective |
| regional_static20 | regional_static20_selective |
| adaptive_temporal_first | adaptive_temporal_first_selective |
| adaptive_spatial_first | adaptive_spatial_first_selective |
| adaptive_semantic_first | adaptive_semantic_first_selective |
| adaptive_semantic_wait_temporal | adaptive_semantic_wait_temporal_selective |
| adaptive_semantic_wait_spatial | adaptive_semantic_wait_spatial_selective |

The project's existing naming applies: Temporal First preserves temporal detail,
Spatial First preserves spatial detail, and Semantic First preserves semantic
detail according to its declared secondary order and release trigger. No new
suppression-priority strategy or selection objective is introduced here.

## Action and policy contract

The existing native action omits all contributions of selected unsupported
terminal taxonomy classes within an owned cell-window. It does not relabel a
cyclist as a pedestrian, remove simulated people or suppress a whole track across
all windows. The root requirement becomes
`semantic_suppression_fraction: {max: 0.10}`. Existing regional caps, including a
prohibition, remain unchanged and the strictest overlap applies. Baselines
receive exactly the same permission as adaptive procedures.

The cap divides selectively omitted observations by the candidate's original
observations. It is not ten percent of people or of the whole recording. Failed
whole cell-windows may still be withheld separately. All retained support,
semantic, occupancy, geometry, timing and complete-sampling constraints are
rechecked after selection.

Keep the already implemented candidate objective:

\[
J_c=\frac{N_{\mathrm{sel}}+\sum_b n_b\ell_b}{N_c}.
\]

A selective alternative is eligible only when every retained requirement passes,
its omission fraction is within the effective cap and its full-input loss is
strictly lower than the ordinary unsuppressed semantic representation. This is
a local candidate rule; it does not guarantee improved full-run scheduling or
utility. No cap sweep, penalty change, arbitrary individual-subset search or
semantic-OFF/selective-ON method belongs to this study.

The historical root support is five distinct operational tracks and five per
published category, with the existing stricter local bounds. Input geometry is
80 m square, depth six (1.25 m source leaves), maximum output side 20 m. Existing
400–4000 ms window bounds, 100 ms extension step, 100 ms sensor cadence and 50 ms
progress clock remain unchanged. The canonical original configuration and every
new variant are hashed by the machine protocol; this paragraph is not a substitute
for the complete local Policy Tree.

## Data, scope and denominators

Reuse the same 72 authenticated recordings: 24 TRAIN, 16 CAL and 32 TEST, each
with its fixed IN/OUT pair. The protected unit remains **all observed contributions
of one operational track inside [0,300 s)**, not a physical person, all building
visits or a completed journey. The original quarter-count position/time target
sightings and seven source road-user types remain unchanged. Movement quality is
separate from privacy evaluation.

TEST was exposed by earlier studies. All new comparisons are therefore explicitly
exploratory on reused sources, not a fresh confirmatory holdout. Fitting still
uses TRAIN only; calibration still uses CAL only. No observed TEST outcome may
change method definitions, source selection, scaling, objective or thresholds.

| Quantity | Fixed total |
|---|---:|
| Headline methods | 14: seven imported and seven new |
| Imported headline rows | 1008 |
| New headline rows | 1008 |
| New native executions | 1296 |
| New regional compositions | 144 |
| Auxiliary fixed-window rows | 432 |
| New MIA models | 14: seven methods × two representations |
| Reused headline MIA objects | 14, plus four unchanged controls |

Auxiliary fixed 20 m windows of 1000, 2000 and 4000 ms are required to compose the
new regional baseline, together with its 400 ms case. They are independently
audited but are not additional headline methods, MIA hypotheses or query workloads.
The regional schedule remains the longest geometry/duration/age-admissible window
chosen from public policy and geometry before reading observations. It selects
from freshly filtered fixed cases; it never filters an old final transcript.

## Utility and public count interpretation

Report equal-recording TEST IN/OUT means with available denominators: retained
fraction, semantic distortion, spatial detail, interval duration, logical sealing
delay and per-original-type/per-original-region retention. Separate selective
omissions from whole-footprint omissions. Full-input utility is

\[
J=\frac{N_{\mathrm{input}}-N_{\mathrm{retained}}
          +\sum_{\mathrm{retained}}\ell}{N_{\mathrm{input}}}.
\]

This score includes all omitted observations, excludes spatial/temporal distortion
and is not a privacy metric. Conditional retained semantic loss cannot establish
success when rare groups disappear. Zero retained observations give undefined
conditional means, never artificial zeros.

Filtered public counts describe the retained population. Even a complete public
tile is not a certificate of the original population count. Preserve the old
10 m/1 s scalar and 20 m/400 ms taxonomy query definitions; for new filtered
products, original-source exact answers are unavailable by contract. Evaluate
public-count proxies separately, with error and signed bias against each world's
own original reference. Missing support and semantic ambiguity remain unknown;
private masks and original data cannot repair recipient predictions. The old
unfiltered exact-query results remain unchanged. Delays use positive retained
observation support, avoiding the known legacy empty-key maximum diagnostic.

For each of the seven paired permission changes, report six utility differences
on jointly available TEST IN recordings: retention, J, conditional taxonomy loss,
mean retained cell side, interval duration and mean logical delay. Use 1000 paired
recording bootstrap samples, seeds 20261028701 through 20261028707 by method order,
linear 95% percentiles. With fewer than two available pairs, no interval is
reported. These are marginal descriptive intervals, not simultaneous significance
or equivalence tests.

## Attack definition and comparisons

Use the existing Full111 (`semantic111`) and Scalar31 (`scalar31`) feature sets,
L2 logistic fitting (lambda 0.1, max 500 iterations, tolerance 1e-8), TRAIN-only
scaling and CAL empirical FPR target 0.10. This target is not a bound on TEST FPR.
Reuse the fourteen old headline objects, old thresholds and all controls exactly.
Fit fourteen new objects only after complete independent utility verification.
Publish/lock the new model hashes and aggregate convergence/calibration diagnostics
before new TEST scoring; fitted parameters, thresholds, row features and scores
remain local.

Report AUC, TPR/FPR and exact binomial uncertainty. Seven primary exploratory
contrasts are AUC(new selective variant) minus AUC(same disabled method), using
1000 paired-recording bootstrap samples with seeds 20261028501–20261028507.
Five additional exploratory comparisons are each new adaptive method minus the
new regional static baseline, seeds 20261028601–20261028605. Both representations
use the stated seed for their contrast. All intervals are marginal 95% intervals,
conditional on fixed TRAIN models/CAL choices. No superiority/equivalence claim
follows from crossing zero. Full111 versus Scalar31 is not a pure semantic-leakage
ablation because multiple feature families differ.

## Execution and verification gates

1. Preserve all historical code, inputs, models, outputs and failures. New files
   and the existing archived-producer bridge authenticate reused evidence.
2. Run synthetic/native filtering, regional composition, query, runner, reporter,
   parallel scheduling and model-stage regressions. Independently review changes.
3. Test all eighteen new native paths and two regional compositions on one
   excluded CITY DEV IN/OUT pair, using an exact 120-second prefix that retains
   all original DEV auxiliary sightings. No new target is selected. DEV is not
   one of the 72 scientific source groups.
4. Freeze contract, variant configurations, code/tests, unchanged binary and
   method/split/seed inventory. Publish compact pre-execution evidence before
   actual runs.
5. Execute whole recordings with six spawned workers, distinct output directories
   and one coordinator lock. Preserve within-recording event/method/dependency
   order. Reserve disk headroom centrally. Failures stop new admission, preserve
   in-flight outcomes and prevent partial success or automatic retries.
6. Collect all 2016 headline and 432 auxiliary rows in manifest order. Independently
   check source/public conservation, retained policy compliance, omissions, utility
   arithmetic, old-row preservation and the complete family. Publish utility
   evidence before fitting.
7. Fit fourteen new TRAIN models, calibrate only on CAL, independently verify and
   publish their immutable lock. Score TEST only afterward. Check all original
   scores/controls/primary results reproduce exactly.
8. Independently audit final scores, denominators, uncertainty and model reuse;
   visually verify exported figures and write the final test/interpretation report.

Concurrent process timings measure batch throughput, not isolated strategy speed
or real-time deadlines. The short six-worker DEV timing pilot is a separate
engineering check and is not treated as a guaranteed full-study acceleration.
No source generation, second attack, new policy search, real-time/privacy guarantee
or tracking-error study is introduced by this protocol. Raw movements, models and
individual scores remain local; only sources/tests/docs and compact aggregate
results are eligible for Git.
