# Native10k own-version A/B — first forward pilot

25October2026. [Run40182320969](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40182320969), benchmark `0a625c3bf3e0ecf685f20f0983d95abb0e67a33b`. Same runner, baseline `071036f83691b89bd9e35bb162d34e305e1874b7` followed by narrowed integrated candidate `1bd8793eda1be01dfe35b22abe00c14e5fff4fc9`. Candidate contains query/checkpoint work, not the unproven backup-byte tweak. Trace disabled; default auto compression and production synchronization unchanged.

**No meaningful whole-task gain in this single pilot; checkpoint time was higher.** This is descriptive evidence, not proof of a general regression or a statistically significant result. A reverse-order pair is required before deciding about the parallel default.

| Metric | Baseline | Candidate |
|---|---:|---:|
| Whole sampler wall, s | 52.3861 | 52.3129 |
| Init, s | 0.0113 | 0.0125 |
| Import, s | 10.7589 | 10.8053 |
| First usable fork, s | 7.1409 | 7.0742 |
| First full read, s | 1.1137 | 1.1696 |
| Warm usable fork, s | 7.1891 | 7.1746 |
| Warm full read, s | 1.1424 | 1.1482 |
| Changed write+fsync, s | 0.0051 | 0.0050 |
| No-op checkpoint+readiness, s | 0.5680 | 0.6398 |
| Changed checkpoint+readiness, s | 0.6198 | 0.6652 |
| Both checkpoints, s | 1.1878 | 1.3050 |
| Two public restores, s | 19.1984 | 19.0175 |
| Restored full reads, s | 0.8350 | 0.8246 |
| Primary wholeFSUsed, bytes | 127,991,808 | 127,954,944 |
| Post-history wholeFSUsed, bytes | 242,397,184 | 242,331,648 |

Candidate whole wall is0.14%lower, while checkpoint sum is9.87%higher (changed7.33%, no-op12.64%). The tiny36KiB/64KiB space differences are not a storage victory. Import/forks/restores account for approximately44seconds of52seconds, versus about1.2seconds for checkpoints; native materialization dominates this workload. Native restore cleanup is0seconds because trees are retained, not deleted/unmounted. Whole wall includes all oracle/ledger/space/archive/normal teardown work; phase totals are diagnostic and are not substituted for the whole task or added twice.

## Correctness and measurement controls

- 10,000unique4KiB files in one wide directory; deterministic64-byte edit; one no-op checkpoint and one changed checkpoint; fresh2GiB Btrfs image per product.
- Both records pass22total complete-tree checks and4historical readbacks; exact path/content/0777-mode/mtime/internal-hardlink/symlink oracle and unchanged source/main/second assertions remain enabled. Full changed-history order/parents are verified. This particular wide-file fixture has no symlink/hardlink groups larger than1; those are exercised by prerequisite canaries.
- Three views stay live at primary space; both restored native trees remain at post-history. All application state, retained trees and harness/runtime logs are charged. No pruning, selective cleanup, cache dropping or coldOS-cache claim.
- All24archived oracle/lifecycle log files verified by bytes/SHA256. Zero trace, zero remaining mounts/owned servers, and normal cleanup complete.
- Separate fresh target roots and copied immutable binaries prevent stale cross-worktree Cargo reuse. Both variants' Rust tests and real projection/writable gates passed. Compiler/source/binary identities and verbose compile logs remain preserved. Binary hashes: baseline `086801ac765401f9fcd3116bbdf48c72118fd9f7682affd0057121756d2c7b12`; candidate `d904aa3c114af19d9719183c8100eb690281aad3165f2bfed4787ae2e71a00bd`.
- This real Btrfs4KiB/64-byte-edit complete-task experiment is not pooled with local microbenchmarks using different file sizes, edit lengths, filesystem, timing scope or builds. It is not a LayerFS comparison.
- One order/pair cannot establish stable tails or confidence. No p95/p99 is claimed from two checkpoints, and no main promotion follows from this result.

[Complete unchanged forward artifact](data/stress-20261025/native10k-forward/) · [Independent verification](data/stress-20261025/native10k-forward/verified.json) · [Every-file provenance](data/stress-20261025/native10k-forward-provenance.json).
