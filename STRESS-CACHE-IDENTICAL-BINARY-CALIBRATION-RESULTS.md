# Inventory identical-binary calibration: identity median gate passes; scatter and negatives remain visible

**identity median gate passed; inspect every pair/scatter and all off-path negatives before any stability claim.** CI correctness success is not automatic stability or promotion. No sample is dropped; no repeat is automatically authorized.

The identical candidate copies differ by median +0.574% in restore time and -2.441% in whole-sample wall time. The predeclared noise-median gate is **PASS**; every individual noise pair lies in the same 5% band: **False**.

[Run 40315552913](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40315552913)
at exact benchmark `7c5011621db953ac78d0bf0fa8e3a08cb479935c` is **success**.
The job finished in4m40s. All three canaries and nine samples, raw oracles and independent
exact-version reanalysis passed. The recomputed records, metrics, comparisons and
calibration assessment equal the original server output; no analysis correction
or product rerun was needed.

## Fixed identity and one-build proof

| Label | Source SHA | Recorded binary SHA256 |
|---|---|---|
| main | `b300693e01c652c1a9631c61b7a439892d8f75cd` | `95e3f068205a9fea634a06537adc84d9170b5834ca4030c690fa1b6b1f847bdc` |
| copy1 | `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` | `886089df03f2bbe5d6d0faf811e70e62217fa7011d58d2026a33f90fc3ccd2ed` |
| copy2 | `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` | `886089df03f2bbe5d6d0faf811e70e62217fa7011d58d2026a33f90fc3ccd2ed` |

C1/copy1 and C2/copy2 are separately installed byte-identical copies of ONE
portable4eb release build and share one exact clean source checkout. The workflow
and live checks verified the origin/copies bytes, SHA256, distinct executable
paths and independent inodes before and after each sample. The source/log/copy
proof is bound into both canary and measurement reports:
`a03981c51ec44258f6fc99d9486a1aae4b7c9a6f920e6e08e695a72d7300244e`.
The complete archived release log contains exactly one candidate package release
compilation. Offline reanalysis verifies that log and proof, not executable bytes:
the executable files themselves are not archived. This is not a second source
optimization, instrumented run, or fabricated binary distinction.

A/main is exact b300. Only two unique sources were built, unlike the earlier
three-source reverse experiment. Do not pool absolute timings or assume equal
setup/page-cache state. Fresh product stores/images do not imply cold OS caches.
The original admission and source-equivalent confirmation identities remain
unchanged and separate.

## Predeclared gates and all paired scatter

Noise C1→C2 median whole AND restore must lie within [0.95,1.05]. Each A→C arm
requires median restore≤0.90 and whole≤1.05. The arms share the SAME three A
observations: three shared-baseline paired rounds, NOT six independent pairs.
No stable p95/p99, significance, host-generalization or platform-wide claim follows.

| Edge | Restore pairs | Restore median | Whole pairs | Whole median |
|---|---|---:|---|---:|
| main-to-copy1 | -40.502%, -43.509%, -40.976% | -40.976% | -17.193%, -18.046%, -20.552% | -18.046% |
| copy1-to-copy2 | -0.270%, +6.573%, +0.574% | +0.574% | -2.441%, -3.135%, -0.618% | -2.441% |
| main-to-copy2 | -40.663%, -39.796%, -40.637% | -40.637% | -19.214%, -20.615%, -21.042% | -20.615% |

Shared-baseline benefit gate: {"main-to-copy1": true, "main-to-copy2": true}.
All-pair noise-band flag is descriptive, not a newly invented hard acceptance
threshold. Median success never licenses hiding wild scatter or declaring stable
performance. If noise persists, this one finite calibration ends inconclusive:
no automatic repeat, sample-count tuning, outlier deletion or main promotion.

## All nine samples, both restores, and order

Canaries A/C1/C2; measured rounds **C2/C1/A, C1/A/C2, A/C2/C1**. Each label
appears once in every position. Cell `cache-large-64k-1024`:1024 independent
unique64KiB files,64MiB logical; no aliases; one no-op checkpoint, one64-byte
edit and both historical restores. Conservative retained charge448MiB.

