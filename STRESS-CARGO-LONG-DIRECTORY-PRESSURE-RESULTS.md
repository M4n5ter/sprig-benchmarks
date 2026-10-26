# Long mounted release pressure: mixed tails, no broad gain

[Run40304840409](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40304840409) completed **success in18m16s** at benchmark `c42b2a22ebc65a9711454c4649cc546539d4a923`. All16 planned samples and correctness gates, final summary, collector and artifact upload passed. Independent exact-source analysis reproduced server identities/comparisons and audited every raw archive.

Fixed untraced release comparison: main `b300693e01c652c1a9631c61b7a439892d8f75cd` → bounded directory candidate `dfee7e4e9ee223f25d141d2e05d3cfcdc6c9269f`. Separate profile `normal-rename2-1024-v2`: two workers×1024 cycles, not the old128-cycle experiment and not the earlier4ef→b300 comparison.

**The intended directory optimization did not establish a broad mounted responsiveness or whole-Cargo win.** Whole sampler paired geometric change is **−1.913% inc0 /−0.208% inc1**. Per-sample rename p99 improves8.645% in inc0 but worsens3.723% in inc1; inc1 metadata p99 worsens4.034% and read p99 worsens5.403%. Rename medians are slightly slower in both modes (+0.328%/+1.181%). Preserve these mixed results; do not promote from this matrix.

Tail changes below are geometric means of four paired **per-sample dependent-operation quantile ratios**, not end-to-end p99 or163,840 independent trials. Four pairs per mode and two per order stratum do not support significance, stable whole-run tails or generalization to other hosts.

## Every whole-sampler pair

| Mode | Round | Actual order | Baseline seconds | Candidate seconds | Paired change |
|---|---:|---|---:|---:|---:|
| inc0 | 0 | baseline → candidate | 26.059401 | 25.110872 | -3.640% |
| inc0 | 1 | candidate → baseline | 25.976461 | 24.857822 | -4.306% |
| inc0 | 2 | baseline → candidate | 25.403864 | 25.348854 | -0.217% |
| inc0 | 3 | candidate → baseline | 25.820761 | 25.976488 | +0.603% |
| inc1 | 0 | candidate → baseline | 26.117362 | 26.793700 | +2.590% |
| inc1 | 1 | baseline → candidate | 27.012556 | 26.542117 | -1.742% |
| inc1 | 2 | candidate → baseline | 26.761325 | 26.721411 | -0.149% |
| inc1 | 3 | baseline → candidate | 27.194286 | 26.794038 | -1.472% |

All8pairs/16samples retained. Whole sampler includes the fixed pressure stage and normal checks/cleanup, but excludes separately measured runtime/image setup. Inc0 runtime setup happened to differ materially between positions; it is not assigned to product code or folded into a fabricated whole-time improvement.

## Every per-sample operation quantile

Each bracket lists rounds0–3 in milliseconds. Every sample includes4096 rename and2048 each write/read/metadata operations. Quantiles use all observations within their own sample before pairing; no pooled percentile, removed warm-up or selected outlier.

