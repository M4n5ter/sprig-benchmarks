# Combined schema-14 candidate: two distinct protocols

Fixed Sprig candidate `2a01fe445b8057ca49b4e8284fdd5583bbb4185c` includes the previously separately measured lifecycle and native-fork work plus schema-13 path-stable manifest pages and schema-14 shared observation references. Comparator stays latest formal release LayerFS v1.1.0 `9f97a7ec95b662e9cb288704afa165feff132cfa`; its newer main has unreleased changes and is not silently substituted. Both use fresh stores. Product observation budgets, durability and default-auto compression remain at defaults; no GC/pruning is added.

## Seven frozen workloads

combined-paired.yml/combined_compare.mjs preserve the earlier seven-scene operation order and primary footprint/timing definitions. combined_sample.py wraps the byte-unchanged latest_sample.py and reuses the previously reviewed retained-count/second-space checks from lifecycle_sample.py. It does not replace the measured workload or call private product APIs. New observations/ files are automatically inside whole-filesystem Used.

A separately named postHistorySpace and postHistoryFilesystemUsedDeltaBytes is sampled for both products after all original timed restore/read/normal-cleanup tasks and unchanged-source/view checks, before closing the three original views. The original activeSpace before historical restoration remains the primary comparable metric. No new component scan is inserted into timed stages. Sprig checks exactly 103 native/projection or 203 writable generations after history100. Comparator retains its history branches and normal SDK storage lifecycle. These are actual product API outcomes, not a claim of identical storage representation.

Each backend smoke has 4 records/200 historical readbacks. Full has 42 records/1,800 readbacks (seven cases × three repetitions × both products). Different backend runners are separate machines. Whole-FS/runtime incremental boundaries, CLI-versus-SDK costs and unequal Sprig synchronization versus Disposable WAL/OFF + workspace MEMORY/OFF remain as previously disclosed. No cold-cache, RAM-equivalence or crash-equivalence claim.

## Separate Cargo transport revision

cargo-transport.yml/cargo_transport_compare.mjs use the reviewed cargo_transport_sample.py and frozen cargo_layerfs.mjs, fixture, toolchain image and full-tree oracle. See CARGO-TRANSPORT-CONTRACT.md for cooperative generation-scoped sessions and failure handling. All original application commands/target/cache content remain, but compiler transport is deliberately changed from per-command startup to per-generation sessions. Therefore new wall time cannot establish a product-only speedup over the old Cargo report.

Exactly one restored Sprig compiler session is live at primary space, as the LayerFS sandbox remains live; startup/removal, writable layers, logs, Docker/containerd roots and all product generations are charged. No added capabilities or security settings. Before owned checkpoint the old compiler exits cooperatively and is observed gone; only then may the product unmount/replace its generation. Full restored bytes/modes/mtimes/hardlinks are checked before executable/rebuild. Both no-op and restored rebuilds must actually show Fresh for owned-cargo-check and no Compiling lines.

Product checkpoint and restore timers are separate from the direct-wall compiler-quiesce-plus-checkpoint and restore-to-compiler-ready composites; composites overlap underlying phase diagnostics and must not be summed twice. Whole task wall is authoritative. UID/root versus501 and SDK/Docker-exec differences remain disclosed. Shared image/toolchain identity is exact within a run; software setup is separately recorded, not removed from footprint.

Smoke is 4 records (incremental0/1 × both products); full is 12 records (three alternating pairs for each incremental setting). This remains a small dependency-free real Cargo project, not a large dependency-graph workload. Old reports/raw are never rewritten. Static/mocked review is not real-kernel validation: release requires actual smoke before full.
