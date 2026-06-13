"""
AI匹配引擎 - 语义解析、多维度评分
"""
import re
import urllib.parse
from datetime import datetime
from typing import Optional

from services.db import get_recruit_db, days_ago
from models.schema import (
    CATEGORY_MAP, LOCATION_SYNONYMS, JOB_TYPE_MAP,
    INDUSTRY_KEYWORDS, WELFARE_KEYWORDS, QUICK_SCENARIOS,
    AI_STOP_WORDS, get_major_cat
)


def parse_query(text: str) -> dict:
    """解析用户自然语言查询，提取关键信息（v2增强版）"""
    info = {
        "salary_min": 0, "salary_max": 0, "salary_unit": "月",
        "location": "", "job_type": "", "category": "", "welfare": [],
        "keywords": [], "raw": text
    }
    t = text

    # ====== 1. 薪资提取（增强版）======
    salary_patterns = [
        # 时薪模式: "20块一小时" "时薪20" "20/小时" "¥20/h"
        (r'(?:时薪|小时|每时)[:：]?\s*(\d+\.?\d*)', 'hour'),
        (r'(\d+\.?\d*)\s*块?\s*[／/一]小时', 'hour'),
        (r'(\d+\.?\d*)\s*[／/]\s*h', 'hour'),
        # 月薪模式: "5000以上" "4000-6000" "4-6千" "五千"
        (r'(\d+)\s*[—\-~到至]\s*(\d+)\s*(千|万|k|K)?', 'range'),
        (r'(\d+\.?\d*)\s*千\s*[—\-~到至]\s*(\d+\.?\d*)\s*千?', 'range_thousand'),
        (r'(\d+\.?\d*)\s*万\s*[—\-~到至]\s*(\d+\.?\d*)\s*万?', 'range_wan'),
        (r'(?:工资|薪资|薪水|待遇)[：:]?\s*(\d+\.?\d*)\s*[—\-~到至]\s*(\d+\.?\d*)\s*(千|万|k)?', 'range_wage'),
        # 最低/以上模式: "5000以上" "3000+"
        (r'(\d+\.?\d*)\s*(千|万)?\s*(以上|以?.上|[\+])\s*', 'min'),
        (r'(?:不低于|不少于|至少)[：:]?\s*(\d+\.?\d*)\s*(千|万)?', 'min'),
        # 基本数值
        (r'(\d+\.?\d*)\s*块', 'block'),
        (r'(\d+\.?\d*)\s*元', 'yuan'),
        (r'(\d+\.?\d*)\s*千(?!.*[—-])', 'thousand'),
        (r'(\d+\.?\d*)\s*万(?!.*[—-])', 'wan'),
    ]

    for pat, mode in salary_patterns:
        m = re.search(pat, t)
        if m:
            if mode == 'hour':
                val = float(m.group(1))
                info["salary_min"] = int(val * 22)
                info["salary_unit"] = "月"
            elif mode == 'range':
                info["salary_min"] = int(m.group(1))
                info["salary_max"] = int(m.group(2))
                if m.group(3) and m.group(3).lower() in ('千', 'k'):
                    info["salary_min"] *= 1000
                    info["salary_max"] *= 1000
                elif m.group(3) and m.group(3).lower() in ('万',):
                    info["salary_min"] *= 10000
                    info["salary_max"] *= 10000
            elif mode == 'range_thousand':
                info["salary_min"] = int(float(m.group(1)) * 1000)
                info["salary_max"] = int(float(m.group(2)) * 1000)
            elif mode == 'range_wan':
                info["salary_min"] = int(float(m.group(1)) * 10000)
                info["salary_max"] = int(float(m.group(2)) * 10000)
            elif mode == 'range_wage':
                info["salary_min"] = int(m.group(1))
                info["salary_max"] = int(m.group(2))
                if m.group(3) and m.group(3).lower() in ('千', 'k'):
                    info["salary_min"] *= 1000
                    info["salary_max"] *= 1000
                elif m.group(3) and m.group(3).lower() in ('万',):
                    info["salary_min"] *= 10000
                    info["salary_max"] *= 10000
            elif mode == 'min':
                val = float(m.group(1))
                if m.group(2) and m.group(2) in ('千', '万'):
                    val *= 1000 if m.group(2) == '千' else 10000
                info["salary_min"] = int(val)
            elif mode == 'block':
                info["salary_min"] = int(float(m.group(1)) * 22)
            elif mode == 'yuan':
                info["salary_min"] = int(float(m.group(1)))
            elif mode == 'thousand':
                info["salary_min"] = int(float(m.group(1)) * 1000)
            elif mode == 'wan':
                info["salary_min"] = int(float(m.group(1)) * 10000)
            break

    # 很小的数值（未显式转换的时薪/日薪）→转为月薪估算
    # 阈值200：已由 'block'/'hour' 模式转换过的时薪（如20*22=440）不会重复计算
    if info["salary_min"] > 0 and info["salary_min"] < 200 and info["salary_max"] == 0:
        info["salary_min"] = info["salary_min"] * 22
    elif 0 < info["salary_min"] < 100 and info["salary_max"] == 0:
        info["salary_min"] *= 1000
    if info["salary_max"] > 0 and info["salary_max"] < 100:
        info["salary_max"] *= 1000

    # ====== 2. 地点提取（含同义词） ======
    for loc_name, synonyms in LOCATION_SYNONYMS.items():
        for s in synonyms:
            if s in t:
                info["location"] = loc_name
                break
        if info["location"]:
            break
    if not info["location"]:
        if "附近" in t or "近" in t:
            info["location"] = "里建"

    # ====== 3. 工作类型提取 ======
    for jt_name, synonyms in JOB_TYPE_MAP.items():
        for s in synonyms:
            if s in t:
                info["job_type"] = jt_name
                break
        if info["job_type"]:
            break

    # ====== 4. 行业分类提取 ======
    for cat_name, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                info["category"] = cat_name
                break
        if info["category"]:
            break

    # ====== 5. 福利需求提取 ======
    for wl_name, keywords in WELFARE_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                info["welfare"].append(wl_name)
                break

    # ====== 6. 其他关键词 ======
    cleaned = re.sub(r'[，。！？、；：""''（）\(\)\[\]\d+\.\d+元块千时薪]', ' ', t)
    stop_words = set(AI_STOP_WORDS)
    for loc_syn_list in LOCATION_SYNONYMS.values():
        stop_words.update(loc_syn_list)
    for jt_syn_list in JOB_TYPE_MAP.values():
        stop_words.update(jt_syn_list)
    for cat_kw_list in INDUSTRY_KEYWORDS.values():
        stop_words.update(cat_kw_list)
    for wl_kw_list in WELFARE_KEYWORDS.values():
        stop_words.update(wl_kw_list)

    info["keywords"] = [w for w in cleaned.split() if len(w) >= 2 and w not in stop_words][:6]
    return info


