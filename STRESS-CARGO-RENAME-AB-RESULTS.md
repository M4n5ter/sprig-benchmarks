# Ordinary Cargo own-version A/B: bounded rename traversal

[Run40238545179](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40238545179), benchmark `6ad8cc1c9d17f32dae8592f3e4f8c49080437921`, passed in6m48s. Same runner, immutable baseline `4ef4a90d7ccf5f305416c5374bfc81038f5ca46e` versus rename candidate `b300693e01c652c1a9631c61b7a439892d8f75cd`, separately built once with distinct target directories/binary hashes. This is within-Sprig with matched sampler/transport/durability, not a new LayerFS comparison.

## Result and limits

Whole sampler wall is8.959893→8.502238s for incremental0 (−5.11%) and10.359983→10.059708s for incremental1 (−2.90%). These are **one pair per mode**, not established statistical gains. Order was baseline→candidate in inc0, candidate→baseline in inc1; changing modes does not supply same-mode reverse-order replication. No latency-tail inference follows. The earlier local rename samples are separate evidence, not pooled with these Cargo samples.

Negatives remain: inc0 normal cleanup0.407664→0.416655s (+2.21%) and whole Used+229,376bytes. Inc1 Used differs by only−16,384bytes, not a general storage win. Runtime setup inc0 varies16.826999→14.291000s before product measurement; do not attribute that difference to rename or fold it selectively into a speedup. Full measured wall includes evidence/oracles and normal cleanup; phase/composite timers overlap and must not be summed.

| Boundary / 边界 (seconds / 秒) | Baseline inc0 | Candidate inc0 | Baseline inc1 | Candidate inc1 |
|---|---:|---:|---:|---:|
| Whole sampler / 完整采样进程 | 8.959893 | 8.502238 | 10.359983 | 10.059708 |
| Runtime setup (separate) / 运行时导入（单列） | 16.826999 | 14.291000 | 14.582164 | 14.509828 |
| init | 0.014666 | 0.011918 | 0.014624 | 0.013388 |
| import | 0.049702 | 0.046175 | 0.050361 | 0.045538 |
| fork | 0.044386 | 0.039766 | 0.043923 | 0.038502 |
| clean_build | 1.373800 | 1.343012 | 1.924543 | 1.796570 |
| noop_build | 0.302214 | 0.253874 | 0.292213 | 0.260588 |
| edit_build | 1.388231 | 1.237248 | 1.674018 | 1.615979 |
| checkpoint | 0.160582 | 0.140554 | 0.201403 | 0.198631 |
| restore | 0.029246 | 0.026674 | 0.036585 | 0.032145 |
| restore_verify | 0.719689 | 0.687297 | 1.014951 | 1.006212 |
| restored_rebuild | 0.297197 | 0.286145 | 0.290321 | 0.285795 |
| retained_input_verify | 1.297898 | 1.208786 | 1.250675 | 1.249219 |
| cleanup | 0.407664 | 0.416655 | 0.438106 | 0.406059 |
| checkpointCompilerQuiescePlusProduct | 0.574481 | 0.516834 | 0.584992 | 0.563216 |
| restoreToCompilerReady | 0.240025 | 0.228579 | 0.249332 | 0.245288 |
| Whole active Used / 全盘Used (bytes / 字节) | 1,055,498,240 | 1,055,727,616 | 1,065,988,096 | 1,065,971,712 |

## Correctness, identity and resource boundary

All four ordinary samples pass: clean/edit builds compile all17packages; no-op/restored builds report all17Fresh and zero compilation; executable269→3400 and build-script values1→2; exact280-entry inc0 and474-entry inc1 restore trees before execution/rebuild; content,0777permissions, exactmtime, symlinks and internal hardlink groups; original source/main and acknowledged history preservation. All four compiler sessions per sample end naturally with verified PID disappearance, normal owned cleanup leaves zero mounts/containers. Four retained generations and all runtime/compiler/target/cache/history/logs remain charged at space accounting. No selective cleanup or hidden baseline subtraction.

