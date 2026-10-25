# Native fork: isolated same-runner A/B

25 October 2026. Baseline `a2b76e4c3ecdccdeeca24a669df4a82d1a4792f3` versus candidate `e2a86dc2b7942e0adf4273cd608857447d403335`, native backend and default auto compression. Benchmark `a5c94333294625262327d2cd374b7d6774990530`. This isolates the native-fork change, not the earlier lifecycle candidate and not a fresh LayerFS comparison.

**Full: 70/70 records, 3,000 historical readbacks. Earlier smoke: 4/4 records, 200 readbacks.** Both original artifacts are retained separately. The full series uses five adjacent AB/BA pairs on one runner. The smoke uses a separate runner and cannot be pooled into a sixth pair.

## Finding

In the four larger nonhistory cases, warm fork plus full read has median paired ratios of 0.538–0.576 (about 42–46% lower time), and preparation ratios of 0.794–0.852 (about 15–21% lower). All 20 large-case warm pairs improve. The change removes a meaningful native-fork cost without a material large-case storage reduction.

The three history-case warm tasks have median paired ratios of 0.947, 0.930 and 0.982. The earlier distributed smoke slowdown is preserved below but does not recur across the five full pairs; one hotset warm pair is still 0.74% slower. Checkpoint and total restore/read/cleanup do not improve: median paired ratios are roughly 1.004–1.009. In recurring history, all five checkpoint samples are 0.3–1.1% slower; complete restore/read/cleanup is slower in 12 of the 15 history pairs. These observations are not hidden or explained away as proven noise.

Physical medians for the larger cases are essentially unchanged; small individual allocation differences and uncontrolled history-space differences remain visible. This is a targeted warm-fork improvement, not a general checkpoint/restore/storage improvement and not evidence of beating LayerFS under equal durability.

## Boundaries

- The frozen lifecycle sample, fixtures, operation timers, durability and safe cleanup are unchanged. Only the two fixed source pins and entrypoint wrappers differ. Each version uses a separate verified target directory with matching compiler/profile/features.
- Preparation includes initialization/import/first usable fork/full read; warm is usable fork plus full read. No cold-cache claim or software-installation timing.
- Primary whole-Btrfs Used delta is sampled with three original views live, before historical restores. A second sample follows all historical readbacks/normal cleanup, retaining the native restored trees. Components are later diagnostics, not additive exclusive physical extent accounting.
- Fresh imports use independent entry identities; identity-dependent metadata page sharing is an uncontrolled potential contributor to history-space differences, not an explanation proven by a particular run.
- Tables show individual medians and median within-pair ratios separately. A ratio of medians is not the median paired ratio. Ranges and every raw pair remain visible.
- Listed bytes/history readback and production gates passed; this is not a new crash/power-loss proof or complete metadata compatibility benchmark. No GC/pruning or weakened durability is used.

[Protocol](feasibility/NATIVE-FORK-AB-CONTRACT.md) · [Full run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40160664806) · [Smoke run](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40160178206)

## full

[Complete original artifact](data/native-fork-20261025/full-40160664806-full-artifact.tar.gz) · [Every pair/summary](data/native-fork-20261025/full-summary.json)

