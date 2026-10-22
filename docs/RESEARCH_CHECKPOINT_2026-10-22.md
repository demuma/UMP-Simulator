# Research checkpoint and repository publication

Date: 2026-10-22. This checkpoint makes the previously uncommitted research
work reviewable and adds cell inspection, leaf-scale policy examples and a
small results-only package. All project documentation remains
English. The user's attached taxonomy specification is discussion material;
its embedded implementation instructions do not authorize the complete v2
taxonomy/ORCA migration.

## Existing changes accounted for

The initial worktree contained **162 changed paths: 44 modified and 118
untracked**. Their initial path/status inventory and checkpoint byte hashes are recorded in
[the initial inventory](RESEARCH_CHECKPOINT_2026-10-22.json). This is the
pre-checkpoint inventory, not an assertion that all of those paths were newly
implemented on October 22.

| Work area | Changes represented by the checkpoint |
|---|---|
| Coordination and history | Future handoff repair, endpoint coordination, bounded source history, immutable ownership/publication and corresponding regression/diagnosis reports |
| Spatial and semantic aggregation | Selective valid-descendant rescue; versioned semantic category tree; exact identity support; intermediate classes; semantic metrics; Semantic First secondaries and release triggers |
| Publication and diagnostics | Reassessment of approved bins; durable recipient/private-journal boundaries; JSON/MongoDB diagnostics, recovery and tests |
| Evaluation | Causal privacy and online occupancy tools; old stress studies kept distinct; frozen-input semantic, moving-population, output-cell-cap and four-second comparisons |
| Replay | Local synchronized recorded observations and actual releases; new explicit cell selection, category tables and opt-in same-window source groups |
| Documentation | Contracts, chronological backlog, terminology/equation export, protocols, test/result reports, figures and bounded presentation narrative |

The initial inventory includes the user's existing display-title/date changes
in `simulator/config.yaml` and formatting of the relative-path workspace file.
They are preserved and documented as existing configuration preferences. A
whitespace-only added line in AgentBasedSensor is normalized for a clean diff;
it changes no sensor behavior. Generated SVG plot bytes are preserved;
`.gitattributes` exempts their machine-generated path whitespace from diff checks.
Source and prose whitespace checks remain enabled.

## New bounded October 22 work

1. Make cell inspection discoverable and keyboard-accessible in both replay
   panels. Distinguish published categories from optional privileged source
   type groups reconstructed for exactly the selected historical cell/window.
2. Exercise four small regional patches affecting 16 of 4096 finest leaves,
   with unchanged observations across uniform/regional policy variants.
   Inspect intermediate category generalization, sibling merging, suppression
   and policy inheritance through a cell intersecting an empty strict patch.
3. Package compact aggregate result tables, policies, audit totals and hash-only
   provenance. Generated observations, recorded movement datasets and full replay
   streams remain local and are excluded from the repository package.
4. Correct an explicit replay-mode override that retained a semantic-only setting.
   Validate the original policy before the override; preserve metric bounds.
   The default local-policy result remains scientifically identical to the frozen output.
5. Run the appropriate regression checks and a browser inspection, then stage
   reviewed changes and publish ordinary commits to the existing origin.

See [leaf-scale protocol](LOCAL_LEAF_POLICY_PROTOCOL_2026-10-22.md),
[results](LOCAL_LEAF_POLICY_RESULTS_2026-10-22.md),
[data package](REPLAY_DATA_PACKAGE.md) and the
[taxonomy/policy roadmap](TAXONOMY_POLICY_ROADMAP_2026-10-22.md).

## Scope boundaries

The new local-policy experiment uses declared synthetic trajectories, not a
validated realistic street or a new full-simulator capture. Numerical support
thresholds are contract fixtures, not calibrated privacy guarantees.
Semantic execution still uses common windows. A strict regional time bound
can constrain that whole common interval, including when the strict footprint
is empty. Individual semantic windows and ownership-aware merging remain the
next algorithm integration gate.

Modifier-based population/profile generation, richer map geometry, overlapping
policy layers, per-attribute disclosure restrictions and ORCA are not silently
implemented by this checkpoint. Existing source files, external paper PDFs and
the 29-GB ignored results tree are not interchangeable with the curated data
package. The latter explicitly lists what can be restored and reproduced.

The final GitHub package contains compact synthetic-study result summaries, not
recorded movement inputs. The user requested that generated movement datasets
remain outside Git to keep the repository small. A first 47-MB package had
already been pushed when that clarification arrived; its just-created data
commit was replaced rather than retaining those recordings in the main branch's
reachable history. The tested source checkpoint is preserved. Original local
recordings and the preliminary archive remain in ignored `results/` storage.

Small analytical examples and regression fixtures are maintained as code/test
inputs. They are distinct from the generated simulator recordings excluded by
the package. Complete local replay bundles still contain privileged source
evidence; the recipient display is a filter, not a sanitized export.
