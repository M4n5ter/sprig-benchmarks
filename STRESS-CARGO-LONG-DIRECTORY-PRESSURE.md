# Separate long mounted directory-pressure experiment

**Preparation only until reviewed tests, exact product CI and explicit dispatch.**
This is not a replay of the old128-cycle result and not promotion evidence. The
candidate's debug directory controls retain measured fallback costs; real mounted
release behavior, Cargo whole time and latency tails still need this experiment.

## Immutable experiment identity

- Profile `normal-rename2-1024-v2`, pressure schema
  `sprig-cargo-normal-pressure-v2`; helper `stress_cargo_pressure_long.py`.
- Baseline: `b300693e01c652c1a9631c61b7a439892d8f75cd`.
- Candidate: `dfee7e4e9ee223f25d141d2e05d3cfcdc6c9269f`.
- Source/binary identities are enforced in the workflow, JS product/prerequisite
  gates and independent Python summary. A new pin cannot be relabeled as an old
  profile. Default `ordinary` and `normal-rename2-v1` retain4ef→b300 pins; the old
 128-cycle helper itself remains byte-for-byte unchanged. Old results are never
  rewritten or pooled with the new profile.
- Both primary products are untraced. `SPRIG_LIFECYCLE_TRACE` and
  `SPRIG_WRITABLE_DIAGNOSTICS` are refused before sampler setup. Helper wall-time
  interval recording is symmetric workload instrumentation, not a product trace
  or proof of internal fsync/journal causality.

## Fixed normal workload and honest clocks

Two joined workers, each1024 fixed cycles in disjoint directories. A cycle is
rename-away →64-byte write →read/compare →metadata witnesses →rename-back.
The unchanged source pressure shape retains2048 unrelated files,16 moving payload
files, hardlink and symlink witnesses with exact mode/mtime and final bytes.
There are4096 rename and2048 each write/read/metadata timings per sample,10240
operation intervals in total. No fault, quota, kernel-error or destructive test.

One shared `CLOCK_MONOTONIC` origin is recorded as an unsigned64-bit decimal
**string**, avoiding JavaScript integer rounding for absolute nanoseconds. Every
operation records a safe-integer relative start/end/duration. Validators require:

- Exact worker IDs,1024 completed cycles and5120 events per worker.
- Contiguous iteration and exact five-operation order, no missing/duplicate event.
- Nonnegative safe integers, start≤end, exact duration=end−start, intervals inside
  the worker lifetime, and each next operation starting after the previous end.
- Per-operation duration arrays exactly reproduce the interval stream.
- Positive worker-lifetime overlap; this does **not** claim every syscall overlaps.
- Exact clock identity/origin format, fixed helper hash and fixed experiment spec.

The1024-cycle count is8× the old count, but “longer” does not demonstrate steady
state/stationarity. There is no adaptive duration, warm-up deletion or discarded
outlier. Workload setup/final verification and event serialization remain charged
to the pressure phase/whole sampler, not individual syscall timing. Shared-clock
interval overlap supports descriptive concurrency correlation, not causal blame.

## Full correctness and finite balanced matrix

The pressure stage remains after `edit_execute`, before the complete checkpoint
oracle. Cargo build phase timers remain separate. All pressure observations are
retained inside `pressure-rename2/observations.json`, bound to helper/raw hashes
and the complete checkpoint/restored oracle; every witness remains covered.
The unchanged Cargo acceptance still checks all17 package build/Fresh states,
program/generated artifacts, full tree/exact-ns/internal hardlinks, retained source
and main view, native compiler exit/lifetime and normal cleanup.

Four balanced pairs per incremental mode,16 samples total: inc0 AB/BA/AB/BA,
inc1 BA/AB/BA/AB. All8 inc0 correctness/archive gates precede inc1. Any failure,
missing/malformed timestamp, wrong pin, partial matrix, changed helper or uncertain
cleanup suppresses every comparison; all raw failed evidence is retained. No
replacement sample or automatic retry. The old ordinary/128 profile gates remain
separate. Native cache data are a different experiment and are not pooled here.

## Existing resource/output bounds stay intact

Existing Ubuntu runner, Cargo jobs2, one measured job, fresh symmetric4GiB images,
original40min admission clock and45min hard job cap. Keep the existing180sec
minimum next-sampler admission plus300sec cleanup reserve. Keep the128MiB
pressure capacity reserve. No automatic8GiB fallback or deadline expansion.
The old128-cycle stage overlapped roughly0.4–0.6s;8× work is an estimate of a few
seconds, not guaranteed. Stop normally if resource/time admission is insufficient.

The new helper additionally caps one serialized report at4MiB without increasing
any transport/collector limit. A structural upper-bound test uses maximum-width
safe-integer values for every interval/duration and verifies it fits4MiB. It also
budgets two pressure copies, escaping overhead and32MiB other evidence against
the existing128MiB Node `maxBuffer`. The collector retains its precise filenames
and depth allowlist (not a new byte-limit relaxation); it validates the explicit
profile/helper identity and preserves partial failures. Raw observations remain
charged to full-tree/space accounting.

Four per-pin repeats do not establish whole-run p95/p99 or significance. Report
all whole/phase paired ratios and all dependent per-sample operation quantiles,
plus timestamp/order/overlap provenance. Do not combine phase times by subtraction
or market4096 dependent operations as4096 independent trials. A metadata/rename
median win with worse p99 must remain a negative tail result.

## Root-owned offline validation

No local Rust build or real Docker/FUSE workload is required for these guards.
After freezing, run serially:

```sh
python3 feasibility/test_stress_cargo_pressure_long.py
python3 feasibility/test_stress_cargo_pressure.py
python3 feasibility/test_stress_cargo.py
python3 feasibility/test_stress_cargo_ab_summary.py
python3 feasibility/test_stress_cargo_collect.py
python3 feasibility/test_stress_cargo_capacity.py
python3 feasibility/test_stress_runtime_storage.py
node feasibility/test_stress_cargo_pressure_long.mjs
node feasibility/test_stress_cargo_own_ab.mjs
node feasibility/test_stress_cargo_compare.mjs
node feasibility/test_stress_cargo_layerfs.mjs
```

Then syntax/YAML/authored whitespace checks and independent review. Exact candidate
standard CI, reviewed benchmark publication, native-job terminal status and a
separate root dispatch decision are still required before the mounted experiment.
