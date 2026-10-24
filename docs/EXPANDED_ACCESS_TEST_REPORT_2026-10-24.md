# Expanded map access and replay verification — 24 October 2026

## Outcome and scope

The maintained Simulator now has an opt-in, source-bound six-shop scenario with both A1/A2 subway surface accesses. Two new 300 s native captures, one mixed and one pedestrian-only, passed capture verification, complete scheduled-episode sensor observability, and an independent audit of all stored positions and motion sweeps. All six shop destinations were actually entered and exited in both captures.

The replay fixes address the reported white label spikes, subway marker shape and typography, clipped access references, and missing modeled shop destinations. These changes do not establish a privacy gain, adaptive-method superiority, calibrated pedestrian behavior, or a hard real-time guarantee. The comparison portfolio and its separate capacity/analysis limits belong to the portfolio report; this report contains no portfolio performance conclusions.

This extension changes Python source construction, verification, and the browser renderer. Both captures used the same existing native executable. No new native Simulator algorithm or movement binary was substituted for these runs.

## Visual correction

The map-name renderer previously used a 3 px white `strokeText` halo with Canvas's default miter joins. Small sharp glyph joins can therefore create elongated white points. The collision-packing code also drew leader lines from a supplied map-name position to a displaced label. The renderer now uses a 2 px halo with rounded joins and a bounded miter limit, and geographic labels no longer draw those leader lines. The supplied shop and street names retain their ordinary 10 px typography and remain separate from entrance-debug overlays.

Every entrance target now uses the same diamond with a 6 px center-to-tip distance. Synthetic shop targets retain orange styling; OSM and subway targets use blue. This is a screen-space symbol convention, not a physical radius or enlargement of the admission region. The separately rendered entrance stroke continues to represent the configured physical width.

A1/A2 references use the normal 10 px map font. Their labels sit close to the exact access target, switch to the opposite side when needed, and remain fully inside the current viewport. Label packing reserves those reference bounds, and a duplicate supplied `A1`/`A2` map label is not drawn over the entrance reference. A focused cell does not gain a floating reference label for a subway access outside that cell. The legend now says “OSM entrance · diamond” for existing and newly generated replays; pixel shape is a renderer convention and did not require rewriting frozen map artifacts.

Browser QA on the fresh mixed replay at `http://127.0.0.1:8793/` confirmed visible A1/A2, the café and Konzertkasse destinations, readable labels, and the corrected diamonds. At the inspected 30 s sample, the UI displayed 118 current visible IDs at 118 distinct XY coordinates. This is one sampled instant, not the full population or a density statistic. A local QA screenshot was retained at `/tmp/ump-expanded-access-2026-10-24.jpg`; it is not a Git dataset.

## Six shop destinations and map provenance

The existing four southern destinations remain Apollo, Ditsch, Adidas Originals, and H&M HOME. The optional `--expanded-shop-access` source adds Elbphilharmonie Kultur Café Starbucks and Konzertkasse Mönckebergstraße. All remain inside their original OSM building footprints; short storefront dividers do not assert surveyed interior partitions.

The café main target is the exact frozen OSM entrance node `9370793427`, version 2, timestamp `2023-07-22T18:14:47Z`, at `(35.24755586031824, 28.583821195177734)` m. The OSM entrance location is source evidence. Its association with the named tenant is explicitly modeled. The Konzertkasse target is a separate synthetic projection onto an original reachable facade at approximately `(42.0313052462705, 32.171902054135664)` m. It is not labeled as a verified OSM tenant door.

The frozen derived walking surface is about 5.70 m from the café main door. The source therefore declares a separate three-meter-wide synthetic exterior approach, bound to that portal. Its three-vertex centerline is approximately 7.58 m long, and its clipped surface area is 22.4808706059 m². This approach fills a missing modeled walking connection; its width and use are not asserted to have been surveyed by OSM. It creates no additional hole through a building. Only the existing, explicitly referenced 1.2 m door throat permits the circular body to overlap the facade at entry/exit.

