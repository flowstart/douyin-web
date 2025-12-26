"""
订单服务
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderSku
from app.models.after_sale import AfterSale
from app.services.douyin_client import DouyinClient


class OrderService:
    """订单服务"""
    
    # 订单状态映射
    ORDER_STATUS = {
        1: "待确认",
        2: "待发货", 
        3: "已发货",
        4: "已取消",
        5: "已完成",
        6: "售后中",
    }
    
    # 售后状态映射（售后未完结的状态）
    AFTERSALE_PENDING_STATUS = [
        1,   # 待商家确认
        2,   # 待买家寄货
        3,   # 待商家收货
        4,   # 待商家退款
    ]
    
    # 物流状态映射
    LOGISTICS_STATUS = {
        0: "运输中",
        1: "已揽收",
        2: "终止揽收",
        3: "已签收",
        4: "已退回签收",
        5: "派送中",
        6: "退回中",
        7: "转单",
        8: "取消",
        9: "已退回在途",
        10: "报废",
        11: "仓库备货中",
        12: "待取件",
        13: "已发货",
    }
    
    def __init__(self, db: AsyncSession, douyin_client: Optional[DouyinClient] = None):
        self.db = db
        self.douyin_client = douyin_client
    
    async def sync_orders(
        self, 
        start_time: datetime, 
        end_time: datetime
    ) -> Dict[str, int]:
        """
        同步订单数据
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            同步统计信息
        """
        if not self.douyin_client:
            raise ValueError("未配置抖音客户端")
        
        stats = {"total": 0, "created": 0, "updated": 0}
        page = 0
        size = 100
        
        while True:
            # 获取订单列表
            result = await self.douyin_client.get_order_list(
                start_time=int(start_time.timestamp()),
                end_time=int(end_time.timestamp()),
                page=page,
                size=size,
            )
            
            order_list = result.get("shop_order_list", [])
            if not order_list:
                break
            
            for order_data in order_list:
                order_id = order_data.get("order_id", "")
                
                # 获取订单详情
                detail = await self.douyin_client.get_order_detail(order_id)
                shop_order = detail.get("shop_order_detail", {})
                
                # 查询或创建订单
                existing = await self.db.execute(
                    select(Order).where(Order.order_id == order_id)
                )
                order = existing.scalar_one_or_none()
                
                if order:
                    stats["updated"] += 1
                else:
                    order = Order(order_id=order_id)
                    self.db.add(order)
                    stats["created"] += 1
                
                # 更新订单信息
                order.order_status = shop_order.get("order_status", 0)
                order.order_status_desc = self.ORDER_STATUS.get(order.order_status, "未知")
                order.create_time = datetime.fromtimestamp(shop_order.get("create_time", 0))
                order.update_time = datetime.fromtimestamp(shop_order.get("update_time", 0)) if shop_order.get("update_time") else None
                order.pay_time = datetime.fromtimestamp(shop_order.get("pay_time", 0)) if shop_order.get("pay_time") else None
                
                # 收货地址
                post_addr = shop_order.get("post_addr", {})
                province = post_addr.get("province", {})
                order.province_id = province.get("id", "")
                order.province_name = province.get("name", "")
                city = post_addr.get("city", {})
                order.city_name = city.get("name", "")
                order.receiver_name = post_addr.get("receiver_name", "")
                
                # 金额
                order.total_amount = float(shop_order.get("total_amount", 0)) / 100
                order.pay_amount = float(shop_order.get("pay_amount", 0)) / 100
                
                # 获取物流状态
                try:
                    logistics = await self.douyin_client.get_logistics_track(order_id)
                    track_list = logistics.get("track_list", [])
                    if track_list:
                        latest_track = track_list[0]
                        order.logistics_status = latest_track.get("state", 0)
                        order.logistics_status_desc = self.LOGISTICS_STATUS.get(order.logistics_status, "未知")
                        order.is_signed = order.logistics_status == 3
                        if order.is_signed:
                            order.sign_time = datetime.fromtimestamp(latest_track.get("time", 0))
                except Exception:
                    # 物流查询失败不影响订单同步
                    pass
                
                # 处理SKU信息
                sku_order_list = shop_order.get("sku_order_list", [])
                for sku_data in sku_order_list:
                    sku_id = sku_data.get("sku_id", "")
                    
                    # 查询或创建订单SKU
                    existing_sku = await self.db.execute(
                        select(OrderSku).where(
                            and_(OrderSku.order_id == order_id, OrderSku.sku_id == sku_id)
                        )
                    )
                    order_sku = existing_sku.scalar_one_or_none()
                    
                    if not order_sku:
                        order_sku = OrderSku(order_id=order_id, sku_id=sku_id)
                        self.db.add(order_sku)
                    
                    order_sku.sku_code = sku_data.get("code", "")
                    order_sku.sku_name = sku_data.get("sku_name", "")
                    order_sku.product_id = sku_data.get("product_id", "")
                    order_sku.product_name = sku_data.get("product_name", "")
                    order_sku.quantity = sku_data.get("item_num", 1)
                    order_sku.price = float(sku_data.get("price", 0)) / 100
                
                stats["total"] += 1
            
            # 检查是否还有更多数据
            if len(order_list) < size:
                break
            page += 1
        
        await self.db.commit()
        return stats
    
    async def sync_aftersales(
        self, 
        start_time: datetime, 
        end_time: datetime
    ) -> Dict[str, int]:
        """
        同步售后数据
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            同步统计信息
        """
        if not self.douyin_client:
            raise ValueError("未配置抖音客户端")
        
        stats = {"total": 0, "created": 0, "updated": 0}
        page = 0
        size = 100
        
        while True:
            # 获取售后列表
            result = await self.douyin_client.get_aftersale_list(
                start_time=int(start_time.timestamp()),
                end_time=int(end_time.timestamp()),
                page=page,
                size=size,
            )
            
            aftersale_list = result.get("aftersale_list", [])
            if not aftersale_list:
                break
            
            for as_data in aftersale_list:
                aftersale_id = as_data.get("aftersale_id", "")
                
                # 获取售后详情
                detail = await self.douyin_client.get_aftersale_detail(aftersale_id)
                
                # 查询或创建售后单
                existing = await self.db.execute(
                    select(AfterSale).where(AfterSale.aftersale_id == aftersale_id)
                )
                aftersale = existing.scalar_one_or_none()
                
                if aftersale:
                    stats["updated"] += 1
                else:
                    aftersale = AfterSale(aftersale_id=aftersale_id)
                    self.db.add(aftersale)
                    stats["created"] += 1
                
                # 更新售后信息
                aftersale.order_id = detail.get("order_id", "")
                aftersale.sku_id = detail.get("sku_id", "")
                aftersale.sku_code = detail.get("out_sku_id", "")  # 商家SKU编码
                aftersale.aftersale_type = detail.get("aftersale_type", 0)
                aftersale.aftersale_status = detail.get("aftersale_status", 0)
                aftersale.reason_code = detail.get("reason_code", "")
                aftersale.reason_text = detail.get("reason_text", "")
                aftersale.refund_amount = float(detail.get("refund_amount", 0)) / 100
                
                # 判断是否品质问题
                quality_reason_codes = ["quality", "fake", "damaged"]  # 需要根据实际情况调整
                aftersale.is_quality_issue = any(
                    code in str(aftersale.reason_code).lower() 
                    for code in quality_reason_codes
                )
                
                # 时间信息
                if detail.get("apply_time"):
                    aftersale.apply_time = datetime.fromtimestamp(detail.get("apply_time"))
                if detail.get("finish_time"):
                    aftersale.finish_time = datetime.fromtimestamp(detail.get("finish_time"))
                
                # 关联订单的省份信息
                order_result = await self.db.execute(
                    select(Order).where(Order.order_id == aftersale.order_id)
                )
                order = order_result.scalar_one_or_none()
                if order:
                    aftersale.province_id = order.province_id
                    aftersale.province_name = order.province_name
                
                stats["total"] += 1
            
            if len(aftersale_list) < size:
                break
            page += 1
        
        await self.db.commit()
        return stats
    
    async def get_pending_ship_orders(self) -> List[Order]:
        """获取待发货订单"""
        result = await self.db.execute(
            select(Order).where(Order.order_status == 2)
        )
        return result.scalars().all()
    
    async def get_signed_orders(self, days: int = 90) -> List[Order]:
        """获取已签收订单（近N天）"""
        start_date = datetime.now() - timedelta(days=days)
        result = await self.db.execute(
            select(Order).where(
                and_(
                    Order.is_signed == True,
                    Order.sign_time >= start_date
                )
            )
        )
        return result.scalars().all()
    
    async def get_pending_aftersales(self) -> List[AfterSale]:
        """获取售后未完结订单"""
        result = await self.db.execute(
            select(AfterSale).where(
                AfterSale.aftersale_status.in_(self.AFTERSALE_PENDING_STATUS)
            )
        )
        return result.scalars().all()

