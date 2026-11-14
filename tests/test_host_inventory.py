import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tradingops.host_inventory import (
    inspect_project, local_source_snapshot, matching_process_state, SHA,
)

GOOD_SHA = "a" * 40


def fake_git(cmd, **kwargs):
    if "rev-parse" in cmd:
        return subprocess.CompletedProcess(cmd, 0, GOOD_SHA + "\n", "")
    if "status" in cmd:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    raise AssertionError(cmd)


class HostInventoryTests(unittest.TestCase):
    def test_git_identity_requires_exact_sha(self):
        with tempfile.TemporaryDirectory() as temp:
            result = local_source_snapshot(Path(temp), run=fake_git)
        self.assertEqual(result["checkout_sha"], GOOD_SHA)
        self.assertEqual(result["status"], "TRACKED_FILES_CLEAN_ONLY")
        self.assertFalse(result["loaded_runtime_proven"])
        self.assertFalse(result["untracked_files_checked"])

    def test_missing_repository_fails(self):
        self.assertEqual(local_source_snapshot(Path("this_path_does_not_exist"))["status"],
                         "CHECKOUT_MISSING")

    def test_git_dirty_is_not_clean(self):
        def dirty(cmd, **kwargs):
            if "rev-parse" in cmd:
                return subprocess.CompletedProcess(cmd, 0, GOOD_SHA + "\n", "")
            return subprocess.CompletedProcess(cmd, 0, " M some.py\n", "")
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(local_source_snapshot(temp, run=dirty)["status"],
                             "TRACKED_FILES_MODIFIED")

    def test_strict_process_identity_and_incomplete_observation(self):
        script = r"C:\\repo\\StockTracker\\run.py"
        right = {"cmdline": ["C:\\Python312\\python.exe", script],
                 "create_time": 1730000000.0, "exe": r"C:\\Python312\\python.exe"}
        wrong = {"cmdline": ["python.exe", r"C:\\repo\\old\\run.py"],
                 "create_time": 1730000000.0, "exe": r"C:\\Python312\\python.exe"}
        self.assertEqual(matching_process_state(script, [right, wrong],
                             enumeration_complete=True),
                         "EXACT_SCRIPT_AND_PROCESS_START_OBSERVED_ONLY")
        self.assertEqual(matching_process_state(script, [right, right],
                             enumeration_complete=True), "AMBIGUOUS_MULTIPLE_PROCESSES")
        self.assertEqual(matching_process_state(script, [right],
                             enumeration_complete=False), "PROCESS_ENUMERATION_INCOMPLETE")
        self.assertEqual(matching_process_state(script, [{**right, "create_time": None}],
                             enumeration_complete=True), "PROCESS_START_TIME_UNVERIFIED")

    def test_registry_never_claims_loaded_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "infrastructure").mkdir()
            (root / "infrastructure" / "registry.json").write_text(json.dumps({
                "project": "StockTracker", "mode": "PAPER_ONLY", "components": [
                    {"id": "supervisor", "entrypoint": "supervisor.py"},
                    {"id": "deployment_agent", "entrypoint": "agent.py"},
                    {"id": "trader", "entrypoint": "trader.py"}
                ]
            }), encoding="utf-8")
            data = inspect_project(root, "StockTracker", [],
                                   enumeration_complete=True, run=fake_git)
        self.assertEqual(data["registry"], "PAPER_ONLY_REGISTRY_OBSERVED")
        self.assertFalse(data["loaded_code_independently_verified"])
        self.assertFalse(data["loaded_dependencies_independently_verified"])
        self.assertFalse(data["broker_trade_health_independently_verified"])
        self.assertFalse(data["deployment_authority"])

    def test_nonpaper_registry_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "infrastructure").mkdir()
            (root / "infrastructure" / "registry.json").write_text(json.dumps({
                "project": "StockTracker", "mode": "LIVE", "components": []
            }), encoding="utf-8")
            result = inspect_project(root, "StockTracker", [],
                                     enumeration_complete=True, run=fake_git)
        self.assertEqual(result["registry"], "UNVERIFIED")
        self.assertTrue(all(x == "UNVERIFIED" for x in result["processes"].values()))


if __name__ == "__main__":
    unittest.main()
