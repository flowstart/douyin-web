"""
FastAPI 应用入口
"""
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.api import api_router
from app.workers.import_worker import ImportWorker
from app import models  # noqa: F401  (确保所有模型已注册到 Base.metadata，用于 create_all)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    # 确保上传目录存在
    os.makedirs(os.path.join(settings.upload_dir, "sku_images"), exist_ok=True)

    # 启动导入 worker（可通过配置关闭，改用独立进程）
    worker_task: asyncio.Task | None = None
    worker: ImportWorker | None = None
    if settings.enable_import_worker:
        worker = ImportWorker()
        worker_task = asyncio.create_task(worker.run_forever())

    yield
    # 关闭时清理资源
    if worker:
        worker.stop()
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except Exception:
            pass


app = FastAPI(
    title="抖音订单统计系统",
    description="基于抖音开放平台的订单数据统计和分析系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（用于访问上传的图片）
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

# 注册路由
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "抖音订单统计系统",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )

