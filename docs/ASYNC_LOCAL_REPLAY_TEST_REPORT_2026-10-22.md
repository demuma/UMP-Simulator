# Asynchronous local replay — test report

Date: 2026-10-22. Status: **verified within the scope below**.

## Scope and outcome

The HTML replay now accepts cell-local result streams and reconstructs an
asynchronous historical mosaic. Each visible entry retains its original cell,
source interval and publication/evaluation time. Unrelated owners can update
without replacing the whole map. Common-window and fixed-window snapshots
retain their existing behavior.

This change implements the [viewer contract](ASYNC_LOCAL_REPLAY_CONTRACT_2026-10-22.md).
It does not change aggregation, policies, input trajectories, metric formulas,
release records or MongoDB. No normal Simulator run or database reset was used.
This report establishes display correctness, not new privacy or utility results.

## Verification results

| Check | Result | Evidence covered |
|---|---|---|
| Python viewer suite | 40/40 passed | Source compatibility, canonical cell/scope geometry, disjoint space-time retirement/support, local public/private correspondence, negative inputs, allowlisted loopback HTTP routes and bundle preparation |
| JavaScript model suite | 58/58 passed | Timing, original cell/window provenance, selection, masks, private isolation, rewind, missing measurements, source groups and fragment budget |
| Four real local result variants | 59/59 per variant | The default model checks plus an independent spatial oracle on the actual recorded result |
| Registered CTest checks | 2/2 passed, 0.76 s | `replay_viewer_evaluation`, `replay_viewer_model` |
| Browser inspection | Passed | Independent intervals, earlier local release, own-window groups, reverse seek, private diagnostics, stable selected cell and visual layout |
| Frozen source integrity | 56/56 hashes unchanged | Complete original study manifest |
| Prepared replay integrity | 9/9 files byte-identical | Original observations and eight common/local result files |
| Existing bundle compatibility | Passed | Regional common-window bundle, 500-user moving comparison with fixed baselines, and 500-user one-/four-second comparison |

The four optional artifact runs repeat the 58 default checks; they are not 236
independent test cases. Their additional oracle checks the centre of each of
4,096 finest cells against an independently reconstructed last-event owner.
It checks both public and private channels at event boundaries, one millisecond
before/after them, and during reverse seeks. Synthetic model tests additionally
cover changing parent/child masks, equal-time ordering, late publication of an
older interval, boundary contact and empty private retirements.

The viewer is the only implementation changed in this gate. The native C++
aggregator was therefore not rebuilt or retested here; its preceding acceptance
is recorded in the [semantic local test report](SEMANTIC_CELL_LOCAL_TEST_REPORT_2026-10-22.md).

## Browser observations on the frozen mechanism fixture

The replay uses the existing analytical fixture: 20 road-user identities,
18 distinct positions at a sample, 380 observations over two seconds, an
80 x 80 m domain and depth 6. Its small movements are explicitly labeled as a
scripted mechanism test. It is not a realistic shopping-street population.

- At 400 ms, the regional local variant has four published cells; the common
  variant has no publication yet. Unavailable recipient information stays blank.
- At 600 ms, the common variant displays `[0,600)` while the local mosaic retains
  `[0,400)` for control cells and `[500,600)` for cell 3168. Both intervals are
  visible in the cell selector and original-cell inspector.
- Cell 3168 has four distinct cyclists in both views, but 20 observations in
  the common window versus four in the local window. Private source groups use
  the respective original intervals: 10 + 10 versus 2 + 2 adult/senior cyclist
  observations. Reference dots remain the current recorded sample.
- Seeking from 600 to 800 ms keeps cell 12300 selected while replacing its
  publication key, interval and counts. A review caught and corrected the
  previous fallback to the first unrelated entry.
- At 1,000 ms, private history contains seven finalized footprints, including
  three suppressed cells. Recipient history contains four aggregates. Private
  empty retirements never erase public history. The private timeline includes
  decision events and uses distinct accessible labels.
- Seeking back to zero clears both recipient views, disables cell selection
  and removes future source information. Subsequent forward seeks rebuild the
  eligible prefix.

The browser proof is stored locally as
`/private/tmp/ump-async-local-replay-proof.png`. It contains private synthetic
position/reference information and is deliberately excluded from Git. Partial
parent-mask correctness is covered by model regressions and code review; the
stationary mechanism fixture does not itself demonstrate changing parent masks.

## Integrity and preparation

`prepare_local_bundle.py` accepts only a verified semantic cell-local study and
a fixed list of eight variants. It verifies observations, results and policy
files against the original manifest, caches the verified bytes, and uses those
same bytes for copying and overlay preparation. Validation precedes publishing
the new output directory. An existing destination is rejected.

Three focused tests cover exact-byte copying and unchanged sources, refusal to
replace an existing destination, and rejection of an incorrect policy digest
without leaving an output bundle. The original study manifest remains:

```text
8124fb27a9fae7db16a28d9b9d8f661dd998204d9d1d6cbeff5c268999637811
```

Only code, tests and English documentation belong in this commit. Generated
movement files, full release streams, the replay bundle and screenshots remain
local and ignored. The helper prepares a private research bundle; selecting
recipient display mode does not sanitize its underlying private files.

## Reproduce

From the project root:

```bash
ctest --test-dir simulator/build -R '^replay_viewer_(evaluation|model)$' --output-on-failure
node tools/replay_viewer/test_model.js results/semantic-cell-local-2026-10-22/cell_local_regional_temporal_first.json
python3 -B tools/replay_viewer/prepare_local_bundle.py \
  --study results/semantic-cell-local-2026-10-22 \
  --output results/semantic-local-viewer-2026-10-22
python3 -B tools/replay_viewer/serve.py \
  --bundle results/semantic-local-viewer-2026-10-22 --port 8773
```

Preparation intentionally fails if the output already exists; use the already
prepared bundle or choose a new output directory. Local HTTP tests require
permission to bind a loopback socket in restricted execution environments.
The initial sandboxed socket test was rerun successfully with that permission.

## Remaining work and acceptance boundary

This is a historical display, not an estimator of simultaneous current
occupancy. Counts from differing intervals must not be added as a current
population. A clipped parent keeps its whole original statistics; fragment
counts remain unknown and are not labeled on the map. Exceeding the explicit
65,536-fragment budget stops the display and clears the failed view rather than
silently truncating it.

Next implement scope-aware semantic fixed-query evaluation, then compare the
existing moving observations against legal fixed grid/window baselines and the
common-window coordination ablation. Review aggregator requirements and any
failures at each gate. Privacy evaluation follows with an explicit protected
unit, recipient knowledge and measured objective. Policy compliance and class
support alone do not establish a privacy guarantee.
