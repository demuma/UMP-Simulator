# Same-source mapped comparison

Status: verified. Observations SHA-256: `f43a28abaa253816e34732f29f07f63b953ecc40f57aae884c349329c6b9a1a1`.

Support-only sensitivity: support60 lowers each root/region type/instance support floor to ceil(0.6*n). All other hard constraints, taxonomy and release triggers match. Compare methods within a policy; policy changes alter the protection contract.

Source horizon: 240 s; sensor period: 100 ms; input observation contributions: 187745; peak observed simultaneous tracks: 224.

A completed source horizon does not imply a drained finite cohort. The lifecycle counts below describe the recorded horizon.

Recorded lifecycle counts: `{"active_episodes_at_horizon": 0, "pending_episodes_at_horizon": 0, "realized_ends": 360, "realized_starts": 360, "scheduled_episodes": 360, "scheduled_people": 256}`.

## Policy and retained detail

| Case | Retained input | Exact subtype / input | Mean semantic loss | Mean cell side (m) | Mean interval (ms) | Mean observation delay (ms) | p95 delay (ms) | Core (ms) | Policy violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original_adaptive_immediate | 61.77% | 0.03% | 0.64 | 9.38 | 678.38 | 390.75 | 1400.00 | 124201.05 | 0 |
| original_fixed_5m_400ms | 24.37% | 0.02% | 0.56 | 5.00 | 400.00 | 249.95 | 400.00 | 1838.22 | 0 |
| original_fixed_5m_1000ms | 29.10% | 0.02% | 0.57 | 5.00 | 1000.00 | 550.29 | 1000.00 | 962.20 | 0 |
| original_fixed_10m_400ms | 50.89% | 0.02% | 0.65 | 10.00 | 400.00 | 250.01 | 400.00 | 1268.28 | 0 |
| original_fixed_10m_1000ms | 52.68% | 0.00% | 0.65 | 10.00 | 1000.00 | 549.95 | 1000.00 | 759.46 | 0 |
| support60_adaptive_immediate | 78.70% | 3.39% | 0.59 | 8.68 | 563.26 | 331.92 | 800.00 | 111002.77 | 0 |
| support60_fixed_5m_400ms | 50.34% | 0.61% | 0.57 | 5.00 | 400.00 | 249.99 | 400.00 | 1854.46 | 0 |
| support60_fixed_5m_1000ms | 55.40% | 0.56% | 0.58 | 5.00 | 1000.00 | 550.01 | 1000.00 | 997.89 | 0 |
| support60_fixed_10m_400ms | 65.64% | 3.41% | 0.60 | 10.00 | 400.00 | 249.98 | 400.00 | 1366.56 | 0 |
| support60_fixed_10m_1000ms | 66.85% | 3.84% | 0.59 | 10.00 | 1000.00 | 549.76 | 1000.00 | 763.51 | 0 |

Zero violations with no releases is vacuous compliance; read it together with retention. Semantic, side and interval means condition on retained observations. Exact subtype / input and retention use the full input denominator.

## Operational observed-track support

Cell statistics use distinct observed tracks per published cell-window. Category statistics use distinct tracks per published semantic bin. Both p50 values are unweighted nearest-rank medians; means are weighted by cell or category observation contributions respectively. Empty output is n/a. These are operational support statistics, not measured attack risk, privacy gain or a trajectory k-anonymity guarantee.

| Case | Cell min | Cell p50 | Cell observation-weighted mean | Category min | Category p50 | Category observation-weighted mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| original_adaptive_immediate | 5 | 7 | 10.32 | 5 | 7 | 10.32 |
| original_fixed_5m_400ms | 5 | 6 | 7.24 | 5 | 6 | 7.24 |
| original_fixed_5m_1000ms | 5 | 6 | 7.45 | 5 | 6 | 7.45 |
| original_fixed_10m_400ms | 5 | 8 | 11.81 | 5 | 8 | 11.81 |
| original_fixed_10m_1000ms | 5 | 8 | 12.29 | 5 | 8 | 12.29 |
| support60_adaptive_immediate | 3 | 4 | 8.21 | 3 | 4 | 7.50 |
| support60_fixed_5m_400ms | 3 | 4 | 5.27 | 3 | 4 | 5.26 |
| support60_fixed_5m_1000ms | 3 | 4 | 5.55 | 3 | 4 | 5.54 |
| support60_fixed_10m_400ms | 3 | 5 | 10.00 | 3 | 5 | 9.06 |
| support60_fixed_10m_1000ms | 3 | 5 | 10.49 | 3 | 5 | 9.36 |

