// Real production CLI series. Prior prototype and native series remain unchanged.
import {LayerFS} from '../layerfs/api/agent/sdk/src/index.js';
import {checkHistory} from '../history-check.mjs';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {performance} from 'node:perf_hooks';
assert.equal(process.env.GITHUB_ACTIONS,'true');assert.ok(path.isAbsolute(process.env.RUNNER_TEMP||''));
const cwd=process.cwd(),records=[];
const mode=process.env.FEASIBILITY_MODE||'smoke';assert.ok(['smoke','full'].includes(mode));
const cases=mode==='full'?['identical','unique','mixed','insert','history-distributed','history-hotset','history-recurring']:['identical','history-distributed'];
const backend=process.env.SPRIG_BACKEND||'projection';assert.ok(['native','projection','writable'].includes(backend));
const productName='sprig-'+backend;
const rounds=mode==='full'?3:1,expectedRecords=cases.length*rounds*2;
const command=(p,a)=>execFileSync(p,a,{encoding:'utf8',maxBuffer:32*1024*1024});
const timed=async fn=>{const start=performance.now();const value=await fn();return {ms:performance.now()-start,value};};
const json=x=>JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v,2);
function space(root){
 command('btrfs',['filesystem','sync',root]);
 const usage=command('btrfs',['filesystem','usage','-b',root]);
 const groups=command('btrfs',['filesystem','df','-b',root]);
 const extentSet=command('btrfs',['filesystem','du','-s','--raw',root]);
 const used=usage.match(/^\s*Used:\s*(\d+)\s*$/m);assert.ok(used);
 return {filesystemUsedBytes:Number(used[1]),usageRaw:usage,groupsRaw:groups,extentSetRaw:extentSet};
}
function fresh(label){
 const dir=fs.mkdtempSync(path.join(process.env.RUNNER_TEMP,'sprig-native-'+label+'-'));
 const image=path.join(dir,'new.img'),mount=path.join(dir,'mount');
 const fd=fs.openSync(image,'wx',0o600);fs.ftruncateSync(fd,2*1024**3);fs.closeSync(fd);fs.mkdirSync(mount);
 assert.ok(fs.lstatSync(image).isFile()&&!fs.lstatSync(image).isSymbolicLink());
 const mkfs=command('mkfs.btrfs',['-d','single','-m','dup',image]);
 try {
  command('mount',['-o','loop,noatime',image,mount]);
  assert.equal(command('stat',['-f','-c','%T',mount]).trim(),'btrfs');
  return {image,mount,mkfs,mountInfo:command('findmnt',['-T',mount]),empty:space(mount),runtimeState:path.join(dir,'runtime-state.json')};
 } catch(error){
  let mounted=false;try{command('mountpoint',['-q',mount]);mounted=true;}catch{}
  if(mounted)try{command('umount',['-i',mount]);}catch(cleanup){throw new AggregateError([error,cleanup],'Setup and unmount failed');}
  throw error;
 }
}
function historyPlans(caseName,oracle,samples,idKey){
 if(!caseName.startsWith('history-'))return [];
 const steps=JSON.parse(fs.readFileSync(`fixtures/${caseName}-steps.json`));assert.equal(samples.length,steps.length);
 const files=new Map(oracle.map(x=>[x.path,{...x}]));
 return steps.map((step,i)=>{assert.equal(samples[i].step,step.step);assert.ok(files.has(step.path));files.get(step.path).sha256=step.sha256;
  const checks='('+[...files.values()].map(f=>`printf '%s  %s\\n' '${f.sha256}' '${f.path}'`).join(';')+') | sha256sum -c -';
  return {step:step.step,id:samples[i][idKey],checks};});
}
function save(){fs.writeFileSync('results/current-comparison.json',json({prototypeOnly:false,productionSha:'fba02ad27a9d82d225d852987a6fd234fe06f122',comparatorSha:'9f97a7ec95b662e9cb288704afa165feff132cfa',backend,mode,rounds,cases,expectedRecords,complete:records.length===expectedRecords&&records.every(r=>r.correct),records,caveats:['See feasibility/CURRENT-MEASUREMENT-BOUNDARIES.md.', 'Real production CLI, not the prior prototype.', 'Three active workspaces retained on both sides.', 'All CLI initialization, capture, lifecycle, state, backup and synchronization costs remain charged.', 'Metadata-only probe omitted on both sides, not a missing production capability.', 'Different durability and CLI versus SDK transport; no cold-cache or equivalent-memory claim.', 'Whole filesystem includes all persistent application/runtime state; runtime-ready delta is not exact app-only usage.']}));}
for(let round=0;round<rounds;round++)for(const caseName of cases)for(const product of round%2?['layerfs',productName]:[productName,'layerfs']){
 const r={product,case:caseName,round,correct:false,metadataBranchMs:null,metadataBranchProbe:'omitted on both sides to preserve the timed operation sequence'};records.push(r);
 let isolated=null,failure=null;
 try{
 isolated=fresh(`${product}-${caseName}-${round}`);r.filesystem={mkfs:isolated.mkfs,mountInfo:isolated.mountInfo,empty:isolated.empty};
 const fixture=path.join(cwd,'fixtures',caseName),oracle=JSON.parse(fs.readFileSync(fixture+'.json'));
 r.files=oracle.length;r.logicalBytes=oracle.reduce((sum,f)=>sum+f.bytes,0);
 const checks='('+oracle.map(f=>`printf '%s  %s\\n' '${f.sha256}' '${f.path}'`).join(';')+') | sha256sum -c -';
  if(product===productName){
   const args=['feasibility/current_sample.py','run','--root',path.join(isolated.mount,'store'),'--source',fixture,'--oracle',fixture+'.json','--binary',path.join(cwd,'sprig/target/release/sprig'),'--backend',backend];
   const recordDir=path.join(process.env.RUNNER_TEMP,'current-paired-records');fs.mkdirSync(recordDir,{recursive:true});args.push('--records',path.join(recordDir,`production-${backend}-${caseName}-${round}-steps.jsonl`));
   if(caseName.startsWith('history-'))args.push('--steps',fixture+'-steps.json');
   let native;try{native=JSON.parse(command('/usr/bin/python3',args));}catch(error){r.nativeFailureOutput=error.stdout?.toString();r.nativeFailureStderr=error.stderr?.toString();throw error;}r.native=native;assert.equal(native.ok,true);assert.equal(native.prototype_only,false);assert.equal(native.backend,backend);
   for(const key of ['init_seconds','import_seconds','first_fork_seconds','first_read_seconds','total_import_fork_read_seconds','warm_fork_seconds','warm_read_seconds','warm_total_seconds','write_seconds','checkpoint_seconds'])assert.ok(typeof native[key]==='number'&&Number.isFinite(native[key])&&native[key]>=0,`Invalid raw ${key}`);
   r.initMs=native.init_seconds*1000;r.initializationIncludedInImport=false;r.lifecycle=native.lifecycle;
   for(const [key,field] of Object.entries({importMs:'import_seconds',forkToWorkspaceMs:'first_fork_seconds',firstFullReadVerifyMs:'first_read_seconds',totalImportForkReadMs:'total_import_fork_read_seconds',warmForkToWorkspaceMs:'warm_fork_seconds',warmFirstFullReadMs:'warm_read_seconds',warmForkReadMs:'warm_total_seconds'}))r[key]=native[field]*1000;
   if(caseName.startsWith('history-')){assert.equal(native.history_distinct_revisions,100);assert.equal(native.checkpoint_steps.length,100);r.historyCheck={totalWriteMs:native.write_seconds*1000,totalCommitMs:native.checkpoint_seconds*1000,acknowledgedCommits:100,completed:true,samples:native.checkpoint_steps};}
   r.activeSpace=native.activeSpace;r.fullHistoricalSnapshotReadbacks=native.fullHistoricalSnapshotReadbacks;
   for(const [key,field] of Object.entries({historicalRestoreMs:'restore_seconds',historicalRestoreReadMs:'restore_read_seconds',historicalRestoreCleanupMs:'restore_cleanup_seconds'})){assert.ok(typeof native[field]==='number'&&Number.isFinite(native[field])&&native[field]>=0);r[key]=native[field]*1000;}
   assert.equal(r.fullHistoricalSnapshotReadbacks,caseName.startsWith('history-')?100:0);
   assert.equal(native.remainingMounts.length,0);assert.equal(native.lifecycle.cleanup.complete,true);assert.equal(native.lifecycle.activeAtSpace.views.length,3);assert.equal(native.lifecycle.activeAtSpace.foregroundFuseProcesses.length,backend!=='native'?3:0);assert.equal(native.lifecycle.activeAtSpace.historicalReadbacksStarted,false);assert.equal(native.lifecycle.activeAtSpace.controlProcessesRunning,backend!=='native'?3:0);assert.equal(native.originalMainViewUnchanged,true);assert.equal(native.originalSecondViewUnchanged,true);assert.equal(native.sourceUnchanged,true);assert.equal(native.allAcknowledgedIdsPresent,true);
  }else{
   r.runtime=JSON.parse(command('/usr/bin/python3',['feasibility/runtime_storage.py','enter','--state',isolated.runtimeState,'--mount',isolated.mount,'--archive',process.env.LAYERFS_IMAGE_ARCHIVE,'--image',process.env.LAYERFS_IMAGE]));
   r.runtimeReadySpace=space(isolated.mount);
   const setupStart=performance.now();
   const id=`nativefeas-${caseName}-${round}-${Date.now()}`,home=path.join(isolated.mount,'sdk-home');fs.mkdirSync(home,{mode:0o700});
   command('docker',['volume','create',id]);
   const data=command('docker',['volume','inspect','--format','{{.Mountpoint}}',id]).trim();
   assert.ok(data.startsWith(isolated.mount+'/'));
   const storePath=path.join(data,'global/store.sqlite');
   process.env.LAYERFS_VOLUME=id;process.env.LAYERFS_HOME=home;process.env.LAYERFS_STORE_PATH=storePath;process.env.LAYERFS_CONTAINER_PREFIX='nativefeas-';
   let l=null,sandbox=null;const mounted=[],unmountAttempted=new Set();
   const mountWorkspace=async branch=>{const view=await l.workspace.mount(sandbox,branch);mounted.push(view);return view;};
   const unmountWorkspace=async view=>{assert.ok(!unmountAttempted.has(view),'unmount already attempted');unmountAttempted.add(view);return l.workspace.unmount(view,true);};
   r.initMs=performance.now()-setupStart;r.lifecycle={fileTreesRetained:true,controlProcessExited:false,reopenImplemented:true};
   try{
    let main;let t=await timed(async()=>{l=await LayerFS.init(id,fixture);({sandbox}=await l.sandbox.create({image:process.env.LAYERFS_IMAGE}));await l.branch.fork('import-main','main');main=await mountWorkspace('import-main');});r.importMs=t.ms;r.importResult=l.created;
    t=await timed(async()=>{await l.branch.fork('work','main');return mountWorkspace('work');});const ws=t.value;r.forkToWorkspaceMs=t.ms;
    t=await timed(()=>l.workspace.exec(ws,checks));assert.equal(t.value.exitCode,0);r.firstFullReadVerifyMs=t.ms;r.totalImportForkReadMs=r.importMs+r.forkToWorkspaceMs+r.firstFullReadVerifyMs;
    t=await timed(async()=>{await l.branch.fork('second','main');return mountWorkspace('second');});const second=t.value;r.warmForkToWorkspaceMs=t.ms;
    t=await timed(()=>l.workspace.exec(second,checks));assert.equal(t.value.exitCode,0);r.warmFirstFullReadMs=t.ms;r.warmForkReadMs=r.warmForkToWorkspaceMs+r.warmFirstFullReadMs;
    if(caseName.startsWith('history-'))await checkHistory(caseName,{
      exec:async cmd=>{const x=await l.workspace.exec(ws,cmd);assert.equal(x.exitCode,0);return x;},
      commit:async msg=>l.workspace.commit(ws,msg),
      onSample:async sample=>fs.appendFileSync('results/current-history-samples.jsonl',JSON.stringify({product,case:caseName,round,...sample})+'\n'),
      history:async()=>{const all=[];let more=true;while(more){const page=await l.branch.list_commits('work',1000,all.length);assert.ok(page.items.length||!page.hasMore);all.push(...page.items);more=page.hasMore;}return all;}
    },r.historyCheck={});
    assert.equal(command('stat',['-f','-c','%T',storePath]).trim(),'btrfs');r.storeFilesystemVerified='btrfs';
    r.activeSpace=space(isolated.mount);
    r.containerInventory=command('docker',['ps','-aq','--filter','volume='+id]).trim().split('\n').filter(Boolean).map(cid=>({id:cid,graphDriver:JSON.parse(command('docker',['inspect','--format','{{json .GraphDriver}}',cid])),logPath:command('docker',['inspect','--format','{{.LogPath}}',cid]).trim()}));
    const plans=historyPlans(caseName,oracle,r.historyCheck?.samples??[],'commitId');
    r.historicalRestoreMs=0;r.historicalRestoreReadMs=0;r.historicalRestoreCleanupMs=0;r.historicalRestoreSamples=[];
    for(const plan of plans){
     const name='verify-history-'+plan.step;const create=await timed(async()=>{await l.branch.fork(name,plan.id);return mountWorkspace(name);});const historical=create.value;r.historicalRestoreMs+=create.ms;
     const row={step:plan.step,commitId:plan.id,restoreMs:create.ms,verified:false};r.historicalRestoreSamples.push(row);
     try{const verified=await timed(()=>l.workspace.exec(historical,plan.checks));r.historicalRestoreReadMs+=verified.ms;row.readMs=verified.ms;assert.equal(verified.value.exitCode,0);row.verified=true;}finally{const closed=await timed(()=>unmountWorkspace(historical));r.historicalRestoreCleanupMs+=closed.ms;row.cleanupMs=closed.ms;fs.appendFileSync('results/current-restore-samples.jsonl',JSON.stringify({product,case:caseName,round,...row})+'\n');}
    }
    r.fullHistoricalSnapshotReadbacks=plans.length;
    const retained=await l.workspace.exec(second,checks);assert.equal(retained.exitCode,0);
    const mainVerified=await l.workspace.exec(main,checks);assert.equal(mainVerified.exitCode,0);
    r.lifecycle.activeWorkspacesAtSpace=['main','work','second'];
    await unmountWorkspace(second);await unmountWorkspace(ws);await unmountWorkspace(main);
   }finally{
    const errors=[];r.lifecycle.cleanupAttempts=[];
    if(l)for(const view of [...mounted].reverse()){if(unmountAttempted.has(view))continue;const attempt={view,ok:false};r.lifecycle.cleanupAttempts.push(attempt);try{await unmountWorkspace(view);attempt.ok=true;}catch(e){attempt.error=e.message;errors.push(e);}}
    if(l&&sandbox&&!errors.length)try{await l.sandbox.close(sandbox);}catch(e){errors.push(e);}
    if(l)try{await l.close();}catch(e){errors.push(e);}
    if(!errors.length)try{command('docker',['volume','rm',id]);}catch(e){errors.push(e);}
    if(errors.length)throw new AggregateError(errors,'Comparator cleanup failed');
   }
  }
  r.initInclusiveImportForkReadMs=(r.initMs??0)+r.totalImportForkReadMs;
  r.filesystemUsedDeltaBytes=r.activeSpace.filesystemUsedBytes-r.filesystem.empty.filesystemUsedBytes;
  if(r.runtimeReadySpace)r.runtimeReadyDeltaBytes=r.activeSpace.filesystemUsedBytes-r.runtimeReadySpace.filesystemUsedBytes;
  for(const key of ['initMs','importMs','forkToWorkspaceMs','firstFullReadVerifyMs','totalImportForkReadMs','initInclusiveImportForkReadMs','warmForkToWorkspaceMs','warmFirstFullReadMs','warmForkReadMs','filesystemUsedDeltaBytes'])assert.ok(Number.isFinite(r[key])&&r[key]>=0,`Invalid ${key}`);
  for(const metric of [r.activeSpace,r.filesystem.empty,...(r.runtimeReadySpace?[r.runtimeReadySpace]:[])])assert.ok(Number.isFinite(metric.filesystemUsedBytes)&&metric.filesystemUsedBytes>=0);
  const near=(a,b)=>assert.ok(Math.abs(a-b)<=Math.max(0.001,Math.abs(b)*1e-9),'Inconsistent phase sum');
  near(r.totalImportForkReadMs,r.importMs+r.forkToWorkspaceMs+r.firstFullReadVerifyMs);near(r.warmForkReadMs,r.warmForkToWorkspaceMs+r.warmFirstFullReadMs);
  if(caseName.startsWith('history-')){
   for(const key of ['totalWriteMs','totalCommitMs'])assert.ok(Number.isFinite(r.historyCheck[key])&&r.historyCheck[key]>=0);
   assert.equal(r.historyCheck.completed,true);assert.equal(r.historyCheck.acknowledgedCommits,100);assert.equal(r.fullHistoricalSnapshotReadbacks,100);
  }
  r.correct=true;
 }catch(error){r.error={message:error.message,stack:error.stack};failure=error;}
 finally{
  const cleanup=[];
  if(isolated){
   if(fs.existsSync(isolated.runtimeState))try{command('/usr/bin/python3',['feasibility/runtime_storage.py','leave','--state',isolated.runtimeState]);}catch(e){cleanup.push(e.message);}
   if(!cleanup.length)try{command('umount',['-i',isolated.mount]);}catch(e){cleanup.push(e.message);}
  }
  if(cleanup.length){r.correct=false;r.cleanupErrors=cleanup;failure??=new Error('Cleanup failed');}
  save();console.log(json(r));
 }
 if(failure)throw failure;
}
