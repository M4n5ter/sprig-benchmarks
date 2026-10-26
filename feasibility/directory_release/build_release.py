#!/usr/bin/env python3
"""Frozen remote release builder. Preparation is inert; execution needs explicit pins.

Linux/Python 3.10+, Git and actual Cargo/rustc binaries are required. This helper
never installs toolchains, fetches source, deletes caches/evidence, or dispatches
work. The workflow must create the common clock BEFORE checkout and setup.
"""

import argparse
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import time


VARIANTS = ("baseline", "count", "narrow")
PINNED = {
    "baseline": "4eb0f4d7afdb19bf22d9667dc520ede8b162c737",
    "count": "104497aefcadc41b1528d7263039c977b77305f8",
}
MODULES = ("writable_directory_benchmark.rs", "writable_directory_lifecycle_benchmark.rs")
EXPECTED_SUFFIX = ("\n#[cfg(test)]\n#[path = \"writable_directory_benchmark.rs\"]\n"
                   "mod directory_benchmark;\n\n#[cfg(test)]\n"
                   "#[path = \"writable_directory_lifecycle_benchmark.rs\"]\n"
                   "mod directory_lifecycle_benchmark;\n")
LIVE_GENERATIONS = frozenset(("create-oracle", "replay-history",
    "directory-create", "directory-remove", "directory-rename-same-parent",
    "directory-rename-cross-parent", "directory-overwrite", "directory-subtree-rename",
    "file-create", "file-hardlink", *(f"create-{index:02}" for index in range(8))))
LIMITS = {"jobSeconds": 2700, "admissionSeconds": 2400,
          "processSeconds": 120,
          "cleanupReserveSeconds": 10, "finalizeReserveSeconds": 60,
          "minimumFreeBytes": 1536 * 1024**2, "maximumEvidenceBytes": 1024**3,
          "evidenceFinalizeReserveBytes": 8 * 1024**2,
          "maximumReportBytes": 1024**2, "cargoBuildJobs": 2}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def regular(path, single_link=False):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), f"not a regular non-symlink file: {path}")
    require(not single_link or info.st_nlink == 1, f"shared hardlink forbidden: {path}")
    return info


def safe_path(value, root=None, exists=True):
    path = Path(value).absolute()
    require(path.resolve(strict=exists) == path, f"symlink/noncanonical path: {path}")
    if root is not None:
        require(path != root and path.is_relative_to(root), f"outside owned root: {path}")
    return path


def make_dir(path, root, fresh=False):
    safe_path(path, root, exists=False)
    path.mkdir(parents=True, exist_ok=not fresh)
    require(path.is_dir(), f"not a directory: {path}")
    return path


def evidence_size(root, live_cleanup_root=None):
    """Strict complete audit by default; narrowly tolerate live owned cleanup.

    Only ENOENT below the active lifecycle fixture's disposable generation
    names may disappear between enumeration and lstat/scandir. Objects, logs,
    reports, receipts, other samples and all unsafe entry types stay strict.
    """
    root = Path(root)
    if live_cleanup_root is not None:
        live_cleanup_root = safe_path(live_cleanup_root, root, exists=False)
        require(live_cleanup_root.name == "fixture" and
                live_cleanup_root.parent.parent == root / "release-core",
                "live cleanup scope must be one owned sample fixture")

    def disappearing(error, path):
        if not isinstance(error, FileNotFoundError) or error.errno != errno.ENOENT or live_cleanup_root is None:
            return False
        try:
            relative = Path(path).relative_to(live_cleanup_root)
        except ValueError:
            return False
        return bool(relative.parts) and relative.parts[0] in LIVE_GENERATIONS

    def inspect(path, directory):
        try:
            info = path.lstat()
        except FileNotFoundError as error:
            if disappearing(error, path):
                return None
            raise
        require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
                f"unsafe non-{'directory' if directory else 'regular'} evidence entry: {path}")
        require(directory or info.st_nlink == 1, f"shared hardlink forbidden: {path}")
        return info

    def walk_error(error):
        if not disappearing(error, error.filename):
            raise error

    inspect(root, True)
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        info = inspect(Path(directory), True)
        if info is None:
            dirs[:] = []
            continue
        total += info.st_blocks * 512
        for name in list(dirs):
            if inspect(Path(directory) / name, True) is None:
                dirs.remove(name)
        for name in files:
            info = inspect(Path(directory) / name, False)
            if info is None:
                continue
            # Bound both filesystem usage and uncompressed artifact content;
            # sparse files must not evade the complete-evidence cap.
            total += max(info.st_size, info.st_blocks * 512)
    return total


