# Sprig CAS projection prototype

This candidate adds bounded upper-absence subtree capture to the compressed
immutable-manifest publication candidate. See [CERTIFICATE.md](CERTIFICATE.md)
for its proof, conservative fallback, and validation boundary;
[PUBLICATION.md](PUBLICATION.md) describes the retained publication format,
fresh-store restriction and durability guarantees.

This is an isolated, **read-only Linux FUSE feasibility prototype**, not a full
Sprig implementation or a new production backend. It imports a quiescent source
using the existing Sprig content-defined chunk capture code, then exposes that
immutable manifest without cloning or materializing the source tree.

Production Sprig and its native workspace behavior are unchanged. This experiment
adds validated OverlayFS upper capture and a small shared publication engine that
reuses Sprig's content and merge modules. It is not a complete workspace manager,
SDK, recovery service, or production backend. There is no automatic OverlayFS
mount, privileged installation, configuration edit, or authentication helper.
Actual read-only FUSE and OverlayFS capability checks passed on an explicitly
authorized temporary Linux runner; the incremental commit extension requires its
own real-kernel semantic validation before any performance conclusion.

## Build and test

Requires stable Rust 1.89 or newer. The only direct dependencies beyond Sprig are
`fuser` 0.16.0, `libc`, `serde`/`serde_json`, `fastcdc`, `blake3`, and `zstd` 0.13.3; fuser's default/libfuse features
are disabled. No system libfuse development package is required for compilation.
The local path dependency is `../sprig-history-rewrite`. When copying this folder
to the benchmark runner's `feasibility/cas-projection`, change only that dependency
path to `../../sprig`, using the runner's already-pinned production source.

```sh
CARGO_BUILD_JOBS=2 cargo build --locked
cargo fmt --check
CARGO_BUILD_JOBS=2 cargo clippy --locked --all-targets -- -D warnings
CARGO_BUILD_JOBS=2 cargo test --locked
```

Debug information and incremental compilation are disabled in the development
and test profiles. Tests never mount a filesystem and create only test-owned
fixtures under this crate's `target/test-work` directory.

## CLI

```sh
# SOURCE must be a trusted, quiescent directory. LIBRARY must not exist.
cargo run --locked -- import --source /path/to/SOURCE --root /path/to/NEW_LIBRARY

# Only run after obtaining appropriate mount authorization and support.
# MOUNTPOINT must already exist, be empty, and be outside LIBRARY's tree.
cargo run --locked -- mount --root /path/to/LIBRARY --mountpoint /path/to/MOUNTPOINT

# Optional: select a different manifest filename inside the same library root.
cargo run --locked -- mount --root /path/to/LIBRARY --manifest manifest.json \
  --mountpoint /path/to/MOUNTPOINT
```

Mounting is foreground-only and **limited to an explicitly authorized Linux root
CI runner** with accessible `/dev/fuse` and the necessary mount capability.
Rootless mounting is not supported. The program makes exactly one direct
`mount(2)` attempt with fixed read-only flags. An error, including `EPERM`, is
returned immediately: no `fusermount` fallback, privilege change, helper, or
installation is attempted.

**External ordinary unmount owns all cleanup**: unmount an overlaid view first,
then this lower mount, using normal `umount`. Never use lazy/force options and
never fall back to them after a busy/error result.

The pinned fuser mount destructor and external `fusermount` helper contain lazy
cleanup paths. This prototype uses neither. After the direct mount succeeds, it
constructs `Session::from_fd`, which owns no fuser `Mount` object. Ordinary session
drop closes the descriptor and releases memory, but never calls unmount. A
startup/run failure or crash can leave a disconnected/busy mount that still needs
ordinary external cleanup. Report such a failure instead of killing unrelated
holders or forcing cleanup. No `AutoUnmount` option or background session is used.

`--allow-other` is **off by default**. Add it explicitly only when an isolated,
authorized root-CI OverlayFS experiment requires other-user/root access. It
allows other users to reach the mount subject to ordinary file modes, not just
root. The kernel still enforces file permissions and mount capability requirements.
The program does not alter host policy or request alternate privileges.

Mount options always include `ro`, `default_permissions`, `nodev`, `nosuid`, and
`noatime`. Execution is not disabled, so executable fixture files retain their
ordinary mode semantics. Import emits one JSON result to stdout. Mount lifecycle,
read errors, and final cache/read statistics are JSON lines on stderr.
`mount_prepared` is not a successful-mount signal; `fuse_initialized` records a
successful FUSE initialization callback. `session_stopped` records the request
loop ending, not successful mountpoint cleanup. The `filesystem_destroyed` statistics line
records a destroy callback or session drop, not verified mountpoint cleanup.
An abrupt process exit can prevent that final statistics line.

