#!/usr/bin/env python3
"""Prepare inert captured-state constructors; never compile or invoke a product.

The model intentionally omits store statistics and outer snapshot metadata.
Unknown cursors/root/namespace/revision use explicit fixed-width placeholders.
Generated values are NOT captured server replies or executable replay requests.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

PIN = 'ad78914e36b258b360daf13aec164b5655814689'
RAW_SHA = 'c2233433f0fedde7d6bca1fb04e0906b33521ee5592645e34ef4614c02ecefd3'
SOURCE_MANIFEST_SHA = '848a841b0876047630cbb2cdd86b49d38aead07577f31b8acc0acad0145147a6'
LIMIT, BUDGET = 65519, 56 * 1024


def sha(body):
    return hashlib.sha256(body).hexdigest()


def cost(value):
    if value is None or type(value) is bool:
        return 1
    if type(value) is int:
        return 9
    if isinstance(value, str):
        return 5 + len(value.encode())
    if isinstance(value, list):
        return 5 + sum(map(cost, value))
    return 5 + sum(2 + len(name.encode()) + cost(item) for name, item in value.items())


def rust(value):
    if value is None:
        return 'SdkValue::Null'
    if type(value) is bool:
        return 'SdkValue::Bool(' + str(value).lower() + ')'
    if type(value) is int:
        assert -(2**63) <= value < 2**63
        return 'SdkValue::Int(' + str(value) + ')'
    if isinstance(value, str):
        assert value.isascii() and '\u0000' not in value
        return 'SdkValue::Text(' + json.dumps(value) + '.to_owned())'
    if isinstance(value, list):
        return 'SdkValue::List(vec![\n' + ',\n'.join(map(rust, value)) + '\n])'
    return 'SdkValue::Map(vec![\n' + ',\n'.join(
        '(' + json.dumps(name) + '.to_owned(),' + rust(item) + ')'
        for name, item in value.items()) + '\n])'


def reconstruct(raw, mask):
    forks = [row['result'] for row in raw['sdkOperations'] if row['operation'] == 'branch.fork']
    assert len(forks) == 103 and len({row['branch'] for row in forks}) == 103
    branches = sorted(forks, key=lambda row: row['branch'])[:64]
    assert branches[-1]['branch'] == 'verify-history-64'
    names = {row['branch'] for row in branches}
    assert 'work' not in names
    base = raw['initialHead']
    branch_values = [{'name': 'main', 'base': base, 'head': None}] + [
        {'name': row['branch'], 'forkedFrom': row['head'] or base,
         'base': row['base'], 'head': row['head']} for row in branches]
    # Only these three original live workspaces were acknowledged before restores.
    # Subsequent EOF means their final server-side state is not captured.
    workspace_values = []
    for index, row in enumerate(raw['lifecycle']['activeAtSpace']['workspaces']):
        observed = bool(mask & (1 << index))
        workspace_values.append({
            'workspace': row['workspace'], 'namespace': 0,
            'branch': row['branch'] if row['branch'] in names else None,
            'base': row['base'], 'baseLayer': base, 'root': '0' * 64,
            'activity': 'idle', 'mounted': True, 'directory': row['path'],
            'headMovedSinceMount': False if row['branch'] in names else None,
            'dirty': row['dirty'] if observed else None, 'pendingMerge': False,
            'revision': 0 if observed else None})
    assert len(workspace_values) == 3
    layer = {'overwroteCount': 0, 'logical': raw['logicalBytes'], 'id': base,
             'parent': None, 'root': raw['importResult']['root'],
             'sourceBranch': None, 'sourceCommit': None}
    records = [record for row in raw['sdkOperations'] if row['operation'] == 'branch.list_commits'
               for record in row['result']['items']]
    assert len(records) == 100 and len({r['id'] for r in records}) == 100
    records = {row['id']: row for row in records}
    spent = sum(map(cost, branch_values)) + sum(map(cost, workspace_values)) + cost(layer)
    initial = spent
    commits, more, seen = [], {}, set()
    for branch in branches:
        head = branch['head']
        if head is None:
            continue
        room = max(0, BUDGET - spent) // 5400
        if room == 0:
            more[branch['branch']] = None
            continue
        # Exact pinned catalog widths: (16384 -160 -16)//4510 ==3 records.
        page = []
        for _ in range(min(room, (16384 - 160 - 16) // 4510)):
            if head is None:
                break
            record = copy.deepcopy(records[head])
            page.append(record)
            head = record['parent']
        for record in page:
            if record['id'] in seen:
                continue
            seen.add(record['id'])
            record['branch'] = None  # Its true author `work` is outside first64 names.
            if spent + cost(record) > BUDGET:
                assert branch['branch'] not in more
                more[branch['branch']] = None
                break
            spent += cost(record)
            commits.append(record)
        if head is not None:
            assert branch['branch'] not in more
            more[branch['branch']] = '0' * 320  # Hex of fixed160-byte cursor, not a valid cursor.
    subset = {'branches': branch_values, 'commits': commits, 'more': more,
              'layers': [layer], 'workspaces': workspace_values}
    summary = {'observedMask': mask, 'branchCountCaptured': 103, 'branchPageCount': 64,
               'initialTrackedBytes': initial, 'finalTrackedBytes': spent,
               'commitValues': len(commits), 'cursorMapEntries': len(more),
               'cursorTextEntries': sum(v is not None for v in more.values()),
               'cursorMapBytes': cost(more), 'trackedPlusCursorMapBytes': spent + cost(more),
               'predictedSubsetAnswerBytes': 14 + cost(subset), 'controlLimitBytes': LIMIT}
    return subset, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', required=True)
    parser.add_argument('--source-manifest', required=True)
    parser.add_argument('--output-directory', required=True)
    args = parser.parse_args()
    body = Path(args.raw).read_bytes()
    source_body = Path(args.source_manifest).read_bytes()
    assert sha(body) == RAW_SHA and sha(source_body) == SOURCE_MANIFEST_SHA
    raw = json.loads(body)
    assert raw['production_sha'] == PIN and raw['ok'] is False
    assert raw['fullHistoricalSnapshotReadbacks'] == 100
    cases = [reconstruct(raw, mask) for mask in range(8)]
    full, full_summary = cases[7]
    assert full_summary['trackedPlusCursorMapBytes'] == 71700
    assert all(summary['predictedSubsetAnswerBytes'] > LIMIT for _, summary in cases)
    # Common structure emitted once; optional dirty/revision fields differ by mask.
    common = {name: value for name, value in full.items() if name != 'workspaces'}
    code = '// Generated from captured bytes; see model.json for unobserved fields.\n'
    code += 'const EXPECTED_SUBSET_ANSWER_BYTES: [usize; 8] = ' + str([
        summary['predictedSubsetAnswerBytes'] for _, summary in cases]) + ';\n'
    code += 'fn reconstructed_subset(mask: usize) -> SdkValue {\nlet mut fields = match '
    code += rust(common) + ' { SdkValue::Map(fields) => fields, _ => unreachable!() };\n'
    code += 'let mut workspaces = match ' + rust(full['workspaces'])
    code += ' { SdkValue::List(values) => values, _ => unreachable!() };\n'
    code += '''for (index, workspace) in workspaces.iter_mut().enumerate() {
    if mask & (1 << index) == 0 {
        if let SdkValue::Map(fields) = workspace {
            for (name, value) in fields {
                if name == "dirty" || name == "revision" { *value = SdkValue::Null; }
            }
        }
    }
}
fields.push(("workspaces".to_owned(), SdkValue::List(workspaces)));
SdkValue::Map(fields)
}
'''
    report = {'schema': 'layerfs-source-only-encoder-model-v1', 'sourcePin': PIN,
              'rawSha256': RAW_SHA, 'sourceManifestSha256': SOURCE_MANIFEST_SHA,
              'actualEncoderExecuted': False, 'capturedDaemonReply': False,
              'mountedRerun': False, 'cases': [summary for _, summary in cases],
              'omittedFields': ['kind', 'version', 'store', 'project', 'moreBranches', 'moreLayers'],
              'unobservedPlaceholders': {
                  'cursorHex': '320 zero hex chars, same width; not valid replay cursors',
                  'workspaceRoot': '64 zero hex chars, same width',
                  'namespaceAndRevision': 'zero int64, same width',
                  'workspaceActivityAndMount': 'last-known idle/live assumption, not final observation'},
              'scope': 'Product public encoder of reconstructed structural subset; NOT live snapshot()/server-cause proof.',
              'fixtureRustSha256': sha(code.encode())}
    output = Path(args.output_directory)
    assert output.is_dir()
    for name, data in [('fixture.rs', code.encode()), ('model.json', (json.dumps(report, indent=2) + '\n').encode())]:
        with (output / name).open('xb') as stream:
            stream.write(data)
    print(json.dumps({'preparationOnly': True, 'outputDirectory': str(output),
                      'fixtureRustBytes': len(code.encode()), 'fixtureRustSha256': sha(code.encode())}))


if __name__ == '__main__':
    main()
