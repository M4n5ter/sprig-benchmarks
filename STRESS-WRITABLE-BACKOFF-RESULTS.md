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

## Reverse-order confirmation

[Run40186608442](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40186608442), benchmark `fcc7839a7bd64067329044777c5c1357938c0188`, runs backoff before baseline on another runner. Exact forward binary hashes and fixture hash are enforced by workflow assertions, not assumed from paths. Protocol/fixture/source pins unchanged.

| Metric | Baseline | Backoff |
|---|---:|---:|
| Whole sampler wall, s | 80.9162 | 65.8386 |
| Init, s | 0.0343 | 0.0109 |
| Import, s | 0.2500 | 0.0494 |
| First Fork, s | 0.1578 | 0.0423 |
| First Read, s | 0.1845 | 0.1830 |
| Warm Fork, s | 0.1418 | 0.0401 |
| Warm Read, s | 0.1936 | 0.1798 |
| Write, s | 2.9622 | 3.6679 |
| Checkpoint, s | 15.0168 | 10.1271 |
| Restore, s | 9.6741 | 5.2271 |
| Restore Read, s | 18.6867 | 18.8282 |
| Restore Cleanup, s | 11.8562 | 6.0205 |
| activeSpace wholeFSUsed, bytes | 11,284,480 | 11,284,480 |
| postHistorySpace wholeFSUsed, bytes | 19,046,400 | 19,152,896 |

Whole wall is18.63%lower, checkpoint total32.56%lower and normal restore cleanup49.22%lower. Both orders favor backoff for these aggregate measures. **The reverse runner is substantially noisier**, with large write/fsync/restore outliers affecting both binaries. Do not attribute every observed difference to lease waits or compare cross-run absolute times. Writes are23.82%slower and restored reads0.76%slower for the candidate in this pair; post-history space is106,496bytes higher.

| Dependent operation latency, ms | Baseline median / p95 / p99 / max | Backoff median / p95 / p99 / max |
|---|---:|---:|
| checkpoint_seconds | 74.721 / 428.286 / 625.732 / 886.702 | 52.672 / 348.258 / 694.170 / 697.628 |
| restore_seconds | 31.124 / 271.695 / 545.126 / 630.400 | 25.430 / 189.763 / 305.409 / 359.969 |
| restore_read_seconds | 184.864 / 200.765 / 204.460 / 219.302 | 187.021 / 200.146 / 220.338 / 224.254 |
| restore_cleanup_seconds | 64.133 / 343.977 / 551.519 / 1059.013 | 24.018 / 200.370 / 327.771 / 914.133 |
| write_seconds | 6.774 / 131.753 / 193.630 / 234.258 | 7.222 / 150.916 / 259.786 / 317.315 |

Checkpoint p99 is worse625.732→694.170ms despite lower median74.721→52.672ms. Other tail directions differ from the first runner; neither pair supports a universal tail-latency guarantee. Two matched runner groups remain limited evidence, not200independent replications per variant.

Again444full-tree checks/208historical restores and884archived log hashes pass;103primary/203post-history generations retained per product, normal cleanup complete, trace disabled. Sequence152.776seconds; full job6m45s. Raw reverse evidence and provenance are retained in `data/stress-20261025/writable-backoff-reverse`. This confirms the aggregate fixed-wait hypothesis in both tested orders while preserving the adverse tails and unrelated phase variation.

## Unplanned staging duplicate — disclosed, not pooled

[Run40188441092](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40188441092), head `6de63cfb2cefd620a92aa4b22489e52e7c03c475`, unexpectedly ran the unchanged reverse backoff workflow during helper/report staging. Skip-marked ancestor commits did not suppress this push; future staging must use an explicit inactive route or verified HEAD skip behavior. The run finished naturally in5m26s; it is **unplanned and excluded from the two planned-pair summaries**, not silently selected or discarded. Full raw/provenance remain in `data/stress-20261025/writable-backoff-unplanned`. All444treechecks/208restores/884loghashes and exactbinary/fixture gates pass.

- baseline: whole54.1197s; checkpoint6.4820s; normal restore cleanup4.1690s; primary/post wholeFSUsed11,350,016/19,152,896bytes.
- backoff: whole49.9473s; checkpoint4.3940s; normal restore cleanup1.8837s; primary/post wholeFSUsed11,210,752/19,017,728bytes.
