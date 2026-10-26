#!/usr/bin/env python3
"""Read-only provenance/encoder-output gates; never invokes a LayerFS product.

Only subprocesses are read-only git identity queries. The original README's
unexecuted no-default-features proposal is superseded by the daemon closure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import subprocess
import sys

SOURCE_PIN = "ad78914e36b258b360daf13aec164b5655814689"
MANIFEST_SHA = "848a841b0876047630cbb2cdd86b49d38aead07577f31b8acc0acad0145147a6"
MANIFEST_COUNT = 1552
INPUT_HASHES = {
    "README.md": "f2c2abc59c4d24a39b0ad29f1e1e0fd7809a37455246b2d2d4cc3107a07d0aef",
    "prepare_fixture.py": "68ce314b745a935dccad7153a2f128553308211fa4d8602ab7705ec7426bb922",
    "fixture.rs": "296d89a322132f90eefe4ad92dd8ae62682982b2297e613f1de093d6d37e820b",
    "model.json": "e47e4cbfa1bb14fcbe0b3d8498a459512c3c53cea0d6204bed1a3f21bdcb1e55",
    "proof.rs": "5221a3ddc7a06b9518cfc906efd46ac7b4627a6745970c0328db7d2528ca6473",
}
BUILD_COMMAND = [
    "cargo", "+1.85.1", "build", "--manifest-path", "core/Cargo.toml",
    "--locked", "--offline", "--release", "-p", "layerfs-daemon",
    "--message-format=json", "-vv",
]
EXPECTED_SIZES = [71643, 71690, 71690, 71737, 71690, 71737, 71737, 71784]
MIB = 1024 * 1024
LOG_CAP = 32 * MIB
RECEIPT_CAP = 2 * MIB
PROOF_LOG_CAP = MIB
FINAL_LINE = ("proof=passed source_identity=external_preflight_required "
              "captured_daemon_receipt=false mounted_run=false")
RUSTC_VERSION = ("rustc 1.85.1 (4eb161250 2025-03-15)\n"
                 "binary: rustc\n"
                 "commit-hash: 4eb161250e340c8f48f66e2b929ef4a5bed7c181\n"
                 "commit-date: 2025-03-15\n"
                 "host: x86_64-unknown-linux-gnu\n"
                 "release: 1.85.1\n"
                 "LLVM version: 19.1.7\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(path, directory=False):
    path = Path(os.path.abspath(path))
    require(path.resolve(strict=True) == path, f"symlink/noncanonical path: {path}")
    mode = path.stat().st_mode
    require(stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode),
            f"wrong file type: {path}")
    return path


def file_record(path, cap=None):
    path = canonical(path)
    before = path.stat()
    require(cap is None or before.st_size <= cap, f"file exceeds acceptance cap: {path}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(MIB):
            size += len(chunk)
            require(cap is None or size <= cap, f"file grew beyond cap: {path}")
            digest.update(chunk)
    after = path.stat()
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(identity(before) == identity(after) and size == before.st_size,
            f"file changed during hash: {path}")
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def read_bounded(path, cap):
    record = file_record(path, cap)
    with Path(record["path"]).open("rb") as stream:
        data = stream.read(cap + 1)
    require(len(data) <= cap, "file grew beyond read cap")
    require(len(data) == record["bytes"] and hashlib.sha256(data).hexdigest() == record["sha256"],
            "file changed during read")
    return data, record


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data):
    return json.loads(data, object_pairs_hook=no_duplicate_keys,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def read_json(path, cap=RECEIPT_CAP):
    data, record = read_bounded(path, cap)
    return parse_json(data), record


def git_identity(source):
    def query(*args):
        result = subprocess.run(["git", "-C", str(source), *args], check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=30, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        require(len(result.stdout) <= MIB and len(result.stderr) <= MIB, "git output cap")
        return result.stdout.decode("utf-8")
    require(query("rev-parse", "--show-toplevel").strip() == str(source), "wrong source root")
    require(query("rev-parse", "HEAD").strip() == SOURCE_PIN, "wrong source pin")
    require(query("status", "--porcelain", "--untracked-files=all") == "", "source is dirty")
    return SOURCE_PIN


def manifest_entries(data):
    entries = []
    seen = set()
    for line in data.decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, "invalid source manifest line")
        digest, name = match.groups()
        path = PurePosixPath(name)
        require(not path.is_absolute() and path.as_posix() == name and
                all(part not in (".", "..") for part in path.parts), "unsafe manifest path")
        require(name not in seen, "duplicate source manifest member")
        seen.add(name)
        entries.append((name, digest))
    require(len(entries) == MANIFEST_COUNT, "wrong source manifest count")
    return entries


def source_snapshot(source, manifest):
    source = canonical(source, directory=True)
    git_identity(source)
    data, record = read_bounded(manifest, RECEIPT_CAP)
    require(record["sha256"] == MANIFEST_SHA, "wrong captured source manifest")
    total = 0
    for name, expected in manifest_entries(data):
        actual = file_record(source / name)
        require(actual["sha256"] == expected, f"source differs: {name}")
        total += actual["bytes"]
    git_identity(source)
    return {"root": str(source), "head": SOURCE_PIN, "manifest": record,
            "files": MANIFEST_COUNT, "bytes": total}


def input_snapshot(inputs):
    inputs = canonical(inputs, directory=True)
    records = {}
    for name, expected in INPUT_HASHES.items():
        actual = file_record(inputs / name, RECEIPT_CAP)
        require(actual["sha256"] == expected, f"changed frozen input: {name}")
        records[name] = actual
    model, _ = read_json(inputs / "model.json")
    validate_model(model)
    return {"root": str(inputs), "files": records}


def validate_model(model):
    require(model["schema"] == "layerfs-source-only-encoder-model-v1" and
            model["sourcePin"] == SOURCE_PIN and model["sourceManifestSha256"] == MANIFEST_SHA,
            "wrong model identity")
    require(model["actualEncoderExecuted"] is False and model["capturedDaemonReply"] is False
            and model["mountedRerun"] is False, "model must remain historical/inert")
    require(model["fixtureRustSha256"] == INPUT_HASHES["fixture.rs"], "fixture/model mismatch")
    require(len(model["cases"]) == 8, "wrong model case count")
    for index, case in enumerate(model["cases"]):
        require(type(case["observedMask"]) is int and case["observedMask"] == index and
                type(case["predictedSubsetAnswerBytes"]) is int and
                case["predictedSubsetAnswerBytes"] == EXPECTED_SIZES[index] and
                case["controlLimitBytes"] == 65519, "changed model case")


def target_identity(target):
    target = canonical(target, directory=True)
    info = target.stat()
    return {"path": str(target), "device": info.st_dev, "inode": info.st_ino}


def check_environment(target):
    rejected = {"RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "RUSTC_WRAPPER",
                "RUSTC_WORKSPACE_WRAPPER", "RUSTC", "RUSTDOC", "CARGO_BUILD_TARGET",
                "CARGO_BUILD_RUSTFLAGS", "CARGO_INCREMENTAL"}
    present = [name for name in os.environ if name in rejected or
               name.startswith("CARGO_PROFILE_") or
               (name.startswith("CARGO_TARGET_") and name != "CARGO_TARGET_DIR")]
    require(not present, "compiler/target/profile override present: " + ",".join(sorted(present)))
    require(os.environ.get("CARGO_BUILD_JOBS", "2") == "2", "jobs must be 2")
    require(os.environ.get("LIBSQLITE3_FLAGS", "-USQLITE_ENABLE_MEMORY_MANAGEMENT") ==
            "-USQLITE_ENABLE_MEMORY_MANAGEMENT", "changed source-configured SQLite build flags")
    require("CARGO_TARGET_DIR" not in os.environ or
            canonical(os.environ["CARGO_TARGET_DIR"], directory=True) == canonical(target, directory=True),
            "environment points to another target")


def preflight(source, target, inputs, manifest):
    check_environment(target)
    identity = target_identity(target)
    require(not any(Path(identity["path"]).iterdir()), "target must start empty")
    result = {"schema": "layerfs-encoder-preflight-v1", "source": source_snapshot(source, manifest),
              "inputs": input_snapshot(inputs), "target": identity,
              "productionBuildCommand": BUILD_COMMAND, "ok": True}
    require(not any(Path(identity["path"]).iterdir()), "target changed during preflight")
    return result


def recheck_preflight(receipt):
    require(receipt["schema"] == "layerfs-encoder-preflight-v1" and receipt["ok"] is True,
            "not a successful preflight")
    require(receipt["productionBuildCommand"] == BUILD_COMMAND, "changed build declaration")
    check_environment(receipt["target"]["path"])
    require(source_snapshot(receipt["source"]["root"], receipt["source"]["manifest"]["path"])
            == receipt["source"], "source changed after preflight")
    require(input_snapshot(receipt["inputs"]["root"]) == receipt["inputs"], "inputs changed")
    require(target_identity(receipt["target"]["path"]) == receipt["target"], "target replaced")


def inside_file(path, parent):
    path = canonical(path)
    parent = canonical(parent, directory=True)
    require(path.is_relative_to(parent), "artifact outside declared target")
    return path


def release_profile(record):
    profile = record["profile"]
    require(profile["opt_level"] == "3" and profile["debug_assertions"] is False and
            profile["overflow_checks"] is False and
            profile["test"] is False and profile.get("debuginfo") in (None, 0),
            "artifact is not the production release profile")
    require(record["fresh"] is False, "fresh empty target unexpectedly reused an artifact")


def one_operand(tokens, flag):
    values = [tokens[index + 1] for index, token in enumerate(tokens[:-1]) if token == flag]
    require(len(values) == 1, f"missing/ambiguous {flag}")
    return values[0]


def daemon_extern(stderr, source, target, bridge_rlib, daemon_rlib):
    matches = {"lib": [], "bin": []}
    for line in stderr.decode("utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("Running `") or not stripped.endswith("`"):
            continue
        tokens = shlex.split(stripped[len("Running `"):-1])
        if "--crate-name" not in tokens:
            continue
        if one_operand(tokens, "--crate-name") != "layerfs_daemon":
            continue
        kind = one_operand(tokens, "--crate-type")
        require("--test" not in tokens and kind in matches, "not production lib/bin")
        relative = ("core/crates/layerfs-daemon/src/lib.rs" if kind == "lib" else
                    "core/crates/layerfs-daemon/src/bin/layerfs-daemon.rs")
        manifest_dirs = [token for token in tokens if token.startswith("CARGO_MANIFEST_DIR=")]
        require(manifest_dirs == [f"CARGO_MANIFEST_DIR={source / 'core/crates/layerfs-daemon'}"],
                "daemon rustc manifest directory mismatch")
        # Cargo may make the root input relative to the repository or core/
        # workspace. These three exact spellings all bind one pinned source file;
        # never accept an arbitrary suffix from another package/check-out.
        require(relative in tokens or relative.removeprefix("core/") in tokens or
                str(source / relative) in tokens,
                "daemon rustc input mismatch")
        dependency = "layerfs_bridge" if kind == "lib" else "layerfs_daemon"
        operands = [tokens[i + 1] for i, token in enumerate(tokens[:-1]) if token == "--extern"
                    and tokens[i + 1].startswith(dependency + "=")]
        require(len(operands) == 1, "daemon extern missing/ambiguous")
        linked = operands[0].split("=", 1)[1]
        require(Path(linked).is_absolute(), "relative daemon extern")
        selected = inside_file(linked, target / "release/deps")
        if kind == "lib":
            require(selected == bridge_rlib, "daemon library links a different bridge rlib")
        else:
            # Cargo can report its top-level primary-library alias in JSON,
            # while rustc links the hash-named deps file. Bind exact bytes;
            # never guess a hash filename or select a directory glob.
            require(file_record(selected)["sha256"] == file_record(daemon_rlib)["sha256"],
                    "daemon bin links a different daemon library")
        matches[kind].append({"extern": operands[0], "linkedRlib": file_record(selected),
                              "rustcArguments": tokens})
    require(all(len(value) == 1 for value in matches.values()),
            "missing/ambiguous daemon lib/bin rustc Running line")
    return {kind: values[0] for kind, values in matches.items()}


def select_artifacts(cargo_json, stderr, source, target):
    records = [parse_json(line) for line in cargo_json.splitlines() if line]
    require(records and all(isinstance(row, dict) for row in records), "invalid Cargo records")
    finishes = [row for row in records if row.get("reason") == "build-finished"]
    require(len(finishes) == 1 and finishes[0].get("success") is True and
            records[-1] == finishes[0], "build did not finish successfully")
    artifacts = [row for row in records if row.get("reason") == "compiler-artifact"]
    def select(name, kind, relative, entry):
        rows = [row for row in artifacts if row.get("target", {}).get("name") == name]
        require(len(rows) == 1, f"missing/ambiguous artifact: {name}")
        row = rows[0]
        require(row["target"]["kind"] == [kind] and row["target"]["crate_types"] == [kind],
                "wrong crate kind")
        require(canonical(row["target"]["src_path"]) == source / relative / "src" / entry,
                "wrong artifact source")
        require(canonical(row["manifest_path"]) == source / relative / "Cargo.toml",
                "wrong artifact manifest")
        require(isinstance(row["package_id"], str) and row["package_id"], "missing package id")
        release_profile(row)
        return row
    bridge = select("layerfs_bridge", "lib", "core/crates/layerfs-bridge", "lib.rs")
    daemon_lib = select("layerfs_daemon", "lib", "core/crates/layerfs-daemon", "lib.rs")
    daemon = select("layerfs-daemon", "bin", "core/crates/layerfs-daemon", "bin/layerfs-daemon.rs")
    require(bridge["features"] == ["default", "duplex"] and daemon["features"] == []
            and daemon_lib["features"] == [],
            "not the fixed default production feature closure")
    rlibs = [value for value in bridge["filenames"] if value.endswith(".rlib")]
    require(len(rlibs) == 1 and bridge["executable"] is None, "ambiguous bridge artifact")
    rlib = inside_file(rlibs[0], target / "release/deps")
    daemon_rlibs = [value for value in daemon_lib["filenames"] if value.endswith(".rlib")]
    require(len(daemon_rlibs) == 1 and daemon_lib["executable"] is None,
            "ambiguous daemon library artifact")
    daemon_rlib = inside_file(daemon_rlibs[0], target / "release")
    require(daemon["package_id"] == daemon_lib["package_id"], "daemon lib/bin package mismatch")
    executable = inside_file(daemon["executable"], target / "release")
    require(executable == target / "release/layerfs-daemon" and
            str(executable) in daemon["filenames"], "daemon ELF artifact mismatch")
    return {"bridgeCargoArtifact": bridge, "daemonCargoArtifact": daemon,
            "daemonLibraryCargoArtifact": daemon_lib, "daemonRlib": file_record(daemon_rlib),
            "bridge": file_record(rlib), "daemonElf": file_record(executable),
            "daemonRustcLinkage": daemon_extern(stderr, source, target, rlib, daemon_rlib)}


def linkage(preflight_path, cargo_json_path, stderr_path, build_exit_code,
            rustc_path, cargo_path, build_command_path):
    require(type(build_exit_code) is int and build_exit_code == 0, "daemon build exit was not zero")
    receipt, preflight_record = read_json(preflight_path)
    recheck_preflight(receipt)
    declared, command_record = read_json(build_command_path)
    require(declared == BUILD_COMMAND and "--no-default-features" not in declared,
            "changed production build command")
    rustc, rustc_record = read_bounded(rustc_path, MIB)
    cargo, cargo_record = read_bounded(cargo_path, MIB)
    require(rustc.decode("utf-8") == RUSTC_VERSION, "wrong Rust compiler/host")
    cargo_lines = cargo.decode("utf-8").splitlines()
    require(cargo_lines and re.fullmatch(r"cargo 1\.85\.1 \([0-9a-f]{7,40} \d{4}-\d{2}-\d{2}\)",
                                        cargo_lines[0]) is not None and
            cargo_lines.count("release: 1.85.1") == 1 and
            cargo_lines.count("host: x86_64-unknown-linux-gnu") == 1, "wrong Cargo -Vv version/host")
    cargo_json, json_record = read_bounded(cargo_json_path, LOG_CAP)
    stderr, stderr_record = read_bounded(stderr_path, LOG_CAP)
    selected = select_artifacts(cargo_json, stderr, Path(receipt["source"]["root"]),
                                Path(receipt["target"]["path"]))
    recheck_preflight(receipt)
    return {"schema": "layerfs-encoder-linkage-v1", "ok": True, "preflight": preflight_record,
            "buildCommand": command_record, "buildExitCode": build_exit_code,
            "rustcVersion": rustc_record, "cargoVersion": cargo_record,
            "cargoJson": json_record, "cargoStderr": stderr_record, **selected}


def expected_stdout(model):
    validate_model(model)
    lines = [f"model_case={case['observedMask']} "
             f"predicted_subset_answer_bytes={case['predictedSubsetAnswerBytes']} "
             "actual_encoder=control_record_limit" for case in model["cases"]]
    return ("\n".join([*lines, FINAL_LINE]) + "\n").encode("utf-8")


def unchanged(record, cap=None):
    require(file_record(record["path"], cap) == record, "retained evidence/artifact changed")


def finalize(preflight_path, linkage_path, stdout_path, stderr_path, proof_exit_code,
             proof_binary, compile_exit_code, binary_before_path):
    require(type(compile_exit_code) is int and compile_exit_code == 0, "proof compile failed")
    require(type(proof_exit_code) is int and proof_exit_code == 0, "proof execution failed")
    receipt, preflight_record = read_json(preflight_path)
    linked, linkage_record = read_json(linkage_path)
    require(linked["schema"] == "layerfs-encoder-linkage-v1" and linked["ok"] is True and
            linked["preflight"] == preflight_record, "linkage/preflight mismatch")
    recheck_preflight(receipt)
    # Recompute selection, not merely trust previously serialized pass flags.
    rebuilt = linkage(preflight_path, linked["cargoJson"]["path"], linked["cargoStderr"]["path"],
                      linked["buildExitCode"], linked["rustcVersion"]["path"],
                      linked["cargoVersion"]["path"], linked["buildCommand"]["path"])
    require(rebuilt == linked, "linkage inputs/artifacts changed")
    binary = file_record(proof_binary)
    before, before_record = read_bounded(binary_before_path, MIB)
    require(before.decode("utf-8") == f"{binary['sha256']}  {binary['path']}\n",
            "proof ELF differs from pre-execution SHA/path")
    stdout, stdout_record = read_bounded(stdout_path, PROOF_LOG_CAP)
    stderr, stderr_record = read_bounded(stderr_path, PROOF_LOG_CAP)
    model, _ = read_json(Path(receipt["inputs"]["root"]) / "model.json")
    require(stdout == expected_stdout(model) and stderr == b"", "proof output is not exact success")
    recheck_preflight(receipt)
    unchanged(binary)
    return {"schema": "layerfs-encoder-result-v1", "ok": True, "complete": True,
            "sourcePin": SOURCE_PIN, "preflight": preflight_record, "linkage": linkage_record,
            "proofElf": binary, "proofElfBefore": before_record, "proofStdout": stdout_record,
            "proofStderr": stderr_record, "compileExitCode": compile_exit_code,
            "proofExitCode": proof_exit_code, "controls": ["small-roundtrip", "65519-roundtrip",
            "65520-control-record-limit"], "subsetAnswerBytes": EXPECTED_SIZES,
            "actualPublicEncoderExecuted": True, "capturedDaemonReply": False,
            "mountedRerun": False, "originalBenchmarkRemainsFailed": True, "ratios": None}


def write_receipt(path, value):
    data = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")
    require(len(data) <= RECEIPT_CAP, "provenance exceeds cap")
    path = Path(os.path.abspath(path))
    canonical(path.parent, directory=True)
    with path.open("xb") as stream:
        stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    before = sub.add_parser("preflight")
    for name in ("source", "target", "inputs", "source-manifest", "output"):
        before.add_argument("--" + name, required=True)
    link = sub.add_parser("linkage")
    for name in ("preflight", "cargo-json", "cargo-stderr", "rustc-version", "cargo-version",
                 "build-command", "output"):
        link.add_argument("--" + name, required=True)
    link.add_argument("--build-exit-code", type=int, required=True)
    final = sub.add_parser("finalize")
    for name in ("preflight", "linkage", "proof-stdout", "proof-stderr", "proof-binary",
                 "proof-binary-before", "output"):
        final.add_argument("--" + name, required=True)
    final.add_argument("--proof-exit-code", type=int, required=True)
    final.add_argument("--compile-exit-code", type=int, required=True)
    args = parser.parse_args(argv)
    if args.command == "preflight":
        result = preflight(args.source, args.target, args.inputs, args.source_manifest)
    elif args.command == "linkage":
        result = linkage(args.preflight, args.cargo_json, args.cargo_stderr, args.build_exit_code,
                         args.rustc_version, args.cargo_version, args.build_command)
    else:
        result = finalize(args.preflight, args.linkage, args.proof_stdout, args.proof_stderr,
                          args.proof_exit_code, args.proof_binary, args.compile_exit_code,
                          args.proof_binary_before)
    write_receipt(args.output, result)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"encoder proof evidence rejected: {error}", file=sys.stderr)
        raise SystemExit(1)
