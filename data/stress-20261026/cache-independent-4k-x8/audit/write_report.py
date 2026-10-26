import json,statistics
from pathlib import Path
ROOT=Path('/tmp/sprig-native-cache-audit-afacf84')
s=json.loads((ROOT/'posthoc-summary.json').read_text());prov=json.loads((ROOT/'posthoc-provenance.json').read_text());audit=json.loads((ROOT/'provenance-audit.json').read_text())
run=json.loads((ROOT/'run-status.json').read_text());report=next(json.loads(p.read_text()) for p in (ROOT/'artifact').rglob('stress-comparison.json') if json.loads(p.read_text())['ablationStage']=='forward-latin')
pct=lambda x: 'unavailable' if x is None else f'{(x-1)*100:+.3f}%'
fmt=lambda x:f'{x:.6f}' if isinstance(x,(int,float)) else str(x)
lines=['# Native cache independent4KiB ×8 screen results','',
'**One intended-reuse cell shows a restore improvement, not promotion readiness.**',
'Inventory→admission median paired restore time improved16.34% (all3 pairs faster);',
'whole-sampler median improved2.46%, with one pair0.48% slower. Main→admission',
'median restore improved21.05% and whole-sampler median5.60%. Negative controls,',
'large-file inventory-path evidence and reverse-order confirmation remain unmeasured.','',
'## Failed CI and transparent same-sample analysis correction','',
'[Run40294193428](https://github.com/M4n5ter/sprig-benchmarks/actions/runs/40294193428)',
'at benchmark `afacf84f0c6c80014c0e7c3cc00fac348357afbe` ended **failure**, after9m19s.',
'Three native canaries and all nine screen sampler invocations succeeded. The final',
'analysis rejected the inherited explicitly omitted `metadata_branch_seconds=null`',
'probe in every row. The original failed summary and all nine errors are preserved.',
'The separately reviewed analysis-only fix `ad7bfdd873a79bd03ee33f1525a5b08303addf4f`',
'passed root-owned22 offline tests and revalidated the **same unmodified** samples.',
'It labels that exact marker `notMeasured`, never zero; all other invalid timers',
'and contradictory markers still fail. No product measurement was rerun and the',
'original CI is not retroactively called green. See',
'[schema correction](STRESS-CACHE-SUMMARY-SCHEMA-CORRECTION.md).','',
'## Pins, workload and bounded order','',
'| Label | Source SHA |','|---|---|']
for p in report['products']:lines.append(f"| {p['label']} | `{p['sha']}` |")
lines+=['','Cell `cache-independent-4k-x8`:4096 independently written4KiB files,512 content',
'keys with8 distinct inodes per key, separated copies (`index %512`) in lexical',
'width-one traversal. Each sample uses a fresh product store, a no-op checkpoint',
'plus one64-byte edit and both historical readbacks. No initial OS-page-cache',
'coldness claim. Orders are main/inventory/admission, inventory/admission/main,',
'admission/main/inventory: each pin occupies each position once.','',
'The inventory-only revision retains64KiB eligibility, so **main→inventory here is',
'a negative-control/noise comparison, not proof that inventory scanning improved**.',
'The admission policy is isolated by inventory→admission; main→admission describes',
'the combined candidate on this one cell. No pooling with Cargo/concurrency data.','',
'## Correctness, identity and resource audit','',
'- Three canaries:15 exact full-tree checks and4 readbacks each. Nine screen',
'  samples:11 exact checks and2 readbacks each. Total144 full-tree checks and30',
'  historical readbacks; every raw oracle and archive hash rechecked. Complete',
'  path/content/type/mode/exact-ns/symlink/hardlink topology, source/retained-view',
'  invariance, acknowledged history and normal cleanup gates passed.',
'- All217 original artifact files (82,807,547B) rehashed unchanged;120 source/test',
'  file hashes and7 benchmark helper hashes match exact git objects. Binary SHA-256',
'  identities match manifests and all12 reports; executable bytes were not archived.',
'- Existing Ubuntu runner,45min hard job cap, original40min admission deadline,',
'  shared1200sec measurement budget including canaries (not reset), fresh2GiB',
'  images,256MiB image reserve, ≤1GiB conservative retained charge and normal',
'  cleanup only. No fault injection, forced unmount, image expansion or retry.',
'- Whole-filesystem Btrfs Used includes retained trees/cache/logs/history; no',
'  empty-image subtraction or logical/referenced-byte substitution. Images were',
'  retained on the ephemeral runner, not included in the downloadable archive.','',
'## All nine raw observations','',
'| Round/order position | Pin | Whole sampler(s) | Restore aggregate(s) | Active Used(MiB) | Post-history Used(MiB) |',
'|---|---|---:|---:|---:|---:|']
for i,r in enumerate(s['records']):
 m=r['metrics'];lines.append(f"| {r['round']+1}/{i%3+1} | {r['product']} | {m['wholeSampleSeconds']:.6f} | {m['restore_seconds']:.6f} | {m['activeWholeFilesystemBytes']/1024**2:.4f} | {m['postHistoryWholeFilesystemBytes']/1024**2:.4f} |")
