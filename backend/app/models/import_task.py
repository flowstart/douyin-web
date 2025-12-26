"""
导入任务模型
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional, Dict, Any

from app.database import Base


class ImportTask(Base):
    """导入任务表"""
    __tablename__ = "import_tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 任务标识
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="任务ID")
    task_type: Mapped[str] = mapped_column(String(32), comment="任务类型: orders/aftersales/all")
    
    # 状态信息
    status: Mapped[str] = mapped_column(String(32), default="processing", comment="状态: processing/completed/failed")
    progress: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="当前进度描述")
    
    # 文件信息
    filename: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="文件名")
    
    # 导入统计 (JSON 格式存储)
    order_stats: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="订单导入统计")
    aftersale_stats: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="售后单导入统计")
    sku_stats_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="SKU统计数量")
    
    # 错误信息
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误信息")
    
    # 时间信息
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="开始时间")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="完成时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "filename": self.filename,
            "order_stats": self.order_stats,
            "aftersale_stats": self.aftersale_stats,
            "sku_stats_count": self.sku_stats_count,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

