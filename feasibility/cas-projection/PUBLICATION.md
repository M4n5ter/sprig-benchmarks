# Publication-cost experiment

This is a fresh-store-only candidate, not a production backend. The original
projection experiment and production Sprig remain unchanged. Use the same
fixtures, operation sequence, permissions, lifetime accounting and full-history
oracles when comparing it. No new mount permissions or lifecycle mechanisms are
introduced.

## Two changes

1. Immutable history manifests use `<uncompressed-json-hash>.manifest.zst`.
   Encoding uses the production metadata settings: zstd level 1, a 1 MiB window,
   pledged input size and a checksum. Decoding limits both the encoded file and
   decoded document to 256 MiB, validates the complete frame and any checksum,
   and rejects trailing bytes and concatenated frames. Manifest validation and
   canonical uncompressed-address checks in the revision reader remain intact.
   Initial `manifest.json` and explicit capture outputs remain plain JSON.
2. Each transaction reconstructs an in-memory set of durable object hashes from
   its already-read, validated current head manifest. Publication still opens
   and checks every referenced object, including regular-file type, no symlink
   following, individual lengths, overflow and aggregate file size. It omits
   only repeated file fsync calls for hashes whose durability is already implied
   by prior successful publication. New or unproven objects still receive fsync.

The proof depends on the existing trusted, immutable store contract. A published
head is durability evidence, not a new verification of object payloads. There
was no commit-time payload rehash in the original experiment; ingestion and
cold content reads continue to verify hashes. Replacing an immutable object
behind the tool is not supported. Missing or malformed known objects still fail
non-noop publication without advancing the head.

No persistent cache or history-wide scan is added. Reopening reconstructs the
set from the current manifest that initialization already reads. Unpublished
conflict candidates cannot enter the set. It changes only after successful head
publication, and old hashes absent from the current head are conservatively
synced again if a later candidate references them.

## Publication order and failures

The order remains: required object inode syncs, objects directory sync, immutable
manifest and revision file/directory syncs, retained previous head, atomic head
rename, root directory sync. A post-rename sync failure still reports an unknown
outcome. It does not advance the transaction's cached head or durability set;
callers must reopen and inspect rather than replay blindly.

Existing experimental histories with `.manifest.json` revision records are
explicitly rejected. There is no migration, reset, overwrite or deletion of old
stores. Create new synthetic stores for this candidate.

## Validation and comparison boundary

Grouped tests cover compressed projection loading, publication/reopen, merge,
conflict retention, stale CAS, no-op, damaged known objects, old-format rejection,
and codec corruption/bounds. They do not simulate power loss. Real-kernel upper
capture semantics and the same full-history performance workload must be rerun
before attributing an end-to-end improvement to this candidate.

The existing semantic driver's one direct JSON read of a published manifest must
instead select the same revision's decoded `manifest` from the existing history
API, then perform the identical full-manifest equality assertion. Initial and
explicit capture JSON reads are unchanged. The performance sample driver needs
no change, and all timing and physical-space boundaries remain unchanged.
