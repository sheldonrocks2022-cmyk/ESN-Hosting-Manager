"""Poll ESN Starter first subscription invoices on the existing bot node."""
import os
import logging
import sqlite3
import stripe
from partner_program import PartnerProgram

log = logging.getLogger(__name__)

def poll_starter(program, payment_link_id):
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe.api_key or not payment_link_id.startswith("plink_"):
        raise ValueError("Configure STRIPE_SECRET_KEY and STRIPE_STARTER_PAYMENT_LINK_ID")
    counts = dict(scanned=0, recorded=0, skipped=0, duplicate=0)
    sessions = stripe.checkout.Session.list(payment_link=payment_link_id, limit=100)
    for session in sessions.auto_paging_iter():
        counts["scanned"] += 1
        if session.get("mode") != "subscription" or session.get("payment_status") != "paid":
            counts["skipped"] += 1
            continue
        code = session.get("client_reference_id")
        customer = session.get("customer")
        subscription_id = session.get("subscription")
        if not code or not customer or not subscription_id:
            counts["skipped"] += 1
            continue
        # Stripe Checkout supplies the first invoice ID for subscription mode.
        # Never use latest_invoice: that becomes a renewal after month one.
        initial_invoice_id = session.get("invoice")
        first_invoice = stripe.Invoice.retrieve(initial_invoice_id) if initial_invoice_id else None
        if first_invoice and first_invoice.get("subscription") != subscription_id:
            counts["skipped"] += 1
            continue
        if first_invoice and first_invoice.get("billing_reason") != "subscription_create":
            counts["skipped"] += 1
            continue
        if not first_invoice or first_invoice.get("status") != "paid":
            counts["skipped"] += 1
            continue
        subtotal = first_invoice.get("subtotal")
        if not isinstance(subtotal, int) or subtotal <= 0:
            counts["skipped"] += 1
            continue
        try:
            program.record_verified_payment(
                code=code, customer_id=customer,
                payment_id="initial-invoice:" + first_invoice["id"],
                amount_cents=subtotal, verified_by="stripe-poll:" + session["id"])
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
            # Separate SQLite connection for the worker thread.
            result = await asyncio.to_thread(
                poll_starter,
                PartnerProgram(os.getenv("PARTNER_DB_PATH", "partners.sqlite3")),
                os.getenv("STRIPE_STARTER_PAYMENT_LINK_ID", "plink_1UOjcEISwShswuKduU8hdd11"))
            log.info("Stripe subscription polling: %s", result)
        except Exception:
            log.exception("Stripe subscription polling failed")
        await asyncio.sleep(900)
