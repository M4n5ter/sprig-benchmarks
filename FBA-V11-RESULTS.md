# Frozen fba02ad production baseline against LayerFS v1.1.0

Completed 24 October 2026. This is the frozen pre-compression Sprig main `fba02ad27a9d82d225d852987a6fd234fe06f122`, **not** the newer `e38225e` default-auto version. New-version runs and reports are separate. Comparator: release v1.1.0 `9f97a7ec95b662e9cb288704afa165feff132cfa`.

All three series passed: **126 paired records and 5,400 complete historical-snapshot readbacks**. Each backend has seven cases × three repetitions × two products. Three live workspaces are retained on both sides when measuring storage. No overall speed-and-storage victory is established.

## Limits that change interpretation

- Every Sprig/LayerFS pair uses the same runner, fixtures and fresh Btrfs configuration. Different backend runs use different runner CPUs; do not treat cross-backend or later-version differences as same-machine causal evidence.
- Sprig retains production synchronization and CLI process overhead. LayerFS uses its persistent SDK, global SQLite WAL/OFF and workspace MEMORY/OFF Disposable mode. This is not equal crash/power-loss durability.
- Preparation includes store initialization, import, the first usable fork and complete checksum read. Warm task includes a new usable fork and complete checksum read. These are phase sums, not software installation or Docker runtime-setup time.
- Storage is whole Btrfs Used minus empty-filesystem baseline, including persistent runtime/overlay/log state. LayerFS runtime-ready delta is also shown, but is **not exact application-only usage**. Its required runtime/software deployment differs from native-host Sprig; RAM, tmpfs, kernel/page cache and external executables are excluded.
- Checks cover listed file bytes, 100 distinct acknowledged revisions and all historical byte readbacks; they are not a complete POSIX metadata/crash oracle. Cargo full-tree checks belong to the separate Cargo series.
- Results are medians of three repetitions. Restore totals occur after the primary live-storage snapshot and include normal cleanup; they must not be added to the earlier storage point.

Full protocol: [measurement boundaries](feasibility/CURRENT-MEASUREMENT-BOUNDARIES.md). Frozen fixture and operation scripts are unchanged; metadata-only probes are omitted on both sides.

## writable

[Run 40053721046](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40053721046); CPU: AMD EPYC 9V45 96-Core Processor. 42/42 records and 1,800/1,800 historical readbacks passed.

Sprig preparation median is lower in 7/7 cases; warm fork/read median is lower in 2/7. History checkpoint and complete write+commit results are reported independently below.

[Complete original artifact, compressed](data/release-20261024/fba02ad/writable-40053721046-full-artifact.tar.gz) · [summary CSV](data/release-20261024/fba02ad/writable-summary.csv)

| Case | Preparation ms, Sprig / LayerFS | Warm fork+read ms, Sprig / LayerFS | Live empty-FS delta MiB, Sprig / LayerFS | LayerFS runtime-ready delta MiB |
|---|---:|---:|---:|---:|
| identical | 294.3 / 409.7 | 178.9 / 119.2 | 1.082 / 95.043 | 13.055 |
| unique | 910.0 / 1783.9 | 233.2 / 436.1 | 100.438 / 195.402 | 113.410 |
| mixed | 751.1 / 1406.6 | 183.0 / 368.5 | 75.348 / 169.961 | 88.090 |
| insert | 373.8 / 456.4 | 195.4 / 124.2 | 9.527 / 98.578 | 16.598 |
| history-distributed | 189.3 / 333.3 | 123.4 / 42.4 | 5.234 / 99.262 | 17.238 |
| history-hotset | 190.1 / 373.3 | 118.0 / 46.3 | 8.844 / 99.238 | 17.266 |
| history-recurring | 187.4 / 344.5 | 121.9 / 38.4 | 8.355 / 98.711 | 16.777 |

| History case | 100 checkpoints s, Sprig / LayerFS | 100 writes+commits s, Sprig / LayerFS | 100 restores+reads+cleanup s, Sprig / LayerFS |
|---|---:|---:|---:|
| history-distributed | 6.205 / 0.339 | 6.702 / 1.575 | 11.869 / 4.264 |
| history-hotset | 6.164 / 0.384 | 6.805 / 1.642 | 12.531 / 4.127 |
| history-recurring | 5.934 / 0.229 | 6.539 / 1.717 | 11.954 / 4.148 |

## native

[Run 40054112873](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40054112873); CPU: AMD EPYC 7763 64-Core Processor. 42/42 records and 1,800/1,800 historical readbacks passed.

