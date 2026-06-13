"""
认证服务 - 管理员认证（bcrypt）、求职者认证（token）、企业认证（token）
"""
import os
import secrets
import hashlib
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request

from config import settings
from services.db import get_recruit_db

SESSION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".web_session_key"
)
USER_SESSION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".user_session_key"
)


# ====== 管理员认证 ======

def _load_session_key() -> Optional[str]:
    """读取持久化的会话密钥"""
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE) as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def _save_session_key(key: str):
    """保存会话密钥"""
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        f.write(key)


def _make_token(password: str, salt: Optional[str] = None) -> str:
    """生成认证 token (bcrypt)"""
    if salt is None:
        salt = secrets.token_hex(16)
    h = bcrypt.hashpw(f"{password}:::{salt}".encode(), bcrypt.gensalt()).decode()
    return f"{salt}::{h}"


def _verify_token(token: str, password: str) -> bool:
    """验证 token (新格式 bcrypt + 旧版 sha256 兼容)"""
    try:
        salt, h = token.split("::", 1)
    except Exception:
        return False

    # 新格式：bcrypt token (以 $2 开头)
    if h.startswith("$2"):
        try:
            expected_new = bcrypt.hashpw(f"{password}:::{salt}".encode(), h.encode()).decode()
            if h == expected_new:
                return True
        except Exception:
            pass  # bcrypt 验证失败，回退到 sha256 检查

    # 旧版格式：sha256 hexdigest
    expected_old = hashlib.sha256(f"{password}:::{salt}".encode()).hexdigest()
    return h == expected_old


def check_auth(request: Request) -> bool:
    """检查管理员是否已登录"""
    token = request.cookies.get("session")
    if not token:
        return False
    return _verify_token(token, settings.ADMIN_PASSWORD)


# ====== 求职者认证 ======

def check_user(request: Request) -> Optional[int]:
    """检查求职者是否登录，返回user_id或None"""
    token = request.cookies.get("user_session")
    if not token:
        return None
    try:
        conn = get_recruit_db()
        uid = conn.execute(
            "SELECT user_id FROM user_tokens WHERE token=? AND expire_at>datetime('now')",
            (token,)
        ).fetchone()
        conn.close()
        if uid:
            return uid["user_id"]
    except Exception:
        pass
    return None


def get_user_info(user_id: int) -> Optional[dict]:
    """获取用户信息"""
    if not user_id:
        return None
    conn = get_recruit_db()
    u = conn.execute(
        "SELECT id, nickname, phone, wechat FROM users WHERE id=?",
        (user_id,)
    ).fetchone()
    conn.close()
    return dict(u) if u else None


def set_user_session(response, token: str, max_age: int = 30 * 86400):
    """设置用户会话cookie"""
    response.set_cookie("user_session", token, max_age=max_age,
                        httponly=True, samesite="lax", path="/")
    response.delete_cookie("session", path="/")
    response.delete_cookie("ent_session", path="/")


def clear_user_session(response):
    """清除用户会话cookie"""
    response.delete_cookie("user_session", path="/")


# ====== 企业认证 ======

def check_enterprise(request: Request) -> Optional[dict]:
    """检查企业是否登录，返回企业信息dict或None"""
    token = request.cookies.get("ent_session")
    if not token:
        return None
    try:
        conn = get_recruit_db()
        ent = conn.execute(
            "SELECT e.* FROM enterprises e JOIN enterprise_tokens t ON e.id=t.enterprise_id "
            "WHERE t.token=? AND t.expire_at>datetime('now')",
            (token,)
        ).fetchone()
        conn.close()
        return dict(ent) if ent else None
    except Exception:
        return None


def get_enterprise_info(ent_id: int) -> Optional[dict]:
    """获取企业信息"""
    conn = get_recruit_db()
    e = conn.execute("SELECT * FROM enterprises WHERE id=?", (ent_id,)).fetchone()
    conn.close()
    return dict(e) if e else None


def make_ent_token(ent_id: int) -> str:
    """生成企业登录token"""
    token = secrets.token_hex(32)
    conn = get_recruit_db()
    exp = (datetime.now() + timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO enterprise_tokens (enterprise_id, token, expire_at, created_at) VALUES (?,?,?,?)",
        (ent_id, token, exp, now)
    )
    conn.commit()
    conn.close()
    return token


def make_ent_password(password: str) -> str:
    """生成企业密码hash"""
    return bcrypt.hashpw(f"ent::{password}".encode(), bcrypt.gensalt()).decode()


def make_admin_token(password: str) -> str:
    """生成管理员登录token"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{password}:::{salt}".encode()).hexdigest()
    token = f"{salt}::{hashed}"
    _save_session_key(token)
    return token
