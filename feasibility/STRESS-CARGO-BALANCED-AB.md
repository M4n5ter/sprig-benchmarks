# Bounded repeated ordinary Cargo A/B — v2

This experiment extends the prior one-pair-per-mode acceptance without modifying
its Cargo workload, sampler, transport, oracle, compiler image contents, jobs2 or
4GiB geometry. Historical failures and results remain immutable and are not pooled.
The source pins remain baseline `4ef4a90d7ccf5f305416c5374bfc81038f5ca46e`
and candidate `b300693e01c652c1a9631c61b7a439892d8f75cd`.

## Predeclared matrix and order

One existing Ubuntu24 runner, one45-minute job, serial builds and serial samples:

| Mode | Round0 | Round1 | Round2 | Round3 |
| --- | --- | --- | --- | --- |
| incremental0 | baseline, candidate | candidate, baseline | baseline, candidate | candidate, baseline |
| incremental1 | candidate, baseline | baseline, candidate | candidate, baseline | baseline, candidate |

There are16 fresh-image samples: four independent image pairs per mode, with two
pairs per order within each mode. All eight incremental0 records must pass the
full original validator, exact archive and provenance gates before incremental1.
The prerequisite binds v2 schema, full experiment spec, both source/binary
identities, image, fixture, Cargo protocol, resource geometry and original deadline.
A legacy one-pair report cannot admit this series. A second run cannot overwrite
records/reports from a partial first attempt. No best-of selection or adaptive
stopping after favorable results is allowed.

## Resource budget and stops

The first workflow step establishes the same40-minute absolute admission deadline;
the job remains45minutes. Each sample requires180seconds of expected work plus
300seconds normal-cleanup reserve before runtime import and again before sampler
launch. Later rounds/modes never reset this deadline. Previous observed whole
sampler8.5–10.4seconds plus runtime setup14.3–16.8seconds implies approximately
6–8minutes for16 samples, plus setup/build/fixture work (~5minutes previously).
This is a planning estimate, not a deadline guarantee or result.

One new symmetric4GiB image is live at a time; it is disposed only after successful
normal runtime restoration, ordinary unmount/loop-detach verification and durable
raw reports/log archives. The host guard still requires4GiB plus1GiB evidence
reserve. Capacity guards retain all generation/cache/compiler/log charges.
No resize, automatic8GiB fallback, cleanup shortcut, reduced fixture or permission,
billing, runner-class or concurrency expansion. Rust compilation remains jobs2.

Any correctness, provenance, exact-tree/mtime/hardlink, archive, compiler-lifetime,
capacity, deadline or cleanup failure stops the matrix; preserve every attempted
record and error. Missing/uncertain outcomes forbid subsequent samples and forced
cleanup. The always-run summary records missing/failing cells and emits **no ratios**
for an incomplete matrix. Collect/upload still run on failure. A later independent
retry must be disclosed as a distinct run; do not erase the original failure.

## Analysis contract

Each raw sample JSON is SHA256-bound to its comparison record. Python summaries
read those raw reports, preserving integer nanoseconds rather than treating the
JavaScript embedded oracle as exact integer evidence. Present all four paired
candidate/baseline ratios per mode, the geometric mean paired ratio, median ratio,
order-stratified observations, whole sampler and all phase/composite/space
measurements, including every regression. Runtime setup is separate. Nested
phase/composite timers overlap and must not be added. N=4 per product/mode does
not justify p95/p99 estimates, statistical significance or a durable performance
claim; report median and min/max and keep p95/p99 unavailable.

Normal two-worker rename/read/write pressure will be a **separate opt-in experiment
profile/run**, never silently inserted into this ordinary primary comparison.
Both variants must receive exactly the same profile. Pressure witnesses and
metadata remain inside the full checkpoint/restore oracle. Stressed whole-task
wall will not be directly comparable with the historical unstressed metric.
No intentional kernel-fault, mapped-fault, quota or negative harness is added.

## Local check handoff (ROOT runs serially; no Rust)

From this worktree:

```sh
node --check feasibility/stress_cargo_compare.mjs
node feasibility/test_stress_cargo_own_ab.mjs
node feasibility/test_stress_cargo_compare.mjs
python3 feasibility/test_stress_cargo_collect.py
python3 feasibility/test_stress_cargo_ab_summary.py
python3 feasibility/test_stress_cargo.py
python3 feasibility/test_stress_cargo_capacity.py
python3 feasibility/test_stress_runtime_storage.py
node feasibility/test_stress_cargo_layerfs.mjs
# If available: actionlint .github/workflows/stress-ab.yml
# Otherwise parse YAML and inspect pinned action/permissions/time/resource diff.
git diff --check
```

Workflow activation/publication/dispatch belongs to ROOT after review. This document
is a protocol, not evidence that the matrix has run or passed.
