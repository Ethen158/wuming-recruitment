"""
企业端路由 - 注册、登录、控制台、岗位管理
"""
import hashlib
from datetime import datetime
import bcrypt
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from services.db import get_recruit_db
from services.auth import check_enterprise, make_ent_token, make_ent_password

router = APIRouter()


def _ent_header(title, back_text="", back_url=""):
    bt = f'<a href="{back_url}" style="color:var(--text2);font-size:12px;">{back_text}</a>' if back_url else ""
    return f'<div class="header"><h1>{title}</h1><div class="time">{bt}</div></div>'


@router.get("/enterprise/register", response_class=HTMLResponse)
async def ent_register_form(request: Request):
    from app import make_page
    content = f"""{_ent_header("🏢 企业注册", "已有账号？去登录 →", "/enterprise/login")}
    <div class="card">
    <form action="/enterprise/register" method="post" style="display:flex;flex-direction:column;gap:10px;">
        <input name="company_name" placeholder="企业/公司全称 *" required style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <input name="contact_name" placeholder="联系人姓名 *" required style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <input name="contact_phone" placeholder="联系电话 *" required type="tel" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <input name="password" placeholder="设置密码（至少6位）*" required type="password" minlength="6" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <input name="license_no" placeholder="营业执照号（选填）" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <button type="submit" style="background:var(--accent);border:none;border-radius:8px;padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">✅ 注册企业账号</button>
    </form>
    </div>"""
    return HTMLResponse(make_page("企业注册 - 武鸣招聘", content, "recruit"))


@router.post("/enterprise/register", response_class=HTMLResponse)
async def ent_register_submit(
    company_name: str = Form(...), contact_name: str = Form(...),
    contact_phone: str = Form(...), password: str = Form(...),
    license_no: str = Form("")
):
    conn = get_recruit_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ph = make_ent_password(password)
    try:
        conn.execute(
            "INSERT INTO enterprises (company_name, contact_name, contact_phone, password_hash, license_no, status, created_at) "
            "VALUES (?,?,?,?,?,'pending',?)",
            (company_name, contact_name, contact_phone, ph, license_no, now)
        )
        conn.commit()
        conn.close()
        return HTMLResponse("""
        <div class='header'><h1>✅ 注册成功</h1></div>
        <div class="card" style="text-align:center;">
            <div style="font-size:48px;margin-bottom:12px;">🎉</div>
            <div style="font-size:16px;font-weight:600;color:var(--green);margin-bottom:8px;">企业账号注册成功！</div>
            <div style="font-size:13px;color:var(--text2);margin-bottom:16px;">请等待管理员审核通过后即可发布岗位</div>
            <a href="/enterprise/login" class="btn">去登录</a>
        </div>""")
    except Exception as e:
        conn.close()
        from app import make_page
        msg = "该公司名称已被注册" if "UNIQUE" in str(e) else str(e)
        return HTMLResponse(make_page("注册失败",
            f"<div class='header'><h1>⚠️ 注册失败</h1></div><div class='card'><p style='color:var(--red);'>{msg}</p><a href='/enterprise/register' class='btn'>重新填写</a></div>",
            "recruit"))


@router.get("/enterprise/login", response_class=HTMLResponse)
async def ent_login_form(request: Request):
    ent = check_enterprise(request)
    if ent:
        return RedirectResponse(url="/enterprise/dashboard")
    from app import make_page
    content = f"""{_ent_header("🏢 企业登录", "没有账号？去注册 →", "/enterprise/register")}
    <div class="card">
    <form action="/enterprise/login" method="post" style="display:flex;flex-direction:column;gap:10px;">
        <input name="company_name" placeholder="企业名称 *" required style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <input name="password" placeholder="密码 *" required type="password" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <button type="submit" style="background:var(--accent);border:none;border-radius:8px;padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">🔑 登录</button>
    </form>
    </div>"""
    return HTMLResponse(make_page("企业登录 - 武鸣招聘", content, "recruit"))


