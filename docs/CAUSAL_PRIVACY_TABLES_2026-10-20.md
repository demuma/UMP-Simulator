# Causal privacy study: complete aggregate tables

Date: 2026-10-20. The complete fixed-protocol result is preserved here, including controls,
both independent TEST cohorts and both attack families. These aggregate tables contain no
private source identities or trajectories. See [the report](CAUSAL_PRIVACY_REPORT_2026-10-20.md)
for assumptions, interpretation and the source/artifact hashes.

TF preserves temporal resolution; SF preserves spatial resolution. C = common windows,
L = cell-local coordination. Each TEST cohort has 64 independent paired source groups.
AUC below 0.5 is retained without TEST-based inversion. All intervals are pointwise,
scenario-stratified paired-group percentile bootstrap intervals (400 resamples).

## Maximum-score membership outcomes

Scores are maximized across all six checkpoint models. TPR/FPR use one CAL-selected
ever-alarm threshold, frozen across both cohorts; this is distinct from raw checkpoint AUC.

| Cohort | Stream | View | Knowledge | Family | Max-score AUC | 95% interval | TPR | FPR | Advantage |
|---|---|---|---|---|---:|---|---:|---:|---:|
| base | C-SF | history | exact | LR | 0.5697 | [0.5282, 0.6243] | 0.2812 | 0.2344 | 0.0469 |
| shift | C-SF | history | exact | LR | 0.5634 | [0.5356, 0.6039] | 0.3750 | 0.2656 | 0.1094 |
| base | C-SF | history | exact | HGB | 0.6299 | [0.5594, 0.6974] | 0.2969 | 0.1094 | 0.1875 |
| shift | C-SF | history | exact | HGB | 0.5625 | [0.4919, 0.6303] | 0.2500 | 0.2188 | 0.0312 |
| base | C-SF | history | noisy | LR | 0.5730 | [0.5309, 0.6300] | 0.2344 | 0.1562 | 0.0781 |
| shift | C-SF | history | noisy | LR | 0.5657 | [0.5330, 0.6140] | 0.3125 | 0.2344 | 0.0781 |
| base | C-SF | history | noisy | HGB | 0.5986 | [0.5196, 0.6782] | 0.3594 | 0.2344 | 0.1250 |
| shift | C-SF | history | noisy | HGB | 0.5411 | [0.4819, 0.6098] | 0.3750 | 0.3750 | 0.0000 |
| base | C-SF | recent | exact | LR | 0.5880 | [0.5577, 0.6305] | 0.1562 | 0.0938 | 0.0625 |
| shift | C-SF | recent | exact | LR | 0.5690 | [0.5447, 0.6085] | 0.2344 | 0.1094 | 0.1250 |
| base | C-SF | recent | exact | HGB | 0.5792 | [0.5090, 0.6552] | 0.3281 | 0.2500 | 0.0781 |
| shift | C-SF | recent | exact | HGB | 0.5638 | [0.4984, 0.6333] | 0.4531 | 0.3594 | 0.0938 |
| base | C-SF | recent | noisy | LR | 0.5857 | [0.5504, 0.6328] | 0.1406 | 0.0781 | 0.0625 |
| shift | C-SF | recent | noisy | LR | 0.5602 | [0.5322, 0.6040] | 0.2031 | 0.1562 | 0.0469 |
| base | C-SF | recent | noisy | HGB | 0.5923 | [0.5189, 0.6608] | 0.1562 | 0.0938 | 0.0625 |
| shift | C-SF | recent | noisy | HGB | 0.5287 | [0.4671, 0.5938] | 0.1562 | 0.1875 | -0.0312 |
| base | C-TF | history | exact | LR | 0.6151 | [0.5748, 0.6671] | 0.1406 | 0.0469 | 0.0938 |
| shift | C-TF | history | exact | LR | 0.6312 | [0.5924, 0.6797] | 0.1406 | 0.0938 | 0.0469 |
| base | C-TF | history | exact | HGB | 0.6682 | [0.6074, 0.7343] | 0.2812 | 0.2188 | 0.0625 |
| shift | C-TF | history | exact | HGB | 0.5776 | [0.5117, 0.6394] | 0.3281 | 0.2812 | 0.0469 |
| base | C-TF | history | noisy | LR | 0.6411 | [0.5984, 0.6847] | 0.1406 | 0.0781 | 0.0625 |
| shift | C-TF | history | noisy | LR | 0.6399 | [0.5920, 0.6873] | 0.2500 | 0.0469 | 0.2031 |
| base | C-TF | history | noisy | HGB | 0.6169 | [0.5469, 0.6901] | 0.2500 | 0.1094 | 0.1406 |
| shift | C-TF | history | noisy | HGB | 0.5566 | [0.4940, 0.6209] | 0.4219 | 0.3594 | 0.0625 |
| base | C-TF | recent | exact | LR | 0.6051 | [0.5537, 0.6701] | 0.1250 | 0.0781 | 0.0469 |
| shift | C-TF | recent | exact | LR | 0.6178 | [0.5736, 0.6728] | 0.1562 | 0.1250 | 0.0312 |
| base | C-TF | recent | exact | HGB | 0.6152 | [0.5506, 0.6791] | 0.2344 | 0.1719 | 0.0625 |
| shift | C-TF | recent | exact | HGB | 0.5861 | [0.5191, 0.6540] | 0.2500 | 0.1250 | 0.1250 |
| base | C-TF | recent | noisy | LR | 0.6477 | [0.6015, 0.7046] | 0.0781 | 0.0781 | 0.0000 |
| shift | C-TF | recent | noisy | LR | 0.6428 | [0.5915, 0.6929] | 0.0625 | 0.0312 | 0.0312 |
| base | C-TF | recent | noisy | HGB | 0.5721 | [0.5134, 0.6277] | 0.1406 | 0.1094 | 0.0312 |
| shift | C-TF | recent | noisy | HGB | 0.5503 | [0.4799, 0.6126] | 0.2500 | 0.1875 | 0.0625 |
| base | Auxiliary | auxiliary | exact | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | Auxiliary | auxiliary | exact | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | Auxiliary | auxiliary | exact | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | Auxiliary | auxiliary | exact | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | Auxiliary | auxiliary | noisy | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | Auxiliary | auxiliary | noisy | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | Auxiliary | auxiliary | noisy | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | Auxiliary | auxiliary | noisy | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | Exact count | history | exact | LR | 0.6075 | [0.5884, 0.6405] | 0.1562 | 0.1562 | 0.0000 |
| shift | Exact count | history | exact | LR | 0.5775 | [0.5602, 0.6049] | 0.2031 | 0.1875 | 0.0156 |
| base | Exact count | history | exact | HGB | 0.7183 | [0.6569, 0.7814] | 0.1562 | 0.0625 | 0.0938 |
| shift | Exact count | history | exact | HGB | 0.5958 | [0.5296, 0.6673] | 0.0938 | 0.0781 | 0.0156 |
| base | Exact count | history | noisy | LR | 0.5986 | [0.5762, 0.6377] | 0.1406 | 0.1250 | 0.0156 |
| shift | Exact count | history | noisy | LR | 0.5803 | [0.5674, 0.6060] | 0.1406 | 0.1094 | 0.0312 |
| base | Exact count | history | noisy | HGB | 0.7034 | [0.6576, 0.7569] | 0.3594 | 0.0938 | 0.2656 |
| shift | Exact count | history | noisy | HGB | 0.5665 | [0.5249, 0.6062] | 0.2969 | 0.2188 | 0.0781 |
| base | Exact count | recent | exact | LR | 0.5978 | [0.5771, 0.6311] | 0.0625 | 0.0469 | 0.0156 |
| shift | Exact count | recent | exact | LR | 0.5621 | [0.5459, 0.5875] | 0.1250 | 0.1094 | 0.0156 |
| base | Exact count | recent | exact | HGB | 0.6760 | [0.6012, 0.7640] | 0.1406 | 0.0781 | 0.0625 |
| shift | Exact count | recent | exact | HGB | 0.5308 | [0.4720, 0.5919] | 0.0312 | 0.0938 | -0.0625 |
| base | Exact count | recent | noisy | LR | 0.5796 | [0.5576, 0.6097] | 0.1406 | 0.0938 | 0.0469 |
| shift | Exact count | recent | noisy | LR | 0.5723 | [0.5598, 0.5938] | 0.1719 | 0.1250 | 0.0469 |
| base | Exact count | recent | noisy | HGB | 0.6864 | [0.6292, 0.7413] | 0.3281 | 0.1562 | 0.1719 |
| shift | Exact count | recent | noisy | HGB | 0.5469 | [0.4880, 0.6035] | 0.2656 | 0.2344 | 0.0312 |
| base | No output | history | exact | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | No output | history | exact | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | No output | history | exact | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | No output | history | exact | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | No output | history | noisy | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | No output | history | noisy | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | No output | history | noisy | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | No output | history | noisy | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | No output | recent | exact | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | No output | recent | exact | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | No output | recent | exact | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | No output | recent | exact | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | No output | recent | noisy | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | No output | recent | noisy | LR | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | No output | recent | noisy | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| shift | No output | recent | noisy | HGB | 0.5000 | [0.5000, 0.5000] | 0.0000 | 0.0000 | 0.0000 |
| base | Fixed | history | exact | LR | 0.5687 | [0.5276, 0.6180] | 0.0781 | 0.0469 | 0.0312 |
| shift | Fixed | history | exact | LR | 0.5488 | [0.5157, 0.5906] | 0.0938 | 0.0938 | 0.0000 |
| base | Fixed | history | exact | HGB | 0.5957 | [0.5326, 0.6576] | 0.2500 | 0.2500 | 0.0000 |
| shift | Fixed | history | exact | HGB | 0.6099 | [0.5534, 0.6681] | 0.4375 | 0.3438 | 0.0938 |
| base | Fixed | history | noisy | LR | 0.5854 | [0.5415, 0.6416] | 0.1250 | 0.0469 | 0.0781 |
| shift | Fixed | history | noisy | LR | 0.5515 | [0.5175, 0.5978] | 0.0312 | 0.0469 | -0.0156 |
| base | Fixed | history | noisy | HGB | 0.5802 | [0.5228, 0.6360] | 0.0781 | 0.0312 | 0.0469 |
| shift | Fixed | history | noisy | HGB | 0.6000 | [0.5447, 0.6492] | 0.1562 | 0.0781 | 0.0781 |
| base | Fixed | recent | exact | LR | 0.5684 | [0.5227, 0.6129] | 0.0625 | 0.0469 | 0.0156 |
| shift | Fixed | recent | exact | LR | 0.5317 | [0.4971, 0.5660] | 0.0156 | 0.0156 | 0.0000 |
| base | Fixed | recent | exact | HGB | 0.6455 | [0.5886, 0.6970] | 0.1562 | 0.0625 | 0.0938 |
| shift | Fixed | recent | exact | HGB | 0.5729 | [0.5148, 0.6386] | 0.2031 | 0.1250 | 0.0781 |
| base | Fixed | recent | noisy | LR | 0.5834 | [0.5356, 0.6371] | 0.1094 | 0.0625 | 0.0469 |
| shift | Fixed | recent | noisy | LR | 0.5432 | [0.5089, 0.5886] | 0.0781 | 0.0469 | 0.0312 |
| base | Fixed | recent | noisy | HGB | 0.6188 | [0.5555, 0.6764] | 0.1094 | 0.0156 | 0.0938 |
| shift | Fixed | recent | noisy | HGB | 0.5836 | [0.5256, 0.6487] | 0.0781 | 0.0625 | 0.0156 |
| base | L-SF | history | exact | LR | 0.5743 | [0.5389, 0.6287] | 0.2500 | 0.1875 | 0.0625 |
| shift | L-SF | history | exact | LR | 0.5662 | [0.5361, 0.6080] | 0.2812 | 0.2031 | 0.0781 |
| base | L-SF | history | exact | HGB | 0.6416 | [0.5781, 0.7163] | 0.2500 | 0.1719 | 0.0781 |
| shift | L-SF | history | exact | HGB | 0.5760 | [0.5059, 0.6523] | 0.2188 | 0.1719 | 0.0469 |
| base | L-SF | history | noisy | LR | 0.5798 | [0.5399, 0.6281] | 0.2031 | 0.1250 | 0.0781 |
| shift | L-SF | history | noisy | LR | 0.5591 | [0.5290, 0.5987] | 0.2656 | 0.1562 | 0.1094 |
| base | L-SF | history | noisy | HGB | 0.6202 | [0.5431, 0.6942] | 0.3438 | 0.2188 | 0.1250 |
| shift | L-SF | history | noisy | HGB | 0.5298 | [0.4672, 0.5907] | 0.3438 | 0.3750 | -0.0312 |
| base | L-SF | recent | exact | LR | 0.5804 | [0.5544, 0.6209] | 0.1875 | 0.1562 | 0.0312 |
| shift | L-SF | recent | exact | LR | 0.5597 | [0.5345, 0.5968] | 0.2656 | 0.1719 | 0.0938 |
| base | L-SF | recent | exact | HGB | 0.5844 | [0.5101, 0.6537] | 0.1719 | 0.1406 | 0.0312 |
| shift | L-SF | recent | exact | HGB | 0.5818 | [0.5227, 0.6509] | 0.1562 | 0.1562 | 0.0000 |
| base | L-SF | recent | noisy | LR | 0.5804 | [0.5486, 0.6285] | 0.2500 | 0.1719 | 0.0781 |
| shift | L-SF | recent | noisy | LR | 0.5658 | [0.5363, 0.6107] | 0.2031 | 0.1562 | 0.0469 |
| base | L-SF | recent | noisy | HGB | 0.5691 | [0.4871, 0.6446] | 0.1094 | 0.0469 | 0.0625 |
| shift | L-SF | recent | noisy | HGB | 0.5034 | [0.4515, 0.5612] | 0.1406 | 0.1719 | -0.0312 |
| base | L-TF | history | exact | LR | 0.5831 | [0.5445, 0.6286] | 0.0469 | 0.0469 | 0.0000 |
| shift | L-TF | history | exact | LR | 0.5756 | [0.5434, 0.6168] | 0.1094 | 0.0938 | 0.0156 |
| base | L-TF | history | exact | HGB | 0.6682 | [0.6003, 0.7398] | 0.2812 | 0.1094 | 0.1719 |
| shift | L-TF | history | exact | HGB | 0.6117 | [0.5379, 0.6773] | 0.2656 | 0.1562 | 0.1094 |
| base | L-TF | history | noisy | LR | 0.5969 | [0.5535, 0.6452] | 0.0938 | 0.0781 | 0.0156 |
| shift | L-TF | history | noisy | LR | 0.5688 | [0.5305, 0.6123] | 0.0938 | 0.0625 | 0.0312 |
| base | L-TF | history | noisy | HGB | 0.6217 | [0.5520, 0.6913] | 0.2031 | 0.1094 | 0.0938 |
| shift | L-TF | history | noisy | HGB | 0.5531 | [0.4874, 0.6203] | 0.4375 | 0.4062 | 0.0312 |
| base | L-TF | recent | exact | LR | 0.5596 | [0.5210, 0.6029] | 0.0938 | 0.0781 | 0.0156 |
| shift | L-TF | recent | exact | LR | 0.5707 | [0.5403, 0.6082] | 0.1094 | 0.1094 | 0.0000 |
| base | L-TF | recent | exact | HGB | 0.6582 | [0.6000, 0.7197] | 0.2656 | 0.0938 | 0.1719 |
| shift | L-TF | recent | exact | HGB | 0.5540 | [0.4747, 0.6256] | 0.2031 | 0.1094 | 0.0938 |
| base | L-TF | recent | noisy | LR | 0.5719 | [0.5329, 0.6155] | 0.1094 | 0.1094 | 0.0000 |
| shift | L-TF | recent | noisy | LR | 0.5533 | [0.5310, 0.5863] | 0.0938 | 0.0938 | 0.0000 |
| base | L-TF | recent | noisy | HGB | 0.6338 | [0.5593, 0.7051] | 0.2031 | 0.0938 | 0.1094 |
| shift | L-TF | recent | noisy | HGB | 0.5585 | [0.4820, 0.6292] | 0.2031 | 0.0781 | 0.1250 |

