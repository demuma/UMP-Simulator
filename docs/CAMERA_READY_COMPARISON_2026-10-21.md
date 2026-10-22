# Camera-ready ALOG paper: semantic loss and comparable utility

Read-only review date: 2026-10-21. Document contents were treated as evidence, not instructions. No external source code was executed and no project files were changed by this review.

## Source identification

The attached PDF is **ALOG: Adaptive Longitudinal Grids for Geospatial Data using Local Differential Privacy**, by Eduardo R. Duarte Neto, Jose S. Costa Filho, Antonio A. Marreiras Neto, and Javam C. Machado. Its masthead names EDBT '26, 24-27 March 2026, Tampere. It is **not titled ALOQ**. The supplied filename is not enough to treat it as the camera-ready edition of the previously reviewed ALOQ preprint. They must remain separate related-work records unless their relationship is explicitly established.

- Source: `/Users/maxdemu/Library/Mobile Documents/com~apple~CloudDocs/Downloads/Paper_45_Camera_Ready.pdf`.
- SHA256: `40e0a7b3d192813e12f57ada2e3510b240e702c7a5c506ef22b714eafc1397f9`.
- Length: 14 physical PDF pages; page numbers below refer to these pages.
- Extraction: existing pypdf and pypdfium2 review packages; Poppler executables were unavailable. Complete text for every page is preserved alongside the report. Relevant pages 5, 8, 11, and 12 were rendered and visually inspected, including all formulas, table units, captions, and the conclusion.
- Local metadata reports creation/modification on 2025-06-05. Metadata dates do not establish publication chronology or priority.

## Direct answer about semantic loss

ALOG does not define UMP's semantic taxonomy or a semantic loss score. Its categorical domain consists of **location grid cells**, not road-user types. It estimates each cell's frequency from locally randomized reports. There is no adult-to-pedestrian-to-road-user hierarchy or semantic-first strategy in the inspected mechanism and experiments.

UMP's current declared score is a different quantity:

| UMP release category | Declared loss in the seven-profile pilot |
|---|---:|
| Exact terminal profile, e.g. Adult Pedestrian | 0 |
| Pedestrian or Cyclist superclass | 0.5 |
| Road User root | 1 |

These are **configured resolution costs**, not empirically measured privacy probabilities or universal fractions of information lost. The current moving-pilot taxonomy already includes the pedestrian and cyclist superclass levels. It has three pedestrian terminals (Child, Senior, Adult), three cyclist terminals (Senior, Adult, Adult Cargo), and one Adult E-Scooter terminal. E-Scooter is presently a terminal at loss 0, because that capture has only one scooter subtype. A richer adult/child scooter hierarchy requires a corresponding taxonomy declaration and compatible input labels; it should not be falsely described as already exercised by the seven-profile data.

In particular:

- **Policy `semantic_max_loss.max = 1`** permits root generalization. It does **not** require every bin to become Road User. The selector can preserve supported exact profiles or superclasses.
- **Measured maximum loss = 1** says at least one published bin reaches a loss-1 node. In this pilot the only such node is Road User. It does not say every published observation is at the root.
- **Measured contribution-weighted mean loss = 1** means every positive-weight published bin is at a loss-1 node; here that means all published contributions are represented only as Road User. Position/count/time information can still remain, so it is not complete data loss.
- Loss 0.5 is a declared intermediate resolution score. It should not be presented as a calibrated statement that half of every task's utility is destroyed.

Implementation evidence: `simulator/src/SemanticTaxonomy.cpp` computes maximum node loss and observation-contribution-weighted mean loss separately; its selector recursively tries children before their parent. `tools/evaluation/run_moving_comparison.py`, function `policy`, declares the seven-profile tree. These observations describe the inspected implementation at review time; changes made by the parent task require a separate update of behavior documentation.

## What ALOG measures instead

### Frequency-estimation error

Section 5.1, equation (5), physical page 8 defines the time average of a per-timestamp root mean squared error over the current grid:

