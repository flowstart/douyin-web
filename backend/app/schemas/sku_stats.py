"""
SKU统计相关 Schema
"""
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List


class SkuStatsSchema(BaseModel):
    """SKU统计信息"""
    sku_id: str
    sku_code: str
    sku_name: Optional[str] = None
    product_name: Optional[str] = None
    image_url: Optional[str] = None      # 商品图片URL
    
    # 核心指标
    pending_ship_count: int = 0          # 待发货量
    aftersale_pending_count: int = 0     # 售后未完结数量
    signed_count: int = 0                # 已签收数量
    signed_return_count: int = 0         # 已签收订单的退货数量
    estimated_return_rate: float = 0.3   # 预估退货率
    is_rate_manual: bool = False         # 是否手动修改
    
    # 在途统计
    in_transit_count: int = 0            # 已发货在途未签收数量
    in_transit_return_estimate: int = 0  # 已发货在途预估退货数量
    
    # 商品缺口
    stock_gap: int = 0                   # 预估商品缺口
    
    # 品质退货
    quality_return_count: int = 0        # 品质问题退货数量
    quality_return_rate: float = 0       # 品质退货率
    
    # 计算时间
    last_calculated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SkuStatsListResponse(BaseModel):
    """SKU统计列表响应"""
    total: int
    items: List[SkuStatsSchema]
    is_realtime: bool = False  # 是否实时计算（有时间筛选时为True）


class SkuStatsQuery(BaseModel):
    """SKU统计查询参数"""
    start_date: Optional[date] = None    # 订单支付时间开始
    end_date: Optional[date] = None      # 订单支付时间结束
    sku_code: Optional[str] = None       # 指定SKU搜索
    top_n: Optional[int] = None          # 按待发货量排序的前N名
    sort_by: str = "pending_ship_count"  # 排序字段
    sort_order: str = "desc"             # 排序方向
    page: int = 1
    page_size: int = 20


class StatsSummary(BaseModel):
    """统计汇总数据（用于数据看板）"""
    total_orders: int = 0                # 订单总数
    pending_ship_orders: int = 0         # 待发货订单数
    aftersale_pending_count: int = 0     # 售后未完结数
    signed_orders: int = 0               # 已签收订单数
    total_stock_gap: int = 0             # 总商品缺口
    last_import_time: Optional[datetime] = None  # 最后导入时间
    last_calculated_at: Optional[datetime] = None  # 最后计算时间

