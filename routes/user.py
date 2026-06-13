"""
求职者路由 - 注册、登录、找回密码、统一入口
"""
import re
import secrets
from datetime import datetime, timedelta
import bcrypt
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from services.db import get_recruit_db
from services.auth import check_user, get_user_info, set_user_session

router = APIRouter()


@router.get("/user/register", response_class=HTMLResponse)
async def user_register_page():
    from app import make_page
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
            <input name="confirm_password" placeholder="确认密码 *" required type="password" minlength="6"
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
                    padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">✅ 注册</button>
        </form>
        <div style="text-align:center;margin-top:12px;font-size:12px;color:var(--text2);">
            已有账号？<a href="/user/login" style="color:var(--accent2);">去登录</a>
        </div>
    </div>"""
    return HTMLResponse(make_page("注册 - 武鸣招聘", content, "recruit"))


@router.post("/user/register", response_class=HTMLResponse)
async def user_register_submit(
    request: Request, nickname: str = Form(...), phone: str = Form(...),
    wechat: str = Form(""), password: str = Form(...),
    confirm_password: str = Form(...), want_job: str = Form(""),
    experience: str = Form("")
):
    if not re.match(r'^1[3-9]\d{9}$', phone):
        from app import make_page
        return HTMLResponse(make_page("注册失败",
            "<div class='header'><h1>❌ 注册失败</h1></div>"
            "<div class='card' style='text-align:center;'><p style='color:var(--red);'>手机号格式不正确</p>"
            "<a href='/user/register' class='btn' style='margin-top:12px;'>重新注册</a></div>", "recruit"))
    if password != confirm_password:
        from app import make_page
        return HTMLResponse(make_page("注册失败",
            "<div class='header'><h1>❌ 两次密码不一致</h1></div>"
            "<div style='text-align:center;'><a href='/user/register' class='btn'>重新注册</a></div>", "recruit"))
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        conn.execute(
            "INSERT INTO users (nickname, phone, wechat, want_job, experience, password_hash, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (nickname, phone, wechat, want_job, experience, pwd_hash, now_dt)
        )
        conn.commit()
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        token = secrets.token_hex(32)
        expire = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO user_tokens (user_id, token, expire_at, created_at) VALUES (?,?,?,?)",
            (uid, token, expire, now_dt)
        )
        conn.commit()
        conn.close()
        from app import make_page
        resp = HTMLResponse(content=make_page("注册成功",
            "<div class='header'><h1>✅ 注册成功！</h1></div><div style='text-align:center;'><p>正在跳转...</p></div>",
            "recruit"))
        set_user_session(resp, token)
        return resp
    except Exception as e:
        conn.close()
        from app import make_page
        return HTMLResponse(make_page("注册失败",
            "<div class='header'><h1>❌ 注册失败</h1></div>"
            "<div class='card'><p style='color:var(--red);'>手机号可能已被注册</p>"
            "<a href='/user/register' class='btn'>重新注册</a></div>", "recruit"))


@router.get("/user/login", response_class=HTMLResponse)
async def user_login_page():
    from app import make_page
    content = """
    <div class='header'><h1>🔑 求职者登录</h1><div class='time'>登录后可查看岗位联系方式</div></div>
    <div class="card" style="max-width:360px;margin:0 auto;">
        <form action="/user/login" method="post" style="display:flex;flex-direction:column;gap:10px;">
            <input name="phone" placeholder="手机号" required
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <input name="password" placeholder="密码" required type="password"
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <button type="submit" style="background:var(--accent);border:none;border-radius:8px;
                    padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">🔑 登录</button>
        </form>
        <div style="text-align:center;margin-top:12px;font-size:12px;color:var(--text2);">
            没有账号？<a href="/user/register" style="color:var(--accent2);">立即注册</a>
            <br><a href="/user/reset-password" style="color:var(--text2);font-size:11px;">忘记密码？</a>
        </div>
    </div>"""
    return HTMLResponse(make_page("登录 - 武鸣招聘", content, "recruit"))


@router.post("/user/login", response_class=HTMLResponse)
async def user_login_submit(
    request: Request, phone: str = Form(...), password: str = Form(...)
):
    conn = get_recruit_db()
    row = conn.execute(
        "SELECT id, nickname, password_hash FROM users WHERE phone=?", (phone,)
    ).fetchone()
    user = None
    if row:
        stored = row["password_hash"]
        if stored.startswith("$2"):
            if bcrypt.checkpw(password.encode(), stored.encode()):
                user = row
        else:
            if stored == hashlib.sha256(password.encode()).hexdigest():
                user = row
                new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, row["id"]))
                conn.commit()
    if not user:
        conn.close()
        from app import make_page
        return HTMLResponse(make_page("登录失败",
            "<div class='header'><h1>❌ 登录失败</h1></div>"
            "<div class='card'><p style='color:var(--red);'>手机号或密码错误</p>"
            "<a href='/user/login' class='btn'>重新登录</a></div>", "recruit"))
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    token = secrets.token_hex(32)
    expire = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO user_tokens (user_id, token, expire_at, created_at) VALUES (?,?,?,?)",
        (user["id"], token, expire, now_dt)
    )
    conn.execute("UPDATE users SET last_login=? WHERE id=?", (now_dt, user["id"]))
    conn.commit()
    conn.close()
    from app import make_page
    html = f"<div class='header'><h1>✅ 欢迎回来，{user['nickname']}！</h1></div><div style='text-align:center;'><a href='/' class='btn'>返回首页</a></div>"
    resp = HTMLResponse(content=make_page("登录成功", html, "recruit"))
    set_user_session(resp, token)
    return resp


@router.get("/user/logout", response_class=HTMLResponse)
async def user_logout():
    resp = RedirectResponse(url="/")
    resp.delete_cookie("user_session", path="/")
    return resp


@router.get("/user/reset-password", response_class=HTMLResponse)
async def user_reset_password_page():
    from app import make_page
    content = """
    <div class='header'><h1>🔑 重置密码</h1><div class='time'>通过手机号验证身份</div></div>
    <div class="card" style="max-width:360px;margin:0 auto;">
        <form action="/user/reset-password" method="post" style="display:flex;flex-direction:column;gap:10px;">
            <input name="phone" placeholder="注册手机号" required
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <input name="new_password" placeholder="新密码（至少6位）" required type="password" minlength="6"
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <input name="confirm_password" placeholder="确认新密码" required type="password" minlength="6"
                   style="padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);font-size:14px;">
            <button type="submit" style="background:var(--accent);border:none;border-radius:8px;
                    padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">🔄 重置密码</button>
        </form>
        <div style="text-align:center;margin-top:12px;font-size:12px;color:var(--text2);">
            <a href="/user/login" style="color:var(--accent2);">← 返回登录</a>
        </div>
    </div>"""
    return HTMLResponse(make_page("重置密码 - 武鸣招聘", content, "recruit"))


@router.post("/user/reset-password", response_class=HTMLResponse)
async def user_reset_password_submit(
    request: Request, phone: str = Form(...),
    new_password: str = Form(...), confirm_password: str = Form(...)
):
    from app import make_page
    if new_password != confirm_password:
        return HTMLResponse(make_page("重置失败",
            "<div class='header'><h1>❌ 两次密码不一致</h1></div>"
            "<div class='card'><a href='/user/reset-password' class='btn'>重新输入</a></div>", "recruit"))
    if len(new_password) < 6:
        return HTMLResponse(make_page("重置失败",
            "<div class='header'><h1>❌ 密码至少6位</h1></div>"
            "<div class='card'><a href='/user/reset-password' class='btn'>重新输入</a></div>", "recruit"))
    conn = get_recruit_db()
    user = conn.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone()
    if not user:
        conn.close()
        return HTMLResponse(make_page("重置失败",
            "<div class='header'><h1>❌ 手机号未注册</h1></div>"
            "<div class='card'><a href='/user/reset-password' class='btn'>重新输入</a></div>", "recruit"))
    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user["id"]))
    conn.commit()
    conn.close()
    return HTMLResponse(make_page("重置成功",
        "<div class='header'><h1>✅ 密码已重置</h1></div>"
        "<div class='card'><p>请用新密码登录</p>"
        "<a href='/user/login' class='btn' style='margin-top:12px;'>去登录</a></div>", "recruit"))


@router.get("/my")
async def my_redirect(request: Request):
    """统一用户入口"""
    from services.auth import check_enterprise
    uid = check_user(request)
    ent = check_enterprise(request)
    if uid:
        return RedirectResponse(url="/resume/my")
    if ent:
        return RedirectResponse(url="/enterprise/dashboard")
    return RedirectResponse(url="/account")


@router.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    """统一登录页 - tab切换身份"""
    from services.auth import check_enterprise, check_auth
    if check_auth(request):
        return RedirectResponse(url="/admin")
    uid = check_user(request)
    if uid:
        return RedirectResponse(url="/resume/my")
    ent = check_enterprise(request)
    if ent:
        return RedirectResponse(url="/enterprise/dashboard")

    return HTMLResponse("""<!DOCTYPE html><html lang='zh-CN'><head>
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
</style></head><body>
<div class="logo"><h1>🏭 武鸣招聘</h1><p>登录后查看联系方式 / 管理岗位</p></div>
<div class="tabs">
    <button class="tab active" onclick="switchTab('seeker')">🙋 求职者</button>
    <button class="tab" onclick="switchTab('enterprise')">🏢 企业</button>
