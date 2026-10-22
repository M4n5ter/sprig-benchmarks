# Native Btrfs feasibility results

**The target is not met.** The experimental native backend makes warm fork + verified reads faster in all seven cases, but initialization + import + fork + verified read is slower in all seven, and 100-checkpoint workloads are substantially slower. It also lacks production merge, reopen/recovery, SDK and other basic features. This is not a replacement release of Sprig.

[Successful fixed run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39773279359), harness `3d6d22a38a4887228e383a7f0ef1ad9b80f4da7f`; native prototype SHA256 `5b24d3da02428c36b8248ff32729b3a47018bb018f790e32e78c6a459c3acd9e`; LayerFS `2aaf2552ce21154928b9f9c83582e41a637f5910`. Each median is three samples on the same AMD EPYC 7763 GitHub runner. These are observed medians, not statistical significance claims; small differences may be noise. All 42 required records passed, including 1,800 complete historical snapshot checksum readbacks and normal runtime restoration/unmount cleanup.

[Complete measurement boundaries](feasibility/MEASUREMENT-BOUNDARIES.md) are part of these results. Each sample uses a new Btrfs filesystem, data SINGLE, metadata DUP, no compression. Both products use the frozen fixtures. LayerFS uses supported classic overlay2 with Btrfs backing and ordinary local volumes; its Docker and containerd persistent roots, SDK home, writable layers, overlays and logs are inside the measured filesystem. No target validation was modified.

## Timing medians

Milliseconds. These are **defined phase sums**, not full software deployment/startup wall time. Native uses Python in-process snapshot APIs; LayerFS uses its in-process SDK. Shell versus Docker-exec transport differs. Native publication has fsync/synchronous snapshots, while LayerFS Disposable uses synchronous OFF. No equal-durability or kernel-only speed conclusion is claimed. First read is not proven cold cache.

| Case | Native init + import + fork + read | LayerFS same phase sum | Native warm fork + read | LayerFS warm fork + read |
|---|---:|---:|---:|---:|
| identical | 827.5 | 588.6 | 120.4 | 208.9 |
| unique | 2090.7 | 2025.3 | 123.5 | 711.8 |
| mixed | 1849.6 | 1634.2 | 125.6 | 591.9 |
| insert | 900.5 | 664.4 | 128.0 | 212.9 |
| history-distributed | 502.7 | 460.2 | 18.2 | 79.6 |
| history-hotset | 503.7 | 467.8 | 18.0 | 81.2 |
| history-recurring | 501.9 | 463.1 | 19.0 | 79.2 |

Warm fork + read is about 1.7–5.8× faster for this native prototype, but most of that task is the verified file read; consult raw fork/read components rather than treating it as metadata-only fork speed.

### 100-step history tasks

Seconds. Same dd write + fsync followed by mtime restoration; final mtime durability is not established by the preceding fsync.

| Case | Native write + checkpoint | LayerFS write + checkpoint | Native checkpoint only | LayerFS checkpoint only |
|---|---:|---:|---:|---:|
| history-distributed | 9.290 | 2.650 | 8.787 | 0.508 |
| history-hotset | 9.475 | 2.789 | 8.970 | 0.594 |
| history-recurring | 9.756 | 3.135 | 8.787 | 0.334 |

## Physical storage medians

MiB = 1,048,576 bytes. Native is final whole-filesystem Used minus empty. LayerFS is shown both as final minus empty and final minus runtime-ready (fixed base image already loaded). The latter still includes product-triggered engine metadata and uploaded daemon software. **These are not exact application-data-only bytes and do not establish a data-only storage winner.** Host journal, installed shared software and volatile /run state are outside the metric. Filesystem metadata and sharing are counted by Btrfs, not by summing per-file du.

| Case | Native filesystem growth | LayerFS whole deployment growth | LayerFS growth after runtime-ready |
|---|---:|---:|---:|
| identical | 1.312 | 94.992 | 13.062 |
| unique | 100.500 | 195.355 | 113.430 |
| mixed | 75.500 | 169.988 | 88.055 |
| insert | 101.984 | 98.438 | 16.633 |
| history-distributed | 9.188 | 99.156 | 17.258 |
| history-hotset | 9.469 | 99.199 | 17.270 |
| history-recurring | 8.734 | 98.793 | 16.770 |

The insertion case is a clear warning: the native ioctl counter reports 104,448,000 bytes compared/shared in every sample, yet its actual filesystem growth remains about 102 MiB and exceeds even LayerFS's whole deployment growth. Successful range-sharing counters are not physical bytes saved. A plausible explanation is partial-extent retention: Btrfs can keep a whole allocation while smaller file ranges still reference it, as described in its [developer documentation](https://github.com/btrfs/btrfs-dev-docs/blob/master/data-extent-reference-counts.md). That is an inference consistent with these counters, not an extent-tree proof from this run. This recipe inserts 4 KiB, so it also does not demonstrate general arbitrary-offset CDC behavior.

Native filesystem snapshots remain after its process exits, but its RAM-only dedup index does not; LayerFS is sampled with SDK/container/workspaces alive. This is not matched live control-service or RAM lifecycle. Native index/RSS observations are in raw records; LayerFS total RAM/background compute was not comparably profiled. No RAM or overall CPU advantage is claimed.

## Reproduction and raw evidence

Dispatch `btrfs-feasibility.yml` with mode `full` at the pinned harness, after its tiny paired smoke. The successful smoke was [39772593953](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39772593953). Earlier runs 39770944292 and 39771893796 were diagnostic harness failures (stderr/TOML parsing, then transient service-start counters), not product performance results.

[Raw measurements, environment, image identity and script hashes](measurements/2026-10-22-btrfs-prototype/) are retained unchanged. [Summary JSON](measurements/2026-10-22-btrfs-prototype/btrfs-summary.json) and [CSV](measurements/2026-10-22-btrfs-prototype/btrfs-summary.csv) are generated by `python3 feasibility/summarize_btrfs.py measurements/2026-10-22-btrfs-prototype/btrfs-comparison.json`. The summarizer checks the exact expected case/product/repetition set and history readbacks.

Original production ext4 reports remain separate; their earlier storage-boundary correction still applies. This experiment does not repair those old measurements or show cross-filesystem causal speedups.
