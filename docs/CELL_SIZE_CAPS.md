# Compare maximum permitted output-cell sizes

This experiment reuses the recorded movements and changes the maximum output
cell side, not the area, sensor resolution or participant population. Protocol:
[predeclared cap study](CELL_SIZE_CAP_PROTOCOL_2026-10-21.md). Existing capture,
query and viewer contracts: [moving replay](MOVING_REPLAY.md).

Run from the repository root with an already verified capture. Each output
directory must be new. The default `--max-cell-side-m 40` retains the original
moving-pilot matrix; choosing 10 or 5 creates its own policy and baseline matrix.

```sh
python3 -B tools/evaluation/run_moving_comparison.py \
  --capture results/moving-replay-2026-10-21/n500/capture \
  --max-cell-side-m 10 \
  --output results/cell-size-caps-2026-10-21/cap10/n500/comparison \
  --timeout 180

python3 -B tools/evaluation/run_moving_comparison.py \
  --capture results/moving-replay-2026-10-21/n500/capture \
  --max-cell-side-m 5 \
  --output results/cell-size-caps-2026-10-21/cap5/n500/comparison \
  --timeout 180
```

Repeat for n200 and n1000 using their own capture and new output paths. There is
no new simulator execution or MongoDB access. Do not alter the normal simulator
configuration or overwrite the completed 40 m bundles.

Validate and view one cap bundle at a time:

```sh
python3 tools/replay_viewer/serve.py \
  --bundle results/cell-size-caps-2026-10-21/cap10/n500/comparison --check

python3 tools/replay_viewer/serve.py \
  --bundle results/cell-size-caps-2026-10-21/cap10/n500/comparison --port 8766
```

Open `http://127.0.0.1:8766/`. Use the cap5 path and another port for a second
viewer. Each individual bundle compares its six fixed grid/window settings and three
adaptive strategies on one shared input. Additional `viewer-n200`, `viewer-n500`
and `viewer-n1000` bundles combine the actual adaptive results across 40/10/5 m
on the same source. For a direct cap comparison, run:

```sh
python3 -B tools/replay_viewer/serve.py \
  --bundle results/cell-size-caps-2026-10-21/viewer-n500 --port 8768
```

Open http://127.0.0.1:8768/. The initial selections compare Temporal First at
10 m and 5 m; 40 m and other priorities remain selectable. These are copied
actual results, not newly generated animations.

Check suppression alongside published cells. At unchanged support thresholds,
a smaller spatial cap leaves fewer opportunities for merging. Temporal extension
can add distinct support only when new identities contribute; semantic
generalization can pool categories but cannot create Road Users. If no allowed
representation passes, suppression is the expected safe action. The study
measures this cost rather than assuming that 5 m must outperform 10 m or 40 m.

Measured results and test scope: [cell-size cap report](CELL_SIZE_CAP_RESULTS_2026-10-21.md).
