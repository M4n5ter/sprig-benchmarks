# Source-only encoder discriminator: production daemon closure

This plan supersedes the earlier README's proposed no-default-features bridge-only
build. That earlier build was NEVER executed and is NOT the approved CI design.
No comparator production source, lockfile, feature, protocol limit or benchmark
input is changed. No local build/test/runtime has been performed for this plan.

## Retained build evidence

Failed benchmark run 40338242966 / benchmark af859651150e8a2835cf3fd4e0e5dcb07914b34e
built LayerFS ad78914e36b258b360daf13aec164b5655814689 on Ubuntu 24.04 x86_64 with
rustc 1.85.1 (4eb161250e340c8f48f66e2b929ef4a5bed7c181), LLVM 19.1.7, jobs 2.
The exact daemon invocation, from the LayerFS source root, was:

    cargo +1.85.1 build --manifest-path core/Cargo.toml --locked --offline --release -p layerfs-daemon

Before that invocation, the addon helper separately built layerfs-node. The
retained log shows layerfs-bridge compiled once for each invocation. Thus an
arbitrary first/globbed release rlib is NOT safe provenance. The workspace uses
resolver=2; the daemon package selection resolves its own production graph.
There are no release-profile overrides in core/Cargo.toml, and the failed workflow
sets only CARGO_BUILD_JOBS=2 for this graph. Direct/default bridge dependencies
from daemon and store-service activate bridge features default + duplex, including
snow=0.9.6. The earlier no-default-features shortcut is explicitly rejected here.

The fresh proof build need not build the unused Node addon: build the daemon
package alone using its original command/production graph, and select the exact
bridge artifact that this daemon compilation actually links. A clean private
target prevents prior addon/test/other-feature artifacts from masquerading as it.
This is the same declared daemon feature/profile closure, not a claim that a new
ELF will be byte-identical to the old CI binary.

## Required preflight and build capture (workflow owner implements)

Root review/dispatch approval is still required. No cold local build is allowed.
Use a fresh Ubuntu 24.04 x86_64 CI runner; jobs 2; retained locked dependency cache
only (no target cache). Use clean exact ad789 source from its repository root.
Verify the full materialized source manifest against the immutable run manifest
848a841b0876047630cbb2cdd86b49d38aead07577f31b8acc0acad0145147a6, including core/crates,
core/vendor, core/Cargo.toml, core/Cargo.lock, api and .cargo/config.toml. Verify
HEAD and clean tracked/untracked state before and after. No substitution of the
local 9f97 checkout, stable Rust, a different lockfile or copied codec is allowed.
Reject inherited RUSTFLAGS/CARGO_ENCODED_RUSTFLAGS, compiler wrappers, target/profile
or feature overrides. Use the source's ordinary config; its aarch64-only flags do
not apply on this host, and LIBSQLITE3_FLAGS remains the original config value.
Pin/record rustc -Vv and Cargo version. Record all command exit statuses and full
bounded stdout/stderr; no clipped successful evidence. Bound setup/build, proof
execution and artifact size separately within the reviewed job budget.

Fetch the exact lockfile's dependencies before offline build, as in the failed
run. Do not install Docker, invoke a daemon, open a Store/SQLite database, mount,
start sockets, run Cargo tests or use the old fault harness.

Example command after the workflow's explicit admission/source checks:

```sh
# cwd = clean exact LayerFS source root; PROOF_TARGET was created NEW and empty.
# No CARGO_PROFILE_*, CARGO_INCREMENTAL, RUSTFLAGS or feature override is added.
CARGO_BUILD_JOBS=2 CARGO_TARGET_DIR="$PROOF_TARGET" \
  cargo +1.85.1 build --manifest-path core/Cargo.toml --locked --offline \
  --release -p layerfs-daemon --message-format=json -vv \
  > "$EVIDENCE/daemon-cargo.jsonl" 2> "$EVIDENCE/daemon-cargo.stderr"
```

JSON/-vv are observation flags only. Build lib dependencies and the daemon with
the SAME command; never follow this with a separate bridge build that could
replace the selected graph. The daemon ELF is hashed, NEVER executed. Daemon,
bridge and proof build outputs are ephemeral runner files: retain exact hashes
and linkage records in the public evidence, NOT uploaded ELF/rlib backups. The
daemon production graph contains SQLite build dependencies;
compilation does not open a product Store or database.

## Fail-closed artifact linkage selection

The first actual build (run 40356426815) succeeded, but its original linkage
parser failed before proof compilation/execution. These rules incorporate the
captured mixed stdout and rmeta pipeline schema. Original failed evidence remains
unchanged; this revised plan is not an executed encoder result.

