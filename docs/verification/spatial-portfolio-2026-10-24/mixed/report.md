# Same-source mapped comparison

Status: verified. Observations SHA-256: `c24134c724acf2df38a85b2906a2e80f8de7b420529a4b8cda3f9e5f98a3eff5`.

Original: all original hard root/region constraints remain. Spatial20: every existing root/region cell_side_m.max becomes20 m, equally for every method. All support, temporal and semantic bounds, regions and taxonomy remain. Selective contribution suppression is disabled in every case. Compare methods within one contract.

Source horizon: 300 s; sensor period: 100 ms; input observation contributions: 82033; peak observed simultaneous tracks: 126.

A completed source horizon does not imply a drained finite cohort. The lifecycle counts below describe the recorded horizon.

Recorded lifecycle counts: `{"active_episodes_at_horizon": 0, "pending_episodes_at_horizon": 0, "realized_ends": 171, "realized_starts": 171, "scheduled_episodes": 171, "scheduled_people": 128}`.

## Policy and retained detail

| Case | Retained input | Exact subtype / input | Mean semantic loss | Mean cell side (m) | Mean interval (ms) | Mean observation delay (ms) | p95 delay (ms) | Core (ms) | Policy violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original_adaptive_immediate | 39.94% | 0.07% | 0.63 | 9.69 | 1019.02 | 557.56 | 2200.00 | 58826.64 | 0 |
| original_adaptive_spatial_first | 40.27% | 0.00% | 0.63 | 9.49 | 3949.14 | 2016.10 | 3800.00 | 52950.24 | 0 |
| original_fixed_5m_400ms | 3.64% | 0.00% | 0.56 | 5.00 | 400.00 | 249.77 | 400.00 | 953.10 | 0 |
| original_fixed_5m_1000ms | 4.98% | 0.00% | 0.56 | 5.00 | 1000.00 | 550.50 | 1000.00 | 546.99 | 0 |
| original_fixed_10m_400ms | 26.97% | 0.07% | 0.62 | 10.00 | 400.00 | 249.98 | 400.00 | 725.57 | 0 |
| original_fixed_10m_1000ms | 30.13% | 0.06% | 0.63 | 10.00 | 1000.00 | 549.94 | 1000.00 | 405.26 | 0 |
| original_fixed_20m_400ms | 0.00% | 0.00% | n/a | n/a | n/a | n/a | n/a | 502.41 | 0 |
| original_fixed_20m_1000ms | 0.00% | 0.00% | n/a | n/a | n/a | n/a | n/a | 313.11 | 0 |
| spatial20_adaptive_immediate | 44.30% | 0.00% | 0.67 | 19.07 | 562.72 | 328.64 | 700.00 | 58052.10 | 0 |
| spatial20_adaptive_spatial_first | 43.42% | 0.00% | 0.67 | 17.61 | 3867.44 | 1976.11 | 3800.00 | 59690.95 | 0 |
| spatial20_fixed_5m_400ms | 3.64% | 0.00% | 0.56 | 5.00 | 400.00 | 249.77 | 400.00 | 958.17 | 0 |
| spatial20_fixed_5m_1000ms | 4.98% | 0.00% | 0.56 | 5.00 | 1000.00 | 550.50 | 1000.00 | 522.24 | 0 |
| spatial20_fixed_10m_400ms | 31.63% | 0.07% | 0.60 | 10.00 | 400.00 | 250.00 | 400.00 | 709.67 | 0 |
| spatial20_fixed_10m_1000ms | 35.39% | 0.06% | 0.61 | 10.00 | 1000.00 | 549.87 | 1000.00 | 398.58 | 0 |
| spatial20_fixed_20m_400ms | 50.66% | 0.00% | 0.64 | 20.00 | 400.00 | 250.04 | 400.00 | 516.71 | 0 |
| spatial20_fixed_20m_1000ms | 50.57% | 0.00% | 0.65 | 20.00 | 1000.00 | 550.52 | 1000.00 | 313.98 | 0 |

Zero violations with no releases is vacuous compliance; read it together with retention. Semantic, side and interval means condition on retained observations. Exact subtype / input and retention use the full input denominator.

