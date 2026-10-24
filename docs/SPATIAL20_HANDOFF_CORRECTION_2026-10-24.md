# Spatial20 handoff correction and test report — 24 October 2026

## Scope and evidence status

The historical 32-case portfolio is preserved. This correction changes the
cell-local controller, not its metric thresholds, taxonomy, source observations,
publication model, or release trigger. Numerical comparison results below must
come from the separately frozen correction study, never overwrite the original
report. All 16 predeclared correction cases are now independently verified on
the complete frozen inputs. See the [full aggregate tables](verification/spatial20-correction-2026-10-24/report.md)
and [machine-readable evidence](verification/spatial20-correction-2026-10-24/aggregate-report.json).

## Suppression and baseline fairness

Selective type/contribution suppression was explicitly disabled in all 32
historical portfolio cases (`semantic_suppression_fraction.max = 0`). The earlier
six-case study enabled it separately. Whole-cell suppression of invalid windows
and semantic generalization were active in both adaptive and fixed methods.

Fixed grids use the shared evaluator and publication coordinator. They enforce
the same numeric root and intersecting regional bounds, including semantic
support, maximum loss, size, duration and age. They deliberately replace adaptive
execution order with a prescribed grid/window. Eleven new independent analytical
fixtures found no fixed-specific policy bypass. See the
[complete policy audit](SPATIAL20_POLICY_AUDIT_2026-10-24.md).

## Exact loss attribution

On the mixed recording, 32,453 observation contributions are retained by both
Semantic First and fixed 20 m / 400 ms, 9,105 only by fixed, and 3,887 only by
adaptive. The net fixed advantage is 5,218. Of the fixed-only losses, 8,226 are
retired at a coordination handoff. For 8,780 (96.4%), an independently recomputed
20 m parent passes every constraint on the exact interval of the failed adaptive
window, but current private ownership has different starts.

On the pedestrian-only recording, Spatial First and fixed 20 m / 1 s retain
58,980 in common, 9,173 only in fixed and 4,138 only in adaptive. The net fixed
advantage is 5,035. For 8,932 fixed-only contributions (97.4%), that same-interval
parent passes while starts differ. These counterfactual counts diagnose lost
options; they do not prove that an online schedule can recover every one without
sacrificing another valid release.

Valid fine publications can legitimately create different starts. For example,
parent 60 initially remains aligned; its child 241 publishes a valid 10 m interval
[14,800, 15,200), while another child still needs more support. That is a real
coordination tradeoff, not itself an implementation error.

## Confirmed implementation error

A subsequent scheduled handoff is supposed to resolve these different starts at
one bounded future boundary. The archived mixed run and a temporary historical
binary with diagnostic logging identify parent 60's requested boundary as
20,000 ms, requested at 19,600 ms.

One empty compressed owner, cell 3852, retires [19,500, 19,900). Its fresh successor
starts at 19,900 and has its next endpoint shortened to the handoff at 20,000.
Its temporal-extension counter is zero. A first new observation arrives at
19,900 and forces refinement into finer children.

Previously, `refineToDomain()` copied the scheduled endpoint only when the old
owner had at least one temporal extension. The fresh successor therefore lost
its shortened endpoint. Its children scheduled 20,300 = 19,900 + 400 ms instead.
They subsequently advanced on 20,300, 20,700, 21,100… while other owners used
20,000, 20,400, 20,800… . The rendezvous required all current starts to equal
20,000, so the skipped boundary could strand the plan indefinitely.

| State | Historical implementation | Corrected implementation |
| --- | --- | --- |
| Fresh owner start | 19,900 ms | 19,900 ms |
| Reserved handoff | 20,000 ms | 20,000 ms |
| Endpoint after refinement | 20,300 ms | 20,000 ms |
| Original source start and IDs | Preserved | Preserved |
| Policy bounds and publication checks | Shared evaluator | Same shared evaluator |

## Minimal correction

Refinement keeps the existing temporal-progress inheritance and additionally
caps every new child's endpoint at its actual active handoff boundary. This
preserves the reserved cut even for a fresh owner with zero extensions. The
child's independently computed hard deadline still applies. No window start is
reset, no previously published support is borrowed, and no threshold is weakened.

A broader first draft copied any earlier coarse endpoint. Adversarial review
found that unrelated disjoint regional minimum/maximum constraints could then
cause unnecessary premature evaluations and exhaust a child's budget. That
incomplete v1 trial was stopped and preserved. The final narrower correction
propagates the actual handoff only; it does not inherit an unrelated coarse
region's deadline. A separate regression covers this case.

For a newly refined child with scheduled endpoint `e_child` and an active,
nonredundant enclosing handoff `h`, the additional rule is simply
`e_child := min(e_child, h)`. Its start remains the original unpublished start.
Repeated refinement therefore preserves the same reserved boundary; the usual
assessment and successful-ACK transition still decide what may be released.

