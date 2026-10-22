import assert from 'node:assert/strict';
import fs from 'node:fs';
import {performance} from 'node:perf_hooks';
export async function checkHistory(caseName,api){
 const steps=JSON.parse(fs.readFileSync(`fixtures/${caseName}-steps.json`)),samples=[];
 for(const step of steps){
  const cmd=`set -e; printf '%s' '${step.data}' | base64 -d | dd of='${step.path}' bs=1 seek=${step.offset} conv=notrunc,fsync status=none; touch -d @1700000000 '${step.path}'`;
  let start=performance.now();await api.exec(cmd);const writeMs=performance.now()-start;
  start=performance.now();const commit=await api.commit('Frozen history step '+step.step);const commitMs=performance.now()-start;
  await api.exec(`printf '%s  %s\\n' '${step.sha256}' '${step.path}' | sha256sum -c -`);
  samples.push({step:step.step,writeMs,commitMs,commit});
 }
 const final=JSON.parse(fs.readFileSync(`fixtures/${caseName}-final.json`));
 await api.exec('('+final.map(f=>`printf '%s  %s\\n' '${f.sha256}' '${f.path}'`).join(';')+') | sha256sum -c -');
 const history=await api.history();assert.ok(history.length>=steps.length,'Missing acknowledged history');
 return {samples,totalWriteMs:samples.reduce((a,x)=>a+x.writeMs,0),totalCommitMs:samples.reduce((a,x)=>a+x.commitMs,0),acknowledgedCommits:samples.length,historyRecords:history.length,finalFullByteVerification:true,changedFileReadbackAfterEveryCommit:true,historicalSnapshotRemountVerification:false};
}
