# Policy filtering, isolated runtime and urban-source extension test report

Date: 2026-10-24. Repository: `/Users/maxdemu/Developer/UMP-Simulator`.
Status: implementation and regression gates passed; the dense isolated real-time gate **fails** and remains an explicit negative result. All documentation is English. Generated motion, full replays and private masks remain local and ignored.

## Scope and implemented behavior

1. **Policy-controlled contribution suppression.** `semantic_suppression_fraction.max` defaults to disabled. A bounded taxonomy-tier search may omit unsupported terminal contributions within one cell-window before accepting greater generalization. All retained policy checks must pass. A unit penalty for every removed observation prevents an improved conditional semantic mean obtained merely by deleting difficult data. Raw private ownership still retires the whole interval; recipient totals and semantic bins describe only retained contributions. Immutable publication, retry and actual MongoDB recovery remain consistent. See [contract/formulas/results](SEMANTIC_SUPPRESSION_2026-10-24.md).
2. **Isolated timing decomposition.** Optional minimal diagnostics omit private window JSON while keeping all policy/publication/retirement guards and exact public output. Complete typed SHA-256 retirement/release audits verify equivalence. Explicit incomplete failure telemetry preserves the completed prefix on queue overflow. This does not anonymize the research artifacts or provide a deadline guarantee. See [runtime report](URBAN_PACED_TEST_REPORT_2026-10-24.md).
3. **Map and traffic source.** A1/A2 use exact frozen OSM identities and typed surface portals; only two source-verified canopies become overhead context rather than ground walls. Synthetic independent station journeys respect the declared stair-profile exclusions. Optional rider-priority entry, finite pedestrian batches, off-apron staging and directed receiving-area checks preserve physical collision predicates. No occupied body is removed or teleported to break a wait cycle. See [implementation](SUBWAY_AND_CROSSING_PRIORITY_2026-10-24.md) and [source acceptance](SUBWAY_AND_PRIORITY_TEST_REPORT_2026-10-24.md).
4. **Reviewable replay.** Public geometry schemas validate surface access, roof metadata and crossing resources against native configuration and frozen provenance. Filtered variants warn that their totals are retained-population counts. Private diagnostics show input/retained/selectively omitted counts and the full-input score. Recipient cells reject private filtering fields. Incomplete future captures explicitly identify failed source completion in their title/provenance.

## Same-source suppression sensitivity

Six native executions use the same 60-second prefix containing **90,619 observation contributions**. No movement is regenerated. Separate Policy Tree/application IDs represent Semantic First, Spatial First and fixed 10 m / 1 s, each with cap zero or 0.10. The fixed baseline receives the same omission permission. Full-source/prefix/configuration/binary hashes are frozen before execution; all independent source/ownership/retained-policy audits pass.

| Method | Retention off → on | Conditional semantic loss off → on | Full-input distortion off → on | Core seconds off → on |
| --- | ---: | ---: | ---: | ---: |
| Semantic First | 65.77 → 66.37% | 70.18 → 69.57% | 80.39 → 79.80% | 63.844 → 67.062 |
| Spatial First | 55.01 → 55.42% | 66.39 → 65.24% | 81.51 → 80.74% | 57.827 → 59.781 |
| Fixed 10 m / 1 s | 55.40 → 56.22% | 72.06 → 70.96% | 84.52 → 83.67% | 0.374 → 0.485 |

Selective omissions are 50, 53 and 65 observations respectively. Semantic First retains 550 more observations overall while selectively omitting 50, because whole-footprint loss decreases by 600. E-scooter and cyclist retention can nevertheless fall. Mean retained cell side also worsens from 9.35 to 9.47 m for Semantic First. These changed retained populations must not be described as universal detail improvements.

These are single serial timing pairs including in-memory diagnostic construction; the measured overhead is not an isolated proposal-search cost. Adaptive methods may use up to four seconds while this fixed comparator chooses one second. The six cases do not replace the earlier wider fixed-window portfolio or prove a general advantage over the best fixed schedule. They demonstrate modest within-method action effects under operational policy bounds. They do not establish an attack-based privacy gain.

[Aggregate evidence](verification/semantic-suppression-2026-10-24.json), [presentation figure](figures/semantic-suppression-2026-10-24.svg).

## Isolated dense runtime result

