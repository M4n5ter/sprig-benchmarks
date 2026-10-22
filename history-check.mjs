import assert from 'node:assert/strict';
import fs from 'node:fs';
import {performance} from 'node:perf_hooks';
export async function checkHistory(caseName,api,report={}){
 const steps=JSON.parse(fs.readFileSync(`fixtures/${caseName}-steps.json`)),samples=[];
 const baseline=await api.history();const returnedIds=new Set();
 Object.assign(report,{samples,expectedSamples:steps.length,completed:false,baselineHistoryRecords:baseline.length});
 for(const step of steps){
  const cmd=`set -e; printf '%s' '${step.data}' | base64 -d | dd of='${step.path}' bs=65536 iflag=fullblock oflag=seek_bytes seek=${step.offset} conv=notrunc,fsync status=none; touch -d @1700000000 '${step.path}'`;
  let start=performance.now();await api.exec(cmd);const writeMs=performance.now()-start;
  start=performance.now();const commit=await api.commit('Frozen history step '+step.step);const commitMs=performance.now()-start;
  assert.ok(commit.committed===true||commit.kind==='Committed','Checkpoint did not acknowledge a new revision');
  const commitId=commit.revision??commit.commit?.id;
  assert.ok(typeof commitId==='string'&&/^[a-f0-9]{16,}$/.test(commitId),'Missing checkpoint ID');
  assert.ok(!returnedIds.has(commitId),'Repeated checkpoint ID');returnedIds.add(commitId);
  await api.exec(`printf '%s  %s\\n' '${step.sha256}' '${step.path}' | sha256sum -c -`);
  const sample={step:step.step,writeMs,commitMs,commitId,commit};samples.push(sample);if(api.onSample)api.onSample(sample);
 }
 const final=JSON.parse(fs.readFileSync(`fixtures/${caseName}-final.json`));
 await api.exec('('+final.map(f=>`printf '%s  %s\\n' '${f.sha256}' '${f.path}'`).join(';')+') | sha256sum -c -');
 const history=await api.history();assert.equal(history.length,baseline.length+steps.length,'History must contain every new acknowledged revision');
 const historyIds=new Set(history.map(r=>r.revision??r.id));
 for(const id of returnedIds)assert.ok(historyIds.has(id),'Acknowledged checkpoint missing from history');
 return Object.assign(report,{completed:true,totalWriteMs:samples.reduce((a,x)=>a+x.writeMs,0),totalCommitMs:samples.reduce((a,x)=>a+x.commitMs,0),acknowledgedCommits:samples.length,historyRecords:history.length,allAcknowledgedIdsPresent:true,finalFullByteVerification:true,changedFileReadbackAfterEveryCommit:true,historicalSnapshotRemountVerification:false});
}