| Mode | Statistic | Baseline ms, rounds0–3 | Candidate ms, rounds0–3 | Paired geometric change |
|---|---|---|---|---:|
| inc0 | rename median | [0.5302, 0.5327, 0.5387, 0.5410] | [0.5351, 0.5326, 0.5441, 0.5377] | +0.328% |
| inc0 | rename p95 | [1.8865, 1.7512, 1.6816, 1.5851] | [1.6195, 1.5803, 1.6013, 1.7371] | -5.177% |
| inc0 | rename p99 | [2.0477, 2.0250, 1.9970, 1.8742] | [1.7955, 1.7318, 1.7872, 1.9453] | -8.645% |
| inc0 | rename maximum | [2.4725, 15.1641, 18.1270, 2.1341] | [2.1589, 18.7401, 2.6927, 3.6675] | -27.554% |
| inc0 | write median | [2.0715, 2.0844, 2.0659, 2.1256] | [1.9060, 1.7098, 1.9304, 2.0479] | -9.209% |
| inc0 | write p95 | [3.3585, 3.4569, 3.3166, 3.4622] | [3.0206, 2.8356, 3.0914, 3.4458] | -9.045% |
| inc0 | write p99 | [3.6111, 3.7220, 3.5947, 3.7132] | [3.2768, 3.0461, 3.2588, 3.7121] | -9.424% |
| inc0 | write maximum | [14.4848, 6.9951, 17.6226, 5.2621] | [17.1266, 18.7646, 11.2679, 5.4678] | +20.485% |
| inc0 | read median | [1.4145, 1.3994, 1.3145, 1.4155] | [1.3506, 1.4016, 1.3780, 1.4297] | +0.314% |
| inc0 | read p95 | [2.0721, 2.0678, 2.0479, 2.0649] | [1.8980, 1.8296, 1.9094, 2.0855] | -6.533% |
| inc0 | read p99 | [2.3177, 2.2790, 2.1983, 2.8213] | [2.2177, 2.4076, 2.3646, 2.3819] | -2.117% |
| inc0 | read maximum | [5.5350, 17.0569, 3.1226, 5.1516] | [16.0463, 4.8691, 2.9980, 4.9182] | -6.676% |
| inc0 | metadata median | [0.9508, 0.9470, 0.9605, 0.9490] | [0.9448, 0.9360, 0.9603, 0.9487] | -0.462% |
| inc0 | metadata p95 | [2.3295, 2.2654, 2.2133, 2.0917] | [2.0823, 1.9910, 2.0342, 2.1494] | -7.190% |
| inc0 | metadata p99 | [2.5210, 2.5297, 2.4865, 2.3890] | [2.3439, 2.1211, 2.2706, 2.3992] | -8.047% |
| inc0 | metadata maximum | [3.9299, 4.0944, 5.7732, 3.2784] | [3.0419, 2.6897, 2.8713, 3.4828] | -28.005% |
| inc1 | rename median | [0.5314, 0.5386, 0.5515, 0.5427] | [0.5453, 0.5518, 0.5433, 0.5491] | +1.181% |
| inc1 | rename p95 | [1.4829, 1.6825, 1.5345, 1.5601] | [1.5414, 1.5701, 1.2794, 1.6833] | -3.348% |
| inc1 | rename p99 | [1.6964, 1.9053, 1.6957, 1.7329] | [1.7853, 1.7293, 1.7873, 1.9924] | +3.723% |
| inc1 | rename maximum | [1.9375, 79.5682, 15.4369, 2.0363] | [2.0574, 2.7122, 2.0152, 3.2696] | -70.487% |
| inc1 | write median | [1.8261, 2.0208, 1.7734, 1.8500] | [1.9070, 1.7470, 1.9291, 1.9635] | +1.041% |
| inc1 | write p95 | [2.8530, 3.3009, 2.9005, 3.0169] | [3.0019, 2.7722, 2.9528, 3.2083] | -1.101% |
| inc1 | write p99 | [3.1130, 3.5683, 3.1921, 3.2788] | [3.1631, 3.0627, 3.1466, 3.4565] | -2.430% |
| inc1 | write maximum | [21.6453, 14.4772, 15.6507, 14.7511] | [19.5648, 13.5690, 19.1941, 28.1654] | +18.679% |
| inc1 | read median | [1.3161, 1.3455, 1.3684, 1.3657] | [1.3527, 1.3771, 1.3327, 1.4108] | +1.425% |
| inc1 | read p95 | [1.8161, 2.0127, 1.8176, 1.8562] | [1.8878, 1.9124, 1.8917, 2.0229] | +2.878% |
| inc1 | read p99 | [2.0939, 2.5020, 2.0207, 2.1824] | [2.4517, 2.2673, 2.3679, 2.1663] | +5.403% |
| inc1 | read maximum | [2.5789, 79.5946, 2.5124, 4.5485] | [4.4053, 12.4134, 2.7850, 3.3166] | -31.880% |
| inc1 | metadata median | [0.9468, 0.9509, 0.9911, 0.9751] | [0.9603, 0.9873, 0.9520, 0.9754] | +0.295% |
| inc1 | metadata p95 | [1.9314, 2.1238, 1.9828, 2.0289] | [2.0077, 2.0074, 1.9980, 2.1460] | +1.159% |
| inc1 | metadata p99 | [2.1374, 2.3328, 2.1613, 2.2476] | [2.2908, 2.1983, 2.2777, 2.4736] | +4.034% |
| inc1 | metadata maximum | [2.7078, 3.6091, 8.4055, 2.9373] | [19.1370, 2.9678, 2.8921, 3.4412] | +23.716% |

