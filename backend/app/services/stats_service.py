"""
统计服务
"""
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, case, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderSku
from app.models.after_sale import AfterSale
from app.models.sku_stats import SkuStats
from app.schemas.sku_stats import SkuStatsQuery, StatsSummary


class StatsService:
    """统计服务"""
    
    # 默认退货率（订单数<10时使用）
    DEFAULT_RETURN_RATE = 0.3
    
    # 最小订单数（用于计算退货率）
    MIN_ORDERS_FOR_RATE = 10

    # 品质退货原因（按你勾选的四项，需兼容“/”与“／”、以及可能的空格变体）
    QUALITY_REASON_TEXTS = [
        "商品破损/包装问题",
        "商品与描述不符",
        "商品质量不好",
        "少件/漏发",
        "少件／漏发",
        "少件 / 漏发",
    ]
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_sku_stats(
        self, 
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        计算所有SKU的统计数据（使用高效的单次聚合查询）
        
        Args:
            start_date: 订单支付时间开始（可选，用于时间区间筛选）
            end_date: 订单支付时间结束（可选）
        
        Returns:
            SKU统计列表
        """
        now = datetime.now()

        # 默认统计窗口：近90天（按 pay_time）
        if start_date is None:
            start_date = date.today() - timedelta(days=90)

        # 构建时间筛选条件（统一按订单支付时间 pay_time）
        time_conditions = [
            Order.pay_time >= datetime.combine(start_date, datetime.min.time()),
        ]
        if end_date:
            time_conditions.append(Order.pay_time <= datetime.combine(end_date, datetime.max.time()))
        
        # 1. 单次聚合查询订单相关统计（按净编码 sku_code 聚合）
        order_stats_query = select(
            OrderSku.sku_code,
            func.max(OrderSku.sku_name).label("sku_name"),
            func.max(OrderSku.product_name).label("product_name"),
            # 待发货订单数（按订单去重）
            func.count(
                func.distinct(
                    case((Order.order_status == 2, Order.order_id), else_=None)
                )
            ).label("pending_ship_count"),
            # 已签收订单数（按订单去重）
            # 口径：is_signed=True 的订单数（不是商品件数）
            func.count(
                func.distinct(
                    case((Order.is_signed == True, Order.order_id), else_=None)
                )
            ).label("signed_count"),
            # 在途未签收订单数（按订单去重）
            func.count(
                func.distinct(
                    case(
                        (and_(Order.order_status == 3, Order.is_signed == False), Order.order_id),
                        else_=None
                    )
                )
            ).label("in_transit_count"),
        ).select_from(OrderSku).join(
            Order, OrderSku.order_id == Order.order_id
        )
        
        # 应用时间筛选
        if time_conditions:
            order_stats_query = order_stats_query.where(and_(*time_conditions))
        
        order_stats_query = order_stats_query.where(OrderSku.sku_code.isnot(None))
        order_stats_query = order_stats_query.group_by(OrderSku.sku_code)
        
        order_result = await self.db.execute(order_stats_query)
        order_stats = {row.sku_code: row for row in order_result.all() if row.sku_code}
        
        # 2. 查询售后未完结订单数（按订单去重，按 pay_time 过滤）
        aftersale_pending_query = select(
            AfterSale.sku_code,
            func.count(func.distinct(Order.order_id)).label("aftersale_pending_count"),
        ).select_from(AfterSale).join(
            Order, AfterSale.order_id == Order.order_id
        ).where(
            and_(
                AfterSale.aftersale_status.in_([2, 3]),  # 待买家寄货、待商家收货
                AfterSale.sku_code.isnot(None),
                *time_conditions,
            )
        ).group_by(AfterSale.sku_code)
        
        aftersale_result = await self.db.execute(aftersale_pending_query)
        aftersale_stats = {row.sku_code: row.aftersale_pending_count for row in aftersale_result.all() if row.sku_code}
        
        # 3. 查询已签收退货数量
        # 口径：订单已签收 + 售后类型为退货退款 + 按订单支付时间过滤
        signed_return_conditions = [
            Order.is_signed == True,
            AfterSale.aftersale_type == 1,  # 退货退款
            AfterSale.sku_code.isnot(None),
        ]
        # 应用与订单统计相同的时间筛选（按支付时间）
        if time_conditions:
            signed_return_conditions.extend(time_conditions)
        
        signed_return_query = select(
            AfterSale.sku_code,
            func.count(func.distinct(Order.order_id)).label("signed_return_count")  # 按订单去重
        ).select_from(AfterSale).join(
            Order, AfterSale.order_id == Order.order_id
        ).where(
            and_(*signed_return_conditions)
        ).group_by(AfterSale.sku_code)
        
        return_result = await self.db.execute(signed_return_query)
        return_stats = {row.sku_code: row.signed_return_count for row in return_result.all() if row.sku_code}
        
        # 3.1 从 after_sales 表统计已签收订单数（用于补充 order_skus 表中缺失的 SKU）
        # 这样 signed_count 和 signed_return_count 使用相同的数据来源，不会出现分子>分母
        aftersale_signed_conditions = [
            Order.is_signed == True,
            AfterSale.sku_code.isnot(None),
        ]
        if time_conditions:
            aftersale_signed_conditions.extend(time_conditions)
        
        aftersale_signed_query = select(
            AfterSale.sku_code,
            func.count(func.distinct(Order.order_id)).label("aftersale_signed_count")
        ).select_from(AfterSale).join(
            Order, AfterSale.order_id == Order.order_id
        ).where(
            and_(*aftersale_signed_conditions)
        ).group_by(AfterSale.sku_code)
        
        aftersale_signed_result = await self.db.execute(aftersale_signed_query)
        aftersale_signed_stats = {row.sku_code: row.aftersale_signed_count for row in aftersale_signed_result.all() if row.sku_code}
        
        # 4. 品质退货订单数（按订单去重；按订单支付时间过滤）
        quality_base_conditions = [
            AfterSale.sku_code.isnot(None),
            # 4类品质原因（兼容斜杠/空格变体）
            or_(
                AfterSale.reason_text.in_(self.QUALITY_REASON_TEXTS),
                AfterSale.reason_text.contains("商品破损/包装问题"),
                AfterSale.reason_text.contains("商品与描述不符"),
                AfterSale.reason_text.contains("商品质量不好"),
                AfterSale.reason_text.contains("少件/漏发"),
                AfterSale.reason_text.contains("少件／漏发"),
            ),
        ]
        
        quality_return_query = select(
            AfterSale.sku_code,
            func.count(func.distinct(Order.order_id)).label("quality_return_count"),
        ).select_from(AfterSale).join(
            Order, AfterSale.order_id == Order.order_id
        ).where(and_(*quality_base_conditions))
        
        # 应用与订单统计相同的时间筛选（按支付时间）
        quality_return_query = quality_return_query.where(and_(*time_conditions))
        
        quality_return_query = quality_return_query.group_by(AfterSale.sku_code)

        quality_result = await self.db.execute(quality_return_query)
        quality_stats = {row.sku_code: row.quality_return_count for row in quality_result.all() if row.sku_code}

        # 5. 已签收订单数（用于计算品退率分母，订单数口径）
        # 口径：按 SKU 维度对订单去重，且包含“after_sales 表中有、order_skus 表中缺失”的订单（union distinct）
        signed_orders_from_ordersku_query = select(
            OrderSku.sku_code,
            func.count(func.distinct(Order.order_id)).label("signed_order_count"),
        ).select_from(OrderSku).join(
            Order, OrderSku.order_id == Order.order_id
        ).where(
            and_(
                Order.is_signed == True,
                OrderSku.sku_code.isnot(None),
                *time_conditions,
            )
        ).group_by(OrderSku.sku_code)
        signed_orders_from_ordersku_result = await self.db.execute(signed_orders_from_ordersku_query)
        signed_orders_from_ordersku = {
            row.sku_code: row.signed_order_count for row in signed_orders_from_ordersku_result.all() if row.sku_code
        }

        signed_orders_overlap_query = select(
            AfterSale.sku_code,
            func.count(func.distinct(Order.order_id)).label("signed_overlap_count"),
        ).select_from(AfterSale).join(
            Order, AfterSale.order_id == Order.order_id
        ).join(
            OrderSku,
            and_(
                OrderSku.order_id == Order.order_id,
                OrderSku.sku_code == AfterSale.sku_code,
            ),
        ).where(
            and_(
                Order.is_signed == True,
                AfterSale.sku_code.isnot(None),
                *time_conditions,
            )
        ).group_by(AfterSale.sku_code)
        signed_orders_overlap_result = await self.db.execute(signed_orders_overlap_query)
        signed_orders_overlap = {
            row.sku_code: row.signed_overlap_count for row in signed_orders_overlap_result.all() if row.sku_code
        }

        # union = ordersku_signed + aftersale_signed - overlap
        signed_sku_orders: Dict[str, int] = {}
        signed_sku_order_keys = set(signed_orders_from_ordersku.keys()) | set(aftersale_signed_stats.keys())
        for sku_code in signed_sku_order_keys:
            a = int(signed_orders_from_ordersku.get(sku_code, 0) or 0)
            b = int(aftersale_signed_stats.get(sku_code, 0) or 0)
            c = int(signed_orders_overlap.get(sku_code, 0) or 0)
            signed_sku_orders[sku_code] = max(a + b - c, 0)
        
        # 7. 汇总统计结果
        stats_list = []
        all_sku_codes = (
            set(order_stats.keys())
            | set(aftersale_stats.keys())
            | set(return_stats.keys())
            | set(quality_stats.keys())
            | set(aftersale_signed_stats.keys())
        )

        for sku_code in all_sku_codes:
            row = order_stats.get(sku_code)
            sku_id = sku_code
            pending_ship_count = (row.pending_ship_count or 0) if row else 0
            in_transit_count = (row.in_transit_count or 0) if row else 0
            aftersale_pending_count = aftersale_stats.get(sku_code, 0)
            signed_return_count = return_stats.get(sku_code, 0)
            quality_return_count = quality_stats.get(sku_code, 0)
            
            # 已签收订单数：SKU 维度 union distinct(order_id)
            signed_count = int(signed_sku_orders.get(sku_code, 0) or 0)
            
            # 计算预估退货率
            if signed_count >= self.MIN_ORDERS_FOR_RATE:
                estimated_return_rate = signed_return_count / signed_count
            else:
                estimated_return_rate = self.DEFAULT_RETURN_RATE
            
            # 计算品质退货率
            # 公式：品退率 = 品质退货数 / 所有已签收订单数
            signed_orders_total = int(signed_sku_orders.get(sku_code, 0) or 0)

            if signed_orders_total > 0:
                quality_return_rate = quality_return_count / signed_orders_total
            else:
                quality_return_rate = 0
            
            # 在途预估退货数量
            in_transit_return_estimate = int(in_transit_count * estimated_return_rate)
            
            # 预估商品缺口
            stock_gap = pending_ship_count - aftersale_pending_count - in_transit_return_estimate
            
            stats = {
                "sku_id": sku_id,
                "sku_code": sku_code,
                "sku_name": row.sku_name if row else None,
                "product_name": row.product_name if row else None,
                "pending_ship_count": int(pending_ship_count),
                "aftersale_pending_count": int(aftersale_pending_count),
                "signed_count": int(signed_count),
                "signed_return_count": int(signed_return_count),
                "estimated_return_rate": round(estimated_return_rate, 4),
                "in_transit_count": int(in_transit_count),
                "in_transit_return_estimate": int(in_transit_return_estimate),
                "stock_gap": int(stock_gap),
                "quality_return_count": int(quality_return_count),
                "quality_return_rate": round(quality_return_rate, 4),
                "last_calculated_at": now,
            }
            stats_list.append(stats)
        
        return stats_list
    
    async def save_sku_stats(self, stats_list: List[Dict[str, Any]]) -> int:
        """
        保存SKU统计数据到缓存表
        
        Args:
            stats_list: 统计数据列表
        
        Returns:
            保存的记录数
        """
        count = 0
        now = datetime.now()
        
        for stats in stats_list:
            sku_code = stats["sku_code"]
            
            # 查询是否存在该 SKU 的记录
            existing = await self.db.execute(
                select(SkuStats).where(SkuStats.sku_code == sku_code)
            )
            sku_stats = existing.scalar_one_or_none()
            
            if sku_stats:
                # 更新：若未手动修改，则使用本次计算值；若手动修改则保留原值
                if not sku_stats.is_rate_manual:
                    sku_stats.estimated_return_rate = stats["estimated_return_rate"]
            else:
                sku_stats = SkuStats(
                    # 统一口径：缓存表的 sku_id 也使用净编码（避免依赖平台 sku_id）
                    sku_id=stats["sku_code"],
                    sku_code=sku_code,
                )
                # 新建记录：写入本次计算的退货率（否则会停留在模型 default=0.3）
                sku_stats.estimated_return_rate = stats["estimated_return_rate"]
                self.db.add(sku_stats)
            
            # 选择最终生效的退货率：
            # - 手动修改：保留 sku_stats.estimated_return_rate
            # - 非手动：使用本次计算的 stats["estimated_return_rate"]
            final_return_rate = (
                float(sku_stats.estimated_return_rate)
                if sku_stats.is_rate_manual
                else float(stats["estimated_return_rate"])
            )

            # 更新其他字段
            sku_stats.sku_name = stats["sku_name"]
            sku_stats.product_name = stats["product_name"]
            sku_stats.pending_ship_count = stats["pending_ship_count"]
            sku_stats.aftersale_pending_count = stats["aftersale_pending_count"]
            sku_stats.signed_count = stats["signed_count"]
            sku_stats.signed_return_count = stats["signed_return_count"]
            sku_stats.in_transit_count = stats["in_transit_count"]
            # 派生字段统一用 final_return_rate 计算，确保与退货率一致且不破坏手动修改
            sku_stats.in_transit_return_estimate = int(sku_stats.in_transit_count * final_return_rate)
            sku_stats.stock_gap = (
                int(sku_stats.pending_ship_count)
                - int(sku_stats.aftersale_pending_count)
                - int(sku_stats.in_transit_return_estimate)
            )
            sku_stats.quality_return_count = stats.get("quality_return_count", 0)
            sku_stats.quality_return_rate = stats.get("quality_return_rate", 0)
            sku_stats.last_calculated_at = now
            
            count += 1
        
        await self.db.commit()
        return count
    
    async def get_sku_stats(self, query: SkuStatsQuery) -> Dict[str, Any]:
        """
        查询SKU统计数据
        
        - 无时间筛选：返回缓存表数据
        - 有时间筛选：实时计算
        
        Args:
            query: 查询参数
        
        Returns:
            统计结果
        """
        is_realtime = bool(query.start_date or query.end_date)
        
        if is_realtime:
            # 有时间筛选：实时计算
            return await self._get_realtime_stats(query)
        else:
            # 无时间筛选：返回缓存
            return await self._get_cached_stats(query)
    
    async def _get_cached_stats(self, query: SkuStatsQuery) -> Dict[str, Any]:
        """从缓存表获取统计数据"""
        stmt = select(SkuStats)
        
        # SKU搜索
        if query.sku_code:
            stmt = stmt.where(SkuStats.sku_code.contains(query.sku_code))
        
        # 排序
        sort_column = getattr(SkuStats, query.sort_by, SkuStats.pending_ship_count)
        if query.sort_order == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())
        
        # Top N 或分页
        if query.top_n:
            stmt = stmt.limit(query.top_n)
        else:
            offset = (query.page - 1) * query.page_size
            stmt = stmt.offset(offset).limit(query.page_size)
        
        result = await self.db.execute(stmt)
        items = result.scalars().all()
        
        # 获取总数
        count_stmt = select(func.count()).select_from(SkuStats)
        if query.sku_code:
            count_stmt = count_stmt.where(SkuStats.sku_code.contains(query.sku_code))
        
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        return {
            "total": total,
            "items": items,
            "is_realtime": False,
        }
    
    async def _get_realtime_stats(self, query: SkuStatsQuery) -> Dict[str, Any]:
        """实时计算统计数据（有时间筛选时使用）"""
        # 实时计算
        stats_list = await self.calculate_sku_stats(
            start_date=query.start_date,
            end_date=query.end_date
        )
        
        # SKU 搜索筛选
        if query.sku_code:
            stats_list = [
                s for s in stats_list 
                if query.sku_code.lower() in (s["sku_code"] or "").lower()
            ]
        
        # 排序
        sort_key = query.sort_by
        reverse = query.sort_order == "desc"
        stats_list.sort(key=lambda x: x.get(sort_key, 0) or 0, reverse=reverse)
        
        total = len(stats_list)
        
        # Top N 或分页
        if query.top_n:
            items = stats_list[:query.top_n]
        else:
            offset = (query.page - 1) * query.page_size
            items = stats_list[offset:offset + query.page_size]
        
        return {
            "total": total,
            "items": items,
            "is_realtime": True,
        }
    
    async def update_return_rate(
        self, 
        sku_code: str, 
        return_rate: float
    ) -> bool:
        """
        手动更新退货率
        
        Args:
            sku_code: SKU编码
            return_rate: 新的退货率
        
        Returns:
            是否更新成功
        """
        result = await self.db.execute(
            select(SkuStats).where(SkuStats.sku_code == sku_code)
        )
        sku_stats = result.scalar_one_or_none()
        
        if not sku_stats:
            return False
        
        sku_stats.estimated_return_rate = return_rate
        sku_stats.is_rate_manual = True
        
        # 重新计算相关指标
        sku_stats.in_transit_return_estimate = int(
            sku_stats.in_transit_count * return_rate
        )
        sku_stats.stock_gap = (
            sku_stats.pending_ship_count 
            - sku_stats.aftersale_pending_count 
            - sku_stats.in_transit_return_estimate
        )
        
        await self.db.commit()
        return True
    
    async def get_province_return_stats(
        self, 
        sku_code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        按省份统计退货率
        
        Args:
            sku_code: SKU编码（可选）
            start_date: 开始日期（支付时间，可选）
            end_date: 结束日期（支付时间，可选）
        
        Returns:
            省份退货率统计
        """
        # 确定时间范围：按订单支付时间 pay_time；不传则默认近90天
        if start_date:
            start_dt = datetime.combine(start_date, datetime.min.time())
        else:
            start_dt = datetime.combine(date.today() - timedelta(days=90), datetime.min.time())
        
        if end_date:
            end_dt = datetime.combine(end_date, datetime.max.time())
        else:
            end_dt = datetime.now()
        
        # 基础查询 - 退货统计（按订单支付时间窗口过滤）
        stmt = select(
            AfterSale.province_name,
            func.count().label("return_count"),
        ).select_from(AfterSale).join(
            Order, AfterSale.order_id == Order.order_id
        ).where(
            and_(
                Order.pay_time >= start_dt,
                Order.pay_time <= end_dt,
                AfterSale.aftersale_type == 1,  # 退货退款
                AfterSale.province_name.isnot(None),
            )
        )
        
        if sku_code:
            stmt = stmt.where(AfterSale.sku_code == sku_code)
        
        stmt = stmt.group_by(AfterSale.province_name)
        
        result = await self.db.execute(stmt)
        return_stats = {row.province_name: row.return_count for row in result.all()}
        
        # 获取各省份订单总数（基于支付时间）
        order_stmt = select(
            Order.province_name,
            func.count().label("order_count"),
        ).where(
            and_(
                Order.pay_time >= start_dt,
                Order.pay_time <= end_dt,
                Order.province_name.isnot(None),
            )
        ).group_by(Order.province_name)
        
        order_result = await self.db.execute(order_stmt)
        order_stats = {row.province_name: row.order_count for row in order_result.all()}
        
        # 计算退货率
        province_stats = []
        for province, order_count in order_stats.items():
            return_count = return_stats.get(province, 0)
            return_rate = return_count / order_count if order_count > 0 else 0
            
            province_stats.append({
                "province_name": province,
                "order_count": order_count,
                "return_count": return_count,
                "return_rate": round(return_rate, 4),
            })
        
        # 按退货率排序
        province_stats.sort(key=lambda x: x["return_rate"], reverse=True)
        
        return province_stats
    
    async def get_summary(self) -> StatsSummary:
        """
        获取统计汇总数据（用于数据看板）
        
        Returns:
            汇总数据
        """
        # 订单总数
        total_orders_result = await self.db.execute(
            select(func.count()).select_from(Order)
        )
        total_orders = total_orders_result.scalar() or 0
        
        # 待发货订单数
        pending_ship_result = await self.db.execute(
            select(func.count()).select_from(Order).where(Order.order_status == 2)
        )
        pending_ship_orders = pending_ship_result.scalar() or 0
        
        # 售后未完结数
        aftersale_pending_result = await self.db.execute(
            select(func.count()).select_from(AfterSale).where(
                AfterSale.aftersale_status.in_([2, 3])
            )
        )
        aftersale_pending_count = aftersale_pending_result.scalar() or 0
        
        # 已签收订单数
        signed_result = await self.db.execute(
            select(func.count()).select_from(Order).where(Order.is_signed == True)
        )
        signed_orders = signed_result.scalar() or 0
        
        # 总商品缺口（从缓存表汇总）
        stock_gap_result = await self.db.execute(
            select(func.sum(SkuStats.stock_gap)).select_from(SkuStats)
        )
        total_stock_gap = stock_gap_result.scalar() or 0
        
        # 最后计算时间
        last_calc_result = await self.db.execute(
            select(func.max(SkuStats.last_calculated_at)).select_from(SkuStats)
        )
        last_calculated_at = last_calc_result.scalar()
        
        # 最后导入时间（取订单表最大更新时间）
        last_import_result = await self.db.execute(
            select(func.max(Order.updated_at)).select_from(Order)
        )
        last_import_time = last_import_result.scalar()
        
        return StatsSummary(
            total_orders=total_orders,
            pending_ship_orders=pending_ship_orders,
            aftersale_pending_count=aftersale_pending_count,
            signed_orders=signed_orders,
            total_stock_gap=int(total_stock_gap),
            last_import_time=last_import_time,
            last_calculated_at=last_calculated_at,
        )

