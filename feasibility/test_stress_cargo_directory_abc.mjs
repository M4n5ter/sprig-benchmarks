// Pure fixtures only: no product build, runtime, mount or benchmark execution.
import assert from 'node:assert/strict';
import {
 ABC_SCHEMA,ABC_EXPERIMENT,ABC_PINS,validateABCProducts,abcOrder,abcSchedule,
 validateABCMode,createABCPlan,validateABCPlan,validateABCPreviousGate,
} from './stress_cargo_directory_abc.mjs';

const copy=value=>structuredClone(value);
const products=Object.entries(ABC_PINS).map(([label,sha],i)=>({
 label,sha,binary:`/fixed/${label}/target/release/sprig`,
 binarySha256:String(i+1).repeat(64),sourcePath:`/sources/${label}`,
}));
const labels=['sprig-baseline','sprig-count','sprig-narrow'];
assert.equal(ABC_SCHEMA,'sprig-stress-cargo-directory-abc-v1');
assert.deepEqual(ABC_PINS,{
 'sprig-baseline':'4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
 'sprig-count':'104497aefcadc41b1528d7263039c977b77305f8',
 'sprig-narrow':'5ef2539af3f07b0a2fc87b3d02f7324a827e8798',
});
assert.deepEqual(ABC_EXPERIMENT,{
 schema:'sprig-cargo-directory-abc-experiment-v1',profile:'ordinary',roundsPerMode:6,
 incrementalModes:[0,1],order:'six-permutations-reverse-mode1',pressure:null,
});
assert.ok(Object.isFrozen(ABC_PINS)&&Object.isFrozen(ABC_EXPERIMENT)&&Object.isFrozen(ABC_EXPERIMENT.incrementalModes));
assert.equal(validateABCProducts(products),products);
for(const malformed of [undefined,null,{},[],products.slice(0,2),[...products,products[0]]])assert.throws(()=>validateABCProducts(malformed));
for(const mutate of [
 p=>p.reverse(),p=>p[1]=null,p=>p[1].label=p[0].label,p=>p[0].label='../escape',
 p=>p[0].sha='main',p=>p[1].sha=ABC_PINS['sprig-narrow'],p=>p[2].sha='0'.repeat(40),
 p=>p[0].binarySha256='bad',p=>p[0].binarySha256='A'.repeat(64),p=>delete p[1].binarySha256,
 p=>p[0].extra=true,p=>delete p[0].sourcePath,
]){const p=copy(products);mutate(p);assert.throws(()=>validateABCProducts(p));}
for(const key of ['binary','sourcePath','binarySha256'])for(const [from,to] of [[0,1],[0,2],[1,2]]){
 const p=copy(products);p[to][key]=p[from][key];assert.throws(()=>validateABCProducts(p));
}
for(const key of ['binary','sourcePath'])for(const value of [
 'relative','../escape','/sources/../alias','/sources/./alias','//sources/alias','/sources//alias',
 '/sources/alias/','/','/sources/alias\0suffix','/sources/alias\nnext','/sources\\alias',null,42,
]){const p=copy(products);p[0][key]=value;assert.throws(()=>validateABCProducts(p));}

const expectedOrders=['ABC','CBA','BAC','CAB','ACB','BCA'].map(order=>[...order].map(letter=>labels['ABC'.indexOf(letter)]));
for(const incremental of [0,1]){
 const orders=Array.from({length:6},(_,round)=>abcOrder(incremental,round));
 assert.deepEqual(orders,incremental===0?expectedOrders:[...expectedOrders].reverse());
 assert.equal(new Set(orders.map(order=>order.join(','))).size,6);
 for(const product of labels)for(const position of [0,1,2])assert.equal(orders.filter(order=>order[position]===product).length,2);
 for(const [a,b] of [[0,1],[0,2],[1,2]])assert.equal(orders.filter(order=>order.indexOf(labels[a])<order.indexOf(labels[b])).length,3);
 const schedule=abcSchedule(incremental);assert.equal(schedule.length,18);
 assert.deepEqual(schedule,orders.flatMap((order,round)=>order.map((product,position)=>({product,incremental,round,position,order}))));
 schedule[0].order.reverse();assert.deepEqual(abcSchedule(incremental)[0].order,orders[0]);
 assert.deepEqual(schedule[1].order,orders[0],'each record has its own order snapshot');
}
for(const incremental of [-1,2,.5,'0',null,undefined,true,NaN]){
 assert.throws(()=>abcOrder(incremental,0));assert.throws(()=>abcSchedule(incremental));
}
for(const round of [-1,6,.5,'0',null,undefined,true,NaN])assert.throws(()=>abcOrder(0,round));
const firstOrder=abcOrder(0,0);firstOrder.reverse();assert.deepEqual(abcOrder(0,0),labels);

