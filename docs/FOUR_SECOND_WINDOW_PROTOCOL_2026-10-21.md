# Four-second maximum windows: predeclared paired replay protocol

Date: 2026-10-21. Freeze this protocol before executing the new comparisons.
The completed [cell-cap protocol](CELL_SIZE_CAP_PROTOCOL_2026-10-21.md), its
1-second outputs and the original moving captures remain unchanged.

## Question and controlled change

Does allowing up to 4 seconds of temporal aggregation improve retained
information and task availability under a maximum output-cell side of 5 m?
Use the 10 m cap as a contextual comparison. Do not assume improvement or select
only favorable population levels. The question concerns the consequences of a
changed policy, not an increase in measured privacy or a better algorithm under
identical requirements.

Reuse, byte-for-byte, the three verified captures of 200, 500 and 1000 initial
Road Users: 20 simulated seconds, an 80 m x 80 m measured area, observation depth
6 (4096 possible 1.25 m leaves), seven existing behavior profiles, a 50 ms
simulation step and 100 ms sensor cadence. Archive source hashes. Generate no
new movement, change no type label and resample no initial position. Captures
at different population levels remain different stochastic realizations.

The source population can decline because the existing simulator does not
replenish departing Road Users. Each population has one source realization;
replaying it deterministically is an engineering check, not a statistical
replication.

## Policy and method matrix

Change all three relevant time limits together:

- Policy Tree `window_duration_ms.max`: 4000 ms.
- Policy Tree `age_at_evaluation_ms.max`: 4000 ms.
- Controller `temporal_adaptation.max_window_ms`: 4000 ms.

The base adaptive window remains 400 ms and each extension is 100 ms. Four
seconds is an upper bound, not a requirement that every adaptive release wait
4 seconds. Use common-window coordination, minimum distinct support 5 in each
nonempty published category, maximum semantic loss 1, minimum cell side 1.25 m
and the same `ump-seven-profile-release` version-1 taxonomy. Preserve the
maximum cell side and corresponding minimum search depth for each cap. No
regional overrides, new semantic actions, tracking model or attack are added.

| Maximum output side | Legal fixed uniform-grid sides | Fixed window durations | Adaptive strategies |
|---|---|---|---|
| 5 m, primary | 1.25, 2.5, 5 m (depths 6, 5, 4) | 400, 1000, 4000 ms | Temporal First, Spatial First, Semantic First |
| 10 m, context | 2.5, 5, 10 m (depths 5, 4, 3) | 400, 1000, 4000 ms | Temporal First, Spatial First, Semantic First |

Each of six cap/population combinations has 12 methods, giving **72 new
outputs**. Run one deterministic Semantic First repeat per combination, giving
six repeats. Fixed controls use the same hard constraints and allowed semantic
generalization. Nine fixed settings are a declared portfolio, not the globally
best fixed baseline.

Compare each adaptive result with its completed 1-second-cap counterpart on the
same source. Pair fixed methods only where grid and duration match. Fixed
4000-ms outputs are additional controls; they have no fixed 4000-ms counterpart
in the old 1-second policy. Preserve old artifacts and identify new policies
explicitly.

## Resource feasibility and isolation

Retain enough private history for any legal 4-second candidate: retention
5000 ms, at most 64 bins, 100000 observations, 16 MB identity strings and 128
bucket descriptors. Allow 64 temporal endpoint evaluations: the inclusive
400..4000 ms sequence at 100 ms intervals has 37 endpoints. Keep 8192 spatial
evaluations per proposal, above the 5460 nodes of a complete depth-6 data tree,
and the existing serialized-artifact bounds.

These resource adjustments permit the enlarged window to be evaluated; they
are not additional policy permissions or a performance optimization. Archive
the values with every result. Resource exhaustion, missing history or malformed
input is an execution failure, never evidence of policy infeasibility. Verify
that the chosen budgets suffice for the actual sources before interpreting
suppression.

No simulator or MongoDB access is needed. Do not edit the normal simulator
configuration, mutate stored captures or replace earlier results. Every output
directory must be new. Freeze the executed replay binary, runner, auditors,
protocol, policy, commands and all artifact hashes.

## Verification gate

For every output independently reconstruct scalar counts, distinct identity
unions, geometry, temporal intervals, nonoverlap and original-source accounting.
Reconstruct semantic category counts/unions, complete truthful antichains,
minimum support and losses from the original observations. Check the exact
5/10 m spatial cap and 4000 ms duration/age limits. Check that input source bytes
are identical for all methods within a population. Validate each viewer bundle.

Compare the deterministic repeat after excluding runtime only. Test parameter
validation, legacy defaults, correct coupling of duration/age/controller limits,
required history/evaluation budgets, the full new method matrix, and cases
where new identities make a longer interval useful. Retain failures and all-
suppressed cases in the report. An independent artifact review must precede
presentation claims.

## Declared outcomes and fair interpretation

Keep the existing task unchanged: mean sampled all-road-user occupancy on fixed
**10 m squares and 1000 ms intervals**. Use the same recipient-only estimator,
uniform-allocation assumptions, query bank and logical deadline lags of 0, 200
and 1000 ms. Keep the original fixed interior cohort (`query end + 1000 ms <
source horizon`) and separate boundary/EOF treatment. Do not add a 4000-ms lag
to this primary evaluation, since that would also change the cohort. A later,
separately labeled latency workload would need its own declaration.

Report together:

- Released/source observation contributions and suppression; these are not
  unique-person retention or preservation of every attribute.
- Eventual fixed-query coverage and conditional MAE, with unanswered queries
  unknown rather than zero.
- Deadline coverage and conditional MAE on the identical fixed primary cohort.
- Weighted spatial detail, semantic loss and logical interval-start age;
  actual released durations and available semantic categories.
- Realized input population/type evolution and any execution/resource failure.

A 4-second aggregate can pool more distinct Road Users if identities enter the
cell over time. Repeated measurements of one identity still count as one.
Longer windows can lose temporal peaks and miss short deadlines even while
retaining more observations. Report availability, error and delay together;
conditional error on a smaller surviving set is not a general improvement.
No public coverage means an unavailable error/detail summary, not zero error.

Seven input profiles do not require 5 people in each of all seven types. Only
nonempty published bins are checked, and the allowed root generalization can
pool the profiles into Road User with support 5 when semantic loss 1 is legal.
Detailed class publication is harder for rare profiles; this study holds the
profile mix fixed and therefore cannot identify a causal type-count effect.
If priorities coincide, examine their actual intervals, cuts, semantic bins and
terminal constraints instead of assuming a controller defect or equivalence
for other policies.

This experiment establishes a policy-sensitivity result on three frozen pilot
sources. It establishes neither formal privacy, measured privacy gain,
statistical superiority, global scheduling optimality nor real sensor-to-
application latency. Present at most one clear 1-second/4-second trade-off in
the 20-minute talk, with the changed bound and fixed task stated.
