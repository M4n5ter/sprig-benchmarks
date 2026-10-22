#!/usr/bin/env python3
"""One temporary root-CI CAS sample, not a product or a comparison harness.

Run only in an explicitly approved, isolated GitHub Actions runner. The caller
provides a fresh synthetic Btrfs filesystem; this script NEVER creates an image,
formats a device, mounts Btrfs, installs helpers, or changes system settings.

  python3 cas_sample.py run --root NEW_DIR_ON_BTRFS --source FIXTURE \
      --oracle FIXTURE.json [--steps FIXTURE-steps.json] --binary PROTOTYPE \
      [--records NEW_JSONL_UNDER_RUNNER_TEMP]

Every mutable product path is below the new root. External inputs are read-only.
Optional --records moves only the harness step ledger outside the measured root;
FUSE logs and all CAS/upper/work state remain charged to the measured filesystem.
No timings are invented for the unavailable metadata-only branch API. Library
import and lazy head initialization share the import timer. Each fork pays for a
new foreground FUSE process, readiness, and its own kernel OverlayFS mount.

The frozen oracle and writer shell commands match fixtures.py, history-check.mjs
and feasibility/native_snapshot.py in the comparison checkout. Historical full
reads happen only AFTER whole-filesystem accounting with both views still live.
All cleanup is ordinary umount -i, overlays before their lower mounts. Cleanup
stops on refusal/error; it never retries, forces/lazily unmounts, or kills FUSE.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shutil
import stat
import subprocess
import sys
import time
import traceback

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SAFE_COMPONENT = re.compile(r"[A-Za-z0-9_.-]+\Z")
FROZEN_MTIME_NS = 1_700_000_000_000_000_000
OVERLAY_FLAGS = "redirect_dir=on,metacopy=off,index=off,nfs_export=off"


class SampleError(RuntimeError):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def require(condition, message, **details):
    if not condition:
        raise SampleError(message, **details)


def inside(path, parent):
    return path == parent or parent in path.parents


def overlaps(a, b):
    return inside(a, b) or inside(b, a)


def checked_path(value, *, new=False, directory=False):
    """Reject symlink traversal rather than resolving it and trusting the result."""
    raw = os.fspath(value)
    require(raw and "\x00" not in raw, "empty or NUL-containing path")
    path = Path(raw)
    require(".." not in path.parts, "parent traversal is not allowed", path=raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    cursor = Path(path.anchor)
    for index, part in enumerate(path.parts[1:]):
        cursor /= part
        leaf = index == len(path.parts) - 2
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            require(new and leaf, "path component does not exist", path=str(cursor))
            return path
        require(not stat.S_ISLNK(info.st_mode), "symlink path component rejected", path=str(cursor))
        if leaf:
            require(not new, "output must be a new path; refusing overwrite", path=str(path))
            require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
                    "unexpected input path kind", path=str(path))
        else:
            require(stat.S_ISDIR(info.st_mode), "ancestor is not a directory", path=str(cursor))
    require(not new, "filesystem root cannot be a new output")
    return path


def relative_name(value):
    require(isinstance(value, str) and value, "invalid fixture relative path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value
            and all(part not in (".", "..") and SAFE_COMPONENT.fullmatch(part)
                    for part in path.parts), "unsafe fixture relative path", path=value)
    require(not value.startswith("-"), "option-like fixture path rejected", path=value)
    return value


def read_manifest(path):
    rows = json.loads(path.read_text())
    require(isinstance(rows, list) and rows, "oracle must be a nonempty array")
    names = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"path", "bytes", "sha256"},
                "oracle row is not the frozen fixture format")
        name = relative_name(row["path"])
        require(name not in names, "duplicate oracle path", path=name)
        names.add(name)
        require(type(row["bytes"]) is int and row["bytes"] >= 0,
                "invalid oracle byte length", path=name)
        require(isinstance(row["sha256"], str) and HEX64.fullmatch(row["sha256"]),
                "invalid SHA-256 oracle", path=name)
    return rows


def full_checks(oracle):
    # Keep the SAME frozen shell check, including grouping, order, and transport.
    return "(" + ";".join(
        "printf '%s  %s\\n' '" + row["sha256"] + "' '" + row["path"] + "'"
        for row in oracle) + ") | sha256sum -c -"


def changed_check(step):
    return "printf '%s  %s\\n' '" + step["sha256"] + "' '" + step["path"] + "' | sha256sum -c -"


def write_command(step):
    # Do not substitute Python I/O, add fsyncs, or change the frozen writer.
    return ("set -e; printf '%s' '" + step["data"]
            + "' | base64 -d | dd of='" + step["path"]
            + "' bs=65536 iflag=fullblock oflag=seek_bytes seek=" + str(step["offset"])
            + " conv=notrunc,fsync status=none; touch -d @1700000000 '" + step["path"] + "'")


def read_steps(path, oracle, final):
    steps = json.loads(path.read_text())
    require(isinstance(steps, list) and len(steps) == 100,
            "the frozen history100 workload requires exactly 100 steps")
    current = {row["path"]: dict(row) for row in oracle}
    for number, step in enumerate(steps, 1):
        require(isinstance(step, dict)
                and set(step) == {"step", "path", "offset", "data", "sha256"},
                "step is not the frozen history format", step=number)
        require(type(step["step"]) is int and step["step"] == number,
                "history steps must be contiguous 1..100")
        name = relative_name(step["path"])
        require(name in current, "history path absent from genesis", path=name)
        require(type(step["offset"]) is int and step["offset"] >= 0,
                "invalid history offset", step=number)
        require(isinstance(step["data"], str), "history data must be base64 text")
        data = base64.b64decode(step["data"], validate=True)
        require(data and base64.b64encode(data).decode() == step["data"],
                "history data must be nonempty canonical base64")
        require(step["offset"] + len(data) <= current[name]["bytes"],
                "history edit extends beyond the frozen file", step=number)
        require(isinstance(step["sha256"], str) and HEX64.fullmatch(step["sha256"]),
                "invalid changed-file SHA-256", step=number)
        current[name]["sha256"] = step["sha256"]
    require(current == {row["path"]: row for row in final},
            "final oracle disagrees with accumulated history steps")
    return steps


def inventory_source(source, oracle, mounts):
    """Metadata-only validation of trusted frozen input, never recursive FUSE du."""
    require(not any(inside(Path(m["mountpoint"]), source) for m in mounts),
            "source must not contain a mountpoint")
    expected = {row["path"]: row for row in oracle}
    found = {}
    device = source.lstat().st_dev
    todo = [source]
    while todo:
        path = todo.pop()
        info = path.lstat()
        require(info.st_dev == device, "fixture crosses a filesystem", path=str(path))
        require(not stat.S_ISLNK(info.st_mode), "frozen fixture symlink rejected", path=str(path))
        if stat.S_ISDIR(info.st_mode):
            require(stat.S_IMODE(info.st_mode) == 0o750 and info.st_mtime_ns == FROZEN_MTIME_NS,
                    "directory does not have frozen fixture metadata", path=str(path))
            todo.extend(path.iterdir())
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                    "fixture must contain only unlinked regular files and directories", path=str(path))
            require(stat.S_IMODE(info.st_mode) == 0o640 and info.st_mtime_ns == FROZEN_MTIME_NS,
                    "file does not have frozen fixture metadata", path=str(path))
            name = relative_name(path.relative_to(source).as_posix())
            found[name] = info.st_size
    require(found == {name: row["bytes"] for name, row in expected.items()},
            "source paths or sizes differ from the frozen oracle")


def decode_mount(value):
    # The kernel escapes space, tab, newline and backslash with octal bytes.
    def decode(match):
        number = int(match.group(1), 8)
        require(0 < number <= 255, "invalid mountinfo escape")
        return chr(number)
    require(re.search(r"\\(?![0-7]{3})", value) is None, "invalid mountinfo escape")
    return re.sub(r"\\([0-7]{3})", decode, value)


def parse_mountinfo(text):
    mounts = []
    for line in text.splitlines():
        left, separator, right = line.partition(" - ")
        a, b = left.split(), right.split()
        require(separator and len(a) >= 6 and len(b) == 3, "malformed mountinfo")
        options = {}
        for option in b[2].split(","):
            key, _, value = option.partition("=")
            require(key not in options, "duplicate mountinfo option")
            options[key] = decode_mount(value)
        mounts.append({"id": int(a[0]), "parentId": int(a[1]),
                       "root": decode_mount(a[3]), "mountpoint": decode_mount(a[4]),
                       "mountOptions": a[5].split(","), "filesystem": b[0],
                       "source": decode_mount(b[1]), "superOptions": options})
    return mounts


def mount_table():
    return parse_mountinfo(Path("/proc/self/mountinfo").read_text())


def exact_mount(path):
    matches = [m for m in mount_table() if m["mountpoint"] == str(path)]
    require(len(matches) <= 1, "stacked mount rejected", path=str(path))
    return matches[0] if matches else None


def filesystem_used(usage):
    # Same filesystem Used metric/parser as feasibility/btrfs_compare.mjs.
    match = re.search(r"^\s*Used:\s*(\d+)\s*$", usage, re.MULTILINE)
    require(match is not None, "Btrfs usage output has no exact Used byte count")
    return int(match.group(1))


def new_report():
    return {
        "ok": False, "prototype_only": True, "complete_sprig_semantics": False,
        "initializationIncludedInImport": True,
        "metadata_branch_available": False, "metadata_branch_seconds": None,
        "metadata_branch_unavailable_reason": "The prototype CLI has no metadata-only branch API.",
        "import_seconds": None, "first_fork_seconds": None, "first_read_seconds": None,
        "total_import_fork_read_seconds": None, "warm_fork_seconds": None,
        "warm_read_seconds": None, "warm_total_seconds": None,
        "write_seconds": 0.0, "checkpoint_seconds": 0.0, "checkpoint_steps": [],
        "history_distinct_revisions": 0, "fullHistoricalSnapshotReadbacks": 0,
        "activeSpace": {"filesystemUsedBytes": None, "usageRaw": None, "groupsRaw": None},
        "lifecycle": {"fileTreesRetained": True, "normalUnmountOnly": True,
                      "persistentControlDaemon": False, "activeAtSpace": None,
                      "daemons": [], "cleanup": {"attempts": [], "complete": False}},
        "remainingMounts": [],
        "measurementNotes": [
            "Import includes source metadata safety inventory, library import and lazy head initialization; outer harness setup is excluded.",
            "Each fork includes a separate foreground FUSE launch/readiness and OverlayFS mount.",
            "Reads/writes use frozen bash commands; CLI subprocess transport is not an in-process SDK.",
            "Filesystem Used includes Btrfs data, metadata and system, not reserved capacity.",
            "Accounting runs while both views and both lower FUSE processes remain active, before historical readback.",
            "FUSE logs and product metadata remain under the measured root; no recursive du traverses FUSE.",
            "Post-accounting historical mounts, readback logs and final report are excluded from the captured space value.",
            "Final Btrfs sync is outside timers and does not imply checkpoint durability equivalence.",
        ],
    }


class Sample:
    def __init__(self, report):
        self.report = report
        self.root = None
        self.library = None
        self.logs = None
        self.records = None
        self.views = []
        self.daemons = []
        self.cleanup_blocked = False
        self.sequence = 0

    def event(self, event, **values):
        if self.logs:
            with (self.logs / "lifecycle.jsonl").open("a") as out:
                out.write(json.dumps({"event": event, "monotonicSeconds": time.monotonic(), **values},
                                     sort_keys=True) + "\n")

    def command(self, arguments, *, cwd=None, record_event=True):
        args = [str(value) for value in arguments]
        self.sequence += 1
        sequence = self.sequence
        proc = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", errors="replace", check=False)
        if record_event:
            self.event("command_finished", sequence=sequence, executable=args[0],
                       operation=args[1] if len(args) > 1 else None, returncode=proc.returncode,
                       stdoutBytes=len(proc.stdout.encode()), stderrBytes=len(proc.stderr.encode()))
        if proc.returncode:
            error_file = self.logs / ("command-%04d-error.json" % sequence) if self.logs else None
            details = {"argv": args, "cwd": str(cwd) if cwd else None,
                       "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
            if error_file:
                error_file.write_text(json.dumps(details, indent=2) + "\n")
            raise SampleError("command failed; no automatic retry", **details)
        return proc.stdout

    def cli(self, action, *args):
        return json.loads(self.command([self.binary, action, "--root", self.library, *args]))

    def shell(self, tree, command):
        return self.command(["bash", "-c", command], cwd=tree)

    def prepare(self, args):
        require(sys.platform == "linux", "sample requires Linux")
        require(os.geteuid() == 0, "sample requires root on an authorized temporary runner")
        require(os.environ.get("GITHUB_ACTIONS") == "true", "sample is limited to GitHub Actions")
        require(os.environ.get("RUNNER_TEMP"), "RUNNER_TEMP is required")
        require(Path(os.environ["RUNNER_TEMP"]).is_absolute(), "RUNNER_TEMP must be absolute")
        temporary = checked_path(os.environ["RUNNER_TEMP"], directory=True)
        root = checked_path(args.root, new=True)
        require(root != temporary and inside(root, temporary), "root must be strictly below RUNNER_TEMP")
        require(all(SAFE_COMPONENT.fullmatch(part) for part in root.parts[1:]),
                "root path contains ambiguous mount-option characters")
        self.source = checked_path(args.source, directory=True)
        self.binary = checked_path(args.binary)
        require(os.access(self.binary, os.X_OK), "prototype binary is not executable")
        oracle_path = checked_path(args.oracle)
        inputs = [self.source, self.binary, oracle_path]
        self.oracle = read_manifest(oracle_path)
        self.steps, self.final = [], self.oracle
        if args.steps:
            steps_path = checked_path(args.steps)
            require(steps_path.name.endswith("-steps.json"), "steps filename must end in -steps.json")
            final_path = checked_path(steps_path.with_name(steps_path.name[:-11] + "-final.json"))
            inputs.extend([steps_path, final_path])
            self.final = read_manifest(final_path)
            self.steps = read_steps(steps_path, self.oracle, self.final)
        require(all(not overlaps(root, path) for path in inputs), "input/output paths overlap")
        # Executable and oracle artifacts must not accidentally be captured as fixture content.
        require(all(not inside(path, self.source) for path in inputs[1:]),
                "binary/oracle inputs must be outside the source tree")
        records = None
        if args.records:
            records = checked_path(args.records, new=True)
            require(inside(records, temporary) and not overlaps(records, root)
                    and all(not overlaps(records, path) for path in inputs),
                    "external records must be below RUNNER_TEMP, outside root and input trees")
        mounts = mount_table()
        require(not any(inside(Path(m["mountpoint"]), root) for m in mounts),
                "output root overlaps an existing mount")
        for executable in ("bash", "sha256sum", "base64", "dd", "touch", "mount", "umount", "stat", "btrfs"):
            require(shutil.which(executable), "required command unavailable", executable=executable)
        require(self.command(["stat", "-f", "-c", "%T", root.parent]).strip() == "btrfs",
                "root parent must already be on synthetic Btrfs; no filesystem fallback")
        backing = [m for m in mounts if inside(root.parent, Path(m["mountpoint"]))]
        require(backing, "cannot identify existing Btrfs mount")
        backing.sort(key=lambda m: len(Path(m["mountpoint"]).parts), reverse=True)
        require(backing[0]["filesystem"] == "btrfs"
                and inside(Path(backing[0]["mountpoint"]), temporary),
                "the containing Btrfs mount itself must be under RUNNER_TEMP")
        measured_mount = Path(backing[0]["mountpoint"])
        measured_device = root.parent.stat().st_dev
        require(not inside(self.source, measured_mount)
                and self.source.stat().st_dev != measured_device,
                "source fixture must be external to the measured Btrfs filesystem")
        if records:
            require(not inside(records, measured_mount)
                    and records.parent.stat().st_dev != measured_device,
                    "external records must be outside the measured Btrfs filesystem")
        root.mkdir(mode=0o700)
        self.root = root
        self.library = root / "library"
        self.logs = root / "logs"
        self.logs.mkdir(mode=0o700)
        self.records = records or root / "steps.jsonl"
        # Atomic exclusive creation prevents overwriting any pre-existing ledger.
        with self.records.open("x") as ledger:
            # This new synthetic harness artifact contains no credentials and
            # must remain readable by the runner's non-root artifact uploader.
            os.fchmod(ledger.fileno(), 0o644)
        self.report.update({"root": str(root), "source": str(self.source), "binary": str(self.binary),
                            "recordsFile": str(self.records), "recordsIncludedInActiveSpace": records is None,
                            "containingFilesystem": backing[0], "oracleFiles": len(self.oracle),
                            "logicalBytes": sum(row["bytes"] for row in self.oracle),
                            "historyExpectedSteps": len(self.steps)})
        self.report["measurementNotes"].append(
            "Harness step JSONL is outside the measured filesystem by explicit --records selection."
            if records else "Harness step JSONL remains under root and is included in filesystem accounting.")
        self.event("sample_prepared", root=str(root), records=str(self.records))

    def check_fuse(self, daemon):
        mount = exact_mount(daemon["lower"])
        require(mount is not None and mount["filesystem"] == "fuse"
                and mount["source"] == "sprig-cas-prototype" and mount["root"] == "/"
                and "ro" in mount["mountOptions"]
                and mount["superOptions"].get("user_id") == "0"
                and "allow_other" not in mount["superOptions"],
                "lower mount does not match the approved root-only read-only FUSE binding")
        require(daemon["process"].poll() is None, "FUSE daemon exited while its mount is retained",
                name=daemon["name"], returncode=daemon["process"].returncode)
        return mount

    def start_fuse(self, name, lower, manifest):
        require(Path(manifest).name == manifest and manifest not in ("", ".", ".."),
                "manifest must be a single filename")
        checked_path(self.library / manifest)
        lower.mkdir(mode=0o700)
        log_path = self.logs / (name + "-fuse.jsonl")
        daemon = {"name": name, "lower": lower, "manifest": manifest, "log": log_path,
                  "process": None, "ready": False, "unmountAttempted": False}
        # Direct file logging must survive a busy-cleanup return from this
        # sampler. A parent-owned pipe tee could SIGPIPE a retained FUSE daemon
        # when the sampler exits. inotify gives event readiness without that
        # lifetime coupling, a polling sleep, or an extra logging daemon.
        libc = ctypes.CDLL(None, use_errno=True)
        libc.inotify_init1.argtypes = [ctypes.c_int]
        libc.inotify_init1.restype = ctypes.c_int
        libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        libc.inotify_add_watch.restype = ctypes.c_int
        watcher = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if watcher < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1 failed; no polling fallback")
        try:
            with log_path.open("x") as log:
                # IN_MODIFY | IN_CLOSE_WRITE | IN_DELETE_SELF | IN_MOVE_SELF.
                watch = libc.inotify_add_watch(watcher, os.fsencode(log_path), 0x2 | 0x8 | 0x400 | 0x800)
                if watch < 0:
                    raise OSError(ctypes.get_errno(), "inotify_add_watch failed; no polling fallback")
                process = subprocess.Popen([str(self.binary), "mount", "--root", str(self.library),
                                            "--mountpoint", str(lower), "--manifest", manifest],
                                           stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            daemon["process"] = process
            self.daemons.append(daemon)
            self.event("fuse_started", name=name, pid=process.pid, lower=str(lower), manifest=manifest)
            deadline = time.monotonic() + 60
            pending = b""
            initialized = False
            with selectors.DefaultSelector() as selector, log_path.open("rb") as events:
                selector.register(watcher, selectors.EVENT_READ)
                while not initialized:
                    pending += events.read()
                    lines = pending.split(b"\n")
                    pending = lines.pop()
                    for line in lines:
                        try:
                            record = json.loads(line)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue
                        if isinstance(record, dict) and record.get("event") == "fuse_initialized":
                            initialized = True
                    require(process.poll() is None, "FUSE exited before readiness", name=name,
                            returncode=process.returncode, log=str(log_path))
                    if initialized:
                        break
                    remaining = deadline - time.monotonic()
                    require(remaining > 0 and selector.select(timeout=max(0, remaining)),
                            "FUSE readiness timeout; mount/process retained for normal cleanup",
                            name=name, pid=process.pid, log=str(log_path))
                    while True:
                        try:
                            if not os.read(watcher, 65536):
                                break
                        except BlockingIOError:
                            break
        finally:
            os.close(watcher)
        self.check_fuse(daemon)
        require(stat.S_ISDIR(lower.stat().st_mode), "ready FUSE root is not a directory")
        daemon["ready"] = True
        self.event("fuse_ready", name=name, pid=process.pid, readiness="inotify_event_stream")
        return daemon

    def check_overlay(self, view):
        self.check_fuse(view["daemon"])
        mount = exact_mount(view["merged"])
        require(mount is not None and mount["filesystem"] == "overlay" and mount["root"] == "/",
                "view is not the expected OverlayFS mount")
        options = mount["superOptions"]
        require(options.get("lowerdir") == str(view["lower"])
                and options.get("upperdir") == str(view["upper"])
                and options.get("workdir") == str(view["work"])
                and "userxattr" not in options and "volatile" not in options
                and options.get("fsync") != "volatile",
                "OverlayFS binding/options differ from the requested private paths")
        # ovl_show_options can omit values equal to current module defaults.
        # Omission is not evidence of off: require stable observed defaults.
        current_defaults = self.overlay_defaults()
        for feature, expected in (("metacopy", "off"), ("index", "off"),
                                  ("nfs_export", "off"), ("redirect_dir", "on")):
            if feature in options:
                require(options[feature] == expected,
                        "OverlayFS reported contradictory feature option", feature=feature)
            else:
                value = "Y" if expected == "on" else "N"
                require(view["moduleDefaults"].get(feature) == value
                        and current_defaults.get(feature) == value,
                        "omitted OverlayFS option lacks stable default evidence", feature=feature)
        return mount

    @staticmethod
    def overlay_defaults():
        values = {}
        for feature in ("metacopy", "index", "nfs_export", "redirect_dir"):
            try:
                values[feature] = (Path("/sys/module/overlay/parameters") / feature).read_text().strip()
            except OSError:
                values[feature] = None
        return values

    def fork(self, name):
        directory = self.root / name
        directory.mkdir(mode=0o700)
        view = {"name": name, **{key: directory / key for key in ("lower", "upper", "work", "merged")},
                "unmountAttempted": False}
        self.views.append(view)
        for key in ("upper", "work", "merged"):
            view[key].mkdir(mode=0o700)
        source_stat = self.source.stat()
        view["upper"].chmod(stat.S_IMODE(source_stat.st_mode))
        os.utime(view["upper"], ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        view["daemon"] = self.start_fuse(name, view["lower"], "manifest.json")
        view["moduleDefaults"] = self.overlay_defaults()
        options = (f"lowerdir={view['lower']},upperdir={view['upper']},workdir={view['work']},"
                   + OVERLAY_FLAGS)
        # -i prohibits /sbin/mount.<type> helper fallback.
        self.command(["mount", "-i", "-t", "overlay", "overlay", "-o", options, view["merged"]])
        view["mountInfo"] = self.check_overlay(view)
        self.event("overlay_ready", name=name, requestedOptions=options, mountInfo=view["mountInfo"])
        return view

    def step_record(self, row):
        with self.records.open("a") as out:
            out.write(json.dumps(row, sort_keys=True) + "\n")
            out.flush()

    def retained_snapshot(self):
        return {"views": [{"name": view["name"], "mountInfo": self.check_overlay(view)}
                          for view in self.views],
                "foregroundFuseProcesses": [{"name": daemon["name"], "pid": daemon["process"].pid,
                                             "lower": str(daemon["lower"]),
                                             "mountInfo": self.check_fuse(daemon)}
                                            for daemon in self.daemons],
                "controlProcessesRunning": len(self.daemons),
                "historicalReadbacksStarted": False, "fileTreesRetained": True}

    def sample_space(self):
        active = self.retained_snapshot()
        self.report["lifecycle"]["activeAtSpace"] = active
        self.event("active_space_begin", lifecycle=active)
        # Do not dirty bookkeeping files between sync and the raw measurements.
        self.command(["btrfs", "filesystem", "sync", self.root], record_event=False)
        usage = self.command(["btrfs", "filesystem", "usage", "-b", self.root], record_event=False)
        groups = self.command(["btrfs", "filesystem", "df", "-b", self.root], record_event=False)
        self.report["activeSpace"] = {"filesystemUsedBytes": filesystem_used(usage),
                                      "usageRaw": usage, "groupsRaw": groups}
        self.retained_snapshot()  # Both processes and mounts must still be alive.
        self.event("active_space_complete", filesystemUsedBytes=filesystem_used(usage))

    def normal_unmount(self, path, owner):
        require(not self.cleanup_blocked, "cleanup already blocked; refusing a retry")
        if not exact_mount(path):
            return
        require(not owner["unmountAttempted"], "ordinary unmount already attempted; refusing retry")
        owner["unmountAttempted"] = True
        attempt = {"mountpoint": str(path), "argv": ["umount", "-i", str(path)], "ok": False}
        self.report["lifecycle"]["cleanup"]["attempts"].append(attempt)
        try:
            self.command(attempt["argv"])
            require(exact_mount(path) is None, "umount returned success but mount remains", path=str(path))
            attempt["ok"] = True
        except BaseException as error:
            self.cleanup_blocked = True
            attempt["error"] = str(error)
            raise

    def close_fuse(self, daemon):
        self.normal_unmount(daemon["lower"], daemon)
        require(exact_mount(daemon["lower"]) is None, "refusing to wait for a mounted FUSE session")
        try:
            code = daemon["process"].wait(timeout=15)
            require(code == 0, "FUSE session exited unsuccessfully", name=daemon["name"], returncode=code)
        except BaseException:
            self.cleanup_blocked = True
            raise
        self.event("fuse_exited", name=daemon["name"], returncode=code)

    def execute(self):
        start = time.perf_counter()
        inventory_source(self.source, self.oracle, mount_table())
        imported = self.cli("import", "--source", self.source)
        head = self.cli("head")  # Transaction::open lazily initializes history here.
        initial_manifest = (self.library / "manifest.json").read_bytes()
        self.report["import_seconds"] = time.perf_counter() - start
        require(imported.get("event") == "imported" and HEX64.fullmatch(head.get("head", "")),
                "unexpected import/head response")
        self.report["import"] = imported
        self.report["initialHead"] = head
        checks = full_checks(self.oracle)
        start = time.perf_counter()
        first = self.fork("first")
        self.report["first_fork_seconds"] = time.perf_counter() - start
        start = time.perf_counter()
        self.shell(first["merged"], checks)
        self.report["first_read_seconds"] = time.perf_counter() - start
        self.report["total_import_fork_read_seconds"] = sum(
            self.report[key] for key in ("import_seconds", "first_fork_seconds", "first_read_seconds"))
        start = time.perf_counter()
        second = self.fork("second")
        self.report["warm_fork_seconds"] = time.perf_counter() - start
        start = time.perf_counter()
        self.shell(second["merged"], checks)
        self.report["warm_read_seconds"] = time.perf_counter() - start
        self.report["warm_total_seconds"] = self.report["warm_fork_seconds"] + self.report["warm_read_seconds"]
        base, revisions = head["head"], set()
        for step in self.steps:
            start = time.perf_counter()
            self.shell(first["merged"], write_command(step))
            write_seconds = time.perf_counter() - start
            self.report["write_seconds"] += write_seconds
            start = time.perf_counter()
            checkpoint = self.cli("checkpoint", "--projection-base", "manifest.json", "--base", base,
                                  "--merged", first["merged"], "--upper", first["upper"],
                                  "--lower", first["lower"], "--message", "Frozen history step " + str(step["step"]))
            checkpoint_seconds = time.perf_counter() - start
            self.report["checkpoint_seconds"] += checkpoint_seconds
            require(checkpoint.get("event") == "checkpoint", "unexpected checkpoint response")
            publication = checkpoint["publication"]
            require(publication.get("status") in ("published", "noop"),
                    "linear history checkpoint conflicted or failed", publication=publication)
            previous = base
            base = publication["head"]["head"]  # Advance after EVERY published/noop result.
            row = {"step": step["step"], "revision": base, "base": previous,
                   "write_seconds": write_seconds, "checkpoint_seconds": checkpoint_seconds,
                   "status": publication["status"], "manifest": publication["manifest"],
                   "generation": publication["head"]["generation"], "checkpoint": checkpoint,
                   "changedFileReadback": False}
            self.report["checkpoint_steps"].append(row)
            # Preserve the acknowledged ID even when a subsequent oracle fails.
            self.step_record({"event": "checkpoint_acknowledged", **row})
            require(HEX64.fullmatch(base) and base != head["head"] and base not in revisions
                    and publication["status"] == "published" and not publication.get("merged"),
                    "history100 requires a distinct unmerged publication at every step", step=step["step"])
            revisions.add(base)
            self.report["history_distinct_revisions"] = len(revisions)
            self.shell(first["merged"], changed_check(step))
            row["changedFileReadback"] = True
            self.step_record({"event": "changed_file_verified", "step": step["step"], "revision": base})
        if self.steps:
            require(len(revisions) == 100, "history100 did not produce 100 distinct revisions")
            self.shell(first["merged"], full_checks(self.final))
        # Do NOT invoke CLI verify: its full capture writes objects and changes space.
        self.sample_space()
        history = self.cli("history")
        expected_ids = [row["revision"] for row in reversed(self.report["checkpoint_steps"])] + [head["head"]]
        require(isinstance(history, list) and [row["id"] for row in history] == expected_ids,
                "history is missing an acknowledged revision or is not the expected first-parent chain")
        by_id = {row["id"]: row for row in history}
        for index, revision in enumerate(history):
            require(revision["parents"] == (expected_ids[index + 1:index + 2]),
                    "unexpected revision parents", revision=revision["id"])
        current = {row["path"]: dict(row) for row in self.oracle}
        historical_root = self.root / "historical"
        historical_root.mkdir(mode=0o700)
        for step, row in zip(self.steps, self.report["checkpoint_steps"]):
            current[step["path"]]["sha256"] = step["sha256"]
            revision = by_id[row["revision"]]
            require(revision["manifest_file"] == row["manifest"], "checkpoint/history manifest mismatch")
            daemon = self.start_fuse("history-%03d" % step["step"],
                                     historical_root / ("step-%03d" % step["step"]), revision["manifest_file"])
            self.shell(daemon["lower"], full_checks(list(current.values())))
            self.report["fullHistoricalSnapshotReadbacks"] += 1
            self.step_record({"event": "historical_snapshot_verified", "step": step["step"],
                              "revision": row["revision"], "manifest": revision["manifest_file"]})
            self.close_fuse(daemon)
        require(self.report["fullHistoricalSnapshotReadbacks"] == len(self.steps),
                "not every historical snapshot received a full shell readback")
        # Original independent view and original projections stay unchanged.
        self.check_overlay(first)
        self.check_overlay(second)
        self.shell(second["merged"], checks)
        self.shell(first["lower"], checks)
        self.shell(self.source, checks)
        require((self.library / "manifest.json").read_bytes() == initial_manifest,
                "original projection manifest changed")
        self.report.update({"originalSecondViewUnchanged": True, "originalLowerUnchanged": True,
                            "sourceUnchanged": True, "initialManifestUnchanged": True,
                            "allAcknowledgedIdsPresent": True})
        self.report["ok"] = True

    def cleanup(self):
        if not self.root:
            return
        try:
            if not self.cleanup_blocked:
                # All overlays first, then any still-mounted lower sessions.
                for view in reversed(self.views):
                    self.normal_unmount(view["merged"], view)
                for daemon in reversed(self.daemons):
                    if daemon["process"].poll() is None or exact_mount(daemon["lower"]):
                        self.close_fuse(daemon)
        except BaseException as error:
            self.cleanup_blocked = True
            self.report.setdefault("cleanupErrors", []).append({"type": type(error).__name__, "message": str(error),
                                                                 "details": getattr(error, "details", {})})
        try:
            self.report["remainingMounts"] = [m for m in mount_table() if inside(Path(m["mountpoint"]), self.root)]
        except BaseException as error:
            self.report["remainingMounts"] = [{"inspectionError": str(error), "root": str(self.root)}]
            self.cleanup_blocked = True
        self.report["lifecycle"]["daemons"] = [
            {"name": daemon["name"], "pid": daemon["process"].pid, "lower": str(daemon["lower"]),
             "manifest": daemon["manifest"], "log": str(daemon["log"]), "ready": daemon["ready"],
             "returncode": daemon["process"].poll(), "running": daemon["process"].poll() is None}
            for daemon in self.daemons]
        alive = any(d["running"] for d in self.report["lifecycle"]["daemons"])
        complete = not self.cleanup_blocked and not self.report["remainingMounts"] and not alive
        self.report["lifecycle"]["cleanup"].update({"complete": complete, "blocked": self.cleanup_blocked,
                                                    "processesKilled": False, "forceOrLazyUnmountUsed": False})
        if not complete:
            self.report["ok"] = False

    def preserve_logs(self):
        """Return runtime evidence even after the caller tears down its image."""
        if not self.logs:
            return
        logs = []
        for path in sorted(self.logs.iterdir()):
            checked_path(path)
            size = path.stat().st_size
            limit = 128 * 1024
            with path.open("rb") as stream:
                data = stream.read(limit)
                if size > limit:
                    stream.seek(max(0, size - limit // 2))
                    data = data[:limit // 2] + b"\n[bounded log excerpt]\n" + stream.read(limit // 2)
            logs.append({"path": str(path), "bytes": size, "truncated": size > limit,
                         "text": data.decode("utf-8", errors="replace")})
        self.report["runtimeLogs"] = logs


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SampleError("invalid command line", error=message)


def main(argv=None):
    report = new_report()
    sample = Sample(report)
    try:
        parser = Parser(description=__doc__)
        sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        run = sub.add_parser("run")
        for name in ("root", "source", "oracle", "binary"):
            run.add_argument("--" + name, required=True)
        run.add_argument("--steps")
        run.add_argument("--records")
        args = parser.parse_args(argv)
        sample.prepare(args)
        sample.execute()
    except SystemExit as error:
        if error.code == 0:
            return 0  # --help is not a sample or an error.
        report["error"] = {"type": type(error).__name__, "message": str(error)}
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
            report.setdefault("cleanupErrors", []).append({"type": type(error).__name__, "message": str(error)})
            if sample.root:
                try:
                    report["remainingMounts"] = [m for m in mount_table()
                                                  if inside(Path(m["mountpoint"]), sample.root)]
                except BaseException as inspection:
                    report["remainingMounts"] = [{"inspectionError": str(inspection)}]
    if sample.root:
        try:
            (sample.root / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        except BaseException as error:
            report["ok"] = False
            report["reportWriteError"] = str(error)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
