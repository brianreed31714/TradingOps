import io
import json
import unittest
from tradingops.notify import exception_summary, send_pushover


class FakeResponse:
    def __enter__(self):
        return io.BytesIO(b'{"status":1,"request":"receipt-123"}')
    def __exit__(self, *args):
        return False


class NotifyTests(unittest.TestCase):
    def test_pending_is_not_an_exception(self):
        self.assertEqual(exception_summary({"projects": [{
            "project": "CryptoTracker", "source_sha": "a"*40,
            "host_status": {"status": "HOST_CLAIM_ONLY"}}]}), "")

    def test_host_status_missing_is_an_exception(self):
        msg = exception_summary({"projects": [
            {"project": "StockTracker", "host_status": {"status": "MISSING"}}
        ]})
        self.assertIn("host evidence MISSING", msg)

    def test_source_missing_and_stale_are_alerts(self):
        msg = exception_summary({"projects": [
            {"project": "StockTracker", "source": "MISSING"},
            {"project": "CryptoTracker", "host_status": {"status": "STALE"}}
        ]})
        self.assertIn("StockTracker", msg)
        self.assertIn("STALE", msg)

    def test_api_acceptance_is_not_device_receipt(self):
        observed = []
        def fake_open(req, timeout):
            observed.append((req.full_url, req.data, timeout))
            return FakeResponse()
        receipt = send_pushover("status", "token", "user", opener=fake_open)
        self.assertEqual(receipt["status"], "PROVIDER_ACCEPTED_NOT_DEVICE_RECEIVED")
        self.assertEqual(len(observed), 1)

    def test_requires_credentials(self):
        with self.assertRaises(ValueError):
            send_pushover("status", "", "user")


if __name__ == "__main__":
    unittest.main()
