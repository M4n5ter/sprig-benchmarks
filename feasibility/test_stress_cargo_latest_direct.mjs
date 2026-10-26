import assert from 'node:assert/strict';
import {DIRECT_SCHEMA,MANIFEST_SCHEMA,SPRIG_SHA,LAYERFS_SHA,validateDirectManifest,validateDirectMode,directOrder,directProduct,validateDirectPreviousGate} from './stress_cargo_latest_direct.mjs';
import {validateProducts} from './stress_cargo_own_ab.mjs';
import {validatePreviousGate} from './stress_cargo_compare.mjs';
import {SOURCE_SHA,selectedSource} from './stress_cargo_layerfs.mjs';
assert.equal(selectedSource({}),SOURCE_SHA);assert.equal(SOURCE_SHA,'9f97a7ec95b662e9cb288704afa165feff132cfa');
assert.equal(selectedSource({latestDirect:{schema:'sprig-cargo-latest-direct-source-v1',sha:LAYERFS_SHA}}),LAYERFS_SHA);
for(const latestDirect of [null,{}, {schema:'sprig-cargo-latest-direct-source-v1',sha:SOURCE_SHA},{schema:'wrong',sha:LAYERFS_SHA},{schema:'sprig-cargo-latest-direct-source-v1',sha:LAYERFS_SHA,extra:true}])assert.throws(()=>selectedSource({latestDirect}));
const manifest={schema:MANIFEST_SCHEMA,sprig:{sha:SPRIG_SHA,ref:'main',binary:'/fixed/sprig/target/release/sprig',binarySha256:'a'.repeat(64),sourcePath:'/fixed/sprig'},layerfs:{sha:LAYERFS_SHA,ref:'main',binary:'/fixed/layerfs/core/target/release/layerfs-daemon',binarySha256:'b'.repeat(64),sourcePath:'/fixed/layerfs',sdkPath:'/fixed/layerfs/api/agent/sdk/src/index.js',sdkSha256:'c'.repeat(64),nativeAddonPath:'/fixed/layerfs/api/binding/layerfs.node',nativeAddonSha256:'d'.repeat(64)}};
assert.deepEqual(validateDirectManifest(manifest),manifest);
for(const [product,key,value] of [['sprig','sha','0'.repeat(40)],['layerfs','ref','v1.1.0'],['layerfs','sha','9f97a7ec95b662e9cb288704afa165feff132cfa'],['layerfs','nativeAddonPath','/tmp/unbound.node'],['layerfs','sdkSha256','wrong'],['sprig','binary','relative']]){const m=structuredClone(manifest);m[product][key]=value;assert.throws(()=>validateDirectManifest(m));}
assert.throws(()=>validateDirectManifest({...manifest,extra:true}));
assert.deepEqual(directOrder(0,0),['sprig-writable','layerfs']);assert.deepEqual(directOrder(0,1),['layerfs','sprig-writable']);assert.deepEqual(directOrder(1,0),['layerfs','sprig-writable']);assert.deepEqual(directOrder(1,1),['sprig-writable','layerfs']);
for(const pair of [[0,2],[2,0],[true,0],[0,.5]])assert.throws(()=>directOrder(...pair));
const mode={rounds:2,profile:'ordinary',ownAB:false,productionSha:SPRIG_SHA,comparatorSha:LAYERFS_SHA};assert.equal(validateDirectMode(mode),true);
for(const [key,value]of [['rounds',1],['rounds',3],['rounds',4],['ownAB',true],['profile','normal-rename2-1024-v2'],['productionSha','0'.repeat(40)]])assert.throws(()=>validateDirectMode({...mode,[key]:value}));
const identity={image:'sha256:'+'e'.repeat(64),protocolSha256:'f'.repeat(64),fixtureManifestSha256:'1'.repeat(64),productionSha:SPRIG_SHA,comparatorSha:LAYERFS_SHA,imageBytes:4*1024**3,resourceProtocol:'sprig-cargo-resource-4g-v1',sharedJobBudget:{fixed:'same deadline'},directManifest:manifest,directManifestSha256:'2'.repeat(64)};
const records=[0,1].flatMap(round=>directOrder(0,round).map(product=>({product,round,incremental:0,correct:true,status:'passed',sampleReturncode:0,rawReportSha256:'3'.repeat(64),rawReportPath:`results/stress-cargo-${product}-inc0-${round}.json`,verifiedProductInputs:directProduct(manifest,product),sample:{ok:true}})));
const gate={schema:DIRECT_SCHEMA,status:'passed',complete:true,incremental:0,rounds:2,expectedRecords:4,...identity,records};let validated=0;assert.equal(validateDirectPreviousGate(gate,identity,(s,p,i)=>{assert.equal(s.ok,true);assert.equal(i,0);validated++;}),true);assert.equal(validated,4);
for(const mutation of [g=>g.records.pop(),g=>g.records.reverse(),g=>g.complete=false,g=>g.rounds=3,g=>g.records[0].correct=false,g=>g.records[0].sampleReturncode=1,g=>g.records[0].verifiedProductInputs.binarySha256='0'.repeat(64),g=>g.sharedJobBudget={changed:true},g=>g.records[0].rawReportPath='other']){const bad=structuredClone(gate);mutation(bad);assert.throws(()=>validateDirectPreviousGate(bad,identity,()=>{}));}
assert.throws(()=>validatePreviousGate(gate,identity));assert.throws(()=>validateProducts([manifest.sprig,manifest.layerfs]));
console.log('latest direct identity, fixed two-round order and previous-gate guards PASS; legacy identities remain separate');
