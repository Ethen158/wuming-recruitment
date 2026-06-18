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
    BRAND_COLORS, BRAND_ICON, BRAND_LOGOS, TOP_COMPANIES, BENEFIT_MAP
)

def _short_name(cname):
    """生成短名：去掉省份/城市前缀，去掉有限公司等后缀"""
    name = cname
    # 去掉省份/城市前缀
    name = re.sub(r'^(?:广西|南宁[市]?|佛山[市]?|武鸣[区]?)+', '', name)
    # 去掉后缀
    name = name.replace("有限公司", "").replace("（李宁）", "").replace("（比亚迪）", "").strip()
    return name


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
        where += " AND created_at >= date('now', '-1 days')"
    elif t == "week":
        where += " AND created_at >= date('now', '-7 days')"
    elif t == "month":
        where += " AND created_at >= date('now', '-30 days')"

    all_matching = conn.execute(
        f"SELECT * FROM jobs {where} ORDER BY created_at DESC", params
    ).fetchall()
    total_match = len(all_matching)
    match_headcount = conn.execute(
        f"SELECT COALESCE(SUM(headcount), 0) FROM jobs {where}", params
    ).fetchone()[0]
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
    total_headcount = conn.execute("SELECT COALESCE(SUM(headcount), 0) FROM jobs WHERE status='active'").fetchone()[0]
    today_date = datetime.now().strftime("%Y-%m-%d")
    # 今日上新：最近1天内发布的岗位
    today_count = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('active','pending') AND created_at >= date('now', '-1 days')"
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

    # 构建JSON-LD结构化数据（Organization + LocalBusiness + JobPosting）
    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": "https://job.ailrabbit.cn/#organization",
                "name": "武鸣招聘",
                "url": "https://job.ailrabbit.cn",
                "logo": "https://job.ailrabbit.cn/static/logos/default.svg",
                "description": "武鸣招聘 - 里建、东盟经开区本地招聘平台，汇集食品厂、包装厂、电子厂等名企招聘信息",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "广西南宁市武鸣区东盟经济技术开发区",
                    "addressLocality": "南宁市",
                    "addressRegion": "广西",
                    "addressCountry": "CN"
                },
                "contactPoint": {
                    "@type": "ContactPoint",
                    "contactType": "customer service",
                    "areaServed": "CN",
                    "availableLanguage": "Chinese"
                }
            },
            {
                "@type": "LocalBusiness",
                "@id": "https://job.ailrabbit.cn/#localbusiness",
                "name": "武鸣招聘平台",
                "description": "武鸣本地招聘求职平台，覆盖里建、东盟经开区等区域",
                "url": "https://job.ailrabbit.cn",
                "areaServed": {
                    "@type": "GeoCircle",
                    "geoMidpoint": {
                        "@type": "GeoCoordinates",
                        "latitude": 23.2,
                        "longitude": 108.4
                    },
                    "geoRadius": "50000"
                },
                "priceRange": "Free"
            },
            {
                "@type": "WebSite",
                "@id": "https://job.ailrabbit.cn/#website",
                "name": "武鸣招聘",
                "url": "https://job.ailrabbit.cn",
                "description": "武鸣本地招聘求职平台",
                "inLanguage": "zh-CN",
                "publisher": {
                    "@id": "https://job.ailrabbit.cn/#organization"
                },
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": "https://job.ailrabbit.cn/?q={search_term_string}",
                    "query-input": "required name=search_term_string"
                }
            }
        ]
    }, ensure_ascii=False)

    # 导入logo工具（提前，供BYD和其他品牌使用）
    from services.company_logo import company_logo_html, _get_company_color, _get_company_char
    from models.schema import BRAND_COLORS, BRAND_LOGOS

    # 动态取前9大公司（按岗位数排序），但强制置顶比亚迪
    top9_raw = conn.execute("""
        SELECT company, COUNT(*) as cnt, COALESCE(SUM(headcount), 0) as hc
        FROM jobs
        WHERE status = 'active'
        GROUP BY company
        ORDER BY cnt DESC
        LIMIT 50
    """).fetchall()

    # 提取比亚迪相关公司（合并所有BYD变体）
    byd_jobs = []
    other_jobs = []
    byd_total = 0
    for r in top9_raw:
        if "比亚迪" in r["company"] or "BYD" in r["company"] or "弗迪" in r["company"]:
            byd_jobs.append(r)
            byd_total += r["cnt"]
        else:
            other_jobs.append(r)

    # 构建轮播图品牌列表：比亚迪置顶 + 其他公司
    brand_list = []

    # 比亚迪聚合卡片
    if byd_jobs:
        byd_short = "比亚迪"
        byd_char = _get_company_char(byd_short)
        byd_color = "#E30613"  # 比亚迪红色
        brand_list.append({
            "key": "__BYD__",
            "short_name": byd_short,
            "color": byd_color,
            "jobs": byd_total,
            "hc": sum(r["hc"] for r in byd_jobs),
            "char": byd_char,
            "byd_jobs": byd_jobs,  # 用于全部企业展开时展开所有BYD子公司
        })

    # 其余公司
    for r in other_jobs[:8]:
        cname = r["company"]
        short_name = _short_name(cname)
        char = _get_company_char(short_name)
        color = _get_company_color(cname)
        brand_list.append({
            "key": cname,
            "short_name": short_name,
            "color": color,
            "jobs": r["cnt"],
            "hc": r["hc"],
            "char": char,
        })

    # 获取全部公司列表（展开全部企业用）
    all_companies = conn.execute("""
        SELECT company, COUNT(*) as cnt, COALESCE(SUM(headcount), 0) as hc
        FROM jobs
        WHERE status = 'active'
        GROUP BY company
        ORDER BY cnt DESC
    """).fetchall()

    conn.close()

    # 为每个岗位添加Logo HTML
    job_list = []
    for j in jobs:
        row = dict(j)
        row["_logo_html"] = company_logo_html(j["company"], size=56)
        # 预计算logo_path和brand_color用于模板
        logo_path = "/static/logos/default.svg"
        brand_color = ""
        for keyword, color in BRAND_COLORS.items():
            if keyword in (j["company"] or ""):
                brand_color = color
                logo_path = BRAND_LOGOS.get(keyword, "/static/logos/default.svg")
                break
        row["logo_path"] = logo_path
        row["brand_color"] = brand_color
        if not brand_color:
            row["brand_color"] = list(BRAND_COLORS.values())[0] if BRAND_COLORS else "#999"
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

    # 全部公司列表（展开用）
    brand_full_list = []

    # 比亚迪聚合（所有BYD变体合并为一个入口）
    byd_subsidiaries = [r for r in all_companies if "比亚迪" in r["company"] or "BYD" in r["company"] or "弗迪" in r["company"]]
    if byd_subsidiaries:
        byd_sub_total = sum(r["cnt"] for r in byd_subsidiaries)
        byd_sub_hc = sum(r["hc"] for r in byd_subsidiaries)
        byd_sub_keys = [r["company"] for r in byd_subsidiaries]
        brand_full_list.append({
            "key": "__BYD_ALL__",
            "short_name": "比亚迪（聚合）",
            "color": "#E30613",
            "jobs": byd_sub_total,
            "hc": byd_sub_hc,
            "char": "BY",
            "byd_subsidiaries": byd_sub_keys,
        })

    for r in all_companies:
        cname = r["company"]
        short_name = _short_name(cname)
        char = _get_company_char(short_name)
        color = _get_company_color(cname)
        brand_full_list.append({
            "key": cname,
            "short_name": short_name,
            "color": color,
            "jobs": r["cnt"],
            "hc": r["hc"],
            "char": char,
        })

    # 渲染模板
    from app import templates
    return templates.TemplateResponse(
        request, "public/index.html", {
            "user_info": user_info,
            "now": now,
            "total_jobs": total_jobs,
            "total_headcount": total_headcount,
            "all_count": all_count,
            "total_match": total_match,
            "match_headcount": match_headcount,
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
            # 全部公司列表（展开用）
            "brand_full_list": brand_full_list,
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
    canonical_url = f"https://job.ailrabbit.cn/job/{job_id}"

    # JSON-LD 面包屑
    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": "https://job.ailrabbit.cn/"},
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

    # 特殊处理：比亚迪聚合页面
    is_byd = (name == "比亚迪" or name == "__BYD__")
    if is_byd:
        jobs_raw = list(conn.execute(
            """SELECT * FROM jobs WHERE status='active' AND (company LIKE '%比亚迪%' OR company LIKE '%BYD%' OR company LIKE '%弗迪%') ORDER BY created_at DESC"""
        ).fetchall())
        name = "比亚迪（聚合）"
    else:
        jobs_raw = list(conn.execute(
            "SELECT * FROM jobs WHERE company=? AND status='active' ORDER BY created_at DESC",
            (name,)
        ).fetchall())
    dt2 = datetime
    jobs = []
    for j in jobs_raw:
        row = dict(j)
        # 计算新标签
        try:
            ca = j["created_at"] or ""
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    job_date = datetime.strptime(ca, fmt)
                    break
                except ValueError:
                    continue
            else:
                job_date = None
            row["_today"] = (dt2.now() - job_date).days <= 2 if job_date else False
        except Exception:
            row["_today"] = False
        # logo
        logo_path = "/static/logos/default.svg"
        for keyword in BRAND_LOGOS:
            if keyword in (j["company"] or ""):
                logo_path = BRAND_LOGOS.get(keyword, "/static/logos/default.svg")
                break
        row["logo_path"] = logo_path
        from services.company_logo import company_logo_html
        row["_logo_html"] = company_logo_html(j["company"], size=56)
        jobs.append(row)

    count = len(jobs)

    # 统计数据
    try:
        company_info = conn.execute(
            "SELECT description FROM company_info WHERE company_name=?", (name,)
        ).fetchone()
        company_desc = _clean_company_desc(company_info["description"]) if company_info else ""
    except Exception:
        company_desc = ""

    # 行业类别
    categories = conn.execute(
        "SELECT DISTINCT category FROM jobs WHERE company=? AND category IS NOT NULL AND category != '' ORDER BY category",
        (name,)
    ).fetchall()
    categories = [r["category"] for r in categories]

    # 用工类型
    job_types = conn.execute(
        "SELECT DISTINCT job_type FROM jobs WHERE company=? AND job_type IS NOT NULL AND job_type != '' ORDER BY job_type",
        (name,)
    ).fetchall()
    job_types = [r["job_type"] for r in job_types]

    # 工作地点（去重，过滤纯福利性质的）
    locations = conn.execute(
        "SELECT DISTINCT location FROM jobs WHERE company=? AND location IS NOT NULL AND location != '' AND location NOT IN ('福利','包食宿','无夜班','全白班','提供食宿','食堂','五险','免费住宿','包工作餐','月休4天','法定节假日') ORDER BY location",
        (name,)
    ).fetchall()
    locations = [r["location"] for r in locations]

    # 总招聘人数
    total_headcount = conn.execute(
        "SELECT COALESCE(SUM(headcount), 0) FROM jobs WHERE company=? AND status='active' AND headcount IS NOT NULL",
        (name,)
    ).fetchone()[0]

    # 从岗位描述中提取企业简介（取最长的非岗位说明描述）
    company_intro = ""
    for j in jobs_raw:
        desc = j["description"] or ""
        if desc and len(desc) > 30:
            lines = desc.split("\n")
            # Skip lines that are job-specific
            intro_lines = []
            for line in lines[:8]:
                line = line.strip()
                if not line:
                    continue
                # Skip job-specific sections
                if any(line.startswith(p) for p in ["工作内容", "任职要求", "薪资", "岗位职责", "岗位职责", "职位要求"]):
                    continue
                # Skip short one-liner job titles like "招X人"
                if re.match(r'^招\d+人|^招.*\d+名$', line):
                    continue
                intro_lines.append(line)
            if intro_lines:
                intro = " ".join(intro_lines)
                if len(intro) > len(company_intro):
                    company_intro = intro[:500]

    conn.close()

    canonical_url = f"https://job.ailrabbit.cn/company/{urllib.parse.quote(name)}"

    from app import templates
    return templates.TemplateResponse(
        request, "public/company.html", {
            "name": name,
            "jobs": jobs,
            "count": count,
            "categories": categories,
            "job_types": job_types,
            "locations": locations,
            "total_headcount": total_headcount,
            "company_intro": company_intro,
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
