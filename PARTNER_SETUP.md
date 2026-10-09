# Partner bot setup

1. Review and merge PR #1 after testing.
2. Install Python 3.10+ and `pip install -r requirements-partner.txt`.
3. Set `DISCORD_BOT_TOKEN` securely in the hosting environment. Do not commit tokens.
4. Optionally set `TEST_GUILD_ID` to register commands in one test server immediately.
5. Run `python partner_bot.py` from the repository root.
6. Test `/partner apply` and `/partner stats`; only Discord user 1515077206886453469 can use approve/reject/payout.
7. Store the SQLite database on persistent storage and back it up.

The bot's responses use the invoking Discord guild's icon when available, including the embed thumbnail, author, and footer. In DMs, the branding falls back to ESN Hosting text.

**Not production ready:** Stripe payment verification, attribution, refund processing, partner dashboard, owner review queues, and actual payout integration are not implemented. Do not process real commissions yet. The `/partner payout` command only changes ledger state and never transfers money.

Do not run this alongside an existing bot using the same token without first merging command trees into a single process. Otherwise gateway sessions and command registrations may conflict.
