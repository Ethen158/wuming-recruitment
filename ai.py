"""
AI路由 - AI匹配页面、AI问答页面
"""
import urllib.parse
from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse

from services.auth import check_user, get_user_info
from services.ai_engine import ai_match_jobs, format_match_results

router = APIRouter()


@router.get("/ai-match", response_class=HTMLResponse)
async def ai_match_page(request: Request, q: str = ""):
    """AI智能匹配页面"""
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    result_html = ""
    if q:
        scored = ai_match_jobs(q)
        result_html = format_match_results(scored, q, user_info)

    from app import make_page
    content = f"""
    <div class='header'>
        <h1>🤖 AI智能匹配</h1>
        <div class='time'>{now}  |  说需求，AI帮你找工作</div>
    </div>
    <div class="card" style="background:linear-gradient(135deg,var(--card),#2a1a4e);border:1px solid #4a2a7e;">
        <div class="card-title" style="font-size:15px;">💬 告诉我你想找什么样的工作</div>
        <form action="/ai-match" method="get" style="display:flex;flex-direction:column;gap:8px;">
            <textarea name="q" rows="3" placeholder="例如：我想找里建附近的夜班工作，一小时20块以上，有吃住最好"
                      style="width:100%;background:var(--card2);border:1px solid var(--border);border-radius:8px;
                             padding:12px;color:var(--text);font-size:14px;resize:none;">{q}</textarea>
            <button type="submit" style="background:linear-gradient(135deg,#6c5ce7,#a29bfe);border:none;border-radius:8px;
                    padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">
                🤖 AI智能匹配
            </button>
        </form>
        <div style="font-size:11px;color:var(--text2);margin-top:8px;text-align:center;">
            试试说「里建夜班」「武鸣小时工20块」「学生兼职」「食品厂包吃住」
        </div>
    </div>
    {result_html}
    <div style="margin-top:12px;text-align:center;">
        <a href="/" style="color:var(--text2);font-size:12px;">← 返回全部岗位</a>
    </div>"""
    return HTMLResponse(make_page("AI智能匹配 - 武鸣招聘", content, "recruit", user=user_info))


@router.post("/ai-match", response_class=HTMLResponse)
async def ai_match_post(request: Request, q: str = Form("")):
    """AI匹配提交（POST方式）"""
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    if q:
        scored = ai_match_jobs(q)
        result_html = format_match_results(scored, q, user_info)
    else:
        result_html = "<p style='color:var(--text2);text-align:center;padding:20px;'>请输入你的求职需求</p>"

    from app import make_page
    content = f"""
    <div class='header'>
        <h1>🤖 AI智能匹配</h1>
        <div class='time'>说需求，AI帮你找工作</div>
    </div>
    <div class="card" style="background:linear-gradient(135deg,var(--card),#2a1a4e);border:1px solid #4a2a7e;">
        <div class="card-title" style="font-size:15px;">💬 告诉我你想找什么样的工作</div>
        <form action="/ai-match" method="get" style="display:flex;flex-direction:column;gap:8px;">
            <textarea name="q" rows="3" placeholder="例如：我想找里建附近的夜班工作"
                      style="width:100%;background:var(--card2);border:1px solid var(--border);border-radius:8px;
                             padding:12px;color:var(--text);font-size:14px;resize:none;">{q}</textarea>
            <button type="submit" style="background:linear-gradient(135deg,#6c5ce7,#a29bfe);border:none;border-radius:8px;
                    padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">
                🤖 AI智能匹配
            </button>
        </form>
    </div>
    {result_html}
    <div style="margin-top:12px;text-align:center;">
        <a href="/" style="color:var(--text2);font-size:12px;">← 返回全部岗位</a>
    </div>"""
    return HTMLResponse(make_page("AI智能匹配 - 武鸣招聘", content, "recruit", user=user_info))


