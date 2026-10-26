# Latest-main Native smoke: stopped on an uncertain LayerFS control outcome

[Run 40338242966](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40338242966)
actually **failed**. It is not a completed performance comparison. No paired
ratios are available and no automatic rerun/full 42 expansion followed.

- Benchmark: `af859651150e8a2835cf3fd4e0e5dcb07914b34e`.
- Sprig main: `4eb0f4d7afdb19bf22d9667dc520ede8b162c737` (Native).
- LayerFS unreleased main: `ad78914e36b258b360daf13aec164b5655814689`.
- Four predeclared records; fresh 2 GiB images; jobs 2; shared 40-minute admission and
  45-minute job cap. All setup/build/source gates passed. Job elapsed 7m 14s.

| Record | Actual sampler/outer result | Evidence retained |
|---|---|---|
| Sprig Native identical | Passed | Listed bytes, original views, both Used boundaries, known-empty cleanup |
| LayerFS identical | Passed at runtime and in corrected offline audit; original audit rejected a valid void-return event | Complete raw output and normal cleanup; original rejection preserved |
| Sprig Native history-distributed | Passed | 100 unique acknowledgments/full historical reads;103 retained directories; both Used boundaries and cleanup |
| LayerFS history-distributed | **Failed** | 100 historical reads completed, but post-history control query failed; no postHistorySpace or confirmed cleanup |

## Actual failure, not inferred cause

After the LayerFS history sample completed 100 historical full SHA readbacks and
unchanged main/second/source checks, `sandbox.list_workspaces` returned a control
receive `UnexpectedEof`. Its outcome became uncertain. The harness correctly
stopped, did not retry the query, did not close the possibly live sandbox, did not
restore the runtime or unmount the image, and did not claim complete cleanup. The image was left to the ephemeral
runner for teardown; it was not uploaded as a filesystem backup. Only the complete
named log/raw evidence archive is available after the job.

The complete named source-log archive and raw failed report were retained. This
shows where the control exchange failed, not why: it does not establish a data
corruption, durability, capacity or product-regression cause. The earlier active
space reading was 105,521,152 B with substantial free space, but that is **before**
the historical restores, not a failure-time space probe. No causal conclusion is
based on that older snapshot.

An independent read-only partial audit verified the failed sample's 100 changed
file reads, 100 complete historical readbacks, 100 unique acknowledged commit IDs,
and unchanged source/main/second checks from complete archived output. This is
partial workload evidence only: missing post-history observation and uncertain
cleanup remain binding failures. It does not turn the sample or comparison green.

## Source-derived response-size hypothesis (not a captured server cause)

Read-only source review found that the operator snapshot budget counts history,
branches and workspaces but omits the separately assembled `more` cursor map.
A model using this run's 103 forks and 100 captured commits yields 52,373 counted
bytes plus 19,327 cursor-map bytes: 71,700 B before remaining outer fields, above the
65,519B control limit. The source encode-error path closes/fences the exchange,
which is consistent with the client-side EOF. Relevant pinned source:
[operator snapshot budgeting](https://github.com/Ephemeral-AI-Lab/layerfs/blob/ad78914e36b258b360daf13aec164b5655814689/core/crates/layerfs-store-service/src/operator/inspect.rs#L114-L240),
[wire limit](https://github.com/Ephemeral-AI-Lab/layerfs/blob/ad78914e36b258b360daf13aec164b5655814689/core/crates/layerfs-bridge/src/wire.rs#L3-L15),
[encode/fence/close path](https://github.com/Ephemeral-AI-Lab/layerfs/blob/ad78914e36b258b360daf13aec164b5655814689/core/crates/layerfs-daemon/src/control/serve.rs#L95-L139), and
[binding-side filtering after the response](https://github.com/Ephemeral-AI-Lab/layerfs/blob/ad78914e36b258b360daf13aec164b5655814689/api/binding/src/dispatch.rs#L56-L104).
The daemon-side cause was not
captured, so this remains a specific source-derived hypothesis, not a confirmed
causal diagnosis. It is not a reason to drop the post-history observation, delete
retained branches, shrink the workload silently or claim a repaired comparator.

## Two separate offline schema findings

The original offline audit accepted the two Native records and correctly rejected
the failed history sample. It also rejected the runtime-successful LayerFS
identical record because successful `client.close` returns JavaScript `undefined`;
JSON therefore omits its `result` property. The separately tested analysis correction permits that
exact void-return operation only with the other normal-cleanup proof; it does not
invent a null result or waive arbitrary missing SDK results.

A separate read-only audit found that real history pages are bounded by response
size: the final 100 IDs arrived as 46+46+8, with `hasMore=true,true,false`, after an
empty baseline page. The producer correctly handled pagination. The original
offline parser incorrectly assumed a single final page. The analysis correction verifies both complete pagination sequences, exact
nextPagePos progress/termination and all unique newest-first acknowledged IDs.
Neither schema correction supplies missing post-history/cleanup evidence or
rescues this failed comparison. Original raw bytes and original failed CI summary
are immutable.

After 37 inert regression tests passed, the corrected helper was applied only to
the same captured bytes: accepted records changed from 2 to 3, with 100 accepted
Native historical readbacks; the LayerFS history record remains failed.
`complete:false` and `ratios:null` are unchanged. No product/runtime code changed
and no measurement was rerun. [Corrected helper](https://github.com/M4n5ter/sprig-benchmarks/blob/e7aeb2babee08a3ef5767eea734387f9a8767bb5/feasibility/latest_combined_summary.py) SHA256:
`73af895dc0000c5696c313c344db0fd765240d43348bce2b82a073fbe7df01b9`.

## Complete evidence and provenance

[Original artifact 12658797326](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40338242966/artifacts/12658797326)
contains 2,008 files / 30,723,169 B; compressed transfer 2,133,854 B. Collection copied
all 2,007 listed members / 30,125,890 B, including 1,812 unique declared log files.
Collection evidence/copy gates passed while benchmarkComplete remained false.
Every copied file hash and complete pathset was verified; 16 benchmark script,
43 Sprig source/build,1,552 LayerFS source/build and 2 exact offline helper hashes
were checked against pinned committed objects. Independent reanalysis reproduces
the original failed summary exactly; the separate posthoc result records only the
two schema corrections described above. All original bytes were rehashed after
reanalysis. No measurement rerun or original-byte edit.

The [1,767,513 B lossless durable archive](data/stress-20261026/latest-native-smoke-failure/README.md)
contains every original artifact file, original helpers and provenance; every
member round-trips byte-for-byte. Its README separates original failed analysis
from the adjacent new posthoc outputs. The original public CI artifact remains
an additional evidence source.

This is a smoke/listed-file/history coverage attempt, not metadata/hardlink parity,
equal durability, balanced statistics or a basis to rank overall Native speed.
The successfully audited latest-main Cargo result remains separate and unchanged.
