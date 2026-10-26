# Source-only encoder proof preparation — NOT EXECUTED

This is a separate inert proof package for failed benchmark run40338242966 at
benchmark af859651150e8a2835cf3fd4e0e5dcb07914b34e and LayerFS
ad78914e36b258b360daf13aec164b5655814689. It does not change the original artifact,
benchmark status, comparator source, protocol limit or retained workload.

## What it can and cannot prove

The Python preparer reconstructs a **structural subset** of the snapshot response
from captured103 fork results and100 commit records. The model follows the pinned
snapshot's first64 name-ordered branches, ancestry pages and deduplication. The
public encoder is then asked to encode that subset, with unchanged65,519-byte
record limit. A rejection proves the real encoder rejects this reconstructed
value, not that the failed daemon actually reached that encoder path. The actual
daemon reply/failure receipt was not captured.

Only byte-width placeholders represent unobserved cursor contents, workspace
roots, namespace/revision integers and last-known live/idle state. They are
explicitly labeled in model.json and are never sent to a daemon. Eight models
cover successful/absent optional dirty/revision observations for all three views.
Whole store statistics and six outer fields are omitted, so the value is smaller
than the corresponding complete response; it is not a fake complete reply.

proof.rs invokes only public Answer::encode/decode on local values. It has small
success and exact-limit/+1 scalar controls. Those are encoder controls, **not a
proposal to shrink/skip the benchmark query**. There are no sockets, mounts,
containers, subprocesses, SQLite/Store creation, fault harnesses or product calls.

## Preparation and evidence

prepare_fixture.py requires exact raw SHA
c2233433f0fedde7d6bca1fb04e0906b33521ee5592645e34ef4614c02ecefd3
and source-manifest SHA
848a841b0876047630cbb2cdd86b49d38aead07577f31b8acc0acad0145147a6.
It writes NEW fixture.rs and model.json only; never overwrites either. Input files
are the existing artifact/results/latest-combined-layerfs-history-distributed.json
and artifact/results/layerfs-source-hashes.txt. No artifact is redownloaded.

## Execution prerequisites — root approval and serial ownership required

No build or proof execution is authorized by this package. The local checkout is
9f97, although inspected files match the run's source manifest; it must NOT be
relabeled ad789. No local LayerFS target cache,1.85.1 toolchain or blake3-1.8.5
registry source is present. Current overlay free space was1,800,155,136B. A cold
local build is forbidden; build-space/time needs have not been measured.

A later approved environment needs a clean exactad789 checkout,1.85.1, and its
locked registry dependencies. Verify all four crate source trees/manifests,
core/Cargo.toml/Cargo.lock and .cargo/config.toml against the retained run manifest
before/after compilation. No source edits or new lockfile are needed. These are
**proposed commands, not executed commands**:

```
# Run from exact source root, after full identity/provenance and resource admission.
CARGO_BUILD_JOBS=2 CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 \
  cargo +1.85.1 build --manifest-path core/Cargo.toml -p layerfs-bridge \
  --no-default-features --locked --offline --target-dir "$PROOF/target"
rustc +1.85.1 --edition=2021 "$PROOF/proof.rs" \
  --extern layerfs_bridge="$PROOF/target/debug/liblayerfs_bridge.rlib" \
  -L dependency="$PROOF/target/debug/deps" -o "$PROOF/encoder-proof"
```

The proof-only no-default-features choice disables duplex/snow, not the control
encoder: its source is unconditional. Dependencies are bridge→content/history/
telemetry and exactblake3-1.8.5/transitives. A normal public encoder compile is
preferable to copied codec/stub code. Root must impose its own finite build/run
bounds, private target, source/ELF hashes and disk floor before any execution.
No timing result from this proof is a product-performance measurement.

## Source references (exactad789 bytes verified against run manifest)

- api/binding/src/dispatch.rs:34,56–104: filter history only after full daemon reply.
- core/crates/layerfs-daemon/src/control/inspect.rs:20–73: snapshot construction.
- core/crates/layerfs-store-service/src/operator/inspect.rs:24–28,114–259:
 56KiB tracked budget; continuation map added outside spent.
- core/crates/layerfs-history/src/contract/query.rs:73–84,127–134:
 160-byte cursors and record-byte page bounds.
- core/crates/layerfs-history/src/contract/records.rs:14–18,539–542: record widths.
- core/crates/layerfs-bridge/src/wire.rs:3–15:65,519-byte control limit.
- core/crates/layerfs-bridge/src/control_reply.rs:16–65: real Answer encoder.
- core/crates/layerfs-bridge/src/control_sdk.rs:115–167: exact value encoding.
- core/crates/layerfs-daemon/src/control/serve.rs:95–139: encoding error closes send.

The independently checked all-observed model is52,373 tracked bytes plus19,327
continuation-map bytes=71,700 before outer wrappers/statistics. It remains a
source-derived explanation, not proof of daemon crash/OOM/data loss. The benchmark
remains FAILED, ratios unavailable. No history pruning, count reduction, limit
increase, query omission, comparator patch or public upstream action is proposed.
