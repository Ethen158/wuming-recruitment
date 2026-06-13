#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
武鸣招聘平台 - 启动入口
"""
from config import settings

if __name__ == "__main__":
    import uvicorn
    print("🏭 武鸣招聘平台启动中...")
    print(f"   公开首页: http://{settings.APP_HOST}:{settings.APP_PORT}")
    print(f"   管理后台: http://{settings.APP_HOST}:{settings.APP_PORT}/login")
    print(f"   视频模式: http://{settings.APP_HOST}:{settings.APP_PORT}/recruit/video")
    uvicorn.run("app:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=False)
