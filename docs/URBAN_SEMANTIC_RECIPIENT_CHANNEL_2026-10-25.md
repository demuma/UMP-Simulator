# P25.2 semantic recipient channel and regional-static publication

Date: 2026-10-25. This addendum implements the recipient boundary required by the
[frozen P25.1 contract](URBAN_PRIVACY_MEMBERSHIP_CONTRACT_2026-10-25.md).
It does not modify that contract, the aggregator or the historical scalar channel.
It supplies data/feature plumbing for later independent urban membership studies.

## Versioned boundary and retained information

`semantic_privacy.py` exports and validates `ump.public-transcript.v2`:

- Fixed square coverage/leaf grid, sampling period and declared horizon.
- A fixed public taxonomy: ID/version, category IDs, parent relationships and
  information-loss values. Private source input-type mappings are omitted.
- An explicit availability model and the approved release sequence.
- Every approved release interval, sealing/availability time, normalized alias,
  publication model and public policy identity/version.
- Every selected cell's geometry, contributions, distinct observed-track support,
  occupancy (including null/unknown), effective public policy identity and semantic
  category counts/supports/loss summary.
- Optional public coordination scope, including an ancestor scope containing
  multiple descendant cells, retained in the channel and validated geometrically.

Strict allowlists reject unknown fields at public header, release, cell, scope,
taxonomy, semantic summary and category-bin levels. Private source/run/sensor IDs,
raw configuration, GT, private windows, journals, suppression reasons/masks and
runtime never enter the export. Native run-derived release aliases are replaced
by public sequential aliases. The pilot additionally verifies actual native model,
policy/version and compiled per-cell effective policy IDs against the frozen
public policy; merely resembling a pN suffix is insufficient.

The original `privacy.py` / `empirical_privacy.py` scalar v1 interface remains
unchanged and continues rejecting semantic additions. V2 uses an explicitly
labelled scalar projection solely to reuse existing scalar feature arithmetic.
That projection neither defines the recipient channel nor drops semantic content
from canonical channel comparisons.

## Validation and limits of public arithmetic

The taxonomy must be a connected acyclic tree with unique IDs, a root loss of one,
terminal loss zero, finite losses in [0,1] and nonincreasing loss toward children.
Published semantic bins form a unique antichain. Their observation counts sum to
the cell count; each support is a positive integer bounded by its bin count and
cell support. Under this contract's stable-type episode assumption, bin supports
partition the cell identities and sum to the cell's distinct-track support.
Weighted mean loss, maximum loss and minimum category support are recomputed.

This arithmetic does not prove the claimed identity unions or correspondence to
raw observations. The pilot therefore independently rechecks native geometry,
coverage, retirement, counts, raw identity support, taxonomy and every effective
regional bound before exporting. It uses the existing full-input auditor with an
explicit one-million-cell limit. Public and private verification have different
roles; a self-consistent but fabricated histogram is not certified by an allowlist.

Public geometry is checked against quadtree IDs. Overlapping public space-time
support, invalid intervals, duplicate cells, illegal ancestors/descendants,
nonfinite/bool-as-number values and inconsistent availability are rejected.
Missing cells, absent categories and unknown means retain availability masks;
a parent category never supplies a fabricated zero count for its descendants.

## Availability is an explicit evaluation assumption

The P25.1 policy names `private_final_snapshot`. The P25.2 default is therefore
`availability_model=final_snapshot_at_horizon`: for a retrospective full-horizon
evaluation, every record is *assumed* available at H. Original `sealed_at_ms`
remains public metadata; `available_at_ms=H` gates visibility. A real completed
snapshot is obtained after replay processing; this model does not measure that
wall-clock delivery or certify receipt at H.

`logical_sealing` is a separate explicit model in which availability is assumed
at logical sealing with instantaneous delivery. Regional composition requires a
nonempty statement of that assumption/evidence. Neither option is a measured
live-delivery claim. Native releases sealed after H are rejected; they are never
backdated into the declared full-horizon view.

Whole releases are selected by `available_at_ms` for prefix/recent views, retaining
the fixed public horizon and reindexing public aliases. Counts or intervals are
never clipped to a checkpoint. Tests establish availability gating; the pilot's
full-episode quarter-sampled auxiliary knowledge remains retrospective and does
not acquire a causal-prefix interpretation.

