"""
武鸣招聘AI Agent服务 - 基于大语言模型的智能问答
替代原有的关键词匹配规则，使用DeepSeek模型进行自然语言理解和回复
"""
import json
import re
import httpx
import os
import yaml
from services.db import get_recruit_db


# ====== 加载DeepSeek配置 ======
_cfg_path = os.path.expanduser("~/.hermes/config.yaml")
with open(_cfg_path) as _f:
    _cfg = yaml.safe_load(_f)
_ds = _cfg.get("providers", {}).get("deepseek", {})
DEEPSEEK_API_URL = _ds.get("base_url", "https://api.deepseek.com/v1") + "/chat/completions"
DEEPSEEK_API_KEY = _ds.get("api_key", "")
DEEPSEEK_MODEL = _ds.get("model", "deepseek-v4-flash")
del _f, _cfg, _ds


# ====== 系统提示词 ======
SYSTEM_PROMPT = """你是武鸣招聘平台的AI助手"小武"，专门帮助求职者找工作。

## 平台信息
- 名称：武鸣招聘
- 覆盖区域：武鸣区（里建、东盟经开区、双桥、宁武、锣圩、太平、府城、陆斡等）
- 主要行业：食品餐饮、包装物流、工厂技工、服装制造、医药化工、服务销售、兼职
- 知名企业：比亚迪（弗迪电池）、海天调味、双汇食品、百威啤酒、伊利、红牛、李宁（宁泰）等
- 对求职者完全免费
- 注册后可查看企业联系电话

## 你的职责
1. 帮助求职者找到合适的工作岗位
2. 回答关于平台使用的问题（注册、查看电话等）
3. 提供求职建议
4. 语气亲切自然，像一个本地朋友在帮忙

## 回复规则
- 每次回复控制在200字以内
- 使用口语化表达，不要书面语
- 适当使用emoji增加亲和力
- 推荐岗位时要包含：岗位名称、公司、地点、薪资
- 如果用户问的不是找工作相关的问题，友好引导回正题
- 不要编造不存在的岗位信息
- 如果不确定，诚实说不知道，不要瞎编
- 回复结尾可以引导用户继续提问或尝试其他关键词

## 当前平台概况
{site_context}

## 可用岗位数据（用于推荐）
{job_data}
"""


