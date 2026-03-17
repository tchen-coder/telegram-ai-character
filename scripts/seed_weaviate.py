#!/usr/bin/env python3
"""
构建 Weaviate 角色知识和历史对话记忆。

用法:
  python3 scripts/seed_weaviate.py
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_db_manager  # noqa: E402
from app.database.models import ChatHistory  # noqa: E402
from app.rag import rag_service  # noqa: E402
from app.services.role_service import RoleService  # noqa: E402
from app.services.chat_service import ChatMessage  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    db_manager = get_db_manager()
    await rag_service.ensure_ready()

    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        roles = await role_service.get_all_active_roles()
        for role in roles:
            await rag_service.index_role_knowledge(role)

        result = await session.execute(
            select(ChatHistory).order_by(ChatHistory.created_at.asc())
        )
        rows = result.scalars().all()
        for row in rows:
            await rag_service.index_chat_memory(ChatMessage.from_orm(row))

    logger.info("Weaviate seed finished: roles=%s messages=%s", len(roles), len(rows))


if __name__ == "__main__":
    asyncio.run(main())
