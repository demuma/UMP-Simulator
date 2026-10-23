# Bounded OSM functional-region feasibility tool

This prototype reproduces the Mönckebergstraße map figures and exports disjoint
rectangular patches for the existing production PolicyTree. It creates no motion,
observations or published aggregates, and makes no privacy-effectiveness claim.
The existing simulator configuration and CMake targets are unchanged.

See [the report](../../docs/OSM_MOENCKEBERG_FEASIBILITY_2026-10-23.md) for actual
results, assumptions, numerical tolerances and the distinction between three
independent D6 domains and one refined tree.

## Reproduce the maps offline

Run from the repository root, with output outside the repository:

```sh
python3 -m venv /private/tmp/ump-osm-venv
/private/tmp/ump-osm-venv/bin/python -m pip install -r tools/osm_regions/requirements.txt
/private/tmp/ump-osm-venv/bin/python tools/osm_regions/build_map.py \
  --source tools/osm_regions/data/moenckeberg/source_geometry.geojson.gz \
  --out /private/tmp/ump-osm-reproduction
```

The snapshot is real projected OSM geometry, compressed to keep Git small. The
tool does not contact a network. `--xml` optionally accepts a separately obtained
OSM API XML file and freezes its relevant geometry first; the experiment's area
and three footprint centres are intentionally fixed in source. This is not a
general city importer. The raw 27-MB XML is not in Git. A fresh download can change;
use the retained source for result reproduction.

Each case writes `policy.json`, `cells.json`, `functional_regions.geojson` and a
summary. Figures include attribution. The probe JSON is an adapter schema,
**not a full Simulator YAML configuration**. The source and functional-region
files use projected/local metric coordinates with explicit descriptions; they
must not be interpreted as RFC 7946 longitude/latitude GeoJSON.

Every mixed cell retains all class bits and all associated requirements. Shared
walking/cycling use is explicitly retained. Single display colours are visual
priority only. Width assumptions, unresolved attribute-only infrastructure and
2D grade-separation limits are deliberate and documented in the report.

## Verify production policy resolution

An existing Release build must supply `simulator/build/libump_semantic.a`.
The standalone `check_policy.cpp` compiles the current production PolicyTree,
metric parser and configuration source; no MongoDB or rendering window is used.
Homebrew/pkg-config dependencies are the simulator's existing SFML and yaml-cpp.
Run, for example:

```sh
python3 tools/osm_regions/run_policy_probe.py \
  --input /private/tmp/ump-osm-reproduction/detail/policy.json \
  --out /private/tmp/ump-osm-reproduction/detail/policy_validation.json
/private/tmp/ump-osm-venv/bin/python tools/osm_regions/audit_geometry.py \
  --source tools/osm_regions/data/moenckeberg/source_geometry.geojson.gz \
  --out /private/tmp/ump-osm-reproduction
```

The wrapper records source and binary hashes and actual emitted results. Repeat
with `overview` and `close` to validate the other PolicyTree exports.

The independent `audit_geometry.py` checks vector-to-raster agreement and input
rectangle ownership. Its optional original-XML check additionally reconstructs
node/way source geometry; relation reconstruction is outside that one check.
The committed validation JSON records the actual checks performed.

## Data and attribution

`data/moenckeberg/` contains the frozen compact source, acquisition manifest,
assumptions, cell masks, exact exported policies and test results. Full temporary
functional layers can be regenerated. No generated road-user movements are stored.

The source snapshot and derived geometry contain OpenStreetMap data:
© OpenStreetMap contributors; ODbL 1.0.
https://www.openstreetmap.org/copyright
