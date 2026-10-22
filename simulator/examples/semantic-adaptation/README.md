# Semantic adaptation: common-window acceptance examples

These frozen sensor inputs exercise the real aggregation, metric, policy and publication
cores. They are small mechanism examples, not a realistic traffic simulation or a privacy
attack experiment. No MongoDB server or renderer is needed for these replay commands.
Child-cyclist labels are explicit synthetic fixture inputs; this does not add a new type
to the default live simulator's behavior profiles.

All cases use an 80 m square at depth 2, measured samples at 100/200/300 ms and one
[0,400) interval. Observation contributions and distinct road users are separate units.
For example, four people observed three times produce 12 contributions and support 4.
The example deliberately restricts publication to depth 2 so semantic effects are clear.
The maintained simulator configuration and depth 6 are unchanged.

| Input/config prefix | Category minimum | Maximum loss | Expected output |
|---|---:|---:|---|
| rare | 5 | 1 | 20 RoadUser; occupancy retained, separate mode counts unknown |
| cyclists | 4 | 0.5 | 4 Cyclist; exact cyclist total, age split unknown |
| strict-loss | 5 | 0.5 | No release; required support and semantic detail cannot both be met here |
| strict-support | 5 | 1 | No release; four distinct people cannot satisfy five |
| exact | 2 | 0 | Exact pedestrian/adult-cyclist/child-cyclist categories |

The public classification catalog is `public-taxonomy.json`. The policy files additionally
contain private-adapter raw label aliases. Terminal loss is 0, the intermediate Cyclist
cost is 0.5, and RoadUser cost is 1. These are declared representation costs, not measured
attack probabilities or validated traffic-task errors.

From the repository root, after the normal build:

```sh
mkdir -p results/semantic-adaptation
./simulator/build/AggregationReplay \
  --input simulator/examples/semantic-adaptation/rare-observations.json \
  --config simulator/examples/semantic-adaptation/rare-policy.json \
  --mode spatial \
  --output results/semantic-adaptation/rare-run.json
ctest --test-dir simulator/build --output-on-failure -R semantic
```

Use matching prefixes for other inputs/policies. Outputs require new filenames and
never replace existing results. The replay file contains PRIVATE diagnostics; only its
`releases` array models recipient output. The generalized `semantic` object never carries
hidden terminal counts, raw types, identities or private node evidence.

The existing general scalar oracle intentionally does not assess these new metrics
without a semantic adapter. The registered `semantic_adaptation_evaluation` tests run
both an independent scalar projection audit and a raw-observation semantic audit.
`semantic_publication_store` additionally tests the actual pipeline through isolated
MongoDB persistence, lost acknowledgement and recovery. It uses only UUID test databases.

See [the model and formulas](../../../docs/SEMANTIC_ADAPTATION.md) and
[the test report](../../../docs/SEMANTIC_ADAPTATION_TEST_REPORT_2026-10-21.md).
