#!/usr/bin/env python3
"""Real Sprig CLI sample on an approved temporary GitHub Btrfs runner.

Uses the unchanged cas_sample.py input, shell, measurement and failure helpers.
No private library calls, manual mounts, force/lazy unmounts or harness process killing.
All product paths, including three active workspaces and server logs, are charged.
The workflow must build the exact PRODUCTION_SHA; the binary does not report Git SHA.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
import traceback

from cas_sample import (HEX64, Parser, Sample, SampleError, checked_path,
                        full_checks, changed_check, write_command, inventory_source,
                        mount_table, exact_mount, inside, new_report, require)

PRODUCTION_SHA = "17130154de38f3c30be6eae620ad0c0b6d404d48"


def production_report():
    report = new_report()
    report.update({"prototype_only": False, "production_sha": PRODUCTION_SHA,
                   "complete_sprig_semantics": False, "workload_only_verification": True,
                   "initializationIncludedInImport": False, "init_seconds": None,
                   "metadata_branch_available": True, "metadata_branch_probe": "omitted",
                   "metadata_branch_unavailable_reason": None})
    report["measurementNotes"] = [
        "Real production CLI; workflow checkout/build must enforce the reported source pin.",
        "Initialization is timed separately; preparation headline adds init to import+fork+read.",
        "Import includes safety inventory and the product-created main workspace with its server if projected.",
        "Each fork is the complete product CLI operation; three independent workspaces remain active at accounting.",
        "Frozen bash SHA/read/dd/fsync/touch commands are unchanged; CLI transport differs from an in-process SDK.",
        "All objects, revisions, native trees or upper/lower generations, state, backups, locks and runtime logs remain charged.",
        "Whole-filesystem Used includes Data, Metadata and System, not reserved capacity; no recursive FUSE du.",
        "Space is sampled after synchronization outside operation timers and before historical restore/readback.",
        "Historical restores and their retained generations occur only after accounting; no store data is deleted.",
        "Full listed-file content oracles do not establish full metadata parity or equal durability.",
        "Harness never signals processes; production startup-failure cleanup may terminate its own child after normal unmount, which the harness cannot count.",
    ]
    return report


class ProductionSample(Sample):
    def prepare(self, args):
        self.backend = args.backend
        self.report["backend"] = self.backend
        super().prepare(args)
        self.attempted_generations = set()

    def cli(self, action, *args, projected=False):
        command = [self.binary, "--store", self.library, "--json"]
        if projected:
            command.append("--projected")
        output = json.loads(self.command([*command, action, *args]))
        require(output.get("schema_version") == 1 and "result" in output and "error" not in output,
                "unexpected production CLI response", output=output)
        return output["result"]

    def view(self, result):
        expected = "projection" if self.backend == "projection" else "native"
        require(result["backend"]["kind"] == expected, "unexpected workspace backend")
        require(result["mount_state"] == ("mounted" if expected == "projection" else "native"),
                "workspace is not usable", workspace=result)
        tree = Path(result["path"])
        require(tree.is_absolute() and tree.parent.parent == self.library / "native"
                and tree.name == "tree", "CLI workspace path escaped managed store", path=str(tree))
        return {"name": result["name"], "merged": tree, "generation": tree.parent.name,
                "base_revision": result["base_revision"], "workspace": result}

    def processes(self):
        """Read-only evidence for this store's production FUSE servers, never signal PIDs."""
        servers = []
        for process in Path("/proc").iterdir():
            if not process.name.isdigit():
                continue
            try:
                args = (process / "cmdline").read_bytes().split(b"\0")
                if not args or args[0] != os.fsencode(self.binary):
                    continue
                if args[1:4] != [b"--store", os.fsencode(self.library), b"__projection-serve"]:
                    continue
                generation = os.fsdecode(args[args.index(b"--generation") + 1])
                servers.append({"pid": int(process.name), "generation": generation})
            except (FileNotFoundError, ProcessLookupError):
                continue
        return servers

    def retained_snapshot(self):
        views, daemons = [], []
        require(len(self.views) == 3 and {view["name"] for view in self.views} == {"main", "work", "second"}
                and len({view["merged"] for view in self.views}) == 3
                and len({view["generation"] for view in self.views}) == 3,
                "expected three distinct production workspaces")
        servers = self.processes()
        for view in self.views:
            current = self.view(self.cli("show", view["name"]))
            require(current["merged"] == view["merged"], "linear workload unexpectedly replaced workspace")
            record = {"name": view["name"], "path": str(view["merged"]), "generation": view["generation"]}
            if self.backend == "projection":
                lower = view["merged"].parent / "lower"
                mounted, lower_mount = exact_mount(view["merged"]), exact_mount(lower)
                require(mounted and mounted["filesystem"] == "overlay"
                        and mounted["superOptions"].get("lowerdir") == str(lower)
                        and lower_mount and lower_mount["filesystem"] == "fuse"
                        and lower_mount["source"] == "sprig-cas" and "ro" in lower_mount["mountOptions"],
                        "production view has unexpected mount binding")
                matching = [server for server in servers if server["generation"] == view["generation"]]
                require(len(matching) == 1, "expected exactly one production FUSE server for each view")
                record["mountInfo"] = mounted
                daemons.append({**matching[0], "name": view["name"], "lower": str(lower), "mountInfo": lower_mount})
            else:
                require(exact_mount(view["merged"]) is None, "native workspace unexpectedly mounted")
            views.append(record)
        require(len(servers) == len(daemons) and
                (self.backend != "projection" or {server["generation"] for server in servers}
                 == {view["generation"] for view in self.views}),
                "unaccounted or duplicate production FUSE server")
        return {"views": views, "foregroundFuseProcesses": daemons,
                "controlProcessesRunning": len(servers), "historicalReadbacksStarted": False,
                "fileTreesRetained": True}

    def execute(self):
        start = time.perf_counter()
        self.cli("init")
        self.report["init_seconds"] = time.perf_counter() - start
        start = time.perf_counter()
        inventory_source(self.source, self.oracle, mount_table())
        imported = self.cli("import", self.source, "main", projected=self.backend == "projection")
        self.report["import_seconds"] = time.perf_counter() - start
        main = self.view(imported)
        self.views.append(main)
        initial = main["base_revision"]
        require(HEX64.fullmatch(initial), "invalid initial revision")
        self.report.update({"import": imported, "initialHead": initial})
        checks = full_checks(self.oracle)
        start = time.perf_counter()
        first_result = self.cli("fork", "main", "work")
        self.report["first_fork_seconds"] = time.perf_counter() - start
        first = self.view(first_result)
        self.views.append(first)
        start = time.perf_counter()
        self.shell(first["merged"], checks)
        self.report["first_read_seconds"] = time.perf_counter() - start
        self.report["total_import_fork_read_seconds"] = sum(self.report[key] for key in
            ("import_seconds", "first_fork_seconds", "first_read_seconds"))
        start = time.perf_counter()
        second_result = self.cli("fork", "main", "second")
        self.report["warm_fork_seconds"] = time.perf_counter() - start
        second = self.view(second_result)
        self.views.append(second)
        start = time.perf_counter()
        self.shell(second["merged"], checks)
        self.report["warm_read_seconds"] = time.perf_counter() - start
        self.report["warm_total_seconds"] = self.report["warm_fork_seconds"] + self.report["warm_read_seconds"]
        base, revisions = initial, set()
        if self.steps:
            baseline = self.cli("log", "work")
            require(len(baseline) == 1 and baseline[0]["revision"] == initial
                    and baseline[0]["parents"] == [], "unexpected history baseline")
        for step in self.steps:
            start = time.perf_counter()
            self.shell(first["merged"], write_command(step))
            write_seconds = time.perf_counter() - start
            self.report["write_seconds"] += write_seconds
            start = time.perf_counter()
            checkpoint = self.cli("checkpoint", "work", "--expected-head", base,
                                  "--message", "Frozen history step " + str(step["step"]))
            checkpoint_seconds = time.perf_counter() - start
            self.report["checkpoint_seconds"] += checkpoint_seconds
            previous, base = base, checkpoint["revision"]
            row = {"step": step["step"], "revision": base, "base": previous,
                   "write_seconds": write_seconds, "checkpoint_seconds": checkpoint_seconds,
                   "checkpoint": checkpoint, "changedFileReadback": False}
            self.report["checkpoint_steps"].append(row)
            self.step_record({"event": "checkpoint_acknowledged", **row})
            require(checkpoint["committed"] is True and checkpoint["branch"] == "work"
                    and checkpoint["previous_head"] == previous and HEX64.fullmatch(base)
                    and base != initial and base not in revisions,
                    "history requires a distinct publication at every step", checkpoint=checkpoint)
            revisions.add(base)
            self.report["history_distinct_revisions"] = len(revisions)
            self.shell(first["merged"], changed_check(step))
            row["changedFileReadback"] = True
            self.step_record({"event": "changed_file_verified", "step": step["step"], "revision": base})
        if self.steps:
            require(len(revisions) == 100, "history100 did not produce 100 distinct revisions")
            self.shell(first["merged"], full_checks(self.final))
        history = self.cli("log", "work")
        expected = [row["revision"] for row in reversed(self.report["checkpoint_steps"])] + [initial]
        require([row["revision"] for row in history] == expected, "history does not contain exact acknowledged chain")
        for index, revision in enumerate(history):
            require(revision["parents"] == expected[index + 1:index + 2], "unexpected revision parents")
        self.sample_space()
        current = {row["path"]: dict(row) for row in self.oracle}
        for step, row in zip(self.steps, self.report["checkpoint_steps"]):
            current[step["path"]]["sha256"] = step["sha256"]
            restored = self.view(self.cli("restore", row["revision"], "history-%03d" % step["step"],
                                         projected=self.backend == "projection"))
            require(restored["base_revision"] == row["revision"], "restore returned wrong history revision")
            self.shell(restored["merged"], full_checks(list(current.values())))
            self.report["fullHistoricalSnapshotReadbacks"] += 1
            self.step_record({"event": "historical_snapshot_verified", "step": step["step"], "revision": row["revision"]})
            if self.backend == "projection":
                self.unmount_generation(restored["generation"])
        require(self.report["fullHistoricalSnapshotReadbacks"] == len(self.steps), "historical readbacks incomplete")
        self.shell(main["merged"], checks)
        self.shell(second["merged"], checks)
        self.shell(self.source, checks)
        listing = self.cli("list")
        require(listing["branches"]["main"] == initial and listing["branches"]["second"] == initial,
                "unmodified branch moved unexpectedly")
        self.report.update({"originalMainViewUnchanged": True, "originalSecondViewUnchanged": True,
                            "sourceUnchanged": True, "allAcknowledgedIdsPresent": True, "ok": True})

    def unmount_generation(self, generation):
        require(not self.cleanup_blocked and generation not in self.attempted_generations,
                "cleanup blocked or already attempted; no retry")
        self.attempted_generations.add(generation)
        attempt = {"generation": generation, "operation": "CLI unmount-generation", "ok": False}
        self.report["lifecycle"]["cleanup"]["attempts"].append(attempt)
        try:
            self.cli("unmount-generation", generation)
            require(not exact_mount(self.library / "native" / generation / "tree")
                    and not exact_mount(self.library / "native" / generation / "lower"),
                    "CLI unmount returned but mount remains")
            attempt["ok"] = True
        except BaseException as error:
            self.cleanup_blocked = True
            attempt["error"] = str(error)
            raise

    def cleanup(self):
        if not self.root:
            return
        try:
            if not self.cleanup_blocked and self.library.exists():
                for pin in sorted((self.library / "native").glob("*/projection-base"), reverse=True):
                    if exact_mount(pin.parent / "tree") or exact_mount(pin.parent / "lower"):
                        self.unmount_generation(pin.parent.name)
            # Normal FUSE teardown is asynchronous; observe exit, never kill.
            deadline = time.monotonic() + 15
            while self.processes() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.report["lifecycle"]["daemons"] = self.processes()
        except BaseException as error:
            self.cleanup_blocked = True
            self.report.setdefault("cleanupErrors", []).append({"message": str(error), "details": getattr(error, "details", {})})
        self.report["remainingMounts"] = [mount for mount in mount_table() if inside(Path(mount["mountpoint"]), self.root)]
        complete = not self.cleanup_blocked and not self.report["remainingMounts"] and not self.processes()
        self.report["lifecycle"]["cleanup"].update({"complete": complete, "blocked": self.cleanup_blocked,
                                                    "harnessProcessesKilled": False, "processesKilled": None, "forceOrLazyUnmountUsed": False})
        if not complete:
            self.report["ok"] = False

    def preserve_logs(self):
        super().preserve_logs()
        if self.library:
            for path in sorted((self.library / "native").glob("*/projection-*.log")):
                checked_path(path)
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 65536))
                    text = stream.read().decode("utf-8", errors="replace")
                self.report.setdefault("runtimeLogs", []).append({"path": str(path), "bytes": path.stat().st_size,
                                                                  "truncated": path.stat().st_size > 65536, "text": text})


def main():
    report = production_report()
    sample = ProductionSample(report)
    try:
        parser = Parser(description=__doc__)
        sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        run = sub.add_parser("run")
        for name in ("root", "source", "oracle", "binary", "backend"):
            run.add_argument("--" + name, required=True, **({"choices": ["native", "projection"]} if name == "backend" else {}))
        run.add_argument("--steps")
        run.add_argument("--records")
        sample.prepare(parser.parse_args())
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
            sample.cleanup()
            sample.preserve_logs()
        except BaseException as error:
            report["ok"] = False
            report.setdefault("cleanupErrors", []).append({"message": str(error)})
    if sample.root:
        try:
            (sample.root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        except BaseException as error:
            report["ok"] = False
            report["reportWriteError"] = str(error)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
