#!/usr/bin/env python3
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import cargo_transport_sample as transport
import current_sample as current
from test_cargo_transport_mock import MockSample,TransportTests
from stress_cargo_sample import StressCargoSample,stress_report,build_observation
from stress_cargo_prepare import PROTOCOL,PROTOCOL_SHA,generate,freeze,expected,validate_manifest


def manifest(initial):
    return dict(schema='sprig-stress-cargo-v2',crates=16,totalPackages=17,
                packages=PROTOCOL['packages'],protocolSha256=PROTOCOL_SHA,
                dependencies=PROTOCOL['dependencies'],expectedStdoutBefore=expected(2),expectedStdoutAfter=expected(103),initial=initial)


class MockStress(StressCargoSample,MockSample):
    def __init__(self,root,incremental=0,failure=None):
        MockSample.__init__(self,root,incremental=incremental,failure=failure)
        base=self.report;self.report=stress_report();self.report.update({k:base[k] for k in ('backend','incremental','containingFilesystem','production_sha')})
        self.manifest=manifest(self.fixture)

    def app(self,value,script,input_data,purpose):
        if script.endswith('snapshot /work'):
            tree=value['tree']
            if tree==str(self.source):assert value['readonly']
            name='source' if tree==str(self.source) else next(n for n,row in self.workspaces.items() if row['path']==tree and row['mount_state']=='mounted')
            self.app_calls.append((purpose,name,script,input_data))
            if purpose in ('fixture_verify','main_unchanged','source_unchanged'):
                return json.dumps(self.fixture),''
            if purpose=='pre_checkpoint_oracle':
                self.checkpoint_oracle={**self.fixture,'entries':self.fixture['entries']+[{'path':'target/probe','type':'file','mtime_ns':1700000000123456789,'mode':416,'size':1,'sha256':'c'*64}],'hardlink_groups':[['target/probe','target/link']]}
            return json.dumps(self.checkpoint_oracle),''
        commands=PROTOCOL['commands']
        if script not in commands.values() and script!='rustc -Vv; cargo -V':
            return super().app(value,script,input_data,purpose)
        names=[n for n,row in self.workspaces.items() if row['path']==value['tree'] and row['mount_state']=='mounted']
        assert len(names)==1,'stale generation'
        name=names[0];self.app_calls.append((purpose,name,script,input_data))
        if name=='second':assert self.report.get('fullRestoredTreeVerified')
        if self.failure==purpose:raise transport.SampleError('mock uncertain exec failure')
        if script==commands['build']:
            mode='Fresh' if purpose in ('noop_build','restored_rebuild') else 'Compiling'
            return '', ''.join(f'       {mode} {p} v0.1.0 (/work/{p})\n' for p in PROTOCOL['packages'])
        if script==commands['program']:
            return self.manifest['expectedStdoutAfter' if self.contents[name]=='after' else 'expectedStdoutBefore'],''
        if script==commands['edit']:self.contents[name]='after';return '',''
        if script==commands['probe']:return '',''
        if script in (commands['verifyBefore'],commands['verifyAfter']):
            return json.dumps(dict(ok=True,buildValue=1 if script==commands['verifyBefore'] else 2,generatedFiles=['target/debug/build/node000-x/out/generated.rs'],hardlinkProbe=True,exactMtime=True)),''
        return 'rustc 1.90.0 (mock)\ncargo 1.90.0 (mock)\n',''


