# Single map layers and guarded Barkhof topology — 2026-10-24

## Accepted checkpoint

The current retained replay now has one toggle-controlled name layer and one
readable entrance layer. Its raster is geometry-only; tiny baked names, OSM text,
door glyphs and access-debug marks are removed. Attribution remains in readable
external UI/map metadata and PNG metadata. The original presentation artifacts
and original capture provenance are archived, with an explicit refresh record.
Motion, source configuration, observations, results and building access bytes are
unchanged. See the [background report](REPLAY_BACKGROUND_CLEANUP_TEST_REPORT_2026-10-24.md).

The next static topology fix is implemented behind
`--experimental-narrow-passages`. It repairs both Barkhof directions without
changing allowed geometry or physical clearance. Dense native interaction is
not accepted, so the flag is **off by default**. All accepted default paths and
native source behavior remain unchanged. This checkpoint does not activate new
entrances, free street crossings, comfort behavior, cyclists or scooters.

## Static routing change

The previous 0.5-m lattice cannot connect `[65,35]` to `[68,45]`, despite a connected
body-safe walking polygon. A deterministic, geometry-scoped visibility fallback
now uses exact polygon vertices only after a failed lattice query, and only when
explicitly enabled. It restricts search to a common polygon component, caps each
graph at 1,024 vertices, settles nodes once and caches only static undirected edges.
Every edge and simplification uses the original containment predicate. There is
no geometry widening, global raster refinement, road-access change or d6 change.
The native C++ dynamic replan graph remains at its original resolution.

Both directions produce an 11-vertex path of about 10.553 m. Independent swept
0.55-m body checks against original walking/building geometry report zero outside
walking area; disconnected islands, holes/buildings and excess vertex counts remain
rejected. The forward query takes 0.400 s and reversed cache reuse 0.262 s in one
measurement including failed coarse routing. This is offline route construction,
not per-frame movement cost or a global shortest-path/latency guarantee.

All 96 retained endpoint queries still match the old successful lattice results.
The default 64-person `mapped_scene` digest remains
`cada80b07538aa5c8add0eb6b233e7653d5e15c2409405b0a579a4c7e04b00a6`.
A fresh experimental 64-person source uses 54 road-crossing guidance routes out of
96, compared with zero by default. Its independent geometry audit passes; generation
takes 13.62 s in that measurement. Geometry and release policies are identical, but
newly reachable source/sink choices change the source stream. Earlier frozen
performance/utility results must not be silently attributed to this new stream.

## Native gate: accepted default and experimental limitation

The original finite-drain gate still uses 600,000 simulated ms and at most 180 s
wall time per case. The final default gate passes without relaxing those budgets:

| Default population / arrival interval | Finished episodes | Last completion | Active / pending / stalled / overlaps | Native wall time |
|---|---:|---:|---:|---:|
| 64 / 1,000 ms | 96 / 96 | 186.900 s | 0 / 0 / 0 / 0 | 11.859 s |
| 128 / 500 ms | 192 / 192 | 344.200 s | 0 / 0 / 0 / 0 | 48.306 s |

Maximum zero-motion stops remain 0.250 s and 25.500 s, respectively. The dense
default source's known long stops remain a limitation; finite completion is not a
calibrated human-movement or hard realtime claim. The whole default Python/native
gate takes 73.09 s including configuration generation.

With experimental visibility enabled, the sparse 64-person source passes the
same full finite-drain assertions. The dense 128-person seed 20261024 / 500-ms
case exceeds the unchanged 180-s wall budget. That failure is retained. The
existing gate emits counters only at horizon end, so the timeout alone cannot
identify deadlock or the number remaining.

A separate 90-s bounded diagnostic on the exact same experimental 128-person
input reaches 132.650 simulated seconds and reports:

- 163 starts, 85 ends, 78 active and 29 pending episodes.
- 46 active stall diagnostics; maximum zero-motion stop 58.850 s.
- 40 active bodies in the declared Barkhof neck/approach diagnostic box.
- 2,914 replans, of which 2,900 fail; no reported physical overlap.
- Step mean 33.94 ms, p95 127.80 ms, p99 148.03 ms, max 210.29 ms;
  602 of 2,653 source steps exceed 50 ms.

Ends continue to advance, so this is evidence of persistent partial local congestion,
not proof of a global deadlock. Static path feasibility has exposed unresolved
native opposing-flow/entry behavior. More A* nodes or a later timeout alone would
not establish a successful movement mechanism. Before enabling crossings by
default, implement tested waiting/clear-exit behavior, finite fair passage
ownership or compatible direction batches, and native recovery that respects the
same topology. Repeat predeclared sparse/dense/500-total finite sources with
swept safety, completion, stop distributions and bounded runtime.

## Regression and visual verification

- **8/8 affected CTest groups pass**, 85.27 s: viewer/server, viewer model,
  independent access audit, generator, dedicated router, exporter, track audit
  and comparison adapter.
- The new router/API/CLI/runner suite contains **12 passing methods**. It covers
  bilateral frozen-map routing, a connected corridor with zero lattice nodes,
  blocked geometry, bounds/caching, default source digest, opt-in construction,
  invalid-mode rejection and launcher forwarding before DB work.
- The exporter suite has **42 passing methods**, including six guarded refresh
  preservation/provenance/directory/overwrite cases. Background artist/PNG tests
  establish actual absence of baked text/door/debug artists while geometry remains.
- The native default64/128 gate above is recorded separately and is not repeated
  inside the affected selection. C++ movement/metrics/aggregation code is unchanged;
  the prior full 86-suite gate belongs to the preceding geometry checkpoint.
- Chrome at 50 s retains 40 tracks/40 positions. Turning names and entrances off
  removes them fully; turning them on shows one name layer and larger fixed-pixel
  glyphs. The final refresh command is idempotent and reproduces the clean raster.

Read the [compact aggregate evidence](BARKHOF_TOPOLOGY_RESULTS_2026-10-24.json) and
[affected CTest log](verification/map-presentation-topology-ctest-2026-10-24.log).
The evidence preserves the timeout and diagnostic counts, exact source/config/
binary hashes, default gate commands/stdout and the exact frozen diagnostic source
for the recorded positive invocation. Generated configurations and motion stay local.

## Use and next experiment

The generator and launcher both accept `--experimental-narrow-passages` only with
`--motion-mode storefronts`; omission preserves the accepted default. Python callers
use `experimental_narrow_passages=True` through `make_config`/`storefront_scene`/
`make_scene`/`SafeRouter`. Cache identity includes the flag and manifests record the
mode, limits and unresolved dense gate. A changed source needs a fresh recording.

The user's presentation comparison is separately predeclared in the
[comparison protocol](PRESENTATION_COMPARISON_PROTOCOL_2026-10-24.md). It uses the
canonical notation and separates a hard 0.5 semantic ceiling from forced family
projection and the established preservation-first priorities. Actual mixed-mode
source support and genuine action-restricted ablations remain implementation
steps. No new adaptive-versus-fixed advantage or measured privacy gain is claimed
by map cleanup or static connectivity alone.
