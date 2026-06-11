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


# ====== 固定回复列表（非岗位类常见问题直接回复，不消耗模型） ======
# 匹配规则：如果消息包含任意关键词 → 返回对应回答
AI_FAQ = [
    (["怎么注册", "如何注册", "注册不了", "注册账号", "注册求职者"], "📝 点击首页「登录/注册」，填写手机号、昵称、密码即可完成注册。注册后可查看所有岗位联系方式！"),
    (["怎么联系", "联系你们", "联系方式", "联系招聘", "客服", "人工"], "📞 平台在线，可通过以下方式联系：\n1️⃣ 注册后查看招聘方电话，直接拨打\n2️⃣ 在页面底部「反馈」提交意见\n3️⃣ 直接转发招聘信息给我也可以~"),
    (["看不到", "看不了", "隐藏", "怎么才能看", "登录后", "注册才能"], "🔒 所有岗位联系方式需注册登录后才能查看。注册很简单，填手机号和密码就行！"),
    (["怎么用", "如何使用", "怎么找", "怎么操作", "使用方法", "网站怎么"], "💡 使用方法：\n1️⃣ 首页浏览岗位，可按分类/地区筛选\n2️⃣ 点击岗位卡片查看详情\n3️⃣ 注册后可直接联系招聘方\n4️⃣ 试试AI智能匹配，说需求自动推荐"),
    (["免费吗", "要不要钱", "收费", "多少钱", "价格", "付费"], "✅ 完全免费！求职者浏览岗位、联系招聘方都是免费的，不收任何费用。"),
    (["你好", "在吗", "hello", "hi", "嗨"], "👋 你好！我是武鸣招聘AI助手，请问你想找什么样的工作？可以直接说「普工」「里建附近」「夜班」「包吃住」等关键词~"),
]


def _fuzzy_faq_answer(message: str) -> str or None:
    """模糊匹配FAQ关键字，对求职类FAQ优先于岗位搜索"""
    msg = message.strip().lower()
    # 精确匹配：如果消息只包含注册/登录相关词，肯定不是搜岗位
    pure_faq_words = ["注册", "登录", "免费", "收费", "客服", "怎么用", "使用方法"]
    is_faq_question = any(w in msg for w in pure_faq_words)
    # 如果明显是FAQ类问题，标记为高优先级
    for keywords, answer in AI_FAQ:
        for kw in keywords:
            if kw in msg:
                return answer
    return None


