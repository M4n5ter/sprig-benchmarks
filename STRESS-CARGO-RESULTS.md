# Cargo DAG16 v2 acceptance — capacity failures and first passing product gates

[Run40188875391](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40188875391), benchmark `d0095a97b40d805abc486d2fea1c74493751504a`, production `70307d3480239e96a24552d8595ec537927d9301`, failed in6m52s. This is **not a passing Cargo comparison and supplies no product performance ratio**.

The source builds/tests, real projection/writable gates, shared pinned1.90.0 compiler image preparation, branching17-package fixture and external capacity pilot steps completed. During the first Sprig sample's runtime setup, `docker load` of the compiler archive failed before the product sampler launched. The inherited runtime helper did not print the captured subprocess output, so the underlying cause is unknown; ENOSPC is only a hypothesis, not a finding. No capacity limit or correctness gate is relaxed.

Artifact upload then failed with EACCES traversing the root-owned capacity-pilot directory. GitHub's artifact API confirms zero artifacts. Only full CI logs, failed-step logs and artifact API response could be recovered; these are preserved in `data/stress-20261025/cargo-first-pilot-failed` with hashes/provenance. Missing raw measurements cannot be reconstructed or reported as acceptance. Recovery work must preserve failed-command diagnostics and copy only evidence into runner-readable artifact staging without altering retained product/runtime state.

The v2 branching graph, matched compiler `--jobs 2`,17-package Fresh/Compiling expectations,269→3400 executable outputs, exact full-tree metadata/content oracle, shared absolute job budget,2GiB image and fail-closed uncertain cleanup remain required for the next attempt. Old correctedCargo v1 acceptance is not relabeled as DAG16 v2 acceptance.

## Evidence-enabled retry: runtime import ENOSPC confirmed

[Run40190944293](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40190944293), benchmark `2643eb5492d8fcd4b444d987fef991f89ff41287`, failed in6m35s before any product sampler. The only changes preserved the failed Docker subprocess output and made allowlisted copied evidence readable by artifact upload; image construction,2GiB bound, product pins and acceptance protocol were unchanged. The collector/upload succeeded, and all25collected files were independently verified by bytes/SHA256.

Docker reports `no space left on device` while writing the Rust `libcore` rlib during image import. Read-only diagnostics immediately after the failed Docker command report2,146,435,072bytes allocated out of2,147,483,648, with only1MiB unallocated; filesystem Used342,478,848bytes (df348,246,016) and apparent free1,575,038,976bytes are **post-failure** observations. They do not establish the transient import peak or explain all reservation/chunk behavior. No unsupported exact peak attribution is made.

The immutable image reports1,005,165,334bytes; saved archive logical size1,013,662,208bytes. Rust1.90.0 toolchain allocation593,596,416bytes, including12,972,032bytes under share/doc; installed components are only cargo, rust-std and rustc. This does not support the speculative stale-documentation explanation. External pilot target allocation is9,134,080bytes for incremental0; that pilot did not cover the Docker import transient footprint.

Setup rollback and outer normal unmount/loop detach completed. There are still **zero product measurements and no Cargo performance comparison**. A failed runtime-load capacity constraint cannot be relabeled as a Sprig or LayerFS correctness failure. No filesystem enlargement, selective runtime deletion, oracle relaxation or further speculative retry is implied. Complete diagnostic artifact and provenance: `data/stress-20261025/cargo-evidence-retry-failed`.

## First fresh 4 GiB incremental0 attempt: product gates pass, one archive gap

[Run40192707608](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40192707608), benchmark `d11cec87bd7c8b2ca8bd6377724c49b9392a0d08`, passed in6m8s. This is the explicitly authorized Cargo-only resource revision `sprig-cargo-resource-4g-v1`: both products used fresh4,294,967,296-byte Btrfs images; native pressure remains2GiB. No8GiB attempt was needed. The original2GiB failures remain capacity evidence, unpooled with these measurements.

Independent raw review confirms both280-entry restored trees exactly match before execution/rebuild. Both actual product samples passed: full restored-tree content, permissions/mtime/symlink/internal-hardlink oracle; source and original-main invariance; acknowledged checkpoint/history; executable outputs269→3400; all17packages Compiling on clean/edited builds and Fresh on no-op/restored builds. Both used shared compiler image `sha256:390554aa50e5f3b7ca310b888a7e2dbaa3e230efc520c3de7a9b2037cd6f7198`, Rust/Cargo1.90.0, jobs2, incremental0. Normal owned cleanup, empty mounts/containers and outer detach were verified. Product pins remain Sprig70307d3480239e96a24552d8595ec537927d9301 and LayerFS9f97a7ec95b662e9cb288704afa165feff132cfa.

