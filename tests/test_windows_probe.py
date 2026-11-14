import json
from pathlib import Path
import tempfile
import unittest

from tradingops.windows_probe import launched_script, process_status, probe_project


class WindowsProbeTests(unittest.TestCase):
    def test_only_canonical_absolute_script_arg_counts(self):
        target = r"C:\\Users\\agent\\StockTracker\\trader.py"
        yes = {"cmdline": ["python.exe", "-u", target]}
        evil = {"cmdline": ["python.exe", "launcher.py", target]}
        other = {"cmdline": ["python.exe", r"C:\\backup\\trader.py"]}
        self.assertEqual(launched_script(yes["cmdline"]).lower(), target.lower())
        self.assertEqual(process_status(target, [yes, other, evil]), "ONE_EXACT_SCRIPT_PATH_OBSERVED")
        self.assertEqual(process_status(target, [yes, yes]), "AMBIGUOUS_MULTIPLE_PROCESSES")
        self.assertEqual(process_status(target, [evil]), "PROCESS_NOT_OBSERVED")
        self.assertIsNone(launched_script(["python.exe", "-m", "trader"]))

    def test_missing_registry_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(probe_project(temp, [])["state"], "UNVERIFIED_REGISTRY")

    def test_registry_cannot_establish_loaded_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "infrastructure").mkdir()
            (root / "infrastructure" / "registry.json").write_text(json.dumps({
                "project": "CryptoTracker", "mode": "PAPER_ONLY",
                "components": [
                    {"id": "supervisor", "entrypoint": "supervisor.py"},
                    {"id": "deployment_agent", "entrypoint": "deploy.py"},
                    {"id": "trader", "entrypoint": "trade.py"}
                ]
            }), encoding="utf-8")
            snapshot = probe_project(root, [])
            self.assertFalse(snapshot["loaded_code_independently_verified"])
            self.assertFalse(snapshot["deployment_authority"])


if __name__ == "__main__":
    unittest.main()
