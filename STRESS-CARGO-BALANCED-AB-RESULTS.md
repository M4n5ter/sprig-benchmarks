# Repeated ordinary Cargo A/B: the initial whole-task gain did not repeat

[Run 40287036513](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40287036513) passed in 12m23s at benchmark `36841f19fc13048a2d865d5b12acd8fd74d5fe08`. Baseline `4ef4a90d7ccf5f305416c5374bfc81038f5ca46e` versus rename candidate/current main `b300693e01c652c1a9631c61b7a439892d8f75cd`; same runner and pinned workload, four balanced fresh-image pairs per incremental mode (16 samples total).

**The earlier one-pair whole-Cargo speedup did not repeat.** Geometric-mean paired whole-sampler change is **+0.29% in incremental0 and +2.00% in incremental1** (candidate slower). All four incremental1 whole-task pairs are slower. The checkpoint phase improves −4.88%/−4.22%, but cannot be isolated as a whole-task gain or summed with overlapping timers. This is descriptive evidence, not statistical significance or a reason to select only favorable phases. Historical one-pair results, failures and local rename-specific results remain unchanged and are not pooled.

## Every whole-task pair

| Mode | Round | Actual order | Baseline seconds | Candidate seconds | Candidate change |
| --- | --- | --- | ---: | ---: | ---: |
| inc0 | 0 | baseline → candidate | 8.835710 | 8.977437 | +1.60% |
| inc0 | 1 | candidate → baseline | 9.152208 | 8.913632 | -2.61% |
| inc0 | 2 | baseline → candidate | 9.036807 | 8.854881 | -2.01% |
| inc0 | 3 | candidate → baseline | 8.936034 | 9.323510 | +4.34% |
| inc1 | 0 | candidate → baseline | 10.317829 | 10.489558 | +1.66% |
| inc1 | 1 | baseline → candidate | 10.641755 | 10.925306 | +2.66% |
| inc1 | 2 | candidate → baseline | 10.754838 | 10.776818 | +0.20% |
| inc1 | 3 | baseline → candidate | 10.999558 | 11.384954 | +3.50% |

All 16 planned records are present, correct and archived; no failed or incomplete sample was removed and no retry occurred. Four samples per variant/mode cannot estimate end-to-end p95/p99 or establish significance. Each pair uses fresh symmetric4GiB filesystems and separately verified immutable binaries. The modes remain separate.

## Matched metric summaries

Percentages below are geometric means of the four candidate/baseline paired ratios. Displayed medians are descriptive medians of variant values, not the source of the paired percentage. Nested phases and convenience composites overlap; **do not add them or subtract them from whole wall**. Runtime setup is separately timed; whole Used is never baseline-subtracted.

| Metric | inc0 baseline median | inc0 candidate median | inc0 paired change | inc1 baseline median | inc1 candidate median | inc1 paired change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| wholeSamplerSeconds | 8.986421 | 8.945535 | +0.29% | 10.698296 | 10.851062 | +2.00% |
| runtimeSetupSeconds | 14.881122 | 14.956285 | +0.12% | 14.971617 | 15.046440 | +1.02% |
| phase.clean_build | 1.422495 | 1.409670 | -0.67% | 1.937601 | 1.988179 | +3.93% |
| phase.noop_build | 0.298357 | 0.298875 | -1.02% | 0.281565 | 0.297291 | +6.46% |
| phase.edit_build | 1.350999 | 1.313083 | -1.23% | 1.702144 | 1.729826 | +2.48% |
| phase.checkpoint | 0.158960 | 0.151271 | -4.88% | 0.210338 | 0.200263 | -4.22% |
| phase.restore | 0.029162 | 0.028217 | -1.48% | 0.033138 | 0.037302 | +7.43% |
| phase.restore_verify | 0.670313 | 0.686200 | +0.61% | 1.044372 | 1.046839 | +0.53% |
| phase.restored_rebuild | 0.292486 | 0.298292 | +3.56% | 0.305018 | 0.299171 | -1.07% |
| phase.retained_input_verify | 1.330471 | 1.389086 | +2.61% | 1.379675 | 1.383831 | -0.88% |
| phase.cleanup | 0.430121 | 0.440377 | +2.72% | 0.465772 | 0.456217 | -0.99% |
| convenience.checkpointCompilerQuiescePlusProduct | 0.533034 | 0.517482 | -3.13% | 0.564070 | 0.572203 | +0.92% |
| convenience.restoreToCompilerReady | 0.247541 | 0.230331 | -3.15% | 0.241327 | 0.246623 | +2.17% |
| wholeFilesystemUsedBytes | 1,055,703,040 | 1,055,731,712 | -0.00% | 1,066,334,208 | 1,066,196,992 | -0.01% |