def validate_manifest(manifest, helper_sha):
    require(manifest.get("schema") == "sprig-directory-counts-release-manifest-v1", "wrong manifest schema")
    require(manifest.get("approvedForExecution") is True, "manifest not approved for execution")
    require(manifest.get("runnerSha256", {}).get("build_release.py") == helper_sha,
            "build helper differs from frozen manifest")
    require(set(manifest.get("variants", {})) == set(VARIANTS), "require all three variants")
    for name in VARIANTS:
        item = manifest["variants"][name]
        commit = item.get("productionCommit")
        require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit), f"unresolved {name} pin")
        if name in PINNED:
            require(commit == PINNED[name], f"unexpected {name} production pin")
        tests = item.get("expectedTests")
        require(isinstance(tests, list) and tests and all(isinstance(x, str) and x for x in tests),
                f"unresolved {name} test inventory")
        require(tests == sorted(set(tests)), f"inventory must be sorted and unique: {name}")
        for test in ("writable::directory_benchmark::ordinary_directory_attribute_pressure",
                     "writable::directory_lifecycle_benchmark::ordinary_directory_lifecycle_pressure"):
            require(test in tests, f"missing instrumented test: {name}")
    require(len({x["productionCommit"] for x in manifest["variants"].values()}) == 3, "duplicate production pins")
    requested = manifest.get("toolchain", {}).get("requested")
    require(isinstance(requested, str) and re.fullmatch(r"\d+\.\d+\.\d+", requested),
            "toolchain.requested must be an exact stable x.y.z release, not stable/latest/pending")
    require(manifest["toolchain"].get("requireSameExactCompiler") is True, "same compiler proof is mandatory")
    for key, expected in LIMITS.items():
        require(manifest.get("limits", {}).get(key) == expected, f"unexpected resource limit: {key}")
    require(set(manifest.get("instrumentationSha256", {})) == set(MODULES), "unexpected instrumentation files")
    require(set(manifest.get("instrumentationFiles", {})) == set(MODULES), "missing module payload map")
    require(manifest.get("moduleSuffix") == EXPECTED_SUFFIX, "append-only suffix differs")
    require(manifest.get("appendOnlySuffixSha256") == sha_bytes(EXPECTED_SUFFIX.encode()), "suffix hash differs")


class Budget:
    def __init__(self, clock_path, work, evidence, limits):
        self.work, self.evidence, self.limits = work, evidence, limits
        self.clock = json.loads(clock_path.read_text())
        self.clock_sha = digest(clock_path)
        self.clock_path = clock_path
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        start = self.clock.get("startedMonotonic")
        require(self.clock.get("bootId") == boot, "global clock comes from another boot")
        require(isinstance(start, (float, int)) and not isinstance(start, bool) and math.isfinite(start), "invalid start clock")
        require(0 <= start <= time.monotonic(), "invalid/future setup clock")
        self.deadline = start + limits["admissionSeconds"]
        self.command_deadline = self.deadline - limits["cleanupReserveSeconds"] - limits["finalizeReserveSeconds"]
        self.minimum_free = shutil.disk_usage(work).free
        self.maximum_evidence = 0
        self.commands = []
        self.check()

    def check(self, extra=0, final=False, live_cleanup_root=None):
        require(digest(self.clock_path) == self.clock_sha, "common setup clock changed")
        free = shutil.disk_usage(self.work).free
        self.minimum_free = min(self.minimum_free, free)
        require(free >= self.limits["minimumFreeBytes"] + extra, "disk floor / pending write reservation exhausted")
        require(not final or live_cleanup_root is None, "final accounting must be strict")
        size = evidence_size(self.evidence, live_cleanup_root=live_cleanup_root)
        self.maximum_evidence = max(self.maximum_evidence, size)
        reserve = 0 if final else self.limits["evidenceFinalizeReserveBytes"]
        require(size + extra <= self.limits["maximumEvidenceBytes"] - reserve, "evidence cap / finalization reserve exhausted")
        deadline = self.deadline if final else self.command_deadline
        require(time.monotonic() < deadline, "setup-inclusive global time budget exhausted")

    def snapshot(self):
        return {"clock": self.clock, "clockSha256": self.clock_sha,
                "deadlineMonotonic": self.deadline, "commandDeadlineMonotonic": self.command_deadline,
                "elapsedSinceSetupSeconds": time.monotonic() - self.clock["startedMonotonic"],
                "minObservedFreeBytes": self.minimum_free,
                "evidenceBytes": evidence_size(self.evidence), "maximumObservedEvidenceBytes": self.maximum_evidence,
                "commands": self.commands}


