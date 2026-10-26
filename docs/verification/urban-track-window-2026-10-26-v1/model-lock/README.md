# Actual TRAIN/CAL lock before TEST

All 40 paired source families pass: 720 native executions and 160 derived regional
streams, with no audited published-cell policy violation. The new fitting input
contains 880 rows from 24 TRAIN and 16 CAL recordings. All 22 attack variants
converge within the unchanged budget. Two fitted and two direct controls also lock.

An independent no-refit audit recomputes TRAIN scaling, final model objectives,
predictions and CAL threshold selection. All thresholds obey the declared
empirical one-in-ten cap: with 16 CAL negatives, at most one false positive is
allowed. This is not a population cap. Relative-loss convergence does not claim
a 1e-8 gradient norm. The actual TEST source/native paths remain absent at this lock.

Only aggregate diagnostics and evidence hashes are published. Inputs, feature
rows, weights, individual scores and private path/identity references remain local.
The [pre-execution freeze](../pre-test-freeze/) retains its original zero counters.
Read the [validation report](../../../URBAN_PRIVACY_TRACK_WINDOW_TEST_REPORT_2026-10-26.md).
