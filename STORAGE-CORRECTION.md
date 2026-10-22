# Storage measurement correction

The published ext4 runs measured Sprig's store tree, but measured only LayerFS's Docker store volume plus SDK home. They did **not** measure LayerFS's active workspace overlay database or other container-writable state. Calling these figures a complete matched active footprint was incorrect.

## What remains and what is withdrawn

- Original raw JSON/CSV and their checksums are preserved without modification. Their `activeStore` field names describe the old collector, not a guarantee of complete product accounting.
- Whole-product storage ratios, storage winners/losers, and the claim that native-tree-plus-object bytes alone prove Sprig cannot beat the complete comparator footprint are withdrawn.
- The observed Sprig-only footprint reduction across versions still compares the same measured components. It is not a complete cross-product storage comparison.
- The full-task timers, changed-file/readback checks, history-ID membership and merge smoke are independent of the omitted storage scan. Their reported values remain measured observations with existing durability, interface and machine caveats. No automatic latency correction can be inferred from missing storage bytes.

## Verified source evidence

At pinned LayerFS `2aaf2552ce21154928b9f9c83582e41a637f5910`:

- [SDK sandbox setup](https://github.com/Ephemeral-AI-Lab/layerfs/blob/2aaf2552ce21154928b9f9c83582e41a637f5910/sdk/js/native/src/sandbox.rs) sets the workspace overlay database to `/layerfs-local/overlay/overlay.sqlite`.
- [Docker container encoding](https://github.com/Ephemeral-AI-Lab/layerfs/blob/2aaf2552ce21154928b9f9c83582e41a637f5910/core/crates/layerfs-sandbox/src/backend/docker/container.rs) mounts only the named store volume at `/layerfs-store`. The overlay therefore resides in the container writable layer, outside the measured volume/home paths.
- The same file's `plain_volume` validation requires a plain local volume with null/empty Options. A proposed bind-option volume would be rejected; no comparator code has been patched to bypass that restriction, and that proposed paired Btrfs driver was not run.

A replacement complete-storage comparison must inventory persistent store, active overlays, SDK state, writable container data and attributable logs, distinguish shared immutable runtime/software from product-written state, and measure both products at the same lifecycle point. A filesystem's shared extents must not be double-counted. Until then, existing cross-product storage columns are explicitly **measured subsets**, not total product footprint.
