#!/usr/bin/env python3
"""Stress-only fail-closed wrapper; frozen runtime helper remains unchanged.
A daemon inventory failure is NOT evidence of no live containers. No restore/stop
is admitted after that failure, including a race between two inventory reads.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import runtime_storage as runtime


def strict_require_empty():
    try:
        containers = runtime.cmd('docker','ps','-aq')
    except subprocess.CalledProcessError as error:
        # Frozen restore catches CalledProcessError; deliberately surface a
        # different exception so its legacy outage fallback cannot stop services.
        raise RuntimeError('cleanup blocked: Docker inventory unavailable; runtime retained') from error
    if containers.strip():
        raise RuntimeError('cleanup blocked: containers remain; runtime retained')


def strict_restore(state):
    strict_require_empty()
    previous=runtime.require_empty
    runtime.require_empty=strict_require_empty
    try:
        runtime.restore(state)
    finally:
        runtime.require_empty=previous



def observed_relocate(mount, state, archive, image):
    """Observe failed image load before legacy setup rollback, never change it."""
    previous_cmd = runtime.cmd
    previous_empty = runtime.require_empty
    def command(*args):
        try:
            return previous_cmd(*args)
        except subprocess.CalledProcessError as error:
            if args[:2] == ('docker', 'load'):
                # Original merged stdout/stderr is otherwise lost by traceback.
                evidence = {'schema': 'sprig-runtime-load-failure-v1',
                            'phase': 'image_load_before_setup_rollback',
                            'returncode': error.returncode,
                            'output': error.output, 'diagnostics': []}
                for query in [('df', '-B1', str(mount)),
                              ('btrfs', 'filesystem', 'usage', '-b', str(mount))]:
                    try:
                        result = subprocess.run(query, text=True, capture_output=True, timeout=10)
                        evidence['diagnostics'].append({'command': list(query),
                            'returncode': result.returncode, 'stdout': result.stdout,
                            'stderr': result.stderr})
                    except Exception as diagnostic_error:
                        evidence['diagnostics'].append({'command': list(query),
                            'error': type(diagnostic_error).__name__})
                # Diagnostic output failure must not replace the original error.
                try:
                    print('SPRIG_RUNTIME_LOAD_FAILURE '+json.dumps(evidence), file=sys.stderr, flush=True)
                except Exception:
                    pass
            raise
    runtime.cmd = command
    runtime.require_empty = strict_require_empty
    try:
        return runtime.relocate(mount, state, archive, image)
    finally:
        runtime.cmd = previous_cmd
        runtime.require_empty = previous_empty


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['enter','leave']);p.add_argument('--state',type=Path,required=True)
    p.add_argument('--mount',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--image')
    a=p.parse_args()
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.geteuid()!=0:
        raise RuntimeError('root authorized GitHub runner required')
    if a.action=='leave':
        strict_restore(a.state);print('{"restored":true}')
    else:
        # Before any product starts, existing relocate owns its setup rollback.
        # Runtime is required empty before relocation; a failed/incomplete
        # rollback must be preserved by outer setup-state admission checks.
        value=observed_relocate(a.mount,a.state,a.archive,a.image)
        print(json.dumps(value))

if __name__=='__main__':main()
