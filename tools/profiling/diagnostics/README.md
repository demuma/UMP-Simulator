# Production diagnostic cost measurements

These adapters compile copied Simulator sources outside the repository. They use
the retained, authenticated 20-second observation recording, the production
aggregation and policy cores, and the production diagnostic file sinks. They do
not generate new movements or connect to MongoDB. The diagnostic profile copies
the live sensor clock ordering: advance at 0 and every 50 ms, then ingest each
100-ms observation batch, whose own advance is retained.

Build a fresh isolated adapter:

```sh
python3 tools/profiling/diagnostics/build_diagnostic_profile.py --repo "$PWD" --output /private/tmp/ump-diagnostic-profile-build
```

Run each variant sequentially with no simultaneous builds or other benchmarks:

```sh
python3 tools/profiling/diagnostics/run_diagnostic_profile.py --repo "$PWD" --binary /private/tmp/ump-diagnostic-profile-build/build/DiagnosticReplay --output /private/tmp/ump-diagnostic-full --mode full --snapshots --protocol docs/DIAGNOSTIC_COST_PROTOCOL_2026-10-23.md
python3 tools/profiling/diagnostics/run_diagnostic_profile.py --repo "$PWD" --binary /private/tmp/ump-diagnostic-profile-build/build/DiagnosticReplay --output /private/tmp/ump-diagnostic-off --mode off --snapshots --protocol docs/DIAGNOSTIC_COST_PROTOCOL_2026-10-23.md
python3 tools/profiling/diagnostics/compare_diagnostic_profiles.py /private/tmp/ump-diagnostic-full /private/tmp/ump-diagnostic-off
```

The compiled adapter uses `readDiagnosticsConfiguration` when the production
source contains that API, and the same enabled-sink guards as Simulation. The
historical measurement-only `disabled` spelling remains accepted only to
reproduce the first control. It is not a production configuration value.
`--snapshots` enables the ordinary immutable renderer progress snapshot creation;
it does not open a renderer or measure drawing. Terminal selection snapshots and
publication metadata are retained in both variants.

The runner checks the frozen input hash and records protocol, policy, binary and
artifact hashes. Each build records all source and prepared-source hashes. Full
logical JSON must match after removing only its `runtime` field. A default-full
comparison across source versions additionally requires byte-identical candidate
and selection JSONL files; use `--require-diagnostics` for that check. Generated
UUID filenames are excluded from file matching; document contents are not.

The stage timings split selected/source/attempt BSON construction, total BSON,
JSON serialization, stream insertion and flush. Candidate-only metric evaluation,
selection copying, metadata and progress snapshots are separate spans. Selected,
source and attempt BSON spans are inside the BSON total, which is inside the
candidate/spatial diagnostic total. Terminal spans include publication, spatial
diagnostics and replay window serialization. Do not add overlapping spans.
Quantiles select the nearest zero-based index `round((n-1)*p)` with ties upward.
The explicit `measured_processing_scope` in each summary governs the measurement,
including the initial baseline whose inherited replay scope predated this adapter.

All full replay results, JSONL diagnostics and detailed timing traces remain
outside Git and should be deleted after comparisons and compact evidence are
secured. The retained user recording is never copied, overwritten or deleted.
The executable preloads that input and retains research outputs; its process
memory is not a bound on streaming aggregation memory.

For an actual live integration probe, `build_live_costs.py` builds an isolated
Simulator using the maintained live overlay plus finer diagnostic/publication
scopes. It records BSON and individual journal/recipient DB operation spans and
explicit sensor/renderer aggregation snapshot/overlay events. Use the maintained
`tools/profiling/live/run_live.py` with a fresh output directory, a 20-second
configuration and `--capture-seconds 20`; do not request `--export-capture`.
The harness verifies owned UUID databases and immutable recipient/journal equality,
then deletes those test databases. Renderer and headless live runs have independent
stochastic motion and cannot establish an equal-input speed difference.


## Matched native mapped I/O gate (October 24)

`build_live_costs.py` now explicitly disables timestamp test targets in its copied
production-only project, and hashes the base timing overlay/header as build inputs.
The production test configuration is unchanged. Run with the mapped-scene Python
requirements and a frozen, completed source scene (source data never enters Git):

```sh
python tools/profiling/diagnostics/run_mapped_costs.py --source-scene results/system-review-empty-origin64-2026-10-23/scene --binary /private/tmp/ump-mongo-cost-after-build-20261024/build/Simulator --output /private/tmp/ump-fresh-mapped-cost-run
python tools/profiling/diagnostics/compare_mapped_costs.py /private/tmp/ump-before /private/tmp/ump-after
```

Use fresh output paths. The runner copies the scene, fixes one common UTC origin,
uses fresh UUID `UMP_Mapped_` databases with clearing disabled, forces headless
execution and requires full empty-retirement journaling. It retains its own local
DBs and raw replay; there is no automatic cleanup. It verifies the exact 50-ms
source cadence, hashes configuration/executable, then invokes the normal mapped
source/publication verifier. Do not run another benchmark/build concurrently.
The comparator checks all GT/lifecycle, raw sensor, recipient and private journal
fields. Only fresh raw BSON IDs, the run UUID and database cursor row order are
normalized. Track IDs, timestamps, values and committed states are retained.

The summary's stage scopes are inclusive. Individual database calls are disjoint,
but must not be added to their enclosing terminal/publication/simulation scopes.
Process wall includes startup and instrumentation flush; it excludes the later
recording/export verifier. Instrumentation buffers events and affects runtime.
See the [report](../../../docs/NATIVE_MONGO_OPTIMIZATION_REPORT_2026-10-24.md) for
measured bounds and the preserved durability contract.