Absolute scale: inc1 rename p99 spans1.696–1.905ms baseline versus1.729–1.992ms candidate; metadata p99 spans2.137–2.333ms versus2.198–2.474ms. Small absolute changes and mixed pairs still remain negative observations; they do not demonstrate seconds-scale stalls or an internal cause.

## Whole/phase distributions and every paired phase

Medians are descriptive per-variant medians. Each paired-change bracket lists all four rounds; the final value is their geometric ratio. Timers may nest/overlap: do not sum/subtract phases into exclusive contributors. Cargo build timers remain separate from normal pressure.

| Mode | Metric | Baseline median | Candidate median | All paired changes | Geometric change |
|---|---|---:|---:|---|---:|
| inc0 | convenience.checkpointCompilerQuiescePlusProduct | 0.716489 | 0.709173 | [-1.31%, +0.79%, -1.61%, -1.04%] | -0.797% |
| inc0 | convenience.restoreToCompilerReady | 0.246245 | 0.250919 | [+1.72%, +3.10%, +0.53%, +2.07%] | +1.852% |
| inc0 | fullTaskSeconds | 25.698732 | 25.026773 | [-3.57%, -4.35%, -0.22%, +0.61%] | -1.906% |
| inc0 | phase.cargo_setup | 0.073806 | 0.074393 | [-2.89%, +5.70%, +1.16%, -3.01%] | +0.176% |
| inc0 | phase.checkpoint | 0.375651 | 0.366328 | [-2.90%, -1.30%, +1.25%, -3.25%] | -1.566% |
| inc0 | phase.checkpoint_cli | 0.372534 | 0.363224 | [-2.91%, -1.35%, +1.27%, -3.25%] | -1.578% |
| inc0 | phase.checkpoint_readiness | 0.003105 | 0.003079 | [-1.04%, +4.44%, -1.40%, -2.52%] | -0.165% |
| inc0 | phase.clean_artifacts | 0.103301 | 0.102270 | [+1.47%, -1.97%, +0.94%, -6.30%] | -1.515% |
| inc0 | phase.clean_build | 1.678106 | 1.601878 | [-5.09%, -7.11%, +2.66%, +4.99%] | -1.268% |
| inc0 | phase.clean_execute | 0.071279 | 0.072112 | [+2.12%, +5.63%, +0.22%, -3.69%] | +1.013% |
| inc0 | phase.cleanup | 0.422309 | 0.418020 | [-1.48%, +5.65%, -8.25%, -2.59%] | -1.790% |
| inc0 | phase.edit | 0.099559 | 0.099213 | [+2.43%, -4.18%, -1.98%, +2.10%] | -0.448% |
| inc0 | phase.edit_artifacts | 0.105109 | 0.104855 | [-0.51%, +2.58%, -0.81%, -1.71%] | -0.127% |
| inc0 | phase.edit_build | 1.528597 | 1.438312 | [-7.81%, -8.12%, -1.59%, +1.24%] | -4.156% |
| inc0 | phase.edit_execute | 0.072367 | 0.071304 | [-2.31%, -0.33%, -2.30%, -0.06%] | -1.258% |
| inc0 | phase.fixture_verify | 0.361738 | 0.364739 | [+0.64%, -17.18%, +25.35%, +5.22%] | +2.397% |
| inc0 | phase.fork | 0.047669 | 0.042239 | [-5.51%, -25.79%, -15.35%, +12.69%] | -9.563% |
| inc0 | phase.import | 0.053920 | 0.048958 | [-9.18%, -25.80%, -4.26%, -2.24%] | -10.884% |
| inc0 | phase.init | 0.017866 | 0.016088 | [-10.26%, -26.65%, -9.06%, +3.03%] | -11.383% |
| inc0 | phase.noop_artifacts | 0.105705 | 0.103015 | [+4.23%, -5.65%, -3.58%, -1.51%] | -1.695% |
| inc0 | phase.noop_build | 0.300837 | 0.303085 | [-3.86%, +12.28%, +3.00%, -1.58%] | +2.279% |
| inc0 | phase.noop_execute | 0.072844 | 0.072675 | [-0.62%, -3.15%, -1.22%, +2.90%] | -0.547% |
| inc0 | phase.normal_pressure | 11.231569 | 10.479377 | [-7.83%, -10.14%, -3.08%, +0.51%] | -5.228% |
| inc0 | phase.pre_checkpoint_oracle | 2.883078 | 3.009115 | [-2.44%, +8.55%, +5.34%, +3.56%] | +3.675% |
| inc0 | phase.preflight | 0.086139 | 0.087427 | [+4.28%, -2.67%, +2.88%, -5.14%] | -0.236% |
| inc0 | phase.restore | 0.055286 | 0.055175 | [-0.92%, -3.03%, +1.80%, +2.67%] | +0.106% |
| inc0 | phase.restore_verify | 3.263028 | 3.322844 | [+7.24%, +0.48%, +3.92%, -0.41%] | +2.762% |
| inc0 | phase.restored_artifacts | 0.104257 | 0.103582 | [-4.18%, -2.04%, +0.64%, +2.08%] | -0.904% |
| inc0 | phase.restored_execute | 0.073894 | 0.072717 | [-1.59%, -5.59%, -0.84%, -0.10%] | -2.053% |
| inc0 | phase.restored_rebuild | 0.328021 | 0.316128 | [-4.14%, +6.78%, -7.26%, -6.15%] | -2.849% |
| inc0 | phase.restored_rebuild_artifacts | 0.105017 | 0.106591 | [+0.28%, +2.72%, -0.63%, +4.51%] | +1.702% |
| inc0 | phase.restored_rebuild_execute | 0.072406 | 0.072595 | [+0.32%, -0.53%, -3.38%, +0.20%] | -0.861% |
| inc0 | phase.retained_input_verify | 1.214261 | 1.221235 | [+5.34%, +4.10%, -2.72%, -4.87%] | +0.370% |
| inc0 | phase.space | 0.103328 | 0.101914 | [-3.29%, -0.55%, +0.96%, -2.78%] | -1.428% |
| inc0 | phase.target_probe | 0.100724 | 0.100258 | [-0.06%, +2.46%, -3.51%, -1.09%] | -0.572% |
| inc0 | phase.toolchain_verify | 0.085566 | 0.085650 | [+1.09%, -5.49%, +3.30%, -0.89%] | -0.552% |
| inc0 | phase.transport_stop_before_checkpoint | 0.322398 | 0.325776 | [+0.56%, +2.92%, -4.17%, +2.17%] | +0.330% |
| inc0 | phase.transport_stop_final_cleanup | 0.311995 | 0.307520 | [-1.79%, +8.35%, -9.72%, -3.11%] | -1.776% |
| inc0 | runtimeSetupSeconds | 19.242020 | 16.253405 | [-16.83%, -14.80%, -15.49%, +0.61%] | -11.900% |
| inc0 | wholeFilesystemUsedBytes | 1,069,598,720 | 1,069,711,360 | [+0.00%, +0.00%, +0.02%, +0.01%] | +0.009% |
| inc0 | wholeSamplerSeconds | 25.898611 | 25.229863 | [-3.64%, -4.31%, -0.22%, +0.60%] | -1.913% |
| inc1 | convenience.checkpointCompilerQuiescePlusProduct | 0.760200 | 0.767566 | [+3.49%, -2.48%, +2.46%, -2.71%] | +0.149% |
| inc1 | convenience.restoreToCompilerReady | 0.246414 | 0.250034 | [+1.69%, -0.81%, +0.03%, +3.48%] | +1.084% |
| inc1 | fullTaskSeconds | 26.682289 | 26.550239 | [+2.59%, -1.76%, -0.15%, -1.49%] | -0.215% |
| inc1 | phase.cargo_setup | 0.073278 | 0.073328 | [-4.08%, -2.74%, +0.71%, +4.21%] | -0.527% |
| inc1 | phase.checkpoint | 0.421629 | 0.420078 | [+3.52%, -2.64%, +1.08%, -2.75%] | -0.233% |
| inc1 | phase.checkpoint_cli | 0.418631 | 0.416995 | [+3.51%, -2.66%, +1.03%, -2.76%] | -0.253% |
| inc1 | phase.checkpoint_readiness | 0.003036 | 0.003086 | [+4.26%, +0.08%, +7.83%, -1.64%] | +2.567% |
| inc1 | phase.clean_artifacts | 0.103340 | 0.105501 | [+4.25%, -0.99%, +4.80%, -2.67%] | +1.294% |
| inc1 | phase.clean_build | 2.172941 | 2.192751 | [+2.63%, +0.37%, -0.08%, +0.62%] | +0.880% |
| inc1 | phase.clean_execute | 0.073329 | 0.073798 | [+2.60%, -3.13%, +2.05%, +2.42%] | +0.958% |
| inc1 | phase.cleanup | 0.445907 | 0.436566 | [-4.32%, -0.57%, -2.59%, -1.91%] | -2.357% |
| inc1 | phase.edit | 0.098876 | 0.100839 | [+2.19%, +3.26%, +1.79%, -3.65%] | +0.860% |
| inc1 | phase.edit_artifacts | 0.104757 | 0.104372 | [+1.95%, -1.26%, -0.98%, -0.88%] | -0.300% |
| inc1 | phase.edit_build | 1.821121 | 1.823480 | [+1.63%, -3.64%, +2.85%, -4.18%] | -0.885% |
| inc1 | phase.edit_execute | 0.070972 | 0.071379 | [-1.36%, -1.07%, -2.57%, +10.49%] | +1.241% |
| inc1 | phase.fixture_verify | 0.352821 | 0.352025 | [+3.66%, -2.37%, +4.35%, -4.06%] | +0.329% |
| inc1 | phase.fork | 0.042055 | 0.042223 | [+6.45%, -2.82%, -1.52%, +1.59%] | +0.861% |
| inc1 | phase.import | 0.048229 | 0.047496 | [+6.17%, -4.62%, +1.72%, -3.45%] | -0.137% |
| inc1 | phase.init | 0.015726 | 0.015472 | [+2.91%, -8.15%, +13.82%, -10.49%] | -0.935% |
| inc1 | phase.noop_artifacts | 0.103328 | 0.102918 | [-0.42%, -2.03%, +1.28%, -0.77%] | -0.493% |
| inc1 | phase.noop_build | 0.330695 | 0.301066 | [+3.48%, -14.69%, -7.42%, -1.78%] | -5.344% |
| inc1 | phase.noop_execute | 0.071562 | 0.072260 | [+3.19%, -2.22%, +4.64%, +0.13%] | +1.402% |
| inc1 | phase.normal_pressure | 10.551680 | 10.425788 | [+4.07%, -2.72%, -0.16%, -2.71%] | -0.418% |
| inc1 | phase.pre_checkpoint_oracle | 3.338596 | 3.262562 | [-0.28%, -4.24%, -7.06%, +4.08%] | -1.966% |
| inc1 | phase.preflight | 0.085115 | 0.086989 | [+3.07%, +5.75%, -8.37%, +4.20%] | +1.004% |
| inc1 | phase.restore | 0.057724 | 0.059045 | [+5.97%, -2.86%, +1.82%, -5.56%] | -0.254% |
| inc1 | phase.restore_verify | 3.589281 | 3.652210 | [-0.34%, +3.01%, +2.36%, -3.14%] | +0.442% |
| inc1 | phase.restored_artifacts | 0.105924 | 0.103541 | [-2.53%, -2.15%, -4.23%, +0.68%] | -2.073% |
| inc1 | phase.restored_execute | 0.072076 | 0.072676 | [+1.26%, +0.45%, -1.86%, +2.57%] | +0.592% |
| inc1 | phase.restored_rebuild | 0.309755 | 0.339234 | [+23.10%, +3.59%, +12.74%, -5.44%] | +7.977% |
| inc1 | phase.restored_rebuild_artifacts | 0.108326 | 0.105321 | [-1.62%, -4.11%, +2.89%, -6.10%] | -2.292% |
| inc1 | phase.restored_rebuild_execute | 0.071773 | 0.073767 | [+5.44%, +3.22%, +2.55%, -0.36%] | +2.691% |
| inc1 | phase.retained_input_verify | 1.197754 | 1.240489 | [+6.25%, -0.69%, +3.48%, +0.81%] | +2.432% |
| inc1 | phase.space | 0.098689 | 0.100851 | [+3.68%, +3.09%, +1.31%, +2.49%] | +2.641% |
| inc1 | phase.target_probe | 0.100221 | 0.102660 | [+3.00%, +2.18%, -0.76%, +0.80%] | +1.294% |
| inc1 | phase.toolchain_verify | 0.085274 | 0.086221 | [+1.49%, +1.44%, +0.21%, +0.77%] | +0.977% |
| inc1 | phase.transport_stop_before_checkpoint | 0.322364 | 0.328632 | [+3.95%, -1.80%, +4.40%, -2.41%] | +0.986% |
| inc1 | phase.transport_stop_final_cleanup | 0.333540 | 0.321697 | [-7.38%, -1.20%, -3.18%, -3.03%] | -3.725% |
| inc1 | runtimeSetupSeconds | 16.402756 | 16.327914 | [-1.73%, +0.09%, +0.00%, -0.49%] | -0.535% |
| inc1 | wholeFilesystemUsedBytes | 1,080,207,360 | 1,080,131,584 | [+0.00%, -0.02%, -0.00%, +0.01%] | -0.004% |
| inc1 | wholeSamplerSeconds | 26.886941 | 26.757555 | [+2.59%, -1.74%, -0.15%, -1.47%] | -0.208% |

