# Scope-aware semantic fixed-query utility — protocol and contract

Date: 2026-10-22. Written before executing the new utility evaluation. This is a
retrospective analysis of already known frozen mechanism outputs, not a preregistered
independent traffic experiment. No privacy-effectiveness claim is intended.

## Question and implementation boundary

Can a recipient answer the same declared space-time/category count queries from
common-window and cell-local releases, and by which deadline? Independent windows
can improve availability while introducing boundaries that prevent an exact answer.
Both outcomes must remain visible; no improvement is assumed.

Implement a new `ump.scoped-semantic-queries.v1` evaluator. Keep the legacy
`semantic_queries.py` and its five-node, depth-2 experiment unchanged. The new
engine accepts declared taxonomies and canonical quadtree cells at the replay's
coverage/depth, independently of regional policy or coordination strategy. It
consumes public release records for predictions and raw observations only for a
separate reference. No aggregation, simulation, policy or publication change is
part of this gate.

The current benchmark assumes one canonical terminal class per identity over the
whole reference run; aliases mapping to that same terminal are allowed. A change
to a different terminal is rejected. This is a declared study restriction, stronger
than the producer's per-candidate stability check. Within a published semantic cut,
category supports partition the cell's distinct identities under that restriction.
Observation contributions, rather than distinct identities, are the query target.

## Fixed query and exact-answer rule

Let a query be q = (C_q, I_q, g_q, d_q), where C_q is an ID-derived quadtree
footprint, I_q = [a_q, b_q) its half-open interval, g_q the requested category and
d_q = b_q + ell its deadline. The lag ell is declared before evaluation.

A public record r has its own footprint C_r, unchanged interval I_r, complete
semantic count partition B_r, and publication time s_r. It is available only if
s_r <= d_q. Public records are immutable and may not overlap in positive spatial
area and source time; publication order does not authorize reuse of old support.
A local `coordination_cell` constrains ownership and containment, but does not
certify omitted cells as measured zeros.

A record is usable for q only if C_r is contained in C_q and the whole I_r is
contained in I_q. Crossing records are never clipped, proportionally allocated,
subtracted or converted using the replay viewer's display masks. Records from
different owners, depths and starts may be combined when their unchanged support
forms a complete tiling of the query at every scheduled observation timestamp.

Let L(g) be the set of terminal categories descending from taxonomy node g. A bin
with category h contributes its complete count when L(h) is contained in L(g_q),
and zero when the sets are disjoint. An intersecting bin whose domain extends
outside L(g_q) makes that record semantically unresolved. This also correctly
handles unary taxonomy chains: an ancestor with the same terminal domain is exact.
Private evidence about which possible types happen to be absent cannot resolve
a straddling public category.

With J_q the scheduled samples in I_q and F(C) the finest spatial cells within C,
complete public support requires the disjoint union

    union_r (F(C_r) x (J_q intersect I_r)) = F(C_q) x J_q.

This identity is checked without expanding all possible finest leaves. Empty
private cells never close a public hole. A complete published category partition
can certify a zero for a disjoint class; an absent public footprint cannot.
The exact prediction is the sum of the qualifying published observation counts,
not a sum of per-cell distinct-person counts. Repeated observations of one person
at different samples are separate contributions by definition.

Reference counts use measured raw samples within the identical C_q, I_q and
terminal category domain. Missing/unavailable scheduled samples make the reference
unknown, without changing the recipient prediction. A deliberate public/reference
count discrepancy must remain a nonzero error rather than being repaired from GT.

## Cadence, horizon and summaries

Use the replay's declared cadence. The existing replay convention excludes the
initial t=0 state from measurements; scheduled samples start at one period. A query
with no scheduled samples is explicitly unavailable, not an observed zero. Complete
fixed windows start at zero; a trailing incomplete window is excluded and its
duration reported. Source coordinates, cell IDs, cadence and canonical taxonomy
mappings are validated. Numeric, geometry, taxonomy, overlap and expansion-budget
failures must stop evaluation explicitly.

All deadline lags share the same interior cohort:

    b_q + max(lags) < source_horizon.

Other complete queries form the boundary cohort. A deadline equal to EOF is
observable but labelled as such; a deadline beyond EOF is censored, not a failure
or an opportunity to use future publications. Report interior and boundary results
separately, with a fixed query identity across methods and lags.

For observed queries Q, recipient answer coverage is |A| / |Q|, where A contains
queries with a complete deadline-visible public answer. Separately report scored
coverage over reference-available queries and conditional count MAE:

    MAE = sum_{q in A intersect R} |prediction_q - reference_q| / |A intersect R|.

R contains reference-available queries. Empty denominators are null. Include
reference-unavailable counts, known-zero/positive-reference strata, per-category
summaries and the absolute-error sum. Conditional MAE alone must not reward a
method for suppressing difficult queries. Exact truthful tilings often have zero
conditional error by construction; the informative outcome is which fixed queries
are answerable, and when.

Paired comparisons require identical query definitions, identities, deadlines and
reference values. Report both answered, only common answered, only local answered,
and neither, plus errors on the common answered/reference-available intersection.
No pairing by release geometry and no average of conditional averages.

## Frozen input and workload for this gate

Reuse the verified `results/semantic-cell-local-2026-10-22` study: 20 persistent
identities, 19 measured samples, 380 observations, 80 x 80 m, finest depth 6 and a
2,000-ms horizon. Verify all required source/result/policy digests before evaluating.
Do not generate a new population or alter frozen results.

Evaluate all eight existing combinations: common/local coordination, uniform/regional
policy, and Temporal First/Spatial First secondary priority under Semantic First.
Use every declared taxonomy category (ten nodes), windows 400 and 1,000 ms, and
lags 0, 200 and 400 ms. The following three spatial query banks are identical for
all variants and chosen from the fixture and policy geometry, never successful
release footprints:

1. Entire 80 x 80 m area at 5 m: all 256 depth-4 cells.
2. Six fixed 2.5 x 2.5 m regions, one depth-5 cell each, with lower corners
   (2.5,2.5), (10,10), (20,10), (30,10), (40,10), and (50,10) metres.
3. The same six regions at 1.25 m: their 24 depth-6 children.

The six regions comprise two controls and the four already declared policy patches.
These application masks do not replace the full-area result. Sparse omission and
privately empty subcells can make full-area or parent queries unanswerable. Keep
that outcome instead of redefining the task after seeing results. The 1,000-ms
workload has only one interior time window; no inferential statistics or population
generalization will be derived from this analytical fixture.

## Acceptance, provenance and next gate

Require independent literal tests for asynchronous space-time tiling, missing
spatial/time support, crossing intervals/geometry, semantic ambiguity and unary
chains, deadlines, EOF, stable-type aliases/rejection, high-depth bounds, invalid
records, private-reference independence, compact summaries and paired denominators.
Compare the new engine with the unchanged legacy engine on the old contract.

Freeze workload and implementation digests before executing the 48 variant/workload
evaluations. Preserve original study files; write only a new ignored output directory.
Store compact summaries and pairwise comparisons, not newly copied movement records.
Keep a small aggregate-only report in Git, with code, tests and English documentation.
Document all test results and unfavorable findings.

After this gate, apply the evaluator to a controlled comparison on the same existing
moving input against legal fixed raster/window baselines and common-window adaptation.
Match hard policies and declare time bounds/query masks before running that comparison.
Privacy evaluation follows with a separate protected-unit/secret and recipient model.
