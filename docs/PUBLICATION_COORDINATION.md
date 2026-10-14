# Fixed-window publication coordination core

Initial A05 implementation, 2026-10-14. This document specifies implemented behavior,
verification and the remaining integration boundary. The class is tested with the real
aggregation/history/spatial-selector pipeline in C++, but the running simulator does not
invoke it yet. Its existing JSONL and MongoDB data remain internal research/debug output.

## Supported scope

`PublicationCoordinator` implements the coordination core for **private final-snapshot**:
all competing spatial alternatives remain private until one closed fixed window is sealed.
The entire configured sensor grid for that interval is one coordination domain. This is
intentionally conservative: it does not implement early child release, independent sibling
windows, bounded-hold deadlines, recipient-visible revisions or temporal extension.

The module owns an immutable metric evaluator and stream geometry. It accepts only the
next interval starting at its retirement watermark (initially zero), of the configured
fixed duration or a shorter explicitly truncated final window. Acknowledging a truncated
window ends the stream; later seals are rejected. It does not reinterpret
Temporal First or Spatial First; these are upstream selection priorities.

## Lifecycle and ownership

1. `seal(selection, nowMs)` verifies the stream, interval, canonical cell ID/geometry,
   non-overlapping cut, decision mapping and memory budgets. It recomputes policy checks
   rather than trusting debug pass flags. Every selected cell needs complete support and
   a passing assessment under the configured immutable evaluator.
2. It owns a copy of the bounded private candidate for later age/deadline checks and reserves
   the whole interval before returning `shared_ptr<const ReleaseSnapshot>`. One pending
   snapshot is the hard queue bound; competing/future seals fail explicitly.
3. `deliver(nowMs, sink)` rechecks the selected cells at the current simulation timestamp.
   Calls are synchronous and timestamps monotonic. The external sink must process the
   payload at this logical instant and return `Acknowledged` only after the entire snapshot
   is accepted. `Retry` or an exception leaves the same immutable payload, ID and reservation.
4. Acknowledgement retires the entire interval. Selected support is committed, while
   suppressed/unobserved support is retired without a public record. The monotonic
   watermark rejects every later historical candidate, including a parent covering an
   already committed child. Future split/merge is permitted at the next common boundary.

There is no rollback/cancel API. If a delivery becomes too old for its policy, it is rejected
and remains reserved. A prior attempt might have been visible even when its acknowledgement
was lost. Reopening that support or treating it as safely suppressed would be incorrect.
Durable reconciliation of this blocked condition remains F03 work; it is not silently retried
under weaker bounds. No busy wait or timer/thread was added.

This whole-grid mode holds all neighbors until acknowledgement, including passing cells.
It does not label them privacy-failing. Later small-domain/early-child models need a finer
cell/interval ledger; the current watermark must not be reused to pretend those models exist.

## Output and disclosure boundary

`ReleaseSnapshot` contains a length-delimited deterministic release ID derived from
run/sensor/application/interval, policy ID/version, interval/seal time, and approved cells
with geometry, counts and effective policy IDs. It deliberately has no whole-window totals,
suppressed cell statistics, failed alternatives or raw road-user identities. Empty or fully
suppressed windows retire privately without calling the sink.

For additive observation counts, a parent total of 24 and three visible children totalling
18 reveal the hidden child's 6 observations by subtraction. Therefore excluding the hidden
child while releasing its parent/global total does not hide that count. The regression test
constructs this case with real manager data. Distinct road-user counts are unions and are
not generally additive, so this example must not be described as a universal identity attack.
Disjoint coverage and minimum-support checks are still not a measured privacy guarantee.

The sink is external to the manager/coordinator and must atomically accept a whole snapshot,
deduplicate by release ID, reject conflicting content under the same ID and supply durable
acknowledgements. The core cannot enforce database permissions or transactions. Tests use
an idempotent in-memory sink and simulate an acknowledged write whose response is lost;
no production MongoDB release sink or access boundary is claimed.

## Memory and complexity

Only one candidate and one selected-only output are pending. Cell count, type-map entry count
and type-name bytes have explicit limits (`PublicationLimits`). The supplied candidate's
aggregate type map and all per-cell maps count toward these budgets. Geometry overlap checks
use cell IDs and ancestor paths, not a dense tree. Completed interval history collapses to a
single watermark rather than an unbounded ledger. Caller-owned retained snapshots remain
the caller's responsibility. No sensor/history identity strings are copied into this core.

## Verification

`PublicationRegressionTests` uses the actual manager, private history and spatial selector.
It covers: immutable ownership, reservation before output, competing parent/future rejection,
committed-child historical merge rejection, allowed future merge and split, Retry/exception,
acknowledgement loss with stable ID/content, reentrancy rejection, private empty/suppressed
retirement, additive subtraction, deadline expiry with reservation retention and no time
travel, unavailable/no-policy rejection, stream/geometry/cut validation, final truncated-window closure and resource limits.

All ten CTest suites and all six Python inspector tests passed. The publication suite was
rerun after adding monotonic rejection-time and truncated-stream checks.

Run with `ctest --test-dir simulator/build --output-on-failure -R publication_regression`.

## Required next implementation

- Explicit policy-selected model configuration and startup validation; reject unsupported
  model names instead of silently substituting this one.
- Wire the actual callback to seal/deliver and expose reservation/commit states in debug
  snapshots. Keep current internal diagnostics separate from recipient data.
- Durable idempotent sink and ledger recovery, pending write reconciliation and bounded
  retry/deadline scheduling (F03). A fresh process must use a new run ID until recovery exists.
- Validate asynchronous delivery timing before adding an asynchronous sink.
- Then add smaller coordination domains and other publication models with their own tests.

A05 remains open until these integration and durability requirements are satisfied.