## Operational observed-track support

Cell statistics use distinct observed tracks per published cell-window. Category statistics use distinct tracks per published semantic bin. Both p50 values are unweighted nearest-rank medians; means are weighted by cell or category observation contributions respectively. Empty output is n/a. These are operational support statistics, not measured attack risk, privacy gain or a trajectory k-anonymity guarantee.

| Case | Cell min | Cell p50 | Cell observation-weighted mean | Category min | Category p50 | Category observation-weighted mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| original_adaptive_immediate | 5 | 6 | 6.15 | 5 | 6 | 6.15 |
| original_adaptive_spatial_first | 5 | 6 | 7.87 | 5 | 6 | 7.87 |
| original_fixed_5m_400ms | 5 | 5 | 5.57 | 5 | 5 | 5.57 |
| original_fixed_5m_1000ms | 5 | 5 | 5.71 | 5 | 5 | 5.71 |
| original_fixed_10m_400ms | 5 | 6 | 6.71 | 5 | 6 | 6.71 |
| original_fixed_10m_1000ms | 5 | 6 | 6.91 | 5 | 6 | 6.91 |
| original_fixed_20m_400ms | n/a | n/a | n/a | n/a | n/a | n/a |
| original_fixed_20m_1000ms | n/a | n/a | n/a | n/a | n/a | n/a |
| spatial20_adaptive_immediate | 5 | 8 | 10.60 | 5 | 8 | 10.60 |
| spatial20_adaptive_spatial_first | 5 | 7 | 11.07 | 5 | 7 | 11.07 |
| spatial20_fixed_5m_400ms | 5 | 5 | 5.57 | 5 | 5 | 5.57 |
| spatial20_fixed_5m_1000ms | 5 | 5 | 5.71 | 5 | 5 | 5.71 |
| spatial20_fixed_10m_400ms | 5 | 6 | 6.71 | 5 | 6 | 6.71 |
| spatial20_fixed_10m_1000ms | 5 | 6 | 6.90 | 5 | 6 | 6.90 |
| spatial20_fixed_20m_400ms | 5 | 8 | 11.30 | 5 | 8 | 11.30 |
| spatial20_fixed_20m_1000ms | 5 | 8 | 11.62 | 5 | 8 | 11.62 |

Core timing excludes input validation and file I/O. The complete comparison pipeline also includes independent Python audits and query evaluation. Neither timing is a per-step live deadline guarantee.

## Recipient queries

Total and immediate taxonomy families, identical across both contracts. Exact subtype preservation is separately source-denominated.

The table separates positive-reference queries from known-zero queries, and interior windows from source-boundary windows. Estimates use public uniform spatial/time allocation and keep their own error; missing output never becomes zero.

