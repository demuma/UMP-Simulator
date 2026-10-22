# Local coordination: causal replay, freshness and missed merges

Date: 2026-10-19. Status: post-hoc diagnosis of the completed
[privacy robustness study](PRIVACY_ROBUSTNESS_STUDY_2026-10-19.md).
The original study, held-out data, model fits, thresholds and artifact manifests are
unchanged. This follow-up adds diagnostic measurements and one instrumented witness;
it does not change the controller or establish a new predeclared primary result.

## What “offline” means

The algorithm runs causally on chronological observations. The replay ingests one
100-ms sensor batch at a time, advances bounded history and checks candidate metrics
and policies at due endpoints. Spatial/temporal choices and publication/suppression
occur during that execution. The live AGBS path invokes the same aggregation controllers.

Counts, distinct road users, sampled mean occupancy, geometry, window duration, age
and observation coverage are available during candidate evaluation. Offline occupancy
MAE explicitly needs a separate reference. After a complete replay, the evaluator
reconstructs occupancy from its releases and compares it with source ground truth.
The attack then evaluates full released history; its model and threshold come from
independent training/calibration groups. Attack AUC is not an online per-cell metric.

The replay reads and validates the input file up front, but the production controller
receives observations chronologically; the preflight does not pass future observations
to it. History queries beyond the watermark are rejected. The endpoint sample is
excluded from a half-open candidate interval. The final horizon explicitly closes
remaining windows. A real infinite stream need not behave like that finalization.

The in-memory sink acknowledges immediately. Simulation time and sealing age therefore
do not measure wall-clock processing, queueing, MongoDB/network delivery or recipient
receipt. Offline replay is appropriate for fair identical-input comparisons and a
full-history attacker; recipient-prefix attacks and deployment timing need additional
contracts. Scientific assessment need not execute inside every simulation step.

Code references:

- `simulator/tools/AggregationReplay.cpp:385`: chronological ingestion/advance and finalization.
- `simulator/src/AggregationManager.cpp:83`: append history, then advance decisions.
- `simulator/src/AggregationHistory.cpp:145`: watermark-bounded history queries.
- `simulator/src/CandidateMetrics.cpp:130`: online values; reference-only MAE unavailable.
- `simulator/src/AdaptiveGridBasedSensor.cpp:106`: live integration.
- `tools/evaluation/run_privacy_robustness.py:167`: post-replay utility/public features.

## What the comparison does and does not establish

Common and local are two coordination models for the same adaptive aggregation
foundation, evaluated with identical input and numeric policies. Common resolves one
shared interval/cut; local permits independently progressing spatial owners and
coordinates parent takeovers. Temporal First preserves time detail by trying spatial
aggregation first; Spatial First preserves spatial detail by extending time first.

The completed study does not establish a general *membership-privacy* improvement
from switching common to local: 15/16 paired intervals contain zero; one exploratory
pointwise contrast indicates higher attack success. That is not a statement that local
coordination has no useful effect. Its expected advantages include faster availability
and adaptation to different local deadlines, neither of which is captured by eventual
occupancy availability alone.

The operational distinct-road-user minimum is three in this controlled fixture. Both
models enforce it, but neither explicitly minimizes membership-attack AUC. Adaptive
geometry, timing and exact counts remain observable. Privacy outcomes depend on the
attack family, auxiliary profile and source population. The subgroup with the largest
retention loss need not explain the largest AUC difference; no causal AUC decomposition
has been performed.

## Where retention is lost

The heterogeneous movement stratum accounts for approximately 76–93% of the net loss
across the two cohorts and two preservation priorities. This is a measured attribution
of released source contributions, not proof of one common causal failure.

| Cohort | Priority | Mixed-mode common retention | Mixed-mode local retention | Share of overall net loss |
|---|---|---:|---:|---:|
| Base | Temporal First | 93.85% | 78.29% | 75.8% |
| Base | Spatial First | 94.03% | 78.24% | 84.0% |
| Shift | Temporal First | 98.27% | 86.87% | 92.6% |
| Shift | Spatial First | 98.41% | 86.58% | 80.8% |

