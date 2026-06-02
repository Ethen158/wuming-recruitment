#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes Web Panel - 武鸣招聘平台
首页公开显示招聘信息，管理后台需登录
"""
import os, subprocess, re, json, urllib.request, urllib.parse, sqlite3, hashlib, secrets, math
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

RECRUIT_DB = "/home/ubuntu/.hermes/wuming_recruitment.db"
SESSION_FILE = "/home/ubuntu/.hermes/.web_session_key"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# ====== 登录配置 ======
# 密码修改方式：export RECRUIT_PASSWORD='你的密码'
ADMIN_PASSWORD = os.environ.get("RECRUIT_PASSWORD", "wuming2026")
# 会话有效期（小时）
SESSION_HOURS = 72

def get_recruit_db():
    conn = sqlite3.connect(RECRUIT_DB)
    conn.row_factory = sqlite3.Row
    return conn

app = FastAPI(title="武鸣招聘平台")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

CSS = open(os.path.join(STATIC_DIR, "style.css"), encoding="utf-8").read()

JS = """
function copyText(text, btn) {
    // 优先用 Clipboard API（微信浏览器支持）
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            showTip(btn, '✅ 已复制到剪贴板', '#00b894');
        }).catch(function() {
            fallbackCopy(text, btn);
        });
    } else {
        fallbackCopy(text, btn);
    }
}
function fallbackCopy(text, btn) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta);
    if (ok) {
        showTip(btn, '✅ 已复制到剪贴板', '#00b894');
    } else {
        showTip(btn, '⚠️ 请长按选择复制', '#e17055');
    }
}
function showTip(btn, msg, color) {
    var tip = document.createElement('div');
    tip.textContent = msg;
    tip.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:'+color+';color:white;padding:10px 20px;border-radius:8px;font-size:14px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3);transition:opacity 0.3s;max-width:90%;text-align:center;';
    document.body.appendChild(tip);
    setTimeout(function() {
        tip.style.opacity = '0';
        setTimeout(function() { tip.remove(); }, 300);
    }, 1500);
}
function copyJob(e, id, title, company, salary, phone) {
    e.stopPropagation();
    e.preventDefault();
    var text = '【' + title + '】' + company + ' | ' + salary;
    if (phone) text += ' | 📞 ' + phone;
    text += ' 🏭武鸣招聘 http://192.144.129.59/';
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        var btn = e.target;
        var old = btn.innerHTML;
        btn.innerHTML = '✅ 已复制';
        setTimeout(function() { btn.innerHTML = old; }, 2000);
    } catch (err) {
        // 复制失败，提示用户手动复制
        prompt('复制失败，请手动复制👇', text);
    }
    document.body.removeChild(ta);
}
function shareJob(e, title, company, salary, location) {
    e.stopPropagation();
    e.preventDefault();
    var text = '【' + title + '】' + company + ' | ' + salary + ' | ' + location;
    text += ' 🏭武鸣招聘 http://192.144.129.59/';
    if (navigator.share) {
        navigator.share({ title: title + ' - ' + company, text: text });
    } else {
        // 不支持Web Share API则复制
        copyJob(e, '', title, company, salary, '');
        if (e.target.innerHTML.indexOf('已复制') < 0) {
            e.target.innerHTML = '📤 已复制，去微信粘贴';
            setTimeout(function() { e.target.innerHTML = '📤 分享'; }, 2000);
        }
    }
}
"""

# ====== 认证工具 ======
# 管理员认证
def _load_session_key():
    """读取持久化的会话密钥"""
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE) as f:
                return f.read().strip()
    except: pass
    return None

def _save_session_key(key):
    """保存会话密钥"""
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        f.write(key)

def _make_token(password, salt=None):
    """生成认证 token"""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{password}:::{salt}".encode()).hexdigest()
    return f"{salt}::{h}"

def _verify_token(token, password):
    """验证 token"""
    try:
        salt, h = token.split("::", 1)
        expected = hashlib.sha256(f"{password}:::{salt}".encode()).hexdigest()
        return h == expected
    except: return False

def check_auth(request: Request):
    """检查管理员是否已登录"""
    token = request.cookies.get("session")
    if not token:
        return False
    return _verify_token(token, ADMIN_PASSWORD)

# 求职者认证
USER_SESSION_FILE = "/home/ubuntu/.hermes/.user_session_key"

def check_user(request: Request):
    """检查求职者是否登录，返回用户信息或None"""
    token = request.cookies.get("user_session")
    if not token:
        return None
    try:
        conn = get_recruit_db()
        uid = conn.execute("SELECT user_id FROM user_tokens WHERE token=? AND expire_at>datetime('now')", (token,)).fetchone()
        conn.close()
        if uid:
            return uid["user_id"]
    except:
        pass
    return None

def get_user_info(user_id):
    """获取用户信息"""
    if not user_id:
        return None
    conn = get_recruit_db()
    u = conn.execute("SELECT id, nickname, phone, wechat FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return u

# ====== HTML 构建 ======
# CSS 版本号 - 每次修改CSS后递增以破除浏览器缓存
CSS_VERSION = "v20260601a"

def make_page(title, content, nav="recruit", extra_css="", user=None):
    # 头部用户状态栏
    user_bar = ""
    if user:
        user_bar = f"""
        <div style="width:100%;display:flex;justify-content:flex-end;align-items:center;gap:6px;padding:4px 0 0;font-size:11px;">
            <span style="color:var(--text2);">👤 {user["nickname"]}</span>
            <a href="/user/logout" style="color:var(--text2);">退出</a>
        </div>"""
    else:
        user_bar = """
        <div style="width:100%;display:flex;justify-content:flex-end;align-items:center;gap:6px;padding:4px 0 0;font-size:11px;">
            <a href="/account" style="color:var(--accent2);">登录 / 注册</a>
        </div>"""

    nav_links = [
        ("/", "🏭", "招聘", "recruit"),
        ("/ai-match", "🤖", "AI匹配", "aimatch"),
        ("/feedback", "💬", "反馈", "feedback"),
    ]
    nav_html = ""
    for url, icon, text, key in nav_links:
        cls = ' class="active"' if key == nav else ""
        nav_html += f'<a href="{url}"{cls}><span class="nav-icon">{icon}</span>{text}</a>'
    # 统一用户入口
    my_label = "登录"
    if user:
        my_label = "我的"
    nav_html += f'<a href="/my"><span class="nav-icon">👤</span>{my_label}</a>'
    return (
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>"
        + "<meta name='viewport' content='width=device-width,initial-scale=1.0'>"
        + "<title>" + title + "</title><style>" + CSS + extra_css + "</style>"
        + "<script>" + JS + "</script></head><body>"
        + "<div class='page'>" + user_bar + content + "<nav class='nav'>" + nav_html + "</nav></div></body></html>"
    )

def card(title, body):
    return "<div class='card'><div class='card-title'>" + title + "</div>" + body + "</div>"

def tag(text, color="blue"):
    c = {"green": "tag-green", "red": "tag-red", "yellow": "tag-yellow", "blue": "tag-blue"}
    return "<span class='tag " + c.get(color, "tag-blue") + "'>" + text + "</span>"

def time_ago(ts):
    """显示相对时间：今天/昨天/X天前/X周前"""
    if not ts:
        return ""
    try:
        dt = datetime.strptime(ts[:10], "%Y-%m-%d")
        days = (datetime.now() - dt).days
        if days == 0: return "今天"
        if days == 1: return "昨天"
        if days < 7: return f"{days}天前"
        if days < 30: return f"{days//7}周前"
        return f"{days//30}月前"
    except:
        return ts[:10]

def days_ago(ts):
    """返回发布时间距今的天数，用于排序和标记"""
    if not ts: return 999
    try:
        dt = datetime.strptime(ts[:10], "%Y-%m-%d")
        return (datetime.now() - dt).days
    except:
        return 999

# ==============================
#       AI 智 能 匹 配 引 擎
# ==============================

LOCATION_KEYWORDS = ["里建", "武鸣", "东盟", "武华", "双桥", "罗波", "宁武", "府城"]
JOB_TYPE_KEYWORDS = {"夜班", "白班", "兼职", "全职", "小时工", "日结", "临时工", "长期"}
CATEGORY_KEYWORDS = {
    "食品": "食品加工", "工厂": "食品加工", "普工": "食品加工",
    "餐饮": "餐饮", "服务员": "餐饮", "厨师": "餐饮", "阿姨": "餐饮",
    "物流": "物流", "快递": "物流", "分拣": "物流", "送货": "物流",
    "学生": "学生兼职", "兼职": "学生兼职", "实习": "学生兼职",
}

def parse_query(text):
    """解析用户自然语言查询，提取关键信息"""
    info = {"salary_min": 0, "location": "", "job_type": "", "category": "", "keywords": []}
    text_lower = text.lower()

    # 提取薪资期望
    salary_patterns = [
        (r'(\d+\.?\d*)\s*块', 1),        # "20块"
        (r'(\d+\.?\d*)\s*元', 1),        # "20元"
        (r'(\d+\.?\d*)\s*千', 1000),     # "3千"
        (r'(\d+\.?\d*)\s*万', 10000),    # "1万"
        (r'(\d+)\s*[—\-~到至]\s*(\d+)', 0),  # "3000-5000"
    ]
    for pat, multiplier in salary_patterns:
        m = re.search(pat, text)
        if m:
            if multiplier == 0:
                info["salary_min"] = int(m.group(1))
                info["salary_max"] = int(m.group(2))
            else:
                info["salary_min"] = int(float(m.group(1)) * multiplier)
            # 有薪资期望，以此筛选
            if info["salary_min"] >= 10 and info["salary_min"] < 200:
                info["salary_min"] = info["salary_min"] * 22  # 时薪换算月薪（22天）
            break

    # 提取地点
    for loc in LOCATION_KEYWORDS:
        if loc in text:
            info["location"] = loc
            break

    # 提取工作类型
    for jt in JOB_TYPE_KEYWORDS:
        if jt in text:
            info["job_type"] = jt
            break

    # 提取分类关键词
    for kw, cat in CATEGORY_KEYWORDS.items():
        if kw in text:
            info["category"] = cat
            break

    # 提取其他关键词（去掉标点、数字、已匹配的关键词）
    cleaned = re.sub(r'[，。！？、；：""''（）\(\)\[\]\d+\.\d+元块千]', ' ', text)
    stop_words = set(LOCATION_KEYWORDS + list(JOB_TYPE_KEYWORDS) + list(CATEGORY_KEYWORDS.keys()) +
                     ["找", "想", "要", "有", "在", "的", "和", "或", "与", "工作", "上班", "招聘", "招人"])
    words = [w.strip() for w in re.split(r'[\s,，]+', cleaned) if w.strip() and w.strip() not in stop_words and len(w.strip()) > 1]
    info["keywords"] = words[:5]

    return info

def ai_match_jobs(query_text, limit=10):
    """AI智能匹配：解析用户需求 → 多维度评分 → 排序返回"""
    conn = get_recruit_db()
    all_jobs = conn.execute("SELECT * FROM jobs WHERE status='active'").fetchall()
    conn.close()

    info = parse_query(query_text)

    scored = []
    for j in all_jobs:
        score = 0
        reasons = []
        combined_text = f"{j['title']} {j['company']} {j['description'] or ''} {j['tags'] or ''} {j['location']} {j['job_type']} {j['category']}"

        # 地点匹配（+30分）
        if info["location"] and info["location"] in (j["location"] or ""):
            score += 30
            reasons.append(f"📍 在{info['location']}")

        # 工作类型匹配（+20分）- 检查 tags、title、job_type 和 description
        if info["job_type"]:
            if info["job_type"] in combined_text:
                score += 20
                reasons.append(f"🕐 {info['job_type']}")

        # 薪资匹配（+25分）
        if info["salary_min"] > 0:
            job_monthly = j["salary_min"] if "月" in (j["salary_unit"] or "") else j["salary_min"] * 22
            if info.get("salary_max", 0) > 0:
                if job_monthly >= info["salary_min"] and job_monthly <= info["salary_max"]:
                    score += 25
                    reasons.append("💰 薪资符合预期")
            elif job_monthly >= info["salary_min"]:
                score += 25
                reasons.append("💰 薪资达到期望")

        # 分类匹配（+15分）
        if info["category"] and info["category"] == j["category"]:
            score += 15
            reasons.append(f"📂 {info['category']}")

        # 关键词匹配（每个+5分，最多+10分）
        kw_match_count = 0
        for kw in info["keywords"]:
            if kw in combined_text:
                kw_match_count += 1
        if kw_match_count > 0:
            score += min(10, kw_match_count * 5)
            reasons.append(f"🔑 匹配需求")

        if score > 0:
            max_score = 100
            pct = min(100, round(score / max_score * 100))
            scored.append((pct, score, j, reasons))

    # 按得分排序
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return scored[:limit]


def format_match_results(scored, query):
    """把匹配结果格式化成HTML"""
    if not scored:
        return """
        <div style="text-align:center;padding:30px 0;color:var(--text2);">
            <div style="font-size:40px;margin-bottom:12px;">🔍</div>
            <p>没有找到匹配的岗位</p>
            <p style="font-size:12px;margin-top:8px;">试试换个说法，比如「里建夜班」「武鸣小时工」「食品厂」</p>
        </div>"""

    html = f'<div style="margin-bottom:8px;color:var(--text2);font-size:12px;">找到 {len(scored)} 个匹配岗位</div>'
    for i, (pct, score, j, reasons) in enumerate(scored):
        s_min = j['salary_min'] if j['salary_min'] else 0
        s_max = j['salary_max'] if j['salary_max'] else 0
        if s_min == 0 and s_max == 0:
            salary = '<span style="color:var(--orange);">面议</span>'
        elif s_max:
            salary = f"{s_min}-{s_max}{j['salary_unit']}"
        else:
            salary = f"{s_min}{j['salary_unit']}"
        # 匹配度进度条颜色
        bar_color = "var(--green)" if pct >= 70 else ("var(--yellow)" if pct >= 40 else "var(--red)")
        tags_html = ""
        for t in (j["tags"] or "").split(","):
            if t.strip(): tags_html += f'<span class="tag">{t.strip()}</span>'
        reasons_html = "&nbsp;·&nbsp;".join(reasons[:3])

        html += f"""
        <div class="job-card" style="border-left:3px solid {bar_color};">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <div class="job-title">{j["title"]}</div>
                <div style="font-size:11px;color:{bar_color};font-weight:600;">匹配度 {pct}%</div>
            </div>
            <div style="height:4px;background:var(--border);border-radius:2px;margin-bottom:6px;">
                <div style="height:100%;width:{pct}%;background:{bar_color};border-radius:2px;transition:width 0.5s;"></div>
            </div>
            <div class="job-meta">{j["company"]} | {j["location"]} | {j["job_type"]}</div>
            <div class="job-salary">{salary}</div>
            <div class="job-desc" style="font-size:11px;color:var(--accent2);">{reasons_html}</div>
            <div class="job-footer">{tags_html}<span class="source">{j["source"]}</span></div>
        </div>"""
    return html

# ==============================
#         公 开 路 由
# ==============================

@app.get("/", response_class=HTMLResponse)
async def public_jobs(request: Request, q: str = "", cat: str = "", loc: str = "", jt: str = ""):
    """公开招聘首页 - 岗位列表+筛选+智能匹配入口"""
    uid = check_user(request) or (check_auth(request) and "admin")
    user_info = get_user_info(uid) if uid and uid != "admin" else None
    conn = get_recruit_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    where = "WHERE status IN ('active','pending')"
    params = []
    if cat:
        where += " AND category=?"
        params.append(cat)
    if loc:
        where += " AND location LIKE ?"
        params.append(f"%{loc}%")
    if jt:
        where += " AND job_type=?"
        params.append(jt)
    if q:
        where += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
        qp = f"%{q}%"
        params.extend([qp, qp, qp])

    jobs = conn.execute(f"SELECT * FROM jobs {where} ORDER BY created_at DESC", params).fetchall()
    categories = [r["category"] for r in conn.execute("SELECT DISTINCT category FROM jobs WHERE status IN ('active','pending') ORDER BY category").fetchall()]
    locations = [r["location"] for r in conn.execute("SELECT DISTINCT location FROM jobs WHERE status='active' AND location != '' ORDER BY location").fetchall()]
    job_types = [r["job_type"] for r in conn.execute("SELECT DISTINCT job_type FROM jobs WHERE status='active' AND job_type != '' ORDER BY job_type").fetchall()]
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='active'").fetchone()[0]
    conn.close()

    # 分类筛选
    cat_btns = '<a href="/#jobs" class="btn-sm ' + ('active' if not (cat or loc or jt) else '') + '">全部</a>'
    for c in categories:
        c_encoded = urllib.parse.quote(c)
        active = 'active' if cat == c else ''
        extra = f"&loc={urllib.parse.quote(loc)}" if loc else ""
        extra += f"&jt={urllib.parse.quote(jt)}" if jt else ""
        cat_btns += f'<a href="/?cat={c_encoded}{extra}#jobs" class="btn-sm {active}">{c}</a>'

    # 地区筛选
    loc_btns = '<div style="font-size:11px;color:var(--text2);margin:6px 0 2px;">📍 地区：</div>'
    loc_options = ["里建", "武鸣", "东盟"]
    seen = set()
    for l in locations:
        for opt in loc_options:
            if opt in l and opt not in seen:
                seen.add(opt)
                active = 'active' if loc == opt else ''
                extra = f"&cat={urllib.parse.quote(cat)}" if cat else ""
                extra += f"&jt={urllib.parse.quote(jt)}" if jt else ""
                loc_btns += f'<a href="/?loc={opt}{extra}#jobs" class="btn-sm {active}">{opt}</a>'
    if loc and loc not in seen:
        # 自定义地点
        seen.add(loc)
        active = 'active'
        extra = f"&cat={urllib.parse.quote(cat)}" if cat else ""
        loc_btns += f'<a href="/?loc={urllib.parse.quote(loc)}{extra}#jobs" class="btn-sm {active}">{loc}</a>'
    if loc:
        loc_btns += f'<a href="/#jobs" class="btn-sm" style="color:var(--red);">✕ 清除</a>'

    # 工作类型筛选
    jt_btns = '<div style="font-size:11px;color:var(--text2);margin:6px 0 2px;">🕐 类型：</div>'
    type_labels = {"全职": "全职", "兼职": "兼职", "小时工": "小时工", "日结": "日结", "临时工": "临时工"}
    for jt_val, jt_label in type_labels.items():
        if jt_val in job_types:
            active = 'active' if jt == jt_val else ''
            extra = f"&cat={urllib.parse.quote(cat)}" if cat else ""
            extra += f"&loc={urllib.parse.quote(loc)}" if loc else ""
            jt_btns += f'<a href="/?jt={jt_val}{extra}#jobs" class="btn-sm {active}">{jt_label}</a>'
    if jt:
        jt_btns += f'<a href="/#jobs" class="btn-sm" style="color:var(--red);">✕ 清除</a>'

    # 岗位列表（点击进详情页）
    jobs_html = ""
    for j in jobs:
        s_min = j['salary_min'] if j['salary_min'] else 0
        s_max = j['salary_max'] if j['salary_max'] else 0
        if s_min == 0 and s_max == 0:
            salary = '<span style="color:var(--orange);">面议</span>'
            salary_plain = "面议"
        elif s_max:
            salary = f"{s_min}-{s_max}{j['salary_unit']}"
            salary_plain = salary
        else:
            salary = f"{s_min}{j['salary_unit']}"
            salary_plain = salary
        tags_html = ""
        for t in (j["tags"] or "").split(","):
            if t.strip(): tags_html += f'<span class="tag">{t.strip()}</span>'
        ta = time_ago(j["created_at"])
        time_tag = f'<span style="font-size:10px;color:var(--text2);margin-left:auto;">{ta}</span>'
        company_encoded = urllib.parse.quote(j["company"])
        # 联系方式栏：登录显示电话，未登录显示提示
        contact_html = ""
        if j["contact_phone"]:
            if uid:
                cn = j["contact_name"] or ""
                contact_html = f'<div class="job-contact" style="font-size:12px;margin:4px 0;">📞 <a href="tel:{j["contact_phone"]}" style="color:var(--green);text-decoration:none;font-weight:600;">{cn} {j["contact_phone"]}</a></div>'
            else:
                contact_html = '<div class="job-contact" style="font-size:12px;margin:4px 0;">🔒 <a href="/login" style="color:var(--accent2);text-decoration:none;font-size:11px;">登录后可查看联系方式 →</a></div>'
        # 从描述中提取关键信息：要求、福利、地址等
        desc = j["description"] or ""
        # 未登录时，脱敏描述中的电话号码
        if not uid:
            desc = re.sub(r'(1[3-9]\d{9})', r'🔒\1****', desc)
            desc = re.sub(r'((0\d{2,3})[- ]?\d{7,8})', r'🔒****', desc)
            desc = re.sub(r'【联系电话[^】]*】\s*[^\n]*', '🔒 登录后可查看', desc)
            desc = re.sub(r'【联系电话/微信[^】]*】\s*[^\n]*', '🔒 登录后可查看', desc)
        # 摘要文本：描述前120字
        desc_short = desc[:120] + ("..." if len(desc) > 120 else "")

        # 构建要求/福利摘要块（job-highlight）
        highlight_lines = []
        desc_lower = desc.lower()
        seen_labels = set()
        for kw, label, icon in [("要求：", "要求", "📋"), ("要求:", "要求", "📋"), ("福利：", "福利", "🎁"), ("福利:", "福利", "🎁")]:
            if kw in desc:
                idx = desc.find(kw)
                end_idx = desc.find("【", idx + 5)
                if end_idx == -1 or end_idx - idx > 100:
                    end_idx = min(idx + 80, len(desc))
                frag = desc[idx + len(kw):end_idx].strip().rstrip("。；；").replace("。", " · ").replace("；", " · ")
                # 如果提取内容包含其他标签，截断
                for other_kw in ["福利：", "福利:", "要求：", "要求:", "公司简介：", "公司简介:", "地址：", "地址:"]:
                    if other_kw != kw and other_kw in frag:
                        frag = frag[:frag.find(other_kw)].strip().rstrip(" ·，,")
                if frag and len(frag) > 3 and label not in seen_labels:
                    seen_labels.add(label)
                    highlight_lines.append(f'<span><span class="hl-label">{icon} {label}</span><span class="hl-text">{frag[:100]}</span></span>')
        highlight_html = ""
        if highlight_lines:
            highlight_html = '<div class="job-highlight">' + "<br>".join(highlight_lines[:2]) + "</div>"

        # 福利标签（带颜色的圆角胶囊）
        benefit_map = {
            "五险一金": 1, "五险": 1, "包吃包住": 1, "包吃住": 1, "包吃": 2,
            "包住": 2, "餐补": 2, "月休4天": 3, "月休": 3, "长白班": 3,
            "两班倒": 3, "日结": 4, "周结": 4, "大专": 2, "中专": 2,
        }
        extra_tags = ""
        tag_idx = 0
        for kw, tclass in benefit_map.items():
            if kw.lower() in desc_lower:
                cls = f"benefit-tag-{tclass}"
                extra_tags += f'<span class="benefit-tag {cls}">{kw}</span>'
                tag_idx += 1
                if tag_idx >= 6:
                    break

        jobs_html += f"""\
        <a href="/job/{j['id']}" style="text-decoration:none;color:inherit;display:block;">
        <div class="job-card">
            <div style="display:flex;justify-content:space-between;align-items:start;gap:8px;">
                <div class="job-title">{j["title"]}</div>
                {time_tag}
            </div>
            <div class="job-meta">
                <a href="/company/{company_encoded}" class="company-link" onclick="event.stopPropagation();">{j["company"]}</a>
                <span><span class="meta-icon">📍</span>{j["location"]}</span>
                <span><span class="meta-icon">🕐</span>{j["job_type"]}</span>
            </div>
            <div class="job-salary">{salary}</div>
            {highlight_html}
            <div class="job-desc">{desc_short}</div>
            <div class="job-benefits">{extra_tags}</div>
            {contact_html}
            <div class="job-footer">{tags_html}<span class="source">{j["source"]}</span>
                <span style="display:inline-flex;gap:4px;">
                    <button onclick="copyJob(event,&#39;{j['id']}&#39;,&#39;{j['title'].replace(chr(39),'')}&#39;,&#39;{j['company'].replace(chr(39),'')}&#39;,&#39;{salary_plain.replace(chr(39),'')}&#39;,&#39;{(j['contact_phone'] or '').replace(chr(39),'')}&#39;)" class="act-btn" title="复制岗位信息">📋</button>
                    <button onclick="shareJob(event,&#39;{j['title'].replace(chr(39),'')}&#39;,&#39;{j['company'].replace(chr(39),'')}&#39;,&#39;{salary_plain.replace(chr(39),'')}&#39;,&#39;{j['location'].replace(chr(39),'')}&#39;)" class="act-btn" title="分享到微信">📤</button>
                </span>
            </div>
        </div>
        </a>"""

    result_count = len(jobs)
    result_info = f'<span style="font-size:12px;color:var(--text2);">找到 {result_count} 个岗位</span>' if (cat or loc or jt or q) else ""

    search_html = f"""
    <form action="/#jobs" method="get" class="search-form">
        <input type="text" name="q" value="{q}" placeholder="搜索岗位、公司...">
        <button type="submit">搜索</button>
    </form>"""

    empty_text = "<p style='color:var(--text2);text-align:center;padding:30px 0;'>暂无匹配的岗位</p>"

    # ====== 🏆 名企/重点企业直招专区 ======
    # 渲染函数
    def _feat_card(name, job_count, salary_range, jobs_list, icon, tag):
        return f"""
            <a href="/company/{urllib.parse.quote(name)}" {tag}>
                <div style="display:flex;align-items:center;background:var(--card2);border-radius:10px;padding:10px 12px;margin-bottom:6px;gap:10px;">
                    <div style="font-size:22px;width:36px;text-align:center;">{icon}</div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:13px;font-weight:600;color:var(--accent2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name}</div>
                        <div style="font-size:11px;color:var(--text2);margin-top:2px;">{job_count}个岗位 {salary_range}</div>
                        <div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:2px;">{jobs_list}</div>
                    </div>
                    <div style="font-size:18px;color:var(--text2);">›</div>
                </div>
            </a>"""

    # 手动置顶的头部企业（品牌优先，固定在前）
    top_companies = [
        "广西东盟弗迪电池有限公司（比亚迪）", "佛山市海天（南宁）调味食品有限公司",
        "南宁双汇食品有限公司", "百威英博啤酒（南宁）有限公司",
        "广西伊利冷冻食品有限公司", "天丝红牛（广西）饮料有限公司",
        "广西宁泰服装有限公司（李宁）",
    ]
    # 品牌颜色和图标映射
    brand_colors = {
        "比亚迪": "#4CAF50", "海天": "#E53935", "双汇": "#1565C0",
        "百威": "#FDD835", "伊利": "#1B5E20", "红牛": "#E65100",
        "李宁": "#D32F2F", "益华": "#9C27B0", "景鸿源": "#00BCD4",
        "嘉能可": "#FF5722", "荣辉": "#607D8B", "宝瑞坦": "#795548",
        "博格": "#FF9800", "壮方": "#3F51B5", "贝联": "#009688",
    }
    brand_icon = {
        "比亚迪":"🚗","海天":"🥫","双汇":"🥩","百威":"🍺","伊利":"🍦",
        "红牛":"🥤","李宁":"👕","益华":"📦","景鸿源":"📦","嘉能可":"🥤",
        "荣辉":"🔧","宝瑞坦":"💊","博格":"🍞","壮方":"🧪","贝联":"⚙️",
    }

    featured_html = ""
    conn2 = get_recruit_db()
    
    # 1. 先处理置顶的头部企业
    processed = set()
    for fc in top_companies:
        rows = conn2.execute("SELECT id, title, salary_min, salary_max, salary_unit FROM jobs WHERE company=? AND status='active' ORDER BY created_at DESC", (fc,)).fetchall()
        if rows:
            processed.add(fc)
            all_min = [r['salary_min'] for r in rows if r['salary_min'] and r['salary_min'] > 0]
            all_max = [r['salary_max'] for r in rows if r['salary_max'] and r['salary_max'] > 0]
            if all_min and all_max:
                salary_range = f"<span style='font-size:11px;color:var(--green);font-weight:600;'>{min(all_min)}-{max(all_max)}{rows[0]['salary_unit']}</span>"
            else:
                salary_range = "<span style='font-size:11px;color:var(--orange);font-weight:600;'>面议</span>"
            jobs_list = "".join(f'<span style="font-size:11px;color:var(--text);margin-right:4px;">·{r["title"]}</span>' for r in rows[:4])
            if len(rows) > 4:
                jobs_list += f'<span style="font-size:11px;color:var(--text2);">+{len(rows)-4}个...</span>'
            tag = "style='text-decoration:none;display:block;'"
            for k, color in brand_colors.items():
                if k in fc:
                    tag = f"style='text-decoration:none;display:block;border-left:3px solid {color};'"
                    break
            icon = next((v for k, v in brand_icon.items() if k in fc), "🏢")
            featured_html += _feat_card(fc, len(rows), salary_range, jobs_list, icon, tag)
    
    # 2. 查数据库按岗位数排序，追加其他企业（最多8家）
    extra = conn2.execute("""
        SELECT company, COUNT(*) as cnt FROM jobs 
        WHERE status='active' AND company NOT IN ('东盟经开区企业','劳务公司','食品厂','物流公司','民宿','糖水店','单位食堂','拼多多','里建高校','东盟经开区企业','六点半豆奶')
        GROUP BY company ORDER BY cnt DESC LIMIT 15
    """).fetchall()
    
    added = 0
    for ec, cnt in extra:
        if ec in processed:
            continue
        rows = conn2.execute("SELECT id, title, salary_min, salary_max, salary_unit FROM jobs WHERE company=? AND status='active' ORDER BY created_at DESC", (ec,)).fetchall()
        if rows:
            all_min = [r['salary_min'] for r in rows if r['salary_min'] and r['salary_min'] > 0]
            all_max = [r['salary_max'] for r in rows if r['salary_max'] and r['salary_max'] > 0]
            if all_min and all_max:
                salary_range = f"<span style='font-size:11px;color:var(--green);font-weight:600;'>{min(all_min)}-{max(all_max)}{rows[0]['salary_unit']}</span>"
            elif all_min:
                salary_range = f"<span style='font-size:11px;color:var(--green);font-weight:600;'>{min(all_min)}{rows[0]['salary_unit']}</span>"
            else:
                salary_range = "<span style='font-size:11px;color:var(--orange);font-weight:600;'>面议</span>"
            jobs_list = "".join(f'<span style="font-size:11px;color:var(--text);margin-right:4px;">·{r["title"]}</span>' for r in rows[:3])
            if len(rows) > 3:
                jobs_list += f'<span style="font-size:11px;color:var(--text2);">+{len(rows)-3}个...</span>'
            tag = next((f"style='text-decoration:none;display:block;border-left:3px solid {color};'" for k, color in brand_colors.items() if k in ec), "style='text-decoration:none;display:block;border-left:3px solid #666;'")
            icon = next((v for k, v in brand_icon.items() if k in ec), "🏢")
            featured_html += _feat_card(ec, len(rows), salary_range, jobs_list, icon, tag)
            added += 1
            if added >= 8:
                break
    
    conn2.close()
    featured_section = f"""
    <div class="card" style="background:linear-gradient(135deg,#1a1a3e,#2a1a3e);border:1px solid #4a2a5e;">
        <div class="card-title" style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:16px;">🏆</span> 名企直招
            <span style="font-size:11px;color:var(--text2);font-weight:400;margin-left:auto;">按岗位数排序</span>
        </div>
        <div class="featured-grid">{featured_html}</div>
    </div>
    """ if featured_html else ""

    content = f"""
    <div class='header'><h1>\U0001f3ed 武鸣招聘</h1><div class='time'>{now}  |  共{total_jobs}个岗位</div></div>
    <div class="card" style="background:linear-gradient(135deg,var(--card),#2a1a4e);border:1px solid #4a2a7e;text-align:center;padding:8px 10px;">
        <a href="/ai-match" style="display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;">
            <span style="font-size:18px;">🤖</span>
            <span style="font-size:13px;font-weight:600;color:var(--accent2);">AI帮你找工作</span>
            <span style="font-size:11px;color:var(--text2);">说需求，智能匹配</span>
            <span style="background:linear-gradient(135deg,#6c5ce7,#a29bfe);border-radius:6px;padding:4px 12px;color:white;font-size:12px;font-weight:600;white-space:nowrap;">💬 试试</span>
        </a>
    </div>
    {featured_section}
    {search_html}
    <div class='filter-row'>{cat_btns}</div>
    <div class="filter-row">{loc_btns}</div>
    <div class="filter-row">{jt_btns}</div>
    <div style="margin:6px 0;">{result_info}</div>
    <div class='jobs-list' id='jobs'>{jobs_html or empty_text}</div>
    <hr style="border-color:var(--border);margin:24px 0;">
    <div style="text-align:center;color:var(--text2);font-size:11px;padding-bottom:10px;">
        <a href="/login" style="color:var(--accent2);text-decoration:none;">\u2699 管理后台</a>
    </div>
    """

    return make_page("武鸣招聘 - 找工作", content, "recruit", user=user_info)


# ==============================
#      岗 位 详 情 页
# ==============================

@app.get("/job/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: int):
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    conn = get_recruit_db()
    j = conn.execute("SELECT * FROM jobs WHERE id=? AND status='active'", (job_id,)).fetchone()
    if not j:
        conn.close()
        return HTMLResponse("<h2>岗位不存在</h2><a href='/'>返回首页</a>")

    # 同类岗位推荐
    similar = conn.execute(
        "SELECT * FROM jobs WHERE id!=? AND status='active' AND (category=? OR company LIKE ?) LIMIT 3",
        (job_id, j["category"], f"%{j['company']}%")
    ).fetchall()
    conn.close()

    s_min = j['salary_min'] if j['salary_min'] else 0
    s_max = j['salary_max'] if j['salary_max'] else 0
    if s_min == 0 and s_max == 0:
        salary = '<span style="color:var(--orange);">面议</span>'
    elif s_max:
        salary = f"{s_min}-{s_max}{j['salary_unit']}"
    else:
        salary = f"{s_min}{j['salary_unit']}"
    ta = time_ago(j["created_at"])
    tags_html = ""
    for t in (j["tags"] or "").split(","):
        if t.strip(): tags_html += f'<span class="tag">{t.strip()}</span>'

    # 分享按钮（复制到剪贴板）
    share_phone = (j['contact_phone'] or '见详情') if user_info else '登录后可查看'
    share_text = f"【武鸣招聘】{j['company']} 招 {j['title']}，{salary}，{j['location']}，电话：{share_phone}"

    similar_html = ""
    for s in similar:
        s_salary = f"{s['salary_min']}-{s['salary_max']}{s['salary_unit']}" if s['salary_max'] else f"{s['salary_min']}{s['salary_unit']}"
        similar_html += f"""
        <a href="/job/{s['id']}" style="text-decoration:none;display:block;">
            <div style="background:var(--card2);padding:8px 12px;border-radius:8px;margin-bottom:4px;">
                <div style="font-size:13px;color:var(--accent2);">{s['title']}</div>
                <div style="font-size:11px;color:var(--text2);">{s['company']} | {s_salary}</div>
            </div>
        </a>"""

    safe_share = share_text.replace("'", "\\'")
    # 未登录时描述脱敏
    desc_display = j['description'] or '暂无详细描述'
    if not user_info:
        desc_display = re.sub(r'(1[3-9]\d{9})', r'🔒\1****', desc_display)
        desc_display = re.sub(r'【联系电话[^】]*】\s*[^\n]*', '🔒 登录后可查看', desc_display)
        desc_display = re.sub(r'【联系电话/微信[^】]*】\s*[^\n]*', '🔒 登录后可查看', desc_display)
    content = f"""
    <div class="header" style="text-align:left;padding:8px 0;">
        <a href="/" style="color:var(--text2);font-size:12px;">← 返回列表</a>
    </div>
    <div class="card">
        <div style="font-size:20px;font-weight:700;color:var(--accent2);">{j['title']}</div>
        <div style="font-size:12px;color:var(--text2);margin:4px 0;">
            <a href="/company/{urllib.parse.quote(j['company'])}" style="color:var(--accent2);">{j['company']}</a>
             | {j['location']} | {j['job_type']} | <span>{ta}</span>
        </div>
        <div style="font-size:22px;font-weight:700;color:var(--green);margin:8px 0;">{salary}</div>
        <div style="font-size:14px;line-height:1.8;margin:8px 0;">{desc_display}</div>
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin:8px 0;">{tags_html}</div>
        <hr style="border-color:var(--border);margin:12px 0;">
        <div style="font-size:14px;">
