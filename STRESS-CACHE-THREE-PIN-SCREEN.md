# Bounded three-pin native cache screen

This is a separate, experimental **native Btrfs** screen, not the Cargo rename
comparison, not a warm/cold OS-page-cache experiment, and not evidence of a
performance improvement before its actual runs. No result is pooled across
profiles. No main-branch promotion or automatic confirmation is authorized by
this workflow.

The dispatch entry point is the already registered `native-fork-ab.yml`, whose
**experimental-branch body only** is replaced by this reviewed three-pin job.
The old 90-minute/fault-gate body is not executed. Default `main`, earlier
workflow history, and the separate ordinary/pressure `stress-ab.yml` are unchanged.
There is no new push trigger or default-branch registration change.

## Fixed inputs and interpretable changes

| Label | Immutable Sprig source | Change |
|---|---|---|
| A / main | `b300693e01c652c1a9631c61b7a439892d8f75cd` | Current main |
| B / inventory | `c392d45079314cdcf9813371ec9120d78be7bcd6` | Bounded cache inventory per exclusive lease; durability barriers retained |
| C / admission | `f481aaba987d960bf119e95b68f5b38da56e1581` | Manifest-local independent duplicate small-file admission |

Sources are checked out at exact commits. Three separate build targets are
compiled serially, with registry/git dependency caching only. Every source
checkout must stay clean and at its pin; every binary must retain its initial
SHA-256 before and after each sample. Instrumentation is off. No optional
fault/negative workload or old fault-containing Python suite is invoked.

The inventory prerequisite retains the original **64 KiB** minimum eligibility.
Thus 1/4 KiB and unique small-file controls cannot establish an inventory gain:
A→B there is a negative control/noise observation, not inventory-path evidence.
The explicit 1024 × 64 KiB cell exercises the actual large-file cache path.
Compare A→B, B→C, and A→C separately; do not attribute the combined result to
small-file admission without the middle comparison.

## Finite order and full evidence gates

One dispatch selects **one** approved cell. First, all three pins pass the same
native canary (16 files, 4 hardlink aliases, depth4, symlink, no-op checkpoint
plus3 edits, all4 historical readbacks and15 exact full-tree checks). Then run
exactly nine fresh-store samples in these orders:

1. A, B, C
2. B, C, A
3. C, A, B

Every pin appears once per round and once in each position. This is a
three-pair-per-edge Latin **screen**, not independent-host confirmation or a
significance estimate. Every sample uses the identical generated source recipe,
full content/path/type/mode/exact-nanosecond/symlink/internal-hardlink oracle,
source and retained-view invariance, acknowledged revision-chain checks, all
historical readbacks, and normal cleanup guards. Each raw standalone sample is
SHA-256-bound to its record; every archived log and full-tree oracle is re-read
before accepting the next sample. The summary rechecks all nine samples plus
all three original canaries, source/binary identities, order, and shared deadline.
Missing, malformed, failed, changed or incomplete evidence suppresses **all**
ratios, not just the bad row. Raw failed samples and driver output remain in
artifacts. No automatic retries or replacement observations.

Legacy `stress_run.py` one-canary/two-paired-product guards remain unchanged.
The new `--ablation-stage` route is explicit, native-only, exactly three fixed
pins; it cannot disguise a singleton pressure trial as a canary. Reverse-Latin
orders exist only as a tested ordering helper, not an exposed runnable workflow
or CLI stage. A later reverse-Latin confirmation needs a separately reviewed
complete eligible screen and a new explicit dispatch decision.

## Approved source recipes

Every zero-step recipe retains the established no-op-plus-one-edit policy.
All rows keep distinct ordinary source writes except explicitly named aliases.
Files with equal contents are not hardlinked or cloned. Independent duplicates
are separated in lexical width-one traversal (`key = file_index % key_count`),
so all distinct keys are visited before their next copy. Editing one independent
copy must not alter any other copy. Full restored-tree hardlink groups prove it.

| Cell | Source shape | Purpose |
|---|---|---|
| `files-4096` | Existing 4096 unique4KiB files | Cold-store unique negative control |
| `files-10000` | Existing 10000 unique4KiB files | Unique/key-bound negative control |
| `cache-history-repeated-300` | Existing200 mixed1/8/48KiB files,300 repeated edits | Unchanged history regression control |
| `cache-independent-1k-x2`, `cache-independent-4k-x2` | 4096 paths,2048 keys,2 copies/key | First-fill crossover, not assumed win |
| `cache-independent-1k-x8`, `cache-independent-4k-x8` | 4096 paths,512 keys,8 copies/key | Intended many-reuse probes |
| `cache-alias-only-1k`, `cache-alias-only-4k` | 2048 originals +2048 true hardlink aliases | Aliases must not trigger independent reuse |
| `cache-independent-over4096` | 8194 paths,4097 keys,2 copies/key,4KiB | Conservative all-small-admission overflow control |
| `cache-large-64k-1024` | 1024 unique64KiB files,64MiB logical | Actual inventory-path control;448MiB conservative retained charge |

