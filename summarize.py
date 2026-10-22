#!/usr/bin/env python3
import json,statistics,sys,csv
from pathlib import Path
p=Path(sys.argv[1]);x=json.loads(p.read_text());records=x['records'];rows=[]
expected=x.get('expectedRecords',42);rounds=x.get('rounds',3);cases=x.get('cases',['identical','unique','mixed','insert','history-distributed','history-hotset','history-recurring'])
expected_keys={(c,p,r) for c in cases for p in ['sprig','layerfs'] for r in range(rounds)}
actual_keys=[(r['case'],r['product'],r['round']) for r in records]
complete=len(records)==expected and len(set(actual_keys))==expected and set(actual_keys)==expected_keys and all(r.get('correct',False) for r in records)
for r in records:
 if 'warmForkToWorkspaceMs' in r and 'warmFirstFullReadMs' in r:r['warmForkReadMs']=r['warmForkToWorkspaceMs']+r['warmFirstFullReadMs']
for case in dict.fromkeys(r['case'] for r in records):
 for product in ['sprig','layerfs']:
  rs=[r for r in records if r['case']==case and r['product']==product]
  row={'case':case,'product':product,'samples':len(rs),'correct':len(rs)==rounds and all(r.get('correct',False) for r in rs)}
  for key in ['importMs','metadataBranchMs','forkToWorkspaceMs','firstFullReadVerifyMs','totalImportForkReadMs','warmForkToWorkspaceMs','warmFirstFullReadMs','warmForkReadMs']:
   vals=[r[key] for r in rs if key in r]
   if vals:row[key]={'median':statistics.median(vals),'min':min(vals),'max':max(vals),'samples':vals}
  for key in ['duApparentBytes','duAllocatedBytes','bytes','allocated']:
   vals=[r['fullStore'][key] for r in rs if key in r.get('fullStore',{})]
   if vals:row['store_'+key]={'median':statistics.median(vals),'min':min(vals),'max':max(vals),'samples':vals}
  for key in ['duApparentBytes','duAllocatedBytes']:
   vals=[r['activeStore'][key] for r in rs if key in r.get('activeStore',{})]
   if vals:row['active_'+key]={'median':statistics.median(vals),'min':min(vals),'max':max(vals),'samples':vals}
  for key in ['totalWriteMs','totalCommitMs','acknowledgedCommits','historyRecords']:
   vals=[r['historyCheck'][key] for r in rs if key in r.get('historyCheck',{})]
   if vals:row[key]={'median':statistics.median(vals),'min':min(vals),'max':max(vals),'samples':vals}
  rows.append(row)
out={'complete':complete,'expected_records':expected,'all_records_correct':complete,'records':len(records),'groups':rows,'caveats':x.get('caveats',[])}
p.with_name('summary.json').write_text(json.dumps(out,indent=2))
cols=['case','product','samples','correct','importMs','metadataBranchMs','forkToWorkspaceMs','totalImportForkReadMs','warmForkToWorkspaceMs','warmFirstFullReadMs','warmForkReadMs','active_duAllocatedBytes','store_duAllocatedBytes','totalWriteMs','totalCommitMs']
with p.with_name('summary.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
 for row in rows:w.writerow({k:(row.get(k,{}).get('median','') if isinstance(row.get(k),dict) else row.get(k,'')) for k in cols})
print(json.dumps(out,indent=2))
