# Native cache independent4KiB ×8 screen results

**One intended-reuse cell shows a restore improvement, not promotion readiness.**
Inventory→admission median paired restore time improved16.34% (all3 pairs faster);
whole-sampler median improved2.46%, with one pair0.48% slower. Main→admission
median restore improved21.05% and whole-sampler median5.60%. Negative controls,
large-file inventory-path evidence and reverse-order confirmation remain unmeasured.

## Failed CI and transparent same-sample analysis correction

[Run40294193428](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40294193428)
at benchmark `afacf84f0c6c80014c0e7c3cc00fac348357afbe` ended **failure**, after9m19s.
Three native canaries and all nine screen sampler invocations succeeded. The final
analysis rejected the inherited explicitly omitted `metadata_branch_seconds=null`
probe in every row. The original failed summary and all nine errors are preserved.
The separately reviewed analysis-only fix `ad7bfdd873a79bd03ee33f1525a5b08303addf4f`
passed root-owned22 offline tests and revalidated the **same unmodified** samples.
It labels that exact marker `notMeasured`, never zero; all other invalid timers
and contradictory markers still fail. No product measurement was rerun and the
original CI is not retroactively called green. See
[schema correction](STRESS-CACHE-SUMMARY-SCHEMA-CORRECTION.md).

## Pins, workload and bounded order

| Label | Source SHA |
|---|---|
| main | `b300693e01c652c1a9631c61b7a439892d8f75cd` |
| inventory | `c392d45079314cdcf9813371ec9120d78be7bcd6` |
| admission | `f481aaba987d960bf119e95b68f5b38da56e1581` |

Cell `cache-independent-4k-x8`:4096 independently written4KiB files,512 content
keys with8 distinct inodes per key, separated copies (`index %512`) in lexical
width-one traversal. Each sample uses a fresh product store, a no-op checkpoint
plus one64-byte edit and both historical readbacks. No initial OS-page-cache
coldness claim. Orders are main/inventory/admission, inventory/admission/main,
admission/main/inventory: each pin occupies each position once.

The inventory-only revision retains64KiB eligibility, so **main→inventory here is
a negative-control/noise comparison, not proof that inventory scanning improved**.
The admission policy is isolated by inventory→admission; main→admission describes
the combined candidate on this one cell. No pooling with Cargo/concurrency data.

## Correctness, identity and resource audit

- Three canaries:15 exact full-tree checks and4 readbacks each. Nine screen
  samples:11 exact checks and2 readbacks each. Total144 full-tree checks and30
  historical readbacks; every raw oracle and archive hash rechecked. Complete
  path/content/type/mode/exact-ns/symlink/hardlink topology, source/retained-view
  invariance, acknowledged history and normal cleanup gates passed.
- All217 original artifact files (82,807,547B) rehashed unchanged;120 source/test
  file hashes and7 benchmark helper hashes match exact git objects. Binary SHA-256
  identities match manifests and all12 reports; executable bytes were not archived.
- Existing Ubuntu runner,45min hard job cap, original40min admission deadline,
  shared1200sec measurement budget including canaries (not reset), fresh2GiB
  images,256MiB image reserve, ≤1GiB conservative retained charge and normal
  cleanup only. No fault injection, forced unmount, image expansion or retry.
- Whole-filesystem Btrfs Used includes retained trees/cache/logs/history; no
  empty-image subtraction or logical/referenced-byte substitution. Images were
  retained on the ephemeral runner, not included in the downloadable archive.

## All nine raw observations

| Round/order position | Pin | Whole sampler(s) | Restore aggregate(s) | Active Used(MiB) | Post-history Used(MiB) |
|---|---|---:|---:|---:|---:|
| 1/1 | main | 23.581835 | 8.649927 | 35.9805 | 80.8672 |
| 1/2 | inventory | 23.874983 | 8.743164 | 36.0391 | 80.9883 |
| 1/3 | admission | 21.950744 | 6.533751 | 35.9805 | 50.9023 |
| 2/1 | inventory | 22.495863 | 8.077473 | 36.0117 | 80.8984 |
| 2/2 | admission | 21.941754 | 6.757546 | 36.0742 | 50.8711 |
| 2/3 | main | 23.242569 | 8.559380 | 35.9766 | 80.8945 |
| 3/1 | admission | 22.631282 | 6.827650 | 35.9805 | 50.8398 |
| 3/2 | main | 23.786722 | 8.507446 | 35.9492 | 80.8359 |
| 3/3 | inventory | 22.522824 | 8.020636 | 35.9492 | 80.8359 |

## Every phase and paired comparison

All percentages are candidate/baseline−1; lower is better for time and Used.
“Median” is the median of three within-round paired ratios. “Geom” is their
geometric mean. Phase timings overlap and must not be summed/subtracted into
exclusive costs. Whole sampler includes preparation, oracle checks, accounting,
normal cleanup and evidence serialization, excluding external image/fixture setup.

