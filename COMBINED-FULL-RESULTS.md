# Combined schema-14 candidate: full three-backend comparison

25 October 2026. Sprig `2a01fe445b8057ca49b4e8284fdd5583bbb4185c` versus released LayerFS v1.1.0 `9f97a7ec95b662e9cb288704afa165feff132cfa`; benchmark `4383a456cd8f26dbbfe4047be4a40d669f1adb9d`. Default auto compression, fresh stores, production CLI versus production SDK. Candidate was unmerged at run preparation; this comparison is not a schema-10/main migration test and does not measure a later promotion.

**126/126 records passed, with 5,400 complete historical snapshot readbacks.** Each backend has seven cases × three alternating-order repetitions × two products = 42 records and 1,800 readbacks. Both real projection and owned-writable kernel gates passed on each runner. Every sample completed normal cleanup with no recorded error. Earlier smoke is separate and not pooled into these medians.

## Interpretation and boundaries

- Each backend is a separate hosted runner. Pair ratios compare the two products within the same case/round; they do not establish causal improvements across backend runners, prior reports, or individual optimizations in the combined candidate. Three pairs are descriptive, not statistical certainty.
- Preparation includes init + import + first usable fork + full checksum read. Warm includes second usable fork + full checksum read. History write+commit sums all 100 frozen write tasks and complete checkpoints. Restore total sums all 100 public restore/mount, full checksum read, and normal cleanup tasks. Each displayed total is summed per sample before taking its median.
- Primary footprint is whole-Btrfs Used minus fresh empty filesystem, with main/work/second live, before historical restores. Post-history is a separate later boundary after all restores/readbacks and unchanged-input checks, still with the original three views live. It is not a replacement primary score or a GC/pruning result.
- Post-history retains exactly 103 native/projection generations or 203 owned-writable generations in each history sample. Native retains materialized restored trees; projection and writable retain their normal product representations. LayerFS retains its normal history branches; equal generation representation is not claimed.
- Whole-filesystem footprint includes persistent software/runtime where deployed: LayerFS image, Docker/containerd roots, overlays, logs and SDK state are included. Lower Sprig footprint is **not** the same percentage of application-only storage savings or common-toolchain deployment savings. Runtime-ready subtraction is diagnostic, not exact application data. All retained product state is charged; host/RAM and executable/build inputs are excluded.
- Sprig synchronization and fsync remain enabled. LayerFS Disposable uses global WAL/OFF and workspace MEMORY/OFF/EXCLUSIVE. CLI startup versus persistent SDK execution remains charged. No equal crash durability, cold-cache, total memory, or background-compute claim.
- Readbacks establish the frozen listed-file content/history workload plus unchanged source/main/second and normal cleanup; they are not a complete metadata compatibility or power-loss proof. Cargo acceptance is a separate protocol/report.

[Full protocol](feasibility/COMBINED-MEASUREMENT-SCOPE.md) · [Detailed inherited boundaries](feasibility/CURRENT-MEASUREMENT-BOUNDARIES.md) · [All raw checksums/provenance](data/combined-20261025/full-provenance.json) · [Every pair and ratio](data/combined-20261025/full-paired-summary.json)

## native

[Exact full run 40166273638](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40166273638) · [Unchanged full artifact](data/combined-20261025/native-full/)

Values are medians of three samples. MiB = 1,048,576 bytes. Lower is better for these measured tasks; different semantics remain as disclosed.

