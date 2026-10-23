# Real production CLI comparison: native and projection

**The overall speed + storage goal is not achieved.** This is the first paired series against the integrated production CLI, not the earlier experimental adapter. Native preparation loses all seven cases. Projection preparation wins five, but both backends lose all three 100-edit history tasks. Storage and runtime boundaries below are essential; no full-product or equal-durability winner is claimed.

Production `46f96341498ef040280720d8f97c17de82db4419`; comparator fixed v1.0.0 `2aaf2552ce21154928b9f9c83582e41a637f5910`; harness `7bbf5e0252dcadad20b7b81907fa7f4114a92115`. Current comparator upstream is newer, so these results are not a benchmark of its latest main. Production source and algorithms were not patched for this experiment. The locked release binary with the optional projection feature serves both native and explicit projected backends.

- [Projection run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39908965839)
- [Native run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39909347636)
- [Complete raw, step ledgers, source/binary hashes, environment and CSV](measurements/2026-10-23-production-cli/)

Each backend ran on its own temporary Ubuntu 24.04 AMD EPYC 7763 runner with its own contemporaneous comparator: three alternating-order paired repetitions of the same seven frozen recipes. Each series passed all 42 records and 1,800 historical snapshot readbacks, for 84 records and 3,600 readbacks total. Production's kernel lifecycle integration gate also passed. Backend-to-backend or earlier-run changes are not controlled same-machine causal speedups, even when CPU models match.

## What is actually matched

[Full measurement contract](feasibility/PRODUCTION-MEASUREMENT-BOUNDARIES.md). Both sides retain three active workspaces: imported main, work and second. Because the comparator's main is a base reference rather than a mountable branch, its import phase includes project.init + branch.fork(import-main, main) + workspace.mount(import-main). Both work/second forks start from unchanged main. This differs explicitly from earlier prototype series with two active views; old results/raw are unchanged.

All production CLI init, source capture, fork, real lifecycle/readiness, observations, upper synchronization, revision/state publication and backups are charged as implemented. No private-library shortcut, free fork or removed flush is used. Native default auto-copy and projected paths are separate. Sources live outside the fresh product Btrfs image, so initial native import copies rather than borrowing uncharged extents: raw copy_stats show 100/101/200 copied files according to the recipe and zero cloned imports. Native workspace bytes are not deduplicated merely because its history CAS is.

The comparator global SQLite store is WAL with Disposable synchronous=OFF/fullfsync=OFF; workspace overlays use MEMORY/OFF/EXCLUSIVE. This is not equivalent to Sprig's synchronization contract. CLI subprocesses, harness lifecycle logging and host shell versus SDK/Docker transport stay inside their defined timings. No pure API, cold-cache, equal-RAM or equal-background-compute claim is made. Installation/build/runtime deployment is excluded; application initialization is included in preparation. The fixed dd fsync precedes restored mtime and does not alone certify final metadata durability.

## Timing medians

Milliseconds. Preparation = init + import + first writable fork + full checksum read. Warm = second writable fork + full checksum read. Per-sample sums are computed before medians. Historical readbacks, additional post-checkpoint integrity oracles and final accounting synchronization are outside these operation timers; the full-read checksum task and production import safety inventory remain inside their respective timers.

### Projection

| Case | Sprig preparation | Comparator preparation | Sprig warm | Comparator warm |
|---|---:|---:|---:|---:|
| identical | 366.1 | 567.8 | 167.4 | 186.8 |
| unique | 2076.7 | 1951.1 | 194.1 | 684.5 |
| mixed | 1684.5 | 1623.2 | 188.3 | 571.0 |
| insert | 561.9 | 627.8 | 163.9 | 198.6 |
| history-distributed | 444.0 | 464.0 | 98.1 | 83.1 |
| history-hotset | 452.3 | 489.8 | 101.1 | 85.4 |
| history-recurring | 443.1 | 473.5 | 96.1 | 80.6 |

| 100-edit history | Sprig write + checkpoint | Comparator | Sprig checkpoint alone | Comparator checkpoint alone |
|---|---:|---:|---:|---:|
| history-distributed | 4320.7 | 2452.5 | 3703.3 | 499.6 |
| history-hotset | 6844.0 | 2575.8 | 6180.5 | 563.7 |
| history-recurring | 3746.1 | 2909.1 | 2983.3 | 334.5 |

### Native

