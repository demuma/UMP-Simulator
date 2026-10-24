# Mönckebergstraße subway access: source review and implementation plan

Date: 2026-10-24. Status: **planned, not implemented**. This review changes no simulation source, policies, movement recording, benchmark result, map snapshot or native portal implementation. The companion [verification artifact](verification/subway-access-feasibility-2026-10-24.json) records the exact public source objects, hashes and geometric checks.

## Why the replay map differs from the web map

The replay contains a custom 80 × 80 m functional-geometry raster centered at longitude 10.0010, latitude 53.5512. The user's [OSM web view](https://karte.openstreetmap.de/#map=18.4/53.551128/10.00133) is centered at longitude 10.00133, latitude 53.551128, approximately 23 m away. It uses a different rendering style and viewport. No web-map tiles were downloaded for the replay.

The frozen data were acquired from the official OSM map API on 2026-10-23. Original polygon coordinates are retained, projected to EPSG:25832 and translated to local metres with x east and y south. Explicit transport areas are used where mapped. Otherwise, lines become corridors using a supported numeric OSM width or declared defaults: walking/cycling 2.5 m, crossings 3 m, pedestrian streets 10 m, service roads 4 m and other roads at least 6 m. Lane counts can increase a road's default width. Unresolved sidewalk/cycleway attributes are not converted into invented offset paths. The current urban source also includes five explicitly synthetic crossing/curb connectors.

Thus, some width differences reflect modeling assumptions rather than a different underlying street location. D6 spatial policy/observation discretization and the 0.5-m movement-routing lattice are separate from the original continuous map geometry. See [the original feasibility report](OSM_MOENCKEBERG_FEASIBILITY_2026-10-23.md) for historical map derivation; its statement that buildings were not collision obstacles applied to that original geometry-only experiment, not to the later movement source.

## A1 and A2 are present in the exact original input

| Reference | Name | OSM node | Latitude | Longitude | Local x/y (m) |
| --- | --- | ---: | ---: | ---: | --- |
| A1 | Barkhof | 280355670 | 53.5509984 | 10.0015621 | 77.554288 / 61.903890 |
| A2 | Spitalerstraße | 348025368 | 53.5514323 | 10.0013746 | 64.453753 / 13.808432 |