The pressure phase spans roughly10.03–11.32s including tree setup, witness validation and serialization. Its paired change is−5.228% inc0 /−0.418% inc1, whereas individual operation timers exclude that setup/final work. Those scopes explain why they need not move together, not why any source change caused a specific result.

## Order strata (only two pairs each)

| Mode | Metric | Baseline first, geometric change | Candidate first, geometric change |
|---|---|---:|---:|
| inc0 | wholeSamplerSeconds | -1.943% | -1.882% |
| inc0 | phase.normal_pressure | -5.489% | -4.965% |
| inc0 | pressure.rename.medianSeconds | +0.974% | -0.313% |
| inc0 | pressure.rename.p99Seconds | -11.417% | -5.787% |
| inc0 | pressure.write.p99Seconds | -9.301% | -9.547% |
| inc0 | pressure.metadata.p99Seconds | -7.857% | -8.236% |
| inc0 | pressure.read.p99Seconds | +1.450% | -5.559% |
| inc1 | wholeSamplerSeconds | -1.607% | +1.211% |
| inc1 | phase.normal_pressure | -2.718% | +1.936% |
| inc1 | pressure.rename.medianSeconds | +1.819% | +0.548% |
| inc1 | pressure.rename.p99Seconds | +2.151% | +5.320% |
| inc1 | pressure.write.p99Seconds | -4.878% | +0.082% |
| inc1 | pressure.metadata.p99Seconds | +1.838% | +6.278% |
| inc1 | pressure.read.p99Seconds | -5.156% | +17.137% |

