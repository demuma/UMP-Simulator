# Paired local-freshness study

Local temporal constraints are illustrative application requirements, not calibrated privacy protection. Native fixed methods use one global schedule, with identical policy rejection. A separately derived static regional schedule has no native execution-time claim.

All results use unchanged observations and suppression OFF. Percentages use the full input stream. Conditional loss and delay are undefined when nothing is retained.

| Source | Policy | Method | Retained % | Full-input loss % | Conditional loss % | Delay mean / p95 ms | Core ms |
|---|---|---|---:|---:|---:|---:|---:|
| mixed | control | adaptive_temporal_first | 65.419 | 76.066 | 63.415 | 340.104 / 900.000 | 34551.018 |
| mixed | control | adaptive_spatial_first | 62.544 | 76.588 | 62.567 | 2051.765 / 3800.000 | 37817.594 |
| mixed | control | adaptive_semantic_first | 65.419 | 76.066 | 63.415 | 340.104 / 900.000 | 34551.956 |
| mixed | control | fixed_10m_400ms | 31.634 | 87.381 | 60.108 | 249.996 / 400.000 | 805.134 |
| mixed | control | fixed_10m_1000ms | 35.394 | 86.268 | 61.204 | 549.867 / 1000.000 | 399.721 |
| mixed | control | fixed_10m_2000ms | 39.903 | 84.753 | 61.790 | 1050.382 / 1900.000 | 288.905 |
| mixed | control | fixed_10m_4000ms | 47.129 | 82.305 | 62.453 | 2041.233 / 3800.000 | 240.410 |
| mixed | control | fixed_20m_400ms | 50.660 | 81.804 | 64.083 | 250.039 / 400.000 | 508.083 |
| mixed | control | fixed_20m_1000ms | 50.566 | 82.058 | 64.519 | 550.522 / 1000.000 | 315.068 |
| mixed | control | fixed_20m_2000ms | 51.437 | 81.874 | 64.760 | 1050.722 / 2000.000 | 241.891 |
| mixed | control | fixed_20m_4000ms | 55.218 | 80.399 | 64.503 | 2051.917 / 3900.000 | 206.698 |
| mixed | local400 | adaptive_temporal_first | 64.887 | 76.161 | 63.261 | 345.547 / 1000.000 | 32859.609 |
| mixed | local400 | adaptive_spatial_first | 61.746 | 76.430 | 61.828 | 1811.040 / 3800.000 | 36665.844 |
| mixed | local400 | adaptive_semantic_first | 64.887 | 76.161 | 63.261 | 345.547 / 1000.000 | 33517.714 |
| mixed | local400 | fixed_10m_400ms | 31.634 | 87.381 | 60.108 | 249.996 / 400.000 | 706.340 |
| mixed | local400 | fixed_10m_1000ms | 29.049 | 89.471 | 63.756 | 549.899 / 1000.000 | 397.447 |
| mixed | local400 | fixed_10m_2000ms | 33.233 | 88.088 | 64.157 | 1050.664 / 2000.000 | 293.507 |
| mixed | local400 | fixed_10m_4000ms | 40.175 | 85.781 | 64.608 | 2042.091 / 3800.000 | 235.490 |
| mixed | local400 | fixed_20m_400ms | 50.660 | 81.804 | 64.083 | 250.039 / 400.000 | 511.477 |
| mixed | local400 | fixed_20m_1000ms | 45.396 | 84.643 | 66.172 | 550.070 / 1000.000 | 333.462 |
| mixed | local400 | fixed_20m_2000ms | 46.267 | 84.459 | 66.409 | 1049.233 / 1900.000 | 244.994 |
| mixed | local400 | fixed_20m_4000ms | 48.916 | 83.863 | 67.010 | 2049.077 / 3900.000 | 207.884 |
| pedestrians | control | adaptive_temporal_first | 78.611 | 56.942 | 45.226 | 311.124 / 400.000 | 30885.345 |
| pedestrians | control | adaptive_spatial_first | 74.889 | 61.342 | 48.380 | 2047.485 / 3800.000 | 39141.130 |
| pedestrians | control | adaptive_semantic_first | 78.611 | 56.712 | 44.933 | 311.124 / 400.000 | 30636.661 |
| pedestrians | control | fixed_10m_400ms | 38.724 | 80.638 | 50.000 | 250.039 / 400.000 | 734.834 |
| pedestrians | control | fixed_10m_1000ms | 41.650 | 79.175 | 50.000 | 549.453 / 1000.000 | 418.711 |
| pedestrians | control | fixed_10m_2000ms | 45.976 | 77.012 | 50.000 | 1049.598 / 1900.000 | 305.963 |
| pedestrians | control | fixed_10m_4000ms | 53.254 | 73.373 | 50.000 | 2050.860 / 3900.000 | 266.112 |
| pedestrians | control | fixed_20m_400ms | 74.306 | 58.931 | 44.730 | 250.038 / 400.000 | 546.229 |
| pedestrians | control | fixed_20m_1000ms | 75.688 | 58.102 | 44.644 | 549.941 / 1000.000 | 329.440 |
| pedestrians | control | fixed_20m_2000ms | 77.818 | 56.397 | 43.968 | 1050.293 / 1900.000 | 263.262 |
| pedestrians | control | fixed_20m_4000ms | 81.024 | 53.408 | 42.496 | 2049.640 / 3900.000 | 220.307 |
| pedestrians | local400 | adaptive_temporal_first | 78.316 | 57.089 | 45.208 | 305.796 / 400.000 | 29805.291 |
| pedestrians | local400 | adaptive_spatial_first | 76.980 | 57.797 | 45.177 | 1734.665 / 3800.000 | 37125.787 |
| pedestrians | local400 | adaptive_semantic_first | 78.316 | 56.859 | 44.914 | 305.796 / 400.000 | 29637.501 |
| pedestrians | local400 | fixed_10m_400ms | 38.724 | 80.638 | 50.000 | 250.039 / 400.000 | 744.372 |
| pedestrians | local400 | fixed_10m_1000ms | 31.767 | 84.116 | 50.000 | 549.156 / 1000.000 | 417.723 |
| pedestrians | local400 | fixed_10m_2000ms | 35.924 | 82.038 | 50.000 | 1049.444 / 1900.000 | 307.914 |
| pedestrians | local400 | fixed_10m_4000ms | 42.593 | 78.703 | 50.000 | 2050.093 / 3900.000 | 248.435 |
| pedestrians | local400 | fixed_20m_400ms | 74.306 | 58.931 | 44.730 | 250.038 / 400.000 | 541.694 |
| pedestrians | local400 | fixed_20m_1000ms | 62.216 | 67.993 | 48.554 | 549.854 / 1000.000 | 328.770 |
| pedestrians | local400 | fixed_20m_2000ms | 64.346 | 66.763 | 48.347 | 1050.119 / 1900.000 | 261.104 |
| pedestrians | local400 | fixed_20m_4000ms | 67.200 | 64.474 | 47.134 | 2048.190 / 3900.000 | 221.949 |

