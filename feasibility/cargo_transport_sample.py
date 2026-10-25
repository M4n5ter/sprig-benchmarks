#!/usr/bin/env python3
"""Scratch cooperative Docker-exec transport for the unchanged Cargo workload.

No image pull/build, signals, forced removal, capabilities, devices, security or
network flags. Every bound generation is released before product checkpoint.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import uuid

from cargo_sample import (CargoSample, cargo_report, fixture_inventory, ENVIRONMENT,
                          PREFIX, ORACLE, BUILD, PROGRAM, EDIT)
from cas_sample import Parser, SampleError, HEX64, require, inside


# Both processes use Python already required by the frozen full-tree oracle.
# The waiter cannot exit until the one marker-writing exec has itself exited.
WAITER = """import json, pathlib, sys, time
marker = pathlib.Path(sys.argv[1])
def identity(pid):
    try:
        value = pathlib.Path('/proc', str(pid), 'stat').read_text().rpartition(') ')[2].split()
        return int(value[19])
    except (FileNotFoundError, ProcessLookupError):
        return None
while not marker.exists():
    time.sleep(0.05)
with marker.open() as stream:
    value = json.load(stream)
pid, ticks = value['pid'], value['startTimeTicks']
if type(pid) is not int or pid <= 1 or type(ticks) is not int or ticks < 0:
    raise ValueError('invalid cooperative marker identity')
while identity(pid) == ticks:
    time.sleep(0.01)
"""
MARKER_WRITER = """import json, os, pathlib, sys
marker = pathlib.Path(sys.argv[1])
pid = os.getpid()
fields = pathlib.Path('/proc/self/stat').read_text().rpartition(') ')[2].split()
temporary = marker.with_name(marker.name + '.' + str(pid))
with temporary.open('x') as stream:
    json.dump({'pid': pid, 'startTimeTicks': int(fields[19])}, stream)