@router.post("/enterprise/login", response_class=HTMLResponse)
async def ent_login_submit(
    request: Request, company_name: str = Form(...), password: str = Form(...)
):
    from app import make_page
    conn = get_recruit_db()
    ent = conn.execute(
        "SELECT * FROM enterprises WHERE company_name=?", (company_name,)
    ).fetchone()
    conn.close()
    if not ent:
        return HTMLResponse(make_page("登录失败",
            "<div class='header'><h1>⚠️ 登录失败</h1></div><div class='card'><p style='color:var(--red);'>企业名称或密码错误</p><a href='/enterprise/login' class='btn'>重新登录</a></div>",
            "recruit"))
    stored = ent["password_hash"]
    if stored.startswith("$2"):
        pwd_ok = bcrypt.checkpw(f"ent::{password}".encode(), stored.encode())
    else:
        pwd_ok = (stored == hashlib.sha256(f"ent::{password}".encode()).hexdigest())
    if not pwd_ok:
        return HTMLResponse(make_page("登录失败",
            "<div class='header'><h1>⚠️ 登录失败</h1></div><div class='card'><p style='color:var(--red);'>企业名称或密码错误</p><a href='/enterprise/login' class='btn'>重新登录</a></div>",
            "recruit"))
    if ent["status"] == "pending":
        return HTMLResponse(make_page("审核中",
            "<div class='header'><h1>⏳ 账号审核中</h1></div><div class='card'><p>请等待管理员审核</p><a href='/' class='btn'>返回首页</a></div>",
            "recruit"))
    if ent["status"] == "blocked":
        return HTMLResponse(make_page("账号已禁用",
            "<div class='header'><h1>🚫 账号已禁用</h1></div><div class='card'><p style='color:var(--red);'>请联系管理员</p><a href='/' class='btn'>返回首页</a></div>",
            "recruit"))
    token = make_ent_token(ent["id"])
    conn2 = get_recruit_db()
    conn2.execute("UPDATE enterprises SET last_login=? WHERE id=?",
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ent["id"]))
    conn2.commit()
    conn2.close()
    resp = RedirectResponse(url="/enterprise/dashboard")
    resp.set_cookie(key="ent_session", value=token, max_age=72 * 3600, httponly=True)
    resp.delete_cookie("user_session", path="/")
    resp.delete_cookie("session", path="/")
    return resp


@router.get("/enterprise/logout", response_class=HTMLResponse)
async def ent_logout(request: Request):
    resp = RedirectResponse(url="/")
    resp.delete_cookie("ent_session")
    return resp


