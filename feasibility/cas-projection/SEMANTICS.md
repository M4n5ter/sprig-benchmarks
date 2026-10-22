# Temporary-runner semantic contract

This extends the already-authorized private root-CI FUSE/OverlayFS smoke. It is
not a production backend, performance comparison, or mount lifecycle manager.
Use the same private RUNNER_TEMP boundary and normal `umount -i` cleanup. Never
force/lazy-unmount, kill unrelated holders, mount a real disk, or install a helper.
Keep all external writers quiescent during every capture/checkpoint.

## Interface

`BIN` is the built prototype. `STORE`, `LOWER`, `UPPER`, `WORK`, and `VIEW` are
separate absolute private paths. Mount the initial `manifest.json` with the
existing foreground root-only mount command, then OverlayFS with a single lower,
redirect_dir=on,index=off,nfs_export=off,metacopy=off. The capture command validates
the actual mount table rather than trusting these requested options.

Common capture/checkpoint flags:

```
--root STORE --projection-base manifest.json --base APPLIED_COMMIT \
--merged VIEW --upper UPPER --lower LOWER
```

`head --root STORE` initializes/returns `{head,generation}`.
`capture COMMON --output NEW_FILENAME` emits `{event,manifest,stats}` without
moving the head. Output is a new plain manifest inside STORE.
`verify --root STORE --merged VIEW --manifest FILENAME` compares every path,
kind/chunk list, mode, and nanosecond mtime with independent full capture. It
ignores generated IDs; identity checks below are separate. Do not time this oracle.
`checkpoint COMMON` emits `{event,publication,capture}`. Publication status is:

- `published`: head, candidate, candidate_manifest, manifest, merged.
- `noop`: unchanged head and manifest.
- `conflict`: unchanged head, candidate, candidate_manifest, conflict_file,
  structured conflicts. This is an expected JSON result, not a nonzero exit.

`write --root STORE --base COMMIT --path RELATIVE --text TEXT` returns the same
publication variants directly. Text is required, even for an intentional empty
file. `read --root STORE --base COMMIT --path RELATIVE` returns `{revision,path,
bytes}`; bytes is a JSON integer array, limited to the core's 16 MiB read helper.
It can read retained conflict candidates as well as ancestral commits.
`history --root STORE` returns first-parent decoded revisions with all parents.
Each revision includes id, manifest_file, manifest, parents, message. Published
manifest files use the compressed `.manifest.zst` representation. Compare their
decoded `manifest` from this history API with plain capture outputs, rather than
parsing a compressed file as JSON. See PUBLICATION.md for the fresh-store limit.

Strict CAS adds both `--expected-head ID --expected-generation NUMBER`.
A stale expectation fails nonzero and leaves the head unchanged. A conflict
candidate is retained/readable but is not an allowable publication base.

## One bounded sequence

Use a source with a multi-line text file, an unchanged binary file, nested
regular files, an opaque-directory fixture, an ordinary victim file, and an
opaque symlink. Do not include `.lww` unless testing its explicit policy.

1. Import; save H0 from `head`. Create two independent upper/work/view sets A/B
   over the same immutable lower. Before mounting, copy the source root mode and
   mtime to each empty upper root, so upper-root setup is not mistaken for a user
   metadata edit. Capture each untouched view and run `verify`. Require enabled
   lower reuse, positive reused bytes, and zero hashed bytes; report the exact
   fallback reason instead of claiming incremental reuse if unavailable.
2. In A, change the first text line, add an upper-only file, change a copied-up
   file while preserving its old length/mtime, and explicitly copy/forge its
   origin xattr. Rename a lower directory, rename the lower symlink, remove the
   victim, and recreate the opaque directory using the existing capability
   smoke's known whiteout/opaque sequence. Preserve unchanged data elsewhere.
   Capture and verify all paths/content/metadata. Require changed upper data to
   be hashed and unchanged lower data reused. Check symlink target bytes and
   hidden/deleted names independently.
3. Checkpoint A against H0; save HA and candidate_manifest. Capture/checkpoint
   unchanged A against HA. Require identical IDs and a noop with unchanged head.
   The immutable initial manifest and lower bytes must remain unchanged.
4. In B, change a non-overlapping last text line. Capture and verify B against
   H0. Checkpoint B against H0 while head is HA. Require a clean merged result
   with two parents. Read the resulting revision through `read`; it must contain
   both text edits and preserve A's independent namespace changes. B's mounted
   view is intentionally NOT rewritten by this experimental API.
5. Direct SDK `write` a separate file against the latest head. Modify another
   non-overlapping line in B and checkpoint B again using H0 as its known applied
   base, plus `--identity-base B_PREVIOUS_CANDIDATE_MANIFEST` if new local paths
   need identity continuity. Require the SDK file and all independent text edits
   to survive. This explicitly tests the shared publication/merge path.
6. Create a third temporary upper/view C over the same lower. Change the same
   first line incompatibly and checkpoint against H0. Require conflict status,
   exact unchanged head/generation, readable retained candidate bytes/report,
   and unchanged input views. No markers are injected and no fallback merge is
   published. Repeat a direct write with stale expected H0/generation and verify
   nonzero refusal and unchanged head. Reject the orphan conflict candidate as
   a publication base while retaining it for reads.
7. Read all recorded revisions/candidates needed for the byte oracle and verify
   first-parent history retains merge second parents. This is ordinary reopen
   and immutable-history validation, not a power-failure test. Hold an FD in one
   view and require ordinary unmount refusal; verify the view/lower remain valid.
   Close it, normally unmount all overlays, then the lower. Do not kill the FUSE
   server while mounts remain. Report exact residual mounts if cleanup is busy.

A successful merge does not refresh a mounted view or advance its applied base.
Projection base, applied merge base, and previous local identity basis have
separate meanings. No GC exists in this experiment, so every lower reference is
retained. Production integration must own this state and safe epoch lifecycle;
these CLI flags are deliberately an explicit experimental boundary.
