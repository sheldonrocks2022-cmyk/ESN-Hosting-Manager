import unittest
from partner_program import PartnerProgram
from partner_permissions import require_owner, review_partner

class PartnerTests(unittest.TestCase):
    def setUp(self):
        self.p = PartnerProgram(":memory:")
        self.code = self.p.apply("100")
        review_partner(self.p, "1515077206886453469", "100", "approved")

    def test_first_commission(self):
        self.assertEqual(self.p.record_verified_payment(code=self.code,customer_id="cus1",
            payment_id="pi1",amount_cents=1000,verified_by="test",customer_discord_id="200"),50)
        self.assertEqual(self.p.stats("100")["verified"],1)

    def test_self_referral_blocked(self):
        with self.assertRaises(ValueError):
            self.p.record_verified_payment(code=self.code,customer_id="cus2",
                payment_id="pi2",amount_cents=1000,verified_by="test",customer_discord_id="100")

    def test_duplicate_customer_blocked(self):
        self.p.record_verified_payment(code=self.code,customer_id="cus1",
            payment_id="pi1",amount_cents=1000,verified_by="test")
        with self.assertRaises(Exception):
            self.p.record_verified_payment(code=self.code,customer_id="cus1",
                payment_id="pi2",amount_cents=1000,verified_by="test")

    def test_owner_only(self):
        with self.assertRaises(PermissionError):
            require_owner("200")
        require_owner("1515077206886453469")

    def test_hold_blocks_early_settlement(self):
        self.p.record_verified_payment(code=self.code,customer_id="cus1",
            payment_id="pi1",amount_cents=1000,verified_by="test")
        with self.assertRaises(ValueError):
            self.p.settle("pi1","eligible","1515077206886453469")

if __name__ == "__main__":
    unittest.main()
