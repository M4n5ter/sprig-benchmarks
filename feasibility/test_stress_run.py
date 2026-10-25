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
    def test_unknown(self):
        with self.assertRaises(ValueError): cell_parameters('not-a-cell')

if __name__=='__main__':unittest.main()
