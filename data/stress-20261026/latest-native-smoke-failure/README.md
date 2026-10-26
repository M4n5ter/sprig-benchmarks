# Complete failed Native-smoke evidence: run 40338242966

This lossless archive preserves **all 2,008 original artifact files / 30,723,169 B**,
including every failed report, complete declared log, original failed summary and
collection manifest. No negative or slow observation is selected away. The 2,019
members also include two exact original benchmark-commit offline helpers, one
changed public LayerFS source file and eight public CI/provenance/partial-audit
records. Every member was round-trip hashed and byte-compared with its source.

- [Actual failed run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40338242966)
- [Original artifact 12658797326](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40338242966/artifacts/12658797326)
- Benchmark `af859651150e8a2835cf3fd4e0e5dcb07914b34e`.
- Sprig main `4eb0f4d7afdb19bf22d9667dc520ede8b162c737`.
- LayerFS unreleased main `ad78914e36b258b360daf13aec164b5655814689`.

`manifest.json` binds the compressed archive and every member's size/SHA256.
`disclosure-audit.json` records public origins and eight secret-pattern classes,
all zero matches. No user files or credential configuration are included.
The failed runtime image was retained by the harness for runner teardown, not
uploaded; this is the complete named evidence archive, not a full filesystem backup.
Archive ownership/time/mode are normalized container metadata, not a rewrite of
measured metadata inside raw JSON. Compressed bytes are not filesystem Used.

## Read-only verification and reproduction of the ORIGINAL failed analysis

```sh
python3 verify_evidence.py
mkdir /tmp/sprig-native40338242966-evidence
# From this bundle directory, after verifying all member hashes:
tar -xzf run-40338242966-evidence.tar.gz -C /tmp/sprig-native40338242966-evidence
cd /tmp/sprig-native40338242966-evidence
PYTHONDONTWRITEBYTECODE=1 python3 tools/latest_combined_summary.py \
  --input artifact/results/latest-combined-comparison.json \
  --archive-root artifact/records \
  --output /tmp/sprig-native40338242966-original-reanalysis.json
```

The last command is **expected to exit 1**, with `complete:false`, two accepted
Native records, 100 accepted historical readbacks and `ratios:null`. This reproduces
the actual failed CI analysis; do not mistake expected reproduction for a passed
benchmark. The output path must be new. No products, subprocesses, mounts or
benchmark workload execute during this reanalysis; bytecode writes are disabled.

The original parser separately rejected a valid void `client.close` result and
assumed one final history page. Those analysis defects are preserved here exactly,
not silently patched into the original run. A separately reviewed, 37-test-validated posthoc helper corrects schema
classification only: 3 records accepted,100 accepted Native historical readbacks,
`complete:false` and `ratios:null`. It cannot create the missing LayerFS
post-history observation or confirmed cleanup. The adjacent posthoc-summary.json
and posthoc-provenance.json are NEW outputs, outside the immutable original tar,
and bind the corrected helper by SHA256; original helper/summary bytes remain
inside the tar unchanged. The actual run remains failed and
no complete comparison ratios are available.

To reproduce the NEW posthoc result, use the corrected repository helper (verify
its SHA256 against `posthoc-provenance.json`) from the repository root, with the
same extracted inputs and another new output path:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 feasibility/latest_combined_summary.py \
  --input /tmp/sprig-native40338242966-evidence/artifact/results/latest-combined-comparison.json \
  --archive-root /tmp/sprig-native40338242966-evidence/artifact/records \
  --output /tmp/sprig-native40338242966-posthoc-reanalysis.json
```

This also **exits 1**: three accepted records are not a completed comparison.

`provenance/partial-history-audit.json` is a read-only audit attestation for 100
LayerFS historical/changed reads, unique acknowledged IDs and unchanged originals
before the control EOF. It is not acceptance of that failed sample. All underlying
raw checks and logs remain in the archive. The source-input audit checked 16
benchmark,43 Sprig and1,552 LayerFS source/build hashes against immutable objects;
extraction itself does not newly fetch/reconstruct those repositories.

The complete archive, manifest, verifier and adjacent posthoc outputs accompany
this README. The [corrected helper](https://github.com/M4n5ter/sprig-benchmarks/blob/e7aeb2babee08a3ef5767eea734387f9a8767bb5/feasibility/latest_combined_summary.py)
is a separate analysis-only commit. The original public CI artifact remains an
additional evidence source.
