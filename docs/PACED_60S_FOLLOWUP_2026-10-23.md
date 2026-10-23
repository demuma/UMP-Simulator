# Approved 60-second paced replay follow-up

Date: 2026-10-23. Repository baseline: `566ecb1`.
This completes the temporary-capture item left open in the
[paced/live test report](PACED_LIVE_TEST_REPORT_2026-10-23.md).
[Compact results](PACED_60S_FOLLOWUP_RESULTS_2026-10-23.json) include the predeclared
plan, provenance hashes, verification, timing and deletion manifest.

## Result

The complete unpaced and paced outputs are equal after removing only `runtime`.
All **275,689 observation contributions** are accounted for. The longer trace
exposes a short deadline miss: one of 599 ordinary measurements takes more than
100 ms of service, and two finish more than 100 ms after their scheduled arrival.
There is no queue overflow or dropped input. The temporary backlog clears before
the next-but-one scheduled input; this is not a hard real-time guarantee.

## Capture and unchanged configuration

The user explicitly approved temporary local movement storage and deletion after
analysis. A fresh 60-s run uses the maintained Simulator with 500 initial Road
Users, all seven behavior profiles, an 80 x 80 m area, depth 6, 50-ms simulation
steps and 100-ms sensor samples. The previous instrumented live binary was reused
only after verifying that its production source hashes still match the checkout.
No algorithm, policy, movement or renderer code changed.

The local Semantic First / Temporal First secondary policy is unchanged:
category support >= 5, semantic loss <= 1, cell sides 1.25--10 m,
400--1,000-ms windows, 100-ms extensions and `policy_satisfied` release.
Population decreases from 500 to 366; this is not a constant-population workload.
The new realization differs from the earlier 20-s and 120-s recordings.

The capture audit verifies 1,200 GT frames, 553,190 GT records and 255,188 raw AGBS
cell records. Reconstruction yields 599 measured sensor frames. Exact per-cell
counts, type counts, geometry, timestamp cadence and identity uniqueness agree.
The 436 sampled GT observations outside the half-open sensor footprint are
explicitly excluded; missing frames are not converted to empty observations.

The live capture takes 84.655 s wall time and reconciles all 6,566 recipient
releases with committed journal payloads. Its three fresh UUID databases were
removed after verified export. This live path includes detailed diagnostics,
50-ms progress calls and synchronous MongoDB writes. The comparison below tests
unpaced versus paced replay, not equality between live MongoDB and replay payloads.

## Paired timing

The same authenticated input, binary and policy are used sequentially for both
replays; their hashes are unchanged before and after execution. Pacing is 1x with
an independent producer and an eight-event FIFO. Parsing and preflight precede
its arrival epoch. Ordinary measurement events and EOF are assessed separately.

| Ordinary input metric | p95 | Maximum |
|---|---:|---:|
| Source scheduling lateness | 10.03 ms | 10.05 ms |
| Queue wait | 0.049 ms | 25.79 ms |
| Consumer service | 76.22 ms | 119.06 ms |
| Scheduled arrival to completed service | 84.79 ms | 129.10 ms |

Peak queue occupancy is **1/8**. One service exceeds the 100-ms arrival interval;
two scheduled-to-completion intervals exceed it. The distinction matters:

- At logical 15.2 s, service takes 119.06 ms and scheduled completion lag is
  129.10 ms.
- The 15.3-s event waits 25.79 ms, then finishes at wall offset 15,373.865 ms,
  before the 15.4-s scheduled input. The backlog has recovered.
- At 15.5 s, service takes 94.65 ms; about 9.17 ms of source scheduling lateness
  raises total scheduled completion lag to 103.83 ms. Queue waiting is only
  about 0.018 ms, so this second miss is not persistent backlog from 15.2 s.

EOF service is 88.73 ms, with 98.78-ms scheduled completion lag. The unpaced core
run takes 32.779 s; complete process duration is 36.636 s. Paced processing,
including intentional waits, takes 60.099 s; complete process duration is 63.925 s.
These values are not a paired comparison with the earlier, different 20-s capture.

All 6,566 replay release callbacks acknowledge in-memory serialization. Their
scheduled logical seal-to-ACK lag is p95 69.50 ms, maximum 118.79 ms. This is not
external client or MongoDB receipt. The final result file is written after replay.

## Memory, verification and cleanup

Across 61 memory samples, history holds at most 21 bins, 10,500 observations and
555,975 identity bytes; final retained observations are 7,417. Sampled RSS rises
from about 117.1 to 187.6 MiB as retained result strings grow to about 79.9 MiB.
Process high-water RSS is about 1,252.4 MiB, already reached before the pacing epoch
in parsing/preflight. The replay tool preloads its input and retains research
outputs; its total RSS is not a streaming-aggregator memory bound.

The maintained summarizer validates full logical equality, cadence including EOF,
causal timing, queue limits, ACK correspondence and memory samples. Input/binary/
policy hashes remain unchanged. An independent review checked the compact evidence,
miss/recovery interpretation and deletion manifest. The source remains the version
covered by the preceding 73/73 CTest gate; no code changed in this follow-up.

After verification, **all seven generated movement, full-result and diagnostic
files were deleted**, totaling **933,173,280 bytes**. Their sizes and SHA-256 hashes
are recorded in the cleanup manifest. All three owned databases are also gone.
Existing user recordings were unchanged. Only compact proof, aggregate counts,
numeric timing evidence, configuration and logs remain; Git receives compact
results and documentation.

Deletion means the exact new unseeded motion cannot be reconstructed from its hash.
The tools reproduce the measurement procedure, while the previously retained
20-s recording remains available for repeatable regression comparisons.

## Next step

The longer same-input test is complete. The separate integrated live bottleneck
remains open: measure diagnostic construction, serialization and flushing apart
from aggregation and publication before changing that path. The isolated deadline
misses also rule out claiming a hard 100-ms bound from either replay trace.
