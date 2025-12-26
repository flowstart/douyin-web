"""
应用配置模块
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # 快递100 API配置
    kd100_key: str = ""
    kd100_customer: str = ""
    
    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./douyin_orders.db"

    # SQLAlchemy 日志（非常影响导入性能，默认关闭；需要排查 SQL 时再打开）
    sqlalchemy_echo: bool = False

    # 是否启用导入 Worker（生产/多进程部署时可关闭，改用单独 worker 进程）
    enable_import_worker: bool = True
    import_worker_poll_interval: float = 1.0
    
    # 服务配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # 快递100 API地址
    kd100_api_url: str = "https://poll.kuaidi100.com/poll/query.do"
    
    # 文件上传目录
    upload_dir: str = "./uploads"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取应用配置（缓存）"""
    return Settings()

