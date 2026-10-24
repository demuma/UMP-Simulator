# Same-source mapped comparison

Status: verified. Observations SHA-256: `4abf12b390f29ce6685d37cbe5167793ed62dfc5c9207ffc42688e7419af5b5a`.

Original: all original hard root/region constraints remain. Spatial20: every existing root/region cell_side_m.max becomes20 m, equally for every method. All support, temporal and semantic bounds, regions and taxonomy remain. Selective contribution suppression is disabled in every case. Compare methods within one contract.

Source horizon: 300 s; sensor period: 100 ms; input observation contributions: 90045; peak observed simultaneous tracks: 127.

A completed source horizon does not imply a drained finite cohort. The lifecycle counts below describe the recorded horizon.

Recorded lifecycle counts: `{"active_episodes_at_horizon": 0, "pending_episodes_at_horizon": 0, "realized_ends": 183, "realized_starts": 183, "scheduled_episodes": 183, "scheduled_people": 128}`.

## Policy and retained detail

| Case | Retained input | Exact subtype / input | Mean semantic loss | Mean cell side (m) | Mean interval (ms) | Mean observation delay (ms) | p95 delay (ms) | Core (ms) | Policy violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original_adaptive_immediate | 40.50% | 0.11% | 0.50 | 9.45 | 935.86 | 517.73 | 2200.00 | 66089.03 | 0 |
| original_adaptive_spatial_first | 41.44% | 0.00% | 0.50 | 8.67 | 3892.71 | 1989.59 | 3800.00 | 49636.03 | 0 |
| original_fixed_5m_400ms | 10.17% | 0.00% | 0.50 | 5.00 | 400.00 | 249.93 | 400.00 | 988.06 | 0 |
| original_fixed_5m_1000ms | 13.11% | 0.00% | 0.50 | 5.00 | 1000.00 | 550.76 | 1000.00 | 544.65 | 0 |
| original_fixed_10m_400ms | 29.02% | 0.00% | 0.50 | 10.00 | 400.00 | 250.00 | 400.00 | 749.70 | 0 |
| original_fixed_10m_1000ms | 31.09% | 0.00% | 0.50 | 10.00 | 1000.00 | 549.39 | 1000.00 | 415.83 | 0 |
| original_fixed_20m_400ms | 0.00% | 0.00% | n/a | n/a | n/a | n/a | n/a | 519.82 | 0 |
| original_fixed_20m_1000ms | 0.00% | 0.00% | n/a | n/a | n/a | n/a | n/a | 320.55 | 0 |
| spatial20_adaptive_immediate | 67.88% | 7.97% | 0.44 | 19.64 | 518.07 | 307.22 | 400.00 | 42617.30 | 0 |
| spatial20_adaptive_spatial_first | 70.10% | 2.43% | 0.48 | 17.81 | 3463.34 | 1781.01 | 3800.00 | 47475.91 | 0 |
| spatial20_fixed_5m_400ms | 10.17% | 0.00% | 0.50 | 5.00 | 400.00 | 249.93 | 400.00 | 989.58 | 0 |
| spatial20_fixed_5m_1000ms | 13.11% | 0.00% | 0.50 | 5.00 | 1000.00 | 550.76 | 1000.00 | 539.27 | 0 |
| spatial20_fixed_10m_400ms | 38.72% | 0.00% | 0.50 | 10.00 | 400.00 | 250.04 | 400.00 | 735.32 | 0 |
| spatial20_fixed_10m_1000ms | 41.65% | 0.00% | 0.50 | 10.00 | 1000.00 | 549.45 | 1000.00 | 409.35 | 0 |
| spatial20_fixed_20m_400ms | 74.31% | 7.83% | 0.45 | 20.00 | 400.00 | 250.04 | 400.00 | 535.97 | 0 |
| spatial20_fixed_20m_1000ms | 75.69% | 8.11% | 0.45 | 20.00 | 1000.00 | 549.94 | 1000.00 | 325.62 | 0 |

Zero violations with no releases is vacuous compliance; read it together with retention. Semantic, side and interval means condition on retained observations. Exact subtype / input and retention use the full input denominator.

## Operational observed-track support

