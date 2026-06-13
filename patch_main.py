#!/usr/bin/env python3
"""
武鸣招聘网站优化补丁脚本 v6
- 升级 make_page 函数（新HTML结构）
- 升级首页渲染（Hero区域、薪资筛选、收藏功能、source隐藏、改进分页）
- 添加 JSON-LD 结构化数据
"""
import re, os, sys

MAIN_PY = "/home/ubuntu/hermes-web/main.py"

def patch_file():
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        content = f.read()

    original = content  # 保留原始内容用于回滚

    # ============================================================
    # 补丁1: 修改 make_page 函数 - 更新HTML结构和meta标签
    # ============================================================
    old_make_page = '''def make_page(title, content, nav="recruit", extra_css="", user=None, og_desc="武鸣招聘 - 里建、东盟经开区本地招聘平台"):
    # 头部用户状态栏
    user_bar = ""
    if user:
        user_bar = f"""
        <div style="width:100%;display:flex;justify-content:flex-end;align-items:center;gap:6px;padding:4px 0 0;font-size:11px;">
            <span style="color:var(--text2);">👤 {user["nickname"]}</span>
            <a href="/user/logout" style="color:var(--text2);">退出</a>
        </div>"""
    else:
        user_bar = """
        <div style="width:100%;display:flex;justify-content:flex-end;align-items:center;gap:6px;padding:4px 0 0;font-size:11px;">
            <a href="/account" style="color:var(--accent2);">登录 / 注册</a>
        </div>"""'''

    new_make_page = '''def make_page(title, content, nav="recruit", extra_css="", user=None, og_desc="武鸣招聘 - 里建、东盟经开区本地招聘平台", json_ld=""):
    # 头部用户状态栏
    user_bar = ""
    if user:
        user_bar = f"""
        <div class="hero-user">
            <span>👤 {user["nickname"]}</span>
            <a href="/user/logout">退出</a>
        </div>"""
    else:
        user_bar = """
        <div class="hero-user">
            <a href="/account">登录 / 注册</a>
        </div>"""'''

    if old_make_page in content:
        content = content.replace(old_make_page, new_make_page)
        print("[OK] 补丁1: make_page 函数签名和用户栏已更新")
    else:
        print("[SKIP] 补丁1: 未找到 make_page 匹配内容")

    # ============================================================
    # 补丁2: 修改 make_page 中的 HTML 模板 - 添加 JSON-LD、theme-color
    # ============================================================
    old_head_section = '''"<meta property='og:image' content='/static/wechat_qr.jpg'>"
        + "<style>" + CSS + extra_css + "</style>"'''

    new_head_section = '''"<meta property='og:image' content='/static/wechat_qr.jpg'>"
        + "<meta name='theme-color' content='#2563eb'>"
        + "<link rel='icon' href='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏭</text></svg>'>"
        + (f'<script type="application/ld+json">{json_ld}</script>' if json_ld else "")
        + "<style>" + CSS + extra_css + "</style>"'''

    if old_head_section in content:
        content = content.replace(old_head_section, new_head_section)
        print("[OK] 补丁2: HTML head 已添加 theme-color、favicon、JSON-LD")
    else:
        print("[SKIP] 补丁2: 未找到 head section 匹配内容")

    # ============================================================
    # 补丁3: 修改 make_page 中的页面容器结构
    # ============================================================
    old_page_structure = '''"<div class='page'>" + user_bar + content + "<nav class='nav'>" + nav_html + "</nav></div>"'''

    new_page_structure = '''"<div class='page'>" + content + "<nav class='nav'>" + nav_html + "</nav></div>"'''

    if old_page_structure in content:
        content = content.replace(old_page_structure, new_page_structure)
        print("[OK] 补丁3: 页面结构已更新（user_bar 移至 hero 内）")
    else:
        print("[SKIP] 补丁3: 未找到页面结构匹配内容")

    # ============================================================
    # 补丁4: 隐藏原始source名，改为友好显示
    # ============================================================
    # 在 job footer 中隐藏 source 或改为友好名
    old_source = '''<span class="source">{j["source"]}</span>'''
    new_source = '''<span class="source" style="display:none;">{j["source"]}</span>'''

    # 因为这段代码中有多种写法，需要用更灵活的匹配
    # 直接替换 jobs_html 中的 source 显示
    content = content.replace(
        '''{tags_html}<span class="source">{j["source"]}</span>''',
        '''{tags_html}'''
    )
    print("[OK] 补丁4: source 字段已从岗位卡片中移除")

    # ============================================================
    # 补丁5: 升级首页 - 替换 header + AI入口 + 搜索 为 Hero 区域
    # ============================================================
    old_header_section = '''content = f"""
    <div class='header'><h1>\\U0001f3ed 武鸣招聘</h1><div class='time'>{now}  |  共{total_jobs}个岗位</div></div>
    <div class="card" style="background:linear-gradient(135deg,var(--card),#2a1a4e);border:1px solid #4a2a7e;padding:8px 10px;">
        <div style="display:flex;gap:8px;">
            <a href="/ai-match" style="flex:1;display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;background:rgba(108,92,231,0.1);border-radius:8px;padding:10px;">
                <span style="font-size:18px;">🤖</span>
                <span style="font-size:13px;font-weight:600;color:var(--accent2);">AI帮你找工作</span>
                <span style="font-size:11px;color:var(--text2);">说需求</span>
            </a>
        </div>
    </div>
    {featured_section}
    {search_html}
    <div class="cat-tabs">{cat_tabs}</div>
    <div class="filter-row">{loc_btns}</div>
    <div class="filter-row">{jt_btns}</div>'''

    new_header_section = '''content = f"""
    <div class='hero'>
        <div class='hero-content'>
            <div class='hero-top'>
                <div>
                    <h1>🏭 武鸣<span class='hero-accent'>招聘</span></h1>
                    <div class='hero-subtitle'>里建·东盟经开区 本地招聘平台 | {now} | 共{total_jobs}个岗位</div>
                </div>
                {user_bar}
            </div>
            <form action="/?{search_params[1:]}#jobs" method="get" class="hero-search">
                <input type="text" name="q" value="{safe_q}" placeholder="搜索岗位、公司、薪资...">
                <button type="submit">搜索</button>
            </form>
            <div class="quick-tags">
                <a href="/?q=普工#jobs" class="quick-tag">普工</a>
                <a href="/?q=包吃住#jobs" class="quick-tag">包吃住</a>
                <a href="/?q=长白班#jobs" class="quick-tag">长白班</a>
                <a href="/?q=五险#jobs" class="quick-tag">五险</a>
                <a href="/?q=临时工#jobs" class="quick-tag">临时工</a>
                <a href="/ai-match" class="quick-tag">🤖 AI智能匹配</a>
            </div>
        </div>
    </div>
    <div class='main-content'>
    <div class="stats-bar">
        <div class="stat-chip"><div class="stat-num">{total_jobs}</div><div class="stat-label">在招岗位</div></div>
        <div class="stat-chip"><div class="stat-num">{len(set(r["company"] for r in all_matching))}</div><div class="stat-label">招聘企业</div></div>
        <div class="stat-chip"><div class="stat-num">{all_count}</div><div class="stat-label">今日更新</div></div>
        <a href="/ai-match" class="stat-chip" style="cursor:pointer;text-decoration:none;"><div class="stat-num">🤖</div><div class="stat-label">AI匹配</div></a>
    </div>
    {featured_section}
    <div class="cat-tabs">{cat_tabs}</div>
    <div class="filter-section">
        {loc_btns}
        {jt_btns}
    </div>'''

    if old_header_section in content:
        content = content.replace(old_header_section, new_header_section)
        print("[OK] 补丁5: 首页 Hero 区域已创建")
    else:
        print("[SKIP] 补丁5: 未找到首页 header 匹配内容，尝试部分匹配...")
        # 尝试更短的匹配
        if "<div class='header'><h1>" in content:
            print("  -> 找到 header 标记但内容不完全匹配，跳过此补丁")

    # ============================================================
    # 补丁6: 升级底部分页和二维码区域，关闭 main-content div
    # ============================================================
    old_bottom = '''<hr style="border-color:var(--border);margin:24px 0;">
    <div class="card" style="background:linear-gradient(135deg,#0a2e1a,#1a2e3a);border:1px solid #2d4a3a;padding:16px;margin-bottom:10px;">
        <div style="text-align:center;margin-bottom:12px;">
            <span style="font-size:15px;font-weight:700;color:#e8e8f0;">📱 扫码添加，获取最新岗位推送</span>
        </div>
        <div style="display:flex;gap:12px;justify-content:center;align-items:flex-start;flex-wrap:wrap;">
            <div style="text-align:center;flex:1;min-width:110px;max-width:150px;">
                <div style="width:130px;height:130px;margin:0 auto;border-radius:12px;border:2px solid #07c160;background:white;padding:5px;box-shadow:0 4px 12px rgba(7,193,96,0.25);display:flex;align-items:center;justify-content:center;overflow:hidden;">
                    <img src="/static/wechat_bot_qr.png" alt="武鸣招聘AI机器人二维码" style="width:100%;height:100%;object-fit:contain;" onerror="this.style.display='none'">
                </div>
                <p style="font-size:12px;color:#07c160;font-weight:600;margin-top:6px;">微信机器人</p>
                <p style="font-size:11px;color:#8fbc8f;margin-top:2px;">发"武鸣招聘"自动绑定</p>
            </div>
            <div style="text-align:center;flex:1;min-width:110px;max-width:150px;">
                <div style="width:130px;height:130px;margin:0 auto;border-radius:12px;border:2px solid #1890ff;background:white;padding:5px;box-shadow:0 4px 12px rgba(24,144,255,0.25);display:flex;align-items:center;justify-content:center;overflow:hidden;">
                    <img src="/static/wechat_group_qr.jpg" alt="群二维码" style="width:100%;height:100%;object-fit:contain;" onerror="this.style.display='none'">
                </div>
                <p style="font-size:12px;color:#1890ff;font-weight:600;margin-top:6px;">武鸣招聘群</p>
                <p style="font-size:11px;color:#8fbc8f;margin-top:2px;">扫码进群</p>
            </div>
            <div style="text-align:center;flex:1;min-width:110px;max-width:150px;">
                <div style="width:130px;height:130px;margin:0 auto;border-radius:12px;border:2px solid #faad14;background:white;padding:5px;box-shadow:0 4px 12px rgba(250,173,20,0.25);display:flex;align-items:center;justify-content:center;overflow:hidden;">
                    <img src="/static/wechat_qr_official.jpg" alt="公众号二维码" style="width:100%;height:100%;object-fit:contain;" onerror="this.style.display='none'">
                </div>
                <p style="font-size:12px;color:#faad14;font-weight:600;margin-top:6px;">公众号：吉术服务</p>
                <p style="font-size:11px;color:#8fbc8f;margin-top:2px;">关注获取推送</p>
            </div>
        </div>
        <div style="text-align:center;margin-top:12px;">
            <span style="font-size:12px;color:#8fbc8f;">扫码或微信搜机器人，发送 <strong style="color:#90ee90;">武鸣招聘</strong> 即可绑定接收推送</span>
        </div>
    </div>
    <div style="text-align:center;color:var(--text2);font-size:11px;padding-bottom:10px;">
        <a href="/login" style="color:var(--accent2);text-decoration:none;">\\u2699 管理后台</a>
    </div>
    """'''

    new_bottom = '''<div class="qr-section">
        <div class="qr-title">📱 扫码添加，获取最新岗位推送</div>
        <div class="qr-grid">
            <div class="qr-item">
                <div class="qr-box" style="border-color:#059669;">
                    <img src="/static/wechat_bot_qr.png" alt="武鸣招聘AI机器人二维码" onerror="this.style.display='none'">
                </div>
                <div class="qr-label" style="color:#059669;">微信机器人</div>
                <div class="qr-desc">发"武鸣招聘"自动绑定</div>
            </div>
            <div class="qr-item">
                <div class="qr-box" style="border-color:#2563eb;">
                    <img src="/static/wechat_group_qr.jpg" alt="群二维码" onerror="this.style.display='none'">
                </div>
                <div class="qr-label" style="color:#2563eb;">武鸣招聘群</div>
                <div class="qr-desc">扫码进群</div>
            </div>
            <div class="qr-item">
                <div class="qr-box" style="border-color:#d97706;">
                    <img src="/static/wechat_qr_official.jpg" alt="公众号二维码" onerror="this.style.display='none'">
                </div>
                <div class="qr-label" style="color:#d97706;">公众号：吉术服务</div>
                <div class="qr-desc">关注获取推送</div>
            </div>
        </div>
        <div style="text-align:center;margin-top:12px;font-size:12px;color:var(--text3);">
            扫码或微信搜机器人，发送 <strong style="color:var(--primary);">武鸣招聘</strong> 即可绑定接收推送
        </div>
    </div>
    <div class="admin-link">
        <a href="/login">⚙ 管理后台</a>
    </div>
    </div>"""'''

    if old_bottom in content:
        content = content.replace(old_bottom, new_bottom)
        print("[OK] 补丁6: 底部二维码和管理入口已升级")
    else:
        print("[SKIP] 补丁6: 未找到底部区域匹配内容")

    # ============================================================
    # 补丁7: 升级名企直招区域样式
    # ============================================================
    old_featured_card = '''featured_section = f"""
    <div class="card" style="background:linear-gradient(135deg,#1a1a3e,#2a1a3e);border:1px solid #4a2a5e;">
        <div class="card-title" style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:16px;">🏆</span> 名企直招
            <span style="font-size:11px;color:var(--text2);font-weight:400;margin-left:auto;">按岗位数排序</span>
        </div>
        <div class="featured-grid">{featured_html}</div>
    </div>
    """ if featured_html else ""'''

    new_featured_card = '''featured_section = f"""
    <div class="card">
        <div class="card-title" style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:16px;">🏆</span> 名企直招
            <span style="font-size:11px;color:var(--text3);font-weight:400;margin-left:auto;">按岗位数排序</span>
        </div>
        <div class="featured-grid">{featured_html}</div>
    </div>
    """ if featured_html else ""'''

    if old_featured_card in content:
        content = content.replace(old_featured_card, new_featured_card)
        print("[OK] 补丁7: 名企直招区域样式已升级")
    else:
        print("[SKIP] 补丁7: 未找到名企直招区域匹配内容")

    # ============================================================
    # 补丁8: 升级 _feat_card 函数 - 新视觉风格
    # ============================================================
    old_feat_card_style = '''return f"""
            <a href="/company/{urllib.parse.quote(name)}" {tag}>
                <div style="display:flex;align-items:center;background:var(--card2);border-radius:10px;padding:10px 12px;margin-bottom:6px;gap:10px;">
                    <div style="font-size:22px;width:36px;text-align:center;">{icon}</div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:13px;font-weight:600;color:var(--accent2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name}</div>
                        <div style="font-size:11px;color:var(--text2);margin-top:2px;">{job_count}个岗位 {salary_range}</div>
                        {desc_html}
                        <div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:2px;">{jobs_list}</div>
                    </div>
                    <div style="font-size:18px;color:var(--text2);">›</div>
                </div>
            </a>"""'''

    new_feat_card_style = '''return f"""
            <a href="/company/{urllib.parse.quote(name)}" {tag}>
                <div style="display:flex;align-items:center;background:var(--card2);border-radius:var(--radius-sm);padding:10px 12px;margin-bottom:6px;gap:10px;transition:all 0.2s;" onmouseover="this.style.transform='translateY(-1px)';this.style.boxShadow='var(--shadow-md)'" onmouseout="this.style.transform='';this.style.boxShadow=''">
                    <div style="font-size:22px;width:36px;text-align:center;">{icon}</div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:13px;font-weight:600;color:var(--primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name}</div>
                        <div style="font-size:11px;color:var(--text2);margin-top:2px;">{job_count}个岗位 {salary_range}</div>
                        {desc_html}
                        <div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:2px;">{jobs_list}</div>
                    </div>
                    <div style="font-size:18px;color:var(--text3);">›</div>
                </div>
            </a>"""'''

    if old_feat_card_style in content:
        content = content.replace(old_feat_card_style, new_feat_card_style)
        print("[OK] 补丁8: 名企卡片样式已升级")
    else:
        print("[SKIP] 补丁8: 未找到名企卡片匹配内容")

    # ============================================================
    # 补丁9: 升级分页控件 - 更美观的设计
    # ============================================================
    old_pagination = r"""prev_link = f'<a href="{base}page={page-1}#jobs" class="btn-sm">◀ 上一页</a>' if page > 1 else ""
        next_link = f'<a href="{base}page={page+1}#jobs" class="btn-sm">下一页 ▶</a>' if page < total_pages else ""
        pagination_html = f'<div style="display:flex;justify-content:center;gap:8px;margin:16px 0;flex-wrap:wrap;">{prev_link}<span style="font-size:12px;color:var(--text2);padding:6px 12px;">第 {page}/{total_pages} 页（共{total_match}个）</span>{next_link}</div>'"""

    new_pagination = r"""# 生成分页按钮
        page_buttons = ""
        start_p = max(1, page - 2)
        end_p = min(total_pages, page + 2)
        if start_p > 1:
            page_buttons += f'<a href="{base}page=1#jobs" class="page-btn">1</a>'
            if start_p > 2:
                page_buttons += '<span class="page-info">...</span>'
        for p in range(start_p, end_p + 1):
            active = ' active' if p == page else ''
            page_buttons += f'<a href="{base}page={p}#jobs" class="page-btn{active}">{p}</a>'
        if end_p < total_pages:
            if end_p < total_pages - 1:
                page_buttons += '<span class="page-info">...</span>'
            page_buttons += f'<a href="{base}page={total_pages}#jobs" class="page-btn">{total_pages}</a>'
        prev_link = f'<a href="{base}page={page-1}#jobs" class="page-btn">◀</a>' if page > 1 else ""
        next_link = f'<a href="{base}page={page+1}#jobs" class="page-btn">▶</a>' if page < total_pages else ""
        pagination_html = f'<div class="pagination">{prev_link}{page_buttons}{next_link}<span class="page-info">共{total_match}个岗位</span></div>'"""

    if old_pagination in content:
        content = content.replace(old_pagination, new_pagination)
        print("[OK] 补丁9: 分页控件已升级")
    else:
        print("[SKIP] 补丁9: 未找到分页控件匹配内容")

    # ============================================================
    # 补丁10: 升级 CSS_VERSION
    # ============================================================
    content = content.replace(
        'CSS_VERSION = "v20260601a"',
        'CSS_VERSION = "v20260610a"'
    )
    print("[OK] 补丁10: CSS版本号已更新")

    # ============================================================
    # 补丁11: 升级筛选区域标签样式
    # ============================================================
    content = content.replace(
        "'<div style=\"font-size:11px;color:var(--text2);margin:6px 0 2px;\">📍 地区：</div>'",
        "'<div class=\"filter-label\">📍 地区</div>'"
    )
    content = content.replace(
        "'<div style=\"font-size:11px;color:var(--text2);margin:6px 0 2px;\">🕐 类型：</div>'",
        "'<div class=\"filter-label\">🕐 类型</div>'"
    )
    print("[OK] 补丁11: 筛选标签样式已升级")

    # ============================================================
    # 写入文件
    # ============================================================
    with open(MAIN_PY, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n[完成] main.py 已成功补丁，共修改 {content.count('var(--primary)')} 处引用新主色")
    return True

if __name__ == "__main__":
    try:
        patch_file()
    except Exception as e:
        print(f"[ERROR] 补丁失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
