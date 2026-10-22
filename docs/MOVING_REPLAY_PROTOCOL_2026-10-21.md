# Moving replay pilot: predeclared protocol

Recorded before the first capture/result on 2026-10-21. This bounded next step
uses the existing C++ Simulator, not a replacement motion generator.

## Purpose and scope

Check causal, policy-approved release behavior on moving observations, compare
against useful fixed settings, and provide an inspectable replay for the talk.
This is one stochastic realization per population, not a statistical efficacy
study or evidence of actual privacy gain. Do not tune thresholds after viewing
results to manufacture an adaptive advantage.

## Input

- Three separate captures: requested initial populations200,500,1000,20 simulated
  seconds,80x80m; all seven existing behavior profiles/weights from the maintained
  simulator configuration. Integer type allocation and actual population are reported.
- Existing numerical step50ms, AGBS cadence100ms, finest depth6 (4096 possible cells,
  side1.25m). Capture one identity-bearing internal observation stream and verify
  per-cell/type counts and geometry against raw AGBS using full GT.
- Same frozen input bytes across every method for each population. Independent
  captures are not paired across different population levels.
- Uniform random starts and destinations, existing motion/noise/collision rules;
  no new map, seed, motion algorithm, replenishment, attack or performance optimization.
- Observe decline/stopping, displacement and type composition. More requested Road
  Users does not imply equal density throughout the session. RawGT retained privately.
- Initial t=0 remainsGT; sensor replay begins at100ms. Missing rows do not prove an
  empty measurement. Reject incomplete/unverifiable captures.

## Methods and shared policy

Six fixed baselines: cell side10,20,40m crossed with400,1000ms windows. Their grids
have depths3,2,1 and the same alignment as the adaptive quadtree. Compare with
Temporal First (preserve time), Spatial First (preserve space), and Semantic First
(preserve semantics, TF secondary). Common-window coordination for every mode.
No globally adaptive uniform-grid competitor is introduced in this pilot.

Every mode uses the same rooted, versioned seven-profile release taxonomy and
original metric evaluator. Fixed means fixed space/time, with the same allowed
semantic generalization; unapproved cells are suppressed. Root: per-category
minimum distinct support5; maximum semantic loss1; cell side1.25..40m; window and
interval-start age at most1000ms. Adaptive base window400ms, extension step100ms.
No regional overrides in this first controlled pilot; their interaction is a
separate experiment. Support is an operational release condition, not a completed
k-anonymity/QI definition or a privacy guarantee.

Taxonomy `ump-seven-profile-release` version1: Road User root loss1; Pedestrian and
Cyclist group losses0.5; the seven exact behavior-label terminals loss0. Adult
E-Scooter Driver is a separate terminal, not a cyclist or pedestrian. The loss
scale expresses a declared preference; it is not empirically calibrated.

Retain bounded2000ms history, at most32 bins,100000 observations,16MB identity
strings,128 bucket descriptors. Each spatial proposal has8192 evaluations,
above the5460-node full data-tree bound at depth6. Resource errors are explicit
failures, never evidence of policy infeasibility. Input/output256MiB cap retained.

## Outcomes and verification

- Independently reconstruct published scalar counts, identity unions, geometry,
  nonoverlap, policy bounds and whole-source accounting.
- Independently reconstruct every semantic public bin from raw identities and
  labels; check the complete truthful antichain, support and loss thresholds.
- Report retained observation fraction, contribution-weighted cell side, semantic
  loss, interval-start age, suppression, population evolution and displacement.
- Fixed recipient task: mean sampled occupancy on10m squares/1000ms windows.
  Report query coverage together with conditional MAE. Reconstruction assumes
  spatially uniform allocation and constant occupancy within each released block.
  This all-road-user workload does not measure class-query utility.
- Logical query deadlines at query end+0,200,1000ms; same interior cohort excludes
  EOF effects. Report EOF/boundary separately. No live network/DB latency claim.
- One deterministic rerun per capture, excluding runtime from equality only.
- Archive config, input, protocol, executed binary, commands, hashes and results.
  No stronger claim than this matrix supports. Later studies need independent
  realizations, heterogeneous flows/regions, class-query utility and privacy models.

## Visible replay

Play/seek the actual recorded sensor observations and actual release events on a
shared simulation-time axis. Show recipient data only after sealing. Retained
historical releases show their original interval and age; suppressed cells are
private diagnostics and must be visually identified as such. No fabricated split
or merge animation. This replay is a research/debug tool, not a public data product.
