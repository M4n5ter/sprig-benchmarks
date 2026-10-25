# Cargo DAG16 v2 acceptance — incomplete first pilot

[Run40188875391](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40188875391), benchmark `d0095a97b40d805abc486d2fea1c74493751504a`, production `70307d3480239e96a24552d8595ec537927d9301`, failed in6m52s. This is **not a passing Cargo comparison and supplies no product performance ratio**.

The source builds/tests, real projection/writable gates, shared pinned1.90.0 compiler image preparation, branching17-package fixture and external capacity pilot steps completed. During the first Sprig sample's runtime setup, `docker load` of the compiler archive failed before the product sampler launched. The inherited runtime helper did not print the captured subprocess output, so the underlying cause is unknown; ENOSPC is only a hypothesis, not a finding. No capacity limit or correctness gate is relaxed.

Artifact upload then failed with EACCES traversing the root-owned capacity-pilot directory. GitHub's artifact API confirms zero artifacts. Only full CI logs, failed-step logs and artifact API response could be recovered; these are preserved in `data/stress-20261025/cargo-first-pilot-failed` with hashes/provenance. Missing raw measurements cannot be reconstructed or reported as acceptance. Recovery work must preserve failed-command diagnostics and copy only evidence into runner-readable artifact staging without altering retained product/runtime state.

The v2 branching graph, matched compiler `--jobs 2`,17-package Fresh/Compiling expectations,269→3400 executable outputs, exact full-tree metadata/content oracle, shared absolute job budget,2GiB image and fail-closed uncertain cleanup remain required for the next attempt. Old correctedCargo v1 acceptance is not relabeled as DAG16 v2 acceptance.

## Evidence-enabled retry: runtime import ENOSPC confirmed

[Run40190944293](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40190944293), benchmark `2643eb5492d8fcd4b444d987fef991f89ff41287`, failed in6m35s before any product sampler. The only changes preserved the failed Docker subprocess output and made allowlisted copied evidence readable by artifact upload; image construction,2GiB bound, product pins and acceptance protocol were unchanged. The collector/upload succeeded, and all25collected files were independently verified by bytes/SHA256.

Docker reports `no space left on device` while writing the Rust `libcore` rlib during image import. Read-only diagnostics immediately after the failed Docker command report2,146,435,072bytes allocated out of2,147,483,648, with only1MiB unallocated; filesystem Used342,478,848bytes (df348,246,016) and apparent free1,575,038,976bytes are **post-failure** observations. They do not establish the transient import peak or explain all reservation/chunk behavior. No unsupported exact peak attribution is made.

The immutable image reports1,005,165,334bytes; saved archive logical size1,013,662,208bytes. Rust1.90.0 toolchain allocation593,596,416bytes, including12,972,032bytes under share/doc; installed components are only cargo, rust-std and rustc. This does not support the speculative stale-documentation explanation. External pilot target allocation is9,134,080bytes for incremental0; that pilot did not cover the Docker import transient footprint.

Setup rollback and outer normal unmount/loop detach completed. There are still **zero product measurements and no Cargo performance comparison**. A failed runtime-load capacity constraint cannot be relabeled as a Sprig or LayerFS correctness failure. No filesystem enlargement, selective runtime deletion, oracle relaxation or further speculative retry is implied. Complete diagnostic artifact and provenance: `data/stress-20261025/cargo-evidence-retry-failed`.
