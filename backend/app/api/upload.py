"""
文件上传 API
"""
import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.models.import_task import ImportTask
from app.models.import_job import ImportJob

router = APIRouter()
settings = get_settings()

# 最大保留任务数
MAX_TASKS = 15


async def cleanup_old_tasks(db: AsyncSession):
    """清理超过最大数量的旧任务"""
    # 获取所有任务按开始时间降序
    stmt = select(ImportTask).order_by(ImportTask.started_at.desc())
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    # 如果超过15条，删除旧的
    if len(tasks) > MAX_TASKS:
        old_task_ids = [t.task_id for t in tasks[MAX_TASKS:]]
        await db.execute(delete(ImportTask).where(ImportTask.task_id.in_(old_task_ids)))
        await db.execute(delete(ImportJob).where(ImportJob.task_id.in_(old_task_ids)))
        await db.commit()


async def create_task(db: AsyncSession, task_id: str, task_type: str, filename: str = None) -> ImportTask:
    """创建任务记录"""
    task = ImportTask(
        task_id=task_id,
        task_type=task_type,
        status="processing",
        progress="排队中...",
        filename=filename,
        started_at=datetime.now(),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task(db: AsyncSession, task_id: str, **kwargs):
    """更新任务记录"""
    stmt = select(ImportTask).where(ImportTask.task_id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if task:
        for key, value in kwargs.items():
            setattr(task, key, value)
        await db.commit()


@router.post("/orders")
async def upload_orders(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    上传订单Excel文件（后台异步处理）
    
    支持 .xlsx 格式的订单导出文件
    立即返回任务ID，后台异步导入
    """
    # 验证文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持Excel文件(.xlsx, .xls)")
    
    # 创建上传目录
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = f"orders_{timestamp}"
    filename = f"{task_id}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建任务记录到数据库
        await create_task(db, task_id, "orders", filename)
        # 入队：由 worker 异步消费
        job = ImportJob(
            task_id=task_id,
            task_type="orders",
            status="queued",
            payload={"orders_filename": filename},
        )
        db.add(job)
        await db.commit()
        
        return {
            "message": "订单文件已上传，已进入队列，后台将自动导入并计算统计。",
            "task_id": task_id,
            "filename": filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")
    finally:
        file.file.close()


@router.post("/aftersales")
async def upload_aftersales(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    上传售后单Excel文件（后台异步处理）
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持Excel文件(.xlsx, .xls)")
    
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = f"aftersales_{timestamp}"
    filename = f"{task_id}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建任务记录到数据库
        await create_task(db, task_id, "aftersales", filename)
        # 入队：由 worker 异步消费
        job = ImportJob(
            task_id=task_id,
            task_type="aftersales",
            status="queued",
            payload={"aftersales_filename": filename},
        )
        db.add(job)
        await db.commit()
        
        return {
            "message": "售后单文件已上传，已进入队列，后台将自动导入并计算统计。",
            "task_id": task_id,
            "filename": filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")
    finally:
        file.file.close()


@router.post("/all")
async def upload_all_and_calculate(
    orders_file: UploadFile = File(..., description="订单文件"),
    aftersales_file: UploadFile = File(..., description="售后单文件"),
    db: AsyncSession = Depends(get_db),
):
    """
    上传订单和售后单文件，后台异步处理
    """
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = f"all_{timestamp}"
    
    try:
        # 保存订单文件
        orders_path = os.path.join(upload_dir, f"orders_{timestamp}.xlsx")
        with open(orders_path, "wb") as buffer:
            shutil.copyfileobj(orders_file.file, buffer)
        
        # 保存售后单文件
        aftersales_path = os.path.join(upload_dir, f"aftersales_{timestamp}.xlsx")
        with open(aftersales_path, "wb") as buffer:
            shutil.copyfileobj(aftersales_file.file, buffer)
        
        # 创建任务记录
        await create_task(db, task_id, "all", f"{orders_file.filename}, {aftersales_file.filename}")
        # 入队：由 worker 异步消费
        job = ImportJob(
            task_id=task_id,
            task_type="all",
            status="queued",
            payload={
                "orders_filename": f"orders_{timestamp}.xlsx",
                "aftersales_filename": f"aftersales_{timestamp}.xlsx",
            },
        )
        db.add(job)
        await db.commit()
        
        return {
            "message": "文件已上传，已进入队列，后台将自动导入并计算统计。",
            "task_id": task_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")
    finally:
        orders_file.file.close()
        aftersales_file.file.close()


@router.get("/status/{task_id}")
async def get_import_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """查询导入任务状态"""
    stmt = select(ImportTask).where(ImportTask.task_id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task.to_dict()


@router.get("/tasks")
async def list_import_tasks(db: AsyncSession = Depends(get_db)):
    """列出最近15条导入任务"""
    stmt = select(ImportTask).order_by(ImportTask.started_at.desc()).limit(MAX_TASKS)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    return {
        "tasks": [t.to_dict() for t in tasks],
        "count": len(tasks),
    }


@router.post("/sku-image/{sku_code}")
async def upload_sku_image(
    sku_code: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    上传SKU商品图片
    
    图片会存储在 uploads/sku_images/ 目录
    支持 jpg, jpeg, png, gif, webp 格式
    """
    from app.models.sku_stats import SkuStats
    
    # 验证文件类型
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"只支持图片格式: {', '.join(allowed_extensions)}"
        )
    
    # 创建目录
    image_dir = os.path.join(settings.upload_dir, "sku_images")
    os.makedirs(image_dir, exist_ok=True)
    
    # 生成文件名（使用 sku_code 作为文件名，覆盖已有图片）
    # 清理 sku_code 中的特殊字符
    safe_sku_code = "".join(c if c.isalnum() or c in '-_' else '_' for c in sku_code)
    filename = f"{safe_sku_code}{file_ext}"
    file_path = os.path.join(image_dir, filename)
    
    try:
        # 保存图片
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 生成访问 URL
        image_url = f"/uploads/sku_images/{filename}"
        
        # 更新 sku_stats 表
        result = await db.execute(
            select(SkuStats).where(SkuStats.sku_code == sku_code)
        )
        sku_stats = result.scalar_one_or_none()
        
        if sku_stats:
            sku_stats.image_url = image_url
            await db.commit()
        
        return {
            "message": "图片上传成功",
            "sku_code": sku_code,
            "image_url": image_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")
    finally:
        file.file.close()
