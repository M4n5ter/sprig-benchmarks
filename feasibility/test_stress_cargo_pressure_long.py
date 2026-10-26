"""Offline normal-operation/schema/clock/transport bounds; no mount or Rust."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import stress_cargo_pressure_long as long
from stress_cargo_pressure_profiles import experiment_for,pins_for


def synthetic_report():
    rows=[]
    for worker in (0,1):
        samples={name:[] for name in ('rename','write','read','metadata')};events=[]
        for ordinal in range(5*long.SPEC['iterationsPerWorker']):
            operation=long.EVENT_ORDER[ordinal%5];start=worker*10+ordinal*3+1
            events.append(dict(iteration=ordinal//5,operation=operation,startNs=start,endNs=start+1,durationNs=1))
            samples['rename' if operation.startswith('rename-') else operation].append(1)
        rows.append(dict(worker=worker,startedNs=worker*10,finishedNs=worker*10+5*long.SPEC['iterationsPerWorker']*3,completedIterations=1024,samplesNanoseconds=samples,operationIntervals=events))
    return dict(schema=long.SCHEMA,profile=long.SPEC['profile'],spec=long.SPEC,ok=True,allWitnessesVerified=True,clock='CLOCK_MONOTONIC',monotonicOriginNs='17000000001234567890',workers=rows,workerLifetimeOverlapNs=rows[0]['finishedNs']-rows[1]['startedNs'])


class LongPressureTests(unittest.TestCase):
    def test_exact_clock_interval_order_duration_and_count_guards(self):
        report=synthetic_report();self.assertEqual(long.validate_report(report),report)
        changes=(lambda r:r.update(clock='CLOCK_REALTIME'),lambda r:r.update(monotonicOriginNs=123),lambda r:r.update(monotonicOriginNs='01'),lambda r:r.update(monotonicOriginNs=str(2**64)),lambda r:r.update(monotonicOriginNs='１２'),lambda r:r.update(workerLifetimeOverlapNs=0),lambda r:r.update(allWitnessesVerified=False),lambda r:r['workers'][0].update(completedIterations=128),lambda r:r['workers'][0]['operationIntervals'].pop(),lambda r:r['workers'][0]['operationIntervals'][0].update(iteration=True),lambda r:r['workers'][0]['operationIntervals'][1].update(operation='read'),lambda r:r['workers'][0]['operationIntervals'][0].update(startNs=-1),lambda r:r['workers'][0]['operationIntervals'][1].update(startNs=0),lambda r:r['workers'][0]['operationIntervals'][0].update(endNs=2**53),lambda r:r['workers'][0]['operationIntervals'][0].update(durationNs=2),lambda r:r['workers'][0]['operationIntervals'][0].update(extra=1),lambda r:r['workers'][0]['samplesNanoseconds']['rename'].__setitem__(0,2))
        for change in changes:
            bad=copy.deepcopy(report);change(bad)
            with self.assertRaises(ValueError):long.validate_report(bad)

    def test_actual_long_normal_workload_retains_exact_observations_and_witnesses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report=long.run(root);self.assertEqual(long.validate_report(report),report)
            self.assertEqual(json.loads((root/'pressure-rename2/observations.json').read_text()),report)
            for worker in (0,1):long.verify_worker(root/'pressure-rename2'/f'worker-{worker}',worker)
            self.assertEqual(sum(len(r['operationIntervals']) for r in report['workers']),10240)
            self.assertEqual(sum(len(r['samplesNanoseconds']['rename']) for r in report['workers']),4096)
            with self.assertRaises(FileExistsError):long.run(root)
            witness=root/'pressure-rename2/worker-1/active/witness';witness.write_bytes(b'wrong')
            with self.assertRaises(AssertionError):long.verify_worker(witness.parent.parent,1)

    def test_max_width_event_json_fits_existing_transport_without_raising_caps(self):
        report=synthetic_report()
        # Structural upper bound: all numeric fields at maximum JSON width,
        # including duration widths that cannot all coexist chronologically.
        for row in report['workers']:
            for key in ('startedNs','finishedNs'):row[key]=2**53-1
            for values in row['samplesNanoseconds'].values():values[:]=[2**53-1]*len(values)
            for event in row['operationIntervals']:
                for key in ('startNs','endNs','durationNs'):event[key]=2**53-1
                event['iteration']=1023;event['operation']='rename-away'
        body=json.dumps(report,sort_keys=True).encode()
        self.assertLess(len(body),long.MAX_REPORT_BYTES)
        # Both embedded object and escaped stdout plus generous existing-tree
        # evidence margin remain below the unchanged128MiB command maxBuffer.
        self.assertLess(2*len(body)+1024*1024+32*1024**2,128*1024**2)
        source=Path(__file__).with_name('stress_cargo_compare.mjs').read_text();self.assertIn('maxBuffer:128*1024**2',source)
        oversized=synthetic_report();oversized['extra']='x'*long.MAX_REPORT_BYTES
        with self.assertRaisesRegex(ValueError,'exceeds4MiB'):long.validate_report(oversized)

    def test_explicit_profile_pins_never_relabel_old_pressure(self):
        self.assertEqual(experiment_for('normal-rename2-v1')['pressure']['spec']['iterationsPerWorker'],128)
        self.assertEqual(experiment_for(long.SPEC['profile'])['pressure'],long.pressure_identity())
        self.assertEqual(pins_for(long.SPEC['profile'])['sprig-baseline'],'b300693e01c652c1a9631c61b7a439892d8f75cd')
        self.assertEqual(pins_for(long.SPEC['profile'])['sprig-candidate'],'dfee7e4e9ee223f25d141d2e05d3cfcdc6c9269f')
        self.assertNotEqual(pins_for('normal-rename2-v1'),pins_for(long.SPEC['profile']))
        for value in ('unknown',None):
            with self.assertRaises(ValueError):experiment_for(value)

if __name__=='__main__':unittest.main()
