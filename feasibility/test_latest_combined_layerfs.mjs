// Inert SDK/subprocess tests only. No Docker, mount, product or shell command executes.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {SOURCE_SHA, SCHEMA, LIMITS, validateOptions, validateFixture, checksumCommand, writeCommand, runLatestCombinedLayerfs} from './latest_combined_layerfs.mjs';

const sha = value => createHash('sha256').update(value).digest('hex');
const image = 'sha256:' + 'a'.repeat(64), initial = '32' + 'b'.repeat(64), container = 'c'.repeat(64);
const sandbox = '1', temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'latest-combined-lfs-inert-'));
const environmentKeys = ['GITHUB_ACTIONS', 'RUNNER_TEMP', 'TMPDIR', 'LAYERFS_HOME', 'LAYERFS_VOLUME', 'LAYERFS_STORE_PATH', 'LAYERFS_IMAGE', 'LAYERFS_DAEMON', 'LAYERFS_DOCKER', 'LAYERFS_CONTAINER_PREFIX',
  'SPRIG_LIFECYCLE_TRACE', 'SPRIG_WRITABLE_DIAGNOSTICS', 'LAYERFS_NATIVE', 'LAYERFS_STORE_POLICY', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH', 'LAYERFS_WORKER_ENDPOINT', 'LAYERFS_TRACE', 'LAYERFS_DAEMON_HOST'];
const saved = new Map(environmentKeys.map(key => [key, process.env[key]]));
let serial = 0;

function fixture(caseName) {
  const base = path.join(temporary, String(++serial)); fs.mkdirSync(base);
  const measuredMount = path.join(base, 'mount'), source = path.join(base, 'source'), records = path.join(base, 'records');
  for (const dir of [measuredMount, source, records, path.join(measuredMount, 'docker'), path.join(measuredMount, 'volume')]) fs.mkdirSync(dir);
  const oracle = [];
  for (let i = 0; i < (caseName === 'identical' ? 100 : 200); i++) {
    const name = 'f' + String(i).padStart(4, '0') + '.dat', body = Buffer.alloc(128, i % 256);
    fs.writeFileSync(path.join(source, name), body); oracle.push({path: name, bytes: body.length, sha256: sha(body)});
  }
  const oraclePath = path.join(base, 'oracle.json'); fs.writeFileSync(oraclePath, JSON.stringify(oracle));
  const steps = caseName === 'identical' ? [] : Array.from({length: 100}, (_, index) => {
    const body = Buffer.alloc(128, index); body[3] = 255;
    return {step: index + 1, path: oracle[index].path, offset: 3, data: Buffer.from([255]).toString('base64'), sha256: sha(body)};
  });
  const options = {caseName, root: path.join(measuredMount, 'sample'), measuredMount, source, oraclePath,
    sdkPath: fileURLToPath(new URL('./latest_combined_layerfs.mjs', import.meta.url)), daemonPath: fs.realpathSync(process.execPath), image,
    recordsPath: path.join(records, 'sample.jsonl'), productionSha: SOURCE_SHA, archiveAllowanceBytes: 128 * 1024**2};
  if (steps.length) { options.stepsPath = path.join(base, 'steps.json'); fs.writeFileSync(options.stepsPath, JSON.stringify(steps)); }
  return {options, oracle, steps};
}

function dependencies(options, failure = null) {
  const events = [], branches = new Map([['main', initial]]), commits = [];
  let project, views = [], count = 0, executions = 0, hasSandbox = false, closed = false, clientClosed = false, inventories = 0, spaces = 0;
  const client = {created: {layer: initial},
    branch: {
      fork: async (name, base) => { events.push('fork:' + name); branches.set(name, branches.get(base) ?? base); },
      list_commits: async () => ({items: [...commits], hasMore: false}),
    },
    project: {list_sandboxes: async () => ({items: [{sandbox, image, workspaces: views.length}], hasMore: false})},
    sandbox: {
      create: async value => { assert.equal(value.image, image); hasSandbox = true; return {sandbox}; },
      list_workspaces: async () => {
        inventories++;
        if (failure === 'inventory_unknown' && inventories === 5) throw Error('synthetic lost inventory');
        const items = views.map(view => ({...view, activity: 'Idle', base: branches.get(view.name)}));
        if (failure === 'untracked_workspace' && inventories === 5) items.push({path: '/workspaces/999', activity: 'Idle'});
        return {items, hasMore: false};
      },
      close: async value => { assert.equal(value, sandbox); assert.equal(views.length, 0); events.push('close'); closed = true; },
    },
    workspace: {
      mount: async (value, name) => { assert.equal(value, sandbox); const view = {sandbox, path: '/workspaces/' + (++count), name}; views.push(view); events.push('mount:' + name); return view; },
      exec: async (view, command) => {
        executions++; events.push('exec:' + view.name);
        assert.ok(command.includes('sha256sum -c -') || command.startsWith('set -e; printf'));
        if (failure === 'unknown_exec' && executions === 2) throw Error('synthetic lost acknowledgment');
        if (failure === 'known_command_failure' && executions === 3) return {exitCode: 1, stdout: 'complete failed stdout', stderr: 'complete failed stderr'};
        if (failure === 'oversize' && executions === 1) return {exitCode: 0, stdout: 'x'.repeat(LIMITS.streamBytes + 1), stderr: ''};
        return {exitCode: 0, stdout: command.startsWith('set -e;') ? '' : 'all listed checks passed\n', stderr: ''};
      },
      commit: async view => { const revision = '12' + String(commits.length + 1).padStart(64, '0'); branches.set(view.name, revision); commits.push({id: revision}); return {kind: 'Committed', head: revision, commit: {id: revision}}; },
      unmount: async (view, discard) => {
        assert.equal(discard, true); events.push('unmount:' + view.name);
        if (failure === 'unknown_unmount') throw Error('synthetic lost unmount acknowledgment');
        views = views.filter(item => item.path !== view.path);
      },
    },
    close: async () => { events.push('client.close'); clientClosed = true; },
  };
  // Deliberately cyclic live state: the adapter must never serialize a client.
  client.self = client;
  const subprocess = async (argv, cwd) => {
    events.push('host:' + argv.join(' ')); let stdout = '';
    if (argv[0] === 'stat') stdout = 'btrfs\n';
    else if (argv[0] === 'findmnt') stdout = JSON.stringify({filesystems: [{target: options.measuredMount, fstype: 'btrfs'}]});
    else if (argv[0] === 'btrfs') {
      if (argv[2] === 'usage') { spaces++; stdout = 'Used: ' + (spaces === 1 ? 200000 : 400000) + '\n'; }
      else stdout = 'complete ordinary Btrfs evidence\n';
    } else if (argv[0] === 'bash') { assert.equal(cwd, options.source); stdout = 'source listed checks passed\n'; }
    else if (argv[0] === 'docker') {
      assert.deepEqual(argv.slice(1, 3), ['--host', 'unix:///var/run/docker.sock']); const command = argv.slice(3);
      if (command[0] === 'image') stdout = JSON.stringify([{Id: image, Config: {User: 'root'}}]);
      else if (command[0] === 'info') stdout = JSON.stringify({DockerRootDir: path.join(options.measuredMount, 'docker')});
      else if (command[0] === 'volume' && command[1] === 'create') stdout = command[2] + '\n';
      else if (command[0] === 'volume' && command[1] === 'inspect') stdout = path.join(options.measuredMount, 'volume') + '\n';
      else if (command[0] === 'ps') {
        if (failure === 'container_inventory_unknown' && closed) throw Error('synthetic Docker inventory failure');
        stdout = hasSandbox && (!closed || failure === 'container_remains') ? container + '\n' : '';
      } else if (command[0] === 'inspect') stdout = JSON.stringify([{Id: container, Image: failure === 'wrong_image' ? 'sha256:' + '0'.repeat(64) : image,
        State: {Running: true}, Config: {Labels: {'layerfs.project': project}}}]);
      else if (command[0] === 'logs') stdout = 'complete available sandbox log\n';
      else throw Error('unexpected host Docker operation: ' + command.join(' '));
    } else throw Error('unexpected subprocess: ' + argv.join(' '));
    return {returncode: 0, signal: null, stdout, stderr: ''};
  };
  return {subprocess, sdk: {LayerFS: {init: async id => { project = id; return client; }}},
    inspect: () => ({events, branches, commits, views, closed, clientClosed, spaces})};
}

try {
  for (const key of environmentKeys) delete process.env[key];
  process.env.GITHUB_ACTIONS = 'true'; process.env.RUNNER_TEMP = temporary;
  const basic = fixture('identical'); validateOptions(basic.options); validateFixture(basic.oracle, [], 'identical');
  for (const change of [{productionSha: '9f97a7ec95b662e9cb288704afa165feff132cfa'}, {caseName: 'unique'}, {archiveAllowanceBytes: -1},
    {archiveAllowanceBytes: 1024**3 + 1}, {archiveAllowanceBytes: true}, {sdkPath: 'relative'}, {stepsPath: '/wrong'}]) assert.throws(() => validateOptions({...basic.options, ...change}));
  assert.throws(() => validateFixture([...basic.oracle, basic.oracle[0]], [], 'identical'));
  assert.throws(() => validateFixture(basic.oracle.map((row, i) => i ? row : {...row, path: '../escape'}), [], 'identical'));
  assert.ok(checksumCommand(basic.oracle).endsWith(') | sha256sum -c -'));
  const historical = fixture('history-distributed'); validateFixture(historical.oracle, historical.steps, 'history-distributed');
  assert.ok(writeCommand(historical.steps[0]).includes('conv=notrunc,fsync status=none; touch -d @1700000000'));
  assert.throws(() => validateFixture(historical.oracle, historical.steps.slice(1), 'history-distributed'));
  assert.throws(() => validateFixture(historical.oracle, historical.steps.map((row, i) => i ? row : {...row, offset: 128}), 'history-distributed'));

  for (const caseName of ['identical', 'history-distributed']) {
    const {options, oracle} = fixture(caseName), deps = dependencies(options), before = sha(fs.readFileSync(options.oraclePath));
    const report = await runLatestCombinedLayerfs(options, deps), state = deps.inspect();
    assert.equal(report.ok, true, JSON.stringify(report.error ?? report.cleanupErrors)); assert.equal(report.schema, SCHEMA); assert.equal(report.testOnly, true);
    assert.equal(report.lifecycle.cleanup.complete, true); assert.equal(report.lifecycle.uncertain, false); assert.equal(report.remainingMountsKnown, true); assert.equal(report.remainingContainersKnown, true);
    assert.deepEqual(report.remainingMounts, []); assert.deepEqual(report.remainingContainers, []); assert.equal(state.closed, true); assert.equal(state.views.length, 0);
    const history = caseName === 'history-distributed'; assert.equal(report.fullHistoricalSnapshotReadbacks, history ? 100 : 0);
    assert.equal(report.historicalRestoreSamples.length, history ? 100 : 0); assert.equal(report.lifecycle.confirmedUnmounts.length, history ? 103 : 3);
    assert.equal(report.lifecycle.activeAtSpace.historicalReadbacksStarted, false); assert.equal(report.postHistoryBoundary.historicalReadbacksComplete, true);
    assert.equal(report.postHistoryBoundary.views.length, 3); assert.equal(report.activeSpace.filesystemUsedBytes, 200000); assert.equal(report.postHistorySpace.filesystemUsedBytes, 400000);
    if (history) { assert.equal(report.historyCheck.acknowledgedCommits, 100); assert.equal(report.historyCheck.completed, true); assert.equal(state.branches.size, 104); }
    assert.equal(report.archiveCopy.complete, true); assert.equal(report.archiveCopy.completedFiles, report.completeLogArchive.length);
    assert.equal(report.archiveAdmission.plannedBytes, report.completeLogArchive.reduce((sum, row) => sum + row.bytes, 0));
    for (const row of report.completeLogArchive) { const body = fs.readFileSync(row.archived); assert.equal(body.length, row.bytes); assert.equal(sha(body), row.sha256); assert.ok(fs.existsSync(row.source)); }
    for (const command of report.commands) for (const stream of ['stdout', 'stderr']) {
      assert.equal(sha(fs.readFileSync(command[stream + 'Path'])), command[stream + 'Sha256']); assert.equal(command[stream], undefined);
    }
    assert.equal(sha(fs.readFileSync(options.oraclePath)), before); assert.equal(report.sourceLogBytes, report.archiveAdmission.plannedBytes);
    assert.ok(report.externalLedgerBytes <= LIMITS.ledgerBytes); assert.ok(!state.events.some(event => /host:.*(?:volume rm|systemctl|umount|kill)/.test(event)));
    assert.equal(report.sdkOperations.find(row => row.operation === 'LayerFS.init').result.created.layer, initial);
    assert.equal(report.logicalBytes, oracle.reduce((sum, row) => sum + row.bytes, 0));
  }

  for (const failure of ['unknown_exec', 'unknown_unmount', 'wrong_image', 'inventory_unknown', 'untracked_workspace', 'container_inventory_unknown', 'container_remains', 'known_command_failure', 'oversize']) {
    const {options} = fixture(failure === 'unknown_unmount' || failure === 'known_command_failure' ? 'history-distributed' : 'identical');
    const deps = dependencies(options, failure), report = await runLatestCombinedLayerfs(options, deps), state = deps.inspect();
    assert.equal(report.ok, false, failure); assert.equal(report.testOnly, true);
    if (['unknown_exec', 'unknown_unmount'].includes(failure)) {
      assert.equal(report.lifecycle.uncertain, true); assert.equal(state.closed, false); assert.equal(state.clientClosed, false);
      assert.equal(report.lifecycle.confirmedUnmounts.length, 0); assert.equal(report.lifecycle.attemptedUnmounts.length, failure === 'unknown_unmount' ? 1 : 0);
    }
    if (['wrong_image', 'inventory_unknown', 'untracked_workspace'].includes(failure)) { assert.equal(state.closed, false); assert.equal(report.lifecycle.confirmedUnmounts.length, 0); }
    if (['container_inventory_unknown', 'container_remains'].includes(failure)) { assert.equal(state.closed, true); assert.equal(report.remainingContainersKnown, false); }
    if (failure === 'known_command_failure') { assert.equal(report.lifecycle.cleanup.complete, true); assert.equal(state.closed, true); }
    if (failure === 'oversize') {
      const row = report.commands.find(row => row.purpose === 'first_full_read');
      assert.equal(fs.statSync(row.stdoutPath).size, LIMITS.streamBytes + 1); assert.equal(report.archiveCopy.complete, true); assert.ok(!row.truncated);
    }
    assert.ok(fs.existsSync(options.root)); assert.ok(!state.events.some(event => event.includes('volume rm')));
  }

  {
    const {options} = fixture('identical'); options.archiveAllowanceBytes = 0;
    const report = await runLatestCombinedLayerfs(options, dependencies(options));
    assert.equal(report.ok, false); assert.equal(report.archiveAdmission.admitted, false); assert.ok(report.archiveAdmission.plannedBytes > 0);
    assert.equal(fs.existsSync(options.recordsPath + '.logs'), false); assert.equal(report.completeLogArchive, undefined);
    assert.ok(fs.readdirSync(path.join(options.root, 'logs')).length > 0);
  }
  {
    const {options} = fixture('identical'), originalOpen = fs.openSync; let changed = false;
    try {
      fs.openSync = (file, flags, ...args) => {
        if (!changed && typeof flags === 'number' && (flags & fs.constants.O_NOFOLLOW) && String(file).startsWith(path.join(options.root, 'logs') + '/')) {
          changed = true; fs.appendFileSync(file, 'changed-after-admission');
        }
        return originalOpen(file, flags, ...args);
      };
      const report = await runLatestCombinedLayerfs(options, dependencies(options));
      assert.equal(changed, true); assert.equal(report.ok, false); assert.equal(report.archiveCopy.complete, false); assert.equal(report.completeLogArchive, undefined);
      assert.equal(report.archiveCopy.failedFile.sourceRetained, true); assert.equal(report.archiveCopy.failedFile.bytesWritten, 0);
    } finally { fs.openSync = originalOpen; }
  }
  {
    const {options} = fixture('identical'); process.env.SPRIG_WRITABLE_DIAGNOSTICS = '1';
    const report = await runLatestCombinedLayerfs(options, dependencies(options)); delete process.env.SPRIG_WRITABLE_DIAGNOSTICS;
    assert.equal(report.ok, false); assert.equal(fs.existsSync(options.root), false);
  }
  console.log('PASS: inert latest combined LayerFS identity, two cases/100 history readbacks, boundaries, exact full archives, unknown-state cleanup and resource rejection guards. No real product/runtime/kernel execution.');
} finally {
  for (const [key, value] of saved) { if (value === undefined) delete process.env[key]; else process.env[key] = value; }
  fs.rmSync(temporary, {recursive: true, force: true});
}
