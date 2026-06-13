"""
API路由 - 收藏、推送设置、通知、Hermes桥接、Webhook
"""
import json
import re
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from services.db import get_recruit_db
from services.auth import check_user

router = APIRouter()


# ====== 收藏功能 ======

@router.post("/favorites/{job_id}")
async def toggle_favorite(job_id: int, request: Request):
    uid = check_user(request)
    if not uid:
        return {"error": "请先登录"}
    conn = get_recruit_db()
    existing = conn.execute(
        "SELECT id FROM favorites WHERE user_id=? AND job_id=?", (uid, job_id)
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM favorites WHERE user_id=? AND job_id=?", (uid, job_id))
        conn.commit()
        conn.close()
        return {"favorited": False}
    conn.execute("INSERT INTO favorites (user_id, job_id) VALUES (?, ?)", (uid, job_id))
    conn.commit()
    conn.close()
    return {"favorited": True}


@router.get("/favorites")
async def get_favorites(request: Request):
    uid = check_user(request)
    if not uid:
        return {"favorites": []}
    conn = get_recruit_db()
    rows = conn.execute("SELECT job_id FROM favorites WHERE user_id=?", (uid,)).fetchall()
    conn.close()
    return {"favorites": [r["job_id"] for r in rows]}


# ====== 推送设置API ======

@router.get("/push/settings")
async def get_push_settings(request: Request):
    user_id = check_user(request)
    if not user_id:
        return JSONResponse({"error": "未登录"}, status_code=401)
    conn = get_recruit_db()
    row = conn.execute("SELECT * FROM user_push_settings WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    defaults = {"push_enabled": 1, "push_latest": 1, "push_categories": [],
                "push_salary_min": 0, "push_salary_max": 99999, "push_frequency": "daily",
                "push_wechat_private": 0, "push_wechat_group": 1, "wechat_bindcode": ""}
    if row:
        defaults.update({"push_enabled": row["push_enabled"], "push_latest": row["push_latest"],
            "push_categories": json.loads(row["push_categories"]) if row["push_categories"] else [],
            "push_salary_min": row["push_salary_min"], "push_salary_max": row["push_salary_max"],
            "push_frequency": row["push_frequency"], "push_wechat_private": row["push_wechat_private"],
            "push_wechat_group": row["push_wechat_group"], "wechat_bindcode": row["wechat_bindcode"] or ""})
    return JSONResponse(defaults)


@router.post("/push/settings")
async def save_push_settings(request: Request):
    user_id = check_user(request)
    if not user_id:
        return JSONResponse({"error": "未登录"}, status_code=401)
    data = await request.json()
    conn = get_recruit_db()
    existing = conn.execute("SELECT user_id FROM user_push_settings WHERE user_id=?", (user_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE user_push_settings SET push_enabled=?, push_latest=?, push_categories=?, "
            "push_salary_min=?, push_salary_max=?, push_frequency=?, "
            "push_wechat_private=?, push_wechat_group=?, updated_at=datetime('now','localtime') WHERE user_id=?",
            (data.get("push_enabled", 1), data.get("push_latest", 1),
             json.dumps(data.get("push_categories", []), ensure_ascii=False),
             data.get("push_salary_min", 0), data.get("push_salary_max", 99999),
             data.get("push_frequency", "daily"),
             data.get("push_wechat_private", 0), data.get("push_wechat_group", 1), user_id))
    else:
        conn.execute(
            "INSERT INTO user_push_settings (user_id, push_enabled, push_latest, push_categories, "
            "push_salary_min, push_salary_max, push_frequency, push_wechat_private, push_wechat_group) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, data.get("push_enabled", 1), data.get("push_latest", 1),
             json.dumps(data.get("push_categories", []), ensure_ascii=False),
             data.get("push_salary_min", 0), data.get("push_salary_max", 99999),
             data.get("push_frequency", "daily"),
             data.get("push_wechat_private", 0), data.get("push_wechat_group", 1)))
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True})


@router.post("/push/bind-wechat")
async def bind_wechat(request: Request):
    data = await request.json()
    bind_code = data.get("bind_code", "").strip()
    wechat_openid = data.get("wechat_openid", "")
    if not bind_code or not wechat_openid:
        return JSONResponse({"error": "参数不完整"}, status_code=400)
    conn = get_recruit_db()
    row = conn.execute("SELECT user_id FROM user_push_settings WHERE wechat_bindcode=?", (bind_code,)).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "绑定码无效"}, status_code=404)
    conn.execute("UPDATE user_push_settings SET wechat_openid=?, push_wechat_private=1 WHERE wechat_bindcode=?",
                 (wechat_openid, bind_code))
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True, "message": "绑定成功"})


# ====== 通知API ======