lines+=['','## Every phase and paired comparison','',
'All percentages are candidate/baseline−1; lower is better for time and Used.',
'“Median” is the median of three within-round paired ratios. “Geom” is their',
'geometric mean. Phase timings overlap and must not be summed/subtracted into',
'exclusive costs. Whole sampler includes preparation, oracle checks, accounting,',
'normal cleanup and evidence serialization, excluding external image/fixture setup.','']
for edge,fields in s['comparisons'].items():
 lines += [f'### {edge}','','| Metric | Pair1 | Pair2 | Pair3 | Median | Geom |','|---|---:|---:|---:|---:|---:|']
 for metric,v in fields.items():
  lines.append('| '+metric+' | '+' | '.join(pct(p['candidateOverBaseline']) for p in v['pairs'])+' | '+pct(v['medianPairedRatio'])+' | '+pct(v['geometricMeanPairedRatio'])+' |')
 lines.append('')
lines+=['## Limitations and decision','',
'The predeclared ≥10% median restore threshold is met in this one many-reuse screen.',
'This is **not** a completed promotion gate: unique4096/10000, alias-only, over-key',
'capacity, x2 crossover, history and eligible≥64KiB inventory controls are not yet',
'measured in this three-pin route. Adjacent order, mixed large/small and nonempty',
'initial-cache conditions remain outside this finite screen too. Reverse-Latin',
'confirmation requires a separate reviewed decision; none is bundled into this run.','',
'Preserve the negatives: inventory→admission whole pair3 is+0.482%; warm-fork',
'median is+2.303% and first-fork geometric mean+1.725%. Main→admission checkpoint',
'median is+1.371%, warm-fork median+3.117%, and active Used median+0.087%.',
'The post-history Used reduction is an observed whole-filesystem result, not by',
'itself a count of cache hits, clone syscalls, unique extents or exclusive cache cost.','',
'Only3 same-host trials per pin. No statistical significance, independent-host',
'generalization or whole-run p95/p99 claim. Two restore operations per screen',
'sample are dependent; their small count does not support p95/p99 estimates.',
'All pairs, original failure evidence and phases are retained rather than selecting',
'only faster rows or resetting order after a loss.','',
'## Reproducible evidence','',
'[`data/stress-20261026/cache-independent-4k-x8/`](data/stress-20261026/cache-independent-4k-x8/)',
'contains the entire original artifact plus `audit/` manifests, source/hash audit,',
'original and corrected summaries, failed-step log, exact original tools and',
'corrected post-hoc tools. `posthoc-provenance.json` binds all hashes, the failed',
'run conclusion and the no-rerun/no-raw-modification facts.','']
(ROOT/'STRESS-CACHE-INDEPENDENT-4K-X8-RESULTS.md').write_text('\n'.join(lines))
print('Report rows',len(lines))
