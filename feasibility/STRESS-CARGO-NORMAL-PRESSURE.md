# Separate ordinary two-worker pressure profile

`normal-rename2-v1` is an explicit workflow-dispatch choice. Default `ordinary`
remains the repeated Cargo experiment. Never pool profiles or interpret stressed
whole wall/space as directly comparable with the old unstressed metric. Both
fixed Sprig pins receive the exact same helper bytes/spec and four balanced pairs
per incremental mode. This profile is **not** a fault/negative/kernel reproducer.

## Fixed normal workload

After the clean/noop/edit Cargo phases, but before compiler quiescence/checkpoint,
one Python command runs two normally joined threads against disjoint worker paths
inside the same writable workspace. Each worker retains1,024 unrelated64-byte
files plus an8-file moving directory, a mutable64-byte file, a relative symlink,
and an ordinary two-name hardlink witness (0640; exactmtime1700000000123456789).
Each worker completes exactly128 cycles: directory rename,64-byte write, exact
readback, metadata/hardlink/symlink validation, reverse rename. All preparation,
verification and observation output remain charged in `normal_pressure` and whole
sampler wall. Existing Cargo phase boundaries are unchanged and exclude this
separate stage; no compiler jobs or extra background compiler are started.

Every operation duration is retained:512 renames,256 writes,256 reads,256 metadata
checks per sample. Timing uses monotonic nanoseconds with a reported overlapping
worker-lifetime interval; this demonstrates concurrent workers, not simultaneous
overlap of every syscall. Per-operation nearest-rank p95/p99 are descriptive
**dependent operations within one sample**. Do not pool all operations into an
independent sample count or use these as whole-task latency tails. Four paired
end-to-end repeats still cannot estimate end-to-end p95/p99 or significance.

The raw observation JSON is retained inside `pressure-rename2/observations.json`
and the complete pre-checkpoint/full-restore oracle. Its bytes/hash, helper stdin
hash, exact witness metadata, all2,048 unrelated files, internal hardlinks and
symlinks are independently checked in the summary. No tree exclusions, deletion
before space accounting, nanosecond rounding or reduced oracle is introduced.
The source helper's SHA256 and full spec bind both modes, variants and all rounds.
An ordinary prerequisite cannot admit pressure and vice versa.

## Budget and stopping

Same existing Ubuntu24 runner,45-minute job,40-minute absolute admission deadline,
180second expected work +300second normal-cleanup reserves, jobs2 Cargo, and fresh
symmetric4GiB images. In addition to the unchanged capacity guard, this profile
requires128MiB **extra available space** for its ~8MiB allocated tiny-file payload
and metadata/generation overhead; this is conservative admission, not a guarantee.
No8GiB retry, quota fill, mmap/fault injection, forced teardown, signal, detached
worker, privilege/runtime/security/billing change or automatic run follows.

A worker exception or incomplete count fails the sample after normal thread join;
uncertain transport still follows the original no-retry/no-forced-cleanup rule.
Any failure stops the entire matrix, preserves attempted records/logs and yields
no performance ratios. Whole filesystem Used continues to charge pressure files,
observations, compiler/runtime/image/target/cache/history and logs. Existing full
Cargo correctness gates, exact restored oracle before execution and natural
compiler lifetime/cleanup gates remain mandatory.

Planning estimate: one ordinary16-sample matrix plus2,048 tiny-file creates and
128cycles per worker/sample; measured cost is not yet known. The original admission
checks, not optimistic estimates, decide whether the next sample may start.
This is a separately reviewed opt-in run after the ordinary matrix terminates;
never dispatch it in parallel with that experiment.

## Root serial offline validation (no Rust/Docker/mount)

```sh
python3 feasibility/test_stress_cargo_pressure.py
python3 feasibility/test_stress_cargo.py
python3 feasibility/test_stress_cargo_ab_summary.py
python3 feasibility/test_stress_cargo_collect.py
node feasibility/test_stress_cargo_own_ab.mjs
node feasibility/test_stress_cargo_compare.mjs
node feasibility/test_stress_cargo_layerfs.mjs
python3 feasibility/test_stress_cargo_capacity.py
python3 feasibility/test_stress_runtime_storage.py
node --check feasibility/stress_cargo_compare.mjs
git diff --check
```

The pressure-helper test uses only ordinary tempfile I/O (~8MiB,2threads) and
explicit witness validation; it does not compile Rust or exercise a real mount.
Publication/dispatch requires ROOT's reviewed GO. This protocol does not assert
that the pressure matrix has run or that either variant is faster.
