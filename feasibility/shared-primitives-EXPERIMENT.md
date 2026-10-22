# Shared object and revision primitives

The `core` directory is a source snapshot of production commit
22e6e4c289be67b78d39a7eae157bfa3219d23a4, with only src/content.rs,
src/metadata.rs and src/lib.rs changed. The production checkout is untouched.
The `adapter` starts from the linear-inventory candidate measured at benchmark
commit 8d00ee96. Diffs are included. Build adapter/Cargo.toml; its dependency is
../core. No mount privilege or benchmark operation changes are required.

The adapter sample driver remains byte-identical to SHA256
17b510933bf844b23fdff79df9dbbefa1bffc8ad086ac43bd3dfb4c6f464f70e.
Use the unchanged real-kernel semantic driver and paired performance sample.
All timing fields and opaque filename result fields remain available. History
returns the decoded embedded manifest as before, adding its logical clock.

Local validation: adapter 9 grouped tests, core 7 grouped tests, adapter clippy
all targets with warnings denied, and both crates' formatting checks passed.
Independent read-only review approved final commit.rs SHA256
b5b9fbe9997c166233208b236ff4daf58efc90eaf82c145ff963313e77c7d4c3.
See adapter/PUBLICATION.md for integrity, durability and format boundaries.

An unmounted, alternating seven-round direct-write CLI experiment issued 100
commits over the same 334-entry synthetic source in each fresh store. It checked
100 distinct IDs, 101 history entries and all final written bytes after timing.
Median summed write-call time was 6.514666 s before and 5.928848 s after, about
9.0% lower, with overlapping samples and one slower candidate pair. This is only
local publication-path evidence, not a mounted workload, isolated fsync timing,
or proof of an end-to-end speed target. The direct-write path does not measure
incremental capture's batched ingestion benefit.

Each local store used 608 versus 507 files; allocated reference bytes were
5,287,936 versus 4,874,240. These local stat blocks are not whole-filesystem
physical extent accounting and are not a cross-product storage comparison.
The raw seven-round records and reproducible script are retained separately.

Benchmark integration: core is stored as cas-shared-core, adapter as cas-projection, with the sole Cargo path adaptation ../core to ../cas-shared-core. The production checkout remains a provenance reference, not the linked library for this candidate. Both workflow source manifests include the complete experimental core. Mounts, semantic driver, performance driver, fixtures and accounting are unchanged.
