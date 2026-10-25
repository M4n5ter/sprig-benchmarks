// Pure identity/order/prerequisite guards for ordinary within-Sprig Cargo A/B.
import assert from 'node:assert/strict';
import path from 'node:path';
export const AB_SCHEMA='sprig-stress-cargo-own-ab-v1';
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
export function sampleOrder(products,incremental){
 validateProducts(products);assert.ok([0,1].includes(incremental));return incremental===0?[...products]:[...products].reverse();
}
export function validateOwnPreviousGate(gate,identity,validate){
 assert.equal(gate.schema,AB_SCHEMA);assert.equal(gate.complete,true);assert.equal(gate.status,'passed');assert.equal(gate.incremental,0);assert.equal(gate.rounds,1);
 for(const key of ['image','protocolSha256','fixtureManifestSha256','imageBytes','resourceProtocol','abManifestSha256','abProducts','sharedJobBudget'])assert.deepEqual(gate[key],identity[key],`own A/B prerequisite ${key} mismatch`);
 validateProducts(identity.abProducts);assert.equal(gate.records?.length,2);
 for(const p of identity.abProducts){
  const rows=gate.records.filter(r=>r.product===p.label);assert.equal(rows.length,1,'missing/duplicate variant prerequisite');
  const r=rows[0];assert.equal(r.correct,true);assert.equal(r.status,'passed');assert.equal(r.incremental,0);assert.equal(r.round,0);assert.equal(r.sampleReturncode,0);
  assert.equal(r.sample?.binarySha256,p.binarySha256);assert.equal(r.sample?.production_sha,p.sha);
  validate(r.sample,p,0);
 }
 return true;
}
