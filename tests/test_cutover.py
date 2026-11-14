import unittest
from tradingops.cutover import evaluate_cutover


def good_results():
    return [
        {"project": n, "state": "VERIFIED_COMPLETE",
         "rollback_plan_verified": True, "parity_shadow_passed": True}
        for n in ("StockTracker", "CryptoTracker")
    ]


class CutoverTests(unittest.TestCase):
    def test_no_approval_is_not_cutover(self):
        result = evaluate_cutover(good_results())
        self.assertFalse(result["eligible_for_manual_cutover_review"])
        self.assertFalse(result["automatic_cutover_permitted"])

    def test_unverified_release_blocks(self):
        items = good_results()
        items[0]["state"] = "PENDING"
        self.assertFalse(evaluate_cutover(items, approval={
            "cutover_authorized": True})["eligible_for_manual_cutover_review"])

    def test_both_complete_still_manual_only(self):
        result = evaluate_cutover(good_results(), approval={"cutover_authorized": True})
        self.assertTrue(result["eligible_for_manual_cutover_review"])
        self.assertFalse(result["automatic_cutover_permitted"])
        self.assertFalse(result["legacy_agents_retired"])


if __name__ == "__main__":
    unittest.main()
