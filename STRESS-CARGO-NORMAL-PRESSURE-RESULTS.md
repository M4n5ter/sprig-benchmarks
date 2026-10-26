# Normal concurrency pressure: faster rename median, worse tail observations

[Run 40289142188](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40289142188) passed in 12m14s at benchmark `12a243730f5db7b47dae5002bf0bc5b80a2a0b61`. Fixed baseline `4ef4a90d7ccf5f305416c5374bfc81038f5ca46e` versus rename candidate/current main `b300693e01c652c1a9631c61b7a439892d8f75cd`. This is the separately predeclared `normal-rename2-v1` profile, not the ordinary Cargo series.

**The pressure exposed a real measurement trade-off, not a broad latency win:** per-sample rename medians improve by a paired geometric mean **53.97% (inc0) / 50.74% (inc1)**, while per-sample rename p99 observations worsen **8.84% / 22.87%**. Incremental1 write p99 is **74.22%** higher, metadata p99 **55.88%** higher and read p99 **26.76%** higher. These percentages are geometric means of four paired **per-sample dependent-operation quantile ratios**. They are not end-to-end p99, pooled independent trials, or statistical significance.

Whole sampler wall changes −2.31% / −1.15%; the separate pressure phase changes +0.46% / −3.84%. Checkpoint phase changes −32.34% / −30.29%. Those modest whole-task/phase observations do not erase the tail negatives. The [ordinary repeated experiment](STRESS-CARGO-BALANCED-AB-RESULTS.md) is separately preserved (+0.29% / +2.00% whole wall); stressed whole wall is not directly comparable to that unstressed workload. No causal attribution to scheduler, lock, FUSE or filesystem behavior follows from these wall timings alone.

## Every whole-sampler pair

| Mode | Round | Actual order | Baseline seconds | Candidate seconds | Candidate change |
| --- | --- | --- | ---: | ---: | ---: |
| inc0 | 0 | baseline → candidate | 12.938392 | 12.251987 | -5.31% |
| inc0 | 1 | candidate → baseline | 12.940104 | 12.752309 | -1.45% |
| inc0 | 2 | baseline → candidate | 13.261981 | 12.612999 | -4.89% |
| inc0 | 3 | candidate → baseline | 13.315719 | 13.663089 | +2.61% |
| inc1 | 0 | candidate → baseline | 14.189941 | 14.305460 | +0.81% |
| inc1 | 1 | baseline → candidate | 13.789479 | 13.838257 | +0.35% |
| inc1 | 2 | candidate → baseline | 14.288389 | 13.489989 | -5.59% |
| inc1 | 3 | baseline → candidate | 13.916093 | 13.911889 | -0.03% |

Four planned rounds per mode, two pairs per order within each mode, 16 complete samples. Every pair and all slower phases remain in the raw summary. N=4 does not support a whole-task p95/p99 or significance claim.

## All per-sample operation statistics

Each bracket lists rounds0–3 in milliseconds. Each value is computed within its own sample from all 512 rename or 256 write/read/metadata observations. The four values are NOT pooled before taking a percentile. Worker operations are concurrent and dependent. Nearest-rank p95/p99 are descriptive tail observations; no independent-operation significance claim is made.

