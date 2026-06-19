"""
武鸣招聘平台 - 应用入口
FastAPI应用创建、路由注册、模板配置、启动事件
"""
import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings
from services.db import _ensure_indexes, get_recruit_db
from services.push import process_push_queue_worker

# ====== FastAPI应用 ======
app = FastAPI(title="武鸣招聘平台")

# ====== 静态文件 ======
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ====== 图片缓存目录服务 ======
IMAGE_CACHE_DIR = os.path.expanduser("~/.hermes/image_cache")
if os.path.isdir(IMAGE_CACHE_DIR):
    app.mount("/images", StaticFiles(directory=IMAGE_CACHE_DIR), name="image_cache")

# ====== Jinja2模板 ======
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.auto_reload = True

# 添加 Jinja2 缺失的内置函数
templates.env.globals["max"] = max
templates.env.globals["min"] = min
templates.env.globals["css_version"] = settings.CSS_VERSION


# ====== make_page 兼容函数（用于尚未完全模板化的页面） ======
def make_page(title: str, content: str, nav: str = "recruit",
              extra_css: str = "", user: dict = None,
              og_desc: str = "武鸣招聘 - 里建、东盟经开区本地招聘平台",
              json_ld: str = "") -> str:
    """生成完整HTML页面（兼容旧代码调用的f-string方式）"""
    user_bar = ""
    if user:
        user_bar = f"""
        <div class="hero-user">
            <span>👤 {user.get("nickname", "")}</span>
            <a href="/user/logout">退出</a>
        </div>"""
    else:
        user_bar = """
        <div class="hero-user">
            <a href="/account">登录 / 注册</a>
        </div>"""
    nav_links = [
        ("/", "🏭", "招聘", "recruit"),
        ("/ai-match", "🤖", "AI匹配", "aimatch"),
        ("/ai-chat", "💬", "AI问答", "aichat"),
        ("/feedback", "💬", "反馈", "feedback"),
    ]
    nav_html = ""
    for url, icon, text, key in nav_links:
        cls = ' class="active"' if key == nav else ""
        nav_html += f'<a href="{url}"{cls}><span class="nav-icon">{icon}</span>{text}</a>'
    my_label = "登录"
    notif_html = ""
    if user:
        my_label = "我的"
        notif_html = f'<a href="/notifications" style="position:relative;"><span class="nav-icon">🔔</span><span id="notifBadge" class="notif-badge"></span></a>'
    nav_html += notif_html + f'<a href="/my"><span class="nav-icon">👤</span>{my_label}</a>'

    css_path = f"/static/style.css?v={settings.CSS_VERSION}"
    css = open(os.path.join(STATIC_DIR, "style.css"), encoding="utf-8").read()
    js_src = f'<script src="/static/js/main.js?v={settings.CSS_VERSION}"></script>'

    return (
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>"
        + "<meta name='viewport' content='width=device-width,initial-scale=1.0'>"
        + "<meta name='description' content='武鸣招聘 - 里建、东盟经开区本地招聘平台，汇集食品厂、包装厂、电子厂等名企招聘信息，免费找工作，一键联系企业。'>"
        + "<meta name='keywords' content='武鸣招聘,里建招聘,东盟经开区招聘,武鸣找工作,里建找工作,武鸣招工,里建普工'>"
        + "<title>" + title + "</title>"
        + "<meta property='og:title' content='" + title.replace(chr(39), "&#39;") + "'>"
        + "<meta property='og:description' content='" + og_desc.replace(chr(39), "&#39;") + "'>"
        + "<meta property='og:type' content='website'>"
        + "<meta property='og:image' content='/static/wechat_qr.jpg'>"
        + "<meta name='theme-color' content='#E85D04'>"
        + "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        + "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        + "<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700;800&display=swap' rel='stylesheet'>"
        + "<meta name='x5-orientation' content='portrait'>"
        + "<meta name='x5-fullscreen' content='false'>"
        + "<meta name='x5-page-mode' content='app'>"
        + "<meta name='format-detection' content='telephone=yes'>"
        + "<style>"
        + "@media (prefers-color-scheme: dark) {:root{--bg:#1a1a2e;--bg-white:#16213e;--card2:#1a1a3e;--text:#e0e0f0;--text2:#a0a0b8;--text3:#707088;--border:#2a2a4e;--border2:#3a3a5e;}}"
        + "</style>"
        + "<link rel='icon' href='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏭</text></svg>'>"
        + (f'<script type="application/ld+json">{json_ld}</script>' if json_ld else "")
        + "<link rel='stylesheet' href='" + css_path + "'>"
        + js_src
        + "<script>(function(){var bp=document.createElement('script');var curProtocol=window.location.protocol.split(':')[0];if(curProtocol==='https'){bp.src='https://zz.bdstatic.com/linksubmit/push.js'}else{bp.src='http://push.zhanzhang.baidu.com/push.js'}var s=document.getElementsByTagName('script')[0];s.parentNode.insertBefore(bp,s)})();</script>"
        + "</head><body>"
        + "<div class='page'>" + content + "<nav class='nav'>" + nav_html + "</nav></div>"
        + "<button class='scroll-top' id='scrollTopBtn' onclick='window.scrollTo({top:0,behavior:\"smooth\"})'>↑</button>"
        + "<script>window.addEventListener('scroll',function(){var b=document.getElementById('scrollTopBtn');if(b)b.classList.toggle('visible',window.scrollY>400);});</script>"
        + "<script>if(document.getElementById('notifBadge')){fetch('/api/notifications/unread-count').then(r=>r.json()).then(d=>{var b=document.getElementById('notifBadge');if(b&&d.unread>0){b.textContent=d.unread;b.style.display='flex';}});}</script>"
        + "</body></html>"
    )


# ====== 数据库索引 ======
_ensure_indexes()


# ====== 启动事件 ======
@app.on_event("startup")
async def init_favorites():
    conn = get_recruit_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(user_id, job_id)
    )""")
    conn.commit()
    conn.close()


@app.on_event("startup")
async def start_push_worker():
    print("[PUSH-WORKER] 启动推送队列自动处理 worker...")
    asyncio.create_task(process_push_queue_worker())
    print("[PUSH-WORKER] Worker 已启动")


# ====== 注册路由 ======
from routes.seo import router as seo_router
from routes.public import router as public_router
from routes.admin import router as admin_router
from routes.user import router as user_router
from routes.enterprise import router as enterprise_router
from routes.chat import router as chat_router
from routes.ai import router as ai_router
from routes.resume import router as resume_router
from routes.feedback import router as feedback_router
from routes.api import router as api_router
from routes.government import router as government_router
from routes.matchmaker import router as matchmaker_router

app.include_router(seo_router)
app.include_router(public_router)
app.include_router(admin_router)
app.include_router(user_router)
app.include_router(enterprise_router)
app.include_router(chat_router)
app.include_router(ai_router)
app.include_router(resume_router)
app.include_router(feedback_router)
app.include_router(api_router, prefix="/api")
app.include_router(government_router)
app.include_router(matchmaker_router)

# ====== Let's Encrypt ACME Challenge ======
@app.get("/.well-known/acme-challenge/{filename}")
async def acme_challenge(filename: str):
    """Let's Encrypt ACME HTTP-01 challenge endpoint"""
    import os
    challenge_dir = "/var/www/html/.well-known/acme-challenge"
    challenge_file = os.path.join(challenge_dir, filename)
    if os.path.exists(challenge_file):
        with open(challenge_file, 'r') as f:
            content = f.read()
        return PlainTextResponse(content=content, media_type="text/plain")
    return PlainTextResponse(content="Not Found", status_code=404)
