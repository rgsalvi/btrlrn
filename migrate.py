import sqlite3, os

db = "mvp.db"
print("DB path exists?", os.path.exists(db), "->", os.path.abspath(db))
con = sqlite3.connect(db)
cur = con.cursor()

def has_col(table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1].lower() == col.lower() for r in cur.fetchall())

added = []

if not has_col("users","language"):
    cur.execute("ALTER TABLE users ADD COLUMN language TEXT")
    cur.execute("UPDATE users SET language='en' WHERE language IS NULL")
    added.append("users.language")

if not has_col("users","phone"):
    cur.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    added.append("users.phone")

if not has_col("users","state"):
    cur.execute("ALTER TABLE users ADD COLUMN state TEXT")
    added.append("users.state")

con.commit(); con.close()
print("Migration complete. Added:", ", ".join(added) or "nothing (already up to date)")
