from typing import Optional
import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database.models import Base
from app.relationship.domain import (
    DEFAULT_INITIAL_RV,
    DEFAULT_MAX_NEGATIVE_DELTA,
    DEFAULT_MAX_POSITIVE_DELTA,
    DEFAULT_RECENT_WINDOW_SIZE,
    DEFAULT_UPDATE_FREQUENCY,
)

logger = logging.getLogger(__name__)

OBSOLETE_TABLES = (
    "user_role_relationship_events",
    "user_role_relationship_states",
)


class DatabaseManager:
    """数据库连接管理器。"""

    def __init__(self, database_url: str):
        database_url, connect_args = self._normalize_database_url(database_url)
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    @staticmethod
    def _normalize_database_url(database_url: str) -> tuple[str, dict]:
        if database_url.startswith("mysql://"):
            database_url = database_url.replace("mysql://", "mysql+aiomysql://", 1)

        url = make_url(database_url)
        connect_args = {}
        if url.drivername.startswith("mysql"):
            query = dict(url.query)
            if query.get("charset") != "utf8mb4":
                query["charset"] = "utf8mb4"
            database_url = url.set(query=query).render_as_string(hide_password=False)
            connect_args = {
                "charset": "utf8mb4",
                "use_unicode": True,
                "init_command": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
            }

        return database_url, connect_args

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(self._ensure_schema_sync)
        logger.info("数据库表创建完成")

    @staticmethod
    def _ensure_schema_sync(sync_conn) -> None:
        inspector = inspect(sync_conn)
        table_names = set(inspector.get_table_names())
        if "roles" not in table_names:
            return

        for table_name in OBSOLETE_TABLES:
            if table_name in table_names:
                sync_conn.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
                logger.info("已删除废弃表: %s", table_name)

        role_columns = {column["name"] for column in inspector.get_columns("roles")}
        if "role_id" not in role_columns:
            sync_conn.execute(text("ALTER TABLE roles ADD COLUMN role_id INT NULL"))
            sync_conn.execute(text("UPDATE roles SET role_id = id WHERE role_id IS NULL"))
            sync_conn.execute(text("ALTER TABLE roles MODIFY COLUMN role_id INT NOT NULL"))
            logger.info("数据库结构已补齐: roles.role_id")
        if "tags" not in role_columns:
            sync_conn.execute(text("ALTER TABLE roles ADD COLUMN tags JSON NULL"))
            logger.info("数据库结构已补齐: roles.tags")

        if "role_relationship_configs" in table_names:
            sync_conn.execute(
                text(
                    "INSERT INTO role_relationship_configs "
                    "("
                    "role_id, initial_rv, update_frequency, max_negative_delta, "
                    "max_positive_delta, recent_window_size, stage_names, stage_floor_rv, "
                    "stage_thresholds, paid_boost_enabled, meta_json, created_at, updated_at"
                    ") "
                    "SELECT "
                    "r.id, :initial_rv, :update_frequency, :max_negative_delta, "
                    ":max_positive_delta, :recent_window_size, "
                    "JSON_ARRAY('朋友', '恋人', '爱人'), "
                    "JSON_ARRAY(0, 40, 70), "
                    "JSON_ARRAY(40, 70, 100), "
                    "FALSE, NULL, UTC_TIMESTAMP(), UTC_TIMESTAMP() "
                    "FROM roles r "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM role_relationship_configs cfg "
                    "  WHERE cfg.role_id = r.id"
                    ")"
                ),
                {
                    "initial_rv": DEFAULT_INITIAL_RV,
                    "update_frequency": DEFAULT_UPDATE_FREQUENCY,
                    "max_negative_delta": DEFAULT_MAX_NEGATIVE_DELTA,
                    "max_positive_delta": DEFAULT_MAX_POSITIVE_DELTA,
                    "recent_window_size": DEFAULT_RECENT_WINDOW_SIZE,
                },
            )

        if "user_roles" in table_names:
            user_role_columns = {column["name"] for column in inspector.get_columns("user_roles")}
            if "real_user_id" not in user_role_columns:
                sync_conn.execute(text("ALTER TABLE user_roles ADD COLUMN real_user_id VARCHAR(50) NULL"))
            if "relationship" not in user_role_columns:
                sync_conn.execute(
                    text("ALTER TABLE user_roles ADD COLUMN relationship INT NOT NULL DEFAULT 1")
                )
            else:
                sync_conn.execute(
                    text("ALTER TABLE user_roles MODIFY COLUMN relationship INT NOT NULL DEFAULT 1")
                )
            if "first_interaction_at" not in user_role_columns:
                sync_conn.execute(text("ALTER TABLE user_roles ADD COLUMN first_interaction_at DATETIME NULL"))
            if "last_interaction_at" not in user_role_columns:
                sync_conn.execute(text("ALTER TABLE user_roles ADD COLUMN last_interaction_at DATETIME NULL"))

        if "chat_history" in table_names:
            chat_columns = {column["name"] for column in inspector.get_columns("chat_history")}
            sync_conn.execute(
                text(
                    "ALTER TABLE chat_history "
                    "MODIFY COLUMN message_type "
                    "ENUM('USER','ASSISTANT','ASSISTANT_IMAGE') NOT NULL"
                )
            )
            if "group_seq" not in chat_columns:
                sync_conn.execute(text("ALTER TABLE chat_history ADD COLUMN group_seq INT NULL"))
            if "timestamp" not in chat_columns:
                sync_conn.execute(
                    text(
                        "ALTER TABLE chat_history "
                        "ADD COLUMN `timestamp` BIGINT NULL"
                    )
                )
                sync_conn.execute(
                    text(
                        "UPDATE chat_history "
                        "SET `timestamp` = UNIX_TIMESTAMP(created_at) * 1000 "
                        "WHERE `timestamp` IS NULL"
                    )
                )
                sync_conn.execute(
                    text(
                        "ALTER TABLE chat_history "
                        "MODIFY COLUMN `timestamp` BIGINT NOT NULL"
                    )
                )
            if "image_url" not in chat_columns:
                sync_conn.execute(text("ALTER TABLE chat_history ADD COLUMN image_url VARCHAR(500) NULL"))
            if "meta_json" not in chat_columns:
                sync_conn.execute(text("ALTER TABLE chat_history ADD COLUMN meta_json JSON NULL"))

    async def drop_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("数据库表删除完成")

    async def get_session(self) -> AsyncSession:
        async with self.async_session() as session:
            yield session

    async def close(self):
        await self.engine.dispose()
        logger.info("数据库连接已关闭")


_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        settings = get_settings()
        if not settings.database_url:
            raise ValueError("DATABASE_URL 环境变量未配置")
        _db_manager = DatabaseManager(settings.database_url)
    return _db_manager


async def init_database():
    db_manager = get_db_manager()
    await db_manager.init_db()


async def close_database():
    db_manager = get_db_manager()
    await db_manager.close()
