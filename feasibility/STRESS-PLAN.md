# Bounded stress protocol v1 — review proposal, not benchmark evidence

25 October 2026. Frozen existing benchmark: `231d66e2d89c16964dc32ea7279c00abd3bb956a`.
Product baseline: promoted schema-14 main `071036f83691b89bd9e35bb162d34e305e1874b7`; comparator release `9f97a7ec95b662e9cb288704afa165feff132cfa`.
Old reports, fixtures, scripts, workflows and raw results are not modified.
No workflow is dispatched or pushed by this change. The new local code prepares
fixtures, oracles, a bounded plan and descriptive statistics, and now implements
separate public-CLI/SDK production samplers plus bounded sequential orchestration.
These drivers have only local/mocked checks so far, not real kernel acceptance. No new performance or Fresh claim is made.

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
| 1 | 10,000 × 4 KiB files, one directory | 39.1 MiB | 273.4 MiB conservative, 7 generations | Metadata/checkpoint scheduling |
| 2 | 256 × 4 KiB, depth 128, narrow | 1 MiB | 7 MiB conservative, 7 generations | Traversal/path and small-file overhead |
| 3 | 256 × 4 KiB, random 64-byte overwrites, 300 commits | 1 MiB | 603 MiB, 3+2N generations | History growth, per-step tails and restores |
| 4 | 16 library crates + binary, shared local dependency DAG, build script | generated source is small; target measured | Must preflight real compiler/target size | Real Cargo graph instead of dependency-free crate |

For priorities 1/2, production execution will include a separately named no-change
checkpoint and one changed-file checkpoint, with exact no-op semantics checked
rather than requiring a new revision for no-op. Both products publicly restore
and fully verify the unchanged initial revision too; no-op restores are charged.
Each image stays **2 GiB**, matching the existing harness. No resource/timeout,
security, privilege or runner-class changes. Parent authorized local preparation
only. The `imageGiB` plan field does not create an image.

**Budgets (planning caps, not measured product forecasts):** existing job limit
45 minutes; allow up to 20 minutes setup/build, at most 570 seconds per product
sample in an ordinary two-product pilot (120seconds in canary), plus a60-second
admission reserve, and5minutes evidence/normal teardown. Actual setup overruns reduce the
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
clean caches, or omit a restore. A cooperative time/capacity budget abort is incomplete, not a correctness pass or
an incorrect-output assertion. Guards admit operations at boundaries, never kill
or cancel an uncertain product mutation. Partial ledgers are retained and normal
teardown is attempted. A single operation can outlast its admission estimate;
the existing45-minute external job cap is unchanged. No blind retry of uncertain mutations.

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

Reuse `tree_oracle.py`: exact path set, regular bytes, file/directory permission bits0777 and
nanosecond mtime, symlink target, internal hardlink equivalence groups. This is
not allPOSIX attributes: uid/gid, atime/ctime, suid/sgid/sticky bits, ACLs, xattrs
and external hardlink relationships are not verified by this oracle. Initial
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
production driver, new runtime image and pinned-source build steps must be
reviewed before any move into a dispatchable location. The current draft can run
one fixed Sprig/release pair or a separately labeled Sprig-only diagnostic canary;
it never automatically launches all menu cells or follow-on pressure jobs.

Optional `SPRIG_LIFECYCLE_TRACE=1` diagnostics must retain prefixed JSON-lines stderr
and inherited writable generation FUSE daemon logs as a separate instrumented
series. Primary timings keep trace disabled. Never subtract logging overhead.


## Implemented driver and current verification state

`stress_run.py` accepts1product for canary or2exact configured products for pressure,
strictly belowRUNNER_TEMP on root GitHub Linux. It provisions fresh2GiB Btrfs images
sequentially, retains images, logs source/binary hashes and measures empty and
runtime-ready boundaries. `stress_sample.py` reuses reviewed normal Sprig
mount/server/cleanup contracts but not frozen fixture assumptions;
`stress_layerfs.mjs` uses public SDK methods with exact commit IDs/parents.
Both perform identical shell dd+fsync+fixed-mtime writes, full Python tree snapshots
for every acknowledged checkpoint and restore, and15full-tree checks for the3-edit
plus no-op canary. Full observed JSON stays in charged logs, copied externally only
after physical samples/normal teardown. This prevents one-sided oracle log costs.
The outer sampler subprocess wall is the matched authoritative window, including
preparation, checks, logging, accounting, normal cleanup and final serialization;
internal timers can overlap and have separately declared narrower scopes.

LayerFS uses a **new stress-only immutable Ubuntu+Python runtime image** built from
an exact official Ubuntu digest with `Stress.Dockerfile`, including the exact
oracle script. Its full image, package manifest/hash and all deployed runtime roots
are charged. The Sprig and LayerFS workspace oracle program is identical; external
source checks use the same host Python helper. This is not a comparison to old
plain-Ubuntu historical results. Cargo retains its separate shared compiler image.

Local Cargo DAG validation passed on rustc/cargo1.99.1: both incremental0/1 built
and executed, all17packages Fresh with noCompiling on no-op; exact stdout645.
This is not pinned1.90.0 CI compiler or product restore acceptance. See
`stress-cargo-local-sanity.json`; real pinned-image build/restore/Fresh gate remains.

