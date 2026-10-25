import subprocess
import io,json
from contextlib import redirect_stderr
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import stress_runtime_storage as strict

class RuntimeTests(unittest.TestCase):
    def test_unreachable_never_calls_restore_or_stop(self):
        with patch.object(strict.runtime,'cmd',side_effect=subprocess.CalledProcessError(1,['docker','ps'])),patch.object(strict.runtime,'restore') as restore,patch.object(strict.runtime,'stop') as stop:
            with self.assertRaises(RuntimeError): strict.strict_restore('unused')
            restore.assert_not_called();stop.assert_not_called()
    def test_inventory_race_is_not_legacy_swallowed_exception(self):
        def restore(_):
            try: strict.runtime.require_empty()
            except subprocess.CalledProcessError: pass
            strict.runtime.stop()
        with patch.object(strict.runtime,'cmd',side_effect=['',subprocess.CalledProcessError(1,['docker','ps'])]),patch.object(strict.runtime,'restore',side_effect=restore),patch.object(strict.runtime,'stop') as stop:
            with self.assertRaises(RuntimeError): strict.strict_restore('unused')
            stop.assert_not_called()
    def test_live_container_blocks_restore(self):
        with patch.object(strict.runtime,'cmd',return_value='container-id\n'),patch.object(strict.runtime,'restore') as restore:
            with self.assertRaises(RuntimeError): strict.strict_restore('unused')
            restore.assert_not_called()

class LoadEvidenceTests(unittest.TestCase):
    def test_full_original_load_output_precedes_rollback_and_error_is_unchanged(self):
        failure=subprocess.CalledProcessError(1,('docker','load'),output='original failure\n'+'x'*200000)
        output=io.StringIO();events=[]
        def relocate(*_):
            try:strict.runtime.cmd('docker','load','-i','archive')
            except subprocess.CalledProcessError:
                events.append('rollback');self.assertIn('SPRIG_RUNTIME_LOAD_FAILURE',output.getvalue());raise
        with patch.object(strict.runtime,'cmd',side_effect=failure) as original,patch.object(strict.runtime,'relocate',side_effect=relocate),patch.object(strict.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='space',stderr='')) as queries,redirect_stderr(output):
            with self.assertRaises(subprocess.CalledProcessError) as caught:strict.observed_relocate('/mount','state','archive','image')
            self.assertIs(caught.exception,failure);self.assertIs(strict.runtime.cmd,original)
        row=json.loads(output.getvalue().split(' ',1)[1]);self.assertEqual(row['output'],failure.output)
        self.assertEqual(row['phase'],'image_load_before_setup_rollback');self.assertEqual(len(row['diagnostics']),2)
        self.assertEqual(events,['rollback']);self.assertEqual(queries.call_count,2)
    def test_diagnostic_failure_does_not_replace_load_error(self):
        failure=subprocess.CalledProcessError(7,('docker','load'),output='real cause')
        with patch.object(strict.runtime,'cmd',side_effect=failure),patch.object(strict.runtime,'relocate',side_effect=lambda *_:strict.runtime.cmd('docker','load')),patch.object(strict.subprocess,'run',side_effect=OSError('diagnostics unavailable')),redirect_stderr(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError) as caught:strict.observed_relocate('/mount','state','archive','image')
            self.assertIs(caught.exception,failure)

if __name__=='__main__':unittest.main()