## History-minus-recent maximum-score contrasts

These compare fixed representations and fitted learners; they do not isolate the
information-theoretic effect of remembering records. At the 1-second checkpoint the
public information coincides, but the duplicated history block changes LR regularization.

| Cohort | Stream | Knowledge | Family | AUC difference | Paired 95% interval |
|---|---|---|---|---:|---|
| base | C-SF | exact | LR | -0.0183 | [-0.0601, 0.0176] |
| shift | C-SF | exact | LR | -0.0056 | [-0.0304, 0.0189] |
| base | C-SF | exact | HGB | 0.0507 | [-0.0056, 0.1081] |
| shift | C-SF | exact | HGB | -0.0013 | [-0.0609, 0.0535] |
| base | C-SF | noisy | LR | -0.0127 | [-0.0575, 0.0309] |
| shift | C-SF | noisy | LR | 0.0055 | [-0.0237, 0.0304] |
| base | C-SF | noisy | HGB | 0.0063 | [-0.0643, 0.0778] |
| shift | C-SF | noisy | HGB | 0.0125 | [-0.0512, 0.0750] |
| base | C-TF | exact | LR | 0.0100 | [-0.0208, 0.0410] |
| shift | C-TF | exact | LR | 0.0134 | [-0.0305, 0.0552] |
| base | C-TF | exact | HGB | 0.0530 | [-0.0079, 0.1074] |
| shift | C-TF | exact | HGB | -0.0084 | [-0.0796, 0.0615] |
| base | C-TF | noisy | LR | -0.0066 | [-0.0418, 0.0354] |
| shift | C-TF | noisy | LR | -0.0029 | [-0.0474, 0.0366] |
| base | C-TF | noisy | HGB | 0.0448 | [-0.0184, 0.1113] |
| shift | C-TF | noisy | HGB | 0.0063 | [-0.0629, 0.0785] |
| base | Exact count | exact | LR | 0.0098 | [-0.0093, 0.0291] |
| shift | Exact count | exact | LR | 0.0154 | [-0.0015, 0.0345] |
| base | Exact count | exact | HGB | 0.0422 | [-0.0145, 0.1051] |
| shift | Exact count | exact | HGB | 0.0651 | [0.0093, 0.1166] |
| base | Exact count | noisy | LR | 0.0190 | [-0.0073, 0.0508] |
| shift | Exact count | noisy | LR | 0.0081 | [-0.0110, 0.0337] |
| base | Exact count | noisy | HGB | 0.0170 | [-0.0536, 0.0971] |
| shift | Exact count | noisy | HGB | 0.0197 | [-0.0227, 0.0643] |
| base | No output | exact | LR | 0.0000 | [0.0000, 0.0000] |
| shift | No output | exact | LR | 0.0000 | [0.0000, 0.0000] |
| base | No output | exact | HGB | 0.0000 | [0.0000, 0.0000] |
| shift | No output | exact | HGB | 0.0000 | [0.0000, 0.0000] |
| base | No output | noisy | LR | 0.0000 | [0.0000, 0.0000] |
| shift | No output | noisy | LR | 0.0000 | [0.0000, 0.0000] |
| base | No output | noisy | HGB | 0.0000 | [0.0000, 0.0000] |
| shift | No output | noisy | HGB | 0.0000 | [0.0000, 0.0000] |
| base | Fixed | exact | LR | 0.0004 | [-0.0243, 0.0298] |
| shift | Fixed | exact | LR | 0.0171 | [-0.0032, 0.0426] |
| base | Fixed | exact | HGB | -0.0498 | [-0.1062, 0.0113] |
| shift | Fixed | exact | HGB | 0.0370 | [-0.0248, 0.1008] |
| base | Fixed | noisy | LR | 0.0021 | [-0.0169, 0.0205] |
| shift | Fixed | noisy | LR | 0.0083 | [-0.0056, 0.0242] |
| base | Fixed | noisy | HGB | -0.0386 | [-0.0842, 0.0089] |
| shift | Fixed | noisy | HGB | 0.0164 | [-0.0293, 0.0729] |
| base | L-SF | exact | LR | -0.0061 | [-0.0499, 0.0336] |
| shift | L-SF | exact | LR | 0.0065 | [-0.0171, 0.0352] |
| base | L-SF | exact | HGB | 0.0573 | [-0.0055, 0.1265] |
| shift | L-SF | exact | HGB | -0.0057 | [-0.0840, 0.0695] |
| base | L-SF | noisy | LR | -0.0006 | [-0.0444, 0.0361] |
| shift | L-SF | noisy | LR | -0.0067 | [-0.0289, 0.0151] |
| base | L-SF | noisy | HGB | 0.0511 | [-0.0182, 0.1176] |
| shift | L-SF | noisy | HGB | 0.0264 | [-0.0305, 0.0959] |
| base | L-TF | exact | LR | 0.0236 | [-0.0154, 0.0709] |
| shift | L-TF | exact | LR | 0.0049 | [-0.0230, 0.0280] |
| base | L-TF | exact | HGB | 0.0100 | [-0.0431, 0.0629] |
| shift | L-TF | exact | HGB | 0.0577 | [-0.0104, 0.1268] |
| base | L-TF | noisy | LR | 0.0250 | [-0.0070, 0.0618] |
| shift | L-TF | noisy | LR | 0.0155 | [-0.0171, 0.0472] |
| base | L-TF | noisy | HGB | -0.0121 | [-0.0680, 0.0332] |
| shift | L-TF | noisy | HGB | -0.0054 | [-0.0609, 0.0488] |