## Shared-clock operation-wrapper evidence

These are **Python operation-wrapper wall intervals, not individual kernel/FUSE syscalls**. `write_bytes` includes open/truncate/write/close; `read_bytes` includes open/read/close; metadata combines stat/readlink/assertions. GIL scheduling, host scheduling, server queues and storage may all contribute. Interval overlap is descriptive concurrency evidence, never causal attribution to locks, directory lookup or fsync.

All163,840 intervals have exact shared CLOCK_MONOTONIC origin strings, safe integer relative timestamps, valid worker bounds,1024 completed iterations/worker and exact five-operation order. Duration arrays equal end−start exactly; no intra-worker overlap, missing event or invalid witness survived the gates. Both worker lifetimes overlap in every sample.

| Mode | Round | Variant | Worker-lifetime overlap(s) | Simultaneously timed wrapper overlap(s) | Positive interval intersections |
|---|---:|---|---:|---:|---:|
| inc0 | 0 | sprig-baseline | 6.248832 | 6.184336 | 10238 |
| inc0 | 0 | sprig-candidate | 5.784121 | 5.717893 | 10239 |
| inc0 | 1 | sprig-candidate | 5.733397 | 5.668020 | 10229 |
| inc0 | 1 | sprig-baseline | 6.224867 | 6.159535 | 10238 |
| inc0 | 2 | sprig-baseline | 6.008935 | 5.944102 | 10230 |
| inc0 | 2 | sprig-candidate | 5.893505 | 5.825823 | 10236 |
| inc0 | 3 | sprig-candidate | 6.170160 | 6.104500 | 10236 |
| inc0 | 3 | sprig-baseline | 6.086769 | 6.022771 | 10238 |
| inc1 | 0 | sprig-candidate | 5.746515 | 5.680183 | 10224 |
| inc1 | 0 | sprig-baseline | 5.578014 | 5.513078 | 10238 |
| inc1 | 1 | sprig-baseline | 6.046942 | 5.984048 | 10238 |
| inc1 | 1 | sprig-candidate | 5.826134 | 5.759380 | 10237 |
| inc1 | 2 | sprig-candidate | 5.686107 | 5.620186 | 10229 |
| inc1 | 2 | sprig-baseline | 5.832231 | 5.766970 | 10228 |
| inc1 | 3 | sprig-baseline | 5.883093 | 5.818602 | 10222 |
| inc1 | 3 | sprig-candidate | 6.070266 | 6.003510 | 10235 |

