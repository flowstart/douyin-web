"""
订单模型
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional

from app.database import Base


class Order(Base):
    """订单表"""
    __tablename__ = "orders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 订单基本信息
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="抖音订单号")
    order_status: Mapped[int] = mapped_column(Integer, index=True, comment="订单状态")
    order_status_desc: Mapped[str] = mapped_column(String(32), comment="订单状态描述")
    
    # 时间信息
    create_time: Mapped[datetime] = mapped_column(DateTime, index=True, comment="订单创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="订单更新时间")
    pay_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="支付时间")
    
    # 收货人信息
    receiver_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="收货人姓名")
    province_id: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True, comment="省份ID")
    province_name: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="省份名称")
    city_name: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="城市名称")
    
    # 物流信息
    logistics_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True, comment="物流单号")
    logistics_company: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="快递公司")
    logistics_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="物流状态")
    logistics_status_desc: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="物流状态描述")
    is_signed: Mapped[bool] = mapped_column(default=False, comment="是否已签收")
    sign_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="签收时间")
    logistics_checked: Mapped[bool] = mapped_column(default=False, comment="是否已查询物流状态")
    
    # 金额信息
    total_amount: Mapped[float] = mapped_column(Float, default=0, comment="订单总金额")
    pay_amount: Mapped[float] = mapped_column(Float, default=0, comment="实付金额")
    
    # 系统字段
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="记录创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="记录更新时间")
    
    # 关联关系
    sku_list: Mapped[List["OrderSku"]] = relationship("OrderSku", back_populates="order", cascade="all, delete-orphan")


class OrderSku(Base):
    """订单SKU表"""
    __tablename__ = "order_skus"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 关联订单
    order_id: Mapped[str] = mapped_column(String(64), ForeignKey("orders.order_id"), index=True, comment="抖音订单号")
    
    # SKU信息
    sku_id: Mapped[str] = mapped_column(String(64), index=True, comment="SKU ID")
    sku_code: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, comment="商家SKU编码")
    sku_code_raw: Mapped[Optional[str]] = mapped_column(
        String(128), index=True, nullable=True, comment="原始商家SKU编码（未去括号，用于追溯）"
    )
    sku_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="SKU名称")
    
    # 商品信息
    product_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="商品ID")
    product_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="商品名称")
    
    # 数量和价格
    quantity: Mapped[int] = mapped_column(Integer, default=1, comment="购买数量")
    price: Mapped[float] = mapped_column(Float, default=0, comment="单价")
    
    # 系统字段
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="记录创建时间")
    
    # 关联关系
    order: Mapped["Order"] = relationship("Order", back_populates="sku_list")

