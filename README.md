# Sprig comparative benchmarks

Independent, reproducible comparisons. [Latest optimization results](OPTIMIZATION-RESULTS.md) and [preserved baseline](RESULTS.md) include complete raw measurements. No equal-durability comparison or overall Sprig win is claimed.

Pinned products:
- Sprig: `aab4985b03e245dabca21fc9eb8769f66896edd0`
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
