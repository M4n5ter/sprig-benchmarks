# Targeted small-file cache threshold experiment

[History300 run40184672530](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40184672530), benchmark `05509976b7e93906b35902fd963e50ef66c821a7`. Same runner, inventory-only `8558b130323d904ae8eaec822d502f52459c5b79` then threshold `9f83c4aec3205b4eb067ca2a367dd7a0b52f49c9`. The runtime difference is cache admission64KiB→1KiB; latter portability changes affect tests only. This does **not** compare main071 to the combined cache implementation.

The new targeted fixture has128×1KiB,64×8KiB,8×48KiB files (1MiB total), with300 deterministic64-byte edits cycling six hot files. Full file states recur every12edits, each edit changes content. It intentionally targets repeated small-file history, not representative arbitrary histories. Fresh product stores/images; no OS-cache eviction claim.

## Targeted history result

| Metric | Inventory only | Lower threshold |
|---|---:|---:|
| Whole sampler wall, s | 106.5154 | 90.8771 |
| Init, s | 0.0111 | 0.0105 |
| Import, s | 0.6726 | 0.2651 |
| First Fork, s | 0.2017 | 0.1914 |
| First Read, s | 0.0400 | 0.0401 |
| Warm Fork, s | 0.2543 | 0.2095 |
| Warm Read, s | 0.0397 | 0.0403 |
| Write, s | 2.9919 | 1.9848 |
| Checkpoint, s | 10.0591 | 7.8590 |
| Restore, s | 69.5162 | 56.3652 |
| Restore Read, s | 10.6322 | 11.7348 |
| Restore Cleanup, s | 0.0000 | 0.0000 |
| activeSpace wholeFSUsed, bytes | 20,676,608 | 20,807,680 |
| postHistorySpace wholeFSUsed, bytes | 504,397,824 | 232,161,280 |

Whole task is14.68%lower; restore total18.92%lower; checkpoint total21.87%lower. **Full restored reads are10.37%slower**, and primary space is131,072bytes higher. Post-history wholeFSUsed is53.97%lower while all300 restored native trees remain retained. This is physical whole-filesystem accounting, not a sum of referenced logical allocations; shared extents are not charged repeatedly as unique storage. All product state, cache, views and runtime/log files inside the measured filesystem remain charged. No pruning, selective cleanup or discarded unfavorable phases.

| Dependent operation latency, ms | Inventory median / p95 / p99 | Threshold median / p95 / p99 |
|---|---:|---:|
| checkpoint_seconds | 22.443 / 87.019 / 155.219 | 21.997 / 49.680 / 88.520 |
| restore_seconds | 184.944 / 467.422 / 797.571 | 154.775 / 415.399 / 577.546 |
| restore_read_seconds | 35.263 / 36.686 / 40.271 | 38.844 / 40.847 / 41.617 |
| write_seconds | 4.268 / 62.000 / 88.007 | 4.309 / 11.874 / 70.748 |

Checkpoint early/middle/late100-operation medians in milliseconds: inventory 24.329, 21.622, 21.621; threshold 23.288, 21.180, 21.311. These are descriptive dependent operation distributions, not300independent experiments or statistical confidence intervals. One forward runner pair cannot establish robustness against order/host variability.

## Acceptance and boundaries

- Both exact binaries first passed Rust tests, real projection/writable gates and native full-tree canaries:30checks,8historical restores. Pressure adds1,214full-tree checks and600historical restores. All1,248archived log files pass offline byte/hash validation, all normal cleanups complete, trace disabled.
- Binary/config identity is frozen before the sequence, checked before each phase, and compared to measured canary/pressure proofs. Fresh separate Cargo targets avoid stale-source reuse. Inventory binary `b16c2e2527d2e06f34f4c5af67f80ed5e8ac04532cec73e768971568e92a01e6`; threshold binary `882afd27c94a41831ac4004a49e49b3117425960de981708f5026d827ff586df`.
- Complete path/content/0777-mode/mtime/internal-hardlink/symlink oracle is unchanged. Source/main/second isolation and complete history remain checked. No uid/gid/ACL/xattr claim. Hardlink/symlink restoration is exercised in canaries, not this uniform ordinary-file pressure case.
- Same2GiB Btrfs image size, same compiler/harness/timing, sequential products. Shared canary+pressure budget1,200seconds; actual sequence202.331seconds. Full job6m49s within45minutes. Worst-case conservative retained logical estimate603MiB is a capacity guard, not measured physical consumption.
- Whole sampler wall includes verification/accounting/evidence/cleanup. Nested timers are not summed into a substitute total; native cleanup0 means retained trees, not deletion. No memory/CPU comparison was measured.
- **The mandatory cold unique10k negative pair is documented below and rejects default threshold promotion.** This favorable targeted history alone is insufficient. Raw bytes and provenance: `data/stress-20261025/cache-history300` and `cache-history300-provenance.json`.

## Mandatory cold-product-cache unique10k negative pair

[Run40185373610](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40185373610), benchmark `644672e3f4fbc8a4d67169074af2cc4c8fa9a879`. Same exact source/binary hashes as the history pair (enforced during rebuild), fresh stores and2GiB images, one forward inventory→threshold pair on one runner. Existing `files-10000` recipe:10,000unique4KiB files, one no-op and one64-byte changed checkpoint, two public restores. “Cold” means initially empty product cache, not evicted OS caches. Both same-binary native canaries run first.

| Metric | Inventory only | Lower threshold |
|---|---:|---:|
| Whole sampler wall, s | 38.6436 | 85.3626 |
| Init, s | 0.0091 | 0.0098 |
| Import, s | 8.4671 | 7.9665 |
| First Fork, s | 5.2291 | 5.0726 |
| First Read, s | 0.5537 | 0.5376 |
| Warm Fork, s | 5.1825 | 5.1271 |
| Warm Read, s | 0.5555 | 0.5402 |
| Write, s | 0.0041 | 0.0043 |
| Checkpoint, s | 0.8869 | 0.8852 |
| Restore, s | 14.7090 | 62.0342 |
| Restore Read, s | 0.5492 | 0.6514 |
| Restore Cleanup, s | 0.0000 | 0.0000 |
| activeSpace wholeFSUsed, bytes | 127,758,336 | 127,856,640 |
| postHistorySpace wholeFSUsed, bytes | 242,167,808 | 234,352,640 |

**Do not promote the1KiB default from these results.** The negative workload takes2.21×whole task (+120.90%) and4.22×restore time (+321.74%), for only3.23%lower post-history wholeFSUsed. Checkpoint time is essentially unchanged; restored reads are slower. The favorable repeated-history result does not override this negative. Cache-capacity/admission diagnosis is a separate engineering question, not permission to tune a fixture-specific first-N cutoff.

All30canary checks/8restores plus22pressure checks/4restores pass;56archived log hashes verified, normal cleanup complete, trace disabled. Same-binary sequence127.683seconds, full job4m54s. Each case is one forward pair with dependent operations, not statistical confidence or cross-run absolute comparison. Raw complete evidence: `data/stress-20261025/cache-unique10k` with provenance manifest. Both favorable and unfavorable results remain preserved.
