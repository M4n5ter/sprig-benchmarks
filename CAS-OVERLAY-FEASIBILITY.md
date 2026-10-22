# Read-only CAS + kernel OverlayFS feasibility

**The authorized kernel semantics smoke passed. This is not a performance comparison or a complete Sprig backend.**

[Successful run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39780562780), fixed experiment commit `6fa34fbeea70502d9694d54f17072a83c8dbcd7c`, production content-library dependency `22e6e4c289be67b78d39a7eae157bfa3219d23a4`. Source hashes, compiler and machine details are in the [raw artifact](measurements/2026-10-22-cas-overlay/).

The isolated Rust prototype imports through the existing Sprig content-defined chunk library and projects immutable manifest data through read-only FUSE. Kernel OverlayFS provides the writable view. No production repository code was changed by this experiment.

## Verified on a temporary Linux runner

The synthetic fixture has 10 entries and 4,194,364 logical bytes. Assertions verified:

- Actual FUSE initialization, exact reads, symlink target, executable mode, nanosecond mtime and repeated directory enumeration. A writable lower-file open fails with EROFS.
- One write-open copy-up, followed by ordinary writes, mmap modification and truncation of the copied-up inode. The immutable lower file remains unchanged. This is not three independent copy-up-trigger tests.
- Lower-directory rename with a trusted redirect xattr; a character-device 0:0 whiteout; deletion and recreation; and an opaque directory marked `trusted.overlay.opaque=y` that hides a retained lower child.
- An open file descriptor makes ordinary OverlayFS unmount fail; after closing it, ordinary OverlayFS then FUSE unmount succeeds. Both mountpoints are confirmed unmounted, and the foreground FUSE process exits successfully.

The adapter makes one direct FUSE mount attempt, with no privileged helper fallback or automatic/lazy unmount. The smoke uses internal-only ordinary `umount -i`; it never uses force/lazy unmount or kills a process serving a retained mount. It does not enable allow-other, install persistent helpers, or change system security/network policy.

The captured FUSE lifecycle reports 55 verified chunk misses, 361 cache hits, 166 read requests and 4,194,364 cached bytes under a 16 MiB content-cache cap. These are functional observations for this small fixture, not total-RSS bounds, a benchmark, or proof of large-workload efficiency.

## Scope of this earlier capability run

This earlier capability run did not test writable-layer reconciliation/checkpoint or shared publication. The later [incremental capture and publication sequence](CAS-CHECKPOINT-SEMANTICS.md) now verifies a bounded subset, without establishing a complete product backend, crash recovery, export or GC. Production Sprig's existing features are not automatically inherited by merely mounting its content library. No speed or storage advantage over another product is claimed.

The library must be trusted and immutable while mounted. This is not a hostile-owner sandbox. Ownership is synthesized; ACLs, original xattrs, hard-link relationships, sparse layout and special files are not preserved. Pre-1970 timestamps and oversized symlink targets are rejected. See the [prototype contract](feasibility/cas-projection/README.md) for complete restrictions.

Reproduce only in the explicitly authorized ephemeral environment through `cas-overlay-feasibility.yml`. Builds use locked dependencies and record the selected stable Rust version. Mount-free tests run before the synthetic mount test.
