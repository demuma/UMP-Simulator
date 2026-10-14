# Bounded history and logical candidate buckets

Status: 2026-10-14. Initial A02 private history and logical buckets implemented and verified.
This adds private reconstruction to the existing fixed-window path. A05 still owns
publication reservations/commit history; A03 owns action selection and metric-ready states.

## Ownership and integration

An opt-in AggregationHistory belongs to AggregationManager and receives the same validated
identity-bearing observation batches. It owns chronological sample bins (one complete sensor
sample per bin), never Agent/Quadtree pointers or SharedBuffer frames. Missing samples stay
implicit; a measured-empty bin proves zero occupancy throughout the declared sensor domain.
An unavailable bin does not. Existing fixed-window output is preserved.

Active and preemptive buckets are small logical records over this common history. Their key
is cell ID/depth, start time and generation inside a run/sensor/application-scoped history.
Each records an exclusive end, a maximum extension end, a fixed retention deadline and role.
No payload or cached statistics are copied per bucket. Preemptive records are alternatives,
not publication owners; overlapping private candidates are allowed. Creating an alternative
does not reserve any public coverage. The A03 selector performs on-demand parent search; the temporal controller reconstructs variable windows from the same history. Automatic prewarming remains disabled.

Start with on-demand reconstruction. No interval tree is required for bounded chronological
bins and one-cell interval queries. This baseline scans retained bins/observations; a spatial
index or prepared ancestor cache needs measurements under E05. An uncached ancestor remains
queryable as long as its complete requested interval is retained and closed.

## Geometry and interval semantics

Reuse the existing quadtree convention: depth-1 cells are IDs 12..15; the synthetic depth-0
root is not a supported data cell. Maximum depth is 14. Validate ID/path-derived geometry
before retaining observations. A request may select a leaf or any representable ancestor;
three relative levels cover 4^3 = 64 finest-cell areas, without requiring 64 bucket copies.
Mixed-depth alternatives use the same finest observations. No below-leaf reconstruction.

Queries use half-open [start,end) intervals in integer simulation milliseconds. All query
boundaries are explicit; sampled occupancy weights each scheduled measured observation
equally, as in A01. This does not assume continuous occupancy between samples. Expected
samples use the declared period and exclude t=0. A sample at end belongs to the suffix.
Queries report complete, incomplete or no_scheduled_samples with observed counts; future
and evicted intervals return no candidate. An evicted prefix is never relabelled as missing
input or zero occupancy. Zero-support cells are explicitly returned for a requested footprint.

Counts are rebuilt from actual bins. Contributor support is an exact union across both
space and time; child distinct counts are never summed. Type counts count observations,
not unique people. The reconstructed candidate's totals refer to its requested cell, while
its grid retains the stream domain for policy lookup. Querying does not consume history
or change any sibling interval. Different sibling starts/durations therefore do not force
a historical parent to wait for those siblings' current buckets.

## Bounds, progress and lifecycle

Time advances monotonically. As in A01, advance(t) seals observations strictly before t
and permits one subsequent on-cadence sample at t. Query end must be <= that watermark.
Retention is a fixed lookback horizon: discard bins strictly before max(0,t-retention_ms).
The earliest retained boundary advances even across missing observations.

Each bucket must satisfy start < end <= max_end <= retain_until <= start+retention_ms.
Its start must still be retained when registered. A bucket is COLLECTING before its end,
and CLOSED once the watermark reaches its end; CLOSED is not metric-ready or published.
Extension changes only end within max_end, preserves the original start and deadline, and
can return a closed record to collecting. Deadlines are inclusive for evaluation; on the
first advance beyond retain_until the record expires and is removed before reclamation.
Live records therefore never point into an evicted prefix. Discarding a record does not
consume shared observations. Publication states READY/SEALED/COMMITTED/SUPPRESSED and
commit-driven invalidation belong to A03/A05 and are not simulated by these private states.

Explicit positive budgets cover retention duration, retained sample bins, observations,
contributor/type string bytes and live bucket records. String-byte accounting is a logical
payload bound, not an allocator/RSS measurement. Capacity checks account for bins that would
expire at the incoming time. Invalid input or capacity failure is rejected before history
mutation or fixed-window emission. Budget exhaustion is a fatal explicit error in the
simulator, never silent record dropping. Closed-run history remains bounded and queryable
until the manager is destroyed; it is not persisted as a restart checkpoint.

No early reclamation or unlimited pinning is needed in this first fixed-lookback design:
bucket deadlines fit the retention horizon. A future output retry must carry sealed owned
values or have its own bounded reservation contract. Reconstructing already-published
support for private analysis is possible; approving it again requires A05's release ledger.
Deleting database records cannot retract earlier disclosure.

## Configuration

Under an enabled AGBS aggregation, opt in explicitly:

```yaml
history:
  retention_ms: 2000
  max_bins: 32
  max_observations: 100000
  max_identity_bytes: 16000000
  max_buckets: 128
```