## Storage and read path

The library owns all persistent data:

```text
LIBRARY/
  manifest.json       # immutable initial projection manifest
  <hash>.manifest.zst # immutable history manifests; explicit capture outputs remain JSON
  head.json           # atomically published head + generation
  commits/            # immutable parent/message/manifest records
  commit-backups/     # previous heads and retained conflict reports
  commit.lock         # cooperative single-writer lock
  objects/
    <64 lowercase hex BLAKE3 hash>
```

Import creates a fresh mode-0700 library, captures and syncs immutable chunks,
then writes and syncs a temporary manifest, atomically renames it, and syncs the
library directory. A failed capture may leave unreferenced objects in its new
root, but cannot publish a partial manifest. Existing roots are never reused or
overwritten. No original file is hard-linked into the object store.

Mount loads metadata once. Inodes are assigned in lexicographic manifest-path
order, starting at root inode 1, and remain stable across mounts of that exact
manifest. Directories provide `.` and `..` and stable continuation offsets.
Chunk sizes are indexed by descriptor-relative, no-follow object opens. The sum
of each file's chunk lengths must equal its declared size. Loading the index does
not read or hash chunk content.

A random file read uses binary search to locate overlapping chunks, loads at
most 256 KiB per chunk, checks the canonical hash name and BLAKE3 content digest
before cache insertion, then copies only the requested range into the response.
The LRU stores at most **16 MiB of verified content**, plus at most one temporary
256 KiB chunk while inserting. Each read response is at most **1 MiB**. The mount
sets a matching maximum read request size; oversized direct library requests are
rejected rather than returned as misleading short reads. There is no full-file
buffer or full-file materialization. The kernel may additionally page-cache
read-only file content independently of this user-space cache.

This is not a 16 MiB total-RSS guarantee. Manifest JSON, the inode/child/chunk-span
index, cache metadata, and FUSE buffers are extra. Manifest input is capped at
256 MiB. Cache eviction uses a straightforward least-recently-used scan, suitable
for this bounded prototype, not an optimized production service.

## Semantics and limits

- Preserves tracked regular-file bytes, file/directory modes, supported nanosecond mtime,
  empty files/directories, and raw symlink target bytes. Paths follow Sprig's
  UTF-8 limitation. File content, including large files, is not UTF-8 constrained.
- Mount rejects every pre-1970 mtime rather than expose incorrect metadata: the
  pinned fuser 0.16 serializer mishandles negative fractional timestamps. Import
  still preserves those timestamps in its manifest. Epoch and later mtimes are
  supported, including nanosecond precision.
- Symlink targets are capped at 4,095 bytes, the conservative Linux FUSE
  readlink-reply limit for the intended 4 KiB-page runner. Longer targets are
  rejected during projection loading rather than failing later at readlink.
- UID/GID are synthesized from the mounting process because Sprig does not track
  ownership. atime, ctime, and creation time are synthesized from mtime. ACLs,
  original xattrs, special files, sparse extents, and hard-link relationships are
  not preserved. statfs reports logical space and zero writable/free capacity.
- `default_permissions` delegates supplementary-group permission checks to the
  kernel; the direct-library access fallback checks uid and primary gid only.
- Every data/namespace mutation callback explicitly returns `EROFS`. Existing
  read-only flush/fsync/release operations are harmless. Unsupported advanced
  operations retain fuser's defaults. There are no object-store writes on mount.
- A manifest option is a single filename inside the library, not an arbitrary
  external path. Object names are exactly 64 lowercase hexadecimal bytes.
  Symlinked object/manifest files and symlinked object/root directories are
  rejected. Objects are opened relative to a held directory descriptor.
- The library, its ancestor directories, and the source during import must be
  trusted and immutable/quiescent as appropriate. This is not a sandbox against
  a malicious owner replacing ancestors, rewriting manifests during startup,
  or removing objects concurrently. Corrupt cold chunks fail reads; already
  verified cached bytes remain the original content if someone violates the
  immutability contract. Referenced missing/invalid-sized chunks fail load.
- A corrupt same-sized object is detected on its first uncached read, not during
  mount. There is no eager whole-store verification or claim of OverlayFS
  NFS-export/file-handle support.

## Validation scope

Mount-free tests cover import publication/failure, CLI parsing, metadata and
non-UTF-8 symlink bytes, stable inode lookup, directory relationships, zero/EOF/
negative/oversized reads, cross-chunk offsets, a file larger than cache, full-stream
hash equivalence, LRU eviction, corruption-before-cache, canonical hash rejection,
missing/symlinked/oversized/mis-sized objects, pre-epoch timestamp rejection,
readlink reply-size boundaries, and
read-only opens/access checks.

