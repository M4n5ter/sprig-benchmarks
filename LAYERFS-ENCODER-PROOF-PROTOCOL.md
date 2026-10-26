# Pinned LayerFS source-only encoder discriminator

**Revised harness preparation; no encoder outcome yet.** The first source-only
CI attempt [40356426815](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40356426815)
built the daemon successfully but failed in the linkage parser before compiling
or executing the proof. This is not a mounted rerun, performance comparison,
comparator fix or successful Native smoke. Original run 40338242966 and its corrected analysis remain failed with no
ratios. The actual daemon reply/server cause was not captured.

## Question and immutable inputs

Does the unmodified public encoder from LayerFS
`ad78914e36b258b360daf13aec164b5655814689`, compiled with the failed run's production
daemon feature closure, reject the eight explicitly reconstructed structural
subsets from that run? The frozen source-only fixture uses labeled byte-width
placeholders for unobserved fields. It is not a captured daemon reply. Expected
subset sizes are 71,643–71,784 bytes against the unchanged 65,519-byte control
record limit. Small, exact-limit and limit-plus-one scalar controls are separate
encoder controls, not a proposal to shrink the mounted workload.

The eight files under `feasibility/layerfs_encoder_inputs/` preserve the reviewed
proof, generator, fixture, model, original preparation note, production-closure
addendum, expected output and captured source-hash manifest. The **original
README's unexecuted no-default-features proposal is superseded**: this workflow
uses the full production daemon closure, with bridge `default` and `duplex`.
The five original proof-package inputs remain byte-identical for provenance.
The fixture was generated from the exact hash-bound public raw report described
in `model.json`; this CI verifies prepared input hashes and all 1,552 captured
source/build hashes, not a fresh download/re-audit of the old mounted artifact.

## Build and linkage

Use Rust/Cargo 1.85.1, the committed lockfile, an empty private external target and
`CARGO_BUILD_JOBS=2`. No profile/feature overrides, source edits, new lockfile,
addon rebuild or no-default-features substitution. The daemon build argv is the
original `cargo +1.85.1 build --manifest-path core/Cargo.toml --locked --offline
--release -p layerfs-daemon`, adding only Cargo JSON and verbose diagnostic output.
The daemon is compiled but **never executed**.

The bridge rmeta and rlib are uniquely selected from the SAME successful Cargo
compiler artifact with exact default+duplex features. Cargo's pipelined daemon
library invocation must use that exact bridge rmeta; the daemon executable must
use the exact bridge rlib directly and link the hash-bound daemon library alias.
Both Cargo artifacts and verbose invocations are bound. No filename-stem guess,
first-match glob or assumption that addon and daemon artifacts are interchangeable.
Cargo -vv build-script lines are classified separately from complete JSON-object
records. Every `[package version]` prefix must match a custom-build compiler
record AND the verified committed lockfile. Full raw lines, classification counts
and hashes remain in evidence; arbitrary malformed/unbound text is rejected. The immutable workflow constructs the external proof compiler argv from this
selected path; the validator does not attest arbitrary external compiler commands.
Record source, lockfile, tools,
bridge/daemon artifacts and proof ELF hashes. Those build outputs are ephemeral
and hash-only in the uploaded evidence; executable/rlib bytes are not uploaded. The external proof links this exact
bridge and invokes only public `Answer::encode/decode` on local values. Standard
Cargo build scripts compile normal dependencies; no socket, Store/SQLite runtime,
daemon, container, mount or filesystem-image workload is invoked.

## Finite resource and failure policy

Existing Ubuntu 24.04 runner, jobs 2, 45-minute job cap and shared benchmark
concurrency group. Setup starts the 40-minute admission deadline. Fetch/build
share its remaining time minus 120 seconds for evidence; proof compile and proof
execution each have a 60-second bound. These source-only processes may be stopped
on deadline; there is no live mounted filesystem to recover. Require 8 GiB host
free space before the fresh build, without changing runner class or provisioning.
No image allocation, Docker service changes, paid settings or permissions change.

The capture wrapper starts each compiler/proof in its own new process group.
It streams through fixed 64 KiB reads, rejects Cargo streams above 32 MiB and
proof/compile streams above 1 MiB, terminates only that owned source-only group
on overflow/deadline, and drains for at most five seconds. Each stream has an
additional 1 MiB bounded drain reserve. Any bytes beyond that reserve are counted
and hashed as observed-but-not-retained, never described as complete evidence;
if EOF was not reached, the unobserved remainder is explicitly unknown. Success
requires exit zero, both EOFs, a settled group, no overflow/deadline/signal and all
bytes retained. Four capture stages retain at most 140 MiB of stream bytes,
plus small receipts/input files, below the 1 GiB artifact budget. This policy
cannot truncate a failed stream into success.

The validator also rejects malformed identities, feature/linkage ambiguity,
source changes, nonzero statuses, wrong controls/output or changed proof ELF. The final named evidence
inventory records sizes/hashes (including its own encoded size) and enforces the
existing 1 GiB artifact acceptance
budget; any exceeded budget is a failure, never a partial-success claim. No
automatic retry, alternate feature build, limit increase or mounted follow-up.

## Interpretation and route

A pass proves that this exact public encoder rejects these reconstructed values
and accepts the declared boundary controls. It narrows a source-derived overflow
explanation; it does **not** prove the actual daemon took that path, establish a
crash/OOM/data-loss cause or repair the failed sample. A failure or linkage
ambiguity is retained as inconclusive, not retried to green.

Use the registered `native-fork-ab.yml` path only on a separately reviewed
experimental ref. The current stress branch's workflows and held writable canary
remain unchanged. No default-branch write. Root review, inert tests, publication
verification and a separate one-dispatch approval are still required.


## First attempt and narrow harness correction

Run 40356426815 retained all 37 artifact files / 1,159,589 bytes. The daemon build
returned zero in 124.30 seconds with complete bounded capture and no signal or
overflow. Its stdout contained 247 JSON records and 932 fully prefixed verbose
build-script lines. The original parser wrongly treated every line as JSON; a
second actual-schema finding was the valid rmeta pipeline described above. No
bridge/daemon binary hashes were produced before that parser rejection, and the
ephemeral build artifacts are unavailable. Offline log compatibility cannot
substitute for a future actual encoder execution. The original failed run and
artifact remain immutable; no mounted/performance result is reclassified.

Creating the diagnostic ref also accidentally triggered legacy push run
[40355668729](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40355668729).
It was cancelled during compilation; product smoke, runtime preparation and
repeated-comparison steps were all skipped. Only after cancellation was terminal
was the one manual source-only attempt dispatched. The revised experimental
`compare.yml` adds only this exact diagnostic ref to its existing push-ignore
list; other refs/default branch/workflow bodies are not disabled or changed.
