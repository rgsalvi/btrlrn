# migrate_users_seen.py
import sqlite3, os
con = sqlite3.connect("mvp.db"); cur = con.cursor()
def has_col(c): cur.execute("PRAGMA table_info(users)"); return any(r[1]==c for r in cur.fetchall())
if not has_col("first_seen"): cur.execute("ALTER TABLE users ADD COLUMN first_seen TEXT")
if not has_col("last_seen"):  cur.execute("ALTER TABLE users ADD COLUMN last_seen  TEXT")
con.commit(); con.close(); print("OK")
