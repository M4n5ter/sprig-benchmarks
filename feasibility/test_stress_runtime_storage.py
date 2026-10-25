import subprocess
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

if __name__=='__main__':unittest.main()
