> Timing scope: import + fork + verified read is a sum of defined phases, not complete startup wall time. Sprig store initialization, software installation/build, and runtime setup are excluded; LayerFS project initialization includes its store initialization. CLI versus SDK and durability differences remain.

# Baseline results: 22 October 2026

> **Storage correction (22 October 2026):** the LayerFS figures below count only the store volume plus SDK home. They omit active workspace overlay databases and other writable-container state. They are **not complete active footprint** and must not support whole-product storage ratios or a storage winner. Raw measurements are preserved unchanged. See [scope correction and source evidence](STORAGE-CORRECTION.md). Timing and byte/history checks are separate measurements; this omission does not by itself invalidate them.

This baseline does **not** show Sprig beating LayerFS in its strong deduplication and history workloads. It establishes a measured starting point for optimization, not an equal-durability comparison.

- [Successful run and complete raw artifact](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39752100080).
- Harness: `e3cd5a68c52fa12b8b078f079352ff83678faf0f`.
- Sprig: `99715fa768ecfda7c4cb959b6306e86e0e0d47fb`; LayerFS v1.0.0: `2aaf2552ce21154928b9f9c83582e41a637f5910`.
- One Ubuntu 24.04 / ext4 GitHub-hosted x86-64 runner, 4 logical CPUs, AMD EPYC 9V74, 15 GiB reported RAM. Docker 29.8.2 with FUSE; the exact runtime-image digest and environment are included below.
- All 42 expected records passed, three fresh-store repetitions per product/case with alternating product order. All 18 history samples acknowledged 100 distinct commits, with every returned ID present in the final history.
- **Sprig keeps its default file/directory synchronization; LayerFS uses Disposable WAL / synchronous=OFF. These are not equal durability guarantees.** No crash-recovery equivalence or equal-durability speed win is established.

## Complete tasks, not just lazy fork

Milliseconds, median of three. Cold task = import + usable fork + full SHA-256 read. Warm task = another usable fork + full read on the already-running sandbox. Inputs are setup-warm, not cold-cache. Every full-read task covers every listed file. Standalone metadata-branch and bare-fork timings are in the raw summary and must not be confused with these tasks.

| Frozen upstream recipe | Sprig cold task | LayerFS cold task | Sprig warm task | LayerFS warm task |
|---|---:|---:|---:|---:|
| identical | 1,371.4 | 504.8 | 700.9 | 161.2 |
| unique | 2,041.5 | 2,208.8 | 780.1 | 556.9 |
| mixed | 1,876.2 | 1,824.1 | 986.2 | 470.8 |
| insert | 1,356.6 | 496.8 | 796.4 | 163.4 |
| history-distributed | 518.5 | 401.9 | 118.7 | 56.7 |
| history-hotset | 375.5 | 324.9 | 117.3 | 57.1 |
| history-recurring | 330.0 | 313.9 | 122.0 | 57.7 |

The first mount includes Docker sandbox startup; the warm task does not. Sprig CLI subprocess overhead and LayerFS in-process SDK / Docker transport overhead are included. Import outputs differ: Sprig immediately creates a native tree, while LayerFS stores history until a workspace is mounted. No overall winner should be inferred from a small difference in one cold-task median.

## Measured storage components (incomplete cross-product scope)

Allocated MiB (1 MiB = 1,048,576 bytes), median of three. Both measured workspaces are still usable at this point. All Sprig native trees, objects, manifests and retained recovery generations count. The LayerFS column counts only its Store volume plus SDK home and omits container workspace overlays and other writable-layer state. This is not a complete matched footprint. Immutable binaries/runtime images were excluded for both. Sprig import additionally materializes a main workspace; LayerFS project initialization does not require one. These recorded components do not establish whole-product storage costs or a storage winner.

| Recipe | Sprig active MiB | LayerFS store + home subset MiB |
|---|---:|---:|
| identical | 301.297 | 2.551 |
| unique | 402.961 | 202.809 |
| mixed | 377.289 | 152.254 |
| insert | 314.133 | 9.621 |
| history-distributed | 43.121 | 6.668 |
| history-hotset | 46.613 | 6.668 |
| history-recurring | 42.633 | 6.266 |

These are filesystem allocated blocks, not exclusive physical extents. This ext4 runner did not provide successful native reflinks. Post-SDK-close `fullStore` values are diagnostics with different lifecycles and are **not** used for this comparison. Native-tree-free retained-history storage is not claimed, because Sprig has no workspace unmount/purge operation; directories were not deleted to manufacture that result.

## One hundred history edits and checkpoints

Seconds, median of three complete 100-step samples. Edit + checkpoint is the median of each sample's summed write and commit intervals, not the sum of two medians. These intervals exclude independent readback/history assertions and are not total suite wall time. All three recipes start with the same 200-file, 1 MiB, 128-directory-deep tree.

| Recipe | Sprig edit + checkpoint | LayerFS edit + checkpoint | Sprig checkpoint only | LayerFS checkpoint only |
|---|---:|---:|---:|---:|
| history-distributed | 5.964 | 1.997 | 4.561 | 0.374 |
| history-hotset | 4.864 | 2.028 | 3.652 | 0.422 |
| history-recurring | 6.161 | 2.352 | 4.389 | 0.249 |

The writer performs a buffered positional overwrite, preserves the inode, fsyncs file data, and restores the original mtime. The fsync precedes mtime restoration, so write timing does not promise final-mtime durability. No synchronization is disabled in Sprig to improve its score.

### A small, evidence-backed optimization target

In distributed-history repetition 0, Sprig allocated 25,333,760 bytes to state backups and 11,599,872 bytes to full revision manifests, versus 2,035,712 bytes to content objects and 5,988,352 bytes to native trees. Repeated metadata dominates this workload. Lossless representation improvements and redundant synchronization analysis are candidates; deleting recovery generations, weakening capture correctness, or reducing durability would not be a fair win.

## Correctness and boundaries

Both products passed the once-per-product same-file non-overlapping text merge smoke, preserved the input branches, and refused overlapping edits. These are correctness checks, not three-repeat merge-speed measurements. LayerFS supports real same-file three-way text merge; it is not treated as a trivial same-file-conflict-only baseline.

Listed-file SHA-256, changed-file readback after every checkpoint, and acknowledged history membership passed. Extra paths, directory metadata, mode/mtime fidelity, historical snapshot remounts, crash recovery and a complete upstream internal-object oracle are **not** verified here.

The fixtures are a recipe-preserving port of upstream frozen seed-1 commit `d296981ace76fe751bebf00dee52818fe18a3eef`, not execution of the entire official harness. The separate DSH real-history corpus has no verified public download/reconstruction source and is not claimed. Earlier diagnostic runs contained a one-byte `dd` writer and asymmetric diagnostic reads. They are retained in Actions for diagnosis and excluded from these results.

## Raw measurements

- [All 42 raw records](measurements/2026-10-22-baseline/comparison.json), [all 1,800 per-step history samples](measurements/2026-10-22-baseline/history-samples.jsonl).
- [Summary with every raw sample, median, minimum and maximum](measurements/2026-10-22-baseline/summary.json), [median CSV](measurements/2026-10-22-baseline/summary.csv).
- [Environment](measurements/2026-10-22-baseline/environment.txt), [fixture hashes](measurements/2026-10-22-baseline/fixture-generation.txt), [runtime image](measurements/2026-10-22-baseline/runtime-image.json), [file SHA-256 manifest](measurements/2026-10-22-baseline/sha256.json).

Recompute the summary with `python3 summarize.py measurements/2026-10-22-baseline/comparison.json`.
