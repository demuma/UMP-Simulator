# Same-source mapped comparison

Status: verified. Observations SHA-256: `f43a28abaa253816e34732f29f07f63b953ecc40f57aae884c349329c6b9a1a1`.

Support-only sensitivity: support60 lowers each root/region type/instance support floor to ceil(0.6*n). All other hard constraints, taxonomy and release triggers match. Compare methods within a policy; policy changes alter the protection contract.

Source horizon: 240 s; sensor period: 100 ms; input observation contributions: 187745; peak observed simultaneous tracks: 224.

A completed source horizon does not imply a drained finite cohort. The lifecycle counts below describe the recorded horizon.

Recorded lifecycle counts: `{"active_episodes_at_horizon": 0, "pending_episodes_at_horizon": 0, "realized_ends": 360, "realized_starts": 360, "scheduled_episodes": 360, "scheduled_people": 256}`.

## Policy and retained detail

| Case | Retained input | Exact subtype / input | Mean semantic loss | Mean cell side (m) | Mean interval (ms) | Mean observation delay (ms) | p95 delay (ms) | Core (ms) | Policy violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original_fixed_5m_4000ms | 44.31% | 0.06% | 0.62 | 5.00 | 4000.00 | 2048.43 | 3800.00 | 522.85 | 0 |
| original_fixed_10m_4000ms | 58.73% | 0.54% | 0.66 | 10.00 | 4000.00 | 2049.84 | 3800.00 | 451.67 | 0 |
| support60_fixed_5m_4000ms | 63.50% | 0.96% | 0.59 | 5.00 | 4000.00 | 2041.92 | 3800.00 | 550.26 | 0 |
| support60_fixed_10m_4000ms | 70.54% | 7.82% | 0.55 | 10.00 | 4000.00 | 2049.33 | 3800.00 | 462.21 | 0 |

Zero violations with no releases is vacuous compliance; read it together with retention. Semantic, side and interval means condition on retained observations. Exact subtype / input and retention use the full input denominator.

## Operational observed-track support

Cell statistics use distinct observed tracks per published cell-window. Category statistics use distinct tracks per published semantic bin. Both p50 values are unweighted nearest-rank medians; means are weighted by cell or category observation contributions respectively. Empty output is n/a. These are operational support statistics, not measured attack risk, privacy gain or a trajectory k-anonymity guarantee.

| Case | Cell min | Cell p50 | Cell observation-weighted mean | Category min | Category p50 | Category observation-weighted mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| original_fixed_5m_4000ms | 5 | 6 | 8.80 | 5 | 6 | 8.80 |
| original_fixed_10m_4000ms | 5 | 9 | 14.71 | 5 | 9 | 14.44 |
| support60_fixed_5m_4000ms | 3 | 5 | 7.23 | 3 | 4 | 7.13 |
| support60_fixed_10m_4000ms | 3 | 6 | 12.91 | 3 | 5 | 10.49 |

Core timing excludes input validation and file I/O. The complete comparison pipeline also includes independent Python audits and query evaluation. Neither timing is a per-step live deadline guarantee.

## Recipient queries

Total and immediate taxonomy families; fine-label preservation is reported separately.

The table separates positive-reference queries from known-zero queries, and interior windows from source-boundary windows. Estimates use public uniform spatial/time allocation and keep their own error; missing output never becomes zero.

