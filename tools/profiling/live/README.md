# Isolated live-pipeline timing

These tools measure the production Simulator path in a copied source tree. They do not change the checked-out Simulator, its configuration or the production MongoDB database. All repository/source paths are explicit. Both executables and measurement outputs remain outside Git.

Run the pure safety and summary tests from the repository root:

```sh
python3 -m unittest discover -s tools/profiling/live -p 'test_live*.py' -v
```

Build an isolated instrumented Simulator (the output directory must not exist):

```sh
python3 tools/profiling/live/build_live.py --repo "$PWD" --output /private/tmp/ump-live-build --expected-revision "$(git rev-parse HEAD)"
```

This authenticates the production revision, copies source, applies explicit measurement-only edits, compiles with the maintained SFML/MongoDB/CMake dependencies, verifies source hashes remained stable and writes `build-manifest.json`. Use the recorded binary SHA-256 and full source/tool hash manifest for provenance. The measured production baseline was `5d3cc4b`. The command above checks the current checkout revision. Exact working-tree source hashes, rather than the commit alone, identify the compiled code; the build manifest also records working-tree status. A later documentation/tooling commit can retain unchanged live-core source hashes.

Prepare or execute a bounded headless run from the repository root. Without `--execute`, this writes only a configuration and manifest and does not access MongoDB:

```sh
python3 tools/profiling/live/run_live.py --repo "$PWD" --policy tools/profiling/live/semantic_local_policy.json --simulator /private/tmp/ump-live-build/build/Simulator --output /private/tmp/ump-live-headless --duration 120 --execute
```

Add `--renderer` with a different fresh output directory for the renderer-enabled case. The renderer runs at requested 1× playback; queues have capacity 8 for this latency experiment. The example's production default remains 128. The harness creates fresh UUID raw/release/journal databases, verifies owner tokens and audited outputs, and drops only those owned databases after success. Failures retain evidence. `--keep-databases` deliberately retains owned databases and must not be used when temporary data retention is disallowed.

No generated movement is exported by default. The optional `--export-capture --capture-seconds 60` path retains identity-bearing motion files and requires explicit authorization for that data retention; it was not used for the 120-second headless measurement. Ordinary timing runs retain only stage events, numeric/count audits and private aggregation diagnostics. Large diagnostics are not a Git artifact and should be removed after compact evidence is secured.

The semantic policy file is an exact copy of the previously frozen local Semantic First → Temporal First experiment. Its empty replay-only `policy_regions` list is omitted when embedding it in live YAML; `policy_tree.regions` remains empty. Thus this is a homogeneous-policy performance case, not a regional-policy effectiveness experiment.

The summary tests distinguish exact source cadence, nonempty GT records, inside-sensor counts, source-to-display timing, normal-step versus EOF publication latency, and fully reconciled recipient ACKs. Nested scopes are inclusive and cannot be summed. Queue writes measure locking/copying/wait together. RSS is sampled externally; timing-vector storage is reported separately.

A live run is not a deterministic replay. Positions/targets are random and motion noise depends on real elapsed time. Headless production is unpaced; renderer pacing backpressures the producer. Separate renderer/headless runs do not isolate renderer overhead on identical trajectories, and source-state timings are not an externally clocked sensor-arrival test. Population can decline substantially over two minutes; inspect time slices rather than claiming sustained capacity from an overall mean.
