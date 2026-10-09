# Cloudflare free-tier deployment (not yet live)

Files: `worker.js`, `schema.sql`. This Worker handles ONLY the ESN Starter Payment Link.

1. Create a Cloudflare account, Worker and D1 database. Attach D1 binding named `DB`.
2. Run `schema.sql` against the D1 database.
3. Set Worker secrets `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`. Never commit them.
4. Set `STARTER_PAYMENT_LINK_ID` to the Stripe Payment Link object's `plink_...` identifier (NOT the buy.stripe.com URL). Retrieve this ID in Stripe Dashboard.
5. Deploy the Worker. Stripe webhook endpoint: `https://YOUR-WORKER.workers.dev/stripe/webhook`. Subscribe to `checkout.session.completed` and `checkout.session.async_payment_succeeded`.
6. Referral redirect format: `https://YOUR-WORKER.workers.dev/ref/CODE/starter`.
7. Use Stripe test-mode credentials and a test-mode Payment Link for end-to-end verification first. The current STARTER URL is live-mode and must not be used for test payments.

## Blockers before launch
- The Python Discord bot currently uses local SQLite; it DOES NOT share D1 data. Add an authenticated Worker API for application/review/stats/payout operations, then switch Discord commands to that API. Never expose D1 administrative access publicly.
- Validate the exact Stripe Payment Link ID, subscription mode, and tax/discount calculation. Subscription-mode payments are deliberately skipped by the Worker.
- Add verified refund/dispute handling and an audit trail. Harden self-referral prevention beyond matching Discord IDs.
- Add automated integration tests, database migration plan, rate limiting, and owner payout reconciliation. Never automatically send payouts.
- Stripe webhook signature verification is required; keep the signing secret private.

No production deployment has been performed.
