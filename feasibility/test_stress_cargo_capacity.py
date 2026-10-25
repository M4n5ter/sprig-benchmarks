import copy,json,unittest
from stress_cargo_capacity import pilot_script,validate_pilot
from stress_cargo_prepare import PROTOCOL,expected

class Tests(unittest.TestCase):
    def row(self):
        row={'ok':True,'software':'rustc 1.90.0 (pinned)\ncargo 1.90.0 (pinned)\n','targetAllocatedBytes':1234,'commands':[]}
        for phase in ('clean_build','noop_build','edit_build','noop_after_edit'):
            mode='Fresh' if phase in ('noop_build','noop_after_edit') else 'Compiling'
            row['commands'].append(dict(purpose=phase,returncode=0,stdout='',stderr=''.join(f' {mode} {p} v0.1.0\n' for p in PROTOCOL['packages'])))
        for phase,value in [('clean_execute',expected(2)),('edit_execute',expected(103))]:row['commands'].append(dict(purpose=phase,returncode=0,stdout=value,stderr=''))
        for phase,value in [('clean_artifacts',1),('edit_artifacts',2)]:row['commands'].append(dict(purpose=phase,returncode=0,stdout=json.dumps(dict(ok=True,buildValue=value,hardlinkProbe=True,exactMtime=True,generatedFiles=['target/generated.rs'])),stderr=''))
        return row
    def test_script_syntax(self):
        script=pilot_script();compile(script.split('\n',1)[1].rsplit('\n',1)[0],'pilot','exec')
    def test_valid_measured_pilot(self):
        row=validate_pilot(self.row(),{'expectedStdoutBefore':expected(2),'expectedStdoutAfter':expected(103)})
        self.assertTrue(row['commands'][0]['packageAcceptance']['allPackagesVerified'])
    def test_rejects_wrong_toolchain_zeroallocation_wrongoutput_failedcommands(self):
        for field,value in [('software','rustc 1.99.1\ncargo 1.99.1'),('targetAllocatedBytes',0),('ok',False)]:
            row=self.row();row[field]=value
            with self.assertRaises(ValueError):validate_pilot(row,{'expectedStdoutBefore':expected(2),'expectedStdoutAfter':expected(103)})
        row=self.row();row['commands'][-1]['returncode']=1
        with self.assertRaises(ValueError):validate_pilot(row,{'expectedStdoutBefore':expected(2),'expectedStdoutAfter':expected(103)})

if __name__=='__main__':unittest.main()
