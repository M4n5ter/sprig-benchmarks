# Writable lease backoff — trace-off same-runner A/B

[Run40186071645](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40186071645), benchmark `cb3248ee750eafdc4e935e0721f364a86d51b325`. Frozen baseline `071036f83691b89bd9e35bb162d34e305e1874b7` then isolated lease-backoff `2c3a7910fe98bf3a8df61f7142cbef740e4ccb2a`, same runner, separate fresh targets and2GiB Btrfs images. No parallel checkpoint or cache-threshold changes. Backoff waits1,2,4,8,16,25ms capped; flock ownership proof and15s deadline remain unchanged. Trace is disabled in both binaries/samples; earlier trace-on diagnostic timings are not pooled.

The frozen `history-hot-100` fixture contains256×4KiB files and100deterministic64-byte hot edits. Every checkpoint and every historical restore receives the unchanged complete-tree oracle. Both exact binaries first pass writable full-tree canaries, Rust tests and real kernel gates. No mutable writers overlap checkpoint; public normal unmount is retained.

| Metric | Baseline | Backoff |
|---|---:|---:|
| Whole sampler wall, s | 49.5023 | 44.0699 |
| Init, s | 0.0104 | 0.0111 |
| Import, s | 0.0462 | 0.0458 |
| First Fork, s | 0.0689 | 0.0374 |
| First Read, s | 0.1613 | 0.1747 |
| Warm Fork, s | 0.0589 | 0.0390 |
| Warm Read, s | 0.1739 | 0.1634 |
| Write, s | 0.5495 | 0.5434 |
| Checkpoint, s | 5.9962 | 3.7352 |
| Restore, s | 2.1772 | 2.0893 |
| Restore Read, s | 17.2382 | 17.0235 |
| Restore Cleanup, s | 3.9268 | 1.6644 |
| activeSpace wholeFSUsed, bytes | 11,276,288 | 11,345,920 |
| postHistorySpace wholeFSUsed, bytes | 19,103,744 | 19,132,416 |

Whole wall is10.97%lower, checkpoints37.71%lower and normal restore cleanup57.61%lower. These are measured complete operations, not trace-time subtraction. Restore/read totals are similar. Small primary/post-history space increases remain reported; this is not a space optimization. First reads are slightly slower. Whole sampler wall includes all verification/accounting/normal cleanup/evidence serialization; phase timers are not substituted for it or double-counted.

| Dependent operation latency, ms | Baseline median / p95 / p99 / max | Backoff median / p95 / p99 / max |
|---|---:|---:|
| checkpoint_seconds | 59.677 / 65.569 / 80.638 / 84.856 | 37.448 / 40.173 / 49.143 / 87.637 |
| restore_seconds | 21.118 / 23.524 / 40.706 / 42.996 | 20.038 / 23.535 / 34.850 / 39.526 |
| restore_read_seconds | 172.206 / 186.189 / 208.488 / 210.717 | 168.701 / 182.886 / 210.855 / 242.252 |
| restore_cleanup_seconds | 38.970 / 40.353 / 43.454 / 48.368 | 14.693 / 17.639 / 66.229 / 72.313 |
| write_seconds | 5.385 / 6.253 / 6.742 / 10.686 | 5.358 / 6.116 / 6.544 / 6.727 |

**Negative tails are not hidden:** cleanup p99 rises43.454→66.229ms and maximum48.368→72.313ms; checkpoint maximum84.856→87.637ms. Lower medians/total do not establish a universal tail improvement. Each100-operation series is dependent within one runner pair, not100independent trials; descriptive nearest-rank p95/p99 are not confidence intervals. One forward pair alone is not an unconditional promotion recommendation.

## Correctness, lifecycle and space

Canaries contribute30full-tree checks/8historical restores; pressure414checks/200restores. All884archived log byte/hash checks pass. Source/main/second content invariants and complete history are checked. Metadata scope is paths/content/0777 modes/nanosecond mtime/symlinks/internal hardlink groups, not UID/GID/ACL/xattrs. Canaries exercise links.

Each product retains103writable generations at primary space and203after100historical restores, exactly3+100+100. The three live views are independently checked; every old/restored generation remains retained and charged, normal unmount only, no force/lazy unmount, no killed daemon, zero mounts/owned servers after normal final cleanup. The ownership/lease proof was not replaced by a sleep estimate. Primary and post-history wholeFSUsed charge complete product/runtime state, not just referenced files; no pruning or selective cleanup.

Sequence97.277seconds within one shared1,200second ceiling; full job4m35s under45minutes. No CPU/memory savings were measured. Frozen binaries: baseline `086801ac765401f9fcd3116bbdf48c72118fd9f7682affd0057121756d2c7b12`, backoff `e9393f24b30f5afaf75aa3e417e165aca20b97bbc3fe842fbcf0f40e8feb28ee`. Config/binary hashes are checked before both phases and matched to measured proofs. Raw evidence and provenance: `data/stress-20261025/writable-backoff100` and matching manifest.
