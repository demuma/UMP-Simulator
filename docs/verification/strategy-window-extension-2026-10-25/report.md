# Strategy and fixed-window extension

Full frozen streams; unchanged hard policies; selective suppression OFF. Temporal First preserves temporal accuracy by preferring spatial aggregation. Fixed windows remain subject to all local duration and age limits.

J penalizes every omitted input observation by one and adds retained taxonomy loss, divided by all inputs. Lower is better. Conditional metrics are undefined when nothing is retained. No attack-based privacy gain is claimed.

## mixed / original

| Method | Evidence | Retained (%) | J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adaptive_immediate | verified_corrected_adaptive_reference | 39.944 | 85.369 | 63.370 | 9.687 | 1019.016 | 557.561 / 2200.000 | 63694.109 |
| adaptive_spatial_first | verified_corrected_adaptive_reference | 40.269 | 85.075 | 62.937 | 9.488 | 3949.140 | 2016.102 / 3800.000 | 53770.345 |
| fixed_5m_400ms | verified_historical_fixed_reference | 3.640 | 98.395 | 55.894 | 5.000 | 400.000 | 249.766 / 400.000 | 953.095 |
| fixed_5m_1000ms | verified_historical_fixed_reference | 4.980 | 97.828 | 56.377 | 5.000 | 1000.000 | 550.502 / 1000.000 | 546.992 |
| fixed_10m_400ms | verified_historical_fixed_reference | 26.968 | 89.713 | 61.856 | 10.000 | 400.000 | 249.984 / 400.000 | 725.565 |
| fixed_10m_1000ms | verified_historical_fixed_reference | 30.132 | 88.900 | 63.160 | 10.000 | 1000.000 | 549.943 / 1000.000 | 405.265 |
| fixed_20m_400ms | verified_historical_fixed_reference | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 502.405 |
| fixed_20m_1000ms | verified_historical_fixed_reference | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 313.112 |
| adaptive_temporal_first | standalone_temporal_priority | 39.944 | 85.369 | 63.370 | 9.687 | 1019.016 | 557.561 / 2200.000 | 57823.016 |
| fixed_5m_2000ms | matched_long_fixed_window | 7.595 | 96.878 | 58.892 | 5.000 | 2000.000 | 1049.775 / 2000.000 | 354.141 |
| fixed_5m_4000ms | matched_long_fixed_window | 15.109 | 94.449 | 63.256 | 5.000 | 4000.000 | 2075.641 / 3900.000 | 280.004 |
| fixed_10m_2000ms | matched_long_fixed_window | 33.946 | 87.732 | 63.860 | 10.000 | 2000.000 | 1049.873 / 1900.000 | 290.458 |
| fixed_10m_4000ms | matched_long_fixed_window | 40.267 | 85.736 | 64.575 | 10.000 | 4000.000 | 2039.722 / 3800.000 | 227.101 |
| fixed_20m_2000ms | matched_long_fixed_window | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 233.367 |
| fixed_20m_4000ms | matched_long_fixed_window | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 196.579 |

## mixed / spatial20

