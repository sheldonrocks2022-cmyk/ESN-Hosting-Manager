# ESN Starter Stripe polling (no Cloudflare)

This is a development integration, not yet deployed. Only the Starter plan is included.

1. Install `pip install stripe discord.py` on the existing Python hosting node.
2. In the hosting panel's private environment settings set:
   - `STRIPE_SECRET_KEY`: your Stripe restricted secret key with permission to read Checkout Sessions.
   - `STRIPE_STARTER_PAYMENT_LINK_ID`: the actual `plink_...` ID for the existing Starter Payment Link (find in Stripe dashboard). This is not the buy.stripe.com URL.
   - `STRIPE_POLLING_ENABLED=1` after completing test checks.
   - `PARTNER_DB_PATH`: persistent local database path, shared by the bot and polling task.
3. The partner redirect `/ref/CODE/starter` still requires an HTTP server, but you can instead construct the partner-specific Stripe URL `https://buy.stripe.com/9B628scRZ2jZ9Nl5pZdnW04?client_reference_id=CODE` inside a bot command. A direct URL alone is not secure attribution; a customer can modify the code.
4. Poller checks paid, one-time sessions only. Subscription checkouts are intentionally skipped.
5. Confirm test-mode Checkout Sessions with a test-mode Starter Payment Link before enabling real payments. Do not paste Stripe secret keys into Discord or GitHub.

## Production blockers
- Add bot-side referral link command and robust identity attribution / self-referral controls.
- Validate actual Stripe Payment Link ID and whether Starter is subscription-mode.
- Handle refunds and disputes before payouts; ensure tax and discount calculation policy.
- Add reconciliation, pagination performance limits, rate limiting, monitoring, and integration tests.
- Only Kavero's owner ID may authorize manual payout state transitions.
- The current Stripe poller scans all sessions for the configured link each cycle; optimize incremental scans as volume grows.

Cloudflare is not required or used by this polling path.
