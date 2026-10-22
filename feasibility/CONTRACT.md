# Native snapshot feasibility contract

This is a disposable experiment, not the Sprig implementation or a claim of full feature parity. It tests the cost/space of authoritative read-only Btrfs snapshots, a small revision DAG and generic aligned-block deduplication. Production Sprig remains unchanged.

## Execution

Use official `btrfs-progs` / `python3-btrfsutil` and `/usr/bin/python3`. Only run on explicitly authorized disposable runner filesystems. The script never formats or mounts a filesystem and refuses existing store paths.

```
/usr/bin/python3 native_snapshot.py smoke --root /mounted-fs/new-smoke --source /external/new-synthetic-source
/usr/bin/python3 native_snapshot.py run --root /mounted-fs/new-store --source /external/fixtures/identical --oracle /external/fixtures/identical.json
/usr/bin/python3 native_snapshot.py run --root /mounted-fs/new-history --source /external/fixtures/history-distributed --oracle /external/fixtures/history-distributed.json --steps /external/fixtures/history-distributed-steps.json
```

Source fixtures must lie outside each measured product filesystem, preventing import from borrowing uncharged source extents. All snapshots, mutable trees, DAG and metadata backups reside under the store. The index is ephemeral Python memory; output reports its estimated live size and process peak RSS. Reopening/index rebuilding is not implemented or timed.

## Timing and correctness

Initialization is separate. The measured sequence is import; metadata branch; first usable fork; complete coreutils sha256sum read; second usable fork; complete coreutils sha256sum read; optional 100 edits/checkpoints. Reads use the same shell checksum workload as the frozen comparison. Writes use the same bash/base64/dd fsync/touch workload. Checkpoints are in-process calls; subprocess versus container transport still differs for reads/writes. Timings do not establish a durability-matched or complete-product victory.

Each checkpoint reads and hashes every regular file even when size/mtime are unchanged. Full-file equality only avoids redundant kernel dedup calls, not reads. SHA-256 block hashes select candidates; FIDEDUPERANGE atomically compares actual bytes before sharing. Adjacent matching blocks coalesce into bounded kernel requests. The algorithm always uses 4096-byte aligned blocks and has no workload-specific condition. A non-block-multiple insertion generally cannot share its shifted native suffix; this is not content-defined chunking.

Every history ID must be distinct, remain in the parent chain, and still expose its expected changed-file bytes after all edits. Initial source/main/second/genesis bytes are checked afterward. These extra oracles do not precede the measured warm fork/read. Regular-file oracles include file-set/length/hash; synthetic smoke additionally checks opaque symlinks, rename/delete, same-size fixed-mtime edits, no-op and rejection before publishing a special file. This is not a full metadata/merge/API acceptance suite.

## Publication and limits

All writers must be quiescent. Capture stat checks detect some races, not arbitrary application transactions. One process holds an exclusive metadata lock. A read-only snapshot is created synchronously at its final unique name before fsynced revision metadata and atomic fsynced head publication. Failed publication can leave an orphan; automatic recovery is not implemented. Checked write fsync remains. Snapshot transaction durability relies on normal barriers and correct device flush/FUA behavior.

The prototype has no merge, stale-writer resolution, SDK mutations, blame, GC, restart/recovery, export, or full security boundary. It accepts only fresh trusted stores and UTF-8 names, rejects nested mounts/subvolumes and special files, keeps symlinks opaque, and rejects hardlinked mutable workspace files. Import uses byte-copy and splits source hardlinks. No performance result overrides these missing capabilities.

Physical storage must be measured externally after sync, with empty-filesystem baseline and final Data + Metadata + System used. Report identical profiles/compression/mount parameters for both products. Global reserve is part of metadata, not an additional used category. Ordinary du double-counts shared extents and is not the primary physical measure. Official btrfs filesystem du extent-union output can supplement whole-filesystem usage.
