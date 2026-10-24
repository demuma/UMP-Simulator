# Strategy, paced timing and one local temporal constraint — 25 October 2026

## Ordered execution contract

The user authorized the following sequence after the handoff correction:
complete the missing strategy/fixed-window comparisons, repeat isolated paced
processing with the corrected engine, then investigate one heterogeneous
application-policy factor. Prepare and test tooling first. Freeze each protocol
before its first native invocation. Native timing jobs run serially, without
builds, simulations, rendering, other benchmarks or intentionally scheduled heavy
work. Preserve failures and all historical studies; never change a queue, source
rate, threshold or output after seeing its result to manufacture a pass.

All maintained documentation is English. Generated movement and full native
results stay under ignored local `results/`. Only code, tests, exact policies,
compact aggregate reports and provenance receipts are eligible for Git.
The unrelated presentation edits and untracked `output/` directory are excluded.

## Phase 1: missing strategy and matched fixed-window envelope

Use the two complete, frozen 300 s observation streams from the verified
Spatial20 correction study. Do not regenerate, filter or shorten movement.
For both Original and Spatial20 numeric contracts, execute:

- Standalone `temporal_first`, suppression OFF, cell-local coordination.
- Fixed 5, 10 and 20 m at 2000 and 4000 ms, suppression OFF.

This is 28 new cases: two sources × two contracts × seven methods. Retain the
verified corrected Semantic First/Spatial First and fixed 400/1000 ms references
with their source/configuration/binary hashes. The former references use the same
corrected engine; all hard root/regional metric bounds and taxonomy remain equal.
Only method/application identifiers and execution strategy differ. Fixed CLI
window choices do not replace policy duration/age bounds.

Naming follows the user's convention: Temporal First preserves temporal detail
and admits spatial coarsening before waiting. Spatial First preserves spatial
detail and extends time first. Semantic First orders semantic representation
preferences; its secondary `temporal_first` is not a substitute for the standalone
Temporal First control. `policy_satisfied` continues to authorize immediate legal
publication rather than speculative preference waiting.

Original fixed 20 m remains an explicit spatial rejection control. Long fixed
windows must also reject cells intersecting shorter regional time limits. Empty
output has retention zero and full-input semantic distortion one; retained-only
means/delays are undefined, never zero.

Report every input contribution, retention, full-input semantic distortion
`J=(N_input-N_retained+sum_retained taxonomy_loss)/N_input`, conditional semantic
loss, cell side, interval duration, logical observation-to-seal delay, per-type
and named source-point-region accounting, hard-policy violations and native
processing time. The independent audit limit is explicitly 1,000,000 records/
cells. This is a finite tested envelope, not a global optimum or a statistical
claim across unseen seeds.

## Phase 2: current-build paced processing

Use the unchanged corrected executable and already classified, tracked, leaf-
assigned source observations. Study both current 300 s streams and the exact
historical dense 240 s source whose earlier paced run failed. Source changes
cannot be substituted for an improvement on that old dense gate.

For each source, predeclare three sequential native invocations:

1. Unpaced full diagnostics with complete typed SHA-256 decision auditing.
2. Unpaced minimal diagnostics with the same complete decision auditing.
3. Minimal diagnostics at wall-clock 1×, 50 ms progress, 100 ms sensor cadence,
   bounded pending FIFO capacity eight, explicit failure sidecar and a 420 s
   native wall budget.

Nine invocations are planned. Full/minimal controls must have identical public
fields and complete retirement/release decision digests. The current sources'
full control must match their already independently audited corrected full result
outside runtime. The historical dense source needs a fresh independent current-
engine audit: its old binary's logical output may legitimately differ after the
handoff correction, so equality to the old buggy engine is not a gate.

Paced success requires all events to finish with causal telemetry and full
logical equality to the corresponding unpaced control. Success alone does not
imply every deadline passed. Report service, queue wait and scheduled-arrival-to-
completion mean/p95/p99/max; 50 ms response misses; the separate 100 ms sensor-
step view; release readiness/acknowledgement delay; peak queue and memory scope.

Overflow is a failed bounded live-operation gate. Preserve completed-prefix
statistics, pending/rejected counts and missing whole-run fields explicitly. Do
not retry with a larger queue, lower offered rate or sliding deadlines. The
source producer remains independent of the consumer. Simulation, inference,
raw-detection-to-leaf mapping, rendering, external transport and disk publication
are outside the measured in-memory service boundary. No hard real-time or
end-to-end application guarantee follows from average throughput.

## Phase 3: a single heterogeneous temporal-policy factor

Keep both complete current streams, Spatial20 geometry, taxonomy, total/category
support, semantic regional bounds, cell-size bounds and suppression OFF unchanged.
Use a paired illustrative application contract:

- `control`: root duration/age maxima remain 4000 ms; remove only the west/east
  local duration/age maxima so temporal allowances are uniform. Other regional
  metric requirements remain in force.
- `local400`: identical to that control except central-through-footway gains
  duration maximum 400 ms and age-at-evaluation maximum 400 ms.

These are illustrative freshness requirements, not empirically calibrated traffic
or privacy thresholds. Freeze exact structural policy diffs. Whole-cell positive-
area region intersection still applies; source-point cohorts are separate reporting
categories and do not determine a cell's effective policy.

For each source and each policy, test three adaptive strategies (Temporal First,
Spatial First, Semantic First) and eight global fixed schedules (10/20 m ×
400/1000/2000/4000 ms). Total: 44 native cases. Excluding fixed 5 m here is a
predeclared bounded scope; Phase 1 already measures it. Use within-method paired
control/treatment deltas and report all fixed references without selecting only
an inconvenient baseline.

Additionally derive eight static regional-window utility controls: two fixed
spatial resolutions × two policies × two sources. For every canonical fixed
cell choose its window from the declared schedule set using only public effective
policy bounds, before examining observations. On control this is 4000 ms
everywhere; on local400 every cell intersecting the fresh region uses 400 ms and
other cells use 4000 ms. Never choose windows from observed support or release
success. Compose cell statistics only from the matching independently audited
native fixed-schedule case. Independently check complete original-source
accounting, disjoint spatial/time assignment and every retained metric bound.
Control composition must reproduce the native global 4000 ms utility exactly.

This derived baseline measures utility of a fixed policy-aware regional schedule.
It is not a new online implementation or an additional timed native execution.
Do not fabricate a native result, compute a misleading runtime by summing runs,
or claim its online deployment performance. Native runtime is unavailable for
that derived schedule. Its purpose is to separate gains from regional flexibility
from gains of data-dependent adaptation.

## Decision and reporting rules

A variant can retain more input but have worse semantic loss or longer delay.
Report these jointly and retain non-dominated tradeoffs instead of declaring
one universal winner. Hard metric compliance and utility are the current scope;
none of these studies establishes attack resistance or formal privacy guarantees.
The next research stage may add repeated seeds/densities or a dedicated privacy
model after this mechanism/measurement boundary is clear.
