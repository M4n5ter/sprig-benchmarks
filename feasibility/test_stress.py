#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from tree_oracle import snapshot, differences
from stress_fixture import generate, apply_edit, expected_after
from stress_plan import matrix
from stress_stats import latency_summary
from stress_cargo_fixture import generate as cargo


class StressTests(unittest.TestCase):
    def test_replay_and_hardlinks(self):
        for pattern in ('random', 'hot', 'repeated'):
            with self.subTest(pattern=pattern), tempfile.TemporaryDirectory() as t:
                root = Path(t)/'source'
                fixture = generate(root, files=16, size=4096, depth=8, width=4,
                                   links=16, steps=30, pattern=pattern, symlink=True)
                for i, edit in enumerate(fixture['edits'], 1):
                    apply_edit(root, edit)
                    self.assertEqual(differences(expected_after(fixture, i), snapshot(root)), [])

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as t:
            a = generate(Path(t)/'a', files=10, steps=10, links=3)
            b = generate(Path(t)/'b', files=10, steps=10, links=3)
            self.assertEqual(a, b)

    def test_full_oracle_rejects_extra_and_metadata(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)/'source'
            fixture = generate(root, files=2)
            next(root.rglob('*.dat')).chmod(0o600)
            (root/'extra').write_bytes(b'')
            diff = differences(fixture['initial'], snapshot(root))
            self.assertTrue(any(x.get('path') == 'extra' for x in diff))
            self.assertGreaterEqual(len(diff), 2)

    def test_bounded_and_nondestructive(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)/'source'
            generate(root, files=1)
            with self.assertRaises(FileExistsError): generate(root, files=1)
            with self.assertRaises(ValueError): generate(Path(t)/'bad', files=50001)
            self.assertFalse((Path(t)/'bad').exists())

    def test_plan(self):
        rows = matrix()
        self.assertEqual(len({r['name'] for r in rows}), len(rows))
        pilots = [r for r in rows if r['priorityPilot']]
        self.assertEqual(len(pilots), 3)
        self.assertTrue(all(not r['capacityReviewRequired'] for r in pilots))
        self.assertTrue(all(r['imageGiB'] == 2 for r in rows))
        self.assertTrue(next(r for r in rows if r['name']=='history-random-1000')['capacityReviewRequired'])

    def test_tails(self):
        self.assertEqual(latency_summary(range(1,101))['p99'], 99)
        self.assertEqual(latency_summary(range(1,101))['p95'], 95)
        self.assertIsNone(latency_summary([1,2,3])['p99'])
        for bad in ([], [-1], [float('nan')], [float('inf')], [1, 'bad'], [True]):
            with self.assertRaises(ValueError): latency_summary(bad)

    def test_cargo_graph_deterministic_acyclic(self):
        with tempfile.TemporaryDirectory() as t:
            a = cargo(Path(t)/'a', 16)
            b = cargo(Path(t)/'b', 16)
            self.assertEqual(a, b)
            self.assertEqual(a['totalPackages'], 17)
            for name, deps in a['graph'].items():
                self.assertTrue(all(d < name for d in deps))
            self.assertTrue((Path(t)/'a/node000/build.rs').exists())

if __name__ == '__main__': unittest.main()
