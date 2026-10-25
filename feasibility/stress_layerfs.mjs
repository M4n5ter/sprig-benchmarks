import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {performance} from 'node:perf_hooks';
import {isDeepStrictEqual} from 'node:util';
import {createHash, randomUUID} from 'node:crypto';

export const SOURCE_SHA='9f97a7ec95b662e9cb288704afa165feff132cfa';
const PREFIX='unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER; set -eu; ';
const ORACLE='/opt/bench/tree_oracle.py';
const HOST_ORACLE=path.join(path.dirname(fileURLToPath(import.meta.url)),'tree_oracle.py');
const sha=s=>createHash('sha256').update(s).digest('hex');
const encode=x=>JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v);
const require=(ok,message)=>{if(!ok)throw new Error(message);};
const inside=(p,base)=>p===base||p.startsWith(base+path.sep);
export const quote=s=>"'"+String(s).replaceAll("'","'\\''")+"'";
export function oracleCommand(tree,expected){
 const command=`python3 -B ${ORACLE} ${expected===undefined?'snapshot':'verify'} ${quote(tree)}`;
 if(expected===undefined)return {script:'export TMPDIR=/tmp; '+command,input:null};
 const input=typeof expected==='string'?expected:encode(expected)+'\n';require(JSON.parse(input)?.schema==='cargo-full-tree-v1','expected oracle schema');const delimiter='LAYERFS_ORACLE_'+sha(input);
 require(!input.split('\n').includes(delimiter),'heredoc delimiter collision');
 return {script:`export TMPDIR=/tmp; ${command} <<'${delimiter}'\n${input}${delimiter}`,input};
}
export function exactOracle(raw){return JSON.parse(raw.replace(/(\"mtime_ns\"\s*:\s*)(-?[0-9]+)/g,'$1\"$2\"'));}
function existing(p,directory=false){
 require(path.isAbsolute(p),'absolute path required');require(fs.realpathSync(p)===p,'symlinked input path refused');
 require(directory?fs.statSync(p).isDirectory():fs.statSync(p).isFile(),'wrong input type');return p;
}
async function subprocess(argv,input){
 return await new Promise((resolve,reject)=>{
  const child=spawn(argv[0],argv.slice(1),{stdio:['pipe','pipe','pipe']});let out=[],err=[];
  child.stdout.on('data',x=>out.push(x));child.stderr.on('data',x=>err.push(x));
  child.on('error',reject);child.stdin.on('error',e=>{if(e.code!=='EPIPE')reject(e);});
  child.on('close',(code,signal)=>resolve({returncode:code,signal,stdout:Buffer.concat(out).toString('utf8'),stderr:Buffer.concat(err).toString('utf8')}));
  child.stdin.end(input??'');
 });
}

export function oracleJSON(value){return encode(value).replace(/("mtime_ns":)"(-?[0-9]+)"/g,'$1$2');}
export function advance(oracle,edit){const entries=new Map(oracle.entries.map(x=>[x.path,x]));for(const name of edit.aliases){require(entries.get(name)?.type==='file','unknown edit alias');entries.get(name).sha256=edit.sha256;}}
export function validateFixture(doc){
 const entries=new Map(doc.initial.entries.map(x=>[x.path,x]));require(entries.size===doc.initial.entries.length&&entries.has('.'),'duplicate/missing fixture paths');
 for(const e of doc.initial.entries){require(e.path==='.'||(!e.path.startsWith('/')&&e.path.split('/').every(p=>p&&p!=='.'&&p!=='..')),'unsafe fixture path');require(['file','directory','symlink'].includes(e.type),'unsupported fixture entry');}
 for(const [i,e]of doc.edits.entries()){require(e.step===i+1&&Number.isSafeInteger(e.offset)&&e.offset>=0&&/^[0-9a-f]{64}$/.test(e.sha256),'invalid edit');const row=entries.get(e.path),data=Buffer.from(e.data,'base64');require(row?.type==='file'&&data.length>0&&data.toString('base64')===e.data&&e.offset+data.length<=row.size,'invalid bounded edit');const aliases=doc.initial.hardlink_groups.find(g=>g.includes(e.path));require(Array.isArray(aliases)&&Array.isArray(e.aliases)&&encode([...e.aliases].sort())===encode([...aliases].sort()),'edit aliases do not exactly match hardlink group');}
}
export function writeCommand(e){return `set -eu; printf '%s' ${quote(e.data)} | base64 -d | dd of=${quote(e.path)} bs=65536 iflag=fullblock oflag=seek_bytes seek=${e.offset} conv=notrunc,fsync status=none; touch -d @1700000000 ${quote(e.path)}`;}
export function verifyHistory(rows,ids){require(rows.length===ids.length,'unexpected history count');for(const [i,row]of rows.entries()){require(row.id===ids[ids.length-i-1],'history order/identity mismatch');require(row.parent===(ids[ids.length-i-2]??null)&&row.secondParent===null,'history parent chain mismatch');}}

/** Parent provides fresh measured Btrfs/runtime, source fixture, image and daemon.
 * Test-only dependency injection marks output testOnly, never a real measurement.
 * No helper builds/pulls images, changes runtime settings, retries or forces teardown.
 */
export async function runStressLayerfs(options, testDependencies=undefined){
 const start=performance.now(), phases={}, views=[], attemptedUnmounts=new Set(),confirmedUnmounts=new Set();
 const report={ok:false,prototype_only:false,production_sha:SOURCE_SHA,product:'layerfs',backend:'fuse',workload:'bounded-stress-full-tree-v1',complete_sprig_semantics:false,workload_only_verification:true,phase_seconds:phases,fullTreeChecks:[],commands:[],checkpoint:null,full_task_seconds:null,activeSpace:{filesystemUsedBytes:null,usageRaw:null,groupsRaw:null},lifecycle:{fileTreesRetained:true,normalUnmountOnly:true,persistentControlDaemon:true,activeAtSpace:null,daemons:[],cleanup:{attempts:[],complete:false}},remainingMounts:[],remainingContainers:[],measurementNotes:[
 'New deterministic stress protocol; not frozen seven-case comparison or Cargo performance.',
 'Every snapshot checks exact path set, content, modes, mtimes, symlinks and internal hardlink groups; no normalization/exclusions.',
 'Three original views remain live at primary and post-history space; every historical branch remains retained, normal unmount only.',
 'Whole filesystem includes immutable Python/oracle image, Docker/containerd roots, SDK overlays, logs and all runtime state.',
 'Internal full_task_seconds includes preflight, full oracles, logs, accounting and cleanup; outer subprocess wall is the authoritative matched whole-task measure.',
 'Full raw oracle stdout remains in measured logs; report previews are capped at16KiB per stream. After space accounting and normal cleanup all logs are copied to recordsPath.logs with byte/hash inventory; archive cost remains in outer whole-task wall.',
 'Optional no-op public genesis restore adds one full readback/retained history branch but no acknowledged Commit.',
 'LayerFS Disposable/WAL and workspace MEMORY synchronous OFF do not match Sprig crash durability.',
 'Soft budget checked before phases/steps; no operation timeout, kill or retry of uncertain mutation.',
 'External source oracles use the same host /usr/bin/python3 and tree_oracle.py as Sprig; workspace oracles run in SDK image as UID501/GID20. No source helper container.',
 'No CPU/RAM or cold-cache equivalence claim. Metadata integer timestamps stay exact through raw JSON.' 
 ]};
 if(testDependencies)report.testOnly=true;
 const o=options;let client=null,sandbox=null,uncertain=false,rootReady=false,seq=0,ledger=null,fixture=null,fixtureRaw=null,steps=[],expected=null;
 const id=o.projectName??('stress-'+randomUUID().replaceAll('-',''));
 const volume=id,home=path.join(o.root,'sdk-home'),logs=path.join(o.root,'logs');
 const runner=testDependencies?.subprocess??subprocess;
 const dockerSocket=o.dockerSocket??'/var/run/docker.sock';
 const envSaved=new Map();
 function setenv(k,v){if(!envSaved.has(k))envSaved.set(k,process.env[k]);process.env[k]=v;}
 async function timed(name,fn){if(name!=='cleanup')budget(name);const t=performance.now();try{return await fn();}finally{phases[name]=(performance.now()-t)/1000;}}
 function event(row){if(ledger)fs.appendFileSync(ledger,encode(row)+'\n');}
 function logResult(purpose,result,extra={}){
  const stem=String(++seq).padStart(4,'0')+'-'+purpose.replace(/[^a-zA-Z0-9_-]/g,'_');
  const stdoutPath=path.join(logs,stem+'.stdout'),stderrPath=path.join(logs,stem+'.stderr');
  fs.writeFileSync(stdoutPath,result.stdout??'');fs.writeFileSync(stderrPath,result.stderr??'');
  const row={purpose,...extra,...result,stdoutPath,stderrPath};
  for(const field of ['stdout','stderr'])if(Buffer.byteLength(row[field]??'')>16384){row[field+'Bytes']=Buffer.byteLength(row[field]);row[field+'Sha256']=sha(row[field]);row[field+'TruncatedInReport']=true;row[field]=row[field].slice(0,16384);}
  report.commands.push(row);return row;
 }
 async function host(argv,purpose,input=null){if(argv[0]==='docker')argv=['docker','--host','unix://'+dockerSocket,...argv.slice(1)];const t=performance.now();const result=await runner(argv,input);const row=logResult(purpose,result,{argv,stdinBytes:input===null?0:Buffer.byteLength(input),stdinSha256:input===null?null:sha(input)});row.secondsIncludingCleanup=(performance.now()-t)/1000;require(result.returncode===0&&!result.signal,`${purpose}: host command failed; no retry`);return result.stdout;}
 async function mutation(fn){try{return await fn();}catch(e){uncertain=true;throw e;}}
 async function exec(ws,script,purpose,input=null){
  const command=PREFIX+script,t=performance.now();
  let result;try{result=await client.workspace.exec(ws,command);}catch(e){uncertain=true;logResult(purpose,{stdout:'',stderr:String(e),returncode:null},{command,workspace:ws});throw e;}
  const row=logResult(purpose,{...result,returncode:result.exitCode},{command,workspace:ws,stdinBytes:input===null?0:Buffer.byteLength(input),stdinSha256:input===null?null:sha(input)});
  row.secondsIncludingCleanup=(performance.now()-t)/1000;
  require(result.exitCode===0,`${purpose}: command failed`);return result.stdout;
 }
 async function oracle(ws,purpose,expected){
  // Keep the command short: a 10k-entry expected oracle exceeds Linux's
  // per-argument limit if inserted into bash -c. SDK output spooling is public.
  const c=oracleCommand(ws.path);const raw=await exec(ws,c.script,purpose);const actual=exactOracle(raw);
  require(actual.schema==='cargo-full-tree-v1'&&Array.isArray(actual.entries)&&Array.isArray(actual.hardlink_groups),'invalid snapshot');
  if(expected!==undefined){const wanted=typeof expected==='string'?exactOracle(expected):expected;require(isDeepStrictEqual(actual,wanted),'full-tree mismatch: '+purpose);report.fullTreeChecks.push({purpose,verified:true,entries:actual.entries.length,oracleSha256:sha(raw)});return {ok:true,entries:actual.entries.length};}
  return raw;
 }

 async function sourceOracle(purpose){
  const raw=await host(['/usr/bin/python3','-B',HOST_ORACLE,'snapshot',o.source],purpose),result=exactOracle(raw);
  require(isDeepStrictEqual(result,fixture),'source oracle mismatch');report.fullTreeChecks.push({purpose,verified:true,entries:result.entries.length,oracleSha256:sha(raw)});
 }

 async function mount(name){const ws=await mutation(()=>client.workspace.mount(sandbox,name));require(ws.sandbox===sandbox&&/^\/workspaces\/[1-9][0-9]*$/.test(ws.path),'unexpected workspace');views.push({name,...ws});return ws;}
 async function history(branch){let found=[],at=0;while(true){const page=await client.branch.list_commits(branch,1000,at);require(Array.isArray(page.items),'invalid history');found.push(...page.items);if(!page.hasMore)return found;require(page.items.length>0,'non-progressing history');at+=page.items.length;}}
 function budget(phase){if(rootReady){const f=fs.statfsSync(o.measuredMount);if(f.bavail*f.bsize<256*1024**2){const e=new Error('capacity reserve exhausted before '+phase+'; no pruning');e.name='CapacityAbort';throw e;}}if((performance.now()-start)/1000>=o.sampleBudgetSeconds){const e=new Error('soft budget exhausted before '+phase+'; no operation was started');e.name='BudgetAbort';throw e;}}
 async function unmount(ws){require(!attemptedUnmounts.has(ws.path),'unmount already attempted');attemptedUnmounts.add(ws.path);report.lifecycle.cleanup.attempts.push({action:'workspace.unmount',workspace:ws});await mutation(()=>client.workspace.unmount(ws,true));confirmedUnmounts.add(ws.path);}
 async function account(label,liveViews){
  budget(label);const live=await client.sandbox.list_workspaces(sandbox,1000,0);require(!live.hasMore&&live.items.length===3&&liveViews.every(v=>live.items.some(w=>w.path===v.path&&w.activity==='Idle')),'three idle live views required at accounting');
  const pending=[];
  for(const [purpose,argv]of [['sync',['btrfs','filesystem','sync',o.measuredMount]],['usage',['btrfs','filesystem','usage','-b',o.measuredMount]],['groups',['btrfs','filesystem','df','-b',o.measuredMount]],['extents',['btrfs','filesystem','du','-s','--raw',o.measuredMount]]]){const result=await runner(argv,null);pending.push({purpose,argv,result});require(result.returncode===0&&!result.signal,'space query failed');}
  const [usageRaw,groupsRaw,extentSetRaw]=pending.slice(1).map(r=>r.result.stdout),used=usageRaw.match(/^\s*Used:\s*(\d+)\s*$/m);require(used,'missing Used');
  const value={filesystemUsedBytes:Number(used[1]),usageRaw,groupsRaw,extentSetRaw};
  for(const row of pending)logResult(label+'_'+row.purpose,row.result,{argv:row.argv});return value;
 }

 try{
  await timed('preflight',async()=>{
   require(process.platform==='linux'&&(process.getuid()===0||testDependencies)&&process.env.GITHUB_ACTIONS==='true','authorized root Linux GitHub runner required');
   require(path.isAbsolute(dockerSocket)&&!/[\n\r]/.test(dockerSocket),'local absolute Docker socket required');
   for(const key of ['DOCKER_CONTEXT','DOCKER_HOST','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH','DOCKER_TLS'])require(!process.env[key],`${key} must be unset for pinned local engine`);
   require(/^sha256:[0-9a-f]{64}$/.test(o.image),'invalid image');
   require(Number.isFinite(o.sampleBudgetSeconds)&&o.sampleBudgetSeconds>0&&o.sampleBudgetSeconds<=600,'budget must be in (0,600] seconds');
   require(/^[a-z0-9][a-z0-9_.-]{0,61}[a-z0-9]$/.test(id),'invalid project name');
   existing(HOST_ORACLE);existing(o.measuredMount,true);existing(o.source,true);existing(o.fixturePath);existing(o.daemonPath);existing(o.layerfsSdkPath);
   require(fs.accessSync(o.daemonPath,fs.constants.X_OK)===undefined,'daemon not executable');
   for(const key of ['LAYERFS_STORE_POLICY','LAYERFS_WORKER_ENDPOINT','LAYERFS_NATIVE','LAYERFS_TRACE','LAYERFS_DAEMON_HOST'])require(!process.env[key],`${key} must be unset; do not inherit unrelated policy/route/output`);
   require(path.isAbsolute(o.root)&&inside(o.root,o.measuredMount)&&o.root!==o.measuredMount&&!fs.existsSync(o.root),'fresh sample root required');
   require(path.isAbsolute(process.env.RUNNER_TEMP??'')&&inside(o.measuredMount,process.env.RUNNER_TEMP)&&o.measuredMount!==process.env.RUNNER_TEMP,'measured mount outside RUNNER_TEMP');
   require(!inside(o.source,o.measuredMount)&&!inside(o.fixturePath,o.measuredMount)&&!/[\n\r,]/.test(o.source),'external safe source/oracle required');
   require(fs.statSync(o.source).dev!==fs.statSync(o.measuredMount).dev||testDependencies,'source must be on separate filesystem');
   require(fs.realpathSync(path.dirname(o.root))===path.dirname(o.root),'root parent symlink');
   fs.mkdirSync(o.root,{mode:0o700});rootReady=true;fs.mkdirSync(logs,{mode:0o700});fs.mkdirSync(path.join(o.root,'node-tmp'),{mode:0o700});
   ledger=o.recordsPath??path.join(o.root,'steps.jsonl');
   if(o.recordsPath){require(path.isAbsolute(ledger)&&!inside(ledger,o.measuredMount)&&inside(ledger,process.env.RUNNER_TEMP)&&fs.realpathSync(path.dirname(ledger))===path.dirname(ledger)&&fs.statSync(path.dirname(ledger)).dev!==fs.statSync(o.measuredMount).dev&&!inside(ledger,o.source)&&![o.source,o.fixturePath,o.daemonPath,o.layerfsSdkPath].some(p=>inside(p,ledger)||inside(ledger,p)),'external ledger location invalid');}
   fs.closeSync(fs.openSync(ledger,'wx',0o644));setenv('TMPDIR',path.join(o.root,'node-tmp'));
   require((await host(['stat','-f','-c','%T',o.measuredMount],'filesystem_type')).trim()==='btrfs','measured filesystem not Btrfs');
   const image=JSON.parse(await host(['docker','image','inspect',o.image],'image_inspect'));require(image.length===1&&image[0].Id===o.image,'image mismatch');require(['','0','root','0:0','root:root'].includes(image[0].Config?.User??''),'image must default to root for ordinary source helper');
   const info=JSON.parse(await host(['docker','info','--format','{{json .}}'],'docker_info'));require(inside(info.DockerRootDir,o.measuredMount)&&fs.realpathSync(info.DockerRootDir)===info.DockerRootDir&&fs.statSync(info.DockerRootDir).dev===fs.statSync(o.measuredMount).dev,'Docker root escaped measured filesystem');
   const mountInfo=JSON.parse(await host(['findmnt','-J','-T',o.measuredMount],'containing_filesystem'));require(mountInfo.filesystems?.[0]?.target===o.measuredMount&&mountInfo.filesystems[0].fstype==='btrfs','not exact Btrfs mount');
   const document=exactOracle(fs.readFileSync(o.fixturePath,'utf8'));
   require(document.schema==='sprig-stress-fixture-v1'&&Array.isArray(document.edits)&&document.edits.length<=1000,'stress fixture schema');
   fixture=document.initial;steps=document.edits;fixtureRaw=oracleJSON(fixture)+'\n';require(fixture.schema==='cargo-full-tree-v1','fixture oracle schema');
   expected=structuredClone(fixture);validateFixture(document);
   report.image=o.image;report.root=o.root;report.source=o.source;report.recordsFile=ledger;report.recordsIncludedInActiveSpace=!o.recordsPath;report.fixtureOraclePath=path.join(logs,'fixture-oracle.json');fs.writeFileSync(report.fixtureOraclePath,fixtureRaw);report.fixtureOracleSha256=sha(fixtureRaw);report.oracleMtimeEncoding='decimal strings in structured report; raw JSON text is authoritative; timestamps parsed as decimal strings for exact host comparison';report.imageInspect=image[0];report.dockerInfo=info;report.containingFilesystem=mountInfo.filesystems[0];
   await sourceOracle('source_before_import');
  });
  const {LayerFS}=testDependencies?.sdk??await import(pathToFileURL(o.layerfsSdkPath));
  await timed('init',async()=>{
   fs.mkdirSync(home,{mode:0o700});await host(['docker','volume','create',volume],'volume_create');
   const mp=(await host(['docker','volume','inspect','--format','{{.Mountpoint}}',volume],'volume_path')).trim();require(inside(mp,o.measuredMount),'volume escaped measured filesystem');
   for(const [k,v]of Object.entries({LAYERFS_HOME:home,LAYERFS_VOLUME:volume,LAYERFS_STORE_PATH:path.join(mp,'global/store.sqlite'),LAYERFS_IMAGE:o.image,LAYERFS_DAEMON:o.daemonPath,LAYERFS_CONTAINER_PREFIX:'stress-lfs-',LAYERFS_DOCKER:o.dockerSocket??'/var/run/docker.sock'}))setenv(k,v);
  });
  let main;await timed('import',async()=>{client=await mutation(()=>LayerFS.init(id,o.source));report.initialHead=client.created.layer;require(/^32[0-9a-f]{64}$/.test(report.initialHead),'invalid acknowledged genesis Layer');report.initialized=client.created;sandbox=(await mutation(()=>client.sandbox.create())).sandbox;await mutation(()=>client.branch.fork('import-main','main'));main=await mount('import-main');});
  await timed('main_read',()=>oracle(main,'main_initial_full_tree',fixtureRaw));
  const work=await timed('fork',async()=>{await mutation(()=>client.branch.fork('work','main'));return await mount('work');});
  await timed('first_read',()=>oracle(work,'first_full_tree',fixtureRaw));
  const second=await timed('warm_fork',async()=>{await mutation(()=>client.branch.fork('second','main'));return await mount('second');});
  await timed('warm_read',()=>oracle(second,'second_full_tree',fixtureRaw));
  const baseline=await history('work');require(baseline.length===0,'genesis branch unexpectedly contains Commit records');
  if(o.noopCheckpoint){
   const before=await history('work');
   report.noopCheckpoint=await timed('noop_checkpoint',()=>mutation(()=>client.workspace.commit(work,'Stress no-change checkpoint')));
   require(report.noopCheckpoint.kind==='UpToDate'&&report.noopCheckpoint.head===null,'no-op changed genesis head');
   require(encode(await history('work'))===encode(before),'no-op history changed');
   await oracle(work,'noop_full_tree',fixtureRaw);
  }
  const ids=[],seen=new Set();report.checkpoint_steps=[];report.historical_restore_steps=[];
  for(const edit of steps){
   budget('history-'+edit.step);const row={step:edit.step};
   let t=performance.now();await exec(work,writeCommand(edit),'write-'+edit.step);row.write_seconds=(performance.now()-t)/1000;
   t=performance.now();const result=await mutation(()=>client.workspace.commit(work,'Stress edit '+edit.step));row.checkpoint_cli_seconds=(performance.now()-t)/1000;
   const id=result.head;require(result.kind==='Committed'&&/^12[0-9a-f]{64}$/.test(id)&&!seen.has(id),'missing/distinct committed acknowledgment');ids.push(id);seen.add(id);
   t=performance.now();const live=await client.sandbox.list_workspaces(sandbox,1000,0);require(live.items.some(w=>w.path===work.path&&w.base===id&&w.activity==='Idle'),'checkpoint workspace not ready');row.checkpoint_ready_seconds=(performance.now()-t)/1000;
   row.checkpoint_seconds=row.checkpoint_cli_seconds+row.checkpoint_ready_seconds;row.revision=id;row.checkpoint=result;
   event({event:'checkpoint_acknowledged',...row});report.checkpoint_steps.push(row);
   advance(expected,edit);await oracle(work,'checkpoint_full_tree-'+edit.step,oracleJSON(expected)+'\n');
   row.fullTreeVerified=true;
  }
  verifyHistory(await history('work'),ids);
  const originalViews=[main,work,second];
  report.activeSpace=await account('primary',originalViews);report.lifecycle.activeAtSpace={views:originalViews,fullTreeVerified:true,historicalReadbacksStarted:false};
  expected=structuredClone(fixture);
  if(o.noopCheckpoint){
   budget('restore-noop');const row={step:0,kind:'noop',revision:report.initialHead};let t=performance.now();
   await mutation(()=>client.branch.fork('verify-history-noop',report.initialHead));const historical=await mount('verify-history-noop');row.restore_seconds=(performance.now()-t)/1000;report.historical_restore_steps.push(row);
   t=performance.now();await oracle(historical,'history_full_tree-noop',fixtureRaw);row.read_seconds=(performance.now()-t)/1000;row.fullTreeVerified=true;
   t=performance.now();await unmount(historical);row.cleanup_seconds=(performance.now()-t)/1000;event({event:'historical_snapshot_verified',...row});
  }
  for(const [index,edit]of steps.entries()){
   budget('restore-'+edit.step);advance(expected,edit);const row={step:edit.step,revision:ids[index]};let historical;
   let t=performance.now();await mutation(()=>client.branch.fork('verify-history-'+edit.step,ids[index]));historical=await mount('verify-history-'+edit.step);row.restore_seconds=(performance.now()-t)/1000;
   report.historical_restore_steps.push(row);
   t=performance.now();await oracle(historical,'history_full_tree-'+edit.step,oracleJSON(expected)+'\n');row.read_seconds=(performance.now()-t)/1000;row.fullTreeVerified=true;
   t=performance.now();await unmount(historical);row.cleanup_seconds=(performance.now()-t)/1000;event({event:'historical_snapshot_verified',...row});
  }
  report.fullHistoricalSnapshotReadbacks=report.historical_restore_steps.filter(x=>x.fullTreeVerified).length;
  require(report.fullHistoricalSnapshotReadbacks===steps.length+(o.noopCheckpoint?1:0),'incomplete historical verification');
  await timed('retained_input_verify',async()=>{await sourceOracle('source_unchanged');await oracle(main,'main_unchanged',fixtureRaw);await oracle(second,'second_unchanged',fixtureRaw);});
  verifyHistory(await history('work'),ids);
  const branches=await client.project.list_branches(1000,0);require(!branches.hasMore,'unexpected branch pagination');const byName=Object.fromEntries(branches.items.map(x=>[x.name,x]));
  require(byName.main.base===report.initialHead&&byName['import-main'].head===null&&byName.second.head===null&&byName.work.head===(ids.at(-1)??null),'unexpected original branch heads');
  require(branches.items.length===4+steps.length+(o.noopCheckpoint?1:0),'unexpected retained branch count');
  Object.assign(report,{originalMainViewUnchanged:true,originalSecondViewUnchanged:true,sourceUnchanged:true,allAcknowledgedIdsPresent:true,history_distinct_revisions:ids.length});
  report.postHistorySpace=await account('post_history',originalViews);report.lifecycle.activeAfterHistory={views:originalViews,historicalReadbacksComplete:true,historicalReadbacksCompleted:report.fullHistoricalSnapshotReadbacks,retainedBranches:branches.items.length};
  report.ok=true;report.status='complete';
 }catch(e){report.ok=false;report.error={type:e.name,message:e.message,stack:e.stack,uncertain};if(e.name==='BudgetAbort'){report.budgetAbort=true;report.status='budget_aborted';}else if(e.name==='CapacityAbort'){report.capacityAbort=true;report.status='capacity_blocked';}}
 finally{
  await timed('cleanup',async()=>{
   if(!rootReady)return;
   try{
    require(!uncertain,'mutation/exec outcome uncertain; retain live state without retry');
    if(client&&sandbox){
     for(const ws of [...views].reverse()){
      if(confirmedUnmounts.has(ws.path))continue;await unmount(ws);
     }
     const left=await client.sandbox.list_workspaces(sandbox,1000,0);require(left.items.length===0&&!left.hasMore,'untracked mounts remain');
     report.lifecycle.cleanup.attempts.push({action:'sandbox.close',sandbox});await mutation(()=>client.sandbox.close(sandbox));
    }
    if(client)await client.close();
    report.remainingContainers=(await host(['docker','ps','-aq','--filter','label=layerfs.project='+id],'cleanup_project_inventory')).trim().split(/\s+/).filter(Boolean);require(!report.remainingContainers.length,'project containers remain');report.remainingMounts=[];report.remainingMountsKnown=true;report.remainingContainersKnown=true;report.lifecycle.cleanup.complete=true;report.lifecycle.fileTreesRetained=false;report.lifecycle.fileTreesRetainedAtSpace=!!report.lifecycle.activeAtSpace;report.lifecycle.committedHistoryRetained=true;report.lifecycle.workspaceOverlaysDiscardedByNormalCleanup=!!sandbox;
   }catch(e){report.ok=false;(report.cleanupErrors??=[]).push({message:e.message});report.lifecycle.cleanup.complete=false;report.remainingMounts=views.filter(v=>!confirmedUnmounts.has(v.path));report.remainingMountsKnown=false;report.remainingContainers=null;report.remainingContainersKnown=false;try{if(client)await client.close();}catch(closeError){report.cleanupErrors.push({message:closeError.message});}}
  });
  for(const[k,v]of envSaved){if(v===undefined)delete process.env[k];else process.env[k]=v;}
  if(rootReady&&ledger){
   const t=performance.now();
   try{
    const archive=ledger+'.logs';fs.mkdirSync(archive,{mode:0o755});fs.chmodSync(archive,0o755);report.preservedLogs=[];report.preservedLogsDirectory=archive;report.preservedLogsExternal=!!o.recordsPath;
    for(const name of fs.readdirSync(logs).sort()){
     const from=path.join(logs,name),info=fs.lstatSync(from);require(info.isFile()&&!info.isSymbolicLink(),'unexpected nonregular log');
     const target=path.join(archive,name);fs.copyFileSync(from,target,fs.constants.COPYFILE_EXCL);fs.chmodSync(target,0o644);
     const data=fs.readFileSync(target);report.preservedLogs.push({source:from,path:target,bytes:data.length,sha256:sha(data)});
    }
   }catch(e){report.ok=false;(report.cleanupErrors??=[]).push({message:'log preservation failed: '+e.message});}
   phases.preserve_logs=(performance.now()-t)/1000;
  }
  report.full_task_seconds=(performance.now()-start)/1000;
 }
 if(!report.ok&&(report.status==='complete'||report.cleanupErrors?.length))report.status='failed';
 if(rootReady){try{fs.writeFileSync(path.join(o.root,'report.json'),encode(report)+'\n');}catch(e){report.ok=false;report.reportWriteError=e.message;}}
 return report;
}

if(process.argv[1]&&pathToFileURL(path.resolve(process.argv[1])).href===import.meta.url){
 try{const report=await runStressLayerfs(JSON.parse(fs.readFileSync(process.argv[2],'utf8')));console.log(encode(report));process.exitCode=report.ok?0:((report.status==='budget_aborted'||report.status==='capacity_blocked')&&report.lifecycle.cleanup.complete?2:1);}catch(e){console.error(e.stack);process.exitCode=1;}
}
