# Buffer reuse verification: 22 October 2026

> **Storage correction (22 October 2026):** the LayerFS figures below count only the store volume plus SDK home. They omit active workspace overlay databases and other writable-container state. They are **not complete active footprint** and must not support whole-product storage ratios or a storage winner. Raw measurements are preserved unchanged. See [scope correction and source evidence](STORAGE-CORRECTION.md). Timing and byte/history checks are separate measurements; this omission does not by itself invalidate them.

**The result has not changed:** Sprig is faster on the complete unique/mixed tasks in this paired run, but still loses identical-content, small-insertion and deep-history comparisons. This is not a speed-and-storage victory over LayerFS.

- Sprig `22e6e4c289be67b78d39a7eae157bfa3219d23a4`, LayerFS `2aaf2552ce21154928b9f9c83582e41a637f5910`.
- [Successful run 39763576668](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39763576668), benchmark pin commit `45d7ddf72d14cdd18d01cceb68004ac29aaf2123`.
- All seven cases × three repetitions × two products passed: 42 records, 1,800 verified distinct-in-history checkpoint IDs, and both products' same-file merge/conflict smoke.
- Fixture, operation and oracle scripts remain byte-identical to frozen harness `e3cd5a68c52fa12b8b078f079352ff83678faf0f`. Fresh stores, alternating product order, unchanged data and commands.
- Ubuntu 24.04, ext4, AMD EPYC 7763, four logical CPUs, 15 GiB reported RAM. This is a **different runner instance** from earlier runs, despite matching the previous CPU model. Cross-run latency changes are not isolated causal measurements of this small optimization.
- The production change reuses a 256 KiB buffer within one capture. It does not cache file contents, mtimes, validation results or old captures; no durability/configuration relaxation was introduced.

## Paired complete-task results

Median of three, milliseconds. Cold means import + usable fork + full SHA-256 read with first sandbox startup; warm means another usable fork + full read. Generated inputs are setup-warm, not cold-cache. Both products run the same full-read shell command; their CLI/SDK transports differ and remain included.

| Recipe | Sprig cold | LayerFS cold | Sprig warm | LayerFS warm | Sprig active MiB | LayerFS store + home subset MiB |
|---|---:|---:|---:|---:|---:|---:|
| identical | 627.304 | 436.007 | 358.802 | 202.297 | 301.160 | 2.551 |
| unique | 1189.630 | 1712.743 | 361.133 | 680.650 | 402.863 | 202.809 |
| mixed | 1033.048 | 1291.671 | 353.695 | 567.549 | 377.191 | 152.270 |
| insert | 692.716 | 517.454 | 365.634 | 204.339 | 313.980 | 9.629 |
| history-distributed | 339.007 | 315.070 | 149.488 | 76.985 | 12.293 | 6.668 |
| history-hotset | 350.128 | 327.364 | 145.755 | 78.189 | 15.785 | 6.652 |
| history-recurring | 372.513 | 314.551 | 156.247 | 76.186 | 11.805 | 6.262 |

The Sprig measurement counts its retained store representations and recovery generations, with both measured workspaces still usable. The LayerFS measurement omits workspace overlay databases and other container-writable state, so this is not a matched complete footprint. Sprig import also materializes main. Ext4 clone falls back to copy; allocated blocks are not exclusive physical extent usage. Software/runtime images are excluded for both.

## One hundred edits and checkpoints

Seconds, median of per-repetition totals. Independent byte/history oracle time is excluded.

| Recipe | Sprig edit + checkpoint | LayerFS edit + checkpoint | Sprig checkpoint only | LayerFS checkpoint only |
|---|---:|---:|---:|---:|
| history-distributed | 4.677 | 2.472 | 3.268 | 0.452 |
| history-hotset | 4.826 | 2.496 | 3.358 | 0.514 |
| history-recurring | 5.328 | 2.905 | 3.466 | 0.291 |

Sprig checkpoint includes an entire CLI process, state loading, full capture, durable persistence and exit. LayerFS uses an in-process SDK call to a running service and tracks writes. LayerFS remains Disposable WAL / synchronous=OFF; Sprig retains default synchronization. These are practical default-interface measurements, **not equal-durability or isolated theoretical algorithm comparisons**. File-data fsync in the edit command precedes fixed-mtime restoration.

## Limits and raw evidence

The oracle checks listed-file bytes, changed-file readback, baseline-plus-100 history and membership of every distinct returned commit ID. It does not claim full directory/mode/mtime/extra-path, historical-remount or crash-recovery equivalence. Merge is one correctness smoke, not a repeated speed benchmark. The unavailable official DSH corpus is not claimed.

- [Raw records](measurements/2026-10-22-22e6e4c/comparison.json), [all 1,800 steps](measurements/2026-10-22-22e6e4c/history-samples.jsonl).
- [All samples/minimum/maximum/median](measurements/2026-10-22-22e6e4c/summary.json), [median CSV](measurements/2026-10-22-22e6e4c/summary.csv), [environment](measurements/2026-10-22-22e6e4c/environment.txt), [hash manifest](measurements/2026-10-22-22e6e4c/sha256.json).
- Earlier [uncompressed baseline](RESULTS.md) and [metadata-compression run](OPTIMIZATION-RESULTS.md) remain unchanged.
- A separately labeled [Btrfs capability smoke](feasibility/README.md) explores native snapshot infrastructure. It is not this production product or a comparative win.