@router.get("/enterprise/dashboard", response_class=HTMLResponse)
async def ent_dashboard(request: Request):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    my_jobs = conn.execute(
        "SELECT * FROM jobs WHERE company=? AND status='active' ORDER BY created_at DESC",
        (ent["company_name"],)
    ).fetchall()
    pending_jobs = conn.execute(
        "SELECT * FROM jobs WHERE company=? AND status='pending' ORDER BY created_at DESC",
        (ent["company_name"],)
    ).fetchall()
    total_resumes = conn.execute("SELECT COUNT(*) FROM resumes WHERE is_active=1").fetchone()[0]
    conn.close()
    from app import make_page
    jobs_html = ""
    for j in my_jobs:
        s_min = j['salary_min'] if j['salary_min'] else 0
        s_max = j['salary_max'] if j['salary_max'] else 0
        salary = f"{s_min}-{s_max}{j['salary_unit']}" if s_max else (f"{s_min}{j['salary_unit']}" if s_min else '<span class="salary-negotiable">面议</span>')
        jobs_html += f"""<div class="job-card" style="border-left:3px solid var(--accent);">
            <div class="job-title">{j['title']}</div>
            <div class="job-meta">{j['location'] or ''} | {j['job_type']} | {j['category']}</div>
            <div class="job-salary">{salary}</div>
            <div class="job-footer" style="justify-content:space-between;">
                <div><span class="source">{j['source']}</span></div>
                <div>
                    <a href="/enterprise/job/edit/{j['id']}" class="btn-sm" style="color:var(--yellow);">✏️ 编辑</a>
                    <a href="/enterprise/job/delete/{j['id']}" onclick="return confirm('确定下架 {j['title']}?')" class="btn-sm" style="color:var(--red);">🗑 下架</a>
                </div>
            </div></div>"""
    content = f"""<div class="header"><h1>🏢 {ent['company_name']}</h1>
        <div class="time"><a href="/enterprise/logout" style="color:var(--text2);font-size:11px;">退出</a></div></div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:12px;">
        <div class="stat-card"><div class="stat-num">{len(my_jobs)}</div><div class="stat-label">已上架</div></div>
        <div class="stat-card"><div class="stat-num" style="color:var(--yellow);">{len(pending_jobs)}</div><div class="stat-label">待审核</div></div>
        <div class="stat-card"><div class="stat-num">{total_resumes}</div><div class="stat-label">简历库</div></div>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
        <a href="/enterprise/job/add" class="btn" style="background:var(--green);">➕ 发布新岗位</a>
        <a href="/resumes" class="btn" style="background:var(--accent2);">👥 浏览简历</a>
    </div>
    <div class="card"><div class="card-title">📋 我发布的岗位</div>
        <div>{jobs_html or '<p style="color:var(--text2);text-align:center;padding:20px;">还没有发布岗位</p>'}</div></div>"""
    return HTMLResponse(make_page("企业控制台 - 武鸣招聘", content, "recruit"))


@router.get("/enterprise/job/add", response_class=HTMLResponse)
async def ent_job_add_form(request: Request):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    from app import make_page
    content = f"""{_ent_header("➕ 发布新岗位", "← 返回控制台", "/enterprise/dashboard")}
    <form action="/enterprise/job/add" method="post" style="display:flex;flex-direction:column;gap:8px;">
        <input name="title" placeholder="岗位名称 *" required style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <input name="location" placeholder="工作地点 *" required style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
            <input name="category" placeholder="分类（食品加工/餐饮/物流/其他）" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
            <input name="salary_min" placeholder="最低薪资" type="number" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <input name="salary_max" placeholder="最高薪资" type="number" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
            <select name="job_type" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
                <option value="全职">全职</option><option value="兼职">兼职</option>
                <option value="小时工">小时工</option><option value="日结">日结</option>
                <option value="临时工">临时工</option>
            </select>
        </div>
        <textarea name="description" rows="4" placeholder="岗位要求、职责描述、福利待遇等" required
                  style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;font-size:14px;"></textarea>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <input name="contact_phone" placeholder="联系电话 *" required style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
            <input name="tags" placeholder="标签（逗号分隔）" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        </div>
        <button type="submit" style="background:var(--green);border:none;border-radius:8px;padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">✅ 提交审核</button>
    </form>"""
    return HTMLResponse(make_page("发布岗位 - 武鸣招聘", content, "recruit"))


@router.post("/enterprise/job/add", response_class=HTMLResponse)
async def ent_job_add_submit(
    request: Request, title: str = Form(...), location: str = Form(""),
    category: str = Form("其他"), salary_min: int = Form(0),
    salary_max: int = Form(0), job_type: str = Form("全职"),
    description: str = Form(""), contact_phone: str = Form(""),
    contact_name: str = Form(""), tags: str = Form("")
):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO jobs (title, company, location, salary_min, salary_max, salary_unit, "
        "job_type, category, description, contact_name, contact_phone, tags, source, status, created_at) "
        "VALUES (?,?,?,?,?,'元/月',?,?,?,?,?,?,'企业发布','pending',?)",
        (title, ent["company_name"], location, salary_min, salary_max,
         job_type, category, description, contact_name, contact_phone, tags, now_dt)
    )
    conn.commit()
    conn.close()
    return HTMLResponse("""
    <div class="header"><h1>✅ 提交成功</h1></div>
    <div class="card" style="text-align:center;">
        <div style="font-size:48px;margin-bottom:12px;">📨</div>
        <div style="font-size:16px;font-weight:600;color:var(--green);margin-bottom:8px;">岗位已提交审核</div>
        <div style="font-size:13px;color:var(--text2);margin-bottom:16px;">管理员审核通过后将在首页展示</div>
        <a href="/enterprise/dashboard" class="btn">返回控制台</a>
    </div>""")


