#!/usr/bin/env python3
"""Exact, fail-closed validation of complete writable-v2 diagnostic evidence.

These functions do not read files, run a workload, or infer request ownership.
The caller must establish regular-file/full-log transport, exact source/ELF and
pressure-generation identity, successful normal cleanup, and clock-proof binding.
Call validate_clock_proof before analyze_trace. Never pass stderr previews here.
"""
from bisect import bisect_right
import json
import re

from stress_cargo_pressure_long import validate_report


SCHEMA = 'sprig-writable-diagnostics-v2'
CLOCK_PROOF_SCHEMA = 'sprig-writable-clock-proof-v1'
CAPACITY = 65536
MAX_LOG_BYTES = 16 * 1024**2
U64_MAX = 2**64 - 1
OPERATIONS = ('directory_attr', 'journal_sync')
TOTAL_KEYS = frozenset(('calls', 'nanoseconds', 'maximum_nanoseconds',
                        'scanned_nodes', 'repeated_successful_syncs',
                        'repeated_successful_sync_nanoseconds'))
EVENT_KEYS = frozenset(('operation', 'started_ns', 'finished_ns', 'sequence',
                        'scanned_nodes', 'success', 'repeats_successful_sync', 'cpu_ns'))
TRACE_KEYS = frozenset(('schema', 'clock', 'capacity', 'overwritten_events',
                        'clock_failures', 'cpu_clock', 'cpu_clock_failures',
                        'cpu_resolution_ns', 'directory_attr', 'journal_sync', 'events'))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _keys(value, keys, name):
    _require(type(value) is dict and set(value) == set(keys), name + ' fields mismatch')


def _uint(value, name, positive=False, counter=False):
    _require(type(value) is int and (1 if positive else 0) <= value <= U64_MAX,
             name + ' must be an exact u64 integer')
    if counter:
        _require(value != U64_MAX, name + ' is saturated')
    return value


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def _no_constant(value):
    raise ValueError('nonfinite JSON constant: ' + value)


def _offsets(raw):
    _require(type(raw) is str and len(raw) <= 4096, 'invalid time-namespace offsets')
    result = {}
    for line in raw.splitlines():
        parts = line.split()
        _require(len(parts) == 3 and parts[0] in ('monotonic', 'boottime'),
                 'invalid time-namespace offset row')
        name, seconds, nanos = parts
        _require(name not in result and re.fullmatch(r'-?(0|[1-9][0-9]*)', seconds)
                 is not None and re.fullmatch(r'0|[1-9][0-9]*', nanos) is not None,
                 'invalid or duplicate time-namespace offset')
        seconds, nanos = int(seconds), int(nanos)
        _require(-(2**63) <= seconds < 2**63 and 0 <= nanos < 10**9,
                 'time-namespace offset outside timespec bounds')
        result[name] = (seconds, nanos)
    _require(set(result) == {'monotonic', 'boottime'}, 'incomplete time-namespace offsets')
    return result


def validate_clock_proof(proof):
    """Validate bound host/container namespace evidence and exact clock sandwich.

    The two side objects contain timeNamespace, timeForChildrenNamespace,
    timensOffsets (raw proc text), monotonicResolutionNs and cpuResolutionNs.
    Absolute endpoints must be Python integers, not numeric strings or floats.
    Collection provenance and attachment to the pressure container are caller gates.
    """
    _keys(proof, ('schema', 'clock', 'hostBeforeNs', 'containerMonotonicNs',
                  'hostAfterNs', 'host', 'container'), 'clock proof')
    _require(proof['schema'] == CLOCK_PROOF_SCHEMA and proof['clock'] == 'CLOCK_MONOTONIC',
             'clock proof schema/domain mismatch')
    for key in ('hostBeforeNs', 'containerMonotonicNs', 'hostAfterNs'):
        _uint(proof[key], key)
    _require(proof['hostBeforeNs'] <= proof['containerMonotonicNs'] <= proof['hostAfterNs'],
             'container clock is outside host sandwich')
    side_keys = ('timeNamespace', 'timeForChildrenNamespace', 'timensOffsets',
                 'monotonicResolutionNs', 'cpuResolutionNs')
    identities, offsets = [], []
    for name in ('host', 'container'):
        side = proof[name]
        _keys(side, side_keys, name + ' clock evidence')
        for key in ('timeNamespace', 'timeForChildrenNamespace'):
            identity = side[key]
            _require(type(identity) is str and re.fullmatch(r'time:\[[1-9][0-9]*\]', identity)
                     is not None, 'invalid time-namespace identity')
            identities.append(identity)
        offsets.append(_offsets(side['timensOffsets']))
        for key in ('monotonicResolutionNs', 'cpuResolutionNs'):
            _uint(side[key], name + '.' + key, positive=True)
    _require(len(set(identities)) == 1, 'host/container time namespaces differ')
    _require(offsets[0] == offsets[1], 'host/container time-namespace offsets differ')
    return proof