"""
    if user_info:
        contact_name = j['contact_name'] or '招聘方'
        contact_phone = j['contact_phone'] or ''
        content += f"""
            <div style="text-align:center;">
                <a href="tel:{contact_phone}" style="display:block;background:var(--green);color:white;text-decoration:none;
                    padding:14px 0;border-radius:10px;font-size:18px;font-weight:700;margin-bottom:10px;">
                    📞 联系 {contact_name}
                </a>
                <div style="font-size:13px;color:var(--text2);margin-bottom:4px;">{contact_phone}</div>
                <div style="font-size:11px;color:var(--text2);">🔗 来源：{j['source']}</div>
            </div>"""
    else:
        content += f"""
            <div style="text-align:center;padding:12px;background:var(--card2);border-radius:8px;">
                <div style="font-size:24px;margin-bottom:8px;">🔒</div>
                <div style="font-size:13px;color:var(--text2);margin-bottom:8px;">登录后可查看联系方式</div>
                <a href="/user/login" class="btn" style="display:inline-block;margin-bottom:4px;">🔑 登录</a>
                <div style="font-size:11px;color:var(--text2);">
                    没有账号？<a href="/user/register" style="color:var(--accent2);">立即注册</a>
                </div>
                <div style="font-size:11px;color:var(--text2);margin-top:8px;">🔗 来源：{j['source']}</div>
            </div>"""
    content += f"""
        </div>
    </div>

    <!-- 一键复制（含岗位信息+网站链接） -->
    <button onclick="copyText('{safe_share}\\n\\n📱 武鸣招聘 http://192.144.129.59/',this)"
            style="width:100%;background:var(--accent);border:none;border-radius:8px;padding:12px;color:white;font-size:14px;cursor:pointer;font-weight:600;">
        📋 复制岗位 · 发到微信
    </button>
    <div style="font-size:11px;color:var(--text2);text-align:center;margin-top:6px;margin-bottom:12px;">
        复制后粘贴到微信群或朋友圈
    </div>

    {f'<div class="card"><div class="card-title">🔥 同类推荐</div>{similar_html}</div>' if similar_html else ''}
    """
    return make_page(f"{j['title']} - 武鸣招聘", content, "recruit", user=user_info)


# ==============================
#      企 业 主 页
# ==============================

@app.get("/company/{company_name}", response_class=HTMLResponse)
async def company_page(request: Request, company_name: str):
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    conn = get_recruit_db()
    name = urllib.parse.unquote(company_name)
    jobs = conn.execute("SELECT * FROM jobs WHERE company=? AND status='active' ORDER BY created_at DESC", (name,)).fetchall()
    count = len(jobs)
    conn.close()

    jobs_html = ""
    for j in jobs:
        s_min = j['salary_min'] if j['salary_min'] else 0
        s_max = j['salary_max'] if j['salary_max'] else 0
        if s_min == 0 and s_max == 0:
            salary = '<span style="color:var(--orange);">面议</span>'
        elif s_max:
            salary = f"{s_min}-{s_max}{j['salary_unit']}"
        else:
            salary = f"{s_min}{j['salary_unit']}"
        ta = time_ago(j["created_at"])
        jobs_html += f"""
        <a href="/job/{j['id']}" style="text-decoration:none;display:block;">
        <div class="job-card">
            <div style="display:flex;justify-content:space-between;">
                <div class="job-title">{j['title']}</div>
                <span style="font-size:10px;color:var(--text2);">{ta}</span>
            </div>
            <div class="job-meta">{j['location']} | {j['job_type']}</div>
            <div class="job-salary">{salary}</div>
        </div>
        </a>"""

    content = f"""
    <div class="header" style="text-align:left;">
        <a href="/" style="color:var(--text2);font-size:12px;">← 返回首页</a>
    </div>
    <div class="card" style="text-align:center;">
        <div style="font-size:22px;font-weight:700;">🏢 {name}</div>
        <div style="font-size:13px;color:var(--text2);margin-top:4px;">在招 {count} 个岗位</div>
    </div>
    <div class='jobs-list'>{jobs_html or '<p style="color:var(--text2);text-align:center;padding:20px;">暂无在招岗位</p>'}</div>
    """
    return make_page(f"{name} - 武鸣招聘", content, "recruit", user=user_info)


# ==============================
#      AI 智 能 匹 配 路 由
# ==============================

@app.get("/ai-match", response_class=HTMLResponse)
async def ai_match_page(request: Request, q: str = ""):
    """AI智能匹配页面"""
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    result_html = ""
    query_text = q

    if q:
        scored = ai_match_jobs(q)
        result_html = format_match_results(scored, q)

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
    </div>
    """
    return make_page("AI智能匹配 - 武鸣招聘", content, "recruit", user=user_info)


