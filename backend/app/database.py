"""
数据库连接和会话管理
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# 创建异步引擎
engine_kwargs = {
    "echo": settings.sqlalchemy_echo,
}
# SQLite 导入期间容易出现读写锁竞争：适当加大 timeout，并在 init_db 里启用 WAL
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"timeout": 60}

engine = create_async_engine(settings.database_url, **engine_kwargs)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 模型基类"""
    pass


async def get_db() -> AsyncSession:
    """获取数据库会话（依赖注入）"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库表"""
    async with engine.begin() as conn:
        # SQLite 性能/并发优化（WAL 会持久化到 DB 文件，设置一次即可）
        if settings.database_url.startswith("sqlite"):
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA synchronous=NORMAL;"))
            await conn.execute(text("PRAGMA temp_store=MEMORY;"))
            await conn.execute(text("PRAGMA foreign_keys=ON;"))
            await conn.execute(text("PRAGMA busy_timeout=60000;"))
        await conn.run_sync(Base.metadata.create_all)

        # SQLite 轻量“补列”迁移（create_all 不会给已有表新增列）
        if settings.database_url.startswith("sqlite"):
            async def _table_columns(table_name: str) -> set[str]:
                result = await conn.execute(text(f"PRAGMA table_info('{table_name}')"))
                rows = result.fetchall()
                return {r[1] for r in rows}  # (cid, name, type, notnull, dflt_value, pk)

            async def _ensure_column(table_name: str, column_name: str, ddl: str):
                cols = await _table_columns(table_name)
                if column_name in cols:
                    return
                await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))

            # sku_stats：历史 DB 可能缺少图片/品质统计列
            await _ensure_column("sku_stats", "image_url", "image_url VARCHAR(512)")
            await _ensure_column("sku_stats", "quality_return_count", "quality_return_count INTEGER NOT NULL DEFAULT 0")
            await _ensure_column("sku_stats", "quality_return_rate", "quality_return_rate FLOAT NOT NULL DEFAULT 0")

            # order_skus / after_sales：保留原始商家编码（用于追溯）
            await _ensure_column("order_skus", "sku_code_raw", "sku_code_raw VARCHAR(128)")
            await _ensure_column("after_sales", "sku_code_raw", "sku_code_raw VARCHAR(128)")

            # 一次性归一化（轻量）：将历史数据的 sku_code_raw 补齐，并清洗 sku_code
            # 说明：SQLite 不支持正则替换，这里用 Python 做清洗并按需更新；仅在 sku_code_raw 为空的历史库上起作用
            from app.utils.sku_code import clean_sku_code  # local import to avoid import-time overhead

            async def _backfill_table(table_name: str):
                # 1) 先把 raw 补齐（SQL 快速批量）
                await conn.execute(
                    text(
                        f"""
                        UPDATE {table_name}
                        SET sku_code_raw = sku_code
                        WHERE sku_code IS NOT NULL
                          AND (sku_code_raw IS NULL OR sku_code_raw = '')
                        """
                    )
                )

                # 2) 清洗 sku_code（仅处理包含括号或存在多余空白的行）
                rows = await conn.execute(
                    text(
                        f"""
                        SELECT id, sku_code
                        FROM {table_name}
                        WHERE sku_code IS NOT NULL
                          AND (
                            instr(sku_code, '(') > 0 OR instr(sku_code, '（') > 0 OR sku_code != trim(sku_code)
                          )
                        """
                    )
                )
                to_update: list[tuple[int, str]] = []
                for row in rows.fetchall():
                    rid = int(row[0])
                    old = row[1]
                    new = clean_sku_code(old)
                    if new and new != old:
                        to_update.append((rid, new))

                # 批量更新（按 SQLite 参数上限做分批）
                if not to_update:
                    return

                BATCH = 500
                for i in range(0, len(to_update), BATCH):
                    batch = to_update[i : i + BATCH]
                    for rid, new_code in batch:
                        await conn.execute(
                            text(f"UPDATE {table_name} SET sku_code = :sku_code WHERE id = :id"),
                            {"id": rid, "sku_code": new_code},
                        )

            await _backfill_table("order_skus")
            await _backfill_table("after_sales")