A coordination endpoint can be shorter than a regional minimum duration. This
only schedules an assessment: the ordinary hard evaluator still rejects an
undersized release. Existing explicit/automatic handoff rules, valid immediate
releases, immutable sink proposals and successful-ACK commit ordering are
unchanged.

More elaborate evidence-guided rendezvous ranking and recent-suffix recovery
were investigated but are not included in this correction. They would change the
algorithm's action space and deserve independent experiments after this concrete
bug is fixed.

## Measured correction results

These primary comparisons keep selective suppression **off** and use exactly
identical observation streams and policy bytes before/after the code change.
The fixed references are the best-retaining tested 20 m interval per source.

| Source / controller | Historical retention | Corrected retention | Best fixed 20 m reference | Historical → corrected full-input J |
| --- | ---: | ---: | ---: | ---: |
| Mixed / Semantic First | 44.299% | **63.956%** | 50.660% (400 ms) | 85.385% → **76.684%** |
| Mixed / Spatial First | 43.423% | **60.413%** | 50.660% (400 ms) | 85.583% → **77.466%** |
| Pedestrians / Semantic First | 67.876% | **77.889%** | 75.688% (1000 ms) | 62.079% → **57.073%** |
| Pedestrians / Spatial First | 70.096% | **76.211%** | 75.688% (1000 ms) | 63.739% → **60.681%** |

`J = (N_input - N_retained + sum_retained taxonomy_loss) / N_input` assigns
unit loss to every omitted contribution; lower is better. It is an experimental
utility score, not privacy risk. Semantic First beats the best tested fixed
reference on both retention and J in these two recordings. Pedestrian Spatial
First only narrowly beats fixed retention and has worse J than fixed 20 m / 1 s
(60.681% versus 58.102%). No universal adaptive or regional dominance is implied.

Mixed Semantic First now retains 5,993/8,149 contributions in the central region,
versus none previously. The west region improves from 0/4,034 to 1,691/4,034.
The named-region counts use original source-point membership; hard release
policies still resolve all intersecting regions over the entire output cell.
The correction auditor omits the outside cohort, so the aggregate report compares
only shared named cohorts and does not infer outside counts by subtraction.

Semantic First's retained mean delay is 319.9 ms (mixed) and 302.1 ms (pedestrians).
Fixed 400 ms has about 250 ms mean delay, while fixed 1 s has about 550 ms.
Spatial First still waits much longer: about 1,818 and 1,682 ms respectively.
The remaining delay is largely a declared execution preference, not evidence
that CPU time was added to the simulated timestamps.

Semantic First's measured core total falls from 58.05 to 33.21 s on the mixed
300 s stream and from 42.62 to 31.33 s on the pedestrian stream. Fixed 20 m / 1 s
still costs only about 0.31–0.33 s core time. These are separate single-run
measurements; they do not establish per-step hard real-time guarantees or a
statistical runtime effect. Simulation/motion generation, Python audit and
rendering are outside the core timer.

The Original-contract controls are preserved: both mixed methods and pedestrian
Spatial First have unchanged scientific utility values. Pedestrian Semantic First
improves slightly (40.495% → 41.151%). Both corrected fixed OFF controls reproduce
every historical logical release and private retirement exactly.

## Separate selective-suppression sensitivity

ON grants at most 0.1 per effective candidate policy. It does **not** mean removing
10% of the recording. It is a separate policy change, equally available to the
fixed comparator, and is not used to explain the unchanged-policy repair.

| Source / method | OFF → ON retention | OFF → ON full-input J | Selectively omitted contributions |
| --- | ---: | ---: | ---: |
| Mixed / Semantic First | 63.956% → 64.448% | 76.684% → 75.279% | 191 / 82,033 |
| Mixed / Spatial First | 60.413% → 61.678% | 77.466% → 74.978% | 275 / 82,033 |
| Mixed / fixed 20 m / 1 s | 50.566% → 57.596% | 82.058% → 77.188% | 555 / 82,033 |
| Pedestrians / Semantic First | 77.889% → 77.872% | 57.073% → 56.972% | 15 / 90,045 |
| Pedestrians / Spatial First | 76.211% → 76.211% | 60.681% → 60.681% | 0 / 90,045 |
| Pedestrians / fixed 20 m / 1 s | 75.688% → 75.647% | 58.102% → 57.869% | 37 / 90,045 |

The filtering objective can intentionally sacrifice a few contributions for a
lower J. Mixed selective omissions are rider contributions; the pedestrian
omissions are senior-pedestrian contributions. Conditional averages must not
hide this class-specific loss. ON Spatial First has the lowest mixed J among
these corrected variants, but has a much longer delay than ON Semantic First.
All removed contributions are included in full-input loss and source accounting.

