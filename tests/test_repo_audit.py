import base64
from datetime import datetime, timedelta, timezone
import unittest

from tradingops.repo_audit import (
    OWNER, PROJECTS, audit_project, extract_checks, host_observation, run_audit,
)

NOW = datetime(2026, 11, 13, 21, tzinfo=timezone.utc)
SHA = "a" * 40


class RepoAuditTests(unittest.TestCase):
    def test_synced_host_cannot_approve_runtime(self):
        result = host_observation({
            "observed_at_utc": NOW.isoformat(),
            "git_head": SHA, "source_code_synced": True,
            "processes_stable": True,
            "in_memory_trader_digest_verified": True,
            "broker_trade_health_verified": True,
            "post_sync_eod_verified": True,
        }, SHA, now=NOW)
        self.assertEqual(result["status"], "HOST_CLAIM_ONLY")
        self.assertFalse(result["loaded_code_independently_verified"])
        self.assertFalse(result["broker_health_independently_verified"])
        self.assertFalse(result["notification_acceptance_independently_verified"])

    def test_stale_wrong_sha_and_invalid_time_block(self):
        base = {"observed_at_utc": NOW.isoformat(), "git_head": SHA,
                "source_code_synced": True}
        self.assertEqual(host_observation(None, SHA, now=NOW)["status"], "MISSING")
        self.assertEqual(host_observation({**base, "git_head": "b" * 40}, SHA,
                                          now=NOW)["status"], "MISMATCH")
        self.assertEqual(host_observation({**base, "observed_at_utc": (
            NOW - timedelta(days=1)).isoformat()}, SHA, now=NOW)["status"], "STALE")
        self.assertEqual(host_observation({**base, "observed_at_utc": "2026-11-13T21:00:00"},
                                          SHA, now=NOW)["status"], "UNVERIFIED")
        self.assertEqual(host_observation({**base, "observed_at_utc": (
            NOW + timedelta(seconds=1)).isoformat()}, SHA, now=NOW)["status"], "UNVERIFIED")

    def test_ci_check_observation_never_equates_required_ci(self):
        checks = extract_checks({"check_runs": [
            {"name": "ok", "head_sha": SHA, "status": "completed", "conclusion": "success"},
            {"name": "wrong", "head_sha": "b" * 40, "conclusion": "success"},
        ]}, SHA)
        self.assertEqual(len(checks["check_runs"]), 1)
        self.assertIn("NOT_REQUIRED_CHECKS_VERIFIED", checks["status"])

    def test_audit_is_read_only_and_fail_closed(self):
        calls = []
        def fake_getter(path):
            calls.append(path)
            if path.endswith("/commits/main"):
                return {"sha": SHA}
            if "/check-runs?" in path:
                return {"check_runs": []}
            if "/contents/status.json?" in path:
                payload = {"observed_at_utc": NOW.isoformat(),
                           "git_head": SHA, "source_code_synced": True}
                return {"content": base64.b64encode(
                    __import__("json").dumps(payload).encode()).decode()}
            raise AssertionError(path)
        report = run_audit(fake_getter, now=NOW)
        self.assertFalse(report["complete"])
        self.assertFalse(report["deployment_authority"])
        self.assertEqual(len(report["projects"]), 2)
        self.assertEqual(len(calls), 6)
        self.assertTrue(all(not x["independently_verified_complete"] for x in report["projects"]))
        self.assertTrue(all(x["required_ci"] == "UNVERIFIED" for x in report["projects"]))

    def test_github_unavailable_never_marks_complete(self):
        def unavailable(path):
            raise OSError("offline")
        for project in PROJECTS:
            record = audit_project(project, unavailable, now=NOW)
            self.assertEqual(record["source"], "MISSING")
            self.assertFalse(record["independently_verified_complete"])

    def test_reject_unknown_project(self):
        with self.assertRaises(ValueError):
            audit_project("other")


if __name__ == "__main__":
    unittest.main()
