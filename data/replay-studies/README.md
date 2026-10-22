# Compact result summaries

This folder contains **aggregate results only**. It includes no generated
movement datasets, observation records, individual IDs/positions, trajectories,
raw MongoDB exports, full replay streams, per-query dumps or compiled binaries.

Three `results-*.tar.gz` archives total **105,688 bytes** (103.21 KiB), containing
110 small files. These summarize 153 moving comparison runs, eight semantic
release methods and four local-policy variants. Policies, protocols, aggregate
audit totals and hashes linking the original local artifacts are included.
The studies used synthetic data; their inputs remain local and ignored.

From the repository root:

```sh
python3 -B tools/evaluation/replay_data.py verify
mkdir -p results
python3 -B tools/evaluation/replay_data.py restore --output results/result-summaries
```

Restoration produces tables and policy files, **not a replay viewer bundle**.
Existing destinations are never overwritten. Original replay demonstrations
require the separate local `results/` inputs.

See [package documentation](../../docs/REPLAY_DATA_PACKAGE.md) for scope and
limitations. `manifest.json` lists all file and archive hashes. `verification.json`
records restoration checks; `publication-scan.json` records the archived-text
credential scan. `assemble.py` preserves the explicit result-only selection.
