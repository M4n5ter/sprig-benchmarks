# Six-run evidence publication: reports and manifests only

This directory contains **no raw archive blobs**. Current complete raw evidence is
in the verified public Actions artifacts linked from `index.json` and each report.
All six archived source file sets were independently audited; failure/negative
results are preserved. Finite GitHub retention means this is not yet durable Git
storage of the full evidence. Prepared lossless archives remain pending publication.

Each run contains:
- `artifact-files.json`: every original public artifact file, relative path, size,
  SHA256; this includes all samples/failures, not a selected subset.
- `artifact-metadata.json`: verified actual artifact identity, source head, size,
  expiry, public API URLs and GitHub ZIP digest when supplied.
- `provenance-audit.json`: actual exact-source/raw audit result, not a new product run.
- `prepared-archive.json`: SHA/size of the separate prepared lossless tar.gz, clearly
  marked **not included/published**. The GitHub ZIP and prepared tar.gz have different
  contents/encoding and therefore different sizes/hashes; do not conflate them.
- `prepared-archive-files.json`: full member identities for that pending tar.gz,
  including the untouched raw artifact plus exact-source tools and derived audits.
  Tar packaging timestamps/ownership are normalized; source-file bytes/path/mode
  are lossless, and actual filesystem metadata is retained in raw oracle JSON.
  Draft report snapshots inside archives predate publication-link wording updates.

For current raw download, use the exact run and repository from `index.json`:

```sh
gh run download RUN_ID --repo M4n5ter/sprig-benchmarks --dir NEW_EMPTY_DIRECTORY
```

With no artifact-name filter, the CLI retains artifact-name directory prefixes
used in each manifest. Check every file's size/SHA256 against `artifact-files.json`
and reject missing or extra files; do not silently omit failed samples. Read the
source-pinned workflow/summary at the benchmark commit before reproducing analysis.
No resource increases, measurements or dispatches are part of this report batch.
