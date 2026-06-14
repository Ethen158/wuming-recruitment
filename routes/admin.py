"""
管理后台路由 - /admin/*, /login, /logout
"""
from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from services.db import get_recruit_db, get_salary_display, time_ago, _clean_company_desc, clean_salary
from services.auth import check_auth, make_admin_token
from services.push import push_new_job_to_users
from config import settings

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """管理员登录页"""
    from app import templates
    return templates.TemplateResponse(request, "admin/login.html", {})


@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request):
    """管理员登录提交"""
    form = await request.form()
    pwd = form.get("password", "")

    if pwd != settings.ADMIN_PASSWORD:
        from app import templates
        return templates.TemplateResponse(request, "admin/login.html", {
            "error": "密码不正确"
        })

    token = make_admin_token(pwd)
    from fastapi.responses import HTMLResponse as Resp
    html = """
    <div class='header'><h1>✅ 登录成功</h1></div>
    <div class="card" style="max-width:360px;margin:40px auto;text-align:center;">
        <p style="margin-bottom:16px;">正在跳转到管理后台...</p>
        <a href="/admin" class="btn">→ 进入后台</a>
    </div>
    """
    from app import make_page
    resp = Resp(content=make_page("登录成功", html, "recruit"))
    resp.set_cookie(
        key="session", value=token,
        max_age=settings.SESSION_HOURS * 3600,
        httponly=True, samesite="lax", path="/"
    )
    resp.set_cookie(key="session_persist", value="1", max_age=30 * 86400, path="/")
    resp.delete_cookie("user_session", path="/")
    resp.delete_cookie("ent_session", path="/")
    return resp


@router.get("/logout", response_class=HTMLResponse)
async def logout():
    resp = RedirectResponse(url="/")
    resp.delete_cookie("session", path="/")
    resp.delete_cookie("session_persist", path="/")
    return resp


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """管理后台首页"""
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='active'").fetchone()[0]
    total_channels = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    pending_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='pending'").fetchone()[0]
    pending_ents = conn.execute("SELECT COUNT(*) FROM enterprises WHERE status='pending'").fetchone()[0]
    cat_stats = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM jobs WHERE status='active' GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    conn.close()

    from app import templates
    return templates.TemplateResponse(request, "admin/dashboard.html", {
        "now": now,
        "total_jobs": total_jobs, "total_channels": total_channels,
        "pending_jobs": pending_jobs, "pending_ents": pending_ents,
        "cat_stats": cat_stats,
    })


@router.get("/admin/jobs", response_class=HTMLResponse)
async def admin_jobs(request: Request, cat: str = "", q: str = ""):
    """岗位管理"""
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
    categories = [
        r["category"] for r in conn.execute(
            "SELECT DISTINCT category FROM jobs WHERE status IN ('active','pending') ORDER BY category"
        ).fetchall()
    ]
    pending_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='pending'").fetchone()[0]
    conn.close()

    from app import templates
    return templates.TemplateResponse(request, "admin/jobs.html", {
        "jobs": jobs, "categories": categories,
        "pending_count": pending_count, "cat": cat, "q": q,
    })


