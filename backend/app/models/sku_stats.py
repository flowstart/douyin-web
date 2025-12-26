"""
SKU统计模型
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.database import Base


class SkuStats(Base):
    """SKU统计缓存表 - 存储最新一份统计快照"""
    __tablename__ = "sku_stats"
    __table_args__ = (
        UniqueConstraint("sku_code", name="uix_sku_code"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # SKU信息
    sku_id: Mapped[str] = mapped_column(String(64), index=True, comment="SKU ID")
    sku_code: Mapped[str] = mapped_column(String(64), index=True, comment="商家SKU编码")
    sku_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="SKU名称")
    product_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="商品名称")
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="商品图片URL")
    
    # 核心统计指标
    pending_ship_count: Mapped[int] = mapped_column(Integer, default=0, comment="待发货量")
    aftersale_pending_count: Mapped[int] = mapped_column(Integer, default=0, comment="售后未完结数量")
    signed_count: Mapped[int] = mapped_column(Integer, default=0, comment="已签收数量（近90天）")
    signed_return_count: Mapped[int] = mapped_column(Integer, default=0, comment="已签收订单的退货数量（近90天）")
    
    # 预估退货率（已签收订单的退货数量/已签收数量，<10单默认30%）
    estimated_return_rate: Mapped[float] = mapped_column(Float, default=0.3, comment="预估退货率")
    is_rate_manual: Mapped[bool] = mapped_column(default=False, comment="退货率是否手动修改")
    
    # 在途统计
    in_transit_count: Mapped[int] = mapped_column(Integer, default=0, comment="已发货在途未签收数量")
    in_transit_return_estimate: Mapped[int] = mapped_column(Integer, default=0, comment="已发货在途预估退货数量")
    
    # 商品缺口 = 待发货数量 - 售后未完结数量 - 已发货在途预估退货数量
    stock_gap: Mapped[int] = mapped_column(Integer, default=0, comment="预估商品缺口")
    
    # 品质退货统计
    quality_return_count: Mapped[int] = mapped_column(Integer, default=0, comment="品质问题退货数量")
    quality_return_rate: Mapped[float] = mapped_column(Float, default=0, comment="品质退货率")
    
    # 系统字段
    last_calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="最后计算时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="记录创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="记录更新时间")

