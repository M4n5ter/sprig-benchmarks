#!/usr/bin/env python3
"""Self-contained mock tests. No Docker, Sprig, Btrfs, mounts, or Rust invoked."""
import copy
from contextlib import ExitStack
import json
import io
import itertools
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cargo_transport_sample as t
import cargo_sample as b
import current_sample as current


class MockSample(t.CargoTransportSample):
    def __init__(self, root, backend="writable", incremental=1, failure=None):
        super().__init__(t.transport_report())
        self.root=root; self.library=root/"library"; (self.library/"native").mkdir(parents=True)
        self.source=root/"fixture"; self.source.mkdir(); self.logs=root/"logs"; self.logs.mkdir()
        self.binary=root/"sprig-not-executed"; self.binary.write_text("mock")
        self.backend=backend; self.incremental=incremental; self.image="sha256:"+"a"*64
        self.label="mock-cargo"; self.container_sequence=0; self.attempted_generations=set()
        self.expected_generation_count=4 if backend=="writable" else 3; self.steps=[]
        self.report.update(backend=backend,incremental=incremental,containingFilesystem={"mountpoint":str(root)},production_sha="b"*40)
        self.fixture={"schema":"cargo-full-tree-v1","entries":[{"path":".","type":"directory","mode":493,"mtime_ns":1}],"hardlink_groups":[]}
        self.workspaces={}; self.generations={}; self.mounts={}; self.contents={}; self.engine={}
        self.cli_calls=[]; self.app_calls=[]; self.engine_calls=[]; self.ledger=[]; self.events=[]
        self.failure=failure; self.checkpoint_oracle=None; self.setup_done=False; self.space_taken=False

    def event(self,event,**values):self.events.append((event,values))
    def step_record(self,row):self.ledger.append(copy.deepcopy(row))
    def command(self,*args,**kwargs):raise AssertionError("unexpected real command route")

    def make(self,name,revision):
        generation="g%04d"%len(self.generations)
        tree=self.library/"native"/generation/"tree"; tree.mkdir(parents=True)
        pin=revision if name in ("main","second") or revision!="0"*64 else f"{1000+len(self.generations):064x}"
        row={"name":name,"path":str(tree),"base_revision":revision,"backend":{"kind":self.backend},"mount_state":"native" if self.backend=="native" else "unmounted"}
        if self.backend!="native":
            row["backend"]["revision"]=pin
            (tree.parent/("writable-base" if self.backend=="writable" else "projection-base")).write_text(pin)
        self.generations[generation]=row; self.workspaces[name]=row
        if self.backend=="projection":self.do_mount(row)
        return copy.deepcopy(row)

    def do_mount(self,row):
        tree=row["path"]; generation=Path(tree).parent.name; row["mount_state"]="mounted"
        if self.backend=="writable":
            self.mounts[tree]={"mountpoint":tree,"root":"/","filesystem":"fuse","source":"sprig-writable-cas:"+generation+":"+row["backend"]["revision"],"mountOptions":["rw","nosuid","nodev","noatime"],"superOptions":{"user_id":"0","group_id":"0","default_permissions":""}}
        else:
            lower=str(Path(tree).parent/"lower")
            self.mounts[tree]={"mountpoint":tree,"root":"/","filesystem":"overlay","source":"overlay","mountOptions":["rw"],"superOptions":{"lowerdir":lower,"upperdir":str(Path(tree).parent/"upper"),"workdir":str(Path(tree).parent/"work")}}
            self.mounts[lower]={"mountpoint":lower,"root":"/","filesystem":"fuse","source":"sprig-cas","mountOptions":["ro"],"superOptions":{"user_id":"0"}}

    def cli(self,action,*args,creation=False):
        self.cli_calls.append((action,args,creation))
        if action=="init":return {}
        if action=="import":self.contents[args[1]]="before";return self.make(args[1],"0"*64)
        if action=="fork":self.contents[args[1]]=self.contents[args[0]];return self.make(args[1],self.workspaces[args[0]]["base_revision"])
        if action=="mount":self.do_mount(self.workspaces[args[0]]);return copy.deepcopy(self.workspaces[args[0]])
        if action=="show":return copy.deepcopy(self.workspaces[args[0]])
        if action=="checkpoint":
            assert not [v for v in self.engine.values() if not v["removed"]], "bound container survived into checkpoint"
            revision="1"*64
            if self.backend=="writable":
                old=self.workspaces["work"];self.mounts.pop(old["path"]);old["mount_state"]="unmounted"
                self.make("work",revision);self.do_mount(self.workspaces["work"])
            else:self.workspaces["work"]["base_revision"]=revision
            return {"committed":True,"branch":"work","revision":revision,"previous_head":"0"*64}
        if action=="restore":self.contents[args[1]]=self.contents["work"];return self.make(args[1],args[0])
        if action=="list":return {"branches":{name:row["base_revision"] for name,row in self.workspaces.items()}}
        if action=="unmount-generation":
            row=self.generations[args[0]]
            assert not any(not value["removed"] and value["tree"]==row["path"] for value in self.engine.values()),"product unmount with compiler bind"
            self.mounts.pop(row["path"],None);self.mounts.pop(str(Path(row["path"]).parent/"lower"),None);row["mount_state"]="unmounted";return {}
        raise AssertionError(action)

    def processes(self):
        return [{"pid":i+1,"generation":generation,"revision":row["backend"]["revision"],"backend":self.backend}
                for i,(generation,row) in enumerate(self.generations.items()) if row["mount_state"]=="mounted"]

    def pid_identity(self,pid):
        return next(({"pid":pid,"startTimeTicks":value["ticks"]} for value in self.engine.values()
                     if value["pid"]==pid and value["running"]),None)

    def app(self,value,script,input_data,purpose):
        tree=value["tree"]
        if tree==str(self.source):name="source";content="before";assert value["readonly"]
        else:
            names=[name for name,row in self.workspaces.items() if row["path"]==tree and row["mount_state"] in ("native","mounted")]
            assert len(names)==1,"stale workspace bind used"
            name=names[0];content=self.contents[name]
        self.app_calls.append((purpose,name,script,input_data))
        if self.failure==purpose:raise t.SampleError("mock uncertain exec failure")
        if script==t.BUILD:
            assert self.setup_done
            assert name!="second" or self.report.get("fullRestoredTreeVerified") is True
            return "",("       Fresh owned-cargo-check\n" if purpose=="noop_build" else "   Compiling owned-cargo-check\n")
        if script==t.PROGRAM:return content+"\n",""
        if script==t.EDIT:self.contents[name]="after";return "",""
        if script.startswith("test ! -e target"):
            assert not self.setup_done;self.setup_done=True;return "",""
        if script.endswith("snapshot /work"):
            self.checkpoint_oracle={**self.fixture,"entries":self.fixture["entries"]+[{"path":"target/a","type":"file","mode":493,"mtime_ns":2,"size":1,"sha256":"c"*64}],"hardlink_groups":[["target/a","target/b"]]}
            return json.dumps(self.checkpoint_oracle),""
        if script.endswith("verify /work"):
            assert json.loads(input_data)==(self.checkpoint_oracle if name=="second" else self.fixture)
            return json.dumps({"ok":True,"entries":1,"differences":[]}),""
        raise AssertionError(script)

    def docker(self,operation,arguments,*,purpose,input_data=None):
        self.engine_calls.append((operation,list(arguments),purpose))
        out=err=""
        if operation=="create":
            assert arguments[0]=="create" and "--pull=never" in arguments
            assert not any(flag in arguments for flag in ("--privileged","--cap-add","--device","--security-opt","--network","--user"))
            assert arguments[arguments.index("--entrypoint")+1]=="python3"
            assert t.WAITER in arguments
            for setting in ("CARGO_HOME=/work/.cargo-home","CARGO_TARGET_DIR=/work/target","TMPDIR=/work/.tmp"):
                assert setting in arguments
            cid=f"{len(self.engine)+1:064x}";name=arguments[arguments.index("--name")+1]
            labels=dict(arguments[i+1].split("=",1) for i,arg in enumerate(arguments) if arg=="--label")
            bind=arguments[arguments.index("--mount")+1]
            tree=bind.split("source=",1)[1].split(",",1)[0]
            self.engine[cid]={"id":cid,"name":name,"labels":labels,"tree":tree,"readonly":bind.endswith(",readonly"),"running":False,"removed":False,"pid":10000+len(self.engine),"ticks":2000+len(self.engine),"started":"mock-start-"+cid,"marker":False}
            out=cid+"\n"
            if self.failure=="create_uncertain":raise t.SampleError("mock lost create acknowledgment")
        elif operation=="start":
            self.engine[arguments[1]]["running"]=True;out=arguments[1]+"\n"
            if self.failure=="start_uncertain":raise t.SampleError("mock lost start acknowledgment")
        elif operation=="inspect":
            value=self.engine[arguments[1]]
            running=value["running"]
            mount={"Type":"bind","Source":value["tree"],"Destination":"/work","RW":not value["readonly"]}
            if self.failure=="binding_mismatch":mount["Source"]="/unexpected"
            out=json.dumps([{"Id":value["id"],"Name":"/"+value["name"],"Image":self.image,"Config":{"Labels":value["labels"]},"Mounts":[mount],"HostConfig":{"Privileged":False,"CapAdd":None,"Devices":None,"SecurityOpt":None,"RestartPolicy":{"Name":"no"}},"RestartCount":0,"State":{"Running":running,"Status":"running" if running else "exited","Pid":value["pid"] if running else 0,"ExitCode":0,"StartedAt":value["started"]},"GraphDriver":{"Name":"overlay2","Data":{"UpperDir":str(self.root/"docker"/value["id"])}},"LogPath":str(self.root/"docker"/(value["id"]+".log"))}])
        elif operation=="inventory":out="\n".join(cid for cid,value in self.engine.items() if not value["removed"])
        elif operation=="exec":
            value=self.engine[arguments[4]]; assert value["running"]
            script=arguments[-1];assert script.startswith(t.PREFIX)
            out,err=self.app(value,script[len(t.PREFIX):],input_data,purpose)
        elif operation=="cooperative_marker":
            value=self.engine[arguments[3]]
            assert not value["marker"],"cooperative marker retried"
            assert t.MARKER_WRITER in arguments
            value["marker"]=True
            if self.failure=="marker_uncertain":raise t.SampleError("mock marker outcome uncertain")
            if self.failure!="exit_timeout":value["running"]=False
        elif operation=="wait_exit":
            assert not self.engine[arguments[1]]["running"];out="0\n"
            if self.failure=="wait_exit_uncertain":raise t.SampleError("mock lost wait acknowledgment")
        elif operation=="session_logs":assert not self.engine[arguments[1]]["running"]
        elif operation=="remove":
            value=self.engine[arguments[1]];assert not value["running"] and value["marker"]
            assert arguments==["rm",value["id"]]
            value["removed"]=True;out=value["id"]+"\n"
            if self.failure=="remove_uncertain":raise t.SampleError("mock lost remove acknowledgment")
        else:raise AssertionError(operation)
        row={"operation":operation,"purpose":purpose,"argv":["docker",*arguments],"stdout":out,"stderr":err,"returncode":0,"stdoutPath":str(self.logs/("mock-%d.out"%len(self.engine_calls))),"stderrPath":str(self.logs/("mock-%d.err"%len(self.engine_calls))),"seconds":0.001}
        self.report["transportCommands"].append(row)
        self.report["transport_seconds"][operation]=self.report["transport_seconds"].get(operation,0)+0.001
        return out,row

    def sample_space(self):
        assert not self.space_taken
        active=self.retained_snapshot()
        assert len(active["views"])==3 and active["compilerContainer"]["count"]==1
        self.report["lifecycle"]["activeAtSpace"]=copy.deepcopy(active)
        self.report["activeSpace"]={"filesystemUsedBytes":1234,"usageRaw":"mock","groupsRaw":"mock"}
        self.space_taken=True


