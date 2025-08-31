# migrate_history_lesson_id.py
# Adds lesson_id column to history if missing and attempts to backfill it for recent rows
import sqlite3

db = "mvp.db"
con = sqlite3.connect(db)
cur = con.cursor()

def has_col(table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1].lower() == col.lower() for r in cur.fetchall())

added = []
if not has_col("history", "lesson_id"):
    cur.execute("ALTER TABLE history ADD COLUMN lesson_id INTEGER")
    added.append("history.lesson_id")

# Attempt to backfill lesson_id for recent history rows
cur.execute("SELECT id, wa_id, subject, level, taken_at FROM history WHERE lesson_id IS NULL")
rows = cur.fetchall()
for row in rows:
    hist_id, wa_id, subject, level, taken_at = row
    # Find matching lesson
    cur.execute("SELECT id FROM lessons WHERE wa_id=? AND subject_label=? AND level=? ORDER BY created_at DESC LIMIT 1", (wa_id, subject, level))
    lesson = cur.fetchone()
    if lesson:
        cur.execute("UPDATE history SET lesson_id=? WHERE id=?", (lesson[0], hist_id))
con.commit(); con.close()
print("Migration complete. Added:", ", ".join(added) or "nothing (already up to date)")
