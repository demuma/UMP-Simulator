# Semantic First implementation test report

Date: 2026-10-21. Acceptance: passed for the first common-window Semantic First mode,
with Temporal First secondary priority and maximum semantic loss as preference metric.
[Contract](SEMANTIC_FIRST_IMPLEMENTATION.md), [results](SEMANTIC_FIRST_RESULTS_2026-10-21.md).

## Implemented change

The new opt-in semantic_first strategy checks a private zero-loss spatial cut at every
scheduled endpoint, waits without resetting start when necessary, and evaluates bounded
positive-loss levels only at terminal complete endpoints. Original regional hard checks
are untouched. The selector's optional ceiling is not inserted as a fake policy bound.
Publication recomputes actual selected bins with the original evaluator. Diagnostics
include private preference metadata only for the new strategy; recipient schemas remain
unchanged. Cell-local/missing-taxonomy/missing-temporal usage rejects explicitly.

## Build and complete regression

```sh
cmake -S simulator -B simulator/build
cmake --build simulator/build -j 6
ctest --test-dir simulator/build --output-on-failure -j 6
```

All targets, including Simulator, build. All **52/52 CTest entries pass** in 15.11 s.
Python reports **373 methods: 361 passed and 12 skipped**. The 12 skips belong to existing
optional matplotlib/pinned histogram dependencies; all 16 new Python acceptance methods
execute and pass. One new native test entry contains 13 substantive cases; these are
not added to the Python method count. The existing MongoDB entry now includes an
additional actual Semantic First end-to-end persistence case.

[Full per-entry log](../results/verification/semantic-first-2026-10-21/ctest-full.log) and
[verification manifest](../results/verification/semantic-first-2026-10-21/manifest.json)
retain counts, source/test hashes and the final replay binary hash.

## New native acceptance

The 13 cases cover immediately available exact parents versus fine Root output;
zero-cost internal categories; private waiting and minimal 0.5 fallback; newly observed
people producing early zero-loss output with the original interval; retention-first
partial fallback and equal-retention maximum-loss ordering; explicit maximum-versus-mean
trade-offs; strict regional/mean requirements; incomplete coverage; sink rollback and
contiguous successors; EOF publication/retry using the original evaluator; empty windows
and configuration guards; and budget/invalid-ceiling errors without mutation/disclosure.

The resource case permits four finest evaluations but rejects the required fifth parent
with length_error. Active start/next/deadline/evaluation/extension/decision/completion
state, history and sink calls remain unchanged. Separate preference checks reject NaN,
negative/excessive ceilings and mismatched catalog instances. Final ID ties are already
sorted canonically by the spatial selector.

## Independent real-core Python acceptance

All 16 methods invoke the actual replay binary and audit successful outputs against raw
observations, original scalar requirements and bounded independently enumerated category/
spatial cuts. Scalar mode projection explicitly verifies data/count/geometry/time checks,
not the Semantic First priority; separate assertions check its intended decisions and
private metadata. Coverage includes low/medium/high, turnover, strict regional size/loss/
mean/age, incomplete/empty/EOF intervals, partial rescue, immutable exclusivity and invalid
configuration/input rejection before output creation. Recipient payloads contain no
semantic_priority or private source evidence.

## Actual MongoDB acceptance

Four finest cells each supply four pedestrians, two adult cyclists and two child cyclists
at 100/200/300 ms. Semantic First selects their exact 40 m parent at 400 ms under an original
hard loss maximum 1. Its private preference is 0; this does not change the policy ID/version
or hard threshold. The approved snapshot contains 96 observations, 32 distinct road users,
three terminal bins with observation counts 48/24/24 and distinct supports 16/8/8, loss 0.

The existing UUID-owned integration database receives a prepared private intent, public
write, simulated lost acknowledgement, reconciliation, commit and restarted recovery.
The exact approved product persists; retries do not duplicate it and retirement is
exactly 400 ms. No preference/trial metadata, private node counts, raw labels or identities
appear in the recipient BSON. Only fresh UUID test databases are used. The normal
simulator is never launched and the user's Simulation database is not used.

This verifies the stated acknowledgement/recovery sequence, not arbitrary crash recovery;
previously documented F03 post-ack allocation/restart work remains separate.

## Sanitizers

The 13 native cases also pass a separate Apple clang C++17 build with ASan and UBSan:
`-O1 -g -Wall -Wextra -Werror -Wno-missing-field-initializers
-fsanitize=address,undefined -fno-omit-frame-pointer`. Linked sources are the new
controller/selector, history, metrics, policy, coordinator and taxonomy. No ASan/UBSan
finding occurred. Leak detection is disabled because it is unavailable on this macOS
setup; no LeakSanitizer or MongoDB-library sanitizer claim is made.

## Frozen compatibility checks

**30/30 before/after pairs match**, including all serialized bytes after omitting exactly
the top-level runtime object. Configuration YAML and formatting are included. The 24
nonsemantic pairs cover fixed depth 5/6 at 400/1000 ms, spatial, common TF/SF, cell-local
TF/SF and A07-enabled common modes on two fixtures. Six additional pairs cover existing
semantic-enabled TF/SF cases. All 60 independent scalar audits pass.

- Before SHA-256: cfdd2a0b68a4185f42afc4f8f19fc8cbf94d1d84f98edfe47e469296a7e64400.
- After SHA-256: 254692961dc225e5d22511a1c2835d15907b7d4cfca80faf6e9e88f4d358426a.

The [compatibility report](../results/verification/semantic-first-2026-10-21/compatibility/baseline-compatibility.json)
and [verification report](../results/verification/semantic-first-2026-10-21/compatibility/verification-report.json)
preserve all 227 hashed staging/check artifacts. The final root manifest separately hashes
the actual integrated source files, including diagnostic serialization and the new store
case, rather than treating intermediate staged sources as identical to the final build.

The additional 27-case illustration passes 135 independent interval checks, with unchanged
hard settings in each strategy triplet. All 18 old TF/SF outputs remain byte-identical
outside runtime relative to the previous density example. The results report records both
class-query gains and fine-query/waiting costs; no general privacy or utility claim follows.

## Independent review and remaining scope

A separate read-only integration review found no blocking policy/accounting/publication
violation. The mode is bounded and causal, with maximum-loss priority and a deliberate
retention-first partial-output exception. It does not optimize mean semantic loss or a
complete future schedule. Static waiting can add delay without gain. Regional execution
overrides, Semantic First + Spatial First, cell-local semantics, maps, empirical privacy
experiments and computation optimization remain outside this implementation gate.
