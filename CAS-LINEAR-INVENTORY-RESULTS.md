# CAS/Overlay linear inventory results

**The combined speed, storage and basic-capability target remains unmet.** The depth-related inventory regression is reduced, but distributed and hotset history tasks still lose. Only recurring history is modestly faster including writes. This is a prototype, not production Sprig or feature parity.

[Run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/39816321273), frozen revision `8d00ee96dab58979ae10667d3f64c12903f81b1e`, production library `22e6e4c289be67b78d39a7eae157bfa3219d23a4`, comparator `2aaf2552ce21154928b9f9c83582e41a637f5910`. Same temporary Ubuntu 24.04 runner, AMD EPYC 7763, three alternating paired repetitions per case. All 42 records, 1,800 full historical snapshot readbacks, 11 semantic cases and normal cleanup checks passed. [Complete raw, step ledgers, hashes, environment and CSV](measurements/2026-10-22-cas-linear-inventory/).

The [measurement boundary](feasibility/CAS-MEASUREMENT-BOUNDARIES.md) is unchanged. CAS CLI startup, capture and conservative fsync are charged versus persistent SDK and Disposable synchronous=OFF: this is not equal durability or pure API speed. Preparation includes application initialization but excludes software/runtime installation. First use is not verified cold cache. Two independent FUSE processes have separate 16 MiB content caches; total memory/background compute is not equalized. Unsupported metadata-only branching remains explicitly absent. The performance driver, fixtures and full semantic oracles are unchanged.

Only inventory lookup changed. [The proof](feasibility/cas-projection/CERTIFICATE.md) retains own-directory flags before/after enumeration, immediate-parent child identity linkage, prefix-closed evidence, and final validation of every saved inventory. Restricted openat2 avoids repeatedly opening all ancestors; only ENOSYS permits the equivalent nofollow legacy path. The [prior hotset regression report](CAS-CERTIFICATE-RESULTS.md) and original raw remain intact. These runs used different hosts, so the before/after values are observations, not controlled causal speedup ratios.

## Time medians

Milliseconds. Preparation = application initialization + import + first writable view + verified full read. Warm = second writable view + verified full read. Medians use each sample's phase sum, not summed independent medians.

| Case | CAS preparation | Comparator preparation | CAS warm | Comparator warm |
|---|---:|---:|---:|---:|
| identical | 367.7 | 530.7 | 135.3 | 184.7 |
| unique | 2138.8 | 1861.9 | 163.7 | 650.5 |
| mixed | 2055.1 | 1521.3 | 154.1 | 541.1 |
| insert | 518.5 | 579.4 | 137.4 | 186.9 |
| history-distributed | 538.9 | 458.0 | 61.3 | 77.8 |
| history-hotset | 552.3 | 464.7 | 58.8 | 84.2 |
| history-recurring | 559.0 | 469.7 | 63.0 | 84.3 |

CAS preparation is lower in only two cases; warm view + read is lower in all seven. Neither is a general win.

| 100-edit history | CAS write + checkpoint | Comparator | CAS checkpoint alone | Comparator checkpoint alone |
|---|---:|---:|---:|---:|
| history-distributed | 3374.5 | 2268.4 | 2801.9 | 472.5 |
| history-hotset | 5225.8 | 2328.2 | 4598.8 | 542.5 |
| history-recurring | 2378.4 | 2652.8 | 1682.9 | 309.6 |

Hotset remains about 2.2 times slower including writes, distributed about 1.5 times slower, recurring about 10% faster. Checkpoint alone still loses all three. The previous hotset 18.66-second task is now observed at 5.23 seconds on this different host; that is not a same-machine causal ratio.

### Charged phase diagnostics

Median of per-repetition 100-checkpoint phase totals, milliseconds. These wall-time instrumentation intervals remain inside the score, not subtracted estimates.

| Phase | Distributed | Hotset | Recurring |
|---|---:|---:|---:|
| Capture total | 1171.88 | 2941.46 | 371.70 |
| Publication total | 1244.22 | 1281.33 | 931.27 |
| Inventory (inside capture walk) | 23.44 | 447.12 | 9.38 |
| Final validation (inside capture) | 79.47 | 475.91 | 70.83 |
| Content hash/put (inside capture walk) | 617.93 | 409.77 | 27.45 |

Do not sum inclusive capture/walk intervals with their components. Hotset no longer spends roughly 14 seconds in inventory and final recheck; substantial capture and publication work remains. The raw includes every other phase and sample.

## Physical storage medians

Decimal MB, whole-filesystem Used Data + Metadata + System with both active views retained. Comparator whole-runtime includes image/software, Docker/containerd persistent data, writable overlays, volumes, SDK home and logs. Runtime-ready increment subtracts the measured pre-application runtime baseline, but is **not exact application-data-only**. CAS includes objects, all revisions/commits, both upper/work trees and logs. Executable/build inputs and volatile host/RAM state are excluded on both sides. Software baseline and capability/durability differences prevent interpreting these columns as an equal-product net-data proof.

| Case | CAS whole-FS MB | Comparator whole-runtime MB | Comparator runtime-ready increment MB |
|---|---:|---:|---:|
| identical | 1.274 | 99.594 | 13.718 |
| unique | 109.941 | 204.861 | 118.944 |
| mixed | 82.559 | 178.315 | 92.340 |
| insert | 10.482 | 103.330 | 17.392 |
| history-distributed | 5.833 | 104.010 | 18.072 |
| history-hotset | 9.871 | 103.920 | 18.096 |
| history-recurring | 2.249 | 103.547 | 17.641 |

CAS whole-FS growth is lower than the stated runtime-ready increment in all seven cases, not an exact app-only or feature-parity claim. Insert remains the frozen 4 KiB-aligned recipe.

The adapter still lacks complete branch APIs, production lifecycle, crash recovery, GC/export and hostile-owner safety. Production was unchanged. Future work must preserve immutable-history/publication correctness and measurement boundaries while addressing the remaining costs; a selective warm result does not satisfy the original goal.
