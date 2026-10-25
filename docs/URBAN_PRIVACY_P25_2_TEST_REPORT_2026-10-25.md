# P25.2: semantic recipient and regional-static channel test report

Date: 2026-10-25. Status: **complete**. Adapters, bounded DEV pilot and all 108 regression
groups are verified. The
[channel addendum](URBAN_SEMANTIC_RECIPIENT_CHANNEL_2026-10-25.md) defines exact
visibility/availability assumptions and feature semantics.

## Implementation

| File | Responsibility |
| --- | --- |
| `semantic_privacy.py` | Strict semantic transcript v2, taxonomy/count/support/loss validation, complete canonical channel, public-only features and availability-gated views. |
| `regional_public_transcript.py` | Audited policy-only fixed-grid schedule composition into actual grouped public release records; no fabricated native result/runtime. |
| `run_urban_privacy_channel_pilot.py` | Frozen, bounded ten-case DEV orchestration, independent raw audits, context/identity checks, public export/features and final artifact verification. |

Each module has a dedicated test file and CTest group. The historical scalar v1
modules remain byte-for-byte unchanged; they still reject semantic extensions.
No C++ aggregation, sensing, map, trajectory or policy requirements were changed.
P25.1 source/contract files remain frozen and independently verifiable.

## Real-source pilot

The one P25.1 development pair is replayed with an unchanged corrected executable
and the same Spatial20 policy in both worlds. IN has 82,033 input observations;
OUT has 81,676 after exactly one episode's 357 contributions are removed.
Each uses the same 90 permitted auxiliary sightings. No traffic is resimulated.
The policy is suppression OFF, Semantic First with Temporal First secondary;
fixed modes explicitly override selection using native CLI parameters.

Ten native executions pass independent full-input, geometry, coverage, retirement,
identity support, semantic category and regional-policy audits. The declared
one-million-cell audit bound is not silently truncated. Every input contribution
is accounted for and no published hard-policy violation is found.

| Native method | IN published cells | OUT published cells |
| --- | ---: | ---: |
| Adaptive Semantic First | 1514 | 1490 |
| Fixed20 / 0.4 s | 1142 | 1120 |
| Fixed20 / 1 s | 467 | 458 |
| Fixed20 / 2 s | 208 | 202 |
| Fixed20 / 4 s | 119 | 115 |

These are format/accounting checks on one DEV neighbor pair, not an attack score
or an estimate of a protection improvement. The target was not reselected based
on these outcomes. Execution elapsed times are operational receipts, not isolated
performance benchmarks.

The fixed families also yield two validated regional-static20 public streams.
The schedule is selected only from the same public policy/footprints and is
identical in IN and OUT. Exact selected native payloads/times and compiled policy
identities are preserved. Every unused fixed component is independently verified
too; the audit includes the full nonempty source partition and empty intervals.
Native runtime for the derived streams is null.

All **12 recipient streams** pass strict v2 validation. Each yields the same
**111-coordinate** feature schema, frozen before native execution. A fresh public-
only process revalidates every stream and reproduces its saved feature vector
from only the approved transcript and auxiliary points, without GT or target IDs.
Public fixed headers/context match across both worlds and all methods.

The default final-snapshot evaluation assumes availability at the full 300-s
horizon. The view at H-1 has no releases and the H view exactly equals the full
transcript. Original seal metadata remains visible in the final view. This is an
explicit retrospective evaluation convention, not measured delivery at H or a
causal-prefix privacy result. No-output controls retain the same feature space
and an all-zero output-feature vector.

An additional **actual mapped uniform-control** composition verifies the wrapper
against the earlier 44-case study: its 28 release events / 140 cell-windows exactly
match native global4s after approved alias normalization and event grouping.
This checks full recipient-stream equality, not just utility totals.

## Tests and review

The three new suites contain **34 test methods**:

- 13 semantic-channel tests: complete nested allowlists, private-field invariance,
  true semantic-only channel changes at identical scalar counts, taxonomy cycles/
  antichains/count/support/loss errors, geometry overlap, long native aliases,
  ancestor coordination scopes, missing-subtype/null masks, no-output dimensions,
  explicit availability models and future-view invariance.
- 10 regional-composer tests: exact grouped4s control, raw partition/support and
  native payload preservation, policy-only schedule invariance, empty source,
  all four receipt/audit components, coherently forged data/metric/policy-ID
  rejection, post-horizon seals, private output permissions and fresh paths.
- 11 pilot tests: exact predeclared ten-case matrix, fixed schedule/clock/native
  header and accounting, public-context allowlist, exact compiled policy IDs/model,
  feature/availability/no-output controls, frozen-artifact mutation, invalid budgets
  and timeout preservation without retry.

Eight affected CTest groups passed before the real pilot. A final pilot-guard
rerun also passed after method/header hardening. The initial three test errors
were caused by macOS `/var` symlink temporary paths; tests now use canonical
`/private/tmp` while the production symlink rejection remains intact. This was
corrected before actual execution, without weakening the guard.

Independent read-only review caught legitimate long native aliases and ancestor
scopes, copy-time receipt anchoring, exact effective-policy validation, transitive
audit-helper freezing and completed-output mutation risks. These were corrected
and tested before the pilot protocol was frozen. All ten real native cases and
both regional compositions completed on the first declared run.

The complete **108/108-group CTest regression passes** in **303.57 s**, with
zero failed or skipped groups. It includes all three new suites and historical
scalar/causal privacy, coordinator, sensor, publication, map, navigation and
native source-drainage regressions. Per-group durations and source hashes are in
the compact receipt. Native pilot/composition jobs finished before this full run;
evaluation/tool sources remained frozen throughout.

## Artifacts and limits

The private pilot is at `results/urban-privacy-channel-pilot-2026-10-25-v1`;
the real uniform control is at
`results/urban-semantic-regional-control-2026-10-25-v1`.
They retain source copies, native results/audits, recipient streams, auxiliary
sightings, feature values and private provenance, excluded from Git.
The [compact aggregate receipt](verification/urban-privacy-p25-2-2026-10-25.json)
contains schemas, hashes, dimensions and verification results only.

All these derivatives belong to **one already inspected DEV source group**.
There is no model fitting, TRAIN/CAL/TEST assessment, AUC, TPR/FPR estimate,
privacy-benefit claim or new independent recording. These remain P25.3/4.
A valid public histogram alone cannot prove its raw identity support; the
separate source auditor supplies that check. Feature maps are bounded attack
representations, not all information available to an unrestricted recipient.
File-format allowlists do not certify database/network access controls.

## Reproduction

Use the existing local frozen inputs and a fresh ignored results path. The runner
rejects overwrites and preserves failed-case evidence rather than retrying or
changing thresholds. No optional attack/ML dependency is required for this gate.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/evaluation/run_urban_privacy_channel_pilot.py \
  --fixture results/urban-membership-dev-2026-10-25-v1 \
  --output results/urban-privacy-channel-pilot-2026-10-25-repeat \
  --binary simulator/build/AggregationReplay

PYTHONDONTWRITEBYTECODE=1 python3 -B tools/evaluation/regional_public_transcript.py \
  --study results/temporal-region-study-2026-10-25-v1 \
  --source mixed --policy control --side 20 \
  --output results/urban-semantic-regional-control-2026-10-25-repeat

ctest --test-dir simulator/build --output-on-failure -j 2
```