| Mode | Operation statistic | Baseline milliseconds, rounds0–3 | Candidate milliseconds, rounds0–3 | Geometric paired change |
| --- | --- | --- | --- | ---: |
| inc0 | rename median | [0.7022, 0.7195, 0.7520, 0.7469] | [0.3196, 0.3426, 0.3473, 0.3352] | -53.97% |
| inc0 | rename p95 | [0.7430, 1.3495, 0.8215, 1.3761] | [0.3859, 1.1634, 1.0003, 1.2438] | -16.21% |
| inc0 | rename p99 | [0.7735, 1.4779, 0.9048, 1.5319] | [1.0749, 1.2961, 1.1499, 1.3878] | +8.84% |
| inc0 | rename maximum | [0.9999, 1.9556, 1.1862, 1.5599] | [1.1395, 1.7618, 1.2328, 1.5283] | +1.12% |
| inc0 | write median | [1.3349, 1.3886, 1.3618, 1.4344] | [1.1607, 1.4076, 1.1884, 1.4793] | -5.63% |
| inc0 | write p95 | [2.0440, 2.0765, 2.1211, 2.2112] | [1.9397, 2.3095, 2.0195, 2.3856] | +2.04% |
| inc0 | write p99 | [2.2790, 2.3041, 5.4348, 2.2924] | [2.0158, 2.4945, 2.1289, 2.4968] | -20.05% |
| inc0 | write maximum | [14.5950, 2.3249, 6.7083, 2.3772] | [2.1144, 3.9749, 3.0730, 3.0185] | -38.39% |
| inc0 | read median | [0.3273, 0.3524, 0.3468, 0.3539] | [0.3327, 0.8583, 0.3473, 0.3730] | +27.15% |
| inc0 | read p95 | [1.1642, 1.4512, 1.2100, 1.5246] | [1.1435, 1.3376, 1.1807, 1.3761] | -5.50% |
| inc0 | read p99 | [1.2147, 1.7421, 1.3688, 1.6187] | [1.2133, 1.4133, 1.3104, 1.4038] | -9.44% |
| inc0 | read maximum | [1.2906, 2.0095, 2.9503, 1.8020] | [1.2455, 3.1146, 2.2569, 1.7305] | +2.39% |
| inc0 | metadata median | [0.5266, 0.5642, 0.5623, 0.5722] | [0.5163, 0.5681, 0.5573, 0.5836] | -0.05% |
| inc0 | metadata p95 | [0.5567, 1.3906, 0.6058, 1.4809] | [1.2052, 1.5196, 1.2999, 1.5653] | +52.20% |
| inc0 | metadata p99 | [0.5703, 1.6799, 0.7809, 1.7118] | [1.2656, 1.7269, 1.3816, 1.6637] | +40.73% |
| inc0 | metadata maximum | [0.5864, 1.7544, 1.1471, 1.8286] | [1.3247, 1.8672, 1.4002, 1.6862] | +28.26% |
| inc1 | rename median | [0.7434, 0.6921, 0.7078, 0.6986] | [0.3520, 0.3541, 0.3521, 0.3413] | -50.74% |
| inc1 | rename p95 | [0.8143, 0.7790, 1.3639, 0.8669] | [0.9429, 1.2246, 0.9487, 1.1918] | +14.86% |
| inc1 | rename p99 | [1.3477, 0.8120, 1.4925, 1.1683] | [1.0196, 1.3326, 2.2885, 1.3985] | +22.87% |
| inc1 | rename maximum | [1.4618, 1.2698, 5.1933, 1.2122] | [1.8319, 1.4613, 4.5057, 1.6776] | +14.71% |
| inc1 | write median | [1.3468, 1.3588, 1.5564, 1.1719] | [1.0206, 1.2794, 0.9962, 1.3241] | -15.24% |
| inc1 | write p95 | [2.0176, 2.0313, 2.3645, 1.5902] | [2.0376, 2.1977, 2.8947, 2.3833] | +18.99% |
| inc1 | write p99 | [2.1610, 2.1442, 2.9582, 1.6731] | [3.9099, 3.6325, 5.9147, 2.5149] | +74.22% |
| inc1 | write maximum | [2.3791, 2.2575, 6.1957, 1.6971] | [14.5457, 4.4103, 11.6471, 2.6097] | +142.41% |
| inc1 | read median | [0.3335, 0.3251, 0.3447, 0.3205] | [0.3899, 0.3661, 0.3561, 0.3380] | +9.44% |
| inc1 | read p95 | [1.3038, 1.1891, 1.4573, 1.1092] | [1.0483, 1.2929, 1.1892, 1.3517] | -3.44% |
| inc1 | read p99 | [1.3792, 1.2402, 1.5838, 1.3017] | [1.3854, 1.3699, 3.3339, 1.4388] | +26.76% |
| inc1 | read maximum | [1.6569, 1.2676, 2.1538, 1.3160] | [1.6427, 2.7391, 8.4035, 1.5276] | +76.49% |
| inc1 | metadata median | [0.5473, 0.5033, 0.5234, 0.5406] | [0.6218, 0.5908, 0.5672, 0.5606] | +10.64% |
| inc1 | metadata p95 | [1.2632, 0.5694, 1.4074, 1.0558] | [1.2212, 1.5416, 2.0226, 1.5365] | +52.96% |
| inc1 | metadata p99 | [1.5697, 0.6022, 2.3581, 1.1427] | [1.4011, 1.6867, 3.6736, 1.7326] | +55.88% |
| inc1 | metadata maximum | [1.6884, 0.6297, 7.1027, 1.1508] | [1.5505, 1.7359, 4.7217, 1.7824] | +27.06% |

