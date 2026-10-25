import unittest
from unittest.mock import patch
from pathlib import Path
from stress_sequence import phase_budget,validate_native_canary,validate_binary_identity

class SequenceTests(unittest.TestCase):
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
            wrong=[dict(label='inventory',sha='c'*40),products[1]]
            with self.assertRaises(ValueError):validate_native_canary(Path('/unused'),wrong)
        proof['records'][0]['historicalReadbacks']=3
        with patch('stress_sequence.verify',return_value=proof),self.assertRaises(ValueError):
            validate_native_canary(Path('/unused'),products)

if __name__=='__main__':unittest.main()