Base Temporal First retention by actual source type is 97.30% → 66.83% for bicycle,
71.90% → 50.28% for car and 98.02% → 94.94% for pedestrian contributions. These are
observation-weighted statistics; they are not the fraction of distinct people protected.
Moving across cell boundaries is a relevant diagnostic condition, not by itself a
complete explanation. The generator contains controlled analytical movement classes,
not realistic city/visit semantics.

## A real Temporal First freshness benefit

Compare exactly the source observation contributions released by both mechanisms.
For each observation o, its exact logical age is sealing time minus observation time.
Different retained sets therefore cannot make suppression appear to improve freshness.

| Cohort | Priority | Shared-point mean age, common → local | Shared-point p95, common → local |
|---|---|---:|---:|
| Base | Temporal First | 324.33 → 207.57 ms | 800 → 400 ms |
| Shift | Temporal First | 302.41 → 213.98 ms | 800 → 400 ms |
| Base | Spatial First | 545.72 → 543.73 ms | 1000 → 1000 ms |
| Shift | Spatial First | 545.30 → 542.58 ms | 1000 → 1000 ms |

Local TF improves mean age by about 117/88 ms on the two matched cohorts. Local SF
changes it only 2–3 ms. These are descriptive logical-time findings on the frozen
population, not measured delivery latency or population confidence bounds.

## Deadline-aware utility changes the assessment

A fixed query Q covers a 10-m square and one second. At query end plus lag ell, count
it as answered only if the recipient already has complete public spatial/time support.
For this diagnosis assume availability equals logical sealing time. With immutable
nonoverlapping releases, earliest complete availability is the latest sealing time
among the releases required by that query. Late releases cannot supply an earlier
answer. A missing spatial/time portion remains unknown.

| Base Temporal First | Common | Local |
|---|---:|---:|
| Answered at query end | 8.06% | 10.80% |
| Answered within another 100 ms | 9.52% | 11.34% |
| Within another 200 ms | 15.24% | 15.41% |
| Within another 500 ms | 17.49% | 15.52% |
| Eventually / within another 1000 ms | 18.99% | 15.62% |

Under the population-count shift, TF coverage at query end is 6.75% common versus
11.00% local; eventual coverage is 18.94% versus 16.39%. Local SF remains lower on
this task across the diagnosed lags. Thus timeliness and eventual availability can
rank the same outputs differently. This does not establish error-constrained traffic
utility: the current task is averaged occupancy, not instantaneous traffic control.
All five diagnostic lags are reported; no preferred lag is selected as a new primary
result. Future workload/deadline choices should follow an application's needs and be
fixed before its new evaluation.

## Confirmed reservation-induced missed merge

Under Temporal First in base `test-00015/present`, at 2100 ms:

- Parent 13, x=40–80 m and y=0–40 m, over `[1800,2100)` has six observations from
  three distinct road users. Coverage and every production metric/policy check pass.
- Its side is 40 m and duration/age 300 ms, within all configured bounds.
- All current descendants have a compatible common start of 1800 ms. The production
  merge-compatibility check returns true.
- No earlier public release exists anywhere in parent 13.
- Nevertheless, a future handoff for contained cell 3488 (2.5 m side, x=40,y=30),
  reserved during the 1800-ms endpoint with boundary 2200 ms, rejects the broader parent.

At 2200 ms the parent still passes, now with nine observations from three users, but
is again blocked by that reservation. Later private empty/suppressed retirements
separate the owner clocks. Leaf 13440 (1.25 m side, x=40,y=10) eventually suppresses
seven observations over `[1800,2800)`. Those seven observations are released by common
coordination inside parent 13 over `[2000,3000)`, sealed at 3000 ms.

