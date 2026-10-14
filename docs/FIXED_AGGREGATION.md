# Fixed aggregation input and candidate contract

Status: 2026-10-13. A01 implementation contract. This is the first fixed-window
foundation, not the adaptive release protocol in [BUCKET_LIFECYCLE.md](BUCKET_LIFECYCLE.md).
Implementation and verification status is recorded in TO-DO and README. The subsequent
[metric contract](METRICS.md) adds a separate evaluator and versioned threshold assessments
to diagnostics. A04's [regional tree](POLICY_TREE.md) now supplies inherited requirements
and per-cell policy provenance in schema v3; the fixed-window core and its count semantics
are unchanged. A02 now optionally retains fine observations for private reconstruction;
see [AGGREGATION_HISTORY.md](AGGREGATION_HISTORY.md). Public release decisions remain open.

## Scope and ownership

An enabled simulation AGBS owns one AggregationManager for one application stream.
The AGBS adapter copies contributor ID, type and leaf geometry during its existing
capture pass. The core accepts owned value batches; it has no Agent, Quadtree, SFML,
MongoDB, YAML or renderer-buffer dependency. Render-only AGBS instances have no manager.
ABS/GBS adapters and multiple applications per sensor remain future work.

Input capabilities are explicit: fixed leaf-cell support, internal stable contributor
IDs and type attributes; no individual positions in the batch. A batch represents a
complete measurement of the configured square detection area, or explicit unavailability.
One ID can occur at most once per batch. Run ID, sensor ID and increasing sequence number
identify a batch. The manager rejects duplicates, wrong streams, late/off-cadence input,
inconsistent cell geometry and unsupported capabilities instead of silently counting twice.

The initial adapter requires the detection area to equal the quadtree extent
(`width = height = 2 * cell_size`) and uses the existing leaf IDs and configured max_depth.
Empty leaves are implicit within that coverage. A cell ID is scoped by run and sensor;
depth and geometry travel with it. The core does not enumerate Morton-code ancestors.

## Time and completeness

Core times are integer milliseconds relative to the configured simulation origin.
Windows are non-overlapping `[start_ms, end_ms)`, anchored at zero. Window length must be
a positive multiple of the sampling period. The first expected sample is at one period;
t=0 initializes the existing sensor schedule and is not a zero-valued measurement.
The initial adapter supports only whole-millisecond periods aligned with the simulation
step. Other schedules must be corrected under D02/F01 before enabling aggregation.

`ingest(batch)` advances to its observation time and adds it to the appropriate window.
`advance(now)` declares observations strictly before now complete and closes elapsed
windows, including on ticks without a measurement. It permits a subsequent sample at
exactly now. `finish(end)` first closes elapsed windows and then emits an explicitly
truncated final window if end lies inside a window. End is exclusive; finish cannot
discard an already ingested observation at that timestamp. Empty trailing windows are
reported too. A normal/cancelled run ends at the next state boundary after its last
processed tick. No artificial endpoint sample is generated.

Each output reports expected, measured, explicitly unavailable and missing sample counts.
No sample due contributes to none of those counts. A due measured-empty batch increments
measured samples and means zero occupancy everywhere in the declared coverage. Missing
or unavailable measurements never become zero observations. Completeness is one of
`complete`, `incomplete`, or `no_scheduled_samples`; a truncated final interval can still
contain all samples expected within that shorter interval.

## Count definitions and worked example

For each occupied cell and the whole stream window:

- `observation_contributions`: sum of detected agents over measured samples.
- `distinct_contributors`: number of different internal IDs in that support/window.
- `type_observation_contributions`: contributions grouped by the observed type.
- `mean_sample_occupancy`: contributions / measured samples, including measured-empty
  samples and zero occupancy in absent cells. Undefined if there are no measurements.

This mean is a sample mean, not continuous-time average occupancy or a count of people
who visited between measurements. Stream distinct counts use a union across cells; cell
distinct counts must not be summed. Type contributions are not distinct people per type.
Input batch occupancy is instantaneous occupancy at an observation time.

For a 100-ms sensor and window `[0,400)`: at 100 ms A is in cell 1; at 200 ms A and B
are in cell 1; at 300 ms A moves to cell 2. There are three expected/measured samples,
four contributions and two distinct contributors. Cell 1 has three contributions,
two distinct contributors and mean sample occupancy 1. Cell 2 has one contribution,
one distinct contributor and mean 1/3. The stream mean is 4/3. A sample at 400 ms belongs
to the next window. Replacing the 300-ms sample with a measured-empty batch gives three
contributions and mean 1; omitting it makes the window incomplete, not empty.

Distinct support is a descriptive statistic. It is not a proof of anonymity or improved
privacy. Sample mean occupancy is not an application utility score.

## Output, bounds and failures

The external synchronous sink receives one fixed-window candidate at closure. It has no
contributor IDs, individual positions or publication approval field. JSONL diagnostics
contain run/sensor/application keys, the original simulation timestamp, coverage, exact
relative window, counts, completeness and closure time. `simulation_origin` uses BSON
Extended JSON date notation; adding the relative millisecond fields gives observation
intervals on the existing sensor/GT timeline. Existing datetime parsing limitations remain D02. They remain internal research data; removing IDs does not approve release.
Raw sensor MongoDB records and typed renderer samples keep their existing schemas.

There is one active window per manager. Its observation budget is explicit and positive;
exceeding it aborts with an error rather than dropping people or declaring privacy success.
Memory grows with occupied cells and distinct contributors in this one window, not run
length. A synchronous sink prevents an unbounded completed-output queue. Sink/file errors
abort the run; there is no durable retry or exactly-once guarantee across process failure.
Closing the fixed window discards its accumulator ID sets. Without A02 history this also
discards reconstruction input. With `history` enabled, a separately bounded sample store
retains owned observations across closure; logical active/preemptive candidates reference
that store. Fixed output remains unchanged. Automatic merges and public release records
are not implemented. Policies evaluate outputs through the separate A04/E04 path.

## Configuration

Add this optional block to a simulation AGBS entry in a **copy** of config.yaml:

```yaml
aggregation:
  enabled: true
  application_id: fixed-baseline
  window_ms: 1000
  max_observations_per_window: 1000000
  diagnostics_directory: results/aggregation
```

These are demonstration parameters, not justified privacy thresholds. No block means no
manager and no identity-copying overhead. Each enabled stream writes a new UUID-named
JSONL file and prints its path. The existing `clear_database` setting still controls raw
MongoDB collection deletion: use a separate research database for experiments.

Window keys are `(run_id, sensor_id, application_id, start_ms, end_ms)`; cell keys additionally
include depth and cell ID. Public release IDs/generations belong to the later release protocol.
Read-only debug state reports the active interval, measured sample count and retained cells/
identity memberships without exposing contributor IDs. Core callbacks run synchronously
on the simulation thread and must not reenter the manager.
