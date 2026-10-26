# Current-main Sprig versus current-main LayerFS: fixed eight-sample Cargo protocol

This is a new direct comparison, not a relabeling of Sprig-only optimizations or
of the historical released-LayerFS run. No performance result is implied by this
protocol. The separate four-sample writable diagnostic canary remains available
but is **not dispatched** while this requested direct comparison takes priority.

## Immutable selections

| Product | Frozen revision | Selection |
|---|---|---|
| Sprig | `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` | current `main` |
| LayerFS | `ad78914e36b258b360daf13aec164b5655814689` | current **unreleased `main`** |

At selection time LayerFS's latest formal release is still v1.1.0, at
`9f97a7ec95b662e9cb288704afa165feff132cfa`, eleven commits behind this main pin.
It is **not** the version measured here. The changed native-addon temporary
workspace naming is not assumed performance-equivalent merely because core
sources are unchanged. Historical release results stay unchanged and unpooled.

The job reads both live main refs before product builds and requires these exact
pins; if either moved, it stops rather than silently measuring another revision.
The operator must review a new selection before any replacement run. All checkouts
remain detached at immutable revisions. The identity manifest binds canonical
source paths, Sprig ELF, LayerFS daemon ELF, SDK entry file and native addon bytes;
HEAD, clean source worktrees, paths and hashes are checked before and after every
sample. Complete tracked source/build hashes accompany the artifacts.

The existing LayerFS adapter defaults to its historical release pin. Only the
explicit new `latestDirect` source schema accepts this fixed main revision; an
arbitrary source SHA, old release presented as latest, or mixed own-AB identity
is rejected. No workload, persistence setting or SDK transport is changed.

## Finite order and budget

One existing `ubuntu-24.04` job, registered `stress-ab.yml`, manual dispatch only:

| Mode | Pair 0 | Pair 1 |
|---|---|---|
| incremental0 | Sprig, LayerFS | LayerFS, Sprig |
| incremental1 | LayerFS, Sprig | Sprig, LayerFS |

Exactly eight product samples, each on a fresh symmetric **4 GiB Btrfs** image;
only one sample/runtime at a time. All four incremental0 samples must pass before
incremental1; the second mode binds the exact first report hash, same identities,
compiler image, fixture and shared job deadline. Legacy direct1/3-round and
Sprig-only1/4-round guards are not widened to accept this new schema.

The unchanged **45-minute job** and setup-inclusive **40-minute admission
budget** apply. Both pre-runtime and pre-sampler admissions retain at least
180 seconds of work plus300 seconds for normal cleanup. Cargo uses jobs2; the
same common Rust/Cargo1.90.0 image is built once, recorded by immutable image ID,
and used for both products/modes. Product build toolchains are separately
recorded (Sprig stable; LayerFS1.85.1), not presented as the workload compiler.
The existing external inc0/inc1 capacity pilots remain setup only, not product
measurements or reusable target caches. There is no8GiB expansion or automatic
retry. Roughly10–15 minutes is a planning estimate, not a guaranteed duration.

## Correctness and evidence before timings

The frozen DAG16v2 workload and shared command protocol are unchanged:
`cargo build --offline --locked --verbose --workspace --jobs 2`; all17 packages
must compile for clean/edited builds, and all17 must be Fresh with no compilation
for no-op/restored rebuilds. Executable outputs269→3400, generated build values
1→2, source/original-main invariance and acknowledged checkpoint/history are
required. Before restored execution, the complete tree must match paths, bytes,
modes, exact nanosecond mtimes, symlinks and internal hardlink groups; no target,
cache, log, history or slow record is excluded.

Standalone raw reports and every declared archive remain authoritative. LayerFS
represents structured nanoseconds as decimal strings; the audit compares the
complete archived raw snapshot using exact Python integers, never JS-rounded
embedded oracles. Sprig uses the existing full raw validator. All lifecycle JSONL
and command stdout/stderr are preserved on failure as well as success. The new
summary fails closed unless all eight raw samples, order, shared identities,
previous-mode hash, cleanup and full archives pass. Failed/absent/not-run samples
remain visible; no partial successful subset becomes a complete comparison.

A first capacity, budget, correctness, uncertain-exec, ordinary-cleanup or archive
failure stops the series. No force/lazy unmount, signal/fault injection, retry or
old fault gate is introduced. Ordinary product unit tests and the actual positive
Cargo oracle gates are used; historical kernel-fault workflow steps stay inactive.
Both trace environments must be absent.

## Interpretation

Report each pair and order, whole sampler wall, common individual phases, runtime
setup separately, and whole active filesystem Used. Retain every regression and
range. Two pairs per mode are small runner-local observations, not independent
multi-host trials; no stable p95/p99, significance or universal winner claim.
Sprig-only quiesce/checkpoint and restore-to-ready composites remain explicitly
unmatched. Nested/composite timers are not summed or subtracted.

Sprig's generation-scoped root Docker CLI transport and LayerFS's persistent
UID501 SDK transport differ and remain charged. LayerFS uses its required
Disposable/WAL/synchronous=OFF Store and separate MEMORY/OFF workspace overlays;
Sprig retains its own sync/fsync behavior. This is **not equal durability**.
Whole Used includes the compiler image, runtime, target/cache, retained views,
history and logs; runtime bytes are not subtracted. No comparison is pooled with
older release, tiny-Cargo, Sprig-only pressure or instrumented diagnostics.
