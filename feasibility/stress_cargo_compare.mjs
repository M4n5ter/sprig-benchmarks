// NEW DAG16 protocol. Frozen tiny-Cargo helpers/reports remain unchanged.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {performance} from 'node:perf_hooks';
import {createHash} from 'node:crypto';
import {AB_SCHEMA,validateProducts,sampleOrder,validateOwnPreviousGate} from './stress_cargo_own_ab.mjs';
import {SOURCE_SHA,loadCommands,verifyCargoPackages} from './stress_cargo_layerfs.mjs';
// Cargo-only resource revision: fixed4GiB first, no automatic fallback/resizing.
export const IMAGE_BYTES=4*1024**3;
export const RESOURCE_PROTOCOL='sprig-cargo-resource-4g-v1';
const MIB=1024**2;
const sha=x=>createHash('sha256').update(x).digest('hex');
const json=x=>JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v,2);
const command=(p,a)=>execFileSync(p,a.map(String),{encoding:'utf8',maxBuffer:128*1024**2});
const expectedPackages=Array.from({length:16},(_,i)=>'node'+String(i).padStart(3,'0')).concat('stress-app');
export class CapacityBlocked extends Error {}
export class BudgetBlocked extends Error {}
export function budgetAdmission({startedEpochSeconds,deadlineEpochSeconds,nowEpochSeconds,workReserveSeconds=180,cleanupReserveSeconds=300}){
 for(const value of [startedEpochSeconds,deadlineEpochSeconds,nowEpochSeconds,workReserveSeconds,cleanupReserveSeconds])assert.ok(Number.isFinite(value)&&value>=0,'invalid shared job budget');
 assert.ok(deadlineEpochSeconds>startedEpochSeconds&&deadlineEpochSeconds-startedEpochSeconds<=40*60,'job admission deadline must fit40min inside45min workflow');
 assert.ok(workReserveSeconds>=180&&cleanupReserveSeconds>=300,'minimum operation and cleanup reserve required');
 const remainingSeconds=deadlineEpochSeconds-nowEpochSeconds,requiredSeconds=workReserveSeconds+cleanupReserveSeconds;
 if(remainingSeconds<requiredSeconds)throw new BudgetBlocked(`shared job budget blocked: remaining ${remainingSeconds}s, required ${requiredSeconds}s; no next sample started`);
 return {startedEpochSeconds,deadlineEpochSeconds,remainingSeconds,workReserveSeconds,cleanupReserveSeconds,requiredSeconds,admitted:true};
}
export function admitSampler(record,admitBudget){
 record.postRuntimeBudgetAdmission=admitBudget();
}
export function capacityGuard({availableBytes,deviceBytes,targetAllocatedBytes,fixtureLogicalBytes}){
 for(const [key,value]of Object.entries({availableBytes,deviceBytes,targetAllocatedBytes,fixtureLogicalBytes}))assert.ok(Number.isSafeInteger(value)&&value>=0,`invalid ${key}`);
 assert.equal(deviceBytes,IMAGE_BYTES,'measured filesystem must remain exactly 4GiB');
 assert.ok(targetAllocatedBytes>0,'capacity requires a real measured target allocation');
 const requiredBytes=Math.max(512*MIB,4*targetAllocatedBytes+8*fixtureLogicalBytes+256*MIB);assert.ok(Number.isSafeInteger(requiredBytes),'capacity arithmetic exceeds safe integer range');
 if(availableBytes<requiredBytes)throw new CapacityBlocked(`capacity blocked: available ${availableBytes}, required ${requiredBytes}; 4GiB Cargo resource bound`);
 return {availableBytes,requiredBytes,deviceBytes,targetAllocatedBytes,fixtureLogicalBytes,admitted:true};
}
export function validateCapacity(document,identity,incremental){
 assert.equal(document.schema,'sprig-stress-cargo-capacity-v1');
 for(const key of ['image','protocolSha256','fixtureManifestSha256'])assert.equal(document[key],identity[key],`capacity ${key} mismatch`);
 assert.equal(document.toolchain?.rustc,'1.90.0');assert.equal(document.toolchain?.cargo,'1.90.0');
 assert.ok(Array.isArray(document.pilots));assert.equal(document.pilots.length,2);
 assert.deepEqual(document.pilots.map(x=>x.incremental).sort(),[0,1]);
 for(const pilot of document.pilots)assert.ok(Number.isSafeInteger(pilot.targetAllocatedBytes)&&pilot.targetAllocatedBytes>0,'missing measured pilot target allocation');
 return document.pilots.find(x=>x.incremental===incremental);
}
export function validateFresh(sample){
 for(const phase of ['clean_build','noop_build','edit_build','restored_rebuild']){
  const rows=sample.cargoBuildObservations?.filter(x=>x.phase===phase);assert.equal(rows?.length,1,`missing unique ${phase}`);
  const row=rows[0];assert.equal(row.returncode,0);
  verifyCargoPackages([...(row.freshLines??[]),...(row.compilingLines??[])].join('\n'),expectedPackages,phase);
 }
}
export function validatePreviousGate(gate,identity){
 assert.equal(gate.schema,'sprig-stress-cargo-comparison-v2');assert.equal(gate.complete,true);assert.equal(gate.status,'passed');assert.equal(gate.incremental,0);
 for(const key of ['image','protocolSha256','fixtureManifestSha256','productionSha','comparatorSha','imageBytes','resourceProtocol'])assert.equal(gate[key],identity[key],`incremental prerequisite ${key} mismatch`);
 assert.ok(Array.isArray(gate.records)&&gate.records.length===2*gate.rounds&&[1,3].includes(gate.rounds));
 for(let round=0;round<gate.rounds;round++)for(const product of ['sprig-writable','layerfs']){
  const rows=gate.records.filter(x=>x.round===round&&x.product===product);assert.equal(rows.length,1);
  const row=rows[0];assert.equal(row.correct,true);assert.equal(row.incremental,0);assert.equal(row.sample?.ok,true);assert.ok(!row.sample.testOnly);assert.equal(row.sample.image,identity.image);assert.equal(row.sample.protocolSha256,identity.protocolSha256);
  assert.equal(row.sample.production_sha,product==='layerfs'?identity.comparatorSha:identity.productionSha);validateFresh(row.sample);
  assert.equal(row.sample.fullRestoredTreeVerified,true);assert.equal(row.sample.lifecycle?.cleanup?.complete,true);assert.deepEqual(row.sample.remainingMounts,[]);assert.deepEqual(row.sample.remainingContainers,[]);
 }
 return true;
}
export function cleanupAdmission({sampleStarted,runtimeAttempted,runtimeReady,runtimeState,sample}){
 if(sampleStarted){
  if(!sample||typeof sample!=='object')return 'sampler report missing or malformed';
  if(sample.error?.uncertain||sample.compilerSessions?.some(s=>s.uncertain))return 'uncertain mutation/exec outcome';
  if(sample.lifecycle?.cleanup?.complete!==true)return 'normal sampler cleanup unconfirmed';
  if(!Array.isArray(sample.remainingMounts)||sample.remainingMounts.length)return 'zero mounts unconfirmed';
  if(!Array.isArray(sample.remainingContainers)||sample.remainingContainers.length)return 'zero containers unconfirmed';
  if(sample.product==='layerfs'&&(sample.remainingMountsKnown!==true||sample.remainingContainersKnown!==true))return 'comparator inventory knowledge missing';
 }
 if(runtimeAttempted&&!runtimeReady&&runtimeState?.restored!==true)return 'runtime setup rollback incomplete or unconfirmed (including absent state)';
 return null;
}
function atomicReport(file,value){const tmp=file+'.'+process.pid+'.new',fd=fs.openSync(tmp,'w',0o644);try{fs.writeFileSync(fd,json(value)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(tmp,file);const dir=fs.openSync(path.dirname(file),'r');try{fs.fsyncSync(dir);}finally{fs.closeSync(dir);}}
function physicalSpace(mount){
 command('btrfs',['filesystem','sync',mount]);
 const usageRaw=command('btrfs',['filesystem','usage','-b',mount]),groupsRaw=command('btrfs',['filesystem','df','-b',mount]);
 const used=usageRaw.match(/^\s*Used:\s*(\d+)\s*$/m),device=usageRaw.match(/^\s*Device size:\s*(\d+)\s*$/m);assert.ok(used&&device);
 const stats=fs.statfsSync(mount,{bigint:true});
 return {filesystemUsedBytes:Number(used[1]),deviceBytes:Number(device[1]),availableBytes:Number(stats.bavail*stats.bsize),usageRaw,groupsRaw};
}
function verifyArchive(sample){
 assert.ok(Array.isArray(sample.completeLogArchive)&&sample.completeLogArchive.length>0,'full log archive missing');
 for(const row of sample.completeLogArchive){const file=fs.lstatSync(row.archived);assert.ok(file.isFile()&&!file.isSymbolicLink());const bytes=fs.readFileSync(row.archived);assert.equal(bytes.length,row.bytes);assert.equal(sha(bytes),row.sha256);const fd=fs.openSync(row.archived,'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}}
}
function validateSample(sample,product,identity,incremental){
 assert.equal(sample.ok,true);assert.ok(!sample.testOnly);assert.equal(sample.incremental,incremental);assert.equal(sample.image,identity.image);assert.equal(sample.protocolSha256,identity.protocolSha256);
 assert.equal(sample.production_sha,product==='layerfs'?identity.comparatorSha:identity.productionSha);assert.equal(sample.backend,product==='layerfs'?'fuse':'writable');
 if(product==='sprig-writable'){
  assert.equal(sample.compressionPolicy,'auto (default init)');assert.equal(sample.lifecycle.activeAtSpace.retainedGenerationCount,4);assert.equal(sample.lifecycle.activeAtSpace.foregroundFuseProcesses.length,3);
  const compiler=sample.lifecycle.activeAtSpace.compilerContainer,second=sample.lifecycle.activeAtSpace.views.find(v=>v.name==='second');assert.equal(compiler.count,1);assert.equal(compiler.image,identity.image);assert.equal(compiler.inspection.state.Running,true);assert.equal(compiler.generation,second.generation);assert.equal(compiler.tree,second.path);
  assert.equal(sample.compilerSessions.length,4);assert.ok(sample.compilerSessions.every(c=>c.removed===true&&c.uncertain===false&&c.naturalExitAndPidGoneVerified===true));
  for(const key of ['checkpointCompilerQuiescePlusProduct','restoreToCompilerReady'])assert.ok(Number.isFinite(sample.convenience_seconds[key])&&sample.convenience_seconds[key]>=0,key);
 }
 validateFresh(sample);
 for(const key of ['fullRestoredTreeVerified','originalMainViewUnchanged','sourceUnchanged','allAcknowledgedIdsPresent'])assert.equal(sample[key],true,key);
 assert.equal(sample.lifecycle.cleanup.complete,true);assert.equal(sample.lifecycle.activeAtSpace.views.length,3);assert.deepEqual(sample.remainingMounts,[]);assert.deepEqual(sample.remainingContainers,[]);
 const artifacts=sample.artifactChecks;assert.ok(Array.isArray(artifacts));
 for(const phase of ['clean_artifacts','noop_artifacts','edit_artifacts','restored_artifacts','restored_rebuild_artifacts']){const found=artifacts.filter(x=>x.phase===phase);assert.equal(found.length,1);assert.equal(found[0].ok,true);assert.equal(found[0].hardlinkProbe,true);assert.equal(found[0].exactMtime,true);assert.ok(found[0].generatedFiles.length>0);assert.equal(found[0].buildValue,['clean_artifacts','noop_artifacts'].includes(phase)?1:2);}
 for(const key of ['preflight','init','import','fork','fixture_verify','cargo_setup','toolchain_verify','clean_build','target_probe','clean_artifacts','clean_execute','noop_build','noop_artifacts','noop_execute','edit','edit_build','edit_artifacts','edit_execute','pre_checkpoint_oracle','checkpoint_cli','checkpoint_readiness','checkpoint','restore','restore_verify','restored_artifacts','restored_execute','restored_rebuild','restored_rebuild_artifacts','restored_rebuild_execute','retained_input_verify','space','cleanup'])assert.ok(Number.isFinite(sample.phase_seconds[key])&&sample.phase_seconds[key]>=0,key);
 assert.ok(Number.isFinite(sample.full_task_seconds)&&sample.full_task_seconds>=0);assert.ok(Math.abs(sample.phase_seconds.checkpoint-sample.phase_seconds.checkpoint_cli-sample.phase_seconds.checkpoint_readiness)<1e-6);
 assert.ok(Number.isFinite(sample.activeSpace.filesystemUsedBytes)&&sample.activeSpace.filesystemUsedBytes>=0);verifyArchive(sample);
}
export async function main(){
 assert.equal(process.env.GITHUB_ACTIONS,'true');assert.equal(process.getuid(),0);assert.ok(path.isAbsolute(process.env.RUNNER_TEMP??''));
 assert.ok(['0','1'].includes(process.env.STRESS_CARGO_INCREMENTAL),'explicit single incremental required');
 assert.equal(process.env.SPRIG_LIFECYCLE_TRACE,undefined,'diagnostics forbidden in formal Cargo acceptance');
 const jobStarted=Number(process.env.STRESS_CARGO_JOB_STARTED_EPOCH),jobDeadline=Number(process.env.STRESS_CARGO_JOB_DEADLINE_EPOCH);
 const invocationEpoch=Date.now()/1000,invocationMonotonic=performance.now();
 const admitBudget=()=>budgetAdmission({startedEpochSeconds:jobStarted,deadlineEpochSeconds:jobDeadline,nowEpochSeconds:invocationEpoch+(performance.now()-invocationMonotonic)/1000});
 const incremental=Number(process.env.STRESS_CARGO_INCREMENTAL),rounds=Number(process.env.STRESS_CARGO_ROUNDS??'1');assert.ok([1,3].includes(rounds));
 const ownAB=process.env.STRESS_CARGO_AB_PRODUCTS!==undefined;
 const cwd=process.cwd(),productionSha=process.env.SPRIG_STRESS_SHA,comparatorSha=SOURCE_SHA,image=process.env.CARGO_IMAGE,archive=process.env.CARGO_IMAGE_ARCHIVE;
 if(!ownAB)assert.match(productionSha??'',/^[a-f0-9]{40}$/);assert.match(image??'',/^sha256:[a-f0-9]{64}$/);assert.ok(path.isAbsolute(archive??''));
 let abBytes=null,abProducts=null;
 if(ownAB){
  assert.equal(rounds,1,'initial own A/B permits one pair per mode');assert.equal(productionSha,undefined,'ambiguous single source and own A/B manifest');
  assert.ok(path.isAbsolute(process.env.STRESS_CARGO_AB_PRODUCTS));abBytes=fs.readFileSync(process.env.STRESS_CARGO_AB_PRODUCTS);abProducts=validateProducts(JSON.parse(abBytes));
 }
 const sharedJobBudget={startedEpochSeconds:jobStarted,deadlineEpochSeconds:jobDeadline,minimumSampleSeconds:180,cleanupReserveSeconds:300,scope:'same absolute first-step deadline across setup and incremental invocations; no reset'};
 const verifyABInputs=()=>{
  assert.ok(fs.readFileSync(process.env.STRESS_CARGO_AB_PRODUCTS).equals(abBytes),'A/B manifest changed');
  for(const p of abProducts){
   assert.equal(fs.realpathSync(p.sourcePath),p.sourcePath,'canonical source path required');assert.equal(fs.realpathSync(p.binary),p.binary,'canonical binary path required');
   assert.equal(command('git',['-C',p.sourcePath,'rev-parse','HEAD']).trim(),p.sha);
   assert.equal(command('git',['-C',p.sourcePath,'status','--porcelain']).trim(),'','source worktree changed');
   const st=fs.lstatSync(p.binary);assert.ok(st.isFile()&&!st.isSymbolicLink(),'fixed regular binary required');assert.equal(sha(fs.readFileSync(p.binary)),p.binarySha256,'fixed binary changed');
  }
 };
 if(ownAB)verifyABInputs();
 const source=path.join(cwd,'fixtures/stress-cargo'),oracle=path.join(cwd,'results/stress-cargo-oracle.json'),manifestPath=path.join(cwd,'results/stress-cargo-manifest.json');
 const manifestRaw=fs.readFileSync(manifestPath),manifest=JSON.parse(manifestRaw),protocolSha256=loadCommands().sha256,fixtureManifestSha256=sha(manifestRaw);
 const identity={image,productionSha,comparatorSha,protocolSha256,fixtureManifestSha256,imageBytes:IMAGE_BYTES,resourceProtocol:RESOURCE_PROTOCOL};
 if(ownAB){delete identity.productionSha;delete identity.comparatorSha;Object.assign(identity,{abProducts,abManifestSha256:sha(abBytes),sharedJobBudget});}assert.equal(manifest.protocolSha256,protocolSha256);
 const capacity=JSON.parse(fs.readFileSync('results/stress-cargo-capacity.json','utf8')),pilot=validateCapacity(capacity,identity,incremental);
 const fixtureFiles=manifest.initial.entries.filter(x=>x.type==='file');assert.ok(fixtureFiles.every(x=>Number.isSafeInteger(x.size)&&x.size>=0));const fixtureLogicalBytes=fixtureFiles.reduce((sum,x)=>sum+x.size,0);assert.ok(Number.isSafeInteger(fixtureLogicalBytes));
 let previousGate=null;if(incremental===1){assert.ok(path.isAbsolute(process.env.STRESS_CARGO_PREVIOUS_GATE??''),'incremental1 requires explicit previous gate');const bytes=fs.readFileSync(process.env.STRESS_CARGO_PREVIOUS_GATE);if(ownAB)validateOwnPreviousGate(JSON.parse(bytes),identity,(sample,p,mode)=>validateSample(sample,'sprig-writable',{...identity,productionSha:p.sha},mode));else validatePreviousGate(JSON.parse(bytes),identity);previousGate={path:process.env.STRESS_CARGO_PREVIOUS_GATE,sha256:sha(bytes)};}
 const recordRoot=path.join(process.env.RUNNER_TEMP,'stress-cargo-records');fs.mkdirSync(recordRoot,{recursive:true});const recordDir=path.join(recordRoot,`inc${incremental}`);fs.mkdirSync(recordDir,{recursive:false});
 const reportPath=`results/stress-cargo-${ownAB?'own-ab':'comparison'}-${incremental}.json`,records=[];
 if(ownAB){const fd=fs.openSync(reportPath,'wx',0o644);fs.closeSync(fd);}
 const report={schema:ownAB?AB_SCHEMA:'sprig-stress-cargo-comparison-v2',status:'running',complete:false,incremental,rounds,expectedRecords:rounds*2,...identity,previousGate,capacityPilot:pilot,imageBytes:IMAGE_BYTES,records,notes:['Cargo-only resource revision: fresh symmetric4GiB images, not pooled with2GiB capacity failures; no automatic8GiB retry.', 'New DAG16 protocol; never pooled with frozen tiny Cargo results.','Whole Used includes immutable image, runtime state, target/cache/logs/history; runtime setup separately timed but baseline bytes never subtracted from primary space.','WholeSampleSubprocessWallSeconds is matched sampler process launch-through-exit including evidence serialization and normal cleanup; internal phases overlap, not additive.','Both products use identical image; Sprig compiler lifetime remains generation-scoped, LayerFS UID501 SDK transport is persistent; no equal durability claim.']};
 report.sharedJobBudget=sharedJobBudget;
 if(ownAB)report.notes[4]='Within-Sprig ordinary positive workloads; same sampler/transport/durability, fixed distinct source and binary identities. One pair per mode, no statistical claim.';
 const save=()=>atomicReport(reportPath,report);save();
 try{
  for(let round=0;round<rounds;round++)for(const product of ownAB?sampleOrder(abProducts,incremental).map(p=>p.label):(round%2?['layerfs','sprig-writable']:['sprig-writable','layerfs'])){
   const budget=admitBudget();
   const variant=ownAB?abProducts.find(p=>p.label===product):null;
   if(ownAB)verifyABInputs();else{assert.equal(command('git',['-C','sprig','rev-parse','HEAD']).trim(),productionSha);assert.equal(command('git',['-C','layerfs','rev-parse','HEAD']).trim(),comparatorSha);}
   if(ownAB)assert.equal(fs.existsSync(`results/stress-cargo-${product}-inc${incremental}-${round}.json`),false,'refuse existing sample output before runtime setup');
   const r={product,incremental,round,correct:false,status:'running',budgetAdmission:budget};records.push(r);save();
   const dir=fs.mkdtempSync(path.join(process.env.RUNNER_TEMP,`stress-cargo-${product}-${incremental}-${round}-`)),imagePath=path.join(dir,'new.img'),mount=path.join(dir,'mount'),runtimeStatePath=path.join(dir,'runtime-state.json');
   Object.assign(r,{filesystem:{dir,imagePath,mount,runtimeStatePath},isolatedImageRetained:imagePath});
   let mounted=false,runtimeAttempted=false,runtimeReady=false,sampleStarted=false,error=null;
   try{
    const host=fs.statfsSync(dir,{bigint:true});if(host.bavail*host.bsize<BigInt(IMAGE_BYTES+1024**3))throw new CapacityBlocked('host capacity blocked: 4GiB image plus1GiB evidence reserve required');
    const fd=fs.openSync(imagePath,'wx',0o600);fs.ftruncateSync(fd,IMAGE_BYTES);fs.closeSync(fd);fs.mkdirSync(mount);
    const stat=fs.lstatSync(imagePath);r.filesystem.imageIdentity={dev:String(stat.dev),ino:String(stat.ino)};assert.equal(stat.size,IMAGE_BYTES);
    r.mkfs=command('mkfs.btrfs',['-d','single','-m','dup',imagePath]);command('mount',['-o','loop,noatime',imagePath,mount]);mounted=true;r.emptySpace=physicalSpace(mount);
    runtimeAttempted=true;const setup=performance.now();r.runtime=JSON.parse(command('/usr/bin/python3',['feasibility/stress_runtime_storage.py','enter','--state',runtimeStatePath,'--mount',mount,'--archive',archive,'--image',image]));runtimeReady=true;r.runtimeSetupSeconds=(performance.now()-setup)/1000;r.runtimeReadySpace=physicalSpace(mount);
    r.capacityAdmission=capacityGuard({availableBytes:r.runtimeReadySpace.availableBytes,deviceBytes:r.runtimeReadySpace.deviceBytes,targetAllocatedBytes:pilot.targetAllocatedBytes,fixtureLogicalBytes});
    const root=path.join(mount,'sample'),ledger=path.join(recordDir,`${product}-${round}.jsonl`),rawPath=`results/stress-cargo-${product}-inc${incremental}-${round}.json`;
    let args;if(ownAB||product==='sprig-writable')args=['/usr/bin/python3','feasibility/stress_cargo_sample.py','run','--root',root,'--source',source,'--oracle',oracle,'--manifest',manifestPath,'--binary',ownAB?variant.binary:path.join(cwd,'sprig/target/release/sprig'),'--backend','writable','--production-sha',ownAB?variant.sha:productionSha,'--incremental',String(incremental),'--image',image,'--records',ledger];
    else{const options={root,measuredMount:mount,source,oraclePath:oracle,manifestPath,layerfsSdkPath:path.join(cwd,'layerfs/api/agent/sdk/src/index.js'),daemonPath:process.env.LAYERFS_DAEMON,image,incremental,recordsPath:ledger};const optionsPath=path.join(recordDir,`${product}-${round}-options.json`);atomicReport(optionsPath,options);args=['node','feasibility/stress_cargo_layerfs.mjs',optionsPath];}
    admitSampler(r,admitBudget);
    sampleStarted=true;const start=performance.now();let raw;try{raw=command(args[0],args.slice(1));r.sampleReturncode=0;}catch(e){raw=e.stdout?.toString()??'';r.sampleReturncode=e.status;r.failureStderr=e.stderr?.toString();}finally{r.wholeSampleSubprocessWallSeconds=(performance.now()-start)/1000;}
    fs.writeFileSync(rawPath,raw,ownAB?{flag:'wx'}:undefined);r.rawReportPath=rawPath;r.sample=JSON.parse(raw);assert.equal(r.sampleReturncode,0);
    if(ownAB){verifyABInputs();assert.equal(r.sample.binarySha256,variant.binarySha256);}
    validateSample(r.sample,ownAB?'sprig-writable':product,ownAB?{...identity,productionSha:variant.sha}:identity,incremental);
    r.activeSpace=r.sample.activeSpace;r.runtimeReadyDeltaBytes=r.activeSpace.filesystemUsedBytes-r.runtimeReadySpace.filesystemUsedBytes;r.correct=true;r.status='passed';
   }catch(e){if(runtimeAttempted&&!runtimeReady)r.runtimeSetupFailure={exitCode:e.status??null,stdout:e.stdout?.toString()??'',stderr:e.stderr?.toString()??''};error=e;r.correct=false;r.status=e instanceof CapacityBlocked?'capacity_blocked':e instanceof BudgetBlocked?'budget_blocked':'failed';r.error={message:e.message,stack:e.stack};}
   finally{
    let state=null;if(fs.existsSync(runtimeStatePath)){try{state=JSON.parse(fs.readFileSync(runtimeStatePath,'utf8'));}catch{state={malformed:true};}}
    const blocked=cleanupAdmission({sampleStarted,runtimeAttempted,runtimeReady,runtimeState:state,sample:r.sample});r.recoveryMetadata={runtimeAttempted,runtimeReady,sampleStarted,cleanupAdmissionBlocked:blocked,action:'On uncertainty retain state; no forced cleanup, repeated action or runtime restoration.'};r.cleanup=[];
    if(blocked){r.cleanupErrors=[blocked];error??=new Error(blocked);r.status='cleanup_blocked';}
    if(!blocked&&runtimeReady){try{command('/usr/bin/python3',['feasibility/stress_runtime_storage.py','leave','--state',runtimeStatePath]);r.cleanup.push('strict runtime restoration completed');}catch(e){r.cleanupErrors=[e.message];error??=e;r.status='cleanup_blocked';}}
    if(mounted&&!r.cleanupErrors){try{command('umount',['-i',mount]);assert.equal(command('losetup',['-j',imagePath]).trim(),'');r.cleanup.push('normal outer unmount and detached loop verified');}catch(e){r.cleanupErrors=[e.message];error??=e;r.status='cleanup_blocked';}}
    if(r.cleanupErrors){if(error)r.originalError=r.error;error=new Error('normal cleanup blocked: '+r.cleanupErrors.join('; '));}
    if(error)r.correct=false;save();
    if(!error){const current=fs.lstatSync(imagePath);assert.ok(current.isFile()&&!current.isSymbolicLink());assert.deepEqual({dev:String(current.dev),ino:String(current.ino)},r.filesystem.imageIdentity);assert.equal(current.size,IMAGE_BYTES);const raw=fs.openSync(r.rawReportPath,'r');try{fs.fsyncSync(raw);}finally{fs.closeSync(raw);}fs.unlinkSync(imagePath);r.isolatedImageRetained=null;r.cleanup.push('detached synthetic image disposed after durable reports/log archive');save();}
   }
   console.log(json({product,round,incremental,correct:r.correct,status:r.status,error:r.error,cleanupErrors:r.cleanupErrors}));if(error)throw error;
  }
  report.complete=records.length===rounds*2&&records.every(x=>x.correct);report.status='passed';
 }catch(error){report.complete=false;report.status=error instanceof CapacityBlocked?'capacity_blocked':error instanceof BudgetBlocked?'budget_blocked':'failed';report.error={message:error.message,stack:error.stack};}
 finally{save();}
 return report.complete?0:report.status==='capacity_blocked'?2:report.status==='budget_blocked'?3:1;
}
if(process.argv[1]&&pathToFileURL(path.resolve(process.argv[1])).href===import.meta.url)process.exitCode=await main();
