# Strategy, timing and local-policy test report — 25 October 2026

## Change and execution scope

This checkpoint adds four tested experiment tools, CTest registration, English
protocol/results documentation, aggregate evidence and scientific figures. It
changes no C++ mechanism, taxonomy, movement source or historical output. The
measured executable SHA-256 is
`72fc0aff452ee036d7dfdd8bd8ca7bd343c7462923ec00ccb39f904ee655502f`.
It contains the previously verified fresh-owner handoff correction.

Native measurements ran serially, without builds, simulations, renderers or
intentionally scheduled competing heavy jobs. Plots and the full regression
suite started after all native measurements and derived-baseline audits ended.
The source tree was not clean: the exact binary and relevant tool/controller/
policy files were fingerprinted. No source-to-binary reproducible-build claim
is implied. Unrelated presentation edits and untracked `output/` are excluded.

## Protocol tests

All four focused CTest groups pass, covering 51 Python test methods:

| Group | Methods | Checks |
| --- | ---: | --- |
| `run_strategy_window_extension_evaluation` | 10 | Complete 28-case matrix; unchanged hard policies; temporal naming; bounded native work; verified source/reference digests; failure and artifact-change rejection. |
| `run_temporal_region_study_evaluation` | 12 | Complete 44-case matrix; exact paired temporal-policy differences; identical within-policy hard requirements; all strategy/fixed variants; source conservation and mandatory audits. |
| `static_regional_schedule_evaluation` | 12 | Data-independent schedule; exact 4-s controls; complete empty/nonempty partition; duplicate/missing/private/public/count/semantic/coverage/source tampering; OFF-only bounds; changed binary and forged receipt rejection. |
| `run_current_paced_study_profiling` | 17 | Three exact sources; nine cases; historical input/policy identity; new dense independent audit; full/minimal/paced equality; bounded failure preservation; frozen successful rate/queue; prior-control hashes; separate protocol SHA receipt; after-run output/failure/summary tamper rejection. |

Independent review found and closed four measurement-integrity gaps before paced
protocol freeze: successful offered-load validation, prior-control artifact
rehashing, a separate prepare-time protocol receipt, and output/summary/failure
rehashing at final reporting. These are tooling fixes, not a change to engine
results or a rerun after observing a benchmark failure.

The complete **104/104-group CTest regression passes**, with no failures or
skips, in 308.62 s. It includes native timestamp/frame/sensor, history, metric,
policy, aggregation/coordination, publication, semantic, replay and mapped
source/drainage regressions. The [per-group receipt](verification/strategy-timing-local-policy-tests-2026-10-25.json)
records every duration and the exact source/binary hashes. Simulator and
evaluation/profiling tool sources remained fixed during the full regression.
Documentation figure label/format edits were rendered after regression
completion and visually checked; plotted data remain unchanged. Generated SVG
trailing whitespace is normalized; final XML parses and all PNG hashes match
the inspected images.

## Native and derived verification

- Phase 1: all **28 new native cases** pass independent input/geometry,
  retirement/coverage, truthful semantic support and hard-policy audits. The
  comparison also retains 32 verified historical/corrected aggregate references.
- Phase 2: all **nine invocations** are preserved. Six unpaced controls and two
  complete paced runs validate. The third paced case is a measured bounded FIFO
  overflow, not a completed run or a successful real-time gate.
- Phase 3: all **44 new native cases** pass independent accounting and public
  hard-policy checks. Complete structural policy differences are frozen before
  the first invocation; all methods receive the same policy within a condition.
- Derived controls: all **eight** policy-only static schedules pass independent
  raw-group support, semantic, coverage, publication and complete partition
  recomputation. Uniform controls reproduce native 4-s utility and cohort/delay
  accounting. They have no measured native runtime.

Every native utility audit explicitly permits at most one million cells/records;
none silently truncates verification. All 72 new utility cases have zero
published hard-policy violations. Compliance is reported jointly with retained
input and full-input distortion so suppression cannot masquerade as utility.

## Results that remain failures or limitations

The unchanged dense source still rejects logical 26,850 ms after 528 completed
progress events and queue depth eight. Its partial decision digests match the
older failed trial. No complete paced output, whole-run equivalence, complete
miss count or full-run privacy/accounting proof is claimed for cancellation.
It has 188/528 completed-prefix 50-ms response misses and 43/264 sensor-response
misses. Only completed events have completion latencies.

The two complete 300-s current streams have 122/64 misses at 50 ms, and zero
observed misses among 2999 sensor events each at 100 ms. Queue peak is one.
No hard real-time guarantee, external MongoDB/application delivery timing,
perception/inference timing or guarantee for a different policy/load follows.
Debug hashing and per-step in-memory serialization remain inside service.

The stronger regional baseline retains more pedestrian observations than the
adaptive method, at greater delay. Mixed data supports an adaptive advantage
against the declared uniform-space regional-window comparator. Neither result
establishes a global optimum, an optimal static comparator or attack resistance.
The policies are illustrative, sources are reused realizations, and J weights
are design choices. Retention is weighted by repeated observations, not unique
people. Sensitive attributes and application-specific attack-based privacy evidence
for these source/policy combinations remain open. Existing controlled synthetic
E02-A–C implementations/evidence are preserved; this study neither reruns nor
replaces them.

## Reproduction and retained artifacts

The [execution protocol](STRATEGY_TIMING_LOCAL_POLICY_PROTOCOL_2026-10-25.md)
and [results report](STRATEGY_TIMING_LOCAL_POLICY_RESULTS_2026-10-25.md) link the
four compact evidence packages. Each package has a SHA-256/size manifest. Source
observations, full native results, private audits and failure event telemetry
remain under ignored local `results/`; they are intentionally absent from Git.
Exact within-workspace replay therefore requires those locally retained frozen
source directories. The compact Git package alone does not contain the movement
streams needed to reproduce the numeric results.

The tools reject existing output directories. Use a fresh suffix rather than
overwriting a failed or completed study. The paced runner separately supports
prepare/resume without re-running cases with existing receipts. Its defaults
remain 1x rate, queue capacity eight, 50-ms progress and 100-ms input cadence.
All runners and this checkpoint use the configured Python environment with
`tools/mapped_scene/requirements.txt` dependencies.

```sh
ctest --test-dir simulator/build --output-on-failure -j 2
```

The aggregate figures are generated by
`docs/verification/plot_strategy_policy_results.py` with explicit strategy,
temporal-study and static-study summary paths. Exact plotted data and all input/
output/script hashes accompany PNG and SVG files. Visual QA inspects every
figure; no regression fit, interpolated data or derived runtime is shown.
