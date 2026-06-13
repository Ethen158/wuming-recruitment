#!/usr/bin/env python3
import sqlite3, sys
DB = '/home/ubuntu/hermes-web/wuming_recruitment.db'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT q.id, q.channel, q.message, q.user_id, u.nickname FROM wechat_push_queue q LEFT JOIN users u ON q.user_id = u.id WHERE q.status='pending' ORDER BY q.id ASC").fetchall()
if not rows:
    conn.close()
    sys.exit(0)
ids = []
seen_msgs = set()
for r in rows:
    ids.append(r['id'])
    ch = r['channel']
    msg = (r['message'] or '').strip()
    if ch == 'group':
        if msg not in seen_msgs:
            print(msg)
            seen_msgs.add(msg)
    elif ch == 'private':
        nick = r['nickname'] or f"用户{r['user_id']}"
        print(f"[私信_{nick}] {msg}")
if ids:
    conn.execute("UPDATE wechat_push_queue SET status='sent', sent_at=datetime('now','localtime') WHERE id IN ({})".format(','.join(['?']*len(ids))), ids)
    conn.commit()
    print(f"[已处理 {len(ids)} 条推送]")
conn.close()
