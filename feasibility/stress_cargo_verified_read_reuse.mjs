// Pure guards for the ordinary fixed-pin baseline / verified-first-read reuse experiment.
// This is a new mode; none of the historical A/B or direct guards are relaxed.
import assert from 'node:assert/strict';
import path from 'node:path';

export const ABC_SCHEMA='sprig-stress-cargo-verified-read-reuse-v1';
export const ABC_EXPERIMENT=Object.freeze({
 schema:'sprig-cargo-verified-read-reuse-experiment-v1',profile:'ordinary',roundsPerMode:6,
 incrementalModes:Object.freeze([0,1]),order:'six-alternating-reverse-mode1',pressure:null,
});
export const ABC_PINS=Object.freeze({
 'sprig-baseline':'4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
 'sprig-verified-read-reuse':'f61ce655d9270e206d97e20bc104644c821e4e5d',
});
const LABELS=Object.freeze(Object.keys(ABC_PINS));
const PERMUTATIONS=Object.freeze([
 [0,1],[1,0],[0,1],[1,0],[0,1],[1,0],
].map(order=>Object.freeze(order)));
const PLAN_SCHEMA='sprig-cargo-verified-read-reuse-plan-v1';
const SHA256=/^[a-f0-9]{64}$/;
const IDENTITY_KEYS=Object.freeze([
 'image','protocolSha256','fixtureManifestSha256','imageBytes','resourceProtocol',
 'abcManifestSha256','abcPlanSha256','abcProducts','sharedJobBudget','abcExperiment',
]);

function object(value,message){assert.ok(value!==null&&typeof value==='object'&&!Array.isArray(value),message);}
function mode(incremental){assert.ok(Number.isInteger(incremental)&&[0,1].includes(incremental),'only incremental modes 0 and 1 are allowed');}
function canonicalPath(value){
 // Lexical validation only. The driver must additionally prove realpath,
 // worktree cleanliness, regular binary files and hashes before/after execution.
 return typeof value==='string'&&path.posix.isAbsolute(value)&&value!=='/'&&
  path.posix.normalize(value)===value&&!value.endsWith('/')&&!/[\x00-\x1f\x7f\\]/.test(value);
}

export function validateABCProducts(products){
 assert.ok(Array.isArray(products)&&products.length===2,'exactly two Sprig products required');
 assert.deepEqual(products.map(p=>p?.label),LABELS,'fixed unique verified-read A/B labels and order required');
 for(const p of products){
  object(p,'product object required');
  assert.deepEqual(Object.keys(p).sort(),['binary','binarySha256','label','sha','sourcePath'].sort(),'exact product fields required');
  assert.equal(p.sha,ABC_PINS[p.label],'fixed verified-read A/B source pin required');
  assert.match(p.binarySha256??'',SHA256,'binary SHA256 required');
  for(const key of ['binary','sourcePath'])assert.ok(canonicalPath(p[key]),'canonical absolute product paths required');
 }
 for(const key of ['binary','sourcePath','binarySha256'])assert.equal(new Set(products.map(p=>p[key])).size,2,`two distinct ${key} values required`);
 return products;
}

export function abcOrder(incremental,round){
 mode(incremental);assert.ok(Number.isInteger(round)&&round>=0&&round<6,'round must be an integer from 0 through 5');
 return PERMUTATIONS[incremental===0?round:5-round].map(index=>LABELS[index]);
}

export function abcSchedule(incremental){
 mode(incremental);
 return Array.from({length:6},(_,round)=>{
  const order=abcOrder(incremental,round);
  return order.map((product,position)=>({product,incremental,round,position,order:[...order]}));
 }).flat();
}

export function validateABCMode({rounds,profile,ownAB,latestDirect,productionSha}){
 assert.equal(rounds,6,'verified-read A/B requires exactly six rounds per mode');
 assert.equal(profile,'ordinary','verified-read A/B only permits the ordinary profile');
 assert.equal(ownAB,false,'verified-read A/B cannot be combined with own-A/B');
 assert.equal(latestDirect,false,'verified-read A/B cannot be combined with latest-direct');
 assert.equal(productionSha,undefined,'verified-read A/B cannot use an ambiguous single production source');
 return true;
}

