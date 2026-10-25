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
        previous=runtime.require_empty;runtime.require_empty=strict_require_empty
        try: value=runtime.relocate(a.mount,a.state,a.archive,a.image)
        finally: runtime.require_empty=previous
        print(json.dumps(value))

if __name__=='__main__':main()
