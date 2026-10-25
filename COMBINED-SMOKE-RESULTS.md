# Combined candidate: three-backend smoke (not full results)

Sprig `2a01fe445b8057ca49b4e8284fdd5583bbb4185c` versus LayerFS v1.1.0 `9f97a7ec95b662e9cb288704afa165feff132cfa`; harness `4383a456cd8f26dbbfe4047be4a40d669f1adb9d`. These use production interfaces: Sprig CLI and LayerFS SDK, not the earlier prototype. Three independent backend runners, one sample per product/case: do not infer a repeatable speedup or cross-run causal optimization.

All 12 records and 600 full historical readbacks passed. Each run also passed real projection and owned-kernel lifecycle gates. Full seven-case repetitions and corrected Cargo are separate pending deliverables.

## Exact measured values

Preparation includes product init/import/fork/full SHA read. Warm includes fork/full read. Restore total is the sum of restore/read/normal cleanup timers. Footprints are whole-FS Used minus fresh empty FS, including software/runtime where deployed, not exact application-only storage. MiB = 1,048,576 bytes.

| Backend / case | Product | Preparation ms | Warm ms | Write + 100 commits s | 100 restores/read/cleanup s | Primary MiB | Post-history MiB |
|---|---|---:|---:|---:|---:|---:|---:|
| native / identical | sprig-native | 802.08 | 235.58 | — | — | 101.586 | 101.590 |
| native / identical | layerfs | 619.94 | 187.79 | — | — | 94.922 | 94.922 |
| native / history-distributed | sprig-native | 831.99 | 387.02 | 4.739 | 29.187 | 6.242 | 153.406 |
| native / history-distributed | layerfs | 452.66 | 80.45 | 2.394 | 8.021 | 99.148 | 101.109 |
| projection / identical | sprig-projection | 426.61 | 161.53 | — | — | 1.094 | 1.105 |
| projection / identical | layerfs | 862.41 | 185.44 | — | — | 94.922 | 94.922 |
| projection / history-distributed | sprig-projection | 249.29 | 106.55 | 4.747 | 10.455 | 4.109 | 5.906 |
| projection / history-distributed | layerfs | 451.04 | 82.13 | 2.282 | 8.081 | 99.207 | 101.152 |
| writable / identical | sprig-writable | 494.59 | 280.50 | — | — | 1.082 | 1.094 |
| writable / identical | layerfs | 582.93 | 188.73 | — | — | 95.012 | 95.012 |
| writable / history-distributed | sprig-writable | 265.68 | 158.93 | 7.491 | 17.157 | 5.027 | 6.961 |
| writable / history-distributed | layerfs | 455.68 | 80.16 | 2.196 | 7.764 | 99.156 | 101.172 |

Runs and complete original artifacts:
- [Run 40164437134](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40164437134); [original artifact](data/combined-20261025/native-smoke/).
- [Run 40164922024](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40164922024); [original artifact](data/combined-20261025/projection-smoke/).
- [Run 40165326886](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40165326886); [original artifact](data/combined-20261025/writable-smoke/).
## Findings and limits

- No overall victory: all three history smoke write/commit and complete restore paths remain slower than the comparator. Single-sample preparation and warm results are mixed.
- Native post-history physical usage rises substantially because the normal restore API retains materialized generations. This is an explicit later lifecycle boundary, not a replacement for primary usage and not a garbage-collection test. The two projected modes retain far less physical data at that boundary.
- Three original workspaces remain live at both space points. After history the sampler validates 103 native/projection or 203 owned generations. Comparator normal history/branch retention remains unchanged.
- The comparator includes its runtime image. Reported lower filesystem usage must not be described as the same percentage of application data or deployment savings with a common toolchain. Cargo will report its separate common-toolchain boundary.
- Sprig fsync durability remains enabled. Comparator Disposable uses global SQLite WAL/OFF and workspace MEMORY/OFF/EXCLUSIVE. No equal crash-durability claim or cold-cache claim. CLI versus persistent SDK execution overhead remains part of the practical interface comparison.
- All original raw artifacts are copied unchanged, including failure/cleanup fields and independent JSONL records. No existing report or data is overwritten.

See [complete protocol boundaries](feasibility/COMBINED-MEASUREMENT-SCOPE.md).
