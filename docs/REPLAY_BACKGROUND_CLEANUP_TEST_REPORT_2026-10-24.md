# Replay background cleanup and retained-capture audit — 24 October 2026

## Problem and corrected contract

The background renderer baked 6–7-point shop/building names, attribution text and
entrance/access debugging marks into the PNG. Hiding the interactive label layer
could not remove those glyphs, and showing that layer duplicated names/doors.

`tools/mapped_scene/build_mapped_scene.py::draw_background` now renders functional
polygons and the original building outlines only. It preserves the exact map
projection, dimensions, geometry, colors and hole handling. It omits names,
entrance symbols, modeled frontages/separators and source/sink debugging marks.
The interactive replay remains responsible for their vector presentation and
readable map attribution. Attribution is also retained in PNG metadata. The
returned rendering descriptor is recorded in the scene manifest and PNG metadata;
it does not change the replay schema or require browser computation of geography.

## Retained replay repair

The current local 64-person storefront replay was refreshed with
`tools/mapped_scene/refresh_background.py`, using its existing
`building_access.json` and the original frozen map source. No routes, motion,
classes, policies or results were regenerated.

- Before PNG SHA-256: `4c9f5f33cfaebb826597d905f1b383438d9ce1ae157fe60a4ab0af922cb55d20`
- After PNG SHA-256: `270e5457022a95ca3dc8223c21208becd6fb062e9601403b09b563771375d7d0`
- Refresh ID: `geometry-only-4c9f5f33cfae-270e5457022a`
- Scene: `results/storefront-navigation-2026-10-24-64/scene`
- Replay: `results/storefront-navigation-2026-10-24-64/replay`

The prior scene PNG/manifest and replay PNG/bundle/capture proof are preserved in
`presentation_history/<refresh-id>/` (under `private/` in the replay). Current
manifests update presentation digests and append an explicit refresh record.
Original generator, native execution and capture evidence are not relabeled as a
new run. The record retains the exact renderer/refresh-tool hashes executed for
this presentation change; subsequent additional guard changes do not rewrite it.
All observation, native result, source, configuration, execution and access bytes
remain unchanged. The validated replay map metadata, including supplied names and
attribution, also remains unchanged. Generated files stay ignored and local.

## Verification

Focused background tests: **3/3 pass**, including a normal CLI generation. They
inspect actual Matplotlib artists to establish that polygons/building boundaries
remain while text/door/debug artists are absent, and inspect PNG metadata and
800 × 800 image dimensions. This tests the actual rendering operation rather
than relying only on a declaration of which layers were rendered.

Exporter suite: **42/42 pass**, including **6 retained-refresh tests**:

1. Preserve all non-presentation bytes and archive exact prior evidence; preserve
   original generator provenance and metadata; verify all updated digests; repeat
   invocation is a no-op without another history entry.
2. Reject a corrupt original capture digest before altering any presentation.
3. Reject a proof missing required native-source/artifact digests.
4. Reject changed scene background or frozen source/transform/map-builder
   provenance before changing files.
5. Refuse to overwrite an existing presentation-history record.
6. Reject identical, nested or repository-containing input directories before
   staging, leaving all existing fixture files byte-for-byte unchanged.

The real retained capture passed scene/access and full replay validation before
and after staged replacement. Repeating the command returns `status: unchanged`.
The additional guarded runner revision also passed the same exporter suite.

Commands used the existing mapped-scene Python environment and `-B`; no native
simulation, MongoDB operation or movement export was required. Existing upstream
Matplotlib/Pyparsing deprecation messages are unrelated to these assertions.

The root task restarted the retained HTTP server and visually verified the
current browser presentation. Toggling map names and entrance overlays off leaves
no baked duplicate names or doorway glyphs. Toggling them on shows one readable
label layer and enlarged entrance glyphs (12-pixel diamonds / 11-pixel squares).
Map attribution is readable outside the map canvas. Local verification images:
`/private/tmp/ump-map-labels-off-20261024.jpg` and
`/private/tmp/ump-single-map-label-layer-20261024.jpg`.
