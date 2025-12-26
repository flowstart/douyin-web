"""
系统配置 API
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.system_config import SystemConfig, ConfigKeys, DEFAULT_CONFIGS

router = APIRouter()


class ConfigItem(BaseModel):
    """配置项"""
    config_key: str
    config_value: str
    description: str


class ConfigUpdate(BaseModel):
    """配置更新"""
    config_value: str


async def get_config_value(db: AsyncSession, key: str, default: str = "") -> str:
    """获取配置值"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == key)
    )
    config = result.scalar_one_or_none()
    if config:
        return config.config_value
    return default


async def init_default_configs(db: AsyncSession):
    """初始化默认配置（如果不存在）"""
    for key, data in DEFAULT_CONFIGS.items():
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_key == key)
        )
        if not result.scalar_one_or_none():
            config = SystemConfig(
                config_key=key,
                config_value=data["value"],
                description=data["description"],
            )
            db.add(config)
    await db.commit()


@router.get("", response_model=List[ConfigItem])
async def get_all_configs(db: AsyncSession = Depends(get_db)):
    """获取所有配置"""
    # 确保默认配置存在
    await init_default_configs(db)
    
    result = await db.execute(select(SystemConfig))
    configs = result.scalars().all()
    
    return [
        ConfigItem(
            config_key=c.config_key,
            config_value=c.config_value,
            description=c.description,
        )
        for c in configs
    ]


@router.get("/{key}")
async def get_config(key: str, db: AsyncSession = Depends(get_db)):
    """获取单个配置"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == key)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        # 检查是否是预定义配置
        if key in DEFAULT_CONFIGS:
            return ConfigItem(
                config_key=key,
                config_value=DEFAULT_CONFIGS[key]["value"],
                description=DEFAULT_CONFIGS[key]["description"],
            )
        raise HTTPException(status_code=404, detail="配置不存在")
    
    return ConfigItem(
        config_key=config.config_key,
        config_value=config.config_value,
        description=config.description,
    )


@router.put("/{key}")
async def update_config(
    key: str, 
    data: ConfigUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """更新配置"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == key)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        # 如果是预定义配置，创建新记录
        if key in DEFAULT_CONFIGS:
            config = SystemConfig(
                config_key=key,
                config_value=data.config_value,
                description=DEFAULT_CONFIGS[key]["description"],
            )
            db.add(config)
        else:
            raise HTTPException(status_code=404, detail="配置不存在")
    else:
        config.config_value = data.config_value
    
    await db.commit()
    
    return {"message": "配置更新成功", "key": key, "value": data.config_value}


@router.post("/batch")
async def update_configs_batch(
    configs: List[ConfigItem],
    db: AsyncSession = Depends(get_db)
):
    """批量更新配置"""
    updated = 0
    for item in configs:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_key == item.config_key)
        )
        config = result.scalar_one_or_none()
        
        if config:
            config.config_value = item.config_value
        else:
            config = SystemConfig(
                config_key=item.config_key,
                config_value=item.config_value,
                description=item.description,
            )
            db.add(config)
        updated += 1
    
    await db.commit()
    
    return {"message": f"已更新 {updated} 项配置"}

