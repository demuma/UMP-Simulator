# Semantic release control: implementation, results and test report

Date: 2026-10-21. The requested Semantic First / Spatial First secondary mode
is implemented. New semantic execution publishes a complete legal cut at its
first eligible scheduled endpoint by default. Explicit preference waiting
remains available. [Contract](SEMANTIC_RELEASE_CONTROL.md),
[same-source protocol](SEMANTIC_RELEASE_PROTOCOL_2026-10-21.md),
[complete examples](../simulator/examples/semantic-release/README.md).

## Exact implemented behavior

```yaml
policy_tree:
  execution:
    strategy: semantic_first
    semantic_secondary_strategy: spatial_first
    release_trigger: policy_satisfied
```

Both secondary values are supported; omission chooses `temporal_first`.
Omission of the trigger now chooses `policy_satisfied` in the semantic
controller. At every scheduled endpoint, search zero and ascending positive
taxonomy loss ceilings over legal spatial proposals and immediately publish
the first complete hard-passing cut. An exact parent is therefore preferred
over generalized fine cells at that endpoint. Regional checks are never
replaced by a preference threshold.

With explicit `priority_satisfied`, Temporal secondary tries zero-loss spatial
merges before extending time; Spatial secondary tries zero-loss finest cells
and extends before merging. At the terminal boundary both consider all legal
spatial levels and remaining semantic tiers. Partial terminal fallback retains
the established ordering: most observations, lower actual maximum loss, finer
weighted side, deterministic IDs. This remains a bounded heuristic.

The immediate trigger overrides optional waiting and can make both secondary
orders equal. It is scoped to the semantic controller in this step;
nonsemantic TF/SF reference scheduling remains unchanged. The CLI permits
explicit historical trigger values on those reference modes for shared-policy
experiment compatibility; they do not redefine nonsemantic scheduling.

Private JSON and MongoDB diagnostics report the real secondary, trigger,
selected/actual loss, trial count and whether a complete policy-triggered cut
closed the window. Positive-ceiling search before the deadline is no longer
misreported as terminal fallback. A finest-only Spatial-secondary trial does
not falsely record a spatial-coarsening action. Recipient schema and trusted
publication checks remain unchanged.

## Independent windows: present capability and remaining gap

CellLocalAggregation already implements independent cell ownership/windows,
regional hard deadlines, same-start parent takeovers, future handoffs and
immutable spatially scoped publication for nonsemantic TF/SF. The latest
semantic experiments use common-window coordination because taxonomy-enabled
local execution is still explicitly rejected in configuration, coordinator
and publication preflight. This is an implementation integration gap, not a
mathematical requirement for shared windows.

The new default still requires a complete admissible cut for the common
coordination domain. It does not release valid neighbors individually while
another observed branch fails. The next algorithm gate is semantic-aware local
ownership/reservations and handoffs; simply removing the rejection could
reuse already published support or create inconsistent parent intervals.
No local-semantic capability is claimed here.

## Build and acceptance

- Complete existing CMake build passed, including Simulator, AggregationReplay,
  private MongoDB diagnostics and all regression targets.
- Final full CTest run: **58/58 passed in 62.84 s**, including four isolated
  MongoDB integration entries, the common/local coordination and stress suites,
  sensor/frame/playback, publication/recovery and all evaluation/viewer suites.
- New independent semantic-release suite: **15 methods, 33 actual C++ replay
  CLI executions**, zero failures/errors. It reconstructs semantic antichains,
  observation counts, distinct identity unions and loss directly from source
  observations; a scalar-only projection independently checks geometry,
  coverage, intervals and retirement. It does not reuse the old controller's
  decision-order oracle. A deliberate mutated bin is rejected by the auditor.
- Acceptance covers default early generalized release; exact parent over
  generalized fine; Temporal-secondary parent at 400 ms versus Spatial-secondary
  exact fine cells at 700 ms after arrivals; all three intermediate families at
  .5; hard semantic/mean/spatial/regional/age constraints; incomplete evidence;
  EOF; terminal-only partial release; determinism; malformed configuration and
  unsupported local semantic rejection. Existing native sink rollback/retry,
  reentrancy, source-retirement and persistence tests also pass.
- Historical examples, native semantic-first fixtures and comparison runners
  now explicitly request `priority_satisfied` where their expected waiting is
  intentional. Frozen studies and their executed binaries/sources are untouched.