Whole Used differences are only tens/hundreds of KiB against ~1.0GiB; do not turn them into a general storage claim. Incremental1 clean/no-op/edit build phases are respectively +3.93%/+6.46%/+2.48%, and restore is +7.43%. Incremental0 cleanup is +2.72% and restored rebuild +3.56%. Those negatives remain part of the verdict.

## Order sensitivity and drift

| Mode | First product | Rounds | Whole paired geometric change |
| --- | --- | --- | ---: |
| inc0 | sprig-baseline | 0,2 | -0.22% |
| inc0 | sprig-candidate | 1,3 | +0.80% |
| inc1 | sprig-baseline | 1,3 | +3.08% |
| inc1 | sprig-candidate | 0,2 | +0.93% |

There are only two pairs per order stratum. Incremental1 whole times rise from 10.318→11.000s for baseline and 10.490→11.385s for candidate across rounds; this runner-local time drift is visible rather than hidden by a best-of result. Order balancing reduces one-sided ordering bias; it does not eliminate host drift or make four samples independent multi-host trials.

## Correctness, provenance and resource audit

- All 16 samples pass clean/edit 17 Compiling, noop/restored 17 Fresh with zero compilation; program 269→3400, generated build-script values 1→2; exact 280-entry incremental0/474-entry incremental1 full-tree restore before execution/rebuild; content/mode/exact integer nanoseconds/symlinks/internal hardlinks; source/main invariance and all acknowledged history.
- Four retained generations and three live product views per active-space snapshot; exactly one correctly bound restored compiler. All 64 compiler sessions exit naturally with verified PID disappearance; each sample confirms zero remaining mounts/containers and normal cleanup. No forced teardown, retry, quota fill, mapped-fault or intentional kernel-fault route.
- The collector contains 4,312 files, with 4,246 unique declared raw archive files verified by size/SHA256. Offline re-audit from exact benchmark36841f1 passes all 16 records with zero errors and reproduces server comparisons/identity exactly. The 40 archived source/test hashes for each variant match exact git objects; all 18 benchmark script hashes match36841f1. Distinct recorded binary hashes match the manifest and every sample. Executable bytes are not archived: this verifies recorded binary provenance, not an offline executable rehash.
- Host build compiler is Rust 1.99.1; shared workload compiler is Rust/Cargo 1.90.0. Shared image is `sha256:356a91d1659cbe5bef040ae69c5dd561555d04de51ad7c2d4a33b3e32ab03d86`. Both variants use one frozen protocol/fixture per run. This image identity differs from the historical one-pair run, another reason not to pool absolute measurements.
- Fresh 4GiB images throughout, one measured image at a time, no 8GiB fallback. The original absolute 40-minute admission deadline 1793000318→1793002718 covers setup and both modes; each sample retains 180 seconds work plus 300 seconds cleanup admission. Job remains 45 minutes, Cargo jobs 2 and existing Ubuntu 24 runner. No permission, security, billing or runner-class change.

