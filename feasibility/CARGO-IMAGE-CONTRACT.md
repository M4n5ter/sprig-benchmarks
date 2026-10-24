# Shared Cargo software image (draft, not executed)

Build once outside timed samples on the authorized temporary GitHub runner.
Resolve the official ubuntu:24.04 repository digest, record its full inspect JSON,
and pass that immutable repository digest as BASE_IMAGE. Do not use a different
base image for either product. Install the official Rust 1.90.0 minimal toolchain
using the runner's existing rustup. Copy only that toolchain directory into a new
synthetic build context as toolchain/, never the user's Cargo home, credentials,
configuration or registry cache. Include the reviewed tree_oracle.py.

Build this Dockerfile with the official Docker daemon, record the resulting
immutable image ID, full inspect JSON, rustc -Vv, cargo -V, cc --version, dpkg
package versions, compiler/linker hashes and all toolchain file hashes. Save that
single image to an archive for the existing runtime_storage enter/leave protocol.
Software setup is excluded from operation timings and disclosed as a separate
software/runtime-ready baseline, identical for both products. LayerFS injection
of its own daemon stays part of its measured runtime footprint.

The actual Cargo commands use the same image ID and /opt/rust/bin PATH on both
sides, workspace-local Cargo home, target and temporary directories. Sprig uses
/work/{.cargo-home,target,.tmp}; LayerFS uses its actual
/workspaces/N/{.cargo-home,target,.tmp}. These absolute paths can affect
restored compiler fingerprints; actual verbose Fresh/Compiling output is
reported rather than assuming equivalent cache hits. Both retain target and incremental caches. Sprig ordinary
compiler containers run with the image's default root; LayerFS sandbox exec uses
its official UID 501/GID 20. This difference is disclosed, not hidden by adding
capabilities or modifying security. No privileged compiler container, additional
device, FUSE access, networking or security option is required by this draft.

First validate one owned-writable/LayerFS pair for CARGO_INCREMENTAL=0 and one
for =1. Stop on any lifecycle/oracle failure. Three paired repeats are meaningful
only after the real smoke passes. The frozen seven-scene comparison remains a
separate protocol and must not wait for or be replaced by this tiny Cargo scene.
