import {checkHistory} from './history-check.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const dir=fs.mkdtempSync(path.join(os.tmpdir(),'history-oracle-test-'));process.chdir(dir);fs.mkdirSync('fixtures');
const id=n=>n.toString(16).padStart(64,'0');
fs.writeFileSync('fixtures/test-steps.json',JSON.stringify([1,2].map(step=>({step,path:'f',data:'YQ==',offset:17,sha256:'irrelevant-mock'}))));
fs.writeFileSync('fixtures/test-final.json',JSON.stringify([{path:'f',sha256:'irrelevant-mock'}]));
function api(product,problem){let n=0;const history=product==='sprig'?[{revision:id(0)}]:[];return {
 exec:async cmd=>{if(cmd.includes('dd of='))assert.ok(cmd.includes('bs=65536 iflag=fullblock oflag=seek_bytes seek=17'));},
 commit:async()=>{n++;const next=problem==='duplicate'?id(1):id(n);if(problem!=='missing-history')history.push(product==='sprig'?{revision:next}:{id:next});return product==='sprig'?{committed:problem!=='no-op',revision:next}:{kind:problem==='no-op'?'UpToDate':'Committed',commit:{id:next}};},
 history:async()=>[...history]
};}
for(const product of ['sprig','layerfs']){
 const report=await checkHistory('test',api(product));assert.equal(report.completed,true);assert.equal(report.acknowledgedCommits,2);assert.equal(report.allAcknowledgedIdsPresent,true);
 for(const problem of ['duplicate','missing-history','no-op'])await assert.rejects(()=>checkHistory('test',api(product,problem)));
}
console.log('History oracle: both product schemas pass; duplicate, absent history, and no-op commits rejected.');