Independent review matches all40archived source/test hashes per variant against exact git objects and cross-checks binary hash records against the manifest and all raw samples; verbose logs show actual builds from separate source paths. Executables themselves are not archived, so this is recorded binary provenance verification, not an offline rehash of executable bytes. Host build compiler is1.99.1; shared workload compiler is Rust/Cargo1.90.0. All1,101collector files and1,060unique declared raw archives pass size/SHA256 verification. Raw originals and provenance are in `data/stress-20261025/cargo-rename-own-ab`. The same immutable compiler image `sha256:8fe1ae418eaa561337241498ea21a276cd7e8cd80ceff4611f4f8c7207fbbf4c`, protocol, fixture and fresh symmetric4GiB images are used throughout. Both inc0 samples pass the full prerequisite before inc1; the prerequisite hash binds both binary/source identities and the original absolute deadline1792965932→1792968332. The45-minute job, jobs2 and180s work+300s cleanup admission reserves are unchanged. No8GiB fallback.

Executed here: offline harness/unit tests, serial source builds, the reviewed ordinary held-FD/hardlink positive preflight for both repaired pins, and four normal Cargo samples. Existing exact-pin product CI supplies separate projection/full product-contract coverage; those complete suites were **not rerun here**. No withheld expected-failure route or deliberate mapped-fault workload was activated. Prior Cargo SIGBUS, partial archive, capacity failures and cache negatives remain unchanged. This single run does not authorize main promotion or an automatic repeat.

### All slower phase observations / 全部更慢阶段观察

These are overlapping descriptive timers, not additive costs or isolated rename attribution. / 这些是重叠的描述性计时，不能相加或独立归因rename。

| Mode / 模式 | Phase / 阶段 | Baseline seconds | Candidate seconds | Change / 变化 |
|---|---|---:|---:|---:|
| 0 | clean_execute | 0.072094 | 0.073307 | +1.68% |
| 0 | cleanup | 0.407664 | 0.416655 | +2.21% |
| 0 | edit_artifacts | 0.106775 | 0.126124 | +18.12% |
| 0 | fixture_verify | 0.348827 | 0.349382 | +0.16% |
| 0 | noop_execute | 0.072024 | 0.073063 | +1.44% |
| 0 | preflight | 0.086466 | 0.087423 | +1.11% |
| 0 | restored_rebuild_execute | 0.071478 | 0.071526 | +0.07% |
| 0 | space | 0.105762 | 0.106856 | +1.03% |
| 0 | toolchain_verify | 0.085176 | 0.087088 | +2.25% |
| 0 | transport_stop_final_cleanup | 0.300296 | 0.303615 | +1.11% |
| 1 | cargo_setup | 0.070936 | 0.071747 | +1.14% |
| 1 | checkpoint_readiness | 0.003421 | 0.003759 | +9.86% |
| 1 | clean_execute | 0.071341 | 0.074451 | +4.36% |
| 1 | edit | 0.097972 | 0.100029 | +2.10% |
| 1 | fixture_verify | 0.350300 | 0.353883 | +1.02% |
| 1 | noop_execute | 0.073187 | 0.073367 | +0.25% |
| 1 | pre_checkpoint_oracle | 0.727817 | 0.740872 | +1.79% |
| 1 | restored_execute | 0.070156 | 0.072508 | +3.35% |
| 1 | toolchain_verify | 0.084576 | 0.088322 | +4.43% |

Precision note: the embedded comparison JSON passes through JavaScript Number serialization, so nanosecond integers in its checkpointTreeOracle may be rounded. Exact metadata evidence is the standalone sampler JSON plus archived raw snapshots, which retain integer nanoseconds and match. No claim of byte/exact-integer equivalence for every embedded comparison field is made.
