# Source-bound shop access expansion — 24 October 2026

The optional `--expanded-shop-access` source adds the Elbphilharmonie Kultur Café Starbucks and Konzertkasse Mönckebergstraße as destinations for actual simulated visits. The four existing southern storefront destinations remain. Historical controls keep their original four-shop geometry and demand unless the option is enabled.

## Source and modeled associations

The extension requires the reviewed frozen source geometry SHA-256 `afa2690e408f467af5ff679770bf872816cc568714d9171cf4efb493809e40ed`. All seven named business POIs in the current crop are accounted for below.

| Business | Source POI node | Modeled destination |
| --- | ---: | --- |
| Apollo | 10771056021 | Existing synthetic original-facade projection |
| Ditsch | 2887815990 | Existing synthetic original-facade projection |
| Adidas Originals | 990030917 | Existing synthetic original-facade projection |
| H&M HOME | 442443889 | Existing synthetic original-facade projection |
| Elbphilharmonie Kultur Café Starbucks | 442443891 | Exact source main entrance node 9370793427 |
| Konzertkasse Mönckebergstraße | 13739289193 | Separate synthetic original-facade projection |
| Mö Grill | 4248082207 | Excluded as an indoor destination: the source places it under the A1 canopy, with no enclosing ground-level building facade |

The café and Konzertkasse occupy source building way 32529387. Their tenant-to-door associations are explicit modeling assumptions. An OSM building door does not itself establish which tenant uses it, accessibility permission, opening hours, or actual visitor demand.

The café main entrance is retained at exactly `(35.24755586031824, 28.583821195177734)` m. Its source node is version 2, timestamp `2023-07-22T18:14:47Z`, tagged `entrance=main`. The native finite door throat uses a local tangent centered at this exact source point. Adjacent original wall segments have a sub-millimeter kink relative to the tangent chord; the original building polygon is not modified or divided.

The Konzertkasse target is approximately `(42.0313052462705, 32.171902054135664)` m, an orthogonal projection onto an original reachable wall. It is marked synthetic. Manual changes are possible only through the existing source-hash-bound override document; they must remain on a reachable original facade. The exact café source door cannot be displaced through a synthetic override.

## Why the main café needed an explicit approach surface

The frozen map's derived walking geometry consists of simplified functional surfaces and buffered transport lines. Its nearest walking polygon is about 5.70 m from the café main door. Merely displaying a door would not make a safe route possible.

The extension therefore declares a separate, synthetic three-meter-wide exterior access connector. Its approximately 7.58 m centerline joins the exact door through an outward normal approach to the original body-safe walking region. The connector is clipped to the domain and actual ground-building polygons. It is exposed as `navigation.synthetic_access_connectors`, with a specific `portal_id`; it is never treated as a road-crossing priority resource.

This is a modeled forecourt connection, not a claim that OSM surveyed its width or walkability. Center paths must remain outside building interiors. Circular-body overlap with a wall is permitted only inside the explicitly referenced 1.2 m door throat. The rest of the building remains an obstacle. Source-bound metadata and independent physical checks are required by the replay export.

## Demand and visible identities

Actual visiting pedestrians cycle across all six enabled business destinations after rider and station-trip selection. Each shop visit has an incoming episode and, after hidden dwell, a newly identified outgoing episode through the same declared portal. Private simulator person identities are not revealed as cross-building track continuity.

For the 128-person seed `20261024`, 150 ms arrival-interval geometry check, the mixed source plans eight incoming/outgoing visits for Apollo and seven for each other shop. A1 and A2 retain independent station arrival/departure trips. These are declared synthetic demand weights, not measured market shares.

The civic building's secondary door node 11062053180 remains unselected: the initial extension uses one primary target per business rather than assigning another tenant without evidence. Rappolthaus door node 6244468529 remains source context without an established tenant link. Node 4616972979 has `level=1`, so no unverified ground access is added there.

## Pedestrian-only experiment source

`--pedestrians-only` retains the entire finite cohort and all five base pedestrian profiles, including stroller and mobility-aid profiles. It skips rider relabeling; it does not delete riders from an existing recorded stream. Walking, crossings, shop access and optional station geometry remain the same. Source metadata records the effective rider fraction as zero and retains the configured ignored fraction separately. Road intervals are context rather than active sources. Rider-priority coordination should be disabled for this source, so empty roads do not impose artificial admission delays.

This is a separately generated scenario. Changing composition also changes routes and demand; comparisons must not be described as identical-motion counterfactuals.

## Verification

Five focused regression tests pass. They verify exact source identity and door location, unchanged original building IDs, bounded explicit access geometry, body clearance outside the finite door throat, two-way planned demand for all six shops, fresh visible episode IDs, the complete 128-person pedestrian-only cohort, unchanged default four-shop geometry, and rejection of altered source hashes, source node versions, off-wall overrides and displacement of the exact café door.

A native run and independent observed-motion audit are separate acceptance gates. Passing construction checks alone does not establish that all trips complete, that local steering remains collision-free, or that the privacy mechanism gains utility on this new source.