| Round/position | Label | Whole(s) | Restore sum(s) | Restore1(s) | Restore2(s) | First fork(s) | Warm fork(s) |
|---|---|---:|---:|---:|---:|---:|---:|
| 1/1 | copy2 | 7.846388 | 3.037206 | 2.382524 | 0.654682 | 0.716547 | 0.550807 |
| 1/2 | copy1 | 8.042746 | 3.045439 | 2.381558 | 0.663881 | 0.986106 | 0.577950 |
| 1/3 | main | 9.712611 | 5.118541 | 4.442632 | 0.675909 | 0.715123 | 0.563406 |
| 2/1 | copy1 | 7.896194 | 2.862271 | 2.267159 | 0.595111 | 0.712228 | 1.038765 |
| 2/2 | main | 9.634933 | 5.066812 | 4.429939 | 0.636873 | 0.718296 | 0.561979 |
| 2/3 | copy2 | 7.648668 | 3.050413 | 2.374580 | 0.675834 | 0.719123 | 0.567798 |
| 3/1 | main | 9.742110 | 5.063021 | 4.421158 | 0.641863 | 0.796440 | 0.577901 |
| 3/2 | copy2 | 7.692151 | 3.005544 | 2.300306 | 0.705238 | 0.754018 | 0.614422 |
| 3/3 | copy1 | 7.739954 | 2.988385 | 2.374779 | 0.613606 | 0.742603 | 0.568318 |

## Every paired phase and storage metric

Percent=second/first−1. Median/geom summarize three within-round ratios.
Whole sample includes preparation/oracles/accounting/normal cleanup/serialization
inside the sampler, excluding external fixture/image preparation. Phases overlap;
never subtract or add them as exclusive contributions. Used is whole-filesystem
Btrfs usage including cache/retained trees/logs; no empty-image subtraction.

### main-to-copy1

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | +0.000% | +0.000% | +0.023% | +0.000% | +0.008% |
| checkpoint_seconds | -3.338% | +5.983% | +1.131% | +1.131% | +1.187% |
| first_fork_seconds | +37.893% | -0.845% | -6.760% | -0.845% | +8.431% |
| first_read_seconds | +1.440% | +1.221% | -5.333% | +1.221% | -0.941% |
| import_seconds | +6.487% | -0.725% | +0.939% | +0.939% | +2.188% |
| init_seconds | -0.285% | +1.871% | +468.521% | +1.871% | +79.412% |
| postHistoryWholeFilesystemBytes | +0.062% | -0.015% | +0.000% | +0.000% | +0.015% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -1.670% | -1.285% | +42.666% | -1.285% | +11.463% |
| restore_seconds | -40.502% | -43.509% | -40.976% | -40.976% | -41.678% |
| total_import_fork_read_seconds | +14.761% | -0.658% | -1.643% | -0.658% | +3.891% |
| warm_fork_seconds | +2.581% | +84.840% | -1.658% | +2.581% | +23.084% |
| warm_read_seconds | +0.450% | -0.292% | -0.841% | -0.292% | -0.229% |
| warm_total_seconds | +2.165% | +68.461% | -1.502% | +2.165% | +19.237% |
| wholeSampleSeconds | -17.193% | -18.046% | -20.552% | -18.046% | -18.609% |
| write_seconds | -0.282% | -8.784% | -3.581% | -3.581% | -4.280% |

### copy1-to-copy2

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | +0.000% | +0.000% | +0.047% | +0.000% | +0.016% |
| checkpoint_seconds | +83.841% | -6.192% | +0.625% | +0.625% | +20.170% |
| first_fork_seconds | -27.336% | +0.968% | +1.537% | +0.968% | -9.348% |
| first_read_seconds | -0.349% | +0.917% | +4.417% | +0.917% | +1.642% |
| import_seconds | -2.881% | +1.740% | +0.186% | +0.186% | -0.337% |
| init_seconds | +2.539% | -4.459% | -82.574% | -4.459% | -44.526% |
| postHistoryWholeFilesystemBytes | +0.000% | +0.000% | +0.077% | +0.000% | +0.026% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -3.350% | +5.278% | -32.756% | -3.350% | -11.882% |
| restore_seconds | -0.270% | +6.573% | +0.574% | +0.574% | +2.248% |
| total_import_fork_read_seconds | -10.749% | +1.487% | +0.769% | +0.769% | -2.997% |
| warm_fork_seconds | -4.696% | -45.339% | +8.112% | -4.696% | -17.418% |
| warm_read_seconds | -1.974% | +1.083% | +4.026% | +1.083% | +1.015% |
| warm_total_seconds | -4.174% | -40.053% | +7.327% | -4.174% | -14.888% |
| wholeSampleSeconds | -2.441% | -3.135% | -0.618% | -2.441% | -2.070% |
| write_seconds | +2.159% | -3.358% | +7.317% | +2.159% | +1.946% |

