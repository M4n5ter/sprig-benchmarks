#!/usr/bin/env python3
"""Provenance-only wrapper; the production sample operation body is unchanged."""
import sys
from pathlib import Path
import production_sample
PINS = {'baseline': '46f96341498ef040280720d8f97c17de82db4419',
        'candidate': '17130154de38f3c30be6eae620ad0c0b6d404d48'}
if __name__ == '__main__':
    label = sys.argv.pop(1)
    if label not in PINS:
        raise SystemExit('unknown revision label')
    expected = Path.cwd() / ('sprig-' + label) / 'target/release/sprig'
    index = sys.argv.index('--binary')
    if Path(sys.argv[index + 1]).resolve(strict=True) != expected.resolve(strict=True):
        raise SystemExit('binary path does not match fixed revision checkout')
    production_sample.PRODUCTION_SHA = PINS[label]
    raise SystemExit(production_sample.main())
