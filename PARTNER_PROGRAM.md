# ESN Hosting Partner Program (foundation)

This branch introduces `partner_program.py`, a Python 3 standard-library SQLite commission ledger. It is **not deployed or connected** to the Discord bot, website, or Stripe.

## Included
- Partner applications with unique codes and owner review status
- 5% / 10% / 15% tier calculations, at 0 / 5 / 15 verified referrals
- First-purchase-only enforcement using unique customer IDs
- Unique Stripe payment IDs, self-referral check (when customer Discord ID supplied)
- 30-day commission hold, manual eligibility and paid-state transitions
- Audit events, refund/reversal state, per-partner statistics

## Critical integration requirements
1. Authenticate Discord users; authorize review and settlement actions against a server-side OWNER_DISCORD_ID (Kavero's numeric Discord user ID), not a username.
2. Verify Stripe webhook signatures using the raw request body and STRIPE_WEBHOOK_SECRET. Confirm the event is an actual successful payment; derive amount and customer identity from Stripe, not user input. Record first payments only. Handle disputes/refunds by reversing unpaid commissions.
3. Use a signed referral attribution token or secure first-party cookie at checkout; prevent self-referrals and coupon abuse.
4. Do not issue automated Cash App/Stripe payouts. Owner must separately verify the recipient and approve payment; never claim a payout occurred before money is sent.
5. Add Discord application/stats commands, admin review commands, a secure website dashboard, backups, and production tests.
6. Set a written affiliate agreement, refund policy, minimum payout, and relevant tax reporting rules before launch.

## Example (local test only)
```python
from partner_program import PartnerProgram
p = PartnerProgram(":memory:")
code = p.apply("123456789012345678")
p.review("123456789012345678", "approved", actor="owner")
print(p.record_verified_payment(code=code, customer_id="stripe-customer-1", payment_id="pi_test_1", amount_cents=599, verified_by="test-fixture"))
print(p.stats("123456789012345678"))
```
The method name `record_verified_payment` does **not** verify Stripe by itself; only call it from a trusted, authenticated server-side integration.