Immutable repository evidence: [`data/stress-20261026/cargo-balanced-own-ab`](data/stress-20261026/cargo-balanced-own-ab). The complete original artifact tree is preserved there, with the offline recomputed summary, exact source/script provenance audit and run metadata in its `audit/` subdirectory.

Raw CI artifacts: [artifact12634243996](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40287036513/artifacts/12634243996) (`stress-cargo-own-ab-balanced`,11,604,346 compressed bytes;4,312 declared files). Exact raw sample JSON and archived snapshot stdout preserve nanosecond integers; JavaScript embedded comparison trees are not authoritative exact-integer evidence. The complete summary retains every metric value, pair, order stratum and negative.

## Every slower geometric-mean metric

Descriptive overlapping timers, not additive costs or isolated causal attribution. The full JSON also retains each faster metric and every individual slower pair.

| Mode | Metric | Paired geometric change |
| --- | --- | ---: |
| inc0 | fullTaskSeconds | +0.29% |
| inc0 | phase.checkpoint_readiness | +3.68% |
| inc0 | phase.clean_artifacts | +1.00% |
| inc0 | phase.cleanup | +2.72% |
| inc0 | phase.edit_artifacts | +1.38% |
| inc0 | phase.edit_execute | +3.71% |
| inc0 | phase.pre_checkpoint_oracle | +2.53% |
| inc0 | phase.restore_verify | +0.61% |
| inc0 | phase.restored_artifacts | +1.69% |
| inc0 | phase.restored_execute | +8.89% |
| inc0 | phase.restored_rebuild | +3.56% |
| inc0 | phase.restored_rebuild_artifacts | +0.41% |
| inc0 | phase.restored_rebuild_execute | +1.72% |
| inc0 | phase.retained_input_verify | +2.61% |
| inc0 | phase.space | +3.95% |
| inc0 | phase.transport_stop_final_cleanup | +3.24% |
| inc0 | runtimeSetupSeconds | +0.12% |
| inc0 | wholeSamplerSeconds | +0.29% |
| inc1 | convenience.checkpointCompilerQuiescePlusProduct | +0.92% |
| inc1 | convenience.restoreToCompilerReady | +2.17% |
| inc1 | fullTaskSeconds | +2.02% |
| inc1 | phase.cargo_setup | +0.90% |
| inc1 | phase.checkpoint_readiness | +6.68% |
| inc1 | phase.clean_artifacts | +3.05% |
| inc1 | phase.clean_build | +3.93% |
| inc1 | phase.clean_execute | +4.44% |
| inc1 | phase.edit | +1.71% |
| inc1 | phase.edit_artifacts | +3.00% |
| inc1 | phase.edit_build | +2.48% |
| inc1 | phase.edit_execute | +2.96% |
| inc1 | phase.import | +1.43% |
| inc1 | phase.noop_artifacts | +3.61% |
| inc1 | phase.noop_build | +6.46% |
| inc1 | phase.noop_execute | +3.20% |
| inc1 | phase.pre_checkpoint_oracle | +6.90% |
| inc1 | phase.restore | +7.43% |
| inc1 | phase.restore_verify | +0.53% |
| inc1 | phase.restored_artifacts | +1.34% |
| inc1 | phase.restored_rebuild_artifacts | +2.23% |
| inc1 | phase.restored_rebuild_execute | +0.05% |
| inc1 | phase.space | +3.21% |
| inc1 | phase.target_probe | +4.84% |
| inc1 | phase.transport_stop_before_checkpoint | +3.79% |
| inc1 | runtimeSetupSeconds | +1.02% |
| inc1 | wholeSamplerSeconds | +2.00% |

## Decision

Do not claim a general Cargo improvement from bounded rename traversal. The existing rename-focused evidence is a different workload. Continue the separately predeclared normal two-worker pressure experiment to test its intended workload and dependent operation tails; do not fold that stage into these ordinary measurements or alter the resource/oracle gates. The cache admission experiment is a different candidate/pin series and must be separately measured. No additional main promotion is implied by this run.
