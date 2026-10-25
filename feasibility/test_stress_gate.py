import copy
import unittest
from pathlib import Path
from unittest.mock import patch
from check_stress_gate import validate

class GateTests(unittest.TestCase):
    def test_exact_gate(self):
        pin='a'*40;head='b'*40
        proof=dict(diagnostic=False,records=[dict(backend=b) for b in ['native','projection','writable'] for _ in range(2)],sourcePins={'sprig':pin})
        provenance=dict(productSha=pin,runId=123,benchmarkSha=head,runUrl='https://github.com/M4n5ter/sprig-benchmarks/actions/runs/123')
        run=dict(id=123,head_sha=head,status='completed',conclusion='success',path='.github/workflows/stress-canary.yml')
        with patch('check_stress_gate.verify',return_value=proof):
            self.assertTrue(validate(Path('/unused'),provenance,pin,run)['accepted'])
            for key,value in [('head_sha','c'*40),('status','in_progress'),('conclusion','failure'),('path','.github/workflows/stress-ab.yml')]:
                bad=dict(run);bad[key]=value
                with self.assertRaises(AssertionError):validate(Path('/unused'),provenance,pin,bad)
            with self.assertRaises(AssertionError):validate(Path('/unused'),provenance,'d'*40,run)
        badproof=copy.deepcopy(proof);badproof['diagnostic']=True
        with patch('check_stress_gate.verify',return_value=badproof),self.assertRaises(AssertionError):
            validate(Path('/unused'),provenance,pin,run)

if __name__=='__main__':unittest.main()
