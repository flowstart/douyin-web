"""
订单相关 API
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.order import Order, OrderSku
from app.schemas.order import OrderSchema, OrderListResponse

router = APIRouter()


@router.get("", response_model=OrderListResponse)
async def get_orders(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    order_status: Optional[int] = Query(None, description="订单状态"),
    province_id: Optional[str] = Query(None, description="省份ID"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    db: AsyncSession = Depends(get_db),
):
    """获取订单列表"""
    
    # 构建查询，预加载 sku_list 关联
    stmt = select(Order).options(selectinload(Order.sku_list))
    
    if order_status is not None:
        stmt = stmt.where(Order.order_status == order_status)
    if province_id:
        stmt = stmt.where(Order.province_id == province_id)
    if start_date:
        stmt = stmt.where(Order.create_time >= start_date)
    if end_date:
        stmt = stmt.where(Order.create_time <= end_date)
    
    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.order_by(Order.create_time.desc()).offset(offset).limit(page_size)
    
    # 执行查询
    result = await db.execute(stmt)
    orders = result.scalars().all()
    
    # 获取总数
    count_stmt = select(func.count()).select_from(Order)
    if order_status is not None:
        count_stmt = count_stmt.where(Order.order_status == order_status)
    if province_id:
        count_stmt = count_stmt.where(Order.province_id == province_id)
    if start_date:
        count_stmt = count_stmt.where(Order.create_time >= start_date)
    if end_date:
        count_stmt = count_stmt.where(Order.create_time <= end_date)
    
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    return OrderListResponse(total=total, items=orders)


@router.get("/{order_id}", response_model=OrderSchema)
async def get_order_detail(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取订单详情"""
    
    result = await db.execute(
        select(Order).where(Order.order_id == order_id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="订单不存在")
    
    return order

