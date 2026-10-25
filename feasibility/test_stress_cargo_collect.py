import hashlib,json,os,stat,tempfile,unittest
from pathlib import Path
from stress_cargo_collect import collect

class Tests(unittest.TestCase):
    def test_failed_setup_copies_only_named_evidence_and_preserves_private_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);results=base/'results';results.mkdir();temporary=base/'temp';temporary.mkdir()
            pilot=temporary/'stress-cargo-capacity-pilot';pilot.mkdir(mode=0o700)
            (pilot/'inc0.stdout').write_text('full pilot output');(pilot/'inc0.stderr').write_text('')
            (pilot/'incremental-0').mkdir();(pilot/'incremental-0'/'secret').write_text('excluded')
            (results/'stress-cargo-comparison-0.json').write_text('{"complete":false}')
            (results/'daemon.json.original').write_text('excluded config')
            dest=base/'artifacts';rows=collect(results,temporary,dest,os.getuid(),os.getgid())
            self.assertEqual(len(rows),3);self.assertEqual(stat.S_IMODE(pilot.stat().st_mode),0o700)
            self.assertEqual((dest/'capacity/inc0.stdout').read_text(),'full pilot output')
            self.assertFalse((dest/'results/daemon.json.original').exists())
            self.assertEqual(stat.S_IMODE((dest/'capacity/inc0.stdout').stat().st_mode),0o644)
            self.assertEqual(stat.S_IMODE(dest.stat().st_mode),0o755)
            self.assertEqual(len(json.loads((dest/'collection.json').read_text())['files']),3)
    def test_missing_sources_before_any_setup_still_produces_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);t=b/'temp';t.mkdir()
            self.assertEqual(collect(b/'results',t,b/'out',os.getuid(),os.getgid()),[])
    def test_symlink_evidence_is_rejected_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);t=b/'temp';t.mkdir();r=b/'results';r.mkdir();secret=b/'secret';secret.write_text('no')
            (r/'environment.txt').symlink_to(secret)
            with self.assertRaises(OSError):collect(r,t,b/'out',os.getuid(),os.getgid())
    def test_allowlisted_archived_logs_and_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);t=b/'temp';t.mkdir();d=t/'stress-cargo-records/inc0';d.mkdir(parents=True)
            (d/'sprig-writable-0.jsonl').write_text('{}\n');logs=d/'sprig-writable-0.jsonl.logs';logs.mkdir();(logs/'000001-example.stderr').write_text('complete')
            self.assertEqual(len(collect(b/'results',t,b/'out',os.getuid(),os.getgid())),2)

    def test_declared_jsonl_archive_is_copied_and_verified(self):
        self.archive_case(None)
    def test_missing_hash_size_and_unsafe_declared_archive_fail_closed(self):
        for failure in ('missing','hash','size','outside','empty','comparison_only','malformed','null_path','null_sample'):
            with self.subTest(failure=failure):self.archive_case(failure)
    def archive_case(self,failure):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);t=b/'temp';t.mkdir();r=b/'results';r.mkdir()
            directory=t/'stress-cargo-records/inc0/sprig-writable-0.jsonl.logs';directory.mkdir(parents=True)
            source=directory/'000055-lifecycle.jsonl';data=b'{"event":"normal cleanup"}\n'
            if failure not in ('missing','comparison_only'):source.write_bytes(data)
            item={'archived':str(source),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            if failure=='hash':item['sha256']='0'*64
            if failure=='size':item['bytes']+=1
            if failure=='outside':item['archived']=str(b/'private.jsonl')
            if failure=='null_path':item['archived']=None
            sample={'ok':True,'completeLogArchive':[] if failure=='empty' else [item]}
            if failure=='comparison_only':
                (r/'stress-cargo-comparison-0.json').write_text(json.dumps({'records':[{'product':'sprig-writable','round':0,'sample':sample}]}))
            else:(r/'stress-cargo-sprig-writable-inc0-0.json').write_text(json.dumps(sample))
            if failure=='malformed':(r/'stress-cargo-sprig-writable-inc0-0.json').write_text('{')
            if failure=='null_sample':(r/'stress-cargo-sprig-writable-inc0-0.json').write_text('null')
            out=b/'out'
            if failure:
                with self.assertRaisesRegex(ValueError,'completeness failed'):collect(r,t,out,os.getuid(),os.getgid())
            else:collect(r,t,out,os.getuid(),os.getgid())
            coverage=json.loads((out/'collection.json').read_text())['declaredArchiveVerification']
            self.assertEqual(coverage['ok'],failure is None)
            if failure is None:
                self.assertEqual(coverage['verifiedUniqueFiles'],1)
                self.assertEqual((out/'records/inc0/sprig-writable-0.jsonl.logs/000055-lifecycle.jsonl').read_bytes(),data)

if __name__=='__main__':unittest.main()
