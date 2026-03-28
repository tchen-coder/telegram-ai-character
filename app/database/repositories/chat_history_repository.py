from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, and_, desc, asc, func

from app.database.models import ChatHistory, MessageType
from app.database.repositories.base import BaseRepository


class ChatHistoryRepository(BaseRepository[ChatHistory]):
    """聊天记录数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ChatHistory)

    async def save_message(
        self,
        user_id: str,
        role_id: int,
        message_type: MessageType,
        content: str,
        group_seq: Optional[int] = None,
        timestamp: Optional[int] = None,
        image_url: Optional[str] = None,
        emotion_data: Optional[dict] = None,
        decision_data: Optional[dict] = None,
        meta_json: Optional[dict] = None,
    ) -> ChatHistory:
        """保存聊天消息"""
        chat = ChatHistory(
            user_id=user_id,
            role_id=role_id,
            group_seq=group_seq,
            timestamp=timestamp or int(datetime.utcnow().timestamp() * 1000),
            message_type=message_type,
            content=content,
            image_url=image_url,
            emotion_data=emotion_data,
            decision_data=decision_data,
            meta_json=meta_json,
        )
        self.session.add(chat)
        await self.session.flush()
        return chat

    async def get_next_group_seq(self, user_id: str, role_id: int) -> int:
        result = await self.session.execute(
            select(func.max(ChatHistory.group_seq)).where(
                and_(ChatHistory.user_id == user_id, ChatHistory.role_id == role_id)
            )
        )
        current_max = result.scalar_one_or_none()
        return int(current_max or 0) + 1

    async def get_conversation_history(
        self, user_id: str, role_id: int, limit: int = 20
    ) -> List[ChatHistory]:
        """获取用户与特定角色的聊天历史"""
        result = await self.session.execute(
            select(ChatHistory)
            .where(and_(ChatHistory.user_id == user_id, ChatHistory.role_id == role_id))
            .order_by(desc(ChatHistory.timestamp), desc(ChatHistory.id))
            .limit(limit)
        )
        messages = result.scalars().all()
        return list(reversed(messages))  # 按时间正序返回

    async def get_latest_messages(
        self, user_id: str, role_id: int, limit: int = 10
    ) -> List[ChatHistory]:
        """获取最新的聊天消息"""
        result = await self.session.execute(
            select(ChatHistory)
            .where(and_(ChatHistory.user_id == user_id, ChatHistory.role_id == role_id))
            .order_by(desc(ChatHistory.timestamp), desc(ChatHistory.id))
            .limit(limit)
        )
        messages = result.scalars().all()
        return list(reversed(messages))

    async def count_messages(self, user_id: str, role_id: int) -> int:
        """统计用户与特定角色的消息数"""
        result = await self.session.execute(
            select(ChatHistory).where(
                and_(ChatHistory.user_id == user_id, ChatHistory.role_id == role_id)
            )
        )
        return len(result.scalars().all())

    async def get_user_history(
        self,
        user_id: str,
        role_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[ChatHistory]:
        conditions = [ChatHistory.user_id == user_id]
        if role_id is not None:
            conditions.append(ChatHistory.role_id == role_id)

        result = await self.session.execute(
            select(ChatHistory)
            .where(and_(*conditions))
            .order_by(asc(ChatHistory.timestamp), asc(ChatHistory.id))
            .limit(limit)
        )
        return result.scalars().all()

    async def delete_user_role_history(self, user_id: str, role_id: int) -> None:
        await self.session.execute(
            delete(ChatHistory).where(
                and_(ChatHistory.user_id == user_id, ChatHistory.role_id == role_id)
            )
        )
        await self.session.flush()
