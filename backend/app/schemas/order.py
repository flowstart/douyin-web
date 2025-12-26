"""
订单相关 Schema
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class OrderSkuSchema(BaseModel):
    """订单SKU信息"""
    sku_id: str
    sku_code: Optional[str] = None
    sku_name: Optional[str] = None
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    quantity: int = 1
    price: float = 0
    
    class Config:
        from_attributes = True


class OrderSchema(BaseModel):
    """订单信息"""
    order_id: str
    order_status: int
    order_status_desc: str
    create_time: datetime
    update_time: Optional[datetime] = None
    pay_time: Optional[datetime] = None
    
    # 收货人信息
    receiver_name: Optional[str] = None
    province_id: Optional[str] = None
    province_name: Optional[str] = None
    city_name: Optional[str] = None
    
    # 物流信息
    logistics_code: Optional[str] = None
    logistics_status: Optional[int] = None
    logistics_status_desc: Optional[str] = None
    is_signed: bool = False
    sign_time: Optional[datetime] = None
    
    # 金额信息
    total_amount: float = 0
    pay_amount: float = 0
    
    # SKU列表
    sku_list: List[OrderSkuSchema] = []
    
    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    """订单列表响应"""
    total: int
    items: List[OrderSchema]