@router.get("/ai-chat", response_class=HTMLResponse)
async def ai_chat_page(request: Request):
    """AI智能问答页面（优化版：暖色主题+建议追问+可点击链接）"""
    from app import make_page
    uid = check_user(request)
    user = get_user_info(uid) if uid else None
    chat_html = """
    <style>
        .chat-wrap { max-width:680px; margin:0 auto; padding:12px; }
        .chat-box { background:var(--card2); border-radius:16px; box-shadow:0 2px 12px rgba(0,0,0,.12); overflow:hidden; display:flex; flex-direction:column; height:calc(100dvh - 120px); border:1px solid rgba(232,93,4,.12); }
        .chat-header { background:linear-gradient(135deg,#E85D04,#F49E4C); color:#fff; padding:14px 18px; font-size:16px; font-weight:600; display:flex; align-items:center; gap:8px; }
        .chat-header .sub { font-size:11px; font-weight:400; opacity:.8; margin-left:auto; }
        .chat-messages { flex:1; overflow-y:auto; padding:14px; display:flex; flex-direction:column; gap:10px; background:var(--bg); }
        .msg { max-width:85%; padding:11px 15px; border-radius:14px; font-size:14px; line-height:1.65; word-break:break-word; animation:fadeIn .25s; }
        @keyframes fadeIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
        .msg-user { align-self:flex-end; background:linear-gradient(135deg,#E85D04,#F49E4C); color:#fff; border-bottom-right-radius:4px; }
        .msg-ai { align-self:flex-start; background:var(--card); color:var(--text); border:1px solid rgba(232,93,4,.08); border-bottom-left-radius:4px; }
        .msg-ai a { color:#E85D04; font-weight:600; text-decoration:none; }
        .msg-ai a:hover { text-decoration:underline; }
        .msg-ai b { color:var(--accent); }
        .typing { display:none; align-self:flex-start; padding:11px 15px; background:var(--card); border-radius:14px; border:1px solid rgba(232,93,4,.08); }
        .typing span { display:inline-block; width:7px; height:7px; background:#E85D04; border-radius:50%; margin:0 2px; animation:bounce .6s infinite alternate; }
        @keyframes bounce { from{opacity:.3;transform:translateY(0)} to{opacity:1;transform:translateY(-5px)} }
        .chat-input { display:flex; gap:8px; padding:10px 14px 12px; border-top:1px solid rgba(232,93,4,.12); background:var(--card2); }
        .chat-input input { flex:1; border:1px solid rgba(232,93,4,.2); border-radius:22px; padding:9px 14px; font-size:14px; outline:none; background:var(--bg); color:var(--text); }
        .chat-input input:focus { border-color:#E85D04; }
        .chat-input button { background:linear-gradient(135deg,#E85D04,#F49E4C); color:#fff; border:none; border-radius:22px; padding:9px 18px; font-size:14px; font-weight:600; cursor:pointer; }
        .chat-input button:disabled { opacity:.5; }
        .suggestions { padding:0 14px 10px; display:flex; flex-wrap:wrap; gap:6px; }
        .suggest-btn { background:rgba(232,93,4,.07); border:1px solid rgba(232,93,4,.15); border-radius:16px; padding:5px 12px; font-size:12px; color:var(--accent2); cursor:pointer; transition:all .15s; }
        .suggest-btn:hover { background:rgba(232,93,4,.15); border-color:#E85D04; }
        .suggest-btn.def { background:rgba(232,93,4,.04); border:1px solid rgba(200,200,200,.2); color:var(--text2); font-size:11px; }
    </style>
    <div class="chat-wrap">
        <div class="chat-box">
            <div class="chat-header">
                <span>🤖</span> 武鸣招聘AI助手
                <span class="sub">420+岗位</span>
            </div>
            <div class="chat-messages" id="chatMsgs">
                <div class="msg msg-ai">👋 你好！我是武鸣招聘AI助手。<br>想问什么工作，直接跟我说！<br>比如「普工」「夜班」「里建附近」</div>
            </div>
            <div class="suggestions" id="suggestArea"></div>
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
        const suggestArea=document.getElementById('suggestArea');
        if(!msgsEl||!inputEl||!sendBtn)return;

        function addMsg(t,u){
            const d=document.createElement('div');
            d.className='msg '+(u?'msg-user':'msg-ai');
            d.innerHTML=t.replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>');
            msgsEl.appendChild(d);
            msgsEl.scrollTop=msgsEl.scrollHeight;
            return d;
        }

        function showSuggestions(suggs){
            suggestArea.innerHTML='';
            suggs.forEach(function(s){
                const btn=document.createElement('span');
                btn.className='suggest-btn';
                btn.textContent=s;
                btn.onclick=function(){inputEl.value=s;sendMsg();};
                suggestArea.appendChild(btn);
            });
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
                    if(data.suggestions&&data.suggestions.length){
                        showSuggestions(data.suggestions);
                    }else{
                        showSuggestions(['普工','夜班','里建附近','包吃住','小时工']);
                    }
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
        showSuggestions(['普工','夜班','里建附近','包吃住','小时工']);
    })();
    </script>"""
    return HTMLResponse(make_page("AI智能问答", chat_html, "recruit", user=user))


