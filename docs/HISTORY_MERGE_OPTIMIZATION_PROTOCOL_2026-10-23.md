# Sequential history-query and merge-feasibility optimization

Date: 2026-10-23. Baseline `a402479`. The user selected single-cell history
queries and merge-feasibility checks before parallelization. No threading,
policy, input, semantic-cap, release-scheduling or privacy-evaluation change.

## Order and acceptance

1. Freeze the current native replay binary, relevant source and authenticated
   existing moving capture/study. Measure one fresh native local control and one
   isolated detailed profile. Do not infer gains from older wall-time outliers.
2. Improve single-cell history queries only. Use existing canonical quadtree IDs
   to exclude unrelated observations, preserving complete exact evidence for the
   requested cell and interval. Explicitly review retained-memory overhead, append
   validation/failure, expiry, missing/empty observations, aliases and cross-cell
   identity conflicts. Never sum child distinct counts.
3. Build actual Simulator/Replay and run the full available regression suite.
   Compare all ten native variants against their complete frozen JSON references,
   removing only runtime; collect a detailed local profile. Stop and fix any
   correctness failure before the next production change.
4. Improve merge-feasibility lookup only after stage 1 passes. Preserve disjoint
   frontier ownership, four-base-cell boundaries, mixed depths, common original
   starts, strict end-after-start, complete footprint coverage, handoffs, holds,
   budgets, failure ordering where observable, publication and ACK/retry behavior.
   Prefer canonical prefix/range lookup without a persistent secondary index.
5. Build and run the full regression suite again. Compare all ten full outputs;
   collect three local detailed profiles and a final uninstrumented local repeat.
   Native matrices include both local secondary priorities and common/fixed controls.

Use independent behavioral tests/oracles for sparse and mixed-depth corner cases,
not only output comparisons on one recording. Keep production changes separated
from isolated instrumentation. Review exact output and requirements between gates;
roll back an optimization if it breaks required behavior or has no justified benefit.

## Timing and reporting

Authenticate source, executable, protocol, input and reference hashes. Run each
native timing block sequentially with builds/tests paused. Report per-stage core,
process wall/CPU, peak RSS, inclusive scopes/counters, per-input p50/p95/max and
services exceeding the 100-ms input cadence. EOF is separate. FIFO delay is a model
of measured service under regular arrivals, not an actual live queue measurement.
Do not add overlapping inclusive scope times. Distinguish profiler perturbation
and host variation; these are repeated runs of one existing 20-s recording.

Keep exact identities and raw source/release documents local. Commit English docs,
tests, compact timing results and a reproducible isolated profiler. The user's
normal MongoDB Simulation database and normal live Simulator are not used here;
existing integration tests use their own UUID databases. A faster offline replay
is not proof of live end-to-end real-time operation, privacy effectiveness or
scalability over arbitrary densities, footprints and history lengths.
