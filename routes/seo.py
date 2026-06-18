"""
SEO路由 - Sitemap, robots.txt
"""
import os
import urllib.parse
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import Response

from services.db import get_recruit_db
from config import settings

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

router = APIRouter()


def _fmt_date(dt_str):
    """格式化日期为 YYYY-MM-DD，兼容多种格式"""
    if not dt_str:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        # 兼容 "2026-06-18 10:30:00" 和 "2026-06-18" 两种格式
        return datetime.strptime(dt_str[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return datetime.now().strftime("%Y-%m-%d")


@router.get("/sitemap.xml", response_class=Response)
async def sitemap():
    """生成Sitemap（HTTPS版本，动态更新）"""
    conn = get_recruit_db()

    # 首页
    now = _fmt_date(datetime.now().isoformat())
    site_url = settings.SITE_URL.rstrip("/")

    urls = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
            '        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"',
            '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
            f'  <url><loc>{site_url}/</loc><lastmod>{now}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>',
            f'  <url><loc>{site_url}/ai-match</loc><lastmod>{now}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>',
            f'  <url><loc>{site_url}/government-jobs</loc><lastmod>{now}</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>',
            f'  <url><loc>{site_url}/matchmaker</loc><lastmod>{now}</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>',
            f'  <url><loc>{site_url}/feedback</loc><lastmod>{now}</lastmod><changefreq>monthly</changefreq><priority>0.5</priority></url>',
            f'  <url><loc>{site_url}/account</loc><lastmod>{now}</lastmod><changefreq>monthly</changefreq><priority>0.3</priority></url>',
            f'  <url><loc>{site_url}/recruitment</loc><lastmod>{now}</lastmod><changefreq>monthly</changefreq><priority>0.3</priority></url>',
            ]

    # 岗位页面（最多500条，按更新时间排序）
    jobs = conn.execute(
        "SELECT id, title, company, created_at, "
        "(SELECT MAX(updated_at) FROM jobs WHERE status='active') AS latest_update "
        "FROM jobs WHERE status='active' ORDER BY created_at DESC LIMIT 500"
    ).fetchall()
    for j in jobs:
        d = _fmt_date(j["created_at"])
        urls.append(
            f'  <url><loc>{site_url}/job/{j["id"]}</loc><lastmod>{d}</lastmod>'
            f'<changefreq>monthly</changefreq><priority>0.6</priority></url>'
        )

    # 公司页面（最多200家）
    companies = conn.execute(
        "SELECT DISTINCT company FROM jobs WHERE status='active' LIMIT 200"
    ).fetchall()
    for c in companies:
        urls.append(
            f'  <url><loc>{site_url}/company/{urllib.parse.quote(c["company"])}</loc>'
            f'<lastmod>{now}</lastmod><changefreq>weekly</changefreq><priority>0.5</priority></url>'
        )

    urls.append('</urlset>')
    conn.close()
    return Response("\n".join(urls), media_type="application/xml")


@router.get("/robots.txt", response_class=Response)
async def robots():
    """Robots.txt"""
    robots_path = os.path.join(STATIC_DIR, "robots.txt")
    content = open(robots_path, encoding="utf-8").read()
    return Response(content, media_type="text/plain")
