# Replay inspection and local-policy checkpoint: verification report

Date: 2026-10-22. Repository: UMP-Simulator. The checkpoint accounts for the
162 previously uncommitted paths and adds inspectable road-user groups,
finest-leaf regional-policy fixtures and portable synthetic replay evidence.
The [checkpoint inventory](RESEARCH_CHECKPOINT_2026-10-22.md) separates previous
work from the additions. No normal Simulator run or production database reset
was used for this verification.

## Integrated build and regressions

```sh
cmake -S simulator -B simulator/build
cmake --build simulator/build -j 6
ctest --test-dir simulator/build --output-on-failure -j 4
```

The Release build completed, including Simulator, AggregationReplay and the
configured regression targets. After the final CLI correction, **60/60 CTest
entries passed**, zero failed, in **17.39 seconds** wall time. CTest entries
are suites/executables, not a count of individual assertions. Four optional
MongoDB integration entries ran against their isolated test databases; the
application's `Simulation` database was not cleared by this checkpoint.
The [complete final CTest output](verification/replay-local-policy-ctest-2026-10-22.log)
is retained. `git diff --check` and JavaScript syntax checks passed.

| Verification area | Evidence and result |
|---|---|
| Viewer model | 29 JavaScript cases pass: exact historical grouping, half-open boundaries, identity union, measured-empty/unavailable handling, explicit opt-in and seal/evaluation gating |
| Viewer server/interface | 26 Python methods pass: compatibility, accessible controls, HTTP allowlist, path/digest checks and bounded finite local-region metadata |
| Local-policy runner | Five methods execute six actual C++ calls; four policy/order variants, independent geometry/category audits, deliberate corruption and unavailable input are covered |
| Semantic release CLI | 17 methods pass; ten new actual CLI calls cover both TF/SF overrides, original invalid settings and preserved hard spatial bounds |
| Data helper | Five methods pass: exact deterministic bytes/copies, corruption, existing destinations, symlink ancestors, traversal and unexpected archive members |

The final reviewer found a small replay CLI issue: an explicit TF/SF override
retained the semantic-only secondary setting. The adapter now validates the
original execution contract first and removes only that inapplicable setting
when overriding the strategy. It preserves taxonomy and numeric thresholds.
A default local-policy replay with the rebuilt executable matches the frozen
scientific output exactly after removing runtime metadata. Historical results,
pre-execution/final manifests and the original study binary remain untouched.
The [post-study comparison record](verification/replay-cli-override-2026-10-22.json)
records both binary hashes.

## Local policy experiment

The [fixed protocol](LOCAL_LEAF_POLICY_PROTOCOL_2026-10-22.md) and
[full results](LOCAL_LEAF_POLICY_RESULTS_2026-10-22.md) describe four 2.5-m
patches affecting 16/4096 finest leaves. The deterministic analytical input
contains 20 identities and 380 observations; it is a mechanism fixture rather
than a new realistic simulator capture. Four production variants and one
repeat passed separate scalar and semantic audits. Across variants, 102 public
cells and 112 public semantic bins were independently reconstructed. All
source observations are accounted for in every result.

Uniform/local retention is 100%/75%. Intermediate Pedestrian release, a
2.5-m Cyclist merge, infeasible suppression, fine control cells and an empty
strict patch's effect on an intersecting parent are directly inspectable.
This is diagnostic evidence, not a claimed adaptive advantage or measured
privacy improvement.

The fixture exposes the existing shared-window limitation: the empty strict
patch's 600-ms time limit caps the whole semantic window. Unrelated valid
branches can wait until that deadline. The next algorithm gate is integration
of semantics with independent cell-local ownership/deadlines; the existing
unsupported-mode guard remains in place.

## Real-data-artifact and browser inspection

The portable [source-group verifier](../tools/replay_viewer/verify_source_groups.js)
passed on all 17 restored bundles / 165 variants, checking **555 sampled public
cells**. It independently scans raw XY/time observations and deduplicates
identities; it does not use the viewer's spatial-hit helper as its oracle.
It checks first/last cells of first/last nonempty releases, with duplicate
selections removed. This is a declared sample, not an exhaustive audit of every
historical cell. It also checks pre-seal and private-opt-in gates.

```sh
node tools/replay_viewer/verify_source_groups.js results/replay-data
```

Chrome inspection at 600 ms verified actual rendered controls, selected-cell
focus, published categories, same-window original type groups, region outlines
and failed support/size checks for the suppressed guard parent. Before the
first release, the cell selector is disabled and no private groups are shown.
The saved [browser preview](figures/local-policy-cell-inspection-2026-10-22.png)
compares cell 12480: exact Adult/Child Pedestrians under uniform requirements
and Pedestrian under the local requirement. Each panel labels its own source
interval: `[0,400)` versus `[0,600)`; unequal observation totals are expected.
Each private group table uses its own displayed interval, not the current
position sample.

## Repository data package

The [package documentation](REPLAY_DATA_PACKAGE.md) and
[manifest](../data/replay-studies/manifest.json) specify six deterministic
archives, 702 original files and **47,073,268 compressed bytes**. Full archive
and member verification passed on the repository copy. Full restoration
verified all 702 original hashes and 16 canonical input copies; all 17 viewer
bundles / 165 variants validate. A separate root invocation also validated the
restored local-policy bundle. These files work without the historical absolute
paths or MongoDB.

Package manifest SHA-256:
`c7fb0661292863e9013a44b878c75dc51e8fe0e36b46d476a1c6e7d28b93fdfe`.

The [package verification](../data/replay-studies/verification.json) and
[publication scan](../data/replay-studies/publication-scan.json) preserve the
scope. Credential patterns yielded zero findings across all 1,761,468,021
uncompressed archived bytes. This is a focused pattern scan, not a formal
confidentiality proof. All included road-user records are synthetic.

The approximately 29-GB ignored results tree remains local. Raw MongoDB exports,
compiled binaries, verbose query dumps and external paper content are excluded.
Hashes establish consistency with the supplied manifest, not independent
provenance or privacy. Previous attack studies were regression-tested through
their test suites; their large experiments were not rerun for this checkpoint.

## Remaining scope

The [four-step roadmap](TAXONOMY_POLICY_ROADMAP_2026-10-22.md) integrates cell
inspection and small numeric regional policies now. Modifier-based taxonomy
profiles, arbitrary/overlapping functional regions, regional attribute-forbidding
rules and realistic street/visit behavior remain separate future steps.
Operational category support is not, by itself, a completed k-anonymity model
or an attack-based/formal privacy guarantee. This checkpoint does not add a
new privacy claim, optimization benchmark or live online service.
