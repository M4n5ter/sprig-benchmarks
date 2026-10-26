# Inventory-only reverse confirmation: benefit signal, failed noise check

**The intended eligible-file signal remains positive, but the predeclared
no-runtime-source-change control is unstable; this is not clean confirmation
or promotion evidence.** Main→portable inventory restore median−27.117%,
whole sampler−14.928%, with all three pairs improving. However inventory→portable
(same non-test runtime source) restore median **+19.424%**, whole **+9.987%**
exceed the predeclared5% noise-review threshold. No data are discarded.

[Run40309337054](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40309337054)
at benchmark `c65e6e2c34455a55832844369b4630d7446dd053` completed **success in5m31s**.
All3 native canaries,9 reverse-Latin samples, strict summary and artifact upload
passed. Independent exact-source reanalysis reproduces every server comparison
and verifies all raw/full-tree evidence. CI correctness success is not a pass
of the noise/interpretation gate. No automatic rerun, extra cell or main merge.

## Fixed separate series

| Label | Immutable source |
|---|---|
| main | `b300693e01c652c1a9631c61b7a439892d8f75cd` |
| inventory | `c392d45079314cdcf9813371ec9120d78be7bcd6` |
| portable | `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` |

Profile `inventory-reverse-v1`, schema `sprig-stress-cache-inventory-confirmation-v1`.
Canaries run ABC; measurements run **CBA/BAC/ACB**. Each pin appears once per
round and once per position. This is separate from the earlier forward screen
and the original small-file admission series; their data and failing unique10000
gate forf481 remain unchanged and binding. Do not pool different source pins.

Cell `cache-large-64k-1024`:1024 independent unique64KiB files (64MiB logical),
width one, no aliases, a no-op checkpoint, one64-byte edit and both historical
restores. Retained charge448MiB. All original files reach the≥64KiB cache
eligibility threshold. Fresh product store/cache per trial does not mean cold
OS page cache. No durability or publication barrier was relaxed.

## Source-equivalent control, not asserted binary equivalence

B/c392 and C/4eb differ only in one test-only repair in `src/file_cache.rs`.
Both source trees have50 entries and identical path sets; the other49 tracked
identities, Cargo/build inputs and configuration match. Removing the single known `#[cfg(test)]` injection seam
and excluding the test module yields the identical11181-byte production prefix
SHA256`95fa75c3ee270cbff96b3dd5d8cc3cec6a5d48ba059839608609f0e2917ace49`.
Exact clean checkouts, full-file hashes and this proof were checked before/after
each sample. The known B/C pair could have equal binary hashes without invented
differences, but this run actually produced distinct hashes:

| Pin | Recorded release binary SHA256 |
|---|---|
| main | `95e3f068205a9fea634a06537adc84d9170b5834ca4030c690fa1b6b1f847bdc` |
| inventory | `f11ce532061c65a11139e225cabe83902fe5c811a37f4c7bfa1a85864bbfed43` |
| portable | `886089df03f2bbe5d6d0faf811e70e62217fa7011d58d2026a33f90fc3ccd2ed` |

Source equivalence is not guaranteed bit-identical output across build paths,
source locations or toolchain details. B→C is the predeclared no-runtime-source-
change/noise control, not another optimization. Its timing discrepancy flags
instability; these wall measurements alone do not prove whether host scheduling,
I/O, binary layout or any other mechanism caused it.

## All nine raw samples and both restores

| Round/position | Pin | Whole(s) | Restore aggregate(s) | Restore1(s) | Restore2(s) | First fork(s) | Warm fork(s) |
|---|---|---:|---:|---:|---:|---:|---:|
| 1/1 | portable | 8.902026 | 3.833082 | 3.084178 | 0.748904 | 0.770465 | 0.772229 |
| 1/2 | inventory | 7.834691 | 3.209632 | 2.517791 | 0.691841 | 0.735528 | 0.578880 |
| 1/3 | main | 10.464138 | 5.071476 | 4.107588 | 0.963888 | 0.728741 | 0.605735 |
| 2/1 | inventory | 9.726009 | 4.015219 | 3.358757 | 0.656462 | 1.370733 | 0.615117 |
| 2/2 | main | 9.512154 | 4.842054 | 4.145898 | 0.696156 | 0.798044 | 0.610490 |
| 2/3 | portable | 8.286980 | 3.529025 | 2.429614 | 1.099411 | 0.745718 | 0.656171 |
| 3/1 | main | 14.559385 | 9.895295 | 5.366803 | 4.528492 | 0.727372 | 0.656998 |
| 3/2 | portable | 8.628290 | 3.916155 | 2.930971 | 0.985184 | 0.764946 | 0.606164 |
| 3/3 | inventory | 7.844808 | 3.161088 | 2.483201 | 0.677888 | 0.765666 | 0.588398 |