def _diagnostic_object(value):
    if type(value) is dict:
        schema = value.get('schema')
        return ((type(schema) is str and schema.startswith('sprig-writable-diagnostics'))
                or bool(set(value) & {'cpu_clock', 'cpu_clock_failures',
                                      'directory_attr', 'journal_sync', 'overwritten_events'}))
    return False


def parse_trace_log(raw, enabled):
    """Parse the full <=16 MiB stderr bytes, with one final newline-terminated footer.

    Ordinary stderr may precede the footer, but diagnostic-looking ordinary text,
    partial records, non-object records, duplicate records and trailing output are
    not substitutes for a complete footer. Disabled logs must contain none.
    """
    _require(type(raw) is bytes, 'full raw log must be bytes')
    _require(type(enabled) is bool, 'enabled identity must be boolean')
    _require(len(raw) <= MAX_LOG_BYTES, 'complete log exceeds 16 MiB')
    lines = raw.splitlines(keepends=True)
    found = []
    markers = (b'sprig-writable-diagnostics', b'"cpu_clock"', b'"cpu_clock_failures"',
               b'"directory_attr"', b'"journal_sync"', b'"overwritten_events"')
    for index, line in enumerate(lines):
        suspicious = any(marker in line for marker in markers)
        # Discovery is deliberately permissive; every potential footer is then
        # decoded again with strict duplicate/nonfinite rejection. This also
        # discovers valid JSON whose schema/keys use JSON Unicode escapes.
        discovered = None
        nested_diagnostic = False
        def discover_pairs(pairs):
            nonlocal nested_diagnostic
            # Inspect every pair before dict construction: an escaped schema
            # followed by a duplicate ordinary schema must not hide a record.
            nested_diagnostic |= any(_diagnostic_object({key: value}) for key, value in pairs)
            return dict(pairs)
        if line.lstrip().startswith((b'{', b'[')):
            try:
                discovered = json.loads(line, object_pairs_hook=discover_pairs)
            except (ValueError, UnicodeError, RecursionError):
                pass
        if not suspicious and not nested_diagnostic and not _diagnostic_object(discovered):
            continue
        _require(enabled, 'disabled sample contains diagnostic-looking output')
        _require(index == len(lines) - 1 and line.endswith(b'\n'),
                 'diagnostic footer must be final and newline-terminated')
        try:
            record = json.loads(line, object_pairs_hook=_no_duplicates,
                                parse_constant=_no_constant)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise ValueError('malformed diagnostic footer: ' + str(error)) from error
        _require(type(record) is dict, 'diagnostic footer must be one JSON object')
        found.append(record)
    if not enabled:
        return None
    _require(len(found) == 1, 'exactly one complete diagnostic footer required')
    return _validate_trace(found[0])


def _empty_totals():
    return dict.fromkeys(TOTAL_KEYS, 0)


def _add_event(totals, event):
    duration = event['finished_ns'] - event['started_ns']
    totals['calls'] += 1
    totals['nanoseconds'] += duration
    totals['maximum_nanoseconds'] = max(totals['maximum_nanoseconds'], duration)
    totals['scanned_nodes'] += event['scanned_nodes']
    if event['repeats_successful_sync'] and event['success']:
        totals['repeated_successful_syncs'] += 1
        totals['repeated_successful_sync_nanoseconds'] += duration


