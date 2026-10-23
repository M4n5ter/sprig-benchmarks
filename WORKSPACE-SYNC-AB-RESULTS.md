# Same-runner synchronization A/B: no demonstrated benefit

**Do not merge the candidate on the strength of these measurements.** In this fixed same-runner experiment, none of the eight backend/case combinations has a lower median paired checkpoint ratio. The previously reported cross-run absolute reductions did not establish a causal improvement, and this direct test does not support the proposed optimization.

Baseline `46f96341498ef040280720d8f97c17de82db4419`; candidate `17130154de38f3c30be6eae620ad0c0b6d404d48`; harness `6b23cf9c7bd75808c81c36e373df51fa82b573cf`. The candidate remains a topic branch; this experiment does not merge or modify Sprig main.

- [Successful run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39922428850)
- [Complete raw, source/binary hashes, environment, step ledgers and paired summary](measurements/2026-10-23-production-sync-ab/)
- [Preregistered measurement contract](feasibility/PRODUCTION-AB-PLAN.md)
- [Preserved separate-run candidate comparison](WORKSPACE-SYNC-RESULTS.md)

## Method and checks

One temporary Ubuntu runner, two independently built immutable binaries, same toolchain and feature set. Five adjacent A/B pairs for each of two backends and four cases, with a fixed counterbalanced AB/BA schedule. All 80 expected samples and 8,000 historical snapshot readbacks passed, both production kernel lifecycle gates passed, and all 40 successful pair cleanups completed. Both revisions retained three live workspaces at accounting.

The three original history recipes and all 100 edits are unchanged. The fourth is a separate synthetic control, not an upstream case: eight 1 KiB root-level files plus root (nine logical entries), 100 real 64-byte edits and 100 distinct resulting content states. It remains below the candidate's 16-observed-entry threshold, so its synchronization path stays serial.

The production sample body and helper remain unchanged; a wrapper selects only fixed source provenance and the matching binary path. Full CLI initialization, captures, publications, synchronization, state/backups, reads and writes remain charged. Full history restores/readbacks occur after live physical accounting. No removed flushes, speculative reuse, cache dropping or outlier deletion. Installation/build and extra oracles are outside operation timers. No third-party comparator is run in this attribution experiment.

Each sample uses a fresh 2 GiB Btrfs image, Data SINGLE/Metadata DUP/no compression/noatime. Whole filesystem Used growth includes physical Data + Metadata + System and all product state/logs. Only after both samples pass, full raw is persisted, ordinary unmount succeeds, and exact path/inode/no-mount/no-loop checks pass are those two harness-created images removed. Failure would preserve diagnostic state; no forced or lazy unmount is used.

## Primary history timings

Milliseconds; each row contains 100 writes/checkpoints. Ratio is the median of five individual candidate/baseline ratios, not the ratio of separately calculated medians. Below 1 means faster. Min–max is the observed range, not a confidence interval.

### Native

| Case | Metric | Baseline median ms | Candidate median ms | Paired ratio median | Paired ratio min–max |
|---|---|---:|---:|---:|---:|
| history-distributed | write + checkpoint | 2783.0 | 2743.2 | 1.000 | 0.954–1.058 |
| history-distributed | checkpoint only | 2407.1 | 2377.2 | 1.002 | 0.960–1.060 |
| history-hotset | write + checkpoint | 2820.2 | 2931.3 | 1.026 | 0.925–1.159 |
| history-hotset | checkpoint only | 2427.6 | 2535.9 | 1.031 | 0.933–1.156 |
| history-recurring | write + checkpoint | 2870.6 | 2945.3 | 1.026 | 0.993–1.045 |
| history-recurring | checkpoint only | 2286.6 | 2343.9 | 1.033 | 0.993–1.055 |
| history-small-control | write + checkpoint | 1163.6 | 1253.4 | 1.024 | 0.988–1.104 |
| history-small-control | checkpoint only | 812.3 | 865.1 | 1.021 | 0.986–1.134 |
### Projection