| Case | Product | Preparation ms | Warm ms | Write + 100 commits s | 100 restores/read/cleanup s | Primary MiB | Post-history MiB |
|---|---|---:|---:|---:|---:|---:|---:|
| identical | sprig-native | 735.44 | 226.18 | — | — | 101.555 | 101.559 |
| identical | layerfs | 550.96 | 189.02 | — | — | 94.980 | 94.980 |
| unique | sprig-native | 923.10 | 225.66 | — | — | 201.012 | 201.016 |
| unique | layerfs | 2031.13 | 700.15 | — | — | 195.320 | 195.320 |
| mixed | sprig-native | 883.76 | 219.11 | — | — | 175.918 | 175.922 |
| mixed | layerfs | 1618.97 | 566.76 | — | — | 170.074 | 170.074 |
| insert | sprig-native | 783.61 | 223.19 | — | — | 111.453 | 111.457 |
| insert | layerfs | 621.61 | 192.52 | — | — | 98.488 | 98.488 |
| history-distributed | sprig-native | 794.07 | 338.64 | 4.611 | 27.050 | 6.273 | 153.340 |
| history-distributed | layerfs | 467.21 | 83.66 | 2.549 | 8.389 | 99.254 | 101.199 |
| history-hotset | sprig-native | 806.81 | 357.15 | 4.709 | 27.780 | 9.961 | 157.348 |
| history-hotset | layerfs | 476.75 | 81.37 | 2.587 | 8.336 | 99.199 | 101.543 |
| history-recurring | sprig-native | 785.87 | 330.48 | 4.530 | 27.224 | 4.223 | 151.355 |
| history-recurring | layerfs | 482.57 | 83.24 | 2.943 | 8.271 | 98.688 | 100.730 |

### Within-pair ratios (Sprig / LayerFS)

Each cell is median paired ratio [min–max], not the ratio of medians. Ratios above 1 are slower/larger.

| Case | Preparation | Warm | Write + commits | Restore total | Primary space | Post-history space |
|---|---:|---:|---:|---:|---:|---:|
| identical | 1.305 [1.264–1.360] | 1.154 [1.056–1.222] | — | — | 1.069 [1.068–1.070] | 1.069 [1.068–1.070] |
| unique | 0.462 [0.442–0.464] | 0.322 [0.300–0.341] | — | — | 1.029 [1.029–1.029] | 1.029 [1.029–1.029] |
| mixed | 0.554 [0.546–0.563] | 0.379 [0.372–0.387] | — | — | 1.034 [1.034–1.034] | 1.034 [1.034–1.034] |
| insert | 1.248 [1.243–1.291] | 1.159 [1.151–1.187] | — | — | 1.132 [1.131–1.132] | 1.132 [1.131–1.132] |
| history-distributed | 1.721 [1.649–1.748] | 4.025 [3.957–4.284] | 1.810 [1.796–1.820] | 3.213 [3.201–3.252] | 0.063 [0.063–0.064] | 1.515 [1.515–1.516] |
| history-hotset | 1.692 [1.611–1.717] | 4.389 [4.046–4.586] | 1.820 [1.770–1.842] | 3.335 [3.236–3.446] | 0.100 [0.100–0.101] | 1.549 [1.546–1.550] |
| history-recurring | 1.620 [1.577–1.704] | 3.965 [3.850–3.977] | 1.539 [1.492–1.552] | 3.269 [3.256–3.326] | 0.043 [0.043–0.043] | 1.500 [1.499–1.503] |

## projection

[Exact full run 40166281989](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40166281989) · [Unchanged full artifact](data/combined-20261025/projection-full/)

Values are medians of three samples. MiB = 1,048,576 bytes. Lower is better for these measured tasks; different semantics remain as disclosed.

| Case | Product | Preparation ms | Warm ms | Write + 100 commits s | 100 restores/read/cleanup s | Primary MiB | Post-history MiB |
|---|---|---:|---:|---:|---:|---:|---:|
| identical | sprig-projection | 332.41 | 140.91 | — | — | 1.094 | 1.105 |
| identical | layerfs | 478.93 | 158.80 | — | — | 95.137 | 95.137 |
| unique | sprig-projection | 961.03 | 164.97 | — | — | 100.457 | 100.469 |
| unique | layerfs | 1789.30 | 573.03 | — | — | 195.297 | 195.297 |
| mixed | sprig-projection | 792.94 | 163.50 | — | — | 75.363 | 75.375 |
| mixed | layerfs | 1420.81 | 480.95 | — | — | 169.977 | 169.977 |
| insert | sprig-projection | 385.94 | 147.62 | — | — | 9.539 | 9.551 |
| insert | layerfs | 518.73 | 157.67 | — | — | 98.523 | 98.523 |
| history-distributed | sprig-projection | 185.31 | 82.37 | 3.393 | 7.696 | 4.109 | 5.910 |
| history-distributed | layerfs | 359.46 | 56.16 | 1.582 | 5.177 | 99.160 | 101.160 |
| history-hotset | sprig-projection | 185.44 | 88.05 | 4.388 | 7.742 | 8.250 | 9.988 |
| history-hotset | layerfs | 356.37 | 51.15 | 1.615 | 5.064 | 99.176 | 101.523 |
| history-recurring | sprig-projection | 188.14 | 83.30 | 2.820 | 7.898 | 1.793 | 3.559 |
| history-recurring | layerfs | 363.99 | 54.69 | 1.878 | 5.005 | 98.762 | 100.750 |