@router.get("/enterprise/job/edit/{job_id}", response_class=HTMLResponse)
async def ent_job_edit_form(request: Request, job_id: int):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    j = conn.execute(
        "SELECT * FROM jobs WHERE id=? AND company=?", (job_id, ent["company_name"])
    ).fetchone()
    conn.close()
    if not j:
        return HTMLResponse("<h2>岗位不存在或无权操作</h2>")
    from app import make_page
    content = f"""{_ent_header("✏️ 编辑岗位", "← 返回控制台", "/enterprise/dashboard")}
    <form action="/enterprise/job/edit/{job_id}" method="post" style="display:flex;flex-direction:column;gap:8px;">
        <input name="title" value="{j['title']}" placeholder="岗位名称 *" required style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <input name="location" value="{j['location'] or ''}" placeholder="工作地点" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
            <input name="category" value="{j['category'] or '其他'}" placeholder="分类" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        </div>
        <input name="salary_min" value="{j['salary_min'] or 0}" type="number" placeholder="最低薪资" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        <input name="salary_max" value="{j['salary_max'] or 0}" type="number" placeholder="最高薪资" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);">
        <textarea name="description" rows="4" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;">{j['description'] or ''}</textarea>
        <input name="contact_phone" value="{j['contact_phone'] or ''}" placeholder="联系电话" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <input name="tags" value="{j['tags'] or ''}" placeholder="标签" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <button type="submit" style="background:var(--yellow);border:none;border-radius:8px;padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">💾 保存修改</button>
    </form>"""
    return HTMLResponse(make_page("编辑岗位 - 武鸣招聘", content, "recruit"))


@router.post("/enterprise/job/edit/{job_id}", response_class=HTMLResponse)
async def ent_job_edit_submit(
    request: Request, job_id: int, title: str = Form(...),
    location: str = Form(""), category: str = Form("其他"),
    salary_min: int = Form(0), salary_max: int = Form(0),
    job_type: str = Form("全职"), description: str = Form(""),
    contact_phone: str = Form(""), contact_name: str = Form(""),
    tags: str = Form("")
):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE jobs SET title=?, location=?, salary_min=?, salary_max=?, "
        "job_type=?, category=?, description=?, contact_name=?, contact_phone=?, tags=?, updated_at=? "
        "WHERE id=? AND company=?",
        (title, location, salary_min, salary_max, job_type, category,
         description, contact_name, contact_phone, tags, now_dt, job_id, ent["company_name"])
    )
    conn.commit()
    conn.close()
    from app import make_page
    return HTMLResponse(make_page("修改成功",
        f"<div class='header'><h1>✅ 修改成功</h1></div>"
        f"<div style='text-align:center;margin:16px;'>"
        f"<a href='/enterprise/dashboard' class='btn'>返回控制台</a> "
        f"<a href='/job/{job_id}' class='btn' style='background:var(--accent2);'>查看岗位</a></div>",
        "recruit"))


@router.get("/enterprise/job/delete/{job_id}")
async def ent_job_delete(request: Request, job_id: int):
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    conn.execute(
        "UPDATE jobs SET status='deleted' WHERE id=? AND company=?",
        (job_id, ent["company_name"])
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/enterprise/dashboard")
