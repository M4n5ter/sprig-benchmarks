import assert from 'node:assert/strict';
import fs from 'node:fs';
import {IMAGE_BYTES,CapacityBlocked,capacityGuard,validateCapacity,validateFresh,validatePreviousGate,cleanupAdmission,BudgetBlocked,budgetAdmission,admitSampler} from './stress_cargo_compare.mjs';
const MiB=1024**2;
const admitted={deviceBytes:IMAGE_BYTES,availableBytes:900*MiB,targetAllocatedBytes:64*MiB,fixtureLogicalBytes:1000};
assert.equal(capacityGuard(admitted).admitted,true);
assert.throws(()=>capacityGuard({...admitted,availableBytes:512*MiB}),CapacityBlocked);
assert.throws(()=>capacityGuard({...admitted,deviceBytes:8*1024**3}),/2GiB/);
assert.throws(()=>capacityGuard({...admitted,targetAllocatedBytes:0}));
assert.throws(()=>capacityGuard({...admitted,targetAllocatedBytes:Number.MAX_SAFE_INTEGER}));
assert.throws(()=>capacityGuard({...admitted,availableBytes:NaN}));
const identity={image:'sha256:'+'a'.repeat(64),protocolSha256:'b'.repeat(64),fixtureManifestSha256:'c'.repeat(64),productionSha:'d'.repeat(40),comparatorSha:'e'.repeat(40)};
const capacity={schema:'sprig-stress-cargo-capacity-v1',...identity,toolchain:{rustc:'1.90.0',cargo:'1.90.0'},pilots:[{incremental:0,targetAllocatedBytes:1},{incremental:1,targetAllocatedBytes:2}]};
assert.equal(validateCapacity(capacity,identity,1).targetAllocatedBytes,2);
for(const mutate of [x=>x.image='sha256:'+'f'.repeat(64),x=>x.toolchain.rustc='1.99.1',x=>x.pilots[1].incremental=0,x=>x.pilots[0].targetAllocatedBytes=0,x=>x.protocolSha256='f'.repeat(64)]){const bad=structuredClone(capacity);mutate(bad);assert.throws(()=>validateCapacity(bad,identity,0));}
const packages=Array.from({length:16},(_,i)=>'node'+String(i).padStart(3,'0')).concat('stress-app');
const observations=['clean_build','noop_build','edit_build','restored_rebuild'].map(phase=>{const fresh=['noop_build','restored_rebuild'].includes(phase);return {phase,returncode:0,freshLines:fresh?packages.map(p=>` Fresh ${p} v0.1.0`):[],compilingLines:fresh?[]:packages.map(p=>` Compiling ${p} v0.1.0`)};});
const sample={ok:true,image:identity.image,protocolSha256:identity.protocolSha256,cargoBuildObservations:observations,fullRestoredTreeVerified:true,lifecycle:{cleanup:{complete:true}},remainingMounts:[],remainingContainers:[]};
validateFresh(sample);
const gate={schema:'sprig-stress-cargo-comparison-v2',complete:true,status:'passed',incremental:0,rounds:1,...identity,records:['sprig-writable','layerfs'].map(product=>({product,round:0,incremental:0,correct:true,sample:{...structuredClone(sample),production_sha:product==='layerfs'?identity.comparatorSha:identity.productionSha}}))};
assert.equal(validatePreviousGate(gate,identity),true);
for(const mutate of [x=>x.complete=false,x=>x.incremental=1,x=>x.image='sha256:'+'0'.repeat(64),x=>x.records.pop(),x=>x.records[0].sample.testOnly=true,x=>x.records[0].sample.cargoBuildObservations[1].freshLines.pop(),x=>x.records[1].sample.cargoBuildObservations[3].compilingLines.push(' Compiling node000 v0.1.0'),x=>x.records[0].sample.lifecycle.cleanup.complete=false]){const bad=structuredClone(gate);mutate(bad);assert.throws(()=>validatePreviousGate(bad,identity));}
const clean={sampleStarted:true,runtimeAttempted:true,runtimeReady:true,runtimeState:{restored:false},sample};
assert.equal(cleanupAdmission(clean),null);
assert.match(cleanupAdmission({...clean,sample:null}),/missing/);
assert.match(cleanupAdmission({...clean,sample:{...sample,error:{uncertain:true}}}),/uncertain/);
assert.match(cleanupAdmission({...clean,sample:{...sample,remainingContainers:['live']}}),/containers/);
assert.match(cleanupAdmission({...clean,sample:{...sample,compilerSessions:[{uncertain:true}]}}),/uncertain/);
assert.match(cleanupAdmission({...clean,sample:{...sample,product:'layerfs'}}),/knowledge/);
assert.equal(cleanupAdmission({...clean,sample:{...sample,product:'layerfs',remainingMountsKnown:true,remainingContainersKnown:true}}),null);
assert.match(cleanupAdmission({sampleStarted:false,runtimeAttempted:true,runtimeReady:false,runtimeState:{restored:false}}),/rollback/);
assert.equal(cleanupAdmission({sampleStarted:false,runtimeAttempted:true,runtimeReady:false,runtimeState:{restored:true}}),null);
assert.match(cleanupAdmission({sampleStarted:false,runtimeAttempted:true,runtimeReady:false,runtimeState:null}),/rollback/);
assert.equal(cleanupAdmission({sampleStarted:false,runtimeAttempted:false,runtimeReady:false,runtimeState:null}),null);
console.log('PASS: pure 2GiB measured-capacity guards, immutable image/protocol/pilot binding, exact 17-package incremental gate, uncertain-sample/runtime cleanup refusal. No Docker/mount/CI execution.');

