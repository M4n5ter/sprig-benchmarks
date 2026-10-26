# Native cache unique10000: failed restore-regression gate

**Correctness/CI passed, but the predeclared performance control failed.**
Inventory→admission restore is slower in all three pairs: +23.601%, +5.684%,
+14.525%; median+14.525%, geometric+14.370%. Its whole-sampler median−4.031%
does not cancel this restore regression. Do not promote the candidate or quietly
discard/replace the negative observations.

[Run40299508761](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40299508761)
at exact benchmark `93ce3366204a34eeefdd95ebc92aad1b2d976468` completed **success**
in12m8s. All3 canaries,9 Latin sample invocations, strict analysis and upload
passed. Independent raw-file/oracle/source audit reproduced the server summary.
The success conclusion concerns execution/correctness, not acceptance of an
optimization. No product rerun or post-hoc analysis correction was used here.

## Fixed inputs and same-pressure comparison

| Label | Immutable source |
|---|---|
| main | `b300693e01c652c1a9631c61b7a439892d8f75cd` |
| inventory | `c392d45079314cdcf9813371ec9120d78be7bcd6` |
| admission | `f481aaba987d960bf119e95b68f5b38da56e1581` |

Cell `files-10000` uses the unchanged legacy source recipe:10000 independently
written unique4KiB files, width-one directory, no aliases, no-op checkpoint plus
one64-byte edit, and both retained historical readbacks. Each trial has a new
product store/cache; this is not a cold OS-page-cache claim. Order is ABC/BCA/CAB,
one observation per pin/round/position. No pooling with other cells or profiles.

Inventory keeps the original≥64KiB eligibility, so this tiny-file main→inventory
comparison does not exercise that inventory optimization path. Nevertheless its
restore varies −16.921%, +1.291%, −27.550% across pairs (median−16.921%).
This substantial phase/order variability warns against attributing the observed
B→C loss solely to admission code. It **does not** justify waiving the frozen
negative-control gate or calling main→inventory an inventory-path improvement.

## Complete correctness/provenance/resource audit

- All3 canaries and9 screen records preserved,144 full-tree checks and30
  historical readbacks: exact paths/content/type/mode/nanosecond timestamps,
  symlink/hardlink topology, source/retained-view invariance, acknowledged
  revision chains and normal cleanup all passed.
- All217 original artifact files198,577,004B hashed.120 product source/test
  hashes and7 helper hashes match exact git objects. All3 recorded executable
  hashes match manifests and12 samples; executable bytes were not archived.
- Existing Ubuntu runner,45min job cap, original40min admission clock, one
  ≤1200sec measurement deadline including canaries, fresh2GiB images,256MiB
  reserve and≤1GiB conservative retained bound. No faults, forced unmount,
  capacity expansion, blind retry, dropped sample or parallel measurement.
- Explicitly omitted metadata probe remains visible as `notMeasured=null`.
  Whole-filesystem Used includes retained state/cache/history; no empty-image
  subtraction or logical-byte substitution. All limits remained unchanged.

## All nine observations

| Round/position | Pin | Whole sampler(s) | Restore aggregate(s) | Active Used(MiB) | Post-history Used(MiB) |
|---|---|---:|---:|---:|---:|
| 1/1 | main | 47.784426 | 20.251122 | 121.9648 | 231.0117 |
| 1/2 | inventory | 49.463945 | 16.824350 | 121.9961 | 231.0742 |
| 1/3 | admission | 49.690105 | 20.795029 | 121.9336 | 231.1367 |
| 2/1 | inventory | 47.034029 | 16.454617 | 121.9648 | 231.0430 |
| 2/2 | admission | 45.138309 | 17.389858 | 121.9023 | 231.0117 |
| 2/3 | main | 47.166516 | 16.244841 | 122.0273 | 231.0742 |
| 3/1 | admission | 45.549687 | 18.760616 | 121.8398 | 230.9180 |
| 3/2 | main | 54.348547 | 22.610225 | 121.9336 | 230.9805 |
| 3/3 | inventory | 51.879351 | 16.381189 | 121.9336 | 230.8594 |

## Every pair and overlapping phase

Change is candidate/baseline−1; lower is better. Median/geom summarize three
within-round paired ratios. Timings overlap and must not be added/subtracted
into exclusive costs. Whole sampler includes preparation, oracles, accounting,
normal cleanup and evidence serialization, excluding external fixture/image setup.

### main-to-inventory

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | +0.026% | -0.051% | +0.000% | +0.000% | -0.009% |
| checkpoint_seconds | +2.187% | -1.631% | -6.387% | -1.631% | -2.007% |
| first_fork_seconds | +52.635% | -31.547% | -4.478% | -4.478% | -0.065% |
| first_read_seconds | -0.341% | -2.344% | -3.562% | -2.344% | -2.091% |
| import_seconds | +11.451% | +18.554% | +3.083% | +11.451% | +10.849% |
| init_seconds | -37.325% | +1056.148% | -68.449% | -37.325% | +31.737% |
| postHistoryWholeFilesystemBytes | +0.027% | -0.014% | -0.052% | -0.014% | -0.013% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | +0.072% | -1.506% | -0.455% | -0.455% | -0.632% |
| restore_seconds | -16.921% | +1.291% | -27.550% | -16.921% | -15.206% |
| total_import_fork_read_seconds | +25.130% | -2.564% | +0.256% | +0.256% | +6.921% |
| warm_fork_seconds | +18.900% | +0.715% | +64.372% | +18.900% | +25.324% |
| warm_read_seconds | -3.301% | +4.213% | +3.240% | +3.240% | +1.329% |
| warm_total_seconds | +16.243% | +1.118% | +57.379% | +16.243% | +22.757% |
| wholeSampleSeconds | +3.515% | -0.281% | -4.543% | -0.281% | -0.491% |
| write_seconds | -2.447% | -0.270% | +6.187% | -0.270% | +1.091% |

