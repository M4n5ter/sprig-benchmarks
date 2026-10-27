// Inert selection/glue inspection, never executes the runtime driver.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import * as directory from './stress_cargo_directory_abc.mjs';
import * as journalTTL from './stress_cargo_clean_sync_ttl.mjs';
import * as current from './stress_cargo_verified_read_reuse.mjs';
import {selectABCIdentity,budgetAdmission,BudgetBlocked,cleanupAdmission,IMAGE_BYTES} from './stress_cargo_compare.mjs';
assert.equal(selectABCIdentity({verifiedRead:true}),current);
assert.equal(selectABCIdentity({directory:true}),directory);assert.equal(selectABCIdentity({cleanSync:true}),journalTTL);
for(const other of ['directory','cleanSync','ownAB','latestDirect'])assert.throws(()=>selectABCIdentity({verifiedRead:true,[other]:true}),/cannot be combined/);
for(const value of [1,'true',null,{},[]])assert.throws(()=>selectABCIdentity({verifiedRead:value}));
const source=fs.readFileSync(new URL('./stress_cargo_compare.mjs',import.meta.url),'utf8');
for(const text of ["process.env.STRESS_CARGO_VERIFIED_READ_REUSE_PRODUCTS!==undefined","verifiedRead?'verified-read-reuse'",
 'expectedRecords:rounds*(verifiedRead?2:abc?3:2)','verifiedRead?records.length===rounds*2:records.length===rounds*(abc?3:2)',
 'abcSchedule(incremental).map','validateABCPreviousGate(JSON.parse(bytes),identity','validateABCPlan(JSON.parse(abcPlanBytes),abcProducts)',
 'r.verifiedProductInputs=structuredClone(variant)','r.verifiedProductInputsAfter=structuredClone(variant)',
 'fs.readFileSync(abcManifestPath).equals(abcBytes)','fs.readFileSync(abcPlanPath).equals(abcPlanBytes)',
 'if(!abc)records.push(r)','ordinary ABC forbids pressure',"latestDirect?[2]:ownAB?[1,4]:[1,3]"])assert.ok(source.includes(text),text);
for(const name of ['SPRIG_WRITABLE_DIAGNOSTICS','SPRIG_LIFECYCLE_TRACE'])assert.ok(source.includes(`assert.equal(process.env.${name},undefined`));
assert.ok(source.indexOf('admitSampler(r,admitBudget);')<source.indexOf('sampleStarted=true;'));
assert.equal(IMAGE_BYTES,4*1024**3);
assert.throws(()=>budgetAdmission({startedEpochSeconds:1000,deadlineEpochSeconds:3400,nowEpochSeconds:2921}),BudgetBlocked);
assert.match(cleanupAdmission({sampleStarted:true,runtimeAttempted:true,runtimeReady:true,sample:{error:{uncertain:true}}}),/uncertain/);
for(const mode of [0,1])assert.equal(current.abcSchedule(mode).length,12);
console.log('PASS: verified-read A/B glue, fixed24, historical selection/rounds and original budget/trace/cleanup controls. No runtime.');
