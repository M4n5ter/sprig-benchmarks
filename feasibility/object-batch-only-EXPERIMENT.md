# ObjectBatch-only candidate

This isolates one change against the linear-inventory adapter measured at
benchmark commit 8d00ee96 and production core 22e6e4c:

- core/src/content.rs exposes ObjectBatch and uses it in core capture/put_bytes.
- adapter/src/capture.rs reuses the same bounded CDC writer across changed files.
- adapter/Cargo.toml points to the isolated ../core snapshot.

All revision, metadata, projection and head-publication implementation files
are identical to the linear-inventory adapter. A content-addressed compressed
manifest is again separate from its small parent/message revision record.
The embedded Revision format and shared codec changes are not included.
The production checkout and all prior candidate stores remain untouched.

Every newly published object inode is synced; every existing object encountered
by ingestion is hash/content verified. A successful finish syncs the object
directory, including empty or dedup-only batches. A failure cannot return a
successful capture to the existing publication caller. Publication's independent
object barrier, immutable metadata ordering and outcome-unknown handling are
unchanged. No trusted-content cache, mount change or fixture change is added.

Independent read-only review approved this extraction. Core seven grouped tests,
adapter nine grouped tests, formatting and adapter all-target clippy passed.
The optional unmounted recurring_probe diagnostic published 100 exact alternating
states, verified 101 historical revisions, restored the initial final manifest,
and found exactly two distinct immutable manifest files. It is not a mounted
performance measurement or evidence that the complete target is achieved.

Build adapter/Cargo.toml. cas_sample.py is unchanged SHA256
17b510933bf844b23fdff79df9dbbefa1bffc8ad086ac43bd3dfb4c6f464f70e.
Use new synthetic stores and the unchanged real-kernel semantics/performance
harness. No migration or deletion of an embedded-format store is performed.

Integration: adapter is cas-projection, core is cas-shared-core, and only the Cargo dependency path is adapted. Earlier shared-primitives provenance files are historical, not the active implementation. Production is unchanged.
