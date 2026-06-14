"""征婚功能路由"""
import re
import sqlite3
from datetime import datetime
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from services.db import get_recruit_db
from services.auth import check_user, get_user_info

router = APIRouter()


def _validate_phone(phone: str) -> bool:
    return bool(re.match(r'^1[3-9]\d{9}$', phone.strip()))


@router.get("/matchmaker", name="matchmaker")
async def matchmaker_list(request: Request, gender: str = "", page: int = 1):
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None

    conn = get_recruit_db()
    conn.row_factory = sqlite3.Row

    where = "WHERE status = 'active'"
    params = []
    if gender:
        where += " AND gender = ?"
        params.append(gender)

    count = conn.execute(f"SELECT COUNT(*) as cnt FROM personals {where}", params).fetchone()["cnt"]
    total_pages = max(1, (count + 9) // 10)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * 10

    rows = conn.execute(f"SELECT * FROM personals {where} ORDER BY created_at DESC LIMIT 10 OFFSET {offset}", params).fetchall()
    items = [dict(r) for r in rows]
    conn.close()

    # Build card HTML
    cards = ""
    for item in items:
        gid = item["id"]
        g = item["gender"]
        gc = chr(128121) if g == "男" else chr(128118)
        a = item["age"]
        c = item["city"]
        h = item["height"]
        e = item["education"]
        o = item["occupation"]
        intro = item["intro"]
        cards += '<a href="/matchmaker/' + str(gid) + '" class="match-card">' + chr(10)
        cards += '<div class="match-avatar ' + g + '">' + gc + '</div>' + chr(10)
        cards += '<div>' + chr(10)
        cards += '<div class="match-name">' + str(a) + '岁 · ' + c + '</div>' + chr(10)
        cards += '<div class="match-meta">' + h + ' · ' + e + ' · ' + o + '</div>' + chr(10)
        cards += '<div class="match-intro">' + intro + '</div>' + chr(10)
        cards += '</div>' + chr(10)
        cards += '</a>' + chr(10)

    gender_active = lambda g: ' active' if gender == g else ''
    pager = ""
    if total_pages > 1:
        prev_url = '/matchmaker?page=' + str(page-1) + ('&amp;gender=' + gender if gender else '')
        next_url = '/matchmaker?page=' + str(page+1) + ('&amp;gender=' + gender if gender else '')
        prev_link = '<a href="' + prev_url + '">‹ 上一页</a>' if page > 1 else ''
        next_link = '<a href="' + next_url + '">下一页 ›</a>' if page < total_pages else ''
        pager = '<div class="pagination">' + prev_link + '<span>第 ' + str(page) + ' / ' + str(total_pages) + ' 页</span>' + next_link + '</div>'


    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title>武鸣征婚 - 找对象</title>
<link rel="stylesheet" href="/static/style.css?v=20260614c">
<style>
.match-hero{background:linear-gradient(135deg,#FF6B6B,#E30613);padding:30px 16px 24px;text-align:center;border-radius:0 0 16px 16px;margin-bottom:12px}
.match-hero h1{font-size:24px;font-weight:800;color:#fff;margin:0 0 6px}
.match-hero p{font-size:13px;color:rgba(255,255,255,.9);margin:0}
.match-filter-btn{display:inline-block;padding:6px 14px;border-radius:20px;border:1px solid var(--border);background:#fff;font-size:13px;color:var(--text);text-decoration:none;margin:0 6px 10px;transition:all .2s}
.match-filter-btn.active{background:#E30613;color:#fff;border-color:#E30613}
.match-card{background:#fff;border-radius:12px;padding:14px;margin:0 12px 10px;box-shadow:0 1px 4px rgba(0,0,0,.06);display:flex;gap:12px;text-decoration:none;color:inherit;transition:transform .15s}
.match-card:active{transform:scale(.98)}
.match-avatar{width:60px;height:60px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:28px;flex-shrink:0}
.match-avatar.male{background:linear-gradient(135deg,#4A90D9,#357ABD)}
.match-avatar.female{background:linear-gradient(135deg,#FF6B9D,#E30613)}
.match-name{font-size:15px;font-weight:700;color:var(--text)}
.match-meta{font-size:12px;color:var(--text2);margin:2px 0}
.match-intro{font-size:13px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.btn-post-match{display:block;margin:12px;padding:12px;background:linear-gradient(135deg,#FF6B6B,#E30613);color:#fff;text-align:center;border-radius:12px;font-size:15px;font-weight:700;text-decoration:none;transition:transform .15s}
.btn-post-match:active{transform:scale(.97)}
.pagination{display:flex;justify-content:center;gap:8px;padding:12px}
.pagination a{padding:6px 12px;border-radius:8px;font-size:13px;text-decoration:none;background:#fff;color:var(--text);border:1px solid var(--border)}
.pagination span{padding:6px 12px;border-radius:8px;font-size:13px;background:#E30613;color:#fff}
</style>
</head>
<body>
<nav class="nav">
<a href="/" class="recruit"><span class="nav-icon">🏭</span>招聘</a>
<a href="/ai-match"><span class="nav-icon">🤖</span>AI匹配</a>
<a href="/ai-chat"><span class="nav-icon">💬</span>AI问答</a>
<a href="/matchmaker" class="active"><span class="nav-icon">🌹</span>征婚</a>
<a href="/government-jobs"><span class="nav-icon">🏛️</span>政务</a>
<a href="/feedback"><span class="nav-icon">💬</span>反馈</a>
</nav>
<div class="match-hero">
<h1>🌹 武鸣征婚</h1>
<p>真实信息 · 本地交友 · 找对象</p>
</div>
<a href="/matchmaker/post" class="btn-post-match">✍️ 发布征婚信息</a>
<div style="padding:0 12px;margin-bottom:8px">
<a href="/matchmaker" class="match-filter-btn {% active1 %}">全部</a>
<a href="/matchmaker?gender=男" class="match-filter-btn {% active2 %}">👨 男士</a>
<a href="/matchmaker?gender=女" class="match-filter-btn {% active3 %}">👩 女士</a>
</div>
"""
    html = html.replace("{% active1 %}", "active" if not gender else "")
    html = html.replace("{% active2 %}", "active" if gender == "男" else "")
    html = html.replace("{% active3 %}", "active" if gender == "女" else "")

    html += cards
    if not items:
        html += '<div style="text-align:center;padding:24px;color:var(--text2)">暂时还没有征婚信息，快来发布第一条吧！</div>'
    html += pager + "</body></html>"
    return HTMLResponse(html)


@router.get("/matchmaker/post", name="matchmaker_post")
async def matchmaker_post_page(request: Request):
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None

    if not user_info:
        html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>请先登录</title>
<link rel="stylesheet" href="/static/style.css?v=20260614c"></head>
<body>
<div style="padding:40px 20px;text-align:center">
<h2>请先登录</h2>
<p style="color:var(--text2);margin:12px 0">发布征婚信息需要登录</p>
<a href="/account" style="display:inline-block;padding:12px 24px;background:linear-gradient(135deg,#FF6B6B,#E30613);color:#fff;border-radius:12px;text-decoration:none;font-size:15px">去登录</a>
</div>
</body></html>"""
        return HTMLResponse(html)

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title>发布征婚信息</title>
<link rel="stylesheet" href="/static/style.css?v=20260614c">
<style>
.form-card{background:#fff;border-radius:12px;margin:12px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.form-title{font-size:18px;font-weight:700;text-align:center;margin-bottom:16px}
.form-group{margin-bottom:14px}
.form-label{display:block;font-size:13px;font-weight:600;margin-bottom:6px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.form-input,.form-select,.form-textarea{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:8px;font-size:14px;background:#fafafa;box-sizing:border-box}
.form-input:focus,.form-select:focus,.form-textarea:focus{outline:none;border-color:#E30613;background:#fff}
.form-textarea{min-height:80px;resize:vertical}
.form-section-title{font-size:15px;font-weight:700;margin:16px 0 10px;padding-left:8px;border-left:3px solid #E30613}
.btn-submit{display:block;margin:16px 12px;padding:14px;background:linear-gradient(135deg,#FF6B6B,#E30613);color:#fff;text-align:center;border-radius:12px;font-size:16px;font-weight:700;border:none;cursor:pointer}
.btn-submit:active{transform:scale(.97)}
.btn-back{display:block;margin:0 12px 12px;padding:10px;background:#fff;color:var(--text2);text-align:center;border-radius:12px;font-size:14px;text-decoration:none;border:1px solid var(--border)}
</style>
</head><body>
<nav class="nav">
<a href="/" class="recruit"><span class="nav-icon">🏭</span>招聘</a>
<a href="/ai-match"><span class="nav-icon">🤖</span>AI匹配</a>
<a href="/ai-chat"><span class="nav-icon">💬</span>AI问答</a>
<a href="/matchmaker" class="active"><span class="nav-icon">🌹</span>征婚</a>
<a href="/government-jobs"><span class="nav-icon">🏛️</span>政务</a>
<a href="/feedback"><span class="nav-icon">💬</span>反馈</a>
</nav>
<div class="form-card">
<div class="form-title">🌹 发布征婚信息</div>
<form action="/matchmaker/submit" method="post">
<div class="form-section-title">基本信息</div>
<div class="form-row">
<div class="form-group"><label class="form-label">性别 *</label>
<select name="gender" class="form-select" required><option value="男">男</option><option value="女">女</option></select></div>
<div class="form-group"><label class="form-label">所在城市</label>
<input type="text" name="city" class="form-input" placeholder="如：武鸣里建"></div>
</div>
<div class="form-row">
<div class="form-group"><label class="form-label">出生年份</label>
<input type="text" name="birth_year" class="form-input" placeholder="如：1998"></div>
<div class="form-group"><label class="form-label">年龄</label>
<input type="text" name="age" class="form-input" placeholder="如：26"></div>
</div>
<div class="form-row">
<div class="form-group"><label class="form-label">身高</label>
<input type="text" name="height" class="form-input" placeholder="如：170cm"></div>
<div class="form-group"><label class="form-label">体重</label>
<input type="text" name="weight" class="form-input" placeholder="如：65公斤"></div>
</div>
<div class="form-section-title">教育与工作</div>
<div class="form-row">
<div class="form-group"><label class="form-label">学历</label>
<select name="education" class="form-select"><option value="">请选择</option><option>初中</option><option>中专</option><option>高中</option><option>大专</option><option>本科</option><option>硕士</option><option>博士</option></select></div>
<div class="form-group"><label class="form-label">职业</label>
<input type="text" name="occupation" class="form-input" placeholder="如：工厂工人"></div>
</div>
<div class="form-group"><label class="form-label">月收入</label>
<input type="text" name="income" class="form-input" placeholder="如：5000元/月"></div>
<div class="form-section-title">资产情况</div>
<div class="form-group"><label class="form-label">房产</label>
<input type="text" name="housing" class="form-input" placeholder="如：里建有房"></div>
<div class="form-row">
<div class="form-group"><label class="form-label">车辆</label>
<input type="text" name="car" class="form-input" placeholder="如：有车"></div>
<div class="form-group"><label class="form-label">是否独生子女</label>
<select name="is_only_child"><option value="on">是</option><option value="off">否</option></select></div>
</div>
<div class="form-section-title">家庭情况</div>
<div class="form-group"><label class="form-label">家庭介绍</label>
<textarea name="family_intro" class="form-textarea" placeholder="如：父母身体健康有退休金..."></textarea></div>
<div class="form-section-title">个人特质</div>
<div class="form-group"><label class="form-label">生活习惯</label>
<input type="text" name="habits" class="form-input" placeholder="如：不抽烟不喝酒，圈子干净"></div>
<div class="form-section-title">择偶要求</div>
<div class="form-group"><label class="form-label">希望另一半...</label>
<textarea name="mate_expect" class="form-textarea" placeholder="如：年龄25-30岁，身高1.55米以上..."></textarea></div>
<div class="form-section-title">联系方式</div>
<div class="form-group"><label class="form-label">联系电话/微信 *</label>
<input type="text" name="contact" class="form-input" placeholder="请输入手机号" required>
</div>
<button type="submit" class="btn-submit">🌹 提交发布</button>
<a href="/matchmaker" class="btn-back">返回列表</a>
</form>
</div>
</body></html>"""
    return HTMLResponse(html)


@router.post("/matchmaker/submit", name="matchmaker_submit")
async def matchmaker_submit(request: Request,
    gender: str = Form(...),
    birth_year: str = Form(""),
    age: str = Form(""),
    height: str = Form(""),
    weight: str = Form(""),
    education: str = Form(""),
    occupation: str = Form(""),
    income: str = Form(""),
    housing: str = Form(""),
    car: str = Form(""),
    family_intro: str = Form(""),
    habits: str = Form(""),
    mate_expect: str = Form(""),
    contact: str = Form(...),
    is_only_child: str = Form("off"),
    city: str = Form(""),
):
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None

    if not user_info:
        return RedirectResponse(url="/account", status_code=302)

    if not _validate_phone(contact):
        return RedirectResponse(url="/matchmaker/post?error=phone", status_code=302)

    conn = get_recruit_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        INSERT INTO personals (gender, birth_year, age, height, weight, education,
            occupation, income, housing, car, family_intro, habits,
            mate_expect, contact, is_only_child, user_id, status, city,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
    """, (
        gender, birth_year, age, height, weight, education,
        occupation, income, housing, car, family_intro, habits,
        mate_expect, contact, is_only_child,
        user_info["id"], city, now, now
    ))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/matchmaker", status_code=302)


@router.get("/matchmaker/{pid}", name="matchmaker_detail")
async def matchmaker_detail(request: Request, pid: int):
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None

    conn = get_recruit_db()
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT * FROM personals WHERE id = ? AND status = 'active'", (pid,)
    ).fetchone()

    if not row:
        conn.close()
        return HTMLResponse("<h2>征婚信息不存在</h2>", status_code=404)

    item = dict(row)

    others = conn.execute(
        "SELECT id, gender, age, height, city, occupation FROM personals WHERE id != ? AND gender = ? AND status = 'active' ORDER BY created_at DESC LIMIT 3",
        (pid, item["gender"])
    ).fetchall()
    others_list = [dict(o) for o in others]
    conn.close()

    gender_char = chr(128121) if item["gender"] == "男" else chr(128118)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{item["age"]}岁{item["gender"]} - 征婚详情</title>
<link rel="stylesheet" href="/static/style.css?v=20260614c">
<style>
.detail-card{{background:#fff;border-radius:12px;margin:12px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.detail-header{{display:flex;align-items:center;gap:12px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border)}}
.detail-avatar{{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:32px;flex-shrink:0}}
.detail-avatar.male{{background:linear-gradient(135deg,#4A90D9,#357ABD)}}
.detail-avatar.female{{background:linear-gradient(135deg,#FF6B9D,#E30613)}}
.detail-name{{font-size:18px;font-weight:700}}
.detail-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.detail-grid-item{{background:#fafafa;padding:8px 10px;border-radius:8px;font-size:13px}}
.detail-grid-item label{{display:block;color:var(--text2);font-size:11px;margin-bottom:2px}}
.detail-section{{margin-bottom:14px}}
.detail-section-title{{font-size:14px;font-weight:700;margin-bottom:6px;padding-left:8px;border-left:3px solid #E30613}}
.detail-text{{font-size:14px;line-height:1.6;padding-left:8px}}
.detail-contact{{background:linear-gradient(135deg,#FFF3E0,#FFE0B2);border-radius:12px;padding:14px;margin:16px 12px;text-align:center}}
.detail-contact-title{{font-size:14px;font-weight:700;color:#E30613;margin-bottom:6px}}
.detail-contact-phone{{font-size:20px;font-weight:800;letter-spacing:1px}}
.btn-back{{display:block;margin:0 12px 12px;padding:10px;background:#fff;color:var(--text);text-align:center;border-radius:12px;font-size:14px;text-decoration:none;border:1px solid var(--border)}}
</style>
</head><body>
<nav class="nav">
<a href="/" class="recruit"><span class="nav-icon">🏭</span>招聘</a>
<a href="/ai-match"><span class="nav-icon">🤖</span>AI匹配</a>
<a href="/ai-chat"><span class="nav-icon">💬</span>AI问答</a>
<a href="/matchmaker" class="active"><span class="nav-icon">🌹</span>征婚</a>
<a href="/government-jobs"><span class="nav-icon">🏛️</span>政务</a>
<a href="/feedback"><span class="nav-icon">💬</span>反馈</a>
</nav>
<div class="detail-card">
<div class="detail-header">
<div class="detail-avatar {item["gender"]}">{gender_char}</div>
<div>
<div class="detail-name">{item["gender"]} · {item["age"]}岁</div>
<div style="font-size:13px;color:var(--text2)">{item["city"]} · {item["education"]} · {item["occupation"]}</div>
</div>
</div>
<div class="detail-grid">
<div class="detail-grid-item"><label>身高</label>{item["height"]}</div>
{'<div class="detail-grid-item"><label>体重</label>' + item["weight"] + '</div>' if item["weight"] else ''}
<div class="detail-grid-item"><label>收入</label>{item["income"]}</div>
<div class="detail-grid-item"><label>房产</label>{item["housing"]}</div>
{'<div class="detail-grid-item"><label>车辆</label>' + item["car"] + '</div>' if item["car"] else ''}
<div class="detail-grid-item"><label>独生子女</label>{'是' if item["is_only_child"]=='on' else '否'}</div>
</div>
</div>
{'<div class="detail-card"><div class="detail-section"><div class="detail-section-title">家庭情况</div><div class="detail-text">' + item["family_intro"] + '</div></div></div>' if item["family_intro"] else ''}
{'<div class="detail-card"><div class="detail-section"><div class="detail-section-title">个人特质</div><div class="detail-text">' + item["habits"] + '</div></div></div>' if item["habits"] else ''}
{'<div class="detail-card"><div class="detail-section"><div class="detail-section-title">择偶要求</div><div class="detail-text">' + item["mate_expect"] + '</div></div></div>' if item["mate_expect"] else ''}
<div class="detail-contact">
<div class="detail-contact-title">📞 联系电话 / 微信</div>
<div class="detail-contact-phone">{item["contact"]}</div>
</div>
<a href="/matchmaker" class="btn-back">← 返回列表</a>
</body></html>"""
    return HTMLResponse(html)
