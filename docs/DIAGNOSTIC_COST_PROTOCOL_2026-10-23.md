# Diagnostic cost and presentation evidence protocol

Date: 2026-10-23. Baseline: `9705eb8`.

Use the existing authenticated 20-second n500 moving recording and unchanged
local Semantic First / Temporal First secondary policy. Generate no new movement.
The isolated adapter must reproduce live clock calls: advance at t=0 and every
50 ms, advance before the 100-ms sample ingest, then the ingest's own advance;
finish at the exclusive end. Compare full logical outputs excluding runtime.
Do not infer equality with the old 100-ms-only adapter without checking it.

Measure BSON document construction, candidate/source/attempt cell construction,
JSON serialization, stream insertion, flush, diagnostic-only candidate evaluation,
selection copying/metadata, progress snapshots, core and in-memory publication.
Nested spans are inclusive and must not be added together. MongoDB is not part
of this paired adapter; earlier live publication timings remain separate evidence.
Record input, policy, production and instrumented source/binary hashes.

Run a full diagnostic baseline and an explicit diagnostic-disabled control before
choosing the production change. If disabling file diagnostics materially helps,
add an explicit opt-in configuration with the historical full output as default.
Required policy evaluation, publication checks/journal and renderer visualization
must remain intact. Do not skip clock calls or change controller decisions.
The final implementation must preserve full logical results under both modes and
preserve full diagnostic contents under the default mode. Use small schema/error
fixtures and complete existing CTest checks after implementation.

Run native timing sequentially without concurrent builds or tests. Keep detailed
artifacts outside Git and remove generated full outputs after securing compact
hashes, checks and numeric results. Preserve the existing input recording. No
optimization success or scenario advantage is assumed in advance.

Today's presentation output is a concrete 20-minute structure with a current
claim/evidence table and three planned regional scenarios using normal Regions
and Policy Trees. Clearly distinguish tested compliance/support from empirical
privacy, existing results from hypotheses and fixed baselines from an oracle.
Scenario implementation and privacy-effectiveness experiments follow this gate;
do not introduce a new movement generator or attack benchmark in this profiling step.
