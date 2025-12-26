"""
统计相关 API
"""
from datetime import date, datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.schemas.sku_stats import SkuStatsQuery, SkuStatsListResponse, StatsSummary
from app.services.stats_service import StatsService
from app.models.order import Order

router = APIRouter()


class TrendItem(BaseModel):
    """趋势数据项"""
    time_label: str
    order_count: int
    pending_ship_count: int = 0
    shipped_count: int = 0
    refunded_count: int = 0


@router.get("/sku", response_model=SkuStatsListResponse)
async def get_sku_stats(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    sku_code: Optional[str] = Query(None, description="SKU编码搜索"),
    top_n: Optional[int] = Query(None, ge=1, le=100, description="Top N"),
    sort_by: str = Query("pending_ship_count", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取SKU统计数据
    
    - 支持时间区间筛选
    - 支持SKU搜索
    - 支持Top N查询
    - 支持自定义排序
    """
    query = SkuStatsQuery(
        start_date=start_date,
        end_date=end_date,
        sku_code=sku_code,
        top_n=top_n,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    
    stats_service = StatsService(db)
    result = await stats_service.get_sku_stats(query)
    
    return SkuStatsListResponse(**result)


@router.post("/sku/calculate")
async def calculate_sku_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    重新计算SKU统计数据
    
    手动触发统计计算，会更新今天的统计快照
    """
    stats_service = StatsService(db)
    
    # 计算统计数据
    stats_list = await stats_service.calculate_sku_stats()
    
    # 保存统计数据
    count = await stats_service.save_sku_stats(stats_list)
    
    return {
        "message": "统计计算完成",
        "count": count,
    }


@router.put("/sku/{sku_code}/return-rate")
async def update_return_rate(
    sku_code: str,
    return_rate: float = Query(..., ge=0, le=1, description="退货率(0-1)"),
    db: AsyncSession = Depends(get_db),
):
    """
    手动更新SKU退货率
    
    更新后会自动重新计算相关指标
    """
    stats_service = StatsService(db)
    
    success = await stats_service.update_return_rate(
        sku_code=sku_code,
        return_rate=return_rate,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="未找到该SKU的统计数据")
    
    return {"message": "退货率更新成功"}


@router.get("/summary", response_model=StatsSummary)
async def get_stats_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    获取统计汇总数据（数据看板用）
    
    返回订单总数、待发货数、售后未完结数、已签收数、总缺口等
    """
    stats_service = StatsService(db)
    return await stats_service.get_summary()


@router.get("/province")
async def get_province_stats(
    start_date: Optional[date] = Query(None, description="开始日期（支付时间）"),
    end_date: Optional[date] = Query(None, description="结束日期（支付时间）"),
    sku_code: Optional[str] = Query(None, description="SKU编码"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取省份退货率统计
    
    返回各省份的订单数、退货数、退货率
    支持按支付时间区间筛选
    """
    stats_service = StatsService(db)
    
    stats = await stats_service.get_province_return_stats(
        sku_code=sku_code,
        start_date=start_date,
        end_date=end_date,
    )
    
    return {
        "items": stats,
        "total": len(stats),
    }


@router.get("/orders/trend", response_model=List[TrendItem])
async def get_order_trend(
    granularity: str = Query("day", description="时间粒度: day/hour/minute"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    days: int = Query(7, ge=1, le=90, description="查询最近N天（当start_date未指定时使用）"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取订单时间维度统计（按日期/小时/分钟聚合）
    
    - granularity: 时间粒度
      - day: 按天聚合，返回每天的订单数
      - hour: 按小时聚合，返回每小时的订单数
      - minute: 按分钟聚合（仅支持最近1天）
    - 包含：待发货、已发货、付款后已退款的订单
    """
    # 确定时间范围
    if start_date and end_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
    else:
        end_dt = datetime.now()
        if granularity == "minute":
            start_dt = end_dt - timedelta(hours=24)  # 分钟维度只支持最近24小时
        else:
            start_dt = end_dt - timedelta(days=days)
    
    results = []
    
    if granularity == "day":
        # 按天聚合
        # SQLite 日期格式: strftime('%Y-%m-%d', pay_time)
        stmt = select(
            func.strftime('%Y-%m-%d', Order.pay_time).label("date_label"),
            func.count().label("order_count"),
            func.sum(func.iif(Order.order_status == 2, 1, 0)).label("pending_ship_count"),
            func.sum(func.iif(Order.order_status == 3, 1, 0)).label("shipped_count"),
            func.sum(func.iif(Order.order_status == 4, 1, 0)).label("refunded_count"),
        ).where(
            and_(
                Order.pay_time >= start_dt,
                Order.pay_time <= end_dt,
                Order.pay_time.isnot(None),
            )
        ).group_by(
            func.strftime('%Y-%m-%d', Order.pay_time)
        ).order_by(
            func.strftime('%Y-%m-%d', Order.pay_time)
        )
        
        result = await db.execute(stmt)
        for row in result.all():
            results.append(TrendItem(
                time_label=row.date_label,
                order_count=row.order_count,
                pending_ship_count=row.pending_ship_count or 0,
                shipped_count=row.shipped_count or 0,
                refunded_count=row.refunded_count or 0,
            ))
    
    elif granularity == "hour":
        # 按小时聚合
        stmt = select(
            func.strftime('%Y-%m-%d %H:00', Order.pay_time).label("hour_label"),
            func.count().label("order_count"),
            func.sum(func.iif(Order.order_status == 2, 1, 0)).label("pending_ship_count"),
            func.sum(func.iif(Order.order_status == 3, 1, 0)).label("shipped_count"),
            func.sum(func.iif(Order.order_status == 4, 1, 0)).label("refunded_count"),
        ).where(
            and_(
                Order.pay_time >= start_dt,
                Order.pay_time <= end_dt,
                Order.pay_time.isnot(None),
            )
        ).group_by(
            func.strftime('%Y-%m-%d %H:00', Order.pay_time)
        ).order_by(
            func.strftime('%Y-%m-%d %H:00', Order.pay_time)
        )
        
        result = await db.execute(stmt)
        for row in result.all():
            results.append(TrendItem(
                time_label=row.hour_label,
                order_count=row.order_count,
                pending_ship_count=row.pending_ship_count or 0,
                shipped_count=row.shipped_count or 0,
                refunded_count=row.refunded_count or 0,
            ))
    
    elif granularity == "minute":
        # 按分钟聚合（仅最近24小时）
        stmt = select(
            func.strftime('%Y-%m-%d %H:%M', Order.pay_time).label("minute_label"),
            func.count().label("order_count"),
        ).where(
            and_(
                Order.pay_time >= start_dt,
                Order.pay_time <= end_dt,
                Order.pay_time.isnot(None),
            )
        ).group_by(
            func.strftime('%Y-%m-%d %H:%M', Order.pay_time)
        ).order_by(
            func.strftime('%Y-%m-%d %H:%M', Order.pay_time)
        )
        
        result = await db.execute(stmt)
        for row in result.all():
            results.append(TrendItem(
                time_label=row.minute_label,
                order_count=row.order_count,
            ))
    
    else:
        raise HTTPException(status_code=400, detail="granularity 必须是 day/hour/minute")
    
    return results


class ProvinceSkuItem(BaseModel):
    """省份SKU退货率项"""
    province_name: str
    sku_code: str
    sku_name: Optional[str] = None
    order_count: int
    return_count: int
    return_rate: float


@router.get("/province-sku")
async def get_province_sku_stats(
    start_date: Optional[date] = Query(None, description="开始日期（支付时间）"),
    end_date: Optional[date] = Query(None, description="结束日期（支付时间）"),
    province_name: Optional[str] = Query(None, description="省份名称筛选"),
    sku_code: Optional[str] = Query(None, description="SKU编码筛选"),
    limit: int = Query(100, ge=1, le=500, description="返回条数限制"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取省份 x SKU 退货率矩阵
    
    返回每个省份下每个SKU的订单数、退货数、退货率
    支持按支付时间区间筛选
    """
    from app.models.order import OrderSku
    from app.models.after_sale import AfterSale
    
    # 确定时间范围：有日期参数则使用，否则默认90天
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
    else:
        start_dt = datetime.combine(date.today() - timedelta(days=90), datetime.min.time())
    
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time())
    else:
        end_dt = datetime.now()
    
    # 1. 查询每个省份每个SKU的订单数
    order_conditions = [
        Order.pay_time >= start_dt,
        Order.pay_time <= end_dt,
        Order.province_name.isnot(None),
        Order.province_name != "",
    ]
    if province_name:
        order_conditions.append(Order.province_name == province_name)
    
    order_stmt = select(
        Order.province_name,
        OrderSku.sku_code,
        func.max(OrderSku.sku_name).label("sku_name"),
        func.count().label("order_count"),
    ).select_from(Order).join(
        OrderSku, Order.order_id == OrderSku.order_id
    ).where(
        and_(*order_conditions)
    )
    
    if sku_code:
        order_stmt = order_stmt.where(OrderSku.sku_code.contains(sku_code))
    
    order_stmt = order_stmt.group_by(
        Order.province_name, OrderSku.sku_code
    ).limit(limit)
    
    order_result = await db.execute(order_stmt)
    order_data = {}  # key: (province, sku_code), value: {order_count, sku_name}
    for row in order_result.all():
        key = (row.province_name, row.sku_code)
        order_data[key] = {
            "order_count": row.order_count,
            "sku_name": row.sku_name,
        }
    
    # 2. 查询每个省份每个SKU的退货数
    return_conditions = [
        AfterSale.apply_time >= start_dt,
        AfterSale.apply_time <= end_dt,
        AfterSale.aftersale_type == 1,  # 退货退款
        AfterSale.province_name.isnot(None),
        AfterSale.province_name != "",
    ]
    if province_name:
        return_conditions.append(AfterSale.province_name == province_name)
    
    return_stmt = select(
        AfterSale.province_name,
        AfterSale.sku_code,
        func.count().label("return_count"),
    ).where(
        and_(*return_conditions)
    )
    
    if sku_code:
        return_stmt = return_stmt.where(AfterSale.sku_code.contains(sku_code))
    
    return_stmt = return_stmt.group_by(
        AfterSale.province_name, AfterSale.sku_code
    )
    
    return_result = await db.execute(return_stmt)
    return_data = {}  # key: (province, sku_code), value: return_count
    for row in return_result.all():
        key = (row.province_name, row.sku_code)
        return_data[key] = row.return_count
    
    # 3. 合并数据
    items = []
    for (prov, sku), data in order_data.items():
        return_count = return_data.get((prov, sku), 0)
        order_count = data["order_count"]
        return_rate = return_count / order_count if order_count > 0 else 0
        
        items.append({
            "province_name": prov,
            "sku_code": sku,
            "sku_name": data["sku_name"],
            "order_count": order_count,
            "return_count": return_count,
            "return_rate": round(return_rate, 4),
        })
    
    # 按退货率降序排序
    items.sort(key=lambda x: x["return_rate"], reverse=True)
    
    return {
        "items": items,
        "total": len(items),
    }