Mö Grill remains accounted for as a POI under the A1 canopy, without an invented enclosing ground-level shop facade. Other source doors without a verified ground connection or defensible tenant association remain documented exclusions. See [the source-access design note](EXPANDED_SHOP_ACCESS_2026-10-24.md) for the complete inventory and exclusions.

The independent `validate_source_access.py` verifier checks the frozen source hash; source entrance node, version, timestamp and exact location; original building wall and storefront frontage; the hash-bound tenant POI label and position; and the bounded synthetic connector. The connector must start at its declared source door, remain a simple polyline no longer than 12 m with width between 1.2 and 4 m, avoid building interiors, and terminate in original walking geometry with full declared body clearance. The generated three-meter approach satisfies these checks. The exact café point cannot be replaced by an arbitrary synthetic override.

## Native source captures

Both captures use an 80 × 80 m area, D6 spatial discretization, 50 ms numerical steps, 100 ms sensor sampling, seed `20261024`, a 150 ms configured arrival interval, and a 300 s source horizon. The finite cohort contains 128 people in each source; indoor reappearance creates another visible episode with a fresh track ID. A cohort size, a visible episode count, and the number simultaneously visible are different quantities.

| Source property | Mixed | Pedestrian-only |
| --- | ---: | ---: |
| People in finite cohort | 128 | 128 |
| Scheduled/completed visible episodes | 171 / 171 | 183 / 183 |
| Sensor-observed episode IDs | 171 | 183 |
| Missing/unexpected sensor episode IDs | 0 / 0 | 0 / 0 |
| Stored native GT rows | 164,137 | 180,157 |
| Measured sensor samples | 2,999 | 2,999 |
| Input observation contributions | 82,033 | 90,045 |
| Active/pending episodes at horizon | 0 / 0 | 0 / 0 |
| Shop destinations / station accesses | 6 / 2 | 6 / 2 |
| Rider-priority coordination | Enabled | Disabled |
| Native process wall time | 99.281 s | 108.416 s |

Native process wall times include startup, source motion, aggregation and database I/O. They are neither an isolated aggregator benchmark nor evidence of per-step deadline compliance.

The mixed cohort contains 22 Adult Pedestrians, 23 Child Pedestrians, 22 Senior Pedestrians, 21 Pedestrians With Mobility Aid, 14 Pedestrians With Stroller, 9 Adult Cyclists, 9 Senior Cyclists, and 8 Adult E-Scooter Drivers. The pedestrian-only cohort contains 32 Adult Pedestrians and 24 of each of the other four pedestrian profiles. It generates no rider trips. Stroller and mobility-aid profiles remain present; the station stairs still accept only the explicitly eligible pedestrian profiles.

The pedestrian-only source is separately generated. Composition, routes, visits, and resulting observation volume change, so the two captures are not identical-motion counterfactuals. Comparisons between policies within either saved observation stream can share exactly the same recorded input.

### Observed portal use

| Destination | Mixed completed entries / exits | Pedestrian-only completed entries / exits |
| --- | ---: | ---: |
| Apollo | 8 / 8 | 10 / 10 |
| Ditsch | 7 / 7 | 9 / 9 |
| Adidas Originals | 7 / 7 | 9 / 9 |
| H&M HOME | 7 / 7 | 9 / 9 |
| Elbphilharmonie Kultur Café Starbucks | 7 / 7 | 9 / 9 |
| Konzertkasse Mönckebergstraße | 7 / 7 | 9 / 9 |
| A1 station surface access | 5 / 5 | 5 / 5 |
| A2 station surface access | 5 / 4 | 5 / 4 |

The station trips are independent seeded arrivals/departures, rather than paired indoor shop returns. A2's different arrival and departure totals therefore do not indicate a missing configured episode. All scheduled episodes completed. Shop hidden dwell gaps were at least 8,000 ms, and returning shop episodes began at the same declared shop entrance with a new visible ID.

## Independent physical audit

