import unittest
from stress_run import capacity_guard, cell_parameters, BudgetAbort, GIB, MIB

class RunTests(unittest.TestCase):
    def test_capacity(self):
        capacity_guard(100*MIB,603*MIB)
        with self.assertRaises(BudgetAbort): capacity_guard(0,GIB+1)
        with self.assertRaises(BudgetAbort): capacity_guard(900*MIB,GIB)
    def test_priority_operation_budget(self):
        params,noop=cell_parameters('files-10000')
        self.assertTrue(noop);self.assertEqual(params['steps'],1)
        self.assertLess(params['files']*params['size']*7,GIB)
        p,n=cell_parameters('canary')
        self.assertTrue(n and p['symlink']);self.assertEqual(p['steps'],3)
        with self.assertRaises(BudgetAbort): cell_parameters('history-random-1000')
    def test_pair_order_alternation(self):
        from stress_run import ordered_products
        self.assertEqual(ordered_products(['base','candidate'],0,'forward'),['base','candidate'])
        self.assertEqual(ordered_products(['base','candidate'],1,'forward'),['candidate','base'])
        self.assertEqual(ordered_products(['base','candidate'],0,'reverse'),['candidate','base'])
        self.assertEqual(ordered_products(['base','candidate'],1,'reverse'),['base','candidate'])

    def test_unknown(self):
        with self.assertRaises(ValueError): cell_parameters('not-a-cell')

if __name__=='__main__':unittest.main()

class CleanupAdmissionTests(unittest.TestCase):
    def check(self,record,**kwargs):
        from stress_run import cleanup_admission
        opts=dict(sampler_started=True,runtime_attempted=True,runtime_ready=True,runtime_state={'restored':False})
        opts.update(kwargs)
        return cleanup_admission(record,**opts)
    def good(self):
        return dict(productType='layerfs',sample=dict(lifecycle=dict(cleanup=dict(complete=True)),remainingMounts=[],remainingContainers=[],remainingMountsKnown=True,remainingContainersKnown=True))
    def test_parse_failure_retains_state(self):
        self.assertIsNotNone(self.check({}))
        self.assertIsNotNone(self.check(dict(sample=None)))
    def test_malformed_nested_proof_retains_state(self):
        for key,value in [('error',[]),('lifecycle',[]),('lifecycle',{'cleanup':None})]:
            r=self.good();r['sample'][key]=value
            self.assertIsNotNone(self.check(r))

    def test_uncertain_mutation_retains_state(self):
        r=self.good();r['sample']['error']=dict(uncertain=True)
        self.assertIsNotNone(self.check(r))
    def test_cleanup_incomplete_retains_state(self):
        r=self.good();r['sample']['lifecycle']['cleanup']['complete']=False
        self.assertIsNotNone(self.check(r))
    def test_affirmative_cleanup_admitted(self):
        self.assertIsNone(self.check(self.good()))
    def test_setup_failure_requires_rollback(self):
        self.assertIsNotNone(self.check({},sampler_started=False,runtime_ready=False))
        self.assertIsNone(self.check({},sampler_started=False,runtime_ready=False,runtime_state={'restored':True}))
        self.assertIsNone(self.check({},sampler_started=False,runtime_ready=False,runtime_state=None))