def group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def settle(process):
    # Only signal this helper's new-session process group, never global names.
    if group_exists(process.pid):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    end = time.monotonic() + 4
    while group_exists(process.pid) and time.monotonic() < end:
        process.poll()
        time.sleep(0.05)
    if group_exists(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=2)
    end = time.monotonic() + 2
    while group_exists(process.pid) and time.monotonic() < end:
        time.sleep(0.05)
    return not group_exists(process.pid)


def check_log_quota(retained_bytes, incoming_bytes, maximum_bytes):
    require(maximum_bytes is None or retained_bytes + incoming_bytes <= maximum_bytes,
            "bounded subprocess log capture overflow")


def command(argv, cwd, env, log, budget, seconds=None, maximum_log_bytes=None, live_cleanup_root=None):
    """Drain bounded pipes ourselves so a subprocess cannot overrun evidence cap."""
    budget.check()
    started = time.monotonic()
    deadline = min(budget.command_deadline, started + seconds) if seconds else budget.command_deadline
    record = {"argv": argv, "cwd": str(cwd), "logPath": str(log), "startedMonotonic": started}
    budget.commands.append(record)
    error = None
    process = None
    retained_bytes = 0
    with log.open("xb") as stream, selectors.DefaultSelector() as selector:
        try:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                active_cleanup = live_cleanup_root if process.poll() is None else None
                budget.check(live_cleanup_root=active_cleanup)
                require(time.monotonic() < deadline, "command deadline exhausted")
                for key, _ in selector.select(timeout=0.2):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    check_log_quota(retained_bytes, len(data), maximum_log_bytes)
                    active_cleanup = live_cleanup_root if process.poll() is None else None
                    budget.check(extra=len(data), live_cleanup_root=active_cleanup)
                    stream.write(data)
                    stream.flush()
                    retained_bytes += len(data)
            process.wait(timeout=max(0.01, min(2, deadline - time.monotonic())))
            require(not group_exists(process.pid), "command returned with live owned descendants")
            require(process.returncode == 0, f"command exited {process.returncode}")
        except BaseException as caught:
            error = caught
        finally:
            if process is not None:
                record["settled"] = settle(process)
                record["returncode"] = process.returncode
                if process.stdout is not None:
                    process.stdout.close()
                if not record["settled"]:
                    error = RuntimeError("owned process-group settlement uncertain")
            record["seconds"] = time.monotonic() - started
            record["retainedLogBytes"] = retained_bytes
            record["maximumLogBytes"] = maximum_log_bytes
    record["logSha256"] = digest(log)
    if error is not None:
        record["error"] = f"{type(error).__name__}: {error}"
        raise error
    budget.check()
    return log.read_bytes()


def verify_inventory(text, expected):
    lines = text.splitlines()
    actual = sorted(line[:-6] for line in lines if line.endswith(": test"))
    unknown = [line for line in lines if line and not line.endswith(": test")
               and not re.fullmatch(r"\d+ tests?, \d+ benchmarks?", line)]
    return {"passed": actual == expected and not unknown,
            "actualNames": actual, "expectedNames": expected, "unknownLines": unknown}