**Evidence caveat:** all373collector-listed files pass byte/SHA256 verification, but only343of344sampler-listed archive files are present. The collector allowlist omitted Sprig's `000055-lifecycle.jsonl`; its hash is recorded but its bytes are unavailable. This is not complete raw-log archive acceptance. No missing file is reconstructed or substituted. Full product reports and command outputs remain available under `data/stress-20261025/cargo-4g-inc0` with explicit missing-file provenance.

One pair, seconds unless bytes:

| Boundary | Sprig writable | LayerFS |
|---|---:|---:|
| Whole sampler subprocess, launch through exit |6.291300|2.568808|
| Runtime import/setup, separate |17.783661|17.380554|
| Clean build |1.032295|0.483125|
| No-op build |0.180421|0.037977|
| Edited build |0.938201|0.384089|
| Product checkpoint plus acknowledgment/readiness |0.103903|0.101881|
| Sprig compiler quiesce plus checkpoint composite |0.425309|not matched|
| Product restore |0.021758|0.003369|
| Sprig restore to compiler-ready composite |0.175098|not matched|
| Restored build |0.185046|0.041233|
| Normal sample cleanup |0.313151|0.158008|
| Whole active filesystem Used, bytes |1,056,051,200|1,065,345,024|

These are descriptive acceptance observations, not a statistically established speedup/regression or equal-durability ranking. Sprig's generation-scoped default-root Docker CLI transport and LayerFS's persistent UID501 SDK transport differ; all costs stay charged. LayerFS uses disposable/WAL/synchronous=OFF semantics, not matched Sprig durability. Compiler runtime, target/cache, retained views, history and logs are included in whole Used; runtime bytes are not subtracted. Nested phase/composite timers are not additive. No tails or incremental1 conclusion follows from this single incremental0 pair. Fresh synthetic images were disposed only after normal cleanup and durable evidence, never pruned during accounting.

## Same-image incremental0→1: incremental1 exposes rustc SIGBUS

[Run40194938788](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40194938788), benchmark `04e969aba1b1be0d1f27b4df5451dc1f0fdfed54`, failed in7m44s. The collector fix now includes lifecycle JSONL and rejects missing/mismatched declared archives: all415collected files and382unique declared archive files are verified, with zero archive errors. This closes collection completeness for this run, **not** the missing file from the preceding pilot.

Incremental0 passed again for both products. Only then did incremental1 start, binding the same job's image `sha256:14cf1f04e43252f654d3afdb8d6112e031cd37b46b03936fca3d97e6b7c2d00d`, product pins, fixture, compiler/protocol, fresh symmetric4GiB geometry and original absolute deadline. This image is intentionally not equated with the earlier job's rebuilt image.

**Sprig incremental1 failed during the initial clean build:** rustc for `node000` and `node004` exited with signal7, **SIGBUS: access to undefined memory**; Cargo returned101. No restored/incremental1 acceptance or comparative timing can be claimed. LayerFS incremental1 was never attempted after this failure. The external common incremental1 pilot had passed, but does not establish mounted-product correctness. This is not a confirmed capacity failure and gives no justification for an8GiB retry. Exact product/root cause remains under investigation; a writable mmap/truncate issue is a hypothesis, not an established attribution.

The conservative harness classified the failed Docker exec as potentially uncertain and blocked normal cleanup rather than retrying, killing processes or forcing unmounts. Runtime/image recovery metadata and all logs were retained; sample cleanup reports `complete:false`, no cleanup attempts. No final active-space result exists for that failed sample. The ephemeral CI runner later terminates, so retaining the image during the job is not a claim that its entire filesystem was exported or remains remotely recoverable.

The independently valid incremental0 samples report whole subprocess8.594441s Sprig /3.418752s LayerFS and whole active Used1,055,641,600 /1,065,095,168bytes. These are separate single-pair observations with the same transport/durability caveats, not pooled with the earlier image/run. Complete raw failure and provenance: `data/stress-20261025/cargo-4g-inc1-sigbus`.
