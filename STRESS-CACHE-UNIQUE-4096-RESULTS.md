# Native cache unique4096 negative-control results

**This control did not expose a >5% median whole-run or restore regression.**
Inventory→admission median restore is+0.338% and whole sampler−2.692%;
main→admission median restore−0.146% and whole sampler−0.339%. These small-N
near-zero restore differences are not evidence of a unique-file cache speedup.

[Run40297607763](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40297607763)
at exact benchmark `93ce3366204a34eeefdd95ebc92aad1b2d976468` completed **success**
in9m18s. All three native canaries, all nine Latin samples, the strict server
summary and artifact upload passed. Independent reanalysis with exact source
helpers reproduced the server summary, every raw oracle and every archive hash.
The previous duplicate-cell run remains a failed CI with transparently corrected
post-hoc analysis; no retrospective green status or replacement run is claimed.

## Fixed pins and source recipe

| Label | Immutable source |
|---|---|
| main | `b300693e01c652c1a9631c61b7a439892d8f75cd` |
| inventory | `c392d45079314cdcf9813371ec9120d78be7bcd6` |
| admission | `f481aaba987d960bf119e95b68f5b38da56e1581` |

Cell `files-4096` delegates the existing fixture unchanged:4096 unique4KiB
files in a width-one directory, each independently written, no aliases or
duplicate-content reuse, no-op checkpoint plus one64-byte edit and both retained
historical readbacks. Each sample has a fresh product store/cache; the host OS
page cache is **not** claimed cold. Orders are ABC/BCA/CAB, one pin per position
and round. All three versions receive the same fixture and resource limits.

Both main and the inventory-only pin retain≥64KiB eligibility. Consequently
main→inventory on this4KiB cell is a negative-control/noise comparison, not
evidence about inventory scanning on its eligible path. No measurements are
pooled with the duplicate-content screen or the earlier Cargo profiles.

## Complete audit and resource budget

- All3 canaries and9 planned screen observations retained:144 exact full-tree
  checks and30 historical readbacks, including paths/content/type/mode/exact-ns,
  symlink and internal hardlink topology, source/retained-view invariance,
  acknowledged revision chains and normal cleanup.
- All217 original artifact files82,877,296B hashed;120 product source/test-file
  hashes and7 benchmark-helper hashes match exact git objects. Three recorded
  binary hashes match manifests and all12 samples; executable bytes not archived.
- One existing Ubuntu runner,45min job cap, original40min admission deadline,
  shared≤1200sec measurement clock across canaries and screen, fresh2GiB images,
 256MiB reserve and≤1GiB conservative retained charge. No fault harness, forced
  cleanup, image enlargement, discarded samples, retry or parallel experiment.
- Explicitly omitted metadata-branch timing remains `notMeasured=null`, not
  zero or a ratio. All other malformed timings fail closed. Physical figures
  are whole-filesystem Btrfs Used including retained state, not logical bytes.

## All nine observations

| Round/position | Pin | Whole sampler(s) | Restore aggregate(s) | Active Used(MiB) | Post-history Used(MiB) |
|---|---|---:|---:|---:|---:|
| 1/1 | main | 24.120533 | 8.839957 | 50.2266 | 94.8945 |
| 1/2 | inventory | 23.972002 | 8.393529 | 50.2539 | 95.0156 |
| 1/3 | admission | 23.326676 | 8.629616 | 50.1953 | 94.9570 |
| 2/1 | inventory | 23.945867 | 8.663648 | 50.2578 | 94.9883 |
| 2/2 | admission | 23.824632 | 8.692916 | 50.1953 | 94.8633 |
| 2/3 | main | 23.905652 | 8.593439 | 50.2266 | 95.0195 |
| 3/1 | admission | 22.590242 | 8.028068 | 50.2852 | 94.9844 |
| 3/2 | main | 22.632917 | 8.039766 | 50.1953 | 95.0508 |
| 3/3 | inventory | 23.255633 | 8.350453 | 50.2578 | 94.9570 |

## Every pair and phase

Percentages are candidate/baseline−1; lower is better. Median/geom describe
the three within-round paired ratios. Timings overlap: do not sum/subtract them
into exclusive costs. Whole sampler includes preparation, correctness, accounting,
normal cleanup and evidence serialization, excluding external image/fixture setup.

### main-to-inventory

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | +0.054% | +0.062% | +0.125% | +0.062% | +0.080% |
| checkpoint_seconds | -4.916% | -0.703% | +0.977% | -0.703% | -1.579% |
| first_fork_seconds | +8.369% | -0.180% | -0.334% | -0.180% | +2.539% |
| first_read_seconds | -6.629% | +4.251% | +7.118% | +4.251% | +1.403% |
| import_seconds | +0.535% | +1.872% | +5.531% | +1.872% | +2.624% |
| init_seconds | +18.334% | -10.700% | -5.216% | -5.216% | +0.053% |
| postHistoryWholeFilesystemBytes | +0.128% | -0.033% | -0.099% | -0.033% | -0.001% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -2.896% | -4.833% | +0.620% | -2.896% | -2.396% |
| restore_seconds | -5.050% | +0.817% | +3.864% | +0.817% | -0.192% |
| total_import_fork_read_seconds | +2.811% | +1.232% | +3.468% | +2.811% | +2.499% |
| warm_fork_seconds | +2.723% | -3.268% | +0.699% | +0.699% | +0.020% |
| warm_read_seconds | +0.862% | -4.261% | -3.890% | -3.890% | -2.457% |
| warm_total_seconds | +2.468% | -3.403% | +0.060% | +0.060% | -0.321% |
| wholeSampleSeconds | -0.616% | +0.168% | +2.751% | +0.168% | +0.758% |
| write_seconds | +1.097% | -3.708% | +4.839% | +1.097% | +0.682% |