Core timing excludes input validation and file I/O. The complete comparison pipeline also includes independent Python audits and query evaluation. Neither timing is a per-step live deadline guarantee.

## Recipient queries

Total and immediate taxonomy families; fine-label preservation is reported separately.

The table separates positive-reference queries from known-zero queries, and interior windows from source-boundary windows. Estimates use public uniform spatial/time allocation and keep their own error; missing output never becomes zero.

| Case | Lag (ms) | Cohort | Positive reference queries | Exact coverage | Estimated coverage | Estimated occupancy MAE |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| original_adaptive_immediate | 0 | interior | 11826 | 0.01% | 3.44% | 0.0628 |
| original_adaptive_immediate | 0 | boundary | 0 | n/a | n/a | n/a |
| original_adaptive_immediate | 1000 | interior | 11826 | 0.01% | 16.37% | 0.0904 |
| original_adaptive_immediate | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_400ms | 0 | interior | 11826 | 0.00% | 0.00% | n/a |
| original_fixed_5m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_400ms | 1000 | interior | 11826 | 0.00% | 0.00% | n/a |
| original_fixed_5m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_1000ms | 0 | interior | 11826 | 0.06% | 0.06% | 0.0000 |
| original_fixed_5m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_1000ms | 1000 | interior | 11826 | 0.06% | 0.06% | 0.0000 |
| original_fixed_5m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_400ms | 0 | interior | 11826 | 0.00% | 6.67% | 0.0378 |
| original_fixed_10m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_400ms | 1000 | interior | 11826 | 0.00% | 13.47% | 0.0382 |
| original_fixed_10m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_1000ms | 0 | interior | 11826 | 16.46% | 16.46% | 0.0000 |
| original_fixed_10m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_1000ms | 1000 | interior | 11826 | 16.46% | 16.46% | 0.0000 |
| original_fixed_10m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| support60_adaptive_immediate | 0 | interior | 11826 | 0.02% | 6.82% | 0.0376 |
| support60_adaptive_immediate | 0 | boundary | 0 | n/a | n/a | n/a |
| support60_adaptive_immediate | 1000 | interior | 11826 | 0.02% | 24.07% | 0.0550 |
| support60_adaptive_immediate | 1000 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_5m_400ms | 0 | interior | 11826 | 0.00% | 0.04% | 0.0300 |
| support60_fixed_5m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_5m_400ms | 1000 | interior | 11826 | 0.00% | 0.08% | 0.0500 |
| support60_fixed_5m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_5m_1000ms | 0 | interior | 11826 | 0.72% | 0.72% | 0.0000 |
| support60_fixed_5m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_5m_1000ms | 1000 | interior | 11826 | 0.72% | 0.72% | 0.0000 |
| support60_fixed_5m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_10m_400ms | 0 | interior | 11826 | 0.00% | 12.86% | 0.0282 |
| support60_fixed_10m_400ms | 0 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_10m_400ms | 1000 | interior | 11826 | 0.00% | 25.68% | 0.0285 |
| support60_fixed_10m_400ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_10m_1000ms | 0 | interior | 11826 | 30.67% | 30.67% | 0.0000 |
| support60_fixed_10m_1000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_10m_1000ms | 1000 | interior | 11826 | 30.67% | 30.67% | 0.0000 |
| support60_fixed_10m_1000ms | 1000 | boundary | 0 | n/a | n/a | n/a |

