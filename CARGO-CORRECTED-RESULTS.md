# Combined schema-14 candidate: corrected real Cargo acceptance

Full [run 40167612813](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40167612813) and prerequisite [smoke 40167253184](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40167253184), 25 October 2026. Harness `0ab93379edbe89c8185714473fd551d2b451bfd5`; Sprig `2a01fe445b8057ca49b4e8284fdd5583bbb4185c` (schema 14, owned writable, default auto compression), LayerFS v1.1.0 `9f97a7ec95b662e9cb288704afa165feff132cfa`. At run preparation, Sprig main was `e2a86dc`/schema 10; this benchmark measured the fixed candidate above. Subsequent promotion is outside these measured runs.

**Correctness: all 4 smoke and 12 full records passed.** Full is three alternating pairs per incremental setting (0 and 1). Both products compiled, executed, edited, checkpointed and restored the real dependency-free Rust crate, retaining target and incremental caches. Full-tree bytes, types, modes, exact mtimes, symlinks and internal hardlink groups were verified before restored execution/rebuild. All 24 full-run no-op/restored rebuild observations showed Fresh for owned-cargo-check with no Compiling lines. All acknowledged revisions remained present; source and main were unchanged. Normal cleanup completed with zero remaining mounts/containers and no recorded cleanup errors.

Each Sprig sample verified exactly one live restored compiler at the primary space point, three live views/four retained generations/three foreground FUSE processes, and four total cooperative generation-scoped compiler sessions, all naturally exited and removed without uncertain acknowledgments. Both real projection and owned-writable kernel gates and production Rust tests passed in each job.

## Full-run medians (three samples each)

| Incremental | Product | Whole task s | Clean build s | No-op s | Edit build s | Product checkpoint ms | Product restore ms | Restored rebuild s | Runtime-ready growth MiB | Whole FS Used MiB |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | sprig-writable | 4.493 | 0.265 | 0.096 | 0.224 | 85.0 | 23.2 | 0.094 | 9.633 | 997.730 |
| 0 | layerfs | 1.868 | 0.153 | 0.031 | 0.125 | 67.5 | 4.4 | 0.032 | 21.332 | 1009.453 |
| 1 | sprig-writable | 4.684 | 0.300 | 0.094 | 0.265 | 104.5 | 26.2 | 0.097 | 9.965 | 998.055 |
| 1 | layerfs | 1.901 | 0.168 | 0.032 | 0.135 | 71.4 | 4.5 | 0.032 | 21.539 | 1009.707 |

Sprig session lifecycle is not hidden inside product-only timings. Direct-wall composites overlap underlying phase diagnostics; do not add them twice. Restore-to-compiler-ready excludes the subsequent oracle, while restore_verify includes both session startup and oracle, so those columns overlap:

| Incremental | Compiler quiesce + product checkpoint ms | Restore to compiler-ready ms | Restore-verification phase s (includes session start) |
|---:|---:|---:|---:|
| 0 | 428.7 | 219.9 | 0.354 |
| 1 | 434.7 | 224.6 | 0.362 |

## Prior failed acceptance preserved

The original full run 40166665918 failed on its first record during cooperative source-oracle shutdown; [failure report and raw evidence](CARGO-COMBINED-RESULTS.md) remain unchanged. The observed mismatch is consistent with Docker-running versus missing-/proc exit observation race, not proven retrospectively because that /proc value was not recorded. The harness-only revision logs observed identity and permits bounded read-only resampling solely after acknowledged cooperative shutdown when the original PID is missing; genuine running identity substitution still fails closed. No candidate, Cargo commands, full-tree/Fresh oracle, accounting boundary, security setting or CI resource limit changed. Corrected smoke was required before this new full run; old failure is not pooled into successful medians.

The corrected full run logged one pending Docker-running/missing-/proc exit snapshot in each of its six Sprig samples; every case then reached verified natural exit and normal removal. Corrected smoke logged no such pending snapshot. This exercises the repaired observation path on real CI without retrospectively proving the exact old failure cause.

## Interpretation and limits

- This corrected transport reuses an ordinary root compiler container within a generation and releases it cooperatively before owned checkpoint. LayerFS uses persistent SDK transport as UID501. All start/exec/exit/removal and oracles remain in whole-task wall. This is not a product-only before/after comparison to the previous per-command-container Cargo report. No added capabilities, relaxed security, forced/lazy unmount, signal/kill or forced removal is introduced.
- Both products use exactly the same immutable compiler image within each run: official Rust 1.90.0 and shared Ubuntu/linker environment. Image identities, software hashes, commands/stdout/stderr and raw oracle reports are preserved. Distinct runs can have distinct image identities; no cross-run speedup claim is made.
- Whole Btrfs Used is primary. Runtime-ready growth includes runtime/log/writable-layer growth, not exact application-only bytes. All persistent Docker/containerd roots, shared compiler image, target/cache, journals, retained generations and live restored compiler are charged. Three views remain live at space; normal teardown is later. Software/runtime setup is separately recorded, not subtracted from physical usage. RAM/tmpfs/kernel cache and external host executables are excluded.
- Sprig production synchronization remains enabled. LayerFS Disposable global WAL/OFF and workspace MEMORY/OFF/EXCLUSIVE are not equal crash durability. The tiny dependency-free crate does not represent a large dependency graph or universal Cargo performance. No cold-cache claim.

## Evidence

[Unchanged smoke artifact files](data/combined-20261025/cargo-smoke-corrected/) · [Unchanged full artifact files](data/combined-20261025/cargo-full-corrected/) · [Every-file SHA-256 manifest and immutable image IDs](data/combined-20261025/cargo-corrected-manifest.json) · [Full medians CSV](data/combined-20261025/cargo-corrected-summary.csv). Raw Python reports preserve exact integer nanoseconds; aggregate JavaScript diagnostics can round and are not oracle inputs. No old report or artifact was rewritten.

See [transport contract](feasibility/CARGO-TRANSPORT-CONTRACT.md) and [combined measurement scope](feasibility/COMBINED-MEASUREMENT-SCOPE.md). The transport contract’s scratch-validation status is historical; the exact real-run acceptance evidence is recorded here.

**Conclusion:** real Cargo restore correctness and cache reuse pass for both incremental settings. Sprig remains slower in complete measured task wall for both settings, despite lower live runtime-ready growth. No universal speed-and-storage victory is established.