class ExitObservationSample(MockSample):
    """Model separate Docker state and /proc observations during natural exit."""
    def __init__(self, root, observation="stale_once"):
        super().__init__(root)
        self.observation = observation
        self.exit_inspections = {}

    def pid_identity(self, pid):
        value = next((v for v in self.engine.values() if v["pid"] == pid), None)
        if value and value["marker"] and self.observation == "pid_reused":
            return {"pid": pid, "startTimeTicks": value["ticks"] + 1}
        if value and not value["marker"] and self.observation == "missing_before_marker":
            # Session startup captures identity, then the required-running
            # pre-marker check sees a missing process.
            if any(s.get("pidIdentity") for s in self.sessions.values()):
                return None
        return super().pid_identity(pid)

    def docker(self, operation, arguments, *, purpose, input_data=None):
        output, row = super().docker(operation, arguments, purpose=purpose, input_data=input_data)
        if operation == "inspect" and purpose in ("observe_natural_exit", "verify_natural_exit"):
            value = self.engine[arguments[1]]
            self.exit_inspections[value["id"]] = self.exit_inspections.get(value["id"], 0) + 1
            result = json.loads(output)
            state = result[0]["State"]
            if (self.observation == "stale_once" and self.exit_inspections[value["id"]] == 1
                    or self.observation in ("stale_timeout", "pid_reused", "docker_pid_changed", "started_changed")):
                state.update(Running=True, Status="running", Pid=value["pid"])
            if self.observation == "docker_pid_changed":state["Pid"] += 1
            if self.observation == "started_changed":state["StartedAt"] = "other-start"
            if self.observation == "failed_exit":state["ExitCode"] = 1
            output = json.dumps(result);row["stdout"] = output
        if operation == "wait_exit" and self.observation == "failed_wait":
            output = "1\n";row["stdout"] = output
        return output, row


