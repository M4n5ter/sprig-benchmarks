# Workspace synchronization candidate: real production CLI

**The overall target remains unmet; these separate hosted runs do not establish a causal speedup or justify merging the candidate by themselves.** Sprig candidate `17130154de38f3c30be6eae620ad0c0b6d404d48` remains on `optimize-workspace-sync`, not main. It changes Linux workspace synchronization scheduling, not storage representation or durability requirements.

Harness `5e0c791c0062e5185ecf18c4ebf1260a31cb6897` differs from the [preserved production baseline](PRODUCTION-CLI-RESULTS.md) only in source pin, cache key and provenance wording. Operations, fixtures, timing definitions, three-live-workspace lifecycle and accounting are unchanged. Comparator remains v1.0.0 `2aaf2552ce21154928b9f9c83582e41a637f5910`.

- [Projection run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39917472081)
- [Native run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39917481636)
- [Complete raw, source hashes, environment, step ledgers and summaries](measurements/2026-10-23-workspace-sync/)

Both runs passed all 42 records and 1,800 historical snapshot readbacks each, 84 records and 3,600 readbacks total. Production kernel lifecycle gates passed. Each backend has its own same-run comparator and three paired repetitions; old/new and native/projection comparisons cross different runner instances. A lower old/new absolute time is an observation, not an isolated optimization effect.

## Boundaries

See the [measurement contract](feasibility/PRODUCTION-MEASUREMENT-BOUNDARIES.md). Preparation includes CLI init + import + first writable fork + full checksum read; warm includes second writable fork + full checksum read. Per-sample sums precede medians. All production capture, synchronization, state and backup work remains charged. Historical readback restores and extra correctness checks occur outside measured operations and after live storage sampling where specified.

Both retain imported main, work and second. Whole-FS growth counts physical Btrfs Data + Metadata + System, all application trees/CAS/revisions/state/generations/logs and, for the comparator, persistent Docker/containerd runtime state. Comparator runtime-ready increment subtracts its software/runtime baseline but is not exact application-only bytes. Shared executables and volatile host/RAM state remain excluded. Do not infer storage optimization from allocation noise: this candidate changes no storage policy.

Sprig synchronization is enabled. Comparator global store uses WAL/OFF and workspace overlay databases MEMORY/OFF/EXCLUSIVE. Different durability, CLI versus SDK/Docker transport and no cold-cache or equivalent-RAM guarantee remain explicit. No full-feature or equal-durability win is claimed.

## Projection medians

Milliseconds.

| Case | Sprig preparation | Comparator | Sprig warm | Comparator |
|---|---:|---:|---:|---:|
| identical | 246.7 | 452.7 | 118.4 | 129.3 |
| unique | 1905.9 | 1833.5 | 138.2 | 456.5 |
| mixed | 1472.7 | 1485.4 | 130.8 | 399.4 |
| insert | 377.9 | 488.4 | 124.3 | 131.7 |
| history-distributed | 345.2 | 342.2 | 67.2 | 44.5 |
| history-hotset | 347.7 | 355.4 | 67.0 | 43.8 |
| history-recurring | 341.3 | 336.8 | 67.6 | 43.4 |

| 100-edit history | Sprig write + checkpoint | Comparator | Sprig checkpoint alone | Comparator checkpoint alone | Prior Sprig write + checkpoint (different runner) |
|---|---:|---:|---:|---:|---:|
| history-distributed | 3235.1 | 1584.0 | 2767.2 | 339.8 | 4320.7 |
| history-hotset | 5480.0 | 1651.7 | 4961.4 | 381.1 | 6844.0 |
| history-recurring | 2646.3 | 1808.0 | 2132.0 | 236.5 | 3746.1 |

Decimal MB, three workspaces live.

| Case | Sprig whole-FS | Comparator whole-runtime | Comparator runtime-ready increment |
|---|---:|---:|---:|
| identical | 1.221 | 99.709 | 13.701 |
| unique | 109.969 | 204.837 | 118.923 |
| mixed | 82.510 | 178.254 | 92.361 |
| insert | 10.482 | 103.424 | 17.449 |
| history-distributed | 7.492 | 104.038 | 18.100 |
| history-hotset | 11.563 | 104.108 | 18.108 |
| history-recurring | 6.472 | 103.543 | 17.633 |

## Native medians

Milliseconds.

| Case | Sprig preparation | Comparator | Sprig warm | Comparator |
|---|---:|---:|---:|---:|
| identical | 1294.8 | 528.7 | 371.0 | 172.2 |
| unique | 4404.7 | 1906.7 | 372.6 | 647.0 |
| mixed | 3487.9 | 1493.8 | 381.9 | 517.7 |
| insert | 1641.0 | 567.6 | 375.3 | 162.2 |
| history-distributed | 1621.9 | 405.8 | 535.7 | 67.8 |
| history-hotset | 1594.9 | 417.7 | 571.2 | 64.3 |
| history-recurring | 1511.3 | 393.0 | 514.0 | 62.1 |

| 100-edit history | Sprig write + checkpoint | Comparator | Sprig checkpoint alone | Comparator checkpoint alone | Prior Sprig write + checkpoint (different runner) |
|---|---:|---:|---:|---:|---:|
| history-distributed | 3393.6 | 1902.8 | 2973.7 | 381.8 | 4224.3 |
| history-hotset | 3542.9 | 1913.5 | 3122.0 | 436.1 | 4271.8 |
| history-recurring | 3268.9 | 2148.2 | 2646.7 | 275.7 | 4205.0 |

Decimal MB, three workspaces live.

| Case | Sprig whole-FS | Comparator whole-runtime | Comparator runtime-ready increment |
|---|---:|---:|---:|
| identical | 106.623 | 99.639 | 13.701 |
| unique | 215.327 | 204.849 | 118.907 |
| mixed | 187.847 | 178.299 | 92.328 |
| insert | 117.338 | 103.383 | 17.412 |
| history-distributed | 10.527 | 104.014 | 18.076 |
| history-hotset | 14.160 | 103.973 | 18.063 |
| history-recurring | 9.445 | 103.567 | 17.658 |

## Interpretation

Projection preparation is lower in 4/7 cases and warm lower in 4/7. Native preparation loses all seven; warm is lower only for unique/mixed. Both lose all three history tasks, including checkpoint-alone latency. Projection history tasks are about 2.0, 3.3 and 1.5 times slower than their current comparator; native about 1.8, 1.9 and 1.5 times slower.

Old/new Sprig history absolute times are lower, but comparator timings also change materially. Native preparation is substantially higher than the previous run, while projection preparation is often lower. This variability prevents crediting the candidate with a controlled end-to-end improvement or declaring the native differences a proven algorithmic regression. Local alternating A/B evidence is separate and cannot replace a same-machine end-to-end attribution test.

Storage patterns remain substantially the same: projection below the stated comparator runtime-ready increment in all seven, native above it for the four large-file cases and below it for history. These are bounded physical/runtime observations, not equal-capability storage superiority. The full speed + storage goal remains open. The production main branch was not changed by this experiment.
