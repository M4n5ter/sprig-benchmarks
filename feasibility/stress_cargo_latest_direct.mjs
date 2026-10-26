// Explicit current-main / current-main series; old acceptance guards stay fixed.
import assert from 'node:assert/strict';
import path from 'node:path';
export const DIRECT_SCHEMA='sprig-stress-cargo-latest-direct-v1';
export const MANIFEST_SCHEMA='sprig-cargo-latest-direct-identity-v1';
export const SPRIG_SHA='4eb0f4d7afdb19bf22d9667dc520ede8b162c737';
export const LAYERFS_SHA='ad78914e36b258b360daf13aec164b5655814689';
export const PRODUCTS=Object.freeze(['sprig-writable','layerfs']);
export function validateDirectManifest(value){
 assert.deepEqual(Object.keys(value).sort(),['schema','sprig','layerfs'].sort());assert.equal(value.schema,MANIFEST_SCHEMA);
 const common=['sha','ref','binary','binarySha256','sourcePath'];
 for(const [name,pin] of [['sprig',SPRIG_SHA],['layerfs',LAYERFS_SHA]]){
  const p=value[name];assert.deepEqual(Object.keys(p).sort(),(name==='sprig'?common:[...common,'sdkPath','sdkSha256','nativeAddonPath','nativeAddonSha256']).sort());assert.equal(p.sha,pin);assert.equal(p.ref,'main');
  for(const key of name==='sprig'?['binarySha256']:['binarySha256','sdkSha256','nativeAddonSha256'])assert.match(p[key]??'',/^[a-f0-9]{64}$/);
  for(const key of name==='sprig'?['binary','sourcePath']:['binary','sourcePath','sdkPath','nativeAddonPath'])assert.ok(typeof p[key]==='string'&&path.isAbsolute(p[key])&&path.normalize(p[key])===p[key],'canonical absolute product paths');
  assert.equal(p.binary,path.join(p.sourcePath,name==='sprig'?'target/release/sprig':'core/target/release/layerfs-daemon'));
 }
 const p=value.layerfs;assert.equal(p.sdkPath,path.join(p.sourcePath,'api/agent/sdk/src/index.js'));assert.equal(p.nativeAddonPath,path.join(p.sourcePath,'api/binding/layerfs.node'));
 assert.notEqual(value.sprig.sourcePath,value.layerfs.sourcePath);assert.notEqual(value.sprig.binarySha256,value.layerfs.binarySha256);return value;
}
export function directOrder(incremental,round){
 assert.ok(Number.isInteger(incremental)&&[0,1].includes(incremental));assert.ok(Number.isInteger(round)&&[0,1].includes(round));return (incremental+round)%2?[...PRODUCTS].reverse():[...PRODUCTS];
}
export function directProduct(manifest,label){assert.ok(PRODUCTS.includes(label));return manifest[label==='layerfs'?'layerfs':'sprig'];}
export function validateDirectMode({rounds,profile,ownAB,productionSha,comparatorSha}){
 assert.equal(rounds,2);assert.equal(profile,'ordinary');assert.equal(ownAB,false);assert.equal(productionSha,SPRIG_SHA);assert.equal(comparatorSha,LAYERFS_SHA);return true;
}
export function validateDirectPreviousGate(gate,identity,validateSample){
 assert.equal(gate.schema,DIRECT_SCHEMA);assert.equal(gate.complete,true);assert.equal(gate.status,'passed');assert.equal(gate.incremental,0);assert.equal(gate.rounds,2);assert.equal(gate.expectedRecords,4);
 for(const key of ['image','protocolSha256','fixtureManifestSha256','productionSha','comparatorSha','imageBytes','resourceProtocol','sharedJobBudget','directManifest','directManifestSha256'])assert.deepEqual(gate[key],identity[key],`latest direct prerequisite ${key} mismatch`);
 validateDirectManifest(identity.directManifest);assert.equal(gate.records?.length,4);
 for(let round=0;round<2;round++)for(const [offset,label] of directOrder(0,round).entries()){
  const r=gate.records[2*round+offset];assert.equal(r.product,label);assert.equal(r.round,round);assert.equal(r.incremental,0);assert.equal(r.correct,true);assert.equal(r.status,'passed');assert.equal(r.sampleReturncode,0);assert.ok(!r.cleanupErrors);assert.match(r.rawReportSha256??'',/^[a-f0-9]{64}$/);assert.equal(r.rawReportPath,`results/stress-cargo-${label}-inc0-${round}.json`);
  assert.deepEqual(r.verifiedProductInputs,directProduct(identity.directManifest,label));validateSample(r.sample,label,0);
 }
 return true;
}
