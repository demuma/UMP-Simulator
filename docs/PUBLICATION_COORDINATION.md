# Publication coordination and durable output

Status: 2026-10-14. A05's first supported model, `private_final_snapshot`, is integrated
into the running AGBS pipeline. This document describes implemented behavior. Other
publication models and automatic simulator checkpoint/resume remain open.

## Supported scope and ownership

The entire sensor grid over one closed interval is one coordination domain. Spatial
alternatives stay private until a final non-overlapping cut is sealed. A passing cell
may be held while another cell needs adaptation. Independent sibling windows, immediate
child releases, bounded-hold variants and recipient-visible revisions are not implemented.

`AggregationManager` owns sensor-independent input/history. `SpatialSelector` or
`AdaptiveAggregation` proposes the cut. `PublicationCoordinator` validates and reserves
it. External `PublicationStore` owns MongoDB persistence. Sensors do not write recipient
releases themselves. Calls are synchronous; no new thread or SharedBuffer reader exists.

The default coordinator accepts the next fixed window or a truncated final interval.
Temporal integration supplies an explicit maximum and permits sampling-aligned variable
intervals, including shorter regional deadlines. Every interval begins at the previous
retirement watermark, initially zero. A truncated interval ends the stream.

## Configuration and demonstration

Run the fixed-window publication example:

```sh
cd /Users/maxdemu/Developer/UMP-Simulator/simulator/examples/publication
../../build/Simulator
```

It appends raw data to `UMP_Publication_Demo_Raw`, selected releases to
`UMP_Publication_Demo_Releases.releases`, and private journal entries to
`UMP_Publication_Demo_Private.publication_journal`. Clearing is disabled. The main
`simulator/config.yaml` is unchanged. The temporal example is documented in
[TEMPORAL_AGGREGATION.md](TEMPORAL_AGGREGATION.md).

Within a history-enabled aggregation stream with `spatial_selection`:

```yaml
aggregation:
  publication:
    database: UMP_Publication_Demo_Releases
    collection: releases
    journal_database: UMP_Publication_Demo_Private
    journal_collection: publication_journal
    max_document_bytes: 8388608
    max_attempts: 3
  policy_tree:
    # Existing id/version/root/regions remain required as applicable.
    execution:
      publication_model: private_final_snapshot
```

Only this publication model is supported. Unknown models/settings fail rather than
substitute behavior. Destination databases must differ, including case-only differences,
and neither may be a raw GT/sensor database. Cross-stream journal/recipient overlap is
also rejected. Names, geometry, timing and execution settings are checked before database
initialization. Filesystem I/O and service availability can still fail during startup.

Database separation does not provision MongoDB users or ACLs. Recipients must not have
access to private history, raw data, diagnostics or the journal. Distinct releases across
applications/recipients need separate composition analysis; isolation alone is no proof.

## Lifecycle

1. `seal(selection, nowMs)` checks stream/geometry, interval, disjoint cut, budgets and
   policy requirements afresh. Complete observation coverage and a passing assessment
   are required for every selected cell. It retains bounded private evidence and reserves
   the whole interval before exposing an immutable release snapshot.
2. The store persists a private `prepared` intent before a recipient write is possible.
   The stable `_id` encodes run, sensor, application and interval without ambiguous
   concatenation. The same ID with different content is a conflict, never an update.
3. `deliver(nowMs, sink)` rechecks selected requirements at the current simulation time.
   One immutable BSON document represents the entire release, giving single-document
   atomicity without requiring a MongoDB replica-set transaction.
4. The store verifies acknowledged identical recipient content and marks the journal
   `committed`. Only then does the coordinator retire the interval. Entirely empty or
   suppressed cuts produce no recipient document, but their private retirement is journaled.
5. Successful terminal output commits the selector's future-transition state. Subsequent
   intervals may merge/refine; none may reuse pending or committed historical support.

The default BSON budget is 8 MiB; the hard configured ceiling is 15 MiB, leaving headroom
under MongoDB's document limit. Both public documents and private wrappers are checked.
Writes request majority acknowledgement plus journaling; primary majority reads reconcile
ambiguous insert results. These tests run on local standalone MongoDB.

Retries are bounded and synchronous at the same logical simulation instant. This is not
wall-clock latency control: a stalled DB slows the simulator, and these checks do not
claim that an external real-time application deadline was met. Conflicting content, size
limits and failed policy checks are fatal. Exhausted retries abort the simulation and leave
the private intent/reservation intact. No later window may silently bypass it.

Debug snapshots are allocated before possible disclosure. After a durable commit, selection
JSONL failures are reported explicitly but cannot undo release or prevent handover. Raw
candidate diagnostic failure, which occurs before that interval's release, remains fatal.

## Recovery boundary

`recoverPending` and `recoverStream` read bounded journal records; `reconcile` confirms
whether an identical release is already visible. None publishes data. An insertion whose
acknowledgement was lost can be recognized without a second disclosure or replacement.

Automatic continuation of a stopped simulation is **not implemented**. Restoring the same
stream requires retirement/reservation state and sufficient private evidence for fresh
policy checks. A stale undelivered snapshot must not simply be sent to recipients. The
simulator always generates a fresh run UUID; do not manually reuse a previous run ID with
a new in-memory coordinator. The store assumes one coordinator owner per stream and does
not arbitrate overlapping different intervals written by concurrent external producers.

There is no cancel/rollback that reopens ambiguous support. Deleting a public document
cannot retract what a recipient already learned. Committed journal entries accumulate on
disk as the audit history; automatic journal archival is not implemented. In-memory pending
output and recovery results are bounded separately.

## Recipient payload and limitations

Schema `ump.release.v1` includes approved cell geometry, observation count, distinct road-user
support, mean sampled occupancy, policy identity and interval/seal metadata. It excludes
raw identities, per-type breakdowns, suppressed-cell statistics, whole-window totals and
failed alternatives. The journal contains only the same scalar-only release snapshot plus
private lifecycle metadata; raw reconstruction evidence remains in bounded history.

For additive counts, publishing parent total 24 and visible children totaling 18 reveals
the suppressed child's count 6. The tested disjoint-interval/cut rules prevent this particular
parent/child subtraction construction. Distinct support counts are unions, not additive.
These safeguards are not formal k-anonymity, differential privacy or measured attack resistance.

Diagnostic `spatial_selection.publication` is `disabled`, `committed`, or
`retired_without_release`; `release_id` links to the journal. The entire diagnostic record,
including suppressed counts, remains private regardless of that status.

## Verification

The standard-C++ coordinator suite checks reservations, immutable content, fresh policy
checks, deadlines, malformed/overlapping cuts, subtraction, sink failures and future handover.
MongoDB store tests cover duplicate/conflicting inserts, lost acknowledgement, read-only
recovery, budgets and empty retirement. The complete pipeline suite covers both strategies,
exact unions, contiguous variable windows, missing/empty input and exact/partial final flush.
All database suites create and delete only fresh UUID test databases.

```sh
cmake -S simulator -B simulator/build -DUMP_BUILD_PUBLICATION_STORE_TESTS=ON
cmake --build simulator/build -j6
ctest --test-dir simulator/build --output-on-failure
```

See [ADAPTIVE_PUBLICATION_VALIDATION.md](ADAPTIVE_PUBLICATION_VALIDATION.md) for recorded
whole-simulator checks. Remaining work includes safe checkpoint/resume, other publication
models, independent regional domains, recipient composition and experimental evaluation.
