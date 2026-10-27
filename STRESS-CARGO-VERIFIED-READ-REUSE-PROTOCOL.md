# Ordinary mounted Cargo: verified first-read reuse

**Local preparation only; publication and one mounted run remain pending specific approval.** No mounted speedup, complete error-case coverage, or promotion is claimed. Local core microbenchmarks motivated this experiment but are not mounted end-to-end results and will not be pooled with it.

## Fixed separate candidate

|Role|Product label|Exact source|Source branch|
|---|---|---|---|
|A baseline|`sprig-baseline`|`4eb0f4d7afdb19bf22d9667dc520ede8b162c737`|fixed main selection|
|B verified first-read reuse|`sprig-verified-read-reuse`|`f61ce655d9270e206d97e20bc104644c821e4e5d`|`experiment/verified-read-reuse`|

B is based on A, not stacked with the clean-journal, read-TTL, directory-count, layout or Native restore experiments. It reuses the already verified owned chunk bytes for the first read while discovering base spans; later reads still revalidate requested chunks. It does not remove the first discovery's full-base integrity checks. The benchmark is an ordinary application-level acceptance comparison, not an instrumented attribution of first-read CPU savings or later-read neutrality. All observed later/negative phase costs remain reportable.

Proposed new benchmark ref: `stress/verified-read-reuse`, registered manual workflow `stress-ab.yml`. Only that exact ref is added to the legacy push workflow exclusion to prevent an accidental second workload. The earlier `stress/clean-sync-file-ttl`, directory and LayerFS refs, source modules, tests and evidence are preserved; no main, permission, billing or default-branch changes.

One source clone with two exact detached worktrees and separate fresh targets. Product toolchain Rust/Cargo1.99.1, projection-enabled release CLIs, build jobs2. Preserve ordinary lib-test/build output, toolchain/source/ELF hashes and exact clean source/binary checks before and after each sample. If publication is approved, the candidate's existing standard CI at this exact pin must pass before the single benchmark dispatch. This job never runs the old kernel/fault harness. Record observed branch tips as matches-fixed/differs-from-fixed/unavailable without a freshness stop or silent repinning.

## Fixed 24-sample schedule and unchanged oracle

Six pairs per incremental mode, one fresh image/sample per product per pair:

- inc0: AB, BA, AB, BA, AB, BA.
- inc1: BA, AB, BA, AB, BA, AB.

Each product is first three times and second three times per mode. The plan declares all24 positions; all12 inc0 records must pass the exact identity/raw/archive/oracle/normal-cleanup prerequisite before inc1. Stop on the first failed sample or insufficient resource reserve; retain failed and not-run positions and every slow pair. No retries, substitute samples, reduced matrix, alternate source or exclusion of outliers. All24 accepted raw records are required before any complete ratios are emitted. Six pairs on one host do not establish statistical significance or p95/p99 tails.

Reuse the frozen ordinary DAG16 workload:16 libraries plus application,17 packages, Rust/Cargo1.90.0 shared compiler image, offline/locked workspace builds with actual `--jobs 2`. The sampler's inherited jobs1 annotation is stale; authoritative executable protocol/command receipts remain jobs2, and historical raw evidence is not rewritten.

Correctness gates remain unchanged:17 Compiling on clean/edit and17 Fresh on no-op/restored;269→3400 program output and generated value1→2; complete checkpoint/restored tree hashes, modes, symlinks, hardlinks and exact-integer-nanosecond timestamps; original source/main isolation; all acknowledged generations; compiler-generation binding; known normal cleanup with zero remaining own mounts and containers. Standalone raw Python JSON and archived command bytes are authoritative over JS-rounded embedded tree numbers. No LayerFS, pressure, trace, CPU instrumentation, fault injection or new privilege is included.

## Resource and evidence envelope

Keep ubuntu-24.04, jobs2,45-minute job and setup-inclusive absolute40-minute admission deadline established before setup. Existing pre-sample and post-runtime checks reserve180 seconds work plus300 seconds cleanup, with no deadline reset/extension. At most one fresh symmetric4GiB measured Btrfs image exists in the measurement loop. The unchanged external inc0/inc1 capacity pilot is setup only, not additional product samples or a reusable measured cache. No8GiB fallback.

Keep original image/runtime/target/cache/history/log/owned-temp accounting. Runtime provisioning is timed separately from the primary sampler launch-through-exit wall; internal `fullTaskSeconds` is also reported separately. Whole filesystem Used is not baseline-subtracted or described as RSS/product-only storage. Unknown mutation or cleanup outcomes retain state and stop; no forced recovery. Successful image disposal follows the original durable-report/normal-detach checks, not a new retention or backup promise.

The explicit collector flag `--verified-read-reuse` selects the previously reviewed bounded engine even if setup fails before creating the identity. Preserve full named-plan admission before any copying,1GiB complete evidence cap, max(logical,allocated) file/directory charges,8MiB manifest reserve,1MiB chunked identity-checked copying, and pending-plus-old manifest admission before atomic final promotion. Failure leaves original reports/archives intact and marks any partial destination incomplete. Hidden files are uploaded only within this validated owned evidence tree. This is a collection cap, not an OS quota or uploaded-image backup.

The completed earlier36-sample Sprig campaigns demonstrate feasibility within the same runner envelope, not guaranteed timing for this new candidate. This smaller24-sample schedule leaves the same admission/cleanup reserves intact. No new local product build, fixture generation or runtime is required for preparation.

## Minimal integration and interpretation

- New fixed identity/plan/prerequisite module `stress_cargo_verified_read_reuse.mjs`, new schemas/stems and two explicit labels. The existing `abc*` field/API names are internal reuse only, not a claim of three participants.
- Existing driver selects this mode via `STRESS_CARGO_VERIFIED_READ_REUSE_PRODUCTS`, mutually exclusive with directoryABC, clean-sync/TTL, legacy ownAB and direct LayerFS modes. Historical rounds, pressure, trace-off and identity validators are unchanged. Only the new mode uses12 expected records per invocation.
- New offline summary and pure tests require all24 samples and preserve every phase and negative. There is exactly one A→B comparison edge per mode, with six ratios; two position strata have three observations each. Historical identities cannot be admitted even when consistently relabeled/rehashed.
- Narrow collector allowlist uses `vrr-*` setup evidence and `stress-cargo-verified-read-reuse-*` manifests/reports; old caller defaults are unchanged. New tests cover early-failure cap, hidden full archives, missing evidence, duplicate/malformed positions, mixed modes and final-budget failure.
- No sampler, runtime, fixture, product algorithm, old result or historical module is modified by this harness change.

Report separate inc0/inc1 outer and internal walls, all six paired ratios, geometric means, medians/ranges, order and position strata, every phase/space cost and all failures. Whole runtime-inclusive costs must not be silently conflated with sampler wall. Nested phase/convenience timings overlap and are not additive or subtractable as exclusive storage/CPU causes. The entire workload may show a smaller, absent or negative effect despite local first-read gains; later/no-op/restored and cleanup costs remain binding observations. Do not pool with core microbenchmarks, prior clean-sync/TTL, directory, Native or LayerFS experiments. No automatic promotion or follow-up run.

Before any run: root serial pure new/legacy tests and syntax checks, independent static review, explicit publication/run approval, exact candidate standard CI, fresh remote/ref reconciliation, then at most one manual dispatch. Benchmark delegates perform no local build, test or product/runtime execution.
