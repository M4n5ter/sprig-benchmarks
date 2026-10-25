# Cargo DAG16 v2 acceptance — new protocol, not historical report replacement

Status: source/mocked validation and local Rust1.99.1 fixture sanity. No pinned
Rust1.90.0 + actual product restore result is claimed until the reviewed workflow
runs and preserves its artifacts. Frozen `cargo_sample.py`,
`cargo_transport_sample.py`, `cargo_layerfs.mjs`, their reports, and historical
measurement boundaries are unchanged.

## Fixture and executable evidence

`stress_cargo_prepare.py generate` derives a deterministic16-library local DAG
plus `stress-app`, no registry dependencies. Shared leaf `node000` has a genuine
rerun-sensitive build script which reads `build-input.txt` and writes
`OUT_DIR/generated.rs`; its exported value is included in the executable result.
The pinned compiler image generates Cargo.lock offline with a container-local
setup Cargo home. `freeze` refuses target/Cargo-home/temp pollution, normalizes
source metadata and emits both the complete source oracle and protocol-bound DAG
manifest. Source contains only regular independent files/directories, matching
the frozen import preflight contract.

Both adapters load identical scripts from `stress-cargo-protocol.json`, whose
SHA256 is bound into the manifest/report. Build is exactly:

```
cargo build --offline --locked --verbose --workspace --jobs 2
```

Clean and shared-leaf/build-input edit builds require exactly the17 known
packages to report Compiling; noop and restored builds require all17 Fresh and
no Compiling. Missing, duplicate, unknown or differently-versioned package lines
fail. The current fan-out/fan-in executable output is269; after source+build input edits it is3400.
The graph has four independent siblings after shared node000, two further four-node
join tiers, two joins, then node015 and the app. Every package depends transitively
on node000; both products and the capacity pilot use jobs2. Algebraically the
app result is31*leaf+207, where leaf changes2→103.
Both generated.rs content and executable outputs are verified, not inferred from
exit status alone.

A target-local probe adds an ordinary file with0640 mode and exact nanosecond
mtime, its hardlink, and a relative symlink. All target binaries, incremental
cache, Cargo home, TMPDIR, generated files and probes remain in the full-tree
snapshot. The exact byte/type/mode/mtime/symlink/internal-hardlink oracle runs
**before** any restored program or build, with raw integer JSON preserved for
LayerFS transport. Both NEW adapters execute a short snapshot command and
compare the complete expected tree on the host (Python integer nanoseconds;
LayerFS raw decimal-string nanoseconds), avoiding unbounded argv heredocs and
one-sided oracle transport. Raw snapshots and comparison time stay charged.
Additional artifact checks surround clean/noop/edit/restore/
restored-rebuild phases and stay in elapsed task time.

## Compiler lifetimes and transport

Sprig's NEW adapter subclasses the corrected cooperative generation transport.
The work compiler session closes via its one acknowledged marker, verified
natural exit/PID identity/wait, normal exact-container removal and absence
inventory before checkpoint. Restored work starts a new exact-generation bind.
Main/source oracles have separate short-lived sessions; source remains read-only.
There are four compiler sessions in total and exactly the restored compiler live
at the primary physical snapshot. No old bind crosses generation replacement;
unknown mutation acknowledgment blocks product unmount and is never retried.

LayerFS retains its existing public SDK persistent-sandbox transport and ordinary
UID501 semantics. The two transports are not identical and no process overhead is
subtracted to manufacture product superiority. Ordinary SDK normal-close behavior
and all lifecycle differences remain explicitly reported.

## Timing and evidence

Space accounting uses the same sync/usage/df queries for both products; no
one-sided recursive extent inventory is inside only one matched task.
Existing product checkpoint/readiness and generation-compiler composites remain
unchanged. New toolchain/probe/artifact checks have explicit phase timers, inside
full task wall. Both samplers run in subprocesses; matched outer wall additionally
includes launch and report serialization. Inner phase/composite/task timers
OVERLAP and cannot be summed. All starts, commands, full oracles, quiescence,
normal cleanup, logs and evidence serialization remain charged at their documented
boundaries. Runtime/image preparation is separately timed but physical image and
runtime roots remain charged in the measured filesystem. External immutable
source fixtures and host-side product/tool executables remain outside that
filesystem, as in the frozen contract, and are disclosed symmetrically rather
than called application-only physical usage.

Successful CLI/container stdout/stderr and full daemon logs that are available
are retained without tail truncation. Copies to the external artifact directory
happen only after physical accounting and normal product cleanup. Original logs
remain inside the measured filesystem through the physical snapshot. Exact file
sizes/hashes accompany copied logs; incomplete evidence is not presumed success.

## Capacity and resources

One existing Ubuntu24 runner,45-minute workflow limit, compilation ceiling2jobs,
product workload Cargo jobs1, one fresh **2GiB** Btrfs image at a time. There is
no automatic fallback to the historical8GiB Cargo runner and no security, paid
resource, capability or runtime-permission expansion.

One immutable shared Rust/Cargo1.90.0 compiler image is built/identified once,
then loaded inside each product's measured runtime. Both products use that exact
image ID. Docker/containerd roots, image layers, retained product generations,
full target/cache and live restored compiler runtime are all charged to whole
Btrfs Used. Runtime-ready growth is secondary, not a substitute for whole Used.

