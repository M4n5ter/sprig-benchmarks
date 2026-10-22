# Sprig comparative benchmarks

Independent, reproducible comparisons. No performance winner is claimed before verified same-machine measurements exist.

Pinned products:
- Sprig: `99715fa768ecfda7c4cb959b6306e86e0e0d47fb`
- LayerFS v1.0.0: `2aaf2552ce21154928b9f9c83582e41a637f5910`

All benchmarks use disposable synthetic data on temporary GitHub-hosted runners. LayerFS currently supports only its Disposable SQLite WAL/synchronous=OFF profile; Sprig synchronization remains enabled. These are different durability contracts and will be reported, not hidden.

Build smoke precedes benchmark execution. Full workspace timings include materialization or mount and first read, separately from metadata-only branch operations. Storage reporting must distinguish historical objects from full stores and native working trees. Repeated runs report raw samples and medians, with correctness checks outside timed intervals.

Official scenario targets: cross-file deduplication, content-defined chunk locality, workspace reuse, and deep branch history. The real DSH history corpus is not bundled in upstream; availability must be established before claiming identical data.

## Method and limits

This is a recipe-preserving benchmark port, not execution of the complete official benchmark harness. Fixture bytes, paths, modes and mtime are transcribed from the upstream frozen seed-1 recipe commit `d296981ace76fe751bebf00dee52818fe18a3eef`, explicitly referenced by v1.0.0 family definitions. All 41 tier-10 files were independently regenerated using a C SplitMix64 implementation and checked byte-for-byte and for metadata before scaling up.

The main run uses the official 100-file cross-file identical/unique/mixed cases, 100 CDC 4 KiB insertion variants plus their reference, and 100-commit distributed/hotset/recurring histories over the original 200-file, 1 MiB, 128-directory-deep tree.

History uses the original positional overwrites, fixed mtime, unchanged inode, and one checkpoint per edit. Shell write + file fsync and product checkpoint are timed separately. Every changed file is read back after every commit; all final files are verified; history record counts are checked. Historical snapshot remount verification and upstream internal canonical-object oracle are not currently claimed.

Fresh stores and fixed inputs are used for every sample. Inputs are setup-warm, not cold-cache. Product order alternates across three repetitions. The full-task timer is import + usable fork + a complete SHA-256 read. The first SDK mount includes sandbox startup; another fork + full read on its already-running sandbox is reported separately, so cold startup is not disguised as steady-state cost. CLI process versus in-process SDK overhead remains included and disclosed.

Import does not have identical output contracts: Sprig also creates a native directory; LayerFS creates stored history only until mounted. Metadata-only branch timings and complete workspace timings must not be conflated. Sprig native trees, retained generations, objects and manifests all count in data-store disk totals. LayerFS Store volume and SDK home count; immutable software/runtime images and binaries are excluded for both. Filesystem allocation is not exclusive physical extent accounting.

The official DSH corpus is referenced by upstream as an external local directory, with no verified public download or reconstruction source. No DSH result is claimed here.
