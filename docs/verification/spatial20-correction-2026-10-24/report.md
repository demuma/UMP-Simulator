# Same-input controller correction: aggregate results

All 16 predeclared corrected cases passed independent audits. The main OFF policies and frozen observation streams are unchanged. Results are a post hoc implementation correction, with one realization per source.

Retention and full-input distortion use every input observation. J assigns unit cost to omitted observations plus retained taxonomy loss; lower is better. Semantic loss, spatial detail and delay are conditional on retained data.

## mixed / original

| Method | Implementation | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adaptive_immediate | historical | 39.944 | 85.369 | 63.370 | 9.687 | 1019.016 | 557.561 / 2200.000 | 58826.636 |
| adaptive_immediate | corrected | 39.944 | 85.369 | 63.370 | 9.687 | 1019.016 | 557.561 / 2200.000 | 63694.109 |
| adaptive_spatial_first | historical | 40.269 | 85.075 | 62.937 | 9.488 | 3949.140 | 2016.102 / 3800.000 | 52950.241 |
| adaptive_spatial_first | corrected | 40.269 | 85.075 | 62.937 | 9.488 | 3949.140 | 2016.102 / 3800.000 | 53770.345 |
| fixed_10m_1000ms | historical_fixed_reference | 30.132 | 88.900 | 63.160 | 10.000 | 1000.000 | 549.943 / 1000.000 | 405.265 |
| fixed_20m_400ms | historical_fixed_reference | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 502.405 |
| fixed_20m_1000ms | historical_fixed_reference | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 313.112 |

## mixed / spatial20

| Method | Implementation | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adaptive_immediate | historical | 44.299 | 85.385 | 67.009 | 19.073 | 562.722 | 328.643 / 700.000 | 58052.102 |
| adaptive_immediate | corrected | 63.956 | 76.684 | 63.544 | 17.816 | 545.558 | 319.884 / 600.000 | 33208.128 |
| adaptive_spatial_first | historical | 43.423 | 85.583 | 66.798 | 17.614 | 3867.441 | 1976.107 / 3800.000 | 59690.946 |
| adaptive_spatial_first | corrected | 60.413 | 77.466 | 62.701 | 16.793 | 3543.056 | 1817.557 / 3800.000 | 38448.416 |
| fixed_10m_1000ms | historical_fixed_reference | 35.394 | 86.268 | 61.204 | 10.000 | 1000.000 | 549.867 / 1000.000 | 398.577 |
| fixed_20m_400ms | historical_fixed_reference | 50.660 | 81.804 | 64.083 | 20.000 | 400.000 | 250.039 / 400.000 | 516.706 |
| fixed_20m_1000ms | historical_fixed_reference | 50.566 | 82.058 | 64.519 | 20.000 | 1000.000 | 550.522 / 1000.000 | 313.976 |

## pedestrians / original

| Method | Implementation | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adaptive_immediate | historical | 40.495 | 79.698 | 49.866 | 9.448 | 935.857 | 517.730 / 2200.000 | 66089.031 |
| adaptive_immediate | corrected | 41.151 | 79.370 | 49.868 | 9.439 | 928.890 | 514.163 / 2100.000 | 64042.920 |
| adaptive_spatial_first | historical | 41.439 | 79.280 | 50.000 | 8.666 | 3892.713 | 1989.588 / 3800.000 | 49636.029 |
| adaptive_spatial_first | corrected | 41.439 | 79.280 | 50.000 | 8.666 | 3892.713 | 1989.588 / 3800.000 | 50951.461 |
| fixed_10m_1000ms | historical_fixed_reference | 31.093 | 84.453 | 50.000 | 10.000 | 1000.000 | 549.386 / 1000.000 | 415.832 |
| fixed_20m_400ms | historical_fixed_reference | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 519.821 |
| fixed_20m_1000ms | historical_fixed_reference | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 320.551 |

## pedestrians / spatial20

