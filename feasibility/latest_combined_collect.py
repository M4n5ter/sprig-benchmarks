#!/usr/bin/env python3
"""Bounded evidence-only copy for the four latest-main Native smoke samples.

No runtime/source/image traversal, source chmod/chown, deletion or truncation is
permitted. A failed experiment may have a successful evidence collection; that
never makes the experiment complete. Public helpers also support inert fixtures.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

CAP = 1024**3
COLLECTION_RESERVE = 2 * 1024**2
REPORT_LIMIT = 16 * 1024**2
DRIVER_REPORT_LIMIT = 64 * 1024**2
CHUNK = 1024**2
PRODUCTS = ('sprig-native', 'layerfs')
CASES = ('identical', 'history-distributed')
IDS = tuple(f'{product}-{case}' for product in PRODUCTS for case in CASES)
ORDER = tuple(f'{product}-{case}' for case in CASES for product in PRODUCTS)
DRIVER_SCHEMA = 'sprig-latest-combined-native-smoke-v1'
PINS = {'sprig-native': '4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
        'layerfs': 'ad78914e36b258b360daf13aec164b5655814689'}
SAMPLE_SCHEMAS = {'sprig-native': 'sprig-latest-combined-native-sample-v1',
                  'layerfs': 'sprig-latest-combined-layerfs-sample-v1'}
SETUP_RESULTS = frozenset('''environment.txt script-hashes.txt latest-main-selection.txt
layerfs-source-hashes.txt production-source-hashes.txt projection-rust-version.txt
layerfs-rust-version.txt layerfs-release-build.log production-tests.txt
production-release-build.log layerfs-binary-hashes.txt production-binary-hash.txt
docker-updated.txt runtime-image.json fixture-generation.txt node-npm-versions.txt'''.split())
RESULTS = SETUP_RESULTS | frozenset('''latest-combined-comparison.json
latest-combined-summary.json latest-combined-identity.json latest-combined-fixtures.json
latest-combined-identical-oracle.json latest-combined-history-distributed-oracle.json
latest-combined-history-distributed-steps.json latest-combined-history-distributed-final.json'''.split()) | frozenset(
    f'latest-combined-{row_id}.{suffix}' for row_id in IDS
    for suffix in ('json', 'stdout', 'stderr'))
PENDING_RESULTS = frozenset(f'latest-combined-{row_id}.json.new'
                            for row_id in (*IDS, 'comparison'))
RESULTS |= PENDING_RESULTS
LOG_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:stdout|stderr|log|jsonl)')
DRIVER_LOG_NAME = re.compile(r'[0-9]{6}\.(?:stdout|stderr)')
HEX = re.compile(r'[0-9a-f]{64}')


class CollectionError(ValueError):
    """Collection failed; already copied bytes and collection.json are retained."""


@contextmanager
def closing(fd):
    try:
        yield fd
    finally:
        os.close(fd)


def allowed(group, parts):
    if not isinstance(parts, (tuple, list)) or any(
            not isinstance(part, str) or part in ('', '.', '..') or '/' in part
            or '\\' in part or '\0' in part or len(part) > 255 for part in parts):
        return False
    if group == 'results':
        return len(parts) == 1 and parts[0] in RESULTS
    if group != 'records':
        return False
    if len(parts) == 1:
        return parts[0] in {f'{row_id}.jsonl' for row_id in (*IDS, 'driver')}
    if len(parts) != 2:
        return False
    if parts[0] == 'driver.jsonl.logs':
        return bool(DRIVER_LOG_NAME.fullmatch(parts[1]))
    return (parts[0] in {f'{row_id}.jsonl.logs' for row_id in IDS}
            and bool(LOG_NAME.fullmatch(parts[1])))


def _canonical(value):
    value = os.fspath(value)
    if (not isinstance(value, str) or not value or '\0' in value
            or not os.path.isabs(value) or os.path.normpath(value) != value):
        raise ValueError('canonical absolute path required')
    return Path(value)


def _open_directory(path):
    """Anchor each path component, refusing symlinks even during replacement."""
    path = _canonical(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open('/', flags)
    try:
        for component in path.parts[1:]:
            next_fd = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_uid, info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _regular(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('only independent regular evidence files are allowed')
    return _identity(info)


def _scan(results, temporary):
    """Stat only exact names/depths; never read evidence bodies during admission."""
    results, temporary = _canonical(results), _canonical(temporary)
    with closing(_open_directory(results.parent)), closing(_open_directory(temporary)):
        pass
    rows, directories = [], []

    def visit(root, group, prefix=(), logs=False):
        try:
            fd = _open_directory(root)
        except FileNotFoundError:
            return
        with closing(fd):
            before = _identity(os.fstat(fd))
            directories.append((str(root), before))
            if logs:
                names = sorted(os.listdir(fd))
                if any(not allowed(group, (*prefix, name)) for name in names):
                    raise ValueError('unexpected name inside exact complete-log archive')
            elif group == 'results':
                names = sorted(RESULTS)
            else:
                names = sorted(f'{row_id}.jsonl' for row_id in (*IDS, 'driver'))
            for name in names:
                try:
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    if logs:
                        raise ValueError('archive member disappeared during admission')
                    continue
                expected = _regular(info)
                file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                  dir_fd=fd)
                with closing(file_fd):
                    if _regular(os.fstat(file_fd)) != expected:
                        raise ValueError('evidence changed during admission')
                rows.append({'source': root / name,
                             'path': '/'.join((group, *prefix, name)),
                             'bytes': info.st_size, 'identity': expected})
            if _identity(os.fstat(fd)) != before:
                raise ValueError('evidence directory changed during admission')

    visit(results, 'results')
    records = temporary / 'latest-combined-records'
    visit(records, 'records')
    for row_id in (*IDS, 'driver'):
        name = f'{row_id}.jsonl.logs'
        visit(records / name, 'records', (name,), logs=True)
    return sorted(rows, key=lambda row: row['path']), sorted(directories)


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
            + '\n').encode('utf-8')


def _admit(rows):
    size = sum(row['bytes'] for row in rows)
    if size + COLLECTION_RESERVE > CAP:
        raise ValueError('full planned evidence plus2MiB manifest reserve exceeds1GiB; no subset copied')
    # Ensure a complete file inventory, not a filtered subset, fits the reserve.
    projected = {'sourcePlan': [{'path': row['path'], 'bytes': row['bytes']} for row in rows],
                 'files': [{'path': row['path'], 'bytes': row['bytes'],
                            'sha256': '0' * 64, 'copyComplete': False,
                            'error': 'source changed during copy'} for row in rows]}
    if len(_encoded(projected)) + 65536 > COLLECTION_RESERVE:
        raise ValueError('complete planned collection manifest exceeds reserved capacity')
    return size


def inventory(results, temporary):
    rows, _ = _scan(results, temporary)
    size = _admit(rows)
    return {'schema': 'sprig-latest-combined-evidence-inventory-v1',
            'bytes': size, 'fileCount': len(rows), 'maximumBytes': CAP,
            'collectionReserveBytes': COLLECTION_RESERVE,
            'admissionBytes': size + COLLECTION_RESERVE, 'completeNamedInventory': True}


def _owned_parent(root_fd, parts, uid, gid):
    fd = os.dup(root_fd)
    try:
        for component in parts:
            created = False
            try:
                os.mkdir(component, 0o755, dir_fd=fd)
                created = True
            except FileExistsError:
                pass
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=fd)
            os.close(fd)
            fd = next_fd
            if created:
                os.fchmod(fd, 0o755)
                os.fchown(fd, uid, gid)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _copy_one(planned, destination_fd, uid, gid):
    row = {'path': planned['path'], 'bytes': 0, 'copyComplete': False}
    digest = hashlib.sha256()
    try:
        with closing(_open_directory(planned['source'].parent)) as parent:
            fd = os.open(planned['source'].name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=parent)
            with os.fdopen(fd, 'rb') as source:
                if _regular(os.fstat(source.fileno())) != planned['identity']:
                    raise ValueError('source changed before copy')
                parts = Path(planned['path']).parts
                with closing(_owned_parent(destination_fd, parts[:-1], uid, gid)) as target_parent:
                    target_fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                        | os.O_NOFOLLOW, 0o644, dir_fd=target_parent)
                    with os.fdopen(target_fd, 'wb', buffering=0) as out:
                        os.fchmod(out.fileno(), 0o644)
                        os.fchown(out.fileno(), uid, gid)
                        remaining = planned['bytes']
                        while remaining:
                            block = source.read(min(CHUNK, remaining))
                            if not block:
                                raise ValueError('source shortened during copy')
                            view = memoryview(block)
                            while view:
                                written = out.write(view)
                                if not written:
                                    raise OSError('short destination write')
                                digest.update(view[:written])
                                row['bytes'] += written
                                view = view[written:]
                            remaining -= len(block)
                        if source.read(1) or _regular(os.fstat(source.fileno())) != planned['identity']:
                            raise ValueError('source mutated during copy')
                if _regular(os.stat(planned['source'].name, dir_fd=parent,
                                    follow_symlinks=False)) != planned['identity']:
                    raise ValueError('source replaced after copy')
        row['copyComplete'] = True
    except (OSError, ValueError) as error:
        # Fixed diagnostics cannot smuggle arbitrary huge paths/data into manifest.
        row['error'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    row['sha256'] = digest.hexdigest()
    return row


def _json_report(destination, row):
    if not row.get('copyComplete'):
        raise ValueError('report copy is incomplete')
    limit = (DRIVER_REPORT_LIMIT if row['path'] == 'results/latest-combined-comparison.json'
             else REPORT_LIMIT)
    if row['bytes'] > limit:
        raise ValueError('report exceeds bounded JSON parser limit; full bytes retained')

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('duplicate JSON object key')
            result[key] = value
        return result

    def constant(_):
        raise ValueError('nonfinite JSON constant')

    with closing(_open_directory((destination / row['path']).parent)) as parent:
        fd = os.open(Path(row['path']).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            _regular(info)
            if info.st_size != row['bytes']:
                raise ValueError('copied report size changed')
            body = stream.read(limit + 1)
            if (len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['sha256']
                    or _identity(os.fstat(stream.fileno())) != _identity(info)):
                raise ValueError('copied report changed')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def verify_declared_archives(destination, temporary, copied):
    """Validate all standalone AND embedded declarations against copied hashes.

    Report-provided source paths are metadata only and are NEVER opened. Failed
    samples may have partial archives; their evidence is preserved, not promoted.
    """
    by_path = {row['path']: row for row in copied}
    reports, errors, verified, sample_count = {}, [], set(), 0
    successful, failed = set(), set()

    def fail(path, message):
        row = {'report': path, 'error': message}
        if row not in errors:
            errors.append(row)

    for row in copied:
        if row['path'].startswith('results/') and row['path'].endswith('.json'):
            try:
                reports[row['path']] = _json_report(destination, row)
            except (ValueError, OSError, UnicodeError, RecursionError) as error:
                fail(row['path'], str(error) if not isinstance(error, OSError) else type(error).__name__)

    def verify(sample, row_id, label):
        nonlocal sample_count
        sample_count += 1
        try:
            if not isinstance(sample, dict) or type(sample.get('ok')) is not bool:
                raise ValueError('sample must be an object with boolean ok')
            product, case = next((p, c) for p in PRODUCTS for c in CASES if f'{p}-{c}' == row_id)
            expected = {'schema': SAMPLE_SCHEMAS[product], 'product': product,
                        'backend': 'native' if product == 'sprig-native' else 'fuse',
                        'production_sha': PINS[product], 'testOnly': False}
            if any(sample.get(key) != value or (key == 'testOnly' and sample.get(key) is not False)
                   for key, value in expected.items()):
                raise ValueError('sample schema/product/backend/source identity mismatch')
            if sample.get('case') != case and (sample['ok'] or sample.get('case') is not None):
                raise ValueError('sample case identity mismatch')
            success = sample['ok']
            if not success:
                failed.add(row_id)
            expected_dir = temporary / 'latest-combined-records' / f'{row_id}.jsonl.logs'
            actual = {key for key in by_path if key.startswith(f'records/{row_id}.jsonl.logs/')}
            declared = set()
            complete = sample.get('completeLogArchive')
            if success and (not isinstance(complete, list) or not complete):
                raise ValueError('successful sample lacks nonempty completeLogArchive')
            for field in ('completeLogArchive', 'partialLogArchive'):
                if field not in sample:
                    continue
                archive = sample[field]
                if not isinstance(archive, list):
                    raise ValueError('archive declaration is not an array')
                if success and field == 'partialLogArchive' and archive:
                    raise ValueError('successful sample still declares a partial archive')
                seen = set()
                for entry in archive:
                    required = {'source', 'archived', 'bytes', 'sha256'}
                    permitted_partial = (field == 'partialLogArchive' and isinstance(entry, dict)
                                         and set(entry) == required | {'partial'}
                                         and entry['partial'] is True)
                    if not isinstance(entry, dict) or (set(entry) != required and not permitted_partial):
                        raise ValueError('archive entry must contain source/archived/bytes/sha256')
                    source, archived = entry['source'], entry['archived']
                    if (not isinstance(source, str) or not isinstance(archived, str)
                            or not source or not archived):
                        raise ValueError('archive paths must be nonempty strings')
                    _canonical(source)
                    path = _canonical(archived)
                    if (path.parent != expected_dir
                            or not allowed('records', (expected_dir.name, path.name))):
                        raise ValueError('archive path escapes exact sample allowlist')
                    if (type(entry['bytes']) is not int or entry['bytes'] < 0
                            or not isinstance(entry['sha256'], str) or not HEX.fullmatch(entry['sha256'])):
                        raise ValueError('invalid archive size/hash')
                    key = f'records/{expected_dir.name}/{path.name}'
                    if key in seen:
                        raise ValueError('duplicate archive declaration')
                    seen.add(key)
                    found = by_path.get(key)
                    if (found is None or not found.get('copyComplete') or found['bytes'] != entry['bytes']
                            or found['sha256'] != entry['sha256']):
                        raise ValueError('missing or mismatched declared archive member')
                    verified.add(key)
                if field == 'completeLogArchive':
                    declared = seen
            if success and declared != actual:
                raise ValueError('successful archive has undeclared extra members')
            if success and isinstance(sample.get('archiveCopy'), dict) and sample['archiveCopy'].get('complete') is not True:
                raise ValueError('successful sample reports incomplete archive copy')
            if success:
                successful.add(row_id)
        except (ValueError, TypeError, StopIteration) as error:
            fail(label, str(error))

    for row_id in IDS:
        key = f'results/latest-combined-{row_id}.json'
        if key in reports:
            verify(reports[key], row_id, key)

    driver_key = 'results/latest-combined-comparison.json'
    benchmark_complete = False
    if driver_key in reports:
        driver = reports[driver_key]
        # Inspect every identifiable embedded sample even if another row or the
        # outer envelope is malformed. No earlier error suppresses later claims.
        embedded = driver.get('records') if isinstance(driver, dict) else None
        if isinstance(embedded, list):
            for record in embedded:
                if isinstance(record, dict) and 'sample' in record:
                    if record.get('id') in IDS:
                        verify(record['sample'], record['id'], f"{driver_key}#{record['id']}")
                    else:
                        fail(driver_key, 'embedded sample has no authorized row identity')
        try:
            if (not isinstance(driver, dict) or driver.get('schema') != DRIVER_SCHEMA
                    or type(driver.get('complete')) is not bool):
                raise ValueError('invalid driver schema/complete flag')
            records = driver.get('records')
            if not isinstance(records, list) or len(records) != 4:
                raise ValueError('driver must retain all four predeclared records')
            seen, all_passed = set(), True
            for position, record in enumerate(records):
                if (not isinstance(record, dict) or record.get('id') not in IDS
                        or record['id'] != f"{record.get('product')}-{record.get('case')}"
                        or record['id'] != ORDER[position]
                        or record['id'] in seen or type(record.get('position')) is not int
                        or record['position'] != position or type(record.get('correct')) is not bool
                        or record.get('status') not in ('not_run', 'running', 'passed', 'failed')):
                    raise ValueError('invalid/duplicate driver record identity or state')
                row_id = record['id']
                seen.add(row_id)
                raw = f'results/latest-combined-{row_id}.json'
                passed = record['status'] == 'passed' and record['correct'] is True
                all_passed = all_passed and passed
                if record['status'] == 'passed' and not record['correct']:
                    raise ValueError('passed driver row is not correct')
                if 'rawReportPath' in record and record['rawReportPath'] != raw:
                    raise ValueError('driver raw report path escapes exact row')
                if 'rawReportSha256' in record:
                    actual = by_path.get(raw)
                    if (not isinstance(record['rawReportSha256'], str) or not HEX.fullmatch(record['rawReportSha256'])
                            or actual is None or not actual.get('copyComplete')
                            or actual['sha256'] != record['rawReportSha256']):
                        raise ValueError('driver raw report hash mismatch')
                if 'sample' in record:
                    if raw in reports and record['sample'] != reports[raw]:
                        raise ValueError('embedded sample differs from standalone raw report')
                if passed and ('sample' not in record or not isinstance(record['sample'], dict)
                               or record['sample'].get('ok') is not True or raw not in reports
                               or 'rawReportSha256' not in record):
                    raise ValueError('passed row lacks successful embedded and standalone sample')
                if record['status'] == 'not_run' and ('sample' in record or record['correct']):
                    raise ValueError('not_run row must not claim a sample or correctness')
            if driver['complete'] and (not all_passed or driver.get('status') != 'passed'):
                raise ValueError('driver claims complete despite failed/no-run records')
            benchmark_complete = driver['complete'] and all_passed and driver.get('status') == 'passed'
        except (ValueError, TypeError) as error:
            fail(driver_key, str(error))
    pending = sorted(key for key in by_path if key.removeprefix('results/') in PENDING_RESULTS)
    return {'ok': not errors, 'sampleDeclarations': sample_count,
            'verifiedUniqueFiles': len(verified), 'successfulSampleIds': sorted(successful),
            'failedSampleIds': sorted(failed), 'pendingReportWrites': pending,
            'benchmarkComplete': benchmark_complete and not errors and not pending,
            'errors': errors}


def collect(results, temporary, destination, uid, gid):
    results, temporary, destination = map(_canonical, (results, temporary, destination))
    if type(uid) is not int or type(gid) is not int or uid < 0 or gid < 0:
        raise ValueError('nonnegative owned-copy uid/gid required')
    if (destination.is_relative_to(results) or destination.is_relative_to(temporary)
            or destination.exists() or destination.is_symlink()):
        raise ValueError('new standalone artifact destination required')
    with closing(_open_directory(destination.parent)):
        pass
    planned, directories = _scan(results, temporary)
    size = _admit(planned)  # Whole plan admission precedes even destination mkdir.
    with closing(_open_directory(destination.parent)) as parent:
        os.mkdir(destination.name, 0o755, dir_fd=parent)
        fd = os.open(destination.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    with closing(fd):
        os.fchmod(fd, 0o755)
        os.fchown(fd, uid, gid)
        copied = [_copy_one(row, fd, uid, gid) for row in planned]
        errors = []
        if not all(row['copyComplete'] for row in copied):
            errors.append('one or more source copies failed; partial owned copies retained')
        try:
            after, after_directories = _scan(results, temporary)
            if after != planned or after_directories != directories:
                errors.append('source identities or complete named inventory changed during collection')
        except (OSError, ValueError):
            errors.append('cannot revalidate complete source inventory after copying')
        coverage = verify_declared_archives(destination, temporary, copied)
        if not coverage['ok']:
            errors.append('declared archive/report verification failed')
        manifest = {'schema': 'sprig-latest-combined-evidence-copy-v1',
                    'evidenceOk': not errors, 'status': 'collected' if not errors else 'failed',
                    'benchmarkComplete': not errors and coverage['benchmarkComplete'],
                    'copyComplete': all(row['copyComplete'] for row in copied) and not any(
                        'inventory' in error for error in errors),
                    'sourcePlan': [{'path': row['path'], 'bytes': row['bytes']} for row in planned],
                    'files': copied, 'plannedSourceBytes': size,
                    'copiedBytes': sum(row['bytes'] for row in copied),
                    'maximumBytes': CAP, 'collectionReserveBytes': COLLECTION_RESERVE,
                    'allSourceFilesRetained': True, 'declaredArchiveVerification': coverage,
                    'errors': errors}
        body = _encoded(manifest)
        if len(body) > COLLECTION_RESERVE or manifest['copiedBytes'] + len(body) > CAP:
            raise CollectionError('collection manifest exceeds explicit artifact bound; all sources/copies retained')
        manifest_fd = os.open('collection.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL
                              | os.O_NOFOLLOW, 0o644, dir_fd=fd)
        with os.fdopen(manifest_fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o644)
            os.fchown(stream.fileno(), uid, gid)
            stream.write(body)
    if not manifest['evidenceOk']:
        raise CollectionError('evidence collection failed; copied files and collection.json retained')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('inventory', 'collect'))
    for name in ('results', 'temporary'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--destination')
    parser.add_argument('--uid', type=int)
    parser.add_argument('--gid', type=int)
    args = parser.parse_args(argv)
    try:
        results, temporary = _canonical(args.results), _canonical(args.temporary)
        if args.command == 'inventory':
            print(json.dumps(inventory(results, temporary)))
            return 0
        if (os.geteuid() != 0 or os.environ.get('GITHUB_ACTIONS') != 'true'
                or args.uid is None or args.uid <= 0 or args.gid is None or args.gid < 0
                or args.destination is None or results != Path.cwd() / 'results'
                or str(temporary) != os.environ.get('RUNNER_TEMP')):
            raise ValueError('authorized CI root copy from current results and canonical RUNNER_TEMP required')
        manifest = collect(results, temporary, _canonical(args.destination), args.uid, args.gid)
        print(json.dumps({'evidenceOk': True, 'benchmarkComplete': manifest['benchmarkComplete'],
                          'fileCount': len(manifest['files']), 'bytes': manifest['copiedBytes']}))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({'evidenceOk': False, 'benchmarkComplete': False,
                          'error': str(error), 'allSourceFilesRetained': True}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
