# Local policies on a few finest leaves

This is a deterministic **analytical mechanism fixture**, not a realistic street simulation or an anonymized public data export. It contains 20 stable synthetic identities in 19 complete 100-ms samples over two seconds. The same coordinates and types are used by all four policies.

Four 2.5 × 2.5 m patches affect **16 of the 4096 possible depth-6 leaves** in an 80 × 80 m area. They demonstrate local semantic support, an intermediate Pedestrian category, a Cyclist sibling merge, unresolved support, and a stricter **empty** region constraining an intersecting coarse cell.

From the repository root, run a single case into a new output filename:

```sh
./simulator/build/AggregationReplay \
  --input simulator/examples/local-policies/observations.json \
  --config simulator/examples/local-policies/local_temporal-policy.json \
  --mode semantic_first \
  --output /private/tmp/local-policy-example-result.json
```

Or reproduce the complete frozen four-variant study into a new directory:

```sh
python3 -B tools/evaluation/run_local_policy_replay.py \
  --output results/local-leaf-policy-rerun \
  --binary simulator/build/AggregationReplay
```

The runner refuses an existing output directory, archives the executable and protocol before execution, independently audits all four outputs, and repeats one case exactly apart from runtime. No MongoDB or live simulator is started.

`uniform_temporal` and `uniform_spatial` use the root policy. `local_temporal` and `local_spatial` add the same four patches. All use Semantic First, the indicated second priority, and `release_trigger: policy_satisfied`. Identical outputs between second priorities are expected in this fixture.

The uniform root retains all 380 observation contributions with 400-ms releases. The local policy retains 285 (75%), uses Pedestrian for the mixed-age pedestrian group, merges two cyclist leaves into a 2.5-m Cyclist cell, and suppresses five identities' contributions. The final published intervals are 600, 600, 600 and 200 ms.

**Important limitation:** these are still common windows. The empty patch's 600-ms time bound caps every shared interval; the valid control groups wait alongside the failing groups. This is an explicit integration gap, not independent regional temporal adaptation. Fine control cells keep their root requirements and exact semantic types, but their release timing is coupled to the shared controller.

Read the [predeclared protocol](../../../docs/LOCAL_LEAF_POLICY_PROTOCOL_2026-10-22.md) and [results and tests](../../../docs/LOCAL_LEAF_POLICY_RESULTS_2026-10-22.md). Raw fixture identities and original types belong to the private research/debug view; only released semantic categories describe the recipient output.