## View-minus-auxiliary maximum-score contrasts

All same-group release-view comparisons are retained. Identical knowledge-only IN/OUT
features imply auxiliary AUC 0.5. An exact-count control is not a proven attack bound.

| Cohort | Stream | View | Knowledge | Family | AUC difference | Paired 95% interval |
|---|---|---|---|---|---:|---|
| base | C-SF | history | exact | LR | 0.0697 | [0.0313, 0.1156] |
| shift | C-SF | history | exact | LR | 0.0634 | [0.0362, 0.1124] |
| base | C-SF | history | exact | HGB | 0.1299 | [0.0531, 0.2017] |
| shift | C-SF | history | exact | HGB | 0.0625 | [-0.0057, 0.1287] |
| base | C-SF | history | noisy | LR | 0.0730 | [0.0348, 0.1174] |
| shift | C-SF | history | noisy | LR | 0.0657 | [0.0339, 0.1096] |
| base | C-SF | history | noisy | HGB | 0.0986 | [0.0129, 0.1749] |
| shift | C-SF | history | noisy | HGB | 0.0411 | [-0.0302, 0.1083] |
| base | C-SF | recent | exact | LR | 0.0880 | [0.0591, 0.1333] |
| shift | C-SF | recent | exact | LR | 0.0690 | [0.0448, 0.1116] |
| base | C-SF | recent | exact | HGB | 0.0792 | [0.0015, 0.1625] |
| shift | C-SF | recent | exact | HGB | 0.0638 | [-0.0076, 0.1254] |
| base | C-SF | recent | noisy | LR | 0.0857 | [0.0480, 0.1355] |
| shift | C-SF | recent | noisy | LR | 0.0602 | [0.0302, 0.1073] |
| base | C-SF | recent | noisy | HGB | 0.0923 | [0.0171, 0.1653] |
| shift | C-SF | recent | noisy | HGB | 0.0287 | [-0.0287, 0.0837] |
| base | C-TF | history | exact | LR | 0.1151 | [0.0786, 0.1661] |
| shift | C-TF | history | exact | LR | 0.1312 | [0.0905, 0.1764] |
| base | C-TF | history | exact | HGB | 0.1682 | [0.1007, 0.2323] |
| shift | C-TF | history | exact | HGB | 0.0776 | [0.0188, 0.1421] |
| base | C-TF | history | noisy | LR | 0.1411 | [0.0983, 0.1915] |
| shift | C-TF | history | noisy | LR | 0.1399 | [0.1020, 0.1861] |
| base | C-TF | history | noisy | HGB | 0.1169 | [0.0521, 0.1824] |
| shift | C-TF | history | noisy | HGB | 0.0566 | [-0.0029, 0.1242] |
| base | C-TF | recent | exact | LR | 0.1051 | [0.0456, 0.1669] |
| shift | C-TF | recent | exact | LR | 0.1178 | [0.0767, 0.1740] |
| base | C-TF | recent | exact | HGB | 0.1152 | [0.0476, 0.1879] |
| shift | C-TF | recent | exact | HGB | 0.0861 | [0.0077, 0.1538] |
| base | C-TF | recent | noisy | LR | 0.1477 | [0.0960, 0.2063] |
| shift | C-TF | recent | noisy | LR | 0.1428 | [0.0930, 0.1946] |
| base | C-TF | recent | noisy | HGB | 0.0721 | [0.0151, 0.1338] |
| shift | C-TF | recent | noisy | HGB | 0.0503 | [-0.0182, 0.1220] |
| base | Exact count | history | exact | LR | 0.1075 | [0.0877, 0.1405] |
| shift | Exact count | history | exact | LR | 0.0775 | [0.0591, 0.1089] |
| base | Exact count | history | exact | HGB | 0.2183 | [0.1509, 0.2815] |
| shift | Exact count | history | exact | HGB | 0.0958 | [0.0343, 0.1641] |
| base | Exact count | history | noisy | LR | 0.0986 | [0.0767, 0.1377] |
| shift | Exact count | history | noisy | LR | 0.0803 | [0.0661, 0.1096] |
| base | Exact count | history | noisy | HGB | 0.2034 | [0.1515, 0.2594] |
| shift | Exact count | history | noisy | HGB | 0.0665 | [0.0297, 0.1037] |
| base | Exact count | recent | exact | LR | 0.0978 | [0.0769, 0.1317] |
| shift | Exact count | recent | exact | LR | 0.0621 | [0.0486, 0.0871] |
| base | Exact count | recent | exact | HGB | 0.1760 | [0.0915, 0.2527] |
| shift | Exact count | recent | exact | HGB | 0.0308 | [-0.0310, 0.0915] |
| base | Exact count | recent | noisy | LR | 0.0796 | [0.0590, 0.1104] |
| shift | Exact count | recent | noisy | LR | 0.0723 | [0.0598, 0.0979] |
| base | Exact count | recent | noisy | HGB | 0.1864 | [0.1207, 0.2447] |
| shift | Exact count | recent | noisy | HGB | 0.0469 | [-0.0043, 0.1035] |
| base | No output | history | exact | LR | 0.0000 | [0.0000, 0.0000] |
| shift | No output | history | exact | LR | 0.0000 | [0.0000, 0.0000] |
| base | No output | history | exact | HGB | 0.0000 | [0.0000, 0.0000] |
| shift | No output | history | exact | HGB | 0.0000 | [0.0000, 0.0000] |
| base | No output | history | noisy | LR | 0.0000 | [0.0000, 0.0000] |
| shift | No output | history | noisy | LR | 0.0000 | [0.0000, 0.0000] |
| base | No output | history | noisy | HGB | 0.0000 | [0.0000, 0.0000] |
| shift | No output | history | noisy | HGB | 0.0000 | [0.0000, 0.0000] |
| base | No output | recent | exact | LR | 0.0000 | [0.0000, 0.0000] |
| shift | No output | recent | exact | LR | 0.0000 | [0.0000, 0.0000] |
| base | No output | recent | exact | HGB | 0.0000 | [0.0000, 0.0000] |
| shift | No output | recent | exact | HGB | 0.0000 | [0.0000, 0.0000] |
| base | No output | recent | noisy | LR | 0.0000 | [0.0000, 0.0000] |
| shift | No output | recent | noisy | LR | 0.0000 | [0.0000, 0.0000] |
| base | No output | recent | noisy | HGB | 0.0000 | [0.0000, 0.0000] |
| shift | No output | recent | noisy | HGB | 0.0000 | [0.0000, 0.0000] |
| base | Fixed | history | exact | LR | 0.0687 | [0.0276, 0.1211] |
| shift | Fixed | history | exact | LR | 0.0488 | [0.0168, 0.0874] |
| base | Fixed | history | exact | HGB | 0.0957 | [0.0375, 0.1567] |
| shift | Fixed | history | exact | HGB | 0.1099 | [0.0461, 0.1671] |
| base | Fixed | history | noisy | LR | 0.0854 | [0.0431, 0.1365] |
| shift | Fixed | history | noisy | LR | 0.0515 | [0.0168, 0.0989] |
| base | Fixed | history | noisy | HGB | 0.0802 | [0.0286, 0.1380] |
| shift | Fixed | history | noisy | HGB | 0.1000 | [0.0403, 0.1556] |
| base | Fixed | recent | exact | LR | 0.0684 | [0.0229, 0.1137] |
| shift | Fixed | recent | exact | LR | 0.0317 | [0.0003, 0.0743] |
| base | Fixed | recent | exact | HGB | 0.1455 | [0.0842, 0.2028] |
| shift | Fixed | recent | exact | HGB | 0.0729 | [0.0193, 0.1285] |
| base | Fixed | recent | noisy | LR | 0.0834 | [0.0379, 0.1322] |
| shift | Fixed | recent | noisy | LR | 0.0432 | [0.0044, 0.0909] |
| base | Fixed | recent | noisy | HGB | 0.1188 | [0.0558, 0.1786] |
| shift | Fixed | recent | noisy | HGB | 0.0836 | [0.0198, 0.1375] |
| base | L-SF | history | exact | LR | 0.0743 | [0.0409, 0.1233] |
| shift | L-SF | history | exact | LR | 0.0662 | [0.0383, 0.1101] |
| base | L-SF | history | exact | HGB | 0.1416 | [0.0670, 0.2104] |
| shift | L-SF | history | exact | HGB | 0.0760 | [0.0032, 0.1491] |
| base | L-SF | history | noisy | LR | 0.0798 | [0.0427, 0.1319] |
| shift | L-SF | history | noisy | LR | 0.0591 | [0.0293, 0.1038] |
| base | L-SF | history | noisy | HGB | 0.1202 | [0.0487, 0.1961] |
| shift | L-SF | history | noisy | HGB | 0.0298 | [-0.0274, 0.0939] |
| base | L-SF | recent | exact | LR | 0.0804 | [0.0500, 0.1190] |
| shift | L-SF | recent | exact | LR | 0.0597 | [0.0379, 0.0990] |
| base | L-SF | recent | exact | HGB | 0.0844 | [0.0095, 0.1564] |
| shift | L-SF | recent | exact | HGB | 0.0818 | [0.0205, 0.1591] |
| base | L-SF | recent | noisy | LR | 0.0804 | [0.0464, 0.1255] |
| shift | L-SF | recent | noisy | LR | 0.0658 | [0.0360, 0.1142] |
| base | L-SF | recent | noisy | HGB | 0.0691 | [-0.0084, 0.1430] |
| shift | L-SF | recent | noisy | HGB | 0.0034 | [-0.0574, 0.0660] |
| base | L-TF | history | exact | LR | 0.0831 | [0.0471, 0.1234] |
| shift | L-TF | history | exact | LR | 0.0756 | [0.0432, 0.1148] |
| base | L-TF | history | exact | HGB | 0.1682 | [0.0921, 0.2357] |
| shift | L-TF | history | exact | HGB | 0.1117 | [0.0382, 0.1820] |
| base | L-TF | history | noisy | LR | 0.0969 | [0.0610, 0.1408] |
| shift | L-TF | history | noisy | LR | 0.0688 | [0.0283, 0.1140] |
| base | L-TF | history | noisy | HGB | 0.1217 | [0.0527, 0.1901] |
| shift | L-TF | history | noisy | HGB | 0.0531 | [-0.0121, 0.1183] |
| base | L-TF | recent | exact | LR | 0.0596 | [0.0191, 0.1049] |
| shift | L-TF | recent | exact | LR | 0.0707 | [0.0393, 0.1134] |
| base | L-TF | recent | exact | HGB | 0.1582 | [0.0966, 0.2239] |
| shift | L-TF | recent | exact | HGB | 0.0540 | [-0.0233, 0.1275] |
| base | L-TF | recent | noisy | LR | 0.0719 | [0.0365, 0.1175] |
| shift | L-TF | recent | noisy | LR | 0.0533 | [0.0303, 0.0874] |
| base | L-TF | recent | noisy | HGB | 0.1338 | [0.0719, 0.2031] |
| shift | L-TF | recent | noisy | HGB | 0.0585 | [-0.0229, 0.1318] |

