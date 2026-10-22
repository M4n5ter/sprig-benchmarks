# Path-computation-only prototype rerun

**The target remains unmet.** All warm fork + verified-read medians favor the native prototype, but 100-step write + checkpoint workloads still favor LayerFS. Initialization-inclusive phase sums are mixed, and insertion storage remains poor. This is still an incomplete feasibility prototype, not production Sprig or feature parity.

[Successful run 39778927311](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39778927311), harness 72f8db8b75c5311e63193b5795f5f4c4eddd1aec. Native SHA256 dc57dac9dc6a9ac0e08992521d5482620cdb90274a28937c78e6647aa5874367 changes only redundant path computation relative to the [original experiment](BTRFS-FEASIBILITY-RESULTS.md). The operation scripts, fixture and measurement boundaries are unchanged. LayerFS remains pinned 2aaf2552ce21154928b9f9c83582e41a637f5910.

All 42 required records passed, including 1800 complete historical snapshot readbacks and cleanup. Three samples per case/product on one AMD EPYC 9V74 runner. The earlier run used EPYC 7763: these are not same-machine before/after causal speedup measurements. Small median differences may be noise. [Full boundary document](feasibility/MEASUREMENT-BOUNDARIES.md) remains binding, including different durability, interfaces, lifecycle and excluded setup.

## Observed median phase sums (milliseconds)

These exclude software/runtime deployment and are not complete startup wall time.

| Case | Native init+import+fork+read | LayerFS | Native warm fork+read | LayerFS |
|---|---:|---:|---:|---:|
| identical | 1201.1 | 540.1 | 99.2 | 145.8 |
| unique | 1959.5 | 1998.5 | 100.2 | 547.4 |
| mixed | 1870.3 | 1671.6 | 125.0 | 455.2 |
| insert | 1622.9 | 533.4 | 132.2 | 148.7 |
| history-distributed | 338.9 | 393.5 | 13.8 | 53.9 |
| history-hotset | 645.6 | 571.8 | 13.5 | 55.0 |
| history-recurring | 527.5 | 716.8 | 14.1 | 55.0 |

## 100 history steps (seconds)

| Case | Native write+checkpoint | LayerFS | Native checkpoint only | LayerFS |
|---|---:|---:|---:|---:|
| history-distributed | 4.869 | 1.797 | 4.391 | 0.378 |
| history-hotset | 3.506 | 1.933 | 3.001 | 0.444 |
| history-recurring | 5.378 | 2.195 | 4.354 | 0.266 |

## Filesystem growth (MiB)

Whole-filesystem and runtime-ready increments include software/runtime differences. They are not application-data-only bytes and do not establish a net-data storage winner. See the original report for the insertion sharing-counter warning and partial-extent-retention hypothesis.

| Case | Native filesystem growth | LayerFS whole deployment | LayerFS after runtime-ready |
|---|---:|---:|---:|
| identical | 1.312 | 95.023 | 13.062 |
| unique | 100.500 | 195.387 | 113.441 |
| mixed | 75.500 | 170.016 | 88.078 |
| insert | 101.984 | 98.582 | 16.625 |
| history-distributed | 9.031 | 99.168 | 17.270 |
| history-hotset | 10.312 | 99.195 | 17.270 |
| history-recurring | 11.953 | 98.691 | 16.785 |

[Full raw evidence, machine details and summaries](measurements/2026-10-22-btrfs-relpath/) are preserved independently. Original measurements remain unchanged. Reproduce summaries with feasibility/summarize_btrfs.py. No checkpoint-internal fsync/read/dedup timers were collected, so these results cannot quantify their separate shares.
