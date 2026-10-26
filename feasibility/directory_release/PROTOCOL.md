# Three-variant release-core protocol — preparation only

**Status:** no publication or dispatch authorized. The manifest remains deliberately non-executable until root approves actual successor inventory and all final helper hashes. Benchmark-repository edits belong exclusively to the benchmark owner.

## Purpose and frozen inputs

Measure the existing child-directory-count implementation and its separately validated narrow-parent successor without conflating either with mounted or whole-task performance.

| Label | Exact production source | Role |
|---|---|---|
| baseline | `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` | Main baseline; never resolve a moving branch at execution time |
| count | `104497aefcadc41b1528d7263039c977b77305f8` | Original measured implementation, including its 240-byte debug Node cost |
| narrow | `5ef2539af3f07b0a2fc87b3d02f7324a827e8798` | Separate narrow-parent successor; never replace or relabel the original count evidence |

Identical test-only modules:

- `writable_directory_benchmark.rs`: SHA-256 `68fc060a91ca5c28b7d45f986c9755faf54c856a385067ddb6129f3628ed32b0`.
- `writable_directory_lifecycle_benchmark.rs`: SHA-256 `b61bc612d4e1de5345e608db55bc40c3acf3a6096560661d1ae5b9e166c2db84`.
- Append-only suffix `writable-test-suffix.txt`: SHA-256 `41f7a6959872da9705584a263ad8e25c117c3dea9a150078a2a8999e22c340c0`.
- Existing reference validators: SHA-256 `dfab5e0c62e79a03460254aa187536b9192b109eef16bc2615f4c51a1b33e3d5`.

The two release modules are byte-identical across all three variants. Relative to the accepted debug inputs, exactly three untimed lines widen private parent IDs with `u64::from`: two original-scan oracle comparisons and one topology-fingerprint field. This is an identity conversion for the baseline/count u64 field and lossless widening for the narrow u32 field. The exact diff and original hashes are retained; all fixtures, timed code and sample counts remain unchanged. The suffix is byte-identical to the debug comparison. They use real API operations or validated initial manifests and the original full-arena oracle. No counters, barriers, recovery behavior or production file bytes are changed for measurement. Adding test modules can influence code layout; this remains an instrumented core measurement.

## One isolated job

- Ordinary manual source-benchmark route only after root review; no reuse of a denied lifecycle-fault route. If the owner chooses the registered `production-ab.yml` route, replace its historical experimental-branch body entirely: its old 90-minute cap and projection kernel gates must not run. Default main remains untouched.
- Existing `ubuntu-24.04`, `CARGO_BUILD_JOBS=2`, shared `sprig-stress-pilot` concurrency group, **45-minute job**, **40-minute setup-inclusive admission** and **1 GiB complete evidence** limits.
- No parallel timing, Docker, mount, image, fault injection, real Cargo workload, paid setting or permission change.
- Record `time.monotonic()` and Linux boot ID **before checkout/fetch/toolchain setup**, then preserve that same clock file through all build and sample steps. Helpers reject future/reset/incompatible-host clocks; the workflow must not recreate the start clock.
- One exact source checkout with detached worktrees is sufficient. Each variant has its own fresh compiled target directory; do not share root artifacts or overwrite retained evidence. Registry/git download caches may be reused. Dependency compilation is allowed remotely within the existing job envelope, not locally on the space-constrained workstation.
- Capture host/CPU/kernel/filesystem, exact rustc/cargo verbose version text and executable hashes, git/source/module/helper/manifest hashes, timestamps and source state. Use the root-selected exact Rust 1.99.1 toolchain and verify the same actual compiler for all three variants.

Build all three serially using ordinary `cargo test --release --locked --features projection --lib --no-run --message-format=json --verbose`, with two compiler jobs. The build helper instruments only the two test modules plus exact suffix, proves the original source prefix unchanged, captures a fresh root compiler artifact (`fresh:false`) and exact selected-source dep-info, requires ordinary release settings (`opt_level=3`, debug assertions and overflow checks disabled), and retains an immutable copied ELF. Exact embedded test lists must match each variant's frozen inventory (baseline 65, count 68, narrow 70 expected; embedded narrow inventory still requires actual validation). Actual ELF hashes must differ across all three variants. Do not treat Cargo's manifest path alone as provenance.

No build or root-artifact evidence from the rejected shared-target debug freshness collision is reused. The production candidate stays separate from benchmark-only instrumentation.

## Canary, then full comparison

The runner predeclares **411 process positions** before measurement. Failed and not-run positions remain in the report.

1. **15-process canary:** the existing three attribute controls (`nested-2048`, `true-tiny`, `budget4-over`) and two lifecycle controls (`tiny`, `retired-history`), one process per variant in baseline/count/narrow order. This verifies protocol, oracle, fixture/topology identity, memory readouts, process cleanup and report schemas. It is not included in performance estimates.
2. **396-process full run:** all 18 attribute profiles and four lifecycle profiles from the accepted debug runner. For each profile, run six blocks in this fixed order:

   `ABC, CBA, BAC, CAB, ACB, BCA`, where A=baseline, B=count, C=narrow.

   Every pair has three A-before-B and three B-before-A observations; each variant appears twice in each position. Each block contains all three variants on the same host, giving six direct ratios for each of baseline→count, baseline→narrow and count→narrow. No cross-run or transitive speedup inference is needed.

Full execution is forbidden unless all 15 canary processes pass. A failure stops later admission; it does not trigger a new canary, change the sample order, remove a control or discard the failure. All 396 full positions must pass before a complete three-way summary is produced. Per-profile partial data remain raw evidence, not accepted comparisons.