@router.get("/ai-chat", response_class=HTMLResponse)
async def ai_chat_page(request: Request):
    """AI智能问答页面"""
    from app import make_page
    uid = check_user(request)
    user = get_user_info(uid) if uid else None
    chat_html = """
    <style>
        .chat-wrap { max-width:680px; margin:0 auto; padding:16px; }
        .chat-box { background:#fff; border-radius:16px; box-shadow:0 2px 12px rgba(0,0,0,.08); overflow:hidden; display:flex; flex-direction:column; height:calc(100dvh - 140px); }
        .chat-header { background:linear-gradient(135deg,#6c5ce7,#a29bfe); color:#fff; padding:16px 20px; font-size:17px; font-weight:600; display:flex; align-items:center; gap:10px; }
        .chat-messages { flex:1; overflow-y:auto; padding:16px; display:flex; flex-direction:column; gap:12px; }
        .msg { max-width:82%; padding:12px 16px; border-radius:16px; font-size:14.5px; line-height:1.6; word-break:break-word; animation:fadeIn .25s; }
        @keyframes fadeIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
        .msg-user { align-self:flex-end; background:#6c5ce7; color:#fff; border-bottom-right-radius:4px; }
        .msg-ai { align-self:flex-start; background:#f0f0f5; color:#333; border-bottom-left-radius:4px; }
        .msg-ai a { color:#6c5ce7; font-weight:500; }
        .typing { display:none; align-self:flex-start; padding:12px 16px; background:#f0f0f5; border-radius:16px; }
        .typing span { display:inline-block; width:7px; height:7px; background:#aaa; border-radius:50%; margin:0 2px; animation:bounce .6s infinite alternate; }
        .chat-input { display:flex; gap:8px; padding:12px 16px; border-top:1px solid #eee; background:#fafafa; }
        .chat-input input { flex:1; border:1px solid #ddd; border-radius:24px; padding:10px 16px; font-size:14.5px; outline:none; }
        .chat-input input:focus { border-color:#6c5ce7; }
        .chat-input button { background:#6c5ce7; color:#fff; border:none; border-radius:24px; padding:10px 20px; font-size:14.5px; font-weight:500; cursor:pointer; }
        .quick-btns { display:flex; flex-wrap:wrap; gap:8px; padding:0 16px 12px; }
        .quick-btn { background:#f0f0f5; border:1px solid #e0e0e5; border-radius:20px; padding:6px 14px; font-size:13px; color:#555; cursor:pointer; }
        .quick-btn:hover { background:#6c5ce7; color:#fff; border-color:#6c5ce7; }
    </style>
    <div class="chat-wrap">
        <div class="chat-box">
            <div class="chat-header">🤖 武鸣招聘AI助手</div>
            <div class="chat-messages" id="chatMsgs">
                <div class="msg msg-ai">👋 你好！我是武鸣招聘AI助手</div>
            </div>
            <div class="quick-btns" id="quickBtns">
                <div class="quick-btn" onclick="sendQuick(this)">有什么工作？</div>
                <div class="quick-btn" onclick="sendQuick(this)">附近高薪岗位</div>
                <div class="quick-btn" onclick="sendQuick(this)">比亚迪招人吗</div>
            </div>
            <div class="typing" id="typing"><span></span><span></span><span></span></div>
            <div class="chat-input">
                <input id="chatInput" placeholder="输入你的问题..." onkeydown="if(event.key==='Enter')sendMsg()">
                <button id="sendBtn" onclick="sendMsg()">发送</button>
            </div>
        </div>
    </div>
    <script>
    let history=[];let sessionId=localStorage.getItem('ai_session_id')||'s_'+Date.now()+'_'+Math.random().toString(36).slice(2,8);
    if(!localStorage.getItem('ai_session_id'))localStorage.setItem('ai_session_id',sessionId);
    (function(){
        const msgsEl=document.getElementById('chatMsgs');
        const inputEl=document.getElementById('chatInput');
        const typingEl=document.getElementById('typing');
        const sendBtn=document.getElementById('sendBtn');
        if(!msgsEl||!inputEl||!sendBtn)return;
        function addMsg(t,u){
            const d=document.createElement('div');
            d.className='msg '+(u?'msg-user':'msg-ai');
            d.innerHTML=t.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
            msgsEl.appendChild(d);
            msgsEl.scrollTop=msgsEl.scrollHeight;
        }
        function sendQuick(el){
            inputEl.value=el.textContent;
            sendMsg();
        }
        async function sendMsg(){
            const t=inputEl.value.trim();
            if(!t)return;
            addMsg(t,true);
            inputEl.value='';
            sendBtn.disabled=true;
            typingEl.style.display='flex';
            try{
                const resp=await fetch('/api/ai/chat',{
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({message:t,history:history,session_id:sessionId})
                });
                const data=await resp.json();
                typingEl.style.display='none';
                if(data.reply){
                    addMsg(data.reply,false);
                    history.push({role:'user',content:t});
                    history.push({role:'assistant',content:data.reply});
                }else{
                    addMsg('AI暂时无法回答，请稍后再试',false);
                }
            }catch(e){
                typingEl.style.display='none';
                addMsg('网络错误，请检查连接后重试',false);
                console.error('AI chat error:',e);
            }
            sendBtn.disabled=false;
            inputEl.focus();
        }
        inputEl.focus();
        window.sendMsg=sendMsg;
        window.sendQuick=sendQuick;
    })();
    </script>"""
    return HTMLResponse(make_page("AI智能问答", chat_html, "recruit", user=user))


