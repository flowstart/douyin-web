"""
Excel 数据导入服务 - 批量优化版本
"""
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
import anyio
from sqlalchemy import select, update, and_, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderSku
from app.models.after_sale import AfterSale
from app.services.kd100_client import parse_express_info
from app.utils.sku_code import clean_sku_code


class ExcelImportService:
    """Excel 导入服务 - 批量优化版本"""
    
    # 批量大小
    BATCH_SIZE = 1000
    
    # 订单状态映射
    ORDER_STATUS_MAP = {
        "待发货": 2,
        "已发货": 3,
        "已完成": 5,
        "已关闭": 4,
    }
    
    # 售后状态映射（判断是否未完结）
    AFTERSALE_PENDING_STATUS = [
        "待买家退货",
        "待商家收货",
        "待商家处理",
    ]
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def import_orders(self, file_path: str) -> Dict[str, int]:
        """
        批量导入订单数据
        
        Args:
            file_path: Excel文件路径
        
        Returns:
            导入统计信息
        """
        # pandas 解析 Excel 是阻塞操作：放到线程池，避免阻塞 FastAPI 事件循环
        df = await anyio.to_thread.run_sync(pd.read_excel, file_path)
        stats = {"total": 0, "created": 0, "updated": 0, "skipped": 0}
        
        # 分批处理
        total_rows = len(df)
        for batch_start in range(0, total_rows, self.BATCH_SIZE):
            batch_end = min(batch_start + self.BATCH_SIZE, total_rows)
            batch_df = df.iloc[batch_start:batch_end]
            
            batch_stats = await self._process_order_batch(batch_df)
            stats["total"] += batch_stats["total"]
            stats["created"] += batch_stats["created"]
            stats["updated"] += batch_stats["updated"]
            stats["skipped"] += batch_stats["skipped"]
        
        return stats
    
    async def _process_order_batch(self, batch_df: pd.DataFrame) -> Dict[str, int]:
        """处理一批订单数据"""
        stats = {"total": 0, "created": 0, "updated": 0, "skipped": 0}
        
        # 1. 解析所有记录
        records = []
        sku_records = []
        
        for _, row in batch_df.iterrows():
            order_id = str(row.get("子订单编号", "")).strip()
            if not order_id or order_id == "nan":
                stats["skipped"] += 1
                continue
            
            # 解析订单数据
            order_status_str = str(row.get("订单状态", "")).strip()
            express_str = str(row.get("快递信息", "")).strip()
            express_info = parse_express_info(express_str)
            
            order_data = {
                "order_id": order_id,
                "order_status": self.ORDER_STATUS_MAP.get(order_status_str, 0),
                "order_status_desc": order_status_str,
                "create_time": self._parse_datetime(row.get("订单提交时间")),
                "pay_time": self._parse_datetime(row.get("支付完成时间")),
                "update_time": self._parse_datetime(row.get("订单完成时间")),
                "receiver_name": str(row.get("收件人", "")).strip(),
                "province_name": str(row.get("省", "")).strip(),
                "city_name": str(row.get("市", "")).strip(),
                "logistics_code": express_info["tracking_number"],
                "logistics_company": express_info.get("company_name", ""),
                "updated_at": datetime.now(),
            }
            records.append(order_data)
            
            # 解析 SKU 数据
            sku_code_raw = str(row.get("商家编码", "")).strip()
            if sku_code_raw and sku_code_raw != "nan":
                sku_code_raw = sku_code_raw.replace("\t", "").strip()
                sku_code = clean_sku_code(sku_code_raw)
                if sku_code:
                    sku_data = {
                        "order_id": order_id,
                        # Excel 导入场景无平台 sku_id，统一用净编码作为 sku_id（仅内部占位，统计聚合以 sku_code 为准）
                        "sku_id": sku_code,
                        "sku_code": sku_code,
                        "sku_code_raw": sku_code_raw,
                        "sku_name": str(row.get("选购商品", "")).strip(),
                        "product_name": str(row.get("选购商品", "")).strip(),
                        "quantity": int(row.get("商品数量", 1) or 1),
                    }
                    sku_records.append(sku_data)
            
            stats["total"] += 1
        
        if not records:
            return stats
        
        # 2. 批量查询已存在的订单（用于统计 created/updated）
        order_ids = [r["order_id"] for r in records]
        result = await self.db.execute(select(Order.order_id).where(Order.order_id.in_(order_ids)))
        existing_ids: Set[str] = set(row[0] for row in result.all())

        # 3. 批量 upsert（SQLite 原生 on_conflict_do_update），避免逐条 UPDATE
        now = datetime.now()
        for record in records:
            record.setdefault("created_at", now)

        stmt = sqlite_insert(Order).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["order_id"],
            set_={
                "order_status": stmt.excluded.order_status,
                "order_status_desc": stmt.excluded.order_status_desc,
                "create_time": stmt.excluded.create_time,
                "pay_time": stmt.excluded.pay_time,
                "update_time": stmt.excluded.update_time,
                "receiver_name": stmt.excluded.receiver_name,
                "province_name": stmt.excluded.province_name,
                "city_name": stmt.excluded.city_name,
                "logistics_code": stmt.excluded.logistics_code,
                "logistics_company": stmt.excluded.logistics_company,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)

        stats["created"] = sum(1 for oid in order_ids if oid not in existing_ids)
        stats["updated"] = sum(1 for oid in order_ids if oid in existing_ids)
        
        # 4. 处理 SKU 数据（批量替换该批次订单的 SKU，避免 N+1 查询）
        if sku_records:
            await self._process_sku_batch(sku_records)
        
        # 5. 提交事务（每批次一次提交，尽量缩短事务持锁时间）
        await self.db.commit()
        
        return stats
    
    async def _process_sku_batch(self, sku_records: List[Dict[str, Any]]):
        """批量处理 SKU 数据（替换式写入）"""
        if not sku_records:
            return

        order_ids = list({r["order_id"] for r in sku_records if r.get("order_id")})
        if not order_ids:
            return

        # 1) 先删除本批次涉及订单的旧 SKU，避免重复且省掉逐条查重
        await self.db.execute(delete(OrderSku).where(OrderSku.order_id.in_(order_ids)))

        # 2) 批量插入新 SKU
        now = datetime.now()
        for record in sku_records:
            record.setdefault("created_at", now)

        stmt = sqlite_insert(OrderSku).values(sku_records)
        await self.db.execute(stmt)
    
    async def import_aftersales(self, file_path: str) -> Dict[str, int]:
        """
        批量导入售后数据
        
        Args:
            file_path: Excel文件路径
        
        Returns:
            导入统计信息
        """
        # pandas 解析 Excel 是阻塞操作：放到线程池，避免阻塞 FastAPI 事件循环
        df = await anyio.to_thread.run_sync(pd.read_excel, file_path)
        stats = {"total": 0, "created": 0, "updated": 0, "skipped": 0}
        
        # 分批处理
        total_rows = len(df)
        for batch_start in range(0, total_rows, self.BATCH_SIZE):
            batch_end = min(batch_start + self.BATCH_SIZE, total_rows)
            batch_df = df.iloc[batch_start:batch_end]
            
            batch_stats = await self._process_aftersale_batch(batch_df)
            stats["total"] += batch_stats["total"]
            stats["created"] += batch_stats["created"]
            stats["updated"] += batch_stats["updated"]
            stats["skipped"] += batch_stats["skipped"]
        
        return stats
    
    async def _process_aftersale_batch(self, batch_df: pd.DataFrame) -> Dict[str, int]:
        """处理一批售后数据"""
        stats = {"total": 0, "created": 0, "updated": 0, "skipped": 0}
        
        # 1. 解析所有记录
        records = []
        order_ids_needed = set()
        
        for _, row in batch_df.iterrows():
            aftersale_id = str(row.get("售后单号", "")).strip()
            if not aftersale_id or aftersale_id == "nan":
                stats["skipped"] += 1
                continue
            
            order_id = str(row.get("订单号", "")).strip()
            sku_code_raw = str(row.get("商家编码", "")).strip()
            if sku_code_raw and sku_code_raw != "nan":
                sku_code_raw = sku_code_raw.replace("\t", "").strip()
                sku_code = clean_sku_code(sku_code_raw)
                if not sku_code:
                    sku_code_raw = None
                    sku_code = None
            else:
                sku_code_raw = None
                sku_code = None
            
            # 售后类型
            aftersale_type_str = str(row.get("售后类型", "")).strip()
            if "退货" in aftersale_type_str:
                aftersale_type = 1
            elif "退款" in aftersale_type_str:
                aftersale_type = 2
            elif "换货" in aftersale_type_str:
                aftersale_type = 3
            else:
                aftersale_type = 0
            
            # 售后状态
            aftersale_status_str = str(row.get("售后状态", "")).strip()
            if any(s in aftersale_status_str for s in self.AFTERSALE_PENDING_STATUS):
                aftersale_status = 2
            elif "成功" in aftersale_status_str or "退款" in aftersale_status_str:
                aftersale_status = 5
            elif "关闭" in aftersale_status_str or "拒绝" in aftersale_status_str:
                aftersale_status = 6
            else:
                aftersale_status = 1
            
            # 售后原因
            reason_text = str(row.get("售后原因", "")).strip()
            reason_code = str(row.get("售后原因标签", "")).strip()
            
            # 判断是否品质问题
            quality_keywords = ["质量", "破损", "与描述不符", "假货", "品质"]
            is_quality_issue = any(kw in reason_text for kw in quality_keywords)
            
            record = {
                "aftersale_id": aftersale_id,
                "order_id": order_id if order_id and order_id != "nan" else None,
                # Excel 导入场景无平台 sku_id，统一用净编码作为 sku_id（仅内部占位，统计聚合以 sku_code 为准）
                "sku_id": sku_code,
                "sku_code": sku_code,
                "sku_code_raw": sku_code_raw,
                "aftersale_type": aftersale_type,
                "aftersale_status": aftersale_status,
                "aftersale_status_desc": aftersale_status_str,
                "reason_text": reason_text,
                "reason_code": reason_code if reason_code != "nan" else None,
                "is_quality_issue": is_quality_issue,
                "apply_time": self._parse_datetime(row.get("售后申请时间")),
                "finish_time": self._parse_datetime(row.get("售后完结时间")),
                # 省份信息：统一先给默认值，避免批量 insert 时部分行缺少 key 导致 SQLAlchemy 报错
                "province_id": None,
                "province_name": None,
                "updated_at": datetime.now(),
            }
            records.append(record)
            
            if order_id and order_id != "nan":
                order_ids_needed.add(order_id)
            
            stats["total"] += 1
        
        if not records:
            return stats
        
        # 2. 批量查询关联订单的省份
        province_map: Dict[str, str] = {}
        if order_ids_needed:
            result = await self.db.execute(
                select(Order.order_id, Order.province_name).where(
                    Order.order_id.in_(list(order_ids_needed))
                )
            )
            for row in result.all():
                province_map[row[0]] = row[1]
        
        # 3. 补充省份信息
        for record in records:
            if record["order_id"] and record["order_id"] in province_map:
                record["province_name"] = province_map[record["order_id"]]
        
        # 4. 批量查询已存在的售后单（用于统计 created/updated）
        aftersale_ids = [r["aftersale_id"] for r in records]
        exist_result = await self.db.execute(
            select(AfterSale.aftersale_id).where(AfterSale.aftersale_id.in_(aftersale_ids))
        )
        existing_ids: Set[str] = set(row[0] for row in exist_result.all())

        # 5. 批量 upsert（避免逐条 UPDATE）
        now = datetime.now()
        for record in records:
            record.setdefault("created_at", now)

        stmt = sqlite_insert(AfterSale).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["aftersale_id"],
            set_={
                "order_id": stmt.excluded.order_id,
                "sku_id": stmt.excluded.sku_id,
                "sku_code": stmt.excluded.sku_code,
                "aftersale_type": stmt.excluded.aftersale_type,
                "aftersale_status": stmt.excluded.aftersale_status,
                "aftersale_status_desc": stmt.excluded.aftersale_status_desc,
                "reason_text": stmt.excluded.reason_text,
                "reason_code": stmt.excluded.reason_code,
                "is_quality_issue": stmt.excluded.is_quality_issue,
                "apply_time": stmt.excluded.apply_time,
                "finish_time": stmt.excluded.finish_time,
                "province_name": stmt.excluded.province_name,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)

        stats["created"] = sum(1 for aid in aftersale_ids if aid not in existing_ids)
        stats["updated"] = sum(1 for aid in aftersale_ids if aid in existing_ids)
        
        # 6. 退货退款类型的售后，标记对应订单为已签收
        # 原因：退货退款意味着买家已收到货并退回，可以确认已签收
        refund_order_ids = [
            r["order_id"] for r in records 
            if r["aftersale_type"] == 1 and r["order_id"]
        ]
        if refund_order_ids:
            await self.db.execute(
                update(Order)
                .where(Order.order_id.in_(refund_order_ids))
                .where(Order.is_signed == False)
                .values(is_signed=True)
            )
        
        # 7. 提交事务（每批次一次提交）
        await self.db.commit()
        
        return stats
    
    def _parse_datetime(self, value) -> Optional[datetime]:
        """解析日期时间"""
        if pd.isna(value) or value == "-" or value == "":
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
        
        try:
            return pd.to_datetime(value).to_pydatetime()
        except Exception:
            return None
