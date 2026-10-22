// Independent CAS/Overlay series. Prior production and snapshot series are unchanged.
import {LayerFS} from '../layerfs/sdk/js/src/index.js';
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
function save(){fs.writeFileSync('results/cas-comparison.json',json({prototypeOnly:true,mode,rounds,cases,expectedRecords,complete:records.length===expectedRecords&&records.every(r=>r.correct),records,caveats:['See feasibility/CAS-MEASUREMENT-BOUNDARIES.md.', 'Experimental CAS adapter, not production Sprig or feature parity.', 'Unsupported metadata-branch probe omitted from BOTH products.', 'CAS initialization is included in import; actual FUSE readiness charged to first fork.', 'CLI checkpoint process startup versus SDK in-process calls is included and disclosed.', 'Both active workspace lifecycles are retained at physical sampling; each view has its own live FUSE lower.', 'Kernel caches affect warm reads; FUSE processes have separate userspace caches; no cold-cache or equivalent-memory claim.', 'Full runtime accounting includes comparator Docker writable layers and persistent daemon roots.', 'Checkpoint durability differs; final accounting sync outside timers does not establish equivalence.']}));}
for(let round=0;round<rounds;round++)for(const caseName of cases)for(const product of round%2?['layerfs','cas-prototype']:['cas-prototype','layerfs']){
 const r={product,case:caseName,round,correct:false,metadataBranchMs:null,metadataBranchProbe:'omitted on both sides: CAS adapter does not implement branch refs'};records.push(r);
 let isolated=null,failure=null;
 try{
 isolated=fresh(`${product}-${caseName}-${round}`);r.filesystem={mkfs:isolated.mkfs,mountInfo:isolated.mountInfo,empty:isolated.empty};
 const fixture=path.join(cwd,'fixtures',caseName),oracle=JSON.parse(fs.readFileSync(fixture+'.json'));
 r.files=oracle.length;r.logicalBytes=oracle.reduce((sum,f)=>sum+f.bytes,0);
 const checks='('+oracle.map(f=>`printf '%s  %s\\n' '${f.sha256}' '${f.path}'`).join(';')+') | sha256sum -c -';
  if(product==='cas-prototype'){
   const args=['feasibility/cas_sample.py','run','--root',path.join(isolated.mount,'store'),'--source',fixture,'--oracle',fixture+'.json','--binary',path.join(cwd,'feasibility/cas-projection/target/release/sprig-cas-projection-prototype')];
   const recordDir=path.join(process.env.RUNNER_TEMP,'cas-paired-records');fs.mkdirSync(recordDir,{recursive:true});args.push('--records',path.join(recordDir,`cas-${caseName}-${round}-steps.jsonl`));
   if(caseName.startsWith('history-'))args.push('--steps',fixture+'-steps.json');
   let native;try{native=JSON.parse(command('/usr/bin/python3',args));}catch(error){r.nativeFailureOutput=error.stdout?.toString();r.nativeFailureStderr=error.stderr?.toString();throw error;}r.native=native;assert.equal(native.ok,true);assert.equal(native.prototype_only,true);
   r.initMs=null;r.initializationIncludedInImport=true;r.lifecycle=native.lifecycle;
   for(const [key,field] of Object.entries({importMs:'import_seconds',forkToWorkspaceMs:'first_fork_seconds',firstFullReadVerifyMs:'first_read_seconds',totalImportForkReadMs:'total_import_fork_read_seconds',warmForkToWorkspaceMs:'warm_fork_seconds',warmFirstFullReadMs:'warm_read_seconds',warmForkReadMs:'warm_total_seconds'}))r[key]=native[field]*1000;
   if(caseName.startsWith('history-')){assert.equal(native.history_distinct_revisions,100);assert.equal(native.checkpoint_steps.length,100);r.historyCheck={totalWriteMs:native.write_seconds*1000,totalCommitMs:native.checkpoint_seconds*1000,acknowledgedCommits:100,completed:true,samples:native.checkpoint_steps};}
   r.activeSpace=native.activeSpace;r.fullHistoricalSnapshotReadbacks=native.fullHistoricalSnapshotReadbacks;
   assert.equal(r.fullHistoricalSnapshotReadbacks,caseName.startsWith('history-')?100:0);
   assert.equal(native.remainingMounts.length,0);assert.equal(native.lifecycle.cleanup.complete,true);assert.equal(native.lifecycle.activeAtSpace.views.length,2);assert.equal(native.lifecycle.activeAtSpace.foregroundFuseProcesses.length,2);assert.equal(native.lifecycle.activeAtSpace.historicalReadbacksStarted,false);assert.equal(native.lifecycle.activeAtSpace.controlProcessesRunning,2);assert.equal(native.originalSecondViewUnchanged,true);assert.equal(native.allAcknowledgedIdsPresent,true);
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
   const l=new LayerFS(id,{storePath});r.initMs=performance.now()-setupStart;r.lifecycle={fileTreesRetained:true,controlProcessExited:false,reopenImplemented:true};
   try{
    let t=await timed(()=>l.project.init(fixture));r.importMs=t.ms;
    t=await timed(async()=>{await l.branch.fork('work','main');return l.workspace.mount('work');});const ws=t.value;r.forkToWorkspaceMs=t.ms;
    t=await timed(()=>l.workspace.exec(ws,checks));assert.equal(t.value.exitCode,0);r.firstFullReadVerifyMs=t.ms;r.totalImportForkReadMs=r.importMs+r.forkToWorkspaceMs+r.firstFullReadVerifyMs;
    t=await timed(async()=>{await l.branch.fork('second','main');return l.workspace.mount('second');});const second=t.value;r.warmForkToWorkspaceMs=t.ms;
    t=await timed(()=>l.workspace.exec(second,checks));assert.equal(t.value.exitCode,0);r.warmFirstFullReadMs=t.ms;r.warmForkReadMs=r.warmForkToWorkspaceMs+r.warmFirstFullReadMs;
    if(caseName.startsWith('history-'))await checkHistory(caseName,{
      exec:async cmd=>{const x=await l.workspace.exec(ws,cmd);assert.equal(x.exitCode,0);return x;},
      commit:async msg=>l.workspace.commit(ws,msg),
      onSample:async sample=>fs.appendFileSync('results/cas-history-samples.jsonl',JSON.stringify({product,case:caseName,round,...sample})+'\n'),
      history:async()=>{const all=[];let more=true;while(more){const page=await l.branch.list_commits('work',1000,all.length);assert.ok(page.items.length||!page.hasMore);all.push(...page.items);more=page.hasMore;}return all;}
    },r.historyCheck={});
    assert.equal(command('stat',['-f','-c','%T',storePath]).trim(),'btrfs');r.storeFilesystemVerified='btrfs';
    r.activeSpace=space(isolated.mount);
    r.containerInventory=command('docker',['ps','-aq','--filter','volume='+id]).trim().split('\n').filter(Boolean).map(cid=>({id:cid,graphDriver:JSON.parse(command('docker',['inspect','--format','{{json .GraphDriver}}',cid])),logPath:command('docker',['inspect','--format','{{.LogPath}}',cid]).trim()}));
    const plans=historyPlans(caseName,oracle,r.historyCheck?.samples??[],'commitId');
    for(const plan of plans){
     const name='verify-history-'+plan.step;await l.branch.fork(name,plan.id);const historical=await l.workspace.mount(name);
     try{const verified=await l.workspace.exec(historical,plan.checks);assert.equal(verified.exitCode,0);}finally{await l.workspace.unmount(historical,true);}
    }
    r.fullHistoricalSnapshotReadbacks=plans.length;
    const retained=await l.workspace.exec(second,checks);assert.equal(retained.exitCode,0);
    await l.workspace.unmount(second,true);await l.workspace.unmount(ws,true);
   }finally{
    const errors=[];try{await l.close();}catch(e){errors.push(e);}
    try{const containers=command('docker',['ps','-aq','--filter','volume='+id]).trim().split('\n').filter(Boolean);if(containers.length)command('docker',['rm','-f',...containers]);command('docker',['volume','rm',id]);}catch(e){errors.push(e);}
    if(errors.length)throw new AggregateError(errors,'Comparator cleanup failed');
   }
  }
  r.initInclusiveImportForkReadMs=(r.initMs??0)+r.totalImportForkReadMs;
  r.filesystemUsedDeltaBytes=r.activeSpace.filesystemUsedBytes-r.filesystem.empty.filesystemUsedBytes;
  if(r.runtimeReadySpace)r.runtimeReadyDeltaBytes=r.activeSpace.filesystemUsedBytes-r.runtimeReadySpace.filesystemUsedBytes;
  for(const key of ['importMs','forkToWorkspaceMs','firstFullReadVerifyMs','totalImportForkReadMs','initInclusiveImportForkReadMs','warmForkToWorkspaceMs','warmFirstFullReadMs','warmForkReadMs','filesystemUsedDeltaBytes'])assert.ok(Number.isFinite(r[key])&&r[key]>=0,`Invalid ${key}`);
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
