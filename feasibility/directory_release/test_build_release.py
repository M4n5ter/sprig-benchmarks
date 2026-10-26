"""Source-only unit tests prepared for owner execution; no Cargo or ELF runs.

Suggested later invocation: python3 -m unittest discover -s PACKAGE -p test_build_release.py
This file and the helper were NOT executed by the preparing agent.
"""

import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location("build_release", Path(__file__).with_name("build_release.py"))
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


def manifest():
    tests = sorted(["writable::directory_benchmark::ordinary_directory_attribute_pressure",
                    "writable::directory_lifecycle_benchmark::ordinary_directory_lifecycle_pressure"])
    return {"schema": "sprig-directory-counts-release-manifest-v1", "approvedForExecution": True,
            "runnerSha256": {"build_release.py": "a" * 64},
            "variants": {name: {"productionCommit": HELPER.PINNED.get(name, "b" * 40),
                                 "expectedTests": list(tests)} for name in HELPER.VARIANTS},
            "toolchain": {"requested": "1.99.1", "requireSameExactCompiler": True},
            "limits": dict(HELPER.LIMITS),
            "instrumentationSha256": {name: "c" * 64 for name in HELPER.MODULES},
            "instrumentationFiles": {name: name for name in HELPER.MODULES},
            "moduleSuffix": HELPER.EXPECTED_SUFFIX,
            "appendOnlySuffixSha256": HELPER.sha_bytes(HELPER.EXPECTED_SUFFIX.encode())}


