# Owned lifecycle optimization: five-pair same-runner results

[Run 40158411448](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40158411448), completed 25 October 2026. Baseline `bc4165f5f55ceac63e18716ac96b19d9e4675afd`; candidate `a2b76e4c3ecdccdeeca24a669df4a82d1a4792f3`; benchmark `f0dcedfde47f301dc138c20e855a2e790489d748`. Owned writable backend, default auto compression, same runner and compiler, separate verified build targets.

**70/70 records and 3,000 complete historical readbacks passed.** Seven cases × five adjacent AB/BA pairs. All raw samples, including slower operations and larger footprints, are retained.

## Finding

Checkpoint time improves consistently across the three history cases: median within-pair candidate/baseline ratios are approximately 0.936, 0.933 and 0.938 (about 6.2–6.7% lower). All 15 checkpoint pairs are faster, with ratios from 0.918 to 0.944. Restore-to-usable-workspace has a smaller improvement, but complete restore/read/normal-cleanup totals and warm fork/read have no consistent substantial improvement. This is a narrow lifecycle improvement, not a solution to all measured weaknesses or a new LayerFS victory.

Physical storage is exactly equal within every pair for the four large nonhistory cases. History storage varies; independently initialized identities and metadata-page sharing are uncontrolled potential contributors, not a cause established by this run. These measurements establish neither a general storage improvement nor a proven candidate-induced encoding regression. Independent identity/codec diagnostics are not substituted for these actual measurements.

## Interpretation and accounting

- This is within-Sprig same-runner A/B, not a fresh comparator series. Production durability, whole operation timing and all retained generations are unchanged. Different earlier runner results are not used as causal evidence.
- Tables show individual baseline/candidate medians and separately the median of five paired ratios. Those are different statistics: a ratio of individual medians can disagree with the median paired ratio, especially for bimodal metadata space. Do not convert one into the other. Every pair and its ratio is in the linked summary.
- Three original workspaces are live at the primary physical snapshot. The second physical snapshot follows 100 historical restores/readbacks and normal unmounts, before final cleanup. Neither sampling point excludes the retained old journals/history.
- Whole Btrfs Used minus the fresh empty-FS baseline is primary; component stat allocation is non-additive diagnostics after all timings. No GC, pruning, cache dropping or cold-cache claim.
- Five pairs support a workload-specific direction, not a universal or formal statistical guarantee. Native/projection have only the separately preserved smoke results for this candidate; their full runs were deferred.

[Measurement contract](feasibility/LIFECYCLE-AB-CONTRACT.md) · [Original smoke](LIFECYCLE-SMOKE-RESULTS.md) · [Complete original full artifact](data/lifecycle-20261025/writable-full/writable-40158411448-full-artifact.tar.gz) · [Every pair and summary](data/lifecycle-20261025/writable-full/summary.json)

## Preparation and warm task

| Case / metric | Baseline median | Candidate median | Median paired B/A | Paired ratio range |
|---|---:|---:|---:|---:|
| identical / preparation | 495.443 ms | 495.872 ms | 1.0085 | 0.9867–1.0113 |
| identical / warm fork/read | 283.131 ms | 289.948 ms | 1.0224 | 0.9867–1.0368 |
| unique / preparation | 721.877 ms | 720.448 ms | 0.9980 | 0.9656–1.0286 |
| unique / warm fork/read | 332.671 ms | 319.867 ms | 0.9961 | 0.9436–1.0041 |
| mixed / preparation | 675.930 ms | 669.380 ms | 0.9965 | 0.9710–1.0118 |
| mixed / warm fork/read | 325.567 ms | 321.524 ms | 0.9885 | 0.9247–1.0430 |
| insert / preparation | 537.882 ms | 536.133 ms | 1.0095 | 0.9686–1.0494 |
| insert / warm fork/read | 305.801 ms | 299.605 ms | 1.0065 | 0.9574–1.0801 |
| history-distributed / preparation | 280.363 ms | 279.930 ms | 0.9737 | 0.9512–1.0922 |
| history-distributed / warm fork/read | 177.330 ms | 174.584 ms | 0.9846 | 0.9397–1.0386 |
| history-hotset / preparation | 289.208 ms | 273.974 ms | 0.9416 | 0.9166–1.0202 |
| history-hotset / warm fork/read | 170.690 ms | 172.770 ms | 0.9962 | 0.9889–1.0664 |
| history-recurring / preparation | 272.183 ms | 273.642 ms | 1.0054 | 0.9844–1.0379 |
| history-recurring / warm fork/read | 172.373 ms | 175.089 ms | 1.0047 | 0.9198–1.0453 |