def _validate_totals(totals, retained, operation):
    _keys(totals, TOTAL_KEYS, operation + ' totals')
    for key in TOTAL_KEYS:
        _uint(totals[key], operation + '.' + key, counter=True)
        _require(totals[key] >= retained[key], 'retained events exceed ' + operation + '.' + key)
    calls, nanos, maximum = (totals[k] for k in ('calls', 'nanoseconds', 'maximum_nanoseconds'))
    repeats, repeat_ns = (totals[k] for k in ('repeated_successful_syncs',
                                           'repeated_successful_sync_nanoseconds'))
    _require(maximum <= nanos <= calls * maximum, 'inconsistent duration totals')
    _require(repeats <= calls and repeat_ns <= min(nanos, repeats * maximum),
             'inconsistent repeated-sync totals')
    if calls == 0:
        _require(not any(totals.values()), 'zero-call totals must be zero')
    if operation == 'directory_attr':
        _require(repeats == repeat_ns == 0, 'directory scans cannot be repeated syncs')
    else:
        _require(totals['scanned_nodes'] == 0, 'sync cannot scan nodes')
        _require(calls == 0 or repeats < calls,
                 'first-ever journal sync cannot repeat a preceding successful sync')
    missing = calls - retained['calls']
    if missing == 0:
        _require(totals == retained, 'complete retained scope must equal lifetime totals')
    else:
        missing_ns = nanos - retained['nanoseconds']
        missing_repeats = repeats - retained['repeated_successful_syncs']
        missing_repeat_ns = repeat_ns - retained['repeated_successful_sync_nanoseconds']
        _require(missing_ns <= missing * maximum and missing_repeats <= missing
                 and missing_repeat_ns <= min(missing_ns, missing_repeats * maximum),
                 'overwritten totals are inconsistent with missing scope counts')
        if maximum > retained['maximum_nanoseconds']:
            _require(missing_ns >= maximum, 'unretained maximum exceeds missing duration')


def _validate_trace(trace):
    _keys(trace, TRACE_KEYS, 'diagnostic footer')
    _require(trace['schema'] == SCHEMA and trace['clock'] == 'CLOCK_MONOTONIC'
             and trace['cpu_clock'] == 'CLOCK_THREAD_CPUTIME_ID', 'diagnostic schema/clock mismatch')
    _uint(trace['capacity'], 'capacity')
    _require(trace['capacity'] == CAPACITY, 'diagnostic ring capacity mismatch')
    for key in ('overwritten_events', 'clock_failures', 'cpu_clock_failures'):
        _uint(trace[key], key, counter=True)
    _require(trace['clock_failures'] == 0, 'wall clock failure disqualifies coverage')
    _require(trace['cpu_clock_failures'] == 0, 'CPU clock failure disqualifies analysis')
    _uint(trace['cpu_resolution_ns'], 'cpu_resolution_ns', positive=True)
    events = trace['events']
    _require(type(events) is list and len(events) <= CAPACITY, 'invalid retained event list')
    retained = {operation: _empty_totals() for operation in OPERATIONS}
    previous_end = previous_sequence = None
    previous_sync_known = trace['overwritten_events'] == 0
    last_successful_sync = None
    first_retained_sync = None
    for event in events:
        _keys(event, EVENT_KEYS, 'event')
        operation = event['operation']
        _require(type(operation) is str and operation in OPERATIONS, 'unknown scope operation')
        for key in ('started_ns', 'finished_ns', 'sequence', 'scanned_nodes', 'cpu_ns'):
            _uint(event[key], 'event.' + key)
        for key in ('success', 'repeats_successful_sync'):
            _require(type(event[key]) is bool, 'event.' + key + ' must be boolean')
        start, end, sequence = (event[k] for k in ('started_ns', 'finished_ns', 'sequence'))
        _require(start <= end, 'backwards wall interval')
        _require(previous_end is None or previous_end <= start, 'unordered or overlapping events')
        _require(previous_sequence is None or previous_sequence <= sequence, 'decreasing sequence')
        previous_end, previous_sequence = end, sequence
        if operation == 'directory_attr':
            _require(event['success'] and not event['repeats_successful_sync'],
                     'directory scan success/repeat flags invalid')
        else:
            _require(event['scanned_nodes'] == 0, 'journal sync cannot scan nodes')
            if first_retained_sync is None:
                first_retained_sync = event
            if previous_sync_known:
                _require(event['repeats_successful_sync'] == (last_successful_sync == sequence),
                         'repeated-successful-sync flag inconsistent with preceding sync')
            previous_sync_known = True
            last_successful_sync = sequence if event['success'] else None
        _add_event(retained[operation], event)
    for operation in OPERATIONS:
        _validate_totals(trace[operation], retained[operation], operation)
    if (first_retained_sync is not None
            and trace['journal_sync']['calls'] == retained['journal_sync']['calls']):
        _require(not first_retained_sync['repeats_successful_sync'],
                 'first-ever retained sync cannot repeat when no sync was overwritten')
    calls = sum(trace[operation]['calls'] for operation in OPERATIONS)
    _uint(calls, 'combined calls', counter=True)
    _require(len(events) == min(calls, CAPACITY), 'retained count must equal min(calls,65536)')
    _require(trace['overwritten_events'] == calls - len(events), 'overwritten count mismatch')
    return trace