| Case | Sprig preparation | Comparator preparation | Sprig warm | Comparator warm |
|---|---:|---:|---:|---:|
| identical | 900.8 | 568.9 | 379.5 | 188.3 |
| unique | 2609.9 | 1904.9 | 379.3 | 663.7 |
| mixed | 2175.6 | 1568.3 | 376.4 | 561.3 |
| insert | 1055.9 | 605.6 | 374.5 | 191.9 |
| history-distributed | 1072.3 | 437.4 | 375.2 | 80.9 |
| history-hotset | 1055.5 | 448.4 | 366.9 | 79.7 |
| history-recurring | 1072.5 | 455.2 | 392.6 | 79.8 |

| 100-edit history | Sprig write + checkpoint | Comparator | Sprig checkpoint alone | Comparator checkpoint alone |
|---|---:|---:|---:|---:|
| history-distributed | 4224.3 | 2350.8 | 3768.1 | 478.2 |
| history-hotset | 4271.8 | 2352.0 | 3795.1 | 544.0 |
| history-recurring | 4205.0 | 2686.7 | 3478.8 | 309.6 |

Projection: preparation lower in 5/7 cases, warm lower in 4/7; the three history tasks are about 1.8, 2.7 and 1.3 times slower. Native: preparation lower in 0/7, warm lower only for unique/mixed; the history tasks are about 1.8, 1.8 and 1.6 times slower. Both lose checkpoint-alone latency in every history case. These are the full production costs, not the smaller prototype's score.

## Physical storage

Decimal MB. Primary metric is whole Btrfs filesystem Used growth including Data + Metadata + System with three workspaces and required servers live. Sprig includes all native trees or projection generations, CAS objects, revisions, state, staging, backups, locks and logs. Comparator whole-runtime includes persistent Docker/containerd roots, software/image baseline, writable overlays, volumes, SDK home and logs. Runtime-ready increment removes its measured pre-application runtime baseline but is **not exact application-data-only**. Shared build/executables and volatile host/RAM state are excluded on both sides. Do not use software-baseline differences to prove net-data superiority.

### Projection footprint

| Case | Sprig whole-FS MB | Comparator whole-runtime MB | Comparator runtime-ready increment MB |
|---|---:|---:|---:|
| identical | 1.221 | 99.709 | 13.701 |
| unique | 110.002 | 204.837 | 118.960 |
| mixed | 82.510 | 178.295 | 92.361 |
| insert | 10.482 | 103.379 | 17.412 |
| history-distributed | 7.492 | 104.010 | 18.084 |
| history-hotset | 11.563 | 104.038 | 18.113 |
| history-recurring | 6.472 | 103.559 | 17.617 |

### Native footprint

| Case | Sprig whole-FS MB | Comparator whole-runtime MB | Comparator runtime-ready increment MB |
|---|---:|---:|---:|
| identical | 106.623 | 99.705 | 13.701 |
| unique | 215.327 | 204.906 | 118.907 |
| mixed | 187.847 | 178.270 | 92.365 |
| insert | 117.338 | 103.318 | 17.412 |
| history-distributed | 10.121 | 104.120 | 18.108 |
| history-hotset | 14.189 | 104.079 | 18.117 |
| history-recurring | 9.855 | 103.588 | 17.629 |

Projection whole-FS growth is lower than the stated comparator runtime-ready increment in all seven cases under this boundary. Native is higher for identical/unique/mixed/insert and lower in the three history recipes. This does not establish equal-capability or equal-durability storage superiority. The aligned insert fixture is not arbitrary-offset coverage.

## Correctness, limitations and next decision

The sample verifies source/main/second unchanged, all 100 distinct committed revisions and their history membership (plus exact first-parent edges for Sprig), each historical snapshot's listed-file bytes, live lifecycle at accounting and ordinary cleanup. History restores occur after space sampling, so their extra retained workspaces do not contaminate the workload footprint. Native and projection both exercise actual production APIs. The gate is production's integration suite, not the old adapter's differently shaped 11-case command contract.

The measured workload is not a full mode/mtime/namespace oracle or a power-loss test. Optional Linux projection currently requires root and the FUSE/Overlay kernel environment; native workspaces are not containers or sandboxes. Other platform CI is functional evidence, not a performance comparison. No source changes or new optimization should be credited to this run: it establishes a real baseline for subsequent measured work.

The first smoke attempt used workspace.mount(main) incorrectly and failed at comparator setup after Sprig's first sample. Commit 7bbf5e0 corrected the harness to create a mountable import-main branch and charges that operation; failed smoke results are not pooled into these medians. The successful smoke runs and all prior prototype results are separate evidence. The original performance target remains open.
