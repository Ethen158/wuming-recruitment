"""
反馈路由 - 反馈页面和提交API
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from services.db import get_recruit_db
from services.auth import check_user, check_auth, get_user_info

router = APIRouter()


@router.get("/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request):
    """反馈提交页面"""
    uid = check_user(request) or (check_auth(request) and "admin")
    user_info = get_user_info(uid) if uid and uid != "admin" else None
    from app import make_page
    content = """
    <div class='header'><h1>💬 建议反馈</h1>
        <div class='time'>你的意见帮助我们做得更好</div>
    </div>
    <div class="card">
        <form id="feedbackForm" style="display:flex;flex-direction:column;gap:12px;">
            <div>
                <label style="font-size:13px;color:var(--text2);display:block;margin-bottom:4px;">📝 你的建议 / 问题描述 *</label>
                <textarea name="content" id="fbContent" rows="5" required
                    style="width:100%;background:var(--card2);border:1px solid var(--border);border-radius:8px;
                           padding:12px;color:var(--text);font-size:14px;resize:vertical;"
                    placeholder="例如：希望增加某某公司的招聘信息、页面功能建议、遇到的bug……"></textarea>
            </div>
            <div>
                <label style="font-size:13px;color:var(--text2);display:block;margin-bottom:4px;">📞 联系方式（选填）</label>
                <input type="text" name="contact" id="fbContact"
                    style="width:100%;background:var(--card2);border:1px solid var(--border);border-radius:8px;
                           padding:10px 12px;color:var(--text);font-size:14px;" placeholder="微信 / 手机号">
            </div>
            <button type="submit" id="fbSubmit"
                style="background:linear-gradient(135deg,#6c5ce7,#a29bfe);border:none;border-radius:8px;
                       padding:14px 0;color:white;font-size:16px;font-weight:600;cursor:pointer;">
                💬 提交反馈
            </button>
        </form>
        <div id="fbSuccess" style="display:none;text-align:center;padding:20px 0;">
            <div style="font-size:48px;margin-bottom:12px;">✅</div>
            <div style="font-size:16px;font-weight:600;color:var(--green);">感谢你的反馈！</div>
            <a href="/" class="btn" style="display:inline-block;margin-top:16px;">← 返回首页</a>
        </div>
    </div>
    <script>
    document.getElementById('feedbackForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        var btn = document.getElementById('fbSubmit');
        btn.textContent = '⏳ 提交中...';
        btn.disabled = true;
        var data = {
            content: document.getElementById('fbContent').value,
            contact: document.getElementById('fbContact').value,
            page: window.location.pathname
        };
        try {
            var resp = await fetch('/api/feedback', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) });
            var result = await resp.json();
            if (result.ok) {
                document.getElementById('feedbackForm').style.display = 'none';
                document.getElementById('fbSuccess').style.display = 'block';
            } else { alert('提交失败：' + (result.msg || '未知错误')); }
        } catch(e) { alert('网络错误，请重试'); }
        btn.textContent = '💬 提交反馈';
        btn.disabled = false;
    });
    </script>
    """
    return HTMLResponse(make_page("建议反馈 - 武鸣招聘", content, "feedback", user=user_info))


@router.post("/api/feedback")
async def submit_feedback(request: Request):
    """接收反馈提交"""
    try:
        data = await request.json()
        content = (data.get("content") or "").strip()
        contact = (data.get("contact") or "").strip()
        page = (data.get("page") or "").strip()
        if not content or len(content) < 5:
            return {"ok": False, "msg": "请填写至少5个字符的建议内容"}
        conn = get_recruit_db()
        conn.execute("INSERT INTO feedback (content, contact, page) VALUES (?, ?, ?)", (content, contact, page))
        conn.commit()
        conn.close()
        return {"ok": True, "msg": "提交成功"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}
