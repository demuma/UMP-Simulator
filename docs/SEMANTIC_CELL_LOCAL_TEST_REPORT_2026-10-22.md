# Semantic cell-local integration and replay inspection — test report

Date: 2026-10-22. Status: passed within the scope below.

## Outcome

Taxonomy-enabled TF/SF and Semantic First now work with the existing cell-local
ownership and handoff coordinator. A valid unrelated owner can publish without
waiting for a failing region's common interval. Current legal parent rescues
are considered before irreversible child publication. Every output still needs
to satisfy its hard regional requirements and complete semantic category cut.

The same analytical input retains 75% under both regional common/local modes,
with unchanged mean semantic loss and spatial detail. Independent control
cells release at 400 ms instead of the common mode's 600-ms first endpoint.
This demonstrates removal of a specific scheduling dependency, not general
utility optimality or a measured privacy gain.

Contracts: [implementation](SEMANTIC_CELL_LOCAL_CONTRACT_2026-10-22.md),
[predeclared experiment](SEMANTIC_CELL_LOCAL_PROTOCOL_2026-10-22.md),
[compact results](SEMANTIC_CELL_LOCAL_RESULTS_2026-10-22.json).

## Implementation and release rules

The existing constructor/configuration guards were replaced only after adding
semantic-aware selection and acceptance tests. The same immutable taxonomy
instance remains required by history, evaluator and publisher. No default
production configuration, sensor sampling or movement generator was changed.

`policy_satisfied` publishes eligible local owners after current endpoint
rescues; future-only holds of passing semantic owners are disabled. Failed
owners can extend independently. Semantic First compares increasing category
loss tiers for legal parents; equal loss preserves finer geometry. A current
parent rescue can consume a passing exact sibling when needed to retain the
complete failed footprint. Nested broader rescues can supersede narrower
improvements. This is a bounded local rule, not global mean-loss optimization.

`priority_satisfied` seeks zero loss before a local terminal boundary. Temporal
secondary permits an exact parent before waiting; Spatial secondary waits at
fine geometry. Hard deadlines and scheduled handoffs are terminal boundaries
for all affected owners. Explicit merge requests obey the same priority rules.
The semantic diagnostic `attempted_ceilings` counts ordered representation
tiers through the selected cost in local mode; it is not a measured number
of ancestor reconstructions or a runtime metric.

Only a complete unpublished frontier with a common actual start may merge.
Mixed depths are permitted; already retired intervals cannot re-enter a parent.
Retries preserve the transaction and reassess time-dependent eligibility.
Scoped MongoDB output uses outer `ump.release.v2` and the existing inner
`ump.semantic-release.v1`; scalar v1/v2 BSON remains byte-identical.

## Same-input comparison

Eight variants cross common/local coordination, uniform/regional requirements
and both semantic secondary priorities. Each uses 20 persistent identities,
19 samples, 380 contributions, 100-ms sampling, an 80-m square and depth 6.
The four regional patches cover 16 of 4096 finest leaves. These deliberately
stationary, partly coincident positions are analytical input, not an actual
Simulator movement recording. All four local variants were repeated exactly.

Both secondaries coincide under default immediate eligibility in this fixture.
The table therefore reports one row per policy/coordination pair.

| Measure | Uniform common | Uniform local | Regional common | Regional local |
|---|---:|---:|---:|---:|
| Retained observations | 380 / 380 | 380 / 380 | 285 / 380 | 285 / 380 |
| Mean category abstraction cost | 0 | 0 | 0.266667 | 0.266667 |
| Mean output side, m | 1.625 | 1.625 | 1.583333 | 1.583333 |
| Mean interval-start age, ms | 400 | 400 | 557.895 | 335.439 |
| Mean observation-to-release delay, ms | 242.105 | 242.105 | 315.789 | 209.825 |
| Public release documents | 5 | 35 | 4 | 31 |
| Public cell records | 35 | 35 | 16 | 31 |
| Private retired domains | 5 | 335 | 4 | 402 |

Means are weighted by retained observation contributions. Interval-start age
is `sealed_at - start`; observation delay is `sealed_at - observed_at`. They
are logical simulated times, not measured network latency. Fully suppressed
source groups remain explicit in the compact report with zero release and
undefined conditional delay.

The regional west/east controls retain all 76/57 observations and use
`[0,400), [400,800), ...` in local mode. Their mean delay falls from 315.789
to 242.105 ms. Both modes suppress all 57 infeasible scooter observations
and both 19-observation guard groups. Intermediate Pedestrian and Cyclist
categories remain available with cost 0.5; no released cell has cost 1.