| Case | Metric | Baseline median ms | Candidate median ms | Paired ratio median | Paired ratio min–max |
|---|---|---:|---:|---:|---:|
| history-distributed | write + checkpoint | 3089.5 | 3205.6 | 1.042 | 0.944–1.055 |
| history-distributed | checkpoint only | 2619.9 | 2725.5 | 1.040 | 0.949–1.057 |
| history-hotset | write + checkpoint | 4290.6 | 4411.9 | 1.028 | 1.006–1.060 |
| history-hotset | checkpoint only | 3798.0 | 3900.9 | 1.027 | 1.005–1.058 |
| history-recurring | write + checkpoint | 2751.1 | 2935.5 | 1.060 | 1.043–1.086 |
| history-recurring | checkpoint only | 2173.5 | 2324.1 | 1.061 | 1.046–1.088 |
| history-small-control | write + checkpoint | 1420.5 | 1506.1 | 1.092 | 1.001–1.102 |
| history-small-control | checkpoint only | 1050.4 | 1147.2 | 1.109 | 1.005–1.129 |

## Secondary preparation and warm timings

Preparation includes init + import + first writable fork + full checksum read. Warm includes second writable fork + full checksum read. All values are ms.

| Backend | Case | Metric | Baseline median | Candidate median | Median paired ratio |
|---|---|---|---:|---:|---:|
| native | history-distributed | preparationMs | 629.6 | 695.1 | 1.025 |
| native | history-distributed | warmMs | 213.4 | 252.2 | 1.018 |
| native | history-hotset | preparationMs | 623.9 | 714.8 | 1.146 |
| native | history-hotset | warmMs | 245.7 | 249.7 | 1.057 |
| native | history-recurring | preparationMs | 602.3 | 701.1 | 1.196 |
| native | history-recurring | warmMs | 214.3 | 252.0 | 1.190 |
| native | history-small-control | preparationMs | 41.3 | 39.6 | 0.951 |
| native | history-small-control | warmMs | 15.1 | 15.3 | 1.044 |
| projection | history-distributed | preparationMs | 298.0 | 306.0 | 1.007 |
| projection | history-distributed | warmMs | 80.6 | 75.0 | 0.959 |
| projection | history-hotset | preparationMs | 288.7 | 307.4 | 1.051 |
| projection | history-hotset | warmMs | 75.8 | 80.3 | 1.059 |
| projection | history-recurring | preparationMs | 293.9 | 321.9 | 1.081 |
| projection | history-recurring | warmMs | 72.7 | 75.2 | 0.995 |
| projection | history-small-control | preparationMs | 53.6 | 59.3 | 1.120 |
| projection | history-small-control | warmMs | 20.5 | 21.7 | 1.062 |

## Physical storage check

Whole-FS growth in decimal MB at the matched three-live-workspace point. This candidate changes synchronization scheduling, not storage representation; small allocation differences are not a storage optimization.

| Backend | Case | Baseline median MB | Candidate median MB |
|---|---|---:|---:|
| native | history-distributed | 10.568 | 10.162 |
| native | history-hotset | 14.197 | 13.787 |
| native | history-recurring | 9.859 | 9.859 |
| native | history-small-control | 1.122 | 1.122 |
| projection | history-distributed | 7.496 | 7.496 |
| projection | history-hotset | 11.567 | 11.567 |
| projection | history-recurring | 6.476 | 6.476 |
| projection | history-small-control | 1.196 | 1.196 |

## Decision and limits

Native checkpoint paired medians are approximately unchanged to 3.3% higher in the three original histories. Projection is 2.7–6.1% higher; hotset and recurring are higher in all five pairs. The serial small-tree control is also higher, especially projected, showing that timing variability and factors outside the changed scheduling must not be ignored. Five pairs are not high-confidence universal performance evidence; this report does not claim every observed difference is caused solely by the source change.

The defensible decision is that this candidate has not demonstrated a worthwhile end-to-end benefit under the tested real workload and should not be merged based on the earlier local microbenchmark or cross-run observations. Preserve the main baseline, negative results and candidate branch. No new optimization or stronger performance claim follows automatically.

These are bounded functional/content and synchronization-preserving measurements, not a power-loss proof, full metadata/namespace oracle or cross-platform speed result. The broader speed + storage objective remains open.