Absolute scale matters: incremental1 rename p99 spans 0.812–1.492ms baseline versus 1.020–2.289ms candidate. Write p99 spans 1.673–2.958ms versus 2.515–5.915ms. The observation is still a tail regression in this matrix; percentages alone should not imply seconds-scale stalls or a proven cause.

## Matched whole/phase observations

Percentages are geometric means of paired ratios. Medians are descriptive variant medians. Cargo build phases exclude the separate pressure stage. Nested/composite timers overlap; never add or subtract them to manufacture an explanation.

| Metric | inc0 baseline median | inc0 candidate median | inc0 paired change | inc1 baseline median | inc1 candidate median | inc1 paired change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| wholeSamplerSeconds | 13.101043 | 12.682654 | -2.31% | 14.053017 | 13.875073 | -1.15% |
| runtimeSetupSeconds | 15.054763 | 17.213242 | +7.02% | 14.634000 | 15.023020 | +2.61% |
| phase.normal_pressure | 3.407390 | 3.440029 | +0.46% | 3.458542 | 3.359547 | -3.84% |
| phase.clean_build | 1.021012 | 1.009588 | -0.59% | 1.346963 | 1.360462 | +0.10% |
| phase.noop_build | 0.184909 | 0.176979 | -6.03% | 0.178146 | 0.211066 | +15.69% |
| phase.edit_build | 0.891888 | 0.914471 | +3.05% | 1.121438 | 1.118491 | +0.23% |
| phase.checkpoint | 0.301348 | 0.202831 | -32.34% | 0.338462 | 0.235696 | -30.29% |
| phase.restore | 0.039822 | 0.039885 | -0.49% | 0.041057 | 0.042418 | +3.91% |
| phase.restore_verify | 2.137390 | 2.074991 | -1.71% | 2.292078 | 2.315423 | +1.25% |
| phase.restored_rebuild | 0.192985 | 0.195132 | +1.76% | 0.193307 | 0.191450 | -1.20% |
| phase.cleanup | 0.313265 | 0.316777 | +0.09% | 0.332617 | 0.330857 | -1.86% |
| convenience.checkpointCompilerQuiescePlusProduct | 0.561458 | 0.438690 | -20.76% | 0.608203 | 0.513190 | -15.95% |
| convenience.restoreToCompilerReady | 0.177544 | 0.181247 | +1.33% | 0.186045 | 0.187088 | +1.16% |
| wholeFilesystemUsedBytes | 1,062,316,032 | 1,062,166,528 | -0.01% | 1,072,859,136 | 1,072,846,848 | -0.00% |

The pressure phase includes source preparation, all witness verification and observation serialization, whereas each operation timer excludes that setup/final verification. Thus rename median gains and whole-pressure phase outcomes need not move together. Runtime setup is separately timed, and its differences are not attributed to product code. Tiny whole-Used differences are not a general storage-win claim.

## Order strata

