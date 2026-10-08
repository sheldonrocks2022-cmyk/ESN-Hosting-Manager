# ESN Hosting Manager MAX — deployment
This project is under active development. Keep your existing live installation backed up.

1. Set the Python startup file to `main.py`.
2. Install `requirements.txt` in the Python environment.
3. Set `DISCORD_TOKEN` privately in the hosting environment. Do not paste it into Discord or GitHub.
4. Optional: `GUILD_ID` for faster slash command sync; `OWNER_DISCORD_ID` to restrict paid-order notes.
5. Optional: `PANEL_URL` and `PTERODACTYL_CLIENT_API_KEY` for server status, power and backup commands. Use a narrowly scoped client API key. Never use an unrestricted application API key.
6. Restart and confirm Discord login, then run `/setup` and `/configure`.
7. Set log and security channels before enabling `/security` or `/honeypot`.
8. Back up the `data/` directory before updates; it holds SQLite state.

## Current capabilities
- Ticket dropdown, claim, transfer, priority, transcript export, archive/reopen and stats
- Discord configuration persisted in SQLite
- Alert-only security event logging and honeypot decoy-channel change detection
- Manual trial requests and approval tracking
- Customer-linked Pterodactyl status, power signals and on-demand backup requests
- API reachability checks, referrals, templates and owner-only billing notes

## Not yet production-ready
- Verified Stripe billing, subscriptions and grace periods
- Automated Pterodactyl provisioning and upgrades
- Automated backup scheduling/restore
- Full Guardian anti-raid/anti-nuke enforcement and rollback
- Node resource capacity dashboards and crash recovery
- Comprehensive integration tests and deployment validation

**Important:** Do not claim automatic server provisioning, verified payments, or full Guardian protection is available yet.
