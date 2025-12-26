"""
导入 Worker（队列消费）

- API 只负责上传文件 + 入队
- Worker 从 DB 队列表取任务执行导入与统计
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_maker
from app.models.import_job import ImportJob
from app.models.import_task import ImportTask
from app.services.excel_import import ExcelImportService
from app.services.stats_service import StatsService

settings = get_settings()


class ImportWorker:
    def __init__(self):
        self._stop_event = asyncio.Event()

    def stop(self):
        self._stop_event.set()

    async def _update_task(self, db: AsyncSession, task_id: str, **kwargs):
        stmt = select(ImportTask).where(ImportTask.task_id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            return
        for key, value in kwargs.items():
            setattr(task, key, value)
        await db.commit()

    async def _cleanup_old_tasks(self, db: AsyncSession, max_tasks: int = 15):
        """清理多余的 ImportTask，同时清理对应 ImportJob（按 task_id 关联）"""
        stmt = select(ImportTask).order_by(ImportTask.started_at.desc())
        result = await db.execute(stmt)
        tasks = result.scalars().all()
        if len(tasks) <= max_tasks:
            return

        old_task_ids = [t.task_id for t in tasks[max_tasks:]]
        await db.execute(delete(ImportTask).where(ImportTask.task_id.in_(old_task_ids)))
        await db.execute(delete(ImportJob).where(ImportJob.task_id.in_(old_task_ids)))
        await db.commit()

    async def _claim_one_job(self, db: AsyncSession) -> Optional[ImportJob]:
        """尝试领取一个 queued 的任务（通过 update 条件保证多 worker 不重复消费）"""
        result = await db.execute(
            select(ImportJob)
            .where(ImportJob.status == "queued")
            .order_by(ImportJob.created_at.asc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if not job:
            return None

        now = datetime.now()
        claim_result = await db.execute(
            update(ImportJob)
            .where(ImportJob.id == job.id, ImportJob.status == "queued")
            .values(status="processing", picked_at=now, updated_at=now)
        )
        await db.commit()

        if (claim_result.rowcount or 0) != 1:
            return None

        # 重新读取最新 job
        refreshed = await db.execute(select(ImportJob).where(ImportJob.id == job.id))
        return refreshed.scalar_one()

    def _resolve_paths(self, task_type: str, payload: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
        payload = payload or {}
        upload_dir = settings.upload_dir
        orders_filename = payload.get("orders_filename")
        aftersales_filename = payload.get("aftersales_filename")

        orders_path = f"{upload_dir}/{orders_filename}" if orders_filename else None
        aftersales_path = f"{upload_dir}/{aftersales_filename}" if aftersales_filename else None

        if task_type == "orders":
            return orders_path, None
        if task_type == "aftersales":
            return None, aftersales_path
        if task_type == "all":
            return orders_path, aftersales_path
        return None, None

    async def _process_job(self, job: ImportJob):
        async with async_session_maker() as db:
            try:
                import_service = ExcelImportService(db)
                stats_service = StatsService(db)

                orders_path, aftersales_path = self._resolve_paths(job.task_type, job.payload)

                order_stats = None
                aftersale_stats = None

                if job.task_type in ("orders", "all"):
                    if not orders_path:
                        raise ValueError("缺少 orders 文件")
                    await self._update_task(db, job.task_id, progress="排队结束，正在导入订单...")
                    order_stats = await import_service.import_orders(orders_path)
                    await self._update_task(db, job.task_id, order_stats=order_stats)

                if job.task_type in ("aftersales", "all"):
                    if not aftersales_path:
                        raise ValueError("缺少 aftersales 文件")
                    await self._update_task(db, job.task_id, progress="正在导入售后单...")
                    aftersale_stats = await import_service.import_aftersales(aftersales_path)
                    await self._update_task(db, job.task_id, aftersale_stats=aftersale_stats)

                # 重算统计
                await self._update_task(db, job.task_id, progress="正在重新计算统计...")
                sku_stats = await stats_service.calculate_sku_stats()
                sku_count = await stats_service.save_sku_stats(sku_stats)

                # 标记完成（ImportTask）
                await self._update_task(
                    db,
                    job.task_id,
                    status="completed",
                    progress="完成",
                    sku_stats_count=sku_count,
                    completed_at=datetime.now(),
                )

                # 标记完成（ImportJob）
                await db.execute(
                    update(ImportJob)
                    .where(ImportJob.id == job.id)
                    .values(status="completed", updated_at=datetime.now())
                )
                await db.commit()

                await self._cleanup_old_tasks(db)
            except Exception as e:
                # 任务失败：记录到 ImportTask + ImportJob
                await self._update_task(db, job.task_id, status="failed", error=str(e), progress="失败")
                await db.execute(
                    update(ImportJob)
                    .where(ImportJob.id == job.id)
                    .values(status="failed", updated_at=datetime.now())
                )
                await db.commit()

    async def run_forever(self):
        """循环消费队列任务"""
        poll_interval = settings.import_worker_poll_interval

        while not self._stop_event.is_set():
            try:
                async with async_session_maker() as db:
                    job = await self._claim_one_job(db)
                if not job:
                    await asyncio.sleep(poll_interval)
                    continue
                await self._process_job(job)
            except Exception:
                # 避免 worker 崩溃，短暂休眠再继续
                await asyncio.sleep(poll_interval)


