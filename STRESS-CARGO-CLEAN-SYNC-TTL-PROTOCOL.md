# Ordinary mounted Cargo: clean journal sync and regular-file read TTL

**Local preparation only.** Publication of the two source branches and this benchmark harness, source CI, and one finite 36-sample run are subject to the pending specific approval. This document does not authorize execution or claim a speedup, complete TTL error-case coverage, or a production promotion.

## Fixed inputs and distinct roles

|Role|Product label|Exact source|Source branch|
|---|---|---|---|
|A / baseline|`sprig-baseline`|`4eb0f4d7afdb19bf22d9667dc520ede8b162c737`|fixed main selection|
|B / clean_sync|`sprig-clean-sync`|`29e25e439cc674152c29712c9d5d315d87f4b14c`|`experiment/clean-journal-sync`|
|C / read_ttl|`sprig-read-ttl`|`23ef28d2a38b58da8a78be1e8fcdd193990371d1`|`experiment/regular-file-read-ttl`|

B is a child of A. C contains the regular-file TTL experiment and its coherence-test commit on A, **not** B's clean-journal change. Thus A→B and A→C compare separate candidates; B→C is not an incremental combination/ablation or evidence that their effects add. Candidate names never substitute for exact sources. Historical `sprig-count`/`sprig-narrow`, LayerFS, and old schema identities are rejected by the new mode; their original modules, tests, reports and refs remain unchanged.

Intended new benchmark ref: `stress/clean-sync-file-ttl`, existing registered manual route `stress-ab.yml`. The old diagnostic ref and `stress/latest-cargo-caebd` are not overwritten. Only this exact new ref is added to the legacy compare workflow's push exclusion, avoiding an accidental additional workload; no blanket trigger, permission or security change.

One production-source clone with three exact detached worktrees and fresh separate targets. Uninstrumented projection-enabled release CLIs, Rust/Cargo1.99.1 and build jobs2. Record compiler versions/hashes, all source hashes, ordinary lib-test/build output and three distinct ELF hashes. Exact clean checkout and source/binary hashes are checked before/after each sample. Root must verify the existing CI of both exact candidate source pins is successful before any benchmark dispatch if publication is approved. This benchmark runs only ordinary lib gates, never the old kernel/fault harness.

Live source branch tips are recorded as matches-fixed/differs-from-fixed/unavailable, **not** admission criteria. Changes or lookup failure do not block a fixed approved SHA or silently repin it. Do not claim latest-at-finish from a fixed selection.

## Unchanged workload, schedule and gates

Reuse the accepted ordinary DAG16 (16 libraries plus application; 17 packages), fixed Rust/Cargo1.90.0 workload image, locked/offline `cargo build --offline --locked --verbose --workspace --jobs 2`, original generation-scoped transport and full correctness/cleanup checks. No LayerFS, pressure stage, tracing, CPU instrumentation, kernel faults, new capabilities or runtime setting changes. The legacy sampler's inherited jobs1 prose is stale; the actual frozen protocol and executable command receipts use jobs2. Historical evidence is never rewritten.

Each incremental mode has six three-way permutation blocks, one fresh sample per product per block:

- inc0: ABC, CBA, BAC, CAB, ACB, BCA.
- inc1: BCA, ACB, CAB, BAC, CBA, ABC.

All36 positions are declared in the fixed plan. Each product occupies every position twice/mode; each pair has three first and three second orderings. All18 inc0 records must pass the original identity/raw/archive/full-oracle/normal-cleanup gates before inc1 admission, with the exact prerequisite report bytes hashed. Stop on the first failure or insufficient reserve; preserve failed and not-run positions and every outlier. No retry, reduced matrix, replacement sample, fallback or selected-run acceptance. The same records form three pair edges, not18 independent comparisons per mode.

