"""
数据同步 API
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.services.douyin_client import DouyinClient
from app.services.order_service import OrderService
from app.services.stats_service import StatsService

router = APIRouter()
settings = get_settings()


@router.post("/orders")
async def sync_orders(
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    access_token: str = Query(..., description="抖音 access_token"),
    db: AsyncSession = Depends(get_db),
):
    """
    同步订单数据
    
    从抖音开放平台拉取订单数据并保存到本地数据库
    
    - 默认同步最近7天的订单
    - 最大支持90天
    """
    # 默认同步最近7天
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=7)
    
    # 验证时间范围
    if (end_date - start_date).days > 90:
        raise HTTPException(status_code=400, detail="时间范围不能超过90天")
    
    # 检查配置
    if not settings.douyin_app_key:
        raise HTTPException(status_code=500, detail="未配置抖音开放平台凭证")
    
    # 创建抖音客户端
    douyin_client = DouyinClient(access_token=access_token)
    
    try:
        # 同步订单
        order_service = OrderService(db, douyin_client)
        stats = await order_service.sync_orders(start_date, end_date)
        
        return {
            "message": "订单同步完成",
            "stats": stats,
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            }
        }
    finally:
        await douyin_client.close()


@router.post("/aftersales")
async def sync_aftersales(
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    access_token: str = Query(..., description="抖音 access_token"),
    db: AsyncSession = Depends(get_db),
):
    """
    同步售后数据
    
    从抖音开放平台拉取售后数据并保存到本地数据库
    """
    # 默认同步最近7天
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=7)
    
    # 验证时间范围
    if (end_date - start_date).days > 90:
        raise HTTPException(status_code=400, detail="时间范围不能超过90天")
    
    # 检查配置
    if not settings.douyin_app_key:
        raise HTTPException(status_code=500, detail="未配置抖音开放平台凭证")
    
    # 创建抖音客户端
    douyin_client = DouyinClient(access_token=access_token)
    
    try:
        # 同步售后
        order_service = OrderService(db, douyin_client)
        stats = await order_service.sync_aftersales(start_date, end_date)
        
        return {
            "message": "售后同步完成",
            "stats": stats,
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            }
        }
    finally:
        await douyin_client.close()


@router.post("/all")
async def sync_all(
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    access_token: str = Query(..., description="抖音 access_token"),
    db: AsyncSession = Depends(get_db),
):
    """
    同步所有数据并计算统计
    
    1. 同步订单数据
    2. 同步售后数据
    3. 计算SKU统计
    """
    # 默认同步最近7天
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=7)
    
    # 验证时间范围
    if (end_date - start_date).days > 90:
        raise HTTPException(status_code=400, detail="时间范围不能超过90天")
    
    # 检查配置
    if not settings.douyin_app_key:
        raise HTTPException(status_code=500, detail="未配置抖音开放平台凭证")
    
    # 创建抖音客户端
    douyin_client = DouyinClient(access_token=access_token)
    
    try:
        order_service = OrderService(db, douyin_client)
        stats_service = StatsService(db)
        
        # 1. 同步订单
        order_stats = await order_service.sync_orders(start_date, end_date)
        
        # 2. 同步售后
        aftersale_stats = await order_service.sync_aftersales(start_date, end_date)
        
        # 3. 计算统计
        sku_stats = await stats_service.calculate_sku_stats()
        sku_count = await stats_service.save_sku_stats(sku_stats)
        
        return {
            "message": "全量同步完成",
            "order_stats": order_stats,
            "aftersale_stats": aftersale_stats,
            "sku_stats_count": sku_count,
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            }
        }
    finally:
        await douyin_client.close()

