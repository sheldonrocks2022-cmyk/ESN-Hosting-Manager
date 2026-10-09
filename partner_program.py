"""ESN Hosting affiliate ledger. Standard-library-only, no payout automation."""
import sqlite3
import secrets
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP

TIERS = ((15, 15), (5, 10), (0, 5))
def now():
    return datetime.now(timezone.utc).isoformat()

class PartnerProgram:
    def __init__(self, database="partners.sqlite3"):
        self.db = sqlite3.connect(database)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS partners(
          id INTEGER PRIMARY KEY, discord_id TEXT NOT NULL UNIQUE,
          code TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'pending'
          CHECK(status IN ('pending','approved','rejected','suspended')),
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS referrals(
          id INTEGER PRIMARY KEY, partner_id INTEGER NOT NULL REFERENCES partners(id),
          customer_id TEXT NOT NULL UNIQUE, stripe_payment_id TEXT NOT NULL UNIQUE,
          amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
          commission_cents INTEGER NOT NULL CHECK(commission_cents>=0),
          rate INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'held'
          CHECK(state IN ('held','eligible','paid','reversed')),
          created_at TEXT NOT NULL, eligible_after TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
          detail TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        self.db.commit()

    def audit(self, actor, action, detail):
        self.db.execute("INSERT INTO events(actor,action,detail,created_at) VALUES(?,?,?,?)",
                        (actor,action,str(detail),now()))

    def apply(self, discord_id):
        code = secrets.token_urlsafe(9).replace("-", "").replace("_", "").upper()
        with self.db:
            self.db.execute("INSERT INTO partners(discord_id,code,created_at) VALUES(?,?,?)",
                            (str(discord_id),code,now()))
            self.audit(str(discord_id),"application",code)
        return code

    def review(self, discord_id, status, actor):
        if status not in ("approved","rejected","suspended"):
            raise ValueError("Invalid partner status")
        with self.db:
            cur = self.db.execute("UPDATE partners SET status=? WHERE discord_id=?",
                                  (status,str(discord_id)))
            if cur.rowcount != 1:
                raise ValueError("Partner not found")
            self.audit(actor,"review",f"{discord_id}: {status}")

    def stats(self, discord_id):
        p = self.db.execute("SELECT id,code,status FROM partners WHERE discord_id=?",
                            (str(discord_id),)).fetchone()
        if not p: return None
        verified = self.db.execute(
            "SELECT count(*) FROM referrals WHERE partner_id=? AND state IN ('held','eligible','paid')",
            (p[0],)).fetchone()[0]
        earnings = self.db.execute(
            "SELECT COALESCE(SUM(commission_cents),0) FROM referrals WHERE partner_id=? AND state IN ('held','eligible','paid')",
            (p[0],)).fetchone()[0]
        rate = next(rate for threshold,rate in TIERS if verified >= threshold)
        return dict(code=p[1],status=p[2],verified=verified,rate=rate,earnings_cents=earnings)

    def record_verified_payment(self, *, code, customer_id, payment_id, amount_cents,
                                verified_by, customer_discord_id=None):
        """Call ONLY after server-side Stripe webhook signature and payment verification.
        amount_cents must be eligible net first-payment amount, excluding tax."""
        if not verified_by:
            raise ValueError("Verification evidence required")
        p = self.db.execute("SELECT id,discord_id,status FROM partners WHERE code=?",(code,)).fetchone()
        if not p or p[2] != "approved": raise ValueError("Partner not approved")
        if customer_discord_id and str(customer_discord_id) == p[1]:
            raise ValueError("Self referral")
        if not isinstance(amount_cents,int) or amount_cents <= 0:
            raise ValueError("Invalid payment amount")
        count = self.db.execute(
            "SELECT count(*) FROM referrals WHERE partner_id=? AND state IN ('held','eligible','paid')",
            (p[0],)).fetchone()[0]
        rate = next(rate for threshold,rate in TIERS if count >= threshold)
        commission = int((Decimal(amount_cents)*Decimal(rate)/100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
        eligible_after = (datetime.now(timezone.utc)+timedelta(days=30)).isoformat()
        with self.db:
            self.db.execute("""INSERT INTO referrals(partner_id,customer_id,stripe_payment_id,
              amount_cents,commission_cents,rate,created_at,eligible_after)
              VALUES(?,?,?,?,?,?,?,?)""",
              (p[0],str(customer_id),str(payment_id),amount_cents,commission,rate,now(),eligible_after))
            self.audit(verified_by,"payment_verified",payment_id)
        return commission

    def settle(self, payment_id, state, actor):
        """Owner-only service layer must authorize actor; never expose to customers."""
        if state not in ("eligible","paid","reversed"): raise ValueError("Invalid state")
        row = self.db.execute("SELECT state,eligible_after FROM referrals WHERE stripe_payment_id=?",
                              (payment_id,)).fetchone()
        if not row: raise ValueError("Payment not found")
        if state == "eligible" and (row[0] != "held" or datetime.fromisoformat(row[1]) > datetime.now(timezone.utc)):
            raise ValueError("Not yet eligible")
        if state == "paid" and row[0] != "eligible": raise ValueError("Not eligible for payout")
        if state == "reversed" and row[0] == "paid": raise ValueError("Paid referral requires manual recovery")
        with self.db:
            self.db.execute("UPDATE referrals SET state=? WHERE stripe_payment_id=?",(state,payment_id))
            self.audit(actor,"settle",f"{payment_id}: {state}")