@app.post("/ai-match", response_class=HTMLResponse)
async def ai_match_post(request: Request, q: str = Form("")):
    """AI匹配提交（POST方式）"""
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    if q:
        scored = ai_match_jobs(q)
        result_html = format_match_results(scored, q)
    else:
        result_html = "<p style='color:var(--text2);text-align:center;padding:20px;'>请输入你的求职需求</p>"

    content = f"""
    <div class='header'>
        <h1>🤖 AI智能匹配</h1>
        <div class='time'>说需求，AI帮你找工作</div>
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
    </div>
    {result_html}
    <div style="margin-top:12px;text-align:center;">
        <a href="/" style="color:var(--text2);font-size:12px;">← 返回全部岗位</a>
    </div>
    """
    return make_page("AI智能匹配 - 武鸣招聘", content, "recruit", user=user_info)



# ==============================
#      求 职 者 注 册 / 登 录
# ==============================

@app.get("/user/register", response_class=HTMLResponse)
async def user_register_page():
    """求职者注册页面"""
    content = """
    <div class='header'><h1>📝 求职者注册</h1><div class='time'>注册后可查看岗位联系方式</div></div>
    <div class="card" style="max-width:400px;margin:0 auto;">
        <form action="/user/register" method="post" style="display:flex;flex-direction:column;gap:10px;">
            <input name="nickname" placeholder="昵称 *" required
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <input name="phone" placeholder="手机号 *" required type="tel"
                   pattern="[0-9]{11}" minlength="11" maxlength="11"
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <input name="wechat" placeholder="微信号"
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <input name="password" placeholder="设置密码（至少6位）*" required type="password" minlength="6"
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <select name="want_job" style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
                <option value="">想找什么类型的工作（选填）</option>
                <option value="食品加工">食品加工</option><option value="服装制衣">服装制衣</option>
                <option value="包装印刷">包装/印刷</option><option value="物流仓储">物流仓储</option>
                <option value="餐饮服务">餐饮服务</option><option value="制药">制药</option>
                <option value="其他">其他</option>
            </select>
            <textarea name="experience" rows="2" placeholder="工作经验或技能（选填）"
                      style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;resize:none;"></textarea>
            <button type="submit" style="background:linear-gradient(135deg,#6c5ce7,#a29bfe);border:none;border-radius:8px;
                    padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">
                ✅ 注册
            </button>
        </form>
        <div style="text-align:center;margin-top:12px;font-size:12px;color:var(--text2);">
            已有账号？<a href="/user/login" style="color:var(--accent2);">去登录</a>
        </div>
    </div>
    """
    return make_page("注册 - 武鸣招聘", content, "recruit")

@app.post("/user/register", response_class=HTMLResponse)
async def user_register_submit(request: Request, nickname: str = Form(...), phone: str = Form(...),
    wechat: str = Form(""), password: str = Form(...), want_job: str = Form(""), experience: str = Form("")):
    # 手机号格式验证
    import re
    if not re.match(r'^1[3-9]\d{9}$', phone):
        return HTMLResponse("""
        <div class='header'><h1>❌ 注册失败</h1></div>
        <div class="card" style="text-align:center;">
            <p style="color:var(--red);">手机号格式不正确，请输入11位有效手机号</p>
            <a href="/user/register" class="btn" style="margin-top:12px;">重新注册</a>
        </div>
        """)
    
    # 开始注册
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        conn.execute("""INSERT INTO users (nickname, phone, wechat, want_job, experience, password_hash, created_at)
                       VALUES (?,?,?,?,?,?,?)""", (nickname, phone, wechat, want_job, experience, pwd_hash, now_dt))
        conn.commit()
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # 自动登录
        token = secrets.token_hex(32)
        expire = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO user_tokens (user_id, token, expire_at, created_at) VALUES (?,?,?,?)",
                     (uid, token, expire, now_dt))
        conn.commit()
        conn.close()
        html = "<div class='header'><h1>✅ 注册成功！</h1></div><div style='text-align:center;'><p>正在跳转...</p></div>"
        resp = HTMLResponse(content=make_page("注册成功", html, "recruit"))
        resp.set_cookie("user_session", token, max_age=30*86400, httponly=True, samesite="lax", path="/")
        resp.delete_cookie("session", path="/")
        resp.delete_cookie("ent_session", path="/")
        return resp
    except Exception as e:
        conn.close()
        return HTMLResponse(f"""
        <div class='header'><h1>❌ 注册失败</h1></div>
        <div class="card" style="text-align:center;">
            <p style="color:var(--red);">手机号可能已被注册</p>
            <a href="/user/register" class="btn" style="margin-top:12px;">重新注册</a>
        </div>
        """)

@app.get("/user/login", response_class=HTMLResponse)
async def user_login_page():
    content = """
    <div class='header'><h1>🔑 求职者登录</h1><div class='time'>登录后可查看岗位联系方式</div></div>
    <div class="card" style="max-width:360px;margin:0 auto;">
        <form action="/user/login" method="post" style="display:flex;flex-direction:column;gap:10px;">
            <input name="phone" placeholder="手机号" required
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <input name="password" placeholder="密码" required type="password"
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <button type="submit" style="background:var(--accent);border:none;border-radius:8px;
                    padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">
                🔑 登录
            </button>
        </form>
        <div style="text-align:center;margin-top:12px;font-size:12px;color:var(--text2);">
            没有账号？<a href="/user/register" style="color:var(--accent2);">立即注册</a>
        </div>
    </div>
    """
    return make_page("登录 - 武鸣招聘", content, "recruit")