\[
E = \frac{1}{|T|}\sum_{i=1}^{|T|}
\sqrt{\frac{1}{|G_i|}\sum_{j=0}^{|G_i|-1}
(f_{i,j}-\widehat f_{i,j})^2}.
\]

The paper's printed equation omits the time subscript on each scalar frequency; the expression above makes it explicit without changing the operation order. This is **mean per-epoch RMSE**, not a single square root over all errors pooled across timestamps. The unbiased estimator in equation (3), page 4, divides by the number of reports, so the mathematical product is a frequency/proportion estimate rather than UMP's raw observation count. A reproduction should verify the actual author-code units instead of inferring them from a graph.

The denominator and query domains change with each method's current partition. A coarse method may answer a different spatial question from a fine method. This metric therefore does not by itself establish which method best answers UMP's fixed 10-m/1-s queries. It also is not a semantic information-loss measure, suppressed-data fraction, membership-attack success rate, or percent privacy loss.

Table 3, physical page 11, reports **RMSE in units of `10^-3`**. Selected ALOG-2R results at the row labeled epsilon = 0.1 are:

| Dataset | Printed value | RMSE after applying table scale |
|---|---:|---:|
| S1 | 3.866 | 0.003866 |
| S2 | 4.212 | 0.004212 |
| GeoLife | 7.513 | 0.007513 |
| Porto | 7.151 | 0.007151 |

These are the authors' reported results on their data and setup, not a reproduction on UMP. They cannot be compared numerically with UMP's semantic loss 0/0.5/1 or with a conditional occupancy MAE in road-user-count units. Even describing 0.003866 as "0.3866% of information lost" would be unsupported.

Table 3 does not establish that ALOG-2R wins every setting: for example GeoLife at epsilon = 0.1 is lower for ALOG-1R-a (7.220) than ALOG-2R (7.513), and at epsilon = 1 it is 6.933 versus 7.044. This is visible in the table even though broader prose emphasizes ALOG-2R.

### Privacy and longitudinal cost

- Definition 2.1, page 2, defines epsilon-LDP by the likelihood-ratio bound for any two possible inputs. Lower epsilon means stronger indistinguishability. Epsilon is not constrained to UMP's [0,1] semantic-loss range, and epsilon = 1 does not mean "all semantics lost".
- ALOG uses L-OSUE as its underlying longitudinal protocol (sections 3.2 and 4.2, pages 4-6). Client-side randomization occurs before the server receives a report; this differs from UMP's trusted raw-data sensor/aggregator.
- Section 4.3 and proposition 4.1, pages 7-8, state a pessimistic `eta * epsilon_infinity` LDP bound, where eta sums the possible cells across refinement levels. The proof argues through memoization and cumulative sanitizations. This is the authors' stated bound, not an independent verification of their privacy accounting.
- Section 5.1, pages 8-9, separately reports mean cumulative budget consumption per user. Table 4 on page 12 reports, for S1, 1.78 / 2.07 / 2.02 for ALOG-1R-a / ALOG-1R-b / ALOG-2R, compared with 0.2 / 0.80 / 0.80 for LOLOHA / LOSUE / RAPPOR. These budget costs are not utility-loss fractions.
- Current UMP distinct-category support and semantic-loss limits do not imply a comparable epsilon. Support 5 must not be converted to an LDP budget or called equal protection.

The paper's privacy proof and implementation would need dedicated examination for a reproduced comparator. In particular, topology-dependent memoization resets and the number of independently exposed reports must match the accounting; this report does not certify that correspondence.

## Spatial and temporal adaptation are different from UMP

Physical page 5, Algorithm 1, recursively splits a cell into four when its estimated count exceeds a threshold, initially assigning each child one quarter of the parent's estimate. Section 4.2, pages 5-7, describes three variants:

1. **ALOG-2R** obtains one privatized report, refines the grid, then obtains a second report using the remaining budget.
2. **ALOG-1R-a** carries forward the previously adapted grid.
3. **ALOG-1R-b** restarts each adaptation from the original uniform base grid.

