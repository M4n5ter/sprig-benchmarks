#!/usr/bin/env python3
"""Offline fixture-only tests: no product binary, mount, fault or benchmark."""
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import stress_cache_fixture as cache
from stress_fixture import apply_edit, expected_after, file_sizes, generate
from stress_plan import matrix
from tree_oracle import differences, snapshot


def small_parameters(*, copies=2, size=1024, order='separated'):
    params, _ = cache.cache_cell_parameters('cache-independent-1k-x2')
    params.update(files=16, size=size, content_keys=16 // copies, content_order=order)
    return params


class CacheFixtureTests(unittest.TestCase):
    def test_fixed_cells_retain_existing_resource_and_noop_bounds(self):
        self.assertEqual(len(cache.CACHE_CELLS), len(set(cache.CACHE_CELLS)))
        self.assertEqual(len(cache.CACHE_CELLS), 11)
        for cell in cache.CACHE_CELLS:
            params, noop = cache.cache_cell_parameters(cell)
            logical = sum(file_sizes(params['files'], params['size'],
                                     params.get('size_profile', 'uniform')))
            # Count aliases conservatively rather than crediting shared bytes.
            logical += params['links'] * params['size']
            retained = logical * (3 + 2 * (params['steps'] + int(noop)))
            self.assertLessEqual(retained, 1024**3, cell)
            self.assertEqual(noop, cell != 'cache-history-repeated-300')
            params['files'] = -1
            self.assertGreater(cache.cache_cell_parameters(cell)[0]['files'], 0)

    def test_large_inventory_control_crosses_real64k_eligibility_and_fits_budget(self):
        params,noop=cache.cache_cell_parameters('cache-large-64k-1024')
        self.assertTrue(noop);self.assertEqual((params['files'],params['size'],params['steps']),(1024,65536,1))
        self.assertNotIn('content_keys',params)
        self.assertEqual(params['files']*params['size'],64*1024**2)
        self.assertEqual(params['files']*params['size']*(3+2*(params['steps']+int(noop))),448*1024**2)
        with mock.patch.object(cache,'generate',return_value={'large':True}) as legacy:
            self.assertEqual(cache.generate_cache_fixture(Path('unused'),'cache-large-64k-1024'),{'large':True})
            legacy.assert_called_once_with(Path('unused'),**params)

    def test_historical_cells_delegate_exact_unchanged_parameters(self):
        rows = {row['name']: row['fixture'] for row in matrix()}
        for cell in ('files-4096', 'files-10000', 'cache-history-repeated-300'):
            expected = dict(rows[cell])
            if expected['steps'] == 0:
                expected['steps'] = 1
            with mock.patch.object(cache, 'generate', return_value={'unchanged': cell}) as legacy:
                self.assertEqual(cache.generate_cache_fixture(Path('unused'), cell),
                                 {'unchanged': cell})
                legacy.assert_called_once_with(Path('unused'), **expected)

    def test_duplicate_routes_use_fixed_keys_and_alias_routes_stay_legacy(self):
        for size_label, size in [('1k', 1024), ('4k', 4096)]:
            for copies in (2, 8):
                cell = f'cache-independent-{size_label}-x{copies}'
                params, _ = cache.cache_cell_parameters(cell)
                self.assertEqual((params['files'], params['size'], params['content_keys']),
                                 (4096, size, 4096 // copies))
                self.assertEqual(params['content_order'], 'separated')
                with mock.patch.object(cache, '_generate_independent', return_value={}) as create:
                    cache.generate_cache_fixture(Path('unused'), cell)
                    create.assert_called_once_with(Path('unused'), params)
            cell = f'cache-alias-only-{size_label}'
            params, _ = cache.cache_cell_parameters(cell)
            self.assertEqual((params['files'], params['links']), (2048, 2048))
            self.assertNotIn('content_keys', params)
            with mock.patch.object(cache, 'generate', return_value={}) as legacy:
                cache.generate_cache_fixture(Path('unused'), cell)
                legacy.assert_called_once_with(Path('unused'), **params)
        params, _ = cache.cache_cell_parameters('cache-independent-over4096')
        self.assertEqual((params['files'], params['content_keys']), (8194, 4097))
        self.assertEqual(params['content_order'], 'separated')

    def test_independent_duplicates_have_exact_bytes_but_distinct_inodes(self):
        for copies in (2, 8):
            for size in (1024, 4096):
                for order in ('separated', 'adjacent'):
                    with self.subTest(copies=copies, size=size, order=order), tempfile.TemporaryDirectory() as temp:
                        root = Path(temp) / 'source'
                        params = small_parameters(copies=copies, size=size, order=order)
                        fixture = cache._generate_independent(root, params)
                        files = [entry for entry in fixture['initial']['entries']
                                 if entry['type'] == 'file']
                        groups = fixture['initial']['hardlink_groups']
                        self.assertEqual(len(files), params['files'])
                        self.assertEqual(len(groups), params['files'])
                        self.assertTrue(all(len(group) == 1 for group in groups))
                        multiplicities = Counter(entry['sha256'] for entry in files)
                        self.assertEqual(len(multiplicities), params['content_keys'])
                        self.assertEqual(set(multiplicities.values()), {copies})
                        identities = set()
                        for index, entry in enumerate(files):
                            path = root / entry['path']
                            metadata = path.stat()
                            identities.add((metadata.st_dev, metadata.st_ino))
                            # Independent expected mapping, not the production
                            # helper: swapped traversal formulas must fail.
                            key = index % (16 // copies) if order == 'separated' else index // copies
                            self.assertEqual(path.read_bytes(), cache.bytes_for(f'file:{key}', size))
                        self.assertEqual(len(identities), params['files'])
                        self.assertEqual(differences(fixture['initial'], snapshot(root)), [])
                        edit = fixture['edits'][0]
                        self.assertEqual(edit['aliases'], [edit['path']])
                        apply_edit(root, edit)
                        self.assertEqual(differences(expected_after(fixture, 1), snapshot(root)), [])

    def test_real_alias_edit_changes_only_the_true_inode_group(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'source'
            fixture = generate(root, files=4, size=4096, width=1, links=4, steps=1)
            groups = fixture['initial']['hardlink_groups']
            self.assertEqual(len(groups), 4)
            self.assertTrue(all(len(group) == 2 for group in groups))
            for group in groups:
                first, second = (root / name for name in group)
                self.assertEqual((first.stat().st_dev, first.stat().st_ino),
                                 (second.stat().st_dev, second.stat().st_ino))
            edit = fixture['edits'][0]
            self.assertEqual(len(edit['aliases']), 2)
            apply_edit(root, edit)
            self.assertEqual(differences(expected_after(fixture, 1), snapshot(root)), [])

    def test_invalid_mapping_rejected_before_creating_any_source(self):
        invalid = [
            {'files': 15}, {'files': 10001}, {'files': True}, {'content_keys': 0},
            {'content_keys': 17}, {'content_keys': 3}, {'size': 2048},
            {'content_order': 'unknown'}, {'links': 1}, {'width': 2}, {'depth': 1},
            {'steps': 2}, {'pattern': 'hot'}, {'symlink': True},
            {'size_profile': 'cache-1-8-48k'},
        ]
        for change in invalid:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'source'
                params = small_parameters()
                params.update(change)
                with self.assertRaises(ValueError):
                    cache._generate_independent(root, params)
                self.assertFalse(root.exists())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'source'
            with self.assertRaises(ValueError):
                cache.generate_cache_fixture(root, 'unknown')
            self.assertFalse(root.exists())

    def test_existing_root_is_not_replaced_or_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'source'
            root.mkdir()
            (root / 'sentinel').write_bytes(b'keep existing source')
            before = snapshot(root)
            with self.assertRaises(FileExistsError):
                cache._generate_independent(root, small_parameters())
            self.assertEqual(differences(before, snapshot(root)), [])


if __name__ == '__main__':
    unittest.main()
