"""
微信小程序集成 - access_token、模板消息、推送
"""
import json
from datetime import datetime, timedelta
from typing import Optional
import httpx

from config import settings
from services.db import get_recruit_db


def get_mini_access_token() -> Optional[str]:
    """获取小程序access_token（带缓存）"""
    conn = get_recruit_db()
    row = conn.execute(
        "SELECT access_token, token_expires_at FROM wechat_mini_config WHERE id=1"
    ).fetchone()

    if row and row["access_token"] and row["token_expires_at"]:
        expires = datetime.fromisoformat(row["token_expires_at"])
        if datetime.now() < expires - timedelta(minutes=5):
            conn.close()
            return row["access_token"]

    try:
        resp = httpx.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": settings.MINI_APPID,
                "secret": settings.MINI_APPSECRET
            },
            timeout=10
        )
        data = resp.json()
        if "access_token" in data:
            token = data["access_token"]
            expires_in = data.get("expires_in", 7200)
            expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
            conn.execute(
                "UPDATE wechat_mini_config SET access_token=?, token_expires_at=? WHERE id=1",
                (token, expires_at)
            )
            conn.commit()
            conn.close()
            print(f"[MINI] access_token 获取成功，有效期 {expires_in}s")
            return token
        else:
            print(f"[MINI] access_token 获取失败: {data}")
            conn.close()
            return None
    except Exception as e:
        print(f"[MINI] access_token 异常: {e}")
        conn.close()
        return None


def send_mini_template_msg(
    openid: str,
    template_id: str,
    data: dict,
    page: str = "/pages/index/index"
) -> dict:
    """发送小程序模板消息"""
    token = get_mini_access_token()
    if not token:
        return {"error": "获取access_token失败"}
    payload = {
        "touser": openid,
        "template_id": template_id,
        "page": page,
        "data": data
    }
    try:
        resp = httpx.post(
            f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}",
            json=payload,
            timeout=10
        )
        result = resp.json()
        print(f"[MINI] 模板消息发送: openid={openid[:8]}..., result={result}")
        return result
    except Exception as e:
        print(f"[MINI] 模板消息异常: {e}")
        return {"error": str(e)}


def send_mini_job_push(openid: str, job: dict) -> dict:
    """发送职位推送模板消息"""
    template_id = "TEMPLATE_ID_HERE"
    data = {
        "thing1": {"value": job.get("title", "新职位")},
        "thing2": {"value": job.get("company", "未知公司")},
        "thing3": {"value": job.get("salary", "面议")},
        "thing4": {"value": job.get("location", "武鸣")},
    }
    return send_mini_template_msg(openid, template_id, data)