The audit uses all stored native source frames, rather than only the coarser sensor samples. It checks each body's position and swept area against independently reconstructed physical surfaces and buildings. Explicit approach connectors extend walking surface only. Wall exceptions remain specific to a track's own declared door, so another shop entrance cannot silently authorize a wall crossing.

| Audit quantity | Mixed | Pedestrian-only |
| --- | ---: | ---: |
| Overall independent audit | Pass | Pass |
| Pairwise static body checks | 6,571,276 | 7,587,213 |
| Pairwise swept body checks | 6,571,276 | 7,587,213 |
| Checked motion segments | 164,137 | 180,157 |
| Checked terminal segments | 171 | 183 |
| Static body/surface checks | 164,137 | 180,157 |
| Speed/velocity consistency checks | 163,966 | 179,974 |
| Minimum swept clearance margin | 0.000025603 m | 0.0000073255 m |
| Maximum velocity consistency error | 0.000198419 m/s | 0.000211578 m/s |
| Compatible boundary endpoint checks | 237 | 237 |
| All planned portal entries completed | Yes | Yes |
| Independently authenticated expanded source access | Pass | Pass |

The mixed source reports a maximum consecutive stop of 8,400 ms and a maximum crossing-pedestrian wait of 20,650 ms; the pedestrian-only source reports 450 ms and 0 ms respectively. The crossing fairness threshold starts bounded admission coordination but does not establish an 8 s end-to-end waiting guarantee while conflicting motion drains. These counters should remain visible when judging the scenario.

Positive clearance margins apply to the modeled circular bodies and linearly evaluated source-step motion in these stored runs. They do not establish general collision avoidance or queue liveness for arbitrary seeds, larger populations, or changed geometry. Motion can deviate substantially from its original guide because local steering and replanning are active; the audit validates actual geometry and sweeps rather than requiring every position to remain on the guide line.

## Defects caught and corrected during integration

The pedestrian-only export initially failed strict public-schema validation. Its road intervals correctly had `spawn_supported=false`, but retained the truthful provenance that they had originally been constructed on body-safe carriageway geometry. The validator incorrectly inferred construction provenance solely from current source eligibility.

The correction permits that exact synthetic road construction provenance on a context-only road interval while still requiring road mode and an explicit road navigation space. It continues to reject walking/cycling misuse, missing or wrongly typed road spaces, unknown provenance, and an active road source mislabeled as a generic derived boundary. The captured public artifact was not rewritten, the simulation did not need to rerun, and export resumed against the retained recording.

A separate sensor-observability proof now compares configured visible-episode tokens with all in-coverage sensor-cadence observations. Lifecycle completion alone is insufficient: a genuine 50 ms episode can have complete GT and both lifecycle boundaries yet occur entirely before the first 100 ms measurement. A regression fixture verifies that this case reports observability `fail` with one missing episode, without inventing measurements. An all-observed fixture reports `pass`; a legacy capture without configured people omits the new claim. Both new native captures pass the observability gate.

## Focused test results

The current work passed 343 individual tests/checks across the following groups, with four explicitly skipped optional native fixture tests. These counts are individual checks, not CTest test-group counts. The previously reported 95-group CTest result belongs to earlier work and is not presented as a fresh complete CTest run here.