### main-to-copy2

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | +0.000% | +0.000% | +0.070% | +0.000% | +0.023% |
| checkpoint_seconds | +77.704% | -0.580% | +1.762% | +1.762% | +21.596% |
| first_fork_seconds | +0.199% | +0.115% | -5.327% | +0.115% | -1.705% |
| first_read_seconds | +1.086% | +2.149% | -1.152% | +1.086% | +0.685% |
| import_seconds | +3.419% | +1.002% | +1.126% | +1.126% | +1.843% |
| init_seconds | +2.246% | -2.671% | -0.929% | -0.929% | -0.472% |
| postHistoryWholeFilesystemBytes | +0.062% | -0.015% | +0.077% | +0.062% | +0.041% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | -4.964% | +3.925% | -4.066% | -4.066% | -1.781% |
| restore_seconds | -40.663% | -39.796% | -40.637% | -40.637% | -40.367% |
| total_import_fork_read_seconds | +2.425% | +0.819% | -0.887% | +0.819% | +0.777% |
| warm_fork_seconds | -2.236% | +1.035% | +6.320% | +1.035% | +1.646% |
| warm_read_seconds | -1.533% | +0.788% | +3.152% | +0.788% | +0.784% |
| warm_total_seconds | -2.099% | +0.988% | +5.715% | +0.988% | +1.484% |
| wholeSampleSeconds | -19.214% | -20.615% | -21.042% | -20.615% | -20.294% |
| write_seconds | +1.871% | -11.847% | +3.474% | +1.871% | -2.417% |

## All median phase regressions retained

These are descriptive negatives, not causal attributions or independent tests.

- main-to-copy1: checkpoint_seconds +1.131%; first_read_seconds +1.221%; import_seconds +0.939%; init_seconds +1.871%; warm_fork_seconds +2.581%; warm_total_seconds +2.165%.
- copy1-to-copy2: checkpoint_seconds +0.625%; first_fork_seconds +0.968%; first_read_seconds +0.917%; import_seconds +0.186%; restore_seconds +0.574%; total_import_fork_read_seconds +0.769%; warm_read_seconds +1.083%; write_seconds +2.159%.
- main-to-copy2: checkpoint_seconds +1.762%; first_fork_seconds +0.115%; first_read_seconds +1.086%; import_seconds +1.126%; total_import_fork_read_seconds +0.819%; warm_fork_seconds +1.035%; warm_read_seconds +0.788%; warm_total_seconds +0.988%; write_seconds +1.871%.

Warm fork occurs before restores and uses unchanged ordinary copy-tree paths;
a wall-time difference there is not by itself evidence of inventory-cache cost.
No CPU, syscall, scheduling, I/O or binary-layout mechanism was measured here.

## Correctness, provenance, caps, and prior binding negatives

All 217 original artifact files (22,485,238 B) are retained and SHA256-manifested.
Exact git-object audit verified 80 source/test files across the two unique checkouts and 15 benchmark helper/prerequisite hashes.
All12 samples/144 full-tree checks/30 historical readbacks retain exact paths,
types/content/modes/exact-ns metadata,
symlink/hardlink topology, historical revision identities, readbacks, source and
retained views, and normal cleanup. Omitted metadata probe remains explicit
`null`/`notMeasured`, never fake zero. All actual failures would suppress ratios.

Prior eligible screen40302159760 is a hash-bound root-reviewed attestation,
not a fresh-job re-audit of its earlier22MB raw artifact. This calibration fully
audits its OWN three canaries and nine samples. Earlier screen, reverse and this
calibration must remain separate: reverse40309337054 had a same-runtime-source
noise-control median+19.424% restore/+9.987% whole and off-path negatives.
Small-admission f481 unique10000 restore median+14.525% remains a failed gate;
inventory-only measurements do not rescue that separate candidate.

Resources unchanged: existing Ubuntu24/jobs2,45min job/40min original admission,
one≤1200s measurement clock shared by all canaries/nine samples; fresh2GiB
images,256MiB reserve and≤1GiB retained ceiling. No kernel-fault harness, forced
teardown, parallel measured job, instrumentation, enlarged caps or permission/
security/billing change. Neither CI success nor these ratios authorize main.

## Published report and current raw evidence

The full raw source is the public [GitHub Actions artifact 12646503811](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40315552913/artifacts/12646503811)
for [run 40315552913](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40315552913) (4,851,919 compressed bytes).
Artifact identity/head and non-expired status were checked on 2026-10-26 before
this report-only publication. GitHub artifact retention is finite; the current
expiry is `2027-01-24T11:30:18Z`. Access may require GitHub sign-in.

This commit publishes the report plus [every original artifact file SHA256](data/stress-20261026/evidence-manifests/40315552913/artifact-files.json),
[provenance audit](data/stress-20261026/evidence-manifests/40315552913/provenance-audit.json), and
[prepared lossless archive identity](data/stress-20261026/evidence-manifests/40315552913/prepared-archive.json).
The lossless archive has been fully byte-verified and retained, but its binary
blob is **not published here yet**. Durable archive publication is pending;
no nonexistent archive download link or permanent-availability claim is made.
The [complete prepared member manifest](data/stress-20261026/evidence-manifests/40315552913/prepared-archive-files.json)
preserves raw failures/negatives as well as exact-version helpers and derived
audits. No raw samples were trimmed to make this small report batch.
