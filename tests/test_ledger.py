from datetime import datetime, timezone
import unittest
from tradingops.ledger import append_observation, from_audit, verify_chain

SHA = "a"*40
TIME = datetime(2026, 11, 13, tzinfo=timezone.utc).isoformat()


class LedgerTests(unittest.TestCase):
    def test_chain_detects_mutation(self):
        records = append_observation([], project="StockTracker", source_sha=SHA,
                                     observed_at_utc=TIME, kind="HOST_CLAIM",
                                     status="UNVERIFIED")
        records = append_observation(records, project="CryptoTracker", source_sha=SHA,
                                     observed_at_utc=TIME, kind="HOST_CLAIM",
                                     status="STALE")
        self.assertTrue(verify_chain(records))
        records[0]["status"] = "OBSERVED"
        self.assertFalse(verify_chain(records))

    def test_must_have_exact_release(self):
        with self.assertRaises(ValueError):
            append_observation([], project="CryptoTracker", source_sha="main",
                               observed_at_utc=TIME, kind="HOST_CLAIM",
                               status="OBSERVED")

    def test_shadow_records_never_grant_authority(self):
        report = from_audit({"mode": "READ_ONLY_SHADOW",
            "observed_at_utc": TIME, "projects": [
                {"project": "StockTracker", "source_sha": SHA,
                 "host_status": {"status": "HOST_CLAIM_ONLY"}}]})
        self.assertFalse(report["verified_complete"])
        self.assertTrue(verify_chain(report["entries"]))
        self.assertFalse(report["entries"][0]["independently_attested"])


if __name__ == "__main__":
    unittest.main()
