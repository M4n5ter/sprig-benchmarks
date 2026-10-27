// Inert identity/schedule fixtures only. No product, process, compiler or mount.
import assert from 'node:assert/strict';
import * as current from './stress_cargo_verified_read_reuse.mjs';
import * as journalTTL from './stress_cargo_clean_sync_ttl.mjs';
import * as directory from './stress_cargo_directory_abc.mjs';
const {ABC_SCHEMA,ABC_PINS,ABC_EXPERIMENT,validateABCProducts,abcOrder,abcSchedule,
 validateABCMode,createABCPlan,validateABCPlan,validateABCPreviousGate}=current;
const copy=x=>structuredClone(x);
const products=Object.entries(ABC_PINS).map(([label,sha],i)=>({label,sha,
 sourcePath:`/sources/${label}`,binary:`/sources/${label}/target/release/sprig`,binarySha256:String(i+1).repeat(64)}));
const labels=['sprig-baseline','sprig-verified-read-reuse'];
assert.deepEqual(ABC_PINS,{'sprig-baseline':'4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
 'sprig-verified-read-reuse':'f61ce655d9270e206d97e20bc104644c821e4e5d'});
assert.equal(ABC_SCHEMA,'sprig-stress-cargo-verified-read-reuse-v1');
assert.deepEqual(ABC_EXPERIMENT,{schema:'sprig-cargo-verified-read-reuse-experiment-v1',profile:'ordinary',
 roundsPerMode:6,incrementalModes:[0,1],order:'six-alternating-reverse-mode1',pressure:null});
assert.ok(Object.isFrozen(ABC_PINS)&&Object.isFrozen(ABC_EXPERIMENT)&&Object.isFrozen(ABC_EXPERIMENT.incrementalModes));
assert.equal(validateABCProducts(products),products);
for(const bad of [null,undefined,{},[],products.slice(0,1),[...products,products[0]]])assert.throws(()=>validateABCProducts(bad));
for(const change of [p=>p.reverse(),p=>p[1]=null,p=>p[1].label='sprig-candidate',p=>p[1].sha='main',
 p=>p[1].sha='0'.repeat(40),p=>p[1].sha=ABC_PINS['sprig-baseline'],p=>p[1].extra=true,
 p=>delete p[1].sourcePath,p=>p[1].binarySha256='BAD',p=>p[1].binarySha256='A'.repeat(64)]){
 const p=copy(products);change(p);assert.throws(()=>validateABCProducts(p));
}
for(const key of ['binary','sourcePath','binarySha256']){const p=copy(products);p[1][key]=p[0][key];assert.throws(()=>validateABCProducts(p));}
for(const key of ['binary','sourcePath'])for(const value of ['relative','/sources/../alias','//sources/alias','/sources/alias/','/',null,42,'/x\nnext','/x\\alias']){
 const p=copy(products);p[1][key]=value;assert.throws(()=>validateABCProducts(p));
}
for(const old of [journalTTL,directory]){
 const p=Object.entries(old.ABC_PINS).map(([label,sha],i)=>({label,sha,sourcePath:`/old/${label}`,binary:`/old/${label}/sprig`,binarySha256:String(i+1).repeat(64)}));
 assert.equal(old.validateABCProducts(p),p);assert.throws(()=>validateABCProducts(p));assert.throws(()=>old.validateABCProducts(products));
 for(const pin of Object.values(old.ABC_PINS)){const wrong=copy(products);wrong[1].sha=pin;assert.throws(()=>validateABCProducts(wrong));}
 assert.throws(()=>validateABCPlan(old.createABCPlan(p)));assert.throws(()=>old.validateABCPlan(createABCPlan(products)));
}
for(const mode of [0,1]){
 const orders=Array.from({length:6},(_,round)=>abcOrder(mode,round));
 assert.deepEqual(orders,Array.from({length:6},(_,r)=>(r+mode)%2?[...labels].reverse():labels));
 for(const label of labels)for(const position of [0,1])assert.equal(orders.filter(x=>x[position]===label).length,3);
 const schedule=abcSchedule(mode);assert.equal(schedule.length,12);
 assert.deepEqual(schedule,orders.flatMap((order,round)=>order.map((product,position)=>({product,incremental:mode,round,position,order}))));
 schedule[0].order.reverse();assert.deepEqual(abcSchedule(mode)[0].order,orders[0]);assert.deepEqual(schedule[1].order,orders[0]);
}
for(const mode of [-1,2,.5,'0',null,undefined,true,NaN]){assert.throws(()=>abcOrder(mode,0));assert.throws(()=>abcSchedule(mode));}
for(const round of [-1,6,.5,'0',null,undefined,true,NaN])assert.throws(()=>abcOrder(0,round));
const mode={rounds:6,profile:'ordinary',ownAB:false,latestDirect:false,productionSha:undefined};
assert.equal(validateABCMode(mode),true);
for(const [key,values] of Object.entries({rounds:[1,2,3,4,5,7,'6'],profile:['normal-rename2-v1','diagnostic',null],
 ownAB:[true,undefined,null,0],latestDirect:[true,undefined,null,0],productionSha:[ABC_PINS[labels[0]],'',null]}))
 for(const value of values)assert.throws(()=>validateABCMode({...mode,[key]:value}));