The last main sample is visibly slow (restore aggregate9.895s, including
4.528s second restore), and inventory round2 first fork is1.371s versus roughly
0.73–0.80s elsewhere. They remain fully included. These observations explain
why a large aggregate ratio deserves caution; they do not license outlier removal
or causal claims. All three main→portable restore pairs improve, but the
no-runtime-source-change control itself moves substantially in both directions.

## Every paired whole/phase/storage metric

Percent=second/first−1. Median/geom summarize three within-round paired ratios.
Whole sampler includes preparation, complete oracles, accounting, normal cleanup
and serialization, excluding external fixture/image setup. Phases may overlap;
never sum/subtract them into exclusive costs. Physical Used is whole-filesystem
Btrfs usage including caches/retained generations/logs, not logical byte estimates.

### main-to-inventory

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | +0.000% | +0.047% | -0.023% | +0.000% | +0.008% |
| checkpoint_seconds | +1.501% | +6.979% | +4.256% | +4.256% | +4.221% |
| first_fork_seconds | +0.931% | +71.762% | +5.265% | +5.265% | +22.202% |
| first_read_seconds | +0.152% | -1.664% | +0.495% | +0.152% | -0.343% |
| import_seconds | -25.628% | +25.021% | +2.685% | +2.685% | -1.531% |
| init_seconds | -91.670% | +66.246% | +20.328% | +20.328% | -44.972% |
| postHistoryWholeFilesystemBytes | -0.031% | +0.015% | -0.015% | -0.015% | -0.010% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -0.214% | -0.870% | +0.241% | -0.214% | -0.282% |
| restore_seconds | -36.712% | -17.076% | -68.055% | -36.712% | -44.860% |
| total_import_fork_read_seconds | -18.761% | +37.426% | +3.283% | +3.283% | +4.862% |
| warm_fork_seconds | -4.434% | +0.758% | -10.441% | -4.434% | -4.816% |
| warm_read_seconds | +1.657% | -1.113% | -0.847% | -0.847% | -0.109% |
| warm_total_seconds | -3.359% | +0.425% | -8.846% | -3.359% | -4.003% |
| wholeSampleSeconds | -25.128% | +2.248% | -46.119% | -25.128% | -25.560% |
| write_seconds | +1.982% | -21.164% | -0.022% | -0.022% | -7.021% |

### inventory-to-portable

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | -0.023% | +0.023% | +0.047% | +0.023% | +0.016% |
| checkpoint_seconds | +14.958% | -5.035% | +26.919% | +14.958% | +11.483% |
| first_fork_seconds | +4.750% | -45.597% | -0.094% | -0.094% | -17.119% |
| first_read_seconds | -3.531% | -0.458% | -1.288% | -1.288% | -1.768% |
| import_seconds | +1.495% | -18.773% | -4.172% | -4.172% | -7.556% |
| init_seconds | +6.677% | -42.212% | -12.795% | -12.795% | -18.688% |
| postHistoryWholeFilesystemBytes | -0.015% | +0.015% | +0.031% | +0.015% | +0.010% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | +0.574% | +1.416% | +1.932% | +1.416% | +1.306% |
| restore_seconds | +19.424% | -12.109% | +23.886% | +19.424% | +9.149% |
| total_import_fork_read_seconds | +2.127% | -27.964% | -2.896% | -2.896% | -10.606% |
| warm_fork_seconds | +33.401% | +6.674% | +3.019% | +6.674% | +13.600% |
| warm_read_seconds | -1.493% | +42.891% | +3.959% | +3.959% | +13.530% |
| warm_total_seconds | +26.925% | +13.017% | +3.189% | +13.017% | +13.966% |
| wholeSampleSeconds | +13.623% | -14.796% | +9.987% | +9.987% | +2.115% |
| write_seconds | +13.925% | +0.873% | +24.181% | +13.925% | +12.585% |