No simultaneous eleven-cell matrix is dispatched. Each job is explicitly
selected and audited before the next decision. This finite screen does **not**
cover the product proposal's entire promotion envelope: adjacent-copy traversal,
mixed large/small content and deliberately nonempty initial caches remain
separate follow-on controls. Do not call the feature promotion-ready from these
screen cells alone.

## Resource and stop conditions

- Existing `ubuntu-24.04` runner; concurrency group `sprig-stress-pilot`, no
  parallel measurements; Cargo jobs2; no permissions/billing/security changes.
- Job hard limit45min. Original admission clock starts before setup and expires
  at40min. After builds, a **single** measurement deadline is at most1200sec,
  clipped to the original40min deadline. It includes all3 canaries and9screen
  samples and is **not reset** between invocations.
- Each sample uses a new2GiB Btrfs image. Original capacity guards require a
  256MiB image reserve and conservative retained estimate ≤1GiB, without clone
  or dedup credit. Host free space must cover the next2GiB image +1GiB evidence.
  Existing images, tree generations, cache entries and history are retained;
  do not reclaim them to improve a measurement or to hide a failure.
- Canary per-sample budget120sec; screen budget126sec under the existing
  `(1200-60)//9` division. Before and after image setup, require the full sample
  budget plus30sec normal-cleanup reserve. Each sampler preserves its own
  operation-before-start deadline and256MiB available-space safety checks.
- Historical samples previously around91sec suggest nine can fit1200sec; this
  is an admission estimate, **not** a promise. Slow setup, capacity, correctness,
  deadline or cleanup failure stops the cell without automatic expansion.
- No forced unmount, kill, discard/prune, restart, image enlargement, fault
  injection or blind retry. On uncertain outcome retain state and recovery
  metadata. Ephemeral runner termination is external to the harness.

The upload contains results, complete standalone reports/ledgers/log archives,
and original fixture manifests, including failures, but not multi-GiB images.
Images remain on the ephemeral runner until its normal termination. Physical
space metrics use whole-filesystem Btrfs **Used**, including retained trees,
cache and measured logs; no empty-image subtraction or logical-byte substitute.

## Reporting and decisions

The summary preserves every per-round paired ratio and every measured phase,
whole-sampler time, active and post-history Used. Whole time includes sampler
setup, correctness checks, accounting, normal cleanup and evidence serialization;
it excludes external fixture/image creation. Phase timings overlap: do not add
or subtract them to invent exclusive costs. Three observations support range,
median and geometric paired ratios, **not** trustworthy whole-run p95/p99.
History p95/p99 are dependent operations inside a sample, never extra trials.

Predeclared product screening thresholds: repeated median restore gain ≥10% on
intended many-reuse workloads; no >5% median whole-run or restore regression on
any negative control; no unaccounted repeated >10% tail regression. Preserve
x2 crossover losses and order sensitivity. Passing a promising cell only makes
it eligible for reviewed reverse-order confirmation; failed controls, missing
cells, unmeasured promotion-envelope cases, or insufficient evidence block
promotion. Do not tune the policy/cutoff to a selected passing fixture.

## Offline validation (root-owned, no mount or Rust)

Run serially from the repository root after files are frozen:

```sh
python3 -m unittest discover -s feasibility -p 'test_stress_cache*.py' -v
python3 -m unittest discover -s feasibility -p 'test_stress_run.py' -v
python3 -m unittest discover -s feasibility -p 'test_stress_sample.py' -v
python3 -m unittest discover -s feasibility -p 'test_stress.py' -v
```

Then syntax/YAML/actionlint where available and authored-file whitespace checks.
These tests cover finite Latin order, fixed pins/binary hashes, same-budget
canary gates, deadline expiration before image creation, exact raw oracle
mutation, missing/malformed samples, failed cleanup/capacity, source fixture
bounds, independent inodes versus true aliases, large64KiB eligibility, and all
three comparison edges. Offline tests do not constitute native performance or
Btrfs clone evidence.
