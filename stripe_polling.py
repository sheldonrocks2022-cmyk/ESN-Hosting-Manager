"""Poll Stripe from the existing ESN bot node; no inbound webhook required.

Only records first-time, paid, one-time Checkout Sessions associated with the
configured Starter Payment Link. Subscription Checkout is deliberately skipped.
"""
import os
import logging
import sqlite3
import stripe
from partner_program import PartnerProgram

log = logging.getLogger(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def poll_starter(program: PartnerProgram, payment_link_id: str) -> dict:
    if not stripe.api_key or not payment_link_id.startswith("plink_"):
        raise ValueError("Configure STRIPE_SECRET_KEY and STRIPE_STARTER_PAYMENT_LINK_ID")
    counts = dict(scanned=0, recorded=0, skipped=0, duplicate=0)
    # Stripe list auto-pagination is supported by the official stripe-python SDK.
    for session in stripe.checkout.Session.list(payment_link=payment_link_id, limit=100).auto_paging_iter():
        counts["scanned"] += 1
        if session.get("payment_status") != "paid" or session.get("mode") != "payment":
            counts["skipped"] += 1
            continue
        code = session.get("client_reference_id")
        customer = session.get("customer")
        payment_intent = session.get("payment_intent")
        subtotal = session.get("amount_subtotal")
        if not code or not customer or not payment_intent or not isinstance(subtotal,int) or subtotal<=0:
            counts["skipped"] += 1
            continue
        try:
            program.record_verified_payment(
                code=code, customer_id=customer, payment_id=payment_intent,
                amount_cents=subtotal, verified_by="stripe-poll:"+session["id"])
            counts["recorded"] += 1
        except sqlite3.IntegrityError:
            counts["duplicate"] += 1
        except ValueError:
            counts["skipped"] += 1
    return counts

async def polling_loop(program):
    import asyncio
    while True:
        try:
            result = await asyncio.to_thread(
                poll_starter, PartnerProgram(os.getenv("PARTNER_DB_PATH","partners.sqlite3")), os.getenv("STRIPE_STARTER_PAYMENT_LINK_ID",""))
            log.info("Stripe partner polling: %s", result)
        except Exception:
            log.exception("Stripe partner polling failed")
        await asyncio.sleep(900)
