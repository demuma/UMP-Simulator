# Adaptive publication implementation contract

Status: contract implemented and verified, 2026-10-14. See
[validation evidence](ADAPTIVE_PUBLICATION_VALIDATION.md) for results and remaining limits.

## A05 integration

The first supported application model is `private_final_snapshot`. One complete
spatial cut of a common interval is coordinated as a unit. Raw sensor collections,
private diagnostics and recipient releases are different data products. Selected
cells alone enter the recipient database; suppressed cells, global totals, private
identities and type breakdowns do not. Counts of distinct road users remain a
support proxy, not a formal anonymity guarantee.

A release is one immutable MongoDB document keyed by its deterministic release ID.
A separate private journal records preparation and commitment, including private
retirement of wholly suppressed intervals. Exact-content duplicate checks make
retries idempotent. Writes require acknowledgement and journaling. Failed or
ambiguous writes retain their reservation and stop the stream after bounded
attempts. Existing visible identical output can be reconciled; an old undelivered
snapshot must never be published automatically without fresh policy/deadline checks.
Read-only journal inspection is not a simulator checkpoint/resume implementation.

Destination validation runs before database initialization. Recipient and journal
databases must be distinct and separate from every raw simulator/sensor database.
This is an application data boundary; MongoDB account/access provisioning remains
an operational responsibility. Existing user configuration stays unchanged.

## A03 temporal slice

A synchronous controller queries the manager's existing bounded private history;
it does not add a SharedBuffer reader, thread or duplicate observation store.
The history reconstructs exact identity unions for arbitrary half-open intervals.
Raw fixed-window diagnostics remain available independently.

The policy tree selects an application-level strategy:

- `temporal_first` preserves time: try spatial coarsening before extending time.
- `spatial_first` preserves space: extend time before spatial coarsening.

Start at the configured base window and extend by explicit sampling-aligned steps.
Reevaluate only at scheduled boundaries and final shutdown. Publish early when all
selected requirements pass. Preserve the original interval start and use a common
handover boundary after retirement. The initial whole-domain window respects the
strictest applicable regional duration/age cap, including empty footprints. This
conservative behavior can hold passing cells and limits independently useful
regional adaptation; independent sibling windows are subsequent research work.

At the legal temporal bound, apply remaining spatial actions and suppress unresolved
footprints. Missing samples and unavailable mandatory metrics never become passes.
Only successful terminal output commits the selector's transition state. Retention,
evaluation work, output size and retries are bounded. A terminal short interval is
explicitly marked; it must not disappear at exact raw-window boundaries.

## Verification and deferred work

Tests cover exact unions, distinct strategy ordering, early completion, regional
bounds, missing evidence, final flush, future refinement, duplicate/conflicting
writes, lost acknowledgement, private empty retirement and counts-only output.
Disposable UUID-named databases are the only integration-test databases removed.

Deferred: additional publication models, automatic simulator restart/checkpointing,
independent regional windows, concurrent policy contexts, A07 selective descendant
rescue, proactive ancestor caches, differential privacy, attack-based privacy metrics
and measured experiment claims. Runtime and utility comparisons require experiments.
