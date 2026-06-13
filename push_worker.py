#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
武鸣招聘 - 推送通知脚本
用于定时任务：匹配职位并推送通知到网站 + 微信
"""

import os, json, sqlite3, subprocess
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wuming_recruitment.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_matching_jobs(settings):
    """根据用户设置筛选匹配的职位"""
    conn = get_db()
    
    conditions = ["status='active'"]
    params = []
    
    # 分类筛选
    if settings["push_categories"]:
        cats = json.loads(settings["push_categories"]) if isinstance(settings["push_categories"], str) else settings["push_categories"]
        if cats:
            placeholders = ",".join(["?" for _ in cats])
            conditions.append(f"category IN ({placeholders})")
            params.extend(cats)
    
    # 薪资筛选
    if settings["push_salary_min"] > 0:
        conditions.append("salary LIKE ?")
        params.append(f"%{settings['push_salary_min']}%")
    
    # 最新职位筛选（7天内）
    if settings["push_latest"]:
        conditions.append("created_at >= datetime('now', '-7 days', 'localtime')")
    
    where = " AND ".join(conditions)
    sql = f"SELECT * FROM jobs WHERE {where} ORDER BY created_at DESC LIMIT 10"
    
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_notification(user_id, job, channel="website"):
    """创建网站通知"""
    conn = get_db()
    conn.execute("""INSERT INTO notifications (user_id, job_id, title, content, channel)
        VALUES (?, ?, ?, ?, ?)""", (
        user_id,
        job["id"],
        f"🆕 新职位推荐：{job['title']}",
        f"{job['company']} - {job.get('salary', '面议')}",
        channel
    ))
    conn.commit()
    conn.close()

def send_wechat_message(user_id, job):
    """通过Hermes发送微信消息"""
    # 获取用户的微信绑定信息
    conn = get_db()
    settings = conn.execute("SELECT wechat_bindcode FROM user_push_settings WHERE user_id=?", (user_id,)).fetchone()
    user = conn.execute("SELECT nickname FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    
    if not settings or not settings["wechat_bindcode"]:
        return False
    
    # 构建消息内容
    msg = f"""🔔 武鸣招聘新职位推荐

📌 {job['title']}
🏢 {job['company']}
💰 {job.get('salary', '面议')}
📍 {job.get('location', '武鸣')}

查看详情：https://wuming.example.com/job/{job['id']}
"""
    
    # 调用Hermes发送消息（这里需要根据实际的Hermes API调整）
    # 实际实现时，可以使用Hermes的send_message工具或API
    print(f"[WECHAT] 发送给用户{user_id}: {job['title']}")
    return True

def push_for_user(user_id):
    """为单个用户执行推送"""
    conn = get_db()
    settings = conn.execute("SELECT * FROM user_push_settings WHERE user_id=? AND push_enabled=1", (user_id,)).fetchone()
    conn.close()
    
    if not settings:
        return 0
    
    # 检查推送频率
    now = datetime.now()
    if settings["push_frequency"] == "daily":
        last_push = dict(settings).get("last_push_at")
        if last_push:
            last_push_dt = datetime.strptime(last_push, "%Y-%m-%d %H:%M:%S")
            if (now - last_push_dt).days < 1:
                return 0
    elif settings["push_frequency"] == "weekly":
        last_push = dict(settings).get("last_push_at")
        if last_push:
            last_push_dt = datetime.strptime(last_push, "%Y-%m-%d %H:%M:%S")
            if (now - last_push_dt).days < 7:
                return 0
    
    # 获取匹配的职位
    jobs = get_matching_jobs(settings)
    if not jobs:
        return 0
    
    # 推送
    count = 0
    for job in jobs[:5]:  # 最多推送5条
        # 创建网站通知
        create_notification(user_id, job, "website")
        
        # 发送微信消息
        send_wechat_message(user_id, job)
        
        count += 1
    
    # 更新最后推送时间
    conn = get_db()
    conn.execute("UPDATE user_push_settings SET last_push_at=datetime('now','localtime') WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    
    return count

def run_push_job():
    """执行推送任务（供cron调用）"""
    conn = get_db()
    users = conn.execute("SELECT user_id FROM user_push_settings WHERE push_enabled=1").fetchall()
    conn.close()
    
    total = 0
    for u in users:
        count = push_for_user(u["user_id"])
        total += count
        if count > 0:
            print(f"✅ 用户{u['user_id']}: 推送{count}条职位")
    
    print(f"\n📊 推送完成: 共{len(users)}个用户, {total}条通知")
    return total

if __name__ == "__main__":
    run_push_job()
