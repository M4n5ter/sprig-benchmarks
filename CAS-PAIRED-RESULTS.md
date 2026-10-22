# CAS/Overlay paired results

**The speed + storage + basic-capability goal is not met.** This experimental adapter improves warm writable-view-plus-read timings in these seven cases, but 100-edit history tasks remain about 4.5–5 times slower. It is not production Sprig or feature parity.

[Run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39796510425), frozen harness `1d97820424d9661bc87259f4d64203240488ea38`, production content-library dependency `22e6e4c289be67b78d39a7eae157bfa3219d23a4`, comparator `2aaf2552ce21154928b9f9c83582e41a637f5910`. Same temporary Ubuntu 24.04 runner, AMD EPYC 7763; three alternating-order paired repetitions per case. All 42 records, 1,800 full historical snapshot readbacks and normal cleanup checks passed. [Raw data, per-step ledgers, source hashes, machine details and CSV](measurements/2026-10-22-cas-paired/).

The [complete frozen boundary](feasibility/CAS-MEASUREMENT-BOUNDARIES.md) is essential: CAS CLI process startup, conservative fsync publication and CAS-only instrumentation versus live SDK calls and Disposable synchronous=OFF are not equal-durability or pure API measurements. Both products use separate fresh identical Btrfs filesystems. Unsupported metadata-only branching is explicitly absent from the adapter and omitted on both sides. The [bounded semantic suite](CAS-CHECKPOINT-SEMANTICS.md) also passed in this run.

## Time medians

Milliseconds. Preparation includes application initialization, import, first writable view startup/mount and verified full read, but not software/runtime installation. Warm includes creation of a second writable view and its verified full read. Each CAS view has a separate FUSE process and 16 MiB content cache; first-use is not verified cold cache. Phase totals are per-sample sums before taking medians, not sums of independent medians.

| Case | CAS preparation | Comparator preparation | CAS warm view + read | Comparator warm view + read |
|---|---:|---:|---:|---:|
| identical | 375.4 | 604.0 | 138.9 | 187.7 |
| unique | 2305.6 | 1927.7 | 166.7 | 667.8 |
| mixed | 2217.9 | 1624.4 | 161.8 | 572.5 |
| insert | 539.4 | 607.1 | 148.1 | 192.6 |
| history-distributed | 648.0 | 510.5 | 64.4 | 80.9 |
| history-hotset | 614.7 | 489.5 | 62.3 | 82.1 |
| history-recurring | 614.9 | 482.8 | 57.3 | 84.2 |

Only identical and insert preparation medians are lower for CAS; all seven warm view/read medians are lower. This does not establish a general or theoretical speed advantage.

| 100-edit history | CAS write + checkpoint (ms) | Comparator (ms) | CAS checkpoint alone (ms) | Comparator checkpoint alone (ms) |
|---|---:|---:|---:|---:|
| history-distributed | 12233.6 | 2464.4 | 11605.7 | 501.6 |
| history-hotset | 12808.7 | 2601.3 | 12109.8 | 584.2 |
| history-recurring | 12775.7 | 2860.2 | 11994.6 | 325.9 |

Checkpoint is the remaining major bottleneck. The series does not isolate its causes or subtract estimated instrumentation/flush costs. Across-run comparisons with earlier prototypes cannot establish causal improvements.

## Physical storage medians

Decimal MB. Whole-filesystem Used growth includes Data, Metadata and System blocks with live workspaces and services retained. Comparator whole-runtime growth includes its image/software baseline, persistent Docker/containerd roots, writable overlays, volumes, SDK home and logs. Its runtime-ready increment removes the measured pre-application runtime baseline, but is still not exact application-data-only accounting. CAS growth includes its objects, all manifests/commits, both upper/work trees and runtime logs; executable/build inputs and volatile/RAM state are outside the metric for both sides. Never interpret the two comparator columns as interchangeable or use software-baseline differences as proof of net-data superiority.

| Case | CAS whole-FS growth MB | Comparator whole-runtime growth MB | Comparator runtime-ready increment MB |
|---|---:|---:|---:|
| identical | 1.380 | 99.594 | 13.718 |
| unique | 109.998 | 204.878 | 118.903 |
| mixed | 82.629 | 178.332 | 92.328 |
| insert | 10.605 | 103.338 | 17.400 |
| history-distributed | 14.967 | 104.047 | 18.072 |
| history-hotset | 19.005 | 104.022 | 18.129 |
| history-recurring | 2.396 | 103.530 | 17.621 |

CAS hotset growth exceeds even the comparator runtime-ready increment; no all-case storage victory is supported. The insert case is the frozen 4 KiB-aligned recipe, not arbitrary shifted-data validation.

## What remains

The adapter has a passing bounded incremental-capture/shared-publication/merge test, not complete branch APIs, production workspace lifecycle, crash recovery, GC/export, or hostile-owner safety. Production source was unchanged. Further work must target the measured checkpoint bottleneck while retaining publication correctness and durability; neither selective warm timings nor incomplete capabilities satisfy the overall request.
