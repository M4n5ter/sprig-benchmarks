# LayerFS response-size discriminator: source-only encoder result

The pinned public encoder **rejected all eight reconstructed response subsets** for exceeding its unchanged 65,519-byte control-record limit. This strengthens the source-derived size explanation for the earlier Native smoke EOF, but **does not capture the actual daemon response or establish the actual EOF cause**. The Native comparison remains failed; comparison ratios remain unavailable.

## Actual execution

[Successful source-only run 40360200739](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40360200739) used benchmark commit `1a3d18009028704b6af64810159f89113f2baad9`, LayerFS `ad78914e36b258b360daf13aec164b5655814689`, and Rust/Cargo 1.85.1. It built the original locked/offline release daemon dependency closure (`layerfs-bridge` default + duplex), then linked an external local-value proof to that build's exact bridge artifact. No daemon, socket, Store, SQLite runtime, image, Docker or mounted workload was executed.

| Encoder check | Actual result |
|---|---|
| Small answer round trip | Pass |
| Exactly 65,519 encoded bytes | Round trip passes |
| 65,520 encoded bytes | Rejected: `control record limit` |
| Eight source-derived subsets | All rejected with the same limit error |

The eight source-model predicted encoded sizes were **71,643; 71,690; 71,690; 71,737; 71,690; 71,737; 71,737; 71,784 bytes**. They are structural subsets reconstructed from recorded branch/commit shapes and explicitly labeled byte-width placeholders, not fabricated daemon receipts. Exact frozen nine-line expected output matched actual stdout; compile/proof exits were zero, stderr empty, and all owned command groups settled without capture overflow. Command durations are diagnostic execution metadata, not product performance results.

The live CI gates bound the same unique bridge Cargo artifact's `.rmeta` and `.rlib`, daemon-library metadata extern, daemon-binary direct bridge extern and daemon-library alias hash, plus the immutable workflow's proof-compile argv. All 1,552 recorded source-file hashes and clean source identity were checked. Proof ELF before/after SHA-256 was `aa3fca00ba2974a99a2f0c53ab0777bb3243dd3fd9762310c64344284e071e71`. Build ELFs/rlibs/rmeta were ephemeral: the archive contains their CI receipts/hashes, **not binary backups or a fresh local rehash of those binaries**.

## Failed and unintended attempts retained

- [Original source-only attempt 40356426815](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40356426815) failed in harness linkage analysis after a successful daemon build. Cargo verbose build-script lines were mixed with JSON, and pipelining used bridge metadata for the daemon library. The proof was **not compiled or executed**. The narrow parser correction strictly binds verbose prefixes to actual custom-build package IDs and the locked source, and metadata/rlib filenames to the same unique artifact. Original logs and failure remain unchanged.
- [Unintended push-triggered run 40355668729](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40355668729) was cancelled and verified terminal before the manual proof. Its Sprig smoke, controlled runtime and repeated comparison steps were all **skipped**. The experimental branch's legacy push workflow now excludes only this exact diagnostic ref in addition to its existing stress-ref exclusion; no default-branch or blanket workflow change was made.
- [Native smoke 40338242966](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40338242966) is still a failed overall comparison. Its EOF followed 100 LayerFS historical readbacks, but post-history space and known-clean cleanup were unavailable. No mounted rerun, comparator patch, crash/OOM/data-loss conclusion, or performance ratio follows from this encoder experiment. See the [unchanged Native failure report](LATEST-COMBINED-NATIVE-SMOKE-FAILURE.md).

## Complete durable evidence

The [lossless archive](data/stress-20261026/layerfs-encoder-proof/layerfs-source-encoder-proof.tar.gz), [per-file manifest](data/stress-20261026/layerfs-encoder-proof/manifest.json) and [extraction instructions](data/stress-20261026/layerfs-encoder-proof/README.md) preserve all **93 original artifact files** across the successful, failed and cancelled runs, public run/artifact metadata, the cancelled job log, original immutable helper sources and separately labeled offline audits. The archive has 115 files / 2,591,948 uncompressed bytes; compressed size 385,052 bytes, SHA-256 `6267d7650efe98849abe7ce8525277a0d66c82be407c9e527b84832411bdc083`. Every member was round-trip verified against its original bytes; no failed sample, log or raw fixture was trimmed.