Parse Cargo output as data (never evaluate diagnostic text as shell commands).
Require every non-JSON verbose line to have a package/version prefix bound to
both a custom-build compiler record and the exact committed lockfile. Preserve
all raw lines, their counts and hashes; reject all other malformed text:

1. Require successful build-finished, single layerfs_daemon library and
   layerfs-daemon binary artifacts from the exact source root and release profile,
   and exactly one layerfs_bridge lib artifact from
   core/crates/layerfs-bridge/src/lib.rs in THIS invocation. The daemon bin input
   is src/bin/layerfs-daemon.rs, not src/main.rs. Tie package identity to the
   exact checked-out manifest; reject test artifacts.
2. Require bridge features exactly ["default", "duplex"] (set comparison),
   release profile opt_level "3", debug_assertions false and test false. Record
   the full actual profile/features rather than inventing absent JSON fields.
3. Select the ONE .rmeta and ONE .rlib filenames on the SAME bridge artifact.
   Resolve both as existing regular files within the new target/release/deps,
   reject symlinks, and hash both. Never use a stem guess, `find ... | head`, a
   filename glob, or debug/lib paths.
4. Inspect captured -vv daemon rustc invocations as shell-token DATA using shlex:
   exactly one library and one binary Running line with crate-name layerfs_daemon.
   Require the library's `--extern layerfs_bridge=<absolute rmeta>` to resolve to
   that exact selected metadata file. Require the bin's direct bridge extern to
   equal the exact selected bridge rlib. Require the bin's `--extern
   layerfs_daemon=<absolute rlib>` inside release/deps to have exactly the bytes
   of the selected daemon-library artifact. Cargo may report the top-level
   release/liblayerfs_daemon.rlib alias while linking its hash-named deps file;
   verify both SHA256 values rather than guess a filename or glob. Reject any
   missing/ambiguous line, token form or mismatch. Never execute captured commands.
5. Record the bridge compiler-artifact, matched daemon rustc argument, daemon ELF
   hash, bridge rmeta/rlib hashes, Cargo/rustc versions, source hashes and all input hashes
   in a machine-readable linkage manifest. Ensure the rlib stays unchanged through
   proof compilation and execution. Any missing proof leaves the job failed.

Only then compile the inert external proof with the same compiler and dependency
search directory; this invokes no Cargo feature resolution/new dependencies:

```sh
rustc +1.85.1 --edition=2021 \
  "$PROOF_INPUT/proof.rs" --extern "layerfs_bridge=$SELECTED_BRIDGE_RLIB" \
  -L "dependency=$PROOF_TARGET/release/deps" -o "$PROOF_OUTPUT/encoder-proof"
```

The selected production rlib, not standalone proof optimization, establishes the
encoder code/features under test. Hash proof ELF before/after its single finite
execution. Preserve all inputs/logs/output on failure without rerunning. A linker
or evidence-format failure is a failed proof attempt, not a reason to change
features, compiler, crate source, limit or artifact selection silently.

## Fixed proof inputs and expected result

proof.rs and fixture.rs remain EXACTLY the previously frozen source. The public
Answer encoder/decoder receives local values only; no imported daemon entrypoint,
Store constructor or SDK is invoked. Inputs/model are disclosed as a reconstructed
structural subset, not a captured complete daemon reply. Unobserved fields use
explicit byte-width placeholders; all eight optional-observation masks are kept.

Three controls must pass before the first case output:
- Small ordinary Answer encodes and decodes equal to its original value.
- Bytes Answer exactly 65,519 encoded bytes encodes and decodes equal.
- 65,520-byte scalar Answer returns ControlError("control record limit").

Then all eight subset cases must be rejected by the SAME real encoder with that
exact error, at model-predicted Answer lengths 71,643;71,690;71,690;71,737;71,690;
71,737;71,737;71,784 bytes. Expected stdout is the exact nine lines in the adjacent
expected-output.txt, exit zero and empty stderr. The three earlier assertion-based
controls have no separate printed line; exit zero with all final lines proves
execution passed those assertions. No output by itself overrides failed preflight,
linkage, source, byte-bound or command-exit gates.

Even if every encoder assertion passes, the only result is: the exact production-
closure public encoder rejects these reconstructed subsets at the original limit.
It does NOT capture the old daemon's failure receipt or prove the old EOF cause,
run snapshot(), repair LayerFS, qualify mounted behavior, or create speed ratios.
The original Native smoke remains FAILED; raw evidence and missing post-history/
cleanup observations remain unchanged. No pruning/query omission/limit increase.