`stress_cargo_capacity.py` performs an explicitly external COMMON setup pilot on
fresh copies of the pristine source for incremental0 and1. It records actual
pinned toolchain output, successful build/Fresh/output checks and `du` target
allocated/logical bytes. Those separate pilot trees remain evidence; no product
imports/reuses them, their target, cache or source modifications. This setup cost
is not silently removed from one product's measurement but is symmetrically
outside both product task scopes.

After loading the shared image into each fresh measured runtime, the runner
records actual whole-FS runtime-ready Used and requires actual available bytes
at least `max(512MiB, 4*pilotTargetAllocatedBytes + 8*fixtureLogicalBytes + 256MiB)`.
This is a conservative admission guard, not a guarantee against all runtime
allocation. Capacity failure is recorded distinctly and stops that cell; it
never enlarges the filesystem, removes retained data, excludes caches, or relaxes
an oracle. The whole image/runtime usage is NOT subtracted from primary Used.

## Gating

Default workflow runs actual incremental0 paired acceptance only. An explicit
`run_incremental1` opt-in may run incremental1 as a separate
runner invocation only after the complete incremental0 report passes the exact
same protocol, fixture, image and product-pin gates, including both products'
all17 Fresh noop/restored evidence. The workflow builds the shared image once
and retains its identity across the two invocations. No automatic onward run
occurs after failure/unknown cleanup/capacity blocking.

The first workflow step establishes one absolute40minute admission deadline
inside the existing45minute job limit. Setup, capacity pilots and incremental0
consume that same budget; incremental1 cannot reset it. Before runtime setup and
again before each sampler launch, require at least180seconds expected operation
plus300seconds normal-cleanup reserve. Insufficient time records budget_blocked
and starts no next sampler; it does not kill an operation or force cleanup.
If incremental1 cannot fit, a separately reviewed gated job preserving the same
immutable image/evidence is needed; no automatic resource extension is attempted.

These are initial correctness acceptance cells, not repeated performance results.
Any later performance series needs alternating order and independent repeated
samples. LayerFS Disposable WAL/syncOFF remains different crash durability; Sprig
synchronization/identity/quiescence guarantees are not weakened for equivalence.

## Local validation boundary

New Python mocked tests exercise both incremental settings, all17package gates,
actual inherited generation transport ordering and lost-marker cleanup blocking.
New JS mocks cover exact-nanosecond oracle transport, both lifecycle settings and
artifact/toolchain/unknown-exec failures. Capacity tests validate script syntax,
measured-allocation and pinned-software requirements.

Local Rust1.99.1 sanity (not1.90 acceptance) compiled both incremental settings:
all17 Compiling clean/edit; all17 Fresh noop and another same-path postedit noop;
real generated.rs/probe checks passed; program777→14109 (superseded serialized-graph sanity; not validation of the current branching graph). Local target allocated
bytes were10,465,280 (incremental0) and18,952,192 (incremental1). These local sizes
are illustrative only and cannot admit CI; the CI common-image pilot is required.
No local product restore/FUSE/container acceptance is asserted.

The forward branching-graph/jobs2 sanity uses a fresh output directory and the same
local Rust1.99.1 only: clean/edit17 Compiling, both same-path noops17 Fresh,
build-script and hardlink/mtime probes pass, executable269→3400. Target allocated
bytes:10,465,280 (incremental0),18,837,504 (incremental1). These figures are not
pinned1.90 capacity admission or product restore results. The graph exposes four
ready siblings; jobs2 bounds compiler concurrency, without asserting a measured
overlap duration from Cargo verbose output.

## Failure evidence, including runtime setup failures

The stress-only runtime wrapper records a failed Docker image load's complete
original merged stdout/stderr before the existing setup rollback. It labels the
phase explicitly and adds read-only df/Btrfs usage (each bounded at10seconds);
diagnostic failures do not replace the original load exception. No cause such as
ENOSPC is inferred without the captured output. Runtime rollback/admission and
unknown-state cleanup rules are unchanged. Component lists, toolchain allocation,
image size and archive bytes are recorded without changing image contents.

An always-run collector copies only named generated reports, ledger files, and
stdout/stderr/log files into a new runner-owned0755 artifact directory with0644
files. It never descends into capacity-pilot source/target, runtime roots, sockets
or private configuration backups; symlinks/nonregular files are rejected. Source
permissions/ownership and cleanup state are untouched. This post-job evidence copy
is outside paired timing; the original measured logs remain fully charged.

## Cargo-only resource revision after confirmed import failure

The initial2GiB attempts remain immutable capacity-failure evidence with zero
product samples. The next Cargo attempt uses fresh symmetric4GiB images for
both products, recorded as `sprig-cargo-resource-4g-v1`; command/fixture/compiler
protocol is unchanged. The fixed guard rejects2GiB and8GiB filesystems in this
first4GiB attempt, and any prior incremental gate must match resource geometry
as well as image/source/protocol identities. Host admission requires4GiB plus
the existing1GiB evidence reserve. No resizing, reuse across sizes or automatic
retry is implemented. Only after a confirmed4GiB capacity failure may a separate
reviewed attempt use fresh8GiB images for BOTH products; no mixed-size ratios.
The45minute job, one runner, two compiler jobs, cleanup/oracle and permission
settings are unchanged. This exception applies only to Cargo; other stress
profiles retain2GiB. The immutable shared compiler image is not pruned/shrunk.