| Test group | Passed | Skipped | Main assertions |
| --- | ---: | ---: | --- |
| Replay JavaScript model/Canvas checks | 78 | 0 | Rounded text halos, no debug leaders, equal diamond geometry, A1/A2 edge placement, duplicate-reference prevention, off-viewport labels, unchanged replay timing and accounting behavior |
| Replay public schema and HTTP checks | 73 | 0 | Closed public metadata, source entrance fields, bounded connector geometry, private-field rejection, disabled-road context provenance, allowlisted serving |
| Native recording/export checks | 55 | 0 | Native/public portal agreement, frozen source authentication, altered source/tenant/connector rejection, observability pass/fail/legacy behavior, original capture protections |
| Independent body/source audit checks | 19 | 0 | Actual source evidence, bounded safe walking gaps, no connector wall holes, actual/swept body checks, lifecycle and velocity constraints |
| Storefront/router checks | 26 | 0 | Expanded destinations, exact café entrance, unchanged defaults, body-safe approaches, two-way visits, pedestrian-only cohort and source constraints |
| Mapped builder/CLI checks | 30 | 4 | Source flags, incompatible-option rejection, forwarding, separate cache entries, source geometry and defaults |
| Comparison and plotting checks | 40 | 0 | Predeclared policy cases, bounded query protocol, source immutability, native two-second contract fixture, explicit missing/NA values, aggregate plotting provenance |
| Suppression audit and study checks | 12 | 0 | Bounded capacity, complete checking of 200,004 legitimate retirements, late corruption detection beyond the old 200,000-entry cap, unchanged default limits and existing selective-suppression checks |
| Compact viewer projection checks | 10 | 0 | Every empty retirement preserved, complete nonempty diagnostics and releases unchanged, actual JavaScript boundary/reverse-seek equivalence, source hashes, path isolation and failed-output cleanup |
| Total | 343 | 4 | |

The four builder skips are opt-in native fixture gates requiring `UMP_MAPPED_CORE_TEST_BINARY`: corridor, multi-building, storefront, and urban finite-source drain fixtures. They are not counted as passes. The two new full native captures and independent audits above provide separately recorded integration evidence; they do not silently substitute for skipped fixture coverage.

The JavaScript suite executes the shipped renderer against a stateful Canvas recording context. It checks the actual drawing commands and paint styles instead of reproducing the layout algorithm. Source-access tests also exercise the actual generated six-shop context against independent frozen-map checks. `git diff --check` passed. After reconfiguration, `mapped_plot_spatial_portfolio_tools` and `replay_viewer_compact_projection` pass 2/2 selected CTest groups, executing their four plotting and ten projection tests; those checks are already included above and are not counted twice. No movement export or generated replay was added to Git.

Representative focused invocations, with the maintained mapped-scene Python environment, are:

```sh
node tools/replay_viewer/test_model.js
python -m unittest discover -s tools/replay_viewer -p test_viewer.py
python -m unittest discover -s tools/mapped_scene -p test_export_replay.py
python -m unittest discover -s tools/mapped_scene -p test_audit_building_access.py
python -m unittest discover -s tools/mapped_scene -p test_storefront_router.py
python -m unittest discover -s tools/mapped_scene -p test_build_mapped_scene.py
```

The comparison contract suite additionally enables its maintained native replay fixture with `UMP_REPLAY_BINARY`; those tests and plotting checks do not establish a completed portfolio evaluation on the new 300 s sources.

## Derived viewer packaging

Full native comparison results can contain hundreds of thousands of private empty
retirements. Loading all sixteen verbose results eagerly is inappropriate for a
browser. `tools/replay_viewer/compact_bundle.py` creates a fresh, self-contained
derived viewer directory after the complete comparison is independently verified.
The original bundle, native results, policies, audits and summary remain unchanged.

The projection retains **every window in exactly the same order**, including
empty local scopes that clear old private footprints. Nonempty windows, every
cell/check, every public release and all other result fields remain logically
identical. Only empty-window metadata unused by the renderer is removed; interval,
evaluation time, coordination geometry, completion reason and supplied policy
identity remain. Each variant records original/derived hashes, byte sizes, counts
and removed field names. Shared map and observation files remain byte-identical.

The tool requires matching verified summary/native/configuration/manifest hashes
before writing and validates the derived result structurally. Its JavaScript
regression compares recipient and private mosaics, event navigation, counters,
source groups and identities at event boundaries and reverse seeks, including an
empty retirement clearing a suppressed footprint. Dropping empty windows is
explicitly excluded because it would leave stale private data visible. This is a
display projection, not another experiment or an independent policy audit.

Final browser acceptance passes for both full 16-variant derived bundles at
`http://127.0.0.1:8793/` and `http://127.0.0.1:8794/`. Mixed at 30 s displays
118 current IDs / 118 distinct XY; pedestrian-only displays 122 / 122 with all
five pedestrian profiles. Actual switches to Spatial20 Semantic First and fixed
20 m / 0.4 s or 1 s show the executed results. The mixed original-policy 20 m
control correctly displays no releases. Both private mosaics clear to zero
footprints at the 300 s horizon, including after forward seeks. Public mode and
30 s views were restored for handoff.

