# Urban contribution-membership contract — 25 October 2026

Contract version: `ump.urban-membership-contract.v1`. This is the P25.1 threat and
visibility contract for one development fixture. It fixes the unit, neighboring
sources and observer before the fixture is constructed. The [execution plan](URBAN_PRIVACY_EVALUATION_PLAN_2026-10-25.md)
keeps semantic-aware attack adapters in P25.2 and the full experimental freeze in
P25.3. No urban attack result or privacy benefit is claimed here.

## Protected unit and neighboring sources

The protected unit is **one complete visible observation-track episode** in the
frozen 300-second recording. It is the original operational track, without
fragmentation or GT-based linking. A later episode of the same modeled physical
person remains background, with all its observations unchanged. The secret is
whether the selected episode's complete recorded contribution was included in the
aggregation input. It is not physical presence, person identity, a visit, transport
mode, or membership of all episodes belonging to a person.

Let the frozen source be the ordered batches

\[
D_{\mathrm{IN}}=((m_t,O_t))_{t\in\mathcal T},\qquad
C_e=\{o\in O_t:\operatorname{id}(o)=e,\ t\in\mathcal T\}.
\]

Here \(m_t\) includes every original batch field other than observations, including
sequence, measurement timestamp and measurement status. For the selected episode
\(e\), define

\[
D_{\mathrm{OUT}}=((m_t,\{o\in O_t:\operatorname{id}(o)\ne e\}))_{t\in\mathcal T}.
\]

IN preserves the original source bytes. OUT filters only observations bearing
that episode ID, preserving every background observation's value and order and
all source/header/batch metadata. It retains every measured batch, including an
originally empty batch or one made empty by the removal. No traffic is resimulated;
no trajectory, collision, queue, arrival, route, type, sensor cadence or timestamp
is recomputed. The physical source realization is held fixed in this controlled
contribution-membership game.

A balanced paired label \(B\in\{0,1\}\), with prior \(P(B=1)=1/2\), selects OUT or
IN. Both labels share the same candidate auxiliary knowledge and every public
constant. The evaluator knows the full background to construct and audit the
pair. The proposed learned attacker does not receive the realized background
trajectories; learning a background distribution requires independent training
sources under the later study protocol.

For a cell \(C\) and interval \(I\), operational support is

\[
n_{\mathrm{track}}(C,I)=\left|\{\operatorname{id}(o):t_o\in I,\ x_o\in C\}\right|.
\]

This track union differs from an observation contribution count, simultaneous
occupancy and the number of physical people. The historical recipient field
`distinct_road_users` denotes this operational track support in the mapped source.
A minimum of five or ten tracks is a release requirement, not a k-anonymity,
l-diversity or inference-resistance guarantee. The [mapped identity contract](MAPPED_SCENE_IDENTITY_CONTRACT_2026-10-23.md)
and [attribute contract](PRIVACY_ATTRIBUTE_AND_ONLINE_CONTRACT.md) retain their
person/track and secret distinctions.

## Frozen horizon, source and eligibility

The observation horizon is public and fixed at \(H=300000\) ms, with source support
\([0,H)\). Coverage is the existing 80 × 80 m mapped footprint, x east/y south,
quadtree leaf depth six and 100-ms measurement cadence. The selected recording
contains 2,999 measured batches at 100 through 299900 ms; zero and 300000 ms are
not fabricated measurement batches. Of those batches, 1,209 are originally empty.
The full source contains 82,033 observation contributions.

The source is the completed mixed capture reused by
`results/spatial20-controller-correction-2026-10-24-v2/mixed-observations.json`;
its observation bytes have
SHA-256 `c24134c724acf2df38a85b2906a2e80f8de7b420529a4b8cda3f9e5f98a3eff5`.
The authenticated original recording is
`results/expanded-access-mixed-2026-10-24-v1/replay/observations.json`.
The existing capture proof reports completed numerical horizon **and** all
scheduled episodes completed: 171 starts, 171 ends, zero active or pending
episodes at the horizon, event-audited GT coverage, and exact sensor-observed
versus scheduled episode-token agreement. A `source_completed` flag alone is
insufficient: its compatibility meaning is horizon completion.

An episode is eligible only after checking that completed-source proof against
the authenticated private lifecycle recording, with one properly ordered visible
start and end inside \([0,H]\), its observed points within those lifecycle bounds,
a stable observed type and private person association, and at least two observed
points. These private checks validate the unit; neither the type nor the person
association becomes attacker knowledge. First and last observation timestamps
inside the horizon alone do not prove episode completion. An incomplete or
unauthenticated lifecycle source must fail instead of silently selecting a
censored episode.

## Target and auxiliary selection fixed before output inspection

