"""
公开页面路由 - 首页、岗位详情、企业主页、视频招聘、recruit重定向
"""
import json
import urllib.parse
import re
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Template

from services.db import get_recruit_db, get_salary_display, time_ago, _clean_company_desc
from services.auth import check_user, get_user_info, check_auth
from services.ai_engine import ai_match_jobs, format_match_results, find_matching_talents
from models.schema import (
    CATEGORY_MAP, MAJOR_CATEGORIES, get_major_cat,
    BRAND_COLORS, BRAND_ICON, TOP_COMPANIES, BENEFIT_MAP
)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def public_jobs(
    request: Request, q: str = "", mcat: str = "", cat: str = "",
    loc: str = "", jt: str = "", salary: str = "", t: str = "", page: int = 1
):
    """公开招聘首页"""
    uid = check_user(request) or (check_auth(request) and "admin")
    user_info = get_user_info(uid) if uid and uid != "admin" else None
    conn = get_recruit_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    where = "WHERE status IN ('active','pending')"
    params = []

    if mcat:
        raw_cats = [rc for rc, mc in CATEGORY_MAP.items() if mc == mcat or mc.startswith(mcat)]
        if raw_cats:
            placeholders = ",".join(["?"] * len(raw_cats))
            where += f" AND category IN ({placeholders})"
            params.extend(raw_cats)

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
    if t == "new" or t == "today":
        where += " AND created_at >= date('now', '-2 days')"
    elif t == "week":
        where += " AND created_at >= date('now', '-7 days')"
    elif t == "month":
        where += " AND created_at >= date('now', '-30 days')"

    all_matching = conn.execute(
        f"SELECT * FROM jobs {where} ORDER BY created_at DESC", params
    ).fetchall()
    total_match = len(all_matching)
    categories = [
        r["category"] for r in conn.execute(
            "SELECT DISTINCT category FROM jobs WHERE status IN ('active','pending') ORDER BY category"
        ).fetchall()
    ]
    locations = [
        r["location"] for r in conn.execute(
            "SELECT DISTINCT location FROM jobs WHERE status='active' AND location != '' ORDER BY location"
        ).fetchall()
    ]
    job_types = [
        r["job_type"] for r in conn.execute(
            "SELECT DISTINCT job_type FROM jobs WHERE status='active' AND job_type != '' ORDER BY job_type"
        ).fetchall()
    ]
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='active'").fetchone()[0]
    today_date = datetime.now().strftime("%Y-%m-%d")
    # 今日上新：最近2天内发布的岗位
    today_count = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('active','pending') AND created_at >= date('now', '-2 days')"
    ).fetchone()[0]
    week_count = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('active','pending') AND created_at >= date('now', '-7 days')"
    ).fetchone()[0]
    month_count = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('active','pending') AND created_at >= date('now', '-30 days')"
    ).fetchone()[0]

    PER_PAGE = 20
    if page < 1:
        page = 1
    total_pages = max(1, (total_match + PER_PAGE - 1) // PER_PAGE)
    if page > total_pages:
        page = total_pages
    jobs = all_matching[(page - 1) * PER_PAGE: page * PER_PAGE]

    # 统计每个大类的岗位数
    mcat_counts = {}
    for j in all_matching:
        mc = get_major_cat(j["category"])
        mcat_counts[mc] = mcat_counts.get(mc, 0) + 1

    all_count = total_jobs

    # 构建筛选和排序参数
    filter_params = {}
    if mcat:
        filter_params["mcat"] = mcat
    if cat:
        filter_params["cat"] = cat
    if loc:
        filter_params["loc"] = loc
    if jt:
        filter_params["jt"] = jt
    if q:
        filter_params["q"] = q
    if t:
        filter_params["t"] = t

    # 构建JSON-LD
    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "武鸣招聘 - 里建东盟经开区本地招聘平台",
        "description": "汇集食品厂、包装厂、电子厂等名企招聘信息，免费找工作，一键联系企业",
        "hiringOrganization": {"@type": "Organization", "name": "武鸣招聘"},
        "jobLocation": {"@type": "Place", "address": "广西南宁市武鸣区东盟经开区"},
    }, ensure_ascii=False)

    # 动态取前6大公司（按岗位数排序）
    top6 = conn.execute("""
        SELECT company, COUNT(*) as cnt
        FROM jobs
        WHERE status = 'active'
        GROUP BY company
        ORDER BY cnt DESC
        LIMIT 6
    """).fetchall()

    conn.close()

    # 为每个岗位添加Logo HTML
    from services.company_logo import company_logo_html, _get_company_color, _get_company_char
    job_list = []
    for j in jobs:
        row = dict(j)
        row["_logo_html"] = company_logo_html(j["company"], size=56)
        # 判断是否今日上新（2天内）
        if j["created_at"]:
            try:
                from datetime import datetime as dt2
                job_date = dt2.strptime(j["created_at"][:10], "%Y-%m-%d")
                row["_today"] = (dt2.now() - job_date).days <= 2
            except:
                row["_today"] = False
        else:
            row["_today"] = False
        job_list.append(row)

    brand_list = []
    for r in top6:
        cname = r["company"]
        char = _get_company_char(cname)
        color = _get_company_color(cname)
        # 短名用于显示（去掉"有限公司"等后缀）
        short_name = cname.replace("有限公司", "").replace("（李宁）", "").replace("（比亚迪）", "").strip()
        brand_list.append({
            "key": cname,
            "short_name": short_name,
            "color": color,
            "jobs": r["cnt"],
            "char": char,
        })

    # 渲染模板
    from app import templates
    return templates.TemplateResponse(
        request, "public/index.html", {
            "user_info": user_info,
            "now": now,
            "total_jobs": total_jobs,
            "all_count": all_count,
            "total_match": total_match,
            "total_pages": total_pages,
            "page": page,
            "jobs": job_list,
            "mcat": mcat,
            "cat": cat,
            "loc": loc,
            "jt": jt,
            "q": q,
            "salary": salary,
            "categories": categories,
            "locations": locations,
            "job_types": job_types,
            "mcat_counts": mcat_counts,
            "today_count": today_count,
            "today_date": today_date,
            "week_count": week_count,
            "month_count": month_count,
            "filter_params": filter_params,
            "json_ld": json_ld,
            "MAJOR_CATEGORIES": MAJOR_CATEGORIES,
            # 品牌大公司轮播数据
            "brand_companies": brand_list,
        }
    )


