> Timing scope: import + fork + verified read is a sum of defined phases, not complete startup wall time. Sprig store initialization, software installation/build, and runtime setup are excluded; LayerFS project initialization includes its store initialization. CLI versus SDK and durability differences remain.

# Metadata optimization: 22 October 2026

> **Storage correction (22 October 2026):** the LayerFS figures below count only the store volume plus SDK home. They omit active workspace overlay databases and other writable-container state. They are **not complete active footprint** and must not support whole-product storage ratios or a storage winner. Raw measurements are preserved unchanged. See [scope correction and source evidence](STORAGE-CORRECTION.md). Timing and byte/history checks are separate measurements; this omission does not by itself invalidate them.

**Result:** Sprig is faster in this run's complete `unique` and `mixed` tasks, but still loses the identical-content, small-insertion and deep-history comparisons. Metadata compression greatly reduces retained-history footprint; it is not an overall win against LayerFS.

- [Successful optimized run and raw artifact](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39756383155).
- Sprig: `aab4985b03e245dabca21fc9eb8769f66896edd0`; LayerFS v1.0.0 remains `2aaf2552ce21154928b9f9c83582e41a637f5910`.
- Benchmark commit: `f0ec13bf9bc04d4939dd59b7aee84306c24c15a8`. All fixture, operation, oracle and summary scripts are byte-identical to baseline harness `e3cd5a68c52fa12b8b078f079352ff83678faf0f`; only the product pin/cache key and README pin changed. [Frozen-script hashes](measurements/2026-10-22-aab4985/frozen-harness-sha256.txt).
- All 42 expected records passed, with three fresh-store repetitions per product/case. All 1,800 acknowledged checkpoint IDs were distinct within their histories and present in final history. Both products again passed the same-file merge/conflict smoke.
- This run: Ubuntu 24.04 / ext4, 4 logical CPUs, AMD EPYC 7763, 15 GiB reported RAM, Docker 29.8.2 + FUSE. The earlier runner used AMD EPYC **9V74**, not 7763. **Old-to-new timing differences are not a same-machine causal speedup measurement.** All Sprig-versus-LayerFS comparisons below are paired on the new runner.
- Sprig default synchronization remains enabled. LayerFS uses Disposable WAL / synchronous=OFF. These are **not equal-durability configurations**.

## Complete tasks

Milliseconds, median of three. Cold task = import + usable fork + full SHA-256 read; first mount includes sandbox startup. Warm task = another usable fork + full read on the already-running sandbox. Inputs are setup-warm, not cold-cache. Metadata-only branching is separate and is not substituted for a materialized/readable workspace.

| Frozen recipe | Sprig cold task | LayerFS cold task | Sprig warm task | LayerFS warm task |
|---|---:|---:|---:|---:|
| identical | 569.6 | 418.5 | 329.6 | 179.9 |
| unique | 1,094.5 | 1,655.9 | 336.0 | 667.1 |
| mixed | 927.2 | 1,281.4 | 327.2 | 556.5 |
| insert | 634.1 | 467.2 | 340.9 | 183.6 |
| history-distributed | 327.2 | 301.7 | 140.6 | 74.4 |
| history-hotset | 330.0 | 306.7 | 137.8 | 76.2 |
| history-recurring | 331.0 | 295.5 | 141.4 | 73.8 |

`unique` and `mixed` are genuine complete-task observations, not a claim that Sprig won the strongest deduplication cases. All seven cases are reported, including losses. Import outputs differ: Sprig immediately materializes its native main tree; LayerFS imports stored history before mounting a workspace.

## Measured storage components (not whole-product matched footprint)

Allocated MiB, median of three, with both measured workspaces still usable. Sprig additionally retains its natively materialized main workspace. All measured Sprig native trees, objects, manifests and retained recovery generations count; the LayerFS column counts only its volume plus SDK home, omitting container workspace overlays. Immutable software/runtime images are excluded for both.

