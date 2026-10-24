#!/usr/bin/env python3
"""Bounded real Cargo lifecycle through the pinned Sprig CLI and ordinary Docker.

This driver never builds/pulls images, provisions filesystems, changes runtime
security settings, signals processes, or force/lazy-unmounts. Run only in an
approved temporary GitHub runner whose Docker/containerd roots already reside
inside the caller's fresh measured Btrfs filesystem.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import traceback
import uuid

from cas_sample import (HEX64, SAFE_COMPONENT, Parser, SampleError, checked_path,
                        inside, overlaps, mount_table, exact_mount, require)
from current_sample import CurrentSample

PRODUCTION_SHA = "e38225e1e1160e8de90aa911d6f1740bef93bacc"

ORACLE = "/opt/bench/tree_oracle.py"
BUILD = "cargo build --offline --locked --verbose --jobs 1"
PROGRAM = "./target/debug/owned-cargo-check"
EDIT = "printf 'fn main() { println!(\"after\"); }\\n' > src/main.rs"
ENVIRONMENT = {
    "CARGO_HOME": "/work/.cargo-home", "CARGO_TARGET_DIR": "/work/target",
    "TMPDIR": "/work/.tmp", "CARGO_NET_OFFLINE": "true", "LC_ALL": "C", "TZ": "UTC",
}
PREFIX = "unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER; set -eu; "


def cargo_report():
    return {
        "ok": False, "prototype_only": False, "production_sha": PRODUCTION_SHA, "compressionPolicy": "auto (default init)",
        "workload": "cargo-clean-noop-edit-checkpoint-restore-rebuild-v1",
        "complete_sprig_semantics": False, "workload_only_verification": True,
        "phase_seconds": {}, "commands": [], "checkpoint": None,
        "full_task_seconds": None,
        "activeSpace": {"filesystemUsedBytes": None, "usageRaw": None, "groupsRaw": None},
        "lifecycle": {"fileTreesRetained": True, "normalUnmountOnly": True,
                      "persistentControlDaemon": False, "activeAtSpace": None,
                      "daemons": [], "cleanup": {"attempts": [], "complete": False}},
        "remainingMounts": [], "remainingContainers": [],
        "measurementNotes": [
            "Separate tiny dependency-free Cargo workload; not one of the frozen history100 recipes.",
            "One immutable supplied image, fixed toolchain and --jobs 1; no image pull or build in this driver.",
            "Default-root ordinary compiler containers have no added capabilities/devices or network/security flags.",
            "Every Docker run includes create, start, command, exit and --rm cleanup; inventory checks and raw log capture remain in that phase.",
            "Cargo home, target, incremental caches and TMPDIR are within the actual /work tree; no target/cache cleanup or exclusion.",
            "All raw command logs and full-tree manifests stay outside workspace trees but inside the measured Btrfs root.",
            "Checkpoint sums CLI and authoritative readiness phases; its immediate raw acknowledgment ledger is outside those phases but inside full-task wall time.",
            "Full-tree oracle checks types, ordinary modes, exact mtimes, file bytes, symlink targets and internal hardlink groups before any restored build.",
            "Source and imported main are checked unchanged; main, work and restored second remain live at final physical accounting.",
            "Writable checkpoint retains its old journal generation: four generations and three live views at final space.",
            "Full-task wall time includes preparation, all oracles, command transport, physical accounting and final normal cleanup.",
            "Whole-filesystem Used includes Data, Metadata and System, all store/runtime state and retained generations; parent owns runtime-ready baseline.",
            "Cargo cache behavior comes from actual verbose outputs; restored paths do not imply a Fresh build or equal durability.",
            "Harness never signals processes or uses force/lazy unmount; product-internal startup-failure behavior is not claimed absent.",
        ],
    }


def fixture_inventory(source, oracle):
    """Validate helper fixture metadata without changing or normalizing it."""
    require(isinstance(oracle, dict) and oracle.get("schema") == "cargo-full-tree-v1",
            "expected full-tree fixture oracle")
    rows = oracle.get("entries")
    require(isinstance(rows, list) and rows, "fixture oracle entries missing")
    expected = {row["path"]: row for row in rows}
    require(len(expected) == len(rows) and "." in expected, "duplicate or missing fixture paths")
    require(not any(inside(Path(m["mountpoint"]), source) for m in mount_table()), "fixture contains a mount")
    found, todo, device = {}, [source], source.stat().st_dev
    while todo:
        path = todo.pop()
        info = path.lstat()
        name = "." if path == source else path.relative_to(source).as_posix()
        require(info.st_dev == device and name in expected, "unexpected fixture path or filesystem", path=name)
        row = expected[name]
        require(stat.S_IMODE(info.st_mode) == row["mode"] and info.st_mtime_ns == row["mtime_ns"],
                "fixture metadata differs from full oracle", path=name)
        if stat.S_ISDIR(info.st_mode):
            require(row["type"] == "directory", "fixture type mismatch", path=name)
            todo.extend(path.iterdir())
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and row["type"] == "file",
                    "fixture must contain only unlinked regular files/directories", path=name)
            require(info.st_size == row["size"] and HEX64.fullmatch(row["sha256"]), "fixture size/hash format mismatch", path=name)
        found[name] = True
    require(set(found) == set(expected), "missing fixture paths")
    require(oracle.get("hardlink_groups") == [[name] for name in sorted(expected) if expected[name]["type"] == "file"],
            "fixture hardlinks differ from declared standalone helper")


class CargoSample(CurrentSample):
    def prepare(self, args):
        self.backend = args.backend
        self.incremental = args.incremental
        self.image = args.image
        self.attempted_generations = set()
        self.steps = []  # This is not a synthetic history100 workload.
        self.expected_generation_count = 4 if self.backend == "writable" else 3
        self.label = "sprig-cargo-" + uuid.uuid4().hex
        self.container_sequence = 0
        self.report.update({"backend": self.backend, "incremental": self.incremental,
                            "image": self.image, "containerLabel": self.label})
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", self.image), "--image must be an immutable local image ID")
        require(not os.environ.get("CARGO_IMAGE") or os.environ["CARGO_IMAGE"] == self.image,
                "--image differs from supplied CARGO_IMAGE")
        require(sys.platform == "linux" and os.geteuid() == 0, "requires root on authorized Linux runner")
        require(os.environ.get("GITHUB_ACTIONS") == "true", "sample is limited to GitHub Actions")
        require(os.environ.get("RUNNER_TEMP") and Path(os.environ["RUNNER_TEMP"]).is_absolute(), "RUNNER_TEMP must be absolute")
        temporary = checked_path(os.environ["RUNNER_TEMP"], directory=True)
        root = checked_path(args.root, new=True)
        require(root != temporary and inside(root, temporary), "root must be strictly below RUNNER_TEMP")
        require(all(SAFE_COMPONENT.fullmatch(part) for part in root.parts[1:]), "unsafe output path")
        self.source = checked_path(args.source, directory=True)
        self.binary = checked_path(args.binary)
        require(os.access(self.binary, os.X_OK), "Sprig binary is not executable")
        oracle_path = checked_path(args.oracle)
        self.fixture = json.loads(oracle_path.read_text())
        inputs = [self.source, self.binary, oracle_path]
        require(all(not overlaps(root, path) for path in inputs), "input/output paths overlap")
        require(all(not inside(path, self.source) for path in inputs[1:]), "binary/oracle must be outside fixture")
        records = checked_path(args.records, new=True) if args.records else None
        if records:
            require(inside(records, temporary) and not overlaps(records, root)
                    and all(not overlaps(records, path) for path in inputs), "invalid external records path")
        mounts = mount_table()
        require(not any(inside(Path(m["mountpoint"]), root) for m in mounts), "output root overlaps existing mount")
        for executable in ("bash", "docker", "stat", "btrfs"):
            require(shutil.which(executable), "required command unavailable", executable=executable)
        require(self.command(["stat", "-f", "-c", "%T", root.parent]).strip() == "btrfs", "root parent must already be Btrfs")
        backing = sorted((m for m in mounts if inside(root.parent, Path(m["mountpoint"]))),
                         key=lambda m: len(Path(m["mountpoint"]).parts), reverse=True)
        require(backing and backing[0]["filesystem"] == "btrfs"
                and inside(Path(backing[0]["mountpoint"]), temporary), "measured Btrfs mount must be under RUNNER_TEMP")
        measured_mount = Path(backing[0]["mountpoint"])
        measured_device = root.parent.stat().st_dev
        require(not inside(self.source, measured_mount) and self.source.stat().st_dev != measured_device,
                "fixture must be external to measured filesystem")
        if records:
            require(not inside(records, measured_mount) and records.parent.stat().st_dev != measured_device,
                    "external ledger must be outside measured filesystem")
        root.mkdir(mode=0o700)
        self.root, self.library, self.logs = root, root / "library", root / "logs"
        self.logs.mkdir(mode=0o700)
        self.records = records or root / "steps.jsonl"
        with self.records.open("x") as ledger:
            os.fchmod(ledger.fileno(), 0o644)
        fixture_inventory(self.source, self.fixture)
        image_info = json.loads(self.command(["docker", "image", "inspect", self.image]))
        require(len(image_info) == 1 and image_info[0]["Id"] == self.image, "local immutable image not found")
        require(image_info[0].get("Config", {}).get("User", "") in ("", "0", "root", "0:0", "root:root"),
                "supplied image must use ordinary default root")
        info = json.loads(self.command(["docker", "info", "--format", "{{json .}}"])); docker_root = Path(info["DockerRootDir"])
        require(docker_root.is_absolute() and inside(docker_root, measured_mount)
                and docker_root.stat().st_dev == measured_device, "Docker persistent root escaped measured filesystem")
        self.report.update({"root": str(root), "source": str(self.source), "binary": str(self.binary),
                            "recordsFile": str(self.records), "recordsIncludedInActiveSpace": records is None,
                            "containingFilesystem": backing[0], "imageInspect": image_info[0],
                            "dockerInfo": info, "fixtureOracle": self.fixture})
        self.event("cargo_sample_prepared", root=str(root), image=self.image, label=self.label)

    def timed(self, name, operation):
        start = time.perf_counter()
        try:
            return operation()
        finally:
            self.report["phase_seconds"][name] = time.perf_counter() - start

    def containers(self):
        output = self.command(["docker", "ps", "-aq", "--filter", "label=sprig.cargo.sample=" + self.label])
        return output.split()

    def require_no_containers(self):
        remaining = self.containers()
        self.report["remainingContainers"] = remaining
        require(not remaining, "sample container retained; no signal, forced removal or unmount", containers=remaining)

    def runtime(self, tree, script, *, input_data=None, readonly=False, purpose):
        """Single ordinary container; preserve complete stdout/stderr in measured logs."""
        self.container_sequence += 1
        name = self.label + "-%04d" % self.container_sequence
        tree = Path(tree)
        require(tree.is_absolute() and not any(c in str(tree) for c in (",", "\n", "\r")), "unsafe Docker bind path")
        mount = "type=bind,source=" + str(tree) + ",target=/work" + (",readonly" if readonly else "")
        argv = ["docker", "run", "--rm", "--pull=never", "-i", "--name", name,
                "--label", "sprig.cargo.sample=" + self.label, "--mount", mount,
                "--workdir", "/work", "--entrypoint", "/bin/bash"]
        for key, value in {**ENVIRONMENT, "CARGO_INCREMENTAL": str(self.incremental)}.items():
            argv.extend(["--env", key + "=" + value])
        argv.extend([self.image, "-c", PREFIX + script])
        start = time.perf_counter()
        result = subprocess.run(argv, input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace", check=False)
        stdout_path = self.logs / (name + ".stdout")
        stderr_path = self.logs / (name + ".stderr")
        stdout_path.write_text(result.stdout); stderr_path.write_text(result.stderr)
        row = {"purpose": purpose, "container": name, "argv": argv, "returncode": result.returncode,
               "stdout": result.stdout, "stderr": result.stderr,
               "stdoutPath": str(stdout_path), "stderrPath": str(stderr_path),
               "stdinBytes": len(input_data.encode()) if input_data is not None else 0,
               "stdinSha256": hashlib.sha256(input_data.encode()).hexdigest() if input_data is not None else None}
        self.report["commands"].append(row)
        self.require_no_containers()
        row["secondsIncludingCleanup"] = time.perf_counter() - start
        self.event("cargo_container_finished", name=name, purpose=purpose, returncode=result.returncode)
        require(result.returncode == 0, "container command failed; no automatic retry", command=row)
        return result.stdout

    def oracle(self, view, *, expected=None, purpose, readonly=False):
        output = self.runtime(view, "python3 -B " + ORACLE + (" snapshot /work" if expected is None else " verify /work"),
                              input_data=None if expected is None else json.dumps(expected, separators=(",", ":")) + "\n",
                              purpose=purpose, readonly=readonly)
        result = json.loads(output)
        if expected is None:
            require(result.get("schema") == "cargo-full-tree-v1" and isinstance(result.get("entries"), list)
                    and isinstance(result.get("hardlink_groups"), list), "unexpected snapshot oracle schema")
        else:
            require(result.get("ok") is True, "full-tree oracle did not verify", oracle=result)
        return result

    def build(self, tree, purpose):
        self.runtime(tree, BUILD, purpose=purpose)
        row = self.report["commands"][-1]
        self.report.setdefault("cargoBuildObservations", []).append({
            "phase": purpose, "freshLines": [line for line in row["stderr"].splitlines() if "Fresh " in line],
            "compilingLines": [line for line in row["stderr"].splitlines() if "Compiling " in line],
            "stdoutPath": row["stdoutPath"], "stderrPath": row["stderrPath"], "returncode": row["returncode"],
        })

    def program(self, tree, expected, purpose):
        output = self.runtime(tree, PROGRAM, purpose=purpose)
        require(output == expected + "\n", "program output mismatch", expected=expected + "\n", actual=output)

    def checkpoint_work(self, first, initial):
        self.require_no_containers()
        start = time.perf_counter()
        checkpoint = self.cli("checkpoint", "work", "--expected-head", initial, "--message", "Cargo edit and complete build tree")
        cli_seconds = time.perf_counter() - start
        self.report["checkpoint"] = checkpoint
        self.step_record({"event": "cargo_checkpoint_response", "checkpoint": checkpoint, "checkpoint_cli_seconds": cli_seconds})
        start = time.perf_counter()
        require(checkpoint["committed"] is True and checkpoint["branch"] == "work"
                and checkpoint["previous_head"] == initial and HEX64.fullmatch(checkpoint["revision"])
                and checkpoint["revision"] != initial, "invalid acknowledged Cargo checkpoint", checkpoint=checkpoint)
        require(not checkpoint.get("mount_error"), "checkpoint remount failed; no retry", checkpoint=checkpoint)
        # Current owned CLI already remounts. Never retry a lost or failed server.
        fresh = self.view(self.cli("show", "work"))
        require(fresh["base_revision"] == checkpoint["revision"], "show differs from acknowledged checkpoint")
        if self.backend == "writable":
            require(fresh["generation"] != first["generation"] and exact_mount(first["merged"]) is None,
                    "owned checkpoint did not normally replace old generation")
        else:
            require(fresh["generation"] == first["generation"], "unexpected native/projection generation replacement")
        self.views[self.views.index(first)] = fresh
        ready_seconds = time.perf_counter() - start
        self.report["phase_seconds"].update({"checkpoint_cli": cli_seconds, "checkpoint_readiness": ready_seconds,
                                             "checkpoint": cli_seconds + ready_seconds})
        self.report["checkpointGeneration"] = {"before": first["generation"], "after": fresh["generation"],
                                               "pathAfter": str(fresh["merged"])}
        return fresh

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
        self.require_no_containers()
        expected = self.timed("pre_checkpoint_oracle", lambda: self.oracle(first["merged"], purpose="pre_checkpoint_oracle"))
        self.report["checkpointTreeOracle"] = expected
        first = self.checkpoint_work(first, initial)
        revision = self.report["checkpoint"]["revision"]
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
        self.require_no_containers()
        self.timed("space", self.sample_space)
        self.report["ok"] = True

    def cleanup(self):
        if not self.root:
            return
        start = time.perf_counter()
        try:
            # A leftover container may retain a bind to a product generation.
            self.require_no_containers()
        except BaseException as error:
            self.cleanup_blocked = True
            self.report["ok"] = False
            self.report.setdefault("cleanupErrors", []).append({"message": str(error), "details": getattr(error, "details", {})})
        super().cleanup()
        self.report["phase_seconds"]["cleanup"] = time.perf_counter() - start

    def retained_snapshot(self):
        views, daemons, expected_mounts = [], [], set()
        require(len(self.views) == 3 and {view["name"] for view in self.views} == {"main", "work", "second"}
                and len({view["merged"] for view in self.views}) == 3
                and len({view["generation"] for view in self.views}) == 3,
                "expected three distinct production workspaces")
        servers = self.processes()
        for view in self.views:
            current = self.view(self.cli("show", view["name"]))
            require(current["merged"] == view["merged"], "active workspace path was not refreshed")
            record = {"name": view["name"], "path": str(view["merged"]), "generation": view["generation"],
                      "backend": current["workspace"]["backend"], "base_revision": current["base_revision"]}
            if self.backend != "native":
                matching = [server for server in servers if server["generation"] == view["generation"]
                            and server["backend"] == self.backend
                            and server["revision"] == current["workspace"]["backend"]["revision"]]
                require(len(matching) == 1, "expected exactly one correctly bound FUSE server for each view")
            if self.backend == "projection":
                generation = view["merged"].parent
                lower = generation / "lower"
                mounted, lower_mount = exact_mount(view["merged"]), exact_mount(lower)
                require(mounted and mounted["filesystem"] == "overlay"
                        and mounted["superOptions"].get("lowerdir") == str(lower)
                        and mounted["superOptions"].get("upperdir") == str(generation / "upper")
                        and mounted["superOptions"].get("workdir") == str(generation / "work")
                        and lower_mount and lower_mount["filesystem"] == "fuse"
                        and lower_mount["source"] == "sprig-cas" and lower_mount["root"] == "/"
                        and "ro" in lower_mount["mountOptions"]
                        and lower_mount["superOptions"].get("user_id") == "0"
                        and "allow_other" not in lower_mount["superOptions"],
                        "production projection has unexpected mount binding")
                expected_mounts.update((str(view["merged"]), str(lower)))
                record["mountInfo"] = mounted
                daemons.append({**matching[0], "name": view["name"], "lower": str(lower), "mountInfo": lower_mount})
            elif self.backend == "writable":
                mounted = exact_mount(view["merged"])
                revision = current["workspace"]["backend"]["revision"]
                require(mounted and mounted["filesystem"] == "fuse" and mounted["root"] == "/"
                        and mounted["source"] == "sprig-writable-cas:" + view["generation"] + ":" + revision
                        and {"rw", "nosuid", "nodev", "noatime"}.issubset(mounted["mountOptions"])
                        and mounted["superOptions"].get("user_id") == "0"
                        and mounted["superOptions"].get("group_id") == "0"
                        and "default_permissions" in mounted["superOptions"]
                        and not any(option in mounted["mountOptions"] or option in mounted["superOptions"]
                                    for option in ("allow_other", "allow_root")),
                        "production writable view has unexpected mount binding")
                expected_mounts.add(str(view["merged"]))
                record["mountInfo"] = mounted
                daemons.append({**matching[0], "name": view["name"], "tree": str(view["merged"]), "mountInfo": mounted})
            else:
                require(exact_mount(view["merged"]) is None, "native workspace unexpectedly mounted")
            views.append(record)
        require(len(servers) == len(daemons) and
                (self.backend == "native" or {server["generation"] for server in servers}
                 == {view["generation"] for view in self.views}),
                "unaccounted or duplicate production FUSE server")
        observed_mounts = {mount["mountpoint"] for mount in mount_table()
                           if inside(Path(mount["mountpoint"]), self.library)}
        require(observed_mounts == expected_mounts, "unaccounted mounted product generation")
        retained = {}
        for kind, pin_name in (("projection", "projection-base"), ("writable", "writable-base")):
            retained[kind] = [pin.parent.name for pin in sorted((self.library / "native").glob("*/" + pin_name))]
        if self.backend == "writable":
            require(len(retained["writable"]) == self.expected_generation_count,
                    "Cargo writable checkpoint generations were not all retained", generations=retained)
        directories = sorted(path.name for path in (self.library / "native").iterdir() if path.is_dir())
        require(len(directories) == self.expected_generation_count, "unexpected retained Cargo generation count", generations=directories)
        return {"cargoRestoreReadbackComplete": self.report.get("fullRestoredTreeVerified", False),
                "retainedGenerationCount": len(directories), "generationDirectories": directories,
                "views": views, "foregroundFuseProcesses": daemons,
                "controlProcessesRunning": len(servers),
                "fileTreesRetained": True, "retainedGenerations": retained,
                "allRuntimeLogsAndJournalsInsideMeasuredStore": True}

def main():
    report = cargo_report(); sample = CargoSample(report)
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