This is a conflict with a private future coordination plan, not an unavoidable conflict
with information already disclosed. The prior parent interval `[800,1800)` contains
only one distinct user and legitimately fails; it must not be counted as an avoidable
policy-passing output. Likewise, taking the earlier passing parent changes later
owner starts: this witness does not prove how many of the later losses a correction
would recover, or that it explains every heterogeneous failure.

An instrumented `/private/tmp` copy of the controller reproduced the exact original
scientific result excluding runtime, while recording the production evaluator and
compatibility outcomes. The original source and frozen study were not changed.
Relevant rejection paths are `CellLocalAggregation.cpp:531` and `:259`; clock/domain
compatibility is at `:195`.

A proposed correction is atomic supersession of fully contained *future handoff plans*
when a broader current merge passes every constraint and owns a complete common-start
interval. It must distinguish these plans from immutable pending recipient releases,
handle rejection/ACK failure without partial state changes and preserve conservation,
bounds and publication nonoverlap. Both rejection paths need consistent handling.

## Next implementation and experiment plan

1. Add the exact reservation witness as a regression, including nested contained plans,
   unrelated plans, failed larger candidates, deadlines and immutable-output retries.
2. Implement and independently audit atomic contained-handoff replacement. Preserve
   existing references and compare before/after retention, timing, error and privacy.
   A legal extra release may improve utility while increasing membership exposure.
3. Integrate exact source-age and deadline-aware occupancy as explicitly defined
   evaluation outputs. Include EOF/interior sensitivity and transport/processing scope.
4. Predeclare a factorial experiment with identical inputs and policies across
   mechanisms: uniform versus spatially heterogeneous deadlines; controlled arrival/
   turnover/mode density; both preservation priorities; numeric bound sweeps. Existing
   functional Regions can provide the policy variation without first importing a city.
5. Give changed algorithms/attack choices new independent assessment data. Retain this
   completed population as diagnostic/reference evidence. Add public-feature ablations
   and noise-aware attacks under separate protocols to explain privacy differences.

A useful research question is: under which regional constraints and workload conditions
can local adaptation improve timely, accurate availability while meeting mandatory
policies, and what retention and empirical membership costs does that incur?

## Inspecting and reproducing this diagnosis

From the repository root:

```sh
open results/evaluation/2026-10-19/privacy-local-diagnosis-20261021/index.html
```

The local English report contains two scientific PNG/SVG figures, scenario/age tables,
the actual missed-merge timeline and links to private evidence. The directory is ignored
by Git. It also preserves analysis/render helpers, source/transcript hashes and the
instrumented trace. It has no external scripts, network dependencies or raw-data upload.

Verification:

- Source-based diagnosis: 7379974 assertions; 256 input files and 1024 adaptive public
  transcripts match their recorded hashes; all retained totals match saved results.
- Deadline diagnosis: all 1792 held-out stream/world results reproduce saved eventual
  query coverage and conditional MAE; hand cases check geometry, gaps and deadlines.
- Independent deadline spot check: 160 actual filtered-prefix evaluator calls across
  two heterogeneous present-world witnesses, four modes, four endpoints and five lags;
  10240 mask bits and 3152 answered errors match exactly. This is a targeted spot check.
- Actual figures were visually inspected. No controller implementation, attack training,
  existing scientific bundle or main simulator configuration was modified.


## Follow-up: separating holds, empty retirement and future plans

The [later controlled investigation](LOCAL_WINDOW_HOLD_PRIVACY_ANALYSIS_2026-10-19.md)
adds 2048 independently audited ablation runs and a nominal-type invariance control.
It distinguishes immediate passing-cell publication from early private-empty retirement,
quantifies the current future-handoff subsystem's net retention effect, and retains the
need for a targeted A03/A05 repair followed by fresh privacy assessment. No production
controller change or new privacy improvement is established by that diagnosis.
