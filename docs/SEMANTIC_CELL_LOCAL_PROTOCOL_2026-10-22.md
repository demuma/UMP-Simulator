# Semantic cell-local comparison protocol

Date: 2026-10-22. Frozen before execution of the new local-mode comparison.

## Question and controlled input

Does cell-local semantic coordination remove avoidable coupling between valid
control cells and a small region with a stricter time cap, while preserving
hard policy compliance, truthful categories and exactly-once source retirement?

Reuse `run_local_policy_replay.fixture()` byte-for-byte as a Python value:
20 persistent synthetic identities, 19 samples, 380 observations, 80 m square,
depth 6, 100-ms measurement cadence and a 2000-ms horizon. Positions vary only
by a few centimetres and some identities coincide. This analytical fixture
isolates mechanism behavior; it is not a realistic movement recording.

## Paired variants

Compare common-window and cell-local coordination under uniform and regional
policies, each with Semantic First / Temporal First secondary and Semantic
First / Spatial First secondary. All eight use the same input, category tree,
base 400-ms duration, maximum 1000-ms duration and age, and explicit
`policy_satisfied` release. Retain the existing four 2.5-m regional patches,
including the empty 600-ms guard; 16 of 4096 finest leaves are affected.

Do not change input density, taxonomy, support requirements or hard bounds in
response to the observed outcome. No favorable result or increased privacy is
assumed. Repeat all four cell-local variants and compare scientific outputs
excluding runtime.

## Independent checks and reported outcomes

Use the established independent scalar space-time oracle with semantic fields
projected out, preserving each local coordination scope. Reconstruct published
semantic bins, distinct identities, complete truthful antichains, declared
losses and regional bounds directly from the original input. Deliberate result
mutations must be rejected by the regression tests.

Report retained observations, suppressed/unavailable support, observation-
weighted interval-start age, observation-to-release delay, semantic loss,
output cell width and per-source-group ages/intervals. Local intervals cannot
be summed as a single global sequence. Preserve differences in empty-domain
retirement and forbid duplicate or missing source retirement.

The experiment tests the specified mechanism on an exact microcase, not
realistic traffic, general utility optimality, k-anonymity, attack resistance
or real network latency. The current common-window HTML viewer remains guarded
against asynchronous local results until a correct interval mosaic is added.

## Artifacts and repeatability

The runner writes to a new ignored `results/` directory, freezes the binary,
input, configurations and source hashes before execution, and records commands,
audits, compact summaries and final hashes. Generated observations and complete
release streams stay out of Git. Track only this protocol, implementation,
tests and compact result summaries/reports.
