// Dedicated four-sample observation canary; never calls/weakens primary main().
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {performance} from 'node:perf_hooks';
import {createHash} from 'node:crypto';
import {IMAGE_BYTES,budgetAdmission,capacityGuard,validateCapacity,cleanupAdmission,CapacityBlocked,BudgetBlocked} from './stress_cargo_compare.mjs';
import {loadCommands} from './stress_cargo_layerfs.mjs';
export const SOURCE='73a462885c7b5bc88d64764152ab8fab08eba055';
export const PARENT='0f00ac4afbfc42b76c63a31833eabb07b82152f2';
export const ALGORITHM='b300693e01c652c1a9631c61b7a439892d8f75cd';
export const PRESSURE='58e5171ba44661a00065297155025a0c75839892cb5c21c770d22e84f4e0b501';
export const ORDER=Object.freeze([{arm:'off',pair:0},{arm:'on',pair:0},{arm:'on',pair:1},{arm:'off',pair:1}]);
export const ARTIFACT_CAP=1024**3;
export const REPORT_RESERVE_BYTES=192*1024**2;
export const COLLECTION_RESERVE_BYTES=2*1024**2;
const sha=x=>createHash('sha256').update(x).digest('hex');
const json=x=>JSON.stringify(x,null,2);
const command=(p,a)=>execFileSync(p,a.map(String),{encoding:'utf8',maxBuffer:128*1024**2});
export function validateIdentity(v){
 assert.deepEqual(Object.keys(v).sort(),['schema','sha','parent','algorithmBase','binary','binarySha256','sourcePath','pressureScriptSha256'].sort());
 assert.equal(v.schema,'sprig-writable-diagnostic-identity-v1');assert.equal(v.sha,SOURCE);assert.equal(v.parent,PARENT);assert.equal(v.algorithmBase,ALGORITHM);assert.equal(v.pressureScriptSha256,PRESSURE);assert.match(v.binarySha256??'',/^[a-f0-9]{64}$/);
 for(const k of ['binary','sourcePath'])assert.ok(typeof v[k]==='string'&&path.isAbsolute(v[k])&&path.normalize(v[k])===v[k]);return v;
}
export function assertEnvironment(env=process.env){
 for(const key of ['SPRIG_LIFECYCLE_TRACE','SPRIG_WRITABLE_DIAGNOSTICS','STRESS_CARGO_AB_PRODUCTS','STRESS_CARGO_INCREMENTAL','STRESS_CARGO_ROUNDS','STRESS_CARGO_PROFILE','STRESS_CARGO_PREVIOUS_GATE'])assert.equal(env[key],undefined,'dedicated fixed diagnostic entry refuses inherited '+key);
 assert.equal(env.GITHUB_ACTIONS,'true');assert.ok(path.isAbsolute(env.RUNNER_TEMP??''));
}
export function sampleArtifactAdmission(inventory){
 assert.equal(inventory.schema,'sprig-writable-diagnostic-artifact-inventory-v1');assert.equal(inventory.completeNamedInventory,true);
 assert.ok(Number.isSafeInteger(inventory.files)&&inventory.files>=0);assert.ok(Number.isSafeInteger(inventory.bytes)&&inventory.bytes>=0&&inventory.bytes<=ARTIFACT_CAP);
 assert.equal(inventory.maximumBytes,ARTIFACT_CAP);assert.equal(inventory.collectionReserveBytes,COLLECTION_RESERVE_BYTES);assert.equal(inventory.admissionBytes,inventory.bytes+COLLECTION_RESERVE_BYTES);
 const projectedAdmissionBytes=inventory.bytes+REPORT_RESERVE_BYTES+COLLECTION_RESERVE_BYTES;
 assert.ok(projectedAdmissionBytes<=ARTIFACT_CAP,'complete evidence plus pending report/collection headroom exceeds1GiB before next sample; no runtime/sample started');
 return {existingNamedExternalBytes:inventory.bytes,reportReserveBytes:REPORT_RESERVE_BYTES,collectionReserveBytes:COLLECTION_RESERVE_BYTES,projectedAdmissionBytes,maximumBytes:ARTIFACT_CAP};
}
function atomic(file,value){const body=json(value)+'\n';assert.ok(Buffer.byteLength(body)<=8*1024**2,'driver report exceeds explicit8MiB reserve; no write');const temp=file+'.'+process.pid+'.new',fd=fs.openSync(temp,'wx',0o644);try{fs.writeFileSync(fd,body);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(temp,file);const dir=fs.openSync(path.dirname(file),'r');try{fs.fsyncSync(dir);}finally{fs.closeSync(dir);}}
function space(mount){command('btrfs',['filesystem','sync',mount]);const usageRaw=command('btrfs',['filesystem','usage','-b',mount]),groupsRaw=command('btrfs',['filesystem','df','-b',mount]),used=usageRaw.match(/^\s*Used:\s*(\d+)\s*$/m),device=usageRaw.match(/^\s*Device size:\s*(\d+)\s*$/m);assert.ok(used&&device);const st=fs.statfsSync(mount,{bigint:true});return {filesystemUsedBytes:Number(used[1]),deviceBytes:Number(device[1]),availableBytes:Number(st.bavail*st.bsize),usageRaw,groupsRaw};}
function inventory(results,temporary){return JSON.parse(command('/usr/bin/python3',['feasibility/stress_writable_diagnostic_collect.py','inventory','--results',results,'--temporary',temporary]));}
export async function main(){
 assertEnvironment();assert.equal(process.getuid(),0);
 const cwd=process.cwd(),results=path.join(cwd,'results'),temporary=process.env.RUNNER_TEMP;
 const manifestPath=path.join(results,'writable-diagnostic-identity.json'),manifestBytes=fs.readFileSync(manifestPath),identity=validateIdentity(JSON.parse(manifestBytes));
 const image=process.env.CARGO_IMAGE,archive=process.env.CARGO_IMAGE_ARCHIVE;assert.match(image??'',/^sha256:[a-f0-9]{64}$/);assert.ok(path.isAbsolute(archive??''));
 const verifyInputs=()=>{assert.ok(fs.readFileSync(manifestPath).equals(manifestBytes));assert.equal(fs.realpathSync(identity.sourcePath),identity.sourcePath);assert.equal(fs.realpathSync(identity.binary),identity.binary);assert.equal(command('git',['-C',identity.sourcePath,'rev-parse','HEAD']).trim(),SOURCE);assert.equal(command('git',['-C',identity.sourcePath,'rev-parse','HEAD^']).trim(),PARENT);assert.equal(command('git',['-C',identity.sourcePath,'status','--porcelain']).trim(),'');const st=fs.lstatSync(identity.binary);assert.ok(st.isFile()&&!st.isSymbolicLink());assert.equal(sha(fs.readFileSync(identity.binary)),identity.binarySha256);assert.equal(sha(fs.readFileSync('feasibility/stress_cargo_pressure_long.py')),PRESSURE);};
 verifyInputs();
 const invocationEpoch=Date.now()/1000,invocationMono=performance.now();
 const sharedJobBudget={startedEpochSeconds:Number(process.env.STRESS_CARGO_JOB_STARTED_EPOCH),deadlineEpochSeconds:Number(process.env.STRESS_CARGO_JOB_DEADLINE_EPOCH),minimumSampleSeconds:180,cleanupReserveSeconds:300};
 const admit=()=>budgetAdmission({...sharedJobBudget,nowEpochSeconds:invocationEpoch+(performance.now()-invocationMono)/1000});admit();
 const source=path.join(cwd,'fixtures/stress-cargo'),oracle=path.join(results,'stress-cargo-oracle.json'),fixturePath=path.join(results,'stress-cargo-manifest.json'),fixtureBytes=fs.readFileSync(fixturePath),fixture=JSON.parse(fixtureBytes),protocolSha256=loadCommands().sha256,fixtureManifestSha256=sha(fixtureBytes);
 assert.equal(fixture.protocolSha256,protocolSha256);const pilot=validateCapacity(JSON.parse(fs.readFileSync(path.join(results,'stress-cargo-capacity.json'))),{image,protocolSha256,fixtureManifestSha256},0);
 const fixtureLogicalBytes=fixture.initial.entries.filter(x=>x.type==='file').reduce((n,x)=>{assert.ok(Number.isSafeInteger(x.size)&&x.size>=0);return n+x.size;},0);assert.ok(Number.isSafeInteger(fixtureLogicalBytes));
 const recordRoot=path.join(temporary,'stress-writable-diagnostic-records');fs.mkdirSync(recordRoot);const recordDir=path.join(recordRoot,'inc0');fs.mkdirSync(recordDir);
 const reportPath=path.join(results,'writable-diagnostic-canary.json');assert.equal(fs.existsSync(reportPath),false);
 const report={schema:'sprig-writable-diagnostic-canary-v1',status:'running',complete:false,expectedRecords:4,incremental:0,imageBytes:IMAGE_BYTES,order:ORDER,identity,identitySha256:sha(manifestBytes),image,protocolSha256,fixtureManifestSha256,sharedJobBudget,capacityPilot:pilot,capacityPilotScope:'Unchanged external inc0+inc1 common capacity setup only; four product measurements are inc0 only, no pilot timing pooled into results.',artifactBudgetBytes:ARTIFACT_CAP,records:[],notRun:ORDER,automaticRetry:false,automaticFallback:false,automaticPromotion:false,notes:['One fixed b300-derived diagnostic ELF off/on then on/off. Not a product optimization comparison, not a full matrix.','Standalone Python sample/oracle/trace files preserve exact integers. No parsed JS embedded trace or oracle is authoritative.','Stop on first resource, correctness, transport, clock, CPU, ring-coverage or cleanup failure; no trimmed window/fallback/retry.','Two pairs only: show all observations, overhead/order negatives; no significance/equivalence or stable overhead claim.']};
 const save=()=>atomic(reportPath,report);save();
 try{
  for(const [index,{arm,pair}] of ORDER.entries()){
   const budget=admit();verifyInputs();report.preSampleArtifactInventory=inventory(results,temporary);
   const artifactAdmission=sampleArtifactAdmission(report.preSampleArtifactInventory);
   const r={arm,pair,incremental:0,status:'running',correct:false,budgetAdmission:budget,artifactAdmission};report.records.push(r);report.notRun=ORDER.slice(index+1);save();
   const dir=fs.mkdtempSync(path.join(temporary,`writable-diagnostic-${arm}-${pair}-`)),imagePath=path.join(dir,'new.img'),mount=path.join(dir,'mount'),runtimeStatePath=path.join(dir,'runtime-state.json');
   Object.assign(r,{filesystem:{dir,imagePath,mount,runtimeStatePath},isolatedImageRetained:imagePath});
   let mounted=false,runtimeAttempted=false,runtimeReady=false,sampleStarted=false,sample=null,error=null;
   try{
    const host=fs.statfsSync(dir,{bigint:true});if(host.bavail*host.bsize<BigInt(IMAGE_BYTES+ARTIFACT_CAP))throw new CapacityBlocked('host requires4GiB image plus1GiB complete evidence reserve');
    const fd=fs.openSync(imagePath,'wx',0o600);fs.ftruncateSync(fd,IMAGE_BYTES);fs.closeSync(fd);fs.mkdirSync(mount);const st=fs.lstatSync(imagePath);r.filesystem.imageIdentity={dev:String(st.dev),ino:String(st.ino)};assert.equal(st.size,IMAGE_BYTES);
    r.mkfs=command('mkfs.btrfs',['-d','single','-m','dup',imagePath]);command('mount',['-o','loop,noatime',imagePath,mount]);mounted=true;r.emptySpace=space(mount);
    runtimeAttempted=true;const setup=performance.now();r.runtime=JSON.parse(command('/usr/bin/python3',['feasibility/stress_runtime_storage.py','enter','--state',runtimeStatePath,'--mount',mount,'--archive',archive,'--image',image]));runtimeReady=true;r.runtimeSetupSeconds=(performance.now()-setup)/1000;r.runtimeReadySpace=space(mount);
    r.capacityAdmission=capacityGuard({availableBytes:r.runtimeReadySpace.availableBytes,deviceBytes:r.runtimeReadySpace.deviceBytes,targetAllocatedBytes:pilot.targetAllocatedBytes,fixtureLogicalBytes,pressureReserveBytes:128*1024**2});
    r.postRuntimeBudgetAdmission=admit();
    const root=path.join(mount,'sample'),ledger=path.join(recordDir,`${arm}-${pair}.jsonl`),rawPath=`results/stress-writable-diagnostic-${arm}-${pair}.json`;assert.equal(fs.existsSync(rawPath),false);
    const args=['feasibility/stress_writable_diagnostic_sample.py','run','--root',root,'--source',source,'--oracle',oracle,'--manifest',fixturePath,'--binary',identity.binary,'--backend','writable','--production-sha',SOURCE,'--incremental','0','--image',image,'--records',ledger,'--diagnostic-arm',arm,'--artifact-results',results];
    sampleStarted=true;const start=performance.now();let raw;
    try{raw=command('/usr/bin/python3',args);r.sampleReturncode=0;}catch(e){raw=e.stdout?.toString()??'';r.sampleReturncode=e.status;r.failureStderr=e.stderr?.toString()??'';}finally{r.wholeSampleSubprocessWallSeconds=(performance.now()-start)/1000;}
    assert.ok(Buffer.byteLength(raw)<=128*1024**2,'standalone sample exceeds128MiB reserved transport');fs.writeFileSync(rawPath,raw,{flag:'wx'});r.rawReportPath=rawPath;r.rawReportSha256=sha(raw);sample=JSON.parse(raw);assert.equal(r.sampleReturncode,0);
    verifyInputs();r.sampleAuditPath=`results/writable-diagnostic-audit-${arm}-${pair}.json`;
    command('/usr/bin/python3',['feasibility/stress_writable_diagnostic_audit.py','sample','--sample',path.join(cwd,rawPath),'--manifest',manifestPath,'--image',image,'--protocol-sha',protocolSha256,'--archive-root',recordRoot,'--arm',arm,'--pair',pair,'--output',path.join(cwd,r.sampleAuditPath)]);
    const audit=JSON.parse(fs.readFileSync(r.sampleAuditPath));assert.equal(audit.correct,true);r.sampleAuditSha256=sha(fs.readFileSync(r.sampleAuditPath));
    r.postSampleArtifactInventory=inventory(results,temporary);assert.ok(r.postSampleArtifactInventory.bytes<=ARTIFACT_CAP,'complete artifact budget exceeded; no filtering');r.correct=true;r.status='passed';
   }catch(e){error=e;r.correct=false;r.status=e instanceof CapacityBlocked?'capacity_blocked':e instanceof BudgetBlocked?'budget_blocked':'failed';r.error={message:e.message,stack:e.stack};if(runtimeAttempted&&!runtimeReady)r.runtimeSetupFailure={exitCode:e.status??null,stdout:e.stdout?.toString()??'',stderr:e.stderr?.toString()??''};}
   finally{
    let state=null;if(fs.existsSync(runtimeStatePath)){try{state=JSON.parse(fs.readFileSync(runtimeStatePath));}catch{state={malformed:true};}}
    const blocked=cleanupAdmission({sampleStarted,runtimeAttempted,runtimeReady,runtimeState:state,sample});r.recoveryMetadata={runtimeAttempted,runtimeReady,sampleStarted,cleanupAdmissionBlocked:blocked,action:'Uncertain outcome retains state; no forced cleanup, repeated operation, signal, or runtime restoration.'};r.cleanup=[];
    if(blocked){r.cleanupErrors=[blocked];error??=new Error(blocked);r.status='cleanup_blocked';}
    if(!blocked&&runtimeReady){try{command('/usr/bin/python3',['feasibility/stress_runtime_storage.py','leave','--state',runtimeStatePath]);r.cleanup.push('strict runtime restoration completed');}catch(e){r.cleanupErrors=[e.message];error??=e;r.status='cleanup_blocked';}}
    if(mounted&&!r.cleanupErrors){try{command('umount',['-i',mount]);assert.equal(command('losetup',['-j',imagePath]).trim(),'');r.cleanup.push('normal outer unmount and detached loop verified');}catch(e){r.cleanupErrors=[e.message];error??=e;r.status='cleanup_blocked';}}
    if(error)r.correct=false;save();
    if(!error){const current=fs.lstatSync(imagePath);assert.ok(current.isFile()&&!current.isSymbolicLink());assert.deepEqual({dev:String(current.dev),ino:String(current.ino)},r.filesystem.imageIdentity);assert.equal(current.size,IMAGE_BYTES);
     // Every complete archive and raw report must be durable before disposable image removal.
     for(const file of [r.rawReportPath,r.sampleAuditPath,...sample.completeLogArchive.map(x=>x.archived)]){const fd=fs.openSync(file,'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}}
     fs.unlinkSync(imagePath);r.isolatedImageRetained=null;r.cleanup.push('detached synthetic image disposed after durable raw/log evidence');save();}
   }
   console.log(json({arm,pair,correct:r.correct,status:r.status,error:r.error,cleanupErrors:r.cleanupErrors}));if(error)throw error;
  }
  report.complete=report.records.length===4&&report.records.every(x=>x.correct);report.status='passed';
 }catch(e){report.complete=false;report.status=e instanceof CapacityBlocked?'capacity_blocked':e instanceof BudgetBlocked?'budget_blocked':'failed';report.error={message:e.message,stack:e.stack};}
 finally{save();}
 return report.complete?0:1;
}
if(process.argv[1]&&pathToFileURL(path.resolve(process.argv[1])).href===import.meta.url)process.exitCode=await main();