Cell statistics use distinct observed tracks per published cell-window. Category statistics use distinct tracks per published semantic bin. Both p50 values are unweighted nearest-rank medians; means are weighted by cell or category observation contributions respectively. Empty output is n/a. These are operational support statistics, not measured attack risk, privacy gain or a trajectory k-anonymity guarantee.

| Case | Cell min | Cell p50 | Cell observation-weighted mean | Category min | Category p50 | Category observation-weighted mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| original_adaptive_immediate | 5 | 6 | 8.16 | 5 | 6 | 8.16 |
| original_adaptive_spatial_first | 5 | 6 | 8.78 | 5 | 6 | 8.78 |
| original_fixed_5m_400ms | 5 | 5 | 6.18 | 5 | 5 | 6.18 |
| original_fixed_5m_1000ms | 5 | 6 | 6.33 | 5 | 6 | 6.33 |
| original_fixed_10m_400ms | 5 | 6 | 9.54 | 5 | 6 | 9.54 |
| original_fixed_10m_1000ms | 5 | 6 | 9.88 | 5 | 6 | 9.88 |
| original_fixed_20m_400ms | n/a | n/a | n/a | n/a | n/a | n/a |
| original_fixed_20m_1000ms | n/a | n/a | n/a | n/a | n/a | n/a |
| spatial20_adaptive_immediate | 5 | 8 | 14.57 | 5 | 7 | 11.42 |
| spatial20_adaptive_spatial_first | 5 | 8 | 12.85 | 5 | 8 | 11.87 |
| spatial20_fixed_5m_400ms | 5 | 5 | 6.18 | 5 | 5 | 6.18 |
| spatial20_fixed_5m_1000ms | 5 | 6 | 6.33 | 5 | 6 | 6.33 |
| spatial20_fixed_10m_400ms | 5 | 6 | 9.02 | 5 | 6 | 9.02 |
| spatial20_fixed_10m_1000ms | 5 | 7 | 9.32 | 5 | 7 | 9.32 |
| spatial20_fixed_20m_400ms | 5 | 8 | 14.86 | 5 | 7 | 12.02 |
| spatial20_fixed_20m_1000ms | 5 | 8 | 15.26 | 5 | 8 | 12.28 |

Core timing excludes input validation and file I/O. The complete comparison pipeline also includes independent Python audits and query evaluation. Neither timing is a per-step live deadline guarantee.

## Recipient queries

Total and immediate taxonomy families, identical across both contracts. Exact subtype preservation is separately source-denominated.

The table separates positive-reference queries from known-zero queries, and interior windows from source-boundary windows. Estimates use public uniform spatial/time allocation and keep their own error; missing output never becomes zero.

