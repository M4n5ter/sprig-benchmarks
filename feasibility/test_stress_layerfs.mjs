import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {execFileSync} from 'node:child_process';
import {advance,exactOracle,oracleJSON,oracleCommand,validateFixture,verifyHistory,writeCommand} from './stress_layerfs.mjs';
const root=fs.mkdtempSync(path.join(os.tmpdir(),'stress-lfs-test-'));
try{
 const source=path.join(root,'source');
 const raw=execFileSync('python3',['feasibility/stress_fixture.py',source,'--files','8','--links','8','--steps','20'],{encoding:'utf8'});
 const doc=exactOracle(raw);validateFixture(doc);
 let expected=structuredClone(doc.initial);
 for(const edit of doc.edits){
  execFileSync('bash',['-c',writeCommand(edit)],{cwd:source});advance(expected,edit);
  const out=execFileSync('python3',['feasibility/tree_oracle.py','verify',source],{input:oracleJSON(expected),encoding:'utf8'});
  assert.equal(JSON.parse(out).ok,true);
 }
 const bad=structuredClone(doc);bad.edits[0].aliases=[bad.edits[0].path];assert.throws(()=>validateFixture(bad));
 const precise='{"schema":"cargo-full-tree-v1","entries":[{"mtime_ns":1700000000000000001}],"hardlink_groups":[]}';
 assert.equal(oracleJSON(exactOracle(precise)),precise);
 const command=oracleCommand('/workspaces/1',precise);assert.ok(command.script.includes('1700000000000000001'));
 verifyHistory([{id:'b',parent:'a',secondParent:null},{id:'a',parent:null,secondParent:null}],['a','b']);
 assert.throws(()=>verifyHistory([{id:'b',parent:null,secondParent:null},{id:'a',parent:null,secondParent:null}],['a','b']));
 assert.throws(()=>verifyHistory([{id:'a',parent:null,secondParent:null}],['a','b']));
 console.log('PASS: 20 shell-writer/full-tree hardlink replays, exact-nanosecond JSON transport, invalid alias/history rejection. Not a kernel/product test.');
}finally{fs.rmSync(root,{recursive:true,force:true});}

// Transport/state-machine mock only: deliberately marked testOnly by sampler.
const {runStressLayerfs}=await import('./stress_layerfs.mjs');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'stress-lfs-mock-'));
const saved={GITHUB_ACTIONS:process.env.GITHUB_ACTIONS,RUNNER_TEMP:process.env.RUNNER_TEMP};
try{
 process.env.GITHUB_ACTIONS='true';process.env.RUNNER_TEMP=temp;
 const measured=path.join(temp,'mount'),source=path.join(temp,'source');fs.mkdirSync(measured);
 const fixturePath=path.join(temp,'fixture.json');
 fs.writeFileSync(fixturePath,execFileSync('python3',['feasibility/stress_fixture.py',source,'--files','4','--links','4','--steps','3']));
 const fixture=exactOracle(fs.readFileSync(fixturePath,'utf8'));let step=0,mounted=[],counter=0;
 const head='32'+'a'.repeat(64),ids=[],branchBases=new Map([['main',head]]),snapshots=new Map([[head,fixture.initial]]);
 const image='sha256:'+'b'.repeat(64);fs.mkdirSync(path.join(measured,'docker'));fs.mkdirSync(path.join(measured,'volume'));
 const client={created:{layer:head},branch:{
  fork:async(name,base)=>{branchBases.set(name,branchBases.get(base)??base);},
  list_commits:async(name)=>{const upto=ids.indexOf(branchBases.get(name));return {items:ids.slice(0,upto+1).reverse().map((id,j,all)=>({id,parent:all[j+1]??null,secondParent:null})),hasMore:false};}
 },sandbox:{
  create:async()=>({sandbox:'test-sandbox'}),
  list_workspaces:async()=>({items:mounted.map(w=>({...w,base:branchBases.get(w.name),activity:'Idle'})),hasMore:false}),
  close:async()=>{}
 },project:{list_branches:async()=>({items:[...branchBases].map(([name,id])=>({name,base:head,head:id===head?null:id})),hasMore:false})},workspace:{
  mount:async(sandbox,name)=>{const w={sandbox,path:'/workspaces/'+(++counter),name};mounted.push(w);return w;},
  exec:async(ws,cmd)=>{if(cmd.includes('conv=notrunc,fsync')){step++;return {exitCode:0,stdout:'',stderr:''};}return {exitCode:0,stdout:oracleJSON(snapshots.get(branchBases.get(ws.name))),stderr:''};},
  commit:async(ws)=>{if(!step)return {kind:'UpToDate',head:null};const id='12'+String(step).padStart(64,'0');const expected=structuredClone(fixture.initial);for(const edit of fixture.edits.slice(0,step))advance(expected,edit);snapshots.set(id,expected);branchBases.set(ws.name,id);ids.push(id);return {kind:'Committed',head:id};},
  unmount:async(ws)=>{mounted=mounted.filter(w=>w.path!==ws.path);}
 },close:async()=>{}};
 const runner=async argv=>{
  let stdout='';const text=argv.join(' ');
  if(argv[0]==='stat')stdout='btrfs\n';
  else if(argv[0]==='findmnt')stdout=JSON.stringify({filesystems:[{target:measured,fstype:'btrfs'}]});
  else if(argv[0]==='btrfs'&&argv[2]==='usage')stdout='Used: 1000000\n';
  else if(text.includes('image inspect'))stdout=JSON.stringify([{Id:image,Config:{User:'root'}}]);
  else if(text.includes('info --format'))stdout=JSON.stringify({DockerRootDir:path.join(measured,'docker')});
  else if(text.includes('volume inspect'))stdout=path.join(measured,'volume');
  else if(argv[0]==='/usr/bin/python3')stdout=oracleJSON(fixture.initial);
  return {returncode:0,signal:null,stdout,stderr:''};
 };
 const report=await runStressLayerfs({root:path.join(measured,'sample'),measuredMount:measured,source,fixturePath,daemonPath:fs.realpathSync('/bin/true'),layerfsSdkPath:path.resolve('feasibility/stress_layerfs.mjs'),image,sampleBudgetSeconds:30,noopCheckpoint:true},{subprocess:runner,sdk:{LayerFS:{init:async()=>client}}});
 assert.equal(report.ok,true,JSON.stringify(report.error));assert.equal(report.testOnly,true);assert.equal(report.fullHistoricalSnapshotReadbacks,4);assert.equal(report.lifecycle.cleanup.complete,true);assert.equal(mounted.length,0);assert.equal(report.lifecycle.activeAfterHistory.retainedBranches,8);assert.equal(report.historical_restore_steps[0].kind,'noop');assert.equal(report.fullTreeChecks.length,15);assert.ok(report.preservedLogs.length>15);assert.equal(fs.statSync(report.preservedLogsDirectory).mode&0o777,0o755);for(const row of report.preservedLogs){assert.equal(fs.statSync(row.path).mode&0o777,0o644);assert.equal(fs.statSync(row.path).size,row.bytes);assert.match(row.sha256,/^[a-f0-9]{64}$/);}
 console.log('PASS: mocked three-checkpoint/history/15-full-oracle/noop/retained-space/normal-cleanup/full-log-archive state machine; testOnly, no kernel claim.');
}finally{for(const[k,v]of Object.entries(saved)){if(v===undefined)delete process.env[k];else process.env[k]=v;}fs.rmSync(temp,{recursive:true,force:true});}
