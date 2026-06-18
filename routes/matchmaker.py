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


# 征婚头像照片池 - 亚洲/中国面孔真人照片
# 使用 Unsplash 免费肖像 + randomuser.me 中国(nat=cn)人物肖像
MALE_AVATARS = [
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&h=200&fit=crop&crop=faces",
    "https://randomuser.me/api/portraits/men/39.jpg",
    "https://randomuser.me/api/portraits/men/88.jpg",
    "https://randomuser.me/api/portraits/men/60.jpg",
    "https://randomuser.me/api/portraits/men/91.jpg",
]

FEMALE_AVATARS = [
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=200&h=200&fit=crop&crop=faces",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&h=200&fit=crop&crop=faces",
    "https://images.unsplash.com/photo-1548142813-c348350df52b?w=200&h=200&fit=crop&crop=faces",
    "https://images.unsplash.com/photo-1525875975471-999f65706a10?w=200&h=200&fit=crop&crop=faces",
    "https://images.unsplash.com/photo-1502823403499-6ccfcf4fb453?w=200&h=200&fit=crop&crop=faces",
]


def get_avatar_url(gender: str, item_id: int) -> str:
    """根据性别和ID从头像池中选取一张"""
    if gender == "男":
        return MALE_AVATARS[item_id % len(MALE_AVATARS)]
    else:
        return FEMALE_AVATARS[item_id % len(FEMALE_AVATARS)]


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

    # Build card HTML with photo avatars
    cards = ""
    for item in items:
        gid = item["id"]
        g = item["gender"]
        a = item["age"]
        c = item["city"]
        h = item["height"] or ""
        e = item["education"] or ""
        o = item["occupation"] or ""
        avatar_url = get_avatar_url(g, gid)
        cards += '<a href="/matchmaker/' + str(gid) + '" class="match-card">' + chr(10)
        cards += '<div class="match-avatar ' + g + '">' + chr(10)
        cards += '<img src="' + avatar_url + '" alt="" loading="lazy">' + chr(10)
        cards += '<div class="avatar-overlay">' + (chr(9794) if g == "男" else chr(9792)) + '</div>' + chr(10)
        cards += '</div>' + chr(10)
        cards += '<div>' + chr(10)
        cards += '<div class="match-name">' + str(a) + '岁 · ' + c + '</div>' + chr(10)
        cards += '<div class="match-meta">' + h + ' · ' + e + ' · ' + o + '</div>' + chr(10)
        cards += '<div class="match-intro">' + str(item.get("habits", "")) + '</div>' + chr(10)
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
.match-hero{background:linear-gradient(135deg,#FF8A65,#E65100);padding:30px 16px 24px;text-align:center;border-radius:0 0 16px 16px;margin-bottom:12px}
.match-hero h1{font-size:24px;font-weight:800;color:#fff;margin:0 0 6px}
.match-hero p{font-size:13px;color:rgba(255,255,255,.9);margin:0}
.match-filter-btn{display:inline-block;padding:6px 14px;border-radius:20px;border:1px solid var(--border);background:#fff;font-size:13px;color:var(--text);text-decoration:none;margin:0 6px 10px;transition:all .2s}
.match-filter-btn.active{background:#E65100;color:#fff;border-color:#E65100}
.match-card{background:#fff;border-radius:12px;padding:14px;margin:0 12px 10px;box-shadow:0 1px 4px rgba(0,0,0,.06);display:flex;gap:12px;text-decoration:none;color:inherit;transition:transform .15s}
.match-card:active{transform:scale(.98)}
.match-avatar{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;position:relative;overflow:hidden;border:2px solid rgba(255,255,255,.8);box-shadow:0 2px 8px rgba(0,0,0,.12)}
.match-avatar img{width:100%;height:100%;object-fit:cover;position:absolute;top:0;left:0}
.match-avatar.male{border-color:rgba(255,138,101,.6)}
.match-avatar.female{border-color:rgba(244,143,177,.6)}
.avatar-overlay{position:absolute;bottom:0;left:0;right:0;height:28px;background:linear-gradient(transparent,rgba(0,0,0,.4));display:flex;align-items:flex-end;justify-content:center;font-size:14px;z-index:1}
.match-name{font-size:15px;font-weight:700;color:var(--text)}
.match-meta{font-size:12px;color:var(--text2);margin:2px 0}
.match-intro{font-size:13px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.btn-post-match{display:block;margin:12px;padding:12px;background:linear-gradient(135deg,#FF8A65,#E65100);color:#fff;text-align:center;border-radius:12px;font-size:15px;font-weight:700;text-decoration:none;transition:transform .15s}
.btn-post-match:active{transform:scale(.97)}
.pagination{display:flex;justify-content:center;gap:8px;padding:12px}
.pagination a{padding:6px 12px;border-radius:8px;font-size:13px;text-decoration:none;background:#fff;color:var(--text);border:1px solid var(--border)}
.pagination span{padding:6px 12px;border-radius:8px;font-size:13px;background:#E65100;color:#fff}
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

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>发布征婚信息 - 武鸣征婚</title>
<link rel="stylesheet" href="/static/style.css?v=20260614c">
<style>
.form-card{background:#fff;border-radius:12px;margin:12px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.form-group{margin-bottom:14px}
.form-group label{display:block;font-size:13px;font-weight:600;color:var(--text);margin-bottom:6px}
.form-group input,.form-group select,.form-group textarea{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:8px;font-size:14px;box-sizing:border-box}
.form-group textarea{min-height:80px;resize:vertical}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.btn-submit{display:block;width:100%;padding:12px;background:linear-gradient(135deg,#FF8A65,#E65100);color:#fff;border:none;border-radius:12px;font-size:16px;font-weight:700;cursor:pointer;margin:16px 12px;transition:transform .15s}
.btn-submit:active{transform:scale(.97)}
.btn-back{display:block;margin:0 12px 12px;padding:10px;background:#fff;color:var(--text);text-align:center;border-radius:12px;font-size:14px;text-decoration:none;border:1px solid var(--border)}
.error-msg{background:#FFF3E0;color:#E65100;padding:10px;border-radius:8px;margin:12px;font-size:14px;text-align:center}
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
<h2 style="font-size:18px;margin:0 0 16px">✍️ 发布征婚信息</h2>
<form action="/matchmaker/submit" method="post">
"""

    error_msg = request.query_params.get("error", "")
    if error_msg == "phone":
        html += '<div class="error-msg">⚠️ 请填写正确的手机号码</div>'

    fields = [
        ("姓名/昵称", "name", "text", "请输入您的称呼"),
        ("性别", "gender", "select", "", [("男", "男"), ("女", "女")]),
        ("年龄", "age", "number", "例如: 28"),
        ("身高(cm)", "height", "text", "例如: 170cm"),
        ("体重(kg)", "weight", "text", "例如: 65kg"),
        ("学历", "education", "select", "", [("初中", "初中"), ("高中/中专", "高中/中专"), ("大专", "大专"), ("本科", "本科"), ("硕士", "硕士"), ("博士", "博士")]),
        ("职业", "occupation", "text", "例如: 教师"),
        ("年收入", "income", "text", "例如: 5-8万"),
        ("房产", "housing", "select", "", [("无", "无"), ("有房无贷", "有房无贷"), ("有房有贷", "有房有贷"), ("有房有车", "有房有车")]),
        ("车辆", "car", "select", "", [("无", "无"), ("有车", "有车")]),
        ("城市/地区", "city", "select", "", [("武鸣区", "武鸣区"), ("里建", "里建"), ("东盟经开区", "东盟经开区"), ("南宁", "南宁")]),
        ("是否独生", "is_only_child", "select", "", [("是", "on"), ("否", "off")]),
        ("家庭情况", "family_intro", "textarea", "例如: 父母务农，有25亩果地"),
        ("个人特质", "habits", "textarea", "例如: 不抽烟少喝酒，性格温和"),
        ("择偶要求", "mate_expect", "textarea", "例如: 1997年后出生，未婚女孩"),
        ("联系电话", "contact", "tel", "请填写手机号"),
    ]

    for label, name, ftype, placeholder, *extra in fields:
        html += '<div class="form-group"><label>' + label + '</label>'
        if ftype == "select":
            opts = extra[0]
            html += '<select name="' + name + '">'
            for val, opt_val in opts:
                html += '<option value="' + opt_val + '">' + val + '</option>'
            html += '</select>'
        elif ftype == "textarea":
            html += '<textarea name="' + name + '" placeholder="' + placeholder + '"></textarea>'
        else:
            html += '<input type="' + ftype + '" name="' + name + '" placeholder="' + placeholder + '" required>'
        html += '</div>\n'

    html += """<button type="submit" class="btn-submit">📤 提交发布</button>
</form>
<a href="/matchmaker" class="btn-back">← 返回列表</a>
</div>
</body></html>"""
    return HTMLResponse(html)


@router.post("/matchmaker/submit", name="matchmaker_submit")
async def matchmaker_submit(request: Request,
                            name: str = Form(...),
                            gender: str = Form(...),
                            age: int = Form(...),
                            height: str = Form(""),
                            weight: str = Form(""),
                            education: str = Form(""),
                            occupation: str = Form(""),
                            income: str = Form(""),
                            housing: str = Form(""),
                            car: str = Form(""),
                            city: str = Form(""),
                            is_only_child: str = Form("off"),
                            family_intro: str = Form(""),
                            habits: str = Form(""),
                            mate_expect: str = Form(""),
                            contact: str = Form("")):

    if not _validate_phone(contact):
        return RedirectResponse(url="/matchmaker/post?error=phone", status_code=302)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_recruit_db()
    conn.row_factory = sqlite3.Row

    # Check if this matchmaker phone already has records
    existing = conn.execute("SELECT COUNT(*) as cnt FROM personals WHERE contact = ?", (contact,)).fetchone()["cnt"]
    status = "active" if existing == 0 else "hidden"

    conn.execute(
        """INSERT INTO personals (name, gender, birth_year, age, height, weight, education,
           occupation, income, housing, car, city, is_only_child, family_intro, habits,
           mate_expect, contact, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, gender, "", age, height, weight, education, occupation, income,
         housing, car, city, is_only_child, family_intro, habits,
         mate_expect, contact, status, now_str)
    )
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

    avatar_url = get_avatar_url(item["gender"], item["id"])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{item["age"]}岁{item["gender"]} - 征婚详情</title>
<link rel="stylesheet" href="/static/style.css?v=20260614c">
<style>
.detail-card{{background:#fff;border-radius:12px;margin:12px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.detail-header{{display:flex;align-items:center;gap:12px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border)}}
.detail-avatar{{width:72px;height:72px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;position:relative;overflow:hidden;border:2px solid rgba(255,255,255,.8);box-shadow:0 2px 8px rgba(0,0,0,.12)}}
.detail-avatar img{{width:100%;height:100%;object-fit:cover;position:absolute;top:0;left:0}}
.detail-avatar.male{{border-color:rgba(255,138,101,.6)}}
.detail-avatar.female{{border-color:rgba(244,143,177,.6)}}
.detail-name{{font-size:18px;font-weight:700}}
.detail-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.detail-grid-item{{background:#fafafa;padding:8px 10px;border-radius:8px;font-size:13px}}
.detail-grid-item label{{display:block;color:var(--text2);font-size:11px;margin-bottom:2px}}
.detail-section{{margin-bottom:14px}}
.detail-section-title{{font-size:14px;font-weight:700;margin-bottom:6px;padding-left:8px;border-left:3px solid #E65100}}
.detail-text{{font-size:14px;line-height:1.6;padding-left:8px}}
.detail-contact{{background:linear-gradient(135deg,#FFF3E0,#FFE0B2);border-radius:12px;padding:14px;margin:16px 12px;text-align:center}}
.detail-contact-title{{font-size:14px;font-weight:700;color:#E65100;margin-bottom:6px}}
.detail-contact-phone{{font-size:20px;font-weight:800;letter-spacing:1px}}
.btn-back{{display:block;margin:0 12px 12px;padding:10px;background:#fff;color:var(--text);text-align:center;border-radius:12px;font-size:14px;text-decoration:none;border:1px solid var(--border)}}
.recommend-section{{margin:12px}}
.recommend-title{{font-size:14px;font-weight:700;color:var(--text);margin-bottom:8px}}
.recommend-card{{background:#fff;border-radius:10px;padding:12px;margin-bottom:8px;box-shadow:0 1px 4px rgba(0,0,0,.06);display:flex;gap:10px;text-decoration:none;color:inherit;transition:transform .15s}}
.recommend-card:active{{transform:scale(.98)}}
.recommend-avatar{{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;position:relative;overflow:hidden;border:2px solid rgba(255,255,255,.8);box-shadow:0 2px 8px rgba(0,0,0,.12)}}
.recommend-avatar img{{width:100%;height:100%;object-fit:cover;position:absolute;top:0;left:0}}
.recommend-avatar.male{{border-color:rgba(255,138,101,.6)}}
.recommend-avatar.female{{border-color:rgba(244,143,177,.6)}}
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
<div class="detail-avatar {item["gender"]}">
<img src="{avatar_url}" alt="" loading="lazy">
<div class="avatar-overlay">{chr(9794) if item["gender"] == "男" else chr(9792)}</div>
</div>
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
<div class="detail-grid-item"><label>是否独生</label>{'是' if item["is_only_child"]=='on' else '否'}</div>
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