| Case | Lag (ms) | Cohort | Positive reference queries | Exact coverage | Estimated coverage | Estimated occupancy MAE |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| original_adaptive_immediate | 0 | interior | 8094 | 0.05% | 2.41% | 0.0980 |
| original_adaptive_immediate | 0 | boundary | 0 | n/a | n/a | n/a |
| original_adaptive_immediate | 1000 | interior | 8094 | 0.05% | 10.49% | 0.1121 |
| original_adaptive_immediate | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_adaptive_spatial_first | 0 | interior | 8094 | 0.00% | 0.51% | 0.8329 |
| original_adaptive_spatial_first | 0 | boundary | 0 | n/a | n/a | n/a |
| original_adaptive_spatial_first | 1000 | interior | 8094 | 0.00% | 4.09% | 0.5814 |
| original_adaptive_spatial_first | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_400ms | 0 | interior | 8094 | 0.00% | 0.00% | n/a |
| original_fixed_5m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_400ms | 1000 | interior | 8094 | 0.00% | 0.00% | n/a |
| original_fixed_5m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_1000ms | 0 | interior | 8094 | 0.00% | 0.00% | n/a |
| original_fixed_5m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_1000ms | 1000 | interior | 8094 | 0.00% | 0.00% | n/a |
| original_fixed_5m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_400ms | 0 | interior | 8094 | 0.00% | 3.36% | 0.0296 |
| original_fixed_10m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_400ms | 1000 | interior | 8094 | 0.00% | 6.62% | 0.0297 |
| original_fixed_10m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_1000ms | 0 | interior | 8094 | 9.28% | 9.28% | 0.0000 |
| original_fixed_10m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_1000ms | 1000 | interior | 8094 | 9.28% | 9.28% | 0.0000 |
| original_fixed_10m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_20m_400ms | 0 | interior | 8094 | 0.00% | 0.00% | n/a |
| original_fixed_20m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_20m_400ms | 1000 | interior | 8094 | 0.00% | 0.00% | n/a |
| original_fixed_20m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_20m_1000ms | 0 | interior | 8094 | 0.00% | 0.00% | n/a |
| original_fixed_20m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_20m_1000ms | 1000 | interior | 8094 | 0.00% | 0.00% | n/a |
| original_fixed_20m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_adaptive_immediate | 0 | interior | 8094 | 0.00% | 10.34% | 1.3157 |
| spatial20_adaptive_immediate | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_adaptive_immediate | 1000 | interior | 8094 | 0.00% | 24.01% | 1.2435 |
| spatial20_adaptive_immediate | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_adaptive_spatial_first | 0 | interior | 8094 | 0.00% | 0.07% | 1.7885 |
| spatial20_adaptive_spatial_first | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_adaptive_spatial_first | 1000 | interior | 8094 | 0.00% | 6.94% | 1.0740 |
| spatial20_adaptive_spatial_first | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_5m_400ms | 0 | interior | 8094 | 0.00% | 0.00% | n/a |
| spatial20_fixed_5m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_5m_400ms | 1000 | interior | 8094 | 0.00% | 0.00% | n/a |
| spatial20_fixed_5m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_5m_1000ms | 0 | interior | 8094 | 0.00% | 0.00% | n/a |
| spatial20_fixed_5m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_5m_1000ms | 1000 | interior | 8094 | 0.00% | 0.00% | n/a |
| spatial20_fixed_5m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_10m_400ms | 0 | interior | 8094 | 0.00% | 3.93% | 0.0275 |
| spatial20_fixed_10m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_10m_400ms | 1000 | interior | 8094 | 0.00% | 7.78% | 0.0278 |
| spatial20_fixed_10m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_10m_1000ms | 0 | interior | 8094 | 11.18% | 11.18% | 0.0000 |
| spatial20_fixed_10m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_10m_1000ms | 1000 | interior | 8094 | 11.18% | 11.18% | 0.0000 |
| spatial20_fixed_10m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_20m_400ms | 0 | interior | 8094 | 0.00% | 14.90% | 1.3335 |
| spatial20_fixed_20m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_20m_400ms | 1000 | interior | 8094 | 0.00% | 30.18% | 1.3196 |
| spatial20_fixed_20m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_20m_1000ms | 0 | interior | 8094 | 0.00% | 32.63% | 1.2713 |
| spatial20_fixed_20m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_20m_1000ms | 1000 | interior | 8094 | 0.00% | 32.63% | 1.2713 |
| spatial20_fixed_20m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |

## Source type and local region costs

Each row keeps the full input denominator for that type or source-point region. Region memberships can overlap and do not sum to a global partition. Effective policy audit instead intersects the entire released footprint with every selected region.

