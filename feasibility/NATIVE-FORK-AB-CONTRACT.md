# Native fork isolated A/B

This version-only series compares baseline `a2b76e4c3ecdccdeeca24a669df4a82d1a4792f3` with descendant `e2a86dc2b7942e0adf4273cd608857447d403335`. It is native-only and reuses the unchanged lifecycle sample, fixture operations, paired schedule, strict summary, physical-accounting boundaries and safe temporary-image lifecycle in [LIFECYCLE-AB-CONTRACT.md](LIFECYCLE-AB-CONTRACT.md).

The two tiny entrypoint wrappers only install these separately fixed source pins before calling the same driver and summarizer. Generic output names remain lifecycle-ab.json and lifecycle-ab-summary.json; pins in those files and the separately named native-fork artifact identify this experiment. Original lifecycle results and source files are not modified. Smoke is 4 samples/200 readbacks; full is 70 samples/3,000 readbacks on one runner. Neither constitutes an updated LayerFS comparison.

Both actual production binaries use independent target directories and the same compiler/profile/features. Source/binary hashes are checked, all synchronization stays enabled, and three live views plus all historical restored trees remain charged. Warm fork and initial preparation are the targeted metrics; checkpoint/restore/space regressions remain visible, never excluded.
