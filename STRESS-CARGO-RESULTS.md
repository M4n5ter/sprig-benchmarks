# Cargo DAG16 v2 acceptance — incomplete first pilot

[Run40188875391](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40188875391), benchmark `d0095a97b40d805abc486d2fea1c74493751504a`, production `70307d3480239e96a24552d8595ec537927d9301`, failed in6m52s. This is **not a passing Cargo comparison and supplies no product performance ratio**.

The source builds/tests, real projection/writable gates, shared pinned1.90.0 compiler image preparation, branching17-package fixture and external capacity pilot steps completed. During the first Sprig sample's runtime setup, `docker load` of the compiler archive failed before the product sampler launched. The inherited runtime helper did not print the captured subprocess output, so the underlying cause is unknown; ENOSPC is only a hypothesis, not a finding. No capacity limit or correctness gate is relaxed.

Artifact upload then failed with EACCES traversing the root-owned capacity-pilot directory. GitHub's artifact API confirms zero artifacts. Only full CI logs, failed-step logs and artifact API response could be recovered; these are preserved in `data/stress-20261025/cargo-first-pilot-failed` with hashes/provenance. Missing raw measurements cannot be reconstructed or reported as acceptance. Recovery work must preserve failed-command diagnostics and copy only evidence into runner-readable artifact staging without altering retained product/runtime state.

The v2 branching graph, matched compiler `--jobs 2`,17-package Fresh/Compiling expectations,269→3400 executable outputs, exact full-tree metadata/content oracle, shared absolute job budget,2GiB image and fail-closed uncertain cleanup remain required for the next attempt. Old correctedCargo v1 acceptance is not relabeled as DAG16 v2 acceptance.
