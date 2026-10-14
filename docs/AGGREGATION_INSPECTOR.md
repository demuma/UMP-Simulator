# Aggregation inspector

Implemented on 2026-10-14 as the first offline inspection slice of A06, brought forward
for the supervisor meeting. The simulator records the metrics and regional requirements;
the inspector displays those recorded assessments. It does not run the policy evaluator
again or generate an adaptive decision.

## Open the prepared demonstration

From the repository root:

```sh
open results/demos/aggregation-inspector.html
```

This is a self-contained HTML file. It opens directly in Safari without a server,
Internet access, a running simulator or a MongoDB connection. Its controls select cells,
move through recorded windows and play/pause the recording. Playback advances one stored
window every 700 ms; it is presentation playback, not real-time simulation performance.

The prepared local run contains 30 consecutive 400-ms windows over 12 seconds, 200 agents
and an 80 × 80 m observation area with 10-m candidate cells. The source is an actual run
of the maintained simulator, based on `simulator/examples/regional-policy/config.yaml`.
The duration, agent count, simulation date and disposable capture database were adjusted
in a separate configuration; the maintained simulator configuration was not edited.

Local artifacts, excluded from Git under `results/`:

| File | Purpose |
|---|---|
| `results/demos/aggregation-inspector.html` | Ready-to-open presentation file, with embedded diagnostics |
| `results/demos/candidates.jsonl` | Original candidate records used by the report |
| `results/demos/capture-config.yaml` | Exact capture configuration, including its disposable database name |

The capture database was removed after export. The optional debug copy described below
remains available. This recording is a functional demonstration, not a controlled privacy/
utility experiment: the current simulator does not supply a common random seed.

## A three-minute walkthrough

1. Explain the implemented path at the top: observations → cell and time window →
   metric values and effective policy requirements → recorded threshold checks.
2. At window 1, select **Show support failure**. Cell 192 has four distinct observed
   contributors; the western region requires at least five. The panel shows the actual
   value, required bound, inherited rule sources and effective policy ID. The region's
   configured minimum of two cannot weaken its type's inherited minimum of five.
3. Select **Show duration failure**. Cell 208 has four contributors and passes its minimum
   of one, but its 400-ms window exceeds the northeastern region's 200-ms limit. This is
   a useful example of sufficient support still failing an application constraint.
4. Select **Show passing cell**. Cell 194 has six contributors and meets the western
   requirements in the first window. Move forward or press **Play** to see its measured
   values and check results change. The selected cell identity is retained across windows.
5. Expand **All recorded metrics, including unavailable values**. Explain that occupancy
   MAE needs a separate ground-truth comparison and is explicitly unavailable here.
   A missing value is never presented as zero error.

These cell IDs and values describe the prepared recording. A new randomized run will
produce different counts; the example-selection buttons find matching cases in the
currently displayed window and disable themselves when no such case exists.

Green means that the configured candidate requirements were met. It is not a public release
or proof of privacy. Distinct observed contributor support is an operational count, not
a demonstrated anonymity guarantee. Red identifies a violated bound; yellow identifies
an unavailable assessment. Grey means no stored candidate or no configured requirements.
Unobserved areas are not silently classified as approved. The map uses recorded cell
geometry; the policy sources are shown for the selected cell, without inventing region
boundaries from the subset of cells that happened to have observations.

## Generate a report from another run

The builder uses Python 3's standard library and accepts one or more candidate JSONL files:

```sh
python3 tools/aggregation_inspector/build_report.py \
  simulator/examples/regional-policy/results/aggregation/candidates-*.jsonl \
  --output results/demos/regional-policy.html
open results/demos/regional-policy.html
```

Run the [regional example](../simulator/examples/regional-policy/config.yaml) first if
that input directory is empty. Multiple runs, sensors or applications appear as separate
streams in the inspector. Windows are sorted within each stream. Use the generated
report, not `tools/aggregation_inspector/inspector.html`, which is a template.

Input must use schema `ump.fixed-candidate.v3` and role `internal_research_candidate`.
The builder rejects duplicate window keys, invalid geometry and empty inputs. It embeds
the original metric values, bounds, unavailable reasons and provenance without changing
the source files. Input filenames and SHA-256 hashes are included in the report; hover
over the run/schema label to see them. No external scripts or fonts are loaded.

An incomplete coverage gate makes the overall cell assessment unavailable, even when
individual numeric comparisons pass. If the selected cell has no candidate in another
window, its panel explicitly reports that absence instead of retaining old measurements.

## Optional MongoDB debug copy

The simulator already writes these fields to JSONL. No extra synchronous database write
has been added to the simulation loop. To inspect the same diagnostics in MongoDB,
explicitly request a separate local debug import:

```sh
python3 tools/aggregation_inspector/build_report.py \
  results/demos/candidates.jsonl \
  --output results/demos/aggregation-inspector.html \
  --mongo-database UMP_Debug_AutSys
```

This requires the installed `mongoimport` executable and targets
`localhost:27017`, database `UMP_Debug_AutSys`, collection `aggregation_candidates`.
The prepared recording has already been imported. One document represents one candidate
window; `cells` contains all its cell assessments. Useful fields are:

- `run_id`, `sensor_id`, `application_id`, `start_ms`, `end_ms` and `assessment`;
- `cells.cell_id`, cell geometry and `cells.threshold_status`;
- `cells.metrics`, with measured values, units and unavailable reasons;
- `cells.checks`, with observed values, effective minimum/maximum and check result;
- `cells.policy`, with effective policy ID, contributing sources and feasibility.

For example, in MongoDB Compass select `UMP_Debug_AutSys.aggregation_candidates` and use:

```json
{"run_id":"87094218-20EE-47F0-BFC8-1881E644CE0D","start_ms":0}
```

The import only permits database names beginning with `UMP_Debug`. It upserts by the
run/sensor/application/window key, so repeating a debug import replaces the same debug
document. It does not clear the collection or alter raw sensor collections. These are
internal research records, not application-visible releases. A concurrent import workflow,
access control and a live MongoDB diagnostics sink are outside this first tool's scope.

## Verification and remaining work

The capture's 1,725 cell assessments across 30 windows were checked against independently
derived regional bounds: 988 met their configured requirements and 737 violated at least
one. These counts describe repeated cell-window assessments, not unique people or cells.
The debug MongoDB copy was checked against the capture's run and assessment totals.

Builder regression checks cover diagnostic round-trip fidelity, unavailable values,
HTML-safe metadata, duplicate/schema/geometry rejection and debug-only MongoDB routing:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tools/aggregation_inspector -p 'test_*.py' -v
```

The JavaScript passed a syntax check. Native Safari inspection verified local-file loading,
support/duration/passing examples, timeline navigation and playback through the final
window. This slice changes no simulator C++ code or sensor scheduling.

The next core task remains A05 publication coordination, followed by A03 automatic spatial/
temporal selection. The separate SFML overlay for collecting/preemptive buckets, proposed
parents, suppression and actual releases remains under A06. The present recording shows
fixed candidate assessment; it does not animate a merge/split algorithm that is not yet
connected to release decisions.
