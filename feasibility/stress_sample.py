#!/usr/bin/env python3
"""Full-tree pressure sampler for an already mounted disposable CI Btrfs image.

Public CLI only. Reuses reviewed preparation/mount/normal-cleanup checks without
changing any frozen sampler. Source pin is supplied by verified build harness;
this program hashes the binary but cannot derive its source commit.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import traceback

from cas_sample import (HEX64, SampleError, checked_path, exact_mount,
                        filesystem_used, inside, mount_table, overlaps,
                        relative_name, require, write_command)
from lifecycle_sample import CurrentSample, production_report
from stress_fixture import expected_after
from stress_stats import latency_summary
from tree_oracle import snapshot, differences

MiB = 1024 ** 2


class BudgetAbort(RuntimeError):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def validate_fixture(fixture, oracle):
    require(fixture.get('schema') == 'sprig-stress-fixture-v1', 'unexpected stress fixture schema')
    initial = fixture['initial']
    # Self comparison validates schema/duplicate paths; shape checks below are
    # deliberately independent of content hashes captured from source later.
    require(not differences(initial, initial), 'invalid initial oracle')
    entries = {row['path']: row for row in initial['entries']}
    require(entries.get('.', {}).get('type') == 'directory', 'missing root directory oracle')
    for path, row in entries.items():
        if path != '.':
            relative_name(path)
        require(row.get('type') in ('file', 'directory', 'symlink'), 'unsupported oracle entry')
    listed = [dict(path=e['path'], bytes=e['size'], sha256=e['sha256'])
              for e in initial['entries'] if e['type'] == 'file']
    require(listed == oracle, 'listed manifest differs from complete source oracle')
    groups = initial['hardlink_groups']
    aliases = {}
    for group in groups:
        require(group and len(set(group)) == len(group), 'invalid hardlink group')
        for path in group:
            require(path not in aliases and entries.get(path, {}).get('type') == 'file',
                    'invalid or duplicate hardlink member')
            aliases[path] = set(group)
    require(set(aliases) == {e['path'] for e in initial['entries'] if e['type'] == 'file'},
            'hardlink groups do not cover all regular files')
    edits = fixture['edits']
    require(isinstance(edits, list) and len(edits) <= 1000, 'history exceeds bounded recipe')
    for i, edit in enumerate(edits, 1):
        require(edit['step'] == i, 'noncontiguous edit ordinal')
        name = relative_name(edit['path'])
        require(entries.get(name, {}).get('type') == 'file', 'edit target is not a regular file')
        require(set(edit['aliases']) == aliases[name] and len(edit['aliases']) == len(aliases[name]),
                'edit aliases differ from complete hardlink group')
        payload = base64.b64decode(edit['data'], validate=True)
        require(payload and base64.b64encode(payload).decode() == edit['data'], 'invalid canonical edit bytes')
        require(type(edit['offset']) is int and edit['offset'] >= 0
                and edit['offset'] + len(payload) <= entries[name]['size'], 'edit outside original file')
        require(HEX64.fullmatch(edit['sha256']), 'invalid edit digest')
    return listed


def parse_trace_line(line):
    prefix = 'SPRIG_LIFECYCLE_TRACE '
    if not line.startswith(prefix):
        return None
    row = json.loads(line[len(prefix):])
    require(isinstance(row, dict) and type(row.get('version')) is int and row['version'] == 1,
            'invalid lifecycle trace schema version')
    require(type(row.get('pid')) is int and row['pid'] > 0,
            'invalid lifecycle trace PID')
    require(isinstance(row.get('phase'), str) and row['phase'], 'invalid lifecycle trace phase')
    require(all(type(row.get(key)) is int and row[key] >= 0 for key in ('elapsed_ns','retries')),
            'invalid lifecycle trace elapsed/retry counters')
    require('ok' in row and (row['ok'] is None or type(row['ok']) is bool),
            'invalid lifecycle trace result')
    return row


class StressSample(CurrentSample):
    def prepare(self, args):
        require(1 <= args.budget_seconds <= 1200, 'budget must be 1..1200 seconds')
        require(args.records is not None, 'stress sampler requires external evidence ledger')
        self.diagnostic = args.diagnostic
        require(os.environ.get('SPRIG_LIFECYCLE_TRACE', '') in ('', '0', '1'), 'invalid trace setting')
        require(self.diagnostic or os.environ.get('SPRIG_LIFECYCLE_TRACE', '') != '1',
                'primary sampler refuses enabled lifecycle tracing')
        self.fixture_path = checked_path(args.fixture)
        self.fixture = json.loads(self.fixture_path.read_text())
        args.steps = None  # Reviewed base preparation only, never history100 loader.
        super().prepare(args)
        require(not overlaps(self.fixture_path, self.root)
                and not inside(self.fixture_path, self.source), 'fixture/oracle overlaps output or source')
        validate_fixture(self.fixture, self.oracle)
        self.operations = ([None] if args.noop_checkpoint else []) + self.fixture['edits']
        # Inherited retained-generation contract counts checkpoint operations,
        # including an unchanged checkpoint's retained writable generation.
        self.steps = self.operations
        self.deadline = time.monotonic() + args.budget_seconds
        self.budget_seconds = args.budget_seconds
        self.report.update(protocol='sprig-stress-full-tree-v1', status='pending',
            binarySha256=hashlib.sha256(self.binary.read_bytes()).hexdigest(),
            fixtureSha256=hashlib.sha256(self.fixture_path.read_bytes()).hexdigest(),
            fixtureParameters=self.fixture['parameters'],
            historyExpectedSteps=len(self.fixture['edits']),
            expectedCheckpointOperations=len(self.operations),
            noopCheckpointIncluded=args.noop_checkpoint,
            exactMetadataOracle=True, fullTreeChecks=[],
            instrumentation='lifecycle-trace' if self.diagnostic else 'off', diagnostic=self.diagnostic,
            checkpointOperationCount=0, resourceComparisonAvailable=False,
            wholeTaskTimingScope='execute: init through post-history space, excluding preparation and final teardown/archive',
            metadataScope=['path-set','type','bytes','mode-0777','mtime-ns','symlink-target','internal-hardlink-groups'],
            binarySourcePinVerifiedBySampler=False)
        self.report['measurementNotes'] = [
            'New stress protocol, not comparable to frozen listed-file timing without workload qualification.',
            'All exact path sets, bytes, modes, nanosecond mtimes, symlinks and internal hardlink groups checked.',
            'Every checkpoint acknowledgement, including unchanged initial revision when selected, is restored and fully checked.',
            'No-op committed=true retains the same revision; writable still retains/replaces its owned generation.',
            'Complete public CLI, readiness and normal-unmount costs retained; no processes killed or uncertain mutations retried.',
            'All source and full-tree oracle checks are setup-warm; no cold-cache, equal crash-durability or CPU/RAM-equivalence claim.',
            'Direct task wall includes checks/ledger/space diagnostics; additive phase diagnostics do not replace it.',
            'Budget guard is cooperative at operation boundaries, never a process-killing command timeout.',
            'Whole filesystem contains all retained trees/generations and runtime logs; no selective cleanup or pruning.',
            'Source commit comes from verified external checkout/build; recorded binary SHA is independently measured.',
        ]
        require(not any(inside(Path(m['mountpoint']), self.source) for m in mount_table()),
                'source contains a mount boundary')
        self.verify_tree(self.source, self.fixture['initial'], 'source-setup')
        # Count hardlink aliases conservatively; do not assume dedup/reflink.
        peak = sum(e['bytes'] for e in self.oracle) * (3 + 2 * len(self.operations))
        self.report['conservativeRetainedLogicalBytes'] = peak
        if peak > 1024 * MiB:
            raise BudgetAbort('capacity review required: retained estimate exceeds 1 GiB', estimatedBytes=peak)
        self.capacity_guard(peak)

    def command(self, arguments, *, cwd=None, record_event=True):
        # Same subprocess semantics as the inherited runner, but retain complete
        # stderr (including opt-in lifecycle trace) on successful commands too.
        args = [str(value) for value in arguments]
        self.sequence += 1
        sequence = self.sequence
        env = os.environ.copy()
        env.pop('SPRIG_LIFECYCLE_TRACE', None)
        if getattr(self, 'diagnostic', False) and args[0] == str(getattr(self, 'binary', '')):
            env['SPRIG_LIFECYCLE_TRACE'] = '1'
        proc = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding='utf-8', errors='replace', check=False)
        if self.logs and proc.stderr:
            (self.logs / ('command-%06d-stderr.log' % sequence)).write_text(proc.stderr)
        if record_event:
            self.event('command_finished', sequence=sequence, executable=args[0],
                       operation=args[1] if len(args) > 1 else None, returncode=proc.returncode,
                       stdoutBytes=len(proc.stdout.encode()), stderrBytes=len(proc.stderr.encode()))
        if proc.returncode:
            details = dict(argv=args, cwd=str(cwd) if cwd else None,
                           returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
            if self.logs:
                (self.logs / ('command-%06d-error.json' % sequence)).write_text(json.dumps(details, indent=2)+'\n')
            raise SampleError('command failed; no automatic retry', **details)
        return proc.stdout

    def guard(self, phase):
        if time.monotonic() >= self.deadline:
            raise BudgetAbort('time budget exhausted before starting operation', phase=phase,
                              budgetSeconds=self.budget_seconds)
        # f_bavail is a cheap capacity safety signal, NOT comparative storage.
        statv = os.statvfs(self.root)
        available = statv.f_bavail * statv.f_frsize
        if available < 256 * MiB:
            raise BudgetAbort('capacity reserve exhausted before operation', phase=phase,
                              availableBytes=available, reserveBytes=256 * MiB)

    def capacity_guard(self, retained):
        usage = self.command(['btrfs', 'filesystem', 'usage', '-b', self.root])
        size = re.search(r'^\s*Device size:\s*(\d+)\s*$', usage, re.MULTILINE)
        require(size is not None and int(size[1]) == 2 * 1024 * MiB,
                'stress requires existing 2 GiB filesystem', usage=usage)
        used = filesystem_used(usage)
        self.report['capacityPreflight'] = dict(filesystemBytes=int(size[1]), usedBytes=used,
            retainedEstimateBytes=retained, reserveBytes=256 * MiB)
        if used + retained + 256 * MiB > int(size[1]):
            raise BudgetAbort('capacity estimate does not fit image plus reserve', **self.report['capacityPreflight'])

    def verify_tree(self, root, expected, label):
        start = time.perf_counter()
        # Same standalone oracle/JSON work as the SDK comparator. Complete
        # observed evidence remains charged inside measured logs, not the tree.
        output = self.command([sys.executable, Path(__file__).with_name('tree_oracle.py'), 'snapshot', root])
        actual = json.loads(output)
        if self.logs:
            (self.logs / ('oracle-%06d.json' % len(self.report['fullTreeChecks']))).write_text(output)
        mismatch = differences(expected, actual)
        seconds = time.perf_counter() - start
        row = dict(label=label, entries=len(actual['entries']), seconds=seconds,
                   verified=not mismatch, oracleSha256=hashlib.sha256(
                       json.dumps(expected, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
        self.report['fullTreeChecks'].append(row)
        if mismatch:
            self.step_record(dict(event='full_tree_mismatch', **row, differences=mismatch))
            raise SampleError('full-tree content/metadata/hardlink oracle failed', label=label, differences=mismatch)
        self.step_record(dict(event='full_tree_verified', **row))
        return seconds

    def checkpoint(self, first, ordinal, edit, previous, distinct):
        self.guard('checkpoint-' + str(ordinal))
        write_seconds = 0.0
        if edit is not None:
            start = time.perf_counter()
            self.shell(first['merged'], write_command(edit))
            write_seconds = time.perf_counter() - start
        start = time.perf_counter()
        result = self.cli('checkpoint', 'work', '--message', 'stress operation ' + str(ordinal))
        cli_seconds = time.perf_counter() - start
        self.step_record(dict(event='checkpoint_response', ordinal=ordinal, checkpoint=result,
                              checkpoint_cli_seconds=cli_seconds))
        require(not result.get('mount_error'), 'checkpoint returned mount_error; no retry')
        require(result['committed'] is True and result['branch'] == 'work'
                and result['previous_head'] == previous and HEX64.fullmatch(result['revision']),
                'invalid checkpoint acknowledgement', checkpoint=result)
        if edit is None:
            require(result['revision'] == previous, 'unchanged checkpoint unexpectedly created revision')
        else:
            require(result['revision'] != previous and result['revision'] not in distinct,
                    'changed checkpoint did not create distinct revision')
            distinct.add(result['revision'])
        old = first
        start = time.perf_counter()
        first = self.view(self.cli('show', 'work'))
        require(first['base_revision'] == result['revision'], 'checkpoint show has wrong revision')
        if self.backend == 'writable':
            require(first['generation'] != old['generation'] and exact_mount(old['merged']) is None,
                    'writable checkpoint did not normally replace generation')
        else:
            require(first['generation'] == old['generation'], 'nonwritable checkpoint replaced generation')
        ready_seconds = time.perf_counter() - start
        self.views[self.views.index(old)] = first
        row = dict(step=ordinal, editStep=edit['step'] if edit else 0, noop=edit is None,
            revision=result['revision'], base=previous, write_seconds=write_seconds,
            checkpoint_cli_seconds=cli_seconds, checkpoint_ready_seconds=ready_seconds,
            checkpoint_seconds=cli_seconds+ready_seconds,
            generation_before=old['generation'], generation_after=first['generation'],
            checkpoint=result, fullTreeVerified=False)
        self.report['write_seconds'] += write_seconds
        self.report['checkpoint_seconds'] += row['checkpoint_seconds']
        self.report['checkpoint_steps'].append(row)
        self.report['checkpointOperationCount'] += 1
        self.report['history_distinct_revisions'] = len(distinct)
        self.step_record(dict(event='checkpoint_acknowledged', **row))
        self.verify_tree(first['merged'], expected_after(self.fixture, row['editStep']),
                         'checkpoint-' + str(ordinal))
        row['fullTreeVerified'] = True
        return first, result['revision']

    def execute(self):
        start_task = time.perf_counter()
        try:
            self.guard('init')
            start = time.perf_counter(); self.cli('init')
            self.report['init_seconds'] = time.perf_counter() - start
            self.guard('import')
            start = time.perf_counter()
            imported = self.cli('import', self.source, 'main', creation=True)
            main = self.created_view(imported)
            self.report['import_seconds'] = time.perf_counter() - start
            self.views.append(main)
            initial = main['base_revision']
            require(HEX64.fullmatch(initial), 'invalid import revision')
            self.report.update(initialHead=initial, **{'import': imported})
            self.verify_tree(main['merged'], self.fixture['initial'], 'main-initial')
            for name, fork_key, read_key in [('work','first_fork_seconds','first_read_seconds'),
                                             ('second','warm_fork_seconds','warm_read_seconds')]:
                self.guard('fork-' + name)
                start = time.perf_counter()
                view = self.created_view(self.cli('fork', 'main', name, creation=self.backend == 'writable'))
                self.report[fork_key] = time.perf_counter() - start
                self.views.append(view)
                self.report[read_key] = self.verify_tree(view['merged'], self.fixture['initial'], name+'-initial')
            first, second = self.views[1:]
            self.report['total_import_fork_read_seconds'] = sum(self.report[k] for k in
                ('import_seconds','first_fork_seconds','first_read_seconds'))
            self.report['warm_total_seconds'] = self.report['warm_fork_seconds']+self.report['warm_read_seconds']
            base, distinct = initial, set()
            for ordinal, edit in enumerate(self.operations, 1):
                first, base = self.checkpoint(first, ordinal, edit, base, distinct)
            history = self.cli('log', 'work')
            expected = [r['revision'] for r in reversed(self.report['checkpoint_steps']) if not r['noop']] + [initial]
            require([r['revision'] for r in history] == expected, 'exact acknowledged revision chain differs')
            for i, revision in enumerate(history):
                require(revision['parents'] == expected[i+1:i+2], 'revision parent chain differs')
            self.guard('primary-space')
            self.sample_space()
            # Exact physical generation cardinality, in addition to inherited
            # mount/PID checks. No selective generation deletion is permitted.
            actual = sum(stat.S_ISDIR(p.lstat().st_mode) for p in (self.library/'native').iterdir())
            expected_count = 3 + (len(self.operations) if self.backend == 'writable' else 0)
            require(actual == expected_count, 'unexpected primary retained generation count',
                    expected=expected_count, actual=actual)
            self.report['lifecycle']['activeAtSpace']['retainedGenerationCount'] = actual
            for row in self.report['checkpoint_steps']:
                self.guard('restore-' + str(row['step']))
                start = time.perf_counter()
                restored = self.created_view(self.cli('restore', row['revision'],
                    'history-%04d' % row['step'], creation=True))
                restore_seconds = time.perf_counter() - start
                require(restored['base_revision'] == row['revision'], 'restore acknowledged wrong revision')
                read_seconds = self.verify_tree(restored['merged'], expected_after(self.fixture, row['editStep']),
                                                'restore-' + str(row['step']))
                self.report['fullHistoricalSnapshotReadbacks'] += 1
                cleanup_seconds = 0.0
                if self.backend != 'native':
                    start = time.perf_counter(); self.unmount_generation(restored['generation'])
                    cleanup_seconds = time.perf_counter() - start
                restored_row = dict(step=row['step'], revision=row['revision'], generation=restored['generation'],
                    restore_seconds=restore_seconds, restore_read_seconds=read_seconds,
                    restore_cleanup_seconds=cleanup_seconds, fullTreeVerified=True,
                    cleanup_operation='native tree retained' if self.backend=='native' else 'CLI unmount-generation')
                self.report['restore_seconds'] += restore_seconds
                self.report['restore_read_seconds'] += read_seconds
                self.report['restore_cleanup_seconds'] += cleanup_seconds
                self.report['historical_restore_steps'].append(restored_row)
                self.step_record(dict(event='historical_snapshot_verified', **restored_row))
            for label, root in [('source',self.source), ('main',main['merged']), ('second',second['merged'])]:
                self.guard('final-' + label)
                self.verify_tree(root, self.fixture['initial'], label+'-unchanged')
            listing = self.cli('list')
            require(listing['branches']['main'] == initial and listing['branches']['second'] == initial,
                    'unchanged branch moved')
            self.guard('post-history-space')
            self.sample_post_history_space()
            self.report.update(originalMainViewUnchanged=True, originalSecondViewUnchanged=True,
                sourceUnchanged=True, allAcknowledgedIdsPresent=True, ok=True, status='passed')
            checkpoint_keys = ('write_seconds','checkpoint_cli_seconds','checkpoint_ready_seconds','checkpoint_seconds')
            restore_keys = ('restore_seconds','restore_read_seconds','restore_cleanup_seconds')
            self.report['latencies'] = {key: latency_summary([r[key] for r in rows])
                for rows, keys in ((self.report['checkpoint_steps'], checkpoint_keys),
                                   (self.report['historical_restore_steps'], restore_keys))
                for key in keys if rows}
            self.report['latencyScope'] = 'all recorded operations; noop/changed are additionally separated below'
            self.report['checkpointLatenciesByKind'] = {}
            for kind, is_noop in [('unchanged', True), ('changed', False)]:
                rows = [r for r in self.report['checkpoint_steps'] if r['noop'] == is_noop]
                if rows:
                    self.report['checkpointLatenciesByKind'][kind] = {
                        key: latency_summary([r[key] for r in rows]) for key in checkpoint_keys}
            changed = [r for r in self.report['checkpoint_steps'] if not r['noop']]
            self.report['historyWindows'] = []
            for index, label in enumerate(('early','middle','late')):
                rows = changed[len(changed)*index//3:len(changed)*(index+1)//3]
                if rows:
                    self.report['historyWindows'].append(dict(label=label,
                        firstEdit=rows[0]['editStep'], lastEdit=rows[-1]['editStep'],
                        checkpointSeconds=latency_summary([r['checkpoint_seconds'] for r in rows])))
        finally:
            self.report['wholeTaskSeconds'] = time.perf_counter() - start_task

    def preserve_logs(self):
        # Do not inline hundreds of complete oracle JSON files again in the
        # report; full bytes live in the archive below and remain in the store.
        if not self.root or not self.records:
            return
        # Evidence copying only after all physical samples/normal cleanup.
        # Originals remain in charged store; no truncation of archived copies.
        archive = self.records.with_name(self.records.name + '.logs')
        archive.mkdir(mode=0o755, exist_ok=False)
        os.chmod(archive, 0o755)
        paths = set(self.logs.glob('*'))
        if self.library:
            paths.update((self.library/'native').glob('*/projection-*.log'))
            paths.update((self.library/'native').glob('*/writable-*.log'))
        self.report['completeLogArchive'] = []
        self.report['runtimeLogs'] = []
        trace_counts = dict(cli=0, daemon=0, other=0)
        trace_phases = {}
        trace_errors = []
        for index, path in enumerate(sorted(paths)):
            checked_path(path)
            if not path.is_file():
                continue
            target = archive/('%06d-' % index + path.name)
            shutil.copyfile(path, target)
            os.chmod(target, 0o644)
            archived_bytes = target.read_bytes()
            self.report['completeLogArchive'].append(dict(source=str(path), archived=str(target),
                bytes=len(archived_bytes), sha256=hashlib.sha256(archived_bytes).hexdigest()))
            if not path.name.startswith('oracle-') and not getattr(self,'diagnostic',False):
                if b'SPRIG_LIFECYCLE_TRACE ' in archived_bytes:
                    trace_counts['other'] += 1
            if not path.name.startswith('oracle-') and getattr(self,'diagnostic',False):
                with target.open('r', encoding='utf-8', errors='replace') as stream:
                    for line_number, line in enumerate(stream, 1):
                        try:
                            trace = parse_trace_line(line.rstrip('\n'))
                        except (ValueError, SampleError) as error:
                            trace_errors.append(dict(path=str(target), line=line_number, error=str(error)))
                            continue
                        if trace is not None:
                            category = ('cli' if path.parent == self.logs and path.name.endswith('-stderr.log')
                                        else 'daemon' if path.parent != self.logs else 'other')
                            trace_counts[category] += 1
                            trace_phases[trace['phase']] = trace_phases.get(trace['phase'], 0) + 1
                text = archived_bytes[-16384:].decode('utf-8', errors='replace')
                self.report['runtimeLogs'].append(dict(path=str(path), archived=str(target),
                    bytes=path.stat().st_size, truncated=len(archived_bytes) > 16384, text=text))
        count = sum(trace_counts.values())
        self.report['lifecycleTraceEvidence'] = dict(validRecords=count, counts=trace_counts,
            phases=trace_phases, invalidRecords=trace_errors, archivedBeforeValidation=True,
            enabled=getattr(self,'diagnostic',False), present=count > 0)
        require(not trace_errors, 'malformed lifecycle trace records preserved', errors=trace_errors)
        if getattr(self,'diagnostic',False):
            if self.report.get('ok'):
                require(count > 0, 'diagnostic run produced no valid archived lifecycle trace records')
        else:
            require(count == 0, 'primary run unexpectedly emitted lifecycle trace records')


def main():
    start_sample = time.perf_counter()
    report = production_report()
    sample = StressSample(report)
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        sub = parser.add_subparsers(dest='command', required=True)
        run = sub.add_parser('run')
        for key in ('root','source','oracle','fixture','binary','production-sha','backend','records'):
            run.add_argument('--'+key, required=True)
        run.add_argument('--budget-seconds', type=float, default=600)
        run.add_argument('--noop-checkpoint', action='store_true')
        run.add_argument('--diagnostic', action='store_true', help='separate instrumented series; never primary timings')
        args = parser.parse_args()
        require(args.backend in ('native','projection','writable'), 'invalid backend')
        sample.prepare(args)
        sample.execute()
    except SystemExit as error:
        if error.code == 0:
            return 0
        report.update(ok=False, status='failed', error=dict(type='SystemExit',message=str(error)))
    except BudgetAbort as error:
        report.update(ok=False, status='budget_aborted', budgetAbort=dict(message=str(error), details=error.details))
    except BaseException as error:
        report.update(ok=False, status='failed', error=dict(type=type(error).__name__, message=str(error),
            details=getattr(error,'details',{}), traceback=traceback.format_exc()))
    finally:
        try:
            sample.cleanup()
            sample.preserve_logs()
        except BaseException as error:
            report['ok'] = False
            report.setdefault('cleanupErrors', []).append(dict(message=str(error)))
    if report.get('cleanupErrors') or sample.cleanup_blocked:
        report['status'] = 'failed'
    elif report.get('status') == 'passed' and not report['ok']:
        report['status'] = 'failed'
    report['wholeSampleIncludingSetupCleanupSeconds'] = time.perf_counter() - start_sample
    if sample.root:
        try:
            (sample.root/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        except BaseException as error:
            report.update(ok=False, status='failed', reportWriteError=str(error))
    print(json.dumps(report, sort_keys=True))
    return 0 if report['ok'] else (2 if report.get('status') == 'budget_aborted' else 1)


if __name__ == '__main__':
    raise SystemExit(main())