| Mode | Metric | Baseline first, paired geometric change | Candidate first, paired geometric change |
| --- | --- | ---: | ---: |
| inc0 | wholeSamplerSeconds | -5.10% | +0.56% |
| inc0 | phase.normal_pressure | -8.16% | +9.90% |
| inc0 | pressure.rename.p99Seconds | +32.89% | -10.87% |
| inc0 | pressure.write.p99Seconds | -41.14% | +8.59% |
| inc0 | pressure.metadata.p99Seconds | +98.15% | -0.05% |
| inc1 | wholeSamplerSeconds | +0.16% | -2.44% |
| inc1 | phase.normal_pressure | -1.80% | -5.84% |
| inc1 | pressure.rename.p99Seconds | +40.16% | +7.71% |
| inc1 | pressure.write.p99Seconds | +59.57% | +90.20% |
| inc1 | pressure.metadata.p99Seconds | +106.07% | +17.92% |

Only two pairs exist per order stratum. The complete operation arrays and every pairing are retained for further read-only diagnosis; there are no per-operation start timestamps, syscall traces, scheduler traces or process-tree CPU counters, so temporal overlap/cause cannot be reconstructed precisely.

## Correctness, concurrency and provenance

- Every sample uses two normally joined workers in disjoint paths; each completes exactly 128 ordinary rename/write/read/metadata/reverse-rename cycles. All 2,048 unrelated files, 16 moving payload files, mutable files, exact0640/nanosecond hardlink witnesses, symlinks and raw observations stay in the complete checkpoint tree. The worker-lifetime overlap is positive in every sample (0.416–0.585s); that establishes concurrent workers, not overlap of every syscall.
- All 16 full restored trees pass before any restored program/build: 2,360 entries in incremental0 and 2,554 in incremental1. The oracle preserves exact Python integer nanoseconds and internal hardlink groups; observation-file SHA256 matches executed raw stdout, and executed helper stdin SHA256 matches the profile identity. All clean/edit17Compiling and noop/restored17Fresh, program269→3400, build-script1→2, source/main/history preservation gates pass.
- All 64 generation-scoped compiler sessions end naturally with PID disappearance proof; zero mounts/containers remain after each sample, normal runtime restoration and loop detach pass. Four retained generations/three live views and the restored compiler are charged at active-space accounting. No forced teardown, fault/quota/mmap test, retry or selected cleanup is present.
- Exact12a2437 offline summary re-audit accepts all 16 records and reproduces server comparisons/identity exactly. All 4,440 collector files and 4,374 unique declared raw archive files pass size/SHA256. All 40 source/test hashes per variant match exact git objects, and all 19 benchmark script hashes match12a2437. Binary record hashes match all samples/manifests and are distinct; executable bytes themselves are not archived.
- Same Ubuntu24 runner class,45-minute job, absolute40-minute admission deadline,180second work+300second cleanup reserves, jobs2 Cargo, fresh symmetric4GiB images. Pressure adds128MiB available-space admission reserve without enlarging images. No8GiB fallback, billing/security/permission change, or parallel measurement job.
- Host compiler Rust1.99.1, workload compiler Rust/Cargo1.90.0; shared image `sha256:51bf0c82887f9dafba17ee788cd87cc642f06f5bb9e17640025e9995c9eb1a0d`. Pressure helper SHA256 `4a7bbb55cfe4e41bc2c2285415a12ea47b8e06e3c9ae46c086756db644925db2` binds all modes/variants/rounds.

Immutable complete evidence: [`data/stress-20261026/cargo-normal-pressure-own-ab`](data/stress-20261026/cargo-normal-pressure-own-ab), including exact-version audit scripts, run metadata, complete original artifact tree, recomputed summary and provenance audit. [Original artifact12636181586](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40289142188/artifacts/12636181586) is33,255,382 compressed bytes. Raw standalone JSON/archive snapshots, not JS-rounded embedded trees, are authoritative exact-integer evidence.

## Every slower geometric-mean metric

