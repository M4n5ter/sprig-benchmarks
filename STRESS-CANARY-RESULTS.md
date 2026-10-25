# Full-tree stress canary — baseline gate

25October2026. [Baseline run40180439871](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40180439871), benchmark `05f77065b9509535fc337e25b8a65923cd9051a9`, Sprig schema14 main `071036f83691b89bd9e35bb162d34e305e1874b7`, LayerFS release `9f97a7ec95b662e9cb288704afa165feff132cfa`.

**6/6 records pass across native, projection and owned writable:90 full-tree checks and24 historical readbacks.** Each sample performs3deterministic edits plus an unchanged checkpoint and4 public restores, including the initial unchanged revision. Exact path sets, bytes,0777 modes, nanosecond mtimes, symlink targets and internal hardlink groups pass; source/main/second remain unchanged. All normal cleanup completes with zero remaining mounts/containers/owned servers. All257 archived full log files were independently checked against recorded byte counts and SHA256 hashes. No lifecycle trace records appear in primary samples.

The two real product kernel gates also pass. One sequential job completed in5m38s, within the unchanged45-minute/2GiB-image/two-build-job limits. An unintended old comparison push run was cancelled and retained as [run40180439821](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40180439821); the experimental branch is now narrowly excluded from that old push trigger, with main/manual behavior unchanged.

This is a **small correctness/release gate**, not pressure acceptance or statistical performance evidence. No before/after speedup is inferred from single pairs or separate runners. New full-tree Python-oracle runtime and full charged evidence differ from the old frozen listed-file series; old reports remain unchanged. All persistent image/runtime/store/native-tree/generation state remains charged at primary/post-history boundaries. Sprig synchronization versus LayerFS Disposable is still unequal crash durability. UID/gid, suid/sgid/sticky bits, ACL/xattrs and external hardlinks are not covered by this metadata oracle; no completePOSIX claim is made.

- [Unmodified downloaded artifact](data/stress-20261025/baseline-canary/)
- [Independent raw verification](data/stress-20261025/baseline-canary/verified.json)
- [Every-file provenance/hash inventory](data/stress-20261025/baseline-provenance.json)
- [Protocol, budgets and phase boundaries](feasibility/STRESS-PLAN.md)

Publication is isolated to the experimental benchmark branch. Benchmark main remains unchanged pending reviewed validation; pressure stays disabled. A separately instrumented writable canary follows at `f09120e3138596c4983371aaccf6f019f395e9fd`; its timings are not primary performance results.


## Separate writable diagnostic gate

[Run40181092961](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40181092961), product `f09120e3138596c4983371aaccf6f019f395e9fd`, benchmark `bc901305772cd6a743a04ed0f335c4ce7cb1c292`:1/1 diagnostic record passes15full-tree checks and4historical readbacks, with complete normal cleanup. All54 archived log files passed independent byte/SHA256 verification. The job took3m40s.

227valid trace records were preserved (214CLI stderr,13daemon logs), with zero malformed records. Normal unmount, lease polling and server readiness each have13result-wrapped `ok=true` records; scope-only `ok=null` spans are retained but do not count as successful-phase evidence. This validates actual mounted trace coverage, not a performance improvement. Nested trace spans overlap and cannot be summed into a synthetic task time; this instrumented sample is never pooled into primary comparisons.

[Full unchanged diagnostic artifact](data/stress-20261025/writable-diagnostic/) · [Independent verification](data/stress-20261025/writable-diagnostic/verified.json) · [All-file provenance](data/stress-20261025/diagnostic-provenance.json).
