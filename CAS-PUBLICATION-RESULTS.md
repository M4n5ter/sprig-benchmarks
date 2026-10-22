# CAS/Overlay publication optimization results

**The speed + storage + basic-capability goal is not met.** This experimental adapter improves warm writable-view-plus-read timings in six of these seven cases, but 100-edit history tasks remain about 5.4–7.6 times slower. It is not production Sprig or feature parity.

[Run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39804648943), frozen harness `fcbce58244f4be453279d87b0a7ca20818ffd526`, production content-library dependency `22e6e4c289be67b78d39a7eae157bfa3219d23a4`, comparator `2aaf2552ce21154928b9f9c83582e41a637f5910`. Same temporary Ubuntu 24.04 runner, Intel(R) Xeon(R) 6973P-C; three alternating-order paired repetitions per case. All 42 records, 1,800 full historical snapshot readbacks and normal cleanup checks passed. [Raw data, per-step ledgers, source hashes, machine details and CSV](measurements/2026-10-22-cas-publication/).

The [complete frozen boundary](feasibility/CAS-MEASUREMENT-BOUNDARIES.md) is essential: CAS CLI process startup, conservative fsync publication and CAS-only instrumentation versus live SDK calls and Disposable synchronous=OFF are not equal-durability or pure API measurements. Both products use separate fresh identical Btrfs filesystems. Unsupported metadata-only branching is explicitly absent from the adapter and omitted on both sides. The [bounded semantic suite](CAS-CHECKPOINT-SEMANTICS.md) also passed in this run.

This fresh-store candidate adds compressed immutable history manifests and skips only redundant fsyncs for objects already proven durable by the validated published head. New-object checks and publication ordering remain intact; see [the exact contract](feasibility/cas-projection/PUBLICATION.md). The [previous complete result](CAS-PAIRED-RESULTS.md) remains unchanged. These runs used different temporary hosts: observed before/after differences are not same-machine causal speedups. The workload, performance sample driver and measurement boundaries are unchanged; the functional oracle reads the same complete published manifest through the existing history decoder instead of opening its now-compressed file as JSON.

## Time medians

Milliseconds. Preparation includes application initialization, import, first writable view startup/mount and verified full read, but not software/runtime installation. Warm includes creation of a second writable view and its verified full read. Each CAS view has a separate FUSE process and 16 MiB content cache; first-use is not verified cold cache. Phase totals are per-sample sums before taking medians, not sums of independent medians.

| Case | CAS preparation | Comparator preparation | CAS warm view + read | Comparator warm view + read |
|---|---:|---:|---:|---:|
| identical | 308.5 | 496.5 | 128.3 | 181.0 |
| unique | 3298.9 | 1757.3 | 129.8 | 611.5 |
| mixed | 2775.4 | 1413.5 | 134.3 | 515.9 |
| insert | 507.1 | 557.4 | 116.8 | 185.8 |
| history-distributed | 741.9 | 370.9 | 55.0 | 57.0 |
| history-hotset | 748.2 | 361.9 | 60.0 | 50.6 |
| history-recurring | 729.4 | 375.6 | 39.6 | 48.8 |

Only identical and insert preparation medians are lower for CAS; six warm view/read medians are lower; hotset is slower. This does not establish a general or theoretical speed advantage.

| 100-edit history | CAS write + checkpoint (ms) | Comparator (ms) | CAS checkpoint alone (ms) | Comparator checkpoint alone (ms) |
|---|---:|---:|---:|---:|
| history-distributed | 9731.2 | 1530.3 | 9195.0 | 296.2 |
| history-hotset | 11490.9 | 1506.9 | 11015.7 | 318.7 |
| history-recurring | 9394.3 | 1752.5 | 8859.6 | 189.1 |

Checkpoint is the remaining major bottleneck. The series does not isolate its causes or subtract estimated instrumentation/flush costs. Across-run comparisons with earlier prototypes cannot establish causal improvements.

## Physical storage medians

Decimal MB. Whole-filesystem Used growth includes Data, Metadata and System blocks with live workspaces and services retained. Comparator whole-runtime growth includes its image/software baseline, persistent Docker/containerd roots, writable overlays, volumes, SDK home and logs. Its runtime-ready increment removes the measured pre-application runtime baseline, but is still not exact application-data-only accounting. CAS growth includes its objects, all manifests/commits, both upper/work trees and runtime logs; executable/build inputs and volatile/RAM state are outside the metric for both sides. Never interpret the two comparator columns as interchangeable or use software-baseline differences as proof of net-data superiority.

| Case | CAS whole-FS growth MB | Comparator whole-runtime growth MB | Comparator runtime-ready increment MB |
|---|---:|---:|---:|
| identical | 1.274 | 99.627 | 13.718 |
| unique | 109.974 | 204.882 | 118.911 |
| mixed | 82.559 | 178.291 | 92.353 |
| insert | 10.482 | 103.367 | 17.424 |
| history-distributed | 5.833 | 104.088 | 18.117 |
| history-hotset | 9.871 | 104.067 | 18.067 |
| history-recurring | 2.216 | 103.633 | 17.650 |

CAS whole-FS growth is lower than the comparator runtime-ready increment in all seven cases under these stated boundaries. This is not exact application-data-only or equal-capability/equal-durability proof, and does not satisfy the overall speed-and-capability goal. The insert case is the frozen 4 KiB-aligned recipe, not arbitrary shifted-data validation.

## What remains

The adapter has a passing bounded incremental-capture/shared-publication/merge test, not complete branch APIs, production workspace lifecycle, crash recovery, GC/export, or hostile-owner safety. Production source was unchanged. Further work must target the measured checkpoint bottleneck while retaining publication correctness and durability; neither selective warm timings nor incomplete capabilities satisfy the overall request.
