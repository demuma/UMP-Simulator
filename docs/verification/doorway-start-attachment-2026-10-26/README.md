# Bounded doorway start attachment: compact correction evidence

26 October 2026. The declared development/source checks pass. This package supports
the [correction report](../../URBAN_PRIVACY_DOORWAY_START_ATTACHMENT_FIX_2026-10-26.md).
It contains explicit aggregate fields, case ordinals and provenance hashes only.
Source identities, seeds, configurations, raw movement, fitted artifacts and
complete local logs are excluded.

| Check | Outcome | Evidence |
|---|---|---|
| Synthetic regression against original/corrected implementations | RED/GREEN; blocked controls remain blocked | [red-green.json](red-green.json) |
| Diagnosed configuration, unchanged before/after | 153/169 completed at 300 s → 169/169 by 215.05 s | [known-case.json](known-case.json) |
| Affected CTest groups | 12/12 pass in 177.688 s; includes 55 replay-export tests | [affected-tests.json](affected-tests.json) |
| Serial development motion matrix | 92/92 cases; 15,590/15,590 episodes completed | [development-matrix.json](development-matrix.json) |
| Production Simulator → MongoDB → replay → independent audit | 169/169 episodes; 89,591 contributions; 2,999 samples; verified | [production-capture.json](production-capture.json) |

All 92 matrix cases are DEV: 72 historical closed-study configurations, eight
original DEV configurations and 12 fresh independent DEV configurations. The 32
formerly held-out source configurations are explicitly exposed development data.
Every planned outcome is retained; no retries or seed replacement occurred.

The maximum observed start-connector work is 281 checks per replan, separately
from the 20,000-node A* expansion cap. Body, swept-body, speed, displacement and
crossing-cohort checks pass. The independent production audit additionally checks
stored geometry/access and lifecycle consistency. These are bounded development
checks; no general crowd-liveness or real-time guarantee follows. The before/after
timings cover different simulated work and support no speedup claim.

The previous P25.4 source-v2 study remains closed at 71/72 valid sources, with no
TEST mechanism runs, predictions or attack/control/utility estimates. This fix
does not reopen that study or establish improved privacy. A future primary study
is only a DRAFT, with no sources or model fits at this packet's creation.
Separate source/analysis DEV integration is outside this correction packet.

[summary.json](summary.json) records the scope; [code-provenance.json](code-provenance.json)
binds archived and corrected public artifact labels. [bundle-receipt.json](bundle-receipt.json)
hashes every other package file and the correction report. Complete local input
receipts/logs remain available for internal reproduction; their hashes do not
make this compact package a raw-data reproduction dataset.