Correctness precedes ratios: exact17 Compiling on clean/edit and17 Fresh on no-op/restored, program269→3400, generated build output1→2, target hardlink/symlink/mode/exact-integer-nanosecond probes, complete checkpoint/restored tree equality, original source/main isolation, all acknowledged generations, exact restored compiler binding, and known normal cleanup with no remaining own mounts/containers. Archived raw Python JSON/stdout is authoritative; rounded embedded JS tree numbers are not. All36 accepted raw records are required for any complete performance report. Missing/failing data remain visible with no complete ratios.

Mounted source-coherence tests in source CI and this ordinary Cargo oracle are complementary; neither proves every possible TTL error/coherence path. The manifest makes no correctness or performance claim in advance.

## Resource envelope and evidence

Keep ubuntu-24.04, jobs2, 45-minute job cap, and the setup-inclusive absolute40-minute admission deadline established before checkout/toolchains/runtime. The unchanged pre-sample and post-runtime checks reserve180 seconds of work plus300 seconds of cleanup. No deadline reset or extension.

Exactly one fresh symmetric4GiB measured Btrfs image at a time. Keep the same external inc0/inc1 capacity pilot as setup only, not additional product samples or reusable measured cache. No8GiB fallback. Compiler/runtime, target/cache, retained generations/history, logs and owned temporary paths remain inside the original accounting boundary. Runtime setup is reported separately from sampler-launch-through-exit; whole filesystem Used is not baseline-subtracted or claimed as RSS/product-only bytes. Unknown mutation/cleanup outcomes retain state and stop; no forced cleanup/recovery workaround.

The previously audited36-sample directory series `40459340560` demonstrates this schedule has completed within the existing envelope on an authorized runner, not that these new candidates are guaranteed to fit. All prior admission stops remain binding. No new local fixture or build is needed to prepare the harness.

The explicit `--clean-sync-ttl` collector uses the same reviewed1GiB bounded engine even before identity/setup succeeds: full named-plan admission before creating/copying destination; charge max(logical,allocated) files and directory allocation plus8MiB manifest reserve; bounded1MiB streaming and identity/size checks; pending plus old manifest charged before final atomic promotion. All original source reports/archives remain on collection failure, and any partial destination is marked incomplete. No truncated/subset-success claim. Hidden files are uploaded only within this validated owned evidence tree. This is an evidence-collection cap, not an OS quota or image-backup promise; unchanged runtime image and host-space guards remain separate.

## Minimal integration and reporting

- New fixed identity/schedule/prerequisite module and tests: `stress_cargo_clean_sync_ttl.mjs` and test. Its ABC-named API and `abc*` structural fields are reused internally, but schemas, pins, product labels and paths are explicitly new.
- Existing driver selects one of the two fixed three-way modules; directoryABC, clean-sync/TTL, ownAB and latest-direct are mutually exclusive. Old rounds/pressure/direct guards remain unchanged. New env `STRESS_CARGO_CLEAN_SYNC_TTL_PRODUCTS`; reports/manifests/plans `stress-cargo-clean-sync-ttl-*`.
- New offline summary/tests reuse the existing ordinary Sprig raw/archive validators and require all36 records, exact before/after inputs and full raw evidence. They reject old directory identities even if rebound consistently.
- Narrow collector mode/allowlist and inert tests, plus the experimental workflow body. Old collector modes/defaults are preserved.
- No sampler/product algorithm or fixture change. New setup evidence uses `cst-*`; historical `abc-*` and LayerFS receipts are not relabeled.

Report separate inc0/inc1 distributions, all six ratios per edge, paired geometric means, absolute medians and every phase/space cost, order strata and all negatives. Six paired blocks on one host do not establish p95/p99, broad significance or general superiority. Nested timings/composites overlap and must not be summed/subtracted as exclusive causes. No pooling with the earlier directory, LayerFS, core microbenchmarks or Native experiments. No automatic promotion follows.

Before run: root serial pure new/legacy tests, independent static review, AST/Node/YAML/bash/diff validation, explicit owner publication/run approval, exact successful source CI, remote/ref reconciliation and one manual dispatch only. No local product execution or builds by benchmark delegates.
