#!/usr/bin/env python3
"""Summarize only complete stress records; raw samples remain authoritative."""
import argparse
import json
from pathlib import Path
from stress_stats import latency_summary


def summarize(report):
    if not report.get('complete') or report.get('status')!='passed':
        raise ValueError('incomplete/aborted/failed run cannot become a performance summary')
    rows=[]
    for record in report['records']:
        if not record.get('correct') or not record['sample'].get('ok'):
            raise ValueError('incorrect sample cannot be summarized as performance')
        sample=record['sample']
        changed=[x for x in sample.get('checkpoint_steps',[]) if not x.get('noop')]
        restores=sample.get('historical_restore_steps',[])
        row=dict(product=record['product'],backend=record['backend'],round=record['round'],
                 wholeSampleSeconds=record['wholeSampleSubprocessWallSeconds'],
                 activeWholeFilesystemBytes=sample['activeSpace']['filesystemUsedBytes'],
                 postHistoryWholeFilesystemBytes=sample['postHistorySpace']['filesystemUsedBytes'],
                 activeMinusEmptyBytes=sample['activeSpace']['filesystemUsedBytes']-record['emptySpace']['filesystemUsedBytes'],
                 postHistoryMinusEmptyBytes=sample['postHistorySpace']['filesystemUsedBytes']-record['emptySpace']['filesystemUsedBytes'],
                 changedCheckpoints=len(changed),historicalReadbacks=sample['fullHistoricalSnapshotReadbacks'],
                 checkpointTails=latency_summary([r['checkpoint_seconds'] for r in changed]) if changed else None,
                 restoreTails=latency_summary([r['restore_seconds'] for r in restores]) if restores else None,
                 historyWindows=[])
        for name,lo,hi in [('early',0,len(changed)//3),('middle',len(changed)//3,2*len(changed)//3),('late',2*len(changed)//3,len(changed))]:
            if hi>lo:
                row['historyWindows'].append(dict(window=name,firstChangedOrdinal=lo+1,lastChangedOrdinal=hi,
                    checkpoint=latency_summary([r['checkpoint_seconds'] for r in changed[lo:hi]])))
        rows.append(row)
    ratios=[]
    if len(report['products'])==2 and not report.get('diagnostic'):
        labels=[p['label'] for p in report['products']]
        for backend in report['backends']:
            for round_no in range(report['rounds']):
                pair=[next(r for r in rows if r['backend']==backend and r['round']==round_no and r['product']==label) for label in labels]
                metrics={}
                for key in ('wholeSampleSeconds','activeWholeFilesystemBytes','postHistoryWholeFilesystemBytes','activeMinusEmptyBytes','postHistoryMinusEmptyBytes'):
                    metrics[key]=pair[0][key]/pair[1][key] if pair[1][key]>0 else None
                ratios.append(dict(backend=backend,round=round_no,numerator=labels[0],denominator=labels[1],ratios=metrics))
    return dict(schema='sprig-stress-summary-v1',cell=report['cell'],diagnostic=report.get('diagnostic',False),
                units='seconds and bytes',rows=rows,withinPairRatios=ratios,
                caveats=['Descriptive correlated-operation tails; no independent-sample statistical claim.',
                         'Whole sample subprocess wall is authoritative; nested phase totals are not added to it.',
                         'Whole filesystem includes runtime and all retained generations; runtime differences disclosed.',
                         ('Same Sprig public CLI and durability protocol; only pinned implementation differs; no CPU/RAM savings measured.'
                          if report.get('comparisonProtocol')=='within-sprig-ab' else
                          'Different durability and CLI versus SDK/container transport; no CPU/RAM-equivalence claim.'),
                         'New full-metadata stress protocol, not interchangeable with frozen listed-file results.'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args();value=summarize(json.loads(a.input.read_text()));text=json.dumps(value,indent=2)+'\n'
    if a.output: a.output.write_text(text)
    print(text,end='')