## Primary deadline utility

The fixed denominator is 114688 queries per cohort and stream: 128 worlds x 896 queries.
Every primary deadline precedes EOF. Missing support is unknown; MAE is conditional on
answered reference queries and uses road users as its unit. These are descriptive pooled
counts, not independent-query confidence intervals. Relaxing a scoring deadline does not
change the publication mechanism or the recipient privacy view.

| Cohort | Stream | Lag (ms) | Answered | Coverage (%) | Scored | MAE |
|---|---|---:|---:|---:|---:|---:|
| base | Fixed | 0 | 13976 | 12.1861 | 13976 | 2.0663 |
| base | Fixed | 200 | 13976 | 12.1861 | 13976 | 2.0663 |
| base | Fixed | 500 | 13976 | 12.1861 | 13976 | 2.0663 |
| base | Fixed | 1000 | 13976 | 12.1861 | 13976 | 2.0663 |
| base | C-TF | 0 | 8488 | 7.4009 | 8488 | 0.6877 |
| base | C-TF | 200 | 16118 | 14.0538 | 16118 | 0.7321 |
| base | C-TF | 500 | 18864 | 16.4481 | 18864 | 0.7207 |
| base | C-TF | 1000 | 20062 | 17.4927 | 20062 | 0.7200 |
| base | C-SF | 0 | 22701 | 19.7937 | 22701 | 0.6929 |
| base | C-SF | 200 | 22701 | 19.7937 | 22701 | 0.6929 |
| base | C-SF | 500 | 22701 | 19.7937 | 22701 | 0.6929 |
| base | C-SF | 1000 | 22701 | 19.7937 | 22701 | 0.6929 |
| base | L-TF | 0 | 11216 | 9.7796 | 11216 | 0.7413 |
| base | L-TF | 200 | 18143 | 15.8194 | 18143 | 0.7389 |
| base | L-TF | 500 | 18933 | 16.5083 | 18933 | 0.7283 |
| base | L-TF | 1000 | 18934 | 16.5091 | 18934 | 0.7283 |
| base | L-SF | 0 | 16907 | 14.7417 | 16907 | 0.7248 |
| base | L-SF | 200 | 18736 | 16.3365 | 18736 | 0.7146 |
| base | L-SF | 500 | 19264 | 16.7969 | 19264 | 0.7166 |
| base | L-SF | 1000 | 21743 | 18.9584 | 21743 | 0.6993 |
| base | Exact count | 0 | 114688 | 100.0000 | 114688 | 0.0000 |
| base | Exact count | 200 | 114688 | 100.0000 | 114688 | 0.0000 |
| base | Exact count | 500 | 114688 | 100.0000 | 114688 | 0.0000 |
| base | Exact count | 1000 | 114688 | 100.0000 | 114688 | 0.0000 |
| base | No output | 0 | 0 | 0.0000 | 0 | — |
| base | No output | 200 | 0 | 0.0000 | 0 | — |
| base | No output | 500 | 0 | 0.0000 | 0 | — |
| base | No output | 1000 | 0 | 0.0000 | 0 | — |
| shift | Fixed | 0 | 18388 | 16.0331 | 18388 | 2.5217 |
| shift | Fixed | 200 | 18388 | 16.0331 | 18388 | 2.5217 |
| shift | Fixed | 500 | 18388 | 16.0331 | 18388 | 2.5217 |
| shift | Fixed | 1000 | 18388 | 16.0331 | 18388 | 2.5217 |
| shift | C-TF | 0 | 5413 | 4.7198 | 5413 | 0.8795 |
| shift | C-TF | 200 | 13484 | 11.7571 | 13484 | 0.8943 |
| shift | C-TF | 500 | 17785 | 15.5073 | 17785 | 0.8585 |
| shift | C-TF | 1000 | 20626 | 17.9844 | 20626 | 0.8569 |
| shift | C-SF | 0 | 24715 | 21.5498 | 24715 | 0.8294 |
| shift | C-SF | 200 | 24715 | 21.5498 | 24715 | 0.8294 |
| shift | C-SF | 500 | 24715 | 21.5498 | 24715 | 0.8294 |
| shift | C-SF | 1000 | 24715 | 21.5498 | 24715 | 0.8294 |
| shift | L-TF | 0 | 11325 | 9.8746 | 11325 | 0.9091 |
| shift | L-TF | 200 | 19169 | 16.7140 | 19169 | 0.8944 |
| shift | L-TF | 500 | 20596 | 17.9583 | 20596 | 0.8852 |
| shift | L-TF | 1000 | 20600 | 17.9618 | 20600 | 0.8851 |
| shift | L-SF | 0 | 16070 | 14.0119 | 16070 | 0.9209 |
| shift | L-SF | 200 | 18978 | 16.5475 | 18978 | 0.8863 |
| shift | L-SF | 500 | 20266 | 17.6705 | 20266 | 0.8692 |
| shift | L-SF | 1000 | 22980 | 20.0370 | 22980 | 0.8442 |
| shift | Exact count | 0 | 114688 | 100.0000 | 114688 | 0.0000 |
| shift | Exact count | 200 | 114688 | 100.0000 | 114688 | 0.0000 |
| shift | Exact count | 500 | 114688 | 100.0000 | 114688 | 0.0000 |
| shift | Exact count | 1000 | 114688 | 100.0000 | 114688 | 0.0000 |
| shift | No output | 0 | 0 | 0.0000 | 0 | — |
| shift | No output | 200 | 0 | 0.0000 | 0 | — |
| shift | No output | 500 | 0 | 0.0000 | 0 | — |
| shift | No output | 1000 | 0 | 0.0000 | 0 | — |