### inventory-to-admission

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | -0.051% | -0.051% | -0.077% | -0.051% | -0.060% |
| checkpoint_seconds | +0.232% | +5.726% | -7.591% | +0.232% | -0.696% |
| first_fork_seconds | -28.732% | +3.507% | -15.536% | -15.536% | -14.589% |
| first_read_seconds | +1.000% | +3.842% | +2.466% | +2.466% | +2.429% |
| import_seconds | -8.407% | -27.270% | -29.185% | -27.270% | -22.155% |
| init_seconds | +1.328% | -91.967% | +1434.200% | +1.328% | +7.687% |
| postHistoryWholeFilesystemBytes | +0.027% | -0.014% | +0.025% | +0.025% | +0.013% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -0.547% | +1.686% | +0.675% | +0.675% | +0.600% |
| restore_seconds | +23.601% | +5.684% | +14.525% | +14.525% | +14.370% |
| total_import_fork_read_seconds | -16.623% | -17.292% | -23.599% | -17.292% | -19.234% |
| warm_fork_seconds | -5.953% | +9.520% | -41.875% | -5.953% | -15.718% |
| warm_read_seconds | +0.367% | +0.231% | -1.092% | +0.231% | -0.167% |
| warm_total_seconds | -5.324% | +8.416% | -38.814% | -5.324% | -14.363% |
| wholeSampleSeconds | +0.457% | -4.031% | -12.201% | -4.031% | -5.405% |
| write_seconds | +4.015% | -2.960% | -7.601% | -2.960% | -2.298% |

### main-to-admission

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | -0.026% | -0.102% | -0.077% | -0.077% | -0.068% |
| checkpoint_seconds | +2.424% | +4.001% | -13.493% | +2.424% | -2.689% |
| first_fork_seconds | +8.779% | -29.146% | -19.318% | -19.318% | -14.645% |
| first_read_seconds | +0.656% | +1.408% | -1.184% | +0.656% | +0.287% |
| import_seconds | +2.082% | -13.776% | -27.002% | -13.776% | -13.710% |
| init_seconds | -36.493% | -7.126% | +384.063% | -7.126% | +41.864% |
| postHistoryWholeFilesystemBytes | +0.054% | -0.027% | -0.027% | -0.027% | -0.000% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -0.476% | +0.154% | +0.217% | +0.154% | -0.035% |
| restore_seconds | +2.686% | +7.048% | -17.026% | +2.686% | -3.021% |
| total_import_fork_read_seconds | +4.329% | -19.413% | -23.403% | -19.413% | -13.644% |
| warm_fork_seconds | +11.821% | +10.303% | -4.458% | +10.303% | +5.625% |
| warm_read_seconds | -2.946% | +4.454% | +2.112% | +2.112% | +1.159% |
| warm_total_seconds | +10.054% | +9.628% | -3.706% | +9.628% | +5.126% |
| wholeSampleSeconds | +3.988% | -4.300% | -16.190% | -4.300% | -5.869% |
| write_seconds | +1.469% | -3.221% | -1.885% | -1.885% | -1.232% |

## Decision and limitations

The frozen negative-control threshold allows no>5% median whole-run or restore
regression. The isolated inventory→admission edge fails on restore; the earlier
4KiB×8 intended-reuse improvement and unique4096 pass do not override it.
Main→admission restore median+2.686% (pairs+2.686/+7.048/−17.026%) is a distinct
combined comparison, not a substitute for the isolated failing edge.

Additional negatives remain visible: main→admission warm-fork median+10.303%
and warm-total+9.628%; main→inventory import+11.451%, warm-fork+18.900%
and warm-total+16.243%. Whole/restore timing variability is descriptive, not a
causal diagnosis. Post-history physical Used is essentially unchanged.

Only3 same-host samples per pin, with2 dependent restore operations each:
no statistical-significance, independent-host or useful p95/p99 claim. Required
alias-only, over-key-limit, history and eligible≥64KiB inventory-path controls
remain pending. Any further diagnostic/confirmation experiment must be separately
reviewed and must preserve these original losses; no automatic promotion or
additional dispatch follows this report.

## Published report and current raw evidence

The full raw source is the public [GitHub Actions artifact 12640441654](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40299508761/artifacts/12640441654)
for [run 40299508761](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40299508761) (43,679,726 compressed bytes).
Artifact identity/head and non-expired status were checked on 2026-10-26 before
this report-only publication. GitHub artifact retention is finite; the current
expiry is `2027-01-24T09:26:07Z`. Access may require GitHub sign-in.

This commit publishes the report plus [every original artifact file SHA256](data/stress-20261026/evidence-manifests/40299508761/artifact-files.json),
[provenance audit](data/stress-20261026/evidence-manifests/40299508761/provenance-audit.json), and
[prepared lossless archive identity](data/stress-20261026/evidence-manifests/40299508761/prepared-archive.json).
The lossless archive has been fully byte-verified and retained, but its binary
blob is **not published here yet**. Durable archive publication is pending;
no nonexistent archive download link or permanent-availability claim is made.
The [complete prepared member manifest](data/stress-20261026/evidence-manifests/40299508761/prepared-archive-files.json)
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
