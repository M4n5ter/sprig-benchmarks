# One finite identical-binary native calibration

**Preparation only until frozen review/root tests/publication/explicit dispatch.**
This is the selected diagnostic after reverse run40309337054 exceeded the
predeclared source-equivalent control's5% noise-review threshold. It is not a
replacement, retry-to-green or permanent veto of inventory. All earlier results,
including small-admission f481 unique10000 failure and off-path fork regressions,
remain binding/visible. No CPU counters, traces or product instrumentation are added.

## Explicit new identity, not relaxed old guards

New series `inventory-identical-binary-v1`, schema
`sprig-stress-cache-identical-calibration-v1`, registered experimental
`native-fork-ab.yml` route, **only `cache-large-64k-1024`**:

- A/main: `b300693e01c652c1a9631c61b7a439892d8f75cd`.
- C1/copy1 and C2/copy2: **both** exact
  `4eb0f4d7afdb19bf22d9667dc520ede8b162c737`, the **same verified sourcePath**.
- Fetch/build main once and4eb once in separate clean targets. Install the one
  `portable-sprig` release output into two distinct executable paths; `cmp` both
  against the original. No second candidate compilation or fabricated hash change.
- Both copies must remain byte-for-byte equal to the single built original, with
  matching SHA256 but distinct regular-file inodes/paths. A's hash/sourcePath stay
  distinct. Exact clean source checkouts, binary bytes and proof are reverified
  before/after each sample.
- `cache-identical-build.json` binds the exact source, original binary, two copies,
  and full candidate release-build log. The log must contain exactly one candidate
  package compilation and its recorded sourcePath. Proof bytes are frozen across
  each stage; both canary and measurement reports bind identical proof SHA/content.
  The archived log/proof are rechecked by the independent summary after relocation.
  Original binary executable bytes are not archived; their runtime measurements
  and immutable workflow/source proof remain explicit, not an offline binary audit.

Only the new `--inventory-calibration-stage` and mandatory
`--inventory-calibration-build-proof` admit this identity. The original admission
series (including distinct hashes), c392/4eb source-equivalent reverse series and
legacy canary/two-product guards stay unchanged. Modes cannot be mixed; proof flags
outside calibration are rejected. “Diagnostic” here is measurement-calibration
purpose, not the existing lifecycle-trace flag: all products remain uninstrumented
and the old diagnostic-canary restriction is untouched.

## One finite balanced matrix and unchanged resource contract

Three fresh-image canaries A/C1/C2, then nine samples in the same reverse-Latin
shape: **C2/C1/A, C1/A/C2, A/C2/C1**. Each label appears once per round/position.
Only candidate binary identity is calibrated; normal workload, ordering shape,
per-sample preparation, full correctness and accounting remain the same. Setup
now builds two unique sources, outside sampler timing; do not pool absolute timing
with prior three-build runs or pretend setup/page-cache state is identical.

1024 independently written unique64KiB files,64MiB logical,448MiB conservative
retained charge, no aliases, one no-op checkpoint, one64-byte edit, both historical
restores. Same Ubuntu24/jobs2,45min job and40min original admission clock, one
shared≤1200sec measurement deadline including all canaries/nine samples, fresh2GiB
images,256MiB reserve and≤1GiB retained ceiling. No deadline/image expansion,
parallel measured job, forced teardown, kernel-fault harness or security/billing
change. Prior eligible64KiB screen remains hash-bound reviewed attestation—not a
fresh raw re-audit—and every new raw canary/sample is fully audited.

## Predeclared interpretation and stop condition

- C1→C2 **median** paired whole and restore ratios must both lie in **[0.95,1.05]**.
- Both A→C1 and A→C2 arms require median restore ratio≤**0.90** and whole≤**1.05**.
- The two arms reuse the SAME three A observations: **not six independent pairs**.
  Report each arm separately, every pair/scatter, order and all off-path negatives.
- The summary separately exposes whether **every individual noise pair** lies in
  the same5% band. This descriptive scatter flag is not a newly invented hard
  acceptance threshold. A passing median never licenses hiding wild pairs or
  declaring stable performance. No automatic stability/promotion property exists.
- If identity noise continues, stop **inconclusive**, retain all data and do not
  automatically repeat, tune sample counts or seek a green result. Failed intended
  benefit or off-path regressions also remain visible for review.
- Correctness `complete=true`/CI success is distinct from performance/noise gates.
  Missing/malformed/proof-changed/failed samples suppress all comparisons. No
  partial rows are dropped, no measured null is faked as zero, and no independent
  p95/p99 or significance claim follows from three rounds.

Any future per-CLI CPU/resource diagnostic is a separate reviewed experiment;
none is implemented here. Main promotion is not authorized by this calibration.

## Root-owned offline validation after freeze

```sh
python3 -m unittest discover -s feasibility -p 'test_stress_cache*.py' -v
python3 -m unittest discover -s feasibility -p 'test_stress_run.py' -v
python3 -m unittest discover -s feasibility -p 'test_stress_sample.py' -v
python3 -m unittest discover -s feasibility -p 'test_stress.py' -v
```

Then syntax/YAML/authored diff checks and independent identity/proof/workflow
review. Local fixtures contain inert synthetic binary bytes only; no Rust build,
product executable, mount or performance measurement is required for these tests.
The benchmark owner directly re-read the verified owner's explicit public
scripts/workflows/results authorization before preparing this route; actual
publication/dispatch still awaits root's review decision and normal tool review.