# ====== AI聊天API ======
import json as _json
import os as _os
import uuid
import httpx
from starlette.responses import StreamingResponse

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"
# 云端DeepSeek模型（从config.yaml动态读取）
import yaml as _yaml
with open(_os.path.expanduser("~/.hermes/config.yaml")) as _f:
    _cfg = _yaml.safe_load(_f)
_ds = _cfg.get("providers", {}).get("deepseek", {})
DEEPSEEK_API_URL = _ds.get("base_url", "https://api.deepseek.com/v1") + "/chat/completions"
DEEPSEEK_API_KEY = _ds.get("api_key", "")
DEEPSEEK_MODEL = _ds.get("model", "deepseek-v4-flash")
del _yaml, _f, _cfg, _ds


def _build_site_context():
    from services.db import get_recruit_db as _db
    conn = _db()
    ctx = []
    total = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='active'").fetchone()[0]
    ctx.append(f"共{total}个岗位")
    cats = conn.execute("SELECT category,COUNT(*) as cnt FROM jobs WHERE status='active' GROUP BY category ORDER BY cnt DESC LIMIT 10").fetchall()
    if cats:
        ctx.append("行业：" + "、".join([f"{c['category']}({c['cnt']})" for c in cats[:8]]))
    locs = conn.execute("SELECT location,COUNT(*) as cnt FROM jobs WHERE status='active' GROUP BY location ORDER BY cnt DESC LIMIT 10").fetchall()
    if locs:
        ctx.append("地区：" + "、".join([f"{l['location']}({l['cnt']})" for l in locs[:5]]))
    conn.close()
    return "\n".join(ctx)


def _search_jobs_for_ai(query, limit=8):
    """根据用户查询搜索匹配的岗位（智能关键词提取）"""
    from services.db import get_recruit_db as _db
    conn = _db()
    q = query.strip()
    if q:
        import re as _re
        # 先用原查询搜索
        like_orig = f"%{q}%"
        rows = conn.execute("""
            SELECT id,title,company,location,salary_min,salary_max,salary_unit
            FROM jobs WHERE status='active'
            AND (title LIKE ? OR company LIKE ? OR description LIKE ? OR category LIKE ? OR location LIKE ?)
            ORDER BY
                CASE
                    WHEN title LIKE ? THEN 0
                    WHEN company LIKE ? THEN 1
                    ELSE 2
                END,
                created_at DESC
            LIMIT ?
        """, (like_orig, like_orig, like_orig, like_orig, like_orig, like_orig, like_orig, limit)).fetchall()
        if rows:
            conn.close()
            return [_job_dict(r) for r in rows]
        # 关键词提取：按长度降序匹配停用词（长词先匹配，避免"有没有"被"工作"截胡）
        stopwords = sorted(["有没有", "推荐", "招聘", "招人", "工作", "岗位", "职位",
                     "什么", "哪些", "哪个", "几个", "怎么", "如何",
                     "请问", "你好", "帮我", "我想", "我要", "找"], key=len, reverse=True)
        keywords = q
        for w in stopwords:
            keywords = keywords.replace(w, " ")
        keywords = _re.sub(r"\s+", " ", keywords).strip()
        search_term = keywords if keywords and len(keywords.replace(" ", "")) >= 2 else q
        like = f"%{search_term}%"
        rows = conn.execute("""
            SELECT id,title,company,location,salary_min,salary_max,salary_unit
            FROM jobs WHERE status='active'
            AND (title LIKE ? OR company LIKE ? OR description LIKE ? OR category LIKE ? OR location LIKE ?)
            ORDER BY
                CASE
                    WHEN title LIKE ? THEN 0
                    WHEN company LIKE ? THEN 1
                    ELSE 2
                END,
                created_at DESC
            LIMIT ?
        """, (like, like, like, like, like, like, like, limit)).fetchall()
        if rows:
            conn.close()
            return [_job_dict(r) for r in rows]
        # 逐个中文词搜索（避免"普工的"这种残留）
        # 提取所有连续中文，滑动取2字组合
        all_chars = _re.findall(r'[\u4e00-\u9fff]', search_term)
        if len(all_chars) >= 2:
            for i in range(len(all_chars) - 1):
                term = all_chars[i] + all_chars[i+1]
                like_ch = f"%{term}%"
                rows = conn.execute("""
                    SELECT id,title,company,location,salary_min,salary_max,salary_unit
                    FROM jobs WHERE status='active'
                    AND (title LIKE ? OR company LIKE ? OR description LIKE ? OR category LIKE ? OR location LIKE ?)
                    ORDER BY
                        CASE
                            WHEN title LIKE ? THEN 0
                            WHEN company LIKE ? THEN 1
                        END,
                        created_at DESC
                    LIMIT ?
                """, (like_ch, like_ch, like_ch, like_ch, like_ch, like_ch, like_ch, limit)).fetchall()
                if rows:
                    conn.close()
                    return [_job_dict(r) for r in rows]
        conn.close()
        return []
    conn.close()
    return []