### Within-pair ratios (Sprig / LayerFS)

Each cell is median paired ratio [min–max], not the ratio of medians. Ratios above 1 are slower/larger.

| Case | Preparation | Warm | Write + commits | Restore total | Primary space | Post-history space |
|---|---:|---:|---:|---:|---:|---:|
| identical | 0.704 [0.666–0.706] | 0.903 [0.870–0.918] | — | — | 0.011 [0.011–0.012] | 0.012 [0.012–0.012] |
| unique | 0.537 [0.515–0.567] | 0.288 [0.277–0.294] | — | — | 0.514 [0.514–0.514] | 0.514 [0.514–0.515] |
| mixed | 0.558 [0.549–0.569] | 0.346 [0.335–0.349] | — | — | 0.443 [0.443–0.443] | 0.443 [0.443–0.444] |
| insert | 0.733 [0.723–0.753] | 0.936 [0.871–0.972] | — | — | 0.097 [0.097–0.097] | 0.097 [0.097–0.097] |
| history-distributed | 0.511 [0.495–0.555] | 1.699 [1.453–1.735] | 2.145 [2.084–2.246] | 1.487 [1.442–1.550] | 0.041 [0.041–0.041] | 0.058 [0.058–0.058] |
| history-hotset | 0.519 [0.503–0.527] | 1.673 [1.563–1.959] | 2.703 [2.677–2.726] | 1.529 [1.507–1.542] | 0.083 [0.083–0.083] | 0.098 [0.098–0.099] |
| history-recurring | 0.513 [0.504–0.517] | 1.496 [1.458–1.578] | 1.501 [1.483–1.503] | 1.586 [1.489–1.619] | 0.018 [0.018–0.018] | 0.035 [0.035–0.035] |

## writable

[Exact full run 40166285366](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40166285366) · [Unchanged full artifact](data/combined-20261025/writable-full/)

Values are medians of three samples. MiB = 1,048,576 bytes. Lower is better for these measured tasks; different semantics remain as disclosed.

| Case | Product | Preparation ms | Warm ms | Write + 100 commits s | 100 restores/read/cleanup s | Primary MiB | Post-history MiB |
|---|---|---:|---:|---:|---:|---:|---:|
| identical | sprig-writable | 347.69 | 200.00 | — | — | 1.082 | 1.094 |
| identical | layerfs | 462.64 | 136.22 | — | — | 95.047 | 95.047 |
| unique | sprig-writable | 1001.58 | 241.51 | — | — | 100.445 | 100.457 |
| unique | layerfs | 1941.92 | 460.45 | — | — | 195.363 | 195.363 |
| mixed | sprig-writable | 860.46 | 234.18 | — | — | 75.352 | 75.363 |
| mixed | layerfs | 1622.39 | 431.60 | — | — | 169.973 | 169.973 |
| insert | sprig-writable | 407.78 | 221.88 | — | — | 9.527 | 9.539 |
| insert | layerfs | 531.12 | 141.04 | — | — | 98.551 | 98.551 |
| history-distributed | sprig-writable | 221.94 | 137.96 | 7.006 | 13.632 | 5.125 | 7.062 |
| history-distributed | layerfs | 597.16 | 49.85 | 1.925 | 5.011 | 99.266 | 101.234 |
| history-hotset | sprig-writable | 213.24 | 135.03 | 7.095 | 13.248 | 8.875 | 10.906 |
| history-hotset | layerfs | 370.98 | 46.44 | 1.834 | 4.766 | 99.289 | 101.629 |
| history-recurring | sprig-writable | 259.91 | 131.69 | 6.808 | 13.381 | 8.438 | 10.500 |
| history-recurring | layerfs | 393.47 | 47.15 | 2.106 | 4.941 | 98.746 | 100.734 |

