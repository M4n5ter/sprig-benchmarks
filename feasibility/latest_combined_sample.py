#!/usr/bin/env python3
"""Separate, fixed-main Native smoke series; no image/runtime ownership here.

The frozen listed-file shell workload and operation timers are inherited, not
rewritten. Complete command logs and an owned measured TMPDIR change accounting
overhead, so this series must not be pooled with the historical combined series.
This adapter never signals children, retries uncertain commands or unmounts an
outer image. Only the outer owner may act after known-empty cleanup evidence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import traceback

from cas_sample import (HEX64, Parser, SampleError, checked_path, inside,
                        mount_table, require)
from latest_sample import CurrentSample as Base, production_report as base_report
from lifecycle_sample import CurrentSample as PostHistoryContract

PRODUCTION_SHA = '4eb0f4d7afdb19bf22d9667dc520ede8b162c737'
SCHEMA = 'sprig-latest-combined-native-sample-v1'
STREAM_LIMIT = 2 * 1024**2
SOURCE_LOG_LIMIT = 64 * 1024**2
LEDGER_LIMIT = 8 * 1024**2
RAW_LIMIT = 128 * 1024**2
ARCHIVE_LIMIT = 1024**3
CHUNK = 1024**2


def production_report():
    report = base_report()  # Never mutate latest_sample's globals.
    report.update(schema=SCHEMA, production_sha=PRODUCTION_SHA,
                  product='sprig-native', backend='native', testOnly=False,
                  postHistorySpace=None, commands=[], uncertain=False,
                  remainingMountsKnown=False, remainingMounts=[],
                  remainingServersKnown=False, remainingServers=[],
                  archiveAdmission=None, archiveCopy=None,
                  sourceFilesRetained=True, complete_metadata_verification=False)
    report['measurementNotes'].extend([
        'Separate latest-main Native smoke series; only identical/count100 and history-distributed/history100.',
        'Original activeSpace remains primary; a second postHistorySpace follows all unchanged timed operations and readbacks, before cleanup.',
        'All command stdout/stderr bytes remain in measured logs. Complete logging/hashing and owned measured TMPDIR add overhead; do not pool with old timings.',
        'Native CLI output streams directly to owned files inside command wait; LayerFS SDK string persistence follows its phase timer. These transport/capture scopes are not product-only equivalence.',
        'The frozen source fixture remains external and read-only, as in the original combined contract; product state, command/runtime logs and TMPDIR remain charged.',
        'The external metadata-only ledger is capped at8MiB. Archive copies are made only after known cleanup and whole-plan admission; original files are retained.',
        'Spawn/wait uncertainty is sticky: no next command, cleanup mutation, complete-archive claim or outer-image admission.',
        'Listed-file SHA/history checks are not a full metadata/hardlink oracle or equal-durability proof.',
    ])
    return report


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def regular_info(path, *, allow_links=False):
    path = checked_path(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and (allow_links or info.st_nlink == 1),
            'log/input must be an unlinked regular file', path=str(path))
    return info


def hash_regular(path, expected=None, *, allow_links=False):
    before = regular_info(path, allow_links=allow_links)
    if expected is not None:
        require(identity(before) == expected, 'source changed before hashing', path=str(path))
    digest = hashlib.sha256()
    with path.open('rb') as source:
        require(identity(os.fstat(source.fileno())) == identity(before), 'source replaced while opening')
        remaining = before.st_size
        while remaining:
            block = source.read(min(CHUNK, remaining))
            require(block, 'source shortened while hashing', path=str(path))
            digest.update(block)
            remaining -= len(block)
        require(source.read(1) == b'', 'source grew while hashing', path=str(path))
        require(identity(os.fstat(source.fileno())) == identity(before), 'source mutated while hashing')
    require(identity(regular_info(path, allow_links=allow_links)) == identity(before), 'source changed after hashing')
    return digest.hexdigest(), before.st_size


def validate_options(args):
    require(args.backend == 'native', 'only Native is authorized in this smoke series')
    require(args.production_sha == PRODUCTION_SHA, 'exact latest-main Sprig source pin required')
    require(isinstance(args.binary_sha256, str) and HEX64.fullmatch(args.binary_sha256),
            '--binary-sha256 must be lowercase SHA256')
    require(args.case in ('identical', 'history-distributed'), 'only fixed smoke cases allowed')
    require(bool(args.steps) == (args.case == 'history-distributed'), 'steps required only for history-distributed')
    require(type(args.archive_allowance_bytes) is int and 0 <= args.archive_allowance_bytes <= ARCHIVE_LIMIT,
            'archive allowance must be an integer in0..1GiB')
    for key in ('root', 'source', 'oracle', 'binary', 'records') + (('steps',) if args.steps else ()):
        value = getattr(args, key)
        require(isinstance(value, str) and value and '\0' not in value
                and Path(value).is_absolute() and os.path.normpath(value) == value,
                'canonical absolute path required', option=key)
    require(not os.environ.get('SPRIG_LIFECYCLE_TRACE'), 'primary Native series forbids ambient tracing')


def validate_fixture(case, oracle, steps):
    require(len(oracle) == (100 if case == 'identical' else 200), 'frozen fixture file count changed')
    require(len(steps) == (0 if case == 'identical' else 100), 'frozen history count changed')
    if case == 'identical':
        require([row['path'] for row in oracle] == [f'files/f{i:04}.dat' for i in range(100)]
                and all(row['bytes'] == 1048576 for row in oracle)
                and len({row['sha256'] for row in oracle}) == 1,
                'identical/count100 recipe shape changed')
    else:
        def name(i):
            if i < 64:
                return f'wide/s000-f{i:03}.dat'
            if i < 199:
                return f'regular/s000/f{i:03}.dat'
            return 'spine/' + '/'.join(f'd{n:03}' for n in range(1, 129)) + '/s000.dat'
        sizes = {name(i): 1024 if i < 128 else 8192 if i < 192 else 49152 for i in range(200)}
        require({row['path']: row['bytes'] for row in oracle} == sizes, 'history genesis shape changed')
        require(len({step['path'] for step in steps}) == 100, 'distributed steps must edit100 different files')
        for step in steps:
            require(step['offset'] == sizes[step['path']] // 2 - 32
                    and len(base64.b64decode(step['data'], validate=True)) == 64,
                    'frozen distributed edit shape changed')


class LatestCombinedSample(Base):
    retained_snapshot = PostHistoryContract.retained_snapshot
    sample_post_history_space = PostHistoryContract.sample_post_history_space

    def __init__(self, report):
        super().__init__(report)
        self.uncertain = False
        self.active_children = []
        self.preflight_logs = None
        self.preflight_argv = None
        self.preflight_used = False
        self.command_env = None
        self.log_bytes = 0
        self.ledger_bytes = 0
        self.archive_allowance = 0

    def prepare(self, args):
        validate_options(args)
        self.archive_allowance = args.archive_allowance_bytes
        self.report.update(case=args.case, binarySha256=args.binary_sha256,
                           binarySourcePinVerifiedBySampler=False,
                           productionShaSource='outer verified immutable checkout/build; sampler verifies binary hash')
        self.preflight_argv = ['stat', '-f', '-c', '%T', str(Path(args.root).parent)]
        self.preflight_logs = Path(args.root).with_name(Path(args.root).name + '.preflight-logs')
        super().prepare(args)
        # Base's sole pre-root command is the fixed stat above. Move, never
        # discard, its complete captured evidence into the owned measured root.
        if self.preflight_logs.exists():
            for source in sorted(self.preflight_logs.iterdir()):
                target = self.logs / source.name
                checked_path(target, new=True)
                source.rename(target)
                for row in self.report['commands']:
                    for field in ('stdoutPath', 'stderrPath'):
                        if row.get(field) == str(source):
                            row[field] = str(target)
            self.preflight_logs.rmdir()  # Only the now-empty owned log directory.
        validate_fixture(args.case, self.oracle, self.steps)
        # Cargo may hardlink target/release/sprig to its deps binary. This is a
        # read-only immutable build input, not a mutable source log alias.
        digest, size = hash_regular(self.binary, allow_links=True)
        require(digest == args.binary_sha256, 'binary bytes differ from immutable manifest')
        self.report.update(binaryHashVerified=True, binaryBytes=size)
        temporary = self.root / 'tmp'
        temporary.mkdir(mode=0o700)
        self.command_env = dict(os.environ, TMPDIR=str(temporary))
        self.report['temporaryDirectory'] = {'path': str(temporary), 'environment': 'TMPDIR',
                                             'insideMeasuredRoot': True, 'setBeforeProductCLI': True}

    def _unknown(self, row, error):
        self.uncertain = self.cleanup_blocked = True
        self.report.update(ok=False, uncertain=True, cleanupAdmissionBlocked=True)
        row.update(outcomeKnown=False, error={'type': type(error).__name__, 'message': str(error)})
        self.report['recoveryMetadata'] = {'retainImageAndSource': True,
            'reason': 'child spawn/wait completion unknown; no retry, signal or outer cleanup',
            'commandSequence': row['sequence']}

    def command(self, arguments, *, cwd=None, record_event=True):
        require(not self.uncertain, 'uncertain child blocks every subsequent command')
        args = [str(value) for value in arguments]
        preflight = self.logs is None
        if preflight:
            require(args == self.preflight_argv and not self.preflight_used and cwd is None,
                    'only the fixed one-shot stat preflight may precede owned logs')
            self.preflight_used = True
            checked_path(self.preflight_logs, new=True)
            self.preflight_logs.mkdir(mode=0o700)
            directory = self.preflight_logs
        else:
            directory = self.logs
        self.sequence += 1
        row = {'sequence': self.sequence, 'argv': args, 'cwd': str(cwd) if cwd else None,
               'returncode': None, 'outcomeKnown': False}
        paths = {stream: directory / f'command-{self.sequence:06}-{stream}.log'
                 for stream in ('stdout', 'stderr')}
        row.update({stream + 'Path': str(path) for stream, path in paths.items()})
        self.report['commands'].append(row)
        # Popen is deliberately NOT a context manager: on uncertainty neither
        # __exit__, timeout, communicate nor any signal can change the child.
        with paths['stdout'].open('xb') as stdout, paths['stderr'].open('xb') as stderr:
            try:
                process = subprocess.Popen(args, cwd=cwd, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, env=self.command_env)
                self.active_children.append(process)
                code = process.wait()
            except BaseException as error:
                self._unknown(row, error)
                raise
        self.active_children.remove(process)
        row.update(returncode=code, outcomeKnown=True)
        for stream, path in paths.items():
            digest, size = hash_regular(path)
            row.update({stream + 'Bytes': size, stream + 'Sha256': digest})
            self.log_bytes += size
        # ALL returned bytes are already on disk before acceptance is checked.
        accepted_limit = 4096 if preflight else STREAM_LIMIT
        accepted = (all(row[stream + 'Bytes'] <= accepted_limit for stream in paths)
                    and self.log_bytes <= SOURCE_LOG_LIMIT)
        row['withinAcceptanceLimits'] = accepted
        if record_event and self.logs:
            self.event('command_finished', **row)
        require(accepted, 'complete stream/source logs exceed acceptance cap; originals retained',
                sequence=self.sequence, stdoutBytes=row['stdoutBytes'], stderrBytes=row['stderrBytes'])
        require(code == 0, 'command failed; complete output retained; no automatic retry',
                sequence=self.sequence, returncode=code, stdoutPath=row['stdoutPath'], stderrPath=row['stderrPath'])
        return paths['stdout'].read_bytes().decode('utf-8', errors='replace')

    def event(self, event, **values):
        if self.logs:
            body = (json.dumps({'event': event, 'monotonicSeconds': time.monotonic(), **values},
                               sort_keys=True) + '\n').encode()
            # Metadata is bounded before append; never truncate a child stream.
            require(self.log_bytes + len(body) <= SOURCE_LOG_LIMIT, 'metadata exceeds source-log cap')
            with (self.logs / 'lifecycle.jsonl').open('ab') as out:
                out.write(body)
            self.log_bytes += len(body)

    def step_record(self, row):
        body = (json.dumps(row, sort_keys=True) + '\n').encode()
        require(self.ledger_bytes + len(body) <= LEDGER_LIMIT, 'metadata ledger exceeds8MiB')
        with self.records.open('ab') as out:
            out.write(body)
            out.flush()
        self.ledger_bytes += len(body)

    def execute(self):
        require(self.command_env is not None and self.report.get('binaryHashVerified') is True,
                'owned TMPDIR and verified binary required before any product CLI')
        started = time.perf_counter()
        try:
            super().execute()
            self.sample_post_history_space()
        finally:
            self.report['wholeTaskSeconds'] = time.perf_counter() - started

    def cleanup(self):
        # Native has no normal unmount operation. Never delegate to the generic
        # projection/writable cleanup, even if unexpected pins are encountered.
        cleanup = self.report['lifecycle']['cleanup']
        cleanup.update(complete=False, blocked=self.uncertain, harnessProcessesKilled=False,
                       processesKilled=0, forceOrLazyUnmountUsed=False)
        if self.uncertain:
            self.report.update(ok=False, remainingMountsKnown=False, remainingServersKnown=False)
            return
        if not self.root:
            self.report['ok'] = False
            return
        for name, query in (
                ('Mounts', lambda: [m for m in mount_table() if inside(Path(m['mountpoint']), self.root)]),
                ('Servers', self.processes)):
            try:
                value = query()
                self.report['remaining' + name] = value
                self.report['remaining' + name + 'Known'] = True
                if name == 'Servers':
                    self.report['lifecycle']['daemons'] = value
            except BaseException as error:
                self.cleanup_blocked = True
                self.report['remaining' + name + 'Known'] = False
                self.report.setdefault('cleanupErrors', []).append({'inventory': name, 'message': str(error)})
        complete = (not self.cleanup_blocked and all(self.report['remaining' + name + 'Known']
                    and not self.report['remaining' + name] for name in ('Mounts', 'Servers')))
        cleanup.update(complete=complete, blocked=not complete)
        if not complete:
            self.report['ok'] = False

    def _log_paths(self):
        roots = [self.logs] if self.logs else []
        if self.preflight_logs and self.preflight_logs.exists():
            roots.append(self.preflight_logs)
        paths = []
        for root in roots:
            checked_path(root, directory=True)
            device = root.stat().st_dev
            pending = [root]
            while pending:
                parent = pending.pop()
                for path in sorted(parent.iterdir()):
                    info = path.lstat()
                    require(info.st_dev == device and not stat.S_ISLNK(info.st_mode),
                            'log source crosses device or symlink', path=str(path))
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(path)
                    else:
                        regular_info(path)
                        paths.append(path)
        if self.library:
            # Same runtime-log scope as the frozen adapter; no selected tails.
            for pattern in ('*/projection-*.log', '*/writable-*.log'):
                paths.extend((self.library / 'native').glob(pattern))
        if self.records and self.records.exists():
            paths.append(self.records)
        return sorted(set(paths))

    def preserve_logs(self):
        self.report.pop('completeLogArchive', None)
        self.report['partialLogArchive'] = []
        state = {'complete': False, 'completedFiles': 0, 'sourceFilesRetained': True}
        self.report['archiveCopy'] = state
        if self.uncertain or not self.report['lifecycle']['cleanup'].get('complete'):
            state['blockedReason'] = 'unknown child or unconfirmed cleanup; original evidence retained'
            self.report['ok'] = False
            return
        require(self.records is not None, 'external ledger required for complete archive')
        paths = self._log_paths()
        plan = [(path, identity(regular_info(path))) for path in paths]
        planned = sum(info[2] for _, info in plan)
        admission = {'allowanceBytes': self.archive_allowance, 'plannedBytes': planned,
                     'plannedFiles': len(plan), 'admitted': planned <= self.archive_allowance}
        self.report['archiveAdmission'] = admission
        require(admission['admitted'], 'full archive plan exceeds pre-admitted allowance; no copy begun')
        # Validate/hash the entire plan before making even an empty destination.
        prepared = [(path, info, hash_regular(path, info)[0]) for path, info in plan]
        archive = self.records.with_name(self.records.name + '.logs')
        checked_path(archive, new=True)
        archive.mkdir(mode=0o755)
        os.chmod(archive, 0o755)
        state['destination'] = str(archive)
        try:
            for index, (source, expected, expected_hash) in enumerate(prepared):
                require(identity(regular_info(source)) == expected, 'source changed after archive plan')
                target = archive / (f'{index:06}-' + source.name)
                digest = hashlib.sha256()
                with source.open('rb') as inp, target.open('xb') as out:
                    os.fchmod(out.fileno(), 0o644)
                    require(identity(os.fstat(inp.fileno())) == expected, 'source replaced on archive open')
                    remaining = expected[2]
                    while remaining:
                        block = inp.read(min(CHUNK, remaining))
                        require(block, 'source shortened during archive copy')
                        out.write(block)
                        digest.update(block)
                        remaining -= len(block)
                    require(inp.read(1) == b'' and identity(os.fstat(inp.fileno())) == expected,
                            'source mutated during archive copy')
                require(identity(regular_info(source)) == expected and digest.hexdigest() == expected_hash,
                        'source identity/hash changed during archive copy')
                copied_hash, copied_size = hash_regular(target)
                require(copied_hash == expected_hash and copied_size == expected[2], 'archive bytes mismatch')
                self.report['partialLogArchive'].append({'source': str(source), 'archived': str(target),
                    'bytes': copied_size, 'sha256': copied_hash})
                state['completedFiles'] += 1
            require(self._log_paths() == paths, 'source log set changed during archive copy')
            for source, expected, digest in prepared:
                require(hash_regular(source, expected)[0] == digest, 'source changed after archive copy')
            require(state['completedFiles'] == len(plan), 'archive incomplete')
            state.update(complete=True, copiedBytes=planned)
            self.report['completeLogArchive'] = self.report.pop('partialLogArchive')
            # A fully copied oversized failed sample stays failed, not truncated.
            source_bytes = sum(info[2] for path, info in plan if path != self.records)
            require(source_bytes <= SOURCE_LOG_LIMIT and self.records.stat().st_size <= LEDGER_LIMIT,
                    'complete originals archived but source/ledger acceptance cap exceeded')
        except BaseException as error:
            state['error'] = {'type': type(error).__name__, 'message': str(error)}
            self.report['ok'] = False
            raise


def main(argv=None):
    started = time.perf_counter()
    report = production_report()
    sample = LatestCombinedSample(report)
    try:
        parser = Parser(description=__doc__)
        run = parser.add_subparsers(dest='command', required=True, parser_class=Parser).add_parser('run')
        for key in ('root', 'source', 'oracle', 'binary', 'records', 'production-sha', 'binary-sha256'):
            run.add_argument('--' + key, required=True)
        run.add_argument('--backend', choices=['native'], required=True)
        run.add_argument('--case', choices=['identical', 'history-distributed'], required=True)
        run.add_argument('--archive-allowance-bytes', type=int, required=True)
        run.add_argument('--steps')
        sample.prepare(parser.parse_args(argv))
        sample.execute()
    except SystemExit as error:
        if error.code == 0:
            return 0
        report.update(ok=False, error={'type': 'SystemExit', 'message': str(error)})
    except BaseException as error:
        report.update(ok=False, error={'type': type(error).__name__, 'message': str(error),
            'details': getattr(error, 'details', {}), 'traceback': traceback.format_exc()})
    finally:
        for action in (sample.cleanup, sample.preserve_logs):
            try:
                action()
            except BaseException as error:
                report['ok'] = False
                report.setdefault('cleanupErrors', []).append({'operation': action.__name__, 'message': str(error)})
    report['status'] = 'passed' if report['ok'] else 'failed'
    report['wholeSampleIncludingSetupCleanupSeconds'] = time.perf_counter() - started
    body = (json.dumps(report, sort_keys=True) + '\n').encode()
    if len(body) > RAW_LIMIT:
        # Retain a complete failure report, never silently drop command entries.
        report.update(ok=False, status='failed', rawReportAcceptanceExceeded=True)
        body = (json.dumps(report, sort_keys=True) + '\n').encode()
    if sample.root:
        try:
            with (sample.root / 'report.json').open('xb') as out:
                out.write(body)
        except BaseException as error:
            report.update(ok=False, status='failed', reportWriteError=str(error))
            body = (json.dumps(report, sort_keys=True) + '\n').encode()
    sys.stdout.buffer.write(body)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
