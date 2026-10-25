#!/usr/bin/env python3
"""Version-only native-fork experiment; reuse the frozen lifecycle driver."""
import lifecycle_ab as lifecycle
PINS = {'baseline': 'a2b76e4c3ecdccdeeca24a669df4a82d1a4792f3',
        'candidate': 'e2a86dc2b7942e0adf4273cd608857447d403335'}
assert lifecycle.BACKENDS == ['native'], 'this experiment is native-only'
lifecycle.PINS = PINS
if __name__ == '__main__':
    lifecycle.run()