@app.post("/user/login", response_class=HTMLResponse)
async def user_login_submit(request: Request, phone: str = Form(...), password: str = Form(...)):
    conn = get_recruit_db()
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    user = conn.execute("SELECT id, nickname FROM users WHERE phone=? AND password_hash=?", (phone, pwd_hash)).fetchone()
    if not user:
        conn.close()
        return HTMLResponse("""
        <div class='header'><h1>❌ 登录失败</h1></div>
        <div class="card" style="text-align:center;">
            <p style="color:var(--red);">手机号或密码错误</p>
            <a href="/user/login" class="btn" style="margin-top:12px;">重新登录</a>
        </div>
        """)
    # 生成token
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    token = secrets.token_hex(32)
    expire = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO user_tokens (user_id, token, expire_at, created_at) VALUES (?,?,?,?)",
                 (user["id"], token, expire, now_dt))
    conn.execute("UPDATE users SET last_login=? WHERE id=?", (now_dt, user["id"]))
    conn.commit()
    conn.close()
    html = f"""
    <div class='header'><h1>✅ 欢迎回来，{user['nickname']}！</h1></div>
    <div style="text-align:center;"><a href="/" class="btn">返回首页</a></div>
    """
    resp = HTMLResponse(content=make_page("登录成功", html, "recruit"))
    resp.set_cookie("user_session", token, max_age=30*86400, httponly=True, samesite="lax", path="/")
    resp.delete_cookie("session", path="/")
    resp.delete_cookie("ent_session", path="/")
    return resp

@app.get("/user/logout", response_class=HTMLResponse)
async def user_logout():
    resp = RedirectResponse(url="/")
    resp.delete_cookie("user_session", path="/")
    return resp


# ==============================
#      管 理 员 登 录 路 由
# ==============================

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    content = """
    <div class='header'><h1>\u2699 管理后台</h1><div class='time'>请输入密码登录</div></div>
    <div class="card" style="max-width:360px;margin:40px auto;">
        <form action="/login" method="post" style="display:flex;flex-direction:column;gap:12px;">
            <input type="password" name="password" placeholder="请输入密码"
                   style="padding:12px 14px;border-radius:8px;border:1px solid var(--border);
                          background:var(--card2);color:var(--text);font-size:16px;">
            <button type="submit" class="btn" style="width:100%;padding:12px;font-size:15px;">登录</button>
        </form>
        <div style="text-align:center;margin-top:12px;">
            <a href="/" style="color:var(--text2);font-size:12px;">\u2190 返回招聘页</a>
        </div>
    </div>
    """
    return make_page("登录 - 武鸣招聘", content, "recruit")


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request):
    form = await request.form()
    pwd = form.get("password", "")

    if pwd != ADMIN_PASSWORD:
        content = """
        <div class='header'><h1>\u274c 密码错误</h1></div>
        <div class="card" style="max-width:360px;margin:40px auto;text-align:center;">
            <p style="color:var(--red);margin-bottom:16px;">密码不正确，请重试</p>
            <a href="/login" class="btn">重新输入</a>
        </div>
        """
        return make_page("登录失败", content, "recruit")

    # 生成 token
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{ADMIN_PASSWORD}:::{salt}".encode()).hexdigest()
    token = f"{salt}::{hashed}"

    # 持久化（跨服务重启有效）
    _save_session_key(token)

    html = """
    <div class='header'><h1>\u2705 登录成功</h1></div>
    <div class="card" style="max-width:360px;margin:40px auto;text-align:center;">
        <p style="margin-bottom:16px;">正在跳转到管理后台...</p>
        <a href="/admin" class="btn">\u2192 进入后台</a>
    </div>
    """
    resp = HTMLResponse(content=make_page("登录成功", html, "recruit"))
    resp.set_cookie(key="session", value=token, max_age=SESSION_HOURS * 3600,
                    httponly=True, samesite="lax", path="/")
    # 额外设置持久 cookie（跨浏览器会话）
    resp.set_cookie(key="session_persist", value="1", max_age=30 * 86400, path="/")
    resp.delete_cookie("user_session", path="/")
    resp.delete_cookie("ent_session", path="/")
    return resp


@app.get("/logout", response_class=HTMLResponse)
async def logout():
    resp = RedirectResponse(url="/")
    resp.delete_cookie("session", path="/")
    resp.delete_cookie("session_persist", path="/")
    return resp


# ==============================
#      受 保 护 管 理 路 由
# ==============================

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")

    conn = get_recruit_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 统计
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='active'").fetchone()[0]
    total_channels = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    pending_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='pending'").fetchone()[0]
    pending_ents = conn.execute("SELECT COUNT(*) FROM enterprises WHERE status='pending'").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")

    cat_stats = conn.execute("SELECT category, COUNT(*) as cnt FROM jobs WHERE status='active' GROUP BY category ORDER BY cnt DESC").fetchall()

    pending_warn = ""
    if pending_jobs > 0 or pending_ents > 0:
        pending_warn = f"""
        <div class="card" style="background:#2d1a1a;border:1px solid #e17055;">
            <div style="font-size:13px;font-weight:600;color:var(--red);margin-bottom:6px;">\u26a0️ 待办事项</div>
            <div style="display:flex;gap:12px;">
                {f'<div><span style="font-size:18px;font-weight:700;color:var(--yellow);">{pending_jobs}</span><span style="font-size:11px;color:var(--text2);margin-left:4px;">个岗位待审核</span><a href="/admin/jobs" class="btn-sm" style="color:var(--yellow);margin-left:6px;">去处理</a></div>' if pending_jobs > 0 else ''}
                {f'<div><span style="font-size:18px;font-weight:700;color:var(--yellow);">{pending_ents}</span><span style="font-size:11px;color:var(--text2);margin-left:4px;">家企业待审核</span><a href="/admin/enterprises" class="btn-sm" style="color:var(--yellow);margin-left:6px;">去处理</a></div>' if pending_ents > 0 else ''}
            </div>
        </div>"""

    content = f"""
    <div class='header'><h1>\U0001f3ed 管理后台</h1><div class='time'>{now} | <a href="/logout" style="color:var(--text2);font-size:11px;">退出</a></div></div>
    {pending_warn}
    <div style='display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-bottom:12px;'>
        <div class='stat-card'><div class='stat-num'>{total_jobs}</div><div class='stat-label'>岗位</div></div>
        <div class='stat-card'><div class='stat-num' style="color:var(--yellow);">{pending_jobs}</div><div class='stat-label'>待审岗位</div></div>
        <div class='stat-card'><div class='stat-num' style="color:var(--yellow);">{pending_ents}</div><div class='stat-label'>待审企业</div></div>
        <div class='stat-card'><div class='stat-num'>{total_channels}</div><div class='stat-label'>渠道</div></div>
    </div>
    <div style='display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;'>
        <a href="/admin/jobs" class="btn">\U0001f4cb 岗位管理</a>
        <a href="/admin/channels" class="btn">\U0001f4e1 渠道管理</a>
        <a href="/admin/scripts" class="btn">\U0001f3ac 视频脚本</a>
        <a href='/admin/gen_script' class='btn' style='background:#e74c3c;'>🎥 生成脚本</a>
        <a href="/admin/feedback" class="btn" style="background:#a29bfe;">💬 反馈管理</a>
        <a href="/admin/enterprises" class="btn" style="background:#00b894;">🏢 企业管理</a>
        <a href="/admin/resumes" class="btn" style="background:#e17055;">📄 简历管理</a>
        <a href="/ai-match" class="btn" style="background:#6c5ce7;">🤖 AI匹配</a>
        <a href="/recruit/video" class="btn" style="background:#00b894;">\U0001f4f9 视频模式</a>
    </div>
    <div class="card">
        <div class="card-title">岗位分类统计</div>
    """
    for cs in cat_stats:
        content += f'<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;"><span>{cs["category"]}</span><span style="color:var(--accent2);">{cs["cnt"]}个岗位</span></div>'
    content += "</div>"
    conn.close()
    return make_page("管理后台", content, "recruit")


# ====== 管理后台 - 反馈管理 ======

