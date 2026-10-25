# Capacity-aware cache admission — all three controls

[Run40189754782](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40189754782), benchmark `561079b1f3281974dcadff9326991e7fa597939a`. Same runner and fixed binary identities across native canaries and three controls: inventory-only `8558b130323d904ae8eaec822d502f52459c5b79` versus capacity-aware small-file admission `cd46df767abaecac2948eebaa46ac9ff5c0885c9`. Separate fresh2GiB images per product/cell, all prior images retained, no OS-cache eviction. Product stores start empty; source trees were read during setup.

**The over-capacity10k cliff is removed, but the under-capacity4096 first-restore cost remains material. This does not justify enabling small-file admission by default.** Capacity-fit is not proof of future reuse. Earlier naive-threshold results remain separately recorded, not pooled with this different implementation.

## Targeted repeated small-file history300

| Metric | Inventory only | Admission guard |
|---|---:|---:|
| Whole sampler wall, s | 105.5222 | 96.6263 |
| Init, s | 0.0165 | 0.0193 |
| Import, s | 0.4130 | 0.4167 |
| First Fork, s | 0.3493 | 0.3610 |
| First Read, s | 0.0353 | 0.0342 |
| Warm Fork, s | 0.3604 | 0.3478 |
| Warm Read, s | 0.0365 | 0.0348 |
| Write, s | 1.3607 | 1.2406 |
| Checkpoint, s | 6.1927 | 5.8744 |
| Restore, s | 76.5268 | 67.1568 |
| Restore Read, s | 9.4083 | 11.0020 |
| Restore Cleanup, s | 0.0000 | 0.0000 |
| activeSpace wholeFSUsed, bytes | 20,643,840 | 20,709,376 |
| postHistorySpace wholeFSUsed, bytes | 499,093,504 | 223,092,736 |

Whole task is8.43%lower and retained post-history wholeFSUsed55.30%lower, but restored full reads are16.94%slower. Initial restore0.2386→0.6035s is slower, showing admission cost even in the favorable repeated history.

| Dependent latency, ms | Inventory median / p95 / p99 | Admission median / p95 / p99 |
|---|---:|---:|
| checkpoint_seconds | 19.028 / 26.891 / 30.203 | 17.774 / 27.729 / 32.433 |
| restore_seconds | 247.195 / 363.910 / 406.829 | 211.515 / 369.663 / 388.698 |
| restore_read_seconds | 31.351 / 32.904 / 33.790 | 36.652 / 38.504 / 39.180 |
## Over-capacity unique10k

| Metric | Inventory only | Admission guard |
|---|---:|---:|
| Whole sampler wall, s | 62.3220 | 62.7910 |
| Init, s | 0.0181 | 0.0177 |
| Import, s | 13.9761 | 13.7177 |
| First Fork, s | 8.7801 | 8.9658 |
| First Read, s | 0.6816 | 0.6582 |
| Warm Fork, s | 9.1979 | 9.2019 |
| Warm Read, s | 0.6453 | 0.6828 |
| Write, s | 0.0052 | 0.0048 |
| Checkpoint, s | 0.6103 | 0.5718 |
| Restore, s | 25.5916 | 26.1396 |
| Restore Read, s | 0.4454 | 0.4545 |
| Restore Cleanup, s | 0.0000 | 0.0000 |
| activeSpace wholeFSUsed, bytes | 127,725,568 | 127,725,568 |
| postHistorySpace wholeFSUsed, bytes | 242,429,952 | 241,905,664 |

Whole task+0.75%, restores+2.14%, primary space equal and post-history space−0.22%. No material advantage is established, but the earlier naive-threshold2.21×whole-task cliff does not recur. This is a new matched pair, not a cross-run ratio against the older threshold experiment.
## Cold product-cache4096 control

| Metric | Inventory only | Admission guard |
|---|---:|---:|
| Whole sampler wall, s | 26.2808 | 33.3979 |
| Init, s | 0.0192 | 0.0175 |
| Import, s | 6.1674 | 6.3414 |
| First Fork, s | 3.7831 | 3.4365 |
| First Read, s | 0.2967 | 0.3007 |
| Warm Fork, s | 3.7571 | 3.4009 |
| Warm Read, s | 0.2790 | 0.3104 |
| Write, s | 0.0044 | 0.0047 |
| Checkpoint, s | 0.2553 | 0.2602 |
| Restore, s | 10.2996 | 17.6783 |
| Restore Read, s | 0.2276 | 0.4283 |
| Restore Cleanup, s | 0.0000 | 0.0000 |
| activeSpace wholeFSUsed, bytes | 52,891,648 | 52,895,744 |
| postHistorySpace wholeFSUsed, bytes | 99,893,248 | 88,666,112 |

Whole task+27.08%, restores+71.64% for only11.24%lower post-history wholeFSUsed. First restore5.1151→13.4484s; second5.1844→4.2299s. The later hit benefit does not erase the initial admission expense in this full task.4096files fit the entry cap per snapshot; the changed revision adds another key across the history union. Only two restores are observed here: no p95/p99 claim.

## Controls, accounting and limits

All1,288complete-tree checks,616historical readbacks and1,296archived log byte/hash verifications pass. Both exact binaries/configs are frozen and checked before every phase, and matched to measured source/backend/binary proofs afterward. No failed control is omitted. Every product uses normal cleanup with zero remaining mounts/owned servers; all original and historical native trees are retained and charged. Full paths/content/0777 modes/nanosecond mtime/internal links/symlinks scope is unchanged; canaries cover link restoration, no UID/GID/ACL/xattr claim.

The repeated-history fixture is128×1KiB+64×8KiB+8×48KiB, six hot files and300deterministic64-byte edits. Unique controls are10,000or4,096distinct4KiB files, each with one no-op and one64-byte changed checkpoint plus two public restores. Existing recipes are unchanged.

Physical wholeFSUsed includes product state, cache, runtime/logs and all retained views; it is not referenced allocation counted as unique extents. Primary space, post-history space and negative read phases remain visible. No selective deletion, filesystem resizing or hidden warm-cache reuse. Whole wall is authoritative and includes correctness/accounting/normal cleanup; nested phase timers are not substituted or double-counted. No memory/CPU savings measured.

One shared1,200second deadline covers canaries and all three cells; actual392.888seconds, full job10m25s under45minutes. This is one forward pair per cell in one runner group, not a broad workload survey or independent per-operation replication. Descriptive dependent-operation tails do not establish confidence or universal latency guarantees. These results support retaining small-file admission as experimental pending a principled reuse/admission design, not tuning a fixture-specific first-N cutoff.

Raw complete records, source/compile identities and provenance: `data/stress-20261025/cache-admission-controls` and matching manifest.