## Public side information and feature contract

The pilot keeps a separate fixed `public-context.json` with public policy bounds,
region geometry, declared method overrides, taxonomy and public map/access assets.
It is identical for IN and OUT. Reference policy execution vocabulary is identified
as provenance; actual fixed modes and derived schedules are explicitly declared.
The context is not the raw simulator configuration. Private source/fixture hashes,
world labels, raw input totals and target identities stay in private receipts.
The v2 JSON does not certify host/database access control or implement a map service.

Feature order is fixed by the public taxonomy, not by the categories that happen
to be released. V2 reuses 18 count/availability or 31 count/geometry features,
adds six semantic summary coordinates, six coordinates per taxonomy node, and
(two with geometry enabled) release-availability timing coordinates. The current
12-node urban taxonomy gives **111** full features.

Per-category coordinates describe explicitly published global and candidate-
matched contribution/support summaries with availability fractions. All values
come from the complete public transcript and permitted coordinate/time sightings.
No target type or source identity is supplied. Whole-history support sums are
sums across products, not a unique person population. Scalar-only geometry
ablations still use geometry for matching and are not causal leakage decompositions.

A valid semantic-only change at unchanged scalar counts changes both the v2
canonical channel and semantic features while leaving scalar-projection features
unchanged. No-output has the same feature dimension and an all-zero output-feature
vector. Unknown mean and explicitly published zero remain distinguishable.
These are bounded summary features for an evaluated attacker, not all information
an unrestricted recipient could derive from the preserved full stream.

## Regional static recipient stream

`regional_public_transcript.py` composes a publication stream from a declared
four-schedule native family (400/1000/2000/4000 ms) on one fixed 10- or 20-m grid.
It chooses the longest permitted window per cell using public footprint/policy
bounds before inspecting source observations or publication success. Membership
changes do not change this schedule.

Each source/config/binary/native-result/private-audit receipt is verified. Every
native fixed schedule's full nonempty partition, selected and failed groups,
source accounting, category metrics and effective bounds are recomputed, including
components unused by the final schedule. The selected source partition also
accounts mathematically for empty cell intervals.

Only exact originally published cells from their assigned schedule are retained.
Original semantic/count payloads, source intervals and sealing metadata remain.
Cells sharing interval/seal/model/policy are grouped into one deterministic event,
with public-order sorting and sequential aliases. Declared public policy namespaces
may replace native method-specific prefixes only after reconstructing the actual
compiled policy suffixes. This avoids world- or component-dependent ID aliases.
When all cells select 4 s, the complete normalized transcript equals native global
4 s, including event grouping, not merely counts.

The result is a **derived public transcript**, with a separate private audit. It
is neither a fabricated native replay result nor a timed online scheduler. Native
runtime is null; source utility statistics using logical seals are explicitly
separate from the chosen recipient availability model.

## Bounded DEV plumbing pilot

`run_urban_privacy_channel_pilot.py` uses the verified P25.1 source pair and one
unchanged Spatial20 policy, suppression OFF. It predeclares ten native commands:
IN/OUT × Semantic First and fixed20 at 0.4/1/2/4 s. Four fixed cases per world also
supply regional-static20, for twelve validated recipient streams in total.
The copy of the executable and all source/policy/auxiliary/map artifacts must match
their previously authenticated receipts; relevant code, feature names, schedule
and commands are frozen before execution. Completed outputs/audits/features are
added to an immutable receipt ledger and rechecked before composition/reporting.

All native inputs account for the original observation contributions. No movement
is generated or resimulated. Exports and feature extraction receive only declared
public products/knowledge. Public headers/context are invariant across labels;
H-1 exposes no final snapshot and H reproduces the full product exactly. The
pilot excludes all episode/source aliases from channel content, validates compiled
policy IDs, checks fixed feature dimension and verifies identical public-only
regional schedules in both worlds.

This is one already inspected DEV source group. No model is trained, no AUC or
attack operating point is calculated, and no privacy or runtime superiority is
claimed. Main independent recordings and TRAIN/CAL/TEST fitting remain P25.3/4.
Raw replays, recipient streams, feature values and private receipts remain local;
Git contains code, this contract addendum and compact aggregate verification only.
