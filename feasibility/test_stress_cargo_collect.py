import json,os,stat,tempfile,unittest
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

if __name__=='__main__':unittest.main()
