# 2026-10-26: six complete experiments, no automatic promotion

This is a **small report/provenance publication**, not publication of the prepared
raw tar.gz blobs. Complete raw evidence is currently in each linked public Actions
artifact; [hash manifests and retention status](data/stress-20261026/evidence-manifests/README.md)
make that distinction explicit. Durable compressed archive publication is pending.
Previously published ordinary/128-cycle reports and flat raw evidence are unchanged.

| Separate experiment | Correctness | Performance interpretation |
|---|---|---|
| [Unique4096](STRESS-CACHE-UNIQUE-4096-RESULTS.md) | 3 canaries +9 samples pass | No >5% median restore/whole loss; near-zero restore is not a speedup. |
| [Unique10000](STRESS-CACHE-UNIQUE-10000-RESULTS.md) | 3+9 pass | **Small-admission gate FAIL:** inventory→admission restore median+14.525%. |
| [Eligible64KiB screen](STRESS-CACHE-LARGE-64K-RESULTS.md) | 3+9 pass | Main→inventory restore−39.570%, whole−21.361%; admission edge slightly slower. |
| [Long mounted directory pressure](STRESS-CARGO-LONG-DIRECTORY-PRESSURE-RESULTS.md) | All16 pass | Mixed tails: whole−1.913%/−0.208%; inc1 rename p99+3.723%, read p99+5.403%. No broad win. |
| [Inventory reverse](STRESS-CACHE-INVENTORY-REVERSE-RESULTS.md) | 3+9 pass | Benefit signal, **noise-review trigger:** same-runtime-source restore+19.424%, whole+9.987%. |
| [Identical binary calibration](STRESS-CACHE-IDENTICAL-BINARY-CALIBRATION-RESULTS.md) | 3+9 pass | Median identity/benefit gates pass, but restore noise pair+6.573% and off-path scatter remain. |

Calibration main→copy1/2 restore medians−40.976%/−40.637%, whole−18.046%/−20.615%.
Those arms share the same THREE baseline observations, not six independent pairs.
Identical-copy median noise is+0.574% restore/−2.441% whole; one restore pair is
outside±5%. Copy1 also has a warm-fork pair+84.840% and first-fork pair+37.893% versus
main. All pairs/phases are shown, not hidden behind passing medians. No automatic
repeat, stability claim or main promotion follows. The earlier failed admission
control remains binding and is not rescued by inventory-only large-file gains.

These are separate fixed-pin workloads/orders and limited same-host samples:
do not pool their ratios or claim independent tail trials. Operation intervals in
the long-pressure report are Python wrapper wall times, not individual syscalls.
Full-tree/exact-ns/hardlink/content oracles and all resource limits remain intact.

## Current status after these experiments

A separate **deliberate reviewed decision**, after code and evidence review,
promoted only inventory candidate `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` to
Sprig main. At this update (2026-10-26 11:43 UTC), the actual
[main CI40316978257](https://github.com/M4n5ter/sprig/actions/runs/40316978257)
is pending; source-branch validation is not substituted for that run. This is not
a claim of new human review or fresh owner approval. The historical experiment
reports, source pins, failed controls and noise/scatter remain unchanged. No
small-admission f481 or directory candidate dfee was promoted by this decision.
“No automatic promotion follows” remains true: the calibration did not trigger
a merge or rerun on its own.
