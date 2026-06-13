"""
简历路由 - 添加、编辑、查看、列表
"""
from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from services.db import get_recruit_db
from services.auth import check_user, get_user_info, check_enterprise

router = APIRouter()


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
            <input name="name" value="{name_val}" placeholder="姓名 *" required style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
            <input name="age" value="{age_val if age_val else ''}" placeholder="年龄" type="number" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <select name="gender" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">{gender_options}</select>
            <select name="edu_level" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">{edu_options}</select>
        </div>
        <input name="phone" value="{phone_val}" placeholder="手机号 *" required style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <input name="wechat" value="{wechat_val}" placeholder="微信号" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <input name="expected_job" value="{exp_job_val}" placeholder="期望岗位" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
            <input name="expected_salary" value="{exp_sal_val}" placeholder="期望薪资" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);font-size:14px;">
        </div>
        <textarea name="experience" rows="3" placeholder="工作经历" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;font-size:14px;">{exp_val or ''}</textarea>
        <textarea name="skills" rows="2" placeholder="技能特长" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;font-size:14px;">{skills_val or ''}</textarea>
        <textarea name="self_desc" rows="2" placeholder="自我介绍" style="background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text);resize:none;font-size:14px;">{self_desc_val or ''}</textarea>
        <button type="submit" style="background:var(--accent2);border:none;border-radius:8px;padding:12px;color:white;font-size:15px;font-weight:600;cursor:pointer;">✅ 保存简历</button>
    </form>"""


@router.get("/resume/add", response_class=HTMLResponse)
async def resume_add_form(request: Request):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    user_info = get_user_info(uid)
    conn = get_recruit_db()
    existing = conn.execute(
        "SELECT * FROM resumes WHERE user_id=? AND is_active=1", (uid,)
    ).fetchone()
    conn.close()
    if existing:
        return RedirectResponse(url="/resume/my")
    form = _resume_form(
        user_info["nickname"] if user_info else "", 0, "", "",
        user_info["phone"] if user_info else "", "", "", "", "", "", "", "/resume/add"
    )
    from app import make_page
    content = f"""<div class='header'><h1>📄 我的简历</h1></div>
    <div style="margin-bottom:8px;font-size:13px;color:var(--text2);">填写信息让企业找到你</div>
    <div class="card">{form}</div>
    <div style="font-size:11px;color:var(--text2);margin-top:8px;padding:8px;background:var(--card2);border-radius:6px;">📌 简历将展示给已认证的企业用户</div>"""
    return HTMLResponse(make_page("上传简历 - 武鸣招聘", content, "recruit",
                                  user={"nickname": user_info["nickname"]}))


@router.post("/resume/add", response_class=HTMLResponse)
async def resume_add_submit(
    request: Request, name: str = Form(...), age: int = Form(0),
    gender: str = Form(""), edu_level: str = Form(""), phone: str = Form(...),
    wechat: str = Form(""), expected_job: str = Form(""),
    expected_salary: str = Form(""), experience: str = Form(""),
    skills: str = Form(""), self_desc: str = Form("")
):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    conn = get_recruit_db()
    existing = conn.execute(
        "SELECT id FROM resumes WHERE user_id=? AND is_active=1", (uid,)
    ).fetchone()
    if existing:
        conn.close()
        from app import make_page
        return HTMLResponse(make_page("已有简历",
            "<div class='header'><h1>⚠️ 已有简历</h1></div><div style='text-align:center;margin:16px;'><a href='/resume/my' class='btn'>查看我的简历</a></div>",
            "recruit"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO resumes (user_id,name,gender,age,phone,wechat,edu_level,experience,"
        "expected_job,expected_salary,skills,self_desc,is_active,is_pinned,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,0,?,?)",
        (uid, name, gender, age, phone, wechat, edu_level, experience,
         expected_job, expected_salary, skills, self_desc, now, now)
    )
    conn.commit()
    conn.close()
    from app import make_page
    return HTMLResponse(make_page("简历已保存",
        "<div class='header'><h1>✅ 简历已保存</h1></div><div class='card' style='text-align:center;'><a href='/resume/my' class='btn'>查看我的简历</a></div>",
        "recruit"))


@router.get("/resume/my", response_class=HTMLResponse)
async def resume_my(request: Request):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    user_info = get_user_info(uid)
    conn = get_recruit_db()
    r = conn.execute(
        "SELECT * FROM resumes WHERE user_id=? AND is_active=1", (uid,)
    ).fetchone()
    conn.close()
    if not r:
        from app import make_page
        content = """<div class='header'><h1>📄 我的简历</h1></div>
        <div class="card" style="text-align:center;">
            <div style="font-size:48px;margin-bottom:12px;">📄</div>
            <p style="color:var(--text2);margin-bottom:16px;">还没有创建简历</p>
            <a href="/resume/add" class="btn" style="background:var(--accent2);">➕ 创建简历</a>
        </div>"""
        return HTMLResponse(make_page("我的简历 - 武鸣招聘", content, "recruit",
                                      user={"nickname": user_info["nickname"]}))
    gender_age = ""
    if r["gender"] or r["age"]:
        parts = []
        if r["gender"]: parts.append(r["gender"])
        if r["age"]: parts.append(str(r["age"]) + "岁")
        gender_age = " · ".join(parts) + " · "
    details = f'<div style="font-size:13px;margin-bottom:6px;"><b>📞 联系方式</b>：{r["phone"]}'
    if r["wechat"]: details += f' / {r["wechat"]}'
    details += "</div>"
    for label, key, icon in [("🎯 期望岗位", "expected_job", "🎯"), ("💰 期望薪资", "expected_salary", "💰"),
                             ("💼 工作经历", "experience", "💼"), ("🔧 技能特长", "skills", "🔧"),
                             ("📝 自我介绍", "self_desc", "📝")]:
        if r[key]:
            details += f'<div style="font-size:13px;margin-bottom:6px;"><b>{icon} {label}</b>：{r[key]}</div>'
    from app import make_page
    content = f"""<div class='header'><h1>📄 我的简历</h1><div class="time"><a href="/resume/edit/{r['id']}" style="color:var(--text2);">✏️ 编辑</a></div></div>
    <div class="card">
        <div style="font-size:20px;font-weight:700;">{r["name"]}</div>
        <div style="font-size:13px;color:var(--text2);margin-top:4px;">{gender_age}{r["edu_level"] or "学历未填"}</div>
        <div style="border-top:1px solid var(--border);padding-top:10px;margin-top:10px;">{details}</div>
        <div style="font-size:11px;color:var(--text2);margin-top:10px;">创建：{r["created_at"][:16]} | 更新：{r["updated_at"][:16]}</div>
    </div>
    <div style="display:flex;gap:8px;margin-top:12px;">
        <a href="/notifications" style="flex:1;text-align:center;padding:12px;background:var(--card);border-radius:10px;border:1px solid var(--border);text-decoration:none;color:var(--text);">
            <div style="font-size:20px;">🔔</div><div style="font-size:12px;margin-top:4px;">通知中心</div></a>
        <a href="/push/settings" style="flex:1;text-align:center;padding:12px;background:var(--card);border-radius:10px;border:1px solid var(--border);text-decoration:none;color:var(--text);">
            <div style="font-size:20px;">⚙️</div><div style="font-size:12px;margin-top:4px;">推送设置</div></a>
    </div>"""
    return HTMLResponse(make_page("我的简历 - 武鸣招聘", content, "recruit",
                                  user={"nickname": user_info["nickname"]}))


@router.get("/resume/edit/{resume_id}", response_class=HTMLResponse)
async def resume_edit_form(request: Request, resume_id: int):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    user_info = get_user_info(uid)
    conn = get_recruit_db()
    r = conn.execute(
        "SELECT * FROM resumes WHERE id=? AND user_id=? AND is_active=1", (resume_id, uid)
    ).fetchone()
    conn.close()
    if not r:
        return HTMLResponse("<h2>简历不存在</h2>")
    form = _resume_form(r["name"], r["age"] or 0, r["gender"] or "", r["edu_level"] or "",
                        r["phone"], r["wechat"] or "", r["expected_job"] or "", r["expected_salary"] or "",
                        r["experience"] or "", r["skills"] or "", r["self_desc"] or "",
                        f"/resume/edit/{resume_id}")
    from app import make_page
    content = f"""<div class='header'><h1>✏️ 编辑简历</h1><div class="time"><a href="/resume/my" style="color:var(--text2);">← 返回</a></div></div>
    <div class="card">{form}</div>"""
    return HTMLResponse(make_page("编辑简历 - 武鸣招聘", content, "recruit",
                                  user={"nickname": user_info["nickname"]}))


@router.post("/resume/edit/{resume_id}", response_class=HTMLResponse)
async def resume_edit_submit(
    request: Request, resume_id: int,
    name: str = Form(...), age: int = Form(0), gender: str = Form(""),
    edu_level: str = Form(""), phone: str = Form(...), wechat: str = Form(""),
    expected_job: str = Form(""), expected_salary: str = Form(""),
    experience: str = Form(""), skills: str = Form(""), self_desc: str = Form("")
):
    uid = check_user(request)
    if not uid:
        return RedirectResponse(url="/user/login")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_recruit_db()
    conn.execute(
        "UPDATE resumes SET name=?, gender=?, age=?, phone=?, wechat=?, edu_level=?, "
        "experience=?, expected_job=?, expected_salary=?, skills=?, self_desc=?, updated_at=? "
        "WHERE id=? AND user_id=?",
        (name, gender, age, phone, wechat, edu_level, experience,
         expected_job, expected_salary, skills, self_desc, now, resume_id, uid)
    )
    conn.commit()
    conn.close()
    from app import make_page
    return HTMLResponse(make_page("修改成功",
        "<div class='header'><h1>✅ 修改成功</h1></div>"
        "<div style='text-align:center;margin:16px;'><a href='/resume/my' class='btn'>查看简历</a></div>",
        "recruit"))


@router.get("/resumes", response_class=HTMLResponse)
async def resume_list(request: Request, q: str = ""):
    """简历库 - 仅企业可访问"""
    ent = check_enterprise(request)
    if not ent:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    where = "WHERE r.is_active=1"
    params = []
    if q:
        where += " AND (r.name LIKE ? OR r.expected_job LIKE ? OR r.skills LIKE ? OR r.experience LIKE ?)"
        qp = f"%{q}%"
        params.extend([qp, qp, qp, qp])
    resumes = conn.execute(
        f"SELECT r.* FROM resumes r {where} ORDER BY r.is_pinned DESC, r.updated_at DESC LIMIT 50",
        params
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM resumes WHERE is_active=1").fetchone()[0]
    conn.close()
    from app import make_page
    resumes_html = ""
    for r in resumes:
        name_display = r["name"]
        extras = []
        if r["gender"]: extras.append(r["gender"])
        if r["age"]: extras.append(str(r["age"]) + "岁")
        ext = f' <span style="font-size:11px;color:var(--text2);">· {" · ".join(extras)}</span>' if extras else ""
        pinned = '<span class="tag" style="background:var(--yellow);color:#000;">📌 置顶</span>' if r["is_pinned"] else ""
        resumes_html += f"""<a href="/resume/{r['id']}" style="text-decoration:none;color:inherit;display:block;">
        <div class="job-card" style="border-left:3px solid {'var(--yellow)' if r['is_pinned'] else 'var(--accent2)'};">
            <div class="job-title">{name_display}{ext} {pinned}</div>
            <div class="job-meta">🎯 {r['expected_job'] or '未填'} | 💰 {r['expected_salary'] or '未填'}</div>
            <div class="job-desc">{r['experience'][:80] if r['experience'] else ''}</div>
        </div></a>"""
    content = f"""<div class="header"><h1>👥 简历库</h1><div class="time">共{total}份简历 | <a href="/enterprise/dashboard" style="color:var(--text2);font-size:11px;">← 控制台</a></div></div>
    <form action="/resumes" method="get" style="display:flex;gap:6px;margin-bottom:12px;">
        <input type="text" name="q" value="{q}" placeholder="搜索..." style="flex:1;background:var(--card2);border:1px solid var(--border);border-radius:8px;padding:10px;color:var(--text);font-size:14px;">
        <button type="submit" class="btn">搜索</button>
    </form>
    <div>{resumes_html or '<p style="text-align:center;padding:30px;">暂无简历</p>'}</div>"""
    return HTMLResponse(make_page("简历库 - 武鸣招聘", content, "recruit"))


@router.get("/resume/{resume_id}", response_class=HTMLResponse)
async def resume_detail(request: Request, resume_id: int):
    ent = check_enterprise(request)
    uid = check_user(request)
    if not ent and not uid:
        return RedirectResponse(url="/enterprise/login")
    conn = get_recruit_db()
    r = conn.execute(
        "SELECT * FROM resumes WHERE id=? AND is_active=1", (resume_id,)
    ).fetchone()
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
    if r["wechat"]: details += f" / {r['wechat']}"
    details += "</div>"
    for label, key, icon in [("🎯 期望岗位", "expected_job", "🎯"), ("💰 期望薪资", "expected_salary", "💰"),
                             ("💼 工作经历", "experience", "💼"), ("🔧 技能特长", "skills", "🔧"),
                             ("📝 自我介绍", "self_desc", "📝")]:
        if r[key]:
            details += f'<div style="font-size:14px;margin-bottom:10px;"><b>{label}</b><br>{r[key]}</div>'
    from app import make_page
    content = f"""<div class='header'><h1>📄 简历详情</h1><div class="time"><a href="/resumes" style="color:var(--text2);">← 返回简历库</a></div></div>
    <div class="card">
        <div style="font-size:22px;font-weight:700;">{r["name"]}</div>
        <div style="font-size:14px;color:var(--text2);margin-top:4px;">{gender_age}{r["edu_level"] or "学历未填"}</div>
        <div style="border-top:1px solid var(--border);padding-top:12px;margin-top:10px;">{details}</div>
        <div style="font-size:11px;color:var(--text2);margin-top:10px;">更新于 {r["updated_at"][:16]}</div>
    </div>"""
    return HTMLResponse(make_page(r["name"] + "的简历 - 武鸣招聘", content, "recruit"))
