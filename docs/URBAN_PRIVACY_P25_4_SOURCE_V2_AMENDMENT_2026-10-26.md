# P25.4 pre-TEST amendment: corrected source version v2

Status: historical amendment frozen before TEST. The v2 main attempt is now
closed incomplete: 71/72 sources are valid, with a new doorway-navigation failure
in TEST. All 40 TRAIN/CAL method families and the pre-TEST model lock passed;
the source gate prevented every TEST mechanism run. Read the
[final outcome](URBAN_PRIVACY_P25_4_EXECUTION_OUTCOME_2026-10-26.md).
The following sections preserve the prospective change and validation requirements;
they are not a claim that the later main source gate passed. The existing
[P25.3 design](verification/urban-privacy-p25-3-2026-10-25/primary-design.json)
remains the reference for unchanged scientific choices.

## Reason and exposure

V1's complete TRAIN/CAL source-attempt batch produced 37 verified and three invalid
captures. The invalid captures complete the observation clock but leave scheduled
movement unfinished because opposing rider queues occupy independently closing
crossings. The waiting primary mechanism/model driver was stopped. No primary
mechanism, fitted model, CAL attack score or TEST realization was inspected.
The [complete v1 source-only report](verification/urban-privacy-p25-4-2026-10-25/v1-source-gate/report.md)
retains all 72 planned slots, including the 32 unattempted TEST slots.

This is an explicit correction to the data-generating implementation before TEST,
not a successful execution of the original source version. The previous version
and its negative outcomes remain immutable and independently identifiable.

## Permitted source change

The actual source motion now uses a finite per-closure cohort to drain coupled
crossing queues. Existing pedestrian ownership, physical separation, swept-body,
static geometry, speed and displacement checks remain in force. New arrivals
cannot extend a cohort. The [source correction report](URBAN_PRIVACY_SOURCE_CROSSING_DRAIN_FIX_2026-10-26.md)
describes the mechanism, isolated negative/positive controls and limitations.
This correction does not prove general liveness or a hard pedestrian wait bound.

Only `MappedScene.cpp`, `MappedScene.hpp` and the Simulator source executable change
within the prior source binding. The existing mapped-scene test target gains two
black-box regressions; CMake is unchanged. The aggregation executable stays
byte-identical:
`72fc0aff452ee036d7dfdd8bd8ca7bd343c7462923ec00ccb39f904ee655502f`.

The configured map/access geometry, demand/route-generation law, 128-person cohort,
300-second horizon, 50-ms GT, 100-ms sensor, source flags and resource caps remain
unchanged. Realized motion can change under the new controller, so v2 is a new
source implementation version. Results must be labeled as evidence under v2's
synthetic generator; neither version is calibrated real-world traffic evidence.

## Unchanged scientific choices

Retain the original study ID/master seed, all 72 group IDs and split assignments,
all 216 role-separated source/target/auxiliary seeds, target slots, 24 TRAIN /
16 CAL /32 TEST counts and all 17 original DEV/historical exclusions. Original
TRAIN/CAL motion exposure stays in those roles and is explicitly recorded. It is
not relabeled as excluded DEV and not moved across splits.

Policy, taxonomy, comparison family, suppression OFF, protected episode unit,
IN/OUT filtering, quarter-sighting knowledge, 111/31 representations, fitting
budget, CAL operating-point rule, controls, risk metrics, paired bootstrap,
exact rate intervals, occupancy workload, world-specific truth, availability and
utility definitions remain unchanged. Candidate construction checks exact equality
of these fields and reconstructs identical group/split/seed assignments.

V2 regenerates every TRAIN/CAL recording using the corrected binary. It does not
retain old successes while replacing failed seeds. Every v2 slot receives one
attempt; all failures remain visible. V1 and v2 are never pooled as independent
recordings, and no TEST-driven source, policy, model or threshold tuning is allowed.
The original 32 TEST realizations remain unseen until the new supplement and actual
complete TRAIN/CAL model lock pass.

## Validation and freeze requirements

Before source application, the original source batch and all accepted capture
artifacts were reauthenticated under the old implementation. Its final source
summary SHA-256 is
`4e9bd5647e58eaf88a03e3b20310f7f161637fe543214bf9fe245cec24900cf3`.
Original C++/header/test/executable bytes and all ten v1 implementation/test files
are retained locally with hashes. The last original sources remain historical
receipts; current-code verification deliberately rejects a changed implementation.

The production Simulator, mapped-scene tests/configuration and maintained motion
probe build successfully. Eleven affected CTest groups pass in 176.97 s. The
updated affected Python suite passes 177 methods; the existing-source 22-stream
DEV recipient integration is reauthenticated. Model preparation now receives the
current authenticated manifest's groups/methods explicitly, so the new execution
does not rely on a legacy default manifest path. This changes orchestration
binding, not the feature/fitting/statistical protocol.