## Source type and local region costs

Each row keeps the full input denominator for that type or source-point region. Region memberships can overlap and do not sum to a global partition. Effective policy audit instead intersects the entire released footprint with every selected region.

| Case | Group kind | Group | Input contributions | Retained contributions | Retained fraction |
| --- | --- | --- | ---: | ---: | ---: |
| original_adaptive_immediate | by_source_type | Adult Cyclist | 6177 | 4962 | 80.33% |
| original_adaptive_immediate | by_source_type | Adult E-Scooter Driver | 6056 | 5101 | 84.23% |
| original_adaptive_immediate | by_source_type | Adult Pedestrian | 38168 | 22132 | 57.99% |
| original_adaptive_immediate | by_source_type | Child Pedestrian | 35088 | 20176 | 57.50% |
| original_adaptive_immediate | by_source_type | Pedestrian With Mobility Aid | 34606 | 21925 | 63.36% |
| original_adaptive_immediate | by_source_type | Pedestrian With Stroller | 35929 | 22937 | 63.84% |
| original_adaptive_immediate | by_source_type | Senior Cyclist | 6048 | 5036 | 83.27% |
| original_adaptive_immediate | by_source_type | Senior Pedestrian | 25673 | 13698 | 53.36% |
| original_adaptive_immediate | by_source_point_region | central-through-footway | 36674 | 34296 | 93.52% |
| original_adaptive_immediate | by_source_point_region | east-footway-control | 9442 | 1091 | 11.55% |
| original_adaptive_immediate | by_source_point_region | entrance-vicinity | 4084 | 1659 | 40.62% |
| original_adaptive_immediate | by_source_point_region | outside_policy_regions | 126885 | 77292 | 60.92% |
| original_adaptive_immediate | by_source_point_region | west-footway-control | 10660 | 1629 | 15.28% |
| original_fixed_5m_400ms | by_source_type | Adult Cyclist | 6177 | 916 | 14.83% |
| original_fixed_5m_400ms | by_source_type | Adult E-Scooter Driver | 6056 | 868 | 14.33% |
| original_fixed_5m_400ms | by_source_type | Adult Pedestrian | 38168 | 9658 | 25.30% |
| original_fixed_5m_400ms | by_source_type | Child Pedestrian | 35088 | 7975 | 22.73% |
| original_fixed_5m_400ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 10382 | 30.00% |
| original_fixed_5m_400ms | by_source_type | Pedestrian With Stroller | 35929 | 9569 | 26.63% |
| original_fixed_5m_400ms | by_source_type | Senior Cyclist | 6048 | 828 | 13.69% |
| original_fixed_5m_400ms | by_source_type | Senior Pedestrian | 25673 | 5550 | 21.62% |
| original_fixed_5m_400ms | by_source_point_region | central-through-footway | 36674 | 21447 | 58.48% |
| original_fixed_5m_400ms | by_source_point_region | east-footway-control | 9442 | 913 | 9.67% |
| original_fixed_5m_400ms | by_source_point_region | entrance-vicinity | 4084 | 0 | 0.00% |
| original_fixed_5m_400ms | by_source_point_region | outside_policy_regions | 126885 | 21948 | 17.30% |
| original_fixed_5m_400ms | by_source_point_region | west-footway-control | 10660 | 1438 | 13.49% |
| original_fixed_5m_1000ms | by_source_type | Adult Cyclist | 6177 | 1391 | 22.52% |
| original_fixed_5m_1000ms | by_source_type | Adult E-Scooter Driver | 6056 | 1493 | 24.65% |
| original_fixed_5m_1000ms | by_source_type | Adult Pedestrian | 38168 | 11314 | 29.64% |
| original_fixed_5m_1000ms | by_source_type | Child Pedestrian | 35088 | 9534 | 27.17% |
| original_fixed_5m_1000ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 11973 | 34.60% |
| original_fixed_5m_1000ms | by_source_type | Pedestrian With Stroller | 35929 | 11258 | 31.33% |
| original_fixed_5m_1000ms | by_source_type | Senior Cyclist | 6048 | 1270 | 21.00% |
| original_fixed_5m_1000ms | by_source_type | Senior Pedestrian | 25673 | 6407 | 24.96% |
| original_fixed_5m_1000ms | by_source_point_region | central-through-footway | 36674 | 23554 | 64.23% |
| original_fixed_5m_1000ms | by_source_point_region | east-footway-control | 9442 | 1182 | 12.52% |
| original_fixed_5m_1000ms | by_source_point_region | entrance-vicinity | 4084 | 0 | 0.00% |
| original_fixed_5m_1000ms | by_source_point_region | outside_policy_regions | 126885 | 27982 | 22.05% |
| original_fixed_5m_1000ms | by_source_point_region | west-footway-control | 10660 | 1922 | 18.03% |
| original_fixed_10m_400ms | by_source_type | Adult Cyclist | 6177 | 4143 | 67.07% |
| original_fixed_10m_400ms | by_source_type | Adult E-Scooter Driver | 6056 | 4307 | 71.12% |
| original_fixed_10m_400ms | by_source_type | Adult Pedestrian | 38168 | 18620 | 48.78% |
| original_fixed_10m_400ms | by_source_type | Child Pedestrian | 35088 | 15996 | 45.59% |
| original_fixed_10m_400ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 18555 | 53.62% |
| original_fixed_10m_400ms | by_source_type | Pedestrian With Stroller | 35929 | 18906 | 52.62% |
| original_fixed_10m_400ms | by_source_type | Senior Cyclist | 6048 | 4137 | 68.40% |
| original_fixed_10m_400ms | by_source_type | Senior Pedestrian | 25673 | 10875 | 42.36% |
| original_fixed_10m_400ms | by_source_point_region | central-through-footway | 36674 | 32839 | 89.54% |
| original_fixed_10m_400ms | by_source_point_region | east-footway-control | 9442 | 0 | 0.00% |
| original_fixed_10m_400ms | by_source_point_region | entrance-vicinity | 4084 | 1739 | 42.58% |
| original_fixed_10m_400ms | by_source_point_region | outside_policy_regions | 126885 | 60961 | 48.04% |
| original_fixed_10m_400ms | by_source_point_region | west-footway-control | 10660 | 0 | 0.00% |
| original_fixed_10m_1000ms | by_source_type | Adult Cyclist | 6177 | 4383 | 70.96% |
| original_fixed_10m_1000ms | by_source_type | Adult E-Scooter Driver | 6056 | 4513 | 74.52% |
| original_fixed_10m_1000ms | by_source_type | Adult Pedestrian | 38168 | 19341 | 50.67% |
| original_fixed_10m_1000ms | by_source_type | Child Pedestrian | 35088 | 16487 | 46.99% |
| original_fixed_10m_1000ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 19040 | 55.02% |
| original_fixed_10m_1000ms | by_source_type | Pedestrian With Stroller | 35929 | 19509 | 54.30% |
| original_fixed_10m_1000ms | by_source_type | Senior Cyclist | 6048 | 4374 | 72.32% |
| original_fixed_10m_1000ms | by_source_type | Senior Pedestrian | 25673 | 11259 | 43.86% |
| original_fixed_10m_1000ms | by_source_point_region | central-through-footway | 36674 | 32980 | 89.93% |
| original_fixed_10m_1000ms | by_source_point_region | east-footway-control | 9442 | 0 | 0.00% |
| original_fixed_10m_1000ms | by_source_point_region | entrance-vicinity | 4084 | 1805 | 44.20% |
| original_fixed_10m_1000ms | by_source_point_region | outside_policy_regions | 126885 | 64121 | 50.53% |
| original_fixed_10m_1000ms | by_source_point_region | west-footway-control | 10660 | 0 | 0.00% |
| support60_adaptive_immediate | by_source_type | Adult Cyclist | 6177 | 5521 | 89.38% |
| support60_adaptive_immediate | by_source_type | Adult E-Scooter Driver | 6056 | 5536 | 91.41% |
| support60_adaptive_immediate | by_source_type | Adult Pedestrian | 38168 | 28602 | 74.94% |
| support60_adaptive_immediate | by_source_type | Child Pedestrian | 35088 | 27428 | 78.17% |
| support60_adaptive_immediate | by_source_type | Pedestrian With Mobility Aid | 34606 | 27272 | 78.81% |
| support60_adaptive_immediate | by_source_type | Pedestrian With Stroller | 35929 | 28957 | 80.60% |
| support60_adaptive_immediate | by_source_type | Senior Cyclist | 6048 | 5518 | 91.24% |
| support60_adaptive_immediate | by_source_type | Senior Pedestrian | 25673 | 18912 | 73.66% |
| support60_adaptive_immediate | by_source_point_region | central-through-footway | 36674 | 35480 | 96.74% |
| support60_adaptive_immediate | by_source_point_region | east-footway-control | 9442 | 2574 | 27.26% |
| support60_adaptive_immediate | by_source_point_region | entrance-vicinity | 4084 | 3479 | 85.19% |
| support60_adaptive_immediate | by_source_point_region | outside_policy_regions | 126885 | 101162 | 79.73% |
| support60_adaptive_immediate | by_source_point_region | west-footway-control | 10660 | 5051 | 47.38% |
| support60_fixed_5m_400ms | by_source_type | Adult Cyclist | 6177 | 3237 | 52.40% |
| support60_fixed_5m_400ms | by_source_type | Adult E-Scooter Driver | 6056 | 3386 | 55.91% |
| support60_fixed_5m_400ms | by_source_type | Adult Pedestrian | 38168 | 18312 | 47.98% |
| support60_fixed_5m_400ms | by_source_type | Child Pedestrian | 35088 | 17499 | 49.87% |
| support60_fixed_5m_400ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 19060 | 55.08% |
| support60_fixed_5m_400ms | by_source_type | Pedestrian With Stroller | 35929 | 18849 | 52.46% |
| support60_fixed_5m_400ms | by_source_type | Senior Cyclist | 6048 | 2941 | 48.63% |
| support60_fixed_5m_400ms | by_source_type | Senior Pedestrian | 25673 | 11232 | 43.75% |
| support60_fixed_5m_400ms | by_source_point_region | central-through-footway | 36674 | 30065 | 81.98% |
| support60_fixed_5m_400ms | by_source_point_region | east-footway-control | 9442 | 2669 | 28.27% |
| support60_fixed_5m_400ms | by_source_point_region | entrance-vicinity | 4084 | 128 | 3.13% |
| support60_fixed_5m_400ms | by_source_point_region | outside_policy_regions | 126885 | 56763 | 44.74% |
| support60_fixed_5m_400ms | by_source_point_region | west-footway-control | 10660 | 4891 | 45.88% |
| support60_fixed_5m_1000ms | by_source_type | Adult Cyclist | 6177 | 3833 | 62.05% |
| support60_fixed_5m_1000ms | by_source_type | Adult E-Scooter Driver | 6056 | 4039 | 66.69% |
| support60_fixed_5m_1000ms | by_source_type | Adult Pedestrian | 38168 | 19868 | 52.05% |
| support60_fixed_5m_1000ms | by_source_type | Child Pedestrian | 35088 | 19296 | 54.99% |
| support60_fixed_5m_1000ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 20688 | 59.78% |
| support60_fixed_5m_1000ms | by_source_type | Pedestrian With Stroller | 35929 | 20384 | 56.73% |
| support60_fixed_5m_1000ms | by_source_type | Senior Cyclist | 6048 | 3547 | 58.65% |
| support60_fixed_5m_1000ms | by_source_type | Senior Pedestrian | 25673 | 12349 | 48.10% |
| support60_fixed_5m_1000ms | by_source_point_region | central-through-footway | 36674 | 31247 | 85.20% |
| support60_fixed_5m_1000ms | by_source_point_region | east-footway-control | 9442 | 2790 | 29.55% |
| support60_fixed_5m_1000ms | by_source_point_region | entrance-vicinity | 4084 | 279 | 6.83% |
| support60_fixed_5m_1000ms | by_source_point_region | outside_policy_regions | 126885 | 64018 | 50.45% |
| support60_fixed_5m_1000ms | by_source_point_region | west-footway-control | 10660 | 5670 | 53.19% |
| support60_fixed_10m_400ms | by_source_type | Adult Cyclist | 6177 | 4939 | 79.96% |
| support60_fixed_10m_400ms | by_source_type | Adult E-Scooter Driver | 6056 | 5017 | 82.84% |
| support60_fixed_10m_400ms | by_source_type | Adult Pedestrian | 38168 | 24428 | 64.00% |
| support60_fixed_10m_400ms | by_source_type | Child Pedestrian | 35088 | 22282 | 63.50% |
| support60_fixed_10m_400ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 22478 | 64.95% |
| support60_fixed_10m_400ms | by_source_type | Pedestrian With Stroller | 35929 | 24497 | 68.18% |
| support60_fixed_10m_400ms | by_source_type | Senior Cyclist | 6048 | 4851 | 80.21% |
| support60_fixed_10m_400ms | by_source_type | Senior Pedestrian | 25673 | 14737 | 57.40% |
| support60_fixed_10m_400ms | by_source_point_region | central-through-footway | 36674 | 35131 | 95.79% |
| support60_fixed_10m_400ms | by_source_point_region | east-footway-control | 9442 | 0 | 0.00% |
| support60_fixed_10m_400ms | by_source_point_region | entrance-vicinity | 4084 | 3190 | 78.11% |
| support60_fixed_10m_400ms | by_source_point_region | outside_policy_regions | 126885 | 84908 | 66.92% |
| support60_fixed_10m_400ms | by_source_point_region | west-footway-control | 10660 | 0 | 0.00% |
| support60_fixed_10m_1000ms | by_source_type | Adult Cyclist | 6177 | 5026 | 81.37% |
| support60_fixed_10m_1000ms | by_source_type | Adult E-Scooter Driver | 6056 | 5081 | 83.90% |
| support60_fixed_10m_1000ms | by_source_type | Adult Pedestrian | 38168 | 24931 | 65.32% |
| support60_fixed_10m_1000ms | by_source_type | Child Pedestrian | 35088 | 22660 | 64.58% |
| support60_fixed_10m_1000ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 22772 | 65.80% |
| support60_fixed_10m_1000ms | by_source_type | Pedestrian With Stroller | 35929 | 24997 | 69.57% |
| support60_fixed_10m_1000ms | by_source_type | Senior Cyclist | 6048 | 4969 | 82.16% |
| support60_fixed_10m_1000ms | by_source_type | Senior Pedestrian | 25673 | 15063 | 58.67% |
| support60_fixed_10m_1000ms | by_source_point_region | central-through-footway | 36674 | 34852 | 95.03% |
| support60_fixed_10m_1000ms | by_source_point_region | east-footway-control | 9442 | 0 | 0.00% |
| support60_fixed_10m_1000ms | by_source_point_region | entrance-vicinity | 4084 | 3356 | 82.17% |
| support60_fixed_10m_1000ms | by_source_point_region | outside_policy_regions | 126885 | 87291 | 68.80% |
| support60_fixed_10m_1000ms | by_source_point_region | west-footway-control | 10660 | 0 | 0.00% |

## Interpretation limits

The fixed portfolio is a declared subset (5/10 m crossed with 400/1000 ms), not a claim of the best possible uniform schedule. Compare controller choices within one policy. Relaxing support changes the protection contract, so improved utility across policies does not establish a privacy gain.

One deterministic source; no population-level statistical generalization or privacy-improvement claim.

Distinct observed-track support is an operational release condition. It is not automatically classical trajectory k-anonymity, and this comparison contains no membership, linkage or re-identification attack.