**Base duration is not a hard minimum.** The 400-ms setting schedules an
owner's initial check. Current parent rescues also examine compatible owners
at other domains' evaluation endpoints. The spatial patch consequently has
some 100-ms local releases after its first 400-ms release. This is legal under
the frozen policy, which has duration maxima but no duration minimum. The
aggregate delay improvement is therefore partly due to this different interval
mix, not solely the controls' independent clocks. The extra release documents
and private retirements are a measurable cost. A future experiment should add
an explicit `window_duration_ms.min` when equal minimum duration is required;
this run was not tuned after observing its result.

## Verification evidence

- Full Release build succeeded. Final integrated `ctest --test-dir simulator/build
  --output-on-failure -j 4`: **62/62 entries passed in 17.54 s**, including four
  isolated MongoDB integration suites. The normal Simulator was not started;
  the `Simulation` database was not reset.
- **14 new native acceptance cases** cover independent clocks, no speculative
  hold, exact/intermediate parents, both secondary orders, manual merge rules,
  handoff pressure, current rescue of passing neighbors, regional bounds,
  moving-identity unions, incompatible retired starts, missing coverage,
  half-open boundaries, EOF, retry/expired retry, budgets and taxonomy identity.
- The same 14 cases passed isolated **ASan + UBSan**, with no diagnostics.
  Leak detection was disabled; this is not a leak-analysis claim. A compact
  compiler/options/source-hash record accompanies the results JSON.
- **Seven new Python integration methods** execute the actual C++ adapter,
  audit original observations and reject changed counts/schema, reused scopes
  and absent coordination scopes. Existing scalar and semantic tests pass.
- Independent audits passed for **234 public cells / 254 bins** across eight
  primary variants, plus four scientifically identical local repeats. The
  scalar oracle verifies complete, nonoverlapping space-time retirement;
  semantic checking reconstructs original identity unions, truthful antichains,
  losses and full-footprint regional constraints. This is not a validator for
  every possible unknown JSON field or an optimality proof.
- All four new common-window reference results equal the original October 22
  results outside runtime. All **56 frozen artifact hashes** in the new study
  manifest verify. No historical observation/result files were rewritten.
- Replay model/server regressions pass (**35 JS checks, 28 Python methods**),
  followed by real Chrome inspection of cell 12300. All six files in the
  existing 8772 bundle stayed byte-identical.
- The first integrated run caught one obsolete test expecting semantic local
  input to be rejected. It now checks an unknown coordination mode; positive
  local-mode tests are explicit. The final 62-entry run is fully green.

## Replay finding and correction

The current local-policy fixture has 20 IDs at each measured sample and 18
unique XY positions. The full-area display collapsed nearby markers into
roughly eight visual groups. Cell 12300 contains four different Adult
Pedestrians whose positions span about 17 cm. Each track changes position by
only a few centimetres, below a pixel at the full-area scale.

The old reference subtitle incorrectly described every input as a Simulator
capture. It now identifies the replay input and the explicitly declared
analytical fixture. **Reference viewport** can follow the selected A/B cell.
The display distinguishes full-sample IDs, exact XY positions and viewport
IDs, labels exact coincidences, and separates the current sample from the
historical aggregation interval. No jitter, interpolation or fabricated
positions were added. At 600 ms, cell 12300 visibly has four separate markers.

Browser proof was captured locally and kept outside the repository because it
contains generated positional observations. The selected cell and its four
markers were verified in Chrome; the observations themselves remain unchanged.

The earlier 500-user `1 s versus 4 s` replay was a different historical run.
Its Root-only cells genuinely had maximum/mean abstraction cost 1. A rare
under-supported branch forces the current complete-cut generalizer to a
shared ancestor. A policy maximum of 1 permits this result but does not force
it. No percentage-calculation correction was justified by that observation.

## Reproduction and remaining work

```sh
cmake --build simulator/build -j 4
ctest --test-dir simulator/build --output-on-failure -j 4
python3 -B tools/evaluation/run_semantic_local_policy.py \
  --output results/semantic-cell-local-new-run
```

The runner requires a fresh destination and does not call MongoDB. Full local
artifacts are under `results/semantic-cell-local-2026-10-22`, excluded from Git.
Only compact result summaries and source/tests/docs are tracked. The browser
proof image remains outside the repository. Frozen binary SHA-256:
`0ade9da4b2ca424420ec8d045484b59ba2fa022a6f643f13d02ff6dd4155143e`.
Study manifest SHA-256:
`8124fb27a9fae7db16a28d9b9d8f661dd998204d9d1d6cbeff5c268999637811`.

The HTML snapshot viewer still rejects cell-local streams. A correct
asynchronous interval mosaic is the next visual task; showing a single latest
global cut would misrepresent independently timed outputs. It is then useful
to repeat controlled comparisons on stored Simulator motion with local rules,
explicit duration minima where appropriate, different density/turnover and
strong fixed baselines. Broader taxonomy facets, realistic street/shop visits,
individual/type suppression, mean-loss optimization and new empirical privacy
attacks remain separate gates. Policy compliance is the demonstrated result;
privacy effectiveness still needs its defined protection objective and test.
