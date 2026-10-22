# Semantic release-control examples

These small, declared acceptance fixtures run the real replay core without MongoDB.
They are not captures from the motion simulator. Adult/Child Scooter labels exist
only in the controlled test taxonomy; no new motion/behavior profile is introduced.

- `intermediate`: each of the three families has two adult and three child Road
  Users in one cell. The implicit policy-satisfied trigger publishes Pedestrian,
  Cyclist and Scooter at 400 ms, all with support 5 and declared loss .5, although
  Root loss 1 is allowed. The finest cell and interval/count information remain.
- `turnover`: two cells initially have four adults in each of three families;
  another identity of each family arrives at 600 ms. Under explicit preference
  waiting, Temporal secondary releases the exact parent at 400 ms, while Spatial
  secondary releases the exact fine cells at 700 ms. Half-open intervals exclude
  observations at their right endpoint. Set `release_trigger: policy_satisfied`
  to release the already legal exact parent at 400 ms under either secondary.

Run from the repository root, choosing a new output filename:

```sh
./simulator/build/AggregationReplay \
  --input simulator/examples/semantic-release/intermediate-observations.json \
  --config simulator/examples/semantic-release/intermediate-policy.json \
  --mode semantic_first --output /private/tmp/ump-semantic-intermediate-new.json
```

For turnover use `turnover-observations.json` with either matching policy file.
Private result diagnostics state effective secondary, trigger and original hard
checks. Only `releases` models recipient output. Local semantic windows remain
unsupported; these examples use common-window coordination.