The original 240-second frozen observation stream is offered at independent-clock 1×, 50 ms progress / 100 ms measurement cadence and queue capacity eight. Full audited unpaced processing takes 125.102 s; minimal takes 122.784 s. Private artifact volume falls 247.34 MB → 2.92 MB, but processing improves only 1.85%. Exact historical full payload and complete full/minimal logical decision audits agree.

About 98.72% of minimal consume time lies outside terminal callbacks, in the manager/history/coordination/selection call path. This is a measured broad component boundary, not attribution to one particular function. Minimal paced replay still overflows at logical 26.85 s. Its **528 completed-prefix events** have service p95/max 85.09/139.06 ms and scheduled response p95/max 234.79/505.42 ms. The remaining run is unmeasured. No successful complete paced output or deadline claim is made. Neural perception, detection-to-cell adaptation, external transport acknowledgement and source motion are excluded.

The next runtime work is targeted profiling and event/deadline-based avoidance of redundant checks, with complete decision equality. Merely changing the clock or increasing queue capacity is a separate experimental treatment.

## Accepted urban source and negative control

The original 128-person/150-ms priority attempt failed drainage and is preserved. A receiving-apron wait cycle was reproduced and corrected; focused tests also reject a global all-request staging barrier and overlapping inflated crossing resources.

The corrected same-source control finishes all 171 episodes by 180.85 s without priority and 190.40 s with priority. Both peak at 121 active tracks and finish with zero active/pending/stalled bodies and zero reported overlaps. These finite matched runs isolate the rule defect; the priority rule adds costs and does not universally improve throughput.

The final corrected native capture has 159,292 GT rows, 79,617 sensor contributions and 1,176 published cell-windows. Every one of the 171 configured visible-episode tokens is sensor-observed. Independent geometry/lifecycle analysis passes **6,111,306 body-pair and 6,111,306 swept-body pair checks**, all terminal sweeps and velocity checks. The minimum swept clearance margin is positive. A1 has five entries/five exits; A2 five entries/four exits. All 43 shop visits/returns complete, with at least eight-second hidden gaps. Only the three UUID-owned test databases were cleaned.

The final capture ran alongside validation tests, so its wall time is not an isolated performance comparison. The new source must receive fresh policy experiments before transferring results from the earlier frozen source.

## Verification performed

| Gate | Result |
| --- | --- |
| `cmake --build simulator/build -j 2` | Complete all-target build, exit 0 |
| `ctest --test-dir simulator/build --output-on-failure -j 1` | 95/95 groups pass, 413.89 s |
| Final filtered replay Python/JavaScript checks | 68 Python and 75 model checks; focused CTest 2/2 pass |
| Actual six-case bundle validation | Pass after retained-count consistency adaptation |
| Actual A1/A2 source bundle validation | Pass |
| Native semantic MongoDB integration | Lost-ACK/reconciliation, immutable retained payload and complete original retirement pass |
| Native source + independent recorded audit | Corrected 128-person/171-episode acceptance passes |
| Chrome inspection | Both local bundles load; moving 100-ms samples, readable A1/A2, six variants and filtered-count warning checked |
| `git diff --check` | Pass |

The final viewer adjustments were tested separately after the earlier viewer group in the complete suite. The combined build/CTest run is a correctness gate, not a performance benchmark. Raw detailed execution logs remain local.

## Reproduce and inspect

Use a Python environment with `tools/mapped_scene/requirements.txt` for source generation/audits. The viewer itself uses the standard library.

```sh
python tools/replay_viewer/serve.py --bundle results/urban-transit-priority-2026-10-24-v3/replay --port 8791
python tools/replay_viewer/serve.py --bundle results/semantic-suppression-2026-10-24-60s-v2 --port 8792
```

Both are private local research views. Large inputs/replays are intentionally absent from Git. Sources, tests, policies, reproducible tools, compact aggregate results and the scientific figure are included. Concurrent presentation edits and `output/` are outside this checkpoint.

## Explicit remaining boundaries

- Extend native mapped capture accounting before enabling filtering in that historical export path; it currently rejects the unsupported filtered-product proof. Native core/MongoDB publication and the separately audited offline study are supported.
- Benchmark the remaining controller path, repeat runtime measurements and rerun the bounded dense paced gate before claiming real-time operation.
- Evaluate additional seeds/scenarios, rare-type retention safeguards and original-traffic count bias. Current loss weights and support constraints are declared operational measures.
- Measure privacy with a defined protected unit, attacker and cross-release knowledge. Policy compliance and a lower semantic utility score alone do not establish stronger privacy.