class _Union:
    """Exact integer prefix integrals; per-wrapper lookup is O(log events)."""

    def __init__(self, intervals):
        merged = []
        for start, end in sorted(intervals):
            if start >= end:
                continue
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        self.starts = [start for start, _ in merged]
        self.ends = [end for _, end in merged]
        self.prefix = [0]
        for start, end in merged:
            self.prefix.append(self.prefix[-1] + end - start)

    def _before(self, point):
        index = bisect_right(self.ends, point)
        result = self.prefix[index]
        if index < len(self.starts):
            result += max(0, point - self.starts[index])
        return result

    def overlap(self, start, end):
        return self._before(end) - self._before(start)


def _quantile(sorted_values, numerator, denominator=100):
    return sorted_values[(len(sorted_values) * numerator + denominator - 1) // denominator - 1]


def _distribution(values):
    values = sorted(values)
    if not values:
        return {'count': 0, 'sumNs': 0, 'minNs': None, 'p50Ns': None,
                'p95Ns': None, 'p99Ns': None, 'maxNs': None}
    return {'count': len(values), 'sumNs': sum(values), 'minNs': values[0],
            'p50Ns': _quantile(values, 50), 'p95Ns': _quantile(values, 95),
            'p99Ns': _quantile(values, 99), 'maxNs': values[-1]}


def _anomalies(events):
    anomalous = [event for event in events
                 if event['cpu_ns'] > event['finished_ns'] - event['started_ns']]
    excess = [event['cpu_ns'] - (event['finished_ns'] - event['started_ns'])
              for event in anomalous]
    return {'count': len(anomalous), 'excessSumNs': sum(excess),
            'maximumExcessNs': max(excess, default=0),
            'zeroWallPositiveCpuCount': sum(event['started_ns'] == event['finished_ns']
                                           for event in anomalous)}


def _occupancy(unions, start, end):
    scan = unions['directory_attr'].overlap(start, end)
    sync = unions['journal_sync'].overlap(start, end)
    either = unions['either'].overlap(start, end)
    both = scan + sync - either
    return {'scanOnlyNs': scan - both, 'syncOnlyNs': sync - both,
            'bothNs': both, 'neitherNs': end - start - either,
            'scanUnionNs': scan, 'syncUnionNs': sync, 'eitherUnionNs': either}


def _wrapper_aggregate(rows, unions):
    totals = dict.fromkeys(('scanOnlyNs', 'syncOnlyNs', 'bothNs', 'neitherNs',
                           'scanUnionNs', 'syncUnionNs', 'eitherUnionNs'), 0)
    scan_count = sync_count = neither_count = 0
    for row in rows:
        overlap = _occupancy(unions, row['start'], row['end'])
        for key in totals:
            totals[key] += overlap[key]
        scan_count += overlap['scanUnionNs'] > 0
        sync_count += overlap['syncUnionNs'] > 0
        neither_count += overlap['eitherUnionNs'] == 0
    return {'count': len(rows), 'wrapperWall': _distribution([row['end'] - row['start'] for row in rows]),
            'summedWrapperOverlapNs': totals, 'withScanOverlapCount': scan_count,
            'withSyncOverlapCount': sync_count, 'withNoMeasuredOverlapCount': neither_count}


def analyze_trace(trace, pressure_report):
    """Return compact descriptive metadata; no event arrays or CPU proration.

    A valid result is conditional on separately validated/bound clock proof and
    source/log/pressure-generation/normal-destroy evidence. Lifetime ring totals
    are not substituted for complete pressure-window coverage.
    """
    _validate_trace(trace)
    validate_report(pressure_report)
    origin = int(pressure_report['monotonicOriginNs'])
    wrappers = []
    for worker in pressure_report['workers']:
        for key in ('startedNs', 'finishedNs'):
            _uint(origin + worker[key], 'absolute worker ' + key)
        for event in worker['operationIntervals']:
            start, end = origin + event['startNs'], origin + event['endNs']
            _uint(start, 'absolute wrapper start')
            _uint(end, 'absolute wrapper end')
            wrappers.append({'start': start, 'end': end, 'worker': worker['worker'],
                             'operation': event['operation']})
    start, end = min(row['start'] for row in wrappers), max(row['end'] for row in wrappers)
    _require(start < end, 'nonempty complete pressure window required')
    events = trace['events']
    _require(bool(events) and events[0]['started_ns'] <= start,
             'first retained event does not cover first pressure wrapper')
    _require(all(event['success'] for event in events if event['operation'] == 'journal_sync'),
             'failed journal sync disqualifies ordinary successful-canary analysis')
    final = events[-1]
    _require(final['operation'] == 'journal_sync' and final['success']
             and final['started_ns'] >= end and final['finished_ns'] >= end,
             'final normal-destroy successful sync must start after the last pressure wrapper')
    unions = {operation: _Union((event['started_ns'], event['finished_ns'])
                                for event in events if event['operation'] == operation)
              for operation in OPERATIONS}
    unions['either'] = _Union((event['started_ns'], event['finished_ns']) for event in events)
    scopes = {}
    for operation in OPERATIONS:
        selected = [event for event in events if event['operation'] == operation]
        contained = [event for event in selected if start <= event['started_ns']
                     <= event['finished_ns'] <= end]
        boundary = [event for event in selected if event['started_ns'] < end
                    and event['finished_ns'] > start and not
                    (start <= event['started_ns'] <= event['finished_ns'] <= end)]
        scopes[operation] = {'fullyContainedCount': len(contained),
                             'boundaryCrossingCount': len(boundary),
                             'fullyContainedWall': _distribution([event['finished_ns'] - event['started_ns']
                                                                  for event in contained]),
                             'fullyContainedCpu': _distribution([event['cpu_ns'] for event in contained]),
                             'fullyContainedCpuExceedsWall': _anomalies(contained)}
    repeats = [event for event in events if event['operation'] == 'journal_sync'
               and event['success'] and event['repeats_successful_sync']]
    contained_repeats = [event for event in repeats if start <= event['started_ns']
                         <= event['finished_ns'] <= end]
    boundary_repeats = [event for event in repeats if event['started_ns'] < end
                        and event['finished_ns'] > start and not
                        (start <= event['started_ns'] <= event['finished_ns'] <= end)]
    by_operation = {}
    for operation in sorted({row['operation'] for row in wrappers}):
        rows = [row for row in wrappers if row['operation'] == operation]
        durations = sorted(row['end'] - row['start'] for row in rows)
        summary = _wrapper_aggregate(rows, unions)
        summary['tails'] = {}
        for percentile in (95, 99):
            threshold = _quantile(durations, percentile)
            tail = [row for row in rows if row['end'] - row['start'] >= threshold]
            summary['tails']['p' + str(percentile)] = {
                'thresholdNs': threshold, 'tiesIncluded': True,
                **_wrapper_aggregate(tail, unions)}
        by_operation[operation] = summary
    return {'schema': 'sprig-writable-pressure-analysis-v1',
            'traceSchema': SCHEMA, 'clock': 'CLOCK_MONOTONIC',
            'pressureWindow': {'startedNs': start, 'finishedNs': end, 'wallNs': end - start,
                               'wrapperCount': len(wrappers), 'coverageComplete': True},
            'retainedEvents': len(events), 'overwrittenEvents': trace['overwritten_events'],
            'lifetimeScopeTotals': {operation: dict(trace[operation]) for operation in OPERATIONS},
            'cpuResolutionNs': trace['cpu_resolution_ns'],
            'retainedCpuExceedsWall': _anomalies(events),
            'wholePressureUnionWall': _occupancy(unions, start, end),
            'pressureScopes': scopes,
            'sameSequenceSuccessfulSyncs': {
                'fullyContainedCount': len(contained_repeats),
                'boundaryCrossingCount': len(boundary_repeats),
                'pressureClippedUnionWallNs': _Union((event['started_ns'], event['finished_ns'])
                                                    for event in repeats).overlap(start, end),
                'fullyContainedWall': _distribution([event['finished_ns'] - event['started_ns']
                                                     for event in contained_repeats]),
                'fullyContainedCpu': _distribution([event['cpu_ns'] for event in contained_repeats])},
            'wrapperOverlaps': {'all': _wrapper_aggregate(wrappers, unions),
                                'byOperation': by_operation,
                                'byWorker': {str(worker): _wrapper_aggregate(
                                    [row for row in wrappers if row['worker'] == worker], unions)
                                             for worker in (0, 1)}},
            'interpretation': {
                'quantiles': 'nearest rank; tail threshold ties included; dependent operations',
                'cpu': 'only fully contained scope deltas; no clipped CPU proration; nominal resolution is not precision',
                'wall': 'wholePressureUnionWall counts server union once; wrapper overlap sums may count the same server time in both workers',
                'causality': 'descriptive temporal overlap only; no request ownership, causal attribution, or storage-wait identification',
                'unmeasured': 'neither includes unmeasured server work, queues, scheduling and wrapper work',
                'provenance': 'conditional on caller-validated bound clock proof, complete raw log, pressure generation and normal cleanup'}}
