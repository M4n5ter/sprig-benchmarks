#!/usr/bin/env python3
"""Harness-pinned Sprig lifecycle comparison sample on an approved temporary GitHub Btrfs runner.

Uses the unchanged cas_sample.py input, shell, measurement and failure helpers.
No private library calls, manual mounts, force/lazy unmounts or harness process killing.
All product paths, including three active workspaces and server logs, are charged.
The workflow must verify the exact --production-sha checkout/build; this sampler cannot derive a source commit from the binary.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
import sys
import time
import traceback

from cas_sample import (HEX64, Parser, Sample, SampleError, checked_path,
                        full_checks, changed_check, write_command, inventory_source,
                        mount_table, exact_mount, inside, new_report, require, filesystem_used)

def production_report():
    report = new_report()
    report.update({"prototype_only": False, "production_sha": None, "compressionPolicy": "auto (default init)",
                   "complete_sprig_semantics": False, "workload_only_verification": True,
                   "initializationIncludedInImport": False, "init_seconds": None,
                   "metadata_branch_available": True, "metadata_branch_probe": "omitted",
                   "metadata_branch_unavailable_reason": None,
                   "restore_seconds": 0.0, "restore_read_seconds": 0.0,
                   "restore_cleanup_seconds": 0.0, "historical_restore_steps": [],
                   "restoreTimingScope": "100 historical snapshots after active-space accounting; zero for nonhistory",
                   "nativeRestoreCleanup": "0.0 seconds: no unmount operation; native trees retained",
                   "productionShaSource": "explicit --production-sha supplied by verified checkout/build harness",
                   "binarySourcePinVerifiedBySampler": False,
                   "postHistorySpace": None, "componentDiagnostics": {}})
    report["measurementNotes"] = [
        "Real production CLI; workflow checkout/build must enforce the reported source pin.",
        "Initialization is timed separately; preparation headline adds init to import+fork+read.",
        "Import includes safety inventory and the product-created main workspace, including its explicit mount if writable.",
        "Writable import, fork and restore first create an unmounted owned journal; explicit mount and readiness are charged to that operation.",
        "Writable checkpoint replaces and auto-remounts its generation; authoritative show/path readiness is charged to checkpoint before the next shell read/write.",
        "Checkpoint timing sums the CLI and readiness phases; the immediate checkpoint-response ledger flush between them is excluded, as is the existing final step ledger.",
        "A returned mount_error is a failure, not authorization to retry an uncertain mount.",
        "Each fork is the complete product CLI operation; three independent workspaces remain active at accounting.",
        "Frozen bash SHA/read/dd/fsync/touch commands are unchanged; CLI transport differs from an in-process SDK.",
        "All objects, revisions, native trees or upper/lower generations, state, backups, locks and runtime logs remain charged.",
        "Whole-filesystem Used includes Data, Metadata and System, not reserved capacity; no recursive FUSE du.",
        "Space is sampled after synchronization outside operation timers and before historical restore/readback.",
        "Historical restores and their retained generations occur after the original activeSpace sample; no store data is deleted.",
        "postHistorySpace is a second whole-filesystem sample after all historical restores/readbacks and final unchanged-input checks, before cleanup, with the same three original views live.",
        "Component diagnostics run only after postHistorySpace, after all timed historical restores/readbacks; no component traversal occurs between activeSpace and restore timers.",
        "Component logical regular-file bytes and inode-deduplicated st_blocks*512 are diagnostics, not exclusive physical usage or additive Btrfs totals: reflinks/shared/compressed extents prevent subtraction or summation into whole-filesystem Used.",
        "Component inventory never follows symlinks, crosses devices, or stats/traverses any mount boundary; live FUSE/overlay trees remain unscanned and underlying store backing files remain charged by whole-filesystem accounting.",
        "Live means one of the three original views; retained means another physical generation, including historical workspaces and old journals, not a claim that it is unreachable or reclaimable.",
        "restore_seconds sums restore CLI plus required mount/readiness; restore_read_seconds sums frozen full SHA readbacks; restore_cleanup_seconds sums normal CLI unmount and server-exit observation.",
        "Native historical cleanup is exactly 0.0: there is no unmount, and restored native trees remain retained.",
        "Full listed-file content oracles do not establish full metadata parity or equal durability.",
        "Harness never signals processes; production startup-failure cleanup may terminate its own child after normal unmount, which the harness cannot count.",
    ]
    return report


class CurrentSample(Sample):
    def prepare(self, args):
        require(re.fullmatch(r"[0-9a-f]{40}", args.production_sha) is not None,
                "--production-sha must be a full lowercase 40-hex source commit")
        self.report["production_sha"] = args.production_sha
        self.backend = args.backend
        self.report["backend"] = self.backend
        self.attempted_generations = set()
        super().prepare(args)

    def cli(self, action, *args, creation=False):
        command = [self.binary, "--store", self.library, "--json"]
        if creation and self.backend != "native":
            command.append("--projected" if self.backend == "projection" else "--writable")
        output = json.loads(self.command([*command, action, *args]))
        require(output.get("schema_version") == 1 and "result" in output and "error" not in output,
                "unexpected production CLI response", output=output)
        return output["result"]

    def view(self, result, *, usable=True):
        require(not result.get("mount_error"), "CLI reported a mount failure; no automatic retry", workspace=result)
        require(result["backend"]["kind"] == self.backend, "unexpected workspace backend", workspace=result)
        expected_state = ("native" if self.backend == "native" else "mounted") if usable else "unmounted"
        require(result["mount_state"] == expected_state, "workspace has unexpected mount state", workspace=result)
        tree = Path(result["path"])
        require(tree.is_absolute() and tree.parent.parent == self.library / "native"
                and tree.name == "tree" and tree.parent.name not in ("", ".", ".."),
                "CLI workspace path escaped managed store", path=str(tree))
        if self.backend != "native":
            require(HEX64.fullmatch(result["backend"]["revision"]), "invalid backend base pin")
            pin = tree.parent / ("writable-base" if self.backend == "writable" else "projection-base")
            checked_path(pin)
            require(pin.read_text() == result["backend"]["revision"], "backend pin differs from owned generation")
        return {"name": result["name"], "merged": tree, "generation": tree.parent.name,
                "base_revision": result["base_revision"], "workspace": result}

    def created_view(self, result):
        """Do not expose an empty writable mountpoint as the workspace's data."""
        if self.backend != "writable":
            return self.view(result)
        initial = self.view(result, usable=False)
        require(exact_mount(initial["merged"]) is None, "new writable generation is unexpectedly mounted")
        mounted = self.view(self.cli("mount", initial["name"]))
        require(mounted["merged"] == initial["merged"]
                and mounted["base_revision"] == initial["base_revision"]
                and mounted["workspace"]["backend"] == initial["workspace"]["backend"],
                "mount unexpectedly replaced the created workspace")
        return mounted

    def processes(self):
        """Read exact executable/store/server argv and PID start ticks; never signal."""
        servers = []
        for process in Path("/proc").iterdir():
            if not process.name.isdigit():
                continue
            try:
                args = (process / "cmdline").read_bytes().rstrip(b"\0").split(b"\0")
                if not args or args[0] != os.fsencode(self.binary):
                    continue
                if args[1:3] != [b"--store", os.fsencode(self.library)]:
                    continue
                if len(args) < 4 or args[3] not in (b"__projection-serve", b"__writable-serve"):
                    continue
                require(len(args) == 8 and args[4] == b"--revision" and args[6] == b"--generation",
                        "unexpected managed FUSE server argv", pid=int(process.name))
                generation, revision = os.fsdecode(args[7]), os.fsdecode(args[5])
                require(HEX64.fullmatch(revision), "invalid managed FUSE server revision")
                ticks = int((process / "stat").read_text().rpartition(") ")[2].split()[19])
                servers.append({"pid": int(process.name), "startTimeTicks": ticks,
                                "generation": generation, "revision": revision,
                                "backend": "writable" if args[3] == b"__writable-serve" else "projection",
                                "argv": [os.fsdecode(arg) for arg in args]})
            except (FileNotFoundError, ProcessLookupError):
                continue
        return sorted(servers, key=lambda server: server["pid"])

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
            require(len(retained["writable"]) == 3 + len(self.steps) + self.report["fullHistoricalSnapshotReadbacks"],
                    "writable checkpoint generations were not all retained", generations=retained)
        return {"views": views, "foregroundFuseProcesses": daemons,
                "controlProcessesRunning": len(servers),
                "historicalReadbacksStarted": self.report["fullHistoricalSnapshotReadbacks"] > 0,
                "historicalReadbacksCompleted": self.report["fullHistoricalSnapshotReadbacks"],
                "fileTreesRetained": True, "retainedGenerations": retained,
                "allRuntimeLogsAndJournalsInsideMeasuredStore": True}

    def execute(self):
        start = time.perf_counter()
        self.cli("init")
        self.report["init_seconds"] = time.perf_counter() - start
        start = time.perf_counter()
        inventory_source(self.source, self.oracle, mount_table())
        imported = self.cli("import", self.source, "main", creation=True)
        main = self.created_view(imported)
        self.report["import_seconds"] = time.perf_counter() - start
        self.views.append(main)
        initial = main["base_revision"]
        require(HEX64.fullmatch(initial), "invalid initial revision")
        self.report.update({"import": imported, "initialHead": initial})
        checks = full_checks(self.oracle)
        start = time.perf_counter()
        first_result = self.cli("fork", "main", "work", creation=self.backend == "writable")
        first = self.created_view(first_result)
        self.report["first_fork_seconds"] = time.perf_counter() - start
        self.views.append(first)
        start = time.perf_counter()
        self.shell(first["merged"], checks)
        self.report["first_read_seconds"] = time.perf_counter() - start
        self.report["total_import_fork_read_seconds"] = sum(self.report[key] for key in
            ("import_seconds", "first_fork_seconds", "first_read_seconds"))
        start = time.perf_counter()
        second_result = self.cli("fork", "main", "second", creation=self.backend == "writable")
        second = self.created_view(second_result)
        self.report["warm_fork_seconds"] = time.perf_counter() - start
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
            checkpoint_cli_seconds = time.perf_counter() - start
            # Preserve a publication even if subsequent authoritative path checks fail.
            # Ledger I/O stays outside both measured operation phases.
            self.step_record({"event": "checkpoint_response", "step": step["step"],
                              "checkpoint": checkpoint, "checkpoint_cli_seconds": checkpoint_cli_seconds})
            old_generation = first["generation"]
            checkpoint_ready_seconds = 0.0
            if self.backend == "writable":
                start = time.perf_counter()
                require(not checkpoint.get("mount_error"), "checkpoint remount failed; no automatic retry", checkpoint=checkpoint)
                current = self.cli("show", "work")
                require(not current.get("mount_error"), "checkpoint show reported a mount failure", workspace=current)
                # fba02ad already remounts a mounted writable checkpoint. An
                # unmounted result now is a failed/lost server, not a fresh request.
                refreshed = self.view(current)
                require(refreshed["generation"] != old_generation
                        and refreshed["base_revision"] == checkpoint["revision"],
                        "writable checkpoint did not replace the authoritative generation")
                require(exact_mount(first["merged"]) is None,
                        "old writable checkpoint generation remains mounted")
                self.views[self.views.index(first)] = refreshed
                first = refreshed
                checkpoint_ready_seconds = time.perf_counter() - start
            checkpoint_seconds = checkpoint_cli_seconds + checkpoint_ready_seconds
            self.report["checkpoint_seconds"] += checkpoint_seconds
            previous, base = base, checkpoint["revision"]
            row = {"step": step["step"], "revision": base, "base": previous,
                   "write_seconds": write_seconds, "checkpoint_seconds": checkpoint_seconds,
                   "checkpoint": checkpoint, "changedFileReadback": False,
                   "generation_before": old_generation, "generation_after": first["generation"],
                   "workspace_path_after": str(first["merged"]),
                   "checkpoint_cli_seconds": checkpoint_cli_seconds,
                   "checkpoint_ready_seconds": checkpoint_ready_seconds}
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
            start = time.perf_counter()
            restored = self.created_view(self.cli("restore", row["revision"], "history-%03d" % step["step"],
                                                 creation=True))
            restore_seconds = time.perf_counter() - start
            self.report["restore_seconds"] += restore_seconds
            require(restored["base_revision"] == row["revision"], "restore returned wrong history revision")
            start = time.perf_counter()
            self.shell(restored["merged"], full_checks(list(current.values())))
            restore_read_seconds = time.perf_counter() - start
            self.report["restore_read_seconds"] += restore_read_seconds
            self.report["fullHistoricalSnapshotReadbacks"] += 1
            restore_cleanup_seconds = 0.0
            if self.backend != "native":
                start = time.perf_counter()
                self.unmount_generation(restored["generation"])
                restore_cleanup_seconds = time.perf_counter() - start
                self.report["restore_cleanup_seconds"] += restore_cleanup_seconds
            restored_row = {"step": step["step"], "revision": row["revision"],
                            "generation": restored["generation"], "restore_seconds": restore_seconds,
                            "restore_read_seconds": restore_read_seconds,
                            "restore_cleanup_seconds": restore_cleanup_seconds,
                            "cleanup_operation": "none; native tree retained" if self.backend == "native" else "CLI unmount-generation"}
            self.report["historical_restore_steps"].append(restored_row)
            self.step_record({"event": "historical_snapshot_verified", **restored_row})
        require(self.report["fullHistoricalSnapshotReadbacks"] == len(self.steps), "historical readbacks incomplete")
        self.shell(main["merged"], checks)
        self.shell(second["merged"], checks)
        self.shell(self.source, checks)
        listing = self.cli("list")
        require(listing["branches"]["main"] == initial and listing["branches"]["second"] == initial,
                "unmodified branch moved unexpectedly")
        self.sample_post_history_space()
        self.component_diagnostics("postHistorySpace")
        self.report.update({"originalMainViewUnchanged": True, "originalSecondViewUnchanged": True,
                            "sourceUnchanged": True, "allAcknowledgedIdsPresent": True, "ok": True})

    def sample_post_history_space(self):
        """Second primary sample, not a replacement for the frozen active sample."""
        require(self.report["fullHistoricalSnapshotReadbacks"] == len(self.steps),
                "post-history sample requires all historical readbacks")
        active = self.retained_snapshot()
        generations = sorted(path.name for path in (self.library / "native").iterdir()
                             if stat.S_ISDIR(path.lstat().st_mode))
        expected_count = 3 + len(self.steps) * (2 if self.backend == "writable" else 1)
        require(len(generations) == expected_count, "unexpected post-history retained generation count",
                expected=expected_count, actual=len(generations), generations=generations)
        active.update({"historicalReadbacksComplete": True, "retainedGenerationCount": len(generations),
                       "generationDirectories": generations, "measurementBoundary": "after all restores/readbacks and before cleanup"})
        self.report["lifecycle"]["activeAfterHistory"] = active
        self.event("post_history_space_begin", lifecycle=active)
        # Exactly the same primary Used metric; no bookkeeping writes in between.
        self.command(["btrfs", "filesystem", "sync", self.root], record_event=False)
        usage = self.command(["btrfs", "filesystem", "usage", "-b", self.root], record_event=False)
        groups = self.command(["btrfs", "filesystem", "df", "-b", self.root], record_event=False)
        self.report["postHistorySpace"] = {"filesystemUsedBytes": filesystem_used(usage),
                                           "usageRaw": usage, "groupsRaw": groups}
        self.retained_snapshot()
        self.event("post_history_space_complete", filesystemUsedBytes=filesystem_used(usage))

    def component_diagnostics(self, sample_name):
        """Read-only backing-path inventory, never recursive du over mounted views.

        Categories follow the inspected schema-10 layout. Objects include packed
        payloads, pack indexes and manifest-page objects; no inferred content split.
        Unknown paths remain explicitly unclassified instead of being omitted.
        """
        require(self.report.get(sample_name) is not None, "component inventory must follow its primary sample")
        started = time.perf_counter()
        record = {"afterPrimarySample": sample_name, "primaryMetric": "whole-filesystem Used",
                  "method": "lstat, no symlink following, same-device only, mounted paths skipped before stat",
                  "physicallyAdditive": False, "exclusivePhysicalBytes": None,
                  "logicalMetric": "regular file st_size, hardlink inodes deduplicated within each component",
                  "allocatedMetric": "st_blocks * 512 for nonmounted inodes, deduplicated within each component; not unique extents",
                  "coverage": "store backing paths plus harness paths under sample root; all mounted view boundaries skipped",
                  "cachePath": "library/file-cache", "cachePresent": False,
                  "components": [], "errors": [], "complete": False}
        self.report["componentDiagnostics"][sample_name] = record
        try:
            mounts = {Path(m["mountpoint"]) for m in mount_table() if inside(Path(m["mountpoint"]), self.root)}
            device = self.root.lstat().st_dev
            live = {view["generation"]: view["workspace"]["backend"]["kind"] for view in self.views}

            def measure(path, category, *, role=None, backend=None, recurse=True):
                row = {"path": str(path.relative_to(self.root)), "category": category,
                       "role": role, "backend": backend, "regularFileLogicalBytes": 0,
                       "allocatedStatBytes": 0, "regularFiles": 0, "directories": 0,
                       "symlinks": 0, "otherNodes": 0, "duplicateHardlinkEntries": 0,
                       "skippedMounts": [], "skippedDevices": [], "errors": []}
                seen, todo = set(), [path]
                while todo:
                    current = todo.pop()
                    # Even lstat on a FUSE root reaches the mounted filesystem.
                    boundary = next((point for point in mounts if inside(current, point)), None)
                    if boundary is not None:
                        row["skippedMounts"].append(str(boundary.relative_to(self.root)))
                        continue
                    try:
                        info = current.lstat()
                        if info.st_dev != device:
                            row["skippedDevices"].append(str(current.relative_to(self.root)))
                            continue
                        inode = (info.st_dev, info.st_ino)
                        if inode in seen:
                            row["duplicateHardlinkEntries"] += 1
                            continue
                        seen.add(inode)
                        row["allocatedStatBytes"] += info.st_blocks * 512
                        if stat.S_ISREG(info.st_mode):
                            row["regularFiles"] += 1
                            row["regularFileLogicalBytes"] += info.st_size
                        elif stat.S_ISDIR(info.st_mode):
                            row["directories"] += 1
                            if recurse:
                                todo.extend(current.iterdir())
                        elif stat.S_ISLNK(info.st_mode):
                            row["symlinks"] += 1
                        else:
                            row["otherNodes"] += 1
                    except OSError as error:
                        row["errors"].append({"path": str(current.relative_to(self.root)), "message": str(error)})
                row["skippedMounts"] = sorted(set(row["skippedMounts"]))
                record["components"].append(row)

            def is_regular(path):
                try:
                    return stat.S_ISREG(path.lstat().st_mode)
                except FileNotFoundError:
                    return False

            measure(self.root, "harness_structure", recurse=False)
            for top in sorted(self.root.iterdir()):
                if top != self.library:
                    measure(top, "harness")
            measure(self.library, "metadata_structure", recurse=False)
            for area in sorted(self.library.iterdir()):
                name = area.name
                if name == "native":
                    if area in mounts or not stat.S_ISDIR(area.lstat().st_mode):
                        measure(area, "unclassified_store")
                        continue
                    measure(area, "metadata_structure", recurse=False)
                    for generation in sorted(area.iterdir()):
                        # Generation directories themselves are unmounted backing paths.
                        if generation in mounts or not stat.S_ISDIR(generation.lstat().st_mode):
                            measure(generation, "unclassified_store")
                            continue
                        projection = is_regular(generation / "projection-base")
                        writable = is_regular(generation / "writable-base")
                        backend = ("ambiguous" if projection and writable else "projection" if projection
                                   else "writable" if writable else "native_unpinned")
                        if generation.name in live:
                            role = "live"
                            expected = live[generation.name]
                            if backend != ("native_unpinned" if expected == "native" else expected):
                                record["errors"].append({"path": str(generation), "message": "backend pin disagrees with live CLI workspace"})
                        else:
                            role = "retained"
                        measure(generation, role + "_generation_backing", role=role, backend=backend)
                elif name == "objects":
                    measure(area, "cas_objects_and_indexes")
                elif name == "file-cache":
                    record["cachePresent"] = True
                    measure(area, "disposable_file_cache")
                elif name in ("revisions", "backups", "staging", "state.json", "lock"):
                    measure(area, "metadata")
                else:
                    measure(area, "unclassified_store")
            record["complete"] = not record["errors"] and not any(row["errors"] or row["skippedDevices"] for row in record["components"])
        except OSError as error:
            record["errors"].append({"message": str(error)})
        finally:
            record["seconds"] = time.perf_counter() - started

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
            # Mount disappearance alone does not prove its exact server exited.
            deadline = time.monotonic() + 15
            while any(server["generation"] == generation for server in self.processes()) and time.monotonic() < deadline:
                time.sleep(0.02)
            require(not any(server["generation"] == generation for server in self.processes()),
                    "normal unmount left a generation server running; no signal or retry")
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
                pins = set((self.library / "native").glob("*/projection-base"))
                pins.update((self.library / "native").glob("*/writable-base"))
                for pin in sorted(pins, reverse=True):
                    if (exact_mount(pin.parent / "tree") or exact_mount(pin.parent / "lower")
                            or any(server["generation"] == pin.parent.name for server in self.processes())):
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
            paths = set((self.library / "native").glob("*/projection-*.log"))
            paths.update((self.library / "native").glob("*/writable-*.log"))
            for path in sorted(paths):
                checked_path(path)
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 65536))
                    text = stream.read().decode("utf-8", errors="replace")
                self.report.setdefault("runtimeLogs", []).append({"path": str(path), "bytes": path.stat().st_size,
                                                                  "truncated": path.stat().st_size > 65536, "text": text})


def main():
    report = production_report()
    sample = CurrentSample(report)
    try:
        parser = Parser(description=__doc__)
        sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        run = sub.add_parser("run")
        for name in ("root", "source", "oracle", "binary", "backend"):
            run.add_argument("--" + name, required=True, **({"choices": ["native", "projection", "writable"]} if name == "backend" else {}))
        run.add_argument("--production-sha", required=True)
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
