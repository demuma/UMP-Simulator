# Held-out track-window privacy and utility results

The adaptive mechanism completes the declared study with better retention and
shorter logical delay than the policy-aware regional 20-m baseline. **An additional
privacy benefit over that baseline is not demonstrated by the declared attack.**
The result is a measured tradeoff, not universal superiority or equivalence.

All 72 original recordings remain in their original roles: 24 TRAIN, 16 CAL and
32 TEST. Every source is a 300-second recording. Each has one matched target
IN/OUT pair; the independent TEST sample size is 32 recording groups, not 64
independent people. The protected secret is whether **all observed contributions
of one operational track in [0,300 s)** were included. Movement completion is
reported separately. This does not protect a person's identity, physical presence,
all visits or a complete journey by definition.

## Prespecified privacy comparison

| Full111 attack | Regional static 20 m | Adaptive Semantic First |
|---|---:|---:|
| TEST ROC-AUC | 0.564941 | 0.577637 |
| TPR at the locked CAL threshold | 40.625% | 40.625% |
| FPR at the locked CAL threshold | 37.500% | 31.250% |

The primary contrast is AUC(adaptive) − AUC(regional static20): **+0.012695**, with
paired 95% bootstrap interval **[−0.043970, +0.072266]**, N=32. The interval crosses
zero. This study does not resolve the direction of the difference and establishes
neither a privacy improvement nor equivalence. The interval uses 1000 whole-
recording paired resamples and is conditional on the frozen TRAIN models/CAL
thresholds. It does not include training or calibration uncertainty. No individual-
method AUC interval was predeclared.

The Scalar31 joint representation ablation also remains inconclusive:
+0.010742, interval [−0.061523, +0.091797]. It removes semantic and availability
coordinates together and cannot isolate semantic leakage.

All three negative controls have AUC 0.5; the unprotected exact approved-sighting
control has AUC 1.0. Under this specific source distribution, auxiliary knowledge,
recipient stream and attack, aggregation reduces the attack's observed ranking
performance relative to that unprotected control. This does not bound other
attacks or establish formal privacy. No fitted attack or score direction was
changed after observing TEST.

**Operating-point limitation:** the empirical CAL FPR cap of 10% does not carry
over to TEST. Adaptive TEST FPR is 10/32 = 31.25%, exact 95% interval
[16.12%, 50.01%]; regional20 is 12/32 = 37.5%, interval [21.10%, 56.31%].
This is an important calibration/generalization limitation, not a hard-policy
violation. CAL contains only 16 negative recording worlds, giving 1/16 empirical
FPR resolution. The current thresholds remain locked; the result is not repaired
by adjusting them on TEST. Precision uses an evaluation prior of 0.5 and is not
deployment positive predictive value.

## Utility tradeoffs

These are equal-recording TEST macro means for the IN world. The listed retention,
J, retained semantic loss, cell side, delay and estimated-query metrics each use
all 32 recordings. OUT-world results and every metric's own denominator are in
[the full table](report.md) and [aggregate JSON](summary.json).

| Metric | Regional static 20 m | Adaptive Semantic First |
|---|---:|---:|
| Retained observation contributions | 60.603% | 68.526% |
| Full-input J, lower is better | 77.248% | 73.802% |
| Semantic loss among retained contributions | 62.538% | 61.796% |
| Mean retained cell side | 20.000 m | 17.935 m |
| Mean logical seal delay | 1839.255 ms | 347.665 ms |
| Estimated query coverage | 13.910% | 12.508% |
| Estimated occupancy MAE on answered queries | 1.351 | 1.260 |

The adaptive point estimates retain **7.923 percentage points** more input, reduce
J by **3.446 points**, and reduce mean logical delay by approximately **81.1%**.
These utility differences are descriptive paired-study outcomes; no confidence
interval for their differences was predeclared. They do not establish superiority
for every application or population.

