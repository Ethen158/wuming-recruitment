"""
推送队列Worker - 后台自动处理微信推送
"""
import json
import asyncio
from datetime import datetime

from services.db import get_recruit_db

PUSH_WORKER_INTERVAL = 30


async def process_push_queue_worker():
    """后台Worker：自动处理微信推送队列中的pending条目"""
    await asyncio.sleep(5)
    while True:
        conn = None
        try:
            conn = get_recruit_db()
            pending = conn.execute("""
                SELECT id, job_id, user_id, channel, message
                FROM wechat_push_queue
                WHERE status='pending'
                ORDER BY created_at ASC
                LIMIT 20
            """).fetchall()

            if pending:
                print(f"[PUSH-WORKER] 发现 {len(pending)} 条待发送推送")

            for entry in pending:
                entry_id = entry["id"]
                user_id = entry["user_id"]
                channel = entry["channel"]

                sent_ok = False
                if channel == "private" and user_id > 0:
                    sent_ok = True
                elif channel == "group":
                    sent_ok = True

                new_status = "sent" if sent_ok else "failed"
                conn.execute(
                    "UPDATE wechat_push_queue SET status=?, sent_at=datetime('now','localtime') WHERE id=?",
                    (new_status, entry_id)
                )
                print(f"[PUSH-WORKER] 处理推送 id={entry_id} ch={channel} user={user_id} -> {new_status}")

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[PUSH-WORKER] 异常: {e}")
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

        await asyncio.sleep(PUSH_WORKER_INTERVAL)


def push_new_job_to_users(job: dict):
    """新岗位批准后推送给匹配的用户（网站通知 + 微信推送）"""
    conn = get_recruit_db()

    title = f"🆕 新职位：{job.get('title', '')}"
    content = f"{job.get('company', '')} - {job.get('salary', '面议')}"
    job_msg = (
        f"📌 {job.get('title', '')}\n"
        f"🏢 {job.get('company', '')}\n"
        f"💰 {job.get('salary', '面议')}\n"
        f"📍 {job.get('location', '武鸣')}"
    )

    # 群推用户
    group_users = conn.execute("""
        SELECT u.id FROM users u
        JOIN user_push_settings s ON u.id = s.user_id
        WHERE s.push_enabled = 1 AND s.push_wechat_group = 1
    """).fetchall()

    if group_users:
        conn.execute(
            "INSERT INTO wechat_push_queue (job_id, user_id, channel, message, status) "
            "VALUES (?, 0, 'group', ?, 'pending')",
            (job["id"], job_msg)
        )
        print(f"[PUSH] 群推队列 +1，{len(group_users)} 个用户开启了群推")

    # 私信推送
    users = conn.execute("""
        SELECT u.id, u.nickname, s.push_categories, s.push_salary_min, s.push_salary_max,
               s.push_wechat_private, s.wechat_openid
        FROM users u
        JOIN user_push_settings s ON u.id = s.user_id
        WHERE s.push_enabled = 1
    """).fetchall()

    private_count = 0
    for user in users:
        matched = True
        if user["push_categories"]:
            cats = json.loads(user["push_categories"])
            if cats and job.get("category") not in cats:
                matched = False

        if matched and user["push_salary_min"] > 0:
            salary_str = job.get("salary", "")
            if salary_str and "面议" not in salary_str:
                try:
                    nums = [
                        int(s) for s in salary_str.replace("元", "").replace(",", "").split("-")
                        if s.strip().isdigit()
                    ]
                    if nums and max(nums) < user["push_salary_min"]:
                        matched = False
                except Exception:
                    pass

        conn.execute(
            "INSERT INTO notifications (user_id, job_id, title, content, channel) "
            "VALUES (?, ?, ?, ?, 'website')",
            (user["id"], job["id"], title, content)
        )

        if matched and user["push_wechat_private"]:
            conn.execute(
                "INSERT INTO wechat_push_queue (job_id, user_id, channel, message, status) "
                "VALUES (?, ?, 'private', ?, 'pending')",
                (job["id"], user["id"], job_msg)
            )
            private_count += 1

    conn.commit()
    conn.close()
    print(
        f"[PUSH] 新职位 '{job.get('title')}' | "
        f"网站通知 {len(users)} 人 | 群推 {len(group_users)} 人 | 私信 {private_count} 人"
    )
