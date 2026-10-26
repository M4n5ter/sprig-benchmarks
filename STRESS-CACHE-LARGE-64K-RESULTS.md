# Native cache eligible64KiB inventory-path screen

**The inventory prerequisite shows a consistent benefit on its actual eligible
path: main→inventory median restore−39.570%, whole sampler−21.361%.**
All3 restore pairs improve39.47–40.08%; all3 whole pairs improve21.36–21.56%.
This is a promising small-N screen, not reverse-order confirmation or promotion.
The failed unique10000 small-admission gate remains binding and is not waived.

[Run40302159760](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40302159760)
at exact benchmark `93ce3366204a34eeefdd95ebc92aad1b2d976468` completed **success**
in7m1s. All3 native canaries,9 Latin samples, strict summary and artifact upload
passed. Independent exact-source reanalysis reproduced all server metrics and
verified every standalone raw report, archive hash and full-tree oracle.

## Fixed source pins and genuinely eligible workload

| Label | Immutable source |
|---|---|
| main | `b300693e01c652c1a9631c61b7a439892d8f75cd` |
| inventory | `c392d45079314cdcf9813371ec9120d78be7bcd6` |
| admission | `f481aaba987d960bf119e95b68f5b38da56e1581` |

Cell `cache-large-64k-1024`:1024 independently written unique64KiB files,
64MiB logical, width-one directory, no aliases, a no-op checkpoint plus one
64-byte edit and both historical restores. Conservative retained charge448MiB.
Unlike earlier1/4KiB controls, every original file reaches the unchanged≥64KiB
eligibility threshold; main→inventory therefore exercises the inventory path.
Admission adds no intended small-file reuse here and serves as a separate edge.

Fresh product store/cache per trial; no cold OS-page-cache claim. Orders are
ABC/BCA/CAB, one sample per pin/round/position. No pooling with small-file cells,
ordinary Cargo or concurrency profiles. All durability/publication barriers remain.

## Full correctness, provenance and unchanged resource limits

- All3canaries+9screen samples retained:144 exact full-tree checks and30
  historical readbacks, content/path/type/mode/exact-ns/symlink/hardlink topology,
  source/retained-view invariance, acknowledged histories and normal cleanup.
- All217 original artifact files22,776,206B hashed;120 product source/test-file
  hashes and7 helper hashes match exact git objects. Binary hashes match all
  manifests/samples; executable bytes were not archived. Original server summary
  exactly matches the independent audit; no post-hoc schema change or rerun.
- Existing Ubuntu runner,45min job limit, original40min admission clock, one
  ≤1200sec measurement deadline shared across canaries/screen, fresh2GiB images,
 256MiB reserve and≤1GiB conservative retained bound. No faults, forced cleanup,
  image enlargement, discarded samples, retry or parallel measurement.
- Physical metrics are whole-filesystem Btrfs Used including cache/retained
  trees/history/logs, not logical bytes or empty-image-subtracted estimates.
  Explicitly omitted metadata timing stays `notMeasured=null`, not zero.

## All nine raw observations

| Round/position | Pin | Whole sampler(s) | Restore aggregate(s) | Active Used(MiB) | Post-history Used(MiB) |
|---|---|---:|---:|---:|---:|
| 1/1 | main | 11.437069 | 6.100822 | 133.3828 | 202.1680 |
| 1/2 | inventory | 8.994031 | 3.693047 | 133.3828 | 202.1055 |
| 1/3 | admission | 9.099757 | 3.746257 | 133.3516 | 202.1680 |
| 2/1 | inventory | 8.935734 | 3.673648 | 133.3516 | 202.1680 |
| 2/2 | admission | 9.037944 | 3.722018 | 133.3203 | 202.0430 |
| 2/3 | main | 11.392252 | 6.130860 | 133.4141 | 202.1680 |
| 3/1 | admission | 8.925041 | 3.691108 | 133.3516 | 202.1055 |
| 3/2 | main | 11.289968 | 6.067595 | 133.4141 | 202.1367 |
| 3/3 | inventory | 8.878458 | 3.666677 | 133.3828 | 202.1992 |

