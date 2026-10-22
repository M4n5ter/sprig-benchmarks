# Sprig comparative benchmarks

Independent, reproducible comparisons. No performance winner is claimed before verified same-machine measurements exist.

Pinned products:
- Sprig: `99715fa768ecfda7c4cb959b6306e86e0e0d47fb`
- LayerFS v1.0.0: `2aaf2552ce21154928b9f9c83582e41a637f5910`

All benchmarks use disposable synthetic data on temporary GitHub-hosted runners. LayerFS currently supports only its Disposable SQLite WAL/synchronous=OFF profile; Sprig synchronization remains enabled. These are different durability contracts and will be reported, not hidden.

Build smoke precedes benchmark execution. Full workspace timings include materialization or mount and first read, separately from metadata-only branch operations. Storage reporting must distinguish historical objects from full stores and native working trees. Repeated runs report raw samples and medians, with correctness checks outside timed intervals.

Official scenario targets: cross-file deduplication, content-defined chunk locality, workspace reuse, and deep branch history. The real DSH history corpus is not bundled in upstream; availability must be established before claiming identical data.
