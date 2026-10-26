# Latest-main direct Cargo comparison: all correctness gates pass, Sprig remains slower

[Run40327569055](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40327569055) completed successfully in9m44s on26October2026. Benchmark `02dfe69f4b868fd47bd2fb5e91d3f4fbbab37707`; [predeclared fixed protocol](https://github.com/M4n5ter/sprig-benchmarks/blob/02dfe69f4b868fd47bd2fb5e91d3f4fbbab37707/STRESS-CARGO-LATEST-DIRECT-PROTOCOL.md). Exactly eight fresh samples: two balanced pairs in each Cargo incremental mode. No rerun, dropped pair, pressure stage or tracing.

**Observed result:** whole sampler wall is about2.51× LayerFS in incremental0 and2.55× in incremental1. Sprig’s product checkpoint boundary is faster in these observations, but does not make the whole Cargo workflow faster. Whole active filesystem Used is only about0.9% lower, approximately9–10MB on a roughly1.06GB runtime-inclusive baseline. These are two pairs per mode, not stable fleet-wide ratios or equal-durability measurements.

## Exact versions and shared workload

| Product | Current-main revision at selection and CI start | Product build compiler |
|---|---|---|
| Sprig | `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` | rustc1.99.1 |
| LayerFS | `ad78914e36b258b360daf13aec164b5655814689` | rustc1.85.1, daemon and native addon |

LayerFS is **unreleased main**, not latest formal release v1.1.0 (`9f97a7e`, eleven commits behind). Both live main refs matched the immutable selections before product builds. No performance equivalence with the older release is assumed. The prior released-LayerFS/direct and Sprig-only results remain historical, separate series.

The actual Cargo workload uses the same Rust/Cargo1.90.0 image for both products, jobs2, frozen DAG16v2/17packages, and offline/locked verbose builds. Product build compilers above are not the workload compiler.

- Shared image: `sha256:28d8df9e4b38fcf9b82f5f58a3e9ee519b0a66bf82aeaaf1ccebc41a7afc324c`.
- Shared protocol SHA256: `08822e9e6e7cd411561559a689bd91c404b587c95ec452fa62e4018e166b748e`.
- Frozen fixture manifest SHA256: `70310e765d81880f2e888ce914e508ded52b22f2dec6519d4f837d38e7616194`.
- Sprig release ELF SHA256: `886089df03f2bbe5d6d0faf811e70e62217fa7011d58d2026a33f90fc3ccd2ed`.
- LayerFS daemon SHA256: `e27e2999c50839d96e94d7f3f6b0751f7a7088f8859516a36b3ef9c9707b1ca3`.
- LayerFS native-addon SHA256: `0c736fc1c21971d8877d8719abf835742d3ad55853d7f4ec9fbe0f786fa2ed3c`.

Every sample used a fresh symmetric4GiB Btrfs image. The existing45-minute job/40-minute setup-inclusive admission limit,180swork+300scleanup admission reserves and normal owned cleanup were preserved. The shared external inc0/inc1 capacity pilots were setup only, not product timings or target caches. Runtime setup is reported separately and not subtracted from whole Used.

## Every paired whole-task observation

Ratios are Sprig/LayerFS; smaller is better for these wall/space metrics. Whole wall means sampler process launch through exit, including normal cleanup and evidence serialization, **excluding separately measured runtime import/setup**.

| Mode | Pair | Execution order | Sprig whole seconds | LayerFS whole seconds | Ratio | Sprig Used bytes | LayerFS Used bytes |
|---|---:|---|---:|---:|---:|---:|---:|
| inc0 | 0 | Sprig→LayerFS | 8.847957 | 3.505349 | 2.524130 | 1055776768 | 1065230336 |
| inc0 | 1 | LayerFS→Sprig | 8.855303 | 3.542588 | 2.499671 | 1055428608 | 1065439232 |
| inc1 | 0 | LayerFS→Sprig | 10.252422 | 4.013349 | 2.554580 | 1066307584 | 1075646464 |
| inc1 | 1 | Sprig→LayerFS | 10.328144 | 4.045296 | 2.553124 | 1065967616 | 1075417088 |

The paired geometric whole-wall ratios are2.511871×/2.553852× for inc0/inc1. Paired geometric space changes are−0.9135%/−0.8734%. No mode or older run is pooled.

## Common metrics and all common phases

Each value list is pair0,pair1 in seconds, except Used bytes. The ratio columns retain both pairs, so negative/order observations cannot disappear behind one aggregate. Geometric means are descriptive only. Phase/composite timers overlap; **do not sum or subtract them to attribute the whole-task difference**. A small checkpoint advantage does not establish equal durability or a whole-workflow win.

### inc0

| Metric | Sprig values | LayerFS values | Pair ratios | Paired geom ratio |
|---|---:|---:|---:|---:|
| `fullTaskSeconds` | 8.754991, 8.762624 | 3.454112, 3.490316 | 2.534658, 2.510553 | 2.522577 |
| `phase.cargo_setup` | 0.073341, 0.070750 | 0.021536, 0.019549 | 3.405476, 3.619050 | 3.510639 |
| `phase.checkpoint` | 0.145506, 0.154002 | 0.159586, 0.157487 | 0.911773, 0.977870 | 0.944243 |
| `phase.checkpoint_cli` | 0.141782, 0.150439 | 0.157018, 0.155065 | 0.902965, 0.970168 | 0.935964 |
| `phase.checkpoint_readiness` | 0.003724, 0.003563 | 0.002567, 0.002422 | 1.450405, 1.470928 | 1.460631 |
| `phase.clean_artifacts` | 0.101070, 0.107347 | 0.045941, 0.046728 | 2.200026, 2.297257 | 2.248116 |
| `phase.clean_build` | 1.393722, 1.417509 | 0.659766, 0.672849 | 2.112448, 2.106727 | 2.109585 |
| `phase.clean_execute` | 0.071546, 0.073479 | 0.018472, 0.018633 | 3.873149, 3.943571 | 3.908201 |
| `phase.cleanup` | 0.446097, 0.427680 | 0.219359, 0.224604 | 2.033637, 1.904152 | 1.967830 |
| `phase.edit` | 0.101189, 0.102830 | 0.043238, 0.043612 | 2.340283, 2.357818 | 2.349034 |
| `phase.edit_artifacts` | 0.099675, 0.105027 | 0.045114, 0.045950 | 2.209396, 2.285651 | 2.247200 |
| `phase.edit_build` | 1.309003, 1.323462 | 0.527391, 0.526623 | 2.482036, 2.513111 | 2.497525 |
| `phase.edit_execute` | 0.071825, 0.075136 | 0.019181, 0.017903 | 3.744671, 4.196758 | 3.964275 |
| `phase.fixture_verify` | 0.364358, 0.362248 | 0.102990, 0.087982 | 3.537808, 4.117318 | 3.816580 |
| `phase.fork` | 0.044450, 0.046134 | 0.005585, 0.005896 | 7.959152, 7.824868 | 7.891725 |
| `phase.import` | 0.056330, 0.050744 | 0.272825, 0.273982 | 0.206469, 0.185211 | 0.195551 |
| `phase.init` | 0.015318, 0.014515 | 0.039340, 0.039812 | 0.389360, 0.364599 | 0.376776 |
| `phase.noop_artifacts` | 0.103434, 0.107182 | 0.047039, 0.046979 | 2.198891, 2.281474 | 2.239802 |
| `phase.noop_build` | 0.255637, 0.282660 | 0.064573, 0.062771 | 3.958886, 4.503035 | 4.222203 |
| `phase.noop_execute` | 0.070555, 0.074364 | 0.019006, 0.019230 | 3.712232, 3.867061 | 3.788856 |
| `phase.pre_checkpoint_oracle` | 0.446694, 0.465847 | 0.125536, 0.129944 | 3.558293, 3.584972 | 3.571608 |
| `phase.preflight` | 0.087154, 0.089962 | 0.085996, 0.090473 | 1.013461, 0.994347 | 1.003858 |
| `phase.restore` | 0.030267, 0.029449 | 0.004619, 0.004351 | 6.553064, 6.769153 | 6.660232 |
| `phase.restore_verify` | 0.680582, 0.657999 | 0.214248, 0.223190 | 3.176609, 2.948151 | 3.060249 |
| `phase.restored_artifacts` | 0.102950, 0.101066 | 0.046357, 0.048480 | 2.220804, 2.084690 | 2.151671 |
| `phase.restored_execute` | 0.071334, 0.072896 | 0.018105, 0.019044 | 3.940027, 3.827716 | 3.883466 |
| `phase.restored_rebuild` | 0.308354, 0.299196 | 0.067345, 0.070534 | 4.578694, 4.241860 | 4.407060 |
| `phase.restored_rebuild_artifacts` | 0.105554, 0.105396 | 0.046817, 0.047049 | 2.254617, 2.240148 | 2.247371 |
| `phase.restored_rebuild_execute` | 0.074589, 0.070923 | 0.018240, 0.019268 | 4.089318, 3.680842 | 3.879708 |
| `phase.retained_input_verify` | 1.294033, 1.263249 | 0.393267, 0.404854 | 3.290470, 3.120257 | 3.204233 |
| `phase.space` | 0.112931, 0.110498 | 0.019648, 0.020319 | 5.747541, 5.438217 | 5.590740 |
| `phase.target_probe` | 0.102041, 0.102002 | 0.042692, 0.043855 | 2.390167, 2.325904 | 2.357817 |
| `phase.toolchain_verify` | 0.092030, 0.087805 | 0.034623, 0.033158 | 2.658085, 2.648059 | 2.653067 |
| `runtimeSetupSeconds` | 14.680154, 15.038637 | 14.851608, 14.980432 | 0.988456, 1.003885 | 0.996141 |
| `wholeFilesystemUsedBytes` | 1055776768, 1055428608 | 1065230336, 1065439232 | 0.991125, 0.990604 | 0.990865 |
| `wholeSamplerSeconds` | 8.847957, 8.855303 | 3.505349, 3.542588 | 2.524130, 2.499671 | 2.511871 |

### inc1

| Metric | Sprig values | LayerFS values | Pair ratios | Paired geom ratio |
|---|---:|---:|---:|---:|
| `fullTaskSeconds` | 10.155466, 10.233758 | 3.957324, 3.990964 | 2.566246, 2.564232 | 2.565239 |
| `phase.cargo_setup` | 0.074884, 0.080026 | 0.020266, 0.020140 | 3.695057, 3.973529 | 3.831764 |
| `phase.checkpoint` | 0.202418, 0.195354 | 0.260093, 0.263514 | 0.778252, 0.741341 | 0.759572 |
| `phase.checkpoint_cli` | 0.199131, 0.191640 | 0.257550, 0.261000 | 0.773172, 0.734253 | 0.753462 |
| `phase.checkpoint_readiness` | 0.003287, 0.003714 | 0.002543, 0.002514 | 1.292736, 1.477155 | 1.381873 |
| `phase.clean_artifacts` | 0.105472, 0.103241 | 0.044623, 0.045446 | 2.363594, 2.271740 | 2.317212 |
| `phase.clean_build` | 1.839837, 1.906550 | 0.828243, 0.829300 | 2.221374, 2.298988 | 2.259848 |
| `phase.clean_execute` | 0.075222, 0.087202 | 0.017359, 0.018294 | 4.333207, 4.766736 | 4.544805 |
| `phase.cleanup` | 0.446353, 0.452331 | 0.211120, 0.208801 | 2.114211, 2.166321 | 2.140107 |
| `phase.edit` | 0.097327, 0.101598 | 0.040199, 0.042141 | 2.421135, 2.410926 | 2.416025 |
| `phase.edit_artifacts` | 0.102003, 0.103125 | 0.046815, 0.047318 | 2.178840, 2.179407 | 2.179124 |
| `phase.edit_build` | 1.578120, 1.621927 | 0.623463, 0.641528 | 2.531215, 2.528227 | 2.529721 |
| `phase.edit_execute` | 0.071783, 0.077636 | 0.018523, 0.019485 | 3.875335, 3.984502 | 3.929540 |
| `phase.fixture_verify` | 0.383333, 0.375172 | 0.083975, 0.085610 | 4.564820, 4.382327 | 4.472643 |
| `phase.fork` | 0.042132, 0.047108 | 0.005649, 0.005444 | 7.457825, 8.653496 | 8.033446 |
| `phase.import` | 0.046365, 0.048762 | 0.277558, 0.279797 | 0.167045, 0.174277 | 0.170623 |
| `phase.init` | 0.014796, 0.014667 | 0.038013, 0.037345 | 0.389237, 0.392748 | 0.390989 |
| `phase.noop_artifacts` | 0.103188, 0.105673 | 0.044253, 0.045302 | 2.331791, 2.332647 | 2.332219 |
| `phase.noop_build` | 0.276428, 0.278961 | 0.062469, 0.063287 | 4.425025, 4.407900 | 4.416454 |
| `phase.noop_execute` | 0.073690, 0.074919 | 0.017339, 0.018965 | 4.249935, 3.950476 | 4.097471 |
| `phase.pre_checkpoint_oracle` | 0.732948, 0.748509 | 0.182388, 0.178126 | 4.018607, 4.202143 | 4.109350 |
| `phase.preflight` | 0.086896, 0.090631 | 0.087154, 0.091353 | 0.997045, 0.992087 | 0.994563 |
| `phase.restore` | 0.031595, 0.036307 | 0.004580, 0.004518 | 6.897780, 8.035715 | 7.445038 |
| `phase.restore_verify` | 0.999333, 1.020158 | 0.333126, 0.318262 | 2.999866, 3.205405 | 3.100933 |
| `phase.restored_artifacts` | 0.105493, 0.102108 | 0.045881, 0.045562 | 2.299262, 2.241100 | 2.269995 |
| `phase.restored_execute` | 0.075226, 0.071415 | 0.018055, 0.018803 | 4.166564, 3.798042 | 3.978038 |
| `phase.restored_rebuild` | 0.289792, 0.282551 | 0.065871, 0.064361 | 4.399400, 4.390092 | 4.394743 |
| `phase.restored_rebuild_artifacts` | 0.106859, 0.102218 | 0.046036, 0.046405 | 2.321209, 2.202735 | 2.261196 |
| `phase.restored_rebuild_execute` | 0.072326, 0.071462 | 0.018703, 0.019201 | 3.867083, 3.721797 | 3.793745 |
| `phase.retained_input_verify` | 1.299018, 1.247881 | 0.398627, 0.414750 | 3.258735, 3.008754 | 3.131251 |
| `phase.space` | 0.111849, 0.110741 | 0.018189, 0.018658 | 6.149221, 5.935361 | 6.041345 |
| `phase.target_probe` | 0.099927, 0.102778 | 0.042207, 0.042462 | 2.367578, 2.420496 | 2.393891 |
| `phase.toolchain_verify` | 0.096402, 0.091728 | 0.031397, 0.031967 | 3.070439, 2.869492 | 2.968265 |
| `runtimeSetupSeconds` | 14.893870, 15.083389 | 14.930464, 14.909790 | 0.997549, 1.011643 | 1.004571 |
| `wholeFilesystemUsedBytes` | 1066307584, 1065967616 | 1075646464, 1075417088 | 0.991318, 0.991213 | 0.991266 |
| `wholeSamplerSeconds` | 10.252422, 10.328144 | 4.013349, 4.045296 | 2.554580, 2.553124 | 2.553852 |

## Unmatched boundaries — no fabricated comparator values

| Mode | Product | Metric | Pair0,pair1 seconds |
|---|---|---|---:|
| inc0 | sprig-writable | `convenience.checkpointCompilerQuiescePlusProduct` | 0.518996, 0.516954 |
| inc0 | sprig-writable | `convenience.restoreToCompilerReady` | 0.226987, 0.235070 |
| inc0 | sprig-writable | `phase.transport_stop_before_checkpoint` | 0.358073, 0.346340 |
| inc0 | sprig-writable | `phase.transport_stop_final_cleanup` | 0.332766, 0.305449 |
| inc0 | layerfs | `phase.compiler_image_verify` | 0.037779, 0.040222 |
| inc0 | layerfs | `phase.preserve_logs` | 0.008024, 0.007926 |
| inc1 | sprig-writable | `convenience.checkpointCompilerQuiescePlusProduct` | 0.568534, 0.528051 |
| inc1 | sprig-writable | `convenience.restoreToCompilerReady` | 0.233200, 0.238085 |
| inc1 | sprig-writable | `phase.transport_stop_before_checkpoint` | 0.350615, 0.316321 |
| inc1 | sprig-writable | `phase.transport_stop_final_cleanup` | 0.325492, 0.336630 |
| inc1 | layerfs | `phase.compiler_image_verify` | 0.039829, 0.037406 |
| inc1 | layerfs | `phase.preserve_logs` | 0.007981, 0.007981 |

Sprig quiesce+checkpoint composites are about0.517–0.569s and restore-to-compiler-ready about0.227–0.238s. LayerFS has no matched entries for these composites. Its persistent UID501 SDK and Sprig’s generation-scoped root Docker CLI differ; all costs remain charged. The observed stage differences alone do not isolate filesystem versus transport/compiler/durability causes.

## Correctness and complete evidence

All eight samples passed17-package clean/edited compilation,17Fresh with zero compilation on no-op/restored builds, executable269→3400 and generated build values1→2. All restored trees match the complete oracle before execution/rebuild:280entries in inc0,474 in inc1, exact content/mode/nanosecond timestamps/symlinks/internal hardlinks. Source/main/history invariants, acknowledged checkpoint identities and ordinary cleanup passed.

Independent audit checked **1,416 original artifact files /29,855,368 bytes**, all1,415collector-listed files, and **1,362 unique declared raw archives** with no missing/hash/size errors. The16 archive declarations are eight standalone reports plus their mode-report references, not16 independent samples. All eight capacity and outer-cleanup records were verified. It matched23benchmark script hashes,43Sprig source/build-input hashes and1,552LayerFS source/build-input hashes against their exact committed objects, plus six immutable analysis helpers. LayerFS’s changed addon source was checked against the exactad789 Git blob, not substituted from v1.1.0.

Independent exact-integer recomputation matches the original successful CI summary, including every per-sample metric and paired result. No product rerun or posthoc runtime/schema repair was needed. LayerFS structured decimal-string nanoseconds were compared against archived raw integer JSON without changing original bytes; JavaScript-rounded embedded trees were not treated as authoritative.

[Complete original public CI artifact](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40327569055/artifacts/12654595029): artifact12654595029,4,137,259 compressed bytes, recorded expiration24January2027. This compressed transfer size is **not** physical filesystem Used. The [durable lossless archive](data/stress-20261026/cargo-latest-main-direct/run-40327569055-evidence.tar.gz) preserves all 1,416 original files plus exact analysis helpers and provenance (1,429 members total). Its [complete SHA256 manifest](data/stress-20261026/cargo-latest-main-direct/manifest.json) and [verification/reanalysis instructions](data/stress-20261026/cargo-latest-main-direct/README.md) bind every original byte; no failed or slower observation is omitted.

## Limits and decisions

- Two pairs per mode on one runner are descriptive small-N observations. Both whole-wall pairs favor LayerFS, but this is not a p95/p99, statistical-significance or multi-host stability estimate.
- Sprig retains its sync/fsync semantics; LayerFS requires Disposable/WAL/synchronous=OFF plus MEMORY/OFF workspace overlays. The measurements are **not an equal-durability ranking**; the caveat does not erase the observed Cargo gap.
- Whole Used includes runtime/compiler, target/cache, retained views/history and logs. A~0.9% whole-image reduction cannot be described as a broad application-store space advantage.
- No causal inference about the inventory optimization follows from comparison with older runners/images. The earlier within-Sprig eligible64KiB improvement does not translate to a2.5× direct win; current Cargo remains slower.
- This run covers writable Cargo, not an updated complete Native/Projection/history suite. Any next scene requires its own reviewed identity/protocol and results; no automatic rerun or main promotion follows.
