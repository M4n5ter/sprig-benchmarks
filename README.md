**Same-runner decision (23 October 2026):** [direct baseline/candidate A/B](WORKSPACE-SYNC-AB-RESULTS.md) passed 80 samples and 8,000 readbacks but demonstrated no checkpoint benefit. Candidate remains unmerged; earlier cross-run changes are not evidence of a speedup.

**Candidate verification (23 October 2026):** [workspace synchronization scheduling](WORKSPACE-SYNC-RESULTS.md), both backends passed all paired samples and historical readbacks; overall target still unmet, candidate not merged to main.

**Current production results (23 October 2026):** [native and projection CLI comparison](PRODUCTION-CLI-RESULTS.md), pinned to Sprig `46f9634`, passed 84 paired records and 3,600 historical readbacks. The speed + storage target remains unmet. This new series includes initialization, three active workspaces and whole-filesystem/runtime accounting.

**The material below describes preserved older experimental series.** Its pins, omitted costs and limitations do not describe the new production series; use the report above and its measurement contract for current results.

[CAS + OverlayFS kernel semantics smoke](CAS-OVERLAY-FEASIBILITY.md) passed; checkpoint integration and performance remain unproven.

[Path-only Btrfs rerun](BTRFS-RELPATH-RESULTS.md): verified, still short of the speed/storage/feature target.

[Independent native Btrfs feasibility results](BTRFS-FEASIBILITY-RESULTS.md): warm reads/forks improve, but import/checkpoint targets and feature parity are not met.

> Timing scope: import + fork + verified read is a sum of defined phases, not complete startup wall time. Sprig store initialization, software installation/build, and runtime setup are excluded; LayerFS project initialization includes its store initialization. CLI versus SDK and durability differences remain.

# Sprig comparative benchmarks

> **Storage correction (22 October 2026):** the LayerFS figures below count only the store volume plus SDK home. They omit active workspace overlay databases and other writable-container state. They are **not complete active footprint** and must not support whole-product storage ratios or a storage winner. Raw measurements are preserved unchanged. See [scope correction and source evidence](STORAGE-CORRECTION.md). Timing and byte/history checks are separate measurements; this omission does not by itself invalidate them.

Independent, reproducible comparisons. [Latest buffer verification](BUFFER-RESULTS.md), [metadata optimization results](OPTIMIZATION-RESULTS.md) and [preserved baseline](RESULTS.md) include complete raw measurements. No equal-durability comparison or overall Sprig win is claimed.

Pinned products:
- Sprig: `22e6e4c289be67b78d39a7eae157bfa3219d23a4`
- LayerFS v1.0.0: `2aaf2552ce21154928b9f9c83582e41a637f5910`

All benchmarks use disposable synthetic data on temporary GitHub-hosted runners. LayerFS currently supports only its Disposable SQLite WAL/synchronous=OFF profile; Sprig synchronization remains enabled. These are different durability contracts and will be reported, not hidden.

Build smoke precedes benchmark execution. Full workspace timings include materialization or mount and first read, separately from metadata-only branch operations. Storage reporting must distinguish historical objects from full stores and native working trees. Repeated runs report raw samples and medians, with independent correctness assertions outside timed intervals; the complete SHA-256 read task itself is timed.

Official scenario targets: cross-file deduplication, content-defined chunk locality, workspace reuse, and deep branch history. The real DSH history corpus is not bundled in upstream; availability must be established before claiming identical data.

## Method and limits

This is a recipe-preserving benchmark port, not execution of the complete official benchmark harness. Fixture bytes, paths, modes and mtime are transcribed from the upstream frozen seed-1 recipe commit `d296981ace76fe751bebf00dee52818fe18a3eef`, explicitly referenced by v1.0.0 family definitions. All 41 tier-10 files were independently regenerated using a C SplitMix64 implementation and checked byte-for-byte and for metadata before scaling up.

The main run uses the official 100-file cross-file identical/unique/mixed cases, 100 CDC 4 KiB insertion variants plus their reference, and 100-commit distributed/hotset/recurring histories over the original 200-file, 1 MiB, 128-directory-deep tree.

History uses the original positional overwrites, fixed mtime, unchanged inode, and one checkpoint per edit. Shell write + file fsync and product checkpoint are timed separately. Every changed file is read back after every commit; all final files are verified; history grows by exactly 100 records and every distinct returned checkpoint ID must be present. Per-step raw samples are appended to JSONL outside timed intervals. A run is complete only when all 42 expected product/case/repetition records pass. Historical snapshot remount verification and upstream internal canonical-object oracle are not currently claimed.

Fresh stores and fixed inputs are used for every sample. Inputs are setup-warm, not cold-cache. Product order alternates across three repetitions. The full-task timer is import + usable fork + a complete SHA-256 read. The first SDK mount includes sandbox startup; another fork + full read on its already-running sandbox is reported separately, so cold startup is not disguised as steady-state cost. CLI process versus in-process SDK overhead remains included and disclosed.

Import does not have identical output contracts: Sprig also creates a native directory; LayerFS creates stored history only until mounted. Metadata-only branch timings and complete workspace timings must not be conflated. Sprig native trees, retained generations, objects and manifests all count in data-store disk totals. LayerFS Store volume and SDK home count; immutable software/runtime images and binaries are excluded for both. Filesystem allocation is not exclusive physical extent accounting.

The official DSH corpus is referenced by upstream as an external local directory, with no verified public download or reconstruction source. No DSH result is claimed here.

The matched footprint is `activeStore`: both measured workspaces remain usable until all timing/history work is finished. Sprig also retains its natively materialized import workspace. `fullStore` after SDK close and daemon stop is a diagnostic with different lifecycle, not an apples-to-apples storage ratio. Sprig does not currently offer workspace unmount/purge, so a native-tree-free retained-history tier is not fabricated by deleting directories.

There are no one-sided full reads, recursive disk scans or operator stats between timed phases. Both products first run the same separate metadata-branch probe; the subsequent usable-fork timer includes its own branch creation. The history writer uses one buffered positional overwrite (64 KiB `dd` blocks with byte offsets), preserves the inode, fsyncs file data, then restores the fixed mtime. This does not promise final mtime durability, and default product durability contracts remain different.

Correctness here means listed-file SHA-256 and acknowledged-history smoke checks, not the upstream complete oracle: extra paths, directory metadata, modes, mtime and historical snapshot remounts are not verified. Merge checks run once as a correctness smoke, not as a repeated merge-speed result.
