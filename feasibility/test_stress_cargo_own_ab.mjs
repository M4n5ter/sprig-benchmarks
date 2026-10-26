import assert from 'node:assert/strict';
import {AB_SCHEMA,AB_PINS,validateProducts,sampleOrder,validateOwnPreviousGate} from './stress_cargo_own_ab.mjs';
const products=Object.entries(AB_PINS).map(([label,sha],i)=>({label,sha,binary:`/fixed/${label}`,sourcePath:`/sources/${label}`,binarySha256:String(i+1).repeat(64)}));
const copy=x=>structuredClone(x);
assert.deepEqual(validateProducts(products),products);
assert.deepEqual(sampleOrder(products,0).map(p=>p.label),['sprig-baseline','sprig-candidate']);
assert.deepEqual(sampleOrder(products,1).map(p=>p.label),['sprig-candidate','sprig-baseline']);
for(const mutate of [p=>p.pop(),p=>p.reverse(),p=>p[1].label=p[0].label,p=>p[0].label='../escape',p=>p[0].sha='main',p=>p[0].sha='0'.repeat(40),p=>p[0].binarySha256='bad',p=>p[1].binarySha256=p[0].binarySha256,p=>p[1].binary=p[0].binary,p=>p[1].sourcePath=p[0].sourcePath,p=>p[0].binary='relative',p=>p[0].sourcePath='/sources/../sources/alias',p=>p[0].extra=true]){const p=copy(products);mutate(p);assert.throws(()=>validateProducts(p));}
const identity={image:'sha256:'+'a'.repeat(64),protocolSha256:'b'.repeat(64),fixtureManifestSha256:'c'.repeat(64),imageBytes:4294967296,resourceProtocol:'sprig-cargo-resource-4g-v1',abManifestSha256:'d'.repeat(64),abProducts:products,sharedJobBudget:{startedEpochSeconds:100,deadlineEpochSeconds:2500}};
const gate={schema:AB_SCHEMA,complete:true,status:'passed',incremental:0,rounds:1,...copy(identity),records:products.map(p=>({product:p.label,correct:true,status:'passed',incremental:0,round:0,sampleReturncode:0,sample:{production_sha:p.sha,binarySha256:p.binarySha256,ok:true,archiveVerified:true}}))};
let calls=0;const validate=(s,p,mode)=>{calls++;assert.equal(mode,0);assert.equal(s.ok,true);assert.equal(s.archiveVerified,true);};
assert.equal(validateOwnPreviousGate(gate,identity,validate),true);assert.equal(calls,2);
for(const key of ['image','protocolSha256','fixtureManifestSha256','imageBytes','resourceProtocol','abManifestSha256','abProducts','sharedJobBudget']){const g=copy(gate);g[key]=null;assert.throws(()=>validateOwnPreviousGate(g,identity,validate));}
for(const mutate of [g=>g.schema='sprig-stress-cargo-comparison-v2',g=>g.complete=false,g=>g.status='running',g=>g.incremental=1,g=>g.rounds=3,g=>g.records.pop(),g=>g.records[1]=copy(g.records[0]),g=>g.records[0].correct=false,g=>g.records[0].status='cleanup_blocked',g=>g.records[0].sampleReturncode=1,g=>g.records[0].sample.production_sha='0'.repeat(40),g=>g.records[0].sample.binarySha256='0'.repeat(64),g=>g.records[0].sample.ok=false,g=>g.records[0].sample.archiveVerified=false]){const g=copy(gate);mutate(g);assert.throws(()=>validateOwnPreviousGate(g,identity,validate));}
console.log('PASS: fixed distinct own-Sprig pins/hashes/labels/paths; opposite per-mode order; complete same-identity/deadline prerequisite and delegated positive/archive gates. Offline only.');
// Same-mode reverse order, unlike the historical one-pair mode offset.
const {AB_REPEATED_SCHEMA,ORDINARY_EXPERIMENT}=await import('./stress_cargo_own_ab.mjs');
for(const mode of [0,1]){
 const orders=Array.from({length:4},(_,round)=>sampleOrder(products,mode,round).map(p=>p.label));
 assert.equal(orders.filter(x=>x[0]==='sprig-baseline').length,2);
 assert.equal(orders.filter(x=>x[0]==='sprig-candidate').length,2);
 assert.notDeepEqual(orders[0],orders[1]);
}
for(const round of [-1,4,0.5,'0',null])assert.throws(()=>sampleOrder(products,0,round));
const repeatedIdentity={...copy(identity),experimentSpec:copy(ORDINARY_EXPERIMENT)};
const repeated={...copy(gate),...copy(repeatedIdentity),schema:AB_REPEATED_SCHEMA,rounds:4,records:[]};
for(let round=0;round<4;round++)for(const p of sampleOrder(products,0,round))repeated.records.push({...copy(gate.records.find(r=>r.product===p.label)),round,rawReportSha256:'e'.repeat(64)});
assert.equal(validateOwnPreviousGate(repeated,repeatedIdentity,validate),true);
for(const mutate of [g=>g.records.reverse(),g=>g.records.pop(),g=>g.records[2].round=0,g=>g.rounds=3,g=>g.schema=AB_SCHEMA,g=>g.experimentSpec.profile='pressure',g=>g.records[0].rawReportSha256=null,g=>g.records[0].correct=false,g=>g.records[0].sample.archiveVerified=false]){const g=copy(repeated);mutate(g);assert.throws(()=>validateOwnPreviousGate(g,repeatedIdentity,validate));}
assert.throws(()=>validateOwnPreviousGate(gate,repeatedIdentity,validate));
console.log('PASS: four bounded rounds; same-mode AB/BA balance; exact complete repeated prerequisite; no legacy/pressure gate pooling.');
