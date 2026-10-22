# Compact result-summary package

Status: result-only repository checkpoint, 2026-10-22.

[`data/replay-studies`](../data/replay-studies/README.md) contains small aggregate
result summaries, policies, protocols, audit totals and provenance hashes.
**No generated movement datasets are versioned in this package.** All original
local inputs and replay results remain under the ignored `results/` directory.

## Included and excluded artifacts

The three `results-*.tar.gz` archives total **105,688 compressed bytes**
(103.21 KiB). Their 110 files occupy 773,357 bytes when restored. They summarize:

- 153 runs across 15 moving comparison contexts: the original pilot, cell
  size caps and four-second windows.
- Eight semantic-release methods.
- Four local-policy variants.

The moving and semantic tables preserve aggregate retention, cell size, semantic
loss, logical age, answered-query coverage and conditional error. Compact audit
records retain scalar validity, violation counts, checked-window counts and
published cell/bin totals. Policies and protocols describe the experimental
conditions. Hash-only provenance links the source observation files, outputs,
summaries, policies and study manifests without including those observation or
full output streams.

Excluded artifacts include **every observation/movement dataset**, raw GT/AGBS
exports, capture dumps, individual IDs/positions, trajectories, full replay and
repeat streams, per-query records, compiled binaries and external paper
PDFs/text/page renderings. Local-policy interval lists are reduced to duration
histograms rather than included as replay events.

All underlying studies used synthetic simulator or scripted data. The numerical
summaries do not establish realistic urban motion, a formal privacy guarantee,
global optimality or an adaptive advantage. Conditional query error must be read
with answered-query coverage. Logical publication age is not measured network
delivery latency.

## Verify and restore tables

From the repository root, with Python 3.10 or later:

```sh
python3 -B tools/evaluation/replay_data.py verify
mkdir -p results
python3 -B tools/evaluation/replay_data.py restore --output results/result-summaries
```

The generic standard-library helper checks every archive and member SHA-256,
byte count and inventory entry. Restoration only creates a new output directory;
existing targets, archive traversal, links, symlink ancestors and unexpected
members are rejected. It does not execute archived commands or connect to MongoDB.

Restored folders are `moving/pilot`, `moving/cell-caps`, `moving/four-second`,
`semantic` and `local`. They contain tables/configuration, **not viewer bundles**.
This package has zero observation copies and zero restored replay bundles.
Example aggregate table:

```text
results/result-summaries/moving/four-second/window4000/cap5/n500/comparison/summary.csv
```

## Replay remains local

The local replay viewer still uses the original ignored data, for example:

```sh
python3 -B tools/replay_viewer/serve.py --bundle results/local-leaf-policy-2026-10-22 --port 8770
```

A new checkout does not contain that input. Generate a controlled fixture or
run a capture locally before viewing it; it is not restored from this package.
Existing source generators and experiment instructions remain in the repository.

## Provenance, assembly and tests

`manifest.json` lists the exact published scope and every archived file/hash.
Some files are byte-preserving source summaries/policies/protocols. Audit totals,
local duration histograms and hash-only provenance are intentionally derived
compact records. Source SHA-256 values identify local originals without claiming
that readers can reconstruct omitted inputs. A digest match proves agreement
with this repository manifest, not independent origin or privacy.

Reassembly requires the original local ignored study outputs and an empty target:

```sh
python3 -B data/replay-studies/assemble.py --output /private/tmp/ump-result-summaries-new
```

Tar ordering/metadata and gzip timestamps are deterministic. Five focused helper
tests cover byte-preserving restoration and deterministic archives, corruption,
existing destinations, links, traversal and duplicate/unlisted/missing members:

```sh
python3 -B -m unittest discover -s tools/evaluation -p test_replay_data.py
```

`verification.json` records complete result-package verification and restoration.
`publication-scan.json` records a credential-pattern scan of all selected text.
The earlier larger replay archives are retained only in ignored local backup
storage; they are absent from this result-only package.
