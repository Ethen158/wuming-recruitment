"""
聊天记忆服务 - 持久化每个用户的聊天历史、偏好提取、欢迎语
"""
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from services.db import get_recruit_db


def _get_conn():
    return get_recruit_db()


def save_message(user_id: int, session_id: str, role: str, content: str, topics: str = ""):
    """保存一条聊天记录到数据库"""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO chat_memory (user_id, session_id, role, content, topics, created_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
        (user_id, session_id, role, content[:500], topics)
    )
    conn.commit()
    conn.close()


def get_recent_history(user_id: int, session_id: str, limit: int = 10) -> List[Dict]:
    """获取用户最近聊天的上下文，登录用户跨session获取，匿名按session"""
    conn = _get_conn()
    if user_id and user_id > 0:
        rows = conn.execute(
            "SELECT role, content, created_at FROM chat_memory "
            "WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT role, content, created_at FROM chat_memory "
            "WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_user_stats(user_id: int) -> dict:
    """获取用户统计信息（用于欢迎语）"""
    conn = _get_conn()
    # 总对话次数
    total = conn.execute(
        "SELECT COUNT(*) FROM chat_memory WHERE user_id=? AND role='user'",
        (user_id,)
    ).fetchone()[0]
    # 最近一次聊天时间
    last = conn.execute(
        "SELECT MAX(created_at) FROM chat_memory WHERE user_id=? AND role='user'",
        (user_id,)
    ).fetchone()[0]
    # 常用查询主题（取最近3条用户消息的关键词）
    recent = conn.execute(
        "SELECT content FROM chat_memory WHERE user_id=? AND role='user' ORDER BY id DESC LIMIT 5",
        (user_id,)
    ).fetchall()
    conn.close()

    topics = []
    for r in recent:
        msg = r[0]
        # 提取关键词（2-4字中文）
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', msg)
        for w in words:
            if w not in ["什么", "怎么", "哪些", "哪个", "多少", "有没有", "请问", "你好", "在吗",
                          "可以", "告诉", "想要", "他们", "或者", "没有", "不是"]:
                topics.append(w)

    return {
        "total_queries": total,
        "last_seen": last or "",
        "recent_topics": list(dict.fromkeys(topics))[:3],
    }


def update_user_preferences(user_id: int, query: str, results_count: int):
    """从用户查询中提取偏好并保存"""
    if not user_id or user_id <= 0:
        return

    conn = _get_conn()
    row = conn.execute("SELECT prefs FROM user_preferences WHERE user_id=?", (user_id,)).fetchone()
    prefs = json.loads(row[0]) if row else {}

    # 提取地点偏好
    loc_match = re.search(r'(里建|武鸣|南宁|东盟)', query)
    if loc_match:
        loc = loc_match.group(1)
        loc_prefs = prefs.get("locations", [])
        if loc in loc_prefs:
            loc_prefs.remove(loc)
        loc_prefs.insert(0, loc)
        prefs["locations"] = loc_prefs[:3]

    # 提取岗位类型偏好
    type_kws = ["普工", "夜班", "白班", "小时工", "兼职", "保安", "保洁", "司机",
                "文员", "销售", "厨师", "搬运", "包装", "食品", "物流"]
    for kw in type_kws:
        if kw in query:
            type_prefs = prefs.get("job_types", [])
            if kw in type_prefs:
                type_prefs.remove(kw)
            type_prefs.insert(0, kw)
            prefs["job_types"] = type_prefs[:3]
            break

    # 更新总查询次数
    total = prefs.get("total_queries", 0) + 1
    prefs["total_queries"] = total
    prefs["last_query"] = query[:100]

    if row:
        conn.execute(
            "UPDATE user_preferences SET prefs=?, last_seen=datetime('now','localtime'), total_queries=? WHERE user_id=?",
            (json.dumps(prefs, ensure_ascii=False), total, user_id)
        )
    else:
        conn.execute(
            "INSERT INTO user_preferences (user_id, prefs, first_seen, last_seen, total_queries) "
            "VALUES (?, ?, datetime('now','localtime'), datetime('now','localtime'), ?)",
            (user_id, json.dumps(prefs, ensure_ascii=False), total)
        )
    conn.commit()
    conn.close()


def get_welcome_message(user_id: int) -> Optional[str]:
    """生成个性化欢迎语"""
    if not user_id or user_id <= 0:
        return None

    stats = get_user_stats(user_id)
    if stats["total_queries"] < 2:
        return None

    if stats["recent_topics"]:
        topics_str = "、".join(stats["recent_topics"])
        time_str = ""
        if stats["last_seen"]:
            try:
                last = datetime.strptime(stats["last_seen"], "%Y-%m-%d %H:%M:%S")
                hours_ago = (datetime.now() - last).total_seconds() / 3600
                if hours_ago < 2:
                    time_str = "刚走开一会儿"
                elif hours_ago < 24:
                    time_str = f"{int(hours_ago)}小时前"
                else:
                    time_str = f"{int(hours_ago/24)}天前"
            except:
                pass

        prefix = f" ({time_str})" if time_str else ""
        return f"👋 欢迎回来{prefix}！上次聊了「{topics_str}」，继续帮您找合适的工作~"
    return None


def merge_anonymous_history(session_id: str, user_id: int):
    """匿名用户登录后，把session历史合并到用户账号下"""
    if not user_id or user_id <= 0:
        return
    conn = _get_conn()
    conn.execute(
        "UPDATE chat_memory SET user_id=? WHERE session_id=? AND (user_id IS NULL OR user_id=0)",
        (user_id, session_id)
    )
    conn.commit()
    conn.close()
