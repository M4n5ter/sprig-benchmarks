import {checkHistory} from './history-check.mjs';
import {checkMerge} from './merge-check.mjs';
import {LayerFS} from './layerfs/sdk/js/src/index.js';
import {LayerFSOperator} from './layerfs/sdk/js/operator/index.js';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {performance} from 'node:perf_hooks';
const root=process.cwd(), records=[];
const json=x=>JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v,2);
const command=(p,a)=>execFileSync(p,a,{encoding:'utf8',maxBuffer:16*1024*1024});
const timed=async fn=>{const t=performance.now();const value=await fn();return {ms:performance.now()-t,value};};
function treeStats(dir){const own=fs.lstatSync(dir);let bytes=own.size,allocated=own.blocks*512,files=0;for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){const s=treeStats(p);bytes+=s.bytes;allocated+=s.allocated;files+=s.files;}else{const s=fs.lstatSync(p);bytes+=s.size;allocated+=s.blocks*512;files++;}}return {bytes,allocated,files,exclusivePhysicalBytes:null};}
function diskStats(dir){return {...treeStats(dir),duApparentBytes:Number(command('du',['-s','--apparent-size','-B1',dir]).split(/\s/)[0]),duAllocatedBytes:Number(command('du',['-s','-B1',dir]).split(/\s/)[0])};}
function components(dir){return Object.fromEntries(fs.readdirSync(dir,{withFileTypes:true}).map(e=>{const p=path.join(dir,e.name);const t=fs.lstatSync(p);return [e.name,e.isDirectory()?diskStats(p):{bytes:t.size,allocated:t.blocks*512}];}));}
function verify(dir,manifest){for(const f of manifest)assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(dir,f.path))).digest('hex'),f.sha256);}
function sprig(store,...args){try{const r=JSON.parse(command(path.join(root,'sprig/target/release/sprig'),['--store',store,'--json',...args]));return r.result??r;}catch(e){if(e.stdout)throw new Error(String(e.stdout));throw e;}}
const rounds=Number(process.env.ROUNDS||1),cases=(process.env.CASES||'identical').split(',');
for(let round=0;round<rounds;round++)for(const caseName of cases){
 const fixture=path.join(root,'fixtures',caseName),manifest=JSON.parse(fs.readFileSync(fixture+'.json'));
 const checks='('+manifest.map(f=>`printf '%s  %s\\n' '${f.sha256}' '${f.path}'`).join(';')+') | sha256sum -c -';
 // Alternate order, fresh store each sample. Fixture generated and hashed before all timers.
 for(const product of round%2?['layerfs','sprig']:['sprig','layerfs']){
 const id=`${product}-${caseName}-${round}`,r={product,case:caseName,round,files:manifest.length,logicalBytes:manifest.reduce((a,x)=>a+x.bytes,0),durability:product==='layerfs'?'Disposable/WAL/synchronous=OFF':'default synchronization enabled',timingScope:product==='layerfs'?'JS SDK in-process':'whole CLI subprocess'};records.push(r);
 try{
 if(product==='sprig'){
   const store=path.join(root,'scratch',id);fs.mkdirSync(path.dirname(store),{recursive:true});sprig(store,'init');
   let t=await timed(()=>sprig(store,'import',fixture,'main'));r.importMs=t.ms;r.copyStats=t.value.copy_stats;
   t=await timed(()=>sprig(store,'branch','metadata','main'));r.metadataBranchMs=t.ms;
   t=await timed(()=>sprig(store,'fork','main','work'));r.forkToWorkspaceMs=t.ms;const wp=t.value.path;r.forkCopyStats=t.value.copy_stats;
   t=await timed(()=>command(path.join(root,'sprig/target/release/sprig'),['--store',store,'exec','work','--','bash','-c',checks]));r.firstFullReadVerifyMs=t.ms;verify(wp,manifest);
   r.totalImportForkReadMs=r.importMs+r.forkToWorkspaceMs+r.firstFullReadVerifyMs;
   r.afterFirstTaskStore=diskStats(store);
   t=await timed(()=>sprig(store,'fork','main','second'));r.warmForkToWorkspaceMs=t.ms;
   t=await timed(()=>command(path.join(root,'sprig/target/release/sprig'),['--store',store,'exec','second','--','bash','-c',checks]));r.warmFirstFullReadMs=t.ms;
   if(caseName.startsWith('history-'))await checkHistory(caseName,{
    exec:async cmd=>command(path.join(root,'sprig/target/release/sprig'),['--store',store,'exec','work','--','bash','-c',cmd]),
    commit:async msg=>sprig(store,'checkpoint','work','-m',msg),
    history:async()=>sprig(store,'log','work')
   },r.historyCheck={});
   r.productStats=sprig(store,'stats');r.fullStore=diskStats(store);r.storeComponents=components(store);r.correct=true;
   if(caseName==='identical' && round===0)r.mergeChecks=await checkMerge({
     write:async(b,p,t)=>sprig(store,'write',b,p,'--text',t),
     fork:async(b,from)=>sprig(store,'fork',from,b),
     merge:async(a,b,c)=>sprig(store,'merge',a,b,c),
     read:async(b,p)=>Buffer.from(sprig(store,'read',b,p)).toString()
   });
   fs.rmSync(store,{recursive:true});
 }else{
   const volume='sprigbench-'+id;command('docker',['volume','create',volume]);
   const mount=command('docker',['volume','inspect','--format','{{.Mountpoint}}',volume]).trim();
   const home=path.join(root,'scratch',id+'-home');fs.mkdirSync(home,{recursive:true,mode:0o700});
   process.env.LAYERFS_HOME=home;process.env.LAYERFS_VOLUME=volume;process.env.LAYERFS_STORE_PATH=path.join(mount,'global/store.sqlite');process.env.LAYERFS_CONTAINER_PREFIX='sprigbench-';
   const l=new LayerFS(id,{storePath:process.env.LAYERFS_STORE_PATH}),op=new LayerFSOperator(l);
   try{
    let t=await timed(()=>l.project.init(fixture));r.importMs=t.ms;
    t=await timed(()=>l.branch.fork('work','main'));r.metadataBranchMs=t.ms;
    r.afterImportStats=await op.store.stats();
    t=await timed(()=>l.workspace.mount('work'));r.mountMs=t.ms;const ws=t.value;r.forkToWorkspaceMs=r.metadataBranchMs+r.mountMs;
    t=await timed(()=>l.workspace.exec(ws,checks));r.firstFullReadVerifyMs=t.ms;assert.equal(t.value.exitCode,0,json(t.value));
    r.totalImportForkReadMs=r.importMs+r.forkToWorkspaceMs+r.firstFullReadVerifyMs;
    t=await timed(async()=>{await l.branch.fork('second','main');return l.workspace.mount('second');});r.warmForkToWorkspaceMs=t.ms;const ws2=t.value;
    t=await timed(()=>l.workspace.exec(ws2,checks));r.warmFirstFullReadMs=t.ms;assert.equal(t.value.exitCode,0,json(t.value));await l.workspace.unmount(ws2,true);
    if(caseName.startsWith('history-'))await checkHistory(caseName,{
      exec:async cmd=>{const result=await l.workspace.exec(ws,cmd);assert.equal(result.exitCode,0,json(result));return result;},
      commit:async msg=>l.workspace.commit(ws,msg),history:async()=>{const items=[];let more=true;while(more){const page=await l.branch.list_commits('work',1000,items.length);assert.ok(page.items.length||!page.hasMore,'Non-progressing history page');items.push(...page.items);more=page.hasMore;}return items;}
    },r.historyCheck={});
    await l.workspace.unmount(ws,true);r.productStats=await op.store.stats();await l.close();const stopped=command('docker',['ps','-q','--filter','volume='+volume]).trim().split('\n').filter(Boolean);if(stopped.length)command('docker',['stop','-t','10',...stopped]);r.fullStore=diskStats(mount);r.storeComponents=components(mount);if(fs.existsSync(path.join(mount,'global')))r.globalFiles=components(path.join(mount,'global'));r.sdkHome=diskStats(home);for(const key of ['bytes','allocated','duApparentBytes','duAllocatedBytes'])r.fullStore[key]+=r.sdkHome[key];r.correct=true;
    if(caseName==='identical' && round===0)r.mergeChecks=await checkMerge({
      write:async(b,p,t)=>l.fs.write(b,'/'+p,t),fork:async(b,from)=>l.branch.fork(b,from),merge:async(a,b,c)=>l.branch.merge(a,b,c),
      read:async(b,p)=>{const v=await l.fs.read(b,'/'+p);return (v.lines??[]).map(x=>x.text).join('\n')||v.text;}
    });
    await l.close();
   }finally{
    await l.close();const containers=command('docker',['ps','-aq','--filter','volume='+volume]).trim().split('\n').filter(Boolean);if(containers.length)command('docker',['rm','-f',...containers]);command('docker',['volume','rm',volume]);fs.rmSync(home,{recursive:true});
   }
 }
 }catch(e){r.correct=false;r.error={message:e.message,stack:e.stack};throw e;}
 finally{fs.writeFileSync('results/comparison.json',json({records,caveats:['Different durability contracts; no durability-matched speed claim.','Warm generated inputs; no cold-cache claim.','Metadata-only branch is separate from fully usable workspace.','Full-read timers include the same shell sha256sum workload, via Sprig exec CLI versus SDK Docker exec; transport overhead is included.','Allocated blocks are not exclusive physical allocation.']}));console.log(json(r));}
 }
}
