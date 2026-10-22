# CAS/Overlay upper-absence certificate results

**The speed + storage + basic-capability goal is still not met.** Distributed and recurring history capture avoids repeated lower-tree traversal, but hotset exposes a serious deep-path inventory/recheck cost. We report that failure rather than selecting the successful cases. This is an experimental adapter, not production Sprig or feature parity.

[Full run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39812096410), frozen revision `870383c2b6b26a834e9b45e9eda0b0ac236a5386`, production library `22e6e4c289be67b78d39a7eae157bfa3219d23a4`, comparator `2aaf2552ce21154928b9f9c83582e41a637f5910`. Ubuntu 24.04, AMD EPYC 9V74, one temporary runner, three alternating paired repetitions. All 42 records, 1,800 full historical snapshot readbacks and normal cleanup checks passed. [Full raw, per-step ledgers, hashes, environment and summaries](measurements/2026-10-22-cas-certificate/).

The [frozen measurement boundaries](feasibility/CAS-MEASUREMENT-BOUNDARIES.md) and [previous publication result](CAS-PUBLICATION-RESULTS.md) remain applicable and unchanged. CLI startup, capture and conservative fsync remain charged versus persistent SDK calls and Disposable synchronous=OFF. These are not equal-durability or pure API comparisons. Software/runtime installation is excluded from preparation; application initialization is included. First use is not verified cold cache. Separate 16 MiB FUSE content caches per view are not total RSS limits. Metadata-only branching remains unavailable, not simulated.

Only capture implementation changed: [certificate contract](feasibility/cas-projection/CERTIFICATE.md). Complete native-upper inventories and clean ancestor flags allow immutable absent prefixes to be reused; uncertain/redirect/opaque cases retain kernel-view fallback. Existing publication and all performance operations remain unchanged. Independent full-capture oracle checks pass in 11 functional cases, including redirect to a base-existing prefix. The root opaque=x flag was read back after mount and confirmed present; this view reused zero certificate subtrees. Initial views reused six files and two directories. No production source changed.

## Time medians

Milliseconds; per-sample phase sums are computed before taking medians. Preparation is application initialization + import + first writable-view creation + verified full read. Warm is second writable-view creation + verified full read. Both active views are retained.

| Case | CAS preparation | Comparator preparation | CAS warm | Comparator warm |
|---|---:|---:|---:|---:|
| identical | 385.2 | 526.5 | 147.3 | 189.3 |
| unique | 1831.1 | 1946.8 | 170.8 | 702.3 |
| mixed | 1737.3 | 1591.1 | 169.2 | 585.3 |
| insert | 519.4 | 586.6 | 147.3 | 189.4 |
| history-distributed | 475.7 | 439.3 | 56.4 | 69.2 |
| history-hotset | 481.0 | 452.0 | 56.9 | 76.8 |
| history-recurring | 476.7 | 457.2 | 54.2 | 78.7 |

CAS has lower preparation medians in three of seven cases and lower warm medians in all seven. These do not imply an overall win.

| 100-edit history | CAS write + checkpoint | Comparator | CAS checkpoint alone | Comparator checkpoint alone |
|---|---:|---:|---:|---:|
| history-distributed | 3306.7 | 2217.9 | 2736.3 | 466.7 |
| history-hotset | 18657.7 | 2312.0 | 18030.8 | 532.8 |
| history-recurring | 2404.0 | 2640.9 | 1692.2 | 305.9 |

Recurring is modestly faster including writes, but distributed remains slower and hotset is about 8.1 times slower. Hotset checkpoint alone is consistently 17.90–18.05 seconds across three repetitions. Its capture phase is 16.35–16.43 seconds: native certificate inventory takes about 7.1 seconds and final recheck about 7.15 seconds. Publication is only 1.11–1.18 seconds. This localizes the new bottleneck without pretending instrumentation intervals are kernel CPU time. Inclusive walk and its subcategories must not be summed twice. Timing instrumentation remains charged. Earlier runs used different hosts, so before/after observations are not same-machine causal speedups.

## Physical storage medians

Decimal MB. Whole-filesystem Used counts Data + Metadata + System with live services/workspaces, not `du` or FIEMAP union. Comparator whole-runtime includes image/software, Docker/containerd persistent roots, writable overlays, volumes, SDK home and logs. Runtime-ready increment subtracts measured pre-application software/runtime baseline, but is **not exact application-data-only**. CAS includes objects, every manifest/commit, both upper/work trees and logs. Executables/build inputs and volatile host/RAM state are excluded for both. These columns cannot establish equal-capability or equal-durability storage superiority.

| Case | CAS whole-FS MB | Comparator whole-runtime MB | Comparator runtime-ready increment MB |
|---|---:|---:|---:|
| identical | 1.274 | 99.631 | 13.685 |
| unique | 109.941 | 204.825 | 118.915 |
| mixed | 82.526 | 178.287 | 92.348 |
| insert | 10.482 | 103.367 | 17.396 |
| history-distributed | 5.865 | 104.079 | 18.104 |
| history-hotset | 9.871 | 104.002 | 18.092 |
| history-recurring | 2.249 | 103.498 | 17.576 |

CAS whole-FS growth is below the comparator runtime-ready increment in all seven cases under these boundaries, not a claim about exact app-only usage or full product parity. Insert remains the frozen aligned 4 KiB recipe, not arbitrary-offset validation.

## Limits and next evidence

The prototype still lacks complete branch APIs, production workspace lifecycle, crash recovery, GC/export and hostile-owner safety. Successful bounded merge/publication checks do not fill those gaps. The hotset inventory/recheck issue must be investigated before claiming a broadly faster capture path. Full raw results above remain frozen; the earlier single smoke and phase diagnosis are not pooled into these medians.