The remaining source validation is a prospectively listed, serial 48-case motion
preflight: eight original DEV plus all 40 original TRAIN/CAL configurations,
8,119 scheduled episodes, including all three invalid cases. Each has one finite
attempt with independent body/swept/speed/displacement checks and cohort-membership
checks. This uses no TEST source and creates no replacement primary recording.
All outcomes must be retained, including any negative diagnostic prototype.

Only after that gate passes may a new binding and manifest be frozen. The binding
must include the corrected source/binary hashes, native and motion validation,
original final source summary/negative gate, and original split-preserving exposure
receipt. The old DEV pilot remains historical evidence/exclusion; it must not be
represented as newly captured under the correction. The new source protocol
replaces the previous generator binding reference, while preserving its fixed
configuration/environment/map checks.

Prepare fresh v2 source/execution directories and an implementation supplement
binding current code plus unit/DEV receipts. Execute all 40 TRAIN/CAL sources and
all compared mechanisms, then lock actual paired models and CAL thresholds.
Generate the original TEST slots only after that gate. Final reporting must
reauthenticate source/IN/OUT/archive provenance and present all methods, controls,
uncertainty and utility, preserving v1's separate failed-source evidence.

## Local retained evidence

The original and corrected source artifacts, complete DEV package, native logs,
preflight protocol and forthcoming receipts are under ignored
`results/urban-privacy-source-correction-2026-10-26-v2`. The immutable v1 source
closure is under `results/urban-privacy-primary-study-2026-10-25-v1`.
Only compact aggregate/source-design evidence and scientific figures enter Git.
Raw movement, target labels, feature rows, fitted weights and individual scores
remain local.

## Completed freeze

Manifest SHA-256:
`e3b4296674c95d407baf6bc2d3def0564cb77eca37286fdbf9b92ff48c82d5c0`.
Implementation supplement SHA-256:
`40e58dbd20ae9a00dcdc1858cd7de405579778663177d45f50b2486a4d21648d`.
Independent review authenticated 143 source-binding hashes and 38 evidence references,
all 72 groups/216 role seeds and 17 exclusions, unchanged policy/methods/analysis and
zero primary fits/TEST at freeze. Before the freeze, all 48 known motion cases passed and were reverified:
8,119/8,119 episodes, zero failures,
zero retries. Minimum swept margin is 0 at required clearance; no violation occurs.

Compact evidence: [freeze](verification/urban-privacy-p25-4-2026-10-26-v2/amendment-freeze.json),
[design](verification/urban-privacy-p25-4-2026-10-26-v2/design.json),
[compatibility](verification/urban-privacy-p25-4-2026-10-26-v2/compatibility.json),
[48-case validation](verification/urban-privacy-p25-4-2026-10-26-v2/motion-preflight.json),
[native regressions](verification/urban-privacy-p25-4-2026-10-26-v2/native-regression.json),
[177-test receipt](verification/urban-privacy-p25-4-2026-10-26-v2/unit-validation.json).

Local new version directories are `results/urban-privacy-primary-protocol-2026-10-26-v2`,
`results/urban-privacy-primary-sources-2026-10-26-v2` and
`results/urban-privacy-primary-study-2026-10-26-v2`. The latter retains the
serial driver and phase logs. Raw v1/v2 data and fitted artifacts stay local.
P25.4 empirical acceptance remains open until all final outcomes are reviewed.

## Local storage operations after freeze

The closed v1 GT JSON files were losslessly gzip-archived locally. All 40 archives
match their original capture-proof SHA-256; 6.077 GiB becomes 0.603 GiB. A real
same-path restoration was tested on the first negative source and matches its
original capture hash. Other legacy GT files can be restored with:

```sh
python3 -B results/urban-privacy-source-correction-2026-10-26-v2/archive_legacy_gt.py \
  --restore --seed 251636138180450197
```

Omit `--seed` to restore all 40 when sufficient storage is available. Old
observations/results/proofs remain present. The original v1 data is retained,
with its immutable archive/release/restoration receipts in the ignored results
folder. Local filesystem snapshots can retain old allocated blocks, so archival
size reduction alone is not treated as guaranteed immediately free disk space.

For v2, only **completed, verified GT files** receive transparent local filesystem
compression at the same path. Before atomic replacement, both copies must match
the existing immutable capture-proof hash and logical size. Ordinary `open()`
reads the same JSON bytes; no reader or scientific code changes. Temporary copies
are outside the capture tree; active captures and invalid sources are untouched.
A real full unchanged source validation passes after conversion, recorded in the
[storage validation](verification/urban-privacy-p25-4-2026-10-26-v2/transparent-storage-validation.json).
The storage worker records every before/after logical hash, size and allocated
size, and exits after 72 files or a stopped driver. This is storage representation,
not a new source realization or protocol/model change. All final source checks
still use their original strict logical-byte digests. V2 replay paths stay usable.
