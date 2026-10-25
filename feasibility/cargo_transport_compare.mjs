// Separate tiny real-Cargo lifecycle; never substitutes for frozen seven scenes.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {performance} from 'node:perf_hooks';
import {runCargoLayerfs} from './cargo_layerfs.mjs';
assert.equal(process.env.GITHUB_ACTIONS,'true');assert.equal(process.getuid(),0);
assert.ok(path.isAbsolute(process.env.RUNNER_TEMP||''));
const cwd=process.cwd(),mode=process.env.CARGO_MODE||'smoke';assert.ok(['smoke','full'].includes(mode));
const rounds=mode==='smoke'?1:3,records=[];
const image=process.env.CARGO_IMAGE,archive=process.env.CARGO_IMAGE_ARCHIVE;
assert.match(image||'',/^sha256:[0-9a-f]{64}$/);assert.ok(path.isAbsolute(archive||''));
const command=(p,a)=>execFileSync(p,a,{encoding:'utf8',maxBuffer:128*1024**2});
const json=x=>JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v,2);
const recordDir=path.join(process.env.RUNNER_TEMP,'cargo-transport-records');fs.mkdirSync(recordDir,{recursive:true});
function space(mount){
 command('btrfs',['filesystem','sync',mount]);
 const usageRaw=command('btrfs',['filesystem','usage','-b',mount]);
 const groupsRaw=command('btrfs',['filesystem','df','-b',mount]);
 const match=usageRaw.match(/^\s*Used:\s*(\d+)\s*$/m);assert.ok(match);
 return {filesystemUsedBytes:Number(match[1]),usageRaw,groupsRaw};
}
function allocate(label){
 const dir=fs.mkdtempSync(path.join(process.env.RUNNER_TEMP,'cargo-paired-'+label+'-'));
 return {dir,imagePath:path.join(dir,'new.img'),mount:path.join(dir,'mount'),runtimeState:path.join(dir,'runtime-state.json')};
}
function prepare(isolated){
 const {imagePath,mount}=isolated;
 const fd=fs.openSync(imagePath,'wx',0o600);fs.ftruncateSync(fd,8*1024**3);fs.closeSync(fd);fs.mkdirSync(mount);
 const info=fs.lstatSync(imagePath);assert.ok(info.isFile()&&!info.isSymbolicLink());
 isolated.imageIdentity={dev:String(info.dev),ino:String(info.ino)};
 isolated.mkfs=command('mkfs.btrfs',['-d','single','-m','dup',imagePath]);
 command('mount',['-o','loop,noatime',imagePath,mount]);
 assert.equal(command('stat',['-f','-c','%T',mount]).trim(),'btrfs');
 isolated.empty=space(mount);
}
function diagnosis(isolated){
 const result={paths:isolated};
 for(const [key,program,args] of [['mounts','findmnt',['-J','-T',isolated.mount]],['loop','losetup',['-j',isolated.imagePath]]]){
  try{result[key]=command(program,args);}catch(e){result[key]={status:e.status,stdout:e.stdout?.toString(),stderr:e.stderr?.toString()};}
 }
 return result;
}
function atomicReport(file,body){const tmp=file+'.'+process.pid+'.new';const fd=fs.openSync(tmp,'w',0o644);try{fs.writeFileSync(fd,body);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(tmp,file);const dir=fs.openSync(path.dirname(file),'r');try{fs.fsyncSync(dir);}finally{fs.closeSync(dir);}}
function save(){atomicReport('results/cargo-transport-comparison.json',json({mode,rounds,expectedRecords:rounds*4,complete:records.length===rounds*4&&records.every(r=>r.correct),productionSha:'2a01fe445b8057ca49b4e8284fdd5583bbb4185c',comparatorSha:'9f97a7ec95b662e9cb288704afa165feff132cfa',sprigCompressionPolicy:'auto (default init)',records,notes:['Separate dependency-free Cargo lifecycle, not seven-case history100.', 'Same immutable compiler/runtime image, root generation-scoped cooperative Docker sessions versus UID501 persistent SDK transport. Both retain live compiler runtime at space; all start/exec/exit/removal costs stay in whole wall. This is not directly comparable to the earlier per-command-container series.', 'Runtime setup and software baseline reported separately from full sample wall.', 'Both retain target/cache and three live views at final space.', 'Raw per-product stdout JSON preserves exact integer nanoseconds; parsed diagnostics may not.']}));}
for(let round=0;round<rounds;round++)for(const incremental of [0,1])for(const product of round%2?['layerfs','sprig-writable']:['sprig-writable','layerfs']){
 const r={product,incremental,round,correct:false};records.push(r);let isolated=null,error=null;
 try{
  assert.equal(command('git',['-C','sprig','rev-parse','HEAD']).trim(),'2a01fe445b8057ca49b4e8284fdd5583bbb4185c');
  assert.equal(command('git',['-C','layerfs','rev-parse','HEAD']).trim(),'9f97a7ec95b662e9cb288704afa165feff132cfa');
  isolated=allocate(`${product}-${incremental}-${round}`);r.filesystem=isolated;save();prepare(isolated);
  const begin=performance.now();
  r.runtime=JSON.parse(command('/usr/bin/python3',['feasibility/runtime_storage.py','enter','--state',isolated.runtimeState,'--mount',isolated.mount,'--archive',archive,'--image',image]));
  r.runtimeSetupSeconds=(performance.now()-begin)/1000;r.runtimeReadySpace=space(isolated.mount);
  const root=path.join(isolated.mount,'sample'),source=path.join(cwd,'fixtures/cargo'),oracle=path.join(cwd,'feasibility/cargo-fixture-oracle.json');
  const ledger=path.join(recordDir,`${product}-${incremental}-${round}.jsonl`);
  const rawPath=`results/cargo-transport-${product}-${incremental}-${round}.json`;
  if(product==='sprig-writable'){
   const args=['feasibility/cargo_transport_sample.py','run','--root',root,'--source',source,'--oracle',oracle,'--binary',path.join(cwd,'sprig/target/release/sprig'),'--backend','writable','--production-sha','2a01fe445b8057ca49b4e8284fdd5583bbb4185c','--incremental',String(incremental),'--image',image,'--records',ledger];
   let raw;try{raw=command('/usr/bin/python3',args);}catch(e){if(e.stdout)fs.writeFileSync(rawPath,e.stdout);r.failureStderr=e.stderr?.toString();throw e;}
   fs.writeFileSync(rawPath,raw);r.sample=JSON.parse(raw);
  }else{
   r.sample=await runCargoLayerfs({root,measuredMount:isolated.mount,source,oraclePath:oracle,layerfsSdkPath:path.join(cwd,'layerfs/api/agent/sdk/src/index.js'),daemonPath:process.env.LAYERFS_DAEMON,image,incremental,recordsPath:ledger});
   fs.writeFileSync(rawPath,json(r.sample));
  }
  r.rawReportPath=rawPath;const sample=r.sample;
  assert.equal(sample.ok,true);assert.ok(!sample.testOnly);assert.equal(sample.incremental,incremental);
  assert.equal(sample.image,image);assert.equal(sample.production_sha,product==='layerfs'?'9f97a7ec95b662e9cb288704afa165feff132cfa':'2a01fe445b8057ca49b4e8284fdd5583bbb4185c');assert.equal(sample.backend,product==='layerfs'?'fuse':'writable');if(product==='sprig-writable')assert.equal(sample.compressionPolicy,'auto (default init)');
  if(product==='sprig-writable'){assert.equal(sample.lifecycle.activeAtSpace.retainedGenerationCount,4);assert.equal(sample.lifecycle.activeAtSpace.foregroundFuseProcesses.length,3);
   const compiler=sample.lifecycle.activeAtSpace.compilerContainer;assert.equal(compiler.count,1);assert.equal(compiler.image,image);assert.equal(compiler.inspection.state.Running,true);
   const second=sample.lifecycle.activeAtSpace.views.find(v=>v.name==='second');assert.ok(second);assert.equal(compiler.generation,second.generation);assert.equal(compiler.tree,second.path);
   assert.equal(sample.compilerSessions.length,4);assert.ok(sample.compilerSessions.every(c=>c.removed===true&&c.uncertain===false));
   for(const key of ['checkpointCompilerQuiescePlusProduct','restoreToCompilerReady'])assert.ok(Number.isFinite(sample.convenience_seconds[key])&&sample.convenience_seconds[key]>=0,key);
  }
  for(const phase of ['noop_build','restored_rebuild']){const rows=sample.cargoBuildObservations.filter(x=>x.phase===phase);assert.equal(rows.length,1);assert.equal(rows[0].returncode,0);assert.ok(rows[0].freshLines.some(line=>/Fresh\s+owned-cargo-check\b/.test(line)));assert.equal(rows[0].compilingLines.length,0);}
  assert.ok(Number.isFinite(sample.activeSpace.filesystemUsedBytes)&&sample.activeSpace.filesystemUsedBytes>=0);
  assert.equal(sample.fullRestoredTreeVerified,true);assert.equal(sample.originalMainViewUnchanged,true);assert.equal(sample.sourceUnchanged,true);assert.equal(sample.allAcknowledgedIdsPresent,true);assert.equal(sample.lifecycle.cleanup.complete,true);
  assert.equal(sample.lifecycle.activeAtSpace.views.length,3);assert.deepEqual(sample.remainingMounts,[]);assert.deepEqual(sample.remainingContainers,[]);
  for(const key of ['preflight','init','import','fork','fixture_verify','cargo_setup','clean_build','clean_execute','noop_build','noop_execute','edit','edit_build','edit_execute','pre_checkpoint_oracle','checkpoint_cli','checkpoint_readiness','checkpoint','restore','restore_verify','restored_execute','restored_rebuild','restored_rebuild_execute','retained_input_verify','space','cleanup'])assert.ok(Number.isFinite(sample.phase_seconds[key])&&sample.phase_seconds[key]>=0,key);
  assert.ok(Number.isFinite(sample.full_task_seconds)&&sample.full_task_seconds>=0);
  assert.ok(Math.abs(sample.phase_seconds.checkpoint-sample.phase_seconds.checkpoint_cli-sample.phase_seconds.checkpoint_readiness)<1e-6);
  r.activeSpace=sample.activeSpace;r.runtimeReadyDeltaBytes=r.activeSpace.filesystemUsedBytes-r.runtimeReadySpace.filesystemUsedBytes;r.emptyFsDeltaBytes=r.activeSpace.filesystemUsedBytes-r.filesystem.empty.filesystemUsedBytes;
  assert.ok(Number.isFinite(r.runtimeReadyDeltaBytes)&&r.runtimeReadyDeltaBytes>=0);r.correct=true;
 }catch(e){error=e;r.error={message:e.message,stack:e.stack};}
 finally{
  r.cleanup=[];
  if(isolated){
   if(fs.existsSync(isolated.runtimeState))try{command('/usr/bin/python3',['feasibility/runtime_storage.py','leave','--state',isolated.runtimeState]);r.cleanup.push('runtime restored');}catch(e){r.cleanupErrors=[e.message];error??=e;}
   if(!error)try{
    command('umount',['-i',isolated.mount]);
    assert.equal(command('losetup',['-j',isolated.imagePath]).trim(),'');
    assert.ok(isolated.dir.startsWith(path.join(process.env.RUNNER_TEMP,'cargo-paired-')));
    const current=fs.lstatSync(isolated.imagePath);assert.ok(current.isFile()&&!current.isSymbolicLink());
    assert.deepEqual({dev:String(current.dev),ino:String(current.ino)},isolated.imageIdentity);
    r.cleanup.push('normal unmount and detached image verified; raw durable before image disposal');save();
    for(const file of ['results/cargo-transport-comparison.json',r.rawReportPath]){const f=fs.openSync(file,'r');try{fs.fsyncSync(f);}finally{fs.closeSync(f);}}
    const resultsFd=fs.openSync('results','r');try{fs.fsyncSync(resultsFd);}finally{fs.closeSync(resultsFd);}
    fs.unlinkSync(isolated.imagePath);r.cleanup.push('normal unmount, detached synthetic image removed');
   }catch(e){(r.cleanupErrors??=[]).push(e.message);error??=e;}
  }
  if(error){r.correct=false;if(isolated)r.failureFilesystem=diagnosis(isolated);}save();console.log(json({product,round,incremental,correct:r.correct,error:r.error,cleanupErrors:r.cleanupErrors}));
 }
 if(error)throw error;
}
