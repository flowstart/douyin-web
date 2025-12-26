"""
售后单相关 Schema
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class AfterSaleSchema(BaseModel):
    """售后单信息"""
    aftersale_id: str
    order_id: str
    sku_id: Optional[str] = None
    sku_code: Optional[str] = None
    
    # 售后类型和状态
    aftersale_type: int
    aftersale_status: int
    aftersale_status_desc: Optional[str] = None
    
    # 退货原因
    reason_code: Optional[str] = None
    reason_text: Optional[str] = None
    is_quality_issue: bool = False
    
    # 金额
    refund_amount: float = 0
    
    # 时间
    apply_time: Optional[datetime] = None
    finish_time: Optional[datetime] = None
    
    # 省份
    province_id: Optional[str] = None
    province_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class AfterSaleListResponse(BaseModel):
    """售后单列表响应"""
    total: int
    items: List[AfterSaleSchema]

