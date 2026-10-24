# Latest default-auto production against LayerFS v1.1.0

Completed 24 October 2026. Sprig production main `e38225e1e1160e8de90aa911d6f1740bef93bacc`, fresh stores with **default auto compression**, against release LayerFS v1.1.0 `9f97a7ec95b662e9cb288704afa165feff132cfa`. The earlier fba baseline remains separate and unchanged. No GC, pruning or retention policy was applied.

All three series passed: **126 paired records and 5,400 complete historical-snapshot readbacks**. Each backend has seven cases × three repetitions × two products. Three live workspaces are retained on both sides when measuring storage. No overall speed-and-storage victory is established.

## Limits that change interpretation

- Every Sprig/LayerFS pair uses the same runner, fixtures and fresh Btrfs configuration. Different backend runs use separate runner instances, sometimes different CPU models; do not treat cross-backend or later-version differences as same-machine causal evidence.
- Sprig retains production synchronization and CLI process overhead. LayerFS uses its persistent SDK, global SQLite WAL/OFF and workspace MEMORY/OFF Disposable mode. This is not equal crash/power-loss durability.
- Preparation includes store initialization, import, the first usable fork and complete checksum read. Warm task includes a new usable fork and complete checksum read. These are phase sums, not software installation or Docker runtime-setup time.
- Storage is whole Btrfs Used minus empty-filesystem baseline, including persistent runtime/overlay/log state. LayerFS runtime-ready delta is also shown, but is **not exact application-only usage**. Its required runtime/software deployment differs from native-host Sprig; RAM, tmpfs, kernel/page cache and external executables are excluded.
- Checks cover listed file bytes, 100 distinct acknowledged revisions and all historical byte readbacks; they are not a complete POSIX metadata/crash oracle. Cargo full-tree checks belong to the separate Cargo series.
- Results are medians of three repetitions. Restore totals occur after the primary live-storage snapshot and include normal cleanup; they must not be added to the earlier storage point.

Full protocol: [measurement boundaries](feasibility/CURRENT-MEASUREMENT-BOUNDARIES.md) and [latest pin/default-auto scope](feasibility/LATEST-MEASUREMENT-PIN.md). Frozen fixture and operation scripts are unchanged; metadata-only probes are omitted on both sides.

## writable

[Run 40054689786](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40054689786); CPU: Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz. 42/42 records and 1,800/1,800 historical readbacks passed.

Sprig preparation median is lower in 7/7 cases; warm fork/read median is lower in 2/7. History checkpoint and complete write+commit results are reported independently below.

[Complete original artifact, compressed](data/release-20261024/e38225e-auto/writable-40054689786-full-artifact.tar.gz) · [summary CSV](data/release-20261024/e38225e-auto/writable-summary.csv)

| Case | Preparation ms, Sprig / LayerFS | Warm fork+read ms, Sprig / LayerFS | Live empty-FS delta MiB, Sprig / LayerFS | LayerFS runtime-ready delta MiB |
|---|---:|---:|---:|---:|
| identical | 429.5 / 516.9 | 256.4 / 184.1 | 1.082 / 95.016 | 13.086 |
| unique | 591.1 / 1660.2 | 273.8 / 727.1 | 100.445 / 195.355 | 113.395 |
| mixed | 557.0 / 1377.1 | 284.7 / 596.3 | 75.352 / 169.930 | 88.066 |
| insert | 455.2 / 554.7 | 269.3 / 187.7 | 9.527 / 98.617 | 16.598 |
| history-distributed | 228.8 / 372.9 | 148.6 / 68.7 | 6.082 / 99.219 | 17.254 |
| history-hotset | 235.9 / 385.6 | 153.0 / 65.7 | 9.668 / 99.164 | 17.258 |
| history-recurring | 234.9 / 396.3 | 153.3 / 65.6 | 8.441 / 98.691 | 16.750 |

| History case | 100 checkpoints s, Sprig / LayerFS | 100 writes+commits s, Sprig / LayerFS | 100 restores+reads+cleanup s, Sprig / LayerFS |
|---|---:|---:|---:|
| history-distributed | 7.020 / 0.436 | 7.617 / 2.126 | 15.062 / 6.574 |
| history-hotset | 7.101 / 0.512 | 7.869 / 2.196 | 14.996 / 6.276 |
| history-recurring | 6.762 / 0.289 | 7.610 / 2.459 | 14.795 / 6.163 |

## native

[Run 40055336925](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40055336925); CPU: AMD EPYC 9V45 96-Core Processor. 42/42 records and 1,800/1,800 historical readbacks passed.

Sprig preparation median is lower in 2/7 cases; warm fork/read median is lower in 2/7. History checkpoint and complete write+commit results are reported independently below.

