# Compare 1-second and 4-second maximum aggregation windows

This follow-up preserves the recorded movements, seven-profile release taxonomy
and 5/10 m maximum output-cell sizes. It permits longer aggregation by changing
both hard Policy Tree duration/age bounds and the controller maximum together.
Protocol: [predeclared four-second study](FOUR_SECOND_WINDOW_PROTOCOL_2026-10-21.md).
Completed results and verification: [four-second report](FOUR_SECOND_WINDOW_RESULTS_2026-10-21.md).
Previous results: [1-second cell caps](CELL_SIZE_CAP_RESULTS_2026-10-21.md).
Source, query and viewer contracts: [moving replay](MOVING_REPLAY.md).

## Run an isolated comparison

Run from the repository root. Each output directory must be new. The optional
`--max-window-ms` defaults to 1000, preserving the completed 1-second matrix.
Choosing 4000 creates its own policy and adds a 4000-ms fixed baseline for each
of the three legal grid sizes. It also supplies bounded history and endpoint
budgets sufficient for the longer candidates. The ordinary simulator
configuration is unchanged; there is no simulator run or MongoDB access.

```sh
python3 -B tools/evaluation/run_moving_comparison.py \
  --capture results/moving-replay-2026-10-21/n500/capture \
  --max-cell-side-m 5 --max-window-ms 4000 \
  --output results/window-duration-2026-10-21/window4000/cap5/n500/comparison \
  --timeout 180

python3 -B tools/evaluation/run_moving_comparison.py \
  --capture results/moving-replay-2026-10-21/n500/capture \
  --max-cell-side-m 10 --max-window-ms 4000 \
  --output results/window-duration-2026-10-21/window4000/cap10/n500/comparison \
  --timeout 180
```

Repeat with the n200 and n1000 captures and matching new paths. All 12 methods
in an individual bundle use identical observations: nine fixed combinations
of three legal grid sizes and 400/1000/4000-ms windows, plus Temporal First,
Spatial First and Semantic First. Adaptive windows start at 400 ms and extend
in 100 ms increments when needed, up to 4000 ms; they need not always last
4 seconds.

For an explicit old-window reproduction use `--max-window-ms 1000`, a new output
directory and the same capture. Do not overwrite the completed cap-study
artifacts. Compare the same adaptive strategy across the two policy limits;
fixed controls match only where both their grid and duration agree.

## Direct 1-second / 4-second replay

The completed paired bundles `results/window-duration-2026-10-21/viewer-n200`,
`viewer-n500` and `viewer-n1000` contain the actual adaptive outputs at both
5/10 m caps and both 1/4 s limits, on one byte-identical source per bundle.
The first two choices directly compare Spatial First at the 5 m cap.

```sh
python3 -B tools/replay_viewer/serve.py \
  --bundle results/window-duration-2026-10-21/viewer-n500 --port 8769
```

Open `http://127.0.0.1:8769/` and seek to 8 s: the 1 s result covers [7,8),
while the 4 s result covers [4,8). Their values summarize different intervals,
which remain visible. At earlier playheads a 4 s release may not yet exist.
Enable private finalized diagnostics to inspect both effective time bounds.

## Validate and view an individual method portfolio

```sh
python3 -B tools/replay_viewer/serve.py \
  --bundle results/window-duration-2026-10-21/window4000/cap5/n500/comparison \
  --check

python3 -B tools/replay_viewer/serve.py \
  --bundle results/window-duration-2026-10-21/window4000/cap5/n500/comparison \
  --port 8770
```

Open `http://127.0.0.1:8770/`. Select Spatial First and Semantic First to compare
the actual new releases. Use the event navigation and cell inspector to check
intervals, sealing time, category bins and finalized private suppression checks.
An empty region is unknown; enabling diagnostics does not turn private failed
cells into recipient data. Snapshots appear only after the recorded sealing
point, so waiting longer can also leave the recipient panel blank longer.

## What the type mix and the longer window mean

The support threshold applies to each **published nonempty category**, not to
every raw type independently in every cell. With maximum semantic loss 1, all
seven profiles may be truthfully generalized to Road User. A 5 m cell therefore
does not need 35 Road Users merely because there are seven input types. It still
needs at least five distinct Road Users for a nonempty root bin, and exact or
intermediate classes can require more favorable composition.

A longer window can help when different Road Users traverse the same cell. Ten
frames of one Road User do not become ten distinct Road Users. Four seconds
also cannot compensate for a cell that never obtains enough support under any
permitted representation. The seven types are held fixed here; changing the
number of types would be a separate experiment.

Similar outputs from Spatial First and Semantic First can occur when tight
spatial bounds and scarce support force both to their allowed time limit and
the same semantic representation. The priorities remain different algorithms.
Inspect released cuts/bins/intervals and terminal constraints before concluding
that they coincide, and do not generalize one equality to all inputs.

## Read the trade-off fairly

The occupancy workload stays **10 m / 1 s**. Eventual coverage says whether a
query can be answered after releases arrive. Deadline coverage separately asks
whether the release arrived by query end + 0/200/1000 ms, on exactly the prior
fixed cohort. A new four-second release may increase eventual retention while
missing many one-second deadlines or smoothing temporal peaks.

Read retention, query availability, conditional error, spatial/semantic detail
and logical age together. The limit changes the feasible product. It does not
by itself establish a stronger privacy guarantee, and logical aggregation age
is not measured end-to-end execution latency. See the completed
[result and test report](FOUR_SECOND_WINDOW_RESULTS_2026-10-21.md) and the
[exact priority-equality diagnosis](SEMANTIC_SPATIAL_EQUALITY_2026-10-21.md).
