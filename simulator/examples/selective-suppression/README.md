# Selective suppression: deterministic A07 replay

This is a hand-worked mechanism example, not a realistic traffic scene or a privacy
experiment. It uses the actual common-window aggregation and publication cores.
No renderer, MongoDB connection or simulation run is required.

The 80 m square has depth 2. Cell 48 (20 m side) contains road users a,b; cell 49 contains c.
At 100/200/300 ms the same three people are observed. The interval [0,400) therefore
contains 9 observation contributions and 3 distinct road users. Every released cell
requires at least 2 distinct road users and a maximum side of 20 m. Parent 12 is 40 m wide
and fails the size constraint. With the option enabled, cell 48 retains 6 contributions
from 2 people; cell 49's 3 contributions are suppressed. The public output has no parent
total or suppressed-cell count. The original option-disabled baseline releases none.

From the repository root, after the normal CMake build:

```sh
mkdir -p results/selective-suppression
./simulator/build/AggregationReplay \
  --input simulator/examples/selective-suppression/observations.json \
  --config simulator/examples/selective-suppression/policy.json \
  --mode spatial \
  --output results/selective-suppression/example.json
python3 -B tools/evaluation/run_oracle.py \
  --input simulator/examples/selective-suppression/observations.json \
  --config simulator/examples/selective-suppression/policy.json \
  --result results/selective-suppression/example.json \
  --output results/selective-suppression/audit.json \
  --analyze-small
```

Both commands require new output filenames and never replace existing files. Use a
fresh directory/filenames to repeat. The replay file contains PRIVATE diagnostics
as well as its `releases` array; only the latter models the recipient payload.
Missing public cells are unknown, not certified zero.

Set `spatial_selection.preserve_valid_descendants` to false in a separate copy of the
policy to compare the baseline, keeping every threshold and observation identical.
Use maximum cell side 40 m instead to verify the legal parent retains all 9 contributions.
The first development step leaves the maintained simulator config and depth 6 unchanged;
depth 2 here is deliberate so the reference case is easy to inspect mathematically.

See the [contract](../../../docs/SELECTIVE_DESCENDANT_RESCUE.md) and
[test report](../../../docs/SELECTIVE_DESCENDANT_RESCUE_TEST_REPORT_2026-10-21.md).
