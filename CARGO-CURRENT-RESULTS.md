# Latest production: tiny real Cargo lifecycle

[Completed run 40054772895](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40054772895), 24 October 2026. **12/12 samples passed**: three alternating pairs for each CARGO_INCREMENTAL setting. Sprig `e38225e1e1160e8de90aa911d6f1740bef93bacc`, owned-writable backend, default auto compression; LayerFS v1.1.0 `9f97a7ec95b662e9cb288704afa165feff132cfa`.

Both products actually compiled, edited, checkpointed and restored the complete build tree. All files, target/cache contents, ordinary modes, exact mtimes, symlink targets and internal hardlink groups matched before restored execution or rebuild. Both no-op and restored rebuilds reported **Fresh in all 12 samples**, without pruning or timestamp normalization. This is a small dependency-free Rust crate, **not a large real-world dependency graph**.

## What these timings mean

Both sides use the same immutable Ubuntu/compiler image and actual Rust 1.90.0 toolchain. Sprig commands run in a new ordinary root Docker container per command, binding its live view at /work; LayerFS uses persistent Sandbox SDK exec as UID501 at /workspaces/N. All container startup/removal and SDK transport costs are included. This makes tiny command timings heavily orchestration-bound: **do not interpret the wall-time gap as pure filesystem speed or an optimal Sprig integration**. The per-command Docker wrapper is this experiment's same-image compiler transport, not a Sprig dependency: ordinary host Cargo can run directly in its mounted workspace. No capabilities, security policy or product synchronization were changed to force equality.

Sprig production durability differs from LayerFS Disposable WAL/OFF + workspace MEMORY/OFF. Full-task wall includes initialization, Cargo commands, strict oracles, accounting and ordinary cleanup. Software installation and runtime relocation/image loading are recorded separately. checkpoint includes CLI/SDK call plus acknowledgment/readiness, not only a hash operation.

All numbers below are medians of three samples. Smaller reported storage is not a claim of equal durability or exact app-only savings.

| Incremental | Product | Complete wall s | Clean build s | No-op build s | Checkpoint ms | Restore ms | Restored rebuild s | Live runtime-ready delta MiB | Whole FS Used MiB |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | sprig-writable | 5.478 | 0.457 | 0.294 | 109.9 | 25.2 | 0.296 | 9.008 | 997.254 |
| 0 | layerfs | 1.901 | 0.160 | 0.032 | 67.1 | 4.7 | 0.034 | 21.332 | 1009.492 |
| 1 | sprig-writable | 5.442 | 0.484 | 0.278 | 110.4 | 21.9 | 0.286 | 9.371 | 997.586 |
| 1 | layerfs | 1.909 | 0.169 | 0.032 | 71.8 | 4.5 | 0.033 | 21.539 | 1009.707 |

## Physical space and preserved evidence

Each product gets a separate fresh 8 GiB Btrfs filesystem (Data SINGLE, Metadata DUP) on the same runner. The shared compiler/runtime image accounts for roughly 988 MiB before the workload. Docker/containerd roots, image layers, writable layers, volumes, stores, histories, all target/cache files and diagnostic logs are inside the measured filesystem. The live point retains three workspaces, plus the previous Sprig owned generation. No target/cache/metadata exclusions are made. RAM/tmpfs/kernel caches and outside-image host executables are not measured.

The runtime-ready delta includes runtime growth and diagnostic logs and is not exact application-only bytes. It must not be confused with a claimed 2× or 3× physical saving of the whole deployment. Normal cleanup occurs after the live snapshot; post-teardown overlay removal is never substituted for live usage. All synthetic images were detached and disposed of only after complete durable raw evidence and successful normal cleanup.

- [Complete original artifact](data/release-20261024/e38225e-cargo/cargo-40054772895-full-artifact.tar.gz)
- [Summary CSV](data/release-20261024/e38225e-cargo/summary.csv)
- [Checksums/provenance](data/release-20261024/e38225e-cargo/manifest.json)
- [Full measurement boundaries](feasibility/CARGO-MEASUREMENT-BOUNDARIES.md)
- [Shared software image contract](feasibility/CARGO-IMAGE-CONTRACT.md)

Raw Python reports preserve exact integer nanoseconds. LayerFS raw oracle text is authoritative; structured copies use decimal strings. Aggregate JavaScript diagnostic copies of Python timestamps may round and are never fed back into verification. Original downloaded raw is archived unchanged.

**Conclusion:** genuine Cargo checkpoint/restore and cache reuse work in both implementations on this tiny workload. Sprig’s measured live runtime increment is smaller here, but its measured checkpoint and chosen end-to-end orchestration are slower. This does not meet a universal speed-plus-storage victory target.
