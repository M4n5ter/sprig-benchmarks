import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
// Backend supplies committed operations; forks may have different materialization costs.
export async function checkMerge(api){
 const text='first=base\nkeep=one\nkeep=two\nmiddle=base\nkeep=three\nkeep=four\nlast=base\n';
 await api.write('work','merge.txt',text);
 await api.fork('left','work');await api.fork('right','work');
 const a=text.replace('first=base','first=left'),b=text.replace('last=base','last=right');
 await api.write('left','merge.txt',a);await api.write('right','merge.txt',b);
 const start=performance.now();await api.merge('left','right','combined');const independentMs=performance.now()-start;
 assert.equal((await api.read('combined','merge.txt')).trim(),a.replace('last=base','last=right').trim());
 assert.equal((await api.read('left','merge.txt')).trim(),a.trim());assert.equal((await api.read('right','merge.txt')).trim(),b.trim());
 await api.fork('conflictleft','work');await api.fork('conflictright','work');
 await api.write('conflictleft','merge.txt',text.replace('middle=base','middle=left'));
 await api.write('conflictright','merge.txt',text.replace('middle=base','middle=right'));
 let refusal=null;try{await api.merge('conflictleft','conflictright','conflicted');}catch(e){refusal=String(e.code||e.message);}
 assert.ok(refusal && /Conflict|merge_conflict|conflict/i.test(refusal),'Expected specific merge conflict, got '+refusal);
 assert.equal((await api.read('conflictleft','merge.txt')).trim(),text.replace('middle=base','middle=left').trim());
 assert.equal((await api.read('conflictright','merge.txt')).trim(),text.replace('middle=base','middle=right').trim());
 return {nonoverlappingSameFileMerged:true,inputBranchesUnchanged:true,overlappingSameFileRefused:true,independentMergeMs:independentMs,conflict:refusal};
}