@app.get("/admin/feedback", response_class=HTMLResponse)
async def admin_feedback(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    feedbacks = conn.execute("SELECT id, content, contact, page, status, created_at FROM feedback ORDER BY created_at DESC").fetchall()
    total = len(feedbacks)
    pending = conn.execute("SELECT COUNT(*) FROM feedback WHERE status='pending'").fetchone()[0]
    conn.close()
    rows = ""
    for fb in feedbacks:
        rows += f"""<div style="background:var(--card2);border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid {'var(--yellow)' if fb['status']=='pending' else 'var(--green)'};">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div style="font-size:13px;color:var(--text);flex:1;">{fb['content'][:500]}</div>
                <div style="font-size:11px;color:var(--text2);white-space:nowrap;margin-left:8px;">{fb['created_at'][:16]}</div>
            </div>
            <div style="display:flex;gap:12px;margin-top:6px;font-size:11px;color:var(--text2);">
                <span>📞 {fb['contact'] or '未留'}</span>
                <span>📍 {fb['page'] or '未知'}</span>
                <span>#{fb['id']} {'⏳待处理' if fb['status']=='pending' else '✅已处理'}</span>
                <a href="/admin/feedback/done/{fb['id']}" style="color:var(--green);text-decoration:none;margin-left:auto;" onclick="return confirm('标记已处理？')">✅ 标记处理</a>
            </div></div>"""
    content = f"""<div class='header'><h1>💬 反馈管理</h1><div class='time'>共{total}条 | 待处理{pending}条 | <a href="/admin" style="color:var(--text2);font-size:11px;">← 返回</a></div></div>
    <div style="display:flex;gap:8px;margin-bottom:12px;">
        <div class="stat-card"><div class="stat-num">{total}</div><div class="stat-label">全部</div></div>
        <div class="stat-card"><div class="stat-num" style="color:var(--yellow);">{pending}</div><div class="stat-label">待处理</div></div>
    </div>
    <div>{rows or '<p style="color:var(--text2);text-align:center;padding:30px;">暂无反馈</p>'}</div>"""
    return make_page("反馈管理 - 武鸣招聘", content, "recruit")

@app.get("/admin/feedback/done/{fb_id}")
async def mark_feedback_done(fb_id: int):
    conn = get_recruit_db()
    conn.execute("UPDATE feedback SET status='done' WHERE id=?", (fb_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/feedback")


@app.get("/admin/jobs", response_class=HTMLResponse)
async def admin_jobs(request: Request, cat: str = "", q: str = ""):
    if not check_auth(request):
        return RedirectResponse(url="/login")

    conn = get_recruit_db()
    where = "WHERE status IN ('active','pending')"
    params = []
    if cat:
        where += " AND category=?"
        params.append(cat)
    if q:
        where += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
        qp = f"%{q}%"
        params.extend([qp, qp, qp])

    jobs = conn.execute(f"SELECT * FROM jobs {where} ORDER BY created_at DESC", params).fetchall()
    categories = [r["category"] for r in conn.execute("SELECT DISTINCT category FROM jobs WHERE status IN ('active','pending') ORDER BY category").fetchall()]
    pending_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='pending'").fetchone()[0]
    conn.close()

    cat_btns = '<a href="/admin/jobs" class="btn-sm ' + ('active' if not cat else '') + '">全部</a>'
    for c in categories:
        c_encoded = urllib.parse.quote(c)
        active = 'active' if cat == c else ''
        cat_btns += f'<a href="/admin/jobs?cat={c_encoded}" class="btn-sm {active}">{c}</a>'

    jobs_html = ""
    for j in jobs:
        s_min = j['salary_min'] if j['salary_min'] else 0
        s_max = j['salary_max'] if j['salary_max'] else 0
        if s_min == 0 and s_max == 0:
            salary = '<span style="color:var(--orange);">面议</span>'
        elif s_max:
            salary = f"{s_min}-{s_max}{j['salary_unit']}"
        else:
            salary = f"{s_min}{j['salary_unit']}"
        tags_html = ""
        for t in (j["tags"] or "").split(","):
            if t.strip(): tags_html += f'<span class="tag">{t.strip()}</span>'
        ta = time_ago(j["created_at"])
        status_badge = '<span class="tag" style="background:var(--yellow);color:#000;">⏳ 待审核</span>' if j['status']=='pending' else ''
        border_color = "var(--yellow)" if j['status']=='pending' else "var(--accent)"
        approve_btn = f'<a href="/admin/job/approve/{j["id"]}" class="btn-sm" style="color:var(--green);" onclick="return confirm(\'确定上架 {j["title"]}?\')">✅ 上架</a>' if j['status']=='pending' else ''
        jobs_html += f"""
        <div class="job-card" style="border-left:3px solid {border_color};">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div class="job-title">{j["title"]} {status_badge}</div>
                <span style="font-size:10px;color:var(--text2);">{ta}</span>
            </div>
            <div class="job-meta">{j["company"]} | {j["location"]} | {j["job_type"]}</div>
            <div class="job-salary">{salary}</div>
            <div class="job-desc">{j["description"][:60] or ""}</div>
            <div class="job-contact" style="font-size:12px;margin:4px 0;">
                {('<a href="tel:' + j['contact_phone'] + '" style="color:var(--green);text-decoration:none;font-weight:600;">📞 ' + (j['contact_name'] or '') + ' ' + j['contact_phone'] + '</a>') if j['contact_phone'] else '<span style="color:var(--red);">📞 无联系方式</span>'}
            </div>
            <div class="job-footer" style="justify-content:space-between;">
                <div><span class="source">{j['source']}</span></div>
                <div>
                    {approve_btn}
                    <a href="/admin/job/edit/{j['id']}" class="btn-sm" style="color:var(--yellow);">✏️编辑</a>
                    <a href="/admin/job/delete/{j['id']}" onclick="return confirm('确定删除 {j['title']}?')" 
                       class="btn-sm" style="color:var(--red);">🗑️删除</a>
                </div>
            </div>
        </div>"""

    content = f"""
    <div class='header'>
        <h1>\U0001f4cb 岗位管理</h1>
        <div class='time'><a href="/admin" style="color:var(--text2);">\u2190 返回后台</a></div>
    </div>
    <div style="margin-bottom:8px;">
        <a href="/admin/job/add" class="btn" style="background:var(--green);">➕ 新增岗位</a>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:8px;">
        <div class="stat-card"><div class="stat-num">{len(jobs)}</div><div class="stat-label">全部</div></div>
        <div class="stat-card"><div class="stat-num" style="color:var(--yellow);">{pending_count}</div><div class="stat-label">待审核</div></div>
    </div>
    <div style='margin-bottom:8px;'>{cat_btns}</div>
    <div class='jobs-list'>{jobs_html or "<p style='color:var(--text2);text-align:center;padding:20px 0;'>暂无岗位</p>"}</div>
    """
    return make_page("岗位管理", content, "recruit")


# ========== 后台：新增岗位 ==========
@app.get("/admin/job/add", response_class=HTMLResponse)
async def admin_job_add_form(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    now = datetime.now().strftime("%Y-%m-%d")
    return make_page("新增岗位", f"""
    <div class='header'><h1>➕ 新增岗位</h1><div class='time'><a href="/admin/jobs" style="color:var(--text2);">\u2190 返回</a></div></div>
    <form action="/admin/job/add" method="post" style="display:flex;flex-direction:column;gap:8px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <input name="title" placeholder="岗位名称 *" required
                   style="grid-column:1/2;background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <input name="company" placeholder="公司名称 *" required
                   style="grid-column:2/3;background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
            <input name="location" placeholder="地点（里建/武鸣）"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <input name="salary_min" placeholder="最低薪资" type="number"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <input name="salary_max" placeholder="最高薪资" type="number"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <select name="salary_unit" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
                <option value="元/月">元/月</option>
                <option value="元/时">元/时</option>
                <option value="元/天">元/天</option>
            </select>
            <select name="job_type" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
                <option value="全职">全职</option><option value="兼职">兼职</option>
                <option value="小时工">小时工</option><option value="日结">日结</option>
                <option value="临时工">临时工</option>
            </select>
        </div>
        <input name="category" placeholder="分类（食品加工/餐饮/物流/服装/包装/印刷/制药/学生兼职/其他）"
               style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        <textarea name="description" rows="3" placeholder="岗位要求、职责描述"
                  style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;"></textarea>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <input name="contact_phone" placeholder="联系电话"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <input name="tags" placeholder="标签（逗号分隔，如 夜班,急招）"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        </div>
        <button type="submit" style="background:var(--green);border:none;border-radius:8px;padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">
            ✅ 保存岗位
        </button>
    </form>
    """, "recruit")

@app.post("/admin/job/add", response_class=HTMLResponse)
async def admin_job_add_submit(request: Request, 
    title: str = Form(...), company: str = Form(...), location: str = Form(""),
    salary_min: int = Form(0), salary_max: int = Form(0), 
    salary_unit: str = Form("元/月"), job_type: str = Form("全职"),
    category: str = Form("其他"), description: str = Form(""),
    contact_phone: str = Form(""), tags: str = Form("")):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("""INSERT INTO jobs (title,company,location,salary_min,salary_max,salary_unit,
                   job_type,category,description,contact_phone,tags,source,status,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,'后台添加','active',?)""",
                 (title, company, location, salary_min, salary_max, salary_unit,
                  job_type, category, description, contact_phone, tags, now_dt))
    conn.commit()
    conn.close()
    return HTMLResponse("""
    <div class='header'><h1>✅ 添加成功</h1></div>
    <div style="text-align:center;"><a href="/admin/jobs" class="btn">返回岗位列表</a></div>
    """)

# ========== 后台：编辑岗位 ==========
@app.get("/admin/job/edit/{job_id}", response_class=HTMLResponse)
async def admin_job_edit_form(request: Request, job_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    j = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not j:
        return HTMLResponse("<h2>岗位不存在</h2>")
    return make_page("编辑岗位", f"""
    <div class='header'><h1>✏️ 编辑岗位</h1><div class='time'><a href="/admin/jobs" style="color:var(--text2);">\u2190 返回</a></div></div>
    <form action="/admin/job/edit/{job_id}" method="post" style="display:flex;flex-direction:column;gap:8px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <input name="title" value="{j['title']}" placeholder="岗位名称"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <input name="company" value="{j['company']}" placeholder="公司名称"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
            <input name="location" value="{j['location'] or ''}" placeholder="地点"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <input name="salary_min" value="{j['salary_min'] or 0}" type="number"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <input name="salary_max" value="{j['salary_max'] or 0}" type="number"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <select name="salary_unit" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
                <option {"selected" if j['salary_unit']=='元/月' else ""} value="元/月">元/月</option>
                <option {"selected" if j['salary_unit']=='元/时' else ""} value="元/时">元/时</option>
                <option {"selected" if j['salary_unit']=='元/天' else ""} value="元/天">元/天</option>
            </select>
            <select name="job_type" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
                <option {"selected" if j['job_type']=='全职' else ""}>全职</option>
                <option {"selected" if j['job_type']=='兼职' else ""}>兼职</option>
                <option {"selected" if j['job_type']=='小时工' else ""}>小时工</option>
                <option {"selected" if j['job_type']=='日结' else ""}>日结</option>
                <option {"selected" if j['job_type']=='临时工' else ""}>临时工</option>
            </select>
        </div>
        <input name="category" value="{j['category'] or '其他'}" placeholder="分类"
               style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        <textarea name="description" rows="3" placeholder="描述"
                  style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;">{j['description'] or ''}</textarea>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <input name="contact_phone" value="{j['contact_phone'] or ''}" placeholder="电话"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <input name="tags" value="{j['tags'] or ''}" placeholder="标签"
                   style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        </div>
        <button type="submit" style="background:var(--yellow);border:none;border-radius:8px;padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">
            💾 保存修改
        </button>
    </form>
    """, "recruit")

@app.post("/admin/job/edit/{job_id}", response_class=HTMLResponse)
async def admin_job_edit_submit(request: Request, job_id: int,
    title: str = Form(...), company: str = Form(...), location: str = Form(""),
    salary_min: int = Form(0), salary_max: int = Form(0), 
    salary_unit: str = Form("元/月"), job_type: str = Form("全职"),
    category: str = Form("其他"), description: str = Form(""),
    contact_phone: str = Form(""), tags: str = Form("")):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("""UPDATE jobs SET title=?,company=?,location=?,salary_min=?,salary_max=?,
                   salary_unit=?,job_type=?,category=?,description=?,contact_phone=?,tags=?,updated_at=?
                   WHERE id=?""",
                 (title, company, location, salary_min, salary_max, salary_unit,
                  job_type, category, description, contact_phone, tags, now_dt, job_id))
    conn.commit()
    conn.close()
    return HTMLResponse(f"""
    <div class='header'><h1>✅ 修改成功</h1></div>
    <div style="text-align:center;margin:16px;">
        <a href="/admin/jobs" class="btn">返回岗位列表</a>
        <a href="/job/{job_id}" class="btn" style="background:var(--accent2);">查看岗位</a>
    </div>
    """)

# ========== 后台：删除岗位 ==========
@app.get("/admin/job/delete/{job_id}", response_class=HTMLResponse)
async def admin_job_delete(request: Request, job_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    conn.execute("UPDATE jobs SET status='deleted' WHERE id=?", (job_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/jobs")

@app.get("/admin/job/approve/{job_id}")
async def admin_job_approve(job_id: int):
    conn = get_recruit_db()
    conn.execute("UPDATE jobs SET status='active' WHERE id=?", (job_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/jobs")




@app.get("/admin/channels", response_class=HTMLResponse)
async def admin_channels(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")

    conn = get_recruit_db()
    channels = conn.execute("SELECT * FROM channels ORDER BY type").fetchall()
    conn.close()

    channels_html = ""
    for ch in channels:
        channels_html += f"""
        <div class="ch-card">
            <div class="ch-name">{ch["name"]}</div>
            <div class="ch-type">{ch["type"]}</div>
            <div class="ch-info">{ch["description"] or ""}</div>
            <div class="ch-info">{ch["notes"] or ""}</div>
            <div class="ch-contact">{ch["contact"] or ""}</div>
        </div>"""

    content = f"""
    <div class='header'><h1>\U0001f4e1 渠道管理</h1><div class='time'><a href="/admin" style="color:var(--text2);">\u2190 返回后台</a></div></div>
    <div>{channels_html or "<p style='color:var(--text2);'>暂无渠道</p>"}</div>
    """
    return make_page("渠道管理", content, "recruit")


@app.get("/admin/scripts", response_class=HTMLResponse)
async def admin_scripts(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")

    conn = get_recruit_db()
    scripts = conn.execute("SELECT * FROM video_scripts ORDER BY created_at DESC LIMIT 10").fetchall()
    conn.close()

    scripts_html = ""
    for s in scripts:
        scripts_html += f"""
        <div class="script-card">
            <div class="script-title">{s["title"]}</div>
            <div class="script-meta">平台：{s["target_platform"]} | 类型：{s["script_type"]} | {s["date"]}</div>
            <pre class="script-content">{s["content"][:500]}{"..." if len(s["content"]) > 500 else ""}</pre>
        </div>"""

    content = f"""
    <div class='header'><h1>\U0001f3ac 视频脚本</h1><div class='time'><a href="/admin" style="color:var(--text2);">\u2190 返回后台</a></div></div>
    <div style="margin-bottom:12px;"><a href="/admin/gen_script" class="btn" style="background:#e74c3c;">\U0001f3a5 生成新脚本</a></div>
    {scripts_html or "<p style='color:var(--text2);'>暂无脚本</p>"}
    """
    return make_page("视频脚本", content, "recruit")


@app.get("/admin/gen_script", response_class=HTMLResponse)
async def admin_gen_script(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")

    conn = get_recruit_db()
    today = datetime.now().strftime("%Y-%m-%d")

    jobs = conn.execute("SELECT * FROM jobs WHERE status='active' ORDER BY RANDOM() LIMIT 3").fetchall()
    if len(jobs) < 3:
        content = "<div class='header'><h1>\u26a0\ufe0f 岗位不足</h1><p style='text-align:center;padding:30px;'>至少需要3个岗位才能生成脚本</p></div>"
        return make_page("生成脚本", content, "recruit")

    job_titles = "\u3001".join([j["title"] for j in jobs])
    script_content = f"""【口播稿 - 武鸣今日好工作】

（开场）
大家好，我是武鸣本地找工作的小冯！
今天给大家带来几个武鸣和里建的好岗位，全是真实招聘！

（岗位1）
第一个：【{jobs[0]["title"]}】
{ jobs[0]["company"]} 在招人
薪资：{ jobs[0]["salary_min"]}-{jobs[0]["salary_max"]}{jobs[0]["salary_unit"]}
工作地点：{jobs[0]["location"]}
{ jobs[0]["description"][:100] if jobs[0]["description"] else ""}

（岗位2）
第二个：【{jobs[1]["title"]}】
薪资：{jobs[1]["salary_min"]}-{jobs[1]["salary_max"]}{jobs[1]["salary_unit"]}

（岗位3）
第三个：【{jobs[2]["title"]}】
{ jobs[2]["company"]} 招人
薪资：{jobs[2]["salary_min"]}-{jobs[2]["salary_max"]}{jobs[2]["salary_unit"]}

（结尾）
想了解更多武鸣本地工作，关注我，每天更新！
#武鸣找工作 #东盟经开区 #武鸣招聘

【发布时间建议】中午12:00或晚上20:00
【推荐平台】抖音 + 视频号同步"""

    conn.execute("INSERT INTO video_scripts(date, title, script_type, content, target_platform, related_jobs, created_at) VALUES (?,?,?,?,?,?,?)",
                 (today, f"武鸣今日好工作 - {today}", "口播", script_content, "抖音+视频号", job_titles, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

    content = f"""
    <div class='header'><h1>\U0001f3ac 视频脚本已生成</h1><div class='time'>{today}</div></div>
    <a href="/admin/scripts" class="btn" style="margin-bottom:12px;">\U0001f519 返回脚本列表</a>
    <a href="/recruit/video" class="btn" style="margin-bottom:12px;background:#00b894;">\U0001f4f9 打开视频模式</a>
    <div class="script-card" style="background:var(--card);padding:16px;border-radius:8px;white-space:pre-wrap;font-size:13px;line-height:1.8;font-family:monospace;">{script_content}</div>
    <div style="margin-top:12px;padding:12px;background:var(--card2);border-radius:8px;font-size:12px;">
        <b>\U0001f4a1 发布建议</b><br>
        1. 打开抖音→点"+"→上传视频或直接用文字模式<br>
        2. 复制上面口播稿，对着念或者录屏展示<br>
        3. 添加话题 #武鸣找工作 #东盟经开区 #里建招聘<br>
        4. 定位：广西-东盟经济技术开发区<br>
        5. 最佳发布时间：中午12:00 或 晚上20:00
    </div>
    """
    return make_page("生成脚本", content, "recruit")


# ==============================
#      视 频 模 式（公开）
# ==============================

@app.get("/recruit/video", response_class=HTMLResponse)
async def recruit_video(cat: str = ""):
    """视频录制模式 - 大字清晰，适合屏幕录制。公开访问"""
    conn = get_recruit_db()
    where = "WHERE status IN ('active','pending')"
    params = []
    if cat:
        where += " AND category=?"
        params.append(cat)
    jobs = conn.execute(f"SELECT * FROM jobs {where} ORDER BY RANDOM() LIMIT 6", params).fetchall()
    conn.close()

    cards = ""
    for j in jobs:
        s_min = j['salary_min'] if j['salary_min'] else 0
        s_max = j['salary_max'] if j['salary_max'] else 0
        if s_min == 0 and s_max == 0:
            salary = '<span style="color:var(--orange);">面议</span>'
        elif s_max:
            salary = f"{s_min}-{s_max}{j['salary_unit']}"
        else:
            salary = f"{s_min}{j['salary_unit']}"
        cards += f"""
        <div class="v-card">
            <div class="v-company">{j['company']}</div>
            <div class="v-title">{j['title']}</div>
            <div class="v-salary">{salary}</div>
            <div class="v-location">{j['location']} | {j['job_type']}</div>
            <div class="v-desc">{j['description'] or ''}</div>
            <div class="v-contact">联系：{j['contact_phone'] or '私信获取'}</div>
        </div>"""

    cats_html = ""
    for c in ["全部", "食品加工", "餐饮", "物流", "学生兼职"]:
        active = "active" if (c == "全部" and not cat) or c == cat else ""
        href = f"/recruit/video?cat={c}" if c != "全部" else "/recruit/video"
        cats_html += f'<a href="{href}" class="v-cat {active}">{c}</a>'

    now = datetime.now().strftime("%m月%d日")

    return HTMLResponse(f"""<!DOCTYPE html><html lang='zh-CN'><head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'>
<title>武鸣招聘 - 视频模式</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,'PingFang SC',sans-serif; background:#0f0f1a; color:#fff; min-height:100vh; }}
.v-header {{ text-align:center; padding:20px 16px 12px; background:linear-gradient(135deg,#6c5ce7,#a29bfe); }}
.v-header h1 {{ font-size:24px; font-weight:700; }}
.v-header p {{ font-size:12px; opacity:0.8; margin-top:4px; }}
.v-cats {{ display:flex; gap:6px; padding:10px 16px; overflow-x:auto; }}
.v-cat {{ padding:6px 14px; border-radius:20px; background:#222240; color:#999; text-decoration:none; font-size:12px; white-space:nowrap; }}
.v-cat.active {{ background:#6c5ce7; color:#fff; }}
.v-list {{ padding:12px 16px 80px; display:flex; flex-direction:column; gap:12px; }}
.v-card {{ background:linear-gradient(135deg,#1a1a2e,#222240); border-radius:12px; padding:20px; border:1px solid #2d2d4a; }}
.v-company {{ font-size:11px; color:#9999b0; margin-bottom:4px; }}
.v-title {{ font-size:20px; font-weight:700; color:#a29bfe; margin-bottom:6px; }}
.v-salary {{ font-size:22px; font-weight:700; color:#00b894; margin-bottom:4px; }}
.v-location {{ font-size:12px; color:#9999b0; margin-bottom:8px; }}
.v-desc {{ font-size:13px; line-height:1.6; margin-bottom:8px; }}
.v-contact {{ font-size:14px; color:#fdcb6e; padding-top:8px; border-top:1px solid #2d2d4a; }}
.v-footer {{ position:fixed; bottom:0; left:0; right:0; background:#1a1a2e; padding:12px 16px; text-align:center; border-top:1px solid #2d2d4a; font-size:11px; color:#9999b0; }}
.v-footer a {{ color:#a29bfe; text-decoration:none; }}
@media (min-width:500px) {{ .v-list {{ max-width:480px; margin:0 auto; }} }}
</style>
</head><body>
<div class="v-header">
    <h1>\U0001f3ed 武鸣今日好工作</h1>
    <p>{now}更新 \u2022 武鸣本地招聘平台</p>
</div>
<div class="v-cats">{cats_html}</div>
<div class="v-list">{cards}</div>
<div class="v-footer">关注我，每天更新武鸣好工作 \U0001f447<br><a href="/">\U0001f3e0 返回首页</a></div>
</body></html>""")


# ==============================
#      建 议 反 馈
# ==============================

@app.get("/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request):
    """反馈提交页面"""
    uid = check_user(request) or (check_auth(request) and "admin")
    user_info = get_user_info(uid) if uid and uid != "admin" else None
    
    content = """
    <div class='header'><h1>💬 建议反馈</h1>
        <div class='time'>你的意见帮助我们做得更好</div>
    </div>
    <div class="card">
        <form id="feedbackForm" style="display:flex;flex-direction:column;gap:12px;">
            <div>
                <label style="font-size:13px;color:var(--text2);display:block;margin-bottom:4px;">📝 你的建议 / 问题描述 *</label>
                <textarea name="content" id="fbContent" rows="5" required
                    style="width:100%;background:var(--card2);border:1px solid var(--border);border-radius:8px;
                           padding:12px;color:var(--text);font-size:14px;resize:vertical;"
                    placeholder="例如：希望增加某某公司的招聘信息、页面功能建议、遇到的bug……"></textarea>
            </div>
            <div>
                <label style="font-size:13px;color:var(--text2);display:block;margin-bottom:4px;">📞 联系方式（选填）</label>
                <input type="text" name="contact" id="fbContact"
                    style="width:100%;background:var(--card2);border:1px solid var(--border);border-radius:8px;
                           padding:10px 12px;color:var(--text);font-size:14px;"
                    placeholder="微信 / 手机号，方便我们联系你">
            </div>
            <div>
                <label style="font-size:13px;color:var(--text2);display:block;margin-bottom:4px;">📍 当前页面（自动）</label>
                <input type="text" name="page" id="fbPage" readonly
                    style="width:100%;background:var(--card2);border:1px solid var(--border);border-radius:8px;
                           padding:10px 12px;color:var(--text2);font-size:13px;"
                    value="首页">
            </div>
            <button type="submit" id="fbSubmit"
                style="background:linear-gradient(135deg,#6c5ce7,#a29bfe);border:none;border-radius:8px;
                       padding:14px 0;color:white;font-size:16px;font-weight:600;cursor:pointer;">
                💬 提交反馈
            </button>
        </form>
        <div id="fbSuccess" style="display:none;text-align:center;padding:20px 0;">
            <div style="font-size:48px;margin-bottom:12px;">✅</div>
            <div style="font-size:16px;font-weight:600;color:var(--green);">感谢你的反馈！</div>
            <div style="font-size:13px;color:var(--text2);margin-top:6px;">我们会认真查看每一条建议</div>
            <a href="/" class="btn" style="display:inline-block;margin-top:16px;">← 返回首页</a>
        </div>
    </div>
    <div class="card" style="background:var(--card2);">
        <div style="font-size:13px;color:var(--text2);line-height:1.8;">
            <div style="font-weight:600;color:var(--text);margin-bottom:6px;">📌 常见问题快速解决</div>
            · 岗位信息有误？直接搜索公司名，进入详情页查看<br>
            · 想发布招聘？联系管理员<br>
            · 网站打不开？检查网络或刷新重试
        </div>
    </div>
    <script>
    document.getElementById('feedbackForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        var btn = document.getElementById('fbSubmit');
        btn.textContent = '⏳ 提交中...';
        btn.disabled = true;
        var data = {
            content: document.getElementById('fbContent').value,
            contact: document.getElementById('fbContact').value,
            page: document.getElementById('fbPage').value
        };
        try {
            var resp = await fetch('/api/feedback', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            var result = await resp.json();
            if (result.ok) {
                document.getElementById('feedbackForm').style.display = 'none';
                document.getElementById('fbSuccess').style.display = 'block';
            } else {
                alert('提交失败：' + (result.msg || '未知错误'));
            }
        } catch(e) {
            alert('网络错误，请重试');
        }
        btn.textContent = '💬 提交反馈';
        btn.disabled = false;
    });
    </script>
    """
    return make_page("建议反馈 - 武鸣招聘", content, "feedback", user=user_info)


@app.post("/api/feedback")
async def submit_feedback(request: Request):
    """接收反馈提交"""
    try:
        data = await request.json()
        content = (data.get("content") or "").strip()
        contact = (data.get("contact") or "").strip()
        page = (data.get("page") or "").strip()
        
        if not content or len(content) < 5:
            return {"ok": False, "msg": "请填写至少5个字符的建议内容"}
        
        conn = get_recruit_db()
        conn.execute(
            "INSERT INTO feedback (content, contact, page) VALUES (?, ?, ?)",
            (content, contact, page)
        )
        conn.commit()
        conn.close()
        return {"ok": True, "msg": "提交成功"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ==============================
#   旧路由兼容（重定向到新路由）
# ==============================

@app.get("/recruit", response_class=HTMLResponse)
async def recruit_redirect(request: Request):
    """兼容旧链接，已登录进后台，未登录进公开首页"""
    if check_auth(request):
        return RedirectResponse(url="/admin")
    return RedirectResponse(url="/")


# ==============================
#      企 业 与 简 历 模 块
# ==============================
#!/usr/bin/env python3
"""Enterprise and Resume route modules - generated code for wuming recruitment"""
# This file contains enterprise auth, enterprise routes, and resume routes

import hashlib, secrets
from datetime import datetime, timedelta
from fastapi import Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse

# ==============================
#      企 业 端 认 证
# ==============================

def check_enterprise(request: Request):
    token = request.cookies.get("ent_session")
    if not token:
        return None
    try:
        conn = get_recruit_db()
        ent = conn.execute(
            "SELECT e.* FROM enterprises e JOIN enterprise_tokens t ON e.id=t.enterprise_id WHERE t.token=? AND t.expire_at>datetime('now')",
            (token,)
        ).fetchone()
        conn.close()
        return dict(ent) if ent else None
    except:
        return None

def get_enterprise_info(ent_id):
    conn = get_recruit_db()
    e = conn.execute("SELECT * FROM enterprises WHERE id=?", (ent_id,)).fetchone()
    conn.close()
    return dict(e) if e else None

def make_ent_token(ent_id):
    token = secrets.token_hex(32)
    conn = get_recruit_db()
    exp = (datetime.now() + timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO enterprise_tokens (enterprise_id, token, expire_at, created_at) VALUES (?,?,?,?)",
                 (ent_id, token, exp, now))
    conn.commit()
    conn.close()
    return token

def make_ent_password(password):
    return hashlib.sha256(f"ent::{password}".encode()).hexdigest()

# ==============================
#   HTML BUILDERS
# ==============================

def _ent_header(title, back_link_text, back_url):
    bt = f'<a href="{back_url}" style="color:var(--text2);font-size:12px;">{back_link_text}</a>' if back_url else ""
    return f'<div class="header"><h1>{title}</h1><div class="time">{bt}</div></div>'

def _ent_input(name, placeholder, required=False, type_="text", value=""):
    req = " required" if required else ""
    val = f' value="{value}"' if value else ""
    return f'<input name="{name}"{req}{val} placeholder="{placeholder}" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">'

def _ent_submit_btn(text, color="accent"):
    c = {"accent": "var(--accent)", "green": "var(--green)", "yellow": "var(--yellow)", "accent2": "var(--accent2)"}
    return f'<button type="submit" style="background:{c.get(color, color)};border:none;border-radius:8px;padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">{text}</button>'

# ==============================
#    企 业 注 册
# ==============================

@app.get("/enterprise/register", response_class=HTMLResponse)
async def ent_register_form(request: Request):
    content = f"""{_ent_header("🏢 企业注册", "已有账号？去登录 →", "/enterprise/login")}
    <div class="card">
    <form action="/enterprise/register" method="post" style="display:flex;flex-direction:column;gap:10px;">
        {_ent_input("company_name", "企业/公司全称 *", True)}
        {_ent_input("contact_name", "联系人姓名 *", True)}
        {_ent_input("contact_phone", "联系电话 *", True, "tel")}
        {_ent_input("password", "设置密码（至少6位）*", True, "password")}
        {_ent_input("license_no", "营业执照号（选填）")}
        {_ent_submit_btn("✅ 注册企业账号", "accent")}
    </form>
    </div>
    <div class="card" style="background:var(--card2);">
        <div style="font-size:12px;color:var(--text2);line-height:1.8;">
            <b>📌 注册说明</b><br>
            · 注册后即可免费发布招聘岗位<br>
            · 所有岗位需管理员审核后上架<br>
            · 每个企业可管理自己发布的岗位
        </div>
    </div>"""
    return make_page("企业注册 - 武鸣招聘", content, "recruit")

@app.post("/enterprise/register", response_class=HTMLResponse)
async def ent_register_submit(
    company_name: str = Form(...), contact_name: str = Form(...),
    contact_phone: str = Form(...), password: str = Form(...),
    license_no: str = Form("")):
    conn = get_recruit_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ph = make_ent_password(password)
    try:
        conn.execute("INSERT INTO enterprises (company_name, contact_name, contact_phone, password_hash, license_no, status, created_at) VALUES (?,?,?,?,?,'pending',?)",
                     (company_name, contact_name, contact_phone, ph, license_no, now))
        conn.commit()
        conn.close()
        return HTMLResponse("""
        <div class='header'><h1>✅ 注册成功</h1></div>
        <div class="card" style="text-align:center;">
            <div style="font-size:48px;margin-bottom:12px;">🎉</div>
            <div style="font-size:16px;font-weight:600;color:var(--green);margin-bottom:8px;">企业账号注册成功！</div>
            <div style="font-size:13px;color:var(--text2);margin-bottom:16px;">请等待管理员审核通过后即可发布岗位</div>
            <a href="/enterprise/login" class="btn">去登录</a>
        </div>
        """)
    except Exception as e:
        if "UNIQUE" in str(e):
            return make_page("注册失败", "<div class='header'><h1>⚠️ 注册失败</h1></div><div class='card' style='text-align:center;'><p style='color:var(--red);'>该公司名称已被注册</p><a href='/enterprise/register' class='btn'>重新填写</a></div>", "recruit")
        return make_page("注册失败", f"<div class='header'><h1>⚠️ 注册失败</h1></div><div class='card'><p style='color:var(--red);'>{str(e)}</p><a href='/enterprise/register' class='btn'>重新填写</a></div>", "recruit")

# ==============================
#    企 业 登 录
# ==============================

@app.get("/enterprise/login", response_class=HTMLResponse)
async def ent_login_form(request: Request):
    ent = check_enterprise(request)
    if ent:
        return RedirectResponse(url="/enterprise/dashboard")
    content = f"""{_ent_header("🏢 企业登录", "没有账号？去注册 →", "/enterprise/register")}
    <div class="card">
    <form action="/enterprise/login" method="post" style="display:flex;flex-direction:column;gap:10px;">
        {_ent_input("company_name", "企业名称 *", True)}
        {_ent_input("password", "密码 *", True, "password")}
        {_ent_submit_btn("🔑 登录", "accent")}
    </form>
    </div>
    <div style="font-size:11px;color:var(--text2);text-align:center;margin-top:12px;">
        <a href="/enterprise/register" style="color:var(--accent2);">还没有企业账号？立即注册 →</a>
    </div>"""
    return make_page("企业登录 - 武鸣招聘", content, "recruit")

@app.post("/enterprise/login", response_class=HTMLResponse)
async def ent_login_submit(request: Request, company_name: str = Form(...), password: str = Form(...)):
    conn = get_recruit_db()
    ent = conn.execute("SELECT * FROM enterprises WHERE company_name=?", (company_name,)).fetchone()
    conn.close()
    if not ent:
        return make_page("登录失败", "<div class='header'><h1>⚠️ 登录失败</h1></div><div class='card' style='text-align:center;'><p style='color:var(--red);'>企业名称或密码错误</p><a href='/enterprise/login' class='btn'>重新登录</a></div>", "recruit")
    if ent["password_hash"] != make_ent_password(password):
        return make_page("登录失败", "<div class='header'><h1>⚠️ 登录失败</h1></div><div class='card' style='text-align:center;'><p style='color:var(--red);'>企业名称或密码错误</p><a href='/enterprise/login' class='btn'>重新登录</a></div>", "recruit")
    if ent["status"] == "pending":
        return make_page("审核中", "<div class='header'><h1>⏳ 账号审核中</h1></div><div class='card' style='text-align:center;'><p style='color:var(--text2);'>您的企业账号正在等待管理员审核，请稍后再试</p><a href='/' class='btn'>返回首页</a></div>", "recruit")
    if ent["status"] == "blocked":
        return make_page("账号已禁用", "<div class='header'><h1>🚫 账号已禁用</h1></div><div class='card' style='text-align:center;'><p style='color:var(--red);'>请联系管理员</p><a href='/' class='btn'>返回首页</a></div>", "recruit")
    token = make_ent_token(ent["id"])
    conn = get_recruit_db()
    conn.execute("UPDATE enterprises SET last_login=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ent["id"]))
    conn.commit()
    conn.close()
    resp = RedirectResponse(url="/enterprise/dashboard")
    resp.set_cookie(key="ent_session", value=token, max_age=72*3600, httponly=True)
    resp.delete_cookie("user_session", path="/")
    resp.delete_cookie("session", path="/")
    return resp

@app.get("/enterprise/logout", response_class=HTMLResponse)
async def ent_logout(request: Request):
    resp = RedirectResponse(url="/")
    resp.delete_cookie("ent_session")
    return resp

# ==============================
#    企 业 控 制 台
# ==============================

@app.get("/enterprise/dashboard", response_class=HTMLResponse)
async def ent_dashboard(request: Request):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    my_jobs = conn.execute("SELECT * FROM jobs WHERE company=? AND status='active' ORDER BY created_at DESC", (ent["company_name"],)).fetchall()
    pending_jobs = conn.execute("SELECT * FROM jobs WHERE company=? AND status='pending' ORDER BY created_at DESC", (ent["company_name"],)).fetchall()
    total_resumes = conn.execute("SELECT COUNT(*) FROM resumes WHERE is_active=1").fetchone()[0]
    conn.close()
    jobs_html = ""
    for j in my_jobs:
        s_min = j['salary_min'] if j['salary_min'] else 0
        s_max = j['salary_max'] if j['salary_max'] else 0
        if s_min == 0 and s_max == 0:
            salary = '<span style="color:var(--orange);">面议</span>'
        elif s_max:
            salary = f"{s_min}-{s_max}{j['salary_unit']}"
        else:
            salary = f"{s_min}{j['salary_unit']}"
        ta = time_ago(j["created_at"])
        jobs_html += f"""
        <div class="job-card" style="border-left:3px solid var(--accent);">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div class="job-title">{j['title']}</div>
                <span style="font-size:10px;color:var(--text2);">{ta}</span>
            </div>
            <div class="job-meta">{j['location'] or ''} | {j['job_type']} | {j['category']}</div>
            <div class="job-salary">{salary}</div>
            <div class="job-footer" style="justify-content:space-between;">
                <div><span class="source">{j['source']}</span></div>
                <div>
                    <a href="/enterprise/job/edit/{j['id']}" class="btn-sm" style="color:var(--yellow);">✏️ 编辑</a>
                    <a href="/enterprise/job/delete/{j['id']}" onclick="return confirm('确定下架 {j['title']}?')" class="btn-sm" style="color:var(--red);">🗑 下架</a>
                </div>
            </div>
        </div>"""
    content = f"""
    <div class="header">
        <h1>🏢 {ent['company_name']}</h1>
        <div class="time"><a href="/enterprise/logout" style="color:var(--text2);font-size:11px;">退出</a></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:12px;">
        <div class="stat-card"><div class="stat-num">{len(my_jobs)}</div><div class="stat-label">已上架</div></div>
        <div class="stat-card"><div class="stat-num" style="color:var(--yellow);">{len(pending_jobs)}</div><div class="stat-label">待审核</div></div>
        <div class="stat-card"><div class="stat-num">{total_resumes}</div><div class="stat-label">简历库</div></div>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
        <a href="/enterprise/job/add" class="btn" style="background:var(--green);">➕ 发布新岗位</a>
        <a href="/resumes" class="btn" style="background:var(--accent2);">👥 浏览简历</a>
    </div>
    <div class="card">
        <div class="card-title">📋 我发布的岗位</div>
        <div>{jobs_html or '<p style="color:var(--text2);text-align:center;padding:20px;">还没有发布岗位，点击上方按钮发布</p>'}</div>
    </div>"""
    return make_page("企业控制台 - 武鸣招聘", content, "recruit")

# ==============================
#    企 业 发 布 岗 位
# ==============================

@app.get("/enterprise/job/add", response_class=HTMLResponse)
async def ent_job_add_form(request: Request):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    content = f"""{_ent_header("➕ 发布新岗位", "← 返回控制台", "/enterprise/dashboard")}
    <form action="/enterprise/job/add" method="post" style="display:flex;flex-direction:column;gap:8px;">
        {_ent_input("title", "岗位名称 *", True)}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            {_ent_input("location", "工作地点 *", True)}
            {_ent_input("category", "分类（食品加工/餐饮/物流/其他）")}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
            {_ent_input("salary_min", "最低薪资", False, "number")}
            {_ent_input("salary_max", "最高薪资", False, "number")}
            <select name="job_type" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
                <option value="全职">全职</option><option value="兼职">兼职</option>
                <option value="小时工">小时工</option><option value="日结">日结</option>
                <option value="临时工">临时工</option>
            </select>
        </div>
        <textarea name="description" rows="4" placeholder="岗位要求、职责描述、福利待遇等" required
                  style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;font-size:14px;"></textarea>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            {_ent_input("contact_phone", "联系电话 *", True)}
            {_ent_input("contact_name", "联系人姓名", False, "text", ent['contact_name'])}
        </div>
        {_ent_input("tags", "标签（逗号分隔，如 五险一金,包吃,夜班）")}
        <div style="font-size:11px;color:var(--text2);margin-top:4px;">
            ⏳ 发布后需管理员审核，审核通过后即展示在首页
        </div>
        {_ent_submit_btn("✅ 提交审核", "green")}
    </form>"""
    return make_page("发布岗位 - 武鸣招聘", content, "recruit")

@app.post("/enterprise/job/add", response_class=HTMLResponse)
async def ent_job_add_submit(request: Request,
    title: str = Form(...), location: str = Form(""), category: str = Form("其他"),
    salary_min: int = Form(0), salary_max: int = Form(0), 
    job_type: str = Form("全职"), description: str = Form(""),
    contact_phone: str = Form(""), contact_name: str = Form(""), tags: str = Form("")):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""INSERT INTO jobs (title, company, location, salary_min, salary_max, salary_unit,
                   job_type, category, description, contact_name, contact_phone, tags, source, status, created_at)
                   VALUES (?,?,?,?,?,'元/月',?,?,?,?,?,?,'企业发布','pending',?)""",
                 (title, ent["company_name"], location, salary_min, salary_max,
                  job_type, category, description, contact_name, contact_phone, tags, now_dt))
    conn.commit()
    conn.close()
    return HTMLResponse(f"""
    <div class="header"><h1>✅ 提交成功</h1></div>
    <div class="card" style="text-align:center;">
        <div style="font-size:48px;margin-bottom:12px;">📨</div>
        <div style="font-size:16px;font-weight:600;color:var(--green);margin-bottom:8px;">岗位已提交审核</div>
        <div style="font-size:13px;color:var(--text2);margin-bottom:16px;">管理员审核通过后将在首页展示</div>
        <a href="/enterprise/dashboard" class="btn">返回控制台</a>
    </div>""")

# ==============================
#    企 业 编 辑 / 下 架 岗 位
# ==============================

@app.get("/enterprise/job/edit/{job_id}", response_class=HTMLResponse)
async def ent_job_edit_form(request: Request, job_id: int):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    j = conn.execute("SELECT * FROM jobs WHERE id=? AND company=?", (job_id, ent["company_name"])).fetchone()
    conn.close()
    if not j:
        return HTMLResponse("<h2>岗位不存在或无权操作</h2>")
    
    job_type_options = ""
    for opt in ["全职", "兼职", "小时工", "日结", "临时工"]:
        sel = "selected" if j["job_type"] == opt else ""
        job_type_options += f"<option {sel}>{opt}</option>"
    
    content = f"""{_ent_header("✏️ 编辑岗位", "← 返回控制台", "/enterprise/dashboard")}
    <form action="/enterprise/job/edit/{job_id}" method="post" style="display:flex;flex-direction:column;gap:8px;">
        {_ent_input("title", "岗位名称 *", True, "text", j['title'])}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            {_ent_input("location", "工作地点", False, "text", j['location'] or '')}
            {_ent_input("category", "分类", False, "text", j['category'] or '其他')}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
            {_ent_input("salary_min", "最低薪资", False, "number", str(j['salary_min'] or 0))}
            {_ent_input("salary_max", "最高薪资", False, "number", str(j['salary_max'] or 0))}
            <select name="job_type" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">{job_type_options}</select>
        </div>
        <textarea name="description" rows="4" placeholder="岗位描述"
                  style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;">{j['description'] or ''}</textarea>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            {_ent_input("contact_phone", "联系电话", False, "text", j['contact_phone'] or '')}
            {_ent_input("contact_name", "联系人", False, "text", j['contact_name'] or ent['contact_name'])}
        </div>
        {_ent_input("tags", "标签", False, "text", j['tags'] or '')}
        {_ent_submit_btn("💾 保存修改", "yellow")}
    </form>"""
    return make_page("编辑岗位 - 武鸣招聘", content, "recruit")

@app.post("/enterprise/job/edit/{job_id}", response_class=HTMLResponse)
async def ent_job_edit_submit(request: Request, job_id: int,
    title: str = Form(...), location: str = Form(""), category: str = Form("其他"),
    salary_min: int = Form(0), salary_max: int = Form(0), 
    job_type: str = Form("全职"), description: str = Form(""),
    contact_phone: str = Form(""), contact_name: str = Form(""), tags: str = Form("")):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""UPDATE jobs SET title=?, location=?, salary_min=?, salary_max=?,
                   job_type=?, category=?, description=?, contact_name=?, contact_phone=?, tags=?, updated_at=?
                   WHERE id=? AND company=?""",
                 (title, location, salary_min, salary_max, job_type, category, description, contact_name, contact_phone, tags, now_dt, job_id, ent["company_name"]))
    conn.commit()
    conn.close()
    return make_page("修改成功", f"""
    <div class="header"><h1>✅ 修改成功</h1></div>
    <div style="text-align:center;margin:16px;">
        <a href="/enterprise/dashboard" class="btn">返回控制台</a>
        <a href="/job/{job_id}" class="btn" style="background:var(--accent2);">查看岗位</a>
    </div>""", "recruit")

@app.get("/enterprise/job/delete/{job_id}")
async def ent_job_delete(request: Request, job_id: int):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    conn.execute("UPDATE jobs SET status='deleted' WHERE id=? AND company=?", (job_id, ent["company_name"]))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/enterprise/dashboard")

# ==============================
#      简 历 功 能
# ==============================

def _resume_form(name_val, age_val, gender_val, edu_val, phone_val, wechat_val,
                 exp_job_val, exp_sal_val, exp_val, skills_val, self_desc_val, action_url):
    gender_options = ""
    for g in ["", "男", "女"]:
        sel = "selected" if gender_val == g else ""
        gender_options += f"<option {sel} value='{g}'>{g if g else '性别'}</option>"
    edu_options = ""
    for e in ["", "初中", "高中/中专", "大专", "本科", "本科以上"]:
        sel = "selected" if edu_val == e else ""
        edu_options += f"<option {sel} value='{e}'>{e if e else '学历'}</option>"
    return f"""
    <form action="{action_url}" method="post" style="display:flex;flex-direction:column;gap:8px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            {_ent_input("name", "姓名 *", True, "text", name_val)}
            {_ent_input("age", "年龄", False, "number", str(age_val) if age_val else "")}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <select name="gender" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">{gender_options}</select>
            <select name="edu_level" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">{edu_options}</select>
        </div>
        {_ent_input("phone", "手机号 *", True, "text", phone_val)}
        {_ent_input("wechat", "微信号", False, "text", wechat_val)}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            {_ent_input("expected_job", "期望岗位", False, "text", exp_job_val)}
            {_ent_input("expected_salary", "期望薪资（如：3000-5000）", False, "text", exp_sal_val)}
        </div>
        <textarea name="experience" rows="3" placeholder="工作经历（如：曾在XX工厂做普工2年）"
                  style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;font-size:14px;">{exp_val or ''}</textarea>
        <textarea name="skills" rows="2" placeholder="技能特长（如：会开叉车、有电工证）"
                  style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;font-size:14px;">{skills_val or ''}</textarea>
        <textarea name="self_desc" rows="2" placeholder="自我介绍"
                  style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;font-size:14px;">{self_desc_val or ''}</textarea>
        {_ent_submit_btn("✅ 保存简历", "accent2")}
    </form>"""

@app.get("/resume/add", response_class=HTMLResponse)
async def resume_add_form(request: Request):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    user_info = get_user_info(uid)
    conn = get_recruit_db()
    existing = conn.execute("SELECT * FROM resumes WHERE user_id=? AND is_active=1", (uid,)).fetchone()
    conn.close()
    if existing:
        return RedirectResponse(url="/resume/my")
    form = _resume_form(user_info["nickname"] if user_info else "", 0, "", "", 
                        user_info["phone"] if user_info else "", "", "", "", "", "", "", "/resume/add")
    content = f"""{_ent_header("📄 我的简历", "", "")}
    <div style="margin-bottom:8px;font-size:13px;color:var(--text2);">填写信息让企业找到你</div>
    <div class="card">{form}</div>
    <div style="font-size:11px;color:var(--text2);margin-top:8px;padding:8px;background:var(--card2);border-radius:6px;">
        📌 简历将展示给已认证的企业用户，帮助他们找到你
    </div>"""
    return make_page("上传简历 - 武鸣招聘", content, "recruit", user={"nickname": user_info["nickname"]})

@app.post("/resume/add", response_class=HTMLResponse)
async def resume_add_submit(request: Request,
    name: str = Form(...), age: int = Form(0), gender: str = Form(""),
    edu_level: str = Form(""), phone: str = Form(...), wechat: str = Form(""),
    expected_job: str = Form(""), expected_salary: str = Form(""),
    experience: str = Form(""), skills: str = Form(""), self_desc: str = Form("")):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    conn = get_recruit_db()
    existing = conn.execute("SELECT id FROM resumes WHERE user_id=? AND is_active=1", (uid,)).fetchone()
    if existing:
        conn.close()
        return make_page("已有简历", """
        <div class="header"><h1>⚠️ 已有简历</h1></div>
        <div style="text-align:center;margin:16px;">
            <p style="color:var(--text2);">你已经有一份简历了，可以编辑它</p>
            <a href="/resume/my" class="btn">查看我的简历</a>
        </div>""", "recruit")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""INSERT INTO resumes (user_id,name,gender,age,phone,wechat,edu_level,experience,
                   expected_job,expected_salary,skills,self_desc,is_active,is_pinned,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,0,?,?)""",
                 (uid, name, gender, age, phone, wechat, edu_level, experience,
                  expected_job, expected_salary, skills, self_desc, now, now))
    conn.commit()
    conn.close()
    return make_page("简历已保存", """
    <div class="header"><h1>✅ 简历已保存</h1></div>
    <div class="card" style="text-align:center;">
        <div style="font-size:48px;margin-bottom:12px;">📄</div>
        <div style="font-size:16px;font-weight:600;color:var(--green);margin-bottom:8px;">简历创建成功！</div>
        <div style="font-size:13px;color:var(--text2);margin-bottom:16px;">企业用户可以在简历库中看到你的信息</div>
        <a href="/resume/my" class="btn">查看我的简历</a>
        <a href="/" class="btn" style="background:var(--accent2);">返回首页</a>
    </div>""", "recruit")

@app.get("/resume/my", response_class=HTMLResponse)
async def resume_my(request: Request):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    user_info = get_user_info(uid)
    conn = get_recruit_db()
    r = conn.execute("SELECT * FROM resumes WHERE user_id=? AND is_active=1", (uid,)).fetchone()
    conn.close()
    if not r:
        content = f"""{_ent_header("📄 我的简历", "", "")}
        <div class="card" style="text-align:center;">
            <div style="font-size:48px;margin-bottom:12px;">📄</div>
            <p style="color:var(--text2);margin-bottom:16px;">还没有创建简历，创建后企业就能找到你</p>
            <a href="/resume/add" class="btn" style="background:var(--accent2);">➕ 创建简历</a>
        </div>"""
        return make_page("我的简历 - 武鸣招聘", content, "recruit", user={"nickname": user_info["nickname"]})
    
    gender_age = ""
    if r["gender"] or r["age"]:
        parts = []
        if r["gender"]: parts.append(r["gender"])
        if r["age"]: parts.append(str(r["age"]) + "岁")
        gender_age = " · ".join(parts) + " · "
    
    details = ""
    details += f'<div style="font-size:13px;margin-bottom:6px;"><b>📞 联系方式</b>：{r["phone"]}'
    if r["wechat"]:
        details += f' / {r["wechat"]}'
    details += "</div>"
    for label, key, icon in [("🎯 期望岗位", "expected_job", "🎯"), ("💰 期望薪资", "expected_salary", "💰"), 
                               ("💼 工作经历", "experience", "💼"), ("🔧 技能特长", "skills", "🔧"),
                               ("📝 自我介绍", "self_desc", "📝")]:
        if r[key]:
            details += f'<div style="font-size:13px;margin-bottom:6px;"><b>{icon} {label}</b>：{r[key]}</div>'
    
    content = f"""{_ent_header("📄 我的简历", "✏️ 编辑", f"/resume/edit/{r['id']}")}
    <div class="card">
        <div style="font-size:20px;font-weight:700;color:var(--text);">{r["name"]}</div>
        <div style="font-size:13px;color:var(--text2);margin-top:4px;">{gender_age}{r["edu_level"] or "学历未填"}</div>
        <div style="border-top:1px solid var(--border);padding-top:10px;margin-top:10px;">{details}</div>
        <div style="font-size:11px;color:var(--text2);margin-top:10px;padding-top:8px;border-top:1px solid var(--border);">
            创建时间：{r["created_at"][:16]} | 更新：{r["updated_at"][:16]}
        </div>
    </div>"""
    return make_page("我的简历 - 武鸣招聘", content, "recruit", user={"nickname": user_info["nickname"]})

@app.get("/resume/edit/{resume_id}", response_class=HTMLResponse)
async def resume_edit_form(request: Request, resume_id: int):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    user_info = get_user_info(uid)
    conn = get_recruit_db()
    r = conn.execute("SELECT * FROM resumes WHERE id=? AND user_id=? AND is_active=1", (resume_id, uid)).fetchone()
    conn.close()
    if not r:
        return HTMLResponse("<h2>简历不存在</h2>")
    form = _resume_form(r["name"], r["age"] or 0, r["gender"] or "", r["edu_level"] or "",
                        r["phone"], r["wechat"] or "", r["expected_job"] or "", r["expected_salary"] or "",
                        r["experience"] or "", r["skills"] or "", r["self_desc"] or "", f"/resume/edit/{resume_id}")
    content = f"""{_ent_header("✏️ 编辑简历", "← 返回", "/resume/my")}
    <div class="card">{form}</div>"""
    return make_page("编辑简历 - 武鸣招聘", content, "recruit", user={"nickname": user_info["nickname"]})

@app.post("/resume/edit/{resume_id}", response_class=HTMLResponse)
async def resume_edit_submit(request: Request, resume_id: int,
    name: str = Form(...), age: int = Form(0), gender: str = Form(""),
    edu_level: str = Form(""), phone: str = Form(...), wechat: str = Form(""),
    expected_job: str = Form(""), expected_salary: str = Form(""),
    experience: str = Form(""), skills: str = Form(""), self_desc: str = Form("")):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_recruit_db()
    conn.execute("""UPDATE resumes SET name=?, gender=?, age=?, phone=?, wechat=?,
                   edu_level=?, experience=?, expected_job=?, expected_salary=?,
                   skills=?, self_desc=?, updated_at=? WHERE id=? AND user_id=?""",
                 (name, gender, age, phone, wechat, edu_level, experience,
                  expected_job, expected_salary, skills, self_desc, now, resume_id, uid))
    conn.commit()
    conn.close()
    return make_page("修改成功", """
    <div class="header"><h1>✅ 修改成功</h1></div>
    <div style="text-align:center;margin:16px;">
        <a href="/resume/my" class="btn">查看简历</a>
        <a href="/" class="btn" style="background:var(--accent2);">返回首页</a>
    </div>""", "recruit")

# ==============================
#  简历列表（企业可见）
# ==============================

@app.get("/resumes", response_class=HTMLResponse)
async def resume_list(request: Request, q: str = ""):
    """简历库 - 仅企业可访问"""
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
        return RedirectResponse(url="/resume/my")
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    where = "WHERE r.is_active=1"
    where = "WHERE r.is_active=1"
    params = []
    if q:
        where += " AND (r.name LIKE ? OR r.expected_job LIKE ? OR r.skills LIKE ? OR r.experience LIKE ?)"
        qp = f"%{q}%"
        params.extend([qp, qp, qp, qp])
    resumes = conn.execute(f"SELECT r.* FROM resumes r {where} ORDER BY r.is_pinned DESC, r.updated_at DESC LIMIT 50", params).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM resumes WHERE is_active=1").fetchone()[0]
    conn.close()
    resumes_html = ""
    for r in resumes:
        name_display = r["name"]
        if r["gender"] or r["age"]:
            extras = []
            if r["gender"]: extras.append(r["gender"])
            if r["age"]: extras.append(str(r["age"]) + "岁")
            name_display += " <span style='font-size:11px;color:var(--text2);'>· " + " · ".join(extras) + "</span>"
        pinned_tag = '<span class="tag" style="background:var(--yellow);color:#000;">📌 置顶</span>' if r["is_pinned"] else ""
        meta_parts = []
        if r["expected_job"]: meta_parts.append("🎯 " + r["expected_job"])
        if r["expected_salary"]: meta_parts.append("💰 " + r["expected_salary"])
        if r["edu_level"]: meta_parts.append("🎓 " + r["edu_level"])
        meta_str = " | ".join(meta_parts)
        exp_text = ""
        if r["experience"]:
            exp_short = r["experience"][:80]
            if len(r["experience"]) > 80: exp_short += "..."
            exp_text = f'<div class="job-desc">💼 {exp_short}</div>'
        skills_text = ""
        if r["skills"]:
            skills_text = f'<div class="job-footer">🔧 {r["skills"][:60]}</div>'
        resumes_html += f"""
        <a href="/resume/{r['id']}" style="text-decoration:none;color:inherit;display:block;">
        <div class="job-card" style="border-left:3px solid {'var(--yellow)' if r['is_pinned'] else 'var(--accent2)'};">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div class="job-title">{name_display}</div>
                {pinned_tag}
            </div>
            <div class="job-meta">{meta_str}</div>
            {exp_text}
            {skills_text}
            <div style="font-size:10px;color:var(--text2);margin-top:4px;">更新于 {time_ago(r['updated_at'])}</div>
        </div>
        </a>"""
    content = f"""
    <div class="header">
        <h1>👥 简历库</h1>
        <div class="time">共{total}份简历 | <a href="/enterprise/dashboard" style="color:var(--text2);font-size:11px;">← 控制台</a></div>
    </div>
    <form action="/resumes" method="get" style="display:flex;gap:6px;margin-bottom:12px;">
        <input type="text" name="q" value="{q}" placeholder="搜索姓名、期望岗位、技能..."
               style="flex:1;background:var(--card2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text);font-size:14px;">
        <button type="submit" style="background:var(--accent);border:none;border-radius:8px;padding:10px 16px;color:white;font-size:14px;">搜索</button>
    </form>
    <div>{resumes_html or '<p style="color:var(--text2);text-align:center;padding:30px 0;">暂无简历</p>'}</div>"""
    return make_page("简历库 - 武鸣招聘", content, "recruit")

# ==============================
#  简历详情（企业可见）
# ==============================

@app.get("/resume/{resume_id}", response_class=HTMLResponse)
async def resume_detail(request: Request, resume_id: int):
    ent = check_enterprise(request)
    uid = check_user(request)
    if not ent and not uid:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    r = conn.execute("SELECT * FROM resumes WHERE id=? AND is_active=1", (resume_id,)).fetchone()
    conn.close()
    if not r:
        return HTMLResponse("<h2>简历不存在</h2>")
    if uid and r["user_id"] != uid:
        return HTMLResponse("<h2>无权查看</h2>")
    
    gender_age = ""
    if r["gender"] or r["age"]:
        parts = []
        if r["gender"]: parts.append(r["gender"])
        if r["age"]: parts.append(str(r["age"]) + "岁")
        gender_age = " · ".join(parts) + " · "
    
    details = f'<div style="font-size:14px;margin-bottom:10px;"><b>📞 联系方式</b><br><span style="color:var(--green);font-size:18px;">{r["phone"]}</span>'
    if r["wechat"]:
        details += f" / {r['wechat']}"
    details += "</div>"
    
    for label, key, icon in [("🎯 期望岗位", "expected_job", "🎯"), ("💰 期望薪资", "expected_salary", "💰"),
                               ("💼 工作经历", "experience", "💼"), ("🔧 技能特长", "skills", "🔧"),
                               ("📝 自我介绍", "self_desc", "📝")]:
        if r[key]:
            details += f'<div style="font-size:14px;margin-bottom:10px;"><b>{label}</b><br>{r[key]}</div>'
    
    content = f"""{_ent_header("📄 简历详情", "← 返回简历库", "/resumes")}
    <div class="card">
        <div style="font-size:22px;font-weight:700;color:var(--text);">{r["name"]}</div>
        <div style="font-size:14px;color:var(--text2);margin-top:4px;">{gender_age}{r["edu_level"] or "学历未填"}</div>
        <div style="border-top:1px solid var(--border);padding-top:12px;margin-top:10px;">{details}</div>
        <div style="font-size:11px;color:var(--text2);margin-top:10px;padding-top:8px;border-top:1px solid var(--border);">
            更新于 {r["updated_at"][:16]}
        </div>
    </div>"""
    return make_page(r["name"] + "的简历 - 武鸣招聘", content, "recruit")

# ==============================
#  后台管理 - 企业/简历
# ==============================

@app.get("/admin/enterprises", response_class=HTMLResponse)
async def admin_enterprises(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    ents = conn.execute("SELECT * FROM enterprises ORDER BY created_at DESC").fetchall()
    pending = conn.execute("SELECT COUNT(*) FROM enterprises WHERE status='pending'").fetchone()[0]
    conn.close()
    rows = ""
    for e in ents:
        status_map = {"active": "✅", "pending": "⏳", "blocked": "🚫"}
        rows += f"""
        <div class="job-card" style="border-left:3px solid {'var(--yellow)' if e['status']=='pending' else 'var(--green)'};">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div class="job-title">{e['company_name']}</div>
                <div style="font-size:11px;color:var(--text2);">{status_map.get(e['status'], '❓')} {e['status']}</div>
            </div>
            <div class="job-meta">📞 {e['contact_name']} {e['contact_phone']} | 📅 {e['created_at'][:10]}</div>
            <div class="job-footer" style="justify-content:flex-end;">
                <a href="/admin/enterprise/approve/{e['id']}" class="btn-sm" style="color:var(--green);" onclick="return confirm('通过 {e['company_name']} 的审核？')">✅ 通过</a>
                <a href="/admin/enterprise/block/{e['id']}" class="btn-sm" style="color:var(--red);" onclick="return confirm('禁用 {e['company_name']}？')">🚫 禁用</a>
            </div>
        </div>"""
    content = f"""
    <div class="header"><h1>🏢 企业管理</h1><div class="time"><a href="/admin" style="color:var(--text2);font-size:11px;">← 返回后台</a></div></div>
    <div style="display:flex;gap:8px;margin-bottom:12px;">
        <div class="stat-card"><div class="stat-num">{len(ents)}</div><div class="stat-label">全部企业</div></div>
        <div class="stat-card"><div class="stat-num" style="color:var(--yellow);">{pending}</div><div class="stat-label">待审核</div></div>
    </div>
    <div>{rows or '<p style="color:var(--text2);text-align:center;padding:20px;">暂无企业注册</p>'}</div>"""
    return make_page("企业管理 - 武鸣招聘", content, "recruit")

@app.get("/admin/enterprise/approve/{ent_id}")
async def admin_enterprise_approve(ent_id: int):
    conn = get_recruit_db()
    conn.execute("UPDATE enterprises SET status='active' WHERE id=?", (ent_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/enterprises")

@app.get("/admin/enterprise/block/{ent_id}")
async def admin_enterprise_block(ent_id: int):
    conn = get_recruit_db()
    conn.execute("UPDATE enterprises SET status='blocked' WHERE id=?", (ent_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/enterprises")

@app.get("/admin/resumes", response_class=HTMLResponse)
async def admin_resumes(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    resumes = conn.execute("SELECT * FROM resumes WHERE is_active=1 ORDER BY created_at DESC").fetchall()
    total = len(resumes)
    conn.close()
    rows = ""
    for r in resumes:
        rows += f"""
        <div class="job-card">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div class="job-title">{r['name']} <span style="font-size:11px;color:var(--text2);">· {r.get('gender','') or ''} {r.get('age',0) or ''}岁</span></div>
                {'<span class="tag" style="background:var(--yellow);color:#000;">📌 置顶</span>' if r['is_pinned'] else ''}
            </div>
            <div class="job-meta">🎯 {r['expected_job'] or '未填'} | 💰 {r['expected_salary'] or '未填'} | 🎓 {r['edu_level'] or '未填'}</div>
            <div class="job-desc">{r['experience'][:60] if r['experience'] else ''}</div>
            <div class="job-footer" style="justify-content:flex-end;">
                <a href="/resume/{r['id']}" class="btn-sm">👁 查看</a>
            </div>
        </div>"""
    content = f"""
    <div class="header"><h1>📄 简历管理</h1><div class="time"><a href="/admin" style="color:var(--text2);font-size:11px;">← 返回后台</a></div></div>
    <div style="display:flex;gap:8px;margin-bottom:12px;">
        <div class="stat-card"><div class="stat-num">{total}</div><div class="stat-label">简历总数</div></div>
    </div>
    <div>{rows or '<p style="color:var(--text2);text-align:center;padding:20px;">暂无简历</p>'}</div>"""
    return make_page("简历管理 - 武鸣招聘", content, "recruit")


# ==============================
#    简 历 引 导 页
# ==============================



# ==============================
#    统一用户入口
# ==============================

@app.get("/my")
async def my_redirect(request: Request):
    """统一用户入口 - 根据登录状态跳转"""
    uid = check_user(request)
    ent = check_enterprise(request)
    if uid:
        return RedirectResponse(url="/resume/my")
    if ent:
        return RedirectResponse(url="/enterprise/dashboard")
    return RedirectResponse(url="/account")

@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    """统一登录页 - tab切换身份"""
    # 已登录直接跳转
    if check_auth(request):
        return RedirectResponse(url="/admin")
    uid = check_user(request)
    if uid:
        return RedirectResponse(url="/resume/my")
    ent = check_enterprise(request)
    if ent:
        return RedirectResponse(url="/enterprise/dashboard")
    
    content = """<!DOCTYPE html><html lang='zh-CN'><head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no'>
<title>登录 - 武鸣招聘</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,'PingFang SC',sans-serif; background:#0f0f1a; color:#e8e8f0; min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:20px; }
.logo { text-align:center; margin-bottom:24px; }
.logo h1 { font-size:24px; background:linear-gradient(135deg,#6c5ce7,#a29bfe); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.logo p { font-size:12px; color:#9999b0; margin-top:4px; }
.tabs { display:flex; gap:0; background:#1a1a2e; border-radius:10px; padding:4px; margin-bottom:20px; width:100%; max-width:360px; }
.tab { flex:1; text-align:center; padding:10px; border-radius:8px; cursor:pointer; font-size:14px; color:#9999b0; transition:all 0.2s; border:none; background:none; }
.tab.active { background:#6c5ce7; color:white; font-weight:600; }
.tab:hover:not(.active) { color:#a29bfe; }
.form-card { background:#1a1a2e; border:1px solid #2d2d4a; border-radius:12px; padding:20px; width:100%; max-width:360px; }
.form { display:none; flex-direction:column; gap:10px; }
.form.active { display:flex; }
.form input { background:#222240; border:1px solid #2d2d4a; border-radius:8px; padding:12px 14px; color:#e8e8f0; font-size:14px; outline:none; }
.form input:focus { border-color:#6c5ce7; }
.form button { background:linear-gradient(135deg,#6c5ce7,#a29bfe); border:none; border-radius:8px; padding:12px; color:white; font-size:15px; font-weight:600; cursor:pointer; }
.form .link-row { font-size:12px; color:#9999b0; text-align:center; margin-top:4px; }
.form .link-row a { color:#a29bfe; text-decoration:none; }
.admin-link { margin-top:16px; font-size:11px; color:#555; text-align:center; }
.admin-link a { color:#666; text-decoration:none; }
.msg { display:none; font-size:12px; color:#e17055; text-align:center; padding:6px; border-radius:6px; background:#2d1a1a; margin-bottom:4px; }
.msg.ok { color:#00b894; background:#1a2d1a; }
</style>
</head><body>
<div class="logo"><h1>🏭 武鸣招聘</h1><p>登录后查看联系方式 / 管理岗位</p></div>
<div id="msg" class="msg"></div>
<div class="tabs">
    <button class="tab active" onclick="switchTab('seeker')">🙋 求职者</button>
    <button class="tab" onclick="switchTab('enterprise')">🏢 企业</button>
</div>
<div class="form-card">
    <!-- 求职者登录 -->
    <form id="form-seeker" class="form active" action="/user/login" method="post">
        <input name="phone" type="tel" placeholder="手机号" required pattern="[0-9]{11}" minlength="11" maxlength="11">
        <input name="password" type="password" placeholder="密码" required minlength="6">
        <button type="submit">🔑 求职者登录</button>
        <div class="link-row">没有账号？<a href="/user/register">立即注册</a></div>
    </form>
    <!-- 企业登录 -->
    <form id="form-enterprise" class="form" action="/enterprise/login" method="post">
        <input name="company_name" placeholder="企业名称" required>
        <input name="password" type="password" placeholder="密码" required minlength="6">
        <button type="submit">🔑 企业登录</button>
        <div class="link-row">没有账号？<a href="/enterprise/register">企业注册</a></div>
    </form>
</div>
<div class="admin-link"><a href="/login">⚙ 管理员入口</a></div>
<script>
function switchTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.form').forEach(f => f.classList.remove('active'));
    document.querySelector(`.tab[onclick*="'${name}'"]`).classList.add('active');
    document.getElementById('form-' + name).classList.add('active');
}
// 显示消息（如果有）
var params = new URLSearchParams(window.location.search);
if (params.get('msg')) {
    var m = document.getElementById('msg');
    m.textContent = params.get('msg');
    m.style.display = 'block';
    if (params.get('ok')) m.classList.add('ok');
}
</script>
</body></html>"""
    return HTMLResponse(content)


# ====== 启动 ======
if __name__ == "__main__":
    import uvicorn
    print("\U0001f3ed 武鸣招聘平台启动中...")
    print(f"   公开首页: http://localhost:8080")
    print(f"   管理后台: http://localhost:8080/login")
    print(f"   视频模式: http://localhost:8080/recruit/video")
    uvicorn.run(app, host="0.0.0.0", port=8080)
