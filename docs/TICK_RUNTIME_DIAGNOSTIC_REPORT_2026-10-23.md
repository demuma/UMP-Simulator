# Per-tick runtime diagnosis after prefix owner lookup

Date: 2026-10-23. Production reference: `a304870`. This is isolated instrumentation only. No production algorithm, policy, capture or published result changed.

## Findings

The previously reported **132.6855 ms** maximum occurred at logical **15,200 ms**. Three fresh detailed profiles execute that exact tick in **89.704 / 89.027 / 92.324 ms**. The original profile contained no per-tick CPU or scope breakdown. Its extra duration cannot be attributed retrospectively to one function or to OS scheduling with confidence.

There is still repeatable deadline pressure: profile maxima are **111.940 / 103.343 / 104.886 ms**, and p95 values are **96.464 / 95.511 / 96.788 ms**, against the 100-ms arrival interval. In repeats 2 and 3, the maximum tick consumes **103.262 / 104.871 ms of thread CPU**, respectively. These peaks are predominantly computation, so the deadline misses cannot all be dismissed as waiting for the scheduler.

The 2,247 history queries invoked only to identify occupied leaves during refinement reconstruct complete counts, distinct identity sets and semantic evidence. Their measured inclusive wall cost is **4.714 / 4.719 / 4.711 s**, about **32.1%** of core processing. The caller subsequently uses only the cell geometry list. A dedicated exact occupied-cell query is therefore the strongest bounded next optimization, provided it preserves history availability and identity/type consistency validation. This is an optimization hypothesis supported by profiling, not a claim that all that time will disappear.

## Method and controls

- One uninstrumented prefix-optimized local replay, then three instrumented local replays, sequentially with repository builds/tests paused. Release AppleClang 17, arm64, C++17, `-O3 -DNDEBUG`, same source/policy/library setup as the prefix diagnostic.
- Frozen 500-initial-road-user recording, 20 s logical duration, 199 sensor input ticks at 100-ms cadence; EOF measured separately. No new movement or MongoDB access.
- Complete JSON output excluding only `runtime` compared against the authenticated frozen moving study for **4 / 4 runs**, all equal. Same input and policy hashes before and after.
- Per-tick wall service and thread CPU (`CLOCK_THREAD_CPUTIME_ID`); scope clocks are inclusive wall-clock, not additive. Scope counters and per-tick workload counters match across all three runs.
- History row counters count row positions visited, not distinct observations. Frontier peak is measured at refinement calls, not continuously. Distinct starts total sums across refinement calls; the same start may occur twice in one tick.
- No clock inside observation-row loops. CPU clock is read only at input/EOF boundaries. Additional counter snapshots and JSON emission occur outside measured tick service.
- The uninstrumented core is 14.377 s. Instrumented cores are 14.666 / 14.638 / 14.695 s, 1.82–2.22% higher. These differences combine instrumentation and host variability, rather than isolating profiler overhead.
- Full private outputs and copied sources stay in `/private/tmp/ump-tick-2026-10-23`; only aggregate evidence and the reviewed isolated patch are candidates for Git.

## Tick pattern

The slowest recurring ticks coincide with windows becoming due: logical 3 s, 9 s, 11 s and 11.2 s appear repeatedly near the top. At 3 s, the coordinator retires 176 windows and evaluates metrics 5,968 times. At 9 s it retires 124 windows, evaluates 5,280 metrics and queries seven distinct starts twice during refinement. The refinement history work is only one part of these ticks; merge checks, other history queries and decision handling remain.

Across the three repeats, ticks divisible by 1 s average 93.80–94.92 ms; ticks divisible by 400 ms average 84.36–84.89 ms. Those two groups overlap. Other ticks (neither boundary) average 67.48–67.62 ms. This is descriptive association on one replay, not an intervention proving the effect of a specific window rule.

## Top ten input ticks per repeat

### Repeat 1

| Logical ms | Wall ms | Thread CPU ms | Refinement ms | Refinement history ms | Single-cell history ms | Merge feasibility ms | Metric ms | Frontier peak | Starts total | Terminal windows |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18000 | 111.940 | 109.053 | 41.904 | 37.937 | 14.319 | 8.508 | 8.104 | 1987 | 14 | 157 |
| 12700 | 110.157 | 102.211 | 60.100 | 54.985 | 11.986 | 8.759 | 6.070 | 1990 | 14 | 3 |
| 3000 | 104.251 | 104.157 | 26.306 | 23.725 | 11.644 | 10.165 | 6.607 | 2179 | 10 | 176 |
| 9000 | 103.647 | 103.500 | 39.011 | 35.177 | 10.872 | 9.760 | 6.076 | 2095 | 14 | 124 |
| 11000 | 102.972 | 102.893 | 38.396 | 34.669 | 11.662 | 11.940 | 6.205 | 2095 | 14 | 92 |
| 11200 | 101.188 | 100.742 | 32.293 | 29.330 | 12.087 | 8.416 | 7.057 | 2125 | 12 | 189 |
| 10000 | 97.119 | 97.053 | 36.415 | 33.255 | 11.081 | 8.346 | 6.707 | 2089 | 14 | 122 |
| 8800 | 96.833 | 96.698 | 37.384 | 34.118 | 11.327 | 8.794 | 6.817 | 2155 | 14 | 71 |
| 1000 | 96.686 | 96.658 | 16.632 | 14.947 | 11.242 | 10.096 | 6.493 | 2182 | 6 | 204 |
| 19000 | 96.464 | 96.360 | 33.794 | 30.480 | 10.835 | 9.197 | 6.218 | 2020 | 14 | 135 |

