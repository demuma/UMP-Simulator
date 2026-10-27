# Semantic-generalization ablation: implementation and test report

Prepared 27 October 2026. Status: pre-execution gates complete; actual study utility
and MIA outcomes pending. This report will be extended after those separate stages.
The frozen [scientific protocol](URBAN_SEMANTIC_ABLATION_PROTOCOL_2026-10-27.md)
retains its declaration-time wording. Compact preflight hashes and validation are
in [verification](verification/urban-semantic-ablation-2026-10-27-v1/pre-execution-freeze/validation.json).

## Change and unchanged requirements

An immutable semantic-generalization action mode defaults to `enabled`.
`AggregationReplay --semantic-generalization exact_only` returns every occupied
original terminal category with its truthful count/support to the same metric
and policy evaluator. It prevents semantic coarsening without changing the
hierarchy, the hard semantic-loss ceiling, category-support requirements or
spatial/temporal policy. Unsupported candidates fail as complete footprints;
rare types are never silently omitted. Positive selective-suppression allowances
are rejected in this mode. Configuration/evaluator mismatches are rejected in
selection, cell coordination and publication revalidation.

Fixed 20 m/0.4 s, regional static20 and the five adaptive execution variants each
receive an OFF counterpart. Three additional fixed OFF windows only support the
regional composition and are excluded from headline/MIA denominators. The same
72 recordings, split roles, target tracks, auxiliary knowledge and IN/OUT pairs
are reused. No new movements, MongoDB capture or policy relaxation is involved.

The new binary is built separately under `simulator/build-semantic-ablation`.
Original replay/Simulator binaries and historical studies remain unchanged.
Before native edits, historical code, results, models and public Git anchors were
authenticated into an explicit local content-addressed archive. The new bridge
distinguishes archived producer code from current native code. It additionally
binds every actual capture proof, configuration and observation file to the
frozen original source input and saved validation receipt before reconstruction.

## Verification completed before study execution

| Gate | Result and scope |
|---|---|
| Affected Python regressions | 530 tests pass; zero failures, errors or skips |
| Affected native suites | 22 pass; zero failures/skips, separate build |
| New native fixtures | Fixed and all five adaptive branches, supported exact output, ON rescue, rare category preservation, repeated IDs, regional checks, mismatch guards and publication retry |
| Legacy compatibility | Enabled native public releases, logical private windows and public export reproduce preserved legacy output on the excluded DEV recording |
| Native city action gate | Five OFF adaptive cases and one Enabled control; all audited |
| Full city integration | 18 OFF native cases, two regional OFF compositions and two fresh legacy fixed controls in matched IN/OUT worlds; all verified |
| Historical bridge | 72 historical source-proof/config/observation bindings authenticate; 2160 old rows and 30 old models unchanged |
| Independent runner review | Catalog/count/stage/provenance review passes; five new proof/map/config/observation tampering cases pass |
| Query/report review | Independent source/query and reporter review passes; full repeated DEV query projection matches all442 values exactly |
| Synthetic figure review | Root viewed all four PNGs; labels, legends, zero markers and synthetic/scope warnings remain visible |

The focused 43 runner, 27 reporter and 15 query tests are included in the530;
they are not additional independent samples. The new native fixture suite is
included in the22. Repeated DEV executions reuse one excluded source and do not
increase the statistical sample. Optional MongoDB integration is not configured
in this separate build; these gates do not claim an end-to-end live display or
per-step deadline test. Imported ON and newly executed OFF runtimes are diagnostic
and are not a controlled timing comparison.

## Retained failure and correction

The first full DEV wrapper stopped after ten audited IN OFF cases because it
compared the complete query return object with its intentionally smaller stored
`exact`/`estimate` projection. An independent repeat found zero numerical
differences over442 leaf values; no timing fields are present. The wrapper was
corrected and the complete matched IN/OUT gate rerun in a fresh directory.
The original failed receipt, code and outputs remain local and unchanged.

Independent review also found that final historical raw reconstruction needed
an explicit frozen capture-proof binding before trusting its file map. The
narrow correction adds that source-authentication helper and call site; an AST
comparison confirms all scientific case/model paths unchanged. Five negative
fixtures and actual bindings for all72 sources pass. No changed raw input was
found. Full raw payload hashes, unchanged GT/sensor reconstruction and archive
decompression remain final assessment gates, not a newly executed physical audit.

## DEV interpretation and remaining gates

On the excluded DEV input, all observed OFF contributions retired without publication under
the unchanged category-support requirements. Supported exact-class hand fixtures
do publish. This records a support/coverage limitation of the chosen action
restriction and policy on that DEV source; it does not prove global infeasibility
or an optimality theorem. Zero retained semantic loss with zero retained data
must remain NA for conditional utility. Empty output cannot establish useful
privacy preservation.

Next execute all1296 declared new native cases and144 regional compositions,
check source conservation and independent policy audits, archive losslessly and
review complete utility before any new attack fit. The new 20 m/400 ms
category-query workload counts observation contributions, retains missing or
semantically ambiguous information as unknown and scores estimates separately.
J measures omission plus semantic distortion, not privacy.

Only after independent utility/numerical/actual-figure review fit fourteen OFF
TRAIN-only attack models, select CAL thresholds and publicly lock them before
TEST scoring. Imported ON models and controls remain exact. Final paired
OFF-minus-ON AUC intervals use the predeclared source bootstrap and are exploratory
on already inspected TEST sources; no new confirmatory sample or universal
privacy guarantee is created. Raw trajectories, features, fitted parameters and
individual scores stay local. Paper/presentation edits in the parallel chat
remain outside this change.
