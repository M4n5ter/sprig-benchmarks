# Isolated native-snapshot feasibility

This is an experimental, separately labeled infrastructure series, not a production Sprig backend or a claim of basic-feature parity. The ext4 production harness and results remain unchanged.

## Verified capability smoke

[Run 39764406619](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39764406619) passed at `a8879edba5b7476542cc8b6be99c21f03a286f68`. A GitHub temporary Linux runner created a new 2 GiB sparse regular-file image, formatted only that file, and mounted it through a loop device. Data profile single, metadata DUP, no compression, noatime. The private mount is unmounted on exit. No user computer or existing physical disk is modified.

The test creates a 4 MiB deterministic file, a readonly subvolume snapshot, a forced reflink copy, and an independently written duplicate. Kernel FIDEDUPERANGE returns success and exactly 4 MiB deduplicated. After modifying the source, the snapshot, clone and deduplicated target retain their original bytes.

| Stage | Filesystem used bytes including metadata/system | Data used bytes | File extent-set union |
|---|---:|---:|---:|
| Empty | 294912 | 0 | 0 |
| Independent duplicate present | 8749056 | 8388608 | 8388608 |
| After deduplication | 4554752 | 4194304 | 4194304 |
| After 8-byte source edit | 4558848 | 4198400 | 4198400 |

`btrfs filesystem usage -b` records total used space; `filesystem df -b` separates groups, and `filesystem du -s --raw` uses FIEMAP and de-overlaps shared extents. The observed exclusive + set-shared union matches Data used in this uncompressed fixture. GlobalReserve is part of metadata and is not added again. Reserved/allocated block-group capacity is not mislabeled actual used space. Ordinary du would double-count reflinks and is not the physical-space verdict.

[Raw measurements, mount parameters, package/environment details and checksums](../measurements/2026-10-22-btrfs-smoke/). [Official accounting documentation](https://btrfs.readthedocs.io/en/latest/btrfs-filesystem.html).

This validates a tiny uncompressed capability/accounting case only. It does not establish application performance, crash safety, full feature parity, or the correctness of accounting under arbitrary compressed/multi-device filesystems. Any later paired experiment must use identical fresh filesystems for both implementations, keep the common input outside those filesystems, and count all product snapshots, indexes, metadata and recovery generations.