The draft `sprig_sha` input requires40hex and verified detached checkout. Diagnostic
mode is canary-only and excludes comparator primary ratios; lifecycletrace is set
only on Sprig CLI/descendants, full stderr/daemon logs retained. Default primary
rejects ambient enabledtrace. Publication/dispatch awaits explicit authority.


## Fail-closed cleanup and canary admission review

The first workflow draft exposes **canary only**. Pressure menu cells remain local
code, not selectable CI jobs, until an exact-head successful real gate is reviewed
and enabling them is separately approved. The outer report labels
`within-sprig-ab`, `sprig-layerfs-stress`, `single-product-canary` and
`diagnostic-canary` distinctly; a nonbaseline fullSHA is labeled candidate.

Outer teardown requires an affirmative parsed sampler cleanup proof and known
zero mounts/daemons/containers. Missing/malformed output or any uncertain mutation
blocks runtime leave and image unmount; image/runtime-state paths are recorded for
recovery without leaking original configuration backups. Stress-specific runtime
wrapper makes any Docker inventory failure a hard block, including a failure
between inventory reads; it cannot fall through the old helper's outage fallback
to stop Docker/containerd. Pre-sampler setup failure requires confirmed rollback
(or no state file, proving no configuration mutation was begun). No workflow
finalizer forcibly stops runtime. Eventual ephemeral-runner termination remains an
external CI action, not a harness claim of successful normal cleanup.

Both sampler physical boundaries run only sync/usage/df, with wholeFSUsed primary.
The one-sided comparator extent traversal was removed; outer empty/runtime-ready
extent diagnostics are symmetric and outside sampler task wall. Admission budget
is checked again after image/runtime setup, immediately before starting a sample.

Primary Sprig evidence archival copies/hashes full logs without the diagnostic-only
line-by-line trace parsing or inline excerpts. Both products still have different
Python/Node orchestration and CLI/SDK transports: matched subprocess **window**
does not mean identical harness implementation or product-only CPU cost. Full
wall charges that work rather than subtracting a guessed overhead. Diagnostic
trace parsing and excerpts remain separately labeled and never pooled with primary.


Publication update: user authorized public benchmark scripts/workflow and
existing-limit CI on25October2026. `.github/workflows/stress-canary.yml` stages the
reviewed canary-only gate; pressure remains disabled pending real acceptance.

## First same-runner own-version pressure pilot

After exact baseline and final integrated three-backend canaries, one native10k
pair compares baseline071036f with integrated1bd8793 on the SAME runner. The AB
workflow verifies committed full artifacts and public exact-head completed/success
run metadata before building; no new token scope or Actions permission is needed.
Two separate fresh target roots prevent cross-worktree Cargo package reuse; only
registry/git downloads are cached. Verbose compile logs must show the actual
source build; copied binary bytes and hashes must differ. Kernel gates use each
copied binary. Same compiler identity, fixture, oracle, tracing-off configuration,
operation boundaries and fresh2GiB images apply to both. No LayerFS or Docker setup
is inserted into this own-version causal question.

The first order is baseline→candidate; `--pair-order reverse` can counterbalance a
later authorized confirmatory job. Its pair/run identity is retained, not pooled
as an invented same-runner repeated measurement. One pilot pair is descriptive;
no confidence or p99 claim is made from its two checkpoint operations. Confirmatory
pairs require fresh review of observed budget. Remaining-time admission is checked
after setup and again immediately before each sampler; normal cleanup reserve stays.

### Targeted cache-threshold experiment (new recipe, not prior protocol)

`cache-history-repeated-300` freezes a 1MiB source mix:128×1KiB,
64×8KiB and8×48KiB files. Six hot files (two per size) receive300
deterministic64-byte toggles. Repeated full-file states recur after12edits;
each individual edit still changes bytes. This targets the known small-file
cache-admission gap, not representative histories. Existing recipes are unchanged.

The first causal pair is inventory-only8558b13 versus threshold9f83c4:
runtime admission threshold only, with test-only portability fixes in the latter.
Each binary must pass tests, real kernel gates and a native full-tree canary
before pressure in the same job. `stress_sequence.py` shares one maximum20minute
remaining measurement budget across BOTH canary and pressure; it reserves30seconds
for sequence evidence, and each child retains its operation/cleanup admission
limits. Setup consumes the existing45minute job budget with5minutes reserved.
Planning estimate is8–12minutes for the pair plus canaries, not a completion
promise; insufficient budget records an incomplete budget abort, never fewer
edits, pruned generations or weakened oracles. Conservative native retention is
603MiB plus measured runtime and reserve in each fresh2GiB image.

A separate fresh-store unique10k4KiB negative pair is mandatory before any
cache-threshold promotion. “Cold” refers to empty product file cache, not OS
page-cache eviction. A favorable repeated-history result alone is insufficient.

The explicit `files-4096` control uses the same unique4KiB recipe, one no-op
and one64-byte changed checkpoint as unique10k, but fits the cache's4096entry
limit per snapshot. The changed revision introduces one additional content key
across the retained-history union while each snapshot still has4096files.
It tests cold-fit admission and the next revision's capacity-bound transition,
not just the favorable reused-history case. Existing cells unchanged.