| Recipe | Sprig active MiB | LayerFS store + home subset MiB |
|---|---:|---:|
| identical | 301.160 | 2.551 |
| unique | 402.867 | 202.840 |
| mixed | 377.195 | 152.285 |
| insert | 313.984 | 9.621 |
| history-distributed | 12.289 | 6.676 |
| history-hotset | 15.781 | 6.656 |
| history-recurring | 11.805 | 6.262 |

Footprints are allocated filesystem blocks, not exclusive physical extents. Native clone fell back to copy on this ext4 runner. Post-close diagnostic footprints are not used as matched active-workspace measurements.

### Observed history-footprint reduction

The earlier uncompressed Sprig baseline is preserved separately. These are allocated-footprint observations across the two recorded runs; the different runner CPUs preclude treating timing changes as isolated optimization effects.

| Recipe | Earlier Sprig MiB | Optimized Sprig MiB | Observed reduction |
|---|---:|---:|---:|
| history-distributed | 43.121 | 12.289 | 71.5% |
| history-hotset | 46.613 | 15.781 | 66.1% |
| history-recurring | 42.633 | 11.805 | 72.3% |

For distributed repetition 0, state backups now allocate 2,105,344 bytes and revisions 2,506,752 bytes, compared with 25,333,760 and 11,599,872 bytes in baseline repetition 0. Native trees and content objects still allocate 5,988,352 + 2,035,712 bytes. That subtotal exceeds the measured LayerFS store + home subset, but the omitted writable-container data prevents drawing a whole-product storage lower-bound or winner from this comparison.

The implementation compresses immutable revision records and state backups and batches redundant content-directory synchronization. It retains file fsync, original revision-hash validation, every recovery generation/root, and full content capture even when size and mtime are unchanged. Fresh stores are used; old-store migration is not benchmarked.

## One hundred edits and checkpoints

Seconds, median of three. Edit + checkpoint is computed per repetition before taking the median; it excludes independent byte/history assertions. Every iteration overwrites the same bytes/offset prescribed by the frozen recipe, preserves the inode, fsyncs file data, and restores the fixed mtime. This fsync precedes mtime restoration and does not promise final-mtime durability.

| Recipe | Sprig edit + checkpoint | LayerFS edit + checkpoint | Sprig checkpoint only | LayerFS checkpoint only |
|---|---:|---:|---:|---:|
| history-distributed | 4.329 | 2.268 | 3.164 | 0.440 |
| history-hotset | 4.219 | 2.318 | 3.118 | 0.504 |
| history-recurring | 4.476 | 2.638 | 3.098 | 0.282 |

Checkpoint-only measures the practical APIs: a complete Sprig CLI invocation (startup, state loading, capture, persistence, output and process exit) versus an in-process LayerFS SDK call to its running service. It is not an isolated algorithm timing, and the different durability contracts also remain. No claim of a theoretical checkpoint lower bound or equal-durability comparison is made.

## Correctness and limits

All listed-file SHA-256 reads, per-edit changed-file readback, strict baseline-plus-100 history counts, and all returned checkpoint-ID membership checks passed. Extra-path, full directory/mode/mtime fidelity, historical snapshot remount, complete upstream internal-object and crash-recovery oracles are not claimed. Merge runs once per product as a correctness smoke, not a repeated merge-speed benchmark.

The exact upstream frozen seed-1 recipe is a port, not the entire official harness. The separate DSH real-history corpus is unavailable from a verified public source and is not claimed. [Baseline methodology and preserved results](RESULTS.md) remain available. No fixture, operation, durability setting, scale or pass criterion was weakened for this optimization.

## Complete raw data

- [42 raw records](measurements/2026-10-22-aab4985/comparison.json), [1,800 per-step samples](measurements/2026-10-22-aab4985/history-samples.jsonl).
- [Every sample, median, minimum and maximum](measurements/2026-10-22-aab4985/summary.json), [median CSV](measurements/2026-10-22-aab4985/summary.csv).
- [Environment](measurements/2026-10-22-aab4985/environment.txt), [fixture hashes](measurements/2026-10-22-aab4985/fixture-generation.txt), [runtime-image digest](measurements/2026-10-22-aab4985/runtime-image.json), [SHA-256 manifest](measurements/2026-10-22-aab4985/sha256.json).
