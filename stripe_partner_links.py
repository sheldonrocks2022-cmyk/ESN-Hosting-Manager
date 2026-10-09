"""Stripe Payment Links referral integration for ESN Hosting.

Install: pip install stripe flask
Environment: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PARTNER_BASE_URL,
PARTNER_DB_PATH (optional). Start with a WSGI server serving app.
Payment Links need client_reference_id supplied via URL query parameter.
"""
import os
import re
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from flask import Flask, request, jsonify, redirect, abort
import stripe
from partner_program import PartnerProgram

app = Flask(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
program = PartnerProgram(os.environ.get("PARTNER_DB_PATH", "partners.sqlite3"))
CODE = re.compile(r"^[A-Z0-9]{8,32}$")
LINKS = {}  # Fill with official Stripe Payment Link URLs, e.g. {"starter":"https://buy.stripe.com/..."}

def payment_link_with_referral(url, code):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "buy.stripe.com":
        raise ValueError("Untrusted Stripe Payment Link")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["client_reference_id"] = code
    return urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode(query),parsed.fragment))

@app.get("/ref/<code>/<plan>")
def referral_redirect(code, plan):
    if not CODE.fullmatch(code): abort(404)
    partner = program.db.execute(
        "SELECT status FROM partners WHERE code=?", (code,)).fetchone()
    if not partner or partner[0] != "approved": abort(404)
    link = LINKS.get(plan)
    if not link: abort(404)
    return redirect(payment_link_with_referral(link,code), code=302)

@app.post("/stripe/webhook")
def stripe_webhook():
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret: return jsonify(error="Webhook not configured"),503
    try:
        event = stripe.Webhook.construct_event(
            request.get_data(), request.headers.get("Stripe-Signature",""), secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify(error="Invalid signature"),400

    kind = event["type"]
    obj = event["data"]["object"]
    if kind not in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        return jsonify(received=True)
    if obj.get("payment_status") != "paid":
        return jsonify(received=True)
    code = obj.get("client_reference_id")
    if not code or not CODE.fullmatch(code):
        return jsonify(received=True)
    customer = obj.get("customer")
    if not customer:
        # Guest checkout requires an alternate stable customer identity strategy.
        return jsonify(received=True, skipped="missing customer")

    # Retrieve full session from Stripe, not values supplied by a browser.
    session = stripe.checkout.Session.retrieve(obj["id"])
    if session.get("payment_status") != "paid" or session.get("client_reference_id") != code:
        return jsonify(error="Session mismatch"),400
    # One-time purchases only for this foundation. Subscriptions need first-invoice handling.
    if session.get("mode") != "payment":
        return jsonify(received=True, skipped="subscription needs first-invoice integration")
    payment_id = session.get("payment_intent")
    amount = session.get("amount_subtotal")
    if not payment_id or not isinstance(amount,int) or amount <= 0:
        return jsonify(received=True, skipped="no eligible payment")
    try:
        program.record_verified_payment(code=code, customer_id=customer,
            payment_id=payment_id, amount_cents=amount,
            verified_by="stripe-webhook:" + event["id"])
    except Exception as exc:
        import sqlite3
        if isinstance(exc, sqlite3.IntegrityError):
            return jsonify(received=True, duplicate=True)
        # Retry webhook later for transient DB failures. No commission for invalid partners.
        if isinstance(exc, ValueError):
            return jsonify(received=True, skipped="ineligible referral")
        raise
    return jsonify(received=True)

@app.get("/health")
def health():
    return jsonify(status="ok", stripe_configured=bool(stripe.api_key and os.environ.get("STRIPE_WEBHOOK_SECRET")))