@router.get("/job/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: int):
    """岗位详情页"""
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    conn = get_recruit_db()
    j = conn.execute(
        "SELECT * FROM jobs WHERE id=? AND status='active'", (job_id,)
    ).fetchone()
    if not j:
        conn.close()
        return HTMLResponse("<h2>岗位不存在</h2><a href='/'>返回首页</a>")

    similar = conn.execute(
        "SELECT * FROM jobs WHERE id!=? AND status='active' AND (category=? OR company LIKE ?) LIMIT 3",
        (job_id, j["category"], f"%{j['company']}%")
    ).fetchall()
    conn.close()

    s_min = j['salary_min'] if j['salary_min'] else 0
    s_max = j['salary_max'] if j['salary_max'] else 0
    if s_min == 0 and s_max == 0:
        salary_plain = "面议"
    elif s_max:
        salary_plain = f"{s_min}-{s_max}{j['salary_unit']}"
    else:
        salary_plain = f"{s_min}{j['salary_unit']}"

    ta = time_ago(j["created_at"])
    share_phone = (j['contact_phone'] or '见详情') if user_info else '登录后可查看'

    desc_display = j['description'] or '暂无详细描述'
    if not user_info:
        desc_display = re.sub(r'(1[3-9]\d{9})', r'🔒\1****', desc_display)
        desc_display = re.sub(
            r'【联系电话[^】]*】\s*[^\n]*', '🔒 登录后可查看', desc_display
        )
        desc_display = re.sub(
            r'【联系电话/微信[^】]*】\s*[^\n]*', '🔒 登录后可查看', desc_display
        )

    og_desc = f"{j['company']}招{j['title']}，{salary_plain}，{j['location']}。武鸣招聘本地找工作平台。"
    canonical_url = f"https://job.airabbit.cn/job/{job_id}"

    # JSON-LD 面包屑
    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": "https://job.airabbit.cn/"},
            {"@type": "ListItem", "position": 2, "name": j["title"], "item": canonical_url}
        ]
    }, ensure_ascii=False)

    from app import templates
    return templates.TemplateResponse(
        request, "public/job_detail.html", {
            "job": j,
            "user_info": user_info,
            "similar": similar,
            "salary_plain": salary_plain,
            "ta": ta,
            "desc_display": desc_display,
            "og_desc": og_desc,
            "canonical_url": canonical_url,
            "json_ld": json_ld,
            "uid": uid,
        }
    )


@router.get("/company/{company_name}", response_class=HTMLResponse)
async def company_page(request: Request, company_name: str):
    """企业主页"""
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    conn = get_recruit_db()
    name = urllib.parse.unquote(company_name)
    jobs = conn.execute(
        "SELECT * FROM jobs WHERE company=? AND status='active' ORDER BY created_at DESC",
        (name,)
    ).fetchall()
    count = len(jobs)
    company_info = conn.execute(
        "SELECT description FROM company_info WHERE company_name=?", (name,)
    ).fetchone()
    conn.close()
    company_desc = _clean_company_desc(company_info["description"]) if company_info else ""

    canonical_url = f"https://job.airabbit.cn/company/{urllib.parse.quote(name)}"

    from app import templates
    return templates.TemplateResponse(
        request, "public/company.html", {
            "name": name,
            "jobs": jobs,
            "count": count,
            "company_desc": company_desc,
            "user_info": user_info,
            "canonical_url": canonical_url,
        }
    )


@router.get("/recruit/video", response_class=HTMLResponse)
async def recruit_video(request: Request, cat: str = ""):
    """视频录制模式"""
    conn = get_recruit_db()
    where = "WHERE status IN ('active','pending')"
    params = []
    if cat:
        where += " AND category=?"
        params.append(cat)
    jobs = conn.execute(
        f"SELECT * FROM jobs {where} ORDER BY RANDOM() LIMIT 6", params
    ).fetchall()
    conn.close()

    now = datetime.now().strftime("%m月%d日")

    from app import templates
    return templates.TemplateResponse(
        request, "public/recruit_video.html", {
            "jobs": jobs,
            "cat": cat,
            "now": now,
        }
    )


@router.get("/recruit", response_class=HTMLResponse)
async def recruit_redirect(request: Request):
    """兼容旧链接"""
    if check_auth(request):
        return RedirectResponse(url="/admin")
    return RedirectResponse(url="/")