class Tests(unittest.TestCase):
    def test_full_mocked_lifecycle_both_incremental_settings(self):
        for incremental in (0,1):
            with self.subTest(incremental=incremental),tempfile.TemporaryDirectory() as root:
                sample=MockStress(Path(root),incremental)
                with TransportTests().patches(sample),patch('stress_cargo_sample.fixture_inventory',lambda *a:None):
                    sample.execute();sample.cleanup()
                self.assertTrue(sample.report['ok'])
                self.assertEqual(len(sample.report['compilerSessions']),4)
                self.assertTrue(all(s['removed'] and s['naturalExitAndPidGoneVerified'] for s in sample.report['compilerSessions']))
                self.assertEqual(len(sample.report['artifactChecks']),5)
                self.assertEqual(len(sample.report['cargoBuildObservations']),4)
                self.assertTrue(all(x['allPackagesVerified'] for x in sample.report['cargoBuildObservations']))
                phases=[x[0] for x in sample.app_calls]
                self.assertLess(phases.index('restore_verify'),phases.index('restored_execute'))
                self.assertEqual(sample.report['remainingMounts'],[])

    def test_uncertain_exit_still_blocks_product_checkpoint_and_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            sample=MockStress(Path(root),failure='marker_uncertain')
            with TransportTests().patches(sample),patch('stress_cargo_sample.fixture_inventory',lambda *a:None):
                with self.assertRaises(transport.SampleError):sample.execute()
                sample.cleanup()
            self.assertTrue(sample.cleanup_blocked)
            self.assertFalse(any(c[0] in ('checkpoint','unmount-generation') for c in sample.cli_calls))

    def test_short_oracle_preserves_large_tree_and_rejects_one_ns_mismatch(self):
        sample=StressCargoSample(stress_report())
        expected={"schema":"cargo-full-tree-v1","entries":[{"path":str(i),"mtime_ns":1700000000000000001,"sha256":"a"*64} for i in range(4000)],"hardlink_groups":[]}
        self.assertGreater(len(json.dumps(expected)),128*1024)
        with patch.object(sample,'runtime',return_value=json.dumps(expected)) as runtime:
            self.assertTrue(sample.oracle('/work',expected=expected,purpose='restore_verify')['ok'])
            self.assertLess(len(runtime.call_args.args[1]),256)
        altered=json.loads(json.dumps(expected));altered['entries'][0]['mtime_ns']+=1
        with patch.object(sample,'runtime',return_value=json.dumps(altered)),self.assertRaises(transport.SampleError):
            sample.oracle('/work',expected=expected,purpose='restore_verify')

    def test_parallel_topology_and_shared_leaf_reach_every_package(self):
        graph=PROTOCOL['dependencies']
        self.assertEqual(len(graph),16)
        self.assertEqual([i for i in range(1,16) if graph[i]==[0]],[1,2,3,4])
        reached={0}
        for i,deps in enumerate(graph[1:],1):
            self.assertTrue(all(0<=d<i for d in deps))
            if any(d in reached for d in deps):reached.add(i)
        self.assertEqual(reached,set(range(16))) # app depends on node015
        # Independent algebra: node015 = 31*leaf + 207, including every branch.
        self.assertEqual(expected(2),'269\n')
        self.assertEqual(expected(103),'3400\n')
        for leaf in (0,1,17):self.assertEqual(expected(leaf),str(31*leaf+207)+'\n')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';generate(root)
            import tomllib
            for i,deps in enumerate(graph):
                actual=tomllib.loads((root/f'node{i:03}/Cargo.toml').read_text())['dependencies']
                self.assertEqual(sorted(actual),[f'node{d:03}' for d in deps])
            self.assertEqual(list(tomllib.loads((root/'app/Cargo.toml').read_text())['dependencies']),['node015'])

    def test_exact_package_cache_acceptance(self):
        fresh=''.join(f'       Fresh {p} v0.1.0 (/work/{p})\n' for p in PROTOCOL['packages'])
        self.assertTrue(build_observation(fresh,'restored_rebuild')['allPackagesVerified'])
        for bad in (fresh.replace('node015','node014'),fresh+' Compiling node000 v0.1.0\n',fresh.replace('v0.1.0','v0.2.0'),fresh.replace('       Fresh node015 v0.1.0 (/work/node015)\n','')):
            with self.subTest(bad=bad),self.assertRaises(Exception):build_observation(bad,'noop_build')

    def test_generator_freeze_requires_pristine_local_lock_and_bound_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';generate(root)
            with self.assertRaises(FileNotFoundError):freeze(root)
            (root/'Cargo.lock').write_text('version = 4\n'+''.join(f'[[package]]\nname = "{p}"\nversion = "0.1.0"\n' for p in PROTOCOL['packages']))
            result=freeze(root);validate_manifest(result)
            self.assertNotEqual(result['expectedStdoutBefore'],result['expectedStdoutAfter'])
            self.assertIn('fs::write', (root/'node000/build.rs').read_text())
            self.assertIn('OUT_DIR',(root/'node000/src/lib.rs').read_text())
            (root/'target').mkdir()
            with self.assertRaises(ValueError):freeze(root)
            result['protocolSha256']='0'*64
            with self.assertRaises(ValueError):validate_manifest(result)

    def test_successful_product_cli_stderr_is_preserved_without_stdout_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            sample=StressCargoSample(stress_report())
            response=SimpleNamespace(returncode=0,stdout='{"result":42}\n',stderr='diagnostic evidence\n')
            with patch('stress_cargo_sample.subprocess.run',return_value=response):
                self.assertEqual(sample.command(['never-executed'],record_event=False),response.stdout)
                self.assertEqual(len(sample.pending_command_logs),1)
                sample.logs=Path(temp)
                self.assertEqual(sample.command(['never-executed'],record_event=False),response.stdout)
                self.assertEqual(list(Path(temp).iterdir()),[])
                sample.flush_command_logs()
            self.assertEqual(len(list(Path(temp).glob('*.stderr'))),2)
            self.assertTrue(all(p.read_text()==response.stderr for p in Path(temp).glob('*.stderr')))
            self.assertEqual(sample.pending_command_logs,[])

    def test_protocol_scripts_are_syntax_valid_and_do_not_exclude_target(self):
        for key in ('edit','probe','verifyBefore','verifyAfter'):
            code=PROTOCOL['commands'][key].split('\n',1)[1].rsplit('\n',1)[0]
            compile(code,key,'exec')
        self.assertEqual(PROTOCOL['commands']['build'],'cargo build --offline --locked --verbose --workspace --jobs 2')
        self.assertEqual(len(PROTOCOL['packages']),17)

if __name__=='__main__':unittest.main()
