import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawn} from 'node:child_process';
import {performance} from 'node:perf_hooks';
import {createHash, randomUUID} from 'node:crypto';

export const SOURCE_SHA='9f97a7ec95b662e9cb288704afa165feff132cfa';
const BUILD='cargo build --offline --locked --verbose --jobs 1';
const PROGRAM='./target/debug/owned-cargo-check';
const EDIT='printf \'fn main() { println!("after"); }\\n\' > src/main.rs';
const PREFIX='unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER; set -eu; ';
const ORACLE='/opt/bench/tree_oracle.py';
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
export function cargoEnvironment(tree,incremental){
 require([0,1].includes(incremental),'incremental must be 0 or 1');
 return `export CARGO_HOME=${quote(tree+'/.cargo-home')} CARGO_TARGET_DIR=${quote(tree+'/target')} TMPDIR=${quote(tree+'/.tmp')} CARGO_INCREMENTAL=${incremental} CARGO_NET_OFFLINE=true LC_ALL=C TZ=UTC; `;
}
export function exactOracle(raw){return JSON.parse(raw.replace(/(\"mtime_ns\"\s*:\s*)(-?[0-9]+)/g,'$1\"$2\"'));}
function existing(p,directory=false){
 require(path.isAbsolute(p),'absolute path required');require(fs.realpathSync(p)===p,'symlinked input path refused');
 require(directory?fs.statSync(p).isDirectory():fs.statSync(p).isFile(),'wrong input type');return p;
}
function metadataInventory(source,oracle){
 const rows=new Map(oracle.entries.map(r=>[r.path,r]));require(rows.size===oracle.entries.length&&rows.has('.'),'invalid fixture entries');
 const dev=fs.lstatSync(source,{bigint:true}).dev;const found=[];
 for(const line of fs.readFileSync('/proc/self/mountinfo','utf8').trim().split('\n')){
  const mount=line.split(' ')[4]?.replace(/\\([0-7]{3})/g,(_,n)=>String.fromCharCode(parseInt(n,8)));require(!mount||!inside(mount,source),'fixture contains mount');
 }
 function visit(full,name){const st=fs.lstatSync(full,{bigint:true}),r=rows.get(name);require(r&&st.dev===dev&&String(st.mtimeNs)===String(r.mtime_ns)&&Number(st.mode&0o7777n)===r.mode,'fixture metadata differs: '+name);found.push(name);
  if(st.isDirectory()){require(r.type==='directory','fixture directory type');for(const child of fs.readdirSync(full))visit(path.join(full,child),name==='.'?child:name+'/'+child);}
  else require(st.isFile()&&st.nlink===1n&&r.type==='file'&&String(st.size)===String(r.size)&&/^[0-9a-f]{64}$/.test(r.sha256),'fixture regular file shape');
 }
 visit(source,'.');require(found.length===rows.size,'missing fixture path');const expected=[...rows.values()].filter(r=>r.type==='file').map(r=>[r.path]).sort((a,b)=>Buffer.compare(Buffer.from(a[0]),Buffer.from(b[0])));require(encode(expected)===encode(oracle.hardlink_groups),'fixture hardlink declarations');
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

/** Parent provides fresh measured Btrfs/runtime, source fixture, image and daemon.
 * Test-only dependency injection marks output testOnly, never a real measurement.
 * No helper builds/pulls images, changes runtime settings, retries or forces teardown.
 */
export async function runCargoLayerfs(options, testDependencies=undefined){
 const start=performance.now(), phases={}, views=[], attemptedUnmounts=new Set(),confirmedUnmounts=new Set();
 const report={ok:false,prototype_only:false,production_sha:SOURCE_SHA,product:'layerfs',backend:'fuse',workload:'cargo-clean-noop-edit-checkpoint-restore-rebuild-v1',complete_sprig_semantics:false,workload_only_verification:true,phase_seconds:phases,commands:[],checkpoint:null,full_task_seconds:null,activeSpace:{filesystemUsedBytes:null,usageRaw:null,groupsRaw:null},lifecycle:{fileTreesRetained:true,normalUnmountOnly:true,persistentControlDaemon:true,activeAtSpace:null,daemons:[],cleanup:{attempts:[],complete:false}},remainingMounts:[],remainingContainers:[],measurementNotes:[
 'Separate dependency-free Cargo series; not frozen seven-case/history100 workload.',
 'LayerFS UID501/GID20 SDK exec in persistent Sandbox differs from default-root per-command Sprig Docker containers; transport costs remain charged.',
 'Actual Cargo paths /workspaces/N differ from Sprig /work; restored Fresh/recompile behavior is observed, not promised.',
 'All target/cache/temp files and full metadata/hardlink oracle are retained without exclusions at accounting; normal teardown later discards workspace overlays but retains committed Store/history.',
 'Raw command outputs/manifests are in measured root/logs; runtime baseline owned by parent.',
 'Init phase provisions private home/volume; import includes public LayerFS.init, sandbox startup and imported-main branch/mount.',
 'checkpoint_cli is SDK commit wall (name retained for paired schema); checkpoint_readiness verifies acknowledged head/history and live workspace.',
 'Full task wall includes preflight, oracles, logs, accounting and normal cleanup; final report serialization occurs afterward.',
 'Disposable/WAL/synchronous=OFF, no matched durability or performance claim.',
 'No harness kill/force/lazy unmount or retry. After normal unmounts SDK sandbox.close uses its documented Docker stop/delete (5-second stop grace).',
 'Oracle heredoc transport exports TMPDIR=/tmp in Sandbox root before redirection; Cargo TMPDIR remains inside captured workspace. Accounting writes are deferred until all space reads complete.'
 ]};
 if(testDependencies)report.testOnly=true;
 const o=options;let client=null,sandbox=null,uncertain=false,rootReady=false,seq=0,ledger=null,fixture=null,fixtureRaw=null;
 const id=o.projectName??('cargo-'+randomUUID().replaceAll('-',''));
 const volume=id,home=path.join(o.root,'sdk-home'),logs=path.join(o.root,'logs');
 const runner=testDependencies?.subprocess??subprocess;
 const dockerSocket=o.dockerSocket??'/var/run/docker.sock';
 const envSaved=new Map();
 function setenv(k,v){if(!envSaved.has(k))envSaved.set(k,process.env[k]);process.env[k]=v;}
 async function timed(name,fn){const t=performance.now();try{return await fn();}finally{phases[name]=(performance.now()-t)/1000;}}
 function event(row){if(ledger)fs.appendFileSync(ledger,encode(row)+'\n');}
 function logResult(purpose,result,extra={}){
  const stem=String(++seq).padStart(4,'0')+'-'+purpose.replace(/[^a-zA-Z0-9_-]/g,'_');
  const stdoutPath=path.join(logs,stem+'.stdout'),stderrPath=path.join(logs,stem+'.stderr');
  fs.writeFileSync(stdoutPath,result.stdout??'');fs.writeFileSync(stderrPath,result.stderr??'');
  const row={purpose,...extra,...result,stdoutPath,stderrPath};report.commands.push(row);return row;
 }
 async function host(argv,purpose,input=null){if(argv[0]==='docker')argv=['docker','--host','unix://'+dockerSocket,...argv.slice(1)];const t=performance.now();const result=await runner(argv,input);const row=logResult(purpose,result,{argv,stdinBytes:input===null?0:Buffer.byteLength(input),stdinSha256:input===null?null:sha(input)});row.secondsIncludingCleanup=(performance.now()-t)/1000;require(result.returncode===0&&!result.signal,`${purpose}: host command failed; no retry`);return result.stdout;}
 async function mutation(fn){try{return await fn();}catch(e){uncertain=true;throw e;}}
 async function exec(ws,script,purpose,input=null){
  const command=PREFIX+cargoEnvironment(ws.path,o.incremental)+script,t=performance.now();
  let result;try{result=await client.workspace.exec(ws,command);}catch(e){uncertain=true;logResult(purpose,{stdout:'',stderr:String(e),returncode:null},{command,workspace:ws});throw e;}
  const row=logResult(purpose,{...result,returncode:result.exitCode},{command,workspace:ws,stdinBytes:input===null?0:Buffer.byteLength(input),stdinSha256:input===null?null:sha(input)});
  row.secondsIncludingCleanup=(performance.now()-t)/1000;
  require(result.exitCode===0,`${purpose}: command failed`);return result.stdout;
 }
 async function oracle(ws,purpose,expected){const c=oracleCommand(ws.path,expected);const raw=await exec(ws,c.script,purpose,c.input);const result=JSON.parse(raw);if(expected===undefined)require(result.schema==='cargo-full-tree-v1'&&Array.isArray(result.entries)&&Array.isArray(result.hardlink_groups),'invalid snapshot');else require(result.ok===true,'full-tree mismatch');return expected===undefined?raw:result;}
 async function sourceOracle(purpose){
  const name=id+'-source-'+seq;const input=fixtureRaw;
  const argv=['docker','run','--rm','--pull=never','-i','--name',name,'--label','layerfs.cargo.sample='+id,'--mount',`type=bind,source=${o.source},target=/work,readonly`,'--workdir','/work','--entrypoint','/bin/bash',o.image,'-c',PREFIX+`python3 -B ${ORACLE} verify /work`];
  const result=JSON.parse(await host(argv,purpose,input));require(result.ok===true,'source oracle mismatch');
  require(!(await host(['docker','ps','-aq','--filter','label=layerfs.cargo.sample='+id],'source_container_inventory')).trim(),'source helper container remains');
 }
 async function mount(name){const ws=await mutation(()=>client.workspace.mount(sandbox,name));require(ws.sandbox===sandbox&&/^\/workspaces\/[1-9][0-9]*$/.test(ws.path),'unexpected workspace');views.push({name,...ws});return ws;}
 async function history(branch){let found=[],at=0;while(true){const page=await client.branch.list_commits(branch,1000,at);require(Array.isArray(page.items),'invalid history');found.push(...page.items);if(!page.hasMore)return found;require(page.items.length>0,'non-progressing history');at+=page.items.length;}}
 async function build(ws,purpose){await exec(ws,BUILD,purpose);const row=report.commands.at(-1);(report.cargoBuildObservations??=[]).push({phase:purpose,freshLines:row.stderr.split('\n').filter(x=>x.includes('Fresh ')),compilingLines:row.stderr.split('\n').filter(x=>x.includes('Compiling ')),stdoutPath:row.stdoutPath,stderrPath:row.stderrPath,returncode:row.returncode});}
 async function program(ws,expected,purpose){require(await exec(ws,PROGRAM,purpose)===expected+'\n','program output mismatch');}
 try{
  await timed('preflight',async()=>{
   require(process.platform==='linux'&&(process.getuid()===0||testDependencies)&&process.env.GITHUB_ACTIONS==='true','authorized root Linux GitHub runner required');
   require(path.isAbsolute(dockerSocket)&&!/[\n\r]/.test(dockerSocket),'local absolute Docker socket required');
   for(const key of ['DOCKER_CONTEXT','DOCKER_HOST','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH','DOCKER_TLS'])require(!process.env[key],`${key} must be unset for pinned local engine`);
   require([0,1].includes(o.incremental)&&/^sha256:[0-9a-f]{64}$/.test(o.image),'invalid incremental/image');
   require(/^[a-z0-9][a-z0-9_.-]{0,61}[a-z0-9]$/.test(id),'invalid project name');
   existing(o.measuredMount,true);existing(o.source,true);existing(o.oraclePath);existing(o.daemonPath);existing(o.layerfsSdkPath);
   require(fs.accessSync(o.daemonPath,fs.constants.X_OK)===undefined,'daemon not executable');
   for(const key of ['LAYERFS_STORE_POLICY','LAYERFS_WORKER_ENDPOINT','LAYERFS_NATIVE','LAYERFS_TRACE','LAYERFS_DAEMON_HOST'])require(!process.env[key],`${key} must be unset; do not inherit unrelated policy/route/output`);
   require(path.isAbsolute(o.root)&&inside(o.root,o.measuredMount)&&o.root!==o.measuredMount&&!fs.existsSync(o.root),'fresh sample root required');
   require(path.isAbsolute(process.env.RUNNER_TEMP??'')&&inside(o.measuredMount,process.env.RUNNER_TEMP)&&o.measuredMount!==process.env.RUNNER_TEMP,'measured mount outside RUNNER_TEMP');
   require(!inside(o.source,o.measuredMount)&&!inside(o.oraclePath,o.measuredMount)&&!/[\n\r,]/.test(o.source),'external safe source/oracle required');
   require(fs.statSync(o.source).dev!==fs.statSync(o.measuredMount).dev||testDependencies,'source must be on separate filesystem');
   require(fs.realpathSync(path.dirname(o.root))===path.dirname(o.root),'root parent symlink');
   fs.mkdirSync(o.root,{mode:0o700});rootReady=true;fs.mkdirSync(logs,{mode:0o700});fs.mkdirSync(path.join(o.root,'node-tmp'),{mode:0o700});
   ledger=o.recordsPath??path.join(o.root,'steps.jsonl');
   if(o.recordsPath){require(path.isAbsolute(ledger)&&!inside(ledger,o.measuredMount)&&inside(ledger,process.env.RUNNER_TEMP)&&fs.realpathSync(path.dirname(ledger))===path.dirname(ledger)&&fs.statSync(path.dirname(ledger)).dev!==fs.statSync(o.measuredMount).dev&&!inside(ledger,o.source)&&![o.source,o.oraclePath,o.daemonPath,o.layerfsSdkPath].some(p=>inside(p,ledger)||inside(ledger,p)),'external ledger location invalid');}
   fs.closeSync(fs.openSync(ledger,'wx',0o644));setenv('TMPDIR',path.join(o.root,'node-tmp'));
   require((await host(['stat','-f','-c','%T',o.measuredMount],'filesystem_type')).trim()==='btrfs','measured filesystem not Btrfs');
   const image=JSON.parse(await host(['docker','image','inspect',o.image],'image_inspect'));require(image.length===1&&image[0].Id===o.image,'image mismatch');require(['','0','root','0:0','root:root'].includes(image[0].Config?.User??''),'image must default to root for ordinary source helper');
   const info=JSON.parse(await host(['docker','info','--format','{{json .}}'],'docker_info'));require(inside(info.DockerRootDir,o.measuredMount)&&fs.realpathSync(info.DockerRootDir)===info.DockerRootDir&&fs.statSync(info.DockerRootDir).dev===fs.statSync(o.measuredMount).dev,'Docker root escaped measured filesystem');
   const mountInfo=JSON.parse(await host(['findmnt','-J','-T',o.measuredMount],'containing_filesystem'));require(mountInfo.filesystems?.[0]?.target===o.measuredMount&&mountInfo.filesystems[0].fstype==='btrfs','not exact Btrfs mount');
   fixtureRaw=fs.readFileSync(o.oraclePath,'utf8');fixture=JSON.parse(fixtureRaw);require(fixture.schema==='cargo-full-tree-v1','fixture oracle schema');
   report.incremental=o.incremental;report.image=o.image;report.root=o.root;report.source=o.source;report.recordsFile=ledger;report.recordsIncludedInActiveSpace=!o.recordsPath;report.fixtureOracle=exactOracle(fixtureRaw);report.fixtureOracleRaw=fixtureRaw;report.oracleMtimeEncoding='decimal strings in structured report; raw JSON text is authoritative and passed unchanged to verify';report.imageInspect=image[0];report.dockerInfo=info;report.containingFilesystem=mountInfo.filesystems[0];
   metadataInventory(o.source,exactOracle(fixtureRaw));
  });
  const {LayerFS}=testDependencies?.sdk??await import(pathToFileURL(o.layerfsSdkPath));
  await timed('init',async()=>{
   fs.mkdirSync(home,{mode:0o700});await host(['docker','volume','create',volume],'volume_create');
   const mp=(await host(['docker','volume','inspect','--format','{{.Mountpoint}}',volume],'volume_path')).trim();require(inside(mp,o.measuredMount),'volume escaped measured filesystem');
   for(const [k,v]of Object.entries({LAYERFS_HOME:home,LAYERFS_VOLUME:volume,LAYERFS_STORE_PATH:path.join(mp,'global/store.sqlite'),LAYERFS_IMAGE:o.image,LAYERFS_DAEMON:o.daemonPath,LAYERFS_CONTAINER_PREFIX:'cargo-lfs-',LAYERFS_DOCKER:o.dockerSocket??'/var/run/docker.sock'}))setenv(k,v);
  });
  let main;await timed('import',async()=>{client=await mutation(()=>LayerFS.init(id,o.source));report.initialHead=client.created.layer;require(/^32[0-9a-f]{64}$/.test(report.initialHead),'invalid acknowledged genesis Layer');report.initialized=client.created;sandbox=(await mutation(()=>client.sandbox.create())).sandbox;await mutation(()=>client.branch.fork('import-main','main'));main=await mount('import-main');});
  const work=await timed('fork',async()=>{await mutation(()=>client.branch.fork('work','main'));return await mount('work');});
  await timed('fixture_verify',()=>oracle(work,'fixture_verify',fixtureRaw));
  await timed('cargo_setup',()=>exec(work,'test ! -e target; test ! -e .cargo-home; test ! -e .tmp; mkdir "$CARGO_HOME" "$TMPDIR"','cargo_setup'));
  for(const [name,fn]of [['clean_build',()=>build(work,'clean_build')],['clean_execute',()=>program(work,'before','clean_execute')],['noop_build',()=>build(work,'noop_build')],['noop_execute',()=>program(work,'before','noop_execute')],['edit',()=>exec(work,EDIT,'edit')],['edit_build',()=>build(work,'edit_build')],['edit_execute',()=>program(work,'after','edit_execute')]])await timed(name,fn);
  const expected=await timed('pre_checkpoint_oracle',()=>oracle(work,'pre_checkpoint_oracle'));report.checkpointTreeOracle=exactOracle(expected);report.checkpointTreeOracleRaw=expected;report.checkpointTreeOracleSha256=sha(expected);
  report.checkpoint=await timed('checkpoint_cli',()=>mutation(()=>client.workspace.commit(work,'Cargo edit and complete build tree')));
  event({event:'cargo_checkpoint_response',checkpoint:report.checkpoint,checkpoint_cli_seconds:phases.checkpoint_cli});
  const revision=report.checkpoint.head;
  await timed('checkpoint_readiness',async()=>{require(report.checkpoint.kind==='Committed'&&/^12[0-9a-f]{64}$/.test(revision),'invalid committed acknowledgment');require((await history('work')).some(x=>x.id===revision),'acknowledged Commit absent from history');const w=await client.sandbox.list_workspaces(sandbox);require(w.items.some(x=>x.path===work.path&&x.base===revision&&x.activity==='Idle'),'workspace not ready at acknowledged head');});
  phases.checkpoint=phases.checkpoint_cli+phases.checkpoint_readiness;
  const second=await timed('restore',async()=>{await mutation(()=>client.branch.fork('second',revision));return await mount('second');});
  await timed('restore_verify',()=>oracle(second,'restore_verify',expected));report.fullRestoredTreeVerified=true;
  await timed('restored_execute',()=>program(second,'after','restored_execute'));
  await timed('restored_rebuild',()=>build(second,'restored_rebuild'));
  await timed('restored_rebuild_execute',()=>program(second,'after','restored_rebuild_execute'));
  await timed('retained_input_verify',async()=>{await oracle(main,'main_unchanged',fixtureRaw);await sourceOracle('source_unchanged');});
  const branches=await client.project.list_branches(1000,0);require(!branches.hasMore,'unexpected branch pagination');const byName=Object.fromEntries(branches.items.map(x=>[x.name,x]));require(byName.main.base===report.initialHead&&byName['import-main'].head===null&&byName.work.head===revision&&byName.second.head===revision,'unexpected branch heads');
  require((await history('work')).some(x=>x.id===revision)&&(await history('second')).some(x=>x.id===revision),'restored acknowledged Commit absent');
  Object.assign(report,{originalMainViewUnchanged:true,sourceUnchanged:true,restoredRevision:revision,allAcknowledgedIdsPresent:true});
  await timed('space',async()=>{
   const mounted=await client.sandbox.list_workspaces(sandbox,1000,0),sandboxes=await client.project.list_sandboxes(1000,0);
   require(!mounted.hasMore&&mounted.items.length===3&&new Set(mounted.items.map(x=>x.path)).size===3&&views.every(v=>mounted.items.some(x=>x.path===v.path)),'three live views not established');
   require(sandboxes.items.length===1&&sandboxes.items[0].sandbox===sandbox&&sandboxes.items[0].workspaces===3,'Sandbox inventory mismatch');
   report.lifecycle.activeAtSpace={views,workspaces:mounted.items,sandboxes:sandboxes.items,controlProcessesRunning:1,fileTreesRetained:true,cargoRestoreReadbackComplete:true,allRuntimeLogsAndJournalsInsideMeasuredStore:true};
   // No measured-root diagnostic writes between sync and completion of all space reads.
   const pending=[];
   for(const [purpose,argv]of [['space_sync',['btrfs','filesystem','sync',o.measuredMount]],['space_usage',['btrfs','filesystem','usage','-b',o.measuredMount]],['space_groups',['btrfs','filesystem','df','-b',o.measuredMount]],['space_extents',['btrfs','filesystem','du','-s','--raw',o.measuredMount]]]){
    const t=performance.now();const result=await runner(argv,null);pending.push({purpose,argv,result,seconds:(performance.now()-t)/1000});
    if(result.returncode!==0||result.signal){for(const row of pending)logResult(row.purpose,row.result,{argv:row.argv,secondsIncludingCleanup:row.seconds});throw new Error(purpose+': space query failed');}
   }
   const [usageRaw,groupsRaw,extentSetRaw]=pending.slice(1).map(x=>x.result.stdout);const used=usageRaw.match(/^\s*Used:\s*(\d+)\s*$/m);require(used,'missing filesystem Used');
   report.activeSpace={filesystemUsedBytes:Number(used[1]),usageRaw,groupsRaw,extentSetRaw};
   const after=await client.sandbox.list_workspaces(sandbox,1000,0),afterSandboxes=await client.project.list_sandboxes(1000,0);
   require(!after.hasMore&&after.items.length===3&&views.every(v=>after.items.some(x=>x.path===v.path&&x.activity==='Idle'))&&afterSandboxes.items.length===1&&afterSandboxes.items[0].workspaces===3,'live views changed during accounting');
   report.lifecycle.activeAtSpace.verifiedAfterSpace=true;
   for(const row of pending)logResult(row.purpose,row.result,{argv:row.argv,secondsIncludingCleanup:row.seconds});
  });report.ok=true;
 }catch(e){report.ok=false;report.error={type:e.name,message:e.message,stack:e.stack,uncertain};}
 finally{
  await timed('cleanup',async()=>{
   if(!rootReady)return;
   try{
    const helper=(await host(['docker','ps','-aq','--filter','label=layerfs.cargo.sample='+id],'cleanup_helper_inventory')).trim();require(!helper,'helper container remains; cleanup blocked');
    require(!uncertain,'mutation/exec outcome uncertain; retain live state without retry');
    if(client&&sandbox){
     for(const ws of [...views].reverse()){
      require(!attemptedUnmounts.has(ws.path),'unmount already attempted');attemptedUnmounts.add(ws.path);report.lifecycle.cleanup.attempts.push({action:'workspace.unmount',workspace:ws});await mutation(()=>client.workspace.unmount(ws,true));confirmedUnmounts.add(ws.path);
     }
     const left=await client.sandbox.list_workspaces(sandbox,1000,0);require(left.items.length===0&&!left.hasMore,'untracked mounts remain');
     report.lifecycle.cleanup.attempts.push({action:'sandbox.close',sandbox});await mutation(()=>client.sandbox.close(sandbox));
    }
    if(client)await client.close();
    report.remainingContainers=(await host(['docker','ps','-aq','--filter','label=layerfs.project='+id],'cleanup_project_inventory')).trim().split(/\s+/).filter(Boolean);require(!report.remainingContainers.length,'project containers remain');report.remainingMounts=[];report.remainingMountsKnown=true;report.remainingContainersKnown=true;report.lifecycle.cleanup.complete=true;report.lifecycle.fileTreesRetained=false;report.lifecycle.fileTreesRetainedAtSpace=!!report.lifecycle.activeAtSpace;report.lifecycle.committedHistoryRetained=true;report.lifecycle.workspaceOverlaysDiscardedByNormalCleanup=!!sandbox;
   }catch(e){report.ok=false;(report.cleanupErrors??=[]).push({message:e.message});report.lifecycle.cleanup.complete=false;report.remainingMounts=views.filter(v=>!confirmedUnmounts.has(v.path));report.remainingMountsKnown=false;report.remainingContainers=null;report.remainingContainersKnown=false;try{if(client)await client.close();}catch(closeError){report.cleanupErrors.push({message:closeError.message});}}
  });
  for(const[k,v]of envSaved){if(v===undefined)delete process.env[k];else process.env[k]=v;}
  report.full_task_seconds=(performance.now()-start)/1000;
 }
 if(rootReady){try{fs.writeFileSync(path.join(o.root,'report.json'),encode(report)+'\n');}catch(e){report.ok=false;report.reportWriteError=e.message;}}
 return report;
}
