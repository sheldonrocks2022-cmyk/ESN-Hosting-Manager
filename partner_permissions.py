"""Discord-side authorization boundary for partner administration."""
import os
from functools import wraps

OWNER_DISCORD_ID = "1515077206886453469"

def require_owner(actor_discord_id):
    if str(actor_discord_id) != OWNER_DISCORD_ID:
        raise PermissionError("Only the ESN Hosting owner may perform this action.")

def review_partner(program, actor_discord_id, partner_discord_id, status):
    require_owner(actor_discord_id)
    return program.review(partner_discord_id, status, actor=str(actor_discord_id))

def settle_commission(program, actor_discord_id, payment_id, state):
    require_owner(actor_discord_id)
    return program.settle(payment_id, state, actor=str(actor_discord_id))
