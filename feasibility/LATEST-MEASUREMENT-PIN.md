# Latest production pin, unchanged seven-scene protocol

Latest series: production Sprig e38225e1e1160e8de90aa911d6f1740bef93bacc,
fresh stores initialized with default **auto compression**; release LayerFS v1.1.0
9f97a7ec95b662e9cb288704afa165feff132cfa remains unchanged.

All rules in CURRENT-MEASUREMENT-BOUNDARIES.md apply. `latest_sample.py` differs
from the frozen current_sample.py only in the provenance SHA and an explicit
compressionPolicy report field. `latest_compare.mjs` changes only driver/output
paths and provenance assertions. The fixture, commands, operation order, full
history readbacks, three active workspaces, timing and physical accounting are
unchanged. No GC, retention application, pruning or extra product optimization is
performed by this harness. Source schema is not hard-coded.

Original fba02ad baseline raw is retained separately; different hosted runners
cannot establish a strict same-machine old-to-new causal speedup. Each current
Sprig/LayerFS pair is measured on its own shared runner under this protocol.
Latest default-auto results do not establish raw/no-compression performance.
Compiler software/runtime versions, CPU/cache differences and durability limits
remain visible in original run artifacts and the shared measurement contract.

The summary helper retains its historical filename current-summary.json/csv
inside each uniquely named latest-BACKEND artifact. Its input is explicitly
latest-comparison.json containing the new production SHA and auto policy.