class TransportTests(unittest.TestCase):
    def patches(self,sample):
        stack=ExitStack()
        for module in (b,current):
            stack.enter_context(patch.object(module,"exact_mount",lambda path:sample.mounts.get(str(path))))
            stack.enter_context(patch.object(module,"mount_table",lambda:list(sample.mounts.values())))
        stack.enter_context(patch.object(t,"fixture_inventory",lambda *args:None))
        return stack

    def test_complete_all_backends_and_incremental_modes(self):
        for backend in ("native","projection","writable"):
            for incremental in (0,1):
                with self.subTest(backend=backend,incremental=incremental),tempfile.TemporaryDirectory() as directory:
                    sample=MockSample(Path(directory),backend,incremental)
                    with self.patches(sample):
                        sample.execute()
                        self.assertTrue(sample.report["ok"])
                        self.assertEqual(len(sample.engine),4)
                        self.assertGreaterEqual(sample.report['convenience_seconds']['checkpointCompilerQuiescePlusProduct'],sample.report['phase_seconds']['checkpoint'])
                        self.assertGreaterEqual(sample.report['convenience_seconds']['restoreToCompilerReady'],sample.report['phase_seconds']['restore'])
                        live=[value for value in sample.engine.values() if not value["removed"]]
                        self.assertEqual(len(live),1)
                        self.assertEqual(live[0]["tree"],sample.workspaces["second"]["path"])
                        self.assertEqual(len(sample.app_calls),16)
                        self.assertEqual([x[0] for x in sample.app_calls],['fixture_verify','cargo_setup','clean_build','clean_execute','noop_build','noop_execute','edit','edit_build','edit_execute','pre_checkpoint_oracle','restore_verify','restored_execute','restored_rebuild','restored_rebuild_execute','main_unchanged','source_unchanged'])
                        self.assertEqual(sample.report['lifecycle']['activeAtSpace']['retainedGenerationCount'],4 if backend=='writable' else 3)
                        self.assertEqual(sample.report['lifecycle']['activeAtSpace']['compilerContainer']['count'],1)
                        sample.cleanup()
                        self.assertTrue(sample.report['lifecycle']['cleanup']['complete'])
                        self.assertFalse(sample.mounts)
                        self.assertTrue(all(value['removed'] for value in sample.engine.values()))
                        self.assertEqual(len([call for call in sample.engine_calls if call[0]=='cooperative_marker']),4)
                        self.assertEqual(len([call for call in sample.engine_calls if call[0]=='remove']),4)

    def test_uncertain_exec_marker_and_bad_binding_block_cleanup_without_retry(self):
        for failure in ('edit_build','marker_uncertain','binding_mismatch','create_uncertain','start_uncertain','wait_exit_uncertain','remove_uncertain','exit_timeout'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                sample=MockSample(Path(directory),failure=failure)
                with self.patches(sample):
                    clock=itertools.count()
                    with patch.object(t.time,'monotonic',lambda:next(clock)), patch.object(t.time,'sleep',lambda _:None):
                        with self.assertRaises(t.SampleError):sample.execute()
                    before_markers=len([call for call in sample.engine_calls if call[0]=='cooperative_marker'])
                    before_unmounts=len([call for call in sample.cli_calls if call[0]=='unmount-generation'])
                    # Avoid a real 15-second wait for fake retained FUSE processes.
                    sample.processes=lambda:[]
                    sample.cleanup()
                    self.assertTrue(sample.cleanup_blocked)
                    self.assertFalse(sample.report['lifecycle']['cleanup']['complete'])
                    self.assertEqual(len([call for call in sample.engine_calls if call[0]=='cooperative_marker']),before_markers)
                    self.assertEqual(len([call for call in sample.cli_calls if call[0]=='unmount-generation']),before_unmounts)
                    self.assertEqual(len([call for call in sample.engine_calls if call[0]=='remove']),1 if failure=='remove_uncertain' else 0)
                    self.assertFalse(any(call[0]=='checkpoint' for call in sample.cli_calls))

    def test_stale_docker_running_missing_proc_resamples_after_marker_only(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = ExitObservationSample(Path(directory))
            with self.patches(sample), patch.object(t.time, "sleep", lambda _: None):
                sample.execute()
                sample.cleanup()
            self.assertTrue(sample.report["lifecycle"]["cleanup"]["complete"])
            self.assertEqual(len([c for c in sample.engine_calls if c[0] == "cooperative_marker"]), 4)
            self.assertEqual(len([c for c in sample.engine_calls if c[0] == "remove"]), 4)
            for session in sample.sessions.values():
                self.assertTrue(session["cooperativeMarkerAcknowledged"])
                self.assertTrue(session["naturalExitAndPidGoneVerified"])
                pending = [o for o in session["pidObservations"] if o.get("pendingDockerExitObservation")]
                self.assertEqual(len(pending), 1)
                self.assertIsNone(pending[0]["observed"])
                self.assertEqual(pending[0]["purpose"], "observe_natural_exit")
                self.assertTrue(any(o["dockerState"]["Status"] == "exited" for o in session["pidObservations"]))

    def test_missing_pid_observation_without_marker_acknowledgment_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = ExitObservationSample(Path(directory))
            session = sample.start_session(sample.source, readonly=True, purpose="source_unchanged")
            sample.engine[session["id"]]["running"] = False
            with self.assertRaisesRegex(t.SampleError, "missing outside acknowledged exit"):
                sample.inspect_session(session, running=None, purpose="observe_natural_exit")
            self.assertFalse(session.get("cooperativeMarkerAcknowledged", False))
            self.assertIsNone(session["pidObservations"][-1]["observed"])
            self.assertFalse(any(c[0] in ("cooperative_marker", "remove") for c in sample.engine_calls))

    def test_exit_observation_identity_failure_timeout_and_bad_exit_block_cleanup(self):
        for observation in ("pid_reused", "docker_pid_changed", "started_changed", "stale_timeout",
                            "failed_exit", "failed_wait", "missing_before_marker"):
            with self.subTest(observation=observation), tempfile.TemporaryDirectory() as directory:
                sample = ExitObservationSample(Path(directory), observation)
                with self.patches(sample):
                    clock = itertools.count()
                    expected_error = {
                        "pid_reused": "cooperative PID1 identity changed",
                        "docker_pid_changed": "cooperative PID1 Docker PID changed",
                        "started_changed": "cooperative PID1 start identity changed",
                        "stale_timeout": "cooperative exit not observed",
                        "failed_exit": "cooperative container did not naturally exit successfully",
                        "failed_wait": "docker wait did not confirm successful natural exit",
                        "missing_before_marker": "cooperative PID1 missing outside acknowledged exit observation",
                    }[observation]
                    with patch.object(t.time, "monotonic", lambda: next(clock)), patch.object(t.time, "sleep", lambda _: None):
                        with self.assertRaisesRegex(t.SampleError, expected_error):sample.execute()
                    mutations_before = [c for c in sample.engine_calls if c[0] in ("cooperative_marker", "remove")]
                    sample.processes = lambda: []
                    sample.cleanup()
                    self.assertTrue(sample.cleanup_blocked)
                    self.assertFalse(sample.report["lifecycle"]["cleanup"]["complete"])
                    self.assertEqual(mutations_before, [c for c in sample.engine_calls if c[0] in ("cooperative_marker", "remove")])
                    self.assertFalse(any(c[0] in ("unmount-generation", "checkpoint") for c in sample.cli_calls))
                    self.assertFalse(any(c[0] == "remove" for c in sample.engine_calls))
                    self.assertEqual(len([c for c in sample.engine_calls if c[0] == "cooperative_marker"]),
                                     0 if observation == "missing_before_marker" else 1)
                    observations = [o for session in sample.sessions.values() for o in session.get("pidObservations", [])]
                    self.assertTrue(observations)
                    if observation == "pid_reused":
                        self.assertNotEqual(observations[-1]["expected"], observations[-1]["observed"])
                        self.assertIsNotNone(observations[-1]["observed"])
                    if observation == "stale_timeout":
                        self.assertTrue(any(o.get("pendingDockerExitObservation") for o in observations))

    def test_waiter_waits_for_exact_marker_writer_identity_to_disappear(self):
        for reused in (False,True):
            observations=[];sleeps=[]
            class MockPath:
                def __init__(self,*parts):self.value='/'.join(map(str,parts))
                def exists(self):return True
                def open(self):return io.StringIO('{"pid":10,"startTimeTicks":23}')
                def read_text(self):
                    observations.append(self.value)
                    if len(observations)>2 and not reused:raise FileNotFoundError(self.value)
                    ticks=24 if len(observations)>2 else 23
                    return '10 (python3) '+' '.join(['S']+['0']*18+[str(ticks)])
            with patch('pathlib.Path',MockPath),patch('time.sleep',lambda seconds:sleeps.append(seconds)),patch('sys.argv',['waiter','/tmp/mock-marker']):
                exec(compile(t.WAITER,'mock_waiter','exec'),{})
            self.assertEqual(len(observations),3)
            self.assertEqual(sleeps,[0.01,0.01])

    def test_pid1_marker_protocol_and_frozen_commands_compile(self):
        compile(t.WAITER,'waiter','exec');compile(t.MARKER_WRITER,'marker_writer','exec')
        for name in ('BUILD','PROGRAM','EDIT','ENVIRONMENT','PREFIX','ORACLE'):
            self.assertEqual(getattr(t,name),getattr(b,name))
        self.assertIn("while identity(pid) == ticks",t.WAITER)
        self.assertIn("os.replace(temporary, marker)",t.MARKER_WRITER)
        source=Path(t.__file__).read_text()
        for forbidden in ('os.kill(','.terminate(','.kill(',"['kill'",'"--force"','"--privileged"'):
            self.assertNotIn(forbidden,source)


if __name__=='__main__':
    unittest.main(verbosity=2)