@router.get("/admin/job/add", response_class=HTMLResponse)
async def admin_job_add_form(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    from app import templates
    return templates.TemplateResponse(request, "admin/job_form.html", {
        "edit_mode": False, "job": None
    })


@router.post("/admin/job/add", response_class=HTMLResponse)
async def admin_job_add_submit(
    request: Request, title: str = Form(...), company: str = Form(...),
    location: str = Form(""), salary_min: int = Form(0), salary_max: int = Form(0),
    salary_unit: str = Form("元/月"), job_type: str = Form("全职"),
    category: str = Form("其他"), description: str = Form(""),
    contact_phone: str = Form(""), tags: str = Form(""), headcount: int = Form(0)
):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    salary_min, salary_max, salary_unit = clean_salary(salary_min, salary_max, salary_unit)
    conn.execute(
        "INSERT INTO jobs (title,company,location,salary_min,salary_max,salary_unit,"
        "job_type,category,description,contact_phone,tags,headcount,source,status,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?)",
        (title, company, location, salary_min, salary_max, salary_unit,
         job_type, category, description, contact_phone, tags, headcount, "后台添加", now_dt)
    )
    conn.commit()
    conn.close()
    from app import make_page
    return HTMLResponse(make_page("添加成功",
        "<div class='header'><h1>✅ 添加成功</h1></div>"
        "<div style='text-align:center;'><a href='/admin/jobs' class='btn'>返回岗位列表</a></div>",
        "recruit"))


@router.get("/admin/job/edit/{job_id}", response_class=HTMLResponse)
async def admin_job_edit_form(request: Request, job_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    j = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not j:
        return HTMLResponse("<h2>岗位不存在</h2>")
    from app import templates
    return templates.TemplateResponse(request, "admin/job_form.html", {
        "edit_mode": True, "job": j
    })


@router.post("/admin/job/edit/{job_id}", response_class=HTMLResponse)
async def admin_job_edit_submit(
    request: Request, job_id: int,
    title: str = Form(...), company: str = Form(...), location: str = Form(""),
    salary_min: int = Form(0), salary_max: int = Form(0),
    salary_unit: str = Form("元/月"), job_type: str = Form("全职"),
    category: str = Form("其他"), description: str = Form(""),
    contact_phone: str = Form(""), tags: str = Form(""), headcount: int = Form(0)
):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    salary_min, salary_max, salary_unit = clean_salary(salary_min, salary_max, salary_unit)
    conn.execute(
        "UPDATE jobs SET title=?,company=?,location=?,salary_min=?,salary_max=?,"
        "salary_unit=?,job_type=?,category=?,description=?,contact_phone=?,tags=?,headcount=?,updated_at=? "
        "WHERE id=?",
        (title, company, location, salary_min, salary_max, salary_unit,
         job_type, category, description, contact_phone, tags, headcount, now_dt, job_id)
    )
    conn.commit()
    conn.close()
    from app import make_page
    return HTMLResponse(make_page("修改成功",
        f"<div class='header'><h1>✅ 修改成功</h1></div>"
        f"<div style='text-align:center;margin:16px;'>"
        f"<a href='/admin/jobs' class='btn'>返回岗位列表</a> "
        f"<a href='/job/{job_id}' class='btn' style='background:var(--accent2);'>查看岗位</a></div>",
        "recruit"))


@router.get("/admin/job/delete/{job_id}", response_class=HTMLResponse)
async def admin_job_delete(request: Request, job_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    conn.execute("UPDATE jobs SET status='deleted' WHERE id=?", (job_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/jobs")


@router.get("/admin/job/approve/{job_id}")
async def admin_job_approve(request: Request, job_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    conn.execute("UPDATE jobs SET status='active' WHERE id=?", (job_id,))
    conn.commit()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if job:
        push_new_job_to_users(dict(job))
    return RedirectResponse(url="/admin/jobs")


@router.get("/admin/channels", response_class=HTMLResponse)
async def admin_channels(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    channels = conn.execute("SELECT * FROM channels ORDER BY type").fetchall()
    conn.close()
    from app import make_page
    content = """<div class='header'><h1>📡 渠道管理</h1>
        <div class='time'><a href="/admin" style="color:var(--text2);">← 返回后台</a></div></div>
    """ + "".join(
        f'<div class="ch-card"><div class="ch-name">{ch["name"]}</div>'
        f'<div class="ch-type">{ch["type"]}</div>'
        f'<div class="ch-info">{ch["description"] or ""}</div>'
        f'<div class="ch-info">{ch["notes"] or ""}</div>'
        f'<div class="ch-contact">{ch["contact"] or ""}</div></div>'
        for ch in channels
    ) or '<p style="color:var(--text2);">暂无渠道</p>'
    return HTMLResponse(make_page("渠道管理", content, "recruit"))


@router.get("/admin/scripts", response_class=HTMLResponse)
async def admin_scripts(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    scripts = conn.execute(
        "SELECT * FROM video_scripts ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    from app import make_page
    content = """<div class='header'><h1>🎬 视频脚本</h1>
        <div class='time'><a href="/admin" style="color:var(--text2);">← 返回后台</a></div></div>
        <div style="margin-bottom:12px;">
        <a href="/admin/gen_script" class="btn" style="background:#e74c3c;">🎥 生成新脚本</a></div>"""
    for s in scripts:
        content += f"""<div class="script-card">
            <div class="script-title">{s["title"]}</div>
            <div class="script-meta">平台：{s["target_platform"]} | 类型：{s["script_type"]} | {s["date"]}</div>
            <pre class="script-content">{s["content"][:500]}{"..." if len(s["content"]) > 500 else ""}</pre>
        </div>"""
    content += "<p style='color:var(--text2);'>暂无脚本</p>" if not scripts else ""
    return HTMLResponse(make_page("视频脚本", content, "recruit"))


@router.get("/admin/gen_script", response_class=HTMLResponse)
async def admin_gen_script(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    today = datetime.now().strftime("%Y-%m-%d")
    jobs = conn.execute(
        "SELECT * FROM jobs WHERE status='active' ORDER BY RANDOM() LIMIT 3"
    ).fetchall()
    if len(jobs) < 3:
        from app import make_page
        return HTMLResponse(make_page("生成脚本",
            "<div class='header'><h1>⚠️ 岗位不足</h1><p style='text-align:center;padding:30px;'>至少需要3个岗位</p></div>",
            "recruit"))
    job_titles = "、".join([j["title"] for j in jobs])
    script_content = (
        f"【口播稿 - 武鸣今日好工作】\n\n（开场）\n大家好，我是武鸣本地找工作的小冯！"
        f"\n今天给大家带来几个武鸣和里建的好岗位，全是真实招聘！\n\n"
        f"（岗位1）\n第一个：【{jobs[0]['title']}】\n{ jobs[0]['company']} 在招人\n"
        f"薪资：{ jobs[0]['salary_min']}-{jobs[0]['salary_max']}{jobs[0]['salary_unit']}\n"
        f"工作地点：{jobs[0]['location']}\n{ jobs[0]['description'][:100] if jobs[0]['description'] else ''}\n\n"
        f"（岗位2）\n第二个：【{jobs[1]['title']}】\n"
        f"薪资：{jobs[1]['salary_min']}-{jobs[1]['salary_max']}{jobs[1]['salary_unit']}\n\n"
        f"（岗位3）\n第三个：【{jobs[2]['title']}】\n{ jobs[2]['company']} 招人\n"
        f"薪资：{jobs[2]['salary_min']}-{jobs[2]['salary_max']}{jobs[2]['salary_unit']}\n\n"
        f"（结尾）\n想了解更多武鸣本地工作，关注我，每天更新！\n"
        f"#武鸣找工作 #东盟经开区 #武鸣招聘\n\n"
        f"【发布时间建议】中午12:00或晚上20:00\n【推荐平台】抖音 + 视频号同步"
    )
    conn.execute(
        "INSERT INTO video_scripts(date, title, script_type, content, target_platform, related_jobs, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (today, f"武鸣今日好工作 - {today}", "口播", script_content, "抖音+视频号",
         job_titles, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    conn.close()
    from app import make_page
    content = (
        f"<div class='header'><h1>🎥 视频脚本已生成</h1><div class='time'>{today}</div></div>"
        f"<a href='/admin/scripts' class='btn' style='margin-bottom:12px;'>← 返回脚本列表</a>"
        f"<a href='/recruit/video' class='btn' style='margin-bottom:12px;background:#00b894;'>📹 打开视频模式</a>"
        f"<div class='script-card' style='background:var(--card);padding:16px;border-radius:8px;"
        f"white-space:pre-wrap;font-size:13px;line-height:1.8;font-family:monospace;'>{script_content}</div>"
    )
    return HTMLResponse(make_page("生成脚本", content, "recruit"))


@router.get("/admin/enterprises", response_class=HTMLResponse)
async def admin_enterprises(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    ents = conn.execute("SELECT * FROM enterprises ORDER BY created_at DESC").fetchall()
    pending = conn.execute("SELECT COUNT(*) FROM enterprises WHERE status='pending'").fetchone()[0]
    conn.close()
    from app import make_page
    status_map = {"active": "✅", "pending": "⏳", "blocked": "🚫"}
    rows = ""
    for e in ents:
        rows += f"""<div class="job-card" style="border-left:3px solid {'var(--yellow)' if e['status']=='pending' else 'var(--green)'};">
            <div class="job-title">{e['company_name']} <span style="font-size:11px;color:var(--text2);">{status_map.get(e['status'], '❓')} {e['status']}</span></div>
            <div class="job-meta">📞 {e['contact_name']} {e['contact_phone']} | 📅 {e['created_at'][:10]}</div>
            <div class="job-footer" style="justify-content:flex-end;">
                <a href="/admin/enterprise/approve/{e['id']}" class="btn-sm" style="color:var(--green);" onclick="return confirm('通过 {e['company_name']} 的审核？')">✅ 通过</a>
                <a href="/admin/enterprise/block/{e['id']}" class="btn-sm" style="color:var(--red);" onclick="return confirm('禁用 {e['company_name']}？')">🚫 禁用</a>
            </div></div>"""
    content = f"""<div class="header"><h1>🏢 企业管理</h1><div class="time"><a href="/admin" style="color:var(--text2);font-size:11px;">← 返回后台</a></div></div>
    <div style="display:flex;gap:8px;margin-bottom:12px;">
        <div class="stat-card"><div class="stat-num">{len(ents)}</div><div class="stat-label">全部企业</div></div>
        <div class="stat-card"><div class="stat-num" style="color:var(--yellow);">{pending}</div><div class="stat-label">待审核</div></div>
    </div>
    <div>{rows or '<p style="color:var(--text2);text-align:center;padding:20px;">暂无企业注册</p>'}</div>"""
    return HTMLResponse(make_page("企业管理 - 武鸣招聘", content, "recruit"))


@router.get("/admin/enterprise/approve/{ent_id}")
async def admin_enterprise_approve(request: Request, ent_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    conn.execute("UPDATE enterprises SET status='active' WHERE id=?", (ent_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/enterprises")


@router.get("/admin/enterprise/block/{ent_id}")
async def admin_enterprise_block(request: Request, ent_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    conn.execute("UPDATE enterprises SET status='blocked' WHERE id=?", (ent_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/enterprises")


@router.get("/admin/resumes", response_class=HTMLResponse)
async def admin_resumes(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    resumes = conn.execute(
        "SELECT * FROM resumes WHERE is_active=1 ORDER BY created_at DESC"
    ).fetchall()
    total = len(resumes)
    conn.close()
    from app import make_page
    rows = ""
    for r in resumes:
        rows += f"""<div class="job-card">
            <div class="job-title">{r['name']} <span style="font-size:11px;color:var(--text2);">· {r.get('gender','') or ''} {r.get('age',0) or ''}岁</span>
            {'<span class="tag" style="background:var(--yellow);color:#000;">📌 置顶</span>' if r['is_pinned'] else ''}</div>
            <div class="job-meta">🎯 {r['expected_job'] or '未填'} | 💰 {r['expected_salary'] or '未填'} | 🎓 {r['edu_level'] or '未填'}</div>
            <div class="job-desc">{r['experience'][:60] if r['experience'] else ''}</div>
            <div class="job-footer" style="justify-content:flex-end;"><a href="/resume/{r['id']}" class="btn-sm">👁 查看</a></div>
        </div>"""
    content = f"""<div class="header"><h1>📄 简历管理</h1><div class="time"><a href="/admin" style="color:var(--text2);font-size:11px;">← 返回后台</a></div></div>
    <div style="display:flex;gap:8px;margin-bottom:12px;">
        <div class="stat-card"><div class="stat-num">{total}</div><div class="stat-label">简历总数</div></div>
    </div>
    <div>{rows or '<p style="color:var(--text2);text-align:center;padding:20px;">暂无简历</p>'}</div>"""
    return HTMLResponse(make_page("简历管理 - 武鸣招聘", content, "recruit"))


@router.get("/admin/feedback", response_class=HTMLResponse)
async def admin_feedback(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    conn = get_recruit_db()
    feedbacks = conn.execute(
        "SELECT id, content, contact, page, status, created_at FROM feedback ORDER BY created_at DESC"
    ).fetchall()
    total = len(feedbacks)
    pending = conn.execute("SELECT COUNT(*) FROM feedback WHERE status='pending'").fetchone()[0]
    conn.close()
    from app import make_page
    rows = ""
    for fb in feedbacks:
        rows += f"""<div class="job-card" style="border-left:3px solid {'var(--yellow)' if fb['status']=='pending' else 'var(--green)'};">
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
    content = f"""<div class="header"><h1>💬 反馈管理</h1><div class="time">共{total}条 | 待处理{pending}条 | <a href="/admin" style="color:var(--text2);font-size:11px;">← 返回</a></div></div>
    <div style="display:flex;gap:8px;margin-bottom:12px;">
        <div class="stat-card"><div class="stat-num">{total}</div><div class="stat-label">全部</div></div>
        <div class="stat-card"><div class="stat-num" style="color:var(--yellow);">{pending}</div><div class="stat-label">待处理</div></div>
    </div>
    <div>{rows or '<p style="color:var(--text2);text-align:center;padding:30px;">暂无反馈</p>'}</div>"""
    return HTMLResponse(make_page("反馈管理 - 武鸣招聘", content, "recruit"))


@router.get("/admin/feedback/done/{fb_id}")
async def mark_feedback_done(fb_id: int):
    conn = get_recruit_db()
    conn.execute("UPDATE feedback SET status='done' WHERE id=?", (fb_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/feedback")
