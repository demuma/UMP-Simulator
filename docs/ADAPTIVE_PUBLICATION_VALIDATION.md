# A05/A03 validation record

Date: 2026-10-14. These are implementation correctness checks, not privacy/utility results.

## Automated coverage

Thirteen CTest suites passed, including existing sensor/frame/playback/policy/history tests,
the coordinator suite, the new temporal suite, MongoDB store tests and the complete
publication pipeline suite. Six Python inspector tests passed. New core/store tests were
also compiled independently with C++17 and `-Wall -Wextra -Werror` during development.

The deterministic strategy fixture uses identical observations for both strategies:
Temporal First releases a spatially merged `[0,400)` interval; Spatial First retains fine
cells and releases `[0,500)`. Final intervals end at 550 ms. Both account for the same ten
observation contributions, without parent/child reuse or overlapping retired intervals.
Other cases cover exact cross-cell/time identity unions, early completion, strict regional
bounds in empty footprints, partial/exact shutdown, missing measurements, private empty
retirement, retry failure and read-only recovery after lost acknowledgement.

## Running-simulator evidence

Each headless capture used 200 road users, depth six, 10-Hz sensing, 50-ms simulation ticks
and a four-second exclusive end. Only fresh UUID test databases were used and removed.
The user configuration and `Simulation` reference database were not run or modified.

| Mode | Final intervals | Durations | Recipient documents | Observation contributions |
|---|---:|---|---:|---:|
| Fixed-window publication | 10 | 400 ms | 10 | 7,800 |
| Temporal First | 10 | 400 ms | 10 | 7,800 |
| Spatial First | 4 | 1,000 ms | 4 | 7,800 |

For every interval, journal state was committed, public cells/counts exactly matched selected
private decisions, no suppressed/type/global count fields were exposed, and interval coverage
was contiguous from zero to 4,000 ms. Raw-window contributions equaled adaptive-window
contributions. These random runs are separate input realizations, not controlled comparisons
of algorithm quality. Wall times of roughly 0.57–0.77 seconds are smoke-run observations,
not a performance benchmark; rendering was disabled.

Two negative startup cases (mismatched base-cell size and empty diagnostic directory) were
run with clearing enabled against fresh empty test namespaces. Both failed before creating
any collections. The underlying geometry/timing validator is shared by preflight and AGBS.

Local capture configurations, JSONL files, MongoDB exports, logs and verification summary
are retained in `results/validation/a05-a03-2026-10-14/` (ignored generated artifacts).
Source tests and opt-in examples are versioned. The corresponding databases were deleted.

## Reproduction

```sh
cmake -S simulator -B simulator/build \
  -DUMP_BUILD_SENSOR_REGRESSION_TESTS=ON \
  -DUMP_BUILD_PUBLICATION_STORE_TESTS=ON
cmake --build simulator/build -j6
ctest --test-dir simulator/build --output-on-failure
python3 -m unittest discover -s tools/aggregation_inspector -p 'test_*.py'
```

MongoDB suites require localhost:27017 and clean up only their fresh UUID databases. The
maintained `publication` and `temporal-aggregation` examples run the actual simulator with
separate raw/release/journal destinations and clearing disabled. Live-renderer controls
are preserved; this change's validation used headless simulation and did not repeat the
previous native-window visual inspection.

Remaining evidence: equal-input baseline experiments, GT utility reconstruction, a stated
attacker model and empirical privacy metrics, policy-feasibility analysis, meaningful
runtime/memory comparisons, and independent regional coordination behavior.
