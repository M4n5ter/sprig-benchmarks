import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {BUILD,PROGRAM,loadCommands,validateProtocol,verifyCargoPackages,oracleCommand,verifyOracleSnapshot,exactOracle,runStressCargoLayerfs} from './stress_cargo_layerfs.mjs';
const hash=x=>createHash('sha256').update(x).digest('hex');
assert.equal(hash(fs.readFileSync(new URL('./cargo_layerfs.mjs',import.meta.url))),'ed6811f90294684c07b1de2019331e06f54572950df3a257f3e1d020f3030f4b','frozen adapter changed');
const identity=loadCommands(), packages=Array.from({length:16},(_,i)=>'node'+String(i).padStart(3,'0')).concat('stress-app');
const expected=leaf=>{const v=[leaf];for(let i=1;i<16;i++)v.push(i+1+[...new Set([i-1,Math.floor(i/2),0])].reduce((s,j)=>s+v[j],0));return String(v.at(-1))+'\n';};
const manifest={schema:'sprig-stress-cargo-v2',crates:16,totalPackages:17,packages,expectedStdoutBefore:expected(2),expectedStdoutAfter:expected(103),buildScriptBefore:'pub const BUILD_VALUE: u64 = 1;\n',buildScriptAfter:'pub const BUILD_VALUE: u64 = 2;\n',protocolSha256:identity.sha256,lockfileSha256:'a'.repeat(64)};
validateProtocol(manifest);
for(const patch of [{crates:64},{totalPackages:16},{packages:packages.slice(1)},{protocolSha256:'0'.repeat(64)},{expectedStdoutAfter:'2\n'},{buildScriptAfter:manifest.buildScriptBefore}])assert.throws(()=>validateProtocol({...manifest,...patch}));
const statuses=kind=>packages.map(p=>`       ${kind} ${p} v0.1.0 (/work/${p})`).join('\n');
for(const phase of ['clean_build','edit_build'])assert.equal(verifyCargoPackages(statuses('Compiling'),packages,phase).allExpectedPackages,true);
for(const phase of ['noop_build','restored_rebuild'])assert.equal(verifyCargoPackages(statuses('Fresh'),packages,phase).freshPackages.length,17);
for(const bad of [statuses('Fresh').split('\n').slice(1).join('\n'),statuses('Fresh')+'\n Fresh node000 v0.1.0',statuses('Fresh').replace('Fresh node000','Compiling node000'),statuses('Fresh').replace('node015','other'),statuses('Fresh').replace('v0.1.0','v0.2.0')])assert.throws(()=>verifyCargoPackages(bad,packages,'restored_rebuild'));
const precise='{"schema":"cargo-full-tree-v1","entries":[{"mtime_ns":1700000000000000001}],"hardlink_groups":[]}';
assert.equal(exactOracle(precise).entries[0].mtime_ns,'1700000000000000001');
assert.equal(oracleCommand('/workspaces/1',precise).input,null);
assert.ok(oracleCommand('/workspaces/1',precise).script.length<256);
assert.ok(!oracleCommand('/workspaces/1',precise).script.includes('1700000000000000001'));
const hugeOracle=JSON.stringify({schema:'cargo-full-tree-v1',entries:Array.from({length:4000},(_,i)=>({path:`target/debug/deps/item${i}`,type:'file',mode:420,mtime_ns:'1700000000000000001',size:1,sha256:'a'.repeat(64)})),hardlink_groups:Array.from({length:4000},(_,i)=>[`target/debug/deps/item${i}`])}).replace(/("mtime_ns":)"([0-9]+)"/g,'$1$2');
assert.ok(Buffer.byteLength(hugeOracle)>128*1024);
assert.equal(verifyOracleSnapshot(hugeOracle,hugeOracle).ok,true);
assert.throws(()=>verifyOracleSnapshot(hugeOracle.replace('1700000000000000001','1700000000000000002'),hugeOracle),/full-tree mismatch/);
assert.ok(oracleCommand('/workspaces/2',hugeOracle).script.length<256);
for(const edit of [x=>x.entries[0].sha256='b'.repeat(64),x=>x.entries[0].type='symlink',x=>x.entries[0].mode=384,x=>x.hardlink_groups[0].push('unrelated'),x=>x.entries[0].target='elsewhere']){const bad=exactOracle(hugeOracle);edit(bad);assert.throws(()=>verifyOracleSnapshot(JSON.stringify(bad),hugeOracle),/full-tree mismatch/);}