Both nodes have `railway=subway_entrance`, `public_transport=entrance`, `entrance=yes`, `wheelchair=no`, and their respective `ref`. Both belong to OSM public-transport stop-area relation 300934, named Mönckebergstraße. Node references such as A1/A2 are not globally unique; the stop-area association and source node identity are necessary. The [OSM tagging documentation](https://wiki.openstreetmap.org/wiki/Tag:railway=subway_entrance) identifies these nodes as surface access points, distinguishes entrance names from station names, and describes the stop-area association.

A1 connects to surface footway 44330705 and stairway 43028024, with 25 steps, `level=-1;0`, `ramp=no`. A2 connects to surface pedestrian way 44330704 and stairway 43028025, with 24 steps, `level=-1;0`, `layer=-1`, `ramp=no`. Excluding the underground/mixed-level stairways from a 2D surface movement graph is appropriate; it does not imply that the surface entrance nodes should be unusable as sources or sinks.

### Exact provenance

- Original XML: `/private/tmp/ump-osm-moenckeberg-2026-10-23/map.osm`; SHA-256 `230dd159d3d01233a6cc641ae826a664bb9228b6833c6ed7f7ddea0c6a7cccec`. This matches the acquisition manifest. It remains temporary local input and is not proposed for Git.
- Frozen compact source: `tools/osm_regions/data/moenckeberg/source_geometry.geojson.gz`; compressed SHA-256 `508ca79545419b1f1028b79a1f8a12684b8a6ed53e95b2d94fb36094298388f3`; decompressed SHA-256 `afa2690e408f467af5ff679770bf872816cc568714d9171cf4efb493809e40ed`.
- Acquisition manifest: `tools/osm_regions/data/moenckeberg/source_manifest.json`; URL, acquisition time and original/retained hashes are recorded there. The companion artifact also records its own exact hash and the inspected source-code hashes.
- Local coordinate transform: `x = easting − 566277.8310511189`, `y = 5934095.84809249 − northing`, in metres.

The freezer's `KEEP_TAGS` in `tools/osm_regions/build_map.py:44` discards `railway`, `public_transport`, `ref` and `wheelchair`. Entrance extraction at line 131 retains the points because `entrance=yes` is present, but transport identity is lost. Stop-area relation membership is also outside the compact geometry schema. The current compact source therefore proves exact entrance positions but cannot by itself establish A1/A2 station semantics. A compact supplemental metadata file tied to both frozen-source and original-XML hashes can preserve this evidence without changing the historical snapshot.

## Concrete ground-obstacle modeling gap

A1 is inside overhead roof way 425508817; A2 is inside roof way 425508816. Both are explicitly `building=roof`, `layer=1`. The current source unites all building polygons in `storefront_scene.py:54` and subtracts them from walking geometry at line 159. `building_access.py:57` similarly treats all building footprints as obstacles. These overhead canopies therefore behave as solid ground-level buildings. Existing facade candidate filtering already recognizes some roof/non-ground buildings as unsuitable indoor destinations, but that distinction does not currently reach the obstacle union.

A read-only counterfactual calculation removed **only these two tagged roof ways** from the obstacle union. All other building polygons and the original walking layer remained unchanged. Results:

| Check | A1 | A2 |
| --- | ---: | ---: |
| Original walk contains exact entrance | No | No |
| Distance from entrance to original walk boundary | 2.724 m | 1.137 m |
| Candidate walk contains exact entrance | Yes | Yes |
| Distance to candidate walk boundary | 2.446 m | 5.496 m |
| Area of 0.502-m disk outside candidate walk | 0 m² | 0 m² |

The 0.502-m test radius corresponds to the current urban maximum pedestrian body radius 0.45 m plus 0.05 m hard clearance and 0.002 m numerical erosion margin. The check used Shapely's default polygonal disk buffer. It establishes that both exact surface nodes fit into the existing 2D derived walking space after the two canopy exclusions. It does **not** establish complete route reachability, dynamic source admission, stairwell geometry, surveyed access widths, physical stairs behavior or global collision/deadlock guarantees. The canopy polygons should remain visible as overhead map context; they should not simply disappear.

## Staged implementation

1. **Freeze the existing benchmark.** Keep the current source recording and comparison results unchanged. Produce new source/configuration manifests for any movement-space or demand modification.
2. **Preserve transit metadata.** Add a compact, validated supplement containing exact public node identity, reference, name, stop-area, accessibility tags and relevant connected-way provenance. Tie it to the existing compressed/decompressed source and original-XML hashes. Do not depend on the temporary raw XML for ordinary replay after that extraction.
3. **Separate overhead context from ground obstacles.** Introduce an explicit level-aware ground-obstacle decision; retain actual walls and uncertain structures conservatively. Display overhead canopies separately. Avoid a broad rule that treats every non-ground tag as permission to walk anywhere below it.
4. **Add an explicit surface-access portal.** Native `MappedPortal` and its YAML parser currently require a building ID, facade segment and opening width (`MappedScene.hpp:27`, `MappedSceneConfiguration.cpp:119`). A subway portal should be a deliberate typed source/sink interface, with checked local approach and a declared admission cross-section, rather than a fake building facade. Preserve existing facade portal behavior and defaults.
5. **Generate reproducible independent passenger trips.** Add seeded arrivals from and departures into A1/A2 with explicit demand weights/rates, rather than forcing every arriving passenger to reappear later. Connect them to body-safe walking routes, shops and/or boundary intervals. Smooth arrivals first; train-related bursts are a separate scenario factor with explicit assumptions. Do not infer measured passenger volumes from OSM geometry.
6. **Respect visibility and accessibility.** End the observed track when the person disappears; assign a fresh track on a later appearance. Optional simulator-only identity can support Ground Truth experiments but must not reach aggregator inputs. Both entrances are tagged `wheelchair=no` and stairs have `ramp=no`. Do not silently route generic mobility-aid or stroller profiles through them: define eligibility or explicitly model an alternative accessible entrance first.
7. **Validate before comparison.** Run the tests below, then create and label a new source recording. Reuse one frozen recording across candidate aggregation methods, and retain the original benchmark as a separate result.

## Acceptance criteria

- The compact supplement matches the exact source/XML hashes, node coordinates, versions, names, references and stop-area membership; unknown/duplicate nodes and transforms fail validation.
- Historical scene generation is byte-stable with the new feature disabled. Existing facade portal configuration remains accepted and retains behavior.
- Exact A1/A2 coordinates are used. Overhead canopies remain displayed; unrelated solid buildings remain impassable. Every used pedestrian body and each complete swept route satisfy the selected ground-space checks.
- Underground stairs do not become ordinary surface through-routes. Portal termination/admission is explicit and unrelated passers cannot disappear merely by touching the portal neighborhood.
- Source/sink capacity, opposite-direction use and simultaneous requests are explicitly defined. No overlapping bodies, duplicated terminal events, endless unintended waiting or hidden-track observations occur in acceptance fixtures.
- The configured demand yields both entering and exiting A1/A2 paths, is deterministic under a fixed seed and remains drainable for the declared workload. Burst capacity is reported separately from total population.
- Profiles excluded by declared accessibility assumptions are never selected for these stairway accesses. Missing accessibility facts are reported rather than guessed.
- A reappearance receives a new observed track; private person association is absent from aggregator inputs and public output. Repeated observed track support is labeled as track support, not a person-level anonymity guarantee. If hidden returns can occur within retained history, the existing `one_episode_per_retained_history` source contract must be revisited rather than silently violated.
- Replay controls show one readable entrance label per A1/A2, provenance and portal type; point/line debugging is optional. Existing movement and policy inspection continue to work.
- Region definitions and privacy/utility thresholds remain explicit research policy choices. OSM does not determine the required privacy constraints or prove a sensitive attribute.

## Scope and limitations

This is a source/geometry feasibility review, not implementation or a new evaluated scenario. No native build, full movement run or runtime/privacy benchmark was started. No source recordings were changed. There are no measured station demand counts, train-arrival times, surveyed stairwell outlines, access widths or indoor movement models in this evidence. The small geometric check supports the next implementation step without claiming calibrated realism or additional privacy protection.