export function createABCPlan(products){
 validateABCProducts(products);
 return {schema:PLAN_SCHEMA,abcExperiment:ABC_EXPERIMENT,abcProducts:products,records:[...abcSchedule(0),...abcSchedule(1)]};
}

export function validateABCPlan(plan,products=plan?.abcProducts){
 object(plan,'verified-read A/B plan object required');
 assert.deepEqual(plan,createABCPlan(products),'exact fixed 24-position verified-read A/B plan required');
 return plan;
}

export function validateABCPreviousGate(gate,identity,validate){
 object(gate,'complete incremental-0 gate required');object(identity,'verified-read A/B identity required');
 assert.equal(typeof validate,'function','original sample/archive oracle callback required');
 assert.equal(gate.schema,ABC_SCHEMA);assert.equal(gate.complete,true);assert.equal(gate.status,'passed');
 assert.equal(gate.incremental,0);assert.equal(gate.rounds,6);assert.equal(gate.expectedRecords,12);
 for(const key of IDENTITY_KEYS){
  assert.ok(Object.hasOwn(identity,key)&&identity[key]!==undefined&&identity[key]!==null,`verified-read A/B identity ${key} required`);
  assert.ok(Object.hasOwn(gate,key)&&gate[key]!==undefined&&gate[key]!==null,`verified-read A/B prerequisite ${key} required`);
  assert.deepEqual(gate[key],identity[key],`verified-read A/B prerequisite ${key} mismatch`);
 }
 assert.match(identity.image,/^sha256:[a-f0-9]{64}$/,'exact container image identity required');
 for(const key of ['protocolSha256','fixtureManifestSha256','abcManifestSha256','abcPlanSha256'])assert.match(identity[key],SHA256,`${key} required`);
 assert.deepEqual(identity.abcExperiment,ABC_EXPERIMENT,'fixed ordinary verified-read A/B experiment required');
 validateABCProducts(identity.abcProducts);
 assert.ok(Array.isArray(gate.records)&&gate.records.length===12,'all 12 incremental-0 records required');
 for(const [index,expected] of abcSchedule(0).entries()){
  const r=gate.records[index];object(r,'verified-read A/B prerequisite record required');
  for(const key of ['product','incremental','round','position','order'])assert.deepEqual(r[key],expected[key],`fixed verified-read A/B prerequisite ${key} required`);
  const p=identity.abcProducts.find(product=>product.label===expected.product);
  assert.equal(r.correct,true);assert.equal(r.status,'passed');assert.equal(r.sampleReturncode,0);
  assert.ok(r.cleanupErrors===undefined||(Array.isArray(r.cleanupErrors)&&r.cleanupErrors.length===0),'verified-read A/B prerequisite cleanup errors forbidden');
  assert.equal(r.error,undefined,'verified-read A/B prerequisite record error forbidden');
  assert.match(r.rawReportSha256??'',SHA256,'raw exact-integer report SHA256 required');
  assert.equal(r.rawReportPath,`results/stress-cargo-${expected.product}-inc0-${expected.round}.json`,'fixed raw report path required');
  assert.deepEqual(r.verifiedProductInputs,p,'selected source/binary proof before sample required');
  assert.deepEqual(r.verifiedProductInputsAfter,p,'selected source/binary proof after sample required');
  object(r.sample,'original prerequisite sample required');
  assert.equal(r.sample.production_sha,p.sha);assert.equal(r.sample.binarySha256,p.binarySha256);
  for(const key of ['normalPressure','normalPressureScriptSha256','normalPressureRawSha256'])assert.equal(r.sample[key],undefined,'ordinary verified-read A/B sample cannot contain pressure');
  assert.equal(r.sample.phase_seconds?.normal_pressure,undefined,'ordinary verified-read A/B sample cannot contain pressure timing');
  validate(r.sample,p,0);
 }
 return true;
}
