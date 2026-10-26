// Pure identity/order/prerequisite guards for ordinary within-Sprig Cargo A/B.
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
export const AB_SCHEMA='sprig-stress-cargo-own-ab-v1';
export const AB_REPEATED_SCHEMA='sprig-stress-cargo-own-ab-v2';
export const ORDINARY_EXPERIMENT=Object.freeze({schema:'sprig-cargo-experiment-v1',profile:'ordinary',roundsPerMode:4,incrementalModes:[0,1],order:'alternating-pairs-mode-offset',pressure:null});
export const PRESSURE_SPEC=Object.freeze({profile:'normal-rename2-v1',workers:2,iterationsPerWorker:128,unrelatedFilesPerWorker:1024,movingFilesPerWorker:8,payloadBytes:64,witnessMtimeNs:'1700000000123456789'});
export function experimentSpec(profile='ordinary'){
 assert.ok(['ordinary',PRESSURE_SPEC.profile].includes(profile),'unreviewed experiment profile');
 if(profile==='ordinary')return ORDINARY_EXPERIMENT;
 const source=fs.readFileSync(new URL('./stress_cargo_pressure.py',import.meta.url));
 return {...ORDINARY_EXPERIMENT,profile,pressure:{schema:'sprig-cargo-normal-pressure-v1',scriptSha256:createHash('sha256').update(source).digest('hex'),spec:PRESSURE_SPEC,availableReserveBytes:128*1024**2}};
}
export function validateExperimentSpec(value){assert.deepEqual(value,experimentSpec(value?.profile));return value;}
export function validatePressureSample(sample,experiment){
 validateExperimentSpec(experiment);
 if(experiment.profile==='ordinary'){for(const key of ['normalPressure','normalPressureScriptSha256','normalPressureRawSha256'])assert.equal(sample[key],undefined,'ordinary sample contains pressure');assert.equal(sample.phase_seconds?.normal_pressure,undefined,'ordinary sample contains pressure timing');return true;}
 assert.equal(sample.normalPressureScriptSha256,experiment.pressure.scriptSha256);assert.match(sample.normalPressureRawSha256??'',/^[a-f0-9]{64}$/);
 const p=sample.normalPressure;assert.equal(p?.schema,experiment.pressure.schema);assert.equal(p.profile,experiment.profile);assert.deepEqual(p.spec,PRESSURE_SPEC);assert.equal(p.ok,true);assert.equal(p.allWitnessesVerified,true);
 assert.ok(Number.isFinite(sample.phase_seconds.normal_pressure)&&sample.phase_seconds.normal_pressure>=0);
 assert.deepEqual(p.workers?.map(r=>r.worker),[0,1]);
 for(const r of p.workers){
  assert.equal(r.completedIterations,128);
  for(const key of ['startedNs','finishedNs'])assert.ok(Number.isSafeInteger(r[key])&&r[key]>=0);
  assert.ok(r.finishedNs>r.startedNs);assert.deepEqual(Object.keys(r.samplesNanoseconds).sort(),['metadata','read','rename','write']);
  for(const [name,values] of Object.entries(r.samplesNanoseconds)){assert.ok(Array.isArray(values));assert.equal(values.length,name==='rename'?256:128);assert.ok(values.every(x=>Number.isSafeInteger(x)&&x>=0));}
 }
 const overlap=Math.min(...p.workers.map(r=>r.finishedNs))-Math.max(...p.workers.map(r=>r.startedNs));assert.ok(overlap>0);assert.equal(p.workerLifetimeOverlapNs,overlap);
 const observations=sample.checkpointTreeOracle.entries.filter(e=>e.path==='pressure-rename2/observations.json');assert.equal(observations.length,1);assert.equal(observations[0].sha256,sample.normalPressureRawSha256,'retained pressure observations missing from complete oracle');
 return true;
}
export const AB_PINS=Object.freeze({'sprig-baseline':'4ef4a90d7ccf5f305416c5374bfc81038f5ca46e','sprig-candidate':'b300693e01c652c1a9631c61b7a439892d8f75cd'});
export function validateProducts(products){
 assert.ok(Array.isArray(products)&&products.length===2,'exactly two variants required');
 assert.deepEqual(products.map(p=>p?.label),Object.keys(AB_PINS),'fixed unique variant labels and order required');
 for(const p of products){
  assert.deepEqual(Object.keys(p).sort(),['binary','binarySha256','label','sha','sourcePath'].sort(),'unexpected product fields');
  assert.equal(p.sha,AB_PINS[p.label],'fixed source pin required');
  assert.match(p.binarySha256??'',/^[a-f0-9]{64}$/,'binary SHA256 required');
  for(const key of ['binary','sourcePath'])assert.ok(typeof p[key]==='string'&&path.isAbsolute(p[key])&&path.normalize(p[key])===p[key],'absolute normalized paths required');
 }
 for(const key of ['binary','sourcePath','binarySha256'])assert.notEqual(products[0][key],products[1][key],`distinct ${key} required`);
 return products;
}
export function sampleOrder(products,incremental,round=0){
 validateProducts(products);assert.ok([0,1].includes(incremental));assert.ok(Number.isInteger(round)&&round>=0&&round<4,'bounded round required');return (incremental+round)%2===0?[...products]:[...products].reverse();
}
export function validateOwnPreviousGate(gate,identity,validate){
 const repeated=identity.experimentSpec!==undefined;
 assert.equal(gate.schema,repeated?AB_REPEATED_SCHEMA:AB_SCHEMA);assert.equal(gate.complete,true);assert.equal(gate.status,'passed');assert.equal(gate.incremental,0);assert.equal(gate.rounds,repeated?4:1);
 const keys=['image','protocolSha256','fixtureManifestSha256','imageBytes','resourceProtocol','abManifestSha256','abProducts','sharedJobBudget'];
 if(repeated){keys.push('experimentSpec');validateExperimentSpec(identity.experimentSpec);}
 for(const key of keys)assert.deepEqual(gate[key],identity[key],`own A/B prerequisite ${key} mismatch`);
 validateProducts(identity.abProducts);assert.equal(gate.records?.length,2*gate.rounds);
 for(let round=0;round<gate.rounds;round++)for(const [offset,p] of sampleOrder(identity.abProducts,0,round).entries()){
  const rows=gate.records.filter(r=>r.product===p.label&&r.round===round);assert.equal(rows.length,1,'missing/duplicate variant prerequisite');
  const r=rows[0];assert.equal(gate.records[2*round+offset],r,'balanced execution order required');assert.equal(r.correct,true);assert.equal(r.status,'passed');assert.equal(r.incremental,0);assert.equal(r.sampleReturncode,0);
  assert.equal(r.sample?.binarySha256,p.binarySha256);assert.equal(r.sample?.production_sha,p.sha);
  if(repeated)assert.match(r.rawReportSha256??'',/^[a-f0-9]{64}$/,'raw exact-integer report hash required');
  validate(r.sample,p,0);
 }
 return true;
}
