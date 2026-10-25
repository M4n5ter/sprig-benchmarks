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
