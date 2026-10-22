# Incremental CAS/Overlay capture and shared publication

**The complete bounded kernel semantics sequence passed. This is an experimental adapter, not production Sprig, a performance comparison, or feature parity.**

[Successful run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39790551084), experiment commit `2f5f26678687459eceb92b005730d9dc40308991`, unchanged production library dependency `22e6e4c289be67b78d39a7eae157bfa3219d23a4`. [Original raw results, source hashes and environment](measurements/2026-10-22-cas-checkpoint/). The earlier basic capability result remains [separately recorded](CAS-OVERLAY-FEASIBILITY.md).

## Verified

The temporary Linux runner built and tested the locked Rust source, reran the basic FUSE/Overlay smoke, then passed every assertion in [the semantic driver](feasibility/cas_checkpoint_smoke.py):

- Two untouched mounted views reused 1,048,638 lower-file bytes with zero content hashing. Independent full capture agreed on every path, kind, content/chunks, mode and nanosecond mtime; generated identities were excluded from that oracle.
- The changed A view hashed 52 bytes and reused 1,048,583 bytes. Same-size, restored-mtime upper modification plus a forged origin xattr did not bypass hashing. Directory and symlink rename, whiteouts, opacity and lower isolation were verified.
- Checkpoint preserved identity continuity; an unchanged checkpoint returned no-op. Upper files are still hashed on the no-op scan: this is not a general unchanged-file cache.
- Two non-overlapping stale workspace edits merged successfully with shared SDK-style publication, including an intervening SDK write. Mounted stale views were deliberately not treated as automatically rebased.
- Conflicting edits retained a readable immutable candidate without advancing head. Strict stale head/generation CAS and orphan-candidate publication-base attempts were refused.
- Five first-parent history entries, two merge-parent relationships, original and intermediate immutable reads, and candidate reads were checked.
- An open descriptor blocked ordinary unmount. After release, all three Overlay views and the FUSE lower were ordinarily unmounted; the raw result confirms no remaining mounts.

The preceding attempt [39788698120](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39788698120) stopped at a CLI output serialization defect after the first zero-hash capture. The corrective commit makes the manifest filename a UTF-8 JSON string and improves failure diagnostics. It does not change storage or merge semantics. That failed attempt is not counted as a passing sequence.

## Boundaries

This is a trusted, quiescent, root-run synthetic experiment on one Linux kernel, not hostile-owner isolation or concurrent filesystem mutation safety. It uses its own experimental publication store and existing Sprig merge/content logic; production Sprig was not modified. It does not establish production lifecycle/reopen integration, crash recovery, export/GC, full product API coverage, every metadata type, or broad multiwriter correctness.

The projection base, applied commit base and local identity base are distinct; after a stale merge the mounted view is not silently rebased. See [SEMANTICS.md](feasibility/cas-projection/SEMANTICS.md) for the exact bounded contract.

No speed, total-RAM, durability equivalence or storage advantage is claimed. The small counters demonstrate avoided lower-content rereading/hashing, not end-to-end performance. Filesystem traversal, upper hashing, publication, FUSE overhead and whole-runtime storage still need a separately defined measurement before any comparison.

Mounts exist only in fresh temporary CI directories. There is one direct FUSE mount attempt and no helper fallback, forced/lazy unmount, persistent helper installation, or host security/network policy change. Busy cleanup is a failure, not permission to bypass it.
