# Semantic First: common-window examples

These historical example policies now explicitly use `priority_satisfied` to
reproduce their original waiting behavior under the new semantic default.
See [new release-control examples](../semantic-release/README.md).

These complete frozen JSON observation/policy pairs run the real core without MongoDB
or a renderer. All use the same public catalog, category minimum 5, hard loss maximum 1,
20 m source leaves, permitted 40 m parents and 400/800-ms base/maximum windows. The same
people recur, so repeated observations cannot increase distinct support.

| Pair | Road users per source leaf | Expected first result |
|---|---|---|
| low | 2 Pedestrian + 1 AdultCyclist + 1 ChildCyclist | Wait to 800 ms, then 40 m Pedestrian 8 + Cyclist 8; loss 0.5 |
| medium | 4 Pedestrian + 2 AdultCyclist + 2 ChildCyclist | Exact 40 m parent at 400 ms; supports 16/8/8; loss 0 |
| high | 10 Pedestrian + 5 AdultCyclist + 5 ChildCyclist | Exact 20 m leaves at 400 ms; supports 10/5/5; loss 0 |

Support counts are distinct road users, not observation totals. The medium first window
contains 96 observations (three samples of 32 people). These controlled static inputs do
not represent a street trajectory model or measured privacy improvement. Production
observation depth 6 and the default simulator configuration are unchanged.

From the repository root after building, choose a NEW output filename:

```sh
./simulator/build/AggregationReplay \
  --input simulator/examples/semantic-first/medium-observations.json \
  --config simulator/examples/semantic-first/medium-policy.json \
  --mode semantic_first \
  --output /private/tmp/ump-semantic-first-medium-new.json
```

Use matching low/high filenames for the other cases. The replay result is PRIVATE:
its windows include hard checks, failed source cells and semantic_priority diagnostics.
Only the releases array models recipient-visible output. Preference metadata and hidden
source evidence must not be copied to that channel. Missing input, no taxonomy or
cell-local coordination reject explicitly; semantic_first requires temporal settings.

The configured mode preserves maximum declared semantic accuracy first and uses Temporal
First as its secondary priority. Zero-loss spatial alternatives are tried before waiting;
positive-cost fallback is allowed only at a terminal endpoint under the original bounds.
Mean loss remains a hard constraint when configured, not a second optimized objective.
A zero-cost internal category is valid in the general taxonomy API.

See the [contract](../../../docs/SEMANTIC_FIRST_IMPLEMENTATION.md),
[27-case comparison](../../../docs/SEMANTIC_FIRST_RESULTS_2026-10-21.md) and
[test report](../../../docs/SEMANTIC_FIRST_TEST_REPORT_2026-10-21.md).
