# ESN Stripe Payment Links integration — development only

The integration lives in `stripe_partner_links.py`. This is not deployed and does not yet support subscription commission attribution or refunds.

## Requirements
- Python dependencies: `pip install flask stripe`
- Environment variables: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `PARTNER_DB_PATH` (persistent volume).
- HTTPS endpoint: `POST https://YOUR_BACKEND/stripe/webhook`
- Configure Stripe webhook events `checkout.session.completed` and `checkout.session.async_payment_succeeded`.
- Populate `LINKS` in `stripe_partner_links.py` with your existing official Stripe Payment Link URLs, keyed by plan slug.

## Flow
Approved partner gets `https://YOUR_BACKEND/ref/CODE/starter`.
The backend redirects to `https://buy.stripe.com/...?...&client_reference_id=CODE`.
Stripe creates Checkout Session; a signed webhook confirms the payment and the backend records the commission.

## Important production blockers
- Stripe Payment Links can be shared without referral attribution; ensure your policy covers purchases without codes.
- Do not count subscriptions until a verified first-invoice integration is implemented.
- Do not treat the client_reference_id alone as strong attribution: implement signed referral tokens / first-party referral records, a time-limited attribution window, and anti-hijack checks.
- Ensure the amount excludes tax and is reduced by discounts as intended; reconcile against Stripe's payment details before payouts.
- Verify customer identity and block self-referrals, including matching payment account/customer identity where legally appropriate.
- Add refund and dispute webhooks, cancellation handling, idempotency and database locking.
- Avoid SQLite on multiple independent nodes without shared persistent storage. Use Postgres for multi-node deployment.
- Run tests and deploy behind HTTPS. Never share secret keys in Discord or commit them to GitHub.
- Owner authorization must be enforced on the backend for every admin action; no automated payout is performed.

## What is needed next
Your public backend URL and the official Stripe Payment Links for each plan. No secret API keys should be sent in chat.