def ai_match_jobs(query_text: str, limit: int = 15) -> list:
    """AI智能匹配v2：多维度语义评分引擎"""
    conn = get_recruit_db()
    all_jobs = conn.execute(
        "SELECT * FROM jobs WHERE status='active' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    if not query_text or not query_text.strip():
        return []

    info = parse_query(query_text)
    scored = []

    top_brands = ["比亚迪", "海天", "双汇", "百威", "伊利", "红牛", "李宁", "京东", "拼多多"]

    for j in all_jobs:
        score = 0
        max_score = 0
        reasons = []

        combined_text = (
            f"{j['title']} {j['company']} {j['description'] or ''} {j['tags'] or ''} "
            f"{j['location']} {j['job_type']} {j['category']}"
        ).lower()
        desc_lower = (j['description'] or '').lower()
        title_lower = j['title'].lower()

        # 维度1：地点匹配（最高25分）
        max_score += 25
        if info["location"]:
            loc_syns = LOCATION_SYNONYMS.get(info["location"], [info["location"]])
            for syn in loc_syns:
                if syn in (j["location"] or "").lower():
                    score += 25
                    reasons.append(f"📍 就在{info['location']}")
                    break
            else:
                for syn in loc_syns:
                    if syn in desc_lower or syn in combined_text:
                        score += 15
                        reasons.append(f"📍 近{info['location']}")
                        break
        else:
            max_score -= 25

        # 维度2：工作类型匹配（最高20分）
        max_score += 20
        if info["job_type"]:
            jt_syns = JOB_TYPE_MAP.get(info["job_type"], [info["job_type"]])
            for syn in jt_syns:
                if syn in combined_text:
                    score += 20
                    reasons.append(f"🕐 {info['job_type']}")
                    break
        else:
            max_score -= 20

        # 维度3：薪资匹配（最高30分）
        max_score += 30
        if info["salary_min"] > 0:
            job_min = j["salary_min"] or 0
            job_max = j["salary_max"] or 0
            unit = j["salary_unit"] or "月"
            if "时" in unit or "小时" in unit:
                job_min_m = job_min * 22
                job_max_m = job_max * 22 if job_max else 0
            elif "日" in unit:
                job_min_m = job_min * 26
                job_max_m = job_max * 26 if job_max else 0
            else:
                job_min_m = job_min
                job_max_m = job_max

            if job_min_m > 0:
                if info["salary_max"] > 0:
                    if job_min_m <= info["salary_max"] and (job_max_m == 0 or job_max_m >= info["salary_min"]):
                        salary_overlap = min(job_max_m or info["salary_max"], info["salary_max"]) - max(job_min_m, info["salary_min"])
                        if salary_overlap > 0:
                            score += 25 + min(5, int(salary_overlap / 500))
                            reasons.append(f"💰 薪资匹配")
                        else:
                            score += 10
                            reasons.append(f"💰 薪资接近")
                elif job_min_m >= info["salary_min"]:
                    score += 30
                    reasons.append(f"💰 薪资达标 ✓")
                elif job_min_m >= info["salary_min"] * 0.7:
                    score += 12
                    reasons.append(f"💰 薪资接近")
        else:
            max_score -= 30

        # 维度4：行业分类匹配（最高15分）
        max_score += 15
        if info["category"]:
            if info["category"] == j["category"]:
                score += 15
                reasons.append(f"📂 {info['category']}")
            else:
                for kw in INDUSTRY_KEYWORDS.get(info["category"], []):
                    if kw in combined_text:
                        score += 8
                        reasons.append(f"📂 相关行业")
                        break
        else:
            max_score -= 15

        # 维度5：福利匹配（最高15分）
        max_score += 15
        if info["welfare"]:
            wl_matches = 0
            for wl in info["welfare"]:
                wl_kws = WELFARE_KEYWORDS.get(wl, [wl])
                for kw in wl_kws:
                    if kw in desc_lower or kw in title_lower or kw in (j["tags"] or "").lower():
                        wl_matches += 1
                        reasons.append(f"🎁 {wl}")
                        break
            if wl_matches > 0:
                score += min(15, wl_matches * 8)
            if wl_matches >= len(info["welfare"]):
                score += 3
                reasons.append(f"✅ 全满足")
        else:
            max_score -= 15

        # 维度6：关键词语义匹配（最高15分）
        max_score += 15
        kw_match_count = 0
        for kw in info["keywords"]:
            if kw in title_lower:
                kw_match_count += 2
            elif kw in combined_text:
                kw_match_count += 1
        if kw_match_count > 0:
            score += min(15, kw_match_count * 5)

        # 维度7：时效加分
        d_ays = days_ago(j["created_at"])
        if d_ays == 0:
            score += 8
        elif d_ays == 1:
            score += 5
        elif d_ays < 7:
            score += 3
        elif d_ays < 14:
            score += 1

        # 维度8：名企加分
        for brand in top_brands:
            if brand in j["company"] or brand in j["title"]:
                score += 5
                reasons.append(f"⭐ {brand}")
                break

        if score > 0:
            pct = min(100, round(score / max(score, max_score) * 100)) if max_score > 0 else 0
            scored.append((pct, score, j, reasons, d_ays))

    scored.sort(key=lambda x: (-x[0], x[4], -x[1]))
    return scored[:limit]


def format_match_results(scored: list, query: str, user_info: Optional[dict] = None) -> str:
    """把匹配结果格式化成HTML（v2增强版）"""
    if not scored:
        return """
        <div class="text-center" style="padding:30px 0;color:var(--text2);">
            <div style="font-size:40px;margin-bottom:12px;">🔍</div>
            <p>没有找到完全匹配的岗位</p>
            <p style="font-size:12px;margin-top:8px;">
                试试换个说法：<br>
                「里建夜班」「武鸣小时工20」「食品厂包吃住」「学生兼职」
            </p>
        </div>"""

    scenarios_html = '<div class="flex-row" style="display:flex;gap:4px;overflow-x:auto;padding:6px 0 10px;scrollbar-width:none;">'
    for s in QUICK_SCENARIOS:
        q_enc = urllib.parse.quote(s["query"])
        active = ' style="background:var(--accent);color:white;border-color:var(--accent);"' if s["query"] == query else ''
        scenarios_html += f'<a href="/ai-match?q={q_enc}" class="btn-sm"{active}>{s["text"]}</a>'
    scenarios_html += '</div>'

    html = f'<div style="margin-bottom:6px;color:var(--text2);font-size:12px;">找到 {len(scored)} 个匹配岗位</div>'
    html += scenarios_html

    for i, (pct, score, j, reasons, d_ays) in enumerate(scored):
        s_min = j['salary_min'] if j['salary_min'] else 0
        s_max = j['salary_max'] if j['salary_max'] else 0
        if s_min == 0 and s_max == 0:
            salary = '<span class="salary-negotiable">面议</span>'
        elif s_max:
            salary = f"{s_min}-{s_max}{j['salary_unit']}"
        else:
            salary = f"{s_min}{j['salary_unit']}"

        bar_color = "var(--green)" if pct >= 70 else ("var(--yellow)" if pct >= 40 else "var(--red)")
        tags_html = ""
        for t in (j["tags"] or "").split(","):
            if t.strip():
                tags_html += f'<span class="tag">{t.strip()}</span>'

        reasons_html = "&nbsp;·&nbsp;".join(reasons[:4])

        time_label = ""
        if d_ays == 0:
            time_label = '<span class="time-today">今日发布</span>'
        elif d_ays == 1:
            time_label = '<span class="time-yesterday">昨天</span>'

        major_cat = get_major_cat(j["category"] or "其他")
        short_cat = major_cat.split(" ", 1)[-1] if " " in major_cat else major_cat
        cat_badge = f'<span class="job-cat-badge">{short_cat}</span>'

        contact_html = ""
        if user_info and j["contact_phone"]:
            contact_html = f'<div class="contact-row">📞 <span class="contact-phone">{j["contact_phone"]}</span></div>'

        html += f"""
        <div class="job-card" style="border-left:3px solid {bar_color};">
            <div class="job-title-row">
                <div class="job-title">{j["title"]}</div>
                <div class="flex-row" style="display:flex;align-items:center;gap:4px;margin-left:auto;">
                    {cat_badge}
                    <div class="match-pct" style="font-size:11px;color:{bar_color};font-weight:600;">{pct}%</div>
                </div>
            </div>
            <div class="match-bar"><div class="match-bar-fill" style="width:{pct}%;background:{bar_color};"></div></div>
            <div class="job-meta">
                {j["company"]} | {j["location"]} | {j["job_type"]}
                {time_label}
            </div>
            <div class="job-salary">{salary}</div>
            <div class="match-reason">{reasons_html}</div>
            {contact_html}
            <div class="job-footer">{tags_html}</div>
        </div>"""
    return html


def find_matching_talents(job_title: str, job_category: str, job_desc: str, uid: Optional[int]) -> str:
    """根据岗位信息，匹配数据库中合适的求职者简历"""
    if not uid:
        return ""
    try:
        conn = get_recruit_db()
        candidates = conn.execute(
            "SELECT name, gender, age, edu_level, expected_job, expected_salary, skills, "
            "self_desc, experience, phone "
            "FROM resumes WHERE is_active=1 AND phone != '' "
            "ORDER BY is_pinned DESC, updated_at DESC LIMIT 6"
        ).fetchall()
        conn.close()
        if not candidates:
            return ""
        matched_html = ""
        count = 0
        for c in candidates:
            score = 0
            reasons = []
            exp_str = (
                (c["expected_job"] or "") + " " + (c["skills"] or "") + " "
                + (c["self_desc"] or "") + " " + (c["experience"] or "")
            )
            if job_category and job_category in exp_str:
                score += 3
                reasons.append("行业相关")
            title_kws = re.sub(r'[的/和与及]', ' ', job_title).split()
            for kw in title_kws[:3]:
                if len(kw) >= 2 and kw in exp_str.lower():
                    score += 3
                    reasons.append(f"匹配「{kw}」")
                    break
            desc_kws = list(set(re.findall(r'[\u4e00-\u9fff]{2,}', job_desc or "")))
            for kw in desc_kws[:8]:
                if len(kw) >= 3 and kw in exp_str:
                    score += 1
            if score > 0:
                count += 1
                age_str = f"{c['age']}岁" if c['age'] else ""
                edu_str = f" · {c['edu_level']}" if c['edu_level'] else ""
                skills_str = (c["skills"] or "")[:40]
                reason_str = " · ".join(reasons[:2])
                matched_html += f"""<div class="job-card talent-card">
                    <div class="talent-header">
                        <span class="talent-name">{c['name']} {age_str}{edu_str}</span>
                        <span class="talent-score">{min(100, score * 15)}%</span>
                    </div>
                    <div class="talent-job">{c['expected_job'] or '——'}</div>
                    <div class="talent-reason">🎯 {reason_str if reason_str else '相关候选人'} · 📞 {c['phone']}</div>
                    {f'<div class="talent-skills">💡 {skills_str}</div>' if skills_str else ''}
                </div>"""
            if count >= 4:
                break
        if not matched_html:
            return ""
        return f'''<div class="card talent-section">
            <div class="card-title talent-section-title">
                <span>👥 可能适合的求职者</span>
                <span class="talent-count">{count}人匹配</span>
            </div>
            {matched_html}
            <div class="text-center" style="margin-top:4px;">
                <a href="/admin" class="link-sm">查看全部求职者 →</a>
            </div>
        </div>'''
    except Exception as e:
        return f"<!-- talent match error: {e} -->"
