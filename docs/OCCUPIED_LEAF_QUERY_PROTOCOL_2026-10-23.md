# Occupied-leaf history query: bounded optimization protocol

Date: 2026-10-23. Production baseline: `a304870`. This gate investigates the
previous 132.6855-ms peak after prefix owner lookup. The diagnosis precedes the
production change and its measurements. No favorable timing outcome is assumed.

## Evidence and scope

Three fresh detailed profiles execute the former peak tick at logical 15.2 s in
89.70, 89.03 and 92.32 ms. Their maxima are 111.94, 103.34 and 104.89 ms. Thread CPU
at the latter two maxima nearly equals wall time. The old outlier cannot be
attributed retrospectively because the original instrumentation lacked per-tick
CPU and scope measurements. Repeated computation near the 100-ms input period is
nevertheless observable. See the separate per-tick diagnostic report.

The 2,247 whole-domain history reconstructions used by refinement take about
4.71 s in each detailed profile, approximately 32.1% of replay core time. The
caller consumes only occupied leaf geometry, although `queryFinest` computes
full scalar statistics, distinct-identity sets and per-leaf semantic evidence.

Add a whole-domain `queryOccupiedLeaves(startMs, endMs)` and use it only in
`refineDue`. Keep full queries for candidate evaluation, diagnostics and all other
callers. Use sparse sorted IDs and canonical geometry; do not allocate the dense
4^D leaf grid. No caching, policy change, changed release cadence, suppression
change or new coordinator action is part of this gate.

## Required invariants

- Reject negative or empty intervals. Preserve Evicted-before-Future precedence,
  retention boundaries, half-open sample membership, absent t=0 sampling, missing
  and explicitly unavailable measurements, and measured empty frames.
- Return no vector for Future/Evicted; return a present, possibly empty vector for
  Complete/Incomplete/NoScheduledSamples. Match `queryFinest` status and sorted
  canonical cell geometries on valid history.
- Retain one whole-interval `SemanticAccumulator`. It must reject the same
  cross-leaf identity/type conflicts, accept aliases of the same canonical leaf,
  and preserve exact semantic count-range validation. Global node counts dominate
  every per-leaf subset; no per-leaf evidence is necessary for these checks.
- Preserve taxonomy-disabled behavior. Keep normal append validation unchanged.
- Gather and validate all distinct-start queries before frontier changes or
  publication, preserving failure behavior for invalid history. Different memory
  allocation/failure characteristics are an expected consequence of less work.

## Acceptance and timing

1. Build the actual Simulator, AggregationReplay and test targets in Release.
2. Add focused public-API history tests plus an independent time/row oracle, sparse
   depth-14 coverage, semantic alias/conflict and integration failure checks.
3. Run the full available CTest suite after production/test edits. Do not run the
   normal Simulator, reset the user's MongoDB Simulation database or change inputs.
4. Execute all ten variants of the authenticated frozen moving comparison. Require
   complete result JSON equality against frozen originals after removing only
   `runtime`, including private decisions, scopes and public records.
5. Add a local native repeat and three instrumented profiles, each subject to the
   same full-output equality check. Keep baseline and new measurements separate;
   profile only in an isolated source tree and preserve source/protocol hashes.
6. Authenticate all pinned inputs before and after. Measure replay core, process
   wall/CPU and peak RSS; report p50/p95/max input-tick wall service, thread CPU,
   scope/counter deltas and a modelled FIFO with 100-ms arrivals. Keep EOF separate.
   Do not add inclusive scope times. Discuss instrumentation and host variability.

Store compact English protocols, results and test reports in Git; keep observations,
raw releases, copied source trees and build products local. A lower measured peak
on this single 20-s, 199-frame workload is not a worst-case bound or live real-time
proof. Longer paced runs, renderer/database contention, actual delivery latency,
backpressure and overload handling remain later gates. Policy/semantic-cap studies
and privacy attacks remain outside this optimization.