class BuildReleaseTests(unittest.TestCase):
    def test_checked_publication_never_gates_after_canonical_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json'
            data={'ok':False,'complete':False,'payload':'measured'}
            observed=[]
            def check(extra=0):
                observed.append((extra,json.loads(path.read_text())['ok'] if path.exists() else None))
                self.assertFalse(path.exists() and json.loads(path.read_text())['ok'])
            self.assertTrue(HELPER.checked_publish(path,data,True,check))
            self.assertTrue(data['ok'] and data['complete'])
            self.assertTrue(json.loads(path.read_text())['ok'])
            self.assertEqual(len(observed),4)
            self.assertGreater(observed[0][0],0)
            self.assertGreater(observed[2][0],0)

    def test_final_resource_failures_reset_build_and_summary_flags(self):
        for include_complete in [False,True]:
            for failed_call in [1,2,3,4]:
                with tempfile.TemporaryDirectory() as directory:
                    path=Path(directory)/'receipt.json'
                    data={'ok':False}
                    if include_complete:data['complete']=False
                    calls=0
                    def check(extra=0):
                        nonlocal calls
                        calls+=1
                        if calls==failed_call:raise RuntimeError('injected final resource failure')
                    self.assertFalse(HELPER.checked_publish(path,data,True,check))
                    self.assertFalse(data['ok'])
                    if include_complete:self.assertFalse(data['complete'])
                    self.assertFalse(path.exists() and json.loads(path.read_text())['ok'])
                    self.assertIn('injected',data['finalizationError'])

    def test_final_stage_write_failure_retains_nonpassing_canonical_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json'
            data={'ok':False,'complete':False}
            original=HELPER.write_checked_json
            def fail_pass_stage(destination,record,check,stage_name,maximum_bytes=None):
                if stage_name.endswith('.pass-pending'):raise OSError('injected pass-stage write failure')
                return original(destination,record,check,stage_name,maximum_bytes)
            with mock.patch.object(HELPER,'write_checked_json',side_effect=fail_pass_stage):
                self.assertFalse(HELPER.checked_publish(path,data,True,lambda extra=0:None))
            self.assertFalse(data['ok'] or data['complete'])
            self.assertFalse(json.loads(path.read_text())['ok'])

    def test_interruption_before_or_after_promotion_cannot_leave_reported_pass(self):
        for after in [False,True]:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'receipt.json'
                data={'ok':False,'complete':False}
                original=HELPER.os.replace
                def interrupt(source,destination):
                    if str(source).endswith('.pass-pending') and destination==path:
                        if after:original(source,destination)
                        raise KeyboardInterrupt('injected promotion interruption')
                    return original(source,destination)
                with mock.patch.object(HELPER.os,'replace',side_effect=interrupt):
                    self.assertFalse(HELPER.checked_publish(path,data,True,lambda extra=0:None))
                self.assertFalse(data['ok'] or data['complete'])
                self.assertFalse(path.exists() and json.loads(path.read_text())['ok'])
                self.assertTrue(list(Path(directory).glob('*rejected-pass*')))

    def test_failed_computation_is_never_promoted(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json';data={'ok':False,'complete':False}
            self.assertFalse(HELPER.checked_publish(path,data,False,lambda extra=0:None))
            self.assertFalse(json.loads(path.read_text())['ok'])
            self.assertFalse(list(Path(directory).glob('*.pass-pending')))

    def test_log_quota_rejects_before_retaining_overflow(self):
        HELPER.check_log_quota(1023,1,1024)
        with self.assertRaisesRegex(ValueError,'capture overflow'):
            HELPER.check_log_quota(1023,2,1024)

    def test_valid_manifest(self):
        HELPER.validate_manifest(manifest(), "a" * 64)

    def test_pending_manifest_fails_closed_for_all_variants(self):
        for field in ("productionCommit", "expectedTests"):
            item = manifest()
            item["variants"]["narrow"][field] = None
            with self.assertRaises(ValueError):
                HELPER.validate_manifest(item, "a" * 64)

    def test_approval_and_hash_are_required(self):
        item = manifest()
        item["approvedForExecution"] = False
        with self.assertRaises(ValueError):
            HELPER.validate_manifest(item, "a" * 64)
        with self.assertRaises(ValueError):
            HELPER.validate_manifest(manifest(), "d" * 64)

    def test_floating_toolchain_or_changed_budget_rejected(self):
        for requested in (None, "stable", "latest", "1.99", "1.99.1-nightly"):
            item = manifest()
            item["toolchain"]["requested"] = requested
            with self.assertRaises(ValueError):
                HELPER.validate_manifest(item, "a" * 64)
        for key in HELPER.LIMITS:
            item = manifest()
            item["limits"][key] += 1
            with self.assertRaises(ValueError):
                HELPER.validate_manifest(item, "a" * 64)

    def test_wrong_pin_suffix_or_inventory_rejected(self):
        for mutate in (lambda x: x["variants"]["baseline"].update(productionCommit="e" * 40),
                       lambda x: x.update(moduleSuffix=x["moduleSuffix"] + "// mutation\n"),
                       lambda x: x["variants"]["count"]["expectedTests"].append("extra"),
                       lambda x: x["variants"]["narrow"].update(productionCommit=HELPER.PINNED["count"])):
            item = manifest()
            mutate(item)
            with self.assertRaises(ValueError):
                HELPER.validate_manifest(item, "a" * 64)

    def test_inventory_is_exact_not_count_only(self):
        expected = ["a", "b"]
        self.assertTrue(HELPER.verify_inventory("a: test\nb: test\n2 tests, 0 benchmarks\n", expected)["passed"])
        for text in ("a: test\nc: test\n", "a: test\na: test\n", "a: test\nb: test\nnoise\n"):
            self.assertFalse(HELPER.verify_inventory(text, expected)["passed"])

    def test_paths_symlinks_and_hardlinks_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "not-owned"
            with self.assertRaises(ValueError):
                HELPER.safe_path(outside, root, exists=False)
            actual = root / "actual"
            actual.write_bytes(b"x")
            link = root / "symlink"
            link.symlink_to(actual)
            with self.assertRaises(ValueError):
                HELPER.safe_path(link, root)
            hard = root / "hard"
            os.link(actual, hard)
            with self.assertRaises(ValueError):
                HELPER.regular(actual, single_link=True)

    def test_sparse_evidence_charges_logical_and_allocated_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            sparse=root/'sparse'
            with sparse.open('wb') as stream:
                stream.truncate(4*1024**2)
            info=sparse.stat()
            self.assertGreaterEqual(HELPER.evidence_size(root),max(info.st_size,info.st_blocks*512))

    def test_artifact_requires_release_fresh_and_exact_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            target = root / "target"
            target.mkdir()
            binary = target / "sprig-example"
            binary.write_bytes(b"\x7fELFfixture-not-executable")
            dep = binary.with_suffix(".d")
            dep.write_text("src/writable.rs src/writable_directory_benchmark.rs "
                           "src/writable_directory_lifecycle_benchmark.rs\n"
                           f"# env-dep:CARGO_MANIFEST_DIR={source}\n")
            artifact = {"executable": str(binary), "fresh": False,
                        "manifest_path": str(source / "Cargo.toml"),
                        "target": {"name": "sprig", "src_path": str(source / "src/lib.rs")},
                        "profile": {"opt_level": "3", "debug_assertions": False,
                                    "overflow_checks": False, "test": True}}
            self.assertTrue(HELPER.verify_artifact(artifact, source, target, 0)["passed"])
            changes = [lambda x: x.update(fresh=True),
                       lambda x: x.update(manifest_path="/wrong/Cargo.toml"),
                       lambda x: x["target"].update(src_path="/wrong/src/lib.rs"),
                       lambda x: x["profile"].update(opt_level="0"),
                       lambda x: x["profile"].update(debug_assertions=True),
                       lambda x: x["profile"].update(overflow_checks=True)]
            for change in changes:
                modified = copy.deepcopy(artifact)
                change(modified)
                with self.assertRaises(ValueError):
                    HELPER.verify_artifact(modified, source, target, 0)
            dep.write_text("# env-dep:CARGO_MANIFEST_DIR=/stale/source\n")
            with self.assertRaises(ValueError):
                HELPER.verify_artifact(artifact, source, target, 0)


if __name__ == "__main__":
    unittest.main()