# ====== AI聊天API ======
import json as _json
import os as _os
import re as _re
import httpx

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
    """构建平台概览信息（岗位数、行业、地区等）"""
    from services.db import get_recruit_db as _db
    conn = _db()
    ctx = []
    total = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='active'").fetchone()[0]
    ctx.append(f"共{total}个岗位")
    cats = conn.execute(
        "SELECT category,COUNT(*) as cnt FROM jobs WHERE status='active' GROUP BY category ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    if cats:
        ctx.append("行业：" + "、".join([f"{c['category']}({c['cnt']})" for c in cats[:8]]))
    locs = conn.execute(
        "SELECT location,COUNT(*) as cnt FROM jobs WHERE status='active' GROUP BY location ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    if locs:
        ctx.append("地区：" + "、".join([f"{l['location']}({l['cnt']})" for l in locs[:5]]))
    conn.close()
    return "\n".join(ctx)


# 停用词表（按长度降序排列，长词优先匹配）
_STOPWORDS = sorted([
    "有没有", "推荐", "招聘", "招人", "工作", "岗位", "职位",
    "什么", "哪些", "哪个", "几个", "怎么", "如何",
    "请问", "你好", "帮我", "我想", "我要", "找",
    "吗", "的", "啦", "啊", "呢", "吧", "呀", "了", "是"
], key=len, reverse=True)


def _extract_search_keywords(q: str) -> str:
    """从用户提问中提取核心搜索关键词（去停用词）"""
    keywords = q
    for w in _STOPWORDS:
        keywords = keywords.replace(w, " ")
    keywords = _re.sub(r"\s+", " ", keywords).strip()
    # 如果去停用词后没有有效内容，用原查询
    if not keywords or len(keywords.replace(" ", "")) < 2:
        return q
    return keywords


def _search_jobs_for_ai(query, limit=6):
    """根据用户查询搜索匹配的岗位（三层搜索：原句→关键词→逐字组合）"""
    from services.db import get_recruit_db as _db
    conn = _db()
    q = query.strip()
    if not q:
        conn.close()
        return []

    def _do_search(like_term):
        like = f"%{like_term}%"
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
        return rows

    # 第1层：原查询直接搜索
    rows = _do_search(q)
    if rows:
        conn.close()
        return [_job_dict(r) for r in rows]

    # 第2层：关键词搜索
    keywords = _extract_search_keywords(q)
    if keywords != q:
        rows = _do_search(keywords)
        if rows:
            conn.close()
            return [_job_dict(r) for r in rows]

    # 第3层：逐字组合（提取连续中文，滑动取2字组合）
    all_chars = _re.findall(r'[\u4e00-\u9fff]', keywords)
    if len(all_chars) >= 2:
        for i in range(len(all_chars) - 1):
            term = all_chars[i] + all_chars[i + 1]
            rows = _do_search(term)
            if rows:
                conn.close()
                return [_job_dict(r) for r in rows]

    conn.close()
    return []


def _job_dict(r):
    return {
        "id": r["id"],
        "title": r["title"],
        "company": r["company"],
        "location": r["location"] or "武鸣",
        "salary": f"{r['salary_min']}-{r['salary_max']}{r['salary_unit']}"
        if r['salary_min'] and r['salary_max']
        else (f"{r['salary_min']}{r['salary_unit']}" if r['salary_min'] else "薪资面议"),
    }


def _format_jobs_as_link(jobs, max_show=5):
    """将岗位列表格式化为可点击小卡片（点击整块直达详情页）"""
    cards = []
    for j in jobs[:max_show]:
        salary_text = j.get("salary", "薪资面议")
        title = j["title"]
        company = j["company"]
        location = j["location"]
        jid = j["id"]
        cards.append(
            f'<a href="/job/{jid}" target="_blank" style="display:block;background:rgba(232,93,4,.05);'
            f'border:1px solid rgba(232,93,4,.12);border-radius:10px;padding:8px 10px;'
            f'margin-bottom:6px;text-decoration:none;color:var(--text);transition:all .12s;">'
            f'<div style="font-size:14px;font-weight:600;color:#E85D04;">{title}</div>'
            f'<div style="font-size:12px;color:#666;margin-top:2px;">{company}</div>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">'
            f'<span style="font-size:11px;color:#999;">📍{location}</span>'
            f'<span style="font-size:13px;font-weight:700;color:#2B9348;">{salary_text}</span>'
            f'</div></a>'
        )
    text = "\n".join(cards)
    if len(jobs) > max_show:
        text += f'<div style="font-size:12px;color:#999;text-align:center;margin-top:2px;">… 还有 {len(jobs) - max_show} 个相关岗位</div>'
    return text


# 为常见岗位类别提供建议追问
_CATEGORY_SUGGESTIONS = {
    "食品": ["食品厂普工", "包吃住", "长白班", "里建食品厂"],
    "物流": ["物流", "叉车司机", "快递分拣", "物流招聘"],
    "普工": ["普工长白班", "包吃住普工", "两班倒", "里建普工"],
    "夜班": ["夜班普工", "夜班小时工", "夜班保安"],
    "小时工": ["小时工20块", "小时工里建", "学生兼职"],
}


def _get_suggestions(message, jobs=None):
    """根据用户消息和搜索结果推荐追问"""
    if jobs and len(jobs) > 0:
        # 按匹配到的岗位类别推荐
        cats = set()
        for j in jobs:
            t = j.get("title", "")
            c = j.get("company", "")
            for kw, suggs in _CATEGORY_SUGGESTIONS.items():
                if kw in t or kw in c:
                    cats.update(suggs[:2])
        if cats:
            return list(cats)[:3]
    # 默认热门追问
    return ["普工有哪些", "夜班工作", "里建附近", "包吃住", "食品厂"]


@router.post("/api/ai/chat")
async def api_ai_chat(request: Request):
    """AI聊天API — 第1层直接搜库 → 第2层DeepSeek → 第3层热门兜底"""
    try:
        data = await request.json()
    except Exception:
        raw = await request.body()
        data = _json.loads(raw.decode("utf-8", errors="replace"))
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return {"reply": "请输入你想找的工作", "suggestions": _get_suggestions(""), "model": "local"}

    # 第一阶段：FAQ关键字匹配（零延迟，不消耗任何API）
    faq_answer = _fuzzy_faq_answer(message)
    if faq_answer:
        suggs = _get_suggestions(message, None)
        return {"reply": faq_answer, "suggestions": suggs, "model": "faq"}

    # 第二阶段：直接搜索数据库
    job_results = _search_jobs_for_ai(message)
    if job_results:
        reply = f"🔍 找到 {len(job_results)} 个相关岗位：\n\n{_format_jobs_as_link(job_results)}"
        suggs = _get_suggestions(message, job_results)
        return {"reply": reply, "suggestions": suggs, "model": "local"}

    # 第三阶段：DeepSeek 云端智能回答
    site_ctx = _build_site_context()
    reply = None
    try:
        broad_prompt = (
            f"你是武鸣招聘AI助手，帮助求职者找工作。平台信息：{site_ctx}\n"
            f"用户问题：{message}\n"
            f"数据库未匹配到该用户的精确岗位，请：\n"
            f"1. 如果是求职类问题（行业、薪资、找工作建议），提供友好建议\n"
            f"2. 如果是非求职类问题（问候、闲聊），简短回应引导到招聘话题\n"
            f"3. 如果确实是岗位关键词，告诉用户换个说法试试\n"
            f"回复50字以内，用emoji，自然亲切。"
        )
        msgs = [
            {"role": "system", "content": broad_prompt},
            {"role": "user", "content": message},
        ]
        async with httpx.AsyncClient(timeout=12.0) as cl:
            resp = await cl.post(
                DEEPSEEK_API_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                json={"model": DEEPSEEK_MODEL, "messages": msgs, "max_tokens": 250, "temperature": 0.7}
            )
            data = resp.json()
            choice = data.get("choices", [{}])[0] if "choices" in data else {}
            reply = choice.get("message", {}).get("content", "")
            if not reply:
                reply = choice.get("message", {}).get("reasoning_content", "")
    except Exception as e:
        print(f"[AI-DEEPSEEK] {e}", flush=True)

    # DeepSeek不可用时展示热门岗位
    if not reply:
        from services.db import get_recruit_db as _db2
        _c2 = _db2()
        recent = _c2.execute(
            "SELECT id,title,company,location,salary_min,salary_max,salary_unit "
            "FROM jobs WHERE status='active' ORDER BY created_at DESC LIMIT 6"
        ).fetchall()
        _c2.close()
        if recent:
            recent_jobs = [_job_dict(r) for r in recent]
            reply = f"💡 没找到完全匹配的岗位，看看最近的热门岗位：\n\n{_format_jobs_as_link(recent_jobs)}"
        else:
            reply = "💡 暂未找到相关岗位，换个关键词试试？比如「普工」「包装」「食品厂」"

    suggs = _get_suggestions(message, None)
    return {"reply": reply, "suggestions": suggs, "model": "ai"}
