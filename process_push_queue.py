#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信推送队列处理脚本
可作为 cron 定时任务或手动执行
处理 wechat_push_queue 中 status='pending' 的条目

用法:
  python3 process_push_queue.py          # 处理队列
  python3 process_push_queue.py --dry-run # 只查看不处理
  crontab: */1 * * * * cd /home/ubuntu/hermes-web && python3 process_push_queue.py >> /tmp/push_queue.log 2>&1
"""

import os, sys, json, sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wuming_recruitment.db")
MINI_APPID = "wxb64c75249902e850"
MINI_APPSECRET = "00c3ee32fcaa0c044bcfe33488ab0a8f"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_access_token(conn):
    """获取小程序 access_token"""
    try:
        import httpx
        row = conn.execute("SELECT access_token, token_expires_at FROM wechat_mini_config WHERE id=1").fetchone()
        if row and row["access_token"] and row["token_expires_at"]:
            expires = datetime.fromisoformat(row["token_expires_at"])
            if datetime.now() < expires:
                return row["access_token"]
        
        resp = httpx.get("https://api.weixin.qq.com/cgi-bin/token", params={
            "grant_type": "client_credential",
            "appid": MINI_APPID,
            "secret": MINI_APPSECRET
        }, timeout=10)
        data = resp.json()
        if "access_token" in data:
            token = data["access_token"]
            expires_in = data.get("expires_in", 7200)
            expires_at = (datetime.now() + __import__("datetime").timedelta(seconds=expires_in)).isoformat()
            conn.execute("UPDATE wechat_mini_config SET access_token=?, token_expires_at=? WHERE id=1", (token, expires_at))
            conn.commit()
            return token
    except Exception as e:
        print(f"[ERROR] 获取access_token失败: {e}")
    return None

def process_queue(dry_run=False):
    conn = get_db()
    
    # 获取待发送的推送消息
    pending = conn.execute("""
        SELECT id, job_id, user_id, channel, message, created_at
        FROM wechat_push_queue 
        WHERE status='pending' 
        ORDER BY created_at ASC 
        LIMIT 50
    """).fetchall()
    
    if not pending:
        if not dry_run:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 无待处理推送")
        conn.close()
        return 0
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 发现 {len(pending)} 条待处理推送")
    
    sent_count = 0
    failed_count = 0
    
    for entry in pending:
        entry_id = entry["id"]
        user_id = entry["user_id"]
        channel = entry["channel"]
        message = entry["message"]
        
        if dry_run:
            print(f"  [DRY-RUN] id={entry_id} ch={channel} user={user_id} msg={message[:50]}...")
            continue
        
        sent_ok = False
        
        if channel == "private" and user_id > 0:
            # 私信：由 Hermes cron 处理（保留 pending）
            print(f"  [PUSH-CRON] Hermes跳过私信 id={entry_id} user={user_id}")
            continue
        
        elif channel == "group":
            # 群推：由 Hermes cron 处理（保留 pending）
            print(f"  [PUSH-CRON] Hermes跳过群推 id={entry_id}")
            continue
        
        new_status = "sent" if sent_ok else "failed"
        conn.execute(
            "UPDATE wechat_push_queue SET status=?, sent_at=datetime('now','localtime') WHERE id=?",
            (new_status, entry_id)
        )
        
        if sent_ok:
            sent_count += 1
        else:
            failed_count += 1
        
        print(f"  {'✅' if sent_ok else '❌'} id={entry_id} ch={channel} user={user_id} -> {new_status}")
    
    conn.commit()
    conn.close()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 处理完成: 成功={sent_count} 失败={failed_count}")
    return sent_count

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    process_queue(dry_run=dry_run)
