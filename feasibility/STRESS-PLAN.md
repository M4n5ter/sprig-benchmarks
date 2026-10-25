# Bounded stress protocol v1 — review proposal, not benchmark evidence

25 October 2026. Frozen existing benchmark: `231d66e2d89c16964dc32ea7279c00abd3bb956a`.
Product baseline: promoted schema-14 main `071036f83691b89bd9e35bb162d34e305e1874b7`; comparator release `9f97a7ec95b662e9cb288704afa165feff132cfa`.
Old reports, fixtures, scripts, workflows and raw results are not modified.
No workflow is dispatched or pushed by this change. The new local code prepares
fixtures, oracles, a bounded plan and descriptive statistics; it does **not** yet
execute production products. No new performance or Fresh claim is made.

## Highest-signal first, not a Cartesian matrix

Each row is a separate **sequential** pilot job, one backend and one alternating
product pair. Start writable for the new checkpoint paths; native and projection
need their own explicitly selected cells after the first pilot, not an automatic
backend multiplier. Candidate A/B and comparator runs are separate questions:
first require a real small three-backend kernel canary and16-crate Cargo build/Fresh
sanity; then frozen-main/candidate on one runner, then accepted candidate/LayerFS when
correctness passes. Never infer improvement from runs on different machines.

| Priority | Fixture | Logical bytes | Worst retained logical estimate | Why |
|---|---|---:|---:|---|
| 1 | 10,000 × 4 KiB files, one directory | 39.1 MiB | 117.2 MiB, 3 views | Metadata/checkpoint scheduling |
| 2 | 256 × 4 KiB, depth 128, narrow | 1 MiB | 3 MiB, 3 views | Traversal/path and small-file overhead |
| 3 | 256 × 4 KiB, random 64-byte overwrites, 300 commits | 1 MiB | 603 MiB, 3+2N generations | History growth, per-step tails and restores |
| 4 | 16 library crates + binary, shared local dependency DAG, build script | generated source is small; target measured | Must preflight real compiler/target size | Real Cargo graph instead of dependency-free crate |

For priorities 1/2, production execution will include a separately named no-change
checkpoint and one changed-file checkpoint, with exact no-op semantics checked
rather than requiring a new revision for no-op. This sequence is not yet wired.
Each image stays **2 GiB**, matching the existing harness. No resource/timeout,
security, privilege or runner-class changes. Parent authorized local preparation
only. The `imageGiB` plan field does not create an image.

**Budgets (planning caps, not measured product forecasts):** existing job limit
45 minutes; allow up to 20 minutes setup/build, at most 10 minutes per product
sample, and 5 minutes evidence/normal teardown. Actual setup overruns reduce the
sample budget; do not start a sample without its remaining reserved budget. First
four pilots are at most 4 × 45 = 180 runner-minutes, concurrency 1, not four jobs
in parallel. Expected warmed setup can be shorter, but no promise relies on it.
Cargo incremental=0 is the first pilot; incremental=1 is a separate gated job.
Three confirmation pairs are allowed only after a successful measured pilot
establishes their fit; otherwise split sequential jobs under the existing cap.

Before creation, require available host space for image+fixture+artifact reserve;
inside image require measured runtime-ready Used + conservative retained bytes +
256 MiB reserve <= 2 GiB. Filesystem metadata can exceed a logical estimate: also
record actual Used at untimed boundaries. Reject insufficiency as **capacity
blocked**, retain evidence, never silently shrink a fixture, prune a generation,
clean caches, or omit a restore. A 600-second sample timeout is a failed/incomplete
sample, not a correctness pass; production integration must retain partial ledgers
and use existing safe normal teardown. No blind retry of uncertain mutations.

## Graduated expansion after pilot evidence

`stress_plan.py` enumerates a menu, not launch instructions: 1k/10k/50k files;
64/256 MiB unique bytes; depth32/128; width128/1024; histories100/300/1000 with
random, eight-file hot set and two-state repeated edits; 256 hardlink groups; an
8 MiB history-size case. All deterministic seed20261025 and a new SHAKE256 recipe,
not a purported reproduction of the old upstream distribution.

At 1 MiB/history step, 1000 steps have a conservative 2003 MiB retained estimate;
8 MiB ×100 has 1624 MiB. Both are explicitly **capacity-review-required** and not
eligible under the current 1 GiB retained pilot ceiling. They remain unrun unless
an independent, honestly relabeled size experiment fits or a later authorized
budget changes. Reflink/dedup/compression savings cannot be assumed to pass guards.
Do not compare a reduced-tree 1000-step case to larger-tree100/300 as an isolated
history-length scaling result.

