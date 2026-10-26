// Separate fixed current-main Native smoke. Historical combined/Cargo paths stay unchanged.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {performance} from 'node:perf_hooks';
import {pathToFileURL} from 'node:url';
import {budgetAdmission} from './stress_cargo_compare.mjs';
import {validateDirectManifest,SPRIG_SHA,LAYERFS_SHA} from './stress_cargo_latest_direct.mjs';
import {runLatestCombinedLayerfs,validateFixture} from './latest_combined_layerfs.mjs';
export {SPRIG_SHA,LAYERFS_SHA};
export const SCHEMA='sprig-latest-combined-native-smoke-v1',IDENTITY_SCHEMA='sprig-latest-combined-native-identity-v1';
export const IMAGE_BYTES=2*1024**3,ARTIFACT_BYTES=1024**3,REPORT_RESERVE=256*1024**2,MANIFEST_RESERVE=2*1024**2;
export const RAW_JSON_BYTES=16*1024**2,DRIVER_REPORT_BYTES=64*1024**2,RAW_TRANSPORT_BYTES=128*1024**2;
export const CASES=Object.freeze(['identical','history-distributed']);
export const ORDER=Object.freeze(CASES.flatMap(caseName=>['sprig-native','layerfs'].map(product=>({id:product+'-'+caseName,product,case:caseName}))));
const sha=value=>createHash('sha256').update(value).digest('hex');
const encode=value=>JSON.stringify(value,(_,v)=>typeof v==='bigint'?v.toString():v,2)+'\n';
function hashFile(file){const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK),hash=createHash('sha256'),buffer=Buffer.alloc(1024**2);try{const st=fs.fstatSync(fd,{bigint:true});assert.ok(st.isFile());let remaining=Number(st.size);while(remaining){const n=fs.readSync(fd,buffer,0,Math.min(buffer.length,remaining));assert.ok(n>0);hash.update(buffer.subarray(0,n));remaining-=n;}assert.equal(fs.readSync(fd,buffer,0,1),0);const after=fs.fstatSync(fd,{bigint:true});for(const key of ['dev','ino','size','mtimeNs','ctimeNs'])assert.equal(after[key],st[key]);return hash.digest('hex');}finally{fs.closeSync(fd);}}
export function validateIdentity(value){assert.equal(value?.schema,IDENTITY_SCHEMA);validateDirectManifest({...value,schema:'sprig-cargo-latest-direct-identity-v1'});return value;}
export function archiveAllowance(bytes){assert.ok(Number.isSafeInteger(bytes)&&bytes>=0);const allowance=ARTIFACT_BYTES-bytes-REPORT_RESERVE-MANIFEST_RESERVE;assert.ok(allowance>0,'no next sample: full pending reports/manifest headroom unavailable');return allowance;}
export function cleanupAdmission({sampleStarted,sample,runtimeAttempted,runtimeReady,runtimeState,outerUncertain}){
 if(outerUncertain)return 'unknown outer child outcome';
 if(sampleStarted){
  if(!sample||sample.uncertain===true||sample.error?.uncertain===true||sample.lifecycle?.uncertain===true)return 'missing sample or uncertain child/SDK outcome';
  if(sample.lifecycle?.cleanup?.complete!==true)return 'normal sampler cleanup unconfirmed';
  if(sample.remainingMountsKnown!==true||!Array.isArray(sample.remainingMounts)||sample.remainingMounts.length)return 'zero owned mounts unconfirmed';
  const field=sample.product==='layerfs'?'remainingContainers':'remainingServers';
  if(sample[field+'Known']!==true||!Array.isArray(sample[field])||sample[field].length)return 'zero owned servers/containers unconfirmed';
 }
 if(runtimeAttempted&&!runtimeReady&&runtimeState?.restored!==true)return 'runtime setup rollback unconfirmed';
 return null;
}
export function validateSample(sample,record,identity){
 assert.equal(sample?.ok,true);assert.equal(sample.testOnly,false);assert.equal(sample.product,record.product);assert.equal(sample.case,record.case);assert.equal(sample.production_sha,record.product==='layerfs'?LAYERFS_SHA:SPRIG_SHA);assert.equal(sample.prototype_only,false);
 assert.equal(sample.schema,record.product==='layerfs'?'sprig-latest-combined-layerfs-sample-v1':'sprig-latest-combined-native-sample-v1');
 assert.equal(sample.backend,record.product==='layerfs'?'fuse':'native');
 if(record.product==='sprig-native')assert.equal(record.sampleReturncode,0,'Native sampler must exit naturally with zero status');
 if(record.product==='layerfs')assert.equal(sample.image,identity.image);
 const history=record.case==='history-distributed';assert.equal(sample.fullHistoricalSnapshotReadbacks,history?100:0);
 for(const key of ['sourceUnchanged','originalMainViewUnchanged','originalSecondViewUnchanged','allAcknowledgedIdsPresent'])assert.equal(sample[key],true,key);
 assert.equal(sample.lifecycle.activeAtSpace.views.length,3);assert.equal(sample.lifecycle.activeAtSpace.historicalReadbacksStarted,false);
 const post=record.product==='layerfs'?sample.postHistoryBoundary:sample.lifecycle.activeAfterHistory;
 assert.equal(post.historicalReadbacksComplete,true);assert.equal(post.historicalReadbacksCompleted,history?100:0);assert.equal(post.views.length,3);
 for(const space of [sample.activeSpace,sample.postHistorySpace])assert.ok(Number.isSafeInteger(space?.filesystemUsedBytes)&&space.filesystemUsedBytes>=0&&space.filesystemUsedBytes<=IMAGE_BYTES);
 const keys=record.product==='layerfs'?['initMs','importMs','forkToWorkspaceMs','firstFullReadVerifyMs','totalImportForkReadMs','warmForkToWorkspaceMs','warmFirstFullReadMs','warmForkReadMs','historicalRestoreMs','historicalRestoreReadMs','historicalRestoreCleanupMs','fullTaskSeconds']:['init_seconds','import_seconds','first_fork_seconds','first_read_seconds','total_import_fork_read_seconds','warm_fork_seconds','warm_read_seconds','warm_total_seconds','restore_seconds','restore_read_seconds','restore_cleanup_seconds','wholeTaskSeconds','wholeSampleIncludingSetupCleanupSeconds'];
 for(const key of keys)assert.ok(Number.isFinite(sample[key])&&sample[key]>=0,'missing timing '+key);
 if(history){const rows=record.product==='layerfs'?sample.historyCheck?.samples:sample.checkpoint_steps;assert.equal(rows?.length,100);const restore=record.product==='layerfs'?sample.historicalRestoreSamples:sample.historical_restore_steps;assert.equal(restore?.length,100);}
 assert.equal(cleanupAdmission({sampleStarted:true,sample}),null);assert.equal(sample.archiveAdmission?.admitted,true);assert.equal(sample.archiveCopy?.complete,true);assert.ok(sample.completeLogArchive?.length>0);
 return true;
}
export async function main(){
 assert.equal(process.env.GITHUB_ACTIONS,'true');assert.equal(process.getuid(),0);
 for(const key of ['SPRIG_LIFECYCLE_TRACE','SPRIG_WRITABLE_DIAGNOSTICS','FEASIBILITY_MODE','SPRIG_BACKEND','STRESS_CARGO_AB_PRODUCTS','DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH','LAYERFS_STORE_POLICY','LAYERFS_WORKER_ENDPOINT','LAYERFS_NATIVE','LAYERFS_TRACE','LAYERFS_DAEMON_HOST'])assert.equal(process.env[key],undefined,'unrelated mode/diagnostics forbidden');
 const cwd=fs.realpathSync(process.cwd()),results=path.join(cwd,'results'),temporary=process.env.RUNNER_TEMP;
 assert.ok(path.isAbsolute(temporary??'')&&fs.realpathSync(temporary)===temporary);assert.equal(fs.realpathSync(results),results);
 const recordsRoot=path.join(temporary,'latest-combined-records');assert.ok(!fs.existsSync(recordsRoot));fs.mkdirSync(recordsRoot);const hostLogs=path.join(recordsRoot,'driver.jsonl.logs');fs.mkdirSync(hostLogs);
 const identityPath=path.join(results,'latest-combined-identity.json'),identityBytes=fs.readFileSync(identityPath),products=validateIdentity(JSON.parse(identityBytes));
 const fixtureBytes=fs.readFileSync(path.join(results,'latest-combined-fixtures.json')),fixtures=JSON.parse(fixtureBytes);assert.equal(fixtures.schema,'sprig-latest-combined-fixtures-v1');
 const image=process.env.LAYERFS_IMAGE,archive=process.env.LAYERFS_IMAGE_ARCHIVE;assert.match(image??'',/^sha256:[a-f0-9]{64}$/);assert.ok(path.isAbsolute(archive??'')&&fs.realpathSync(archive)===archive);assert.equal(process.env.LAYERFS_DAEMON,products.layerfs.binary);
 const jobStart=Number(process.env.LATEST_COMBINED_JOB_STARTED_EPOCH),jobDeadline=Number(process.env.LATEST_COMBINED_JOB_DEADLINE_EPOCH),epoch=Date.now()/1000,monotonic=performance.now();
 const admit=()=>budgetAdmission({startedEpochSeconds:jobStart,deadlineEpochSeconds:jobDeadline,nowEpochSeconds:epoch+(performance.now()-monotonic)/1000});
 const report={schema:SCHEMA,complete:false,status:'incomplete',backend:'native',mode:'smoke',rounds:1,expectedRecords:4,image,imageBytes:IMAGE_BYTES,productionSha:SPRIG_SHA,comparatorSha:LAYERFS_SHA,identity:products,identitySha256:sha(identityBytes),fixtureManifest:fixtures,fixtureManifestSha256:sha(fixtureBytes),sharedJobBudget:{startedEpochSeconds:jobStart,deadlineEpochSeconds:jobDeadline,minimumSampleSeconds:180,cleanupReserveSeconds:300},records:ORDER.map((r,position)=>({...r,position,status:'not_run',correct:false})),limits:{artifactBytes:ARTIFACT_BYTES,pendingReportReserveBytes:REPORT_RESERVE,collectionManifestReserveBytes:MANIFEST_RESERVE},notes:['One pair per case is a smoke correctness/coverage gate, not a balanced performance estimate.','Listed-file hashes/history only; not full metadata parity or equal durability.','Both active and post-history Used remain distinct; all103 native history trees remain retained.','No image deletion, pruning, forced/lazy unmount, fault injection or automatic repeat.','Explicit measured TMPDIR and complete evidence are new-series accounting changes; not pooled with old combined measurements.']};
 let sequence=0,outerUncertain=false;
 function externalBytes(){let total=0;for(const base of [results,recordsRoot]){const stack=[base];while(stack.length){const current=stack.pop();for(const name of fs.readdirSync(current)){const p=path.join(current,name),st=fs.lstatSync(p);assert.ok(!st.isSymbolicLink(),'external evidence symlink refused');if(st.isDirectory()){assert.ok(base===recordsRoot&&path.relative(base,p).split(path.sep).length<=1,'external evidence tree shape');stack.push(p);}else{assert.ok(st.isFile()&&st.nlink===1);total+=st.size;}}}}assert.ok(Number.isSafeInteger(total));return total;}
 function atomic(file,value){const bytes=Buffer.from(encode(value));assert.ok(bytes.length<=(path.basename(file)==='latest-combined-comparison.json'?DRIVER_REPORT_BYTES:RAW_JSON_BYTES),'complete JSON exceeds bounded report acceptance; originals retained');assert.ok(externalBytes()+bytes.length+MANIFEST_RESERVE<=ARTIFACT_BYTES,'full pending report would exceed evidence cap; originals retained');const temp=file+'.new';assert.ok(!fs.existsSync(temp));const fd=fs.openSync(temp,'wx');try{fs.writeFileSync(fd,bytes);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(temp,file);const dir=fs.openSync(path.dirname(file),'r');try{fs.fsyncSync(dir);}finally{fs.closeSync(dir);}}
 const save=()=>atomic(path.join(results,'latest-combined-comparison.json'),report);
 async function run(argv,{allowNonzero=false,rawStem=null,maxBytes=2*1024**2}={}){
  assert.equal(outerUncertain,false,'unknown outer child: no additional commands');
  const stem=rawStem??path.join(hostLogs,String(++sequence).padStart(6,'0')),stdoutPath=stem+'.stdout',stderrPath=stem+'.stderr';
  const out=fs.openSync(stdoutPath,'wx'),err=fs.openSync(stderrPath,'wx');let result;
  try{result=await new Promise((resolve,reject)=>{const child=spawn(argv[0],argv.slice(1).map(String),{stdio:['ignore',out,err]});child.on('error',reject);child.on('close',(code,signal)=>resolve({code,signal}));});}catch(error){outerUncertain=true;throw error;}finally{fs.closeSync(out);fs.closeSync(err);}
  const row={argv,returncode:result.code,signal:result.signal,stdoutPath,stderrPath,stdoutBytes:fs.statSync(stdoutPath).size,stderrBytes:fs.statSync(stderrPath).size,stdoutSha256:hashFile(stdoutPath),stderrSha256:hashFile(stderrPath)};
  fs.appendFileSync(path.join(recordsRoot,'driver.jsonl'),JSON.stringify(row)+'\n');assert.ok(row.stdoutBytes+row.stderrBytes<=maxBytes,'full output retained but aggregate command acceptance cap exceeded');
  assert.equal(result.signal,null,'child exited by signal');if(!allowNonzero)assert.equal(result.code,0,'command failed: '+argv.join(' '));return {...row,stdout:fs.readFileSync(stdoutPath,'utf8'),stderr:fs.readFileSync(stderrPath,'utf8')};
 }
 async function inventory(){const row=await run(['/usr/bin/python3','feasibility/latest_combined_collect.py','inventory','--results',results,'--temporary',temporary]);const value=JSON.parse(row.stdout);assert.ok(Number.isSafeInteger(value.bytes)&&value.bytes>=0);return value;}
 async function verifyInputs(){assert.ok(fs.readFileSync(identityPath).equals(identityBytes));assert.ok(fs.readFileSync(path.join(results,'latest-combined-fixtures.json')).equals(fixtureBytes));
  for(const p of [products.sprig,products.layerfs]){assert.equal((await run(['git','-C',p.sourcePath,'rev-parse','HEAD'])).stdout.trim(),p.sha);assert.equal((await run(['git','-C',p.sourcePath,'status','--porcelain'])).stdout.trim(),'');for(const [key,hash]of [['binary','binarySha256'],...(p.sdkPath?[['sdkPath','sdkSha256'],['nativeAddonPath','nativeAddonSha256']]:[])]){assert.equal(fs.realpathSync(p[key]),p[key]);assert.equal(hashFile(p[key]),p[hash]);}}
  for(const entry of fixtures.cases){assert.ok(CASES.includes(entry.case));for(const [key,hash]of [['oraclePath','oracleSha256'],...(entry.stepsPath?[['stepsPath','stepsSha256'],['finalPath','finalSha256']]:[])])assert.equal(hashFile(entry[key]),entry[hash]);}assert.deepEqual(fixtures.cases.map(x=>x.case),[...CASES]);
 }
 async function space(mount){await run(['btrfs','filesystem','sync',mount]);const usage=(await run(['btrfs','filesystem','usage','-b',mount])).stdout,groups=(await run(['btrfs','filesystem','df','-b',mount])).stdout;const used=usage.match(/^\s*Used:\s*(\d+)\s*$/m),device=usage.match(/^\s*Device size:\s*(\d+)\s*$/m);assert.ok(used&&device);assert.equal(Number(device[1]),IMAGE_BYTES);return {filesystemUsedBytes:Number(used[1]),deviceBytes:Number(device[1]),usageRaw:usage,groupsRaw:groups};}
 save();let failure=null;
 for(const record of report.records){
  let isolated=null,sampleStarted=false,runtimeAttempted=false,runtimeReady=false,mounted=false;
  record.status='running';save();
  try{
   record.budgetAdmission=admit();await verifyInputs();record.preSampleArtifactInventory=await inventory();record.archiveAllowanceBytes=archiveAllowance(record.preSampleArtifactInventory.bytes);
   const stats=fs.statfsSync(temporary,{bigint:true}),available=Number(stats.bavail*stats.bsize);record.hostAdmission={availableBytes:available,requiredBytes:IMAGE_BYTES+ARTIFACT_BYTES+512*1024**2};assert.ok(available>=record.hostAdmission.requiredBytes,'host cannot safely admit another retained2GiB image/evidence');
   const dir=fs.mkdtempSync(path.join(temporary,'latest-combined-'+record.id+'-')),mount=path.join(dir,'mount'),imagePath=path.join(dir,'new.img');fs.mkdirSync(mount);const fd=fs.openSync(imagePath,'wx',0o600);fs.ftruncateSync(fd,IMAGE_BYTES);fs.closeSync(fd);isolated={directory:dir,mount,image:imagePath,runtimeState:path.join(dir,'runtime-state.json')};record.filesystem={...isolated};
   record.filesystem.mkfs=(await run(['mkfs.btrfs','-d','single','-m','dup',imagePath])).stdout;
   try{await run(['mount','-o','loop,noatime',imagePath,mount]);mounted=true;}catch(error){if(!outerUncertain){const check=await run(['findmnt','-rn','--mountpoint',mount],{allowNonzero:true});assert.ok([0,1].includes(check.returncode));mounted=check.returncode===0;}throw error;}
   assert.equal((await run(['stat','-f','-c','%T',mount])).stdout.trim(),'btrfs');record.filesystem.mountInfo=(await run(['findmnt','-T',mount])).stdout;record.filesystem.empty=await space(mount);
   if(record.product==='layerfs'){runtimeAttempted=true;record.runtime=JSON.parse((await run(['/usr/bin/python3','feasibility/stress_runtime_storage.py','enter','--state',isolated.runtimeState,'--mount',mount,'--archive',archive,'--image',image])).stdout);runtimeReady=true;record.runtimeReadySpace=await space(mount);}
   record.postRuntimeBudgetAdmission=admit();const fixture=fixtures.cases.find(x=>x.case===record.case),source=fixture.sourcePath,oraclePath=fixture.oraclePath,stepsPath=fixture.stepsPath;validateFixture(JSON.parse(fs.readFileSync(oraclePath)),stepsPath?JSON.parse(fs.readFileSync(stepsPath)):[],record.case);
   const root=path.join(mount,'store'),recordsPath=path.join(recordsRoot,record.id+'.jsonl'),rawPath=path.join(results,'latest-combined-'+record.id+'.json');sampleStarted=true;
   if(record.product==='layerfs')record.sample=await runLatestCombinedLayerfs({caseName:record.case,root,measuredMount:mount,source,oraclePath,...(stepsPath?{stepsPath}:{}),sdkPath:products.layerfs.sdkPath,daemonPath:products.layerfs.binary,image,recordsPath,productionSha:LAYERFS_SHA,archiveAllowanceBytes:record.archiveAllowanceBytes});
   else{const args=['/usr/bin/python3','feasibility/latest_combined_sample.py','run','--backend','native','--production-sha',SPRIG_SHA,'--binary-sha256',products.sprig.binarySha256,'--case',record.case,'--root',root,'--source',source,'--oracle',oraclePath,'--binary',products.sprig.binary,'--records',recordsPath,'--archive-allowance-bytes',record.archiveAllowanceBytes,...(stepsPath?['--steps',stepsPath]:[])];const transport=await run(args,{allowNonzero:true,rawStem:path.join(results,'latest-combined-'+record.id),maxBytes:RAW_TRANSPORT_BYTES});record.sampleReturncode=transport.returncode;assert.ok(transport.stdoutBytes<=RAW_JSON_BYTES,'complete raw JSON retained but16MiB acceptance exceeded');record.sample=JSON.parse(transport.stdout);}
   atomic(rawPath,record.sample);record.rawReportPath='results/'+path.basename(rawPath);record.rawReportSha256=hashFile(rawPath);validateSample(record.sample,record,{image});
   for(const entry of record.sample.completeLogArchive){assert.equal(path.dirname(entry.archived),recordsPath+'.logs');const info=fs.lstatSync(entry.archived);assert.ok(info.isFile()&&!info.isSymbolicLink()&&info.nlink===1);assert.equal(info.size,entry.bytes);assert.equal(hashFile(entry.archived),entry.sha256);}
   await verifyInputs();record.verifiedProductInputs=record.product==='layerfs'?products.layerfs:products.sprig;record.correct=true;record.status='passed';
  }catch(error){record.correct=false;record.status='failed';record.error={message:error.message,stack:error.stack,outerUncertain};failure=error;}
  finally{
   const cleanup=[];let state=null;if(isolated&&fs.existsSync(isolated.runtimeState))try{state=JSON.parse(fs.readFileSync(isolated.runtimeState));}catch{}
   const blocked=cleanupAdmission({sampleStarted,sample:record.sample,runtimeAttempted,runtimeReady,runtimeState:state,outerUncertain});
   record.cleanup={blocked,originalImageRetained:!!isolated,normalOnly:true,complete:false};
   if(blocked)cleanup.push(blocked);
   if(!blocked&&runtimeReady)try{record.runtimeLeave=JSON.parse((await run(['/usr/bin/python3','feasibility/stress_runtime_storage.py','leave','--state',isolated.runtimeState])).stdout);assert.equal(record.runtimeLeave.restored,true);}catch(error){cleanup.push(error.message);}
   if(!blocked&&!cleanup.length&&mounted)try{await run(['umount','-i',isolated.mount]);const check=await run(['findmnt','-rn','--mountpoint',isolated.mount],{allowNonzero:true});assert.equal(check.returncode,1);record.cleanup.unmounted=true;}catch(error){cleanup.push(error.message);}
   record.cleanup.complete=!cleanup.length;if(cleanup.length){record.cleanupErrors=cleanup;record.correct=false;record.status='failed';failure??=new Error(cleanup.join('; '));}
   try{record.finalArtifactInventory=await inventory();assert.ok(record.finalArtifactInventory.bytes+MANIFEST_RESERVE<=ARTIFACT_BYTES,'evidence cap exceeded');}catch(error){record.correct=false;record.status='failed';record.artifactError=error.message;failure??=error;}
   report.status=failure?'failed':'incomplete';save();
  }
  if(failure)break;
 }
 report.complete=report.records.every(r=>r.correct&&r.status==='passed');report.status=report.complete?'passed':'failed';save();if(!report.complete)throw failure??new Error('incomplete finite native smoke');
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href)await main();
