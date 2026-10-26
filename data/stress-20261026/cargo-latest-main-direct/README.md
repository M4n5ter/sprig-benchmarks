# Complete latest-main Cargo evidence: run40327569055

This lossless bundle preserves **every one of the1,416 original public CI artifact
files /29,855,368 bytes**, including all raw reports, complete logs, negative timing
observations and original successful summary. Nothing is selected away. It also
contains six exact benchmark-commit analysis helpers and public source/provenance
records. See `manifest.json` for every member's byte count/SHA256 and the archive's
complete compressed-byte hash. `disclosure-audit.json` records origin checks and
eight secret-pattern classes (zero matches); no user files or credential config.

- Public run: https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40327569055
- Original artifact12654595029: https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40327569055/artifacts/12654595029
- Benchmark: `02dfe69f4b868fd47bd2fb5e91d3f4fbbab37707`.
- Sprig main: `4eb0f4d7afdb19bf22d9667dc520ede8b162c737`.
- LayerFS unreleased main: `ad78914e36b258b360daf13aec164b5655814689`.

Archive ownership/time/mode are normalized container metadata. Original measured
filesystem metadata are retained exactly in unchanged raw oracle JSON. Compressed
archive bytes are not workload physical Used. All members were round-trip hashed
and byte-compared against their original local public-artifact/helper sources.

## Read-only verification and exact raw reanalysis

Run the verifier first; it reads every member but does not extract or run products:

```sh
python3 verify_evidence.py
```

Extract only into a **new empty directory** after verification:

```sh
mkdir /tmp/sprig-run40327569055-evidence
# Run from this bundle directory.
tar -xzf run-40327569055-evidence.tar.gz -C /tmp/sprig-run40327569055-evidence
cd /tmp/sprig-run40327569055-evidence
PYTHONDONTWRITEBYTECODE=1 python3 tools/stress_cargo_latest_summary.py \
  --inc0 artifact/results/stress-cargo-comparison-0.json \
  --inc1 artifact/results/stress-cargo-comparison-1.json \
  --archive-root artifact/records \
  --output /tmp/sprig-run40327569055-recomputed.json
```

The output must be a new path; the helper does not overwrite original evidence.
It runs no Sprig, LayerFS, Cargo, Docker, mount or benchmark operation. All eight
samples must pass before paired ratios are emitted. Compare its `comparisons`,
`unmatchedMetrics`, `slowerOrLargerPairs`, `identity` and per-sample metrics with
`artifact/results/stress-cargo-latest-direct-summary.json`; local `reportPath`
strings naturally depend on the extraction location. Python bytecode writes are
disabled explicitly so reanalysis leaves the extracted evidence tree untouched.

The source-input audit checked43Sprig and1,552LayerFS source/build hashes against
exact committed objects. Its result is `provenance/provenance-audit.json`;
`source-proofs/overrides` preserves the one changed LayerFS API source used when
checking the current-main tree against the previously available release objects.
This attestation is not a claim that extraction itself freshly fetches or
independently reconstructs both Git repositories. Raw CI source-hash manifests,
fixed source pins and captured public tree/diff metadata remain available.

Two pairs per mode on one runner are descriptive observations, not stable tails,
significance or equal-durability measurements. The report preserves that Sprig is
slower in whole Cargo wall, despite a faster isolated product checkpoint boundary.