const plan=createABCPlan(products);assert.equal(validateABCPlan(plan),plan);assert.equal(plan.records.length,24);
assert.deepEqual(plan.records,[...abcSchedule(0),...abcSchedule(1)]);
for(const change of [p=>p.schema='sprig-cargo-clean-sync-ttl-plan-v1',p=>p.extra=true,p=>delete p.abcExperiment,
 p=>p.abcExperiment.order='six-permutations-reverse-mode1',p=>p.abcExperiment.pressure={},p=>p.records.pop(),
 p=>p.records.push(copy(p.records[0])),p=>p.records.reverse(),p=>p.records[12]=copy(p.records[0]),
 p=>p.records[0].order.reverse(),p=>p.records[0].position=1,p=>p.records[0].product='layerfs',p=>p.records[0].extra=true]){
 const p=copy(plan);change(p);assert.throws(()=>validateABCPlan(p));
}
const identity={image:'sha256:'+'a'.repeat(64),protocolSha256:'b'.repeat(64),fixtureManifestSha256:'c'.repeat(64),
 imageBytes:4*1024**3,resourceProtocol:'sprig-cargo-resource-4g-v1',abcManifestSha256:'d'.repeat(64),abcPlanSha256:'e'.repeat(64),
 abcProducts:copy(products),abcExperiment:copy(ABC_EXPERIMENT),sharedJobBudget:{startedEpochSeconds:100,deadlineEpochSeconds:2500,minimumSampleSeconds:180,cleanupReserveSeconds:300}};
const gate={schema:ABC_SCHEMA,complete:true,status:'passed',incremental:0,rounds:6,expectedRecords:12,...copy(identity),
 records:abcSchedule(0).map(expected=>{const p=products.find(p=>p.label===expected.product);return {...expected,correct:true,status:'passed',sampleReturncode:0,
 rawReportSha256:'f'.repeat(64),rawReportPath:`results/stress-cargo-${p.label}-inc0-${expected.round}.json`,
 verifiedProductInputs:copy(p),verifiedProductInputsAfter:copy(p),sample:{production_sha:p.sha,binarySha256:p.binarySha256,ok:true,archiveVerified:true,cleanupVerified:true}};})};
let calls=[];const validate=(sample,p,mode)=>{calls.push(sample);assert.equal(mode,0);assert.equal(sample.production_sha,p.sha);
 assert.equal(sample.ok,true);assert.equal(sample.archiveVerified,true);assert.equal(sample.cleanupVerified,true);};
assert.equal(validateABCPreviousGate(gate,identity,validate),true);assert.equal(calls.length,12);
for(let i=0;i<12;i++)assert.equal(calls[i],gate.records[i].sample,'unchanged original sample reaches oracle');
for(const old of [journalTTL,directory])assert.throws(()=>old.validateABCPreviousGate(gate,identity,validate));
for(const key of Object.keys(identity)){
 const g=copy(gate),id=copy(identity);delete g[key];delete id[key];assert.throws(()=>validateABCPreviousGate(g,id,validate));
}
for(const key of ['protocolSha256','fixtureManifestSha256','abcManifestSha256','abcPlanSha256']){
 const g=copy(gate),id=copy(identity);g[key]=id[key]='not-a-sha';assert.throws(()=>validateABCPreviousGate(g,id,validate));
}
for(const change of [g=>g.schema=journalTTL.ABC_SCHEMA,g=>g.complete=false,g=>g.status='running',g=>g.incremental=1,
 g=>g.rounds=4,g=>g.expectedRecords=18,g=>g.records.pop(),g=>g.records.push(copy(g.records[0])),g=>g.records.reverse(),
 g=>g.records[1]=copy(g.records[0]),g=>g.records[0].product='sprig-clean-sync',g=>g.records[0].position=1,
 g=>g.records[0].round=1,g=>g.records[0].incremental=1,g=>g.records[0].order.reverse(),g=>g.records[0].correct=false,
 g=>g.records[0].status='cleanup_blocked',g=>g.records[0].sampleReturncode=1,g=>g.records[0].sampleReturncode='0',
 g=>g.records[0].cleanupErrors=['uncertain'],g=>g.records[0].cleanupErrors=false,g=>g.records[0].error={},
 g=>delete g.records[0].rawReportSha256,g=>g.records[0].rawReportPath='results/../outside.json',
 g=>delete g.records[0].verifiedProductInputs,g=>delete g.records[0].verifiedProductInputsAfter,
 g=>g.records[0].verifiedProductInputs=copy(products[1]),g=>g.records[0].verifiedProductInputsAfter=copy(products[1]),
 g=>g.records[0].sample.production_sha=ABC_PINS[labels[1]],g=>g.records[0].sample.binarySha256='0'.repeat(64),
 g=>g.records[0].sample.ok=false,g=>g.records[0].sample.archiveVerified=false,g=>g.records[0].sample.cleanupVerified=false,
 g=>g.records[0].sample.normalPressure={},g=>g.records[0].sample.normalPressureScriptSha256='a'.repeat(64),
 g=>g.records[0].sample.normalPressureRawSha256='a'.repeat(64),g=>g.records[0].sample.phase_seconds={normal_pressure:0},
 g=>g.sharedJobBudget.deadlineEpochSeconds++,g=>g.abcExperiment.pressure={}]){
 const g=copy(gate);change(g);assert.throws(()=>validateABCPreviousGate(g,identity,validate));
}
for(const bad of [null,undefined,{},[]])assert.throws(()=>validateABCPreviousGate(bad,identity,validate));
assert.throws(()=>validateABCPreviousGate(gate,identity,undefined));
const error=new Error('oracle decisive');assert.throws(()=>validateABCPreviousGate(gate,identity,()=>{throw error;}),e=>e===error);
console.log('PASS: distinct fixed verified-read A/B, balanced 24-position plan, all12 inc0 prerequisite and original raw/oracle gates. Inert fixtures only.');