The fixture seed is **20261025**. Domain-separated namespaces `target-v1` and
`aux-v1` select the target and auxiliary points independently of each other and of
mechanism output. Canonical JSON means
`json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')`.
Hash ordering compares SHA-256 digests, with the original episode ID as a stable
tie-break for target selection.

1. For every eligible episode ID, hash canonical JSON
   `["target-v1", 20261025, source_observations_sha256, episode_id]`.
   Select the ID with the smallest hash. Do not inspect releases, suppression,
   support success, utility or attack scores to choose or reject it.
2. Construct the selected episode's exact points as objects with only
   `observed_at_ms`, `x`, `y`, and `cell_id`, using recorded time/coordinates and
   the existing public finest-grid cell. There is one observation per episode at
   a measured timestamp; duplicate or inconsistent points fail validation.
3. For each point, hash canonical JSON
   `["aux-v1", 20261025, source_observations_sha256, episode_id, point]`.
   Select the smallest \(k=\max(1,\lceil n/4\rceil)\) hashes, breaking any ties by
   canonical point bytes, and finally order selected points by timestamp.

This is an exact **quarter-count sample with upward rounding** when \(n\) is not
divisible by four. It is not independent 25% Bernoulli sampling. The sampling
rule uses the full frozen episode; it does not inherit the causal-prefix
invariance of the earlier [16-second protocol](CAUSAL_PRIVACY_PROTOCOL_2026-10-20.md).
This development fixture specifies one full-horizon view. A later prefix study
must explicitly freeze its auxiliary acquisition/sampling contract.

The permitted auxiliary record contains exact coordinate/time sightings and their
publicly derivable cell IDs only. No spatial noise, timestamp jitter or type
knowledge is claimed. It excludes track/person IDs, labels, private GT, source
hashes, selection ranks, lifecycle events, routes, destinations, unselected trajectory
points, post-horizon samples and capture provenance. Private hashes and IDs used to reproduce sampling
are not prediction features. `auxiliary-in.json` and `auxiliary-out.json` must be
byte-identical; the full auxiliary record is available at the final view \(H\).

## Complete recipient channel and clock

The observer knows the fixed domain/coordinate system, public map geometry and
labels, taxonomy hierarchy/category labels/loss values, declared mechanism,
public policy bounds and their regional-intersection semantics. This is a public
knowledge assumption, not permission to read the private simulator configuration,
source seed, realized population, visit labels or routes. Public constants must
be identical in IN and OUT; source/run/database identities and membership labels
must not leak through filenames, aliases or policy identifiers.

The protected product is the **complete approved aggregate release**, including
its semantic content and availability. The following table defines the intended
recipient channel; fields must not be silently dropped from a claimed assessment.

| Component | Permitted content |
| --- | --- |
| Public header | Versioned schema, fixed coverage/leaf grid, sampling period, declared horizon; fixed public map, taxonomy and policy metadata or their public references. |
| Release identity and policy | Canonical recipient alias; publication model; `policy_id`, `policy_version`; each cell's `effective_policy_id`; any publicly exposed coordination geometry. No private source/run/DB identity. |
| Space and time | `cell_id`, `depth`, `x`, `y`, `width`, `height`; complete `start_ms`, `end_ms`, `sealed_at_ms`; release order and observable periods without release. |
| Scalar counts | `observation_contributions`, operational `distinct_road_users`, `mean_sample_occupancy` including its unknown/null state. No original-input totals for a selectively filtered product. |
| Semantic product | `ump.semantic-release.v1`: `taxonomy_id`, `taxonomy_version`; each released category's `category_id`, `observation_contributions`, `distinct_contributors`; `min_category_distinct_contributors`, `semantic_mean_loss`, `semantic_max_loss`. Labels follow the public taxonomy. |

An approved parent category certifies the published parent count; it does not
reveal an omitted subtype count. A missing cell, absent release, missing subtype
or unknown occupancy remains unavailable information, not a measured zero. A
measured-empty **private source** batch does not itself grant a public zero
certificate. Observable no-release periods belong to the channel; private empty
retirements, rejection attempts and their causes do not.

For logical time \(t\le H\), the permitted release view is

\[
V_t=\{r\in M(D_B): r.\mathrm{sealed\_at\_ms}\le t\}.
\]

Include whole immutable releases only; do not clip their counts or intervals at a
checkpoint. Space and source intervals use half-open containment. Normalize
release aliases without introducing a label-dependent ordering or private key.
Logical sealing assumes instantaneous recipient delivery. It is separate from
execution time, queueing, transport, actual wall-clock delivery and client receipt.
No live deadline or runtime conclusion follows from this offline fixture.