The post-measurement interval audit sums intersections of half-open intervals from disjoint per-worker streams; intersection duration is a union, not a double-counted sum. Timed wrapper overlap spans5.513–6.184s baseline and5.620–6.104s candidate. It does not imply every operation overlaps or establish steady state.

Four fixed256-iteration descriptive windows per worker are retained in `interval-audit.json` with all per-class quantiles and cross-worker class intersections. They are not extra independent trials, a stationarity test, a new acceptance gate or a reason to discard early/late work. Both products use identical symmetric observation overhead.

## Correctness, source identity and resource accounting

- All16 complete checkpoint/restored oracles pass before restored execution/build:2360 entries in inc0 and2554 in inc1. Exact paths/types/content, modes, nanosecond metadata, symlinks and internal hardlinks remain authoritative in standalone Python JSON, not rounded JS copies.2048 unrelated files,16 moving payloads, mutable bytes, hardlink/symlink witnesses and raw observations are retained in the checkpoint tree.
- Clean/edit builds retain17Compiling checks; no-op/restored builds retain17Fresh checks; program269→3400, build-script1→2, unchanged source/main and all acknowledged history checks pass.64 generation-scoped compiler sessions finish naturally; cleanup leaves zero mounts/containers, restores runtime and normally detaches loops. No forced teardown, fault/quota/mmap test or retry.
- All4364 collector files (377,721,310B, excluding the collection manifest itself) and4298 unique declared archive files match exact sizes/SHA256.40 source/test hashes per variant match git objects;21 benchmark script hashes matchc42b2a2. Distinct recorded binary hashes match manifests/samples; executable bytes were not archived.
- Independent exactc42b2a2 helper analysis accepted16samples/zeroerrors and reproduced every server comparison and identity. Separate post-hoc interval description does not modify the predeclared primary summary or raw samples.
- Existing Ubuntu24 runner, Cargo jobs2, fresh symmetric4GiB images,128MiB pressure reserve,40min absolute admission deadline and45min job cap. No enlargement, extra worker, billing/security/permission change, parallel measured job or silently changed helper. One exact dispatch completed18m16s.
- Pressure helper SHA256`58e5171ba44661a00065297155025a0c75839892cb5c21c770d22e84f4e0b501`; shared compiler image`sha256:c54fd7e305dee70f3658739051999e420be7bd11b565fb83a995d58991a0035d`. Both product trace variables were off. Source standardCI40301987667 was green before launch, but that is not performance evidence.