## Every paired phase and whole-task metric

Percent is candidate/baseline−1; lower is better. Median/geom use3 within-round
paired ratios. Overlapping phases must not be summed/subtracted into exclusive
costs. Whole sampler includes preparation, oracle verification, accounting, normal
cleanup and serialization, excluding external fixture/image setup.

### main-to-inventory

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | +0.000% | -0.047% | -0.023% | -0.023% | -0.023% |
| checkpoint_seconds | +0.352% | -0.075% | +0.631% | +0.352% | +0.302% |
| first_fork_seconds | -1.218% | +2.787% | -0.889% | -0.889% | +0.210% |
| first_read_seconds | +0.461% | -6.098% | +1.387% | +0.461% | -1.474% |
| import_seconds | -0.685% | +1.365% | +1.156% | +1.156% | +0.608% |
| init_seconds | -5.755% | -2.806% | +2.484% | -2.806% | -2.084% |
| postHistoryWholeFilesystemBytes | -0.031% | +0.000% | +0.031% | +0.000% | -0.000% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -3.051% | +1.003% | -2.831% | -2.831% | -1.644% |
| restore_seconds | -39.466% | -40.079% | -39.570% | -39.570% | -39.706% |
| total_import_fork_read_seconds | -0.768% | +1.193% | +0.501% | +0.501% | +0.305% |
| warm_fork_seconds | -1.090% | +0.275% | -1.092% | -1.090% | -0.638% |
| warm_read_seconds | +7.274% | -8.073% | -4.001% | -4.001% | -1.810% |
| warm_total_seconds | +0.800% | -1.775% | -1.812% | -1.775% | -0.937% |
| wholeSampleSeconds | -21.361% | -21.563% | -21.360% | -21.361% | -21.428% |
| write_seconds | +4.319% | -6.211% | -5.000% | -5.000% | -2.408% |

### inventory-to-admission

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | -0.023% | -0.023% | -0.023% | -0.023% | -0.023% |
| checkpoint_seconds | -0.628% | -0.407% | +1.118% | -0.407% | +0.025% |
| first_fork_seconds | +1.346% | -2.543% | +1.261% | +1.261% | +0.005% |
| first_read_seconds | -2.222% | +6.410% | +0.484% | +0.484% | +1.494% |
| import_seconds | +3.295% | +4.019% | -1.315% | +3.295% | +1.972% |
| init_seconds | +14.906% | +14.447% | +0.912% | +14.447% | +9.891% |
| postHistoryWholeFilesystemBytes | +0.031% | -0.062% | -0.046% | -0.046% | -0.026% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -1.482% | +2.538% | +3.841% | +2.538% | +1.607% |
| restore_seconds | +1.441% | +1.317% | +0.666% | +1.317% | +1.141% |
| total_import_fork_read_seconds | +2.177% | +2.009% | -0.324% | +2.009% | +1.281% |
| warm_fork_seconds | -0.825% | -0.795% | +0.848% | -0.795% | -0.261% |
| warm_read_seconds | +0.456% | +3.236% | +3.847% | +3.236% | +2.502% |
| warm_total_seconds | -0.517% | +0.131% | +1.573% | +0.131% | +0.392% |
| wholeSampleSeconds | +1.176% | +1.144% | +0.525% | +1.144% | +0.948% |
| write_seconds | -0.683% | -0.034% | -3.990% | -0.683% | -1.584% |