The final view at **300000 ms includes the actual source EOF/terminal sealing
behavior** and must be labeled `final_including_eof`. It is distinct from any
interior view with \(t<300000\); do not call it an interior checkpoint, force an
earlier EOF to create a prefix, or use post-horizon information. EOF must be the
same declared boundary in IN and OUT. An implementation that emits a release
only after \(H\) must not backdate it into \(V_H\); that case needs explicit
later-availability/censoring treatment before a study can use it.

The attacker never receives raw/background observations, track/person IDs or
unions, private source/GT metadata, visits/dwell, suppressed candidates/categories,
original totals, suppression masks/reasons, failed checks, ownership/retirement
journals, debug overlays or private runtime. Source/candidate/world hashes and fixture receipts are audit
material, not recipient metadata: comparison against an IN or OUT receipt must
never be an attack input. Private research replays remain
private even when their UI shows a recipient display filter.

## Policy reference and implementation boundary

The fixture records an unchanged Spatial20 reference mapping from the existing
`mixed_spatial20_adaptive_immediate_off-policy.json` in
`results/spatial20-controller-correction-2026-10-24-v2/`, SHA-256
`eff7a65e08c3f352a0c984d956917e7312da8815021f256e68db6b2189016bda`.
Its root requires total and per-category track support at least five; the entrance
requires total support ten. Root bounds are 1.25–20 m, 400–4000-ms windows,
logical age at evaluation at most 4000 ms, semantic maximum loss at most one,
and selective suppression zero. West/east retain 1000-ms duration and age bounds;
west/central/east semantic maximum loss is 0.5. Full positive-area cell/Region
intersection applies. Its frozen execution vocabulary is
`publication_model=private_final_snapshot`, primary `strategy=semantic_first`,
`semantic_secondary_strategy=temporal_first`, `release_trigger=policy_satisfied`,
and `temporal_adaptation.coordination=cell_local`. These are reference provenance;
P25.1 certifies no public incremental stream or causal-prefix execution. The exact
file is authoritative over this summary.

This frozen reference maps the source and operational policy vocabulary; P25.1
does not execute it or choose a winning mechanism. The later study must freeze
all compared methods, legal global grids/windows and the regional static
reference under identical hard requirements within each policy condition. The
central local400 treatment and its control, if included, remain explicit separate
conditions. Their selection and the main attack budget are not frozen by this
single development fixture.

The existing `privacy.py` / `empirical_privacy.py` path validates the scalar
`ump.public-transcript.v1` channel. It currently rejects additional semantic
fields; it does not yet implement the complete channel specified above. P25.2
must introduce an audited versioned semantic-aware allowlist, preserve prior
scalar-study compatibility, validate actual semantic values and extend public-only
features. It must also materialize a deterministic recipient transcript for the
regional static baseline from its audited cells and policy-only schedule. Until
those gates pass, a scalar-only export cannot be described as evaluating the
complete semantic recipient product. This contract is not an implemented public
schema or access-control certification.

## Fixture acceptance and later evidence

The development bundle must contain a protocol written before filtering, original
IN bytes, the filtered OUT source, private target trace/provenance, identical
auxiliary files, a manifest and a separate verification result. Verification must
reopen the authenticated source, reconstruct eligibility/selection/knowledge and
OUT, and check exact background equality, unchanged batch/header metadata,
removal of the complete target contribution only, source fingerprint consistency,
auxiliary invariance and file hashes. No aggregation executable, model fitting or
attack evaluation is required for this source-neighbor gate.

All target episodes, IN/OUT worlds, mechanisms, policy variants and excerpts of
this recording share one source group. This already inspected historical source
and every derivative are **DEV only**, unavailable for final held-out TEST; ID
renaming or nearby slices do not make independent sources. Raw movement, IDs and
private labels remain local under ignored `results/`; Git receives only compact
aggregate receipts, contracts and implementation code.

P25.3 still must freeze independent TRAIN/CAL/TEST sources and counts, candidate
population and multiplicity, auxiliary profiles, methods/policy conditions,
features, fitting budget, calibration rules, checkpoints/EOF treatment, controls
and uncertainty analysis before final assessment. Planned risk measures include
ROC-AUC, observed TPR/FPR and threshold advantage, with uncertainty grouped by
independent source. Prior/auxiliary-only, no-output and unprotected controls must
be declared. Report risk beside retention, full-input semantic distortion,
retained detail, application utility and logical release delay. Full-input utility
uses each world's included aggregation input, not inferred physical occupancy. Neither
one-minus-AUC nor an operational track threshold is a universal privacy measure;
a single verified pair supplies no attack accuracy, statistical power or privacy
benefit estimate.