## Published report and current raw evidence

The full raw source is the public [GitHub Actions artifact 12643565991](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40304840409/artifacts/12643565991)
for [run 40304840409](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40304840409) (61,937,244 compressed bytes).
Artifact identity/head and non-expired status were checked on 2026-10-26 before
this report-only publication. GitHub artifact retention is finite; the current
expiry is `2027-01-24T10:06:54Z`. Access may require GitHub sign-in.

This commit publishes the report plus [every original artifact file SHA256](data/stress-20261026/evidence-manifests/40304840409/artifact-files.json),
[provenance audit](data/stress-20261026/evidence-manifests/40304840409/provenance-audit.json), and
[prepared lossless archive identity](data/stress-20261026/evidence-manifests/40304840409/prepared-archive.json).
The lossless archive has been fully byte-verified and retained, but its binary
blob is **not published here yet**. Durable archive publication is pending;
no nonexistent archive download link or permanent-availability claim is made.
The [complete prepared member manifest](data/stress-20261026/evidence-manifests/40304840409/prepared-archive-files.json)
preserves raw failures/negatives as well as exact-version helpers and derived
audits. No raw samples were trimmed to make this small report batch.

## Every slower geometric-mean metric

| Mode | Metric | Paired geometric change |
|---|---|---:|
| inc0 | convenience.restoreToCompilerReady | +1.852% |
| inc0 | phase.cargo_setup | +0.176% |
| inc0 | phase.clean_execute | +1.013% |
| inc0 | phase.fixture_verify | +2.397% |
| inc0 | phase.noop_build | +2.279% |
| inc0 | phase.pre_checkpoint_oracle | +3.675% |
| inc0 | phase.restore | +0.106% |
| inc0 | phase.restore_verify | +2.762% |
| inc0 | phase.restored_rebuild_artifacts | +1.702% |
| inc0 | phase.retained_input_verify | +0.370% |
| inc0 | phase.transport_stop_before_checkpoint | +0.330% |
| inc0 | pressure.read.medianSeconds | +0.314% |
| inc0 | pressure.rename.medianSeconds | +0.328% |
| inc0 | pressure.write.maximumSeconds | +20.485% |
| inc0 | wholeFilesystemUsedBytes | +0.009% |
| inc1 | convenience.checkpointCompilerQuiescePlusProduct | +0.149% |
| inc1 | convenience.restoreToCompilerReady | +1.084% |
| inc1 | phase.checkpoint_readiness | +2.567% |
| inc1 | phase.clean_artifacts | +1.294% |
| inc1 | phase.clean_build | +0.880% |
| inc1 | phase.clean_execute | +0.958% |
| inc1 | phase.edit | +0.860% |
| inc1 | phase.edit_execute | +1.241% |
| inc1 | phase.fixture_verify | +0.329% |
| inc1 | phase.fork | +0.861% |
| inc1 | phase.noop_execute | +1.402% |
| inc1 | phase.preflight | +1.004% |
| inc1 | phase.restore_verify | +0.442% |
| inc1 | phase.restored_execute | +0.592% |
| inc1 | phase.restored_rebuild | +7.977% |
| inc1 | phase.restored_rebuild_execute | +2.691% |
| inc1 | phase.retained_input_verify | +2.432% |
| inc1 | phase.space | +2.641% |
| inc1 | phase.target_probe | +1.294% |
| inc1 | phase.toolchain_verify | +0.977% |
| inc1 | phase.transport_stop_before_checkpoint | +0.986% |
| inc1 | pressure.metadata.maximumSeconds | +23.716% |
| inc1 | pressure.metadata.medianSeconds | +0.295% |
| inc1 | pressure.metadata.p95Seconds | +1.159% |
| inc1 | pressure.metadata.p99Seconds | +4.034% |
| inc1 | pressure.read.medianSeconds | +1.425% |
| inc1 | pressure.read.p95Seconds | +2.878% |
| inc1 | pressure.read.p99Seconds | +5.403% |
| inc1 | pressure.rename.medianSeconds | +1.181% |
| inc1 | pressure.rename.p99Seconds | +3.723% |
| inc1 | pressure.write.maximumSeconds | +18.679% |
| inc1 | pressure.write.medianSeconds | +1.041% |

## Decision

Do not promote or market dfee as a broad mounted tail/whole-Cargo improvement. Inc0 has modest improvements; inc1 whole time is essentially unchanged and several tail/median observations regress. Keep source diagnostics/debug fallback costs and this release result separate. No causal rollback or selective rerun follows automatically from four pairs.

Native inventory-only confirmation is an independent experiment with different pins/workload. Its eligible64KiB screen cannot explain these mounted pressure results, and the failed small-admission unique10000 gate remains binding forf481. No pooling between ordinary,128-cycle,1024-cycle or native cache series.