| Case / task | Baseline | Candidate | Paired B/A | Paired range |
|---|---:|---:|---:|---:|
| identical / preparation | 901.171 ms | 718.407 ms | 0.7943 | 0.7898–0.8005 |
| identical / warm fork/read | 396.876 ms | 215.891 ms | 0.5411 | 0.5332–0.5551 |
| identical / active space | 101.637 MiB | 101.637 MiB | 1.0000 | 0.9997–1.0000 |
| identical / post-history space | 101.641 MiB | 101.641 MiB | 1.0000 | 0.9997–1.0000 |
| unique / preparation | 1058.871 ms | 901.891 ms | 0.8520 | 0.8483–0.8535 |
| unique / warm fork/read | 377.858 ms | 214.108 ms | 0.5761 | 0.5622–0.5801 |
| unique / active space | 201.000 MiB | 201.000 MiB | 1.0000 | 0.9998–1.0002 |
| unique / post-history space | 201.004 MiB | 201.004 MiB | 1.0000 | 0.9998–1.0002 |
| mixed / preparation | 1008.479 ms | 851.165 ms | 0.8416 | 0.8327–0.8547 |
| mixed / warm fork/read | 372.816 ms | 212.853 ms | 0.5681 | 0.5435–0.5757 |
| mixed / active space | 175.844 MiB | 175.844 MiB | 1.0000 | 1.0000–1.0005 |
| mixed / post-history space | 175.910 MiB | 175.910 MiB | 1.0000 | 1.0000–1.0002 |
| insert / preparation | 941.745 ms | 748.453 ms | 0.7972 | 0.7943–0.8045 |
| insert / warm fork/read | 403.898 ms | 218.424 ms | 0.5385 | 0.5162–0.5598 |
| insert / active space | 111.504 MiB | 111.504 MiB | 1.0000 | 0.9997–1.0000 |
| insert / post-history space | 111.508 MiB | 111.508 MiB | 1.0000 | 0.9997–1.0000 |
| history-distributed / preparation | 765.715 ms | 743.229 ms | 0.9852 | 0.9083–1.0262 |
| history-distributed / warm fork/read | 350.497 ms | 334.332 ms | 0.9470 | 0.9361–0.9681 |
| history-distributed / 100 checkpoints | 4.159 s | 4.159 s | 1.0039 | 0.9955–1.0054 |
| history-distributed / 100 restore+read+cleanup | 33.541 s | 33.513 s | 1.0059 | 0.9950–1.0127 |
| history-distributed / active space | 9.555 MiB | 8.613 MiB | 0.9015 | 0.8810–1.0033 |
| history-distributed / post-history space | 171.875 MiB | 171.379 MiB | 0.9962 | 0.9923–1.0042 |
| history-hotset / preparation | 759.979 ms | 729.577 ms | 0.9484 | 0.9270–0.9741 |
| history-hotset / warm fork/read | 350.727 ms | 322.776 ms | 0.9303 | 0.9055–1.0074 |
| history-hotset / 100 checkpoints | 4.186 s | 4.197 s | 1.0050 | 0.9921–1.0474 |
| history-hotset / 100 restore+read+cleanup | 32.607 s | 33.117 s | 1.0075 | 0.9784–1.0483 |
| history-hotset / active space | 13.016 MiB | 12.922 MiB | 1.0000 | 0.9700–1.0535 |
| history-hotset / post-history space | 175.227 MiB | 175.484 MiB | 1.0016 | 0.9961–1.0056 |
| history-recurring / preparation | 739.623 ms | 745.135 ms | 1.0068 | 0.9746–1.0885 |
| history-recurring / warm fork/read | 335.843 ms | 331.726 ms | 0.9818 | 0.9665–0.9940 |
| history-recurring / 100 checkpoints | 3.797 s | 3.823 s | 1.0087 | 1.0032–1.0114 |
| history-recurring / 100 restore+read+cleanup | 32.592 s | 32.926 s | 1.0068 | 1.0020–1.0123 |
| history-recurring / active space | 6.434 MiB | 6.434 MiB | 1.0000 | 0.9952–1.0079 |
| history-recurring / post-history space | 169.020 MiB | 169.246 MiB | 1.0005 | 0.9965–1.0031 |

## smoke

[Complete original artifact](data/native-fork-20261025/smoke-40160178206-full-artifact.tar.gz) · [Every pair/summary](data/native-fork-20261025/smoke-summary.json)

| Case / task | Baseline | Candidate | Paired B/A | Paired range |
|---|---:|---:|---:|---:|
| identical / preparation | 945.177 ms | 766.389 ms | 0.8108 | 0.8108–0.8108 |
| identical / warm fork/read | 405.706 ms | 221.178 ms | 0.5452 | 0.5452–0.5452 |
| identical / active space | 101.637 MiB | 101.637 MiB | 1.0000 | 1.0000–1.0000 |
| identical / post-history space | 101.641 MiB | 101.641 MiB | 1.0000 | 1.0000–1.0000 |
| history-distributed / preparation | 747.051 ms | 808.189 ms | 1.0818 | 1.0818–1.0818 |
| history-distributed / warm fork/read | 337.935 ms | 369.095 ms | 1.0922 | 1.0922–1.0922 |
| history-distributed / 100 checkpoints | 4.336 s | 4.492 s | 1.0360 | 1.0360–1.0360 |
| history-distributed / 100 restore+read+cleanup | 36.008 s | 36.232 s | 1.0062 | 1.0062–1.0062 |
| history-distributed / active space | 9.586 MiB | 9.586 MiB | 1.0000 | 1.0000–1.0000 |
| history-distributed / post-history space | 172.293 MiB | 172.324 MiB | 1.0002 | 1.0002–1.0002 |

[Archive checksums and provenance](data/native-fork-20261025/manifest.json). All slower samples and storage observations are retained; raw archives are unchanged.
