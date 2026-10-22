# Semantic priorities and the release trigger

**October 22 extension:** [semantic cell-local coordination](SEMANTIC_CELL_LOCAL_CONTRACT_2026-10-22.md)
now supports taxonomy-enabled independent owners and both Semantic First secondary
priorities. Earlier scope exclusions below describe the original implementation
gate; see the [new verification report](SEMANTIC_CELL_LOCAL_TEST_REPORT_2026-10-22.md)
for current behavior and remaining visualization/effectiveness limits.

Pre-implementation contract, 2026-10-21. This bounded step separates hard
eligibility from intentional preference waiting. Existing archived results,
policies, protocols and binaries remain unchanged.

## Configuration and scope

```yaml
policy_tree:
  execution:
    strategy: semantic_first
    semantic_secondary_strategy: spatial_first
    release_trigger: policy_satisfied
```

Semantic secondary choices are `temporal_first` (omitted default, preserving
the existing secondary) and `spatial_first`. The semantic controller's release
trigger defaults to `policy_satisfied`; `priority_satisfied` explicitly retains
intentional preference waiting. These execution choices do not change any
regional metric requirement. They apply to the common-window semantic
controller. Nonsemantic TF/SF scheduling retains its established behavior;
the trigger does not retroactively redefine those two reference strategies.

Cell-local ownership, independent starts and merge handoffs already exist for
nonsemantic TF/SF. Taxonomy-enabled cell-local execution is still explicitly
rejected. Integrating semantic priorities with that coordinator is a separate
required step, not an implementation switch or an architectural impossibility.
This step must not silently claim individual semantic windows.

## Publish when policy is satisfied (new semantic default)

At every scheduled endpoint, test the zero-loss preferred cut and then the
remaining distinct taxonomy loss ceilings in ascending order, using all legal
spatial levels. Choose the first complete passing cut and publish immediately.
Thus an exact parent is preferred over generalized finer cells at the same
endpoint. Every original support, space, time, age, mean-loss and coverage
constraint still applies. A synthetic preference ceiling never replaces a
Policy Tree bound.

Completeness requires complete measurements, no suppressed observed support
and retained observation contributions equal to original contributions. It
does not require public zeros in unoccupied regions. Until a complete cut
exists, partial cuts remain private; the current common-window coordinator
does not publish valid neighbors independently. At a terminal endpoint the
existing retention-first legal partial fallback remains.

Immediate eligible release overrides optional waiting for better semantic or
spatial accuracy. Therefore the two secondaries can have identical outputs
under this trigger. They must not be advertised as distinct measured mechanisms
where that immediate-release rule removes the behavioral distinction.

## Intentional preference waiting (explicit option)

With `priority_satisfied`:

- Temporal secondary tries a complete zero-loss cut over all legal spatial
  levels at every endpoint; if none exists it extends time.
- Spatial secondary tries a complete zero-loss cut at finest observation depth
  while extension is possible; if none exists it extends time before allowing
  any spatial merge. At the terminal boundary it tries zero loss over all legal
  spatial levels, then ascending positive-loss ceilings.
- Either secondary publishes immediately once its current preferred complete
  cut exists. This is a bounded wait-before-merge baseline, not prediction or a
  global lexicographic optimizer.

At a terminal endpoint, if no full cut exists at any assessed ceiling, maximize
retained observation contributions, then minimize actual maximum loss, then
weighted mean side, then cell IDs. This documented retention-first exception
is preserved. Missing measurements cannot become a legal partial release.
Resource or invalid-evidence failures throw, never masquerade as suppression.
Sink failure/retry must preserve ownership and the exact immutable proposal.

## Taxonomy and loss interpretation

Terminals have declared loss 0; Pedestrian/Cyclist intermediates in the moving
catalog have .5; the Road User root has 1. These are declared category costs,
not fractions of all information lost and not empirical privacy scores.
`semantic_max_loss.max: 1` permits root generalization; it does not force it.
A measured maximum 1 means at least one published bin reached root cost, not
that every cell/bin was generalized. Root output retains counts, spatial
support and time support but loses road-user type distinctions.

Adult/Child/Senior Pedestrian can pool to Pedestrian; cyclist subtypes can pool
to Cyclist before Road User. Existing seven-profile captures contain only Adult
E-Scooter Driver, mapped to one terminal. A new versioned example makes that
adult terminal explicit below E-Scooter (.5), without inventing a Child Scooter
profile or rewriting the captured sources. Mixed category cuts are allowed:
one cell can retain exact categories in one branch and generalize another.

## Acceptance before experiment claims

Test exact-parent versus generalized-fine ordering; default early generalized
release; explicit old waiting; temporal-secondary early parent versus
spatial-secondary later exact fine output; Pedestrian/Cyclist/E-Scooter
intermediates; hard semantic/space/age/coverage limits; terminal partial
suppression; EOF; deterministic retry and source accounting. Independently
reconstruct public category counts and distinct unions from raw inputs.

Record actual secondary/trigger in private diagnostics only. Positive-ceiling
search before the deadline is not `terminal_fallback`. The recipient schema
must not expose preference trials, private identities or failed support.
Historical fixtures/runners with intentional waiting must opt in explicitly;
archived immutable files are never migrated. Test reports distinguish old
behavior reproduction from new default acceptance.