const mode={rounds:6,profile:'ordinary',ownAB:false,latestDirect:false,productionSha:undefined};
assert.equal(validateABCMode(mode),true);
for(const [key,values] of Object.entries({
 rounds:[1,2,3,4,5,7,'6',null],profile:['normal-rename2-v1','normal-rename2-1024-v2','diagnostic',null],
 ownAB:[true,undefined,null,0],latestDirect:[true,undefined,null,0],productionSha:[ABC_PINS['sprig-baseline'],'',null],
}))for(const value of values)assert.throws(()=>validateABCMode({...mode,[key]:value}));

const plan=createABCPlan(products);
assert.deepEqual(plan,{schema:'sprig-cargo-directory-abc-plan-v1',abcExperiment:ABC_EXPERIMENT,abcProducts:products,records:[...abcSchedule(0),...abcSchedule(1)]});
assert.equal(validateABCPlan(plan),plan);assert.equal(validateABCPlan(copy(plan),products).records.length,36);
for(const mutate of [
 p=>p.schema='sprig-cargo-directory-abc-plan-v0',p=>p.extra=true,p=>delete p.abcExperiment,
 p=>p.abcExperiment.roundsPerMode=4,p=>p.abcExperiment.pressure={},p=>p.abcProducts.reverse(),
 p=>p.records.pop(),p=>p.records.push(copy(p.records[0])),p=>p.records.reverse(),
 p=>p.records[0]=copy(p.records[1]),p=>p.records[18]=copy(p.records[0]),
 p=>p.records[0].position=1,p=>p.records[0].order.reverse(),p=>p.records[0].incremental=1,
 p=>p.records[0].round=1,p=>p.records[0].product='layerfs',p=>delete p.records[0].position,
 p=>p.records[0].extra=true,
]){const p=copy(plan);mutate(p);assert.throws(()=>validateABCPlan(p));}
for(const malformed of [null,undefined,{},[]])assert.throws(()=>validateABCPlan(malformed));
const otherProducts=copy(products);otherProducts[0].binarySha256='9'.repeat(64);
assert.throws(()=>validateABCPlan(plan,otherProducts),'plan must bind the supplied manifest');

