"""Persistent guild settings, with no secrets stored in Discord."""
import os
import sqlite3
from pathlib import Path

Path("data").mkdir(exist_ok=True)
db = sqlite3.connect("data/esn.sqlite3")
db.execute("CREATE TABLE IF NOT EXISTS settings (guild INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(guild,key))")
db.execute("CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY, guild INTEGER, kind TEXT, actor INTEGER, detail TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
db.execute("CREATE TABLE IF NOT EXISTS trials (user INTEGER PRIMARY KEY, guild INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, expires_at TEXT, status TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS subscriptions (server TEXT PRIMARY KEY, guild INTEGER, user INTEGER, plan TEXT, expires_at TEXT, status TEXT)")
db.commit()

def get(guild, key, default=""):
    row=db.execute("SELECT value FROM settings WHERE guild=? AND key=?", (guild,key)).fetchone()
    return row[0] if row else default

def put(guild, key, value):
    db.execute("INSERT INTO settings(guild,key,value) VALUES(?,?,?) ON CONFLICT(guild,key) DO UPDATE SET value=excluded.value",(guild,key,str(value)))
    db.commit()

def audit(guild, kind, actor, detail):
    db.execute("INSERT INTO incidents(guild,kind,actor,detail) VALUES(?,?,?,?)",(guild,kind,actor,detail[:1500]))
    db.commit()

def role_allowed(member):
    role_id=int(get(member.guild.id,"staff_role",os.getenv("STAFF_ROLE_ID") or 0))
    return member.guild_permissions.manage_guild or (role_id and any(r.id==role_id for r in member.roles))

def owner_allowed(member):
    owner=int(os.getenv("OWNER_DISCORD_ID") or 0)
    return bool(owner and member.id==owner)
