# Current real Cargo lifecycle: measurement contract

This is a separate, tiny dependency-free Cargo workload. It is NOT the frozen
seven-scene history benchmark, a large-project benchmark, or a performance result
until a real runner record passes every gate.

Pins: Sprig production e38225e1e1160e8de90aa911d6f1740bef93bacc with a fresh
store's default auto compression; LayerFS release v1.1.0
9f97a7ec95b662e9cb288704afa165feff132cfa, official Disposable persistence. The
Sprig helper reuses the unchanged current_sample.py lifecycle methods, but the
Cargo driver and workflow explicitly identify/build the newer production SHA.
The seven-scene fba baseline is untouched. No GC, retention, pruning, target
cleanup, compression disabling or product-source patch is performed.

## Work performed

For CARGO_INCREMENTAL=0 and =1 in separate fresh stores: initialize and import;
fork a working view; verify fixture; create workspace-local Cargo home/temp;
clean build and run; no-op build and run; change source and build/run; checkpoint
all contents; restore the exact acknowledged revision; verify every restored
entry BEFORE running or rebuilding; run restored binary, rebuild and run again.
Source and the original imported view remain unchanged. Main, work and restored
second are all live at physical accounting. The owned writable arm also retains
its previous working generation, four generations total.

Complete tree verification includes target, caches, hidden files, regular bytes,
ordinary modes, exact nanosecond mtimes, symlink targets and internal hardlink
equivalence classes. No file is excluded. Exact raw oracle JSON is retained:
LayerFS structured copies encode mtime_ns as decimal strings to avoid precision
loss. Sprig's raw Python report preserves exact integers; its parsed aggregate
JavaScript diagnostic copy may round them and is never the oracle authority.
No post-import/restoration timestamp normalization is allowed. The fixture
preparer only constructs the deterministic EXTERNAL source before either import.

## Software and execution differences

Both arms use the same immutable runtime/compiler image, archived once and loaded
into each freshly relocated runtime. See CARGO-IMAGE-CONTRACT.md. The actual
compiler/sysroot/linker hashes, installed versions and image identity are recorded.
One Cargo build job is used. The tiny crate has no third-party dependencies and
builds offline with a fixed lockfile. This verifies genuine compilation and cache
lifecycle, not a representative large dependency graph.

Sprig compiler commands use ordinary root Docker containers with the actual
already-mounted writable view bound at /work. Each invocation includes container
create/start/exec/exit/removal; none is granted extra capabilities, devices or
security options. Every container must exit before checkpoint. LayerFS runs
through its official persistent Sandbox SDK as UID501/GID20 at /workspaces/N.
Actual paths, UID and transports differ. They are not hidden by changing either
product's security configuration. Different restored paths may invalidate Cargo
fingerprints: report actual verbose Fresh/Compiling lines, not assumed cache hits.

## Timing and space

Raw phase_seconds retains every initialization, mount/fork, Cargo, checkpoint,
restore, oracle, accounting and cleanup cost. full_task_seconds is authoritative
end-to-end sample wall time. checkpoint is the sum of checkpoint_cli and
checkpoint_readiness, so do NOT sum all fields blindly. The immediate acknowledged
revision ledger lies between those phases but remains in full-task wall time.
Runtime relocation/image loading and software setup are separately reported, not
silently included in one arm's compiler time.

Both samples use fresh 8 GiB Btrfs images, Data SINGLE/Metadata DUP, noatime, and
identical whole-filesystem accounting. Docker/containerd persistent roots,
images, writable layers, volumes, product store, generations, histories, journals
and runtime logs are inside the measured image. Complete command logs/oracles
outside captured trees are also charged. External raw acknowledgment ledgers are
not charged, symmetrically. Whole filesystem Used and runtime-ready delta are
reported; the latter is NOT exact app-only space. Volatile kernel/tmpfs memory,
page cache, RAM and outside-image binaries remain exclusions. No cold-cache claim.

Sprig preserves its production synchronization. LayerFS global SQLite WAL/OFF and
workspace MEMORY/OFF do not provide equal crash/power-loss durability. Neither
this test nor successful readback proves equivalent durability.

Space is sampled with all three views live before cleanup. Subsequent ordinary
LayerFS Sandbox teardown removes overlays while retaining committed Store history;
Sprig retains materializations/generations. Post-cleanup usage is not substituted
for the live accounting point. Failed or uncertain lifecycle operations retain
state without retry/forced/lazy unmount. Successful synthetic images are removed
only after normal unmount, loop detachment, inode verification and durable raw
report persistence. No real disk or user data is formatted or deleted.

Smoke has one pair per incremental mode (4 records); full has three alternating
pairs per mode (12 records). Report all records, failures and repetitions. One
smoke result is not a performance distribution. The workflow must first pass the
real production projection and owned-writable lifecycle tests.
