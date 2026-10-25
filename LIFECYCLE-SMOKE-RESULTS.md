# Lifecycle optimization: preliminary same-runner smoke

25 October 2026. Baseline `bc4165f5f55ceac63e18716ac96b19d9e4675afd` versus candidate `a2b76e4c3ecdccdeeca24a669df4a82d1a4792f3`, default auto compression. Candidate is a topic revision, not a claim about a merged release. Benchmark `f0dcedfde47f301dc138c20e855a2e790489d748`.

**All 12 records and 600 complete historical readbacks passed. These are only one adjacent pair per case/backend, not five-pair results and not a new LayerFS comparison.** Native and projection full series are deferred pending further diagnosis; owned full results, if completed, will be separately reported.

The visible direction is mixed: owned distributed-history checkpoints improve in the single pair, but warm forks/restores do not consistently improve, and fresh-store physical space can differ substantially. No universal optimization success or causal storage regression is established.

## Interpretation

- Each baseline/candidate pair shares one runner and fixed compiler/profile; source and binary hashes are recorded, and the two revisions use separate target directories. Different backend runs use separate runners.
- Original fixtures, complete initialization/fork/read/checkpoint/restore tasks, durability barriers, three live workspaces and all generations are retained. There is no GC, pruning, dropped cache state or cold-cache claim.
- Primary physical space is whole Btrfs Used minus empty-FS baseline before historical restoration. A second separately labeled sample follows all restored-readback/normal-unmount tasks, before final cleanup. Native restored trees remain retained.
- Component diagnostics occur only after every timed operation and the second space sample. Their logical/st_blocks counts are not additive unique physical extent accounting. Mounted views are never traversed.
- Each fresh import creates independent entry identities. Metadata CDC/page-sharing boundaries depend on encoded identities, so otherwise equal logical content may produce unequal metadata-object bytes. These runs do not control initial identity seeds and do not prove the cause of a particular storage difference. Original raw values are preserved.
- 207 physical object files, when observed, does not mean 207 logical content chunks or metadata pages.

[Protocol](feasibility/LIFECYCLE-AB-CONTRACT.md). All timing values below are actual single samples, baseline / candidate.

## native

[Run 40157066125](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40157066125) · [Complete original artifact](data/lifecycle-20261025/smoke/native-40157066125-full-artifact.tar.gz) · [Paired summary](data/lifecycle-20261025/smoke/native-summary.json)

| Case | Preparation ms | Warm fork/read ms | Active physical delta MiB | Post-history physical delta MiB |
|---|---:|---:|---:|---:|
| identical | 878.672 / 899.995 | 384.441 / 407.187 | 101.637 / 101.637 | 101.641 / 101.641 |
| history-distributed | 801.711 / 791.193 | 312.107 / 376.761 | 8.445 / 9.586 | 171.031 / 171.953 |

| 100-operation history task | Baseline / candidate seconds |
|---|---:|
| Writes plus checkpoint | 4.672 / 4.831 |
| Checkpoint only | 4.226 / 4.365 |
| Restore to usable workspace | 36.215 / 35.330 |
| Restore plus full read and normal cleanup | 36.926 / 36.035 |

## writable

[Run 40157514250](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40157514250) · [Complete original artifact](data/lifecycle-20261025/smoke/writable-40157514250-full-artifact.tar.gz) · [Paired summary](data/lifecycle-20261025/smoke/writable-summary.json)

| Case | Preparation ms | Warm fork/read ms | Active physical delta MiB | Post-history physical delta MiB |
|---|---:|---:|---:|---:|
| identical | 483.728 / 494.197 | 280.921 / 280.138 | 1.082 / 1.082 | 1.094 / 1.094 |
| history-distributed | 301.136 / 269.349 | 179.570 / 154.255 | 5.066 / 6.078 | 6.977 / 7.992 |

| 100-operation history task | Baseline / candidate seconds |
|---|---:|
| Writes plus checkpoint | 8.468 / 7.789 |
| Checkpoint only | 7.789 / 7.135 |
| Restore to usable workspace | 3.027 / 2.914 |
| Restore plus full read and normal cleanup | 17.485 / 17.497 |

## projection

[Run 40157941109](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40157941109) · [Complete original artifact](data/lifecycle-20261025/smoke/projection-40157941109-full-artifact.tar.gz) · [Paired summary](data/lifecycle-20261025/smoke/projection-summary.json)

| Case | Preparation ms | Warm fork/read ms | Active physical delta MiB | Post-history physical delta MiB |
|---|---:|---:|---:|---:|
| identical | 379.940 / 357.521 | 155.822 / 155.904 | 1.145 / 1.145 | 1.156 / 1.156 |
| history-distributed | 222.985 / 216.785 | 97.993 / 105.001 | 7.324 / 7.324 | 19.508 / 19.965 |

| 100-operation history task | Baseline / candidate seconds |
|---|---:|
| Writes plus checkpoint | 4.717 / 4.579 |
| Checkpoint only | 4.149 / 4.029 |
| Restore to usable workspace | 14.033 / 14.217 |
| Restore plus full read and normal cleanup | 21.860 / 22.098 |

[Archive checksums and provenance](data/lifecycle-20261025/smoke/manifest.json). Original downloaded artifacts are unchanged; all slower samples and larger storage observations remain included.