| Case | Lag (ms) | Cohort | Positive reference queries | Exact coverage | Estimated coverage | Estimated occupancy MAE |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| original_fixed_5m_4000ms | 0 | interior | 11826 | 0.00% | 0.18% | 0.9714 |
| original_fixed_5m_4000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_5m_4000ms | 1000 | interior | 11826 | 0.00% | 0.36% | 0.6976 |
| original_fixed_5m_4000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_4000ms | 0 | interior | 11826 | 0.00% | 5.63% | 0.9644 |
| original_fixed_10m_4000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| original_fixed_10m_4000ms | 1000 | interior | 11826 | 0.00% | 11.25% | 0.7324 |
| original_fixed_10m_4000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_5m_4000ms | 0 | interior | 11826 | 0.00% | 0.83% | 1.1658 |
| support60_fixed_5m_4000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_5m_4000ms | 1000 | interior | 11826 | 0.00% | 1.66% | 0.8849 |
| support60_fixed_5m_4000ms | 1000 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_10m_4000ms | 0 | interior | 11826 | 0.00% | 10.12% | 0.7789 |
| support60_fixed_10m_4000ms | 0 | boundary | 0 | n/a | n/a | n/a |
| support60_fixed_10m_4000ms | 1000 | interior | 11826 | 0.00% | 20.14% | 0.6020 |
| support60_fixed_10m_4000ms | 1000 | boundary | 0 | n/a | n/a | n/a |

## Source type and local region costs

Each row keeps the full input denominator for that type or source-point region. Region memberships can overlap and do not sum to a global partition. Effective policy audit instead intersects the entire released footprint with every selected region.

