"""Explicit profile identities; legacy ordinary/128 recipes remain unchanged."""
import stress_cargo_pressure as legacy
import stress_cargo_pressure_long as long
ORDINARY={'schema':'sprig-cargo-experiment-v1','profile':'ordinary','roundsPerMode':4,'incrementalModes':[0,1],'order':'alternating-pairs-mode-offset','pressure':None}
MODULES={legacy.SPEC['profile']:legacy,long.SPEC['profile']:long}
PROFILE_NAMES=('ordinary',*MODULES)
LEGACY_PINS={'sprig-baseline':'4ef4a90d7ccf5f305416c5374bfc81038f5ca46e','sprig-candidate':'b300693e01c652c1a9631c61b7a439892d8f75cd'}
LONG_PINS={'sprig-baseline':'b300693e01c652c1a9631c61b7a439892d8f75cd','sprig-candidate':'dfee7e4e9ee223f25d141d2e05d3cfcdc6c9269f'}
def module_for(profile):
    if profile not in MODULES:raise ValueError('unreviewed pressure profile')
    return MODULES[profile]
def experiment_for(profile):
    if profile=='ordinary':return dict(ORDINARY)
    module=module_for(profile)
    return {**ORDINARY,'profile':profile,'pressure':module.pressure_identity()}
def pins_for(profile):
    if profile not in PROFILE_NAMES:raise ValueError('unreviewed pressure profile')
    return dict(LONG_PINS if profile==long.SPEC['profile'] else LEGACY_PINS)
