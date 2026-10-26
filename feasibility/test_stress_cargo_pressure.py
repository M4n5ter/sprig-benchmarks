import copy
import json
from pathlib import Path
import tempfile
import unittest
from stress_cargo_pressure import SPEC, run, verify_worker, validate_report, pressure_identity

class Tests(unittest.TestCase):
    def test_fixed_normal_workload_retains_every_observation_and_witness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result=run(root)
            self.assertTrue(result['ok']);self.assertTrue(result['allWitnessesVerified'])
            self.assertEqual(validate_report(result),result)
            for mutate in (lambda r:r['workers'][0]['samplesNanoseconds']['rename'].pop(),lambda r:r['workers'][0].update(worker=False),lambda r:r.update(workerLifetimeOverlapNs=0),lambda r:r.update(allWitnessesVerified=False),lambda r:r['workers'][0]['samplesNanoseconds']['write'].__setitem__(0,-1)):
                changed=copy.deepcopy(result);mutate(changed)
                with self.assertRaises(ValueError):validate_report(changed)
            self.assertEqual(pressure_identity()['availableReserveBytes'],128*1024**2)
            self.assertEqual(result['spec'],SPEC);self.assertEqual(len(result['workers']),2)
            self.assertGreater(result['workerLifetimeOverlapNs'],0)
            for worker in result['workers']:
                self.assertEqual(worker['completedIterations'],128)
                for name,values in worker['samplesNanoseconds'].items():
                    self.assertEqual(len(values),256 if name=='rename' else 128)
                    self.assertTrue(all(type(v) is int and v>=0 for v in values))
                verify_worker(root/'pressure-rename2'/f"worker-{worker['worker']}",worker['worker'])
            self.assertEqual(json.loads((root/'pressure-rename2/observations.json').read_text()),result)
            self.assertEqual(len(list((root/'pressure-rename2').glob('worker-*/unrelated/*'))),2048)
            with self.assertRaises(FileExistsError):run(root)
            witness=root/'pressure-rename2/worker-0/active/witness'
            witness.write_bytes(b'changed')
            with self.assertRaises(AssertionError):verify_worker(witness.parent.parent,0)

if __name__=='__main__':unittest.main()
