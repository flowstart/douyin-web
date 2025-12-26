"""
物流查询 API
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_maker
from app.models.order import Order
from app.models.system_config import SystemConfig, ConfigKeys
from app.services.kd100_client import KD100Client
from app.services.stats_service import StatsService

router = APIRouter()

# 物流检查任务状态
logistics_tasks = {}


async def get_config_value(db: AsyncSession, key: str, default: str = "") -> str:
    """获取配置值"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == key)
    )
    config = result.scalar_one_or_none()
    return config.config_value if config else default


async def get_logistics_query_interval(db: AsyncSession) -> int:
    """获取物流查询间隔（分钟）"""
    value = await get_config_value(db, ConfigKeys.LOGISTICS_QUERY_INTERVAL, "35")
    try:
        return int(value)
    except ValueError:
        return 35


@router.get("/query/{tracking_number}")
async def query_logistics(
    tracking_number: str,
    company_name: str = Query(..., description="快递公司名称"),
    db: AsyncSession = Depends(get_db),
):
    """
    查询单个物流单号的轨迹
    
    Args:
        tracking_number: 物流单号
        company_name: 快递公司名称，如"申通快递"
    """
    # 从数据库配置获取快递100的密钥
    customer = await get_config_value(db, ConfigKeys.KD100_CUSTOMER)
    key = await get_config_value(db, ConfigKeys.KD100_KEY)
    
    if not customer or not key:
        raise HTTPException(
            status_code=400, 
            detail="请先在系统设置中配置快递100的API密钥"
        )
    
    client = KD100Client(customer=customer, key=key)
    
    try:
        result = await client.query(tracking_number, company_name)
        status = client.parse_status(result)
        
        return {
            "tracking_number": tracking_number,
            "company_name": company_name,
            "raw_result": result,
            "parsed_status": status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
    finally:
        await client.close()


@router.post("/check-all")
async def check_all_logistics(
    background_tasks: BackgroundTasks,
    limit: int = Query(0, ge=0, description="本次检查的订单数量（0 表示全部）"),
    db: AsyncSession = Depends(get_db),
):
    """
    批量检查已发货订单的签收状态
    
    后台异步执行，检查所有有物流单号且超过查询间隔的订单
    完成后自动触发统计重算
    
    注意：同一物流单号的查询间隔默认35分钟，可在系统设置中修改
    """
    # 检查快递100配置
    customer = await get_config_value(db, ConfigKeys.KD100_CUSTOMER)
    key = await get_config_value(db, ConfigKeys.KD100_KEY)
    
    if not customer or not key:
        raise HTTPException(
            status_code=400, 
            detail="请先在系统设置中配置快递100的API密钥"
        )
    
    # 获取查询间隔
    interval_minutes = await get_logistics_query_interval(db)
    interval_threshold = datetime.now() - timedelta(minutes=interval_minutes)
    
    # 查询条件：
    # 1. 有物流单号
    # 2. 已发货状态
    # 3. 未签收
    # 4. 满足以下任一条件：
    #    a. 从未查询过（logistics_checked = False）
    #    b. 上次查询时间超过间隔（updated_at < interval_threshold）
    # 说明：不再强行限制 500/1000；limit=0 表示全部。
    # 为避免一次性把所有订单ID加载到内存，后台任务会按批次分页查询并处理。

    base_conditions = and_(
        Order.logistics_code.isnot(None),
        Order.logistics_code != "",
        Order.order_status == 3,  # 已发货
        Order.is_signed == False,  # 未签收
        or_(
            Order.logistics_checked == False,  # 从未查询过
            Order.updated_at < interval_threshold,  # 超过查询间隔
        ),
    )

    # 先统计总量（用于进度）
    from sqlalchemy import func
    total_result = await db.execute(select(func.count()).select_from(Order).where(base_conditions))
    eligible_total = total_result.scalar() or 0

    # 若指定 limit，则本次目标 total 为 min(eligible_total, limit)
    target_total = eligible_total if limit == 0 else min(eligible_total, limit)
    
    if target_total == 0:
        return {
            "message": "没有需要检查的订单（已全部签收或查询间隔未到）",
            "count": 0,
            "task_id": None,
            "interval_minutes": interval_minutes,
        }
    
    # 创建任务ID
    task_id = f"logistics_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logistics_tasks[task_id] = {
        "status": "processing",
        "total": target_total,
        "checked": 0,
        "signed": 0,
        "skipped": 0,
        "started_at": datetime.now().isoformat(),
        "progress": "正在检查物流状态...",
        "interval_minutes": interval_minutes,
        "limit": limit,
    }
    
    # 添加后台任务
    background_tasks.add_task(
        batch_check_logistics,
        task_id,
        customer,
        key,
        interval_minutes,
        limit,
    )
    
    return {
        "message": f"已启动后台任务，正在检查 {target_total} 个订单的物流状态",
        "count": target_total,
        "task_id": task_id,
        "interval_minutes": interval_minutes,
    }


@router.get("/check-status/{task_id}")
async def get_logistics_check_status(task_id: str):
    """查询物流检查任务状态"""
    if task_id not in logistics_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return logistics_tasks[task_id]