Initial full verification passed 57 entries but caught one obsolete canonical
policy fingerprint assertion: the runner now includes an explicit historical
trigger. The fixture was migrated to assert that option separately and then
verify the original policy body and original SHA256 unchanged. An intermediate
fixture edit referenced an undefined local variable; this was corrected before
the final full passing run. Neither issue changed production metric thresholds.
The initial and final full logs are archived separately.

## Same-recording eight-configuration check

All eight runs reuse the byte-identical existing N=500 capture: 20 s, 80 m
square, 100-ms observations, seven maintained source profiles. Compare two
caps crossed with both secondary choices and both release triggers. Hard
support remains five per nonempty category, semantic maximum one, and maximum
duration/age four seconds. No new simulator run, source relabeling or MongoDB
access was needed for this check.

| Maximum side | Trigger | Secondary | Retained observations | Actual release durations | Weighted mean side | Weighted mean semantic loss | Weighted start age |
|---:|---|---|---:|---|---:|---:|---:|
| 5 m | policy satisfied | either | 49.26% | 5 x 4000 ms | 5.000 m | .9354 | 4000 ms |
| 5 m | priority satisfied | either | 49.26% | 5 x 4000 ms | 5.000 m | .9354 | 4000 ms |
| 40 m | policy satisfied | either | 100% | 50 x 400 ms | 32.639 m | .1732 | 400 ms |
| 40 m | priority satisfied | either | 100% | 5 x 4000 ms | 27.584 m | .2404 | 4000 ms |

At 40 m, the new default avoids waiting solely for semantic preference. In this
recording the longer wait also has higher mean category loss, while retaining
finer spatial cells. The controller prioritizes worst loss tiers and bounded
proposals; it does not optimize weighted mean loss over time. Waiting need not
improve that mean. These different intervals/cuts are not paired per-cell
semantic guarantees or an overall utility ranking.

At 5 m, the new trigger does not repair global completeness: every method still
waits to four seconds and retains 48838/99140 observations. This is an honest
remaining limitation. The two default secondary recipient streams compare
exactly equal at both caps, as expected from the declared override rule.

An independent second checker verified all **57 manifest hashes, eight outputs,
two runtime-only-normalized deterministic repeats, 2206 public cells and 4856
semantic bins**. All category counts/unions, antichains, support, geometry and
weighted summaries were rebuilt from raw input. Its checker and report are
archived in the verification directory. This is one captured realization,
not statistical replication, global optimality or a measured privacy gain.
No new occupancy-query or live latency result is claimed for this follow-up.

## Hierarchy and loss interpretation

The existing moving catalog already permits Adult/Child/Senior Pedestrian ->
Pedestrian and cyclist subtypes -> Cyclist -> Road User. Exact terminals have
cost 0, these family nodes .5, and the root 1. Mixed cuts preserve detailed
classes where possible while generalizing only other branches.

Maximum policy loss 1 permits the root; it does not force every bin to it.
Measured maximum 1 means at least one published positive-support bin reaches
that cost. Mean 1 means all positive-weight contributions have cost 1 in this
catalog. Root output loses road-user-type distinctions while retaining counts,
spatial support and time intervals. The declared costs are not fractions of
all information lost or empirical privacy risks.

The seven-profile motion capture contains only Adult E-Scooter Driver, mapped
to one exact terminal. The new controlled fixtures demonstrate adult/child
subclasses -> Scooter -> Road User, but do not create a Child Scooter behavior
profile in the simulator. Adding real scooter subprofiles and versioning their
production taxonomy remains separate from this algorithm test.

## Reproduction and artifacts

- Run the new suite: `ctest --test-dir simulator/build -R semantic_release_evaluation --output-on-failure`.
- Complete controlled policies/observations are in `simulator/examples/semantic-release`.
- The eight outputs, source, policies, summaries, frozen binary, commands and
  per-method scalar/semantic audits are in `results/semantic-release-2026-10-21`.
  The viewer bundle validates; use `tools/replay_viewer/serve.py --bundle results/semantic-release-2026-10-21 --port 8771` for optional private playback.
- `verification/` contains initial/final CTest logs, the independent 15-method
  gate with binary/test hashes, the separate artifact checker/report, examples
  acceptance, frozen-source/study preservation checks and the PDF-review
  source hash. The final study manifest freezes these added artifacts.
- The [Camera-ready review](CAMERA_READY_COMPARISON_2026-10-21.md) identifies the
  attachment as ALOG and distinguishes frequency RMSE/LDP from declared semantic
  loss. Its numbers are not a direct UMP loss/privacy ranking.
