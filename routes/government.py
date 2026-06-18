"""
政务招聘路由 - 公务员/事业单位招聘板块
"""
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Template

from services.db import get_recruit_db, time_ago
from services.auth import check_user, get_user_info

router = APIRouter()


@router.get("/government-jobs", response_class=HTMLResponse)
async def government_jobs(request: Request, cat: str = "", q: str = ""):
    """政务招聘板块"""
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    conn = get_recruit_db()

    # 构建查询条件
    conditions = ["status='active'"]
    params = []
    if cat:
        conditions.append("edu_level LIKE ?")
        params.append(f"%{cat}%")
    if q:
        conditions.append("(title LIKE ? OR company LIKE ? OR description LIKE ? OR department LIKE ?)")
        like_q = f"%{q}%"
        params.extend([like_q, like_q, like_q, like_q])

    where_clause = " AND ".join(conditions)
    query = f"SELECT * FROM gov_recruitments WHERE {where_clause} ORDER BY job_code ASC"

    jobs = conn.execute(query, params).fetchall()

    # 获取所有学历分类
    edu_levels = conn.execute(
        "SELECT DISTINCT edu_level FROM gov_recruitments WHERE status='active' ORDER BY edu_level"
    ).fetchall()

    # 获取所有单位
    units = conn.execute(
        "SELECT DISTINCT company FROM gov_recruitments WHERE status='active' ORDER BY company"
    ).fetchall()

    total = len(jobs)
    conn.close()

    # 构建JSON-LD
    import json as json_module
    json_ld = json_module.dumps({
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "武鸣招聘-政务招聘",
        "itemListElement": [{
            "@type": "ListItem",
            "position": i + 1,
            "item": {
                "@type": "JobPosting",
                "title": dict(j)["title"],
                "hiringOrganization": {"@type": "Organization", "name": dict(j)["company"]},
                "jobLocation": {"@type": "Place", "address": dict(j).get("address", "广西")},
                "employmentType": "FULL_TIME",
            }
        } for i, j in enumerate(jobs[:5])],
    }, ensure_ascii=False)

    from app import templates
    return templates.TemplateResponse(
        request, "public/government_jobs.html", {
            "jobs": jobs,
            "user_info": user_info,
            "total": total,
            "edu_levels": [e["edu_level"] for e in edu_levels],
            "units": [u["company"] for u in units],
            "current_cat": cat,
            "current_q": q,
            "json_ld": json_ld,
        }
    )


@router.get("/government-jobs/{job_id}", response_class=HTMLResponse)
async def government_job_detail(request: Request, job_id: int):
    """政务岗位详情页"""
    uid = check_user(request)
    user_info = get_user_info(uid) if uid else None
    conn = get_recruit_db()
    j = conn.execute(
        "SELECT * FROM gov_recruitments WHERE id=? AND status='active'", (job_id,)
    ).fetchone()
    if not j:
        conn.close()
        return HTMLResponse("<h2>岗位不存在</h2><a href='/government-jobs'>返回政务招聘</a>")

    from app import templates
    return templates.TemplateResponse(
        request, "public/government_job_detail.html", {
            "job": dict(j),
            "user_info": user_info,
        }
    )