</div>
<div class="form-card">
    <form id="form-seeker" class="form active" action="/user/login" method="post">
        <input name="phone" type="tel" placeholder="手机号" required pattern="[0-9]{11}" minlength="11" maxlength="11">
        <input name="password" type="password" placeholder="密码" required minlength="6">
        <button type="submit">🔑 求职者登录</button>
        <div class="link-row">没有账号？<a href="/user/register">立即注册</a></div>
    </form>
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
</script>
</body></html>""")


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    conn = get_recruit_db()
    rows = conn.execute("""SELECT n.*, j.title as job_title, j.company,
        COALESCE(j.salary_min, 0) as salary_min, COALESCE(j.salary_max, 0) as salary_max, j.salary_unit
        FROM notifications n LEFT JOIN jobs j ON n.job_id = j.id
        WHERE n.user_id=? ORDER BY n.created_at DESC LIMIT 50""", (uid,)).fetchall()
    conn.close()
    from app import make_page
    notif_html = ""
    if rows:
        for r in rows:
            read_style = "opacity:0.6;" if r["is_read"] else ""
            badge = "" if r["is_read"] else '<span style="width:8px;height:8px;background:var(--red);border-radius:50%;flex-shrink:0;"></span>'
            notif_html += f"""<div class="card" style="margin-bottom:8px;{read_style}cursor:pointer;" onclick="markReadAndGo({r['id']}, this, {r['job_id'] if r['job_id'] else 'null'})">
                <div style="display:flex;align-items:flex-start;gap:8px;">{badge}
                    <div style="flex:1;"><div style="font-weight:600;font-size:14px;">{r['title'] or '新通知'}</div>
                    <div style="font-size:13px;color:var(--text2);margin-top:4px;">{r['content'] or ''}</div>
                    <div style="font-size:11px;color:var(--text2);margin-top:4px;">{r['created_at']}</div></div></div></div>"""
    else:
        notif_html = """<div class="card" style="text-align:center;padding:40px;">
            <div style="font-size:48px;margin-bottom:12px;">🔔</div>
            <div style="color:var(--text2);">暂无通知</div>
            <a href="/push/settings" class="btn" style="margin-top:16px;">设置推送</a></div>"""
    content = f"""<div class='header'><h1>🔔 通知中心</h1></div>
    <div style="max-width:480px;margin:0 auto;">{notif_html}</div>
    <script>
    function markReadAndGo(id, el, jobId) {{
        fetch('/api/notifications/read', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ids:[id]}})}})
        .then(() => {{el.style.opacity='0.6';const badge=el.querySelector('span[style*="background:var(--red)"]');if(badge)badge.remove();if(jobId)setTimeout(()=>window.location.href='/job/'+jobId,200);}});
    }}
    </script>"""
    return HTMLResponse(make_page("通知中心 - 武鸣招聘", content, "recruit", user={"nickname": ""}))


@router.get("/push/settings", response_class=HTMLResponse)
async def push_settings_page(request: Request):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    import json, random, string
    conn = get_recruit_db()
    row = conn.execute("SELECT * FROM user_push_settings WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    p_settings = {"push_enabled": 1, "push_latest": 1, "push_categories": [], "push_salary_min": 0, "push_salary_max": 99999, "push_frequency": "daily", "push_wechat_private": 0, "push_wechat_group": 1, "wechat_bindcode": ""}
    if row:
        p_settings.update({"push_enabled": row["push_enabled"], "push_latest": row["push_latest"], "push_categories": json.loads(row["push_categories"]) if row["push_categories"] else [], "push_salary_min": row["push_salary_min"], "push_salary_max": row["push_salary_max"], "push_frequency": row["push_frequency"], "push_wechat_private": row["push_wechat_private"], "push_wechat_group": row["push_wechat_group"], "wechat_bindcode": row["wechat_bindcode"] or ""})
    from models.schema import CATEGORY_MAP
    seen = set()
    cats_html = ""
    for cat_name in CATEGORY_MAP.values():
        if cat_name not in seen:
            seen.add(cat_name)
            checked = "checked" if cat_name in p_settings["push_categories"] else ""
            cats_html += f'<label style="display:flex;align-items:center;gap:6px;padding:8px 12px;background:var(--card2);border-radius:8px;cursor:pointer;"><input type="checkbox" name="categories" value="{cat_name}" {checked} style="width:18px;height:18px;accent-color:var(--accent);"><span>{cat_name}</span></label>'
    bind_code = p_settings["wechat_bindcode"]
    if not bind_code:
        bind_code = "WM" + ''.join(random.choices(string.digits, k=6))
        conn2 = get_recruit_db()
        conn2.execute("UPDATE user_push_settings SET wechat_bindcode=? WHERE user_id=?", (bind_code, uid))
        conn2.commit()
        conn2.close()
    from app import make_page
    content = f"""<div class='header'><h1>🔔 推送设置</h1></div>
    <div class="card" style="max-width:480px;margin:0 auto;">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 0;border-bottom:1px solid var(--border);">
            <div><div style="font-weight:600;">开启推送</div><div style="font-size:12px;color:var(--text2);">接收匹配的职位推荐</div></div>
            <div onclick="toggleSwitch()" style="position:relative;width:48px;height:26px;cursor:pointer;">
                <input type="checkbox" id="pushEnabled" {"checked" if p_settings['push_enabled'] else ""} style="display:none;">
                <span id="enabledTrack" style="position:absolute;top:0;left:0;right:0;bottom:0;background:var(--border);border-radius:13px;transition:0.3s;"></span>
                <span id="enabledThumb" style="position:absolute;top:3px;left:3px;width:20px;height:20px;background:white;border-radius:50%;transition:0.3s;"></span>
            </div>
        </div>
        <div style="padding:16px 0;">
            <div class="card-title">关注行业</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">{cats_html}</div>
        </div>
        <div style="padding:16px 0;">
            <div class="card-title">薪资范围</div>
            <div style="display:flex;gap:8px;align-items:center;">
                <input type="number" id="salaryMin" value="{p_settings['push_salary_min']}" placeholder="最低" style="flex:1;padding:10px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);">
                <span style="color:var(--text2);">-</span>
                <input type="number" id="salaryMax" value="{p_settings['push_salary_max']}" placeholder="最高" style="flex:1;padding:10px;border-radius:8px;border:1px solid var(--border);background:var(--card2);color:var(--text);">
            </div>
        </div>
        <div class="btn" style="width:100%;text-align:center;cursor:pointer;" onclick="saveSettings()">保存设置</div>
    </div>
    <script>
    function toggleSwitch(){{var cb=document.getElementById('pushEnabled');if(!cb)return;cb.checked=!cb.checked;var t=document.getElementById('enabledTrack');var th=document.getElementById('enabledThumb');if(t&&th){{t.style.background=cb.checked?'var(--accent)':'var(--border)';th.style.left=cb.checked?'25px':'3px';}}}}
    function saveSettings(){{
        var cats=[];document.querySelectorAll('input[name="categories"]:checked').forEach(function(cb){{cats.push(cb.value);}});
        var minSal=parseInt(document.getElementById('salaryMin').value)||0;var maxSal=parseInt(document.getElementById('salaryMax').value)||99999;
        fetch('/api/push/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{push_enabled:document.getElementById('pushEnabled').checked?1:0,push_categories:cats,push_salary_min:minSal,push_salary_max:maxSal,push_frequency:'daily',push_wechat_private:0,push_wechat_group:1}})}})
        .then(r=>r.json()).then(d=>{{if(d.ok)alert('✅ 已保存');}});
    }}
    </script>"""
    return HTMLResponse(make_page("推送设置 - 武鸣招聘", content, "recruit", user={"nickname": ""}))


@router.get("/favorites", response_class=HTMLResponse)
async def favorites_page(request: Request):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/account")
    user_info = get_user_info(uid)
    conn = get_recruit_db()
    rows = conn.execute(
        "SELECT j.* FROM jobs j JOIN favorites f ON j.id = f.job_id "
        "WHERE f.user_id=? AND j.status IN ('active','pending') ORDER BY f.created_at DESC",
        (uid,)
    ).fetchall()
    conn.close()
    from app import make_page
    jobs_html = ""
    for j in rows:
        s_min, s_max = (j['salary_min'] or 0), (j['salary_max'] or 0)
        salary = f"{s_min}-{s_max}{j['salary_unit']}" if s_max else (f"{s_min}{j['salary_unit']}" if s_min else '<span class="salary-negotiable">面议</span>')
        jobs_html += f"""<div class="job-card" onclick="window.location.href='/job/{j['id']}'" style="cursor:pointer;">
            <div class="job-title">{j['title']}</div>
            <div class="job-meta"><a href="/company/{urllib.parse.quote(j['company'])}" class="company-link" onclick="event.stopPropagation();">{j['company']}</a></div>
            <div class="job-salary">{salary}</div>
        </div>"""
    if not jobs_html:
        jobs_html = '<div style="text-align:center;padding:40px;color:var(--text2);">还没有收藏任何岗位<br><a href="/" class="btn-sm">去看看 →</a></div>'
    content = f"<div style='padding:16px;'><h2 style='margin-bottom:16px;'>⭐ 我的收藏</h2>{jobs_html}</div>"
    return HTMLResponse(make_page("我的收藏 - 武鸣招聘", content, "recruit",
                                  user={"nickname": user_info["nickname"]} if user_info else None))
