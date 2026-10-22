# Semantic cell-local release contract

Date: 2026-10-22. Implementation review gate following the common-window
leaf-scale policy experiment. This document specifies intended behavior; the
accompanying test report records which checks have actually passed.

## Scope and terminology

Integrate the existing truthful semantic category tree with the existing
cell-local ownership, interval, publication and handoff coordinator. Do not
change movement generation, the production configuration, frozen experiments,
or the nonsemantic TF/SF scheduling contract.

Temporal First preserves temporal detail; Spatial First preserves spatial
detail; Semantic First preserves semantic detail. Its secondary strategy is
Temporal First or Spatial First. Semantic costs describe category abstraction,
not a measured privacy gain. All hard regional constraints still apply to the
entire footprint and interval of each candidate.

## Hard eligibility and preference

A hard-eligible candidate satisfies every configured metric and structural
constraint. Semantic preference cannot override a failed hard constraint.
Semantic First searches permitted category ceilings in increasing order
(exact labels, intermediate categories, Root). Among equal semantic loss,
prefer the finer spatial representation. This is a bounded local policy,
not a globally optimal mean-loss objective.

For `release_trigger: policy_satisfied`, plan feasible merges at the current
endpoint before disclosing their children. A current parent that legally
rescues a failed child may consume hard-passing siblings, including exact
siblings, if the complete unpublished footprint and interval are eligible.
An exact or lower-loss parent may also improve a generalized passing child.
Publish eligible remaining owners immediately. Do not hold a hard-passing
owner solely for a possible future merge. Failed owners may extend their own
interval; empty-domain holds remain bounded. Unrelated regions do not share
a release clock.

For `priority_satisfied`, before the owner's local terminal endpoint, Semantic
First seeks zero semantic loss. Temporal First secondary may spatially merge
now to retain exact categories; Spatial First secondary preserves fine space
while waiting. At a terminal endpoint, try every legally permitted semantic
tier and spatial rescue, then retain valid owners and suppress unresolved
support. Any hold must respect its owner's hard duration and age deadline.

Taxonomy-enabled TF/SF retain their respective dimension ordering. Their
`policy_satisfied` trigger also forbids future-only holds of hard-passing
owners. Existing nonsemantic TF/SF behavior is unchanged.

## Ownership and publication invariants

- A parent can consume only a complete unpublished frontier with the same
  actual interval start. Fine and coarse owners may coexist.
- Previously published, suppressed or explicitly retired empty support cannot
  be reused. Different starts require existing future handoff coordination;
  they cannot be repaired by rewriting recipient history.
- Public semantic bins contain only declared truthful released categories.
  Private identity and raw-type evidence remain in trusted diagnostics.
- Exact distinct-person unions, half-open intervals, source completeness and
  full-footprint policy evaluation remain mandatory.
- Parent planning and resource preflight precede irreversible publication.
  Failed acknowledgement preserves the same pending ownership transaction.
  Retried delivery rechecks age and other time-dependent hard requirements.
- Potential future semantic improvement is not a guarantee: missing evidence,
  impossible structural constraints and expired bounds still fail closed.

## Required verification

1. An eligible local owner releases at 400 ms while an unrelated failed owner
   can extend to 1000 ms; immediate release does not wait for a speculative
   future rescue.
2. A legal exact parent can beat generalized children, an intermediate category
   can beat Root, and secondary priorities differ when preference waiting is
   explicitly selected.
3. Tiny regional semantic, duration and age bounds govern every intersecting
   candidate, including empty policy-covered portions of a parent.
4. Mixed-depth same-start merges, incompatible starts, handoffs, exact identity
   unions, missing coverage, terminal flush and source retirement stay valid.
5. Delivery failure/retry, expiry at retry and scoped MongoDB recovery preserve
   public semantics and prevent duplicate source use. Legacy encodings remain
   compatible.
6. Resource limits fail before disclosure; independent raw-input audits check
   semantic bins and scalar space-time ownership, not only controller flags.
7. Compare common and local modes on identical analytical input, reporting
   retained support, release age, detail and policy failures without inferring
   empirical privacy gains.

## Visualization boundary

The existing common-window viewer must continue rejecting cell-local results
until it supports independently valid historical intervals and a correct
spatial mosaic. A latest-global-frame approximation would misrepresent this
contract. The analytical leaf-policy fixture is stationary and intentionally
co-locates distinct identities; it is not a realistic moving population.

## Verified implementation notes

The [test report](SEMANTIC_CELL_LOCAL_TEST_REPORT_2026-10-22.md) records the
completed gate. A scheduled handoff is also a local terminal boundary. Explicit
merge requests obey the same secondary preference as automatic candidates.
Nested broader rescues can supersede narrower semantic improvements when needed
to rescue a failed domain; this is not global lexicographic optimality.

The base window schedules an initial owner check; it is not a hard minimum
release duration. Current parent rescues can use shorter intervals at another
owner's endpoint unless `window_duration_ms.min` forbids them. Local
`attempted_ceilings` denotes the ordered representation tiers through selected
loss, not a count of ancestor computations.