def _job_dict(r):
    return {"id": r["id"], "title": r["title"], "company": r["company"], "location": r["location"] or "", "salary": f"{r['salary_min']}-{r['salary_max']}{r['salary_unit']}" if r['salary_min'] and r['salary_max'] else (f"{r['salary_min']}{r['salary_unit']}" if r['salary_min'] else "")}


@router.post("/api/ai/chat")
async def api_ai_chat(request: Request):
    try:
        data = await request.json()
    except Exception:
        raw = await request.body()
        data = _json.loads(raw.decode("utf-8", errors="replace"))
    message = data.get("message", "").strip()
    history = data.get("history", [])
    if not message:
        return {"error": "消息不能为空"}
    site_ctx = _build_site_context()
    job_results = _search_jobs_for_ai(message)
    job_ctx = "\n".join([f"- 【{j['title']}】{j['company']}|{j['location']}|{j['salary']}| /job/{j['id']}" for j in job_results]) if job_results else ""
    sys_prompt = f"你是武鸣招聘AI助手，只根据下方岗位数据回答。\n{job_ctx}\n平台：{site_ctx}\n规则：1.只回答岗位数据中的信息 2.如问的岗位不存在则说'暂未收录相关岗位' 3.100字以内 4.用emoji 5.不编造不猜测"
    messages = [{"role": "system", "content": sys_prompt}]
    for h in history[-12:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})
    reply = None
    # 先搜索本数据库匹配的岗位
    job_results = _search_jobs_for_ai(message)
    if job_results:
        # 有匹配岗位：直接构建回答
        lines = [f"- 【{j['title']}】{j['company']} | {j['location']} | {j['salary']}" for j in job_results[:5]]
        reply = f"找到以下{len(job_results)}个相关岗位：\n" + "\n".join(lines)
        if len(job_results) > 5:
            reply += f"\n…还有{len(job_results)-5}个"
        return {"reply": reply, "model": "local"}
    
    # 无匹配：先试DeepSeek云端
    try:
        async with httpx.AsyncClient(timeout=15.0) as cl:
            resp = await cl.post(DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}, json={"model": DEEPSEEK_MODEL, "messages": messages, "max_tokens": 300, "temperature": 0.7})
            data = resp.json()
            choice = data.get("choices", [{}])[0] if "choices" in data else {}
            reply = choice.get("message", {}).get("content", "")
            # 推理模型content可能为空，尝试reasoning_content
            if not reply:
                reply = choice.get("message", {}).get("reasoning_content", "")
    except Exception as e:
        print(f"[AI-DEEPSEEK] {e}", flush=True)
    # DeepSeek不行则展示最近热门岗位
    if not reply:
        from services.db import get_recruit_db as _db2
        _c2 = _db2()
        recent = _c2.execute("SELECT id,title,company,location,salary_min,salary_max,salary_unit FROM jobs WHERE status='active' ORDER BY created_at DESC LIMIT 8").fetchall()
        _c2.close()
        if recent:
            lines = [f"- 【{r['title']}】{r['company']} | {r['location'] or '武鸣'} | {r['salary_min'] or ''}{'-'+str(r['salary_max']) if r['salary_max'] else ''}{r['salary_unit'] or ''}" for r in recent]
            reply = "以下是近期热门岗位：\n" + "\n".join(lines)
    return {"reply": reply or "暂未找到相关岗位，请换个关键词试试。", "model": "ai"}


