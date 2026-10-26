#!/usr/bin/env python3
"""Fixed, bounded source recipes for the separate three-pin cache experiment.

Legacy recipes are delegated unchanged. Independent duplicate content is
written into separate new files, never linked or cloned. This module creates
only a fresh source tree; it never normalizes a product or a restored tree.
"""
import base64
import hashlib
from pathlib import Path
import random

from stress_fixture import SEED, bytes_for, generate, normalize_source
from stress_plan import matrix
from tree_oracle import snapshot


_LEGACY_CELLS = ('files-4096', 'files-10000', 'cache-history-repeated-300')
_COMMON = dict(depth=0, width=1, links=0, steps=0, pattern='random', symlink=False)
_NEW_CELLS = {
    f'cache-independent-{label}-x{copies}': dict(
        _COMMON, files=4096, size=size, content_keys=4096 // copies,
        content_order='separated')
    for label, size in [('1k', 1024), ('4k', 4096)]
    for copies in [2, 8]
}
_NEW_CELLS.update({
    f'cache-alias-only-{label}': dict(_COMMON, files=2048, size=size, links=2048)
    for label, size in [('1k', 1024), ('4k', 4096)]
})
_NEW_CELLS['cache-independent-over4096'] = dict(
    _COMMON, files=8194, size=4096, content_keys=4097, content_order='separated')
_NEW_CELLS['cache-large-64k-1024'] = dict(_COMMON, files=1024, size=65536)
CACHE_CELLS = _LEGACY_CELLS + tuple(_NEW_CELLS)


def cache_cell_parameters(cell):
    """Return fresh parameters and the existing no-op-plus-one-edit policy."""
    if cell in _LEGACY_CELLS:
        params = dict(next(row['fixture'] for row in matrix() if row['name'] == cell))
    elif cell in _NEW_CELLS:
        params = dict(_NEW_CELLS[cell])
    else:
        raise ValueError('unknown approved cache cell')
    noop = params['steps'] == 0
    if noop:
        params['steps'] = 1
    return params, noop


def _validate_independent(params):
    expected = {'files', 'size', 'depth', 'width', 'links', 'steps', 'pattern',
                'symlink', 'content_keys', 'content_order'}
    if set(params) != expected:
        raise ValueError('unexpected independent-content fixture parameters')
    for key in ('files', 'size', 'depth', 'width', 'links', 'steps', 'content_keys'):
        if type(params[key]) is not int:
            raise ValueError('independent-content fixture counts must be integers')
    files, size, keys = (params[key] for key in ('files', 'size', 'content_keys'))
    if not (1 <= files <= 10000 and size in (1024, 4096)
            and 1 <= keys <= files and files % keys == 0):
        raise ValueError('invalid bounded independent-content mapping')
    if (params['depth'] != 0 or params['width'] != 1 or params['links'] != 0
            or params['steps'] not in (0, 1) or params['pattern'] != 'random'
            or params['symlink'] is not False
            or params['content_order'] not in ('separated', 'adjacent')):
        raise ValueError('unsupported independent-content recipe')
    if files * size > 256 * 1024**2:
        raise ValueError('independent-content fixture exceeds existing byte budget')


def _content_index(index, params):
    if params['content_order'] == 'separated':
        # Lexical width-one traversal sees every key before its next copy.
        return index % params['content_keys']
    return index // (params['files'] // params['content_keys'])


def _generate_independent(root, params):
    _validate_independent(params)  # reject everything before creating the root
    root = Path(root)
    root.mkdir()  # never replace or normalize an existing source
    names = []
    for index in range(params['files']):
        relative = Path('w0000') / f'f{index:06d}.dat'
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        key = _content_index(index, params)
        path.write_bytes(bytes_for(f'file:{key}', params['size']))
        names.append(relative.as_posix())
    normalize_source(root)
    initial = snapshot(root)
    rng = random.Random(SEED)
    edits = []
    for ordinal in range(params['steps']):
        index = rng.randrange(params['files'])
        key = _content_index(index, params)
        data = bytearray(bytes_for(f'file:{key}', params['size']))
        offset = rng.randrange(params['size'] - 63)
        payload = bytes_for(f'edit:random:{ordinal}', 64)
        data[offset:offset + 64] = payload
        name = names[index]
        # Equal content does not imply aliasing: only this independent inode
        # changes. Other copies remain covered by the complete-tree oracle.
        edits.append(dict(step=ordinal + 1, path=name, aliases=[name], offset=offset,
                          data=base64.b64encode(payload).decode(),
                          sha256=hashlib.sha256(data).hexdigest()))
    return dict(schema='sprig-stress-fixture-v1', seed=SEED,
                parameters=dict(params), initial=initial, edits=edits)


def generate_cache_fixture(root, cell):
    params, _ = cache_cell_parameters(cell)
    if 'content_keys' in params:
        return _generate_independent(root, params)
    # This includes the historical cells and alias-only controls. In
    # particular, historical source bytes, edits and metadata stay unchanged.
    return generate(root, **params)