@router.get("/notifications")
async def get_notifications(request: Request, limit: int = Query(20, ge=1, le=100)):
    user_id = check_user(request)
    if not user_id:
        return JSONResponse({"error": "未登录"}, status_code=401)
    conn = get_recruit_db()
    rows = conn.execute(
        "SELECT n.*, j.title as job_title, j.company, "
        "COALESCE(j.salary_min, 0) as salary_min, COALESCE(j.salary_max, 0) as salary_max, j.salary_unit "
        "FROM notifications n LEFT JOIN jobs j ON n.job_id = j.id "
        "WHERE n.user_id=? ORDER BY n.created_at DESC LIMIT ?", (user_id, limit)
    ).fetchall()
    unread = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user_id,)).fetchone()[0]
    conn.close()
    return JSONResponse({"notifications": [dict(r) for r in rows], "unread": unread})


@router.post("/notifications/read")
async def mark_notifications_read(request: Request):
    user_id = check_user(request)
    if not user_id:
        return JSONResponse({"error": "未登录"}, status_code=401)
    data = await request.json()
    conn = get_recruit_db()
    if data.get("all"):
        conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0", (user_id,))
    elif data.get("ids"):
        placeholders = ",".join(["?" for _ in data["ids"]])
        conn.execute(f"UPDATE notifications SET is_read=1 WHERE user_id=? AND id IN ({placeholders})",
                     [user_id] + data["ids"])
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True})


@router.get("/notifications/unread-count")
async def get_unread_count(request: Request):
    user_id = check_user(request)
    if not user_id:
        return JSONResponse({"unread": 0})
    conn = get_recruit_db()
    count = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user_id,)).fetchone()[0]
    conn.close()
    return JSONResponse({"unread": count})


# ====== Hermes推送桥接 ======

@router.get("/hermes/pending-push")
async def hermes_get_pending_push():
    conn = get_recruit_db()
    rows = conn.execute("""
        SELECT q.id, q.job_id, q.user_id, q.channel, q.message, q.created_at,
               s.wechat_openid, u.nickname, u.phone
        FROM wechat_push_queue q
        LEFT JOIN user_push_settings s ON q.user_id = s.user_id
        LEFT JOIN users u ON q.user_id = u.id
        WHERE q.status='pending' ORDER BY q.id ASC LIMIT 50
    """).fetchall()
    result = [{"id": r["id"], "job_id": r["job_id"], "user_id": r["user_id"],
               "channel": r["channel"], "message": r["message"], "created_at": r["created_at"],
               "wechat_openid": r["wechat_openid"] or "", "nickname": r["nickname"] or "",
               "phone": r["phone"] or ""} for r in rows]
    conn.close()
    return JSONResponse({"ok": True, "count": len(result), "items": result})


@router.post("/hermes/mark-sent")
async def hermes_mark_sent(request: Request):
    data = await request.json()
    ids = data.get("ids", [])
    if not ids:
        return JSONResponse({"ok": False, "message": "请提供ids"})
    conn = get_recruit_db()
    placeholders = ",".join(["?" for _ in ids])
    conn.execute(f"UPDATE wechat_push_queue SET status='sent', sent_at=datetime('now','localtime') WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True, "updated": len(ids)})


# ====== Webhook ======

@router.post("/webhook/bind-code")
async def webhook_bind_code(request: Request):
    data = await request.json()
    message = data.get("message", "").strip()
    sender_openid = data.get("sender_openid", "")
    if not sender_openid:
        return JSONResponse({"ok": False, "message": "缺少sender_openid"})
    match = re.match(r'^WM\d{6}$', message)
    if match:
        bind_code = message
        conn = get_recruit_db()
        row = conn.execute("SELECT user_id FROM user_push_settings WHERE wechat_bindcode=?", (bind_code,)).fetchone()
        if not row:
            conn.close()
            return JSONResponse({"ok": False, "message": "绑定码无效"})
        conn.execute("UPDATE user_push_settings SET wechat_openid=?, push_wechat_private=1 WHERE wechat_bindcode=?", (sender_openid, bind_code))
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True, "message": "绑定成功", "user_id": row["user_id"]})
    if message in ("武鸣招聘", "绑定", "bd", "BD", "关注"):
        conn = get_recruit_db()
        existing = conn.execute("SELECT user_id FROM user_push_settings WHERE wechat_openid=?", (sender_openid,)).fetchone()
        if existing:
            conn.close()
            return JSONResponse({"ok": True, "message": "已绑定", "user_id": existing["user_id"], "already_bound": True})
        import secrets
        nickname = f"微信用户_{sender_openid[-8:]}_{secrets.token_hex(3)}"
        conn.execute("INSERT INTO users (nickname, phone, password_hash, created_at) VALUES (?, '', 'wechat_anon', datetime('now','localtime'))", (nickname,))
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        existing_s = conn.execute("SELECT user_id FROM user_push_settings WHERE user_id=?", (user_id,)).fetchone()
        if not existing_s:
            conn.execute("INSERT INTO user_push_settings (user_id, push_enabled, push_wechat_private) VALUES (?, 1, 1)", (user_id,))
        conn.execute("UPDATE user_push_settings SET wechat_openid=?, push_wechat_private=1 WHERE user_id=?", (sender_openid, user_id))
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True, "message": "绑定成功", "user_id": user_id})
    return JSONResponse({"ok": False, "message": "未识别的消息"})