const budget={startedEpochSeconds:1000,deadlineEpochSeconds:3400,nowEpochSeconds:1100};
assert.equal(budgetAdmission(budget).admitted,true);
assert.throws(()=>budgetAdmission({...budget,nowEpochSeconds:3000}),BudgetBlocked);
assert.throws(()=>budgetAdmission({...budget,deadlineEpochSeconds:3701}));
assert.throws(()=>budgetAdmission({...budget,cleanupReserveSeconds:299}));
assert.throws(()=>budgetAdmission({...budget,nowEpochSeconds:NaN}));
// Later incremental/sample admission uses the SAME deadline, not another20min.
assert.equal(budgetAdmission({...budget,nowEpochSeconds:2500}).remainingSeconds,900);
assert.throws(()=>budgetAdmission({...budget,nowEpochSeconds:2921}),BudgetBlocked);
console.log('PASS: shared absolute job deadline refuses later samples without480s operation/cleanup reserve; no timeout kills.');

const runnerSource=fs.readFileSync(new URL('./stress_cargo_compare.mjs',import.meta.url),'utf8');
assert.doesNotMatch(runnerSource,/performance\.now\(\)>=deadline/);
assert.ok(runnerSource.indexOf('admitSampler(r,admitBudget);')>runnerSource.indexOf('r.runtimeReadySpace=physicalSpace(mount)'));
assert.ok(runnerSource.indexOf('admitSampler(r,admitBudget);')<runnerSource.indexOf('sampleStarted=true;'));
let launch=false;const record={};
assert.throws(()=>{admitSampler(record,()=>budgetAdmission({...budget,nowEpochSeconds:3000}));launch=true;},BudgetBlocked);
assert.equal(launch,false);assert.equal(record.postRuntimeBudgetAdmission,undefined);
admitSampler(record,()=>budgetAdmission({...budget,nowEpochSeconds:2500}));
assert.equal(record.postRuntimeBudgetAdmission.remainingSeconds,900);
console.log('PASS: actual post-runtime admission hook refuses launch after consumed budget; no stale per-invocation deadline reference.');