def _build_site_context():
    """构建平台概览信息"""
    conn = get_recruit_db()
    ctx = []
    total = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='active'").fetchone()[0]
    ctx.append(f"平台共有{total}个在招岗位")

    cats = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM jobs WHERE status='active' GROUP BY category ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    if cats:
        ctx.append("热门行业：" + "、".join([f"{c['category']}({c['cnt']})" for c in cats[:8]]))

    locs = conn.execute(
        "SELECT location, COUNT(*) as cnt FROM jobs WHERE status='active' GROUP BY location ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    if locs:
        ctx.append("覆盖地区：" + "、".join([f"{l['location']}({l['cnt']})" for l in locs[:5]]))

    salaries = conn.execute(
        "SELECT AVG(salary_min) as avg_min FROM jobs WHERE status='active' AND salary_min > 0"
    ).fetchone()
    if salaries and salaries['avg_min']:
        ctx.append(f"平均薪资范围：{int(salaries['avg_min'])}元起")

    conn.close()
    return "\n".join(ctx)


def _get_relevant_jobs(query, limit=8):
    """根据查询获取相关岗位数据"""
    conn = get_recruit_db()
    q = query.strip()
    if not q:
        conn.close()
        return ""

    # 多关键词搜索
    keywords = []
    for word in re.findall(r'[\u4e00-\u9fff]{2,}', q):
        keywords.append(word)

    job_data = []
    if keywords:
        # 构建OR条件搜索
        conditions = []
        params = []
        for kw in keywords[:5]:
            conditions.append("(title LIKE ? OR company LIKE ? OR description LIKE ? OR category LIKE ? OR location LIKE ?)")
            p = f"%{kw}%"
            params.extend([p, p, p, p, p])
        where = " OR ".join(conditions)
        rows = conn.execute(
            f"SELECT id, title, company, location, salary_min, salary_max, salary_unit, category FROM jobs WHERE status='active' AND ({where}) ORDER BY created_at DESC LIMIT ?",
            params + [limit]
        ).fetchall()
        job_data = [dict(r) for r in rows]

    if not job_data:
        # 降级：返回最新岗位
        rows = conn.execute(
            "SELECT id, title, company, location, salary_min, salary_max, salary_unit, category FROM jobs WHERE status='active' ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        job_data = [dict(r) for r in rows]

    conn.close()

    # 格式化为AI可读的岗位列表
    lines = []
    for j in job_data:
        salary = ""
        if j.get('salary_min') and j.get('salary_max'):
            salary = f"{j['salary_min']}-{j['salary_max']}{j.get('salary_unit', '元/月')}"
        elif j.get('salary_min'):
            salary = f"{j['salary_min']}{j.get('salary_unit', '元/月')}"
        else:
            salary = "面议"
        lines.append(f"- [{j['title']}] {j['company']} | {j.get('location', '武鸣')} | {salary} | {j.get('category', '')}")

    return "\n".join(lines) if lines else "暂无具体岗位数据"


def _extract_keywords(message: str) -> str:
    """提取搜索关键词"""
    # 去除停用词
    stop_words = {"找", "想", "要", "有", "在", "的", "和", "或", "工作", "上班",
                  "招聘", "招人", "附近", "这边", "那个", "帮我", "推荐", "看看",
                  "什么", "哪些", "怎么", "你好", "在吗", "请问", "可以", "能",
                  "吗", "啦", "啊", "呢", "吧", "呀", "了", "是", "吗", "不", "没"}
    words = re.findall(r'[\u4e00-\u9fff]{2,}', message)
    filtered = [w for w in words if w not in stop_words]
    return " ".join(filtered) if filtered else message


def _generate_faq_reply(message: str) -> str:
    """生成FAQ类问题的回复（零延迟，不调用模型）"""
    msg = message.lower().strip()

    # 注册相关
    if any(w in msg for w in ["注册", "登录", "账号", "密码"]):
        return "📝 注册超简单的！点首页「登录/注册」，填个手机号和密码就搞定~注册完就能看到所有岗位的联系电话，找工作方便多了！"

    # 联系方式
    if any(w in msg for w in ["联系", "电话", "客服", "人工", "怎么联系"]):
        return "📞 想联系招聘方：\n1️⃣ 注册后能看到电话，直接打过去聊\n2️⃣ 页面底部点「反馈」也能找到我\n3️⃣ 或者直接转发招聘信息给我，我帮您对接~"

    # 看不到电话
    if any(w in msg for w in ["看不到", "看不了", "隐藏", "才能看"]):
        return "🔒 电话需要注册登录后才能看到哦，主要是为了保护招聘方的信息。注册很快的，填手机号和密码就行，一分钟搞定！"

    # 平台使用
    if any(w in msg for w in ["怎么用", "如何使用", "怎么找", "怎么操作"]):
        return "💡 用起来很简单：\n1️⃣ 首页刷岗位，按分类/地区筛选\n2️⃣ 点岗位卡片看详情\n3️⃣ 注册后直接打电话联系\n4️⃣ 也可以跟我说需求，我帮您智能匹配！"

    # 费用
    if any(w in msg for w in ["免费", "收费", "多少钱", "价格"]):
        return "✅ 对求职者完全免费！一分钱不收，放心用！只管专心找工作就好~"

    # 打招呼
    if any(w in msg for w in ["你好", "在吗", "hello", "hi", "嗨", "您好"]):
        return "👋 您好呀！我是武鸣招聘AI助手小武~您想找什么样的工作？直接跟我说「普工」「里建」「夜班」「包吃住」这些关键词就行，我帮您筛！"

    return None


async def ai_agent_reply(message: str, session_id: str = "", user_id: int = 0,
                         history: list = None) -> dict:
    """
    AI Agent智能回复主函数
    
    Args:
        message: 用户消息
        session_id: 会话ID
        user_id: 用户ID（0表示未登录）
        history: 历史消息列表
    
    Returns:
        dict: {reply, suggestions, model, user_id}
    """
    # 第一步：FAQ快速回复（零延迟）
    faq_reply = _generate_faq_reply(message)
    if faq_reply:
        return {
            "reply": faq_reply,
            "suggestions": ["普工", "夜班", "里建附近", "包吃住", "小时工"],
            "model": "faq",
            "user_id": user_id
        }

    # 第二步：构建上下文
    site_context = _build_site_context()
    keywords = _extract_keywords(message)
    relevant_jobs = _get_relevant_jobs(keywords)

    # 第三步：构建对话历史
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(
            site_context=site_context,
            job_data=relevant_jobs
        )}
    ]

    # 添加历史对话（如果有）
    if history:
        for h in history[-6:]:  # 最近6条
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    # 添加当前消息
    messages.append({"role": "user", "content": message})

    # 第四步：调用DeepSeek模型
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.7
                }
            )
            data = resp.json()
            choice = data.get("choices", [{}])[0] if "choices" in data else {}
            reply = choice.get("message", {}).get("content", "").strip()

            if not reply:
                reply = "🤔 抱歉，我暂时没理解您的问题。您可以试试说「找普工」「里建夜班」「包吃住」之类的关键词~"
    except Exception as e:
        # 模型调用失败时的降级回复
        reply = _generate_fallback_reply(message, relevant_jobs)

    # 第五步：生成建议追问
    suggestions = _generate_suggestions(message, relevant_jobs)

    return {
        "reply": reply,
        "suggestions": suggestions,
        "model": "ai-agent",
        "user_id": user_id
    }


