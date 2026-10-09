# ESN Hosting Starter Partner Program — one-node deployment

**Development code only. Not yet tested or deployed. No Cloudflare.**

## Environment variables (set privately in your ESN Hosting panel)

```env
DISCORD_BOT_TOKEN=<your existing bot token>
STRIPE_SECRET_KEY=<your Stripe restricted secret key>
STRIPE_STARTER_PAYMENT_LINK_ID=plink_1UOjcEISwShswuKduU8hdd11
STRIPE_POLLING_ENABLED=1
PARTNER_DB_PATH=partners.sqlite3
```

Never publish Stripe or Discord tokens. The Starter link is a monthly subscription. The poller records a commission only when Stripe confirms that the **initial subscription invoice** is paid, not for monthly renewals. Only approved partners qualify.

## Start

Install `pip install -r requirements-partner.txt` and start `python partner_bot.py` on the **existing node**. This file starts a standalone Discord bot. If your ESN Hosting Manager already has a bot process, integrate the PartnerGroup and polling_loop into that existing process instead of starting a second client using the same token. Keep the SQLite database on persistent storage.

## Discord commands

`/partner apply`, `/partner stats`, `/partner link`, `/partner pending`, `/partner approve`, `/partner reject`, `/partner payout`.

Owner-only actions check Discord ID `1515077206886453469`. All partner responses use guild-icon embeds where available. Payout commands update the ledger only; they never transfer funds.

## Before accepting production partner sales

- Verify Stripe restricted-key permissions, correct Payment Link ID, initial-invoice fields and test-mode behavior.
- Test full checkout, attribution, duplicate delivery, first invoice and renewals. No tests have been run in this chat.
- Add refund/dispute reconciliation and stronger self-referral prevention before authorizing payouts.
- The polling implementation scans Checkout Sessions repeatedly; optimize pagination for high volume.
- Ensure the Stripe Checkout Session retains the referral code through `client_reference_id`.
- Merge the development PR only after testing and confirming that the integration does not conflict with your live bot.

No extra hosting provider is needed for the polling approach.