## Paired effect of the central 400-ms cap

| Source | Method | Retention change pp | Full-input loss change pp | Central retained change |
|---|---|---:|---:|---:|
| mixed | adaptive_temporal_first | -0.531 | 0.094 | -460 |
| mixed | adaptive_spatial_first | -0.798 | -0.158 | 101 |
| mixed | adaptive_semantic_first | -0.531 | 0.094 | -460 |
| mixed | fixed_10m_400ms | 0.000 | 0.000 | 0 |
| mixed | fixed_10m_1000ms | -6.345 | 3.203 | -5205 |
| mixed | fixed_10m_2000ms | -6.670 | 3.335 | -5472 |
| mixed | fixed_10m_4000ms | -6.953 | 3.477 | -5704 |
| mixed | fixed_20m_400ms | 0.000 | 0.000 | 0 |
| mixed | fixed_20m_1000ms | -5.170 | 2.585 | -2801 |
| mixed | fixed_20m_2000ms | -5.170 | 2.585 | -2801 |
| mixed | fixed_20m_4000ms | -6.302 | 3.463 | -3077 |
| pedestrians | adaptive_temporal_first | -0.294 | 0.147 | -264 |
| pedestrians | adaptive_spatial_first | 2.091 | -3.545 | 1456 |
| pedestrians | adaptive_semantic_first | -0.294 | 0.147 | -264 |
| pedestrians | fixed_10m_400ms | 0.000 | 0.000 | 0 |
| pedestrians | fixed_10m_1000ms | -9.883 | 4.941 | -8899 |
| pedestrians | fixed_10m_2000ms | -10.052 | 5.026 | -9051 |
| pedestrians | fixed_10m_4000ms | -10.661 | 5.331 | -9600 |
| pedestrians | fixed_20m_400ms | 0.000 | 0.000 | 0 |
| pedestrians | fixed_20m_1000ms | -13.472 | 9.891 | -9861 |
| pedestrians | fixed_20m_2000ms | -13.472 | 10.366 | -9861 |
| pedestrians | fixed_20m_4000ms | -13.824 | 11.066 | -10146 |

The reported source-point regions describe observation cohorts. Policy compliance uses conservative positive-area intersections of complete cell footprints; neighboring observations may therefore be affected.

Operational support and hard-policy compliance are measured. No attack-based or formal privacy gain is claimed.
