import sqlite3
from pathlib import Path

db = Path("data/storage.db").resolve()
print("db", db)
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
rows = conn.execute(
    """
    SELECT id, url, hash, timestamp
    FROM snapshots
    WHERE source_id = ?
    ORDER BY id DESC
    LIMIT 15
    """,
    ("local-multipage-change-test",),
).fetchall()
print("snapshots:")
for row in rows:
    print(dict(row))
diffs = conn.execute(
    """
    SELECT id, old_snapshot_id, new_snapshot_id, created_at
    FROM diffs
    WHERE source_id = ?
    ORDER BY id DESC
    LIMIT 10
    """,
    ("local-multipage-change-test",),
).fetchall()
print("diffs:", [dict(item) for item in diffs])
