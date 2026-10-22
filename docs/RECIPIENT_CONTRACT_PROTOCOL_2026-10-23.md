# Recipient query contract and public-support diagnosis

Date: 2026-10-23. This protocol fixes the additive evaluation before executing it.
It is a post-hoc diagnosis of the already known October 22 moving-input comparison,
not a new independent traffic study or a preregistered claim of adaptive superiority.

## Scope and provisional application product

The first product is mean sampled Road User occupancy in a specified region and
time interval; category occupancy is an extension of the same product. Define

    C(Q,g) = sum over t in T_Q of count of observed Road Users in R_Q and category g,
    O(Q,g) = C(Q,g) / |T_Q|.

T_Q contains the declared discrete sensor samples in [a_Q,b_Q), excluding initial
t=0. C counts observation contributions, not distinct people. O is mean sampled
occupancy, not flow, speed, a continuous-time integral or a current live snapshot.

A recipient query also specifies a deadline d_Q=b_Q+lag. Published records carry
immutable spatial support R_j, source interval I_j, sample cadence, a truthful
semantic count partition and seal time s_j. Only records with s_j<=d_Q can inform
an answer at that deadline. Raw source observations supply a separate reference
for offline error measurement; private failed/empty candidates do not supply
recipient predictions.

The existing policy constrains distinct support per published category, semantic
hierarchy loss, spatial size, interval duration and logical age. It does not promise
alignment with every requested query boundary, complete public coverage of a region,
exact fine-category values, an application MAE bound or bounded wall-clock latency.
These missing promises must not be inferred from a successful policy check.

Retain the existing conservative whole-tile exact decoder as the primary reference.
Separately evaluate a uniform allocation estimator as an exploratory application
model. This does not change simulator or controller defaults, hard thresholds,
published records, semantic categories, or the previous reported scores. The user
has been asked whether exact-only or additionally estimated products are preferred;
this analytical comparison does not mandate estimates for a deployed application.

## Frozen inputs and task cohort

Reuse `results/moving-scoped-comparison-2026-10-22` with verified manifest SHA256
`e81b724b673ac5f8e77ddd483b41b4ec2756206fbd32ccf2455e14bd234dc83f`.
Original observations SHA256:
`ab4fadf254bfb5432018ff4bd305cd16d82a7475ae3d934c14c4f9af67dd5cf1`.

All ten variants, their policies, four query banks, ten taxonomy nodes and deadline
lags remain unchanged. The banks cover the entire 80 x 80 m area with 5/10-m query
cells and 400/1,000-ms intervals; lags are 0/200/1,000 ms. Primary comparisons use
the named fixed grid/window matching each query, with common/local comparisons
for each semantic secondary: forty evaluations and twenty-four paired comparisons.
The two semantic secondaries are equivalent on this source, not independent samples.

The interior rule stays `query_end + 1000 < 20000`. EOF-observable and later-censored
queries remain separate. No new source generation, sensor run, MongoDB reset or
policy/scenario tuning is part of this gate. All input and parent artifact hashes
must remain unchanged. Freeze implementation/dependency/protocol digests before
running and reject modified source artifacts. Store only compact new output; raw
recordings and releases stay ignored and are not copied to Git.

## Disjoint support diagnosis

Use finest-cell Morton intervals and discrete sample-index intervals to represent
support without enumerating all finest cells. Let

    V_Q = F(R_Q) x T_Q,
    V_jQ = (F(R_j) intersect F(R_Q)) x (T_j intersect T_Q).

The existing validator rejects overlapping public support, so the intersections
V_jQ are disjoint. Each nonempty intersection receives a joint bitmask:

| Bit | Meaning |
| --- | --- |
| 1 | Published spatial footprint crosses the query boundary |
| 2 | Published source interval crosses the query boundary |
| 4 | Published semantic bins do not resolve the requested category |
| 8 | The record seals after this query's deadline |

The uncovered remainder is `|V_Q| - sum_j |V_jQ|`: support with no corresponding
publication anywhere in the recorded horizon. It is not inferred empty, and this
public-only measure cannot distinguish suppression, genuinely empty private data
or other internal causes. Late records may explain missing deadline support in
this retrospective diagnosis, but never supply a prediction before their seal.

Report volume by all sixteen disjoint masks, the unpublished remainder, and
mutually exclusive query signatures (OR of present blocker bits, plus bit16 when
unpublished support remains). Keep censored and no-scheduled-sample queries separate.
For observed queries, mask0 volume equals the old decoder's eligible support;
exact answer flags must agree. Positive-reference/zero-reference and category
summaries use the same cohort. Summing over category queries measures query support
volume with repeated category questions, not unique physical area or unique people.

These are limitations of the declared decoding certificate. They are not a causal
attribution of algorithmic failure, a simulation of alternative release decisions,
or a proof that no recipient could infer the answer by another method. In particular,
a public Pedestrian-only bin can certify Cyclist=0 even inside a subregion, while
the existing whole-tile decoder rejects a crossing record first. Its conservative
scores remain frozen; do not describe every rejected query as mathematically
impossible to infer.

## Separate uniform spatial/temporal estimator

For a category resolved by a public semantic partition, let C_j,g be its whole
record count (possibly a certified zero). Estimate

    C_hat(Q,g) = sum_j C_j,g * |F(R_j) intersect F(R_Q)| / |F(R_j)|
                            * |T_j intersect T_Q| / |T_j|,
    O_hat(Q,g) = C_hat(Q,g) / |T_Q|.

Use discrete scheduled samples, not source-duration ratios; the first interval has
no t=0 sample. This is uniform allocation within each public cell and constant
mean occupancy within its source interval. A temporal/spatial crossing may now
contribute an estimate. A straddling semantic category still supplies no finer-class
count; no class-proportion prior is introduced.

An estimated answer requires full query support from visible, semantically resolved
public records. Unknown space is not zero-filled and estimates from partial coverage
are not scaled to the whole region. All required records must have sealed by the
query deadline. An exact whole-tile answer must also be an estimated answer with
an equal numerical value (within floating-point tolerance).

Report exact and estimated coverage side by side, positive and zero-reference
strata, conditional count MAE, conditional occupancy MAE (Road Users), total absolute
error, and errors on the matched answered intersection. Preserve all query
identities/denominators. Separately count estimated-only answers; improved coverage
alone is not improved total utility. No single weighted score or application error
threshold is invented. Future deployments must choose acceptable errors/latencies.

## Verification and stop condition

Tests must cover disjoint partition conservation, mixed crossing/semantic/deadline
masks, unpublished versus late support, source-independent predictions/diagnostics,
truthful parent/child categories, disjoint-class zeros, initial-sample weighting,
space/time allocation examples with nonzero error, missing support, EOF censoring,
high-depth sparse operation and malformed/resource-bound rejection. Compare the
estimator's root-category results with the established scalar occupancy estimator
on a bounded independent case. Verify the new exact definitions/summaries equal
all forty original compact evaluations. Preserve the legacy evaluator unchanged.

The new study starts unverified and becomes verified only after input/code integrity,
all forty exact equivalence checks, estimated coverage/error checks and twenty-four
paired comparisons pass. An error leaves an explicit unverified failure manifest.
Keep the aggregate Git package small; no query-row or identity-bearing output is
necessary. Document results and unfavorable findings in English, with README and
TO-DO links.

After evaluating this contract, interpret why the fixed baseline wins under each
product. Separately profile the frozen implementation to identify actual runtime
costs before optimization. Preserve independent controller semantics, policy-time
checks, identity unions, immutable publication and ACK/retry behavior in any later
performance change. Logical sealing age alone does not include processing backlog.
