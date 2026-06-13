"""
武鸣招聘平台 - 配置管理
从 .env 文件加载敏感配置，提供类型安全的 Settings 对象
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务器
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080
    APP_DEBUG: bool = False

    # 认证
    ADMIN_PASSWORD: str  # 必填，无默认值
    SESSION_HOURS: int = 72

    # 微信小程序
    MINI_APPID: str = "wxb64c75249902e850"
    MINI_APPSECRET: str  # 必填，无默认值

    # 数据库
    DATABASE_PATH: str = "wuming_recruitment.db"

    # 站点
    SITE_URL: str = "https://job.airabbit.cn"
    SITE_NAME: str = "武鸣招聘"

    # 模板
    CSS_VERSION: str = "v20260612g"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
