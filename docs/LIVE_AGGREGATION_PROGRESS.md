# Live aggregation progress and display layers

Implemented display contract, 2026-10-14.

The renderer must distinguish current sensor geometry, the running aggregation interval,
and the latest completed decision. A completed interval's support counts cannot be presented
as instantaneous occupancy. Previously, only completed decisions reached the display, so
an extended window appeared to cause an unexplained rendering delay.

The new read-only progress attachment carries interval start, next scheduled evaluation,
hard deadline, observation watermark, strategy and collection/extension phase. An immutable
reference to the latest existing finest-cell assessment is retained between checks. That
assessment is explicitly dated and cleared when a new interval starts. The display neither
queries private history nor runs metrics or selection. No new thread, sensor observation,
SharedBuffer subscriber or database write is introduced.

Display layers are independent: H toggles fine AGBS sensor geometry, G toggles completed
aggregation decisions, and P toggles active progress and the latest checked unresolved
cells. S continues controlling sensor areas. Pending checks must not be labeled suppressed
or released. Unknown/unavailable checks remain distinguishable from failed requirements.
Only the existing terminal path can approve output.

The temporal example starts with completed decisions and active progress visible, and
fine sensor geometry hidden. Existing configurations retain their default grid behavior.
Progress travels with real sensor samples, so it is updated at the sampling cadence and
keeps its observation time when held between samples. The final shutdown-only snapshot
still has no subsequent sensor frame; final records remain available in diagnostics.

Verification: temporal-core progress transitions and failure behavior, typed multi-sensor
frame transport and immutable held snapshots, rendering visibility/text semantics, and
native-window inspection on an isolated disposable demo configuration. README and TO-DO
will distinguish implemented display behavior from remaining metric/experiment decisions.


## What is shown

- The completed layer shows selected/suppressed footprints and future-window coarsening/
  refinement. It says "Released output" only after an acknowledged publication commit.
- The active layer shows collecting or extending, preservation strategy, the next candidate
  interval, hard deadline, processed simulation time and planned extension count.
- Before the first scheduled check, it says "First policy check pending". During extension,
  the last checked interval/time and pass/fail/unavailable cell counts remain explicit.
  Checked-window distinct road users are a union over that interval, not current occupancy.
- Thin dashed amber outlines mark failed/unavailable finest-cell checks in the running
  interval. They differ from solid orange coarsened output and red final suppression.
  These checks clear at the next window; the last completed decision remains available.

The status sidebar uses free space left of the map at the normal demo size, wraps long
identifiers/lines, and draws after road users so text stays legible. When there is no side
margin it becomes an overlay. Very small windows or many sensor panels may need a later
scrollable inspector; there is no new GUI layout framework in this slice.

## Configuration and compatibility

```yaml
renderer:
  show_aggregation: true
  show_aggregation_progress: true
  show_sensor_grid: false
```

G/P/H change the respective layer independently. S controls sensor areas; none of G/P/H
requires those areas to be visible. Existing configs without `show_sensor_grid` inherit
the prior initial AGBS grid visibility. An explicit value or the first H press overrides
per-sensor grid flags so the grid can always be enabled. GBS keeps its prior grid gate.
The maintained user `simulator/config.yaml` is not changed. Both opt-in publication examples
now use the new initial layer settings.

Only metadata is refreshed each progress notification; the retained metric evidence is a
shared immutable value from an already executed policy check. No extra history scan or
metric evaluation occurs. Headless simulation skips renderer progress snapshot allocation.
The controller retains at most one current check; bounded frame transport can hold older
immutable diagnostic references until they are consumed.

## Next research decisions

This display explains existing behavior; it does not improve measured privacy. The next
queue in TO-DO puts frozen-input replay ahead of comparative runs, implements the already
specified occupancy/GT utility query, binds the attacker model before choosing a privacy
score, and then compares fixed/spatial/adaptive policies on identical observations.


## Verification record

All fourteen CTest suites passed, including live progress transitions, immutable multi-sensor
frame transport and presentation semantics. Native-window inspection used a separate QA
bundle and three fresh UUID MongoDB databases. The normal demo size showed a readable
wrapped sidebar alongside the map. At processed time 1,600 ms it correctly distinguished
released `[0,1000)` output from active `[1000,1700)` next-check support, a 2,000-ms deadline,
and the dated `[1000,1600)` check. H revealed the black input subdivisions without changing
G/P; hiding H/G/S retained active amber checks; hiding P and enabling G retained only the
completed cut even with sensor areas hidden. Pausing kept the timestamps fixed.

The QA application was closed and only its three disposable test databases were removed.
Local logs/configuration/selection evidence is retained under
`results/validation/live-progress-2026-10-14/`. The existing user application and main
configuration were not operated or changed. No privacy/utility experiment is claimed.
