"""
SEO路由 - Sitemap, robots.txt
"""
import os
import urllib.parse
from fastapi import APIRouter
from fastapi.responses import Response

from services.db import get_recruit_db
from config import settings

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

router = APIRouter()


@router.get("/sitemap.xml", response_class=Response)
async def sitemap():
    """生成Sitemap（HTTPS版本）"""
    conn = get_recruit_db()
    jobs = conn.execute(
        "SELECT id, title, company, created_at FROM jobs WHERE status='active' ORDER BY created_at DESC LIMIT 500"
    ).fetchall()
    companies = conn.execute(
        "SELECT DISTINCT company FROM jobs WHERE status='active'"
    ).fetchall()
    conn.close()

    site_url = settings.SITE_URL.rstrip("/")
    urls = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    urls.append(f'  <url><loc>{site_url}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>')
    urls.append(f'  <url><loc>{site_url}/ai-match</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    for j in jobs:
        d = j["created_at"][:10] if j["created_at"] else "2026-01-01"
        urls.append(
            f'  <url><loc>{site_url}/job/{j["id"]}</loc><lastmod>{d}</lastmod>'
            f'<changefreq>monthly</changefreq><priority>0.6</priority></url>'
        )
    for c in companies:
        urls.append(
            f'  <url><loc>{site_url}/company/{urllib.parse.quote(c["company"])}</loc>'
            f'<changefreq>weekly</changefreq><priority>0.5</priority></url>'
        )
    urls.append('</urlset>')
    return Response("\n".join(urls), media_type="application/xml")


@router.get("/robots.txt", response_class=Response)
async def robots():
    """Robots.txt"""
    robots_path = os.path.join(STATIC_DIR, "robots.txt")
    content = open(robots_path, encoding="utf-8").read()
    return Response(content, media_type="text/plain")
