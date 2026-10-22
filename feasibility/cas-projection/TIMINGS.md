# Checkpoint metadata diagnostics

This candidate retains the publication candidate's diagnostic timing boundaries
and adds the bounded capture optimization described in [CERTIFICATE.md](CERTIFICATE.md).
Publication ordering and mounted-view lifetime are unchanged. Use the existing
sample operations and full-history readbacks; no performance victory can be
inferred from one sample.

Each checkpoint adds `timings` with `transaction_open_seconds`,
`base_identity_load_seconds`, `capture_total_seconds`,
`identity_reconcile_seconds`, and `publication_total_seconds`. These phases are
disjoint, but exclude argument parsing, JSON serialization, process startup and
small intervening bookkeeping. The external checkpoint timer still covers the
whole CLI invocation.

`capture.timings` reports setup, inclusive walk and finalize totals. Eleven
additional, disjoint walk categories measure regular merged-file open,
directory open, descriptor close, fstat/lstat metadata, merged-origin xattr,
native upper-state proof, repeated lower reuse proof, content hashing/object
writes, directory enumeration, certificate inventory, and certificate prefix
reuse. Lower proof includes its own path opens,
origin checks and chunk metadata queries; do not add those operations again.
Directory enumeration includes collection/sorting but not recursive traversal.
Unaccounted walk time includes readlink, validation, bookkeeping, recursion and
timer overhead. Setup includes mount binding and manifest load. Finalize includes
identity assignment, validation, object-directory sync, native inventory
revalidation and topology rechecks. Preliminary merged visibility lookups for
upper-present children are currently unaccounted walk time, not metadata_seconds.

Explicit descriptor drops occur at the same branch lifetime boundary as before.
Timers do not measure remote/kernel CPU directly. All durations are elapsed wall
seconds in the current process. No ptrace, tracing privilege, sampler daemon or
additional mount is required. The original sample driver retains the complete
checkpoint JSON, so no harness adaptation is needed.
