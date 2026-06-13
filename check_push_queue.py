import sqlite3, json, datetime

DB_PATH = '/home/ubuntu/hermes-web/wuming_recruitment.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Check if table exists
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', [t[0] for t in tables])

# Check pending messages
rows = conn.execute("SELECT * FROM wechat_push_queue WHERE status='pending'").fetchall()
print('Pending count:', len(rows))
for r in rows:
    print(json.dumps(dict(r), ensure_ascii=False, default=str))

# Check user_push_settings schema
try:
    cols = conn.execute("PRAGMA table_info(user_push_settings)").fetchall()
    print('user_push_settings columns:', [(c[1], c[2]) for c in cols])
except:
    print('user_push_settings table not found')

conn.close()