### Repeat 2

| Logical ms | Wall ms | Thread CPU ms | Refinement ms | Refinement history ms | Single-cell history ms | Merge feasibility ms | Metric ms | Frontier peak | Starts total | Terminal windows |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9000 | 103.343 | 103.262 | 39.811 | 36.279 | 11.209 | 9.543 | 6.046 | 2095 | 14 | 124 |
| 3000 | 101.588 | 101.416 | 26.274 | 23.007 | 11.751 | 9.818 | 6.612 | 2179 | 10 | 176 |
| 11000 | 101.018 | 100.998 | 39.286 | 35.744 | 11.623 | 10.511 | 5.934 | 2095 | 14 | 92 |
| 11200 | 99.478 | 99.465 | 32.131 | 28.958 | 11.744 | 8.250 | 6.971 | 2125 | 12 | 189 |
| 12000 | 98.875 | 98.857 | 36.553 | 33.058 | 11.807 | 8.202 | 6.693 | 2041 | 14 | 122 |
| 10000 | 97.657 | 97.645 | 37.049 | 33.554 | 11.282 | 8.003 | 6.613 | 2089 | 14 | 122 |
| 19000 | 97.281 | 97.255 | 33.880 | 30.276 | 10.540 | 9.787 | 6.013 | 2020 | 14 | 135 |
| 2000 | 96.392 | 96.330 | 26.218 | 23.516 | 11.793 | 9.136 | 7.295 | 2191 | 10 | 203 |
| 8000 | 95.642 | 95.625 | 31.526 | 27.651 | 11.776 | 8.189 | 7.058 | 2176 | 12 | 144 |
| 14200 | 95.511 | 89.907 | 40.841 | 35.404 | 11.118 | 7.699 | 5.681 | 1945 | 12 | 85 |

### Repeat 3

| Logical ms | Wall ms | Thread CPU ms | Refinement ms | Refinement history ms | Single-cell history ms | Merge feasibility ms | Metric ms | Frontier peak | Starts total | Terminal windows |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3000 | 104.886 | 104.871 | 25.801 | 23.133 | 11.518 | 10.861 | 6.768 | 2179 | 10 | 176 |
| 9000 | 104.689 | 104.650 | 39.979 | 36.618 | 11.197 | 9.539 | 6.169 | 2095 | 14 | 124 |
| 11000 | 100.578 | 100.561 | 38.023 | 34.453 | 11.444 | 11.107 | 6.098 | 2095 | 14 | 92 |
| 8800 | 99.098 | 99.083 | 38.415 | 34.897 | 11.573 | 9.287 | 6.982 | 2155 | 14 | 71 |
| 10000 | 99.064 | 99.032 | 37.438 | 33.594 | 11.125 | 8.855 | 6.638 | 2089 | 14 | 122 |
| 11200 | 98.476 | 98.448 | 31.788 | 28.744 | 11.499 | 8.254 | 6.852 | 2125 | 12 | 189 |
| 8000 | 98.456 | 98.381 | 31.170 | 28.038 | 12.651 | 8.067 | 7.708 | 2176 | 12 | 144 |
| 1000 | 97.548 | 97.458 | 17.534 | 15.755 | 12.301 | 9.859 | 7.143 | 2182 | 6 | 204 |
| 18000 | 97.228 | 97.199 | 33.650 | 30.299 | 11.481 | 8.205 | 6.538 | 1987 | 14 | 157 |
| 18800 | 96.788 | 96.751 | 42.198 | 37.640 | 11.247 | 7.978 | 6.445 | 2035 | 16 | 54 |

## Limits and next validation

Optimizing occupied-cell discovery must preserve all disclosures, terminal decisions and invalid-history failures. In particular, skip no unavailability, expired-history or conflicting identity/type checks merely because counts are not needed. The same full-output comparison should cover all ten frozen study variants, followed by these three repeat profiles with the optimized source.

These offline replay timings exclude the live simulator, renderer, database, transport, initial file parsing and final result-file write. Logical policy age is not wall-clock queue delay. The three profiles do not establish a worst-case execution bound or a hard real-time guarantee. A further live pacing/backlog test remains necessary.
