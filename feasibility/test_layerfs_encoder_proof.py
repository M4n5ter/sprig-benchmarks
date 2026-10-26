#!/usr/bin/env python3
"""Inert filesystem/JSON fixtures only; no compiler, product, mount or socket."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

import layerfs_encoder_proof as proof


class EncoderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.inputs = self.root / "inputs"
        for directory in (self.source, self.target, self.inputs):
            directory.mkdir()
        source_files = {
            "core/Cargo.lock": b'version = 4\n[[package]]\nname = "libc"\nversion = "0.2.189"\n'
                               b'[[package]]\nname = "fuser"\nversion = "0.18.0"\n',
            "core/crates/layerfs-bridge/Cargo.toml": b"bridge manifest\n",
            "core/crates/layerfs-bridge/src/lib.rs": b"bridge source\n",
            "core/crates/layerfs-daemon/Cargo.toml": b"daemon manifest\n",
            "core/crates/layerfs-daemon/src/lib.rs": b"daemon library source\n",
            "core/crates/layerfs-daemon/src/bin/layerfs-daemon.rs": b"daemon bin source\n",
        }
        manifest_lines = []
        for name, data in source_files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            manifest_lines.append(f"{self.sha(data)}  {name}")
        self.manifest = self.root / "captured-source-hashes.txt"
        self.manifest.write_text("\n".join(manifest_lines) + "\n")
        manifest_sha = self.sha(self.manifest.read_bytes())
        self.model = {
            "schema": "layerfs-source-only-encoder-model-v1", "sourcePin": proof.SOURCE_PIN,
            "sourceManifestSha256": manifest_sha, "actualEncoderExecuted": False,
            "capturedDaemonReply": False, "mountedRerun": False,
            "fixtureRustSha256": self.sha(b"fixture source\n"),
            "cases": [{"observedMask": i, "predictedSubsetAnswerBytes": size,
                       "controlLimitBytes": 65519} for i, size in enumerate(proof.EXPECTED_SIZES)],
        }
        data = {"README.md": b"historical proposal\n", "prepare_fixture.py": b"not executed\n",
                "fixture.rs": b"fixture source\n", "proof.rs": b"inert source\n",
                "model.json": (json.dumps(self.model) + "\n").encode()}
        for name, value in data.items():
            (self.inputs / name).write_bytes(value)
        # Test-only injection of tiny inert source/input manifests, never CLI flags.
        self.patches = [patch.object(proof, "INPUT_HASHES", {k: self.sha(v) for k, v in data.items()}),
                        patch.object(proof, "MANIFEST_SHA", manifest_sha),
                        patch.object(proof, "LOCK_SHA", self.sha(source_files["core/Cargo.lock"])),
                        patch.object(proof, "MANIFEST_COUNT", len(source_files)),
                        patch.object(proof, "git_identity", return_value=proof.SOURCE_PIN),
                        patch.dict(os.environ, {}, clear=True)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.before = proof.preflight(self.source, self.target, self.inputs, self.manifest)
        self.before_path = self.root / "preflight.json"
        proof.write_receipt(self.before_path, self.before)

    @staticmethod
    def sha(data):
        return hashlib.sha256(data).hexdigest()

    def build_fixture(self):
        deps = self.target / "release/deps"
        deps.mkdir(parents=True)
        self.bridge = deps / "liblayerfs_bridge-1234.rlib"
        self.bridge.write_bytes(b"inert bridge rlib")
        self.bridge_meta = deps / "liblayerfs_bridge-1234.rmeta"
        self.bridge_meta.write_bytes(b"inert bridge metadata")
        self.daemon_dep = deps / "liblayerfs_daemon-5678.rlib"
        self.daemon_dep.write_bytes(b"inert daemon rlib")
        self.daemon_alias = self.target / "release/liblayerfs_daemon.rlib"
        self.daemon_alias.write_bytes(self.daemon_dep.read_bytes())
        self.daemon = self.target / "release/layerfs-daemon"
        self.daemon.write_bytes(b"inert nonexecutable daemon bytes")
        profile = {"opt_level": "3", "debuginfo": 0, "debug_assertions": False,
                   "overflow_checks": False, "test": False}

        def artifact(name, crate, kind, entry, filename, features, executable=None):
            directory = self.source / "core/crates" / crate
            return {"reason": "compiler-artifact", "package_id": f"path+file://{directory}#1.1.0",
                    "manifest_path": str(directory / "Cargo.toml"),
                    "target": {"name": name, "kind": [kind], "crate_types": [kind],
                               "src_path": str(directory / "src" / entry)},
                    "profile": copy.deepcopy(profile), "features": features,
                    "filenames": [str(filename)], "executable": str(executable) if executable else None,
                    "fresh": False}
        self.rows = [artifact("layerfs_bridge", "layerfs-bridge", "lib", "lib.rs", self.bridge,
                              ["default", "duplex"]),
                     artifact("layerfs_daemon", "layerfs-daemon", "lib", "lib.rs", self.daemon_alias, []),
                     artifact("layerfs-daemon", "layerfs-daemon", "bin", "bin/layerfs-daemon.rs",
                              self.daemon, [], self.daemon),
                     {"reason": "build-finished", "success": True}]
        self.rows[0]["filenames"].append(str(self.bridge_meta))
        manifest_env = f"CARGO_MANIFEST_DIR={self.source / 'core/crates/layerfs-daemon'}"
        library_tokens = [manifest_env, "rustc", "--crate-name", "layerfs_daemon",
                          "core/crates/layerfs-daemon/src/lib.rs", "--crate-type", "lib",
                          "--extern", f"layerfs_bridge={self.bridge_meta}"]
        bin_tokens = [manifest_env, "rustc", "--crate-name", "layerfs_daemon",
                      "core/crates/layerfs-daemon/src/bin/layerfs-daemon.rs", "--crate-type", "bin",
                      "--extern", f"layerfs_daemon={self.daemon_dep}",
                      "--extern", f"layerfs_bridge={self.bridge}"]
        self.stderr_bytes = (f"     Running `{shlex.join(library_tokens)}`\n"
                             f"     Running `{shlex.join(bin_tokens)}`\n").encode()
        self.cargo_json = self.root / "cargo.jsonl"
        self.cargo_stderr = self.root / "cargo.stderr"
        self.flush_build()
        self.rustc_version = self.root / "rustc-version.txt"
        self.rustc_version.write_text(proof.RUSTC_VERSION)
        self.cargo_version = self.root / "cargo-version.txt"
        self.cargo_version.write_text("cargo 1.85.1 (d73d2caf9 2024-12-31)\nrelease: 1.85.1\n"
                                      "host: x86_64-unknown-linux-gnu\n")
        self.command = self.root / "build-command.json"
        self.command.write_text(json.dumps(proof.BUILD_COMMAND))

    def flush_build(self):
        self.cargo_json.write_bytes(b"".join((json.dumps(row) + "\n").encode() for row in self.rows))
        self.cargo_stderr.write_bytes(self.stderr_bytes)

    def link(self, exit_code=0):
        return proof.linkage(self.before_path, self.cargo_json, self.cargo_stderr, exit_code,
                             self.rustc_version, self.cargo_version, self.command)

    def final_fixture(self):
        self.build_fixture()
        self.link_path = self.root / "linkage.json"
        proof.write_receipt(self.link_path, self.link())
        self.proof_binary = self.root / "proof-binary"
        self.proof_binary.write_bytes(b"inert proof binary bytes - not executable")
        self.binary_before = self.root / "proof-before.sha256"
        self.binary_before.write_text(f"{self.sha(self.proof_binary.read_bytes())}  {self.proof_binary}\n")
        self.stdout = self.root / "proof.stdout"
        self.stdout.write_bytes(proof.expected_stdout(self.model))
        self.stderr = self.root / "proof.stderr"
        self.stderr.write_bytes(b"")

    def finish(self, proof_exit=0, compile_exit=0):
        return proof.finalize(self.before_path, self.link_path, self.stdout, self.stderr, proof_exit,
                              self.proof_binary, compile_exit, self.binary_before)

    def test_preflight_retains_fixed_inputs(self):
        self.assertTrue(self.before["ok"])
        self.assertEqual(self.before["source"]["head"], proof.SOURCE_PIN)
        self.assertEqual(set(self.before["inputs"]["files"]), set(proof.INPUT_HASHES))

    def test_dirty_git_rejected(self):
        with patch.object(proof, "git_identity", side_effect=ValueError("dirty")):
            with self.assertRaises(ValueError):
                proof.recheck_preflight(self.before)

    def test_source_change_rejected(self):
        (self.source / "core/crates/layerfs-bridge/src/lib.rs").write_text("changed")
        with self.assertRaises(ValueError):
            proof.recheck_preflight(self.before)

    def test_frozen_input_change_rejected(self):
        (self.inputs / "proof.rs").write_text("changed")
        with self.assertRaises(ValueError):
            proof.recheck_preflight(self.before)

    def test_nonempty_target_rejected(self):
        (self.target / "old").write_text("old")
        with self.assertRaises(ValueError):
            proof.preflight(self.source, self.target, self.inputs, self.manifest)

    def test_target_replacement_rejected(self):
        self.target.rename(self.root / "old-target")
        self.target.mkdir()
        with self.assertRaises(ValueError):
            proof.recheck_preflight(self.before)

    def test_environment_override_rejected(self):
        for name in ("RUSTFLAGS", "RUSTC_WRAPPER", "CARGO_PROFILE_RELEASE_OPT_LEVEL", "LIBSQLITE3_FLAGS"):
            with self.subTest(name=name), patch.dict(os.environ, {name: "unexpected"}):
                with self.assertRaises(ValueError):
                    proof.recheck_preflight(self.before)

    def test_matching_target_environment_allowed(self):
        with patch.dict(os.environ, {"CARGO_TARGET_DIR": str(self.target), "CARGO_BUILD_JOBS": "2"}):
            proof.recheck_preflight(self.before)

    def test_log_cap_rejects_without_clipping(self):
        file = self.root / "log"
        file.write_bytes(b"abcde")
        with self.assertRaises(ValueError):
            proof.read_bounded(file, 4)
        self.assertEqual(file.read_bytes(), b"abcde")

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError):
            proof.parse_json('{"ok":true,"ok":false}')

    def test_manifest_unsafe_or_duplicate_rejected(self):
        digest = "a" * 64
        for data in (f"{digest}  ../bad\n", f"{digest}  /bad\n",
                     f"{digest}  x\n{digest}  x\n"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                proof.manifest_entries(data.encode())

    def test_source_symlink_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.inputs / "proof.rs")
        with self.assertRaises(ValueError):
            proof.file_record(link)

    def test_complete_library_alias_chain(self):
        self.build_fixture()
        linked = self.link()
        self.assertEqual(linked["bridge"]["path"], str(self.bridge))
        self.assertEqual(linked["daemonElf"]["path"], str(self.daemon))
        self.assertEqual(linked["daemonLinkedRlib"]["path"], str(self.daemon_dep))
        self.assertEqual(linked["bridgeMetadata"]["path"], str(self.bridge_meta))
        self.assertNotEqual(str(self.daemon_dep), linked["daemonRlib"]["path"])

    def test_build_nonzero_rejected(self):
        self.build_fixture()
        with self.assertRaises(ValueError):
            self.link(1)

    def test_workspace_relative_rustc_inputs_with_exact_manifest(self):
        self.build_fixture()
        self.stderr_bytes = self.stderr_bytes.replace(b"core/crates/layerfs-daemon/src/",
                                                      b"crates/layerfs-daemon/src/")
        self.flush_build()
        self.assertTrue(self.link()["ok"])

    def test_different_manifest_dir_rejected_even_same_relative_source(self):
        self.build_fixture()
        expected = f"CARGO_MANIFEST_DIR={self.source / 'core/crates/layerfs-daemon'}".encode()
        self.stderr_bytes = self.stderr_bytes.replace(expected, b"CARGO_MANIFEST_DIR=/unrelated")
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_no_default_features_command_rejected(self):
        self.build_fixture()
        self.command.write_text(json.dumps([*proof.BUILD_COMMAND, "--no-default-features"]))
        with self.assertRaises(ValueError):
            self.link()

    def test_missing_duplex_rejected(self):
        self.build_fixture()
        self.rows[0]["features"] = []
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_ambiguous_bridge_artifact_rejected(self):
        self.build_fixture()
        self.rows.insert(1, copy.deepcopy(self.rows[0]))
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_debug_or_test_or_cached_profile_rejected(self):
        self.build_fixture()
        original = copy.deepcopy(self.rows[0])
        for field, value in (("opt_level", "0"), ("debug_assertions", True),
                             ("overflow_checks", True), ("test", True)):
            with self.subTest(field=field):
                self.rows[0] = copy.deepcopy(original)
                self.rows[0]["profile"][field] = value
                self.flush_build()
                with self.assertRaises(ValueError):
                    self.link()
        self.rows[0] = copy.deepcopy(original)
        self.rows[0]["fresh"] = True
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_failed_or_missing_finish_rejected(self):
        self.build_fixture()
        self.rows[-1]["success"] = False
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()
        self.rows.pop()
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_wrong_compiler_or_cargo_host_rejected(self):
        self.build_fixture()
        self.rustc_version.write_text(proof.RUSTC_VERSION.replace("1.85.1", "1.86.0"))
        with self.assertRaises(ValueError):
            self.link()
        self.rustc_version.write_text(proof.RUSTC_VERSION)
        self.cargo_version.write_text("cargo 1.85.1 (d73d2caf9 2024-12-31)\nrelease: 1.85.1\n"
                                      "host: aarch64-unknown-linux-gnu\n")
        with self.assertRaises(ValueError):
            self.link()

    def test_bridge_extern_mismatch_rejected(self):
        self.build_fixture()
        wrong = self.target / "release/deps/wrong.rlib"
        wrong.write_bytes(self.bridge.read_bytes())
        self.stderr_bytes = self.stderr_bytes.replace(str(self.bridge).encode(), str(wrong).encode())
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_daemon_alias_byte_mismatch_rejected(self):
        self.build_fixture()
        self.daemon_dep.write_bytes(b"different")
        with self.assertRaises(ValueError):
            self.link()

    def test_ambiguous_rustc_line_rejected(self):
        self.build_fixture()
        self.stderr_bytes *= 2
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_artifact_outside_target_rejected(self):
        self.build_fixture()
        outside = self.root / "outside.rlib"
        outside.write_bytes(self.bridge.read_bytes())
        self.rows[0]["filenames"] = [str(outside)]
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_wrong_daemon_binary_source_rejected(self):
        self.build_fixture()
        self.rows[2]["target"]["src_path"] = self.rows[1]["target"]["src_path"]
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_complete_proof_never_rescues_failed_benchmark(self):
        self.final_fixture()
        result = self.finish()
        self.assertTrue(result["ok"] and result["complete"] and result["actualPublicEncoderExecuted"])
        self.assertTrue(result["originalBenchmarkRemainsFailed"])
        self.assertFalse(result["capturedDaemonReply"] or result["mountedRerun"])
        self.assertIsNone(result["ratios"])

    def test_wrong_or_extra_proof_output_rejected(self):
        self.final_fixture()
        original = self.stdout.read_bytes()
        for value in (original.replace(b"71643", b"71644"), original + b"extra\n",
                      b"\n".join(original.splitlines()[1:]) + b"\n"):
            with self.subTest(value=value[:90]):
                self.stdout.write_bytes(value)
                with self.assertRaises(ValueError):
                    self.finish()

    def test_proof_stderr_rejected(self):
        self.final_fixture()
        self.stderr.write_text("warning or failure")
        with self.assertRaises(ValueError):
            self.finish()

    def test_compile_or_proof_exit_failure_rejected(self):
        self.final_fixture()
        for run, compile_ in ((1, 0), (0, 1), (124, 0)):
            with self.subTest(run=run, compile_=compile_), self.assertRaises(ValueError):
                self.finish(run, compile_)

    def test_changed_proof_binary_rejected(self):
        self.final_fixture()
        self.proof_binary.write_bytes(b"changed binary")
        with self.assertRaises(ValueError):
            self.finish()

    def test_changed_bridge_after_linkage_rejected(self):
        self.final_fixture()
        self.bridge.write_bytes(b"changed bridge")
        with self.assertRaises(ValueError):
            self.finish()

    def test_mutated_linkage_success_cannot_pass(self):
        self.final_fixture()
        value = json.loads(self.link_path.read_text())
        value["bridge"]["sha256"] = "f" * 64
        self.link_path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            self.finish()

    def test_write_receipt_refuses_overwrite_or_oversize(self):
        with self.assertRaises(FileExistsError):
            proof.write_receipt(self.before_path, {})
        path = self.root / "oversize.json"
        with self.assertRaises(ValueError):
            proof.write_receipt(path, {"large": "a" * proof.RECEIPT_CAP})
        self.assertFalse(path.exists())

    def script_artifact(self, name="libc", version="0.2.189", path_package=False):
        prefix = "path+file:///exact/vendor/fuser" if path_package else "registry+https://github.com/rust-lang/crates.io-index"
        return {"reason": "compiler-artifact", "package_id": f"{prefix}#{name}@{version}",
                "target": {"kind": ["custom-build"]}}

    def mixed_stream(self, text=b"[libc 0.2.189] cargo:rerun-if-changed=build.rs\n", scripts=None):
        scripts = [self.script_artifact()] if scripts is None else scripts
        prefix = b"".join((json.dumps(row) + "\n").encode() for row in scripts)
        return prefix + text + self.cargo_json.read_bytes()

    def parse_stream(self, data):
        return proof.parse_cargo_stream(data, (self.source / "core/Cargo.lock").read_bytes())

    def test_real_shaped_mixed_cargo_stream_count_hash_and_packages(self):
        self.build_fixture()
        text = (b"[libc 0.2.189] cargo:rerun-if-changed=build.rs\n"
                b"[libc 0.2.189] \n[fuser 0.18.0] cargo:rustc-cfg=abi_7_31\n")
        # Actual Cargo can compile libc build.rs twice; one package ID remains.
        scripts = [self.script_artifact(), self.script_artifact(),
                   self.script_artifact("fuser", "0.18.0", True)]
        data = self.mixed_stream(text, scripts)
        records, summary = self.parse_stream(data)
        self.assertEqual(len(records), 7)
        self.assertEqual(summary["verboseLines"], 3)
        self.assertEqual(summary["verboseBytes"], len(text))
        self.assertEqual(summary["verboseRawLinesSha256"], self.sha(text))
        self.assertEqual(summary["verbosePackageLineCounts"], {"fuser 0.18.0": 1, "libc 0.2.189": 2})
        self.cargo_json.write_bytes(data)
        self.assertTrue(self.link()["ok"])

    def test_unbound_wrong_version_or_arbitrary_verbose_line_rejected(self):
        self.build_fixture()
        for line in (b"[unknown 1.0.0] ignored?\n", b"[libc 0.2.188] wrong version\n",
                     b"plain unbound output\n", b"[libc 0.2.189]missing space\n"):
            with self.subTest(line=line), self.assertRaises(ValueError):
                self.parse_stream(self.mixed_stream(line))
        with self.assertRaises(ValueError):
            self.parse_stream(self.mixed_stream(scripts=[]))

    def test_verbose_record_not_in_lock_rejected(self):
        self.build_fixture()
        with self.assertRaises(ValueError):
            self.parse_stream(self.mixed_stream(b"[libc 9.9.9] cargo:rerun-if-changed=x\n",
                                               [self.script_artifact("libc", "9.9.9")]))

    def test_malformed_json_not_discarded_as_verbose(self):
        self.build_fixture()
        with self.assertRaises(ValueError):
            self.parse_stream(self.mixed_stream(b'{"reason":broken}\n'))

    def test_text_after_build_finished_rejected(self):
        self.build_fixture()
        with self.assertRaises(ValueError):
            self.parse_stream(self.mixed_stream() + b"[libc 0.2.189] late output\n")

    def test_changed_lock_bytes_rejected(self):
        self.build_fixture()
        with self.assertRaises(ValueError):
            proof.parse_cargo_stream(self.mixed_stream(), b"version = 4\n")

    def test_metadata_must_belong_to_same_unique_bridge_artifact(self):
        self.build_fixture()
        wrong = self.target / "release/deps/other.rmeta"
        wrong.write_bytes(self.bridge_meta.read_bytes())
        self.stderr_bytes = self.stderr_bytes.replace(str(self.bridge_meta).encode(), str(wrong).encode())
        self.flush_build()
        with self.assertRaises(ValueError):
            self.link()

    def test_missing_or_ambiguous_bridge_metadata_rejected(self):
        self.build_fixture()
        original = list(self.rows[0]["filenames"])
        for filenames in ([str(self.bridge)], original + [str(self.bridge_meta)]):
            with self.subTest(filenames=filenames):
                self.rows[0]["filenames"] = filenames
                self.flush_build()
                with self.assertRaises(ValueError):
                    self.link()

    def test_pure_old_log_audit_never_claims_missing_artifacts_or_encoder(self):
        self.build_fixture()
        data = self.mixed_stream()
        for file in (self.bridge, self.bridge_meta, self.daemon, self.daemon_alias, self.daemon_dep):
            file.unlink()
        result = proof.audit_cargo_structure(data, self.stderr_bytes,
                    (self.source / "core/Cargo.lock").read_bytes(), self.source, self.target)
        self.assertTrue(result["structureCompatible"])
        self.assertFalse(result["filesystemArtifactsVerified"])
        self.assertFalse(result["encoderExecuted"])
        self.assertNotIn("complete", result)
        with self.assertRaises(FileNotFoundError):
            proof.select_artifacts(data, self.stderr_bytes, self.source, self.target,
                                   (self.source / "core/Cargo.lock").read_bytes())


if __name__ == "__main__":
    unittest.main()
