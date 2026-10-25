#!/usr/bin/env python3
"""Fixed same-runner A/B experiment. No source patches or comparator runtime."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time
from cas_sample import filesystem_used
PINS = {'baseline': 'bc4165f5f55ceac63e18716ac96b19d9e4675afd',
        'candidate': 'a2b76e4c3ecdccdeeca24a669df4a82d1a4792f3'}

MODE = os.environ.get('LIFECYCLE_MODE', 'smoke')
assert MODE in ('smoke', 'full')
CASES = (['identical', 'unique', 'mixed', 'insert', 'history-distributed',
          'history-hotset', 'history-recurring'] if MODE == 'full'
         else ['identical', 'history-distributed'])
BACKENDS = [os.environ.get('SPRIG_BACKEND', 'native')]
assert BACKENDS[0] in ('native', 'projection', 'writable')
PAIRS = 5 if MODE == 'full' else 1
EXPECTED = len(CASES) * len(BACKENDS) * PAIRS * 2
READBACKS = sum(c.startswith('history-') for c in CASES) * len(BACKENDS) * PAIRS * 2 * 100
SIZE = 2 * 1024**3
RESERVE = 8 * 1024**3


def command(args):
    return subprocess.check_output([str(x) for x in args], text=True, stderr=subprocess.PIPE)


def save(path, data):
    # Atomic durable external evidence before any successful image disposal.
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def empty_space(mount):
    command(['btrfs', 'filesystem', 'sync', mount])
    usage = command(['btrfs', 'filesystem', 'usage', '-b', mount])
    return {'filesystemUsedBytes': filesystem_used(usage), 'usageRaw': usage,
            'groupsRaw': command(['btrfs', 'filesystem', 'df', '-b', mount])}


def validate(sample, label, backend, case):
    history_count = 100 if case.startswith("history-") else 0
    assert sample['ok'] and not sample['prototype_only']
    assert sample['production_sha'] == PINS[label] and sample['backend'] == backend
    for field in ['init_seconds', 'import_seconds', 'first_fork_seconds', 'first_read_seconds',
                  'total_import_fork_read_seconds', 'warm_fork_seconds', 'warm_read_seconds',
                  'warm_total_seconds', 'write_seconds', 'checkpoint_seconds',
                  'restore_seconds', 'restore_read_seconds', 'restore_cleanup_seconds']:
        v = sample[field]
        assert type(v) in (int, float) and math.isfinite(v) and v >= 0, field
    assert sample.get('history_distinct_revisions', 0) == history_count
    assert len(sample['checkpoint_steps']) == history_count and sample['fullHistoricalSnapshotReadbacks'] == history_count
    assert all(sample[k] for k in ['allAcknowledgedIdsPresent', 'sourceUnchanged',
                                 'originalMainViewUnchanged', 'originalSecondViewUnchanged'])
    assert sample['remainingMounts'] == [] and sample['lifecycle']['cleanup']['complete']
    for point in ('activeSpace', 'postHistorySpace'):
        used = sample[point]['filesystemUsedBytes']
        assert type(used) in (int, float) and math.isfinite(used) and used >= 0
    after = sample['lifecycle']['activeAfterHistory']
    assert after['historicalReadbacksComplete'] is True
    assert after['historicalReadbacksCompleted'] == history_count
    assert len(after['views']) == 3
    assert after['retainedGenerationCount'] == 3 + history_count * (2 if backend == 'writable' else 1)
    assert sample['componentDiagnostics']['postHistorySpace']['complete'] is True
    active = sample['lifecycle']['activeAtSpace']
    assert len(active['views']) == 3 and not active['historicalReadbacksStarted']
    assert len(active['foregroundFuseProcesses']) == (3 if backend != 'native' else 0)
    assert active['controlProcessesRunning'] == (3 if backend != 'native' else 0)


def run():
    assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.geteuid() == 0
    temp = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    cwd = Path.cwd().resolve(strict=True)
    results = cwd / 'results'
    results.mkdir(exist_ok=True)
    ledger = temp / 'lifecycle-ab-records'
    ledger.mkdir(exist_ok=False)
    built = json.loads((results / 'ab-builds.json').read_text())
    binary_hashes = {}
    for label, sha in PINS.items():
        checkout = cwd / ('sprig-' + label)
        assert built[label]['sha'] == sha
        binary = checkout / 'target/release/sprig'
        binary_hashes[label] = hashlib.sha256(binary.read_bytes()).hexdigest()
        assert binary_hashes[label] == built[label]['binarySha256']
        assert Path(built[label]['targetDirectory']) == (checkout / 'target').resolve()
        assert command(['git', '-C', checkout, 'rev-parse', 'HEAD']).strip() == sha
    assert built['baseline']['targetDirectory'] != built['candidate']['targetDirectory']
    assert built['profile'] == 'release' and built['features'] == ['projection']
    schedule = []
    for pair in range(PAIRS):
        for ci, case in enumerate(CASES):
            for backend in (BACKENDS if (pair + ci) % 2 == 0 else BACKENDS[::-1]):
                bi = BACKENDS.index(backend)
                order = ['baseline', 'candidate'] if (pair + ci + bi) % 2 == 0 else ['candidate', 'baseline']
                schedule.append({'pair': pair, 'case': case, 'backend': backend, 'order': order})
    report = {'pins': PINS, 'binaryHashes': binary_hashes, 'schedule': schedule,
              'expectedRecords': EXPECTED, 'expectedHistoricalReadbacks': READBACKS,
              'mode': MODE, 'cases': CASES, 'backends': BACKENDS, 'pairs': PAIRS,
              'complete': False, 'records': [], 'pairCleanup': [],
              'postBuildDisk': dict(zip(['total', 'used', 'free'], shutil.disk_usage(temp)))}
    output = results / 'lifecycle-ab.json'
    save(output, report)
    try:
        for plan in schedule:
            capacity = shutil.disk_usage(temp)
            assert capacity.free >= 2 * SIZE + RESERVE, 'insufficient space for whole A/B pair and reserve'
            images = []
            for label in plan['order']:
                r = {**plan, 'revision': label, 'correct': False, 'freeBeforePair': capacity.free}
                report['records'].append(r)
                save(output, report)
                directory = Path(tempfile.mkdtemp(prefix='sprig-ab-', dir=temp))
                image, mount = directory / 'new.img', directory / 'mount'
                with image.open('xb') as f:
                    f.truncate(SIZE)
                identity = (image.stat().st_dev, image.stat().st_ino)
                mount.mkdir()
                r['filesystem'] = {'image': str(image), 'mount': str(mount)}
                save(output, report)
                r['filesystem']['mkfs'] = command(['mkfs.btrfs', '-d', 'single', '-m', 'dup', image])
                child_started = False
                unmount_attempted = False
                try:
                    command(['mount', '-o', 'loop,noatime', image, mount])
                    assert command(['stat', '-f', '-c', '%T', mount]).strip() == 'btrfs'
                    r['filesystem']['empty'] = empty_space(mount)
                    source = cwd / 'fixtures' / plan['case']
                    args = ['/usr/bin/python3', cwd / 'feasibility/lifecycle_sample.py',
                        'run', '--root', mount / 'store', '--source', source,
                        '--oracle', str(source) + '.json', '--production-sha', PINS[label],
                        '--binary', cwd / ('sprig-' + label) / 'target/release/sprig',
                        '--backend', plan['backend'], '--records',
                        ledger / f"{plan['backend']}-{plan['case']}-{plan['pair']}-{label}.jsonl"]
                    if plan['case'].startswith('history-'):
                        args += ['--steps', str(source) + '-steps.json']
                    started = time.monotonic()
                    child_started = True
                    proc = subprocess.run([str(x) for x in args], text=True, capture_output=True)
                    r['sampleWallSeconds'] = time.monotonic() - started
                    r['sampleStderr'] = proc.stderr
                    try:
                        r['sample'] = json.loads(proc.stdout)
                    except Exception:
                        r['invalidSampleStdout'] = proc.stdout
                        raise
                    save(output, report)
                    assert proc.returncode == 0, 'sample failed; preserve image and mount diagnostics'
                    validate(r['sample'], label, plan['backend'], plan['case'])
                    r['filesystemUsedDeltaBytes'] = (r['sample']['activeSpace']['filesystemUsedBytes']
                        - r['filesystem']['empty']['filesystemUsedBytes'])
                    assert r['filesystemUsedDeltaBytes'] >= 0
                    r['postHistoryFilesystemUsedDeltaBytes'] = (r['sample']['postHistorySpace']['filesystemUsedBytes'] - r['filesystem']['empty']['filesystemUsedBytes'])
                    assert r['postHistoryFilesystemUsedDeltaBytes'] >= 0
                    unmount_attempted = True
                    command(['umount', '-i', mount])
                    assert subprocess.run(['mountpoint', '-q', str(mount)]).returncode == 32
                    r['correct'] = True
                    images.append((image, mount, identity))
                    save(output, report)
                    print(json.dumps({**plan, 'revision': label, 'correct': True,
                          'sampleWallSeconds': r['sampleWallSeconds']}), flush=True)
                finally:
                    if not r['correct']:
                        diagnostic = {'imagePreserved': True, 'mount': str(mount), 'image': str(image)}
                        diagnostic['mountinfo'] = Path('/proc/self/mountinfo').read_text()
                        try:
                            diagnostic['loopDevices'] = command(['losetup', '-j', image])
                            mounted = subprocess.run(['mountpoint', '-q', str(mount)]).returncode == 0
                            child_clean = r.get('sample', {}).get('lifecycle', {}).get('cleanup', {}).get('complete') is True
                            if mounted and not unmount_attempted and (not child_started or child_clean):
                                command(['umount', '-i', mount])
                                diagnostic['ordinaryUnmount'] = 'success'
                            elif mounted:
                                diagnostic['ordinaryUnmount'] = 'preserved: prior ordinary unmount failed or child teardown unconfirmed'
                            else:
                                diagnostic['ordinaryUnmount'] = 'not mounted'
                        except Exception as cleanup:
                            diagnostic['cleanupError'] = str(cleanup)
                            diagnostic['cleanupStderr'] = getattr(cleanup, 'stderr', None)
                        r['failureLifecycle'] = diagnostic
                        save(output, report)
            # Only completed, fully verified pairs may dispose their own unmounted images.
            clean = {**plan, 'complete': False, 'images': []}
            report['pairCleanup'].append(clean)
            for image, mount, identity in images:
                assert image.parent.parent == temp and image.parent.name.startswith('sprig-ab-')
                info = image.lstat()
                assert stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == identity
                assert image.resolve(strict=True) == image
                assert subprocess.run(['mountpoint', '-q', str(mount)]).returncode == 32
                for attempt in range(20):
                    loops = command(['losetup', '-j', image]).strip()
                    if not loops:
                        break
                    time.sleep(0.25)
                assert not loops, 'loop still attached; preserve image'
                clean['images'].append({'path': str(image), 'allocatedBytes': info.st_blocks * 512,
                                        'bytes': info.st_size, 'removed': False})
                save(output, report)
                image.unlink()
                clean['images'][-1]['removed'] = True
                save(output, report)
            clean['complete'] = True
            save(output, report)
        assert len(report['records']) == EXPECTED and all(r['correct'] for r in report['records'])
        assert len(report['pairCleanup']) == EXPECTED // 2 and all(p['complete'] for p in report['pairCleanup'])
        report['complete'] = True
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error),
                           'stderr': getattr(error, 'stderr', None)}
        raise
    finally:
        save(output, report)


if __name__ == '__main__':
    run()