async def batch_check_logistics(
    task_id: str, 
    customer: str, 
    key: str,
    interval_minutes: int,
    limit: int = 0,
):
    """
    批量检查物流状态（后台任务）
    完成后自动触发统计重算
    
    Args:
        task_id: 任务ID
        order_ids: 订单ID列表
        customer: 快递100 customer
        key: 快递100 key
        interval_minutes: 查询间隔（分钟）
    """
    client = KD100Client(customer=customer, key=key)
    checked_count = 0
    signed_count = 0
    skipped_count = 0
    
    interval_threshold = datetime.now() - timedelta(minutes=interval_minutes)
    
    try:
        async with async_session_maker() as db:
            # 分批查询（避免一次性加载所有订单）
            batch_size = 500
            last_id = 0

            while True:
                if limit and checked_count >= limit:
                    break

                remaining = (limit - checked_count) if limit else batch_size
                current_batch_size = min(batch_size, remaining) if limit else batch_size

                # 重新计算阈值，避免任务太久导致间隔判断漂移（逻辑更贴近“当前时刻”）
                interval_threshold = datetime.now() - timedelta(minutes=interval_minutes)

                base_conditions = and_(
                    Order.id > last_id,
                    Order.logistics_code.isnot(None),
                    Order.logistics_code != "",
                    Order.order_status == 3,
                    Order.is_signed == False,
                    or_(
                        Order.logistics_checked == False,
                        Order.updated_at < interval_threshold,
                    )
                )

                batch_result = await db.execute(
                    select(Order)
                    .where(base_conditions)
                    .order_by(Order.id.asc())
                    .limit(current_batch_size)
                )
                orders = batch_result.scalars().all()

                if not orders:
                    break

                for order in orders:
                    last_id = max(last_id, order.id)
                    try:
                        # 再次检查间隔（防止并发任务重复查询）
                        if order.logistics_checked and order.updated_at and order.updated_at >= interval_threshold:
                            skipped_count += 1
                            logistics_tasks[task_id]["skipped"] = skipped_count
                            continue

                        status = await client.check_signed(
                            order.logistics_code,
                            order.logistics_company or "申通快递"
                        )

                        order.logistics_checked = True
                        order.is_signed = status["is_signed"]
                        order.logistics_status_desc = status["status_desc"]
                        order.updated_at = datetime.now()

                        if status["is_signed"]:
                            signed_count += 1
                            if status["latest_time"]:
                                try:
                                    order.sign_time = datetime.strptime(
                                        status["latest_time"],
                                        "%Y-%m-%d %H:%M:%S"
                                    )
                                except Exception:
                                    pass

                        await db.commit()
                        checked_count += 1

                        logistics_tasks[task_id]["checked"] = checked_count
                        logistics_tasks[task_id]["signed"] = signed_count

                        if limit and checked_count >= limit:
                            break

                    except Exception as e:
                        print(f"Error checking order {order.order_id}: {e}")
                        try:
                            await db.rollback()
                        except Exception:
                            pass
                        continue

            # 物流检查完成后，自动重算统计
            logistics_tasks[task_id]["progress"] = "正在重新计算统计..."
            stats_service = StatsService(db)
            sku_stats = await stats_service.calculate_sku_stats()
            sku_count = await stats_service.save_sku_stats(sku_stats)
            
            logistics_tasks[task_id]["status"] = "completed"
            logistics_tasks[task_id]["progress"] = "完成"
            logistics_tasks[task_id]["sku_stats_count"] = sku_count
            logistics_tasks[task_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        logistics_tasks[task_id]["status"] = "failed"
        logistics_tasks[task_id]["error"] = str(e)
    finally:
        await client.close()


@router.get("/stats")
async def get_logistics_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    获取物流状态统计
    """
    from sqlalchemy import func
    
    # 总订单数
    total_result = await db.execute(
        select(func.count()).select_from(Order)
    )
    total = total_result.scalar() or 0
    
    # 有物流单号的订单
    with_logistics_result = await db.execute(
        select(func.count()).select_from(Order).where(
            and_(Order.logistics_code.isnot(None), Order.logistics_code != "")
        )
    )
    with_logistics = with_logistics_result.scalar() or 0
    
    # 已检查物流状态的订单
    checked_result = await db.execute(
        select(func.count()).select_from(Order).where(Order.logistics_checked == True)
    )
    checked = checked_result.scalar() or 0
    
    # 已签收的订单
    signed_result = await db.execute(
        select(func.count()).select_from(Order).where(Order.is_signed == True)
    )
    signed = signed_result.scalar() or 0
    
    # 待检查的订单（有物流单号、已发货、未签收）
    pending_result = await db.execute(
        select(func.count()).select_from(Order).where(
            and_(
                Order.logistics_code.isnot(None),
                Order.logistics_code != "",
                Order.order_status == 3,
                Order.is_signed == False,
            )
        )
    )
    pending_check = pending_result.scalar() or 0
    
    # 获取查询间隔配置
    interval_minutes = await get_logistics_query_interval(db)
    
    return {
        "total_orders": total,
        "with_logistics": with_logistics,
        "checked": checked,
        "signed": signed,
        "pending_check": pending_check,
        "query_interval_minutes": interval_minutes,
    }
