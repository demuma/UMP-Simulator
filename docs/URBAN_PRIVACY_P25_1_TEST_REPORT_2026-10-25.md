# P25.1: urban membership contract and source-neighbor verification

Date: 2026-10-25. Status: **complete for the first development fixture**.
This checkpoint fixes the [urban contribution-membership contract](URBAN_PRIVACY_MEMBERSHIP_CONTRACT_2026-10-25.md)
and implements/tests one matched source pair. It does not run aggregation,
train an attacker or establish a privacy benefit. The next gate is P25.2.

## Source and protected unit

Use the existing completed mapped synthetic mixed recording: 300 s, an 80 × 80 m
D6 domain, a 20-Hz recorded GT clock and 10-Hz sensor observations. The recording
has 128 modeled people and 171 completed visible track episodes; every scheduled
episode is sensor-observed. All input bytes and capture/geometry/lifecycle
provenance are authenticated against the corrected study and original capture.

The protected unit is the full sampled contribution of one original visible
track episode, selected from complete episodes with at least two observations.
The fixed seed/hash rule selects from all 171 eligible episodes independently of
mechanism outcomes. The secret is source inclusion. It does not establish person
anonymity, physical absence or protection of all visits/episodes of one person.
Each contribution is a timestamped observation occurrence: equal positions at
different measurement times are separate contributions.

The complete observation source is frozen. OUT removes the target observations;
its motion, every background trajectory, sensor clock, source metadata and
measurement opportunity remain unchanged. A different-world simulator rerun
would change interactions and is not the defined neighbor relation.

## Actual fixture result

| Check | Verified result |
| --- | --- |
| IN source observations | 82,033 |
| OUT source observations | 81,676 |
| Exactly removed target observations | 357 |
| Complete eligible visible episodes | 171 |
| Measurement batches in both worlds | 2999, at 100 through 299900 ms |
| Originally empty measured batches | 1209, preserved as measured |
| Empty batches after this removal | 1209 |
| Auxiliary points in each world | 90 = ceil(357 / 4) |
| Auxiliary world equality | Byte-identical |
| Original IN | Byte-identical to frozen source |
| Background / batch / header equality | Reconstructed and verified, including canonical numeric types and ordering |
| Local artifact protection | Directory 0700, files 0600, ignored by Git |

The auxiliary record contains only exact time/coordinates and the geometrically
derivable leaf ID. It contains no target ID, type, private person mapping or
membership label. Sampling is an exact rounded quarter over the complete episode,
not causal Bernoulli acquisition; this gate makes no prefix-privacy claim.

Before fixture generation, preflight reconstructs 50-ms GT coverage and per-track
start/end intervals from the authenticated private capture. It checks stable
person/type associations, nonoverlapping episodes, exact completed lifecycle and
scheduled-person counts, then independently projects GT onto the complete 100-ms
sensor observations. A horizon-complete flag alone is insufficient.

The builder writes and fsyncs its protocol before target filtering/artifact
creation. After construction, its verifier reopens original evidence and checks
the full source again. A separate fresh-process CLI verification succeeds.
A standalone reference check importing no fixture code also reconstructs the
seeded target, every OUT batch and the exact auxiliary subset from original IN.

## Automated tests and independent review

All **14 new unit test methods pass**, including authenticated miniature-source
construction and verification, deterministic selection, full measured-empty
preservation and rejection of modified background, target, auxiliary, batch,
geometry, lifecycle/GT, hashes, protocol/manifest types and existing outputs.
Tamper tests repair dependent receipts where appropriate, ensuring that checks
reject incorrect content rather than only stale hashes. Private ID/type additions
to auxiliary records are rejected. Symlinks, path escape, nonregular/oversized
inputs, world-readable fixture artifacts and overwrite attempts fail closed.

The affected CTest run passes **6/6 groups** in 1.96 s:

- `urban_privacy_fixture_evaluation`
- `privacy_dataset_evaluation`
- `privacy_evaluation`
- `empirical_privacy_evaluation`
- `causal_privacy_evaluation`
- `replay_data_evaluation`

There are now 105 registered groups. The previous checkpoint's full 104-group
suite remains its historical baseline; this checkpoint does not claim a fresh
105-group full run. No simulator/aggregation C++ source or existing attack schema
was changed. Focused tests cover the new standalone tool and related legacy
contracts. Source/hash/contract review preceded real fixture construction.

Review corrected an execution-summary mismatch before freeze: the canonical
policy uses Semantic First with Temporal First secondary. It also hardened raw
event clocks, scheduled-person consistency and canonical metadata/auxiliary
comparisons. The frozen policy/source were not modified to pass verification.

## Kept local and next gate

The private fixture is at
`results/urban-membership-dev-2026-10-25-v1` (approximately 28 MiB). It contains
IN/OUT observations, full target trace, auxiliary files, private group/label
manifest, frozen protocol and verification receipt. Every derivative of this
already inspected source is development-only; it supplies no independent
training/calibration/test source for P25.3.

The [compact Git receipt](verification/urban-membership-p25-1-2026-10-25.json)
exports aggregate counts and code/contract/test provenance. It excludes identities,
target type/interval, trajectory/auxiliary points, per-type world differences,
private group metadata and raw movement. Audit receipts and source hashes are
not recipient features.

P25.2 must implement the full semantic recipient channel and its public-only
attack features, and materialize a validated regional-static recipient stream.
The current scalar exporter still rejects semantic fields. The private snapshot
policy reference and this source fixture do not certify incremental recipient
availability, live access controls or wall-clock delivery performance.

## Reproduction

Use the locally retained authenticated capture and corrected study. New construction
requires a fresh ignored output directory; completed/failed outputs are never
reused. The original source and contract remain fixed by the protocol hashes.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/evaluation/urban_privacy_fixture.py \
  --source-study results/spatial20-controller-correction-2026-10-24-v2 \
  --capture results/expanded-access-mixed-2026-10-24-v1/replay \
  --contract docs/URBAN_PRIVACY_MEMBERSHIP_CONTRACT_2026-10-25.md \
  --output results/urban-membership-dev-2026-10-25-repeat

PYTHONDONTWRITEBYTECODE=1 python3 -B tools/evaluation/urban_privacy_fixture.py \
  --verify results/urban-membership-dev-2026-10-25-v1

ctest --test-dir simulator/build \
  -R '^(urban_privacy_fixture_evaluation|privacy_dataset_evaluation|privacy_evaluation|empirical_privacy_evaluation|causal_privacy_evaluation|replay_data_evaluation)$' \
  --output-on-failure -j 2
```