## Common/local matched-query accuracy

Each comparison uses the intersection of answered queries from the same source world
and deadline. Report this with full-domain coverage, never in isolation.

| Cohort | Priority | Lag (ms) | Matched queries | Common MAE | Local MAE | Local minus common |
|---|---|---:|---:|---:|---:|---:|
| base | TF | 0 | 5222 | 0.6312 | 0.6265 | -0.0046 |
| base | TF | 200 | 14218 | 0.7547 | 0.7525 | -0.0022 |
| base | TF | 500 | 17295 | 0.7354 | 0.7336 | -0.0017 |
| base | TF | 1000 | 18389 | 0.7357 | 0.7340 | -0.0017 |
| base | SF | 0 | 16907 | 0.7248 | 0.7248 | 0.0000 |
| base | SF | 200 | 18728 | 0.7147 | 0.7146 | -0.0001 |
| base | SF | 500 | 19254 | 0.7162 | 0.7167 | 0.0005 |
| base | SF | 1000 | 21703 | 0.6996 | 0.6994 | -0.0002 |
| shift | TF | 0 | 3407 | 0.7728 | 0.7699 | -0.0029 |
| shift | TF | 200 | 12211 | 0.9126 | 0.9241 | 0.0115 |
| shift | TF | 500 | 16909 | 0.8719 | 0.8800 | 0.0081 |
| shift | TF | 1000 | 19608 | 0.8718 | 0.8843 | 0.0125 |
| shift | SF | 0 | 16070 | 0.9209 | 0.9209 | 0.0000 |
| shift | SF | 200 | 18920 | 0.8895 | 0.8871 | -0.0024 |
| shift | SF | 500 | 20184 | 0.8733 | 0.8704 | -0.0029 |
| shift | SF | 1000 | 22840 | 0.8464 | 0.8459 | -0.0005 |