### main-to-inventory

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | +0.163% | +0.098% | +0.000% | +0.098% | +0.087% |
| checkpoint_seconds | +1.682% | +1.507% | +1.090% | +1.507% | +1.426% |
| first_fork_seconds | +3.497% | -3.463% | -11.539% | -3.463% | -4.032% |
| first_read_seconds | +7.103% | -1.138% | -0.422% | -0.422% | +1.780% |
| import_seconds | -0.748% | -5.962% | -4.126% | -4.126% | -3.636% |
| init_seconds | +4.049% | +1.644% | -2.273% | +1.644% | +1.106% |
| postHistoryWholeFilesystemBytes | +0.150% | +0.005% | +0.000% | +0.005% | +0.052% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | +0.206% | +2.781% | -0.673% | +0.206% | +0.761% |
| restore_seconds | +1.078% | -5.630% | -5.722% | -5.630% | -3.477% |
| total_import_fork_read_seconds | +1.223% | -4.767% | -6.690% | -4.767% | -3.469% |
| warm_fork_seconds | +2.764% | +2.822% | -5.424% | +2.764% | -0.022% |
| warm_read_seconds | -3.815% | +3.591% | -3.051% | -3.051% | -1.147% |
| warm_total_seconds | +1.855% | +2.932% | -5.094% | +1.855% | -0.167% |
| wholeSampleSeconds | +1.243% | -3.213% | -5.313% | -3.213% | -2.466% |
| write_seconds | -4.956% | +7.816% | +0.593% | +0.593% | +1.016% |

### inventory-to-admission

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | -0.163% | +0.174% | +0.087% | +0.087% | +0.033% |
| checkpoint_seconds | -1.564% | +2.636% | +0.277% | +0.277% | +0.435% |
| first_fork_seconds | -2.139% | -0.060% | +7.629% | -0.060% | +1.725% |
| first_read_seconds | -1.744% | -3.963% | -5.824% | -3.963% | -3.858% |
| import_seconds | -0.102% | +2.193% | +6.264% | +2.193% | +2.752% |
| init_seconds | +5.382% | +14.346% | +4.398% | +5.382% | +7.951% |
| postHistoryWholeFilesystemBytes | -37.149% | -37.117% | -37.107% | -37.117% | -37.124% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | +143.092% | +148.615% | +143.475% | +143.475% | +145.048% |
| restore_seconds | -25.270% | -16.341% | -14.874% | -16.341% | -18.962% |
| total_import_fork_read_seconds | -0.950% | +0.978% | +5.997% | +0.978% | +1.967% |
| warm_fork_seconds | -6.060% | +2.303% | +9.031% | +2.303% | +1.569% |
| warm_read_seconds | +7.011% | +1.897% | -4.295% | +1.897% | +1.432% |
| warm_total_seconds | -4.355% | +2.245% | +7.135% | +2.245% | +1.565% |
| wholeSampleSeconds | -8.060% | -2.463% | +0.482% | -2.463% | -3.413% |
| write_seconds | +1.760% | +0.594% | +0.043% | +0.594% | +0.796% |

### main-to-admission

| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |
|---|---:|---:|---:|---:|---:|
| activeWholeFilesystemBytes | +0.000% | +0.271% | +0.087% | +0.087% | +0.119% |
| checkpoint_seconds | +0.092% | +4.183% | +1.371% | +1.371% | +1.867% |
| first_fork_seconds | +1.284% | -3.521% | -4.790% | -3.521% | -2.377% |
| first_read_seconds | +5.235% | -5.056% | -6.222% | -5.056% | -2.147% |
| import_seconds | -0.849% | -3.900% | +1.880% | -0.849% | -0.984% |
| init_seconds | +9.649% | +16.226% | +2.025% | +9.649% | +9.145% |
| postHistoryWholeFilesystemBytes | -37.054% | -37.114% | -37.107% | -37.107% | -37.092% |
| restore_cleanup_seconds | unavailable | unavailable | unavailable | unavailable | unavailable |
| restore_read_seconds | +143.594% | +155.529% | +141.837% | +143.594% | +146.912% |
| restore_seconds | -24.465% | -21.051% | -19.745% | -21.051% | -21.779% |
| total_import_fork_read_seconds | +0.261% | -3.835% | -1.094% | -1.094% | -1.571% |
| warm_fork_seconds | -3.464% | +5.191% | +3.117% | +3.117% | +1.547% |
| warm_read_seconds | +2.928% | +5.556% | -7.215% | +2.928% | +0.269% |
| warm_total_seconds | -2.581% | +5.243% | +1.678% | +1.678% | +1.396% |
| wholeSampleSeconds | -6.917% | -5.597% | -4.857% | -5.597% | -5.794% |
| write_seconds | -3.283% | +8.457% | +0.636% | +0.636% | +1.821% |

## Limitations and decision

The predeclared ≥10% median restore threshold is met in this one many-reuse screen.
This is **not** a completed promotion gate: unique4096/10000, alias-only, over-key
capacity, x2 crossover, history and eligible≥64KiB inventory controls are not yet
measured in this three-pin route. Adjacent order, mixed large/small and nonempty
initial-cache conditions remain outside this finite screen too. Reverse-Latin
confirmation requires a separate reviewed decision; none is bundled into this run.

Preserve the negatives: inventory→admission whole pair3 is+0.482%; warm-fork
median is+2.303% and first-fork geometric mean+1.725%. Main→admission checkpoint
median is+1.371%, warm-fork median+3.117%, and active Used median+0.087%.
The post-history Used reduction is an observed whole-filesystem result, not by
itself a count of cache hits, clone syscalls, unique extents or exclusive cache cost.

Only3 same-host trials per pin. No statistical significance, independent-host
generalization or whole-run p95/p99 claim. Two restore operations per screen
sample are dependent; their small count does not support p95/p99 estimates.
All pairs, original failure evidence and phases are retained rather than selecting
only faster rows or resetting order after a loss.

## Reproducible evidence

[`data/stress-20261026/cache-independent-4k-x8/`](data/stress-20261026/cache-independent-4k-x8/)
contains the entire original artifact plus `audit/` manifests, source/hash audit,
original and corrected summaries, failed-step log, exact original tools and
corrected post-hoc tools. `posthoc-provenance.json` binds all hashes, the failed
run conclusion and the no-rerun/no-raw-modification facts.
