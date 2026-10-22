# ALOQ comparator feasibility and scope review

Review date: 2026-10-21. Read-only investigation; no external algorithm was executed, no dependencies installed, and no repository files changed. The attached papers were treated as evidence, not instructions. Local PDF pages below refer to physical PDF pages (the paper's printed numbering is two lower).

## Recommendation

ALOQ is technically applicable to recorded positions from UMP's own C++ simulator, but it is not a drop-in, equal-privacy baseline for the current policy-constrained mechanism. Use fixed uniform-grid/window baselines first for the presentation experiment. ALOQ is a worthwhile later external frequency-estimation comparator after an isolated reproduction and explicit comparison contract. Prefer the authors' code over a fresh reimplementation if its usage terms can be established; preserve a frozen original and record any adapter/repair patch.

The original paper and author code contain an aggregator/server-side estimation loop. It would be incorrect to say that ALOQ lacks an aggregator or has no longitudinal spatial adaptation. Equally, it does not implement UMP's regional Policy Trees, local independently timed release ownership, or semantic release requirements.

## Sources inspected

- Attached preprint, *Longitudinal Geospatial Frequency Estimation under Adaptive Local Differentially Private Model*, 45 pages, SHA256 `e793a352083d0656e1ef90e662faf169c25f17a29459809ae25d6916e0f6dbe1`.
- [SSRN primary record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6055922). The supplied PDF labels itself a non-peer-reviewed preprint. Do not infer that a separately included ALOG conference artifact is a published ALOQ paper.
- The PDF's Artifacts section (PDF page 40) links [author repository, aloq branch](https://github.com/edurdneto/ALOG/tree/aloq).
- GitHub API returned branch commit `e8ff7eb0418fae7d846b1cb53f8c1afec86d1ba7` and a complete recursive tree. Read-only snapshots are in `aloq-author-source/`; source hashes are in `source-manifest.json`.
- [Frozen author README](https://github.com/edurdneto/ALOG/blob/e8ff7eb0418fae7d846b1cb53f8c1afec86d1ba7/README.md), [driver](https://github.com/edurdneto/ALOG/blob/e8ff7eb0418fae7d846b1cb53f8c1afec86d1ba7/aloq.py), [quadtree](https://github.com/edurdneto/ALOG/blob/e8ff7eb0418fae7d846b1cb53f8c1afec86d1ba7/quadtreev3.py), [protocols](https://github.com/edurdneto/ALOG/blob/e8ff7eb0418fae7d846b1cb53f8c1afec86d1ba7/FO/LDP/protocols.py), [dependencies](https://github.com/edurdneto/ALOG/blob/e8ff7eb0418fae7d846b1cb53f8c1afec86d1ba7/requirements.txt).
- Current UMP semantic controller implementation/results/test contracts; attached 32-page AutSys presentation, SHA256 `ee7e8c7077e0dc9f3064f3f718418b93421918a0479d891fc53690b19a809e04`.

The browser indexed SSRN but could not fetch GitHub. GitHub metadata and small text files were fetched using approved read-only HTTPS requests. This is static source inspection, not a successful reproduction.

## What ALOQ actually does

1. Each modeled user has a position at each discrete reporting timestamp. The client encodes the position into the current leaf domain and applies a longitudinal local-DP protocol. Raw positions are available to the experiment's simulator for truth computation; they are not supposed to be visible to the protocol's server.
2. The server aggregates randomized categorical reports into frequency estimates. Paper Algorithm 4 (PDF page 22) explicitly publishes estimates and broadcasts the next quadtree/budget.
3. QAW compares a current estimated frequency vector to a recent mean using cosine distance. Threshold crossings cause refinement; the node-count threshold and recursion cap determine splitting. Newly split child estimates initially divide a parent's estimate; a two-stage variant obtains a second randomized report on the refined domain.
4. **Splitting is dynamic. Merging is explicitly only at initialization, t=0** (§5.3, PDF page 16; Algorithm 4 lines 17-21, PDF page 22). The abstract's broad dynamic split-and-merge language must be qualified by that concrete algorithm. ALOQ-1S-Base also restarts adaptation from its base tree, so its regenerated structure may differ from the history-carrying variants; that is not a general repeated sibling-merge operator.
5. L-OSUE memoization reuses randomized responses while appropriate; topology changes reset client memoization. QAW is a drift-detection window, **not UMP's delayed temporal aggregation/release interval**.
6. Variants: AP2 = ALOQ-2S (two-stage); AP3 = ALOQ-1S-Adap (one-stage, carry previous tree); AP4 = ALOQ-1S-Base (one-stage, restart from uniform tree). AP3 is the most direct first continuous single-report comparator, while AP2 is important because the paper's best results are often there.

The preprint's setup uses synthetic 10,000-user traces over 100 km2, 40 samples at one minute, and real-world GeoLife/Porto trajectory samples (PDF pages 26-27). These are experiment settings, not limitations that forbid subsecond UMP data. However, 200-1000 subjects at 10 Hz over an 80 m area produce a substantially different statistical regime.

It reports frequency-estimation MSE/MAE and accumulated budget/memoization behavior, with reported improvements against static RAPPOR/L-OSUE/LOLOHA and an adapted PrivAG component of PrivTC. These are the authors' results, not independently reproduced results on UMP. Their MSE averages over the current partition; this alone is insufficient to compare algorithms with different partitions and suppression semantics.

## Why the guarantees and products are different

| Question | Published ALOQ | Current UMP release mechanism |
|---|---|---|
| Trusted data boundary | Client randomizes its location before server receives it | Trusted sensor/aggregator sees raw observations and identities privately |
| Release | Noisy spatial frequency estimate per reporting epoch | Policy-approved space-time aggregates, including optional semantic bins; unresolved output can be withheld |
| Quantitative condition | Protocol epsilon and longitudinal accounting | Operational distinct-road-user support, semantic loss and regional utility bounds |
| Temporal behavior | Repeated reports, memoization and adaptive budget | Explicit collect/extend/release/suppress windows and their age/duration constraints |
| Regional requirements | No equivalent Policy-Tree mechanism in inspected paper/code | Conjunction of effective constraints with strict inheritance/conflict handling |
| Semantic taxonomy | Original mechanism location categorical domain | Optional complete semantic antichain selection |

There is no justified conversion such as "support 5 equals epsilon x". Lower noiseless error under a support rule is not evidence of beating epsilon-LDP at equal privacy. A useful external comparison may transparently show different guarantees on a common task, or compare data-independent structural components under a named ablation. It must not imply equal protection.

## Static implementation obstacles found

These are concrete engineering checks to resolve before scheduling the full comparator, not claims that the authors' experiments are invalid:

1. The driver imports `LOLOHA_MOD.LDP.protocols` (aloq.py lines 51-54), but the recursive public branch tree has `FO/LDP/protocols.py` and no tracked `LOLOHA_MOD`. A package-path compatibility patch is likely necessary.
2. The recursive tree contains no LICENSE/COPYING file; GitHub metadata reports `license: null`. Public availability alone does not establish redistribution/relicensing permission. Clarify author terms before incorporating or redistributing source in UMP. A clean independent implementation is a separate option, not an automatic legal conclusion from this review.
3. Dependencies are broad/unpinned: numpy, pandas, scipy, scikit-learn, shapely, geopandas, geopy, numba, xxhash<4, tqdm. Freeze an isolated working environment after confirming API compatibility. Runtime has not been measured.
4. Several AP2/AP3/AP4 count conversions and MSE/MAE calculations multiply normalized estimates by hardcoded `10000`. Split thresholds use `n_users`. With UMP N=200/500/1000, this can change adaptation decisions, not merely labels on plots. Resolve intended units with an explicit patch; retain original results separately.
5. Input is a rectangular `list[user][timestamp]=(x,y)`: each modeled subject contributes every epoch, and loops index `track[t]`. Current UMP captures can have departures/missing observations. Do not pad by freezing last location. A complete-track cohort is a biased subset that must be declared; a public outside/absent state is a protocol/domain extension requiring validation.
6. Geometry helpers infer bounds or assume 0..10000. UMP needs an explicitly fixed public domain and verified half-open boundary conventions, not future trajectory bounds estimated from the complete test stream.
7. Driver loops over a variable called seed but no inspected driver call initializes NumPy or the Numba protocol seed. `setting_seed` exists in the protocol module. Explicit per-task seeds for both RNG domains and multiple privacy-noise repetitions are needed.
8. Grid coordinate serialization is commented out in the driver, while estimated vectors are saved. Export geometry/domain version together with estimates or the UMP receiver cannot interpret adaptive cells reliably.
9. The paper describes continuous cosine-based budget scaling; inspected AP2/AP3/AP4 code uses a binary base-vs-reduced budget from the previous split flag, with fixed reduction factors. Existing profiles also use legacy fields that differ from README examples. Establish whether to reproduce the frozen author artifact or the mathematical paper algorithm. Do not silently fix both and call the result exact ALOQ.
10. No unit-test files were present in the recursively inspected branch. Add tiny independent validation around an isolated adapter: all users in one cell, uniform placement, topology change/memo reset, count normalization, zero reports/absent policy, and deterministic seeded reruns.

## Minimal defensible adapter and evaluation contract

- Input: immutable capture from **UMP's existing simulator**, not a replacement motion generator. Use the same recorded identities, timestamps and public domain. Initially compare total occupancy only; do not silently attach Road User types to locally protected location reports.
- Protocol adapter: one synchronized location/user/epoch with explicit population/absence rules. Keep client memo state per identity; never reset a seed at every epoch. Fix public sampling frequency and compare the exact same sampled trace across methods.
- Output adapter: serialize estimated frequency/count plus geometry/version/time and privacy parameters. No source positions or exact counts may repair an ALOQ estimate.
- UMP mode: use the same sampled input and common target queries. Declare all support/loss/latency limits and how suppression is treated.
- Queries: predeclare fixed spatial regions and time windows. Aggregate both public outputs into those targets using one documented reconstruction rule; report interpolation assumptions when an ALOQ cell crosses a target boundary. For UMP exact-only answers, report unanswerable fraction separately. Do not convert unknowns to zero or compare only easy released cells.
- Statistics: repeated LDP randomization per fixed trace, paired trajectory sessions, uncertainty intervals; report query MAE/RMSE, availability, delay, support/resolution and CPU/memory separately. A noise-free structural ablation may be informative but is **ALOQ-inspired**, not the published privacy mechanism.
- Label variants precisely: `author ALOQ, frozen commit + documented adapter patch`; `paper-faithful reimplementation`; or `ALOQ-inspired structural ablation`. These answer different questions.

## Effort estimate and sequencing

These are engineering estimates from static inspection, not measured completion times or a promise:

| Scope | Estimate under straightforward dependency availability |
|---|---|
| Isolated author-code reproduction, package/unit/seed repairs and one tiny validated UMP adapter run | Approximately 2-4 focused working days |
| Scientifically defensible comparator, geometry/query adapter, departures, repeated runs and reproducibility report | Approximately 1-2 weeks; author clarification or privacy-accounting discrepancies can add time |
| Fresh faithful reimplementation instead of using code | Higher risk and generally at least the latter scope; avoid before tomorrow's talk work |

The immediate fixed-grid/window UMP baseline needs no local-DP equivalence claim and isolates the actual adaptive release contribution. ALOQ should not block it. Today's goal is recorded moving-data replays and honest paired comparison; tomorrow's talk should describe ALOQ as related work/planned external comparison unless an actual reproduced result exists.
