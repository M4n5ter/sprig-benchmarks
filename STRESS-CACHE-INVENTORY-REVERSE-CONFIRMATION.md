# Separate inventory-only reverse confirmation

**Local preparation; no launch until independent review, root-run tests and an
explicit decision after the current long mounted-pressure run is terminal/audited.**
This is not a replacement for the failed unique10000 admission control. Its
`f481aaba987d960bf119e95b68f5b38da56e1581` evidence and failed gate remain binding.

## Fixed new series, no source relabeling

`inventory-reverse-v1` uses the registered experimental-branch
`native-fork-ab.yml` route, with only `cache-large-64k-1024` permitted:

| Position label | Immutable source |
|---|---|
| A/main | `b300693e01c652c1a9631c61b7a439892d8f75cd` |
| B/inventory | `c392d45079314cdcf9813371ec9120d78be7bcd6` |
| C/portable | `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` |

Three fresh native canaries in ABC order precede exactly nine measurement samples
in **CBA/BAC/ACB** order. Every pin appears once per round and once per position.
The new explicit `--inventory-confirmation-stage` accepts only canary/reverse-Latin;
the old `--ablation-stage` remains canary/forward-Latin with unchanged admission
pins, distinct-binary requirement and original summaries. Modes cannot be mixed.
No implicit singleton, diagnostic-canary or unknown-pin fallback exists.

C is B plus one portable test-only repair in `src/file_cache.rs`. Exact source
checks require that to be the only changed tracked file and verify both full-file
hashes. Removing only the known `#[cfg(test)]` two-line injection seam and excluding
the single `#[cfg(test)] mod tests` suffix must yield production-prefix SHA256
`95fa75c3ee270cbff96b3dd5d8cc3cec6a5d48ba059839608609f0e2917ace49` in both.
Other source, Cargo/build inputs and tracked configuration must be unchanged.
All three checkouts must be exact/clean and binaries independently hashed before
and after each sample. B/C may honestly have equal release binary hashes, but
only in this fixed series with the known source-equivalence proof; A must remain
distinct. Binary/source paths must all be distinct. No differences are fabricated.
B→C is a **no-runtime-source-change/noise control**, not another optimization;
A→C measures the exact validated inventory-only candidate.

## Prior screen is a reviewed attestation, not a new raw audit

The four small files in `feasibility/cache-inventory-prerequisite/` are exact
bytes of the root-reviewed audit of actual
[run40302159760](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40302159760),
benchmark `93ce3366204a34eeefdd95ebc92aad1b2d976468`, original
[artifact12641212210](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40302159760/artifacts/12641212210).
They bind the completed run metadata, full217-file/22,776,206-byte manifest,
source/raw provenance audit and complete nine-sample independently recomputed
summary. Each exact content SHA is compiled into the new gate. The gate requires
the actual eligible64KiB cell, exact old A/B/admission pins, complete audit, all
three improving A→B restore pairs, restore median ratio≤0.90 and whole ratio≤1.05.
An arbitrary self-asserted `passed` value or a replacement hash is not accepted.

This is explicitly a **prior reviewed provenance attestation**, not an independent
fresh-job re-audit of the old22MB raw artifact. Original raw evidence is preserved
in that artifact and `/tmp/sprig-native-cache-audit-93ce336-large64k/`; the complete
control report/raw batch publication is a separate decision. The new run still
fully checks its own three canaries/nine samples, every archived exact oracle,
source/binary identity, historical readback and normal cleanup. Missing or changed
prior proof stops before any image or runtime command.

## Same finite resource and correctness contract

Existing Ubuntu24 runner/jobs2,45-minute hard job limit and original40-minute
admission clock. One≤1200-second measurement deadline shared across canaries and
all nine samples, never reset. Fresh2GiB images;256MiB reserve;≤1GiB conservative
retained charge; large cell uses1024 independently written64KiB files (64MiB logical,
448MiB conservative retained charge). One no-op checkpoint, one64-byte edit and
both historical snapshots remain in every sample. No extra cell, fault harness,
process killing, forced cleanup, image enlargement, permission or billing change.

All failed/partial samples and omitted timing markers are retained; any missing,
changed or malformed record, wrong source/proof/order, full-tree/exact-ns/hardlink
failure or uncertain cleanup suppresses comparisons. No rerun-to-green or discard.
Original admission screen summaries and guards stay separate and unchanged.

## Interpretation and root decision

Report all three edges, every pair and all slower phases. A→C restore median
ratio≤0.90 with whole ratio≤1.05 is the intended eligible-path confirmation signal,
not automatic promotion. B→C whole/restore median departures exceeding5% in either
direction flag noise/instability for review. Preserve failures and mixed results.
Three selected reverse rounds are not statistical significance, general storage
benefit, tail independence or broad-platform performance proof. Timers overlap;
never subtract phases to invent exclusive costs. Prior forward screen and new
reverse confirmation retain separate tables, pins, conditions and provenance.
The failed f481 unique10000 gate is neither waived nor retroactively reinterpreted.

## Root-owned validation after freeze

```sh
python3 -m unittest discover -s feasibility -p 'test_stress_cache*.py' -v
python3 -m unittest discover -s feasibility -p 'test_stress_run.py' -v
python3 -m unittest discover -s feasibility -p 'test_stress_sample.py' -v
python3 -m unittest discover -s feasibility -p 'test_stress.py' -v
```

Then Python syntax/YAML/authored diff checks and independent guard/source-proof
review. No local Rust build or Btrfs runtime is required for these tests. Source
4eb standard CI40305323322 passed all four jobs; explicit ReFS runtime remains
uncovered. No benchmark publication, dispatch or main merge follows from this
preparation document by itself.
