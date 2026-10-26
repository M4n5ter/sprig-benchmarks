#!/usr/bin/env python3
"""Inert Python-child capture checks; never compiler/product/mount execution."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import layerfs_encoder_capture as capture


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def run_child(self, code, cap=1024, seconds=3, reserve=1024):
        return capture.capture([sys.executable, '-c', code], self.root,
                               self.root/'stdout', self.root/'stderr', self.root/'receipt.json',
                               seconds, cap, reserve)

    def test_complete_small_streams(self):
        result = self.run_child("import sys;print('out');print('err',file=sys.stderr)")
        self.assertTrue(result['accepted'])
        self.assertTrue(result['captureComplete'])
        self.assertTrue(result['ownedGroupSettled'])
        self.assertEqual(result['processReturncode'], 0)
        self.assertEqual(result['signals'], [])
        for name, data in [('stdout', b'out\n'), ('stderr', b'err\n')]:
            self.assertEqual((self.root/name).read_bytes(), data)
            self.assertEqual(result['streams'][name]['retainedSha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(json.loads((self.root/'receipt.json').read_text()), result)

    def test_nonzero_not_success_but_complete_bytes_retained(self):
        result = self.run_child("import sys;print('failure',file=sys.stderr);sys.exit(7)")
        self.assertFalse(result['accepted'])
        self.assertEqual(result['processReturncode'], 7)
        self.assertTrue(result['allObservedBytesRetained'])
        self.assertEqual((self.root/'stderr').read_bytes(), b'failure\n')

    def test_stdout_overflow_is_failure_and_hard_bounded(self):
        result = self.run_child("import os;os.write(1,b'x'*8192)", cap=64, reserve=128)
        self.assertFalse(result['accepted'])
        self.assertIn('stdout_overflow', result['errors'])
        self.assertLessEqual((self.root/'stdout').stat().st_size, 192)
        self.assertGreater(result['streams']['stdout']['discardedBytes'], 0)
        self.assertFalse(result['allObservedBytesRetained'])
        self.assertTrue(all(s['signal'] in ('SIGTERM','SIGKILL') for s in result['signals']))

    def test_stderr_overflow_is_failure(self):
        result = self.run_child("import os;os.write(2,b'x'*8192)", cap=64, reserve=128)
        self.assertFalse(result['accepted'])
        self.assertIn('stderr_overflow', result['errors'])
        self.assertLessEqual((self.root/'stderr').stat().st_size, 192)

    def test_small_overflow_retains_full_observed_bytes_but_fails(self):
        result = self.run_child("import os;os.write(1,b'x'*65)", cap=64, reserve=128)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['streams']['stdout']['discardedBytes'], 0)
        self.assertEqual((self.root/'stdout').read_bytes(), b'x'*65)

    def test_deadline_only_terminates_owned_child(self):
        result = self.run_child("import time;print('started',flush=True);time.sleep(20)", seconds=1)
        self.assertFalse(result['accepted'])
        self.assertIn('deadline_exceeded', result['errors'])
        self.assertTrue(result['processStarted'])
        self.assertIsInstance(result['processReturncode'], int)
        self.assertEqual((self.root/'stdout').read_bytes(), b'started\n')

    def test_spawn_failure_has_explicit_receipt(self):
        result = capture.capture(['/definitely/absent/source-only-test-command'], self.root,
                                 self.root/'out',self.root/'err',self.root/'receipt',1,1024)
        self.assertFalse(result['accepted'])
        self.assertFalse(result['processStarted'])
        self.assertIsNone(result['processReturncode'])
        self.assertTrue(any(e.startswith('spawn_failed:') for e in result['errors']))

    def test_existing_file_not_overwritten(self):
        (self.root/'stdout').write_bytes(b'keep')
        with self.assertRaises(ValueError): self.run_child("print('no')")
        self.assertEqual((self.root/'stdout').read_bytes(), b'keep')

    def test_symlink_output_rejected(self):
        (self.root/'keep').write_bytes(b'keep')
        (self.root/'stdout').symlink_to(self.root/'keep')
        with self.assertRaises(ValueError): self.run_child("print('no')")
        self.assertEqual((self.root/'keep').read_bytes(), b'keep')

    def test_duplicate_output_rejected(self):
        with self.assertRaises(ValueError):
            capture.capture([sys.executable], self.root, self.root/'same',self.root/'same',self.root/'receipt',1,1)

    def test_unverified_group_never_signalled(self):
        with patch.object(capture.os, 'getpgid', return_value=-1), patch.object(capture.os, 'killpg') as group_signal:
            result = self.run_child("import time;time.sleep(20)")
        self.assertFalse(result['accepted'])
        self.assertIsNone(result['ownedProcessGroup'])
        group_signal.assert_not_called()
        self.assertTrue(any(s.get('scope') == 'owned-child-only' for s in result['signals']))

    def test_command_allowlist(self):
        capture.validate_command('fetch',capture.FETCH)
        capture.validate_command('build',capture.BUILD)
        capture.validate_command('compile',['rustc','+1.85.1','--edition=2021','/inputs/proof.rs','--extern','layerfs_bridge=/target/lib.rlib','-L','dependency=/target','-o','/tmp/layerfs-encoder-proof'])
        capture.validate_command('proof',['/tmp/layerfs-encoder-proof'])
        for stage,argv in [('build',capture.BUILD+['--no-default-features']),('proof',['/tmp/layerfs-daemon']),('fetch',['sh','-c','true']),('compile',['rustc','other.rs'])]:
            with self.subTest(stage=stage,argv=argv),self.assertRaises(ValueError): capture.validate_command(stage,argv)

    def test_invalid_caps_do_not_start(self):
        for seconds,cap,reserve in [(0,1,1),(2401,1,1),(1,0,1),(1,33*capture.MIB,1),(1,1,2*capture.MIB)]:
            with self.subTest(values=(seconds,cap,reserve)),self.assertRaises(ValueError):
                capture.capture([sys.executable],self.root,self.root/'a',self.root/'b',self.root/'c',seconds,cap,reserve)
        self.assertEqual(list(self.root.iterdir()),[])


if __name__=='__main__':unittest.main()
