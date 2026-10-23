# ObjectBatch-only comparison results

**The speed, storage and basic-capability target is not met.** Restoring independent content-addressed manifests fixes the recurring-state storage regression, but all three history task medians are slower than the comparator in this run. This is an experimental adapter, not production Sprig or feature parity.

[Full run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39884221137), frozen revision `9cccfb534e6d980cc59ffcfd5d6116ee2f65c5ce`, comparator `2aaf2552ce21154928b9f9c83582e41a637f5910`. One temporary Ubuntu 24.04 runner, Intel Xeon Platinum 8573C, three alternating paired repetitions. All 42 records, 1,800 full historical snapshot readbacks, 11 semantic oracle cases and normal cleanup checks passed. [Complete raw, ledgers, hashes, environment and CSV](measurements/2026-10-23-cas-object-batch-only/).

Relative to the linear-inventory baseline, the isolated core snapshot differs from production `22e6e4c289be67b78d39a7eae157bfa3219d23a4` only in content.rs, and the adapter runtime differs only in capture.rs. ObjectBatch shares bounded CDC ingestion and finishes the object-directory durability barrier; existing object verification and new-object inode sync remain. The embedded Revision/shared-codec experiment is withdrawn: independent compressed manifest sharing and the original small Record publication are restored. [Exact experiment](feasibility/object-batch-only-EXPERIMENT.md). Production is unchanged; fresh synthetic stores only, no migration/deletion of previous stores.

The [measurement boundary](feasibility/CAS-MEASUREMENT-BOUNDARIES.md), fixtures, sample driver and 11 semantic assertions are unchanged. CLI startup, capture and conservative fsync are charged versus persistent SDK and Disposable synchronous=OFF, not equal durability or pure API speed. Preparation includes application initialization, excludes software/runtime installation. First use is not verified cold cache. Separate 16 MiB FUSE content caches per view do not establish equal total RAM/background compute. Metadata-only branching remains unavailable. Different temporary hosts mean cross-run observations are not same-machine causal speedups.

## Time medians

Milliseconds. Preparation = initialization + import + first writable view + verified full read. Warm = second writable view + verified full read. Medians use per-sample phase sums.

| Case | CAS preparation | Comparator preparation | CAS warm | Comparator warm |
|---|---:|---:|---:|---:|
| identical | 336.6 | 573.8 | 132.8 | 176.1 |
| unique | 2593.9 | 2048.6 | 159.0 | 655.4 |
| mixed | 2469.8 | 1644.6 | 148.3 | 538.5 |
| insert | 516.6 | 612.4 | 142.0 | 174.0 |
| history-distributed | 643.9 | 442.0 | 54.4 | 60.9 |
| history-hotset | 649.5 | 450.0 | 60.6 | 54.6 |
| history-recurring | 642.4 | 443.5 | 52.4 | 62.0 |

Only two preparation medians and six warm medians are lower for CAS. Hotset warm view + read is slower.

| 100-edit history | CAS write + checkpoint | Comparator | CAS checkpoint alone | Comparator checkpoint alone |
|---|---:|---:|---:|---:|
| history-distributed | 3325.9 | 2075.8 | 2666.2 | 415.9 |
| history-hotset | 4366.2 | 2109.3 | 3653.8 | 472.8 |
| history-recurring | 2457.2 | 2386.3 | 1762.7 | 283.3 |

Distributed is about 1.6 times slower, hotset about 2.1 times slower, and recurring about 3% slower including writes. Checkpoint alone also loses all three. Small recurring differences across runs are not a robust winner claim. The raw preserves charged phase instrumentation; inclusive capture/walk totals must not be added to their subcategories.

## Physical storage medians

Decimal MB. Whole-filesystem Used includes Data + Metadata + System with both writable views/services live. Comparator whole-runtime includes image/software, Docker/containerd persistent roots, writable overlays, volumes, SDK home and logs. Runtime-ready increment subtracts measured pre-application runtime baseline, but is **not exact application-data-only**. CAS includes objects, every manifest/Record, both upper/work trees and logs. Executable/build inputs and volatile host/RAM state are excluded for both. Do not interpret these columns as equal-capability/equal-durability net-data proof.

| Case | CAS whole-FS MB | Comparator whole-runtime MB | Comparator runtime-ready increment MB |
|---|---:|---:|---:|
| identical | 1.274 | 99.590 | 13.718 |
| unique | 110.006 | 204.825 | 118.919 |
| mixed | 82.559 | 178.389 | 92.328 |
| insert | 10.482 | 103.428 | 17.424 |
| history-distributed | 5.800 | 104.137 | 18.067 |
| history-hotset | 9.871 | 104.038 | 18.072 |
| history-recurring | 2.216 | 103.481 | 17.605 |

Recurring CAS growth is back to 2.216 MB, versus 4.682 MB in the embedded-revision experiment. Independent manifests can share repeated states without tying them to distinct revision identity. A separate local diagnostic verified 100 alternating publications retain two immutable manifests; that is not additional timed benchmark evidence. All seven CAS values remain below the comparator runtime-ready increment under the disclosed deployment boundary, not an exact app-only or feature-parity claim. Insert remains the frozen 4 KiB-aligned recipe.

[Previous shared-primitives result](CAS-SHARED-PRIMITIVES-RESULTS.md) and all earlier raw remain intact. The prototype still lacks complete branch APIs, production lifecycle/recovery, GC/export and hostile-owner safety. A passing bounded merge/history suite and selected warm phases do not satisfy the complete user goal.
