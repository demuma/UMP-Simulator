# Native MongoDB empty-checkpoint optimization and test report — 2026-10-24

## Outcome

Complete source, recipient output and final private journal are preserved. The
normal empty-retirement path now makes one acknowledged journal insert instead
of two reads, one insert and one update. No private checkpoints are disabled.
The measured instrumented native process fell from 26.10–26.48 s to 21.80–22.08 s
for the same 180-s source (16.5% lower mean wall across two pairs). This is bounded
measurement evidence, not a hard realtime guarantee or a privacy improvement.
Compact measurements and equality hashes are in
[NATIVE_MONGO_OPTIMIZATION_RESULTS_2026-10-24.json](NATIVE_MONGO_OPTIMIZATION_RESULTS_2026-10-24.json).

## Preserved contract

Aggregation candidate/history queries remain in RAM. MongoDB reads are used for
publication intent/conflict checking, recipient acknowledgement reconciliation,
explicit recovery and later research export. They are not spatial-history rereads.

`PublicationStore::retireEmpty` accepts only a validated snapshot without released
cells. It builds the same final committed BSON as the former prepare/commit path
and inserts it under the same unique release ID, using the existing majority write
concern. Only an acknowledged insert permits the controller to retire its held
scope. No public empty record is inserted. Duplicate/ambiguous inserts read and
compare full durable content; mismatch throws PublicationConflict, absence throws
without retiring the reservation. An identical legacy prepared empty record uses
the existing conditional commit path. The nonempty prepare/publish/commit path,
policy checks, source, taxonomy, counts, release timing and journal schema remain
unchanged. No cache of assumed database state or weaker write concern is added.

The pre-existing `journal_empty_retirements:false` option remains explicit and is
**not used** in these runs. Automatic simulator/controller restart remains outside
the contract. Read-only recovery of durable entries is preserved; this change does
not implement an automatic restart mechanism.

## Measurement design

Two sequential before/after pairs use the frozen 64-person corridor source:
80 visible episodes including 16 modeled visits, 80 x 80 m, D6, native 50-ms steps,
10-Hz AGBS, 180-s horizon, the same regional policy and semantic strategy, diagnostics
off, headless, full empty journaling. They reproduce 47,706 input contributions.
Fresh UUID-owned local databases avoid overwriting any existing data. Absolute UTC
origin is fixed for equality checking; private run IDs are freshly generated.
No other benchmark or build runs concurrently with these native measurements.

The isolated Release overlay records per-operation steady-clock spans. Inclusive
scopes overlap; individual DB operations may be summed, but not again with their
parent publication/terminal/step scopes. Process wall includes initialization and
buffered instrumentation flush, excludes the subsequent independent export/audit.
Instrumentation adds overhead and changes event counts. Two pairs cannot quantify
all server/scheduler variability; before/after operation latencies differ visibly.

| Quantity | Before pair 1 / 2 | After pair 1 / 2 |
|---|---:|---:|
| Native instrumented wall, s | 26.101 / 26.477 | 22.075 / 21.803 |
| Journal find calls | 94,721 / 94,721 | 1,527 / 1,527 |
| Journal insert calls | 47,106 / 47,106 | 47,106 / 47,106 |
| Journal update calls | 47,106 / 47,106 | 509 / 509 |
| Total measured journal DB time, s | 10.316 / 10.367 | 5.322 / 5.504 |
| Terminal callback time, s | 11.125 / 11.196 | 5.990 / 6.204 |
| Simulation-step p95, ms | 27.449 / 27.804 | 21.203 / 21.957 |
| Simulation-step p99, ms | 40.769 / 42.811 | 28.225 / 28.597 |
| Maximum step, ms | 56.668 / 57.302 | 48.949 / 51.315 |
| Steps above 50 ms | 9 / 11 | 0 / 1 |

All 46,597 empty checkpoints remain. The 509 nonempty releases retain their original
DB path. Exactly 139,791 journal operations disappear (74.0% of journal operations).
GT writes and raw sensor writes consume 0.86/0.81 s before and 1.60/1.61 s after;
they were not the dominant cost in this source. The measured path still has a
51.315-ms maximum step in one optimized run, and does not measure an external
application or a paced renderer. Do not claim a 50-ms end-to-end deadline from it.

## Correctness and tests

- Full configured CMake build and **82/82 CTest suites pass**, 16.12 s.
- Expanded real MongoDB regression checks direct committed state, identical retry
  through a newly constructed adapter (durable state after a lost response), exact
  conflict rejection, compatibility with existing prepare/commit calls, completion
  of legacy prepared empty records, nonempty rejection, byte budgets, malformed
  IDs and recovery coverage. No real server/network failure is injected.
- **13 profiling helper unit methods pass**, including checks that the equality
  normalizer cannot hide track, position, timestamp, journal-ID, state or payload
  differences. Instrumentation/build scripts pass Python compilation.
- Both verified pairs pass the maintained mapped export, lifecycle, source/sensor,
  policy, geometry, semantics, ownership and journal/recipient checks.
- In each pair all **95,605 GT/metadata/lifecycle documents**, **42,852 sensor
  documents**, **509 recipient releases** and **47,106 complete private journal
  documents** are equal. Only fresh raw BSON IDs, the run UUID including its
  release-ID embedding, and database cursor row order are normalized. Counts,
  identities, timestamps, positions, velocities, semantic bins and final states
  are retained. Normalized full-channel hashes agree between pairs as well.

An initial exploratory timing run used a UMP_Cost database prefix and was refused
by the exporter's UUID mapped-namespace guard. The runner was corrected to the
required UMP_Mapped namespace; the guard was not weakened. That exploratory run
is excluded from the verified measurements above.

## Reproduction and retained evidence

Use `tools/profiling/diagnostics/build_live_costs.py`, `run_mapped_costs.py` and
`compare_mapped_costs.py`; commands and scope rules are in the
[profiling README](../tools/profiling/diagnostics/README.md).
The builder explicitly disables timestamp test targets in its isolated source-only
project and records the base overlay/header hashes. Production test defaults remain
unchanged. The former source-only build included a newly added default-on test
whose test source was deliberately not copied; this build adapter is corrected.

Raw runs are local under `/private/tmp/ump-mongo-cost-*-20261024`, their fresh DBs
are retained, and the frozen input scene under ignored results/ is unchanged.
Only compact evidence, scripts, source, tests and English documentation enter Git.

Next runtime gate: distinguish remaining aggregation search/controller work from
source motion and measure dense input and actual paced delivery. Keep source and
policy fixed for each before/after pair. Independent building portals and modifier
source design are documented separately in
[the design note](BUILDING_ACCESS_AND_TAXONOMY_DESIGN_2026-10-24.md).
