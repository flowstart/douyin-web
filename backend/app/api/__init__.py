"""
API 路由
"""
from fastapi import APIRouter

from app.api import orders, stats, upload, logistics, config

api_router = APIRouter()

api_router.include_router(orders.router, prefix="/orders", tags=["订单"])
api_router.include_router(stats.router, prefix="/stats", tags=["统计"])
api_router.include_router(upload.router, prefix="/upload", tags=["文件上传"])
api_router.include_router(logistics.router, prefix="/logistics", tags=["物流查询"])
api_router.include_router(config.router, prefix="/config", tags=["系统配置"])