| Case | Group kind | Group | Input contributions | Retained contributions | Retained fraction |
| --- | --- | --- | ---: | ---: | ---: |
| original_fixed_5m_4000ms | by_source_type | Adult Cyclist | 6177 | 3895 | 63.06% |
| original_fixed_5m_4000ms | by_source_type | Adult E-Scooter Driver | 6056 | 4021 | 66.40% |
| original_fixed_5m_4000ms | by_source_type | Adult Pedestrian | 38168 | 16105 | 42.20% |
| original_fixed_5m_4000ms | by_source_type | Child Pedestrian | 35088 | 13588 | 38.73% |
| original_fixed_5m_4000ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 16557 | 47.84% |
| original_fixed_5m_4000ms | by_source_type | Pedestrian With Stroller | 35929 | 16533 | 46.02% |
| original_fixed_5m_4000ms | by_source_type | Senior Cyclist | 6048 | 3605 | 59.61% |
| original_fixed_5m_4000ms | by_source_type | Senior Pedestrian | 25673 | 8893 | 34.64% |
| original_fixed_5m_4000ms | by_source_point_region | central-through-footway | 36674 | 29848 | 81.39% |
| original_fixed_5m_4000ms | by_source_point_region | east-footway-control | 9442 | 0 | 0.00% |
| original_fixed_5m_4000ms | by_source_point_region | entrance-vicinity | 4084 | 0 | 0.00% |
| original_fixed_5m_4000ms | by_source_point_region | outside_policy_regions | 126885 | 53349 | 42.05% |
| original_fixed_5m_4000ms | by_source_point_region | west-footway-control | 10660 | 0 | 0.00% |
| original_fixed_10m_4000ms | by_source_type | Adult Cyclist | 6177 | 4931 | 79.83% |
| original_fixed_10m_4000ms | by_source_type | Adult E-Scooter Driver | 6056 | 5001 | 82.58% |
| original_fixed_10m_4000ms | by_source_type | Adult Pedestrian | 38168 | 21806 | 57.13% |
| original_fixed_10m_4000ms | by_source_type | Child Pedestrian | 35088 | 18360 | 52.33% |
| original_fixed_10m_4000ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 20859 | 60.28% |
| original_fixed_10m_4000ms | by_source_type | Pedestrian With Stroller | 35929 | 21823 | 60.74% |
| original_fixed_10m_4000ms | by_source_type | Senior Cyclist | 6048 | 4952 | 81.88% |
| original_fixed_10m_4000ms | by_source_type | Senior Pedestrian | 25673 | 12532 | 48.81% |
| original_fixed_10m_4000ms | by_source_point_region | central-through-footway | 36674 | 32625 | 88.96% |
| original_fixed_10m_4000ms | by_source_point_region | east-footway-control | 9442 | 0 | 0.00% |
| original_fixed_10m_4000ms | by_source_point_region | entrance-vicinity | 4084 | 2410 | 59.01% |
| original_fixed_10m_4000ms | by_source_point_region | outside_policy_regions | 126885 | 75229 | 59.29% |
| original_fixed_10m_4000ms | by_source_point_region | west-footway-control | 10660 | 0 | 0.00% |
| support60_fixed_5m_4000ms | by_source_type | Adult Cyclist | 6177 | 5211 | 84.36% |
| support60_fixed_5m_4000ms | by_source_type | Adult E-Scooter Driver | 6056 | 5282 | 87.22% |
| support60_fixed_5m_4000ms | by_source_type | Adult Pedestrian | 38168 | 22926 | 60.07% |
| support60_fixed_5m_4000ms | by_source_type | Child Pedestrian | 35088 | 21130 | 60.22% |
| support60_fixed_5m_4000ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 22550 | 65.16% |
| support60_fixed_5m_4000ms | by_source_type | Pedestrian With Stroller | 35929 | 23234 | 64.67% |
| support60_fixed_5m_4000ms | by_source_type | Senior Cyclist | 6048 | 4999 | 82.66% |
| support60_fixed_5m_4000ms | by_source_type | Senior Pedestrian | 25673 | 13883 | 54.08% |
| support60_fixed_5m_4000ms | by_source_point_region | central-through-footway | 36674 | 33907 | 92.46% |
| support60_fixed_5m_4000ms | by_source_point_region | east-footway-control | 9442 | 0 | 0.00% |
| support60_fixed_5m_4000ms | by_source_point_region | entrance-vicinity | 4084 | 1573 | 38.52% |
| support60_fixed_5m_4000ms | by_source_point_region | outside_policy_regions | 126885 | 83735 | 65.99% |
| support60_fixed_5m_4000ms | by_source_point_region | west-footway-control | 10660 | 0 | 0.00% |
| support60_fixed_10m_4000ms | by_source_type | Adult Cyclist | 6177 | 5218 | 84.47% |
| support60_fixed_10m_4000ms | by_source_type | Adult E-Scooter Driver | 6056 | 5233 | 86.41% |
| support60_fixed_10m_4000ms | by_source_type | Adult Pedestrian | 38168 | 26442 | 69.28% |
| support60_fixed_10m_4000ms | by_source_type | Child Pedestrian | 35088 | 23711 | 67.58% |
| support60_fixed_10m_4000ms | by_source_type | Pedestrian With Mobility Aid | 34606 | 23815 | 68.82% |
| support60_fixed_10m_4000ms | by_source_type | Pedestrian With Stroller | 35929 | 26565 | 73.94% |
| support60_fixed_10m_4000ms | by_source_type | Senior Cyclist | 6048 | 5199 | 85.96% |
| support60_fixed_10m_4000ms | by_source_type | Senior Pedestrian | 25673 | 16253 | 63.31% |
| support60_fixed_10m_4000ms | by_source_point_region | central-through-footway | 36674 | 33595 | 91.60% |
| support60_fixed_10m_4000ms | by_source_point_region | east-footway-control | 9442 | 0 | 0.00% |
| support60_fixed_10m_4000ms | by_source_point_region | entrance-vicinity | 4084 | 3914 | 95.84% |
| support60_fixed_10m_4000ms | by_source_point_region | outside_policy_regions | 126885 | 94927 | 74.81% |
| support60_fixed_10m_4000ms | by_source_point_region | west-footway-control | 10660 | 0 | 0.00% |

## Interpretation limits

Post-hoc fixed maximum-window sensitivity: 5/10 m crossed with 4000 ms, selected after the original ten-case results; the original study remains unchanged. Compare controller choices within one policy. Relaxing support changes the protection contract, so improved utility across policies does not establish a privacy gain.

One deterministic source; no population-level statistical generalization or privacy-improvement claim.

Distinct observed-track support is an operational release condition. It is not automatically classical trajectory k-anonymity, and this comparison contains no membership, linkage or re-identification attack.
