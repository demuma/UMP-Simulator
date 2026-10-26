# Complete observed-track-window evidence

Read [the result interpretation](interpretation.md), [all method results](report.md)
and [aggregate data](summary.json). The adjacent
[execution/test report](../../../URBAN_PRIVACY_TRACK_WINDOW_EXECUTION_TEST_REPORT_2026-10-26.md)
records actual QA and execution scope. The
[technical amendment](../../../URBAN_PRIVACY_TRACK_WINDOW_DIAGNOSTIC_REPAIR_2026-10-26.md)
explains the preserved original diagnostic failures and exact correction.

The primary adaptive-minus-regional20 AUC difference is +0.012695, with paired
95% interval [-0.043970,+0.072266]. Neither superiority nor equivalence is
established. Utility retention and logical delay improve, while TEST FPR exceeds
the CAL cap and fixed-query coverage remains limited. Controls pass.

`numeric-artifact-receipt.json` preserves the numerical export receipt.
`packet-receipt.json` binds those numeric artifacts, mandatory
`repair-lineage-public.json` and interpretation together. `verification.json`
summarizes actual checks; `bundle-receipt.json` binds every file here and the
adjacent test report. Keep the lineage and interpretation with the figures.

This package contains aggregate evidence and figure assets only. Raw movements,
models, feature vectors, target labels and individual scores remain local.
