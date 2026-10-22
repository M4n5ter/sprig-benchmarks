# Experimental upper-absence subtree capture

This candidate changes capture only. It does not change the content format,
publication durability, merge rules, mounted-view lifetime, or benchmark sample
operations. It is not production support or a performance claim.

## Proof and boundary

The existing mount validation must establish the exact single read-only Sprig
projection, its pinned manifest, the native upper directory, and metacopy being
off. The projection and immutable object store are trusted. Writers and mount
changes must be quiescent throughout capture; inventory checks are race
detection, not a writer freeze or hostile-process sandbox.

For a directory, capture reads its actual merged metadata, then completely
enumerates the native upper through an owned, no-follow directory descriptor.
Every upper ancestor, including the root, must report ENODATA for both
trusted.overlay.redirect and trusted.overlay.opaque. Any value, including an
empty value or opaque=x, or any uncertain result disables the certificate for
that entire subtree.

Under these conditions, a base child absent from the complete upper inventory
cannot have upper descendants: those would require an upper directory at that
child. No redirect or opaque ancestor changes its lower mapping. Its entire
component-bounded manifest prefix can therefore be reused without opening,
stating, enumerating, or reading xattrs from the merged descendants. Directory
modes and nanosecond mtimes and opaque symlink targets are retained exactly.
The currently visited directory's metadata is never substituted from the base.

Names present in the upper are resolved through the kernel's merged view.
ENOENT means hidden; visible files, directories, and symlinks follow the ordinary
capture path. The implementation does not decode whiteouts or redirect targets.
Unsupported visible special files remain rejected. Copied-up files still have
their contents hashed even if size, mtime, or a copied origin hint is unchanged.

Clean inventories include child identities, types and metadata, and are
re-enumerated before success. Existing final mount-binding and lower-root-origin
checks remain. Reused file chunk types and lengths are checked, each file's
aggregate length is verified, and only duplicate chunk-length lookups within the
same capture are memoized. No persisted cache or mtime-based reuse is introduced.

Logical identities continue through the existing assignment and reconciliation
rules. A directory's optional origin hint is omitted only when its same-path
base identity necessarily takes priority; root provenance checks are unchanged.

## Observability and validation

Capture reports certificate_subtrees_reused and separate reused file,
directory, and symlink counts. Existing entry, reuse, and byte counts include
these entries. certificate_inventory_seconds and certificate_reuse_seconds are
disjoint walk categories. Final inventory rechecks are included in finalize.

Local grouped differential checks compare ordinary traversal with certified
capture, including component boundaries, deep subtrees, changed siblings,
metadata and symlink preservation, malformed object references, inventory
changes, and conservative fallback. They do not demonstrate real OverlayFS
whiteout, redirect, or opaque behavior. The authorized temporary-runner semantic
suite must still compare every captured manifest with independent full capture,
exercise those kernel behaviors, and pass the shared publication/merge/history
checks before a separate unchanged-sample performance comparison.

The prior diagnostic measured capture and publication separately. Its timings
are evidence for investigating this path, not predicted savings: this candidate
adds native inventory work and must be measured independently.
