# Finite writable wall/thread-CPU observation canary

**Local preparation only until independent review, root serial tests and explicit
publication/dispatch GO.** Registered `cargo-transport.yml` (ID395659725) is reused
only on the experimental branch with this entirely dedicated body. Default main,
`stress-ab.yml`, `native-fork-ab.yml` and the inactive historical fault route are
untouched. No intentional failure, quota/kernel-fault test or security change.

## Identity and finite stopping rule

One source `73a462885c7b5bc88d64764152ab8fab08eba055`, parent
`0f00ac4afbfc42b76c63a31833eabb07b82152f2`, algorithm base
`b300693e01c652c1a9631c61b7a439892d8f75cd`. This is not literal original b300 ELF
and not the dfee algorithm. The source's actual standard CI40317373367 passed;
that is not a mounted diagnostic-canary result.

Exactly ONE release build/ELF is used by **four fresh inc0 samples**:
**off/on, then on/off**. Off means diagnostic environment variable absent; on
means exactly `SPRIG_WRITABLE_DIAGNOSTICS=1` only for product CLI children (and
therefore their ordinary server descendants). Docker/compiler processes do not
receive it. Inherited lifecycle/writable trace variables and old matrix selectors
are refused. No primary trace-off guard, pin-distinctness check or old schema is
relaxed. Dedicated manifest/run/sample/audit schemas are explicit.

Stop after four samples OR the first budget/admission/clock/CPU/coverage/output/
correctness/transport/normal-cleanup failure. Completed and failed raw records
remain; not-run positions are reported. No full matrix, inc1 product sample,
automatic retry, shortened window, wall-only fallback or promotion is authorized.
Two paired overhead observations cannot establish equivalence or stable overhead.

## Ordinary workload and resources stay fixed

Unchanged DAG16 Cargo lifecycle, exact full-tree paths/content/mode/nanosecond/
hardlink/symlink/checkpoint/restored/build witnesses. The exact long helper SHA is
`58e5171ba44661a00065297155025a0c75839892cb5c21c770d22e84f4e0b501`:
two workers×1024 cycles, all10240 Python operation-wrapper intervals retained.
These are wall intervals around wrappers, not individual kernel/FUSE syscalls.

Existing Ubuntu24 runner/jobs2,45min job and original40min admission clock include
all setup; per-sample180s operation/300s cleanup admission remains unchanged.
Four fresh4GiB images,128MiB pressure reserve, no8GiB fallback. The unchanged
common **external inc0+inc1 capacity pilot is setup only**, not a product trace or
additional measured sample; no pilot timings/cache are pooled into results.

Normal cooperative compiler shutdown and15s product-exit wait are unchanged.
Unknown exec/cleanup outcomes retain state; no signals, force/lazy unmount,
timeout extension or replay. Runtime/image cleanup uses original strict helpers.
Disposable image removal follows normal detached-loop verification and durable
raw reports/full archived logs. Failure images/evidence are not pruned.

## Exact clock, full logs and pressure-generation binding

Before pressure, ordinary Docker exec in the SAME bound compiler generation
records `/proc/self/ns/time`, `time_for_children`, raw `timens_offsets`, positive
nominal monotonic/thread-CPU resolutions and a monotonic sample bracketed by
host-before/host-after CLOCK_MONOTONIC. All four namespace IDs and normalized
offsets must match. Host/container proof, its complete raw command stdout and
pressure command share exact containerId/generation; the helper origin follows
the completed sandwich. Join absolute-u64 timestamps only in Python, not JS
floats or64KiB runtimeLogs previews. Nominal resolution is not verified precision.

All five expected server source logs are copied completely after normal cleanup.
Their actual source/archive sizes and hashes must match, each≤16MiB; controls
must contain no enabled footer, on must contain a complete validated v2 footer.
Only the sole log for `checkpointGeneration.before` is used for pressure analysis.
The ring must satisfy exact calls/retained/overwritten counts, zero wall/CPU
failures, nonsaturated counters, ordered nonoverlapping valid events/totals,
positive CPU resolution and all integer CPU values. Null is never a fake zero.

Full coverage requires first retained start≤earliest wrapper start and a final
successful normal-destroy sync starting AFTER all wrapper ends. Any failed sync
invalidates attribution. Post-pressure oracle work can overwrite the pressure
window; such failure remains inconclusive, never replaced by a shorter suffix.
Fully contained scopes alone contribute CPU totals; boundary scopes are separate,
not prorated. CPU>wall anomalies are reported without clamping.

## Accounting and analysis boundaries

The original active whole-filesystem Used metric remains unchanged. A NEW
post-normal-cleanup observation, before runtime leave/outer unmount, captures
physical Used/free, complete source-log logical and allocated bytes after late
buffered dumps. Source logs are charged inside4GiB. External archives are separate.
Before creating/copying any archive, exact existing named external bytes plus
ALL planned source-file bytes must fit the same1GiB cap with a separate192MiB
reserve for pending standalone sample/audit/driver/summary output and2MiB for
the final collection manifest. The raw sample is bounded128MiB, per-sample audit
1MiB, driver8MiB and final summary16MiB before writes; the reserve is conservative,
not actual Used. A failed preflight creates no archive and keeps all source logs/
image. Source identity/size/timestamps are rechecked, and growth/shrink stops the
bounded stream copy with explicit incomplete/partial-file metadata.
The same192MiB report plus2MiB collection headroom is required before starting
each fresh runtime/sample, so a later archive rejection can still preserve its
failure report within the unchanged budget. Near-cap admission stops before
creating the next image; no attempted sample is silently omitted.
Actual complete named collector inventory still has a≤1GiB cap (including2MiB
manifest reserve); no compressed-size inference or filtered evidence subset.
A cap failure preserves sources and stops, never discards a slow/failed sample.

The summary re-audits standalone raw samples with original full-oracle/archive
validators, exact long pressure observations and strict diagnostic guards before
any pair ratios. It shows each off/on pair/order, whole/phase/shutdown/wrapper
quantiles and space including regressions; phases overlap and must not be added
or subtracted. Scoped wall union avoids double-counting two worker overlaps.
Scan/sync/neither overlap and fully-contained scope CPU are descriptive:
low charged CPU does NOT distinguish storage wait from scheduling/other waits;
no request IDs means no scope ownership claim. Material observation perturbation
limits untraced generalization; small observed differences prove no zero overhead.

## Root-owned offline validation after all files freeze

```sh
python3 -m unittest discover -s feasibility -p 'test_stress_writable_diagnostic*.py' -v
node feasibility/test_stress_writable_diagnostic_run.mjs
python3 feasibility/test_stress_cargo.py
python3 feasibility/test_stress_cargo_capacity.py
python3 feasibility/test_stress_runtime_storage.py
python3 feasibility/test_stress_cargo_collect.py
python3 feasibility/test_stress_cargo_ab_summary.py
python3 feasibility/test_stress_cargo_pressure_long.py
node feasibility/test_stress_cargo_compare.mjs
node feasibility/test_stress_cargo_own_ab.mjs
node feasibility/test_stress_cargo_pressure_long.mjs
```

Plus Python/Node syntax, YAML/bash-run parsing, authored diff checks and independent
source/parser review. Tests use synthetic bytes/tempfiles/mocks only, no Rust,
product, Docker or mounted workload. No new run follows from this document alone.
