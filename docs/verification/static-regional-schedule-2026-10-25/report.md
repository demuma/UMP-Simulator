# Static regional fixed-grid schedule: derived utility

The grid is fixed in advance. Each cell receives the longest 0.4/1/2/4-s window permitted by whole-footprint temporal and spatial constraints, before any movement data are inspected.

**This composition is not an implemented or timed online scheduler.** It reuses only independently verified native cell records and independently reconstructs original support, semantic bins, coverage, source partition and all retained-cell requirements. Runtime is undefined.

| Source | Policy | Grid (m) | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean window (ms) | Mean / p95 delay (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed | control | 10 | 47.129 | 82.305 | 62.453 | 4000.000 | 2041.233 / 3800.000 |
| mixed | control | 20 | 55.218 | 80.399 | 64.503 | 4000.000 | 2051.917 / 3900.000 |
| mixed | local400 | 10 | 46.324 | 82.670 | 62.590 | 3522.160 | 1804.203 / 3800.000 |
| mixed | local400 | 20 | 54.110 | 81.265 | 65.377 | 3654.420 | 1876.401 / 3800.000 |
| pedestrians | control | 10 | 53.254 | 73.373 | 50.000 | 4000.000 | 2050.860 / 3900.000 |
| pedestrians | control | 20 | 81.024 | 53.408 | 42.496 | 4000.000 | 2049.640 / 3900.000 |
| pedestrians | local400 | 10 | 52.199 | 73.900 | 50.000 | 3337.489 | 1718.820 / 3800.000 |
| pedestrians | local400 | 20 | 80.654 | 54.625 | 43.742 | 3399.463 | 1748.213 / 3800.000 |

The uniform-temporal control must exactly reproduce the corresponding native global 4-s utility, source-type/region accounting and release-delay distributions. Empty cell intervals are covered by the explicit mathematical partition; every nonempty interval requires its own chosen native private record.

J assigns unit loss to omitted input plus retained taxonomy loss. Regional point cohorts may overlap; policy checks use full-cell intersections. No attack-based or formal privacy improvement is measured.