### inventory-to-admission

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | -0.117% | -0.124% | +0.054% | -0.117% | -0.062% |
| checkpoint_seconds | -0.347% | +0.140% | -1.123% | -0.347% | -0.445% |
| first_fork_seconds | -7.483% | -4.021% | -0.316% | -4.021% | -3.985% |
| first_read_seconds | +3.613% | +3.930% | -3.158% | +3.613% | +1.408% |
| import_seconds | -8.531% | -0.155% | -5.659% | -5.659% | -4.845% |
| init_seconds | -21.480% | -6.648% | -3.407% | -6.648% | -10.872% |
| postHistoryWholeFilesystemBytes | -0.062% | -0.132% | +0.029% | -0.062% | -0.055% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | +0.575% | -0.443% | -0.298% | -0.298% | -0.056% |
| restore_seconds | +2.813% | +0.338% | -3.861% | +0.338% | -0.275% |
| total_import_fork_read_seconds | -7.523% | -1.356% | -3.611% | -3.611% | -4.197% |
| warm_fork_seconds | -6.949% | -0.776% | -1.355% | -1.355% | -3.067% |
| warm_read_seconds | +4.324% | +2.351% | +6.220% | +4.324% | +4.286% |
| warm_total_seconds | -5.425% | -0.354% | -0.342% | -0.354% | -2.070% |
| wholeSampleSeconds | -2.692% | -0.506% | -2.861% | -2.692% | -2.026% |
| write_seconds | +0.279% | +2.905% | -4.255% | +0.279% | -0.401% |

### main-to-admission

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | -0.062% | -0.062% | +0.179% | -0.062% | +0.018% |
| checkpoint_seconds | -5.247% | -0.564% | -0.156% | -0.564% | -2.017% |
| first_fork_seconds | +0.260% | -4.194% | -0.649% | -0.649% | -1.547% |
| first_read_seconds | -3.255% | +8.347% | +3.736% | +3.736% | +2.831% |
| import_seconds | -8.042% | +1.714% | -0.440% | -0.440% | -2.347% |
| init_seconds | -7.085% | -16.637% | -8.445% | -8.445% | -10.824% |
| postHistoryWholeFilesystemBytes | +0.066% | -0.164% | -0.070% | -0.070% | -0.056% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -2.338% | -5.255% | +0.320% | -2.338% | -2.451% |
| restore_seconds | -2.379% | +1.158% | -0.146% | -0.146% | -0.467% |
| total_import_fork_read_seconds | -4.923% | -0.140% | -0.268% | -0.268% | -1.803% |
| warm_fork_seconds | -4.415% | -4.018% | -0.666% | -4.018% | -3.047% |
| warm_read_seconds | +5.223% | -2.011% | +2.089% | +2.089% | +1.724% |
| warm_total_seconds | -3.091% | -3.745% | -0.282% | -3.091% | -2.384% |
| wholeSampleSeconds | -3.291% | -0.339% | -0.189% | -0.339% | -1.283% |
| write_seconds | +1.379% | -0.911% | +0.378% | +0.378% | +0.278% |

## Control gate and remaining work

On all three edges, neither median whole-sampler nor median restore regression
exceeds the predeclared5% threshold. This is a **single negative-control screen**,
not proof of performance equivalence. Preserve restore losses: B→C pair1+2.813%,
pair2+0.338%; A→C pair2+1.158%; A→B pair3+3.864%. Other phase/order fluctuations
are visible above rather than hidden behind the whole-run aggregate.

No whole-run p95/p99 or statistical confidence claim from three same-host
observations. Each sample has only two dependent restore operations, so their
counts do not support useful tail estimates. Required unique10000, alias-only,
over-key-limit, repeated history and actual≥64KiB inventory-path controls remain
pending, as do crossover/projection-envelope and reviewed reverse-order
confirmation. This result alone does not authorize promotion or automatic
additional dispatches.

## Published report and current raw evidence

The full raw source is the public [GitHub Actions artifact 12638744812](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40297607763/artifacts/12638744812)
for [run 40297607763](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40297607763) (18,190,371 compressed bytes).
Artifact identity/head and non-expired status were checked on 2026-10-26 before
this report-only publication. GitHub artifact retention is finite; the current
expiry is `2027-01-24T09:11:10Z`. Access may require GitHub sign-in.

This commit publishes the report plus [every original artifact file SHA256](data/stress-20261026/evidence-manifests/40297607763/artifact-files.json),
[provenance audit](data/stress-20261026/evidence-manifests/40297607763/provenance-audit.json), and
[prepared lossless archive identity](data/stress-20261026/evidence-manifests/40297607763/prepared-archive.json).
The lossless archive has been fully byte-verified and retained, but its binary
blob is **not published here yet**. Durable archive publication is pending;
no nonexistent archive download link or permanent-availability claim is made.
The [complete prepared member manifest](data/stress-20261026/evidence-manifests/40297607763/prepared-archive-files.json)
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