Derived declared artifacts are 652.14 MiB mixed and 517.52 MiB pedestrian-only,
versus 1,491.09 and 1,129.33 MiB in the full comparison bundles. Every 1,041,258
mixed and 642,551 pedestrian private window remains. The result payload alone
is 641.12 / 505.44 MiB, so these are still substantial local research viewers.
Cold loading and whole-history private seeks can take seconds; this does not
establish smooth private playback or a small browser-memory bound. The public
view responded promptly in the acceptance session. Further lazy loading/indexed
private rendering is deferred. The [packaging receipt](verification/spatial-portfolio-viewers-2026-10-24.json)
records every original/derived digest and count. Cropped screenshots are local at
`/tmp/ump-spatial-portfolio-map-2026-10-24.jpg` and
`/tmp/ump-spatial-portfolio-pedestrians-2026-10-24.jpg` and are excluded from Git.

## Reproducibility and artifact identities

Local mixed artifacts are under `results/expanded-access-mixed-2026-10-24-v1/`; pedestrian-only artifacts are under `results/expanded-access-pedestrians-2026-10-24-v1/`. Each contains `scene/`, `replay/capture-proof.json`, and `physical-audit.json`. Raw GT, observations, sampled motion, private configuration and browser replays remain local and ignored by Git. Compact implementation documentation may be committed.

Shared source identities:

```text
Frozen geometry SHA-256:
afa2690e408f467af5ff679770bf872816cc568714d9171cf4efb493809e40ed
Frozen POI label evidence SHA-256:
20c8054effb92f10843e8ff6c70675f888fd6bec301ef3cf607aacee1e3b4333
Unchanged native executable SHA-256 (both captures):
4d69a20892fc7806e902793de27e133af0cd28893e8d2219da6f8275fb5e5204
Shared rendered background SHA-256:
9c7f84be4af893f63d27fa6de235b846259cf14deffc0e4e9b114343274e972b
```

Mixed capture:

```text
scene/config.yaml:
238a1ea92f6766c78197dcf395745f4ff494555895465d2a5ed57f9f4aa9b32b
scene/building_access.json:
34d3ad3cb91dbd53900427f13099a7aa47eb4547d21eeba1294e8fdcd3d32597
replay/capture-proof.json:
eba903f5cf22ad97083cee0735b2397e78fece8dda4f8b7e45274840b5265640
physical-audit.json:
705ad28045853dbb1bbd89f20d67f70498ab4563bc038cc4d27b2ba3124ac82e
replay/observations.json:
c24134c724acf2df38a85b2906a2e80f8de7b420529a4b8cda3f9e5f98a3eff5
```

Pedestrian-only capture:

```text
scene/config.yaml:
2e9b2887bcf9bb9776a257ad87e083391747a95d3c1825899e5d0c38c0013651
scene/building_access.json:
595401118bd4fed1fb408fc39c262f9a70fb503da1394e6bfc97131310fce8d0
replay/capture-proof.json:
2652ab50a75730c79e8c8d99ba62c78cc1fce49b57541f6f907a260727daa3f0
physical-audit.json:
c8151ac866ca47a4a02826629ef28ccaca3d2c6c2a98ef9e5bf89d57f831af31
replay/observations.json:
4abf12b390f29ce6685d37cbe5167793ed62dfc5c9207ffc42688e7419af5b5a
```

Remaining limits include synthetic visitor demand and tenant assignment, simplified physical surfaces, circular-body local navigation, incomplete infrastructure semantics, and the absence of a new empirical privacy claim. Successful construction, complete visits, sensor visibility, and recorded-run collision checks are the acceptance evidence supplied here. Policy comparisons, uncertainty across seeds and densities, and isolated real-time performance remain separate evaluations.
