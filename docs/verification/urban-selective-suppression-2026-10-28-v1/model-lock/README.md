# Selective-suppression model lock

Fourteen new models are locked after 24 TRAIN and 16 CAL recordings. Fourteen historical models and four controls are unchanged.

The fitter receives zero TEST rows. New TEST scoring has not been performed by this stage; the 32 TEST recordings were exposed in earlier studies, so the comparison remains exploratory.

The independent audit verifies TRAIN arithmetic, CAL operating choices, frozen objects and lineage. This publication precedes the next scoring stage.

| New method | Representation | Status | Converged | Iterations | TRAIN rows | Features |
|---|---|---|---|---:|---:|---:|
| fixed20_400ms_selective | semantic111 | locked | true | 121 | 48 | 111 |
| fixed20_400ms_selective | scalar31 | locked | true | 31 | 48 | 31 |
| regional_static20_selective | semantic111 | locked | true | 94 | 48 | 111 |
| regional_static20_selective | scalar31 | locked | true | 44 | 48 | 31 |
| adaptive_temporal_first_selective | semantic111 | locked | true | 77 | 48 | 111 |
| adaptive_temporal_first_selective | scalar31 | locked | true | 45 | 48 | 31 |
| adaptive_spatial_first_selective | semantic111 | locked | true | 67 | 48 | 111 |
| adaptive_spatial_first_selective | scalar31 | locked | true | 49 | 48 | 31 |
| adaptive_semantic_first_selective | semantic111 | locked | true | 80 | 48 | 111 |
| adaptive_semantic_first_selective | scalar31 | locked | true | 46 | 48 | 31 |
| adaptive_semantic_wait_temporal_selective | semantic111 | locked | true | 79 | 48 | 111 |
| adaptive_semantic_wait_temporal_selective | scalar31 | locked | true | 45 | 48 | 31 |
| adaptive_semantic_wait_spatial_selective | semantic111 | locked | true | 94 | 48 | 111 |
| adaptive_semantic_wait_spatial_selective | scalar31 | locked | true | 44 | 48 | 31 |

summary.json contains provenance hashes and these limited fit diagnostics. Complete fitted objects stay local. Utility and observed attack performance remain separate evidence.
