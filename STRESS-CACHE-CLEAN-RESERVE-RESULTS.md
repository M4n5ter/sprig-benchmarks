# Clean-reserve cache experiment — no demonstrated material benefit

[Run40199207356](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40199207356), benchmark `3c918de468baafd614af4544ef7f9c9f41b1cd74`, passed in10m15s. This isolates admission `cd46df767abaecac2948eebaa46ac9ff5c0885c9` versus clean-reserve `382564b39806b3b1015107b5a40866946d82512b`: only already-reviewed redundant cache reservation barriers are removed; authoritative deletion/publication/durability barriers remain. It does not compare inventory-only or main against the combined cache policy.

**No material cold-fit restore benefit was demonstrated; prior cold-fit regression remains unresolved and default promotion is not justified.** History wholewall91.352134→91.170070s (−0.20%); unique10k52.522462→53.958364s (+2.73%); cold4096whole29.846132→29.414390s (−1.45%) but restore14.859957→14.921259s (+0.41%). First cold-fit restore11.474987→11.544458s also worsens. These small mixed changes from one forward pair do not establish a general gain or regression.

Same runner, separate fresh build targets and binary hashes, native canaries then all three controls under one1200s budget (actual355.953954s). Fresh2GiB filesystems per sample, all retained views/history/runtime charged; no selective pruning or OS-cache eviction. “Cold” means empty product cache, not cold OS caches. Independent audit matches38source hashes for each exact pin and distinct binary hashes across all eight samples. All1288full-tree checks,616historical readbacks and1296archived log hashes pass; normal cleanup and source/main/second invariance preserved. Full immutable raw and source/build identity evidence: `data/stress-20261025/cache-clean-reserve-controls`.

### history300

| Metric / 指标 (seconds / 秒) | Admission cd46 | Clean-reserve382 |
|---|---:|---:|
| Whole sampler / 完整采样 | 91.352134 | 91.170070 |
| Init / 初始化 | 0.011647 | 0.014511 |
| Import / 导入 | 0.261601 | 0.281876 |
| First fork / 首次分叉 | 0.237357 | 0.235244 |
| First read / 首次读取 | 0.046649 | 0.047770 |
| Warm fork / 再次分叉 | 0.236679 | 0.241311 |
| Warm read / 再次读取 | 0.048951 | 0.048867 |
| Write / 写入 | 1.403535 | 1.401536 |
| Checkpoint / 检查点 | 7.644281 | 7.606864 |
| Restore / 恢复 | 52.318559 | 52.195696 |
| Restored read / 恢复后读取 | 14.685895 | 14.634300 |
| Restore cleanup / 恢复清理 | 0.000000 | 0.000000 |
| Primary whole Used / 主阶段全盘Used (bytes / 字节) | 20,905,984 | 20,807,680 |
| Post-history whole Used / 历史后全盘Used (bytes / 字节) | 230,875,136 | 230,416,384 |

### unique10k

| Metric / 指标 (seconds / 秒) | Admission cd46 | Clean-reserve382 |
|---|---:|---:|
| Whole sampler / 完整采样 | 52.522462 | 53.958364 |
| Init / 初始化 | 0.014545 | 0.013862 |
| Import / 导入 | 10.771842 | 11.201324 |
| First fork / 首次分叉 | 7.042932 | 7.097565 |
| First read / 首次读取 | 1.194064 | 1.122007 |
| Warm fork / 再次分叉 | 7.097156 | 7.261023 |
| Warm read / 再次读取 | 1.174307 | 1.164005 |
| Write / 写入 | 0.005248 | 0.005220 |
| Checkpoint / 检查点 | 1.153369 | 1.154046 |
| Restore / 恢复 | 19.419386 | 20.261565 |
| Restored read / 恢复后读取 | 0.838718 | 0.843158 |
| Restore cleanup / 恢复清理 | 0.000000 | 0.000000 |
| Primary whole Used / 主阶段全盘Used (bytes / 字节) | 127,889,408 | 127,860,736 |
| Post-history whole Used / 历史后全盘Used (bytes / 字节) | 242,266,112 | 242,233,344 |

### cold4096

| Metric / 指标 (seconds / 秒) | Admission cd46 | Clean-reserve382 |
|---|---:|---:|
| Whole sampler / 完整采样 | 29.846132 | 29.414390 |
| Init / 初始化 | 0.013425 | 0.015155 |
| Import / 导入 | 4.821266 | 4.632464 |
| First fork / 首次分叉 | 2.990552 | 2.963969 |
| First read / 首次读取 | 0.489834 | 0.484952 |
| Warm fork / 再次分叉 | 3.160421 | 2.895980 |
| Warm read / 再次读取 | 0.510717 | 0.516081 |
| Write / 写入 | 0.005109 | 0.005121 |
| Checkpoint / 检查点 | 0.480489 | 0.481705 |
| Restore / 恢复 | 14.859957 | 14.921259 |
| Restored read / 恢复后读取 | 0.718119 | 0.690236 |
| Restore cleanup / 恢复清理 | 0.000000 | 0.000000 |
| Primary whole Used / 主阶段全盘Used (bytes / 字节) | 52,662,272 | 52,695,040 |
| Post-history whole Used / 历史后全盘Used (bytes / 字节) | 88,236,032 | 88,100,864 |

## Tails and interpretation

History300 restore p95/p99:248.070/260.055→242.067/254.313ms, but maximum448.251→458.603ms worsens. Checkpoint p95/p99:29.789/35.765→29.624/30.981ms; median24.556→24.920ms worsens. These are descriptive dependent operations, not300independent trials. The two-restore file-count controls have no meaningfulp95/p99 estimate.

Whole filesystem Used is physical accounting including retained state; referenced allocation is not unique physical storage. Small byte differences do not justify a storage-win claim. The unique10k negative control admits no small-file population in either variant: its+2.73%whole/+4.34%restore cannot be attributed to the removed reservation barrier and illustrates run-level variation. No syscall trace was collected, so timings cannot attribute exact fsync savings. The causal next inference is that removing these clean reservation barriers alone does not address the dominant first-fill work. Keep small-file admission experimental; a new experiment requires a concrete new hypothesis and review, not automatic repeats or fixture-specific cutoffs. Earlier inventory/admission and naive-threshold negatives remain separate and unchanged. No cache main merge is implied.
