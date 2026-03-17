from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from sqlalchemy import inspect, text
from typing import Optional
import logging

from app.database.models import Base
from app.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库连接管理器"""

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
        """统一 MySQL 连接方言和字符集，避免中文在会话层被降级。"""
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
        """创建所有表"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(self._ensure_schema_sync)
        logger.info("数据库表创建完成")

    @staticmethod
    def _ensure_schema_sync(sync_conn) -> None:
        inspector = inspect(sync_conn)
        table_names = inspector.get_table_names()
        if "roles" not in table_names:
            return

        role_columns = {column["name"] for column in inspector.get_columns("roles")}
        if "system_prompt_friend" not in role_columns:
            sync_conn.execute(text("ALTER TABLE roles ADD COLUMN system_prompt_friend TEXT NULL"))
            logger.info("数据库结构已补齐: roles.system_prompt_friend")
        if "system_prompt_partner" not in role_columns:
            sync_conn.execute(text("ALTER TABLE roles ADD COLUMN system_prompt_partner TEXT NULL"))
            logger.info("数据库结构已补齐: roles.system_prompt_partner")
        if "system_prompt_lover" not in role_columns:
            sync_conn.execute(text("ALTER TABLE roles ADD COLUMN system_prompt_lover TEXT NULL"))
            logger.info("数据库结构已补齐: roles.system_prompt_lover")
        if "tags" not in role_columns:
            sync_conn.execute(text("ALTER TABLE roles ADD COLUMN tags JSON NULL"))
            logger.info("数据库结构已补齐: roles.tags")

        if "role_relationship_prompts" in table_names:
            prompt_columns = {
                column["name"] for column in inspector.get_columns("role_relationship_prompts")
            }
            if "is_active" not in prompt_columns:
                sync_conn.execute(
                    text(
                        "ALTER TABLE role_relationship_prompts "
                        "ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"
                    )
                )
                logger.info("数据库结构已补齐: role_relationship_prompts.is_active")
            if "updated_at" not in prompt_columns:
                sync_conn.execute(
                    text(
                        "ALTER TABLE role_relationship_prompts "
                        "ADD COLUMN updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP "
                        "ON UPDATE CURRENT_TIMESTAMP"
                    )
                )
                logger.info("数据库结构已补齐: role_relationship_prompts.updated_at")
            if "created_at" not in prompt_columns:
                sync_conn.execute(
                    text(
                        "ALTER TABLE role_relationship_prompts "
                        "ADD COLUMN created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP"
                    )
                )
                logger.info("数据库结构已补齐: role_relationship_prompts.created_at")

            sync_conn.execute(
                text(
                    "INSERT INTO role_relationship_prompts "
                    "(role_id, relationship, prompt_text, is_active, created_at, updated_at) "
                    "SELECT r.id, 1, COALESCE(NULLIF(r.system_prompt_friend, ''), r.system_prompt), "
                    "TRUE, UTC_TIMESTAMP(), UTC_TIMESTAMP() "
                    "FROM roles r "
                    "WHERE COALESCE(NULLIF(r.system_prompt_friend, ''), r.system_prompt) IS NOT NULL "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM role_relationship_prompts p "
                    "  WHERE p.role_id = r.id AND p.relationship = 1"
                    ")"
                )
            )
            sync_conn.execute(
                text(
                    "INSERT INTO role_relationship_prompts "
                    "(role_id, relationship, prompt_text, is_active, created_at, updated_at) "
                    "SELECT r.id, 2, r.system_prompt_partner, TRUE, UTC_TIMESTAMP(), UTC_TIMESTAMP() "
                    "FROM roles r "
                    "WHERE NULLIF(r.system_prompt_partner, '') IS NOT NULL "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM role_relationship_prompts p "
                    "  WHERE p.role_id = r.id AND p.relationship = 2"
                    ")"
                )
            )
            sync_conn.execute(
                text(
                    "INSERT INTO role_relationship_prompts "
                    "(role_id, relationship, prompt_text, is_active, created_at, updated_at) "
                    "SELECT r.id, 3, r.system_prompt_lover, TRUE, UTC_TIMESTAMP(), UTC_TIMESTAMP() "
                    "FROM roles r "
                    "WHERE NULLIF(r.system_prompt_lover, '') IS NOT NULL "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM role_relationship_prompts p "
                    "  WHERE p.role_id = r.id AND p.relationship = 3"
                    ")"
                )
            )

        if "user_roles" in table_names:
            user_role_columns = {column["name"] for column in inspector.get_columns("user_roles")}
            if "relationship" not in user_role_columns:
                sync_conn.execute(text("ALTER TABLE user_roles ADD COLUMN relationship INT NOT NULL DEFAULT 3"))
                logger.info("数据库结构已补齐: user_roles.relationship")
            sync_conn.execute(
                text("ALTER TABLE user_roles MODIFY COLUMN relationship INT NOT NULL DEFAULT 3")
            )
            if "first_interaction_at" not in user_role_columns:
                sync_conn.execute(text("ALTER TABLE user_roles ADD COLUMN first_interaction_at DATETIME NULL"))
                logger.info("数据库结构已补齐: user_roles.first_interaction_at")
            if "last_interaction_at" not in user_role_columns:
                sync_conn.execute(text("ALTER TABLE user_roles ADD COLUMN last_interaction_at DATETIME NULL"))
                logger.info("数据库结构已补齐: user_roles.last_interaction_at")

        if "chat_history" in table_names:
            chat_columns = {column["name"] for column in inspector.get_columns("chat_history")}
            sync_conn.execute(
                text(
                    "ALTER TABLE chat_history "
                    "MODIFY COLUMN message_type "
                    "ENUM('USER','ASSISTANT','ASSISTANT_IMAGE') NOT NULL"
                )
            )
            if "image_url" not in chat_columns:
                sync_conn.execute(text("ALTER TABLE chat_history ADD COLUMN image_url VARCHAR(500) NULL"))
                logger.info("数据库结构已补齐: chat_history.image_url")
            if "meta_json" not in chat_columns:
                sync_conn.execute(text("ALTER TABLE chat_history ADD COLUMN meta_json JSON NULL"))
                logger.info("数据库结构已补齐: chat_history.meta_json")

    async def drop_db(self):
        """删除所有表（仅用于测试）"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("数据库表删除完成")

    async def get_session(self) -> AsyncSession:
        """获取数据库会话"""
        async with self.async_session() as session:
            yield session

    async def close(self):
        """关闭数据库连接"""
        await self.engine.dispose()
        logger.info("数据库连接已关闭")


# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        settings = get_settings()
        if not settings.database_url:
            raise ValueError("DATABASE_URL 环境变量未配置")
        _db_manager = DatabaseManager(settings.database_url)
    return _db_manager


async def init_database():
    """初始化数据库"""
    db_manager = get_db_manager()
    await db_manager.init_db()


async def close_database():
    """关闭数据库连接"""
    db_manager = get_db_manager()
    await db_manager.close()