def write_checked_json(path, data, check, stage_name, maximum_bytes=None):
    """Stage complete bytes, check their actual footprint, then atomically publish.

    No resource gate follows publication: replacing an existing same-directory
    file adds no payload beyond the already charged complete stage.
    """
    encoded = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
    require(maximum_bytes is None or len(encoded) <= maximum_bytes, "receipt exceeds report size")
    stage = path.with_name(stage_name)
    require(not stage.exists(), "staged receipt already exists; retain it as evidence")
    check(extra=((len(encoded)+4095)//4096)*4096+4096)
    with stage.open("xb") as stream:
        stream.write(encoded)
    stage.chmod(0o444)
    check()
    os.replace(stage, path)


def checked_publish(path, data, ready, check, maximum_bytes=None):
    """Canonical FAIL first; checked staged PASS is the final publication op."""
    data["ok"] = False
    if "complete" in data:
        data["complete"] = False
    negative_stage = path.name + ".final-negative-pending"
    pass_stage = path.name + ".pass-pending"
    try:
        write_checked_json(path, data, check, negative_stage, maximum_bytes)
        if not ready:
            return False
        candidate = dict(data, ok=True)
        if "complete" in candidate:
            candidate["complete"] = True
        write_checked_json(path, candidate, check, pass_stage, maximum_bytes)
        data["ok"] = True
        if "complete" in data:
            data["complete"] = True
        return True
    except BaseException as error:
        data["ok"] = False
        if "complete" in data:
            data["complete"] = False
        data["finalizationError"] = f"{type(error).__name__}: {error}"
        # A signal exactly after atomic promotion must not leave PASS when this
        # handler reports failure. Move only this new receipt, never old evidence.
        try:
            if path.exists() and json.loads(path.read_text()).get("ok") is True:
                os.replace(path, path.with_name(path.name + ".rejected-pass"))
            pending = path.with_name(pass_stage)
            if pending.exists():
                os.replace(pending, path.with_name(path.name + ".rejected-pass-stage"))
            write_checked_json(path, data, check, path.name + ".failure-pending", maximum_bytes)
        except BaseException as recovery_error:
            data["failureReceiptError"] = f"{type(recovery_error).__name__}: {recovery_error}"
        return False


def verify_artifact(artifact, source, target, instrumented_ns):
    binary = safe_path(artifact["executable"], target)
    regular(binary, single_link=True)
    dep = binary.with_suffix(".d")
    regular(dep, single_link=True)
    profile = artifact.get("profile", {})
    dep_text = dep.read_text()
    expected_env = f"# env-dep:CARGO_MANIFEST_DIR={source}"
    env_lines = [line for line in dep_text.splitlines() if line.startswith("# env-dep:CARGO_MANIFEST_DIR=")]
    require(artifact.get("fresh") is False, "root compiler artifact was fresh")
    require(artifact.get("manifest_path") == str(source / "Cargo.toml"), "wrong root manifest")
    require(artifact.get("target", {}).get("src_path") == str(source / "src/lib.rs"), "wrong root lib source")
    require(artifact.get("target", {}).get("name") == "sprig", "wrong root crate")
    require(profile.get("opt_level") == "3" and profile.get("debug_assertions") is False
            and profile.get("overflow_checks") is False and profile.get("test") is True,
            "root is not ordinary release opt3/no-assertions/no-overflow test profile")
    require(env_lines == [expected_env], "dep-info has wrong/ambiguous exact source directory")
    for path in ("src/writable.rs", *("src/" + x for x in MODULES)):
        require(path in dep_text, f"dep-info missing instrumented source {path}")
    require(binary.stat().st_mtime_ns >= instrumented_ns and dep.stat().st_mtime_ns >= instrumented_ns,
            "artifact/dep-info predates instrumentation")
    with binary.open("rb") as stream:
        require(stream.read(4) == b"\x7fELF", "root artifact is not ELF")
    return {"passed": True, "compilerArtifact": artifact, "depInfoSourcePath": str(dep),
            "depInfoSha256": digest(dep), "manifestEnvLines": env_lines,
            "instrumentedMtimeNs": instrumented_ns, "binaryMtimeNs": binary.stat().st_mtime_ns,
            "depInfoMtimeNs": dep.stat().st_mtime_ns}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    for arg in ("manifest", "manifest-sha256", "source", "work-root", "evidence-root", "clock-json", "cargo", "rustc"):
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    work = safe_path(args.work_root)
    require(work.is_dir() and str(work) not in ("/", "/tmp", "/home", "/workspace"), "specific owned work root required")
    evidence = safe_path(args.evidence_root, work)
    require(evidence.is_dir(), "workflow must create evidence root")
    source = safe_path(args.source, work)
    require(not source.is_relative_to(evidence) and not evidence.is_relative_to(source), "source/evidence overlap")
    manifest_path = safe_path(args.manifest)
    regular(manifest_path)
    manifest_sha = digest(manifest_path)
    require(manifest_sha == args.manifest_sha256, "manifest hash differs from workflow pin")
    manifest = json.loads(manifest_path.read_text())
    validate_manifest(manifest, digest(Path(__file__).resolve()))
    clock_path = safe_path(args.clock_json)
    regular(clock_path)
    budget = Budget(clock_path, work, evidence, manifest["limits"])
    receipt_dir = make_dir(evidence / "build-receipts", work)
    receipt_path = receipt_dir / (args.variant + ".json")
    require(not receipt_path.exists(), "immutable receipt already exists; no retry-overwrite")
    output = make_dir(evidence / "builds" / args.variant, work, fresh=True)
    receipt = {"schema": "sprig-release-build-receipt-v1", "ok": False,
               "variant": args.variant, "productionCommit": manifest["variants"][args.variant]["productionCommit"],
               "manifestSha256": manifest_sha, "helperSha256": digest(Path(__file__).resolve()),
               "binary": None, "rootArtifact": None, "inventory": None, "source": {"path": str(source)}}
    # Explicit nonblocking lock: build variants are serial, never silently wait
    # while someone else consumes the setup-inclusive deadline or target space.
    lock_path = work / "release-helper.lock"
    if lock_path.exists():
        regular(lock_path, single_link=True)
    lock = lock_path.open("a+b")
    computations_complete = False
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        home = make_dir(work / "helper-home", work)
        cargo_home = make_dir(work / "cargo-home", work)
        tmp = make_dir(work / "tmp" / args.variant, work, fresh=True)
        target = make_dir(work / "targets" / args.variant, work, fresh=True)
        receipt["targetPath"] = str(target)
        # Use real binaries, not rustup proxies that may install a toolchain or
        # write to an unrelated home. The workflow installs/pins them first.
        cargo = Path(args.cargo).resolve(strict=True)
        rustc = Path(args.rustc).resolve(strict=True)
        require(cargo.name == "cargo" and rustc.name == "rustc" and cargo != rustc, "pass actual cargo/rustc, not rustup proxy")
        require(cargo.parent == rustc.parent, "cargo/rustc must come from one installed toolchain")
        regular(cargo)
        regular(rustc)
        # No inherited RUSTFLAGS, wrappers, profile overrides, Cargo config,
        # credentials, or target directory can alter the experiment.
        env = {"PATH": str(cargo.parent) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
               "HOME": str(home), "CARGO_HOME": str(cargo_home), "TMPDIR": str(tmp),
               "TMP": str(tmp), "TEMP": str(tmp), "LC_ALL": "C", "LANG": "C",
               "RUSTC": str(rustc), "CARGO_TARGET_DIR": str(target), "CARGO_BUILD_JOBS": "2",
               "CARGO_INCREMENTAL": "0", "CARGO_TERM_COLOR": "never", "GIT_OPTIONAL_LOCKS": "0",
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
        for directory in (source, *source.parents):
            for filename in ("config", "config.toml"):
                require(not (directory / ".cargo" / filename).exists(), f"unreviewed Cargo config: {directory}")
        for filename in ("config", "config.toml"):
            require(not (cargo_home / filename).exists(), "unreviewed CARGO_HOME config")
        counter = 0

        def run(argv, label, seconds=15):
            nonlocal counter
            counter += 1
            return command(argv, source, env, output / f"{counter:02d}-{label}.log", budget, seconds)

        git = shutil.which("git", path=env["PATH"])
        require(git is not None, "git unavailable")

        def git_read(*arguments):
            return run([git, *arguments], "git")

        require(Path(git_read("rev-parse", "--show-toplevel").decode().strip()) == source, "source is not checkout root")
        head = git_read("rev-parse", "HEAD").decode().strip()
        require(head == receipt["productionCommit"], "checkout differs from exact production commit")
        require(not git_read("status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching"),
                "source is dirty or contains ignored files before instrumentation")
        tracked = git_read("ls-files", "-z").decode().rstrip("\0").split("\0")
        require(tracked and all(x and "\n" not in x for x in tracked), "invalid tracked paths")
        before = {}
        for name in tracked:
            path = safe_path(source / name, source)
            regular(path, single_link=True)
            before[name] = digest(path)
        receipt["source"].update(head=head, beforeHashes=before)
        original = git_read("show", "HEAD:src/writable.rs")
        require((source / "src/writable.rs").read_bytes() == original, "production writable.rs differs from Git blob")
        suffix_path = safe_path(manifest_path.parent / "writable-test-suffix.txt", manifest_path.parent)
        require(suffix_path.read_bytes() == EXPECTED_SUFFIX.encode(), "suffix payload differs")
        for name in MODULES:
            payload = safe_path(manifest_path.parent / manifest["instrumentationFiles"][name], manifest_path.parent)
            regular(payload)
            require(digest(payload) == manifest["instrumentationSha256"][name], f"module payload differs: {name}")
            destination = source / "src" / name
            require(not destination.exists(), f"module already present: {name}")
            with destination.open("xb") as stream:
                stream.write(payload.read_bytes())
        with (source / "src/writable.rs").open("ab") as stream:
            stream.write(EXPECTED_SUFFIX.encode())
        instrumented_ns = max((source / "src" / x).stat().st_mtime_ns for x in ("writable.rs", *MODULES))

        def verify_source():
            require(git_read("rev-parse", "HEAD").decode().strip() == head, "source HEAD changed")
            require((source / "src/writable.rs").read_bytes() == original + EXPECTED_SUFFIX.encode(), "non-append source mutation")
            require(git_read("diff", "--cached", "--name-only", "-z") == b"", "staged source changed")
            changed = git_read("diff", "--name-only", "-z").decode().rstrip("\0").split("\0")
            require(changed == ["src/writable.rs"], "unexpected tracked source diff")
            wanted_status = {" M src/writable.rs", *("?? src/" + x for x in MODULES)}
            actual_status = set(git_read("status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching").decode().splitlines())
            require(actual_status == wanted_status, "post-instrumentation diff is not exactly two modules plus suffix")
            after = {}
            for name in (*tracked, *("src/" + x for x in MODULES)):
                path = safe_path(source / name, source)
                regular(path, single_link=True)
                after[name] = digest(path)
                if name in before and name != "src/writable.rs":
                    require(after[name] == before[name], f"production source changed: {name}")
            for name in MODULES:
                require(after["src/" + name] == manifest["instrumentationSha256"][name], "instrumentation changed")
            return after

        receipt["source"].update(afterHashes=verify_source(), appendOnly=True,
                                  instrumentationSha256=manifest["instrumentationSha256"])
        toolchain = {}
        for name, executable in (("cargo", cargo), ("rustc", rustc)):
            version = run([str(executable), "-Vv"], name + "-version").decode()
            first = version.splitlines()[0]
            require(first.startswith(name + " " + manifest["toolchain"]["requested"] + " "), f"wrong requested {name} version")
            toolchain[name] = {"path": str(executable), "sha256": digest(executable),
                               "version": version, "versionSha256": sha_bytes(version.encode())}
        receipt["toolchain"] = toolchain
        for other_name in VARIANTS:
            other_path = receipt_dir / (other_name + ".json")
            if other_path.exists():
                other = json.loads(other_path.read_text())
                require(other.get("ok") is True and other.get("manifestSha256") == manifest_sha, "prior build is failed or from another manifest")
                require(other.get("budget", {}).get("clockSha256") == budget.clock_sha, "prior build reset the global clock")
                old_binary = safe_path(other["binary"]["path"], evidence)
                old_stat = regular(old_binary, single_link=True)
                require(stat.S_IMODE(old_stat.st_mode) == 0o555 and digest(old_binary) == other["binary"]["sha256"],
                        "prior immutable ELF changed")
                for name in ("cargo", "rustc"):
                    for key in ("sha256", "versionSha256"):
                        require(other["toolchain"][name][key] == toolchain[name][key], "variants use different exact toolchains")
        argv = [str(cargo), "test", "--release", "--locked", "--features", "projection",
                "--lib", "--no-run", "--message-format=json", "--verbose"]
        raw = run(argv, "cargo-release", seconds=None)
        artifacts = []
        build_finished = []
        for line in raw.decode(errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("reason") == "build-finished":
                build_finished.append(item.get("success"))
            if item.get("reason") == "compiler-artifact" and item.get("target", {}).get("name") == "sprig" and item.get("executable"):
                artifacts.append(item)
        require(build_finished == [True] and len(artifacts) == 1, "missing/ambiguous root executable or completed Cargo build")
        proof = verify_artifact(artifacts[0], source, target, instrumented_ns)
        receipt["rootArtifact"] = proof
        dep_copy = output / "root.d"
        dep_data = Path(proof["depInfoSourcePath"]).read_bytes()
        budget.check(extra=len(dep_data))
        with dep_copy.open("xb") as stream:
            stream.write(dep_data)
        proof["depInfoPath"] = str(dep_copy)
        require(digest(dep_copy) == proof["depInfoSha256"], "retained dep-info differs")
        built = Path(artifacts[0]["executable"])
        binary = output / (args.variant + "-release.elf")
        before_binary = digest(built)
        budget.check(extra=built.stat().st_size)
        with built.open("rb") as src, binary.open("xb") as dst:
            shutil.copyfileobj(src, dst)
        binary.chmod(0o555)
        require(digest(binary) == before_binary == digest(built), "ELF changed during immutable copy")
        receipt["binary"] = {"path": str(binary), "sha256": before_binary,
                             "bytes": binary.stat().st_size, "mode": "0555"}
        for other_name in VARIANTS:
            other_path = receipt_dir / (other_name + ".json")
            if other_path.exists():
                other = json.loads(other_path.read_text())
                require(other["binary"]["sha256"] != before_binary, "different variants produced identical ELF hashes")
        listing = run([str(binary), "--list", "--format", "terse"], "inventory", seconds=10)
        inventory = verify_inventory(listing.decode(), manifest["variants"][args.variant]["expectedTests"])
        inventory.update(logPath=budget.commands[-1]["logPath"], logSha256=budget.commands[-1]["logSha256"])
        receipt["inventory"] = inventory
        require(inventory["passed"], "embedded exact test inventory differs")
        require(digest(binary) == before_binary, "retained ELF changed during inventory")
        receipt["source"]["afterHashes"] = verify_source()
        require(digest(manifest_path) == manifest_sha, "frozen manifest changed")
        for name, executable in (("cargo", cargo), ("rustc", rustc)):
            require(digest(executable) == toolchain[name]["sha256"], "toolchain binary changed during build")
        budget.check()
        computations_complete = True
    except BaseException as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
    finally:
        # Negative records are never removed. Refuse output reuse on all reruns.
        receipt["budget"] = budget.snapshot()
        checked_publish(receipt_path, receipt, computations_complete,
                        lambda extra=0: budget.check(extra=extra, final=True),
                        manifest["limits"]["maximumReportBytes"])
        lock.close()
    print(json.dumps({"ok": receipt["ok"], "receiptPath": str(receipt_path),
                      "receiptSha256": digest(receipt_path) if receipt_path.exists() else None,
                      "error": receipt.get("error") or receipt.get("finalizationError")}))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
