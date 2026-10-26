"""Synthetic exact-integer/clock/coverage/transport tests; never run a workload."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

import stress_cargo_pressure_long as long
import stress_writable_diagnostic_trace as diagnostic


ORIGIN = 17000000001234567890
HELPER_SHA256 = '58e5171ba44661a00065297155025a0c75839892cb5c21c770d22e84f4e0b501'


def pressure_report(origin=ORIGIN):
    rows = []
    for worker in (0, 1):
        samples = {name: [] for name in ('rename', 'write', 'read', 'metadata')}
        intervals = []
        for ordinal in range(5 * long.SPEC['iterationsPerWorker']):
            operation = long.EVENT_ORDER[ordinal % 5]
            start = 10 + worker + ordinal * 4
            intervals.append({'iteration': ordinal // 5, 'operation': operation,
                              'startNs': start, 'endNs': start + 2, 'durationNs': 2})
            samples['rename' if operation.startswith('rename-') else operation].append(2)
        rows.append({'worker': worker, 'startedNs': worker, 'finishedNs': 20500 + worker,
                     'completedIterations': 1024, 'samplesNanoseconds': samples,
                     'operationIntervals': intervals})
    return {'schema': long.SCHEMA, 'profile': long.SPEC['profile'], 'spec': dict(long.SPEC),
            'ok': True, 'allWitnessesVerified': True, 'clock': 'CLOCK_MONOTONIC',
            'monotonicOriginNs': str(origin), 'workers': rows,
            'workerLifetimeOverlapNs': 20499}


def event(operation='directory_attr', start=ORIGIN, end=ORIGIN + 2,
          sequence=10, cpu=1, success=True, repeat=False, scanned=4):
    return {'operation': operation, 'started_ns': start, 'finished_ns': end,
            'sequence': sequence, 'scanned_nodes': scanned if operation == 'directory_attr' else 0,
            'success': success, 'repeats_successful_sync': repeat, 'cpu_ns': cpu}


def trace_from(events, overwritten=None):
    totals = {}
    for operation in diagnostic.OPERATIONS:
        chosen = [item for item in events if item['operation'] == operation]
        repeats = [item for item in chosen if item['success'] and item['repeats_successful_sync']]
        durations = [item['finished_ns'] - item['started_ns'] for item in chosen]
        totals[operation] = {
            'calls': len(chosen), 'nanoseconds': sum(durations),
            'maximum_nanoseconds': max(durations, default=0),
            'scanned_nodes': sum(item['scanned_nodes'] for item in chosen),
            'repeated_successful_syncs': len(repeats),
            'repeated_successful_sync_nanoseconds': sum(item['finished_ns'] - item['started_ns']
                                                       for item in repeats)}
    kept = events[-diagnostic.CAPACITY:]
    return {'schema': diagnostic.SCHEMA, 'clock': 'CLOCK_MONOTONIC',
            'capacity': diagnostic.CAPACITY,
            'overwritten_events': len(events) - len(kept) if overwritten is None else overwritten,
            'clock_failures': 0, 'cpu_clock': 'CLOCK_THREAD_CPUTIME_ID',
            'cpu_clock_failures': 0, 'cpu_resolution_ns': 1,
            **totals, 'events': kept}


def sample_trace():
    # Pressure window is [ORIGIN+10, ORIGIN+20489]. Scopes cross both
    # boundaries; their CPU must not be prorated into the window.
    return trace_from([
        event(start=ORIGIN + 5, end=ORIGIN + 11, cpu=600),
        event('journal_sync', ORIGIN + 12, ORIGIN + 14, cpu=1),
        event('journal_sync', ORIGIN + 15, ORIGIN + 18, cpu=5, repeat=True),
        event(start=ORIGIN + 20, end=ORIGIN + 23, cpu=0),
        event('journal_sync', ORIGIN + 20488, ORIGIN + 20500, cpu=1200, repeat=True),
        event('journal_sync', ORIGIN + 20501, ORIGIN + 20503, cpu=1, repeat=True)])


def raw_log(trace):
    return json.dumps(trace, separators=(',', ':'), allow_nan=False).encode() + b'\n'


def clock_proof():
    side = {'timeNamespace': 'time:[4026531834]',
            'timeForChildrenNamespace': 'time:[4026531834]',
            'timensOffsets': 'monotonic           0         0\nboottime            0         0\n',
            'monotonicResolutionNs': 1, 'cpuResolutionNs': 1}
    return {'schema': diagnostic.CLOCK_PROOF_SCHEMA, 'clock': 'CLOCK_MONOTONIC',
            'hostBeforeNs': ORIGIN - 1, 'containerMonotonicNs': ORIGIN,
            'hostAfterNs': ORIGIN + 1, 'host': side, 'container': copy.deepcopy(side)}


class DiagnosticTraceTests(unittest.TestCase):
    def parse(self, trace):
        return diagnostic.parse_trace_log(raw_log(trace), True)

    def test_frozen_helper_identity_and_exact_above_2_to_53_round_trip(self):
        self.assertEqual(hashlib.sha256(Path(long.__file__).read_bytes()).hexdigest(), HELPER_SHA256)
        trace = sample_trace()
        parsed = diagnostic.parse_trace_log(b'ordinary stderr\n{"message":"ready"}\n' + raw_log(trace), True)
        self.assertEqual(parsed, trace)
        self.assertIs(type(parsed['events'][0]['started_ns']), int)
        self.assertEqual(parsed['events'][0]['started_ns'], ORIGIN + 5)
        self.assertGreater(parsed['events'][0]['started_ns'], 2**53)
        self.assertEqual(diagnostic.analyze_trace(parsed, pressure_report())['pressureWindow']['startedNs'], ORIGIN + 10)

    def test_off_on_identity_and_footer_not_ordinary_stderr(self):
        encoded = raw_log(sample_trace())
        self.assertIsNone(diagnostic.parse_trace_log(b'', False))
        self.assertIsNone(diagnostic.parse_trace_log(b'ordinary stderr without newline', False))
        self.assertIsNone(diagnostic.parse_trace_log(b'{"message":"ready"}\n', False))
        invalid = (b'', b'ordinary stderr\n', encoded[:-1], encoded[:-2] + b'\n',
                   encoded + b'ordinary stderr\n', encoded + encoded,
                   b'ordinary mentions sprig-writable-diagnostics-v2\n' + encoded,
                   b'[' + encoded.rstrip() + b']\n', b'prefix ' + encoded)
        for raw in invalid:
            with self.subTest(raw=raw[:90]), self.assertRaises(ValueError):
                diagnostic.parse_trace_log(raw, True)
        for raw in (encoded, encoded[:-1], encoded[:-30],
                    b'ordinary mentions sprig-writable-diagnostics-v2\n',
                    encoded.replace(b'sprig-writable', b'sprig\\u002dwritable'),
                    encoded.replace(b'"schema"', b'"schem\\u0061"'),
                    b'{"schema":"sprig\\u002dwritable\\u002ddiagnostics\\u002dv2","schema":"ordinary"}\n',
                    b'[{"schema":"sprig\\u002dwritable\\u002ddiagnostics\\u002dv2"}]\n'):
            with self.subTest(raw=raw[:90]), self.assertRaises(ValueError):
                diagnostic.parse_trace_log(raw, False)
        for enabled in (0, 1, None, '1'):
            with self.assertRaises(ValueError):
                diagnostic.parse_trace_log(encoded, enabled)
        for raw in (encoded.decode(), bytearray(encoded), None):
            with self.assertRaises(ValueError):
                diagnostic.parse_trace_log(raw, True)

    def test_duplicate_keys_nonfinite_bad_json_and_exact_schema(self):
        encoded = raw_log(sample_trace())
        malformed = (
            encoded.replace(b'"capacity":65536', b'"capacity":65536,"capacity":65536'),
            encoded.replace(b'"cpu_ns":1', b'"cpu_ns":1,"cpu_ns":1', 1),
            encoded.replace(b'"cpu_ns":1', b'"cpu_ns":NaN', 1),
            encoded.replace(b'"cpu_ns":1', b'"cpu_ns":Infinity', 1),
            encoded.replace(b'"cpu_ns":1', b'"cpu_ns":-Infinity', 1),
            encoded.replace(b'"cpu_ns":1', b'"cpu_ns":1.0', 1),
            encoded.replace(b'"cpu_ns":1', b'"cpu_ns":1e0', 1),
            encoded.replace(b'"cpu_ns":1', b'"cpu_ns":01', 1),
            encoded.replace(b'"cpu_ns":1', b'"cpu_ns":\xff', 1),
            encoded + b'{}\n', encoded.rstrip() + b' {}\n')
        for raw in malformed:
            with self.subTest(raw=raw[:90]), self.assertRaises(ValueError):
                diagnostic.parse_trace_log(raw, True)
        changes = (
            lambda t: t.update(schema='sprig-writable-diagnostics-v1'),
            lambda t: t.update(clock='CLOCK_REALTIME'),
            lambda t: t.update(cpu_clock='CLOCK_PROCESS_CPUTIME_ID'),
            lambda t: t.update(capacity=65535), lambda t: t.update(capacity=True),
            lambda t: t.update(extra=1), lambda t: t.pop('cpu_resolution_ns'),
            lambda t: t['events'][0].update(extra=1),
            lambda t: t['directory_attr'].update(extra=1))
        for change in changes:
            trace = sample_trace()
            change(trace)
            with self.assertRaises(ValueError):
                self.parse(trace)

    def test_complete_file_cap_includes_all_ordinary_stderr(self):
        footer = raw_log(sample_trace())
        padding = b'x' * (diagnostic.MAX_LOG_BYTES - len(footer) - 1) + b'\n'
        self.assertEqual(self.parse(sample_trace()), diagnostic.parse_trace_log(padding + footer, True))
        for enabled in (False, True):
            with self.assertRaisesRegex(ValueError, 'exceeds 16 MiB'):
                diagnostic.parse_trace_log(padding + b'x' + footer, enabled)

    def test_clock_failures_null_cpu_and_saturated_counters_are_not_zero(self):
        changes = (
            lambda t: t.update(clock_failures=1),
            lambda t: t.update(cpu_clock_failures=1),
            lambda t: t.update(cpu_resolution_ns=None),
            lambda t: t.update(cpu_resolution_ns=0),
            lambda t: t.update(cpu_resolution_ns=True),
            lambda t: t['events'][0].update(cpu_ns=None),
            lambda t: t['events'][0].update(cpu_ns=False),
            lambda t: t['events'][0].update(cpu_ns=-1),
            lambda t: t['events'][0].update(cpu_ns=2**64),
            lambda t: t.update(overwritten_events=diagnostic.U64_MAX),
            lambda t: t['directory_attr'].update(calls=diagnostic.U64_MAX),
            lambda t: t['directory_attr'].update(nanoseconds=diagnostic.U64_MAX),
            lambda t: t['directory_attr'].update(maximum_nanoseconds=diagnostic.U64_MAX),
            lambda t: t['directory_attr'].update(scanned_nodes=diagnostic.U64_MAX))
        for change in changes:
            trace = sample_trace()
            change(trace)
            with self.assertRaises(ValueError):
                self.parse(trace)
        trace = sample_trace()
        trace['events'][0]['cpu_ns'] = 0
        self.assertEqual(self.parse(trace)['events'][0]['cpu_ns'], 0)
        trace['events'][0]['cpu_ns'] = diagnostic.U64_MAX
        self.assertEqual(self.parse(trace)['events'][0]['cpu_ns'], diagnostic.U64_MAX)

    def test_event_fields_order_sequences_flags_and_totals(self):
        changes = (
            lambda t: t['events'][0].update(operation='other'),
            lambda t: t['events'][0].update(started_ns=float(ORIGIN)),
            lambda t: t['events'][0].update(finished_ns=ORIGIN),
            lambda t: t['events'][1].update(started_ns=ORIGIN + 10),
            lambda t: t['events'][1].update(sequence=9),
            lambda t: t['events'][1].update(sequence=True),
            lambda t: t['events'][0].update(success=False),
            lambda t: t['events'][0].update(success=1),
            lambda t: t['events'][0].update(repeats_successful_sync=True),
            lambda t: t['events'][1].update(repeats_successful_sync=True),
            lambda t: t['events'][2].update(repeats_successful_sync=False),
            lambda t: t['events'][1].update(scanned_nodes=1),
            lambda t: t['events'][0].update(scanned_nodes=-1),
            lambda t: t['directory_attr'].update(calls=True),
            lambda t: t['directory_attr'].update(nanoseconds=10),
            lambda t: t['directory_attr'].update(maximum_nanoseconds=5),
            lambda t: t['directory_attr'].update(scanned_nodes=9),
            lambda t: t['journal_sync'].update(repeated_successful_syncs=1),
            lambda t: t['journal_sync'].update(repeated_successful_sync_nanoseconds=14),
            lambda t: t.update(overwritten_events=1),
            lambda t: t['events'].pop())
        for change in changes:
            trace = sample_trace()
            change(trace)
            with self.assertRaises(ValueError):
                self.parse(trace)

    def test_repeat_flag_on_failed_sync_and_reset_are_source_accurate(self):
        trace = trace_from([
            event('journal_sync', ORIGIN, ORIGIN + 1),
            event('journal_sync', ORIGIN + 2, ORIGIN + 3, success=False, repeat=True),
            event('journal_sync', ORIGIN + 4, ORIGIN + 5, repeat=False),
            event('journal_sync', ORIGIN + 6, ORIGIN + 7, repeat=True)])
        self.assertEqual(self.parse(trace)['journal_sync']['repeated_successful_syncs'], 1)
        trace['events'][2]['repeats_successful_sync'] = True
        with self.assertRaisesRegex(ValueError, 'preceding sync'):
            self.parse(trace)

    def test_ring_overwrite_subset_and_full_window_coverage(self):
        # An actual-capacity synthetic ring, including one overwritten startup
        # event and a first retained repeated sync whose predecessor is absent.
        events = [event('journal_sync', ORIGIN - 3 + 3 * index,
                        ORIGIN - 2 + 3 * index, cpu=0, repeat=index > 0)
                  for index in range(diagnostic.CAPACITY + 1)]
        trace = trace_from(events)
        parsed = self.parse(trace)
        self.assertEqual(len(parsed['events']), diagnostic.CAPACITY)
        self.assertEqual(parsed['overwritten_events'], 1)
        analysis = diagnostic.analyze_trace(parsed, pressure_report())
        self.assertTrue(analysis['pressureWindow']['coverageComplete'])
        self.assertEqual(analysis['pressureWindow']['wrapperCount'], 10240)
        parsed['overwritten_events'] = 2
        with self.assertRaisesRegex(ValueError, 'overwritten count'):
            diagnostic.analyze_trace(parsed, pressure_report())
        parsed['overwritten_events'] = 1
        parsed['journal_sync']['nanoseconds'] += 1
        with self.assertRaises(ValueError):
            diagnostic.analyze_trace(parsed, pressure_report())
        # Retaining only a covered suffix is not a permissible repair.
        late = trace_from([event('journal_sync', ORIGIN + 11 + 3 * index,
                                 ORIGIN + 12 + 3 * index, repeat=index > 0)
                           for index in range(diagnostic.CAPACITY + 1)])
        with self.assertRaisesRegex(ValueError, 'first retained'):
            diagnostic.analyze_trace(late, pressure_report())

    def test_overwritten_history_cannot_make_the_first_ever_sync_repeat(self):
        events = [event('journal_sync', ORIGIN + 3 * index, ORIGIN + 3 * index + 1,
                        repeat=index > 0) for index in range(diagnostic.CAPACITY + 1)]
        trace = trace_from(events)
        trace['journal_sync']['repeated_successful_syncs'] += 1
        trace['journal_sync']['repeated_successful_sync_nanoseconds'] += 1
        with self.assertRaisesRegex(ValueError, 'first-ever journal sync'):
            self.parse(trace)
        # Only attrs were overwritten: the first retained sync is also the
        # first-ever sync, even though the trace has nonzero overwritten_events.
        events = [event(start=ORIGIN + 3 * index, end=ORIGIN + 3 * index + 1)
                  for index in range(diagnostic.CAPACITY - 1)]
        events.extend([
            event('journal_sync', ORIGIN + 3 * diagnostic.CAPACITY,
                  ORIGIN + 3 * diagnostic.CAPACITY + 1, repeat=True),
            event('journal_sync', ORIGIN + 3 * diagnostic.CAPACITY + 3,
                  ORIGIN + 3 * diagnostic.CAPACITY + 4, sequence=11)])
        with self.assertRaisesRegex(ValueError, 'no sync was overwritten'):
            self.parse(trace_from(events))

    def test_pressure_coverage_final_destroy_and_no_shortened_suffix(self):
        events = sample_trace()['events']
        cases = []
        late = copy.deepcopy(events)
        late[0]['started_ns'] = ORIGIN + 11
        cases.append(trace_from(late))
        short = copy.deepcopy(events)
        short[-1]['finished_ns'] = ORIGIN + 20488
        cases.append(trace_from(short))
        failed = copy.deepcopy(events)
        failed[-1]['success'] = False
        cases.append(trace_from(failed))
        not_sync = copy.deepcopy(events)
        not_sync[-1].update(operation='directory_attr', scanned_nodes=4, repeats_successful_sync=False)
        cases.append(trace_from(not_sync))
        # The crossing scope is not evidence of the later normal destroy.
        cases.append(trace_from(copy.deepcopy(events[:-1])))
        poisoned = copy.deepcopy(events)
        poisoned[1]['success'] = False
        poisoned[2]['repeats_successful_sync'] = False
        cases.append(trace_from(poisoned))
        cases.append(trace_from([]))
        for trace in cases:
            with self.assertRaises(ValueError):
                diagnostic.analyze_trace(trace, pressure_report())
        report = pressure_report()
        report['workers'][0]['operationIntervals'].pop(0)
        with self.assertRaises(ValueError):
            diagnostic.analyze_trace(sample_trace(), report)
        for origin in (str(2**64 - 1), str(ORIGIN) + '.0', ORIGIN, '0' + str(ORIGIN)):
            report = pressure_report()
            report['monotonicOriginNs'] = origin
            with self.assertRaises(ValueError):
                diagnostic.analyze_trace(sample_trace(), report)

    def test_cpu_only_fully_contained_and_union_not_per_worker_double_counted(self):
        result = diagnostic.analyze_trace(sample_trace(), pressure_report())
        window = result['pressureWindow']
        self.assertEqual(window, {'startedNs': ORIGIN + 10, 'finishedNs': ORIGIN + 20489,
                                  'wallNs': 20479, 'wrapperCount': 10240, 'coverageComplete': True})
        occupancy = result['wholePressureUnionWall']
        self.assertEqual(occupancy['scanUnionNs'], 4)
        self.assertEqual(occupancy['syncUnionNs'], 6)
        self.assertEqual(occupancy['bothNs'], 0)
        self.assertEqual(occupancy['neitherNs'], 20469)
        scopes = result['pressureScopes']
        self.assertEqual(scopes['directory_attr']['fullyContainedCpu']['sumNs'], 0)
        self.assertEqual(scopes['directory_attr']['boundaryCrossingCount'], 1)
        self.assertEqual(scopes['journal_sync']['fullyContainedCpu']['sumNs'], 6)
        self.assertEqual(scopes['journal_sync']['boundaryCrossingCount'], 1)
        self.assertEqual(scopes['journal_sync']['fullyContainedCpuExceedsWall']['count'], 1)
        self.assertEqual(result['retainedCpuExceedsWall']['count'], 3)
        self.assertEqual(result['retainedCpuExceedsWall']['maximumExcessNs'], 1188)
        repeats = result['sameSequenceSuccessfulSyncs']
        self.assertEqual(repeats['fullyContainedCount'], 1)
        self.assertEqual(repeats['boundaryCrossingCount'], 1)
        self.assertEqual(repeats['pressureClippedUnionWallNs'], 4)
        self.assertEqual(repeats['fullyContainedCpu']['sumNs'], 5)
        all_wrappers = result['wrapperOverlaps']['all']
        self.assertEqual(all_wrappers['count'], 10240)
        self.assertEqual(all_wrappers['wrapperWall']['sumNs'], 20480)
        sums = all_wrappers['summedWrapperOverlapNs']
        self.assertEqual(sum(sums[key] for key in ('scanOnlyNs', 'syncOnlyNs', 'bothNs', 'neitherNs')), 20480)
        self.assertEqual(result['wrapperOverlaps']['byOperation']['read']['tails']['p99']['count'], 2048)
        self.assertTrue(result['wrapperOverlaps']['byOperation']['read']['tails']['p99']['tiesIncluded'])
        def assert_no_arrays(value):
            self.assertIsNot(type(value), list)
            if type(value) is dict:
                for nested in value.values():
                    assert_no_arrays(nested)
        assert_no_arrays(result)
        self.assertLess(len(json.dumps(result)), 40000)

    def test_zero_wall_positive_cpu_anomaly_is_not_clamped_or_divided(self):
        events = sample_trace()['events']
        events[3].update(finished_ns=ORIGIN + 20, cpu_ns=7)
        result = diagnostic.analyze_trace(trace_from(events), pressure_report())
        scan = result['pressureScopes']['directory_attr']
        self.assertEqual(scan['fullyContainedCpu']['sumNs'], 7)
        self.assertEqual(scan['fullyContainedWall']['sumNs'], 0)
        self.assertEqual(scan['fullyContainedCpuExceedsWall']['zeroWallPositiveCpuCount'], 1)

    def test_exact_clock_proof_equal_endpoints_and_format_normalized_offsets(self):
        proof = clock_proof()
        self.assertIs(diagnostic.validate_clock_proof(proof), proof)
        proof['container']['timensOffsets'] = 'boottime 0 0\nmonotonic 0 0\n'
        proof['hostBeforeNs'] = proof['containerMonotonicNs'] = proof['hostAfterNs'] = ORIGIN
        self.assertEqual(diagnostic.validate_clock_proof(proof)['containerMonotonicNs'], ORIGIN)

    def test_clock_proof_domain_namespace_offsets_types_and_sandwich_rejections(self):
        changes = (
            lambda p: p.update(schema='other'), lambda p: p.update(clock='CLOCK_REALTIME'),
            lambda p: p.update(hostBeforeNs=True), lambda p: p.update(hostAfterNs=float(ORIGIN)),
            lambda p: p.update(containerMonotonicNs=str(ORIGIN)),
            lambda p: p.update(containerMonotonicNs=ORIGIN - 2),
            lambda p: p.update(containerMonotonicNs=ORIGIN + 2),
            lambda p: p.update(hostBeforeNs=ORIGIN + 3),
            lambda p: p.update(hostAfterNs=2**64), lambda p: p.update(hostBeforeNs=-1),
            lambda p: p.update(extra=1),
            lambda p: p['container'].update(timeNamespace='time:[4026531835]'),
            lambda p: p['container'].update(timeForChildrenNamespace='time:[4026531835]'),
            lambda p: p['host'].update(timeForChildrenNamespace='time:[4026531835]'),
            lambda p: p['host'].update(timeNamespace='4026531834'),
            lambda p: p['host'].update(monotonicResolutionNs=0),
            lambda p: p['host'].update(cpuResolutionNs=False),
            lambda p: p['container'].update(cpuResolutionNs=None),
            lambda p: p['container'].update(timensOffsets='monotonic 1 0\nboottime 0 0\n'),
            lambda p: p['container'].update(timensOffsets='monotonic 0 0\n'),
            lambda p: p['container'].update(timensOffsets='monotonic 0 0\nmonotonic 0 0\nboottime 0 0\n'),
            lambda p: p['container'].update(timensOffsets='monotonic 0 1000000000\nboottime 0 0\n'),
            lambda p: p['container'].update(timensOffsets='monotonic 0.0 0\nboottime 0 0\n'),
            lambda p: p['container'].pop('timensOffsets'))
        for change in changes:
            proof = clock_proof()
            change(proof)
            with self.assertRaises(ValueError):
                diagnostic.validate_clock_proof(proof)


if __name__ == '__main__':
    unittest.main()
