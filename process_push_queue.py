#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信推送队列处理脚本
读取待发送的推送消息，输出供Hermes发送
"""

import os, json, sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wuming_recruitment.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def process_queue():
    conn = get_db()
    
    # 获取待发送的群推消息（取最新的一条）
    group_msg = conn.execute("""
        SELECT id, message FROM wechat_push_queue 
        WHERE channel='group' AND status='pending' 
        ORDER BY created_at DESC LIMIT 1
    """).fetchone()
    
    # 获取待发送的私信消息
    private_msgs = conn.execute("""
        SELECT q.id, q.user_id, q.message, u.phone, u.wechat
        FROM wechat_push_queue q
        JOIN users u ON q.user_id = u.id
        WHERE q.channel='private' AND q.status='pending'
        ORDER BY q.created_at DESC LIMIT 10
    """).fetchall()
    
    # 标记已处理
    if group_msg:
        conn.execute("UPDATE wechat_push_queue SET status='sent', sent_at=datetime('now','localtime') WHERE id=?", (group_msg["id"],))
    
    for msg in private_msgs:
        conn.execute("UPDATE wechat_push_queue SET status='sent', sent_at=datetime('now','localtime') WHERE id=?", (msg["id"],))
    
    conn.commit()
    conn.close()
    
    # 输出消息供Hermes发送
    if group_msg:
        print(group_msg["message"])
    
    for msg in private_msgs:
        print(msg["message"])

if __name__ == "__main__":
    process_queue()