os.replace(temporary, marker)
"""


def transport_report():
    report = cargo_report()
    report.update({"production_sha": None, "productionShaSource": "required --production-sha supplied by checkout/build harness",
                   "binarySourcePinVerifiedBySampler": False,
                   "transport": "cooperative-generation-container-plus-docker-exec-v1",
                   "transport_seconds": {}, "transportCommands": [], "compilerSessions": [],
                   "transportObservationRevision": "post-marker-missing-pid-resample-v2",
                   "convenience_seconds": {"checkpointCompilerQuiescePlusProduct": None, "restoreToCompilerReady": None},
                   "convenienceBoundaries": {
                       "checkpointCompilerQuiescePlusProduct": "wall time from compiler shutdown start through product checkpoint/readiness completion, including intervening inventory and acknowledgment bookkeeping",
                       "restoreToCompilerReady": "wall time from restore CLI start through first exact-bound restored compiler start/inspection; excludes subsequent full-tree oracle, which must still pass before execution/build"},
                   "compilerContainerBoundaryAtSpace": "exactly the restored-generation compiler container remains live with three product views; all compiler sessions close before product cleanup"})
    report["measurementNotes"] = [note for note in report["measurementNotes"]
                                   if not note.startswith("Every Docker run includes")]
    report["measurementNotes"].extend([
        "A single ordinary compiler container is reused for foreground commands in one bound workspace generation; restored work uses a new container.",
        "PID1 only waits for a unique marker in container-local /tmp, outside /work and the checkpoint oracle.",
        "Before checkpoint and final product cleanup, marker exec is attempted once, its writer exits before PID1, natural PID1 exit is observed, docker wait confirms zero exit, then exact-container docker rm and absence checks complete.",
        "Unknown create/start/exec/exit/removal outcomes fail closed, retain evidence, block product unmount, and are never automatically retried or signaled.",
        "Main/source read-only-purpose oracles use separately charged short-lived cooperative sessions; the source bind remains read-only.",
        "transport_seconds is a diagnostic breakdown overlapping phase_seconds and full_task_seconds, never an amount to subtract from measured phases.",
        "Session start is charged to its first command phase; pre-checkpoint stop and final cleanup have explicit phase fields. Full checkpoint CLI/readiness remains unchanged.",
        "At active-space accounting exactly the restored-generation compiler container remains; its writable layer/logs plus Docker/containerd roots, image and product generations remain charged. Main/source transient sessions have already exited and been removed.",
        "This is a separately labeled revised-transport series, not a direct speedup claim against the earlier per-command docker-run series.",
        "The two convenience_seconds composites cover disjoint checkpoint and restore intervals but overlap their underlying phase/transport fields; never add both accounting layers. Restored compiler-start readiness is not full-tree verification.",
    ])
    return report


class CargoTransportSample(CargoSample):
    def __init__(self, report):
        super().__init__(report)
        self.sessions = {}
        self.transport_sequence = 0

    def prepare(self, args):
        require(re.fullmatch(r"[0-9a-f]{40}", args.production_sha) is not None,
                "--production-sha requires a complete lowercase source commit")
        self.report["production_sha"] = args.production_sha
        super().prepare(args)

    def docker(self, operation, arguments, *, purpose, input_data=None):
        """One exact Docker operation with complete measured-filesystem logs."""
        self.transport_sequence += 1
        name = "transport-%05d" % self.transport_sequence
        argv = ["docker", *arguments]
        started = time.perf_counter()
        row = {"operation": operation, "purpose": purpose, "argv": argv,
               "stdinBytes": len(input_data.encode()) if input_data is not None else 0,
               "stdinSha256": hashlib.sha256(input_data.encode()).hexdigest() if input_data is not None else None}
        self.report["transportCommands"].append(row)
        try:
            result = subprocess.run(argv, input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", check=False)
            out, err = self.logs / (name + ".stdout"), self.logs / (name + ".stderr")
            out.write_text(result.stdout); err.write_text(result.stderr)
            row.update({"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
                        "stdoutPath": str(out), "stderrPath": str(err)})
            require(result.returncode == 0, "Docker operation failed; no retry and outcome may be uncertain", command=row)
            return result.stdout, row
        except BaseException as error:
            row["error"] = str(error)
            raise
        finally:
            seconds = time.perf_counter() - started
            row["seconds"] = seconds
            totals = self.report["transport_seconds"]
            totals[operation] = totals.get(operation, 0.0) + seconds

    @staticmethod
    def pid_identity(pid):
        try:
            fields = (Path("/proc") / str(pid) / "stat").read_text().rpartition(") ")[2].split()
            return {"pid": pid, "startTimeTicks": int(fields[19])}
        except (FileNotFoundError, ProcessLookupError):
            return None

    def inspect_session(self, session, *, running, purpose):
        output, _ = self.docker("inspect", ["inspect", session["id"]], purpose=purpose)
        values = json.loads(output)
        require(len(values) == 1, "unexpected exact-container inspection", container=session["id"])
        value = values[0]
        labels = value.get("Config", {}).get("Labels") or {}
        mounts = value.get("Mounts", [])
        config = value.get("HostConfig", {})
        require(value["Id"] == session["id"] and value["Name"] == "/" + session["name"]
                and value["Image"] == self.image
                and labels.get("sprig.cargo.sample") == self.label
                and labels.get("sprig.cargo.session") == session["token"]
                and labels.get("sprig.cargo.generation") == session["generation"],
                "container identity/image/label mismatch", inspect=value)
        require(len(mounts) == 1 and mounts[0]["Type"] == "bind"
                and mounts[0]["Source"] == session["tree"] and mounts[0]["Destination"] == "/work"
                and mounts[0]["RW"] is (not session["readonly"]),
                "container binding differs from exact workspace generation", inspect=value)
        require(not config.get("Privileged") and not config.get("CapAdd") and not config.get("Devices")
                and not config.get("SecurityOpt") and config.get("RestartPolicy", {}).get("Name", "no") in ("", "no")
                and value.get("RestartCount", 0) == 0,
                "unexpected privileged/security/restart container configuration", inspect=value)
        state = value["State"]
        if running is True:
            require(state.get("Running") is True and state.get("Status") == "running" and state.get("Pid", 0) > 0,
                    "expected running cooperative container", inspect=value)
        elif running is False:
            require(state.get("Running") is False and state.get("Status") == "exited"
                    and state.get("Pid") == 0 and state.get("ExitCode") == 0,
                    "cooperative container did not naturally exit successfully", inspect=value)
        if "pidIdentity" in session:
            observed = self.pid_identity(session["pidIdentity"]["pid"])
            observation = {"purpose": purpose, "dockerState": dict(state),
                           "expected": dict(session["pidIdentity"]), "observed": observed}
            session.setdefault("pidObservations", []).append(observation)
            require(state.get("StartedAt") == session["startedAt"],
                    "cooperative PID1 start identity changed", inspect=value, pidObservation=observation)
            if state.get("Running"):
                require(state.get("Pid") == session["pidIdentity"]["pid"],
                        "cooperative PID1 Docker PID changed", inspect=value, pidObservation=observation)
                # Docker's running snapshot and /proc are not atomic. Only an
                # acknowledged cooperative shutdown may observe a missing PID
                # while waiting for the next exact-container exited snapshot.
                # A present but different identity is never accepted here.
                if observed is None:
                    require(running is None and purpose == "observe_natural_exit"
                            and session.get("cooperativeMarkerAcknowledged") is True,
                            "cooperative PID1 missing outside acknowledged exit observation",
                            inspect=value, pidObservation=observation)
                    observation["pendingDockerExitObservation"] = True
                else:
                    require(observed == session["pidIdentity"],
                            "cooperative PID1 identity changed", inspect=value, pidObservation=observation)
        log_path = value.get("LogPath", "")
        measured = self.report.get("containingFilesystem", {}).get("mountpoint")
        require(not log_path or (measured and inside(Path(log_path), Path(measured))),
                "compiler container log path escaped measured filesystem", logPath=log_path)
        session["lastInspection"] = {"id": value["Id"], "mounts": mounts, "state": state,
                                     "labels": labels, "image": value["Image"],
                                     "graphDriver": value.get("GraphDriver"), "logPath": log_path}
        return state

    def containers(self):
        output, _ = self.docker("inventory", ["ps", "-aq", "--no-trunc", "--filter",
                                               "label=sprig.cargo.sample=" + self.label], purpose="sample_inventory")
        ids = output.split()
        require(all(HEX64.fullmatch(cid) for cid in ids) and len(ids) == len(set(ids)),
                "invalid container inventory", containers=ids)
        self.report["remainingContainers"] = ids
        return ids

    def require_no_containers(self):
        remaining = self.containers()
        require(not remaining, "compiler container retained; refusing checkpoint/space/product unmount", containers=remaining)

    def require_session_inventory(self):
        expected = {session["id"] for session in self.sessions.values() if not session.get("removed")}
        observed = set(self.containers())
        require(observed == expected, "unexpected compiler container inventory", expected=sorted(expected), actual=sorted(observed))
        for session in self.sessions.values():
            if not session.get("removed"):
                require(not session.get("uncertain") and not session.get("stopAttempted"),
                        "session outcome is uncertain; no reuse", session=session)
                self.inspect_session(session, running=True, purpose="quiescent_inventory")

    def start_session(self, tree, *, readonly, purpose):
        tree = Path(tree)
        require(tree.is_absolute() and not any(char in str(tree) for char in (",", "\n", "\r")), "unsafe bind path")
        key = str(tree)
        existing = self.sessions.get(key)
        require(existing is None, "one session per generation; no automatic restart", tree=key)
        self.container_sequence += 1
        token = uuid.uuid4().hex
        generation = "source-fixture" if tree == self.source else tree.parent.name
        session = {"name": self.label + "-generation-%04d" % self.container_sequence,
                   "token": token, "tree": key, "generation": generation, "readonly": readonly,
                   "firstPurpose": purpose, "stopAttempted": False, "removed": False, "uncertain": False}
        self.sessions[key] = session
        self.report["compilerSessions"].append(session)
        marker = "/tmp/sprig-cargo-exit-" + token
        session["marker"] = marker
        mount = "type=bind,source=" + key + ",target=/work" + (",readonly" if readonly else "")
        argv = ["create", "--pull=never", "--name", session["name"],
                "--label", "sprig.cargo.sample=" + self.label,
                "--label", "sprig.cargo.session=" + token,
                "--label", "sprig.cargo.generation=" + generation,
                "--mount", mount, "--workdir", "/work", "--entrypoint", "python3"]
        for name, value in {**ENVIRONMENT, "CARGO_INCREMENTAL": str(self.incremental)}.items():
            argv.extend(["--env", name + "=" + value])
        argv.extend([self.image, "-B", "-c", WAITER, marker])
        started = time.perf_counter()
        try:
            output, _ = self.docker("create", argv, purpose=purpose)
            cid = output.strip(); require(HEX64.fullmatch(cid), "Docker create did not return exact full ID", output=output)
            session["id"] = cid
            self.docker("start", ["start", cid], purpose=purpose)
            state = self.inspect_session(session, running=True, purpose="session_start")
            identity = self.pid_identity(state["Pid"])
            require(identity is not None, "cooperative PID1 disappeared during start", container=cid)
            session["pidIdentity"], session["startedAt"] = identity, state.get("StartedAt")
            session["startSeconds"] = time.perf_counter() - started
            return session
        except BaseException:
            session["uncertain"] = True
            self.cleanup_blocked = True
            raise

    def close_session(self, session, *, purpose):
        if session.get("removed"):
            return
        require(not session.get("uncertain") and not session.get("stopAttempted"),
                "uncertain or already-attempted session exit; no retry", session=session)
        started = time.perf_counter()
        session["stopAttempted"] = True
        try:
            self.inspect_session(session, running=True, purpose=purpose)
            # One cooperative marker request, outside the product's working tree.
            self.docker("cooperative_marker", ["exec", "--workdir", "/", session["id"],
                                               "python3", "-B", "-c", MARKER_WRITER, session["marker"]], purpose=purpose)
            session["cooperativeMarkerAcknowledged"] = True
            deadline = time.monotonic() + 15
            while True:
                state = self.inspect_session(session, running=None, purpose="observe_natural_exit")
                if not state.get("Running"):
                    break
                require(time.monotonic() < deadline, "cooperative exit not observed; preserve container, no retry", session=session)
                time.sleep(0.02)
            self.inspect_session(session, running=False, purpose="verify_natural_exit")
            output, _ = self.docker("wait_exit", ["wait", session["id"]], purpose=purpose)
            require(output.strip() == "0", "docker wait did not confirm successful natural exit", output=output)
            original = session["pidIdentity"]
            while self.pid_identity(original["pid"]) == original:
                require(time.monotonic() < deadline, "original PID1 still present; preserve container", session=session)
                time.sleep(0.02)
            self.docker("session_logs", ["logs", session["id"]], purpose=purpose)
            self.docker("remove", ["rm", session["id"]], purpose=purpose)
            require(session["id"] not in self.containers(), "removed container remains in exact-label inventory")
            session["removed"] = True
            session["stopPurpose"] = purpose
            session["stopSeconds"] = time.perf_counter() - started
            session["naturalExitAndPidGoneVerified"] = True
        except BaseException:
            session["uncertain"] = True
            self.cleanup_blocked = True
            raise

    def close_all_sessions(self, purpose):
        started = time.perf_counter()
        try:
            for session in reversed(list(self.sessions.values())):
                self.close_session(session, purpose=purpose)
            self.require_no_containers()
        finally:
            self.report["phase_seconds"]["transport_stop_" + purpose] = time.perf_counter() - started

    def runtime(self, tree, script, *, input_data=None, readonly=False, purpose):
        started = time.perf_counter()
        tree = Path(tree)
        session = self.sessions.get(str(tree))
        if session is None:
            session = self.start_session(tree, readonly=readonly, purpose=purpose)
            if purpose == "restore_verify" and hasattr(self, "restore_started"):
                self.report["convenience_seconds"]["restoreToCompilerReady"] = time.perf_counter() - self.restore_started
        require(session["readonly"] == readonly and not session.get("removed")
                and not session.get("uncertain") and not session.get("stopAttempted"),
                "cannot reuse a closed, mismatched or uncertain generation session", session=session)
        try:
            self.inspect_session(session, running=True, purpose="before_" + purpose)
            output, row = self.docker("exec", ["exec", "-i", "--workdir", "/work", session["id"],
                                              "/bin/bash", "-c", PREFIX + script], purpose=purpose, input_data=input_data)
            # Keep the original command record last for inherited Cargo Fresh/Compiling collection.
            command = {**row, "container": session["name"], "containerId": session["id"],
                       "workspaceGeneration": session["generation"], "sessionReused": session["firstPurpose"] != purpose}
            if purpose in ("main_unchanged", "source_unchanged"):
                self.close_session(session, purpose=purpose)
            command["secondsIncludingTransportChecks"] = time.perf_counter() - started
            self.report["commands"].append(command)
            return output
        except BaseException:
            # An unsuccessful exec return may be a transport disconnect, not proof
            # that every compiler child exited. Never terminate PID1 in that case.
            session["uncertain"] = True
            self.cleanup_blocked = True
            raise

    def compiler_session_at_space(self):
        second = next((view for view in self.views if view["name"] == "second"), None)
        require(second is not None and self.report.get("fullRestoredTreeVerified") is True,
                "restored compiler accounting requires the verified second workspace")
        session = self.sessions.get(str(second["merged"]))
        require(session is not None and not session.get("removed") and not session.get("uncertain")
                and not session.get("stopAttempted") and session["generation"] == second["generation"],
                "restored compiler session is not live and correctly generation-bound")
        expected = session["id"]
        require(self.containers() == [expected], "active-space boundary requires exactly the restored compiler container")
        require(all(other is session or other.get("removed") for other in self.sessions.values()),
                "another compiler session still owns a binding")
        self.inspect_session(session, running=True, purpose="active_space_compiler")
        return {"containerId": expected, "generation": session["generation"], "tree": session["tree"],
                "pidIdentity": dict(session["pidIdentity"]), "image": self.image,
                "inspection": json.loads(json.dumps(session["lastInspection"])),
                "count": 1, "boundary": "restored compiler live; main/source transients removed"}

    def retained_snapshot(self):
        active = super().retained_snapshot()
        active["compilerContainer"] = self.compiler_session_at_space()
        return active

    def checkpoint_work(self, first, initial):
        started = time.perf_counter()
        try:
            self.close_all_sessions("before_checkpoint")
            return super().checkpoint_work(first, initial)
        finally:
            self.report["convenience_seconds"]["checkpointCompilerQuiescePlusProduct"] = time.perf_counter() - started

    def cleanup(self):
        if not self.root:
            return
        started = time.perf_counter()
        try:
            self.close_all_sessions("final_cleanup")
        except BaseException as error:
            self.cleanup_blocked = True
            self.report["ok"] = False
            self.report.setdefault("cleanupErrors", []).append({"message": str(error), "details": getattr(error, "details", {})})
        super().cleanup()
        self.report["phase_seconds"]["cleanup"] = time.perf_counter() - started

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
        self.timed("clean_build", lambda: self.build(first["merged"], "clean_build"))
        self.timed("clean_execute", lambda: self.program(first["merged"], "before", "clean_execute"))
        self.timed("noop_build", lambda: self.build(first["merged"], "noop_build"))
        self.timed("noop_execute", lambda: self.program(first["merged"], "before", "noop_execute"))
        self.timed("edit", lambda: self.runtime(first["merged"], EDIT, purpose="edit"))
        self.timed("edit_build", lambda: self.build(first["merged"], "edit_build"))
        self.timed("edit_execute", lambda: self.program(first["merged"], "after", "edit_execute"))
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
        self.timed("restored_execute", lambda: self.program(second["merged"], "after", "restored_execute"))
        self.timed("restored_rebuild", lambda: self.build(second["merged"], "restored_rebuild"))
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
    report = transport_report(); sample = CargoTransportSample(report)
    started = time.perf_counter()
    try:
        parser = Parser(description=__doc__)
        sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        run = sub.add_parser("run")
        for name in ("root", "source", "oracle", "binary", "image"):
            run.add_argument("--" + name, required=True)
        run.add_argument("--backend", required=True, choices=["native", "projection", "writable"])
        run.add_argument("--incremental", required=True, type=int, choices=[0, 1])
        run.add_argument("--records")
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