### Within-pair ratios (Sprig / LayerFS)

Each cell is median paired ratio [min–max], not the ratio of medians. Ratios above 1 are slower/larger.

| Case | Preparation | Warm | Write + commits | Restore total | Primary space | Post-history space |
|---|---:|---:|---:|---:|---:|---:|
| identical | 0.760 [0.712–0.765] | 1.469 [1.445–1.560] | — | — | 0.011 [0.011–0.011] | 0.012 [0.011–0.012] |
| unique | 0.517 [0.515–0.520] | 0.531 [0.475–0.533] | — | — | 0.514 [0.514–0.514] | 0.514 [0.514–0.515] |
| mixed | 0.530 [0.516–0.576] | 0.548 [0.543–0.556] | — | — | 0.443 [0.443–0.443] | 0.443 [0.443–0.443] |
| insert | 0.785 [0.752–0.803] | 1.558 [1.517–1.627] | — | — | 0.097 [0.097–0.097] | 0.097 [0.097–0.097] |
| history-distributed | 0.374 [0.274–0.512] | 2.768 [2.384–2.898] | 3.607 [3.411–4.020] | 2.721 [2.538–3.049] | 0.052 [0.051–0.052] | 0.070 [0.069–0.070] |
| history-hotset | 0.552 [0.530–0.610] | 2.609 [2.564–3.121] | 3.869 [3.767–4.072] | 2.780 [2.734–2.918] | 0.089 [0.089–0.090] | 0.107 [0.107–0.107] |
| history-recurring | 0.661 [0.541–0.778] | 2.793 [2.574–2.905] | 3.214 [3.174–3.592] | 2.709 [2.708–2.716] | 0.085 [0.085–0.086] | 0.104 [0.104–0.104] |

## Negative and mixed findings

- **native preparation:** Sprig median paired ratio is above 1 in 5/7 cases (identical, insert, history-distributed, history-hotset, history-recurring).
- **native warm fork/read:** Sprig median paired ratio is above 1 in 5/7 cases (identical, insert, history-distributed, history-hotset, history-recurring).
- **native history write+commit:** Sprig median paired ratio is above 1 in 3/3 cases (history-distributed, history-hotset, history-recurring).
- **native history restore/read/cleanup:** Sprig median paired ratio is above 1 in 3/3 cases (history-distributed, history-hotset, history-recurring).
- **native post-history footprint is larger** in identical, unique, mixed, insert, history-distributed, history-hotset, history-recurring. These retained bytes remain in the report; no favorable-boundary substitution is made.
- **projection preparation:** Sprig median paired ratio is above 1 in 0/7 cases.
- **projection warm fork/read:** Sprig median paired ratio is above 1 in 3/7 cases (history-distributed, history-hotset, history-recurring).
- **projection history write+commit:** Sprig median paired ratio is above 1 in 3/3 cases (history-distributed, history-hotset, history-recurring).
- **projection history restore/read/cleanup:** Sprig median paired ratio is above 1 in 3/3 cases (history-distributed, history-hotset, history-recurring).
- **writable preparation:** Sprig median paired ratio is above 1 in 0/7 cases.
- **writable warm fork/read:** Sprig median paired ratio is above 1 in 5/7 cases (identical, insert, history-distributed, history-hotset, history-recurring).
- **writable history write+commit:** Sprig median paired ratio is above 1 in 3/3 cases (history-distributed, history-hotset, history-recurring).
- **writable history restore/read/cleanup:** Sprig median paired ratio is above 1 in 3/3 cases (history-distributed, history-hotset, history-recurring).

No overall product victory or product-only improvement over old reports is inferred. All raw individual samples, phase measurements, failed/cleanup fields, per-step ledgers, environment identities and original gate outputs are preserved byte-for-byte. The checksum manifest verifies each downloaded file against its report copy.