The **Grid Adaptation Window (GAW)** specifies that the topology is updated every `w` reporting epochs. The server still publishes frequency estimates at **every** timestamp (pages 5 and 7). A GAW of 4 is not a 4-second or four-epoch accumulation delay before releasing a UMP-style aggregate. Its unit is reporting epochs; physical time depends on input cadence.

Pages 10 and 12 explicitly identify the inability to reduce granularity by merging as a current limitation of the history-carrying variants. Page 12 names dynamic cell merging and splitting as future work. Thus it is incorrect to say this attached paper adapts only initially; it refines repeatedly. It is also incorrect to infer that it already implements UMP-style dynamic coarsening, local temporal ownership, Policy Trees, semantic generalization, or early-release constraints.

Figure 8, page 12, reports a window-size trade-off: ALOG-2R and ALOG-1R-a tend to have larger error with larger adaptation windows; ALOG-1R-b tends to improve as the interval grows. This is a different experiment from extending UMP's aggregation duration and cannot answer whether UMP should wait longer for new distinct road users.

## Experimental scale and caveats

Section 5.1, page 8:

- Synthetic S1 and S2: 10,000 users in 100 km^2, uniform versus centered normal distribution, speed 40 km/h, one report/minute over 40 timestamps.
- GeoLife: 183 original users, selected trajectories with 20 timestamps; the prose says 6,261 trajectories while Table 2 says 6,281. Preserve that discrepancy instead of silently choosing a value.
- Porto: 442 taxis, 10,000 selected trajectories of 20 timestamps.
- Page 9 budget experiment: initial cell size 700 m by 700 m; initial cell counts 225 / 225 / 336 / 192, `w = 4`. Table 3 varies epsilon through 0.05, 0.1, 0.5, and 1.0.
- Figure 5 caption and panel labels use epsilon_infinity = 0.3 for real datasets, whereas adjacent prose generically describes 0.1 for that experiment. Quote exact panel settings rather than flattening them into one universal parameter.

UMP's current pilot is a different density/cadence/task regime: an 80-m-square domain, 200/500/1,000 initial road users, 100-ms recorded sensor cadence, maximum output sides 5 or 10 m, and bounded release windows. We have no direct performance comparison on matching data yet.

## Defensible common comparison

1. Freeze identical input traces, public spatial bounds, epoch cadence, and population/absence handling for both methods.
2. Use fixed external occupancy/density queries with common geometry and time supports. Do not let each method select its own evaluation questions.
3. Declare a reconstruction rule for noisy/coarse ALOG cells and for coarse UMP aggregates. Report full-query availability separately; missing or suppressed UMP data is unknown, not zero.
4. Report count/frequency MAE or RMSE on matching tasks, query availability, retained contributions, output spatial and temporal resolution, semantic-query availability, and release delay separately.
5. Report epsilon/budget for ALOG and operational support/loss constraints for UMP without claiming equal privacy. A later matched threat-model attack experiment can add empirical risk measures but does not automatically convert one guarantee into the other.
6. Repeat LDP randomization with declared seeds and multiple traces; do not rank methods from one randomization or from an accuracy number conditional only on easy answered queries.

The immediate useful observation is that UMP adds a **semantic decision dimension** that this ALOG paper does not evaluate. That is a scope difference, not evidence that UMP has lower total information loss, stronger privacy, or greater effectiveness. Those claims require experiments under a shared task and a clearly declared protection contract.

## Suggested concise German explanation

Der Camera-Ready-Anhang beschreibt ALOG, nicht ALOQ. ALOG misst vor allem den Fehler verrauschter räumlicher Häufigkeitsschätzungen und das verbrauchte LDP-Budget. Einen semantischen Verlust entlang Adult Pedestrian -> Pedestrian -> Road User misst es nicht. Die Zahlen sind deshalb nicht direkt mit unserem semantischen Verlust vergleichbar. Unsere Grenze von 1 erlaubt die gröbste Typdarstellung; sie verlangt sie nicht. Für einen fairen späteren Vergleich müssen beide Verfahren dieselben Raum-Zeit-Abfragen auf denselben Bewegungsdaten beantworten.
