"""
售后单模型
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.database import Base


class AfterSale(Base):
    """售后单表"""
    __tablename__ = "after_sales"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 售后单基本信息
    aftersale_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="售后单号")
    order_id: Mapped[str] = mapped_column(String(64), index=True, comment="关联订单号")
    
    # SKU信息
    sku_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, comment="SKU ID")
    sku_code: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, comment="商家SKU编码")
    sku_code_raw: Mapped[Optional[str]] = mapped_column(
        String(128), index=True, nullable=True, comment="原始商家SKU编码（未去括号，用于追溯）"
    )
    
    # 售后类型和状态
    aftersale_type: Mapped[int] = mapped_column(Integer, comment="售后类型: 1-退货退款 2-仅退款 3-换货")
    aftersale_status: Mapped[int] = mapped_column(Integer, index=True, comment="售后状态")
    aftersale_status_desc: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="售后状态描述")
    
    # 退货原因
    reason_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="退货原因代码")
    reason_text: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="退货原因文本")
    is_quality_issue: Mapped[bool] = mapped_column(default=False, comment="是否品质问题")
    
    # 金额信息
    refund_amount: Mapped[float] = mapped_column(Float, default=0, comment="退款金额")
    
    # 时间信息
    apply_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="申请时间")
    finish_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="完成时间")
    
    # 省份信息（冗余存储，便于统计）
    province_id: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True, comment="省份ID")
    province_name: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="省份名称")
    
    # 系统字段
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="记录创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="记录更新时间")

