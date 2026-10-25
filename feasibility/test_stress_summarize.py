import unittest
from stress_summarize import summarize

class SummaryTests(unittest.TestCase):
    def test_refuses_partial(self):
        for state in ('running','failed','budget_aborted'):
            with self.assertRaises(ValueError): summarize(dict(complete=False,status=state))
    def test_matched_pair(self):
        records=[]
        for label,wall in [('baseline',2.0),('candidate',1.0)]:
            records.append(dict(product=label,backend='native',round=0,correct=True,
                wholeSampleSubprocessWallSeconds=wall,emptySpace=dict(filesystemUsedBytes=10),sample=dict(
                    ok=True,checkpoint_steps=[dict(noop=True,checkpoint_seconds=9),*[dict(checkpoint_seconds=i) for i in range(1,101)]],
                    historical_restore_steps=[dict(restore_seconds=.1) for _ in range(101)],
                    activeSpace=dict(filesystemUsedBytes=100),postHistorySpace=dict(filesystemUsedBytes=200),
                    fullHistoricalSnapshotReadbacks=101)))
        report=dict(complete=True,status='passed',cell='test',records=records,products=[dict(label='baseline'),dict(label='candidate')],backends=['native'],rounds=1)
        s=summarize(report)
        self.assertEqual(s['rows'][0]['changedCheckpoints'],100)
        self.assertEqual(s['rows'][0]['checkpointTails']['p99'],99)
        self.assertEqual(s['withinPairRatios'][0]['ratios']['wholeSampleSeconds'],2)
        self.assertEqual(len(s['rows'][0]['historyWindows']),3)

if __name__=='__main__':unittest.main()
