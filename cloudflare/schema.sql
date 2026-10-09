CREATE TABLE IF NOT EXISTS partners (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 discord_id TEXT NOT NULL UNIQUE,
 code TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','suspended')),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS referrals (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 partner_id INTEGER NOT NULL REFERENCES partners(id),
 customer_id TEXT NOT NULL UNIQUE,
 stripe_payment_id TEXT NOT NULL UNIQUE,
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
 commission_cents INTEGER NOT NULL CHECK(commission_cents>=0),
 rate INTEGER NOT NULL,
 state TEXT NOT NULL DEFAULT 'held' CHECK(state IN ('held','eligible','paid','reversed')),
 created_at TEXT NOT NULL,
 eligible_after TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_referrals_partner ON referrals(partner_id);