### main-to-admission

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | -0.023% | -0.070% | -0.047% | -0.047% | -0.047% |
| checkpoint_seconds | -0.278% | -0.482% | +1.756% | -0.278% | +0.327% |
| first_fork_seconds | +0.112% | +0.173% | +0.362% | +0.173% | +0.215% |
| first_read_seconds | -1.772% | -0.079% | +1.878% | -0.079% | -0.002% |
| import_seconds | +2.587% | +5.439% | -0.174% | +2.587% | +2.592% |
| init_seconds | +8.293% | +11.235% | +3.419% | +8.293% | +7.601% |
| postHistoryWholeFilesystemBytes | +0.000% | -0.062% | -0.015% | -0.015% | -0.026% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -4.488% | +3.567% | +0.901% | +0.901% | -0.063% |
| restore_seconds | -38.594% | -39.290% | -39.167% | -39.167% | -39.018% |
| total_import_fork_read_seconds | +1.392% | +3.225% | +0.176% | +1.392% | +1.590% |
| warm_fork_seconds | -1.907% | -0.522% | -0.254% | -0.522% | -0.897% |
| warm_read_seconds | +7.762% | -5.099% | -0.308% | -0.308% | +0.647% |
| warm_total_seconds | +0.278% | -1.646% | -0.267% | -0.267% | -0.548% |
| wholeSampleSeconds | -20.436% | -20.666% | -20.947% | -20.666% | -20.683% |
| write_seconds | +3.606% | -6.242% | -8.791% | -6.242% | -3.954% |

## Negatives, interpretation and decision

Inventory→admission is **slower on every pair** here: restore+1.441/+1.317/
+0.666% (median+1.317%), whole+1.176/+1.144/+0.525% (median+1.144%). These
are within the5% screening threshold, not a new admission benefit. The combined
main→admission gain (restore median−39.167%, whole−20.666%) is predominantly
consistent with the isolated inventory prerequisite; do not attribute it to small
admission. Whole Used is essentially unchanged, so do not claim a space win.

This result makes inventory an eligible **screening candidate**, not a promoted
optimization. The preceding unique10000 inventory→admission median restore
+14.525% failure is preserved; a large-file gain cannot cancel that failed
small-file admission control. Review inventory and admission separately.

Only3 same-host observations per pin,2 dependent restores per sample. No useful
whole-run or per-sample p95/p99, statistical significance or independent-host
generalization is claimed. Reverse-Latin confirmation and remaining required
controls remain separate reviewed decisions; no automatic additional dispatch.

## Published report and current raw evidence

The full raw source is the public [GitHub Actions artifact 12641212210](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40302159760/artifacts/12641212210)
for [run 40302159760](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40302159760) (4,883,994 compressed bytes).
Artifact identity/head and non-expired status were checked on 2026-10-26 before
this report-only publication. GitHub artifact retention is finite; the current
expiry is `2027-01-24T09:46:33Z`. Access may require GitHub sign-in.

This commit publishes the report plus [every original artifact file SHA256](data/stress-20261026/evidence-manifests/40302159760/artifact-files.json),
[provenance audit](data/stress-20261026/evidence-manifests/40302159760/provenance-audit.json), and
[prepared lossless archive identity](data/stress-20261026/evidence-manifests/40302159760/prepared-archive.json).
The lossless archive has been fully byte-verified and retained, but its binary
blob is **not published here yet**. Durable archive publication is pending;
no nonexistent archive download link or permanent-availability claim is made.
The [complete prepared member manifest](data/stress-20261026/evidence-manifests/40302159760/prepared-archive-files.json)
preserves raw failures/negatives as well as exact-version helpers and derived
audits. No raw samples were trimmed to make this small report batch.

## Subsequent results, without replacing this run

The original pending-work statements above describe the state at this run.
The [unique10000 control](STRESS-CACHE-UNIQUE-10000-RESULTS.md) later failed the
small-admission restore gate; [eligible64KiB screening](STRESS-CACHE-LARGE-64K-RESULTS.md),
[inventory reverse confirmation](STRESS-CACHE-INVENTORY-REVERSE-RESULTS.md), and
[one-build identical-copy calibration](STRESS-CACHE-IDENTICAL-BINARY-CALIBRATION-RESULTS.md)
are separately reported. None waives the original small-admission failure.
Alias-only, over-key-limit and history controls are not claimed completed here.
