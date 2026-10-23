# Shared object batches and embedded revision results

**The combined speed, storage and basic-capability target remains unmet.** This candidate does not establish a general improvement: distributed and hotset history remain slower, recurring is essentially tied, and recurring retained storage is higher than the previous observation. Fewer record files are not proof of less physical storage.

[Full run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39875512070), frozen revision `61a8db5580d5d4fbdc7d1de11c3901fd3092a4a4`, comparator `2aaf2552ce21154928b9f9c83582e41a637f5910`. One temporary Ubuntu 24.04 runner, AMD EPYC 7763; three alternating paired repetitions. All 42 records, 1,800 full historical snapshot readbacks, 11 semantic oracle cases and normal cleanup checks passed. [Complete raw, ledgers, hashes, environment and CSV](measurements/2026-10-23-cas-shared-primitives/).

Unlike previous adapters, this candidate links an **isolated experimental core snapshot**, based on production `22e6e4c289be67b78d39a7eae157bfa3219d23a4` with content.rs, metadata.rs and lib.rs changed. Production itself was not modified. The changes share ObjectBatch ingestion and bounded metadata codec, batch object directory barriers at capture completion, and store a manifest inside one immutable revision record. New-object file durability and before-head barriers remain required. See [experiment provenance](feasibility/shared-primitives-EXPERIMENT.md), [core diff](feasibility/shared-primitives-core-changes.diff) and [publication contract](feasibility/cas-projection/PUBLICATION.md).

The [frozen measurement boundary](feasibility/CAS-MEASUREMENT-BOUNDARIES.md), performance sample, seven fixtures, write/read operations and 11 semantic assertions are unchanged. CAS CLI startup, capture and conservative fsync are charged versus persistent SDK and Disposable synchronous=OFF, not equal durability or pure API latency. Software/runtime installation is excluded from preparation; application initialization is included. First use is not verified cold cache. Two independent FUSE content caches are 16 MiB each, not total RSS limits. Metadata-only branching remains unavailable. The [prior linear inventory results](CAS-LINEAR-INVENTORY-RESULTS.md) remain intact. Even where the CPU model matches, separate temporary runners are not a controlled same-machine A/B.

## Time medians

Milliseconds. Preparation = application initialization + import + first writable view + verified full read. Warm = second writable view + verified full read. Medians are taken over per-sample phase sums.

| Case | CAS preparation | Comparator preparation | CAS warm | Comparator warm |
|---|---:|---:|---:|---:|
| identical | 378.4 | 580.3 | 140.4 | 188.3 |
| unique | 2290.7 | 1893.3 | 163.1 | 653.3 |
| mixed | 2218.7 | 1548.7 | 156.0 | 549.2 |
| insert | 538.2 | 591.2 | 141.3 | 187.0 |
| history-distributed | 591.6 | 470.5 | 63.5 | 78.1 |
| history-hotset | 605.0 | 481.3 | 62.5 | 87.4 |
| history-recurring | 602.5 | 483.8 | 63.3 | 86.5 |

Preparation is lower for CAS in two cases; warm view + read is lower in all seven. These selected phases do not establish overall superiority.

| 100-edit history | CAS write + checkpoint | Comparator | CAS checkpoint alone | Comparator checkpoint alone |
|---|---:|---:|---:|---:|
| history-distributed | 3207.0 | 2321.9 | 2594.8 | 476.9 |
| history-hotset | 5290.2 | 2401.0 | 4618.6 | 545.5 |
| history-recurring | 2710.2 | 2736.4 | 1974.0 | 312.9 |

Distributed is about 1.4 times slower and hotset about 2.2 times slower including writes. Recurring differs by only about 1%, not a robust speed-win claim from three repetitions. Checkpoint alone loses all three.

Median charged capture totals are 937.41 / 2946.07 / 389.68 ms (distributed / hotset / recurring); publication totals are 1161.66 / 1148.68 / 1091.04 ms. Transaction opening is about 167–168 ms and base loading about 129–140 ms per 100 checkpoints. These diagnostic wall intervals are inside the score, not subtracted CPU estimates. Inclusive capture/walk and their components must not be double-counted.

## Physical storage medians

Decimal MB. Whole-filesystem Used includes Data + Metadata + System with both writable views and services live. Comparator whole-runtime includes software/image baseline, Docker/containerd persistent roots, writable overlays, volumes, SDK home and logs. Runtime-ready increment removes measured pre-application runtime baseline, but is **not exact application-data-only**. CAS includes objects, all history, both upper/work trees and logs. Executable/build inputs and volatile host/RAM state are excluded for both. These columns do not prove equal-capability/equal-durability net-data superiority.

| Case | CAS whole-FS MB | Comparator whole-runtime MB | Comparator runtime-ready increment MB |
|---|---:|---:|---:|
| identical | 1.274 | 99.623 | 13.685 |
| unique | 109.941 | 204.866 | 118.956 |
| mixed | 82.526 | 178.262 | 92.324 |
| insert | 10.482 | 103.305 | 17.428 |
| history-distributed | 5.669 | 104.112 | 18.129 |
| history-hotset | 9.708 | 104.042 | 18.076 |
| history-recurring | 4.682 | 103.490 | 17.641 |

CAS remains below the stated runtime-ready increment in these seven cases, but recurring CAS storage is observed at 4.682 MB versus 2.249 MB in the prior run. Embedding state in distinct revision records can trade away repeated-state metadata sharing; that hypothesis needs source/component verification, not an invented physical-byte attribution. The original raw is preserved. Insert remains the frozen 4 KiB-aligned recipe, not arbitrary-offset validation.

This prototype is not a production integration and still lacks complete branch APIs, lifecycle/recovery, GC/export and hostile-owner safety. Passing the bounded kernel/merge/history suite does not imply those capabilities. The measured evidence does not justify claiming the overall goal achieved or retaining every optimization merely because it reduces source duplication.
