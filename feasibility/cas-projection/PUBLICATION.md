# Shared publication primitives experiment

This isolated, fresh-store candidate is not a production backend. The production
checkout and all prior measurements remain unchanged. Fixtures, operation order,
mount lifetimes, whole-filesystem accounting and history readback oracles must
remain unchanged in a paired run.

## One content writer and one revision representation

`sprig::content::ObjectBatch` owns one bounded 256 KiB CDC buffer. Core capture,
core byte writes, and incremental adapter capture use the same writer. Every
existing chunk encountered during ingestion is still checked for regular-file
type, length, content hash and byte equality. Every new chunk inode is synced
before its non-overwriting immutable publication. A successful batch finish
syncs the objects directory before capture returns. Errors return no successful
manifest; unused durable objects may remain. Publication retains its independent
object-directory barrier and checks arbitrary referenced objects.

A published revision is one `<revision-id>.revision.zst` file containing the
existing public `sprig::Revision` model: parents, logical clock, message and
manifest. Its identity is BLAKE3 of the canonical uncompressed JSON bytes.
The projection reads the embedded manifest directly; no per-revision second
manifest is written. The initial import's `manifest.json` remains a bootstrap
input, and explicit capture JSON files remain diagnostic outputs.

The shared codec writes a checksummed zstd frame, with level 1 and a 1 MiB window.
Adapter reads separately bound encoded and decoded data to 256 MiB, consume the
complete frame, reject trailing bytes and concatenated frames, and check the
revision address. The generic production reader retains its existing trusted-
store, unbounded-document policy. A checksum is validated when present; revision
address verification supplies independent integrity. Parent clocks are derived
from already validated parent views using checked `max(parent) + 1`, not head
generation. No persistent cache or second source of truth is introduced.

## Publication order

The required order remains:

1. New object inode syncs and object-directory barrier.
2. Referenced-object type, length, aggregate-size and necessary durability checks.
3. Immutable revision inode sync, no-overwrite publication and directory barrier.
4. Retained previous-head backup and its directory barrier.
5. Atomic new-head rename and root-directory barrier.

A failure after the head rename reports outcome unknown. Cached head/durability
state advances only after confirmed success. Callers reopen and inspect instead
of blindly replaying. Previously published current-head objects provide
*durability evidence*, not a new payload integrity check. Unchanged lower objects
remain governed by the trusted immutable-store contract; this experiment does
not introduce universal commit-time rehashing or claim concurrent hostile-store
protection. New or unproven object references still receive inode syncs.

Existing incompatible current-head records are rejected before lock or directory
creation. There is no migration, overwrite, deletion or automatic retry of an old
store. Use new synthetic stores. Revision IDs change with this representation.

## Validation and limits

Grouped tests cover CDC equivalence, short/interrupted reads, corruption and
symlink refusal, failed final barriers, publication/reopen, merge/conflict/CAS,
no-op, codec bounds, immutable reuse, legacy rejection, and projection loading.
These are not power-cut certification. The same real-kernel semantic driver and
full paired workload must pass before claiming an end-to-end improvement.

The opaque `manifest` CLI field now names an embedded revision file. The existing
sample driver needs no change. An exact revision filename or revision hash is an
exact historical reference; bootstrap/capture JSON base resolution remains
content-based. This is still an experimental single-head publisher, not the
production multi-workspace Store, complete SDK, or recovery implementation.
