# Current-main Sprig versus LayerFS caebd: fixed eight-sample Cargo protocol v2

This is a locally prepared new direct series. No build or measurement is implied
by this protocol; publication/dispatch needs a separate root review and GO. The
completed36-sample Sprig4eb/104/5ef run and historical4eb/ad789 direct result remain
unchanged. This is not an experimental-candidate promotion or a LayerFS source
change. The separate writable diagnostic canary is not dispatched.

## Immutable selections

| Product | Frozen revision | Selection |
|---|---|---|
| Sprig | `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` | current `main` |
| LayerFS | `caebd268dc376865e964f33f78047f7918763190` | current **unreleased `main`** |

LayerFS main was verified at this exact revision on2026-10-27 at06:46UTC.
The previously measured `ad78914e36b258b360daf13aec164b5655814689` is54 commits
behind this selection. Source changes include the root Cargo workspace and
engine/API reorganization and real behavior changes; performance and the old
Native-history EOF outcome are not assumed equivalent or repaired. Old source
identities, raw results and failures remain historical and unpooled.

The job records both observed live main refs and their match/difference/unavailable
status against the fixed selections before builds. Tip movement or observation
failure does not block the selected comparison and never silently changes a pin.
Results are labeled current-at-selection fixed revisions, not latest-at-finish
when a tip differs or cannot be observed. All checkouts remain detached at the
immutable reviewed revisions; actual checkout/ELF/source identity checks still
fail closed. A future replacement source selection needs its own review. The identity manifest binds canonical
source paths, Sprig ELF, LayerFS daemon ELF, SDK entry file and native addon bytes;
HEAD, clean source worktrees, paths and hashes are checked before and after every
sample. Complete tracked source/build hashes accompany the artifacts.

The existing LayerFS adapter defaults to its historical release pin. Only the
explicit v2 `latestDirect` source schema accepts this fixed main revision; an
arbitrary source SHA, old release presented as latest, or mixed own-AB identity
is rejected. No workload, persistence setting or SDK transport is changed.

## Concrete caebd compatibility migration

The product source is unchanged. Builds run from the LayerFS repository root:
root `Cargo.toml` / `Cargo.lock` cover `core/crates/*` and `engine/crates/*`;
`engine/vendor/fuser-0.18.0` is the existing pinned patch. Sparse checkout and
source hashes cover those paths plus `api` and `.cargo`, including root manifests.
The checked-in `api/scripts/build-native.mjs` invokes Cargo1.85.1 explicitly,
offline/locked/release for `layerfs-node`. The ordinary daemon build uses that
same toolchain and root manifest, with jobs2 and no feature/profile override.
Canonical outputs are `target/release/layerfs-daemon` and
`engine/crates/layerfs-node/layerfs.node`; the SDK entry is
`api/agent/src/index.js`. Host Node/npm and both LayerFS Rust/Cargo versions are
recorded. The actual addon/daemon/SDK hashes and full relevant source hashes are
bound; a package version string alone is not a source identity.

The existing adapter already uses `LayerFS.init(name, source)` and the current
positional sandbox/workspace/branch methods. The inspected source signatures
match; actual runtime acceptance remains unproven until the normal oracle passes.
The SDK may internally spool large exec output; this series keeps its ordinary
no-sinks call and complete returned strings/raw archives. It never turns a
truncated stream into success. The measured-root TMPDIR binding before SDK load,
strict local-Docker route, trace-off and unset worker/policy/native overrides stay.
No SDK method, output witness, operation order, persistence behavior or cleanup
strategy is substituted. Unknown outcomes remain sticky and block teardown.


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
recorded (Sprig1.99.1; LayerFS1.85.1), not presented as the workload compiler.
Only ordinary Sprig projection-enabled library tests run, not old kernel gates.
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

The explicit `--latest-direct` collection route uses the already reviewed bounded
whole-evidence engine even when setup fails before an identity file exists.
It admits the complete named plan before copies; max(logical,allocated) file
charges, directory blocks and transient pending/final metadata stay within1GiB.
Copies use bounded chunks and strict source identity checks. Failed/partial
collection cannot claim complete evidence. Hidden files are uploaded only from
this validated owned collection root; no runtime root or unrelated file is swept.

## External comparison, not an upstream campaign qualification

This is the user's prospectively balanced external end-to-end DAG16 comparison.
It does not claim to satisfy LayerFS's different upstream campaign conventions
(one treatment sample, separately timed verification, residency-qualified cold
inputs and15s/25s campaign commands). Fresh symmetric writable images do not prove
OS-cold pages. This external protocol retains verification/lifecycle in its
primary boundary, records setup separately, makes no upstream campaign PASS or
cold-cache claim, and does not change product defaults/worker wiring to fit a gate.
The wrapper remains frozen before measurement; root review confirms the specific
external scope. No old run is relabeled to these assumptions.


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