| Mode | Metric | Paired geometric change |
| --- | --- | ---: |
| inc0 | convenience.restoreToCompilerReady | +1.33% |
| inc0 | phase.clean_artifacts | +1.76% |
| inc0 | phase.clean_execute | +1.06% |
| inc0 | phase.cleanup | +0.09% |
| inc0 | phase.edit | +0.27% |
| inc0 | phase.edit_artifacts | +4.69% |
| inc0 | phase.edit_build | +3.05% |
| inc0 | phase.edit_execute | +0.54% |
| inc0 | phase.fixture_verify | +1.85% |
| inc0 | phase.fork | +7.47% |
| inc0 | phase.import | +2.08% |
| inc0 | phase.init | +10.81% |
| inc0 | phase.noop_execute | +0.74% |
| inc0 | phase.normal_pressure | +0.46% |
| inc0 | phase.restored_rebuild | +1.76% |
| inc0 | phase.restored_rebuild_artifacts | +0.53% |
| inc0 | phase.target_probe | +0.20% |
| inc0 | pressure.metadata.maximumSeconds | +28.26% |
| inc0 | pressure.metadata.p95Seconds | +52.20% |
| inc0 | pressure.metadata.p99Seconds | +40.73% |
| inc0 | pressure.read.maximumSeconds | +2.39% |
| inc0 | pressure.read.medianSeconds | +27.15% |
| inc0 | pressure.rename.maximumSeconds | +1.12% |
| inc0 | pressure.rename.p99Seconds | +8.84% |
| inc0 | pressure.write.p95Seconds | +2.04% |
| inc0 | runtimeSetupSeconds | +7.02% |
| inc1 | convenience.restoreToCompilerReady | +1.16% |
| inc1 | phase.checkpoint_readiness | +5.44% |
| inc1 | phase.clean_build | +0.10% |
| inc1 | phase.edit | +1.32% |
| inc1 | phase.edit_artifacts | +5.78% |
| inc1 | phase.edit_build | +0.23% |
| inc1 | phase.edit_execute | +1.38% |
| inc1 | phase.fork | +0.97% |
| inc1 | phase.noop_build | +15.69% |
| inc1 | phase.noop_execute | +2.22% |
| inc1 | phase.pre_checkpoint_oracle | +2.20% |
| inc1 | phase.preflight | +0.60% |
| inc1 | phase.restore | +3.91% |
| inc1 | phase.restore_verify | +1.25% |
| inc1 | phase.restored_rebuild_artifacts | +1.40% |
| inc1 | phase.restored_rebuild_execute | +0.09% |
| inc1 | phase.target_probe | +0.56% |
| inc1 | phase.transport_stop_before_checkpoint | +2.36% |
| inc1 | pressure.metadata.maximumSeconds | +27.06% |
| inc1 | pressure.metadata.medianSeconds | +10.64% |
| inc1 | pressure.metadata.p95Seconds | +52.96% |
| inc1 | pressure.metadata.p99Seconds | +55.88% |
| inc1 | pressure.read.maximumSeconds | +76.49% |
| inc1 | pressure.read.medianSeconds | +9.44% |
| inc1 | pressure.read.p99Seconds | +26.76% |
| inc1 | pressure.rename.maximumSeconds | +14.71% |
| inc1 | pressure.rename.p95Seconds | +14.86% |
| inc1 | pressure.rename.p99Seconds | +22.87% |
| inc1 | pressure.write.maximumSeconds | +142.41% |
| inc1 | pressure.write.p95Seconds | +18.99% |
| inc1 | pressure.write.p99Seconds | +74.22% |
| inc1 | runtimeSetupSeconds | +2.61% |

## Decision

Do not market the median rename reduction as a broad latency-tail or whole-Cargo win. Preserve these tail negatives and diagnose them before claiming a general responsiveness improvement. No additional main promotion or automatic rollback follows from this small matrix alone. Cache admission is a separate three-pin experiment with distinct controls and cannot be used to explain or pool these measurements.
