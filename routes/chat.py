"""
聊天路由 - 访客、发起对话、收件箱、聊天页面、WebSocket
"""
import hashlib
import random
import asyncio
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services.db import get_recruit_db
from services.auth import check_user, check_enterprise

router = APIRouter()

# WebSocket连接存储
ws_connections = {}


def _chat_session_key(user_type, user_id):
    return f"{user_type}::{user_id}"


# ====== AI自动回复 ---
async def _ai_auto_reply(message_text, conv_id=None):
    """使用AI Agent模型进行智能回复，替代原有的关键词匹配"""
    from services.ai_agent import ai_agent_reply
    
    # 直接调用异步函数
    result = await ai_agent_reply(message_text)
    return result if result else None


@router.get("/chat/guest", response_class=HTMLResponse)
async def chat_guest_entry(request: Request, job_id: int = 0):
    """游客直接进入聊天"""
    if not job_id:
        return HTMLResponse("<h3>参数错误</h3>")
    conn = get_recruit_db()
    job = conn.execute("SELECT id, company, title FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not job:
        return HTMLResponse("<h3>岗位不存在</h3>")
    random_nick = "visitor_" + str(random.randint(100000, 999999))
    resp = RedirectResponse(f"/chat/start?job_id={job_id}&guest=1", status_code=302)
    resp.set_cookie("guest_nick", random_nick, max_age=2592000, path="/")
    return resp


@router.get("/chat/start")
async def chat_start(request: Request, job_id: int = 0, guest: int = 0):
    conn = get_recruit_db()
    job = conn.execute("SELECT id, company, title FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        return HTMLResponse("<h3>岗位不存在</h3>")
    ent = conn.execute("SELECT id FROM enterprises WHERE company_name=?", (job["company"],)).fetchone()
    if not ent:
        now = datetime.now().isoformat()
        placeholder_hash = hashlib.md5(b"placeholder").hexdigest()
        conn.execute(
            "INSERT INTO enterprises (company_name, contact_name, contact_phone, password_hash, created_at) VALUES (?,?,?,?,?)",
            (job["company"], "企业管理员", "00000000000", placeholder_hash, now)
        )
        conn.commit()
        ent_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        ent = {"id": ent_id}

    user = check_user(request)
    if guest or not user:
        guest_nick = request.cookies.get("guest_nick", "").strip()
        if not guest_nick:
            return RedirectResponse(f"/chat/guest?job_id={job_id}", status_code=302)
        guest_id = int(hashlib.md5(guest_nick.encode()).hexdigest()[:8], 16) % 1000000 + 9000000
        conv = conn.execute(
            "SELECT id FROM conversations WHERE user_id=? AND enterprise_id=? AND job_id=?",
            (guest_id, ent["id"], job_id)
        ).fetchone()
        if not conv:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO conversations (user_id, enterprise_id, job_id, guest_name, last_message, last_message_at, created_at) VALUES (?,?,?,?,?,?,?)",
                (guest_id, ent["id"], job_id, guest_nick, "", now, now)
            )
            conn.commit()
            conv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            conv_id = conv["id"]
        conn.close()
        return RedirectResponse(f"/chat/{conv_id}?guest=1", status_code=302)

    if not job_id:
        return HTMLResponse("<h3>参数错误</h3>")
    conv = conn.execute(
        "SELECT id FROM conversations WHERE user_id=? AND enterprise_id=? AND job_id=?",
        (user, ent["id"], job_id)
    ).fetchone()
    now = datetime.now().isoformat()
    if not conv:
        conn.execute(
            "INSERT INTO conversations (user_id, enterprise_id, job_id, last_message, last_message_at, created_at) VALUES (?,?,?,?,?,?)",
            (user, ent["id"], job_id, "", now, now)
        )
        conn.commit()
        conv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        conv_id = conv["id"]
    conn.close()
    return RedirectResponse(f"/chat/{conv_id}", status_code=302)


@router.get("/chat/inbox", response_class=HTMLResponse)
async def chat_inbox(request: Request):
    user = check_user(request)
    ent = check_enterprise(request)
    guest_nick = request.cookies.get("guest_nick", "")
    conn = get_recruit_db()
    conv_list = ""
    my_type = "guest"
    if user:
        convs = conn.execute(
            "SELECT c.*, j.title as job_title, e.company_name as other_name FROM conversations c "
            "JOIN jobs j ON c.job_id=j.id JOIN enterprises e ON c.enterprise_id=e.id "
            "WHERE c.user_id=? ORDER BY c.last_message_at DESC", (user["id"],)
        ).fetchall()
        my_type = "user"
    elif ent:
        convs = conn.execute(
            "SELECT c.*, j.title as job_title, COALESCE(c.guest_name, u.nickname, '游客') as other_name "
            "FROM conversations c JOIN jobs j ON c.job_id=j.id LEFT JOIN users u ON c.user_id=u.id "
            "WHERE c.enterprise_id=? ORDER BY c.last_message_at DESC", (ent["id"],)
        ).fetchall()
        my_type = "enterprise"
    else:
        convs = []
    conn.close()

    for c in convs:
        unread = c["enterprise_unread"] if my_type in ("user", "guest") else c["user_unread"]
        badge = f'<span class="unread-badge">{unread}</span>' if unread > 0 else ""
        last = (c["last_message"] or "暂无消息")[:30]
        t = c["last_message_at"][5:16].replace("T", " ") if c["last_message_at"] else ""
        link = f'/chat/{c["id"]}{"?guest=1" if my_type == "guest" else ""}'
        conv_list += f'<a href="{link}" class="conv-item">'
        conv_list += f'<div class="conv-avatar">👤</div>'
        conv_list += f'<div class="conv-info"><div class="conv-name">{c["other_name"]} {badge}</div>'
        conv_list += f'<div class="conv-job">{c["job_title"]}</div>'
        conv_list += f'<div class="conv-last">{last}</div></div>'
        conv_list += f'<div class="conv-time">{t}</div></a>'

    if not conv_list:
        conv_list = '<div style="text-align:center;padding:40px;color:#666;">暂无对话</div>'

    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>消息中心</title><style>
* {{ margin:0;padding:0;box-sizing:border-box; }}
body {{ background:#0f0f1a;color:#e8e8f0;font-family:-apple-system,sans-serif; }}
.header {{ background:#1a1a2e;padding:16px;border-bottom:1px solid #2d2d4a;display:flex;align-items:center;gap:12px; }}
.header a {{ color:#a29bfe;text-decoration:none;font-size:14px; }}
.header h2 {{ font-size:18px;flex:1; }}
.list {{ padding:16px;display:flex;flex-direction:column;gap:10px;max-width:600px;margin:0 auto; }}
.conv-item {{ display:flex;align-items:center;gap:12px;padding:14px 16px;background:#1a1a2e;border:1px solid #2d2d4a;border-radius:12px;text-decoration:none;color:#e8e8f0; }}
.conv-avatar {{ width:42px;height:42px;border-radius:50%;background:#2d2d4a;display:flex;align-items:center;justify-content:center;font-size:18px; }}
.conv-info {{ flex:1; }}
.conv-name {{ font-weight:600;font-size:14px; }}
.conv-job {{ font-size:12px;color:#888;margin-top:2px; }}
.conv-last {{ font-size:12px;color:#666;margin-top:2px; }}
.conv-time {{ font-size:11px;color:#555; }}
.unread-badge {{ background:#6c5ce7;color:white;border-radius:10px;padding:2px 8px;font-size:11px;margin-left:6px; }}
</style></head><body>
<div class="header"><a href="/">← 首页</a><h2>💬 消息中心</h2></div>
<div class="list">{conv_list}</div>
</body></html>""")


@router.get("/chat/{conv_id}", response_class=HTMLResponse)
async def chat_page(request: Request, conv_id: int):
    user = check_user(request)
    ent = check_enterprise(request)
    is_guest = request.query_params.get("guest") == "1" or bool(request.cookies.get("guest_nick"))
    conn = get_recruit_db()
    conv = conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
    if not conv:
        return HTMLResponse("<h3>对话不存在</h3>")
    if user and conv["user_id"] != user["id"]:
        return HTMLResponse("<h3>无权访问</h3>")
    if ent and conv["enterprise_id"] != ent["id"]:
        return HTMLResponse("<h3>无权访问</h3>")
    msgs = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (conv_id,)).fetchall()
    guest_name = conv["guest_name"] or ""
    other_name = ""
    if user:
        ent_info = conn.execute("SELECT company_name FROM enterprises WHERE id=?", (conv["enterprise_id"],)).fetchone()
        other_name = ent_info["company_name"] if ent_info else "企业"
    elif ent:
        other_name = guest_name or (conn.execute("SELECT nickname FROM users WHERE id=?", (conv["user_id"],)).fetchone() or {}).get("nickname", "求职者")
    else:
        other_name = guest_name or "对方"
    job = conn.execute("SELECT title, company FROM jobs WHERE id=?", (conv["job_id"],)).fetchone()
    if user:
        my_type, my_id = "user", user["id"]
    elif ent:
        my_type, my_id = "enterprise", ent["id"]
    else:
        my_type, my_id = "guest", conv["user_id"]
    conn.close()

    msg_html = ""
    for m in msgs:
        if m["sender_type"] == "system":
            msg_html += f'<div class="msg ai-msg">{m["content"].replace(chr(10),"<br>")}<div class="time">{m["created_at"][11:16]}</div></div>'
        elif m["sender_type"] == my_type:
            msg_html += f'<div class="msg mine">{m["content"]}<div class="time">{m["created_at"][11:16]}</div></div>'
        else:
            msg_html += f'<div class="msg theirs">{m["content"]}<div class="time">{m["created_at"][11:16]}</div></div>'

    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>和{other_name}聊天</title>
<style>
* {{ margin:0;padding:0;box-sizing:border-box; }}
body {{ background:#0f0f1a;color:#e8e8f0;font-family:-apple-system,sans-serif;min-height:100vh;display:flex;flex-direction:column; }}
.header {{ background:#1a1a2e;padding:12px 16px;border-bottom:1px solid #2d2d4a;display:flex;align-items:center;gap:10px; }}
.header a {{ color:#a29bfe;text-decoration:none;font-size:14px; }}
.header .title {{ flex:1; }}
.header .title h3 {{ font-size:15px;color:white; }}
.header .title span {{ font-size:12px;color:#8888aa; }}
.msgs {{ flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:8px; }}
.msg {{ max-width:75%;padding:10px 14px;border-radius:16px;font-size:14px;line-height:1.5;word-break:break-word; }}
.msg.mine {{ background:#6c5ce7;color:white;align-self:flex-end;border-bottom-right-radius:4px; }}
.msg.theirs {{ background:#1a1a2e;border:1px solid #2d2d4a;align-self:flex-start;border-bottom-left-radius:4px; }}
.msg.ai-msg {{ background:linear-gradient(135deg,#1a3a2e,#1a2e3a);border:1px solid #2d4a3a;align-self:flex-start;max-width:85%; }}
.msg .time {{ font-size:10px;color:rgba(255,255,255,0.5);margin-top:4px;text-align:right; }}
.msg.theirs .time,.msg.ai-msg .time {{ color:#666; }}
.input-bar {{ background:#1a1a2e;padding:12px 16px;border-top:1px solid #2d2d4a;display:flex;gap:8px;position:sticky;bottom:0;flex-shrink:0; }}
.input-bar input {{ flex:1;background:#222240;border:1px solid #2d2d4a;border-radius:20px;padding:10px 16px;color:white;font-size:14px;outline:none; }}
.input-bar input:focus {{ border-color:#6c5ce7; }}
.input-bar button {{ background:#6c5ce7;border:none;border-radius:20px;padding:10px 20px;color:white;font-weight:600;cursor:pointer;font-size:14px; }}
</style></head><body>
<div class="header">
    <a href="/chat/inbox">←</a>
    <div class="title"><h3>{other_name}</h3><span>{job["title"] if job else ""} · {job["company"] if job else ""}</span></div>
</div>
<div class="msgs" id="msgs">{msg_html}</div>
<div class="input-bar">
    <input id="inp" placeholder="输入消息..." onkeydown="if(event.key==='Enter')send()">
    <button id="sendBtn" onclick="send()">发送</button>
</div>
<script>
var convId={conv_id};var myType="{my_type}";var myId={my_id};var lastMsgId=0;
(function(){{var msgs=document.querySelectorAll('.msg');msgs.forEach(function(m){{var id=parseInt(m.getAttribute('data-id')||'0');if(id>lastMsgId)lastMsgId=id;}});}})();
function send(){{
    var inp=document.getElementById('inp');var txt=inp.value.trim();if(!txt)return;
    var div=document.createElement('div');div.className='msg mine';
    div.innerHTML=txt+'<div class="time">刚刚</div>';
    document.getElementById('msgs').appendChild(div);inp.value='';scrollBottom();
    fetch('/api/chat/send',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{conversation_id:convId,content:txt,sender_type:myType,sender_id:myId}})}})
    .then(function(r){{return r.json();}}).then(function(d){{if(d.time){{var t=div.querySelector('.time');if(t)t.textContent=d.time.substring(11,16);}}}});
    fetch('/api/chat/'+convId+'/read',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{reader_type:myType}})}});
}}
function pollMessages(){{
    fetch('/api/chat/'+convId+'/poll?after='+lastMsgId).then(function(r){{return r.json();}}).then(function(msgs){{
        msgs.forEach(function(m){{if(m.id>lastMsgId){{lastMsgId=m.id;if(m.sender===myType)return;
        var div=document.createElement('div');div.className=m.sender==='system'?'msg ai-msg':'msg theirs';
        div.setAttribute('data-id',m.id);div.innerHTML=m.content+'<div class="time">'+m.time.substring(11,16)+'</div>';
        document.getElementById('msgs').appendChild(div);scrollBottom();}}}});
    }});
}}
setInterval(pollMessages,3000);
document.getElementById('inp').addEventListener('keydown',function(e){{if(e.key==='Enter'){{e.preventDefault();send();}}}});
function scrollBottom(){{var m=document.getElementById('msgs');m.scrollTop=m.scrollHeight;}}
scrollBottom();
</script></body></html>""")


# ====== 聊天API（Chat API endpoints under /api prefix）======

from fastapi.responses import JSONResponse


@router.post("/api/chat/send")
async def api_chat_send(request: Request):
    data = await request.json()
    conv_id = data.get("conversation_id", 0)
    content = data.get("content", "").strip()
    sender_type = data.get("sender_type", "guest")
    sender_id = data.get("sender_id", 0)
    if not conv_id or not content:
        return {"error": "参数错误"}
    conn = get_recruit_db()
    now = datetime.now().isoformat()
    conn.execute("INSERT INTO messages (conversation_id, sender_type, sender_id, content, created_at) VALUES (?,?,?,?,?)",
                 (conv_id, sender_type, sender_id, content, now))
    if sender_type in ("user", "guest"):
        conn.execute("UPDATE conversations SET last_message=?, last_message_at=?, enterprise_unread=enterprise_unread+1 WHERE id=?",
                     (content[:50], now, conv_id))
    else:
        conn.execute("UPDATE conversations SET last_message=?, last_message_at=?, user_unread=user_unread+1 WHERE id=?",
                     (content[:50], now, conv_id))
    conn.commit()
    ai_reply = None
    if sender_type in ("user", "guest"):
        ai_result = await _ai_auto_reply(content, conv_id)
        if ai_result and isinstance(ai_result, dict) and ai_result.get("reply"):
            ai_reply = ai_result["reply"]
        elif ai_result:
            ai_reply = ai_result
        if ai_reply:
            await asyncio.sleep(0.3)
            conn2 = get_recruit_db()
            reply_now = datetime.now().isoformat()
            conn2.execute("INSERT INTO messages (conversation_id, sender_type, sender_id, content, created_at) VALUES (?,?,?,?,?)",
                          (conv_id, "system", 0, ai_reply, reply_now))
            conn2.execute("UPDATE conversations SET last_message=?, last_message_at=? WHERE id=?",
                          (ai_reply[:50], reply_now, conv_id))
            conn2.commit()
            conn2.close()
    conn.close()
    return {"ok": True, "time": now, "conversation_id": conv_id, "ai_reply": bool(ai_reply)}


@router.get("/api/chat/{conv_id}/poll")
async def api_chat_poll(request: Request, conv_id: int, after: int = 0):
    conn = get_recruit_db()
    if after:
        msgs = conn.execute("SELECT * FROM messages WHERE conversation_id=? AND id>? ORDER BY created_at", (conv_id, after)).fetchall()
    else:
        msgs = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (conv_id,)).fetchall()
    conn.close()
    return [{"id": m["id"], "sender": m["sender_type"], "content": m["content"], "time": m["created_at"]} for m in msgs]


@router.post("/api/chat/{conv_id}/read")
async def api_chat_read(request: Request, conv_id: int):
    data = await request.json()
    reader_type = data.get("reader_type", "guest")
    conn = get_recruit_db()
    if reader_type in ("user", "guest"):
        conn.execute("UPDATE conversations SET user_unread=0 WHERE id=?", (conv_id,))
    else:
        conn.execute("UPDATE conversations SET enterprise_unread=0 WHERE id=?", (conv_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/chat/conversations")
async def api_chat_conversations(request: Request):
    user = check_user(request)
    ent = check_enterprise(request)
    if not user and not ent:
        return {"error": "请先登录"}
    conn = get_recruit_db()
    if user:
        convs = conn.execute(
            "SELECT c.id, c.last_message, c.last_message_at, c.user_unread, c.enterprise_unread, "
            "j.title as job_title, e.company_name as other_name "
            "FROM conversations c JOIN jobs j ON c.job_id=j.id JOIN enterprises e ON c.enterprise_id=e.id "
            "WHERE c.user_id=? ORDER BY c.last_message_at DESC", (user,)).fetchall()
        uk = "enterprise_unread"
    else:
        convs = conn.execute(
            "SELECT c.id, c.last_message, c.last_message_at, c.user_unread, c.enterprise_unread, "
            "j.title as job_title, COALESCE(c.guest_name, u.nickname, '游客') as other_name "
            "FROM conversations c JOIN jobs j ON c.job_id=j.id LEFT JOIN users u ON c.user_id=u.id "
            "WHERE c.enterprise_id=? ORDER BY c.last_message_at DESC", (ent["id"],)).fetchall()
        uk = "user_unread"
    conn.close()
    return [{"id": c["id"], "other": c["other_name"], "job": c["job_title"],
             "last": c["last_message"] or "", "time": c["last_message_at"] or "",
             "unread": c[uk]} for c in convs]


@router.get("/api/chat/{conv_id}/messages")
async def api_chat_messages(request: Request, conv_id: int):
    user = check_user(request)
    ent = check_enterprise(request)
    if not user and not ent:
        return {"error": "请先登录"}
    conn = get_recruit_db()
    conv = conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
    if not conv:
        return {"error": "对话不存在"}
    if user and conv["user_id"] != user:
        return {"error": "无权访问"}
    if ent and conv["enterprise_id"] != ent["id"]:
        return {"error": "无权访问"}
    msgs = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (conv_id,)).fetchall()
    conn.close()
    return [{"id": m["id"], "sender": m["sender_type"], "content": m["content"], "time": m["created_at"]} for m in msgs]


@router.get("/api/chat/unread")
async def api_chat_unread(request: Request):
    user = check_user(request)
    ent = check_enterprise(request)
    conn = get_recruit_db()
    if user:
        row = conn.execute("SELECT COALESCE(SUM(enterprise_unread),0) as n FROM conversations WHERE user_id=?", (user,)).fetchone()
        conn.close()
        return {"unread": row["n"]}
    if ent:
        row = conn.execute("SELECT COALESCE(SUM(user_unread),0) as n FROM conversations WHERE enterprise_id=?", (ent["id"],)).fetchone()
        conn.close()
        return {"unread": row["n"]}
    conn.close()
    return {"unread": 0}


