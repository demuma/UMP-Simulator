# Moving replay implementation: test report

Date: 2026-10-21. Scope: configurable capture of the existing C++ simulator,
identical-input fixed/adaptive comparisons, independent released-data audits,
local interactive playback and presentation evidence. No motion/controller C++
algorithm, normal simulator configuration, new attack or ALOQ code was changed.

## Acceptance result

- **55/55 CTest entries passed**, 58.37 s wall time during concurrent pilot work.
  This is test execution time, not mechanism throughput or live service latency.
- Targeted Python: capture adapter 12 methods; moving comparison 14 methods; viewer 16
  methods. All 42 passed. The moving tests include 19 actual C++ replay executions
  on a tiny depth-6 fixture, not only mocks.
- JavaScript timeline model: 17 cases passed. Python server tests include real
  localhost HTTP requests and verify only allowlisted bundle files are served.
- Existing optional Python skips remain historical optional-dependency limitations;
  passing CTest does not mean every optional scientific plotting/attack test ran.
- Actual data: 3 independent real-simulator captures, 9 release methods each,
  **27 audited outputs plus 3 deterministic frozen-input repeats**. All captures
  completed with consistent GT/AGBS evidence; no resource failure occurred.
- All 27 outputs were reaudited with the final scalar/semantic validator. A second
  read-only reviewer checked 219 archived artifact hashes, input/policy/binary
  pairing, all repeats/retention and freshly reran all 27 semantic audits.

## Capture and provenance

The maintained temporal example is copied into a generated configuration with
one complete 80 m square AGBS footprint. Mixed capture copies the exact seven
existing behavior profiles after checking names/weights.200/500/1000 requested
initial populations were verified exactly; last sampled populations were
189/495/988. Each capture contains 400 GT frames and 199 sensor samples over 20 s.
Full rawGT and rawAGBS exports are preserved along with observation replay.

Only fresh UUID-owned capture databases were used; each verified owned database
was dropped after export. The maintained Simulation database was not targeted.
The generated configuration disables aggregation/rendering. Simulator/config.yaml
was read to copy behavior profiles and was not edited. No fixed generation seed
or wall-clock-dependent noise repair is implied.

Capture tests cover defaults/backward API, duration/population bounds, explicit
mixed profiles, source drift and initial-type counts, partial/incomplete/extinct
GT rejection, half-open spatial boundaries, duplicate/inconsistent cell records,
UTF-8 byte limits, bounded cursor export and no-overwrite database/artifact rules.
Large artifacts fail explicitly at 256 MiB; validation is bounded but still loads
raw arrays in memory. Arbitrary unlimited sessions are not supported.

The runner freezes the replay binary, source input, shared policy, predeclared
protocol, commands and validation helpers. The200-user run began before archive-
at-start and stricter schema/proof-digest checks were added: its exact original
runner was restored from unchanged staging for provenance, and all 27 outputs
were then independently reaudited using final validation. This is explicit in
its manifest. Actual result bytes were not rewritten by final verification.
Run orchestration from a repository checkout with docs/layout; archived sources
are evidence and are not a self-contained installed package.

## Mechanism and metric checks

The six fixed settings 10/20/40 m x 400/1000 ms and three adaptive priorities use
identical observations, taxonomy, semantic selector and numeric thresholds.
The independent scalar oracle reconstructs geometry, counts, identity unions,
coverage, policy bounds, nonoverlap, retirement and source accounting. Its
explicit semantic-strategy projection does not prove the priority order;
existing dedicated controller tests cover that order separately.

The new semantic audit reconstructs each published category from original
identity/type observations, checks stable source classes, integer counts,
complete nonoverlapping truthful antichains, exact category identity unions,
maximum/mean semantic loss and the original support/loss limits. Tampered
counts, duplicate/omitted/overlapping categories, summaries, catalog versions,
source hashes, geometry and hard constraints are rejected. It validates
published cuts, not optimality or all possible suppressed alternatives.

Occupancy uses only recipient releases for estimates, and frozen positions for
reference. Suppression is unknown. Uniform spatial allocation and constant
occupancy within each public block are explicit assumptions. Eventual outcomes
cover 1280 queries (64 cells x 20 intervals). Deadline primary outcomes cover 1152 queries
over [0,18 s); 128 boundary queries remain separate. These cohorts must not be mixed.
The total-occupancy workload does not measure class-specific query utility.

## Browser verification

Opened the 500-user bundle in Chrome at http://127.0.0.1:8765/. Verified actual
sampled positions, fixed 10 m/400 ms vs Semantic First at 4 s, cell bins/support/loss,
private constraint overlay, seek, 2x playback, EOF position clearing and historical
release labels. Corrected the paused button label when seeking back from EOF.
No synthetic interpolation, merge animation or future release was displayed.
The screenshot fallback is docs/figures/moving-replay-500-at4s-2026-10-21.jpg.

Viewer server validation covers source run/sensor/grid/cadence/horizon identity,
timestamps, bounds, unsupported cell-local snapshot streams, path traversal,
external symlinks, digest mismatch and restricted HTTP routes. Temporal model
cases cover sealing/evaluation gating, missing/unavailable vs measured-empty,
latest whole snapshots, event stepping and cumulative published accounting.
The viewer is private research tooling; recipient filtering does not sanitize
identity-bearing source files. It does not show every pending intermediate
candidate state and has no full-GT 50 ms movement mode.

## Evidence limits and next gate

This verifies the declared mechanism/tool contracts for the tested sources.
There is one stochastic realization per initial N, 20 s, uniform initialization,
common windows and uniform-root policy. No population-level significance,
formal privacy guarantee, measured privacy gain, end-to-end latency, globally
optimal schedule, exhaustive best-fixed frontier or ALOQ reproduction follows.
Regional/temporal heterogeneity, class-query utility and independent repetitions
are next experiments. Slide editing and a timed rehearsal remain to be done.

Artifacts: results/moving-replay-2026-10-21. Sources, commands, per-method audits,
summary JSON/CSV, public estimates, deadline cohorts, repeats and SHA256 manifests
are retained. Full test output: verification/ctest-last-test.log.