| Method | Implementation | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adaptive_immediate | historical | 67.876 | 62.079 | 44.132 | 19.643 | 518.066 | 307.217 / 400.000 | 42617.296 |
| adaptive_immediate | corrected | 77.889 | 57.073 | 44.886 | 19.562 | 507.169 | 302.099 / 400.000 | 31328.003 |
| adaptive_spatial_first | historical | 70.096 | 63.739 | 48.269 | 17.814 | 3463.342 | 1781.013 / 3800.000 | 47475.913 |
| adaptive_spatial_first | corrected | 76.211 | 60.681 | 48.408 | 17.990 | 3265.697 | 1682.375 / 3800.000 | 39041.250 |
| fixed_10m_1000ms | historical_fixed_reference | 41.650 | 79.175 | 50.000 | 10.000 | 1000.000 | 549.453 / 1000.000 | 409.350 |
| fixed_20m_400ms | historical_fixed_reference | 74.306 | 58.931 | 44.730 | 20.000 | 400.000 | 250.038 / 400.000 | 535.972 |
| fixed_20m_1000ms | historical_fixed_reference | 75.688 | 58.102 | 44.644 | 20.000 | 1000.000 | 549.941 / 1000.000 | 325.615 |

## Regional correction deltas

Nonexclusive source-point cohorts; this is not a disjoint regional partition. Deltas are corrected minus historical OFF.

| Source / contract / method | Region | Input | Retained before → after | Retention delta (pp) |
| --- | --- | ---: | ---: | ---: |
| mixed / original / adaptive_immediate | central-through-footway | 8149 | 5516 → 5516 | 0.000 |
| mixed / original / adaptive_immediate | east-footway-control | 6410 | 492 → 492 | 0.000 |
| mixed / original / adaptive_immediate | entrance-vicinity | 1057 | 0 → 0 | 0.000 |
| mixed / original / adaptive_immediate | west-footway-control | 4034 | 0 → 0 | 0.000 |
| mixed / original / adaptive_spatial_first | central-through-footway | 8149 | 5724 → 5724 | 0.000 |
| mixed / original / adaptive_spatial_first | east-footway-control | 6410 | 502 → 502 | 0.000 |
| mixed / original / adaptive_spatial_first | entrance-vicinity | 1057 | 0 → 0 | 0.000 |
| mixed / original / adaptive_spatial_first | west-footway-control | 4034 | 0 → 0 | 0.000 |
| mixed / spatial20 / adaptive_immediate | central-through-footway | 8149 | 0 → 5993 | 73.543 |
| mixed / spatial20 / adaptive_immediate | east-footway-control | 6410 | 1202 → 3046 | 28.768 |
| mixed / spatial20 / adaptive_immediate | entrance-vicinity | 1057 | 0 → 33 | 3.122 |
| mixed / spatial20 / adaptive_immediate | west-footway-control | 4034 | 0 → 1691 | 41.919 |
| mixed / spatial20 / adaptive_spatial_first | central-through-footway | 8149 | 33 → 5477 | 66.806 |
| mixed / spatial20 / adaptive_spatial_first | east-footway-control | 6410 | 1216 → 2977 | 27.473 |
| mixed / spatial20 / adaptive_spatial_first | entrance-vicinity | 1057 | 65 → 65 | 0.000 |
| mixed / spatial20 / adaptive_spatial_first | west-footway-control | 4034 | 0 → 1647 | 40.828 |
| pedestrians / original / adaptive_immediate | central-through-footway | 11716 | 9587 → 9587 | 0.000 |
| pedestrians / original / adaptive_immediate | east-footway-control | 5829 | 146 → 146 | 0.000 |
| pedestrians / original / adaptive_immediate | entrance-vicinity | 1629 | 0 → 192 | 11.786 |
| pedestrians / original / adaptive_immediate | west-footway-control | 5585 | 664 → 664 | 0.000 |
| pedestrians / original / adaptive_spatial_first | central-through-footway | 11716 | 8566 → 8566 | 0.000 |
| pedestrians / original / adaptive_spatial_first | east-footway-control | 5829 | 215 → 215 | 0.000 |
| pedestrians / original / adaptive_spatial_first | entrance-vicinity | 1629 | 460 → 460 | 0.000 |
| pedestrians / original / adaptive_spatial_first | west-footway-control | 5585 | 664 → 664 | 0.000 |
| pedestrians / spatial20 / adaptive_immediate | central-through-footway | 11716 | 10109 → 10109 | 0.000 |
| pedestrians / spatial20 / adaptive_immediate | east-footway-control | 5829 | 4917 → 5071 | 2.642 |
| pedestrians / spatial20 / adaptive_immediate | entrance-vicinity | 1629 | 0 → 614 | 37.692 |
| pedestrians / spatial20 / adaptive_immediate | west-footway-control | 5585 | 1618 → 4720 | 55.542 |
| pedestrians / spatial20 / adaptive_spatial_first | central-through-footway | 11716 | 8389 → 8389 | 0.000 |
| pedestrians / spatial20 / adaptive_spatial_first | east-footway-control | 5829 | 4650 → 5071 | 7.223 |
| pedestrians / spatial20 / adaptive_spatial_first | entrance-vicinity | 1629 | 939 → 939 | 0.000 |
| pedestrians / spatial20 / adaptive_spatial_first | west-footway-control | 5585 | 1616 → 4682 | 54.897 |