def _generate_fallback_reply(message: str, job_data: str) -> str:
    """模型调用失败时的降级回复"""
    if "注册" in message or "登录" in message:
        return "📝 注册超简单的！点首页「登录/注册」，填个手机号和密码就搞定~"
    if "免费" in message or "收费" in message:
        return "✅ 对求职者完全免费！一分钱不收~"
    if "你好" in message or "在吗" in message:
        return "👋 您好呀！我是武鸣招聘AI助手小武~您想找什么样的工作？直接跟我说「普工」「里建」「夜班」这些关键词就行~"

    # 通用降级
    if job_data:
        return f"🤔 抱歉，AI服务暂时繁忙。不过我帮您看看这些岗位：\n{job_data[:300]}\n\n💡 您也可以试试说「普工」「夜班」「包吃住」之类的关键词~"
    return "🤔 抱歉，AI服务暂时繁忙。您可以试试说「找普工」「里建夜班」「包吃住」之类的关键词~"


def _generate_suggestions(message: str, job_data: str) -> list:
    """生成建议追问"""
    msg_lower = message.lower()

    # 根据消息类型推荐
    if "普工" in message or "工作" in message:
        return ["包吃住", "长白班", "里建附近", "小时工", "夜班"]
    if "里建" in message or "东盟" in message:
        return ["普工", "包吃住", "长白班", "食品厂"]
    if "夜班" in message:
        return ["包吃住", "小时工", "里建附近", "食品厂"]
    if "包吃住" in message:
        return ["普工", "夜班", "里建附近", "食品厂"]
    if "兼职" in message or "学生" in message:
        return ["日结", "小时工", "里建附近", "食品厂"]

    # 默认推荐
    return ["普工", "夜班", "里建附近", "包吃住", "小时工"]


async def ai_agent_chat_send(message: str, conversation_id: int) -> str:
    """
    聊天发送后的AI自动回复（替代原有的关键词匹配）
    
    Args:
        message: 用户消息
        conversation_id: 对话ID
    
    Returns:
        str: AI回复内容
    """
    # 获取对话上下文
    conn = get_recruit_db()
    conv = conn.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
    if not conv:
        conn.close()
        return None

    # 获取该对话的历史消息
    msgs = conn.execute(
        "SELECT sender_type, content, created_at FROM messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT 10",
        (conversation_id,)
    ).fetchall()
    conn.close()

    # 构建历史消息列表
    history = []
    for m in reversed(msgs):
        if m["sender_type"] in ("user", "guest"):
            history.append({"role": "user", "content": m["content"]})
        elif m["sender_type"] == "system":
            history.append({"role": "assistant", "content": m["content"]})

    # 调用AI Agent
    result = await ai_agent_reply(message, history=history)
    return result.get("reply")