const temp=fs.mkdtempSync(path.join(os.tmpdir(),'stress-cargo-lfs-test-'));
const saved={GITHUB_ACTIONS:process.env.GITHUB_ACTIONS,RUNNER_TEMP:process.env.RUNNER_TEMP};
try{
 process.env.GITHUB_ACTIONS='true';process.env.RUNNER_TEMP=temp;
 async function sample(failure=null,incremental=0){
  const run=path.join(temp,`${failure??'pass'}-${incremental}`);fs.mkdirSync(run);
  const measured=path.join(run,'mount'),source=path.join(run,'source');fs.mkdirSync(measured);fs.mkdirSync(source);
  fs.writeFileSync(path.join(source,'Cargo.lock'),'# synthetic test-only lock\n');
  const fixtureRaw=execFileSync('python3',['feasibility/tree_oracle.py','snapshot',source],{encoding:'utf8'});
  const oraclePath=path.join(run,'oracle.json');fs.writeFileSync(oraclePath,fixtureRaw);
  const manifestPath=path.join(run,'manifest.json');fs.writeFileSync(manifestPath,JSON.stringify({...manifest,initial:exactOracle(fixtureRaw),lockfileSha256:hash(fs.readFileSync(path.join(source,'Cargo.lock')))}).replace(/(\"mtime_ns\"\s*:\s*)\"(-?[0-9]+)\"/g,'$1$2'));
  fs.mkdirSync(path.join(measured,'docker'));fs.mkdirSync(path.join(measured,'volume'));
  const image='sha256:'+'b'.repeat(64),head='32'+'a'.repeat(64),revision='12'+'c'.repeat(64);
  let mounted=[],counter=0,builds=0,edited=false,closed=false;const projectName='test-cargo-project',containerId='f'.repeat(64);
  const events=[],branches=new Map([['main',head]]);
  const client={created:{layer:head},branch:{fork:async(name,base)=>{branches.set(name,branches.get(base)??base);},list_commits:async name=>({items:branches.get(name)===revision?[{id:revision}]:[],hasMore:false})},sandbox:{create:async()=>({sandbox:'test-sandbox'}),list_workspaces:async()=>({items:mounted.map(w=>({...w,base:branches.get(w.name),activity:'Idle'})),hasMore:false}),close:async()=>{closed=true;events.push('close');}},project:{list_branches:async()=>({items:[...branches].map(([name,base])=>({name,base:head,head:base===head?null:base})),hasMore:false}),list_sandboxes:async()=>({items:[{sandbox:'test-sandbox',workspaces:mounted.length}],hasMore:false})},workspace:{mount:async(sandbox,name)=>{const ws={sandbox,path:'/workspaces/'+(++counter),name};mounted.push(ws);events.push('mount:'+name);return ws;},exec:async(ws,command)=>{
   events.push(command);
   if(command.includes('rustc -Vv; cargo -V'))return {exitCode:0,stdout:failure==='toolchain'?'rustc 1.99.1 (test)\ncargo 1.99.1 (test)\n':'rustc 1.90.0 (test)\ncargo 1.90.0 (test)\n',stderr:''};
   if(command.endsWith(BUILD)){
    builds++;if(failure==='uncertain_exec'&&builds===2)throw Error('lost exec acknowledgment');
    const kind=[2,4].includes(builds)?'Fresh':'Compiling';let stderr=statuses(kind);
    if(failure==='missing_fresh'&&builds===4)stderr=stderr.split('\n').slice(1).join('\n');
    return {exitCode:0,stdout:'',stderr};
   }
   if(command.endsWith(PROGRAM))return {exitCode:0,stdout:edited?manifest.expectedStdoutAfter:manifest.expectedStdoutBefore,stderr:''};
   if(command.endsWith(identity.commands.edit)){edited=true;return {exitCode:0,stdout:'',stderr:''};}
   if(command.endsWith(identity.commands.verifyBefore)||command.endsWith(identity.commands.verifyAfter))return {exitCode:0,stdout:JSON.stringify({ok:failure!=='artifact',hardlinkProbe:true,exactMtime:true,buildValue:command.endsWith(identity.commands.verifyAfter)?2:1,generatedFiles:['target/debug/build/node000-test/out/generated.rs']}),stderr:''};
   if(command.includes(' snapshot ')){assert.ok(command.length<1024);const raw=ws.name==='second'||(ws.name==='work'&&builds>=3)?hugeOracle:fixtureRaw;return {exitCode:0,stdout:failure==='mtime_mismatch'&&ws.name==='second'?raw.replace('1700000000000000001','1700000000000000002'):raw,stderr:''};}
   if(command.includes(' verify '))return {exitCode:0,stdout:'{"ok":true}',stderr:''};
   return {exitCode:0,stdout:'',stderr:''};
  },commit:async ws=>{events.push('commit');branches.set(ws.name,revision);return {kind:'Committed',head:revision};},unmount:async ws=>{events.push('unmount:'+ws.name);mounted=mounted.filter(x=>x.path!==ws.path);}},close:async()=>{}};
  const runner=async argv=>{
   const line=argv.join(' ');let stdout='';
   if(argv[0]==='stat')stdout='btrfs\n';
   else if(argv[0]==='findmnt')stdout=JSON.stringify({filesystems:[{target:measured,fstype:'btrfs'}]});
   else if(argv[0]==='btrfs'&&argv[2]==='usage')stdout='Used: 123456\n';
   else if(line.includes('ps -aq --no-trunc'))stdout=containerId;
   else if(line.includes('inspect '+containerId))stdout=JSON.stringify([{Id:containerId,Image:failure==='wrong_image'?'sha256:'+'0'.repeat(64):image,Config:{Labels:{'layerfs.project':projectName}},State:{Running:true}}]);
   else if(line.includes('image inspect'))stdout=JSON.stringify([{Id:image,Config:{User:'root'}}]);
   else if(line.includes('info --format'))stdout=JSON.stringify({DockerRootDir:path.join(measured,'docker')});
   else if(line.includes('volume inspect'))stdout=path.join(measured,'volume');
   else if(line.includes(' run '))stdout=fixtureRaw;
   return {returncode:0,signal:null,stdout,stderr:''};
  };
  const report=await runStressCargoLayerfs({root:path.join(measured,'sample'),measuredMount:measured,source,oraclePath,manifestPath,daemonPath:fs.realpathSync('/bin/true'),layerfsSdkPath:path.resolve('feasibility/stress_cargo_layerfs.mjs'),image,incremental,projectName},{subprocess:runner,sdk:{LayerFS:{init:async()=>client}}});
  assert.equal(report.testOnly,true);
  if(!failure){
   assert.equal(report.ok,true,JSON.stringify(report.error));assert.equal(report.cargoBuildObservations.length,4);assert.equal(report.artifactChecks.length,5);assert.equal(report.fullRestoredTreeVerified,true);assert.equal(report.lifecycle.cleanup.complete,true);assert.equal(mounted.length,0);assert.equal(closed,true);assert.equal(report.lifecycle.activeAtSpace.workspaces.length,3);assert.equal(report.image,image);assert.equal(report.protocolSha256,identity.sha256);
   assert.deepEqual(report.commands.filter(x=>x.purpose.startsWith('space_')).map(x=>x.purpose),['space_sync','space_usage','space_groups']);
   const restoredOracle=report.commands.find(x=>x.purpose==='restore_verify');assert.ok(Buffer.byteLength(restoredOracle.stdout)>128*1024);assert.equal(fs.readFileSync(restoredOracle.stdoutPath,'utf8'),hugeOracle);assert.ok(restoredOracle.command.length<1024);
   const verify=report.commands.findIndex(x=>x.purpose==='restore_verify'),execute=report.commands.findIndex(x=>x.purpose==='restored_execute');assert.ok(verify<execute);assert.ok(report.full_task_seconds>=report.phase_seconds.cleanup);assert.equal(report.commands.filter(x=>x.purpose==='target_probe').length,1);
  }else{assert.equal(report.ok,false,failure);if(failure==='mtime_mismatch')assert.equal(report.commands.some(x=>x.purpose==='restored_execute'),false);if(['uncertain_exec','wrong_image'].includes(failure)){assert.equal(closed,false);assert.equal(report.lifecycle.cleanup.complete,false);assert.equal(events.some(x=>x.startsWith('unmount:')),false);}}
  return report;
 }
 await sample(null,0);await sample(null,1);
 for(const failure of ['missing_fresh','artifact','toolchain','uncertain_exec','wrong_image','mtime_mismatch'])await sample(failure);
 console.log('PASS: strict 17-package acceptance; shared protocol identity; >128KiB exact host oracle with bounded argv and 1ns mismatch rejection; two mocked incremental lifecycles; artifact/toolchain/Fresh/unknown-exec failures. Test-only, no real Cargo/kernel claim.');
}finally{
 for(const [k,v]of Object.entries(saved)){if(v===undefined)delete process.env[k];else process.env[k]=v;}
 fs.rmSync(temp,{recursive:true,force:true});
}
