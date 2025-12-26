"""
系统配置模型
"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_configs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 配置键（唯一）
    config_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="配置键")
    
    # 配置值
    config_value: Mapped[str] = mapped_column(Text, default="", comment="配置值")
    
    # 描述
    description: Mapped[str] = mapped_column(String(256), default="", comment="配置描述")
    
    # 时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


# 预定义配置键
class ConfigKeys:
    """配置键常量"""
    KD100_CUSTOMER = "kd100_customer"
    KD100_KEY = "kd100_key"
    LOGISTICS_QUERY_INTERVAL = "logistics_query_interval"  # 物流查询间隔（分钟）


# 默认配置值
DEFAULT_CONFIGS = {
    ConfigKeys.KD100_CUSTOMER: {
        "value": "",
        "description": "快递100 Customer ID"
    },
    ConfigKeys.KD100_KEY: {
        "value": "",
        "description": "快递100 API Key"
    },
    ConfigKeys.LOGISTICS_QUERY_INTERVAL: {
        "value": "35",
        "description": "同一物流单号查询间隔（分钟），默认35分钟"
    },
}