| Method | Evidence | Retained (%) | J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adaptive_immediate | verified_corrected_adaptive_reference | 63.956 | 76.684 | 63.544 | 17.816 | 545.558 | 319.884 / 600.000 | 33208.128 |
| adaptive_spatial_first | verified_corrected_adaptive_reference | 60.413 | 77.466 | 62.701 | 16.793 | 3543.056 | 1817.557 / 3800.000 | 38448.416 |
| fixed_5m_400ms | verified_historical_fixed_reference | 3.640 | 98.395 | 55.894 | 5.000 | 400.000 | 249.766 / 400.000 | 958.168 |
| fixed_5m_1000ms | verified_historical_fixed_reference | 4.980 | 97.828 | 56.377 | 5.000 | 1000.000 | 550.502 / 1000.000 | 522.242 |
| fixed_10m_400ms | verified_historical_fixed_reference | 31.634 | 87.381 | 60.108 | 10.000 | 400.000 | 249.996 / 400.000 | 709.673 |
| fixed_10m_1000ms | verified_historical_fixed_reference | 35.394 | 86.268 | 61.204 | 10.000 | 1000.000 | 549.867 / 1000.000 | 398.577 |
| fixed_20m_400ms | verified_historical_fixed_reference | 50.660 | 81.804 | 64.083 | 20.000 | 400.000 | 250.039 / 400.000 | 516.706 |
| fixed_20m_1000ms | verified_historical_fixed_reference | 50.566 | 82.058 | 64.519 | 20.000 | 1000.000 | 550.522 / 1000.000 | 313.976 |
| adaptive_temporal_first | standalone_temporal_priority | 63.956 | 76.684 | 63.544 | 17.816 | 545.558 | 319.884 / 600.000 | 32284.745 |
| fixed_5m_2000ms | matched_long_fixed_window | 7.595 | 96.878 | 58.892 | 5.000 | 2000.000 | 1049.775 / 2000.000 | 360.242 |
| fixed_5m_4000ms | matched_long_fixed_window | 15.109 | 94.449 | 63.256 | 5.000 | 4000.000 | 2075.641 / 3900.000 | 284.083 |
| fixed_10m_2000ms | matched_long_fixed_window | 33.946 | 87.732 | 63.860 | 10.000 | 2000.000 | 1049.873 / 1900.000 | 284.800 |
| fixed_10m_4000ms | matched_long_fixed_window | 40.267 | 85.736 | 64.575 | 10.000 | 4000.000 | 2039.722 / 3800.000 | 227.373 |
| fixed_20m_2000ms | matched_long_fixed_window | 45.613 | 84.785 | 66.644 | 20.000 | 2000.000 | 1050.358 / 2000.000 | 240.515 |
| fixed_20m_4000ms | matched_long_fixed_window | 49.191 | 83.413 | 66.280 | 20.000 | 4000.000 | 2048.326 / 3900.000 | 204.907 |

## pedestrians / original

| Method | Evidence | Retained (%) | J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adaptive_immediate | verified_corrected_adaptive_reference | 41.151 | 79.370 | 49.868 | 9.439 | 928.890 | 514.163 / 2100.000 | 64042.920 |
| adaptive_spatial_first | verified_corrected_adaptive_reference | 41.439 | 79.280 | 50.000 | 8.666 | 3892.713 | 1989.588 / 3800.000 | 50951.461 |
| fixed_5m_400ms | verified_historical_fixed_reference | 10.172 | 94.914 | 50.000 | 5.000 | 400.000 | 249.929 / 400.000 | 988.060 |
| fixed_5m_1000ms | verified_historical_fixed_reference | 13.115 | 93.443 | 50.000 | 5.000 | 1000.000 | 550.758 / 1000.000 | 544.652 |
| fixed_10m_400ms | verified_historical_fixed_reference | 29.015 | 85.492 | 50.000 | 10.000 | 400.000 | 250.002 / 400.000 | 749.700 |
| fixed_10m_1000ms | verified_historical_fixed_reference | 31.093 | 84.453 | 50.000 | 10.000 | 1000.000 | 549.386 / 1000.000 | 415.832 |
| fixed_20m_400ms | verified_historical_fixed_reference | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 519.821 |
| fixed_20m_1000ms | verified_historical_fixed_reference | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 320.551 |
| adaptive_temporal_first | standalone_temporal_priority | 41.151 | 79.370 | 49.868 | 9.439 | 928.890 | 514.163 / 2100.000 | 62977.298 |
| fixed_5m_2000ms | matched_long_fixed_window | 15.869 | 92.066 | 50.000 | 5.000 | 2000.000 | 1047.428 / 1900.000 | 386.603 |
| fixed_5m_4000ms | matched_long_fixed_window | 23.519 | 88.240 | 50.000 | 5.000 | 4000.000 | 2039.706 / 3800.000 | 297.333 |
| fixed_10m_2000ms | matched_long_fixed_window | 34.247 | 82.876 | 50.000 | 10.000 | 2000.000 | 1049.569 / 1900.000 | 312.814 |
| fixed_10m_4000ms | matched_long_fixed_window | 39.626 | 80.187 | 50.000 | 10.000 | 4000.000 | 2044.351 / 3900.000 | 241.775 |
| fixed_20m_2000ms | matched_long_fixed_window | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 250.741 |
| fixed_20m_4000ms | matched_long_fixed_window | 0.000 | 100.000 | n/a | n/a | n/a | n/a / n/a | 214.843 |