[Complete original artifact, compressed](data/release-20261024/e38225e-auto/native-40055336925-full-artifact.tar.gz) · [summary CSV](data/release-20261024/e38225e-auto/native-summary.csv)

| Case | Preparation ms, Sprig / LayerFS | Warm fork+read ms, Sprig / LayerFS | Live empty-FS delta MiB, Sprig / LayerFS | LayerFS runtime-ready delta MiB |
|---|---:|---:|---:|---:|
| identical | 982.8 / 437.1 | 279.6 / 128.0 | 101.625 / 95.168 | 13.055 |
| unique | 1613.2 / 1853.3 | 263.4 / 444.4 | 200.988 / 195.348 | 113.395 |
| mixed | 1434.2 / 1477.0 | 262.0 / 379.8 | 175.926 / 170.117 | 88.062 |
| insert | 1088.0 / 494.0 | 286.1 / 129.6 | 111.465 / 98.551 | 16.594 |
| history-distributed | 650.1 / 350.1 | 291.2 / 46.6 | 9.527 / 99.141 | 17.266 |
| history-hotset | 659.8 / 375.4 | 293.4 / 45.4 | 13.020 / 99.195 | 17.266 |
| history-recurring | 655.9 / 353.5 | 293.0 / 44.4 | 6.797 / 98.730 | 16.836 |

| History case | 100 checkpoints s, Sprig / LayerFS | 100 writes+commits s, Sprig / LayerFS | 100 restores+reads+cleanup s, Sprig / LayerFS |
|---|---:|---:|---:|
| history-distributed | 3.481 / 0.363 | 3.865 / 1.808 | 27.268 / 4.767 |
| history-hotset | 3.323 / 0.404 | 3.675 / 1.789 | 27.081 / 4.564 |
| history-recurring | 3.157 / 0.253 | 3.673 / 1.912 | 27.200 / 4.422 |

## projection

[Run 40055092686](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40055092686); CPU: AMD EPYC 9V45 96-Core Processor. 42/42 records and 1,800/1,800 historical readbacks passed.

Sprig preparation median is lower in 7/7 cases; warm fork/read median is lower in 4/7. History checkpoint and complete write+commit results are reported independently below.

[Complete original artifact, compressed](data/release-20261024/e38225e-auto/projection-40055092686-full-artifact.tar.gz) · [summary CSV](data/release-20261024/e38225e-auto/projection-summary.csv)

| Case | Preparation ms, Sprig / LayerFS | Warm fork+read ms, Sprig / LayerFS | Live empty-FS delta MiB, Sprig / LayerFS | LayerFS runtime-ready delta MiB |
|---|---:|---:|---:|---:|
| identical | 241.0 / 409.9 | 113.4 / 125.4 | 1.133 / 95.047 | 13.086 |
| unique | 893.7 / 1781.6 | 136.3 / 442.4 | 100.496 / 195.371 | 113.391 |
| mixed | 744.2 / 1439.3 | 131.1 / 371.7 | 75.402 / 170.039 | 88.051 |
| insert | 316.3 / 464.9 | 118.5 / 127.4 | 9.582 / 98.676 | 16.594 |
| history-distributed | 161.7 / 341.2 | 72.4 / 41.6 | 6.922 / 99.199 | 17.270 |
| history-hotset | 165.7 / 348.3 | 69.7 / 42.7 | 10.789 / 99.289 | 17.262 |
| history-recurring | 171.4 / 351.3 | 73.5 / 43.2 | 3.488 / 98.613 | 16.781 |

| History case | 100 checkpoints s, Sprig / LayerFS | 100 writes+commits s, Sprig / LayerFS | 100 restores+reads+cleanup s, Sprig / LayerFS |
|---|---:|---:|---:|
| history-distributed | 3.122 / 0.346 | 3.602 / 1.597 | 14.293 / 4.381 |
| history-hotset | 5.130 / 0.384 | 5.621 / 1.655 | 14.078 / 4.364 |
| history-recurring | 2.423 / 0.247 | 2.926 / 1.828 | 14.943 / 4.313 |

## Provenance

All three runs use benchmark commit `5f1d2d2`. The latest protocol differs from the preserved fba protocol only in provenance/default-auto labels and driver/output paths; workload operations and accounting remain frozen. Each archive retains original machine, compiler, binary/source/script hashes, raw per-step ledgers, kernel gates and measurements. No original raw result is rewritten. Default-auto results do not establish raw/no-compression performance; different hosted runners do not establish old-to-new causal speedup.

[Archive checksums and original JSON hashes](data/release-20261024/e38225e-auto/manifest.json).