Cargo64 libraries is similarly second-stage only after measured16-crate build,
target and storage budgets fit. Local dependency DAG means real Cargo and Rust
compilation but **synthetic**, not a representative crates.io/application workload.
No network dependencies. Freeze Cargo.lock with the exact shared pinned compiler
before recording source oracle. Build `--offline --locked -j2`; same image and
incremental mode on both sides. All workspace crates must be Fresh on no-op and
restored rebuild, with no Compiling lines; include build-script state and complete
target/incremental caches. Cooperative compiler exit precedes owned checkpoint;
retain four generation-scoped session lifecycle costs and direct-wall composites.

Read concurrency is a later semantic gate: 1/2/4 readers on already materialized,
immutable snapshots, join all readers before transition, verify every read. Do
not race writers against checkpoint/unmount or advertise mutable concurrency.
Independent-store writer concurrency is a different workload, not a substituted
claim about a shared workspace. No concurrent scenario is currently executable.

## Correctness is stronger, not cheaper

Reuse `tree_oracle.py`: exact path set, regular bytes, file/directory mode and
nanosecond mtime, symlink target, internal hardlink equivalence groups. Initial
oracle is captured on a deterministic external source tree **before import**;
no product/restored tree normalization. Every acknowledged historical revision
gets a public restore, full-tree verification and normal public unmount when
applicable. Exact revision count/order/parents and retained generation counts,
unchanged source/main/second, no leaked mounts/containers and Fresh remain gates.
Changed-file checks are additional and never replace full historical readbacks.
The replay oracle updates all hardlink aliases after an inode-preserving write.

No GC, selective deletion, target filtering, retained-tree removal or artificial
cache clearing. Primary physical space with three live views is sampled before
historical restores; post-history is separately measured before their retained
state is removed (normal unmount is not deletion). Count all native trees,
checkpoint/restore generations, CAS/metadata/journals, Docker/containerd roots,
images, writable layers, compiler state and logs inside the isolated filesystem.
Runtime-ready delta is diagnostic, not exact application-only usage.

## Timing, phase attribution and resource fairness

Keep direct whole-task wall authoritative; separately record init/import, usable
fork, full read/oracle, write+fsync, checkpoint CLI/publication and readiness,
restore/materialization, full restored read/oracle and normal unmount. Cargo adds
clean/no-op/edit/restored builds, compiler quiesce+checkpoint and
restore-to-compiler-ready. Composite/underlying phase overlaps are explicit, never
summed twice or subtracted as if independent. Product diagnostic instrumentation
must be identically enabled and outside primary A/B or shown to have matched cost.

Append raw per-step timings/ordinal/bytes/files/revision/phase to JSONL outside
timed intervals. Report median/p95/p99/max and early/middle/late history windows;
nearest-rank quantiles, p95 only n>=20, p99 only n>=100. These are descriptive
correlated-operation tails, not confidence intervals. Keep repetition and product
pair IDs; do not pool medians into p99. At3 pairs give all pair ratios/range, not a
statistical-significance claim. Record path counts, sizes and observed scaling
ratios rather than silently label one differing case an optimization effect.

Memory/CPU product comparison is **not available yet**. CLI `/usr/bin/time` misses
Sprig FUSE and LayerFS daemon/Docker children; VmRSS sum double-counts shared pages.
Only add comparative resource claims after matched whole-process-tree/cgroup
accounting includes compiler/runtime and descendant lifetime on both products,
with availability/permissions verified under existing security. Otherwise retain
host resource context and explicitly mark per-product CPU/RAM unavailable.
Sprig sync/fsync stays on; LayerFS Disposable WAL/OFF and MEMORY/OFF are not equal
crash durability. Setup-warm input is not cold cache. CLI versus SDK is charged.

## Local preparation checks

```
python3 -m unittest discover -s feasibility -p test_stress.py -v
python3 feasibility/stress_plan.py
python3 feasibility/stress_fixture.py NEW_DIR --files 10000 --width 1 > fixture.json
python3 feasibility/stress_cargo_fixture.py NEW_DIR --crates 16 > cargo-fixture.json
```

Generators fail on an existing output; they never replace it. Unit tests are
non-kernel fixture/oracle checks, not production acceptance. The review-only
`stress-pilot.workflow-draft.yml` is deliberately outside `.github/workflows`;
production driver and pinned-source build steps must be reviewed/implemented
before any move into dispatchable location.

Optional `SPRIG_LIFECYCLE_TRACE=1` diagnostics must retain prefixed JSON-lines stderr
and inherited writable generation FUSE daemon logs as a separate instrumented
series. Primary timings keep trace disabled. Never subtract logging overhead.