## pedestrians / spatial20

| Method | Evidence | Retained (%) | J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adaptive_immediate | verified_corrected_adaptive_reference | 77.889 | 57.073 | 44.886 | 19.562 | 507.169 | 302.099 / 400.000 | 31328.003 |
| adaptive_spatial_first | verified_corrected_adaptive_reference | 76.211 | 60.681 | 48.408 | 17.990 | 3265.697 | 1682.375 / 3800.000 | 39041.250 |
| fixed_5m_400ms | verified_historical_fixed_reference | 10.172 | 94.914 | 50.000 | 5.000 | 400.000 | 249.929 / 400.000 | 989.580 |
| fixed_5m_1000ms | verified_historical_fixed_reference | 13.115 | 93.443 | 50.000 | 5.000 | 1000.000 | 550.758 / 1000.000 | 539.271 |
| fixed_10m_400ms | verified_historical_fixed_reference | 38.724 | 80.638 | 50.000 | 10.000 | 400.000 | 250.039 / 400.000 | 735.319 |
| fixed_10m_1000ms | verified_historical_fixed_reference | 41.650 | 79.175 | 50.000 | 10.000 | 1000.000 | 549.453 / 1000.000 | 409.350 |
| fixed_20m_400ms | verified_historical_fixed_reference | 74.306 | 58.931 | 44.730 | 20.000 | 400.000 | 250.038 / 400.000 | 535.972 |
| fixed_20m_1000ms | verified_historical_fixed_reference | 75.688 | 58.102 | 44.644 | 20.000 | 1000.000 | 549.941 / 1000.000 | 325.615 |
| adaptive_temporal_first | standalone_temporal_priority | 77.889 | 57.303 | 45.182 | 19.503 | 507.169 | 302.099 / 400.000 | 30514.245 |
| fixed_5m_2000ms | matched_long_fixed_window | 15.869 | 92.066 | 50.000 | 5.000 | 2000.000 | 1047.428 / 1900.000 | 386.985 |
| fixed_5m_4000ms | matched_long_fixed_window | 23.519 | 88.240 | 50.000 | 5.000 | 4000.000 | 2039.706 / 3800.000 | 310.111 |
| fixed_10m_2000ms | matched_long_fixed_window | 34.247 | 82.876 | 50.000 | 10.000 | 2000.000 | 1049.569 / 1900.000 | 315.887 |
| fixed_10m_4000ms | matched_long_fixed_window | 39.626 | 80.187 | 50.000 | 10.000 | 4000.000 | 2044.351 / 3900.000 | 250.819 |
| fixed_20m_2000ms | matched_long_fixed_window | 58.740 | 65.936 | 42.008 | 20.000 | 2000.000 | 1050.002 / 1900.000 | 258.696 |
| fixed_20m_4000ms | matched_long_fixed_window | 61.461 | 63.190 | 40.108 | 20.000 | 4000.000 | 2045.576 / 3900.000 | 219.997 |

## Limits

- One realization per source; strategy and window sensitivity, not population-level inference.
- Previous verified references are reused with summary/configuration/result digests. Their timings are separate recordings; no paired runtime claim.
- A 2 s or 4 s fixed window is not exempt from a regional 1 s bound. Zero release is an admissibility result, not evidence of an implementation failure.
- Core processing excludes motion generation, Python audit, rendering and final file I/O. Offline throughput does not establish deadline compliance.
- Regional source-point cohorts may overlap and must not be summed as a partition.
- Every current case passes the independent full-input accounting and public-policy audit with a declared one-million-cell audit bound.