| Case | Lag (ms) | Cohort | Positive reference queries | Exact coverage | Estimated coverage | Estimated occupancy MAE |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| original_adaptive_immediate | 0 | interior | 7790 | 0.00% | 2.46% | 0.0654 |
| original_adaptive_immediate | 0 | boundary | 0 | n/a | n/a | n/a |
| original_adaptive_immediate | 1000 | interior | 7790 | 0.00% | 10.96% | 0.1170 |
| original_adaptive_immediate | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_adaptive_spatial_first | 0 | interior | 7790 | 0.00% | 1.31% | 0.9240 |
| original_adaptive_spatial_first | 0 | boundary | 0 | n/a | n/a | n/a |
| original_adaptive_spatial_first | 1000 | interior | 7790 | 0.00% | 5.06% | 0.7076 |
| original_adaptive_spatial_first | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_400ms | 0 | interior | 7790 | 0.00% | 0.00% | n/a |
| original_fixed_5m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_400ms | 1000 | interior | 7790 | 0.00% | 0.00% | n/a |
| original_fixed_5m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_1000ms | 0 | interior | 7790 | 0.05% | 0.05% | 0.0000 |
| original_fixed_5m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_1000ms | 1000 | interior | 7790 | 0.05% | 0.05% | 0.0000 |
| original_fixed_5m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_400ms | 0 | interior | 7790 | 0.00% | 3.75% | 0.0315 |
| original_fixed_10m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_400ms | 1000 | interior | 7790 | 0.00% | 7.55% | 0.0310 |
| original_fixed_10m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_1000ms | 0 | interior | 7790 | 10.04% | 10.04% | 0.0000 |
| original_fixed_10m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_1000ms | 1000 | interior | 7790 | 10.04% | 10.04% | 0.0000 |
| original_fixed_10m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_20m_400ms | 0 | interior | 7790 | 0.00% | 0.00% | n/a |
| original_fixed_20m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_20m_400ms | 1000 | interior | 7790 | 0.00% | 0.00% | n/a |
| original_fixed_20m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_20m_1000ms | 0 | interior | 7790 | 0.00% | 0.00% | n/a |
| original_fixed_20m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_20m_1000ms | 1000 | interior | 7790 | 0.00% | 0.00% | n/a |
| original_fixed_20m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_adaptive_immediate | 0 | interior | 7790 | 0.00% | 15.51% | 1.7524 |
| spatial20_adaptive_immediate | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_adaptive_immediate | 1000 | interior | 7790 | 0.00% | 48.19% | 1.5936 |
| spatial20_adaptive_immediate | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_adaptive_spatial_first | 0 | interior | 7790 | 0.00% | 5.80% | 1.3019 |
| spatial20_adaptive_spatial_first | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_adaptive_spatial_first | 1000 | interior | 7790 | 0.00% | 23.36% | 1.3677 |
| spatial20_adaptive_spatial_first | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_5m_400ms | 0 | interior | 7790 | 0.00% | 0.00% | n/a |
| spatial20_fixed_5m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_5m_400ms | 1000 | interior | 7790 | 0.00% | 0.00% | n/a |
| spatial20_fixed_5m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_5m_1000ms | 0 | interior | 7790 | 0.05% | 0.05% | 0.0000 |
| spatial20_fixed_5m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_5m_1000ms | 1000 | interior | 7790 | 0.05% | 0.05% | 0.0000 |
| spatial20_fixed_5m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_10m_400ms | 0 | interior | 7790 | 0.00% | 5.24% | 0.0314 |
| spatial20_fixed_10m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_10m_400ms | 1000 | interior | 7790 | 0.00% | 10.47% | 0.0309 |
| spatial20_fixed_10m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_10m_1000ms | 0 | interior | 7790 | 13.99% | 13.99% | 0.0000 |
| spatial20_fixed_10m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_10m_1000ms | 1000 | interior | 7790 | 13.99% | 13.99% | 0.0000 |
| spatial20_fixed_10m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_20m_400ms | 0 | interior | 7790 | 0.00% | 25.49% | 1.7520 |
| spatial20_fixed_20m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_20m_400ms | 1000 | interior | 7790 | 0.00% | 50.81% | 1.7597 |
| spatial20_fixed_20m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_20m_1000ms | 0 | interior | 7790 | 0.00% | 54.63% | 1.6980 |
| spatial20_fixed_20m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| spatial20_fixed_20m_1000ms | 1000 | interior | 7790 | 0.00% | 54.63% | 1.6980 |
| spatial20_fixed_20m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |

## Source type and local region costs

Each row keeps the full input denominator for that type or source-point region. Region memberships can overlap and do not sum to a global partition. Effective policy audit instead intersects the entire released footprint with every selected region.

