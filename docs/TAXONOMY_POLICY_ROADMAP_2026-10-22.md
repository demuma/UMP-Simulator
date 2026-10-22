# Four-step taxonomy, policy and inspection roadmap

Date: 2026-10-22. This integrates the user's modifier-based taxonomy discussion
with immediate inspectable experiments. The attached implementation proposal
is a design input, not an instruction to implement all its modules at once.

## 1. Preserve and describe the present agent model

Map the seven existing production labels to explicit age/mode/aid/accessory
attributes before changing geometry, movement or population probabilities.
Keep identity separate from future time-varying equipment/mode state. Preserve
the distinction between the original richer taxonomy, the seven-profile
experimental projection and the limited currently implemented release tree.

The current flat AgentTypeAttributes combines sampling and simulation fields.
A pure, versioned Profile Builder with explicit modifier order is a suitable
later refactoring. Its synthetic parameter choices require their own evidence;
they are not supplied by Holländer et al.'s conceptual HCI taxonomy.

## 2. Define observation and release semantics

Private simulated truth, sensor-observed attributes and recipient-visible
categories are distinct contracts. `none`, unknown and deliberately withheld
must not share one value. Define a bounded set of truthful joint release
projections and application queries before extending the present single-parent
tree into independently generalizable facets. Separate marginal tables do not
automatically have the same support/composition properties as joint groups.

The current Pedestrian/Cyclist intermediate nodes and Root cost are available.
Scalar costs 0/.5/1 are declared category abstraction costs, not percentages of
total information lost or privacy risks. Per-attribute permitted/forbidden
release is a future rule; a maximum-loss bound alone does not force age or aid
to be omitted. Wider supported attribute combinations and calibrated sensor
classification remain open.

## 3. Exercise fine regional constraints before adding new geometry

Existing aligned rectangular PolicyRegions can affect only a few D6 leaves.
Their numeric requirements compile into the immutable policy tree and apply
to the full intersecting output footprint. Regions do not become data cells or
separate clocks. Selected overlapping regions and arbitrary polygons remain
unsupported. A residential context and a sidewalk can conceptually overlap;
that future layering needs an explicit composition/intersection contract.

The [leaf-scale protocol](LOCAL_LEAF_POLICY_PROTOCOL_2026-10-22.md) now specifies
four 2.5-m patches in an 80-m square: each patch covers four 1.25-m leaves,
16/4096 leaves in total. This is small enough to inspect every intended cause.
The same observations are compared under uniform and regional policies. Read
the [actual results and limits](LOCAL_LEAF_POLICY_RESULTS_2026-10-22.md).

This is ready now for numeric requirements. It is too early to claim regional
attribute-forbidding rules, realistic residential behavior or independently
timed semantic cells. In particular a common-window controller may apply the
strictest regional time cap to its entire domain; expose this coupling rather
than present it as individual temporal policy enforcement.

## 4. Inspect cells and audit controlled examples

The replay must allow explicit selection of an actual displayed cell, expose
its ID/geometry and original interval, and show published semantic group counts
separately from opt-in private source-type counts for that exact cell/interval.
No current sample, future sample or source-only type may be presented as a
published historical group. Missing public support remains unknown.

Use controlled cases with exact support, family-only support, a legal sibling
merge, insufficient Root support and a cross-boundary strict requirement.
Check source retirement, immutable publications, declared constraints and
observable utility losses before larger scenes. This step is integrated with
the current viewer and leaf-policy experiment; it does not require the full
modifier builder or a new collision solver.

Next, integrate semantics with the existing cell-local ownership/handoff
coordinator and repeat identical inputs. Then add seeded continuous-flow street
scenarios and meaningful type-count/hotspot queries, retaining strong legal
uniform-grid/window baselines and cases where adaptation has no advantage.

The [repository results package](REPLAY_DATA_PACKAGE.md) preserves compact
comparison tables, policy configurations and verification summaries for review.
Generated movement recordings remain local. A fresh checkout can regenerate
the small analytical fixture; exact historical moving-data replays require the
excluded local observations. Hash-only provenance does not reconstruct them.
