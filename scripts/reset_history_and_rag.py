#!/usr/bin/env python3
"""
清空聊天历史，并重置 Weaviate RAG 数据。

行为：
1. 清空 MySQL chat_history
2. 重建 Weaviate collections
3. 仅回灌角色知识，不回灌旧聊天历史
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_db_manager  # noqa: E402
from app.database.models import ChatHistory  # noqa: E402
from app.rag import rag_service  # noqa: E402
from app.services.role_service import RoleService  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    db_manager = get_db_manager()

    async with db_manager.async_session() as session:
        await session.execute(delete(ChatHistory))
        await session.commit()

        role_service = RoleService(session)
        roles = await role_service.get_all_active_roles()

    await rag_service.clear_all()
    for role in roles:
        await rag_service.index_role_knowledge(role)

    logger.info("History and RAG reset finished: roles=%s", len(roles))


if __name__ == "__main__":
    asyncio.run(main())