## 100-operation history tasks

| Case / metric | Baseline median | Candidate median | Median paired B/A | Paired ratio range |
|---|---:|---:|---:|---:|
| history-distributed / write+checkpoint | 8.441 s | 7.935 s | 0.9400 | 0.9385–0.9479 |
| history-distributed / checkpoint | 7.773 s | 7.275 s | 0.9359 | 0.9332–0.9444 |
| history-distributed / restore to usable | 3.032 s | 2.942 s | 0.9667 | 0.9630–0.9823 |
| history-distributed / restore+read+cleanup | 17.652 s | 17.557 s | 0.9955 | 0.9874–1.0045 |
| history-hotset / write+checkpoint | 8.634 s | 8.038 s | 0.9380 | 0.9186–0.9431 |
| history-hotset / checkpoint | 7.779 s | 7.224 s | 0.9332 | 0.9183–0.9389 |
| history-hotset / restore to usable | 3.028 s | 2.863 s | 0.9593 | 0.9183–1.0056 |
| history-hotset / restore+read+cleanup | 17.602 s | 17.316 s | 0.9923 | 0.9740–1.0066 |
| history-recurring / write+checkpoint | 8.189 s | 7.766 s | 0.9444 | 0.9375–0.9484 |
| history-recurring / checkpoint | 7.318 s | 6.885 s | 0.9381 | 0.9293–0.9421 |
| history-recurring / restore to usable | 3.009 s | 2.920 s | 0.9719 | 0.9574–0.9904 |
| history-recurring / restore+read+cleanup | 17.488 s | 17.455 s | 1.0032 | 0.9934–1.0052 |

## Physical storage

| Case / metric | Baseline median | Candidate median | Median paired B/A | Paired ratio range |
|---|---:|---:|---:|---:|
| identical / active snapshot | 1.082 MiB | 1.082 MiB | 1.0000 | 1.0000–1.0000 |
| identical / post-history snapshot | 1.094 MiB | 1.094 MiB | 1.0000 | 1.0000–1.0000 |
| unique / active snapshot | 100.445 MiB | 100.445 MiB | 1.0000 | 1.0000–1.0000 |
| unique / post-history snapshot | 100.457 MiB | 100.457 MiB | 1.0000 | 1.0000–1.0000 |
| mixed / active snapshot | 75.352 MiB | 75.352 MiB | 1.0000 | 1.0000–1.0000 |
| mixed / post-history snapshot | 75.363 MiB | 75.363 MiB | 1.0000 | 1.0000–1.0000 |
| insert / active snapshot | 9.527 MiB | 9.527 MiB | 1.0000 | 1.0000–1.0000 |
| insert / post-history snapshot | 9.539 MiB | 9.539 MiB | 1.0000 | 1.0000–1.0000 |
| history-distributed / active snapshot | 5.273 MiB | 6.008 MiB | 0.9923 | 0.9439–1.2186 |
| history-distributed / post-history snapshot | 7.180 MiB | 7.906 MiB | 0.9849 | 0.9527–1.1584 |
| history-hotset / active snapshot | 8.953 MiB | 9.727 MiB | 1.0121 | 0.9882–1.1406 |
| history-hotset / post-history snapshot | 10.934 MiB | 11.758 MiB | 1.0060 | 0.9864–1.1198 |
| history-recurring / active snapshot | 8.418 MiB | 8.410 MiB | 1.0005 | 0.9954–1.0028 |
| history-recurring / post-history snapshot | 10.379 MiB | 10.383 MiB | 0.9996 | 0.9947–1.0045 |

[Checksums and provenance](data/lifecycle-20261025/writable-full/manifest.json). All original artifact files are preserved unchanged.
