"""
导入队列任务（Worker 用）

说明：
- ImportTask 负责“给前端展示”的任务记录（状态/进度/统计）
- ImportJob 负责“可被 worker 安全消费”的队列任务（持久化、可重试）
"""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportJob(Base):
    """导入队列任务表"""

    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="关联的任务ID")
    task_type: Mapped[str] = mapped_column(String(32), comment="任务类型: orders/aftersales/all")

    # queued -> processing -> completed/failed
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True, comment="队列状态")

    # payload 示例：
    # - orders: {"orders_filename": "..."}
    # - aftersales: {"aftersales_filename": "..."}
    # - all: {"orders_filename": "...", "aftersales_filename": "..."}
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="任务参数")

    picked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="被 worker 取走时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