## Separate filtering sensitivity

ON changes the root maximum selective-suppression fraction from 0 to 0.1. It is a separate policy sensitivity, not part of the unchanged-policy correction.

| Source / method | OFF → ON retention (%) | OFF → ON full-input J (%) | Selectively omitted / input (%) | Mean delay OFF → ON (ms) |
| --- | ---: | ---: | ---: | ---: |
| mixed / adaptive_immediate | 63.956 → 64.448 | 76.684 → 75.279 | 0.233 | 319.884 → 317.797 |
| mixed / adaptive_spatial_first | 60.413 → 61.678 | 77.466 → 74.978 | 0.335 | 1817.557 → 1781.325 |
| mixed / fixed_20m_1000ms | 50.566 → 57.596 | 82.058 → 77.188 | 0.677 | 550.522 → 550.070 |
| pedestrians / adaptive_immediate | 77.889 → 77.872 | 57.073 → 56.972 | 0.017 | 302.099 → 302.112 |
| pedestrians / adaptive_spatial_first | 76.211 → 76.211 | 60.681 → 60.681 | 0.000 | 1682.375 → 1682.375 |
| pedestrians / fixed_20m_1000ms | 75.688 → 75.647 | 58.102 → 57.869 | 0.041 | 549.941 → 549.997 |

## Limits and provenance

- J=(N_input-N_retained+sum_retained taxonomy_loss)/N_input; unit omission cost. Lower is better; experimental utility, not privacy risk.
- Semantic loss, cell side, interval length and observation-to-release delay condition on retained observations.
- Compare the four named nonexclusive source-point cohorts; regional privacy/utility checks use full-cell intersections. Historical outside-policy-region counts remain as optional provenance, but the corrected audit does not provide this cohort. It is not reconstructed by subtracting overlapping named cohorts. Regional counts must not be summed as a partition.
- Historical and corrected core/process timings are separate recordings, not paired statistical estimates. Core excludes simulation, Python audit, rendering and report writing.
- Historical fixed10m/1s and fixed20m/.4s,1s are unchanged-policy references. The corrected fixed20m/1s OFF identity control checks exact public/private logical equality; other fixed cases are not rerun.
- ON is a separate root maximum selective-suppression fraction of 0.1; OFF policies retain byte identity. Compare ON/OFF within the same method and contract.
- Two frozen sources, one realization each; post hoc implementation repair, no statistical population inference. Different source motion prevents an isolated taxonomy-causality claim.
- Zero audited violations refers to selected operational constraints; neither attack resistance nor a privacy gain is measured.
- Reported source/native result digests are execution receipts from the verified runner; this lightweight report does not reread movement or private arrays.

Correction summary SHA-256: `34f214e19bfb065dd469c253d4dd903e76d59427d0d5b1600a3817427bf65b36`.
Corrected binary SHA-256: `72fc0aff452ee036d7dfdd8bd8ca7bd343c7462923ec00ccb39f904ee655502f`.

The accompanying aggregate JSON contains source/configuration/result hashes and numerical baseline/region deltas. It contains no individual identities, positions or movement records.