All keys are required; unknown/duplicate keys are rejected. Retention must cover at least
the configured fixed window and be a sampling-period multiple. These are resource limits,
not privacy policy thresholds. Omitting history keeps the previous fixed-window-only path.
The configuration exposes no inert preemptive-depth or publication-model switches.

## Worked reconstruction

In [0,400), samples at 100/200/300 ms contain A in leaf L, A+B in L, then A in sibling R.
L has two distinct contributors and R one. Their parent has four contributions and two
distinct contributors, not three. Its mean sampled occupancy is 4/3. Measured-empty other
siblings are covered by the complete sensor samples and do not require physical records.
At 400 ms a new observation belongs to [400,...); rebuilding [0,400) excludes it. Extending
the parent to [0,600) includes 400/500-ms samples without changing either leaf bucket's
start or releasing any data. A later parent beyond a prepared range is the same history
query; unavailable history, unsupported geometry and policy failure remain separate issues.


## API and current integration

`AggregationHistory.hpp/.cpp` contains standard-C++ storage, geometry helpers and logical
records. `AggregationConfiguration.hpp/.cpp` parses explicit YAML limits; Simulation checks
their stream compatibility before database initialization. AggregationManager appends input
once before fixed-window emission, with history geometry/budgets validated before mutation.
Its const `history()` view supports inspection/query; manager `openBucket`, `extendBucket`
and `discardBucket` methods mutate logical records. Disabled streams return a null view.
No new thread, buffer reader or database readback is added.

For example, for a depth-3 parent ID 192 in a depth-4 stream:

```cpp
ump::BucketKey key{192, 3, 0, 1};
manager.openBucket({key, 400, 800, 1000, ump::BucketRole::Preemptive});
// After observations and advance(400):
auto query = manager.history()->queryBucket(key);
if (query.status == ump::HistoryQueryStatus::Complete) {
    auto assessment = evaluator.evaluate(*query.candidate, 400);
    // Record assessment; public release still needs A05 coordination.
}
manager.extendBucket(key, 600); // Same start/deadline; end grows within maxEndMs.
```

The main fixed-window sink still receives its original leaf candidates. With
`aggregation.spatial_selection` enabled, its callback also invokes the standard-C++
[spatial selector](SPATIAL_SELECTION.md), which queries parents on demand and emits a private
mixed-depth cut. It does not automatically register/prewarm logical buckets or publish output.
The regional example enables actual sample retention; no history block means no history
copying. Read-only debug counters expose retained bins, observations, string bytes, live
records and expired-record count, without contributor identities.

## Verification — 2026-10-14

All eight CTest suites passed. HistoryRegressionTests also compiled and passed with C++17,
`-Wall -Wextra -Werror` and no SFML/YAML/MongoDB dependency. It covers the worked union case,
source ownership, interval endpoints, independent sibling windows, temporal extension,
known-empty regions, missing/unavailable samples, region-policy evaluation, invalid input,
deadline cleanup and each budget. Invalid history input cannot emit an earlier fixed window.
A 300-step deterministic replay compared 1,200 queries at four spatial depths with an
independent rectangle/time oracle, including missing and unavailable samples. At most five
bins/twenty observations were retained, independent of elapsed run length.

SensorRegressionTests enables history on the real 10-Hz AGBS while leaving the 5-Hz stream
without history. After three fixed windows close it reconstructs [0,950) from nine complete
sensor samples: nine contributions, two distinct contributors, mean occupancy one. Empty
samples and an empty sibling remain covered; existing MongoDB/frame checks still pass.

The full headless example with history, two regional policies and 200 agents produced five
v3 fixed windows. An independent check verified 316 cell assessments (174 pass, 142 fail).
Fourteen invalid policy/history configurations preserved a disposable DB sentinel and wrote
no metadata. All integration databases were UUID-named and removed; the maintained YAML
and existing Simulation DB were untouched. These checks establish functional behavior,
not a runtime benchmark, privacy improvement or utility experiment.

```bash
cmake -S simulator -B simulator/build -DCMAKE_BUILD_TYPE=Release
cmake --build simulator/build -j 4
ctest --test-dir simulator/build -R history_regression --output-on-failure
```

Enable the optional sensor integration suite with `-DUMP_BUILD_SENSOR_REGRESSION_TESTS=ON`
and local MongoDB. The normal simulator build was updated as well.


## Variable-window reconstruction

`queryFinest(startMs, endMs)` scans retained bins once and reconstructs occupied finest
cells plus a separate whole-domain identity union. A road user seen in two cells counts
once globally, even though each cell can include that identity. Expected/measured/missing
samples and half-open endpoints follow `query`. Future or evicted intervals return no
candidate; missing coverage remains explicit. No raw identities leave the returned candidate.

The manager's progress callback runs after advancing history on every tick and once with
`finishing=true` at the exclusive stream end. Final advancement does not first send an
ordinary progress callback, so no extension beyond shutdown is scheduled. These callbacks
only query history and never reenter manager mutation. A03 shares this store rather than
subscribing to SharedBuffer or retaining a second observation history.
