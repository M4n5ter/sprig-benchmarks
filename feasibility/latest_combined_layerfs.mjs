// Separate current-main Native-smoke comparator. Frozen combined adapters stay untouched.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawn} from 'node:child_process';
import {performance} from 'node:perf_hooks';
import {createHash, randomUUID} from 'node:crypto';

export const SOURCE_SHA = 'ad78914e36b258b360daf13aec164b5655814689';
export const SCHEMA = 'sprig-latest-combined-layerfs-sample-v1';
export const LIMITS = Object.freeze({streamBytes: 2 * 1024**2, sourceLogBytes: 64 * 1024**2, ledgerBytes: 8 * 1024**2, archiveBytes: 1024**3});
const require = (condition, message) => { if (!condition) throw new Error(message); };
const sha = value => createHash('sha256').update(value).digest('hex');
const encode = value => JSON.stringify(value, (_, v) => typeof v === 'bigint' ? v.toString() : v);
const inside = (value, root) => value === root || value.startsWith(root + path.sep);
const HEX = /^[a-f0-9]{64}$/;
const safeName = value => typeof value === 'string' && /^[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/.test(value)
  && value.split('/').every(part => part !== '.' && part !== '..') && !value.startsWith('-');

function existing(value, directory = false) {
  require(typeof value === 'string' && path.isAbsolute(value) && path.normalize(value) === value && !value.includes('\0'), 'canonical absolute input required');
  require(fs.realpathSync(value) === value, 'symlink input refused');
  const st = fs.lstatSync(value);
  require(directory ? st.isDirectory() : st.isFile(), 'wrong input type');
}

export function validateOptions(o) {
  require(o && ['identical', 'history-distributed'].includes(o.caseName), 'only fixed Native-smoke cases allowed');
  require(o.productionSha === SOURCE_SHA, 'exact current-main LayerFS pin required');
  require(/^sha256:[a-f0-9]{64}$/.test(o.image), 'immutable image ID required');
  require(Number.isSafeInteger(o.archiveAllowanceBytes) && o.archiveAllowanceBytes >= 0 && o.archiveAllowanceBytes <= LIMITS.archiveBytes, 'invalid pre-admitted archive allowance');
  for (const key of ['root', 'measuredMount', 'source', 'oraclePath', 'sdkPath', 'daemonPath', 'recordsPath'])
    require(typeof o[key] === 'string' && path.isAbsolute(o[key]) && path.normalize(o[key]) === o[key] && !o[key].includes('\0'), 'canonical option path required: ' + key);
  require(o.caseName === 'history-distributed' ? typeof o.stepsPath === 'string' && path.isAbsolute(o.stepsPath) && path.normalize(o.stepsPath) === o.stepsPath : o.stepsPath === undefined, 'history steps required only for history case');
  return o;
}

export function validateFixture(oracle, steps, caseName) {
  require(Array.isArray(oracle) && oracle.length === (caseName === 'identical' ? 100 : 200), 'frozen listed-file count differs');
  const files = new Map();
  for (const row of oracle) {
    require(row && Object.keys(row).sort().join(',') === 'bytes,path,sha256' && safeName(row.path)
      && Number.isSafeInteger(row.bytes) && row.bytes > 0 && HEX.test(row.sha256) && !files.has(row.path), 'invalid listed-file oracle');
    files.set(row.path, row);
  }
  require(Array.isArray(steps) && steps.length === (caseName === 'identical' ? 0 : 100), 'frozen history count differs');
  for (const [index, step] of steps.entries()) {
    require(step && Object.keys(step).sort().join(',') === 'data,offset,path,sha256,step' && step.step === index + 1
      && files.has(step.path) && Number.isSafeInteger(step.offset) && step.offset >= 0 && HEX.test(step.sha256)
      && typeof step.data === 'string' && step.data.length > 0 && Buffer.from(step.data, 'base64').toString('base64') === step.data
      && step.offset + Buffer.from(step.data, 'base64').length <= files.get(step.path).bytes, 'invalid frozen history step');
  }
  return files;
}

export const checksumCommand = oracle => '(' + oracle.map(row => `printf '%s  %s\\n' '${row.sha256}' '${row.path}'`).join(';') + ') | sha256sum -c -';
export const writeCommand = step => `set -e; printf '%s' '${step.data}' | base64 -d | dd of='${step.path}' bs=65536 iflag=fullblock oflag=seek_bytes seek=${step.offset} conv=notrunc,fsync status=none; touch -d @1700000000 '${step.path}'`;

async function subprocess(argv, cwd = undefined) {
  return await new Promise((resolve, reject) => {
    const child = spawn(argv[0], argv.slice(1), {cwd, stdio: ['ignore', 'pipe', 'pipe']});
    const stdout = [], stderr = [];
    child.stdout.on('data', value => stdout.push(value)); child.stderr.on('data', value => stderr.push(value));
    child.on('error', reject);
    child.on('close', (returncode, signal) => resolve({returncode, signal, stdout: Buffer.concat(stdout).toString('utf8'), stderr: Buffer.concat(stderr).toString('utf8')}));
  });
}

const fileIdentity = st => ({device: String(st.dev), inode: String(st.ino), size: String(st.size), mtimeNs: String(st.mtimeNs), ctimeNs: String(st.ctimeNs)});
const sameIdentity = (st, expected) => st.isFile() && st.nlink === 1n && encode(fileIdentity(st)) === encode(expected);

/** All runtime setup/restoration and outer-image ownership stay with the caller.
 * Injection is inert test scaffolding, always marked testOnly. No real sample may use it.
 */
export async function runLatestCombinedLayerfs(options, testDependencies = undefined) {
  const started = performance.now(), o = options;
  const report = {schema: SCHEMA, ok: false, testOnly: testDependencies !== undefined, product: 'layerfs', backend: 'fuse',
    production_sha: SOURCE_SHA, case: o?.caseName, image: o?.image, root: o?.root, source: o?.source,
    prototype_only: false, workload_only_verification: true, complete_metadata_verification: false,
    commands: [], sdkOperations: [], historicalRestoreSamples: [], fullHistoricalSnapshotReadbacks: 0,
    historicalRestoreMs: 0, historicalRestoreReadMs: 0, historicalRestoreCleanupMs: 0,
    activeSpace: null, postHistorySpace: null, postHistoryBoundary: null,
    lifecycle: {normalUnmountOnly: true, cleanup: {complete: false, attempts: []}, activeAtSpace: null},
    remainingMounts: null, remainingContainers: null, remainingMountsKnown: false, remainingContainersKnown: false,
    measurementNotes: ['Frozen listed-file bytes/history workload only; no metadata/hardlink/power-loss parity claim.',
      'Original init/import/fork/read/write/commit/restore API and shell scopes retained; new evidence writes follow each phase timer and remain charged to fullTaskSeconds and measured-root space.',
      'activeSpace is before historical restores; postHistorySpace is after all100 readbacks with three originals live. Neither substitutes for the other.',
      'Committed history branches and all source evidence are retained; no volume removal, pruning, outer unmount or runtime restore occurs in this adapter.',
      'Disposable global WAL/OFF and workspace MEMORY/OFF differ from Sprig durability. Persistent UID501 SDK transport differs from CLI.',
      'TMPDIR explicitly resides inside this measured root, unlike the historical combined inline adapter; old-series timings are not pooled.',
      'Normal sandbox.close only follows confirmed zero workspaces; no harness signals, retry or force/lazy unmount.']};
  let client = null, sandbox = null, compilerContainer = null, uncertain = false, rootReady = false, sequence = 0, ledgerBytes = 0;
  let sourceLogBytes = 0, ledger = null, logs = null, oracle = null, steps = null, timingDepth = 0;
  const deferredEvidence = [];
  const mounted = [], attempted = new Set(), confirmed = new Set(), envSaved = new Map();
  const id = 'combined-' + randomUUID().replaceAll('-', ''), runner = testDependencies?.subprocess ?? subprocess;
  const env = (key, value) => { if (!envSaved.has(key)) envSaved.set(key, process.env[key]); process.env[key] = value; };
  function event(value) {
    if (!ledger) return;
    if (timingDepth) { deferredEvidence.push(() => event(value)); return; }
    const body = encode(value) + '\n', bytes = Buffer.byteLength(body);
    require(ledgerBytes + bytes <= LIMITS.ledgerBytes, 'metadata ledger exceeds8MiB; no further events written');
    fs.appendFileSync(ledger, body); ledgerBytes += bytes;
    fs.appendFileSync(path.join(logs, 'lifecycle.jsonl'), body); sourceLogBytes += bytes;
    require(sourceLogBytes <= LIMITS.sourceLogBytes, 'source log acceptance exceeds64MiB; complete originals retained');
  }
  function logResult(purpose, result, extra = {}) {
    if (timingDepth) { deferredEvidence.push(() => logResult(purpose, result, extra)); return; }
    require(result && typeof result.stdout === 'string' && typeof result.stderr === 'string', 'complete text streams required');
    const stem = String(++sequence).padStart(5, '0') + '-' + purpose.replace(/[^A-Za-z0-9_.-]/g, '_');
    const row = {sequence, purpose, ...extra, returncode: result.returncode, signal: result.signal ?? null};
    for (const field of ['stdout', 'stderr']) {
      const body = result[field], target = path.join(logs, stem + '.' + field);
      fs.writeFileSync(target, body, {flag: 'wx'}); // Persist ALL returned bytes before enforcing acceptance limits.
      row[field + 'Path'] = target; row[field + 'Bytes'] = Buffer.byteLength(body); row[field + 'Sha256'] = sha(body);
      sourceLogBytes += row[field + 'Bytes'];
    }
    report.commands.push(row); event({event: 'command_finished', ...row});
    require(row.stdoutBytes <= LIMITS.streamBytes && row.stderrBytes <= LIMITS.streamBytes && sourceLogBytes <= LIMITS.sourceLogBytes,
      'complete stream/source log exceeds acceptance cap; originals retained, sample failed');
    return row;
  }
  async function host(argv, purpose, cwd) {
    if (argv[0] === 'docker') argv = ['docker', '--host', 'unix:///var/run/docker.sock', ...argv.slice(1)];
    const value = await runner(argv, cwd); logResult(purpose, value, {argv, cwd: cwd ?? null});
    require(value.returncode === 0 && !value.signal, 'host command failed: ' + purpose); return value.stdout;
  }
  async function sdk(operation, fn, mutation = false) {
    let value;
    try { value = await fn(); }
    catch (error) { uncertain = true; report.lifecycle.uncertain = true; event({event: 'sdk_error', operation, mutation, message: String(error)}); throw error; }
    const row = {operation, mutation, result: operation === 'LayerFS.init' ? {created: value?.created} : value};
    report.sdkOperations.push(row); event({event: 'sdk_completed', ...row}); return value;
  }
  async function exec(ws, command, purpose) {
    let value;
    try { value = await client.workspace.exec(ws, command); }
    catch (error) { uncertain = true; report.lifecycle.uncertain = true; event({event: 'exec_unknown', purpose, workspace: ws, message: String(error)}); throw error; }
    if (!value || !Number.isInteger(value.exitCode) || typeof value.stdout !== 'string' || typeof value.stderr !== 'string') uncertain = true;
    logResult(purpose, {...value, returncode: value?.exitCode}, {command, workspace: ws});
    require(Number.isInteger(value.exitCode) && value.exitCode === 0 && !value.signal, 'workspace command failed: ' + purpose); return value;
  }
  async function timed(fn) {
    const start = performance.now(); timingDepth++; let value, failure;
    try { value = await fn(); } catch (error) { failure = error; }
    const ms = performance.now() - start; timingDepth--;
    // Complete evidence writes follow the original API timer, never inside it.
    if (!timingDepth) while (deferredEvidence.length) { const write = deferredEvidence.shift(); try { write(); } catch (error) { failure ??= error; } }
    if (failure) throw failure; return {ms, value};
  }
  async function mount(name) {
    const view = await sdk('workspace.mount', () => client.workspace.mount(sandbox, name), true);
    require(view?.sandbox === sandbox && /^\/workspaces\/[1-9][0-9]*$/.test(view.path) && !mounted.some(v => v.path === view.path), 'unexpected mounted workspace');
    const record = {name, ...view}; mounted.push(record); return record;
  }
  async function unmount(view) {
    require(!uncertain && !attempted.has(view.path), 'unknown or previously attempted unmount; no retry');
    attempted.add(view.path); report.lifecycle.cleanup.attempts.push({operation: 'workspace.unmount', workspace: view});
    await sdk('workspace.unmount', () => client.workspace.unmount(view, true), true); confirmed.add(view.path);
  }
  async function history() {
    const all = [];
    while (true) {
      const page = await sdk('branch.list_commits', () => client.branch.list_commits('work', 1000, all.length));
      require(Array.isArray(page?.items) && typeof page.hasMore === 'boolean', 'invalid public history page');
      all.push(...page.items); require(all.length <= 101, 'history exceeds fixed100-step series');
      if (!page.hasMore) return all; require(page.items.length > 0, 'history pagination made no progress');
    }
  }
  async function workspaceInventory() {
    const page = await sdk('sandbox.list_workspaces', () => client.sandbox.list_workspaces(sandbox, 1000, 0));
    require(Array.isArray(page?.items) && page.hasMore === false, 'complete workspace inventory required'); return page.items;
  }
  async function liveBoundary(historicalReadbacksComplete) {
    const views = mounted.filter(view => !confirmed.has(view.path));
    require(views.length === 3 && new Set(views.map(v => v.name)).size === 3 && ['import-main', 'work', 'second'].every(name => views.some(v => v.name === name)), 'three original views must remain live');
    const workspaces = await workspaceInventory();
    require(workspaces.length === 3 && views.every(view => workspaces.some(w => w.path === view.path && w.activity === 'Idle')), 'live workspace inventory differs');
    const page = await sdk('project.list_sandboxes', () => client.project.list_sandboxes(1000, 0));
    require(page?.hasMore === false && page.items?.length === 1 && page.items[0].sandbox === sandbox && page.items[0].workspaces === 3, 'one live sandbox with three views required');
    return {views, workspaces, sandboxes: page.items, controlProcessesRunning: 1, fileTreesRetained: true,
      historicalReadbacksStarted: report.fullHistoricalSnapshotReadbacks > 0, historicalReadbacksComplete,
      historicalReadbacksCompleted: report.fullHistoricalSnapshotReadbacks, allRuntimeLogsAndJournalsInsideMeasuredStore: true};
  }
  async function space(purpose) {
    const queries = [['sync', ['btrfs', 'filesystem', 'sync', o.measuredMount]], ['usage', ['btrfs', 'filesystem', 'usage', '-b', o.measuredMount]],
      ['groups', ['btrfs', 'filesystem', 'df', '-b', o.measuredMount]], ['extents', ['btrfs', 'filesystem', 'du', '-s', '--raw', o.measuredMount]]];
    const pending = [];
    try {
      for (const [name, argv] of queries) { const value = await runner(argv); pending.push({name, argv, value}); require(value.returncode === 0 && !value.signal, 'space query failed: ' + name); }
      const usageRaw = pending[1].value.stdout, match = usageRaw.match(/^\s*Used:\s*(\d+)\s*$/m);
      require(match && Number.isSafeInteger(Number(match[1])) && Number(match[1]) <= 2 * 1024**3, 'invalid2GiB Used accounting');
      return {filesystemUsedBytes: Number(match[1]), usageRaw, groupsRaw: pending[2].value.stdout, extentSetRaw: pending[3].value.stdout};
    } finally { for (const row of pending) logResult(purpose + '_' + row.name, row.value, {argv: row.argv}); }
  }
  function preserveLogs() {
    if (!rootReady || !ledger) return;
    const archive = ledger + '.logs';
    const planned = fs.readdirSync(logs).sort().map(name => {
      require(/^[A-Za-z0-9_.-]+\.(?:stdout|stderr|jsonl)$/.test(name), 'unexpected owned log name');
      const source = path.join(logs, name), st = fs.lstatSync(source, {bigint: true});
      require(st.isFile() && st.nlink === 1n, 'independent regular source logs required');
      return {source, archived: path.join(archive, name), bytes: Number(st.size), identity: fileIdentity(st)};
    });
    const plannedBytes = planned.reduce((sum, row) => sum + row.bytes, 0);
    report.archiveAdmission = {allowanceBytes: o.archiveAllowanceBytes, plannedBytes, plannedFiles: planned, admitted: false};
    require(Number.isSafeInteger(plannedBytes) && plannedBytes <= o.archiveAllowanceBytes, 'full planned archive exceeds admitted allowance; no subset copied');
    require(!fs.existsSync(archive), 'archive already exists');
    fs.mkdirSync(archive, {mode: 0o755}); report.archiveAdmission.admitted = true;
    report.archiveCopy = {complete: false, completedFiles: 0, sourceFilesRetained: true}; const rows = [];
    try {
      for (const row of planned) {
        const input = fs.openSync(row.source, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
        let output = null, bytes = 0; const hash = createHash('sha256');
        try {
          require(sameIdentity(fs.fstatSync(input, {bigint: true}), row.identity), 'source changed after archive admission');
          output = fs.openSync(row.archived, 'wx', 0o644); const buffer = Buffer.alloc(1024**2);
          while (bytes < row.bytes) { const read = fs.readSync(input, buffer, 0, Math.min(buffer.length, row.bytes - bytes)); require(read > 0, 'source shrank during copy');
            let written = 0; while (written < read) { const count = fs.writeSync(output, buffer, written, read - written); require(count > 0, 'archive write made no progress');
              hash.update(buffer.subarray(written, written + count)); bytes += count; written += count; } }
          require(fs.readSync(input, buffer, 0, 1) === 0 && sameIdentity(fs.fstatSync(input, {bigint: true}), row.identity)
            && sameIdentity(fs.lstatSync(row.source, {bigint: true}), row.identity), 'source changed during bounded archive copy');
          fs.fsyncSync(output); rows.push({source: row.source, archived: row.archived, bytes, sha256: hash.digest('hex')});
          report.archiveCopy.completedFiles = rows.length;
        } catch (error) {
          report.partialLogArchive = [...rows, ...(output === null ? [] : [{source: row.source, archived: row.archived, bytes, sha256: hash.digest('hex'), partial: true}])];
          report.archiveCopy.failedFile = {source: row.source, archived: row.archived, bytesWritten: bytes, sourceRetained: fs.existsSync(row.source)}; throw error;
        } finally { fs.closeSync(input); if (output !== null) fs.closeSync(output); }
      }
      report.completeLogArchive = rows; report.archiveCopy.complete = true;
    } catch (error) { report.archiveCopy.error = String(error); report.partialLogArchive ??= rows; throw error; }
  }

  try {
    validateOptions(o);
    require(process.platform === 'linux' && (process.getuid() === 0 || testDependencies) && process.env.GITHUB_ACTIONS === 'true', 'authorized Linux CI required');
    for (const key of ['DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH', 'SPRIG_LIFECYCLE_TRACE', 'SPRIG_WRITABLE_DIAGNOSTICS',
      'LAYERFS_STORE_POLICY', 'LAYERFS_WORKER_ENDPOINT', 'LAYERFS_NATIVE', 'LAYERFS_TRACE', 'LAYERFS_DAEMON_HOST']) require(process.env[key] === undefined, 'inherited route/policy/trace refused: ' + key);
    existing(o.measuredMount, true); existing(o.source, true); existing(o.oraclePath); existing(o.sdkPath); existing(o.daemonPath);
    require(fs.accessSync(o.daemonPath, fs.constants.X_OK) === undefined, 'daemon must be executable');
    existing(process.env.RUNNER_TEMP, true);
    require(inside(o.measuredMount, process.env.RUNNER_TEMP) && o.measuredMount !== process.env.RUNNER_TEMP && inside(o.root, o.measuredMount) && o.root !== o.measuredMount
      && !fs.existsSync(o.root) && fs.realpathSync(path.dirname(o.root)) === path.dirname(o.root), 'new root on exact measured filesystem required');
    require(!inside(o.measuredMount, o.source) && [o.source, o.oraclePath, o.sdkPath, o.daemonPath, ...(o.stepsPath ? [o.stepsPath] : [])].every(p => !inside(p, o.measuredMount)), 'inputs must remain outside measured mount');
    require([o.oraclePath, o.sdkPath, o.daemonPath, ...(o.stepsPath ? [o.stepsPath] : [])].every(p => !inside(p, o.source)), 'oracle/executable inputs must remain outside captured fixture');
    require(fs.statSync(o.source).dev !== fs.statSync(o.measuredMount).dev || testDependencies, 'fixture must be on separate filesystem');
    existing(path.dirname(o.recordsPath), true);
    require(inside(o.recordsPath, process.env.RUNNER_TEMP) && !inside(o.recordsPath, o.measuredMount) && !inside(o.recordsPath, o.source)
      && !fs.existsSync(o.recordsPath) && (fs.statSync(path.dirname(o.recordsPath)).dev !== fs.statSync(o.measuredMount).dev || testDependencies), 'new independent external ledger required');
    const oracleRaw = fs.readFileSync(o.oraclePath, 'utf8'); oracle = JSON.parse(oracleRaw);
    let stepsRaw = null; if (o.stepsPath) { existing(o.stepsPath); stepsRaw = fs.readFileSync(o.stepsPath, 'utf8'); }
    steps = stepsRaw === null ? [] : JSON.parse(stepsRaw); validateFixture(oracle, steps, o.caseName);
    report.oracleSha256 = sha(oracleRaw); report.stepsSha256 = stepsRaw === null ? null : sha(stepsRaw);
    report.files = oracle.length; report.logicalBytes = oracle.reduce((sum, row) => sum + row.bytes, 0);
    report.sdkPath = o.sdkPath; report.daemonPath = o.daemonPath;
    fs.mkdirSync(o.root, {mode: 0o700}); rootReady = true; logs = path.join(o.root, 'logs'); fs.mkdirSync(logs, {mode: 0o700});
    fs.mkdirSync(path.join(o.root, 'node-tmp'), {mode: 0o700}); ledger = o.recordsPath; fs.closeSync(fs.openSync(ledger, 'wx', 0o644));
    report.recordsFile = ledger; report.recordsIncludedInActiveSpace = false;
    event({event: 'prepared', source: o.source, oracleSha256: report.oracleSha256, stepsSha256: report.stepsSha256});
    require((await host(['stat', '-f', '-c', '%T', o.measuredMount], 'filesystem_type')).trim() === 'btrfs', 'measured filesystem must be Btrfs');
    const mountInfo = JSON.parse(await host(['findmnt', '-J', '-T', o.measuredMount], 'containing_filesystem'));
    require(mountInfo.filesystems?.length === 1 && mountInfo.filesystems[0].target === o.measuredMount && mountInfo.filesystems[0].fstype === 'btrfs', 'exact measured mount required');
    const imageInfo = JSON.parse(await host(['docker', 'image', 'inspect', o.image], 'image_inspect'));
    require(imageInfo.length === 1 && imageInfo[0].Id === o.image, 'fixed image identity differs');
    const docker = JSON.parse(await host(['docker', 'info', '--format', '{{json .}}'], 'docker_info'));
    existing(docker.DockerRootDir, true); require(inside(docker.DockerRootDir, o.measuredMount)
      && fs.statSync(docker.DockerRootDir).dev === fs.statSync(o.measuredMount).dev, 'Docker storage outside measured filesystem');
    env('TMPDIR', path.join(o.root, 'node-tmp'));
    const home = path.join(o.root, 'sdk-home');
    const initialized = await timed(async () => {
      fs.mkdirSync(home, {mode: 0o700}); await host(['docker', 'volume', 'create', id], 'volume_create');
      const volume = (await host(['docker', 'volume', 'inspect', '--format', '{{.Mountpoint}}', id], 'volume_inspect')).trim();
      existing(volume, true); require(inside(volume, o.measuredMount) && fs.statSync(volume).dev === fs.statSync(o.measuredMount).dev, 'volume outside measured filesystem');
      for (const [key, value] of Object.entries({LAYERFS_HOME: home, LAYERFS_VOLUME: id, LAYERFS_STORE_PATH: path.join(volume, 'global/store.sqlite'), LAYERFS_IMAGE: o.image,
        LAYERFS_DAEMON: o.daemonPath, LAYERFS_DOCKER: '/var/run/docker.sock', LAYERFS_CONTAINER_PREFIX: 'combined-'})) env(key, value);
    });
    report.initMs = initialized.ms; report.initializationIncludedInImport = false;
    const {LayerFS} = testDependencies?.sdk ?? await import(pathToFileURL(o.sdkPath));
    let main; let value = await timed(async () => {
      client = await sdk('LayerFS.init', () => LayerFS.init(id, o.source), true); // Do not serialize the live SDK client.
      const created = await sdk('sandbox.create', () => client.sandbox.create({image: o.image}), true); sandbox = created.sandbox;
      await sdk('branch.fork', () => client.branch.fork('import-main', 'main'), true); main = await mount('import-main');
    });
    report.importMs = value.ms; report.importResult = client.created; report.initialHead = client.created.layer;
    require(/^32[a-f0-9]{64}$/.test(report.initialHead), 'invalid acknowledged initial Layer');
    value = await timed(async () => { await sdk('branch.fork', () => client.branch.fork('work', 'main'), true); return await mount('work'); });
    const work = value.value; report.forkToWorkspaceMs = value.ms;
    const checks = checksumCommand(oracle); value = await timed(() => exec(work, checks, 'first_full_read')); report.firstFullReadVerifyMs = value.ms;
    report.totalImportForkReadMs = report.importMs + report.forkToWorkspaceMs + report.firstFullReadVerifyMs;
    value = await timed(async () => { await sdk('branch.fork', () => client.branch.fork('second', 'main'), true); return await mount('second'); });
    const second = value.value; report.warmForkToWorkspaceMs = value.ms;
    value = await timed(() => exec(second, checks, 'warm_full_read')); report.warmFirstFullReadMs = value.ms; report.warmForkReadMs = report.warmForkToWorkspaceMs + report.warmFirstFullReadMs;
    const found = (await host(['docker', 'ps', '-aq', '--no-trunc', '--filter', 'label=layerfs.project=' + id], 'compiler_container_inventory')).trim().split(/\s+/).filter(Boolean);
    require(found.length === 1 && HEX.test(found[0]), 'one bound sandbox container required');
    const inspected = JSON.parse(await host(['docker', 'inspect', found[0]], 'compiler_container_inspect'));
    require(inspected.length === 1 && inspected[0].Id === found[0] && inspected[0].Image === o.image && inspected[0].State?.Running === true
      && inspected[0].Config?.Labels?.['layerfs.project'] === id, 'sandbox/image identity mismatch');
    compilerContainer = found[0]; report.compilerContainerIdentity = {id: compilerContainer, image: o.image, project: id};
    if (steps.length) {
      const baseline = await history(), samples = [], ids = new Set();
      report.historyCheck = {samples, expectedSamples: 100, baselineHistoryRecords: baseline.length, completed: false};
      for (const step of steps) {
        const written = await timed(() => exec(work, writeCommand(step), 'history_write_' + step.step));
        const committed = await timed(() => sdk('workspace.commit', () => client.workspace.commit(work, 'Frozen history step ' + step.step), true));
        const commit = committed.value, commitId = commit?.commit?.id;
        require(commit?.kind === 'Committed' && /^12[a-f0-9]{64}$/.test(commitId) && commit.head === commitId && !ids.has(commitId), 'checkpoint must acknowledge a new unique revision'); ids.add(commitId);
        await exec(work, `printf '%s  %s\\n' '${step.sha256}' '${step.path}' | sha256sum -c -`, 'history_changed_read_' + step.step);
        const row = {step: step.step, writeMs: written.ms, commitMs: committed.ms, commitId, commit}; samples.push(row); event({event: 'checkpoint_verified', ...row});
      }
      const final = new Map(oracle.map(row => [row.path, {...row}])); for (const step of steps) final.get(step.path).sha256 = step.sha256;
      await exec(work, checksumCommand([...final.values()]), 'history_final_full_read');
      const observed = await history(), allIds = new Set(observed.map(row => row.id));
      require(observed.length === baseline.length + 100 && [...ids].every(id => allIds.has(id)), 'history must retain all acknowledged commits');
      Object.assign(report.historyCheck, {completed: true, totalWriteMs: samples.reduce((sum, row) => sum + row.writeMs, 0), totalCommitMs: samples.reduce((sum, row) => sum + row.commitMs, 0),
        acknowledgedCommits: 100, historyRecords: observed.length, allAcknowledgedIdsPresent: true, finalFullByteVerification: true, changedFileReadbackAfterEveryCommit: true});
    }
    report.lifecycle.activeAtSpace = await liveBoundary(false); report.activeSpace = await space('active_space'); await liveBoundary(false);
    const current = new Map(oracle.map(row => [row.path, {...row}]));
    for (const [index, step] of steps.entries()) {
      current.get(step.path).sha256 = step.sha256; const commitId = report.historyCheck.samples[index].commitId;
      const created = await timed(async () => { const name = 'verify-history-' + step.step; await sdk('branch.fork', () => client.branch.fork(name, commitId), true); return await mount(name); });
      const historical = created.value; report.historicalRestoreMs += created.ms;
      const row = {step: step.step, commitId, restoreMs: created.ms, verified: false}; report.historicalRestoreSamples.push(row);
      const checked = await timed(() => exec(historical, checksumCommand([...current.values()]), 'historical_full_read_' + step.step));
      row.readMs = checked.ms; report.historicalRestoreReadMs += checked.ms; row.verified = true;
      const closed = await timed(() => unmount(historical)); row.cleanupMs = closed.ms; report.historicalRestoreCleanupMs += closed.ms;
      report.fullHistoricalSnapshotReadbacks++; event({event: 'historical_snapshot_verified', ...row});
    }
    require(report.fullHistoricalSnapshotReadbacks === steps.length, 'all historical snapshots must be read back');
    await exec(second, checks, 'second_unchanged'); await exec(main, checks, 'main_unchanged'); await host(['bash', '-c', checks], 'source_unchanged', o.source);
    report.originalMainViewUnchanged = true; report.originalSecondViewUnchanged = true; report.sourceUnchanged = true; report.allAcknowledgedIdsPresent = true;
    report.postHistoryBoundary = await liveBoundary(true); report.postHistoryBoundary.measurementBoundary = 'after all historical readbacks and unchanged-input checks, before closing three original views';
    report.postHistorySpace = await space('post_history_space'); await liveBoundary(true);
    report.initInclusiveImportForkReadMs = report.initMs + report.totalImportForkReadMs; report.ok = true;
  } catch (error) { report.ok = false; report.error = {type: error.name, message: error.message, stack: error.stack, uncertain}; }
  finally {
    if (rootReady) {
      try {
        require(!uncertain, 'SDK mutation/exec outcome unknown; retain all live state without retry');
        if (client && sandbox) {
          require(compilerContainer, 'sandbox container identity unknown; preserve runtime');
          const known = await workspaceInventory(), expected = mounted.filter(view => !confirmed.has(view.path));
          require(known.length === expected.length && expected.every(view => known.some(row => row.path === view.path)), 'untracked workspace; cleanup blocked');
          for (const view of [...expected].reverse()) await unmount(view);
          require((await workspaceInventory()).length === 0, 'workspaces remain after normal unmount');
          await host(['docker', 'logs', compilerContainer], 'sandbox_logs_before_close');
          report.sandboxLogBoundary = 'complete available logs after workspace unmount, before normal sandbox close; later shutdown output is outside this snapshot';
          report.lifecycle.cleanup.attempts.push({operation: 'sandbox.close', sandbox}); await sdk('sandbox.close', () => client.sandbox.close(sandbox), true);
        }
        if (client) await sdk('client.close', () => client.close());
        const remaining = (await host(['docker', 'ps', '-aq', '--filter', 'label=layerfs.project=' + id], 'cleanup_container_inventory')).trim().split(/\s+/).filter(Boolean);
        require(remaining.length === 0, 'project containers remain'); report.remainingMounts = []; report.remainingContainers = [];
        report.remainingMountsKnown = true; report.remainingContainersKnown = true; report.lifecycle.cleanup.complete = true;
        report.lifecycle.committedHistoryRetained = true; report.lifecycle.volumeRetained = true;
      } catch (error) {
        report.ok = false; (report.cleanupErrors ??= []).push({message: error.message}); report.lifecycle.cleanup.complete = false;
        report.remainingMounts = mounted.filter(view => !confirmed.has(view.path)); report.remainingMountsKnown = false; report.remainingContainersKnown = false;
      }
      report.lifecycle.uncertain = uncertain; report.lifecycle.attemptedUnmounts = [...attempted]; report.lifecycle.confirmedUnmounts = [...confirmed];
      try { preserveLogs(); } catch (error) { report.ok = false; report.logArchiveError = error.message; }
    }
    for (const [key, value] of envSaved) { if (value === undefined) delete process.env[key]; else process.env[key] = value; }
    report.fullTaskSeconds = (performance.now() - started) / 1000; report.sourceLogBytes = sourceLogBytes; report.externalLedgerBytes = ledgerBytes;
    if (rootReady) { try { fs.writeFileSync(path.join(o.root, 'report.json'), encode(report) + '\n', {flag: 'wx'}); }
      catch (error) { report.ok = false; report.reportWriteError = String(error); } }
  }
  return report;
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  const report = await runLatestCombinedLayerfs(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')));
  process.stdout.write(encode(report) + '\n'); process.exitCode = report.ok ? 0 : 1;
}
