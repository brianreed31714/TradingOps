import unittest
from datetime import datetime, timedelta, timezone
from tradingops.release_gate import STAGES, evaluate_release

SHA = "a" * 40
NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


def good():
    timestamp = NOW.isoformat()
    return {"release_sha": SHA, **{
        stage: {"verified": True, "independent": True,
                "release_sha": SHA, "observed_at": timestamp,
                "evidence_uri": "evidence://signed/" + stage}
        for stage in STAGES
    }}


class ReleaseGateTests(unittest.TestCase):
    def test_complete_only_with_all_evidence(self):
        self.assertEqual(evaluate_release(good(), NOW)["state"], "VERIFIED_COMPLETE")

    def test_missing_stage_fails_closed(self):
        evidence = good()
        del evidence["dated_eod"]
        result = evaluate_release(evidence, NOW)
        self.assertEqual(result["stages"]["dated_eod"]["reason"], "MISSING")
        self.assertFalse(result["complete"])

    def test_source_sync_does_not_prove_runtime(self):
        evidence = good()
        evidence["loaded_runtime"]["verified"] = False
        self.assertFalse(evaluate_release(evidence, NOW)["complete"])

    def test_self_attestation_fails(self):
        evidence = good()
        evidence["loaded_dependencies"]["independent"] = False
        self.assertEqual(evaluate_release(evidence, NOW)["stages"]["loaded_dependencies"]["reason"],
                         "INDEPENDENCE_UNVERIFIED")

    def test_stale_future_and_naive_fail(self):
        for timestamp, expected in [
            ((NOW - timedelta(hours=2)).isoformat(), "STALE_EVIDENCE"),
            ((NOW + timedelta(seconds=1)).isoformat(), "FUTURE_EVIDENCE"),
            ("2026-11-05T00:00:00", "TIMESTAMP_INVALID"),
        ]:
            with self.subTest(expected=expected):
                evidence = good()
                evidence["process_health"]["observed_at"] = timestamp
                self.assertEqual(evaluate_release(evidence, NOW)["stages"]["process_health"]["reason"], expected)

    def test_wrong_commit_and_missing_receipt(self):
        evidence = good()
        evidence["required_ci"]["release_sha"] = "b" * 40
        evidence["notification_acceptance"]["evidence_uri"] = ""
        result = evaluate_release(evidence, NOW)
        self.assertEqual(result["stages"]["required_ci"]["reason"], "RELEASE_MISMATCH")
        self.assertEqual(result["stages"]["notification_acceptance"]["reason"], "EVIDENCE_URI_MISSING")

    def test_invalid_release_and_now(self):
        self.assertEqual(evaluate_release({"release_sha": "main"}, NOW)["reason"], "INVALID_RELEASE_SHA")
        with self.assertRaises(ValueError):
            evaluate_release(good(), datetime(2026, 11, 5))


if __name__ == "__main__":
    unittest.main()