J = (number of omitted observations + summed retained taxonomy loss) / number of
input observations. It combines omission and declared semantic loss; it does
not include spatial or temporal loss. Retained detail and delay are conditional
on contributions that survive. Semantic loss remains substantial at 61.8%; a
high retention rate does not retain all class distinctions.

The fixed query workload has 19,200 10-m/1-s occupancy queries per world and
recording. The lower adaptive estimated MAE applies to a smaller answered subset
and is not proof of better query answering. Exact coverage is only 0.00309% for
adaptive, versus 0% for regional20. Fixed10m/1s answers 2.275% exactly, while
retaining fewer contributions (28.936%). Exact adaptive MAE=0 is defined in only
14/32 IN recordings and 13/32 OUT recordings, rather than all32. Unknown queries
are never converted to zero. This workload exposes an application-utility
limitation despite the retention and delay gains.

## Policy and execution evidence

All eleven methods use the same local400 regional hard requirements and native
aggregation implementation. Selective semantic contribution suppression is OFF;
whole candidates that cannot satisfy the policy can still be withheld. Policy
compliance is distinct from measured inference risk and availability.

- All 32 TEST families complete: 576 audited native executions, 128 audited
  regional-static compositions and 704 new method/world rows.
- Together with unchanged TRAIN/CAL artifacts: 72 groups, 1296 native executions,
  288 regional compositions and 1584 method/world rows.
- Audited native published-cell policy violations are zero. Empty or withheld
  regions do not become useful observations merely by being compliant.
- All 22 originally locked method/representation variants remain converged;
  original model/scaler/threshold bytes are preserved. No refits or retunes.
- The final reporting command repeats full raw validation and archive verification
  before assessment and exits zero. The scientific gates are complete.

Recipient availability is one retrospective snapshot at H=300 s. Logical seal
delay is intentional aggregation time, not measured delivery latency. Adaptive
IN whole-recording core processing averages 32.846 s for a 300-s recording
(about 9.13 times aggregate throughput); OUT averages 32.714 s. These are offline
batch-throughput observations, with no per-step deadline or live/RT guarantee.
Derived regional-composition online runtime is unavailable.

## Movement quality and diagnostic repair lineage

All 72 sources pass the hard clock, GT/sensor, provenance and physical/data
requirements. One TRAIN source and one TEST source have active tracks and
reported stalls at the horizon; no source has pending tracks. These counts are
recordings with a condition, not affected-track counts. Quality does not filter
enrollment, and stalled movement is not a privacy benefit. The synthetic source
still needs broader realism and navigation-liveness evaluation.

The original 32 TEST source-qualification attempts failed in a surface-access
building-count diagnostic. Their failures and raw inputs were preserved. The
one-field reporting correction then produced 32 successful corrected physical
audits, 40 authenticated legacy-proof reuses and 72 new full raw-validation
receipts, before any TEST recipient mechanisms. Source generation, policy,
models, CAL thresholds and statistical rules were unchanged. Repair code and
readiness were pushed in commit `7326d40` before TEST mechanisms; the original
model lock had been pushed earlier, before all TEST captures.

**The numerical results and both figures must travel with
[repair-lineage-public.json](repair-lineage-public.json), the numerical artifact
receipt and the outer packet receipt.** Standalone numeric export omits this
repair lineage. Raw movements, models, feature rows and individual scores remain
local and are excluded from Git.

## Next scientific work

1. Diagnose calibration stability on development data and predeclare larger or
   repeated calibration studies; keep this TEST cohort and its current results
   unchanged. A small observed AUC is not an FPR guarantee.
2. Choose a concrete traffic-query objective, including answered coverage,
   freshness and error, before changing aggregation selection. Retention and J
   alone miss the sparse exact-query coverage exposed here.
3. Then test new sources/sites and complementary attacks with newly declared
   held-out groups. Sensitive-visit or person-level claims require a new secret,
   observation model and evidence.