### main-to-portable

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | -0.023% | +0.070% | +0.023% | +0.023% | +0.023% |
| checkpoint_seconds | +16.684% | +1.592% | +32.320% | +16.684% | +16.189% |
| first_fork_seconds | +5.726% | -6.557% | +5.166% | +5.166% | +1.282% |
| first_read_seconds | -3.384% | -2.115% | -0.799% | -2.115% | -2.105% |
| import_seconds | -24.517% | +1.551% | -1.600% | -1.600% | -8.972% |
| init_seconds | -91.114% | -3.929% | +4.932% | -3.929% | -55.256% |
| postHistoryWholeFilesystemBytes | -0.046% | +0.031% | +0.015% | +0.015% | +0.000% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | +0.359% | +0.534% | +2.178% | +0.534% | +1.020% |
| restore_seconds | -24.419% | -27.117% | -60.424% | -27.117% | -39.815% |
| total_import_fork_read_seconds | -17.034% | -1.004% | +0.292% | -1.004% | -6.259% |
| warm_fork_seconds | +27.486% | +7.483% | -7.737% | +7.483% | +8.129% |
| warm_read_seconds | +0.140% | +41.300% | +3.079% | +3.079% | +13.407% |
| warm_total_seconds | +22.662% | +13.498% | -5.939% | +13.498% | +9.405% |
| wholeSampleSeconds | -14.928% | -12.880% | -40.737% | -14.928% | -23.986% |
| write_seconds | +16.183% | -20.476% | +24.154% | +16.183% | +4.681% |

## Binding negatives and decision

- B→C restore pairs+19.424/−12.109/+23.886%, whole+13.623/−14.796/+9.987%.
  Median noise controls exceed5%; this requires investigation, not a clean pass.
- A→C first-fork median+5.166% and warm-fork median+7.483% remain negatives;
  all three B→C warm forks are slower (median+6.674%). A restore gain does not
  erase regressions in other operations.
- A→C restore pairs−24.419/−27.117/−60.424%, whole−14.928/−12.880/−40.737%.
  The intended≥10% restore/≤5% whole signal is present, but noise-control failure
  prevents calling it robust confirmation. Whole Used is essentially unchanged,
  so no new storage-saving claim follows.
- Only three observations per pin and two dependent restores per sample; no
  significance, stable p95/p99, independent-host or broad-platform claim.
- No main promotion from this run. Preserve the strong prior inventory screen
  and this mixed reverse result separately; investigate variability under a
  separately reviewed diagnostic rather than rerunning until green.
- Small-admission f481 unique10000 restore median+14.525% remains a failed
  control. Neither inventory-only release equivalence nor these large-file
  improvements waive it.

## Full correctness, provenance and unchanged caps

All12 planned samples retained:144 exact full-tree checks/30 historical readbacks,
paths/types/content/modes/exact-ns/symlink/hardlink topology, source/retained views,
acknowledged revision histories and normal cleanup. All218 original artifact files
22,786,750B and all120 source/test-file hashes plus13 helper/prerequisite hashes
were checked; source-file path sets match exact git objects. Binary identities
match all raw reports/manifests; executable bytes were not archived. Independent
exactc65 summary equals the original server result; no analysis fix or product rerun.

The prior eligible-screen gate binds exact reviewed40302159760 metadata, manifest,
summary and source/raw audit SHA values. It is a **prior root-reviewed attestation**,
not a fresh-job independent re-audit of that earlier22MB artifact. This run fully
audited its own three canaries/nine samples and recorded the proof in both stages.

Existing Ubuntu24/jobs2,45min hard job,40min original admission clock, one≤1200sec
measurement deadline across canaries+confirmation, fresh2GiB images,256MiB reserve
and≤1GiB retained bound. No parallel measurement, forced teardown, kernel-fault
harness, image enlargement, discarded sample or security/billing change. Omitted
metadata probe remains explicit null/notMeasured, never a fabricated zero.

## Published report and current raw evidence

The full raw source is the public [GitHub Actions artifact 12644626148](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40309337054/artifacts/12644626148)
for [run 40309337054](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40309337054) (4,891,390 compressed bytes).
Artifact identity/head and non-expired status were checked on 2026-10-26 before
this report-only publication. GitHub artifact retention is finite; the current
expiry is `2027-01-24T10:41:15Z`. Access may require GitHub sign-in.

This commit publishes the report plus [every original artifact file SHA256](data/stress-20261026/evidence-manifests/40309337054/artifact-files.json),
[provenance audit](data/stress-20261026/evidence-manifests/40309337054/provenance-audit.json), and
[prepared lossless archive identity](data/stress-20261026/evidence-manifests/40309337054/prepared-archive.json).
The lossless archive has been fully byte-verified and retained, but its binary
blob is **not published here yet**. Durable archive publication is pending;
no nonexistent archive download link or permanent-availability claim is made.
The [complete prepared member manifest](data/stress-20261026/evidence-manifests/40309337054/prepared-archive-files.json)
preserves raw failures/negatives as well as exact-version helpers and derived
audits. No raw samples were trimmed to make this small report batch.
