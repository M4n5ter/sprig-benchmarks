# Current-main Native smoke: four records, no automatic expansion

This is a new **smoke/correctness coverage series**, not a replacement for the
historical combined reports or the just-audited latest-main Cargo comparison.
It first establishes that the current Native and LayerFS paths can complete the
same frozen listed-file/history workload with fully retained evidence. One pair
per case is not a balanced statistical performance estimate.

## Fixed inputs and finite order

- Sprig main: `4eb0f4d7afdb19bf22d9667dc520ede8b162c737`, backend **native**.
- LayerFS unreleased main: `ad78914e36b258b360daf13aec164b5655814689`.
  This is not the older v1.1.0 release.
- Exact source HEADs, clean worktrees, Sprig ELF, LayerFS daemon, native addon and
  SDK entry hashes are checked before and after every sample. The first CI setup
  also compares both live main refs with these pins; drift stops, never repins.
- Exactly `sprig-native/identical`, `layerfs/identical`,
  `sprig-native/history-distributed`, `layerfs/history-distributed`.
- The unchanged `fixtures.py` seed-1 recipe generates only these two cases with
  count100. Identical has100 independent1MiB files; history has200 listed files,
  100 ordinary writes/commits and100 full historical readbacks per product.
- The Native history sample retains all103 physical generation directories.
  No restore tree, acknowledged history, failed command or slow sample is dropped.
- No projection, writable, full42, random matrix, pressure stage, fault harness or
  automatic retry is enabled. The writable diagnostic canary remains held.

The old `combined_compare.mjs`, `combined_sample.py` and historical source pins
remain untouched. Only the experimental branch's already-registered
`combined-paired.yml` body becomes this explicit manual-dispatch smoke job. The
old projection/writable kernel fault gates are absent, not reactivated.

## Original operation scopes and separate accounting boundaries

Both products preserve the frozen init/import/fork/full-SHA/read/write/commit/
historical-restore shell/API operations. Original active-space accounting stays
**before** historical restores. A second `postHistorySpace` stays **after** all
100 readbacks and unchanged-source/main/second checks, with three originals live.
These are separate whole-filesystem `Used` values; neither replaces the other.

The oracle proves the listed file bytes, unique acknowledged history and full
historical readbacks. It is **not** a complete metadata/hardlink oracle, power-loss
or equal-durability test. Native zero restore-cleanup time means no unmount exists;
it does not mean the retained Native trees were deleted.

New complete command capture and explicit measured `TMPDIR` add harness work.
Native CLI stdout/stderr stream to measured files during command wait. LayerFS
SDK returns strings; complete evidence writes follow its original phase timer.
Those scopes are not product-only or transport-equivalent. Native
`wholeTaskSeconds` covers execute plus post-history observation; its
`wholeSampleIncludingSetupCleanupSeconds` also covers setup, normal cleanup and
archive. LayerFS `fullTaskSeconds` covers the adapter lifecycle including evidence.
Show these scopes separately, never silently divide unlike whole-task timers.
Initialization-inclusive import/fork/read, individual common phases and both Used
boundaries can be shown descriptively after all four pass; no tail/significance
or general Native ranking follows from this smoke.

LayerFS uses Disposable WAL/OFF and workspace MEMORY/OFF; Sprig retains its
production sync behavior. LayerFS persistent UID501 SDK/container transport is
not the Native host CLI. Whole Used includes any product/runtime/log state in the
image; runtime-ready space is separately recorded, not subtracted into a claim of
exact application-only bytes.

### Precise temporary-directory correction

The new series sets an owned measured-root TMPDIR before the product CLI or SDK
is invoked. The old LayerFS direct API keeps its temporary template directory and
service in `STORES` until the final `storeClose`; the old combined adapter closes
the client only after both space boundaries. This demonstrates the *lifetime*,
not the old physical placement or byte count: the old TMPDIR value and allocated
bytes were not recorded. Do not retroactively quantify or invalidate old Used
from this source observation alone. Source evidence: [release direct.rs creation/storeClose](https://github.com/Ephemeral-AI-Lab/layerfs/blob/9f97a7ec95b662e9cb288704afa165feff132cfa/api/binding/src/direct.rs#L47-L118) and [historical combined accounting/close order](https://github.com/M4n5ter/sprig-benchmarks/blob/e06dcae965446c3dc9b5e86e6b53e7550cbc18de/feasibility/combined_compare.mjs#L100-L119). Individual private namespaces can retire
sooner. The latest-main Cargo comparison already bound TMPDIR inside its measured
root; this finding does not undercut that audited Cargo result.

## Resource and lifecycle admission

- Existing Ubuntu24 runner, jobs2,45-minute job, setup-inclusive40-minute absolute
  admission deadline shared by all samples. No deadline reset or extension.
- Each sample gets a fresh fixed2GiB Btrfs loop image. No resize/fallback. Before
  each image, host free space must cover2GiB image +1GiB evidence +512MiB headroom.
  Previous images remain retained; no deletion to force admission.
- The unchanged pure Cargo budget admission requires180 seconds work plus300
  seconds cleanup reserve both before runtime setup and before sample start.
  No Cargo4GiB capacity pilot is relabeled as Native evidence.
- Unknown child/SDK outcomes are sticky. No subsequent product command, forced or
  lazy unmount, signal, timeout kill, repeat unmount, volume deletion or automatic
  retry. First failure stops the finite series; every remaining position is
  explicitly `not_run`.
- Native requires known-zero owned mount and server inventories. LayerFS requires
  known-zero mounted workspaces before normal sandbox close, then known-zero
  project/helper containers. Empty arrays without knowledge flags do not pass.
- Only confirmed sampler cleanup admits strict runtime restoration, then ordinary
  `umount -i` and a separate unmounted observation. Failed or uncertain cleanup
  retains the image/runtime and is reported, never treated as complete.

## Complete bounded evidence

Source command/runtime logs remain in the measured image. Metadata ledgers and
lossless archive copies are external, separately declared and counted. No preview
substitutes for a full stream. Both samplers admit the *entire* archive plan before
creating it, check source identities/hash/size during bounded copies, and retain
originals on every failure. A partial archive is never called complete.

-2MiB acceptance per sampler stream;64MiB source logs;8MiB metadata ledger.
-128MiB aggregate Native stdout/stderr transport acceptance;16MiB standalone raw
JSON acceptance;64MiB complete four-record driver report; oversized bytes remain
retained and fail rather than get truncated.
- Fixed1GiB total named external evidence. Before each sample, actual inventory
must leave256MiB pending raw/ledger/driver/summary headroom plus2MiB collector
manifest reserve. The archive allowance is the remaining budget, not a new cap.
Every atomic report write is additionally checked against actual current external
bytes before writing. No selected-subset copying to make a sample pass.
- Collector streams a full admitted allowlisted plan into independent files,
checks every declared archive against copied bytes, and preserves failed/not-run
reports. It does not modify original permissions or copy images/user files.
- Offline summary binds actual identity/fixture/report bytes, full log hashes,
original/retained/history readbacks and both cleanup/resource boundaries. Any
malformed/missing/failing record suppresses **all** paired ratios.

The actual job records host Node/npm, Rust build tools, immutable runtime image,
source/build hashes and complete normal setup outputs. No raw evidence or claims
exist yet for this new smoke. Root review and serial inert tests precede any
publication/dispatch; full42 requires this actual smoke plus a separate decision.