| Case | Group kind | Group | Input contributions | Retained contributions | Retained fraction |
| --- | --- | --- | ---: | ---: | ---: |
| original_adaptive_immediate | by_source_type | Adult Cyclist | 2867 | 1821 | 63.52% |
| original_adaptive_immediate | by_source_type | Adult E-Scooter Driver | 2404 | 1655 | 68.84% |
| original_adaptive_immediate | by_source_type | Adult Pedestrian | 14047 | 5801 | 41.30% |
| original_adaptive_immediate | by_source_type | Child Pedestrian | 15200 | 5058 | 33.28% |
| original_adaptive_immediate | by_source_type | Pedestrian With Mobility Aid | 16639 | 6000 | 36.06% |
| original_adaptive_immediate | by_source_type | Pedestrian With Stroller | 13060 | 3839 | 29.40% |
| original_adaptive_immediate | by_source_type | Senior Cyclist | 2837 | 1924 | 67.82% |
| original_adaptive_immediate | by_source_type | Senior Pedestrian | 14979 | 6669 | 44.52% |
| original_adaptive_immediate | by_source_point_region | central-through-footway | 8149 | 5516 | 67.69% |
| original_adaptive_immediate | by_source_point_region | east-footway-control | 6410 | 492 | 7.68% |
| original_adaptive_immediate | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| original_adaptive_immediate | by_source_point_region | outside_policy_regions | 62383 | 26759 | 42.89% |
| original_adaptive_immediate | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| original_adaptive_spatial_first | by_source_type | Adult Cyclist | 2867 | 1512 | 52.74% |
| original_adaptive_spatial_first | by_source_type | Adult E-Scooter Driver | 2404 | 1374 | 57.15% |
| original_adaptive_spatial_first | by_source_type | Adult Pedestrian | 14047 | 6185 | 44.03% |
| original_adaptive_spatial_first | by_source_type | Child Pedestrian | 15200 | 5098 | 33.54% |
| original_adaptive_spatial_first | by_source_type | Pedestrian With Mobility Aid | 16639 | 6316 | 37.96% |
| original_adaptive_spatial_first | by_source_type | Pedestrian With Stroller | 13060 | 3981 | 30.48% |
| original_adaptive_spatial_first | by_source_type | Senior Cyclist | 2837 | 1567 | 55.23% |
| original_adaptive_spatial_first | by_source_type | Senior Pedestrian | 14979 | 7001 | 46.74% |
| original_adaptive_spatial_first | by_source_point_region | central-through-footway | 8149 | 5724 | 70.24% |
| original_adaptive_spatial_first | by_source_point_region | east-footway-control | 6410 | 502 | 7.83% |
| original_adaptive_spatial_first | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| original_adaptive_spatial_first | by_source_point_region | outside_policy_regions | 62383 | 26808 | 42.97% |
| original_adaptive_spatial_first | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| original_fixed_5m_400ms | by_source_type | Adult Cyclist | 2867 | 4 | 0.14% |
| original_fixed_5m_400ms | by_source_type | Adult E-Scooter Driver | 2404 | 4 | 0.17% |
| original_fixed_5m_400ms | by_source_type | Adult Pedestrian | 14047 | 761 | 5.42% |
| original_fixed_5m_400ms | by_source_type | Child Pedestrian | 15200 | 413 | 2.72% |
| original_fixed_5m_400ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 607 | 3.65% |
| original_fixed_5m_400ms | by_source_type | Pedestrian With Stroller | 13060 | 360 | 2.76% |
| original_fixed_5m_400ms | by_source_type | Senior Cyclist | 2837 | 56 | 1.97% |
| original_fixed_5m_400ms | by_source_type | Senior Pedestrian | 14979 | 781 | 5.21% |
| original_fixed_5m_400ms | by_source_point_region | central-through-footway | 8149 | 549 | 6.74% |
| original_fixed_5m_400ms | by_source_point_region | east-footway-control | 6410 | 448 | 6.99% |
| original_fixed_5m_400ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| original_fixed_5m_400ms | by_source_point_region | outside_policy_regions | 62383 | 1989 | 3.19% |
| original_fixed_5m_400ms | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| original_fixed_5m_1000ms | by_source_type | Adult Cyclist | 2867 | 47 | 1.64% |
| original_fixed_5m_1000ms | by_source_type | Adult E-Scooter Driver | 2404 | 36 | 1.50% |
| original_fixed_5m_1000ms | by_source_type | Adult Pedestrian | 14047 | 1010 | 7.19% |
| original_fixed_5m_1000ms | by_source_type | Child Pedestrian | 15200 | 596 | 3.92% |
| original_fixed_5m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 767 | 4.61% |
| original_fixed_5m_1000ms | by_source_type | Pedestrian With Stroller | 13060 | 466 | 3.57% |
| original_fixed_5m_1000ms | by_source_type | Senior Cyclist | 2837 | 103 | 3.63% |
| original_fixed_5m_1000ms | by_source_type | Senior Pedestrian | 14979 | 1060 | 7.08% |
| original_fixed_5m_1000ms | by_source_point_region | central-through-footway | 8149 | 752 | 9.23% |
| original_fixed_5m_1000ms | by_source_point_region | east-footway-control | 6410 | 474 | 7.39% |
| original_fixed_5m_1000ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| original_fixed_5m_1000ms | by_source_point_region | outside_policy_regions | 62383 | 2836 | 4.55% |
| original_fixed_5m_1000ms | by_source_point_region | west-footway-control | 4034 | 23 | 0.57% |
| original_fixed_10m_400ms | by_source_type | Adult Cyclist | 2867 | 992 | 34.60% |
| original_fixed_10m_400ms | by_source_type | Adult E-Scooter Driver | 2404 | 808 | 33.61% |
| original_fixed_10m_400ms | by_source_type | Adult Pedestrian | 14047 | 4175 | 29.72% |
| original_fixed_10m_400ms | by_source_type | Child Pedestrian | 15200 | 3616 | 23.79% |
| original_fixed_10m_400ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 4354 | 26.17% |
| original_fixed_10m_400ms | by_source_type | Pedestrian With Stroller | 13060 | 2627 | 20.11% |
| original_fixed_10m_400ms | by_source_type | Senior Cyclist | 2837 | 1037 | 36.55% |
| original_fixed_10m_400ms | by_source_type | Senior Pedestrian | 14979 | 4514 | 30.14% |
| original_fixed_10m_400ms | by_source_point_region | central-through-footway | 8149 | 5044 | 61.90% |
| original_fixed_10m_400ms | by_source_point_region | east-footway-control | 6410 | 0 | 0.00% |
| original_fixed_10m_400ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| original_fixed_10m_400ms | by_source_point_region | outside_policy_regions | 62383 | 17079 | 27.38% |
| original_fixed_10m_400ms | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| original_fixed_10m_1000ms | by_source_type | Adult Cyclist | 2867 | 1207 | 42.10% |
| original_fixed_10m_1000ms | by_source_type | Adult E-Scooter Driver | 2404 | 1051 | 43.72% |
| original_fixed_10m_1000ms | by_source_type | Adult Pedestrian | 14047 | 4543 | 32.34% |
| original_fixed_10m_1000ms | by_source_type | Child Pedestrian | 15200 | 4030 | 26.51% |
| original_fixed_10m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 4745 | 28.52% |
| original_fixed_10m_1000ms | by_source_type | Pedestrian With Stroller | 13060 | 2897 | 22.18% |
| original_fixed_10m_1000ms | by_source_type | Senior Cyclist | 2837 | 1271 | 44.80% |
| original_fixed_10m_1000ms | by_source_type | Senior Pedestrian | 14979 | 4974 | 33.21% |
| original_fixed_10m_1000ms | by_source_point_region | central-through-footway | 8149 | 5205 | 63.87% |
| original_fixed_10m_1000ms | by_source_point_region | east-footway-control | 6410 | 0 | 0.00% |
| original_fixed_10m_1000ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| original_fixed_10m_1000ms | by_source_point_region | outside_policy_regions | 62383 | 19513 | 31.28% |
| original_fixed_10m_1000ms | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Adult Cyclist | 2867 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Adult E-Scooter Driver | 2404 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Adult Pedestrian | 14047 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Child Pedestrian | 15200 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Pedestrian With Stroller | 13060 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Senior Cyclist | 2837 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Senior Pedestrian | 14979 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | central-through-footway | 8149 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | east-footway-control | 6410 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | outside_policy_regions | 62383 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Adult Cyclist | 2867 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Adult E-Scooter Driver | 2404 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Adult Pedestrian | 14047 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Child Pedestrian | 15200 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Pedestrian With Stroller | 13060 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Senior Cyclist | 2837 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Senior Pedestrian | 14979 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | central-through-footway | 8149 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | east-footway-control | 6410 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | outside_policy_regions | 62383 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| spatial20_adaptive_immediate | by_source_type | Adult Cyclist | 2867 | 1661 | 57.94% |
| spatial20_adaptive_immediate | by_source_type | Adult E-Scooter Driver | 2404 | 1505 | 62.60% |
| spatial20_adaptive_immediate | by_source_type | Adult Pedestrian | 14047 | 6663 | 47.43% |
| spatial20_adaptive_immediate | by_source_type | Child Pedestrian | 15200 | 6214 | 40.88% |
| spatial20_adaptive_immediate | by_source_type | Pedestrian With Mobility Aid | 16639 | 6625 | 39.82% |
| spatial20_adaptive_immediate | by_source_type | Pedestrian With Stroller | 13060 | 4496 | 34.43% |
| spatial20_adaptive_immediate | by_source_type | Senior Cyclist | 2837 | 1831 | 64.54% |
| spatial20_adaptive_immediate | by_source_type | Senior Pedestrian | 14979 | 7345 | 49.04% |
| spatial20_adaptive_immediate | by_source_point_region | central-through-footway | 8149 | 0 | 0.00% |
| spatial20_adaptive_immediate | by_source_point_region | east-footway-control | 6410 | 1202 | 18.75% |
| spatial20_adaptive_immediate | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| spatial20_adaptive_immediate | by_source_point_region | outside_policy_regions | 62383 | 35138 | 56.33% |
| spatial20_adaptive_immediate | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| spatial20_adaptive_spatial_first | by_source_type | Adult Cyclist | 2867 | 1541 | 53.75% |
| spatial20_adaptive_spatial_first | by_source_type | Adult E-Scooter Driver | 2404 | 1411 | 58.69% |
| spatial20_adaptive_spatial_first | by_source_type | Adult Pedestrian | 14047 | 6717 | 47.82% |
| spatial20_adaptive_spatial_first | by_source_type | Child Pedestrian | 15200 | 6050 | 39.80% |
| spatial20_adaptive_spatial_first | by_source_type | Pedestrian With Mobility Aid | 16639 | 6555 | 39.40% |
| spatial20_adaptive_spatial_first | by_source_type | Pedestrian With Stroller | 13060 | 4511 | 34.54% |
| spatial20_adaptive_spatial_first | by_source_type | Senior Cyclist | 2837 | 1736 | 61.19% |
| spatial20_adaptive_spatial_first | by_source_type | Senior Pedestrian | 14979 | 7100 | 47.40% |
| spatial20_adaptive_spatial_first | by_source_point_region | central-through-footway | 8149 | 33 | 0.40% |
| spatial20_adaptive_spatial_first | by_source_point_region | east-footway-control | 6410 | 1216 | 18.97% |
| spatial20_adaptive_spatial_first | by_source_point_region | entrance-vicinity | 1057 | 65 | 6.15% |
| spatial20_adaptive_spatial_first | by_source_point_region | outside_policy_regions | 62383 | 34307 | 54.99% |
| spatial20_adaptive_spatial_first | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| spatial20_fixed_5m_400ms | by_source_type | Adult Cyclist | 2867 | 4 | 0.14% |
| spatial20_fixed_5m_400ms | by_source_type | Adult E-Scooter Driver | 2404 | 4 | 0.17% |
| spatial20_fixed_5m_400ms | by_source_type | Adult Pedestrian | 14047 | 761 | 5.42% |
| spatial20_fixed_5m_400ms | by_source_type | Child Pedestrian | 15200 | 413 | 2.72% |
| spatial20_fixed_5m_400ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 607 | 3.65% |
| spatial20_fixed_5m_400ms | by_source_type | Pedestrian With Stroller | 13060 | 360 | 2.76% |
| spatial20_fixed_5m_400ms | by_source_type | Senior Cyclist | 2837 | 56 | 1.97% |
| spatial20_fixed_5m_400ms | by_source_type | Senior Pedestrian | 14979 | 781 | 5.21% |
| spatial20_fixed_5m_400ms | by_source_point_region | central-through-footway | 8149 | 549 | 6.74% |
| spatial20_fixed_5m_400ms | by_source_point_region | east-footway-control | 6410 | 448 | 6.99% |
| spatial20_fixed_5m_400ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| spatial20_fixed_5m_400ms | by_source_point_region | outside_policy_regions | 62383 | 1989 | 3.19% |
| spatial20_fixed_5m_400ms | by_source_point_region | west-footway-control | 4034 | 0 | 0.00% |
| spatial20_fixed_5m_1000ms | by_source_type | Adult Cyclist | 2867 | 47 | 1.64% |
| spatial20_fixed_5m_1000ms | by_source_type | Adult E-Scooter Driver | 2404 | 36 | 1.50% |
| spatial20_fixed_5m_1000ms | by_source_type | Adult Pedestrian | 14047 | 1010 | 7.19% |
| spatial20_fixed_5m_1000ms | by_source_type | Child Pedestrian | 15200 | 596 | 3.92% |
| spatial20_fixed_5m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 767 | 4.61% |
| spatial20_fixed_5m_1000ms | by_source_type | Pedestrian With Stroller | 13060 | 466 | 3.57% |
| spatial20_fixed_5m_1000ms | by_source_type | Senior Cyclist | 2837 | 103 | 3.63% |
| spatial20_fixed_5m_1000ms | by_source_type | Senior Pedestrian | 14979 | 1060 | 7.08% |
| spatial20_fixed_5m_1000ms | by_source_point_region | central-through-footway | 8149 | 752 | 9.23% |
| spatial20_fixed_5m_1000ms | by_source_point_region | east-footway-control | 6410 | 474 | 7.39% |
| spatial20_fixed_5m_1000ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| spatial20_fixed_5m_1000ms | by_source_point_region | outside_policy_regions | 62383 | 2836 | 4.55% |
| spatial20_fixed_5m_1000ms | by_source_point_region | west-footway-control | 4034 | 23 | 0.57% |
| spatial20_fixed_10m_400ms | by_source_type | Adult Cyclist | 2867 | 992 | 34.60% |
| spatial20_fixed_10m_400ms | by_source_type | Adult E-Scooter Driver | 2404 | 808 | 33.61% |
| spatial20_fixed_10m_400ms | by_source_type | Adult Pedestrian | 14047 | 4926 | 35.07% |
| spatial20_fixed_10m_400ms | by_source_type | Child Pedestrian | 15200 | 4425 | 29.11% |
| spatial20_fixed_10m_400ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 5148 | 30.94% |
| spatial20_fixed_10m_400ms | by_source_type | Pedestrian With Stroller | 13060 | 3164 | 24.23% |
| spatial20_fixed_10m_400ms | by_source_type | Senior Cyclist | 2837 | 1037 | 36.55% |
| spatial20_fixed_10m_400ms | by_source_type | Senior Pedestrian | 14979 | 5450 | 36.38% |
| spatial20_fixed_10m_400ms | by_source_point_region | central-through-footway | 8149 | 5044 | 61.90% |
| spatial20_fixed_10m_400ms | by_source_point_region | east-footway-control | 6410 | 1427 | 22.26% |
| spatial20_fixed_10m_400ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| spatial20_fixed_10m_400ms | by_source_point_region | outside_policy_regions | 62383 | 19021 | 30.49% |
| spatial20_fixed_10m_400ms | by_source_point_region | west-footway-control | 4034 | 458 | 11.35% |
| spatial20_fixed_10m_1000ms | by_source_type | Adult Cyclist | 2867 | 1207 | 42.10% |
| spatial20_fixed_10m_1000ms | by_source_type | Adult E-Scooter Driver | 2404 | 1051 | 43.72% |
| spatial20_fixed_10m_1000ms | by_source_type | Adult Pedestrian | 14047 | 5360 | 38.16% |
| spatial20_fixed_10m_1000ms | by_source_type | Child Pedestrian | 15200 | 5015 | 32.99% |
| spatial20_fixed_10m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 5660 | 34.02% |
| spatial20_fixed_10m_1000ms | by_source_type | Pedestrian With Stroller | 13060 | 3455 | 26.45% |
| spatial20_fixed_10m_1000ms | by_source_type | Senior Cyclist | 2837 | 1271 | 44.80% |
| spatial20_fixed_10m_1000ms | by_source_type | Senior Pedestrian | 14979 | 6016 | 40.16% |
| spatial20_fixed_10m_1000ms | by_source_point_region | central-through-footway | 8149 | 5205 | 63.87% |
| spatial20_fixed_10m_1000ms | by_source_point_region | east-footway-control | 6410 | 1542 | 24.06% |
| spatial20_fixed_10m_1000ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| spatial20_fixed_10m_1000ms | by_source_point_region | outside_policy_regions | 62383 | 21720 | 34.82% |
| spatial20_fixed_10m_1000ms | by_source_point_region | west-footway-control | 4034 | 568 | 14.08% |
| spatial20_fixed_20m_400ms | by_source_type | Adult Cyclist | 2867 | 1470 | 51.27% |
| spatial20_fixed_20m_400ms | by_source_type | Adult E-Scooter Driver | 2404 | 1320 | 54.91% |
| spatial20_fixed_20m_400ms | by_source_type | Adult Pedestrian | 14047 | 7178 | 51.10% |
| spatial20_fixed_20m_400ms | by_source_type | Child Pedestrian | 15200 | 7377 | 48.53% |
| spatial20_fixed_20m_400ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 8361 | 50.25% |
| spatial20_fixed_20m_400ms | by_source_type | Pedestrian With Stroller | 13060 | 5347 | 40.94% |
| spatial20_fixed_20m_400ms | by_source_type | Senior Cyclist | 2837 | 1654 | 58.30% |
| spatial20_fixed_20m_400ms | by_source_type | Senior Pedestrian | 14979 | 8851 | 59.09% |
| spatial20_fixed_20m_400ms | by_source_point_region | central-through-footway | 8149 | 2805 | 34.42% |
| spatial20_fixed_20m_400ms | by_source_point_region | east-footway-control | 6410 | 1950 | 30.42% |
| spatial20_fixed_20m_400ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| spatial20_fixed_20m_400ms | by_source_point_region | outside_policy_regions | 62383 | 35310 | 56.60% |
| spatial20_fixed_20m_400ms | by_source_point_region | west-footway-control | 4034 | 1493 | 37.01% |
| spatial20_fixed_20m_1000ms | by_source_type | Adult Cyclist | 2867 | 1483 | 51.73% |
| spatial20_fixed_20m_1000ms | by_source_type | Adult E-Scooter Driver | 2404 | 1331 | 55.37% |
| spatial20_fixed_20m_1000ms | by_source_type | Adult Pedestrian | 14047 | 7164 | 51.00% |
| spatial20_fixed_20m_1000ms | by_source_type | Child Pedestrian | 15200 | 7333 | 48.24% |
| spatial20_fixed_20m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16639 | 8404 | 50.51% |
| spatial20_fixed_20m_1000ms | by_source_type | Pedestrian With Stroller | 13060 | 5295 | 40.54% |
| spatial20_fixed_20m_1000ms | by_source_type | Senior Cyclist | 2837 | 1669 | 58.83% |
| spatial20_fixed_20m_1000ms | by_source_type | Senior Pedestrian | 14979 | 8802 | 58.76% |
| spatial20_fixed_20m_1000ms | by_source_point_region | central-through-footway | 8149 | 2801 | 34.37% |
| spatial20_fixed_20m_1000ms | by_source_point_region | east-footway-control | 6410 | 1680 | 26.21% |
| spatial20_fixed_20m_1000ms | by_source_point_region | entrance-vicinity | 1057 | 0 | 0.00% |
| spatial20_fixed_20m_1000ms | by_source_point_region | outside_policy_regions | 62383 | 35577 | 57.03% |
| spatial20_fixed_20m_1000ms | by_source_point_region | west-footway-control | 4034 | 1423 | 35.28% |

## Interpretation limits

Two adaptive strategies and fixed 5/10/20 m crossed with 400/1000 ms under each selected contract. Original 20 m is a deliberate negative control. Adaptive windows may reach 4000 ms. Connected fixed-grid measurements are empirical guides only: no fitted regression, statistical significance or claim for intermediate cell sizes. Compare controller choices within one policy. Changing spatial utility bounds changes the output contract; between-policy utility differences do not establish a privacy gain.

One deterministic source; no population-level statistical generalization or privacy-improvement claim.

Distinct observed-track support is an operational release condition. It is not automatically classical trajectory k-anonymity, and this comparison contains no membership, linkage or re-identification attack.