| Case | Group kind | Group | Input contributions | Retained contributions | Retained fraction |
| --- | --- | --- | ---: | ---: | ---: |
| original_adaptive_immediate | by_source_type | Adult Pedestrian | 20736 | 8994 | 43.37% |
| original_adaptive_immediate | by_source_type | Child Pedestrian | 17796 | 7622 | 42.83% |
| original_adaptive_immediate | by_source_type | Pedestrian With Mobility Aid | 16954 | 6241 | 36.81% |
| original_adaptive_immediate | by_source_type | Pedestrian With Stroller | 19842 | 7649 | 38.55% |
| original_adaptive_immediate | by_source_type | Senior Pedestrian | 14717 | 5958 | 40.48% |
| original_adaptive_immediate | by_source_point_region | central-through-footway | 11716 | 9587 | 81.83% |
| original_adaptive_immediate | by_source_point_region | east-footway-control | 5829 | 146 | 2.50% |
| original_adaptive_immediate | by_source_point_region | entrance-vicinity | 1629 | 0 | 0.00% |
| original_adaptive_immediate | by_source_point_region | outside_policy_regions | 65286 | 26067 | 39.93% |
| original_adaptive_immediate | by_source_point_region | west-footway-control | 5585 | 664 | 11.89% |
| original_adaptive_spatial_first | by_source_type | Adult Pedestrian | 20736 | 9296 | 44.83% |
| original_adaptive_spatial_first | by_source_type | Child Pedestrian | 17796 | 7953 | 44.69% |
| original_adaptive_spatial_first | by_source_type | Pedestrian With Mobility Aid | 16954 | 6384 | 37.65% |
| original_adaptive_spatial_first | by_source_type | Pedestrian With Stroller | 19842 | 7757 | 39.09% |
| original_adaptive_spatial_first | by_source_type | Senior Pedestrian | 14717 | 5924 | 40.25% |
| original_adaptive_spatial_first | by_source_point_region | central-through-footway | 11716 | 8566 | 73.11% |
| original_adaptive_spatial_first | by_source_point_region | east-footway-control | 5829 | 215 | 3.69% |
| original_adaptive_spatial_first | by_source_point_region | entrance-vicinity | 1629 | 460 | 28.24% |
| original_adaptive_spatial_first | by_source_point_region | outside_policy_regions | 65286 | 27409 | 41.98% |
| original_adaptive_spatial_first | by_source_point_region | west-footway-control | 5585 | 664 | 11.89% |
| original_fixed_5m_400ms | by_source_type | Adult Pedestrian | 20736 | 1934 | 9.33% |
| original_fixed_5m_400ms | by_source_type | Child Pedestrian | 17796 | 2240 | 12.59% |
| original_fixed_5m_400ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 1409 | 8.31% |
| original_fixed_5m_400ms | by_source_type | Pedestrian With Stroller | 19842 | 1906 | 9.61% |
| original_fixed_5m_400ms | by_source_type | Senior Pedestrian | 14717 | 1670 | 11.35% |
| original_fixed_5m_400ms | by_source_point_region | central-through-footway | 11716 | 3803 | 32.46% |
| original_fixed_5m_400ms | by_source_point_region | east-footway-control | 5829 | 144 | 2.47% |
| original_fixed_5m_400ms | by_source_point_region | entrance-vicinity | 1629 | 0 | 0.00% |
| original_fixed_5m_400ms | by_source_point_region | outside_policy_regions | 65286 | 4661 | 7.14% |
| original_fixed_5m_400ms | by_source_point_region | west-footway-control | 5585 | 551 | 9.87% |
| original_fixed_5m_1000ms | by_source_type | Adult Pedestrian | 20736 | 2474 | 11.93% |
| original_fixed_5m_1000ms | by_source_type | Child Pedestrian | 17796 | 2873 | 16.14% |
| original_fixed_5m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 1946 | 11.48% |
| original_fixed_5m_1000ms | by_source_type | Pedestrian With Stroller | 19842 | 2458 | 12.39% |
| original_fixed_5m_1000ms | by_source_type | Senior Pedestrian | 14717 | 2058 | 13.98% |
| original_fixed_5m_1000ms | by_source_point_region | central-through-footway | 11716 | 4514 | 38.53% |
| original_fixed_5m_1000ms | by_source_point_region | east-footway-control | 5829 | 178 | 3.05% |
| original_fixed_5m_1000ms | by_source_point_region | entrance-vicinity | 1629 | 0 | 0.00% |
| original_fixed_5m_1000ms | by_source_point_region | outside_policy_regions | 65286 | 6327 | 9.69% |
| original_fixed_5m_1000ms | by_source_point_region | west-footway-control | 5585 | 790 | 14.15% |
| original_fixed_10m_400ms | by_source_type | Adult Pedestrian | 20736 | 6925 | 33.40% |
| original_fixed_10m_400ms | by_source_type | Child Pedestrian | 17796 | 5326 | 29.93% |
| original_fixed_10m_400ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 4356 | 25.69% |
| original_fixed_10m_400ms | by_source_type | Pedestrian With Stroller | 19842 | 5499 | 27.71% |
| original_fixed_10m_400ms | by_source_type | Senior Pedestrian | 14717 | 4021 | 27.32% |
| original_fixed_10m_400ms | by_source_point_region | central-through-footway | 11716 | 8650 | 73.83% |
| original_fixed_10m_400ms | by_source_point_region | east-footway-control | 5829 | 0 | 0.00% |
| original_fixed_10m_400ms | by_source_point_region | entrance-vicinity | 1629 | 157 | 9.64% |
| original_fixed_10m_400ms | by_source_point_region | outside_policy_regions | 65286 | 17320 | 26.53% |
| original_fixed_10m_400ms | by_source_point_region | west-footway-control | 5585 | 0 | 0.00% |
| original_fixed_10m_1000ms | by_source_type | Adult Pedestrian | 20736 | 7337 | 35.38% |
| original_fixed_10m_1000ms | by_source_type | Child Pedestrian | 17796 | 5758 | 32.36% |
| original_fixed_10m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 4751 | 28.02% |
| original_fixed_10m_1000ms | by_source_type | Pedestrian With Stroller | 19842 | 5823 | 29.35% |
| original_fixed_10m_1000ms | by_source_type | Senior Pedestrian | 14717 | 4329 | 29.41% |
| original_fixed_10m_1000ms | by_source_point_region | central-through-footway | 11716 | 8899 | 75.96% |
| original_fixed_10m_1000ms | by_source_point_region | east-footway-control | 5829 | 0 | 0.00% |
| original_fixed_10m_1000ms | by_source_point_region | entrance-vicinity | 1629 | 212 | 13.01% |
| original_fixed_10m_1000ms | by_source_point_region | outside_policy_regions | 65286 | 18887 | 28.93% |
| original_fixed_10m_1000ms | by_source_point_region | west-footway-control | 5585 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Adult Pedestrian | 20736 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Child Pedestrian | 17796 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Pedestrian With Stroller | 19842 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_type | Senior Pedestrian | 14717 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | central-through-footway | 11716 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | east-footway-control | 5829 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | entrance-vicinity | 1629 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | outside_policy_regions | 65286 | 0 | 0.00% |
| original_fixed_20m_400ms | by_source_point_region | west-footway-control | 5585 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Adult Pedestrian | 20736 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Child Pedestrian | 17796 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Pedestrian With Stroller | 19842 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_type | Senior Pedestrian | 14717 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | central-through-footway | 11716 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | east-footway-control | 5829 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | entrance-vicinity | 1629 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | outside_policy_regions | 65286 | 0 | 0.00% |
| original_fixed_20m_1000ms | by_source_point_region | west-footway-control | 5585 | 0 | 0.00% |
| spatial20_adaptive_immediate | by_source_type | Adult Pedestrian | 20736 | 15001 | 72.34% |
| spatial20_adaptive_immediate | by_source_type | Child Pedestrian | 17796 | 11232 | 63.12% |
| spatial20_adaptive_immediate | by_source_type | Pedestrian With Mobility Aid | 16954 | 11123 | 65.61% |
| spatial20_adaptive_immediate | by_source_type | Pedestrian With Stroller | 19842 | 12995 | 65.49% |
| spatial20_adaptive_immediate | by_source_type | Senior Pedestrian | 14717 | 10768 | 73.17% |
| spatial20_adaptive_immediate | by_source_point_region | central-through-footway | 11716 | 10109 | 86.28% |
| spatial20_adaptive_immediate | by_source_point_region | east-footway-control | 5829 | 4917 | 84.35% |
| spatial20_adaptive_immediate | by_source_point_region | entrance-vicinity | 1629 | 0 | 0.00% |
| spatial20_adaptive_immediate | by_source_point_region | outside_policy_regions | 65286 | 44475 | 68.12% |
| spatial20_adaptive_immediate | by_source_point_region | west-footway-control | 5585 | 1618 | 28.97% |
| spatial20_adaptive_spatial_first | by_source_type | Adult Pedestrian | 20736 | 15070 | 72.68% |
| spatial20_adaptive_spatial_first | by_source_type | Child Pedestrian | 17796 | 11879 | 66.75% |
| spatial20_adaptive_spatial_first | by_source_type | Pedestrian With Mobility Aid | 16954 | 11879 | 70.07% |
| spatial20_adaptive_spatial_first | by_source_type | Pedestrian With Stroller | 19842 | 13290 | 66.98% |
| spatial20_adaptive_spatial_first | by_source_type | Senior Pedestrian | 14717 | 11000 | 74.74% |
| spatial20_adaptive_spatial_first | by_source_point_region | central-through-footway | 11716 | 8389 | 71.60% |
| spatial20_adaptive_spatial_first | by_source_point_region | east-footway-control | 5829 | 4650 | 79.77% |
| spatial20_adaptive_spatial_first | by_source_point_region | entrance-vicinity | 1629 | 939 | 57.64% |
| spatial20_adaptive_spatial_first | by_source_point_region | outside_policy_regions | 65286 | 47524 | 72.79% |
| spatial20_adaptive_spatial_first | by_source_point_region | west-footway-control | 5585 | 1616 | 28.93% |
| spatial20_fixed_5m_400ms | by_source_type | Adult Pedestrian | 20736 | 1934 | 9.33% |
| spatial20_fixed_5m_400ms | by_source_type | Child Pedestrian | 17796 | 2240 | 12.59% |
| spatial20_fixed_5m_400ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 1409 | 8.31% |
| spatial20_fixed_5m_400ms | by_source_type | Pedestrian With Stroller | 19842 | 1906 | 9.61% |
| spatial20_fixed_5m_400ms | by_source_type | Senior Pedestrian | 14717 | 1670 | 11.35% |
| spatial20_fixed_5m_400ms | by_source_point_region | central-through-footway | 11716 | 3803 | 32.46% |
| spatial20_fixed_5m_400ms | by_source_point_region | east-footway-control | 5829 | 144 | 2.47% |
| spatial20_fixed_5m_400ms | by_source_point_region | entrance-vicinity | 1629 | 0 | 0.00% |
| spatial20_fixed_5m_400ms | by_source_point_region | outside_policy_regions | 65286 | 4661 | 7.14% |
| spatial20_fixed_5m_400ms | by_source_point_region | west-footway-control | 5585 | 551 | 9.87% |
| spatial20_fixed_5m_1000ms | by_source_type | Adult Pedestrian | 20736 | 2474 | 11.93% |
| spatial20_fixed_5m_1000ms | by_source_type | Child Pedestrian | 17796 | 2873 | 16.14% |
| spatial20_fixed_5m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 1946 | 11.48% |
| spatial20_fixed_5m_1000ms | by_source_type | Pedestrian With Stroller | 19842 | 2458 | 12.39% |
| spatial20_fixed_5m_1000ms | by_source_type | Senior Pedestrian | 14717 | 2058 | 13.98% |
| spatial20_fixed_5m_1000ms | by_source_point_region | central-through-footway | 11716 | 4514 | 38.53% |
| spatial20_fixed_5m_1000ms | by_source_point_region | east-footway-control | 5829 | 178 | 3.05% |
| spatial20_fixed_5m_1000ms | by_source_point_region | entrance-vicinity | 1629 | 0 | 0.00% |
| spatial20_fixed_5m_1000ms | by_source_point_region | outside_policy_regions | 65286 | 6327 | 9.69% |
| spatial20_fixed_5m_1000ms | by_source_point_region | west-footway-control | 5585 | 790 | 14.15% |
| spatial20_fixed_10m_400ms | by_source_type | Adult Pedestrian | 20736 | 8435 | 40.68% |
| spatial20_fixed_10m_400ms | by_source_type | Child Pedestrian | 17796 | 7767 | 43.64% |
| spatial20_fixed_10m_400ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 5843 | 34.46% |
| spatial20_fixed_10m_400ms | by_source_type | Pedestrian With Stroller | 19842 | 7208 | 36.33% |
| spatial20_fixed_10m_400ms | by_source_type | Senior Pedestrian | 14717 | 5616 | 38.16% |
| spatial20_fixed_10m_400ms | by_source_point_region | central-through-footway | 11716 | 8650 | 73.83% |
| spatial20_fixed_10m_400ms | by_source_point_region | east-footway-control | 5829 | 2546 | 43.68% |
| spatial20_fixed_10m_400ms | by_source_point_region | entrance-vicinity | 1629 | 157 | 9.64% |
| spatial20_fixed_10m_400ms | by_source_point_region | outside_policy_regions | 65286 | 21551 | 33.01% |
| spatial20_fixed_10m_400ms | by_source_point_region | west-footway-control | 5585 | 1965 | 35.18% |
| spatial20_fixed_10m_1000ms | by_source_type | Adult Pedestrian | 20736 | 9088 | 43.83% |
| spatial20_fixed_10m_1000ms | by_source_type | Child Pedestrian | 17796 | 8327 | 46.79% |
| spatial20_fixed_10m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 6364 | 37.54% |
| spatial20_fixed_10m_1000ms | by_source_type | Pedestrian With Stroller | 19842 | 7686 | 38.74% |
| spatial20_fixed_10m_1000ms | by_source_type | Senior Pedestrian | 14717 | 6039 | 41.03% |
| spatial20_fixed_10m_1000ms | by_source_point_region | central-through-footway | 11716 | 8899 | 75.96% |
| spatial20_fixed_10m_1000ms | by_source_point_region | east-footway-control | 5829 | 2907 | 49.87% |
| spatial20_fixed_10m_1000ms | by_source_point_region | entrance-vicinity | 1629 | 212 | 13.01% |
| spatial20_fixed_10m_1000ms | by_source_point_region | outside_policy_regions | 65286 | 23404 | 35.85% |
| spatial20_fixed_10m_1000ms | by_source_point_region | west-footway-control | 5585 | 2082 | 37.28% |
| spatial20_fixed_20m_400ms | by_source_type | Adult Pedestrian | 20736 | 16332 | 78.76% |
| spatial20_fixed_20m_400ms | by_source_type | Child Pedestrian | 17796 | 13719 | 77.09% |
| spatial20_fixed_20m_400ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 11768 | 69.41% |
| spatial20_fixed_20m_400ms | by_source_type | Pedestrian With Stroller | 19842 | 13844 | 69.77% |
| spatial20_fixed_20m_400ms | by_source_type | Senior Pedestrian | 14717 | 11246 | 76.42% |
| spatial20_fixed_20m_400ms | by_source_point_region | central-through-footway | 11716 | 9845 | 84.03% |
| spatial20_fixed_20m_400ms | by_source_point_region | east-footway-control | 5829 | 5033 | 86.34% |
| spatial20_fixed_20m_400ms | by_source_point_region | entrance-vicinity | 1629 | 724 | 44.44% |
| spatial20_fixed_20m_400ms | by_source_point_region | outside_policy_regions | 65286 | 46612 | 71.40% |
| spatial20_fixed_20m_400ms | by_source_point_region | west-footway-control | 5585 | 4695 | 84.06% |
| spatial20_fixed_20m_1000ms | by_source_type | Adult Pedestrian | 20736 | 16563 | 79.88% |
| spatial20_fixed_20m_1000ms | by_source_type | Child Pedestrian | 17796 | 13922 | 78.23% |
| spatial20_fixed_20m_1000ms | by_source_type | Pedestrian With Mobility Aid | 16954 | 12029 | 70.95% |
| spatial20_fixed_20m_1000ms | by_source_type | Pedestrian With Stroller | 19842 | 14189 | 71.51% |
| spatial20_fixed_20m_1000ms | by_source_type | Senior Pedestrian | 14717 | 11450 | 77.80% |
| spatial20_fixed_20m_1000ms | by_source_point_region | central-through-footway | 11716 | 9861 | 84.17% |
| spatial20_fixed_20m_1000ms | by_source_point_region | east-footway-control | 5829 | 5138 | 88.15% |
| spatial20_fixed_20m_1000ms | by_source_point_region | entrance-vicinity | 1629 | 808 | 49.60% |
| spatial20_fixed_20m_1000ms | by_source_point_region | outside_policy_regions | 65286 | 47615 | 72.93% |
| spatial20_fixed_20m_1000ms | by_source_point_region | west-footway-control | 5585 | 4731 | 84.71% |

## Interpretation limits

Two adaptive strategies and fixed 5/10/20 m crossed with 400/1000 ms under each selected contract. Original 20 m is a deliberate negative control. Adaptive windows may reach 4000 ms. Connected fixed-grid measurements are empirical guides only: no fitted regression, statistical significance or claim for intermediate cell sizes. Compare controller choices within one policy. Changing spatial utility bounds changes the output contract; between-policy utility differences do not establish a privacy gain.

One deterministic source; no population-level statistical generalization or privacy-improvement claim.

Distinct observed-track support is an operational release condition. It is not automatically classical trajectory k-anonymity, and this comparison contains no membership, linkage or re-identification attack.