const identity={
 image:'sha256:'+'a'.repeat(64),protocolSha256:'b'.repeat(64),fixtureManifestSha256:'c'.repeat(64),
 imageBytes:4*1024**3,resourceProtocol:'sprig-cargo-resource-4g-v1',abcManifestSha256:'d'.repeat(64),
 abcPlanSha256:'e'.repeat(64),abcProducts:copy(products),abcExperiment:copy(ABC_EXPERIMENT),
 sharedJobBudget:{startedEpochSeconds:100,deadlineEpochSeconds:2500,minimumSampleSeconds:180,cleanupReserveSeconds:300},
};
const gate={
 schema:ABC_SCHEMA,complete:true,status:'passed',incremental:0,rounds:6,expectedRecords:18,...copy(identity),
 records:abcSchedule(0).map(expected=>{
  const p=products.find(product=>product.label===expected.product);
  return {...expected,correct:true,status:'passed',sampleReturncode:0,
   rawReportSha256:'f'.repeat(64),rawReportPath:`results/stress-cargo-${p.label}-inc0-${expected.round}.json`,
   verifiedProductInputs:copy(p),verifiedProductInputsAfter:copy(p),
   sample:{production_sha:p.sha,binarySha256:p.binarySha256,ok:true,archiveVerified:true,cleanupVerified:true},
  };
 }),
};
let calls=[];
const validate=(sample,p,incremental)=>{
 calls.push({sample,p,incremental});assert.equal(incremental,0);
 assert.deepEqual(p,products.find(product=>product.label===p.label));
 assert.equal(sample.ok,true);assert.equal(sample.archiveVerified,true);assert.equal(sample.cleanupVerified,true);
};
assert.equal(validateABCPreviousGate(gate,identity,validate),true);
assert.equal(calls.length,18);assert.deepEqual(calls.map(call=>call.p.label),abcSchedule(0).map(record=>record.product));
for(const [index,call] of calls.entries())assert.equal(call.sample,gate.records[index].sample,'original sample passed to oracle without rewriting');
const emptyCleanup=copy(gate);emptyCleanup.records[0].cleanupErrors=[];assert.equal(validateABCPreviousGate(emptyCleanup,identity,validate),true);
for(const key of Object.keys(identity)){
 const missing=copy(gate);delete missing[key];assert.throws(()=>validateABCPreviousGate(missing,identity,validate));
 const changed=copy(gate);changed[key]=null;assert.throws(()=>validateABCPreviousGate(changed,identity,validate));
 const bothMissing=copy(identity);delete bothMissing[key];assert.throws(()=>validateABCPreviousGate(missing,bothMissing,validate),'matching missing identities cannot pass');
 const bothNull=copy(identity);bothNull[key]=null;assert.throws(()=>validateABCPreviousGate(changed,bothNull,validate));
}
for(const key of ['protocolSha256','fixtureManifestSha256','abcManifestSha256','abcPlanSha256']){
 const g=copy(gate),id=copy(identity);g[key]=id[key]='not-a-sha';assert.throws(()=>validateABCPreviousGate(g,id,validate));
}
for(const mutate of [
 g=>g.schema='sprig-stress-cargo-own-ab-v2',g=>g.schema='sprig-stress-cargo-latest-direct-v1',
 g=>g.complete=false,g=>g.status='running',g=>g.incremental=1,g=>g.rounds=4,g=>g.expectedRecords=36,
 g=>g.records.pop(),g=>g.records.push(copy(g.records[0])),g=>g.records.reverse(),
 g=>g.records[1]=copy(g.records[0]),g=>g.records[0].product='sprig-candidate',
 g=>g.records[0].round=1,g=>g.records[0].incremental=1,g=>g.records[0].position=1,
 g=>g.records[0].order.reverse(),g=>delete g.records[0].order,g=>g.records[0].correct=false,
 g=>g.records[0].status='cleanup_blocked',g=>g.records[0].sampleReturncode=1,
 g=>g.records[0].sampleReturncode='0',g=>g.records[0].cleanupErrors=['uncertain teardown'],
 g=>g.records[0].cleanupErrors=false,g=>g.records[0].cleanupErrors=null,g=>g.records[0].error={message:'failed'},
 g=>delete g.records[0].rawReportSha256,g=>g.records[0].rawReportSha256='wrong',
 g=>g.records[0].rawReportPath='results/../outside.json',g=>delete g.records[0].rawReportPath,
 g=>g.records[0].rawReportPath=g.records[1].rawReportPath,
 g=>delete g.records[0].verifiedProductInputs,g=>delete g.records[0].verifiedProductInputsAfter,
 g=>g.records[0].verifiedProductInputs=copy(products[1]),g=>g.records[0].verifiedProductInputsAfter=copy(products[1]),
 g=>g.records[0].verifiedProductInputs.binarySha256='0'.repeat(64),
 g=>g.records[0].verifiedProductInputsAfter.sourcePath='/sources/changed',
 g=>g.records[0].verifiedProductInputsAfter.extra=true,g=>g.records[0].sample=null,
 g=>g.records[0].sample.production_sha=ABC_PINS['sprig-narrow'],g=>g.records[0].sample.binarySha256='0'.repeat(64),
 g=>g.records[0].sample.ok=false,g=>g.records[0].sample.archiveVerified=false,g=>g.records[0].sample.cleanupVerified=false,
 g=>g.records[0].sample.normalPressure={},g=>g.records[0].sample.normalPressureScriptSha256='1'.repeat(64),
 g=>g.records[0].sample.normalPressureRawSha256='1'.repeat(64),g=>g.records[0].sample.phase_seconds={normal_pressure:0},
 g=>g.sharedJobBudget.deadlineEpochSeconds++,g=>g.abcExperiment.pressure={},
]){const g=copy(gate);mutate(g);assert.throws(()=>validateABCPreviousGate(g,identity,validate));}
for(const malformed of [null,undefined,{},[]])assert.throws(()=>validateABCPreviousGate(malformed,identity,validate));
assert.throws(()=>validateABCPreviousGate(gate,null,validate));
assert.throws(()=>validateABCPreviousGate(gate,identity,undefined));
const oracleError=new Error('original oracle must be decisive');
assert.throws(()=>validateABCPreviousGate(gate,identity,()=>{throw oracleError;}),error=>error===oracleError);
console.log('PASS: fixed ordinary three-Sprig pins/paths/hashes; exact balanced 36-position plan; complete same-identity incremental-0 gate with raw-report, before/after input proofs and original oracle. Pure fixtures only.');
