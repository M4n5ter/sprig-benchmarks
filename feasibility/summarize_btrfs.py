import json,statistics,sys,collections,csv,pathlib
p=pathlib.Path(sys.argv[1]);x=json.loads(p.read_text());assert x['complete'];expected={(case,product,round) for case in x['cases'] for product in ['native-prototype','layerfs'] for round in range(x['rounds'])};actual=[(r['case'],r['product'],r['round']) for r in x['records']];assert set(actual)==expected and len(actual)==len(expected)
rows=[]
for case in x['cases']:
 for product in ['native-prototype','layerfs']:
  rs=[r for r in x['records'] if r['case']==case and r['product']==product];assert all(r['correct'] and not r.get('cleanupErrors') for r in rs)
  if case.startswith('history'):assert all(r['fullHistoricalSnapshotReadbacks']==100 and r['historyCheck']['acknowledgedCommits']==100 for r in rs)
  row=dict(case=case,product=product,samples=len(rs))
  for key in ['initMs','importMs','metadataBranchMs','forkToWorkspaceMs','firstFullReadVerifyMs','totalImportForkReadMs','initInclusiveImportForkReadMs','warmForkToWorkspaceMs','warmFirstFullReadMs','warmForkReadMs','filesystemUsedDeltaBytes','runtimeReadyDeltaBytes']:
   row[key]=statistics.median(r[key] for r in rs) if all(key in r for r in rs) else None
  if case.startswith('history'):
   for k in ['totalWriteMs','totalCommitMs']:row[k]=statistics.median(r['historyCheck'][k] for r in rs)
   row['writeAndCommitMs']=statistics.median(r['historyCheck']['totalWriteMs']+r['historyCheck']['totalCommitMs'] for r in rs)
  rows.append(row)
out=dict(complete=True,expectedRecords=len(expected),rows=rows,scope='See frozen MEASUREMENT-BOUNDARIES.md. Whole deployment and runtime incremental bytes are not exact app-data-only usage.')
p.with_name('btrfs-summary.json').write_text(json.dumps(out,indent=2)+'\n');keys=list(dict.fromkeys(k for row in rows for k in row))
with p.with_name('btrfs-summary.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
for row in rows:print(row)
