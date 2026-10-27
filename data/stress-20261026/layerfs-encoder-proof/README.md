# Lossless source-only encoder evidence

`layerfs-source-encoder-proof.tar.gz` preserves all original public artifacts:

- [Success 40360200739 / artifact12668606135](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40360200739/artifacts/12668606135):55 files,1,185,721 bytes.
- [Harness failure40356426815 / artifact12667025282](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40356426815/artifacts/12667025282):37 files,1,159,589 bytes.
- [Cancelled unintended push40355668729 / artifact12663814837](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40355668729/artifacts/12663814837):1 file,4,918 bytes; full public job log separately included.

Additional members are public run/artifact metadata, exact helper Git objects and labeled post-hoc audits. No private local auditor script, user files or credentials are included. Eight secret-pattern classes had zero matches; that scan supplements, not replaces, the explicit public-source provenance audit. No build binaries or runner images are archived. Original Native failure/ratios null are unchanged.

Verify compressed SHA-256 against `manifest.json`, extract into a fresh owned directory, then verify each regular member's byte count and SHA-256 against `manifest.json.members`. Reject links, absolute paths, `..` components, duplicate names or unlisted members before extraction. The archive contains only flat/nested regular files and no symlinks. A complete round-trip verification was performed before publication.

The embedded helper sources and original source-only workflow reproduce the proof contract; running them against a fresh build is a new execution, not required to inspect this evidence. Offline `posthoc-cargo-structure.json` is explicitly structural only: it does not rehash absent ephemeral build artifacts or independently rerun the encoder. Live CI linkage/execution receipts and actual proof stdout are separately retained.
