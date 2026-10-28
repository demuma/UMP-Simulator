# Source-order audit correction: pre-execution evidence

The original independent model audit failed on a manifest-versus-sorted list
comparison. Source memberships are identical (24 TRAIN / 16 CAL / 32 TEST).
The failed attempt is preserved. The additive verifier changes only the expected
metadata order and retains the frozen model/data/math checks.

All 23 targeted tests pass, including nine new regressions. Independent review
confirms no source reassignment or model change. Exact code/test and preserved
fitted-artifact hashes are in [summary.json](summary.json). No real corrective
audit or new TEST scoring has run at this publication boundary; no fit is repeated.

Read the [verification addendum](../../../URBAN_SELECTIVE_SUPPRESSION_AUDIT_ORDER_ADDENDUM_2026-10-28.md).
