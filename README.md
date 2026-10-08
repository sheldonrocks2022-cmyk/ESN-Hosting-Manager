# ESN Hosting Manager MAX

Python Discord bot for ESN Hosting's Pterodactyl-based Discord bot hosting service.

## Planned modules
- Independent ticket panel with dropdown categories, claim/close/reopen, transcripts and staff permissions
- Customer server status and permission-checked start/stop/restart controls
- Hosting plans and 14-day trial tracking
- Guardian-inspired anti-raid, anti-nuke, spam protection and audit logging
- Honeypot decoy roles/channels and alerting with false-positive safeguards
- Monitoring and staff notifications

Runs alongside **ESN Hosting Utilities**, which keeps its own ticket system. **No AI integration.**

## Security
Never commit Discord bot tokens, Pterodactyl API keys, `.env` files, or customer credentials. Test protective actions in a separate Discord server before enabling enforcement in production.

## Status
Repository initialized. The modules listed above are a roadmap, not implemented features yet.
