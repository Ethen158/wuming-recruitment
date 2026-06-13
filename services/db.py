"""
数据库服务 - 连接管理、索引管理、辅助函数
"""
import os
import sqlite3
from config import settings

RECRUIT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    settings.DATABASE_PATH
)


def get_recruit_db() -> sqlite3.Connection:
    """获取数据库连接（row_factory=sqlite3.Row）"""
    conn = sqlite3.connect(RECRUIT_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_indexes():
    """确保数据库索引存在"""
    conn = get_recruit_db()
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(category)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_conv_ent ON conversations(enterprise_id)",
        "CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_ent_name ON enterprises(company_name)",
        "CREATE INDEX IF NOT EXISTS idx_resume_user ON resumes(user_id)",
    ]:
        conn.execute(idx_sql)
    conn.commit()
    conn.close()


def _clean_company_desc(desc: str) -> str:
    """清理公司描述中的AI提示词痕迹"""
    if not desc:
        return ""
    ai_patterns = ['所以我的输出', '首先我得', '用户提供', '好的用户', '让我',
                   '根据要求', '再确认', '扫描一下', '看看数据', '我得先',
                   '先看看', '我需要', '公司名：', '现有信息：', '用户要求',
                   'assistant', 'prompt', '输出必须是']
    for p in ai_patterns:
        if p in desc:
            lines = desc.split('\n')
            clean_lines = []
            for line in lines:
                if not any(ap in line for ap in ai_patterns):
                    clean_lines.append(line)
            desc = '\n'.join(clean_lines).strip()
            break
    return desc


def time_ago(ts: str) -> str:
    """显示相对时间：今天/昨天/X天前/X周前"""
    if not ts:
        return ""
    try:
        from datetime import datetime
        dt = datetime.strptime(ts[:10], "%Y-%m-%d")
        days = (datetime.now() - dt).days
        if days == 0:
            return "今天"
        if days == 1:
            return "昨天"
        if days < 7:
            return f"{days}天前"
        if days < 30:
            return f"{days//7}周前"
        return f"{days//30}月前"
    except Exception:
        return ts[:10]


def days_ago(ts: str) -> int:
    """返回发布时间距今的天数"""
    if not ts:
        return 999
    try:
        from datetime import datetime
        dt = datetime.strptime(ts[:10], "%Y-%m-%d")
        return (datetime.now() - dt).days
    except Exception:
        return 999


def get_salary_display(salary_min, salary_max, salary_unit="元/月"):
    """格式化薪资显示"""
    s_min = salary_min or 0
    s_max = salary_max or 0
    if s_min == 0 and s_max == 0:
        return "面议"
    elif s_max:
        return f"{s_min}-{s_max}{salary_unit}"
    else:
        return f"{s_min}{salary_unit}"


def get_salary_html(salary_min, salary_max, salary_unit="元/月"):
    """格式化薪资HTML显示"""
    s_min = salary_min or 0
    s_max = salary_max or 0
    if s_min == 0 and s_max == 0:
        return '<span class="salary-negotiable">面议</span>'
    elif s_max:
        return f'{s_min}-{s_max}{salary_unit}'
    else:
        return f'{s_min}{salary_unit}'
