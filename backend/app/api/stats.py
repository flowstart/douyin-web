"""
统计相关 API
"""
from datetime import date, datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, extract, case, union
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
            func.sum(case((Order.order_status == 2, 1), else_=0)).label("pending_ship_count"),
            func.sum(case((Order.order_status == 3, 1), else_=0)).label("shipped_count"),
            func.sum(case((Order.order_status == 4, 1), else_=0)).label("refunded_count"),
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
            func.sum(case((Order.order_status == 2, 1), else_=0)).label("pending_ship_count"),
            func.sum(case((Order.order_status == 3, 1), else_=0)).label("shipped_count"),
            func.sum(case((Order.order_status == 4, 1), else_=0)).label("refunded_count"),
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
    
    # 口径对齐（与 SKU 统计一致）：
    # - 订单数：已签收订单（Order.is_signed=True），按 pay_time 窗口过滤；
    #          union distinct(order_id) 融合 ordersku 与 aftersale 两个来源，避免缺失且去重；
    # - 退货数：已签收 + 退货退款(aftersale_type=1) + sku_code 非空，count(distinct order_id)，按 pay_time 窗口过滤；
    # - 仍按 省份 x SKU 聚合。

    # 1) 订单数：union distinct(province_name, sku_code, order_id)
    signed_from_ordersku_conditions = [
        Order.is_signed == True,
        Order.pay_time >= start_dt,
        Order.pay_time <= end_dt,
        Order.province_name.isnot(None),
        Order.province_name != "",
        OrderSku.sku_code.isnot(None),
    ]
    if province_name:
        signed_from_ordersku_conditions.append(Order.province_name == province_name)

    signed_from_aftersale_conditions = [
        Order.is_signed == True,
        Order.pay_time >= start_dt,
        Order.pay_time <= end_dt,
        AfterSale.province_name.isnot(None),
        AfterSale.province_name != "",
        AfterSale.sku_code.isnot(None),
    ]
    if province_name:
        signed_from_aftersale_conditions.append(AfterSale.province_name == province_name)

    if sku_code:
        signed_from_ordersku_conditions.append(OrderSku.sku_code.contains(sku_code))
        signed_from_aftersale_conditions.append(AfterSale.sku_code.contains(sku_code))

    signed_ordersku_q = select(
        Order.province_name.label("province_name"),
        OrderSku.sku_code.label("sku_code"),
        Order.order_id.label("order_id"),
    ).select_from(Order).join(
        OrderSku, Order.order_id == OrderSku.order_id
    ).where(and_(*signed_from_ordersku_conditions))

    signed_aftersale_q = select(
        AfterSale.province_name.label("province_name"),
        AfterSale.sku_code.label("sku_code"),
        Order.order_id.label("order_id"),
    ).select_from(AfterSale).join(
        Order, AfterSale.order_id == Order.order_id
    ).where(and_(*signed_from_aftersale_conditions))

    signed_union = union(signed_ordersku_q, signed_aftersale_q).subquery("signed_union")

    order_counts_subq = select(
        signed_union.c.province_name,
        signed_union.c.sku_code,
        func.count(func.distinct(signed_union.c.order_id)).label("order_count"),
    ).group_by(
        signed_union.c.province_name,
        signed_union.c.sku_code,
    ).subquery("order_counts")

    # 2) 退货数：已签收 + 退货退款 + sku_code非空，distinct order_id
    return_conditions = [
        Order.is_signed == True,
        Order.pay_time >= start_dt,
        Order.pay_time <= end_dt,
        AfterSale.aftersale_type == 1,
        AfterSale.province_name.isnot(None),
        AfterSale.province_name != "",
        AfterSale.sku_code.isnot(None),
    ]
    if province_name:
        return_conditions.append(AfterSale.province_name == province_name)
    if sku_code:
        return_conditions.append(AfterSale.sku_code.contains(sku_code))

    return_counts_subq = select(
        AfterSale.province_name.label("province_name"),
        AfterSale.sku_code.label("sku_code"),
        func.count(func.distinct(Order.order_id)).label("return_count"),
    ).select_from(AfterSale).join(
        Order, AfterSale.order_id == Order.order_id
    ).where(and_(*return_conditions)).group_by(
        AfterSale.province_name,
        AfterSale.sku_code,
    ).subquery("return_counts")

    # 3) 合并 + 计算退货率（按退货率降序）
    return_count_col = func.coalesce(return_counts_subq.c.return_count, 0)
    return_rate_col = case(
        (order_counts_subq.c.order_count > 0, return_count_col * 1.0 / order_counts_subq.c.order_count),
        else_=0,
    ).label("return_rate")

    stmt = select(
        order_counts_subq.c.province_name,
        order_counts_subq.c.sku_code,
        order_counts_subq.c.order_count,
        return_count_col.label("return_count"),
        return_rate_col,
    ).select_from(order_counts_subq).outerjoin(
        return_counts_subq,
        and_(
            return_counts_subq.c.province_name == order_counts_subq.c.province_name,
            return_counts_subq.c.sku_code == order_counts_subq.c.sku_code,
        ),
    ).order_by(
        return_rate_col.desc()
    ).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    # 补充 sku_name（仅能从 order_skus 获取；after_sales-only 的 sku 可能为空）
    sku_codes = [r.sku_code for r in rows if r.sku_code]
    sku_name_map = {}
    if sku_codes:
        sku_name_stmt = select(
            OrderSku.sku_code,
            func.max(OrderSku.sku_name).label("sku_name"),
        ).where(
            OrderSku.sku_code.in_(list(set(sku_codes)))
        ).group_by(OrderSku.sku_code)
        sku_name_result = await db.execute(sku_name_stmt)
        sku_name_map = {r.sku_code: r.sku_name for r in sku_name_result.all() if r.sku_code}

    items = []
    for r in rows:
        items.append(
            {
                "province_name": r.province_name,
                "sku_code": r.sku_code,
                "sku_name": sku_name_map.get(r.sku_code),
                "order_count": int(r.order_count or 0),
                "return_count": int(r.return_count or 0),
                "return_rate": round(float(r.return_rate or 0), 4),
            }
        )

    return {"items": items, "total": len(items)}