## Boundary utility and censoring

Queries ending at 15 or 16 seconds are separate. A deadline exactly at 16 seconds can
use EOF releases. A later deadline is unobserved and excluded, not counted as a failure.

| Cohort | Stream | Lag (ms) | Observed deadlines | Censored | Answered | Coverage (%) | MAE |
|---|---|---:|---:|---:|---:|---:|---:|
| base | Fixed | 0 | 16384 | 0 | 1920 | 11.7188 | 2.0338 |
| base | Fixed | 200 | 8192 | 8192 | 948 | 11.5723 | 2.0391 |
| base | Fixed | 500 | 8192 | 8192 | 948 | 11.5723 | 2.0391 |
| base | Fixed | 1000 | 8192 | 8192 | 948 | 11.5723 | 2.0391 |
| base | C-TF | 0 | 16384 | 0 | 2139 | 13.0554 | 1.1513 |
| base | C-TF | 200 | 8192 | 8192 | 1044 | 12.7441 | 1.2734 |
| base | C-TF | 500 | 8192 | 8192 | 1332 | 16.2598 | 1.1739 |
| base | C-TF | 1000 | 8192 | 8192 | 1459 | 17.8101 | 1.1409 |
| base | C-SF | 0 | 16384 | 0 | 3789 | 23.1262 | 0.9912 |
| base | C-SF | 200 | 8192 | 8192 | 1937 | 23.6450 | 1.0820 |
| base | C-SF | 500 | 8192 | 8192 | 1937 | 23.6450 | 1.0820 |
| base | C-SF | 1000 | 8192 | 8192 | 1937 | 23.6450 | 1.0820 |
| base | L-TF | 0 | 16384 | 0 | 2161 | 13.1897 | 0.8863 |
| base | L-TF | 200 | 8192 | 8192 | 1507 | 18.3960 | 1.1374 |
| base | L-TF | 500 | 8192 | 8192 | 1507 | 18.3960 | 1.1374 |
| base | L-TF | 1000 | 8192 | 8192 | 1507 | 18.3960 | 1.1374 |
| base | L-SF | 0 | 16384 | 0 | 2989 | 18.2434 | 1.0287 |
| base | L-SF | 200 | 8192 | 8192 | 1366 | 16.6748 | 1.1158 |
| base | L-SF | 500 | 8192 | 8192 | 1427 | 17.4194 | 1.1052 |
| base | L-SF | 1000 | 8192 | 8192 | 1732 | 21.1426 | 1.1046 |
| base | Exact count | 0 | 16384 | 0 | 16384 | 100.0000 | 0.0000 |
| base | Exact count | 200 | 8192 | 8192 | 8192 | 100.0000 | 0.0000 |
| base | Exact count | 500 | 8192 | 8192 | 8192 | 100.0000 | 0.0000 |
| base | Exact count | 1000 | 8192 | 8192 | 8192 | 100.0000 | 0.0000 |
| base | No output | 0 | 16384 | 0 | 0 | 0.0000 | — |
| base | No output | 200 | 8192 | 8192 | 0 | 0.0000 | — |
| base | No output | 500 | 8192 | 8192 | 0 | 0.0000 | — |
| base | No output | 1000 | 8192 | 8192 | 0 | 0.0000 | — |
| shift | Fixed | 0 | 16384 | 0 | 2552 | 15.5762 | 2.4500 |
| shift | Fixed | 200 | 8192 | 8192 | 1248 | 15.2344 | 2.4968 |
| shift | Fixed | 500 | 8192 | 8192 | 1248 | 15.2344 | 2.4968 |
| shift | Fixed | 1000 | 8192 | 8192 | 1248 | 15.2344 | 2.4968 |
| shift | C-TF | 0 | 16384 | 0 | 2492 | 15.2100 | 1.4077 |
| shift | C-TF | 200 | 8192 | 8192 | 1250 | 15.2588 | 1.5534 |
| shift | C-TF | 500 | 8192 | 8192 | 1553 | 18.9575 | 1.6180 |
| shift | C-TF | 1000 | 8192 | 8192 | 1770 | 21.6064 | 1.4972 |
| shift | C-SF | 0 | 16384 | 0 | 4547 | 27.7527 | 1.2334 |
| shift | C-SF | 200 | 8192 | 8192 | 2320 | 28.3203 | 1.4665 |
| shift | C-SF | 500 | 8192 | 8192 | 2320 | 28.3203 | 1.4665 |
| shift | C-SF | 1000 | 8192 | 8192 | 2320 | 28.3203 | 1.4665 |
| shift | L-TF | 0 | 16384 | 0 | 2254 | 13.7573 | 1.1162 |
| shift | L-TF | 200 | 8192 | 8192 | 1486 | 18.1396 | 1.6238 |
| shift | L-TF | 500 | 8192 | 8192 | 1707 | 20.8374 | 1.5200 |
| shift | L-TF | 1000 | 8192 | 8192 | 1707 | 20.8374 | 1.5200 |
| shift | L-SF | 0 | 16384 | 0 | 3215 | 19.6228 | 1.2269 |
| shift | L-SF | 200 | 8192 | 8192 | 1494 | 18.2373 | 1.3800 |
| shift | L-SF | 500 | 8192 | 8192 | 1693 | 20.6665 | 1.4161 |
| shift | L-SF | 1000 | 8192 | 8192 | 2007 | 24.4995 | 1.3545 |
| shift | Exact count | 0 | 16384 | 0 | 16384 | 100.0000 | 0.0000 |
| shift | Exact count | 200 | 8192 | 8192 | 8192 | 100.0000 | 0.0000 |
| shift | Exact count | 500 | 8192 | 8192 | 8192 | 100.0000 | 0.0000 |
| shift | Exact count | 1000 | 8192 | 8192 | 8192 | 100.0000 | 0.0000 |
| shift | No output | 0 | 16384 | 0 | 0 | 0.0000 | — |
| shift | No output | 200 | 8192 | 8192 | 0 | 0.0000 | — |
| shift | No output | 500 | 8192 | 8192 | 0 | 0.0000 | — |
| shift | No output | 1000 | 8192 | 8192 | 0 | 0.0000 | — |
