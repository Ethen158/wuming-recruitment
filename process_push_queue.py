#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信推送队列处理脚本
由Hermes cronjob调用，读取待发送的推送并输出消息内容
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
    
    conn.close()
    
    results = []
    
    # 群推消息
    if group_msg:
        results.append(f"📢 群推消息:\n{group_msg['message']}\n---")
    
    # 私信消息
    for msg in private_msgs:
        contact = msg['phone'] or msg['wechat'] or '未绑定'
        results.append(f"💌 私信给 {contact}:\n{msg['message']}")
    
    if results:
        print("=== 武鸣招聘推送队列 ===")
        for r in results:
            print(r)
    else:
        # 空输出 = 静默，不发送消息
        pass

if __name__ == "__main__":
    process_queue()
