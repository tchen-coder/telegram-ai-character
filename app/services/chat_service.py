from typing import List, Optional
import copy
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.dispatch import dispatch_layer
from app.database.models import ChatHistory, MessageType
from app.database.repositories import ChatHistoryRepository


class ChatMessage(BaseModel):
    """聊天消息模型"""
    id: int
    user_id: str
    role_id: int
    message_type: str
    content: str
    image_url: Optional[str] = None
    emotion_data: Optional[dict] = None
    decision_data: Optional[dict] = None
    meta_json: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatService:
    """聊天记录业务逻辑层"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.chat_repo = ChatHistoryRepository(session)

    async def save_user_message(
        self,
        user_id: str,
        role_id: int,
        content: str,
        emotion_data: Optional[dict] = None,
    ) -> ChatMessage:
        """保存用户消息"""
        chat = await self.chat_repo.save_message(
            user_id=user_id,
            role_id=role_id,
            message_type=MessageType.USER,
            content=content,
            emotion_data=emotion_data,
        )
        await self.session.commit()
        return ChatMessage.from_orm(chat)

    async def save_assistant_message(
        self,
        user_id: str,
        role_id: int,
        content: str,
        decision_data: Optional[dict] = None,
    ) -> ChatMessage:
        """保存 AI 回复消息"""
        chat = await self.chat_repo.save_message(
            user_id=user_id,
            role_id=role_id,
            message_type=MessageType.ASSISTANT,
            content=content,
            decision_data=decision_data,
        )
        await self.session.commit()
        return ChatMessage.from_orm(chat)

    async def save_assistant_image_message(
        self,
        user_id: str,
        role_id: int,
        image_url: str,
        *,
        content: str = "",
        meta_json: Optional[dict] = None,
        decision_data: Optional[dict] = None,
    ) -> ChatMessage:
        chat = await self.chat_repo.save_message(
            user_id=user_id,
            role_id=role_id,
            message_type=MessageType.ASSISTANT_IMAGE,
            content=content,
            image_url=image_url,
            decision_data=decision_data,
            meta_json=meta_json,
        )
        await self.session.commit()
        return ChatMessage.from_orm(chat)

    async def save_assistant_messages(
        self,
        user_id: str,
        role_id: int,
        content: str,
        decision_data: Optional[dict] = None,
    ) -> List[ChatMessage]:
        """按展示分段保存 AI 回复消息。"""
        split_level = 2
        if isinstance(decision_data, dict):
            split_level = max(1, int(decision_data.get("split_level") or 2))

        segments = dispatch_layer.split_message(content, split_level)
        saved_messages: List[ChatMessage] = []
        total = len(segments)

        for index, segment in enumerate(segments, start=1):
            segment_decision = copy.deepcopy(decision_data) if isinstance(decision_data, dict) else {}
            segment_decision["raw_response"] = content
            segment_decision["segment_index"] = index
            segment_decision["segment_total"] = total

            chat = await self.chat_repo.save_message(
                user_id=user_id,
                role_id=role_id,
                message_type=MessageType.ASSISTANT,
                content=segment,
                decision_data=segment_decision,
            )
            saved_messages.append(ChatMessage.from_orm(chat))

        await self.session.commit()
        return saved_messages

    async def get_conversation_history(
        self, user_id: str, role_id: int, limit: int = 20
    ) -> List[ChatMessage]:
        """获取聊天历史"""
        messages = await self.chat_repo.get_conversation_history(
            user_id=user_id, role_id=role_id, limit=limit
        )
        return self._expand_assistant_segments([ChatMessage.from_orm(msg) for msg in messages])

    async def get_latest_messages(
        self, user_id: str, role_id: int, limit: int = 10
    ) -> List[ChatMessage]:
        """获取最新消息"""
        messages = await self.chat_repo.get_latest_messages(
            user_id=user_id, role_id=role_id, limit=limit
        )
        return [ChatMessage.from_orm(msg) for msg in messages]

    async def count_messages(self, user_id: str, role_id: int) -> int:
        """统计消息数"""
        return await self.chat_repo.count_messages(user_id, role_id)

    @staticmethod
    def is_opening_image_message(message: ChatMessage) -> bool:
        message_type = (
            message.message_type.value
            if hasattr(message.message_type, "value")
            else str(message.message_type)
        )
        if message_type != MessageType.ASSISTANT_IMAGE.value:
            return False

        meta_json = dict(getattr(message, "meta_json", None) or {})
        source = str(meta_json.get("source") or "").strip()
        image_type = str(meta_json.get("image_type") or "").strip()
        stage_key = str(meta_json.get("stage_key") or "").strip()

        return source == "role_opening" or image_type == "opening" or stage_key == "intro"

    def ensure_opening_image_first(
        self,
        messages: List[ChatMessage],
        opening_image: Optional[ChatMessage] = None,
    ) -> List[ChatMessage]:
        ordered = list(messages or [])
        if not ordered and opening_image is None:
            return ordered

        first_role_index = next(
            (
                index
                for index, message in enumerate(ordered)
                if (
                    message.message_type.value
                    if hasattr(message.message_type, "value")
                    else str(message.message_type)
                ) in {
                    MessageType.ASSISTANT.value,
                    MessageType.ASSISTANT_IMAGE.value,
                }
            ),
            len(ordered),
        )

        opening_indexes = [
            index for index, message in enumerate(ordered)
            if self.is_opening_image_message(message)
        ]

        if not opening_indexes:
            if opening_image is None:
                return ordered
            ordered.insert(first_role_index, opening_image)
            return ordered

        primary_index = opening_indexes[0]
        primary_message = ordered.pop(primary_index)
        if primary_index < first_role_index:
            first_role_index -= 1
        ordered.insert(first_role_index, primary_message)

        for index in reversed(opening_indexes[1:]):
            if index == primary_index:
                continue
            adjusted_index = index - 1 if index > primary_index else index
            ordered.pop(adjusted_index)

        return ordered

    def _expand_assistant_segments(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        expanded: List[ChatMessage] = []
        synthetic_id = -1

        for message in messages:
            message_type = (
                message.message_type.value
                if hasattr(message.message_type, "value")
                else str(message.message_type)
            )
            if message_type != MessageType.ASSISTANT.value:
                expanded.append(message)
                continue

            if isinstance(message.decision_data, dict) and message.decision_data.get("segment_index"):
                expanded.append(message)
                continue

            if not isinstance(message.decision_data, dict) or not message.decision_data.get("split_level"):
                expanded.append(message)
                continue

            split_level = max(1, int(message.decision_data.get("split_level") or 2))

            segments = dispatch_layer.split_message(message.content, split_level)
            if len(segments) <= 1:
                expanded.append(message)
                continue

            for segment in segments:
                expanded.append(
                    ChatMessage(
                        id=synthetic_id,
                        user_id=message.user_id,
                        role_id=message.role_id,
                        message_type=message_type,
                        content=segment,
                        emotion_data=message.emotion_data,
                        decision_data=message.decision_data,
                        created_at=message.created_at,
                    )
                )
                synthetic_id -= 1

        return expanded