@router.post("/api/ai/chat/stream")
async def api_ai_chat_stream(request: Request):
    import sqlite3 as _sql
    from config import settings as _cfg
    data = await request.json()
    message = data.get("message", "").strip()
    history = data.get("history", [])
    session_id = data.get("session_id", "") or f"visitor_{uuid.uuid4().hex[:8]}"
    if not message:
        async def _e(): yield f"data: {_json.dumps({'error': 'empty'})}\n\n"
        return StreamingResponse(_e(), media_type="text/event-stream")
    uid = check_user(request)
    db_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), _cfg.DATABASE_PATH)
    _conn = _sql.connect(db_path)
    _cur = _conn.cursor()
    _cur.execute("INSERT INTO ai_chat_history (session_id, user_id, role, content) VALUES (?, ?, 'user', ?)", (session_id, uid, message))
    _conn.commit()
    site_ctx = _build_site_context()
    job_results = _search_jobs_for_ai(message)
    job_ctx = "\n".join([f"- 【{j['title']}】{j['company']}|{j['location']}|{j['salary']}| /job/{j['id']}" for j in job_results]) if job_results else ""
    sys_prompt = f"你是武鸣招聘AI助手。\n{job_ctx}\n平台：{site_ctx}\n回答：直接回答，100字以内，用emoji。"
    messages = [{"role": "system", "content": sys_prompt}]
    for h in history[-12:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    async def _gen():
        full = ""
        saved = False
        try:
            async with httpx.AsyncClient(timeout=90.0) as cl:
                async with cl.stream("POST", f"{OLLAMA_URL}/api/chat", json={"model": OLLAMA_MODEL, "messages": messages, "stream": True, "options": {"temperature": 0.7, "num_predict": 200}}) as resp:
                    async for line in resp.aiter_lines():
                        if line.strip():
                            try:
                                ch = _json.loads(line)
                                tok = ch.get("message", {}).get("content", "")
                                if tok:
                                    full += tok
                                    yield f"data: {_json.dumps({'token': tok})}\n\n"
                                if ch.get("done"):
                                    yield f"data: {_json.dumps({'done': True})}\n\n"
                                    saved = True
                                    break
                            except Exception:
                                pass
        except Exception as e:
            print(f"[AI-STREAM-LOCAL] {e}", flush=True)
        if not saved:
            try:
                async with httpx.AsyncClient(timeout=15.0) as cl:
                    async with cl.stream("POST", DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}, json={"model": DEEPSEEK_MODEL, "messages": messages, "max_tokens": 200, "temperature": 0.7, "stream": True}) as resp:
                        async for line in resp.aiter_lines():
                            raw = line.strip()
                            if raw.startswith("data: "): raw = raw[6:]
                            if raw == "[DONE]": break
                            if raw:
                                try:
                                    ch = _json.loads(raw)
                                    tok = ch.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if tok:
                                        full += tok
                                        yield f"data: {_json.dumps({'token': tok})}\n\n"
                                except Exception:
                                    pass
                yield f"data: {_json.dumps({'done': True})}\n\n"
                saved = True
            except Exception as e:
                print(f"[AI-STREAM-CLOUD] {e}", flush=True)
        if not saved:
            yield f"data: {_json.dumps({'token': 'AI服务暂时不可用', 'done': True})}\n\n"
        try:
            _cur.execute("INSERT INTO ai_chat_history (session_id, user_id, role, content) VALUES (?, ?, 'assistant', ?)", (session_id, uid, full))
            _conn.commit()
        except Exception:
            pass
        finally:
            _conn.close()

    return StreamingResponse(_gen(), media_type="text/event-stream")
