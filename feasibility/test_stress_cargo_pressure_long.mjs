import assert from 'node:assert/strict';
import {experimentSpec,validateProducts,sampleOrder,validatePressureSample,validateOwnPreviousGate,LONG_PRESSURE_SPEC,LONG_AB_PINS,AB_REPEATED_SCHEMA} from './stress_cargo_own_ab.mjs';
const profile=LONG_PRESSURE_SPEC.profile,experiment=experimentSpec(profile);
const products=Object.entries(LONG_AB_PINS).map(([label,sha],i)=>({label,sha,binary:`/fixed/${label}`,sourcePath:`/sources/${label}`,binarySha256:String(i+1).repeat(64)}));
assert.equal(validateProducts(products,profile),products);assert.throws(()=>validateProducts(products));
for(const mode of [0,1])assert.equal(Array.from({length:4},(_,round)=>sampleOrder(products,mode,round,profile)).filter(row=>row[0].label==='sprig-baseline').length,2);
const workers=[0,1].map(worker=>{
 const samplesNanoseconds={rename:[],write:[],read:[],metadata:[]},operationIntervals=[];
 for(let ordinal=0;ordinal<5120;ordinal++){
  const operation=['rename-away','write','read','metadata','rename-back'][ordinal%5],startNs=worker*10+ordinal*3+1;
  operationIntervals.push({iteration:Math.floor(ordinal/5),operation,startNs,endNs:startNs+1,durationNs:1});samplesNanoseconds[operation.startsWith('rename-')?'rename':operation].push(1);
 }
 return {worker,startedNs:worker*10,finishedNs:worker*10+15360,completedIterations:1024,samplesNanoseconds,operationIntervals};
});
const pressure={schema:experiment.pressure.schema,profile,spec:LONG_PRESSURE_SPEC,ok:true,allWitnessesVerified:true,clock:'CLOCK_MONOTONIC',monotonicOriginNs:'17000000001234567890',workers,workerLifetimeOverlapNs:15350};
const sample={normalPressure:pressure,normalPressureScriptSha256:experiment.pressure.scriptSha256,normalPressureRawSha256:'f'.repeat(64),phase_seconds:{normal_pressure:1},checkpointTreeOracle:{entries:[{path:'pressure-rename2/observations.json',sha256:'f'.repeat(64)}]}};
assert.equal(validatePressureSample(sample,experiment),true);
assert.throws(()=>validatePressureSample(sample,experimentSpec('normal-rename2-v1')));
for(const mutate of [s=>s.normalPressure.clock='CLOCK_REALTIME',s=>s.normalPressure.monotonicOriginNs=1,s=>s.normalPressure.monotonicOriginNs='01',s=>s.normalPressure.monotonicOriginNs=String(2n**64n),s=>s.normalPressure.workers[0].operationIntervals.pop(),s=>s.normalPressure.workers[0].operationIntervals[0].iteration=true,s=>s.normalPressure.workers[0].operationIntervals[1].operation='read',s=>s.normalPressure.workers[0].operationIntervals[0].endNs=2**53,s=>s.normalPressure.workers[0].operationIntervals[1].startNs=0,s=>s.normalPressure.workers[0].operationIntervals[0].durationNs=2,s=>s.normalPressure.workers[0].samplesNanoseconds.rename[0]=2,s=>s.normalPressureScriptSha256='0'.repeat(64),s=>s.checkpointTreeOracle.entries=[]]){const value=structuredClone(sample);mutate(value);assert.throws(()=>validatePressureSample(value,experiment));}
const identity={image:'sha256:'+'a'.repeat(64),protocolSha256:'b'.repeat(64),fixtureManifestSha256:'c'.repeat(64),imageBytes:4294967296,resourceProtocol:'sprig-cargo-resource-4g-v1',abManifestSha256:'d'.repeat(64),abProducts:products,sharedJobBudget:{startedEpochSeconds:100,deadlineEpochSeconds:2500},experimentSpec:experiment};
const gate={...identity,schema:AB_REPEATED_SCHEMA,complete:true,status:'passed',incremental:0,rounds:4,records:[]};
for(let round=0;round<4;round++)for(const p of sampleOrder(products,0,round,profile))gate.records.push({product:p.label,round,incremental:0,correct:true,status:'passed',sampleReturncode:0,rawReportSha256:'e'.repeat(64),sample:{...structuredClone(sample),binarySha256:p.binarySha256,production_sha:p.sha}});
assert.equal(validateOwnPreviousGate(gate,identity,s=>validatePressureSample(s,experiment)),true);
for(const mutate of [g=>g.records.pop(),g=>g.records.reverse(),g=>g.records[0].sample.production_sha='0'.repeat(40),g=>g.experimentSpec=experimentSpec('normal-rename2-v1')]){const value=structuredClone(gate);mutate(value);assert.throws(()=>validateOwnPreviousGate(value,identity,s=>validatePressureSample(s,experiment)));}
console.log('PASS: separate long-profile fixed pins, exact monotonic intervals/order/counts, witnesses and full balanced prerequisite; legacy profile not relabeled.');
