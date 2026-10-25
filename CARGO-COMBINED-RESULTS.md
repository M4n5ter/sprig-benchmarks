# Combined schema-14 candidate: Cargo acceptance failure preserved

**Full acceptance did not pass.** [Full run 40166665918](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40166665918) failed on its first Sprig writable sample (round 0, CARGO_INCREMENTAL=0), after the earlier [smoke run 40166288627](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40166288627) passed all four samples. Of 12 planned full records, one failed and 11 were never attempted; there is no complete full pair or valid full timing/space comparison.

Frozen Sprig `2a01fe445b8057ca49b4e8284fdd5583bbb4185c`/schema 14; comparator LayerFS v1.1.0 `9f97a7ec95b662e9cb288704afa165feff132cfa`; harness `4383a456cd8f26dbbfe4047be4a40d669f1adb9d`. The failed run predates the later harness-only repair; no candidate change, merge, forced cleanup, security or resource-limit change occurred.

## Exact failing stage

Production tests/build, both real kernel lifecycle gates, comparator build and shared compiler image setup passed. The failing sample completed clean build/execute, no-op, source edit/rebuild/execute, checkpoint, full restored tree oracle, restored execute/rebuild/execute. Both no-op and restored rebuild had Fresh owned-cargo-check and no Compiling lines.

Failure arose during retained_input_verify, when closing the short-lived read-only source_unchanged oracle container, not from a Cargo compiler or restored-tree mismatch. `cargo_transport_sample.py:163`, called from close_session → observe_natural_exit, raised `cooperative PID1 identity changed`. Docker inspection reported Running=true, PID 10867 and StartedAt `2026-10-25T05:50:11.569371005Z`, matching the recorded PID/StartedAt; the recorded original process startTimeTicks was 38116. The additional live /proc identity result is not captured in the failure, so its exact value is unknown.

**Likely diagnosis, not proven:** a normal-exit observation race: Docker’s Running snapshot can become stale before the subsequent /proc read, which then sees the PID already gone (or reused). The adapter treats any mismatch as a hard identity violation even in the post-marker natural-exit observation loop. This explanation is consistent with the failure location and unchanged Docker identity, but does not establish the actual /proc outcome.

The adapter failed closed. It recorded two retained compiler containers, blocked normal product unmount, and runtime relocation refused existing containers. No primary active-space measurement was taken. Failure/cleanup evidence was preserved; no failed sample is counted as success or selectively removed. This artifact does not prove successful runner-level disposal of retained resources.

## Smoke correctness and single-sample measurements

Smoke 4/4 covered incremental 0 and 1 for both products, full restored bytes/types/modes/mtimes/symlinks/internal hardlink groups, unchanged source/main, acknowledged revisions, Fresh no-op/restored rebuild, and normal cleanup with no remaining mounts or containers. Each Sprig smoke record retained one live restored compiler, three views/four product generations/three foreground FUSE processes at space; all four generation-scoped compiler sessions naturally exited and were normally removed.

These are **one sample per cell**, not full medians or repeatable speedup evidence.

| Incremental | Product | Complete wall s | Runtime-ready growth MiB | Whole FS Used MiB |
|---:|---|---:|---:|---:|
| 0 | sprig-writable | 4.898 | 9.676 | 997.871 |
| 0 | layerfs | 2.071 | 21.395 | 1009.480 |
| 1 | sprig-writable | 4.913 | 9.871 | 998.188 |
| 1 | layerfs | 2.051 | 21.508 | 1009.414 |

Sprig smoke remains slower in measured end-to-end wall despite smaller runtime-ready growth. This is not a universal speed-and-storage victory.

## Boundaries and next repair proposal

Both products use one identical immutable compiler/runtime image within a run (official Rust 1.90.0). Sprig ordinary root Docker generation-scoped sessions differ from LayerFS UID501 persistent SDK transport; all startup/exec/cooperative exit/removal remain in task wall. Earlier per-command-container Cargo timings are not directly comparable. No added capabilities/security relaxation. Sprig synchronization differs from Disposable WAL/OFF + workspace MEMORY/OFF/EXCLUSIVE. This tiny dependency-free crate does not represent a large dependency graph.

Whole Btrfs Used includes shared compiler image, Docker/containerd roots, layers/logs, target/cache, journals and retained product generations at the live point. Runtime-ready growth is not exact app-only usage. Software/runtime setup is separate; RAM/tmpfs/cache/external host executables are excluded. Product checkpoint/restore and compiler-ready composite intervals overlap and must not be summed twice.

Harness-only repair reviewed and published separately as `0ab93379edbe89c8185714473fd551d2b451bfd5`; this failed run is not reclassified. Repair contract: distinguish post-marker natural-exit observation from required-running checks; retain exact container/name/image/label/bind/restart/PID/StartedAt validation, and only resample read-only state within the existing deadline if the original /proc identity disappears. Require a subsequent exact-container exited/zero-exit/PID-zero acknowledgment, successful wait, and original PID identity gone before normal removal. Never accept identity substitution, retry uncertain mutations, force cleanup, change the candidate, weaken full-tree/Fresh checks, or omit costs. Add race and PID-reuse regression cases. Corrected acceptance is a separate run series; this report retains only the original smoke and failed full.

## Unchanged evidence

[Smoke artifact files](data/combined-20261025/cargo-smoke/) · [Failed full artifact files](data/combined-20261025/cargo-full-failed/) · [Every-file SHA-256 manifest](data/combined-20261025/cargo-manifest.json). The downloaded raw aggregate, exact per-product report, independent JSONL ledger, source/script/binary hashes, environment and kernel gates are preserved without edits. Raw Python oracle nanoseconds are authoritative; JavaScript diagnostic copies may round. Paths to logs inside the failed measured filesystem are not a claim that those external files were included in the uploaded artifact.

[Transport contract](feasibility/CARGO-TRANSPORT-CONTRACT.md) · [Combined scope](feasibility/COMBINED-MEASUREMENT-SCOPE.md).
