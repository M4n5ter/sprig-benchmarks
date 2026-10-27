// Inert selection/glue tests only: no process, product, compiler, mount or Docker.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import * as historical from './stress_cargo_directory_abc.mjs';
import * as current from './stress_cargo_clean_sync_ttl.mjs';
import {selectABCIdentity,budgetAdmission,BudgetBlocked,cleanupAdmission,IMAGE_BYTES} from './stress_cargo_compare.mjs';
assert.equal(selectABCIdentity({}),null);
assert.equal(selectABCIdentity({ownAB:true}),null);
assert.equal(selectABCIdentity({latestDirect:true}),null);
assert.equal(selectABCIdentity({directory:true}),historical);
assert.equal(selectABCIdentity({cleanSync:true}),current);
for(const keys of [['directory','cleanSync'],['ownAB','cleanSync'],['latestDirect','cleanSync'],['directory','ownAB'],['directory','latestDirect'],['ownAB','latestDirect']]){
 assert.throws(()=>selectABCIdentity(Object.fromEntries(keys.map(k=>[k,true]))),/cannot be combined/);
}
for(const invalid of [1,'true',null,{},[]])assert.throws(()=>selectABCIdentity({cleanSync:invalid}));
const source=fs.readFileSync(new URL('./stress_cargo_compare.mjs',import.meta.url),'utf8');
for(const fragment of ["process.env.STRESS_CARGO_CLEAN_SYNC_TTL_PRODUCTS!==undefined",'abcIdentity??directoryABC',"cleanSync?'clean-sync-ttl':'directory-abc'",'path.isAbsolute(abcManifestPath)','fs.readFileSync(abcManifestPath).equals(abcBytes)','validateABCPlan(JSON.parse(abcPlanBytes),abcProducts)','abcPlanSha256:sha(abcPlanBytes)','abcSchedule(incremental).map','validateABCPreviousGate(JSON.parse(bytes),identity','r.verifiedProductInputs=structuredClone(variant)','r.verifiedProductInputsAfter=structuredClone(variant)','records.length===rounds*(abc?3:2)','if(!abc)records.push(r)','ordinary ABC forbids pressure',"latestDirect?[2]:ownAB?[1,4]:[1,3]"])assert.ok(source.includes(fragment),fragment);
for(const variable of ['SPRIG_WRITABLE_DIAGNOSTICS','SPRIG_LIFECYCLE_TRACE'])assert.ok(source.includes(`assert.equal(process.env.${variable},undefined`));
assert.ok(source.indexOf('admitSampler(r,admitBudget);')<source.indexOf('sampleStarted=true;'));
assert.equal(IMAGE_BYTES,4*1024**3);
for(const mode of [0,1]){
 const schedule=current.abcSchedule(mode);assert.equal(schedule.length,18);
 for(let round=0;round<6;round++)assert.deepEqual(schedule.slice(round*3,round*3+3).map(r=>r.product),current.abcOrder(mode,round));
 assert.ok(schedule.every(r=>['sprig-baseline','sprig-clean-sync','sprig-read-ttl'].includes(r.product)));
}
assert.throws(()=>budgetAdmission({startedEpochSeconds:1000,deadlineEpochSeconds:3400,nowEpochSeconds:2921}),BudgetBlocked);
assert.match(cleanupAdmission({sampleStarted:true,runtimeAttempted:true,runtimeReady:true,sample:{error:{uncertain:true}}}),/uncertain/);
console.log('PASS: fixed clean-sync/TTL selection, historical isolation, full36 glue and original resource/cleanup/trace guards. No runtime.');
