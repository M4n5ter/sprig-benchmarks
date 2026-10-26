// Pure glue regression: no process, Docker, mount, compiler or product execution.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {abcOrder,abcSchedule,validateABCMode} from './stress_cargo_directory_abc.mjs';
import {budgetAdmission,BudgetBlocked,cleanupAdmission,IMAGE_BYTES} from './stress_cargo_compare.mjs';
const source=fs.readFileSync(new URL('./stress_cargo_compare.mjs',import.meta.url),'utf8');
for(const fragment of ['validateABCMode({rounds,profile,ownAB,latestDirect,productionSha})','validateABCPlan(JSON.parse(abcPlanBytes),abcProducts)','abcPlanSha256:sha(abcPlanBytes)','abcSchedule(incremental).map','validateABCPreviousGate(JSON.parse(bytes),identity','r.verifiedProductInputs=structuredClone(variant)','r.verifiedProductInputsAfter=structuredClone(variant)','records.length===rounds*(abc?3:2)','if(!abc)records.push(r)','ordinary ABC forbids pressure'])assert.ok(source.includes(fragment),fragment);
assert.ok(source.includes("assert.equal(process.env.SPRIG_WRITABLE_DIAGNOSTICS,undefined"));
assert.ok(source.includes("assert.equal(process.env.SPRIG_LIFECYCLE_TRACE,undefined"));
assert.ok(source.indexOf('admitSampler(r,admitBudget);')<source.indexOf('sampleStarted=true;'));
assert.ok(source.includes("latestDirect?[2]:ownAB?[1,4]:[1,3]"),'old rounds remain bounded');
assert.equal(IMAGE_BYTES,4*1024**3);
for(const mode of [0,1]){const plan=abcSchedule(mode);assert.equal(plan.length,18);for(let block=0;block<6;block++)assert.deepEqual(plan.slice(3*block,3*block+3).map(r=>r.product),abcOrder(mode,block));}
assert.throws(()=>validateABCMode({rounds:6,profile:'normal-rename2-1024-v2',ownAB:false,latestDirect:false,productionSha:undefined}));
assert.throws(()=>budgetAdmission({startedEpochSeconds:1000,deadlineEpochSeconds:3400,nowEpochSeconds:2921}),BudgetBlocked);
assert.match(cleanupAdmission({sampleStarted:true,runtimeAttempted:true,runtimeReady:true,sample:{error:{uncertain:true}}}),/uncertain/);
console.log('PASS: exclusive ABC glue, fixed36 positions, pressure/trace guards and original budget/cleanup admission. No runtime.');