The first real-kernel smoke passed read-only projection, copy-up/in-place and mmap
writes, truncation, lower-directory rename with redirect, whiteouts, opaque
replacement, old-lower isolation, and ordinary unmount refusing an open descriptor.
That result does not establish incremental capture or workspace publication.
No mount is part of the default build/test workflow.

## Incremental capture and shared publication experiment

Use only an already-authorized, private, rootful temporary Linux runner. Keep all
external writers quiescent. The merged view, lower, upper, work, and object store
must be separate trees; nested mounts, extra lowers, rootless userxattr, volatile
mode, and ambiguous mount paths are rejected. The actual mount table must bind
these exact paths. The lower must be this root-owned read-only projection.

A metadata walk uses the kernel's merged namespace, including redirects,
whiteouts, and opaque directories. Content reuse requires an absent upper leaf
proved through descriptor-relative, no-follow ancestor checks, a bound immutable
lower origin, and a matching base entry. Metacopy must be proven disabled. All
upper files and every uncertain file are streamed through the normal CDC/hash
writer. Preserved sizes, timestamps, inode numbers, or copied/forged origin xattrs
never authorize content reuse. The public prototype origin xattr is advisory for
identity and does not expose arbitrary original xattrs. It is not advertised on
symlinks, because Linux forbids user.* attributes there; symlink rename identity
hints are consequently unavailable.

After mounting one lower and OverlayFS view through the runner's reviewed helper:

```sh
# Initialize/read the experimental head; save its head and generation values.
$BIN head --root "$STORE"

# Capture a candidate without moving the head, then check every path/content,
# mode and mtime using the independent full-capture oracle (outside any timer).
$BIN capture --root "$STORE" --projection-base manifest.json \
  --base manifest.json --merged "$VIEW" --upper "$UPPER" --lower "$LOWER" \
  --output candidate.json
$BIN verify --root "$STORE" --merged "$VIEW" --manifest candidate.json

# Checkpoint through the same publication core as direct SDK writes.
$BIN checkpoint --root "$STORE" --projection-base manifest.json \
  --base "$APPLIED_BASE" --merged "$VIEW" --upper "$UPPER" --lower "$LOWER"
$BIN write --root "$STORE" --base "$APPLIED_BASE" --path file.txt --text 'new text'
$BIN history --root "$STORE"
```

`--base` is the known history state actually applied to that workspace, not merely
the latest published head. `--projection-base` identifies the immutable mounted
lower. Identity reconciliation defaults to the logical base; an optional
`--identity-base FILENAME` supplies the previous local candidate's immutable
manifest when its identities must survive a still-mounted older projection.
It affects IDs only, never content reuse. These explicit experimental inputs are
not an automatic workspace lifecycle. In particular, a successful merge does
**not** rewrite or refresh the mounted view, advance its applied base, or release
its lower pin. Upper-only renames without a known identity are not tracked by a
persistent inode journal.

All cooperating captures and writes hold one nonblocking transaction lock. A
candidate is immutable before the head changes. A stale candidate uses Sprig's
three-way merge; a clean merge retains both parents. The current head's `.lww`
rules are honored by that existing core; without such an explicit policy,
overlapping incompatible edits return structured conflicts. Conflicts retain the
candidate and report, leave the head unchanged, and do not overwrite the mounted
view or inject textual markers. This is not a full interactive conflict resolver.
An explicit CAS requires both `--expected-head ID` and
`--expected-generation NUMBER`. Unrelated or orphan candidate commits cannot be
used as publication bases. Unchanged candidates do not create head updates just
because the message differs.

Checked content fsyncs and directory publication precede immutable records, then
an old-head backup precedes atomic head replacement and root-directory fsync.
A post-replacement sync failure reports publication outcome unknown: reopen and
inspect the head before deciding what to do, never blindly retry. Orphan files
may remain after failed publication; this experiment never purges them. Ordinary
close/reopen checks are not a complete crash/power-failure test suite. There is no
GC or mount-epoch reset, so all prior manifests, candidates, chunks, and the live
projection base remain retained. Busy mounts keep the old projection unchanged;
only normal, successful unmount allows external lifecycle cleanup.

Style follows the [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html)
where appropriate for a standalone Cargo crate: stable Rust, rustfmt, explicit
modules/imports, borrowed cached bytes, documented unsafe descriptor calls, and
localized protocol-driven exceptions. FUSE interfaces follow the official
[fuser 0.16 documentation](https://docs.rs/fuser/0.16.0/fuser/trait.Filesystem.html).