Attribute instrumentation is unchanged: 32 batches ×100 calls per case, root/hot/wide/flat, original oracle outside timers. Lifecycle instrumentation is unchanged: eight one-call initialization/replay samples, and 12 batches ×8 calls for eight mutation cases. Real initialization retains durability barriers; buffered mutation excludes sync. RSS/HWM, exact Node size/alignment and occupied node-value byte counts are read outside timers. Subtree topology, replay state and fixture fingerprints must match across variants while memory layout is allowed to differ.

## Bounds and cleanup

- Each process: 120 seconds, isolated owned process group, one test thread. Stdout/stderr are drained through the shared bounded pipe capture, not redirected into an unchecked growing file; each process log retains at most 1 MiB and any overflow fails the process.
- Before every process, require the full 120-second sample allowance plus 10-second cleanup and 60-second finalization reserve before the shared 40-minute deadline. Setup/build time is never reset or excluded.
- Keep at least 1.5 GiB filesystem free space throughout. Complete evidence, including logs, reports, receipts and copied ELFs, is capped at 1 GiB, charging max(logical bytes, allocated bytes) per file plus allocated directory blocks so sparse files cannot evade the cap; reserve 8 MiB for failure/final summary writes. Every per-process JSON report remains capped at 1 MiB.
- A process exiting with live owned descendants fails. Stop/settle only that process group, with bounded TERM/KILL cleanup. Do not kill unrelated jobs.
- The frozen instrumentation removes only successfully verified owned generation fixtures. Failed fixtures, logs, receipts, partial reports and all not-run reasons remain evidence. Never delete older negative receipts, protected ELFs, source or unrelated caches to recover budget.
- Recheck source/protected identities before final publication. Every progress/final JSON write reserves its transient old-plus-staged footprint before writing. Final publication first persists canonical non-passing evidence, writes a prospective PASS only into a non-authoritative staged file, checks its fully written footprint and time, then atomically replaces the canonical receipt as the last publication operation. No unchecked canonical PASS is exposed before a later resource gate. Exceptions reset flags and preserve rejected-stage/failure evidence.
- Overall fixture-disk growth is a supervised admission/observation guard, not an OS filesystem quota; the unchanged fixed fixture/report bounds limit known writes, and no observed overflow may produce an accepted receipt. Bounded pipe retention is enforced before each retained chunk. Do not describe the runner as an OS-enforced hard filesystem cap. Always retain bounded failure evidence and upload only evidence within the reviewed artifact budget; workflow/preflight stderr remains available even if final evidence cannot be admitted.

## Analysis and interpretation

Retain raw batches and process wall times, all six paired ratios, the geometric mean of those ratios, all six absolute per-process medians, absolute deltas, source/ELF/compiler identities and order/position fields. The full run yields 112 cases ×3 pair relationships =336 comparison rows. Report all 40 lifecycle cases, especially the debug regressions: file-heavy rmdir/overwrite/hardlink, directory-heavy overwrite, tiny replay and same-parent rename. Do not pool heterogeneous cases or discard negative controls.

Actual Node layout and process RSS/HWM are distinct metrics. Node payload extrapolation is not a measured total-heap bound; RSS includes executable mappings, base manifests, allocator history and oracle allocations. Batch maxima are not per-operation p99. This protocol cannot establish mounted Cargo performance or superiority over LayerFS, and it does not authorize production promotion.

The actual accepted 176-process debug evidence contains 993 files and 673 directories: 17,264,369 logical bytes and 18,264,064 charged bytes, including 13,458,905 logical / 14,139,392 allocated bytes of surviving fixture/object files. The separate 10-process canary occupies 598,016 charged bytes. Scaling the full evidence to 396 and canary to 15 gives 41,991,168 bytes (40.047 MiB) for 411 positions. Adding three copies of the larger prior release ELF (7,982,960 bytes each) gives 65,940,048 bytes (62.885 MiB); conservatively substituting three current debug ELF allocations gives 101,968,896 bytes (97.245 MiB). These are capacity estimates, not promised release sizes. Three-way summary differences, build logs/receipts and toolchain metadata are additional, and the 1 GiB cap remains enforced on actual evidence; no larger cap is requested.

For planning only, the accepted debug 176-process run took 239.407 seconds. Linear scaling to 396 processes is about 538.666 seconds, plus the canary and three remote builds; this is not a release-runtime prediction or a reason to relax limits. If remote setup/builds consume the available envelope, retain the incomplete result instead of silently extending the job or shrinking controls.

## Prepared files and validation status

`run_release.py`, `build_release.py`, their pure validation-test sources, `manifest.template.json`, the suffix, the two modules and `reference_validators.py` live only in this external preparation directory. The manifest is intentionally blocked pending root execution approval and actual embedded successor-inventory validation. No local Cargo/rustc/test ELF, unit test or benchmark was executed during this preparation; syntax may be inspected with `ast.parse` without executing helper code. Root can run the pure validator tests serially before the benchmark owner integrates reviewed helpers. No remote repository or workflow has been edited by this preparation.

Local, unbuilt release-only benchmark children are recorded in `local-release-benchmark-children.json`: baseline `debb016104a481b3a460f1e253beb770bb893a82`, count `3f20cbefc9effe85cae50f099779310b6ad18fc1`, narrow `82c2bbb019b5fea874c58936b763b0d2165b8540`. Each is a direct child of its production pin with only the identical modules and eight-line suffix. Old debug worktrees/commits and unbuilt narrow-original-input child `dc4fcd86ac92ea5946fb078c3bc58b9bd1f48fe1` remain unchanged; the latter is not a type-compatible release build input. No local benchmark child is published.
