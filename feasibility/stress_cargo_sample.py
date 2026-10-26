#!/usr/bin/env python3
"""New17-package Cargo DAG; reuse frozen generation transport without altering it."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback
from cargo_transport_sample import CargoTransportSample, transport_report
from cargo_sample import fixture_inventory, ORACLE
from cas_sample import Parser, require, HEX64
from stress_cargo_prepare import PROTOCOL, PROTOCOL_SHA, validate_manifest
from stress_cargo_pressure import SPEC as PRESSURE_SPEC, validate_report as validate_pressure_report


def stress_report():
    report=transport_report()
    report.update(workload="stress-cargo-dag16-v2", protocol="sprig-stress-cargo-protocol-v2",
                  packages=PROTOCOL["packages"], protocolSha256=PROTOCOL_SHA,
                  artifactChecks=[], testOnly=False)
    report["measurementNotes"]=[n for n in report["measurementNotes"] if "tiny dependency-free" not in n]
    report["measurementNotes"].extend([
        "New16-library+application local dependency DAG with real generated build-script output; frozen Cargo reports are not rewritten.",
        "Exactly17packages must compile on clean/edit and be Fresh on noop/restored; wrong or duplicate package observations fail.",
        "Target hardlink/symlink/mode/exact-nanosecond-mtime probes and generated build artifacts stay in the full checkpoint oracle.",
        "All additional toolchain/probe/artifact verification runs are charged; complete logs copied only after space and normal cleanup.",
    ])
    return report


def build_observation(stderr,purpose):
    fresh=[];compiling=[]
    for line in stderr.splitlines():
        match=re.fullmatch(r"\s*(Fresh|Compiling) ([a-z0-9-]+) v0\.1\.0(?: \(.*\))?",line)
        if match:
            (fresh if match[1]=="Fresh" else compiling).append(match[2])
        elif re.match(r"\s*(Fresh|Compiling)\s",line):
            raise ValueError("unexpected Cargo package/version line: "+line)
    expected=PROTOCOL["packages"]
    seen=fresh if purpose in ("noop_build","restored_rebuild") else compiling
    other=compiling if purpose in ("noop_build","restored_rebuild") else fresh
    require(len(seen)==17 and set(seen)==set(expected) and not other,
            "Cargo package cache/build acceptance failed",purpose=purpose,fresh=fresh,compiling=compiling)
    return {"freshPackages":fresh,"compilingPackages":compiling,"allPackagesVerified":True}


class StressCargoSample(CargoTransportSample):
    def __init__(self,report):
        super().__init__(report)
        self.pending_command_logs=[]
        self.pressure_profile='ordinary'

    def flush_command_logs(self):
        if not self.logs:
            return
        for row in self.pending_command_logs:
            stem="command-%06d"%row["sequence"]
            (self.logs/(stem+".stdout")).write_text(row["stdout"])
            (self.logs/(stem+".stderr")).write_text(row["stderr"])
        self.pending_command_logs.clear()

    def command(self,arguments,*,cwd=None,record_event=True):
        # Frozen command transport discards successful stderr. This new protocol
        # preserves it; the operation, error handling and external timers remain.
        args=[str(value) for value in arguments]
        self.sequence+=1
        proc=subprocess.run(args,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                            text=True,encoding="utf-8",errors="replace",check=False)
        self.pending_command_logs.append({"sequence":self.sequence,"argv":args,
                                          "stdout":proc.stdout,"stderr":proc.stderr,"returncode":proc.returncode})
        # The inherited space sampler passes record_event=False from sync
        # through its last raw query. Keep those logs in memory until a later
        # command, so diagnostic writes cannot dirty the accounting interval.
        if record_event:
            self.flush_command_logs()
            self.event("command_finished",sequence=self.sequence,executable=args[0],
                       operation=args[1] if len(args)>1 else None,returncode=proc.returncode,
                       stdoutBytes=len(proc.stdout.encode()),stderrBytes=len(proc.stderr.encode()))
        require(proc.returncode==0,"command failed; no automatic retry",argv=args,
                returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr)
        return proc.stdout

    def prepare(self,args):
        for key in ("DOCKER_HOST","DOCKER_CONTEXT","DOCKER_TLS_VERIFY","DOCKER_CERT_PATH","DOCKER_TLS","SPRIG_LIFECYCLE_TRACE"):
            require(not os.environ.get(key), "unexpected inherited routing/diagnostic setting",variable=key)
        self.pressure_profile=getattr(args,'pressure_profile','ordinary')
        require(self.pressure_profile in ('ordinary',PRESSURE_SPEC['profile']),'unknown pressure profile')
        if self.pressure_profile!='ordinary':
            self.pressure_source=Path(__file__).with_name('stress_cargo_pressure.py').read_bytes()
            self.report['normalPressureScriptSha256']=hashlib.sha256(self.pressure_source).hexdigest()
            require(self.report['normalPressureScriptSha256']==args.pressure_script_sha256,'pressure source identity mismatch')
        else:
            require(not getattr(args,'pressure_script_sha256',None),'ordinary profile cannot claim pressure identity')
        self.manifest=validate_manifest(json.loads(Path(args.manifest).read_text()))
        super().prepare(args)
        self.flush_command_logs()
        require(self.fixture==self.manifest["initial"],"frozen oracle differs from DAG manifest")
        require(hashlib.sha256((self.source/"Cargo.lock").read_bytes()).hexdigest()==self.manifest["lockfileSha256"],"lockfile identity mismatch")
        self.report["dagManifest"]={k:v for k,v in self.manifest.items() if k!="initial"}
        self.report["binarySha256"]=hashlib.sha256(self.binary.read_bytes()).hexdigest()

    def verify_toolchain(self,tree):
        output=self.runtime(tree,"rustc -Vv; cargo -V",purpose="toolchain_verify")
        require(re.search(r"^rustc 1\.90\.0 ",output,re.M) and re.search(r"^cargo 1\.90\.0 ",output,re.M),"compiler image is not pinned Rust/Cargo1.90.0",output=output)
        self.report["compilerVersionOutput"]=output

    def oracle(self,view,*,expected=None,purpose,readonly=False):
        # Match the new LayerFS protocol: a short snapshot command plus exact
        # host comparison. Never place an unbounded target oracle in argv.
        output=self.runtime(view,"python3 -B "+ORACLE+" snapshot /work",
                            purpose=purpose,readonly=readonly)
        actual=json.loads(output)
        require(actual.get("schema")=="cargo-full-tree-v1" and isinstance(actual.get("entries"),list)
                and isinstance(actual.get("hardlink_groups"),list),"invalid full-tree snapshot")
        if expected is not None:
            require(actual==expected,"complete restored/source oracle mismatch",purpose=purpose)
            return {"ok":True,"entries":len(actual["entries"])}
        return actual

    def build(self,tree,purpose):
        self.runtime(tree,PROTOCOL["commands"]["build"],purpose=purpose)
        row=self.report["commands"][-1]
        observed=build_observation(row["stderr"],purpose)
        self.report.setdefault("cargoBuildObservations",[]).append({
            "phase":purpose,**observed,"freshLines":[x for x in row["stderr"].splitlines() if "Fresh " in x],
            "compilingLines":[x for x in row["stderr"].splitlines() if "Compiling " in x],
            "stdoutPath":row["stdoutPath"],"stderrPath":row["stderrPath"],"returncode":row["returncode"]})

    def program(self,tree,expected,purpose):
        wanted=self.manifest["expectedStdoutBefore" if expected=="before" else "expectedStdoutAfter"]
        output=self.runtime(tree,PROTOCOL["commands"]["program"],purpose=purpose)
        require(output==wanted,"DAG program output mismatch",expected=wanted,actual=output)

    def artifacts(self,tree,state,purpose):
        output=self.runtime(tree,PROTOCOL["commands"]["verifyBefore" if state=="before" else "verifyAfter"],purpose=purpose)
        data=json.loads(output)
        require(data.get("ok") is True and data.get("hardlinkProbe") is True and data.get("exactMtime") is True
                and data.get("buildValue")== (1 if state=="before" else 2) and data.get("generatedFiles"),"build artifact acceptance failed",result=data)
        self.report["artifactChecks"].append({"phase":purpose,**data})

    def normal_pressure(self,tree):
        raw=self.runtime(tree,'python3 -B - /work',input_data=self.pressure_source.decode(),purpose='normal_pressure')
        pressure=validate_pressure_report(json.loads(raw))
        self.report['normalPressure']=pressure
        self.report['normalPressureRawSha256']=hashlib.sha256(raw.encode()).hexdigest()

    def preserve_logs(self):
        self.flush_command_logs()
        super().preserve_logs()
        if not self.root or not self.records:
            return
        archive=Path(str(self.records)+".logs")
        archive.mkdir()
        files=sorted(set(self.logs.glob("*"))|set((self.library/"native").glob("*/writable-*.log")))
        rows=[]
        for index,source in enumerate(files):
            require(source.is_file() and not source.is_symlink(),"unsafe diagnostic log path",path=str(source))
            target=archive/("%06d-"%index+source.name)
            shutil.copyfile(source,target)
            body=target.read_bytes()
            rows.append({"source":str(source),"archived":str(target),"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()})
        self.report["completeLogArchive"]=rows

    def execute(self):
        self.timed("init", lambda: self.cli("init"))
        def do_import():
            fixture_inventory(self.source, self.fixture)
            return self.created_view(self.cli("import", self.source, "main", creation=True))
        main = self.timed("import", do_import); self.views.append(main)
        initial = main["base_revision"]; require(HEX64.fullmatch(initial), "invalid import revision")
        self.report["initialHead"] = initial
        first = self.timed("fork", lambda: self.created_view(self.cli("fork", "main", "work", creation=self.backend == "writable")))
        self.views.append(first)
        self.timed("fixture_verify", lambda: self.oracle(first["merged"], expected=self.fixture, purpose="fixture_verify"))
        self.timed("cargo_setup", lambda: self.runtime(first["merged"],
            'test ! -e target; test ! -e .cargo-home; test ! -e .tmp; mkdir "$CARGO_HOME" "$TMPDIR"', purpose="cargo_setup"))
        self.timed("toolchain_verify", lambda: self.verify_toolchain(first["merged"]))
        self.timed("clean_build", lambda: self.build(first["merged"], "clean_build"))
        self.timed("target_probe", lambda: self.runtime(first["merged"], PROTOCOL["commands"]["probe"], purpose="target_probe"))
        self.timed("clean_artifacts", lambda: self.artifacts(first["merged"], "before", "clean_artifacts"))
        self.timed("clean_execute", lambda: self.program(first["merged"], "before", "clean_execute"))
        self.timed("noop_build", lambda: self.build(first["merged"], "noop_build"))
        self.timed("noop_artifacts", lambda: self.artifacts(first["merged"], "before", "noop_artifacts"))
        self.timed("noop_execute", lambda: self.program(first["merged"], "before", "noop_execute"))
        self.timed("edit", lambda: self.runtime(first["merged"], PROTOCOL["commands"]["edit"], purpose="edit"))
        self.timed("edit_build", lambda: self.build(first["merged"], "edit_build"))
        self.timed("edit_artifacts", lambda: self.artifacts(first["merged"], "after", "edit_artifacts"))
        self.timed("edit_execute", lambda: self.program(first["merged"], "after", "edit_execute"))
        if getattr(self,'pressure_profile','ordinary')!='ordinary':
            self.timed('normal_pressure',lambda:self.normal_pressure(first['merged']))
        self.require_session_inventory()
        expected = self.timed("pre_checkpoint_oracle", lambda: self.oracle(first["merged"], purpose="pre_checkpoint_oracle"))
        self.report["checkpointTreeOracle"] = expected
        first = self.checkpoint_work(first, initial)
        revision = self.report["checkpoint"]["revision"]
        self.restore_started = time.perf_counter()
        second = self.timed("restore", lambda: self.created_view(self.cli("restore", revision, "second", creation=True)))
        self.views.append(second)
        require(second["base_revision"] == revision, "restore returned wrong checkpoint")
        self.timed("restore_verify", lambda: self.oracle(second["merged"], expected=expected, purpose="restore_verify"))
        self.report["fullRestoredTreeVerified"] = True
        self.timed("restored_artifacts", lambda: self.artifacts(second["merged"], "after", "restored_artifacts"))
        self.timed("restored_execute", lambda: self.program(second["merged"], "after", "restored_execute"))
        self.timed("restored_rebuild", lambda: self.build(second["merged"], "restored_rebuild"))
        self.timed("restored_rebuild_artifacts", lambda: self.artifacts(second["merged"], "after", "restored_rebuild_artifacts"))
        self.timed("restored_rebuild_execute", lambda: self.program(second["merged"], "after", "restored_rebuild_execute"))
        def verify_inputs():
            self.oracle(main["merged"], expected=self.fixture, purpose="main_unchanged")
            self.oracle(self.source, expected=self.fixture, purpose="source_unchanged", readonly=True)
        self.timed("retained_input_verify", verify_inputs)
        listing = self.cli("list")
        require(listing["branches"]["main"] == initial and listing["branches"]["work"] == revision
                and listing["branches"]["second"] == revision, "unexpected branch heads after Cargo lifecycle")
        self.report.update({"originalMainViewUnchanged": True, "sourceUnchanged": True,
                            "restoredRevision": revision, "allAcknowledgedIdsPresent": True})
        self.compiler_session_at_space()
        self.timed("space", self.sample_space)
        self.report["ok"] = True


def main():
    report = stress_report(); sample = StressCargoSample(report)
    started = time.perf_counter()
    try:
        parser = Parser(description=__doc__)
        sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        run = sub.add_parser("run")
        for name in ("root", "source", "oracle", "binary", "image", "manifest"):
            run.add_argument("--" + name, required=True)
        run.add_argument("--backend", required=True, choices=["native", "projection", "writable"])
        run.add_argument("--incremental", required=True, type=int, choices=[0, 1])
        run.add_argument("--records")
        run.add_argument("--pressure-profile",choices=["ordinary",PRESSURE_SPEC["profile"]],default="ordinary")
        run.add_argument("--pressure-script-sha256")
        run.add_argument("--production-sha", required=True)
        args = parser.parse_args()
        sample.timed("preflight", lambda: sample.prepare(args))
        sample.execute()
    except SystemExit as error:
        if error.code == 0:
            return 0
        report["error"] = {"message": str(error)}
    except BaseException as error:
        report["ok"] = False
        report["error"] = {"type": type(error).__name__, "message": str(error),
                           "details": getattr(error, "details", {}), "traceback": traceback.format_exc()}
    finally:
        try:
            sample.cleanup(); sample.preserve_logs()
        except BaseException as error:
            report["ok"] = False
            report.setdefault("cleanupErrors", []).append({"message": str(error)})
        report["full_task_seconds"] = time.perf_counter() - started
    if sample.root:
        try:
            (sample.root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        except BaseException as error:
            report["ok"] = False; report["reportWriteError"] = str(error)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