## Verification gates

A focused regression constructs a fresh compressed owner with zero extensions,
a shortened future handoff, then a first observation that causes refinement.
It checks that all new children preserve the boundary and original start, that
the entire domain reaches the common boundary, and that later processing
finishes with exact source accounting and no duplicated support. The case is repeated
with a controlled failed empty-prefix sink acknowledgement, followed by retry.
An independent raw-input audit checks complete accounting, disjoint retired
space-time scopes, truthful semantic unions and all selected hard bounds.

The same new assertion fails on the historical core with the specific lost
handoff-endpoint message. It passes on the corrected core. Existing coordination,
stress and semantic cell-local groups pass before the full comparison.
The semantic executable now has 19 groups, including both new counterexamples.

All simulator targets build. All 100 registered CTest groups have a passing latest
result. The first full run passed 97: two provenance-aware studies correctly
rejected a concurrent edit to the aggregate-report helper; the new correction
orchestrator test used the standard-library Python interpreter without PyYAML.
After source freezing and moving that test into the existing mapped-tool Python
environment, all three targeted reruns pass. The full-suite and rerun hashes,
per-group outcomes and explanations are preserved in
[`ctest-summary.json`](verification/spatial20-correction-2026-10-24/ctest-summary.json).
Optional individual Python checks still depend on their declared dependencies;
passing CTest groups do not imply every optional check ran.

Additional independent checks comprise eleven fresh analytical policy fixtures,
four diagnostic parser/join tests, aggregate-report consistency tests, all 16
native correction/filtering cases, and exact public/private equality for both
fixed OFF controls. The report and protocol test groups are registered in CTest.
No policy or native result was changed to make a failing scientific audit pass.
The maintained correction runner also loads its mapped comparison helper under a
unique module name, preventing a cached unrelated `run_comparison` from being
used accidentally. All eleven protocol checks, including this import-isolation
case, pass. This tooling hardening does not alter the completed native study;
its executed runner copy remains frozen in the local provenance directory.

## Correction study protocol

The case-selectable runner is
[`run_spatial20_correction.py`](../tools/evaluation/run_spatial20_correction.py).
Its protocol is written before execution with all 16 cases, exact commands,
source/configuration hashes, binary and maintained source copies, historical
references and explicit audit limits. It uses both complete frozen 300 s streams.

Eight primary cases cross two sources, unchanged Original/Spatial20 contracts,
and Semantic First/Spatial First. OFF configurations are byte-for-byte identical
to their historical counterparts. Six separately identified Spatial20 cases
allow selective suppression up to 0.1 for both adaptive strategies and fixed
20 m / 1 s. Two OFF fixed identity controls must reproduce every original logical
public release and private retirement. Generated movement and full native
results remain local under ignored `results/`.

Native subprocess timing ends before JSON parsing and independent audit. Every
new result must independently satisfy raw source accounting, strongest regional
bounds, semantic support/loss, complete coverage and disjoint retirement before
its summary can be marked verified. These measurements concern operational
policy compliance and utility; empirical privacy improvement remains a separate
study with its own threat model.

## Fresh reviewable replays

The new derived catalogs have seven Spatial20 variants per source: corrected
Semantic First and Spatial First OFF/ON, corrected fixed 20 m / 1 s OFF/ON, and
the frozen fixed 20 m / 400 ms OFF reference. Each result retains its actual policy
ID, hard requirements, provenance and selection contract. The full native evidence
remains separate; viewer packaging does not rerun or change the mechanism.

- [Corrected mixed replay](http://127.0.0.1:8795/)
- [Corrected pedestrian replay](http://127.0.0.1:8796/)

Both were checked in Chrome at 30 s, paused, with the corrected Semantic First
OFF result against the source's best-retaining fixed OFF reference. The current
motion panel shows 118 mixed tracks or 122 pedestrian tracks at distinct recorded
positions. Both grids, actual selected-cell policy inspectors and nonzero release
counts are visible. Every projection preserves every empty retirement, nonempty
window and public release; compact receipts are in
[`viewer-verification.json`](verification/spatial20-correction-2026-10-24/viewer-verification.json).
The historical viewers on ports 8793/8794 remain the original, pre-correction
results and must not be used to assess this fix.

Restart from the repository root if needed:

```sh
python3 tools/replay_viewer/serve.py --bundle results/spatial20-correction-replays-2026-10-24-v2/mixed-viewer --port 8795
python3 tools/replay_viewer/serve.py --bundle results/spatial20-correction-replays-2026-10-24-v2/pedestrians-viewer --port 8796
```

Run the two commands in separate terminals. No live simulator or MongoDB service
is required for these replays. Movement, full native results and browser screenshots
remain local; Git receives maintained sources/tests/docs and compact aggregate
JSON, exact policies and verification receipts only.