Sprig preparation median is lower in 2/7 cases; warm fork/read median is lower in 2/7. History checkpoint and complete write+commit results are reported independently below.

[Complete original artifact, compressed](data/release-20261024/fba02ad/native-40054112873-full-artifact.tar.gz) · [summary CSV](data/release-20261024/fba02ad/native-summary.csv)

| Case | Preparation ms, Sprig / LayerFS | Warm fork+read ms, Sprig / LayerFS | Live empty-FS delta MiB, Sprig / LayerFS | LayerFS runtime-ready delta MiB |
|---|---:|---:|---:|---:|
| identical | 873.9 / 576.9 | 364.0 / 188.2 | 101.625 / 94.918 | 13.055 |
| unique | 1023.7 / 1974.7 | 372.8 / 682.8 | 201.012 / 195.324 | 113.391 |
| mixed | 984.9 / 1601.1 | 372.4 / 568.6 | 175.922 / 170.047 | 88.066 |
| insert | 904.8 / 601.8 | 377.6 / 193.9 | 111.465 / 98.613 | 16.594 |
| history-distributed | 796.3 / 454.5 | 367.9 / 79.8 | 9.535 / 99.086 | 17.281 |
| history-hotset | 774.1 / 467.5 | 349.5 / 80.6 | 13.020 / 99.219 | 17.262 |
| history-recurring | 802.6 / 472.5 | 371.1 / 85.1 | 6.457 / 98.805 | 16.812 |

| History case | 100 checkpoints s, Sprig / LayerFS | 100 writes+commits s, Sprig / LayerFS | 100 restores+reads+cleanup s, Sprig / LayerFS |
|---|---:|---:|---:|
| history-distributed | 4.249 / 0.488 | 4.719 / 2.382 | 33.568 / 8.159 |
| history-hotset | 4.182 / 0.555 | 4.646 / 2.406 | 32.624 / 8.106 |
| history-recurring | 3.834 / 0.319 | 4.573 / 2.786 | 33.509 / 8.226 |

## projection

[Run 40054144941](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40054144941); CPU: AMD EPYC 9V74 80-Core Processor. 42/42 records and 1,800/1,800 historical readbacks passed.

Sprig preparation median is lower in 7/7 cases; warm fork/read median is lower in 4/7. History checkpoint and complete write+commit results are reported independently below.

[Complete original artifact, compressed](data/release-20261024/fba02ad/projection-40054144941-full-artifact.tar.gz) · [summary CSV](data/release-20261024/fba02ad/projection-summary.csv)

| Case | Preparation ms, Sprig / LayerFS | Warm fork+read ms, Sprig / LayerFS | Live empty-FS delta MiB, Sprig / LayerFS | LayerFS runtime-ready delta MiB |
|---|---:|---:|---:|---:|
| identical | 295.8 / 501.2 | 138.3 / 147.1 | 1.133 / 94.922 | 13.055 |
| unique | 935.3 / 2049.6 | 225.3 / 582.6 | 100.488 / 195.430 | 113.406 |
| mixed | 814.1 / 1668.4 | 171.5 / 472.6 | 75.398 / 169.969 | 88.039 |
| insert | 395.7 / 576.9 | 140.9 / 152.8 | 9.582 / 98.641 | 16.598 |
| history-distributed | 181.3 / 412.5 | 83.5 / 57.8 | 6.875 / 99.180 | 17.250 |
| history-hotset | 198.9 / 483.0 | 82.5 / 57.6 | 10.789 / 99.184 | 17.254 |
| history-recurring | 221.1 / 574.5 | 85.9 / 55.6 | 3.457 / 98.820 | 16.824 |

| History case | 100 checkpoints s, Sprig / LayerFS | 100 writes+commits s, Sprig / LayerFS | 100 restores+reads+cleanup s, Sprig / LayerFS |
|---|---:|---:|---:|
| history-distributed | 4.097 / 0.403 | 4.687 / 1.973 | 21.953 / 5.790 |
| history-hotset | 8.869 / 0.444 | 9.805 / 1.909 | 22.792 / 5.567 |
| history-recurring | 3.425 / 0.263 | 4.096 / 2.189 | 22.052 / 5.586 |

## Provenance

The original current-paired scripts are byte-identical between benchmark commits `931a57f` and `a4f0972`; the latter only added the independent Cargo files. Each archive retains original machine, compiler, binary/source/script hashes, raw per-step ledgers, kernel gates and measurements. No original raw result is rewritten.

[Archive checksums and original JSON hashes](data/release-20261024/fba02ad/manifest.json).
