import unittest
from unittest.mock import patch
from pathlib import Path
from stress_sequence import phase_budget,validate_native_canary,validate_binary_identity,validate_canary,validate_backend,sequence_phases

class SequenceTests(unittest.TestCase):
    def test_bounded_suite_order(self):
        self.assertEqual(sequence_phases(suite="cache-admission-controls"),[("canary","canary"),("history300","cache-history-repeated-300"),("unique10k","files-10000"),("cold4096","files-4096")])
        self.assertEqual(sequence_phases(cell="files-10000"),[("canary","canary"),("pressure","files-10000")])
        with self.assertRaises(ValueError):sequence_phases(suite="unbounded")
        with self.assertRaises(ValueError):sequence_phases(cell="files-10000",suite="cache-admission-controls")
    def test_under_capacity_control_recipe(self):
        from stress_run import cell_parameters
        p,noop=cell_parameters("files-4096")
        self.assertEqual((p["files"],p["size"],p["steps"],p["width"]),(4096,4096,1,1))
        self.assertTrue(noop)
    def test_pressure_backend(self):
        proof=dict(records=[dict(backend="writable")]*2)
        validate_backend(proof,"writable")
        with self.assertRaises(ValueError):validate_backend(proof,"native")
    def test_binary_identity(self):
        proof=dict(records=[dict(product="inventory",binarySha256="a"),dict(product="threshold",binarySha256="b")])
        validate_binary_identity(proof,{"inventory":"a","threshold":"b"})
        with self.assertRaises(ValueError):validate_binary_identity(proof,{"inventory":"a","threshold":"c"})
    def test_shared_budget(self):
        self.assertEqual(phase_budget(1200,True),300)
        self.assertEqual(phase_budget(1100,False),1070)
        self.assertEqual(phase_budget(90,False),60)
        with self.assertRaises(ValueError):phase_budget(89,False)
    def test_exact_native_canary_proof(self):
        products=[dict(label='inventory',sha='a'*40),dict(label='threshold',sha='b'*40)]
        proof=dict(diagnostic=False,records=[dict(backend='native',fullTreeChecks=15,historicalReadbacks=4)]*2,sourcePins={p['label']:p['sha'] for p in products})
        with patch('stress_sequence.verify',return_value=proof):
            self.assertEqual(validate_native_canary(Path('/unused'),products),proof)
            with self.assertRaises(ValueError):validate_canary(Path('/unused'),products,'writable')
            for row in proof['records']:row['backend']='writable'
            self.assertEqual(validate_canary(Path('/unused'),products,'writable'),proof)
            with self.assertRaises(ValueError):validate_native_canary(Path('/unused'),products)
            for row in proof['records']:row['backend']='native'
            wrong=[dict(label='inventory',sha='c'*40),products[1]]
            with self.assertRaises(ValueError):validate_native_canary(Path('/unused'),wrong)
        proof['records'][0]['historicalReadbacks']=3
        with patch('stress_sequence.verify',return_value=proof),self.assertRaises(ValueError):
            validate_native_canary(Path('/unused'),products)

if __name__=='__main__':unittest.main()
