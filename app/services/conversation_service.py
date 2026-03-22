import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.decision import decision_engine
from app.generation import generation_layer
from app.prompt_agent import prompt_agent
from app.rag import rag_service
from app.relationship.service import RelationshipService
from app.services.chat_service import ChatService
from app.services.role_service import RoleService
from app.state_machine import state_machine
from app.understanding import understanding_layer

logger = logging.getLogger(__name__)


class ConversationService:
    """统一封装一轮对话的业务编排，供 Bot 和 WebApp API 复用。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.role_service = RoleService(session)
        self.chat_service = ChatService(session)
        self.relationship_service = RelationshipService(session)

    async def chat(
        self,
        *,
        user_id: str,
        user_text: str,
        user_name: Optional[str] = None,
        role_id: Optional[int] = None,
    ) -> dict:
        current_role = await self._resolve_role(user_id, role_id)
        if not current_role:
            raise ValueError("请先选择一个角色。")

        emotion = await understanding_layer.analyze(user_text)
        user_message = await self.chat_service.save_user_message(
            user_id=user_id,
            role_id=current_role.id,
            content=user_text,
            emotion_data=emotion.model_dump(),
        )
        conversation_history = await self.chat_service.get_latest_messages(
            user_id=user_id,
            role_id=current_role.id,
            limit=30,
        )
        relationship_context = await self.relationship_service.resolve_generation_context(
            role=current_role,
            user_id=user_id,
            user_text=user_text,
            emotion=emotion,
            recent_messages=conversation_history,
            trigger_message_id=user_message.id,
        )
        current_role.system_prompt = relationship_context.prompt_text
        await self._index_message_for_rag(user_message)
        await self._ensure_role_knowledge(current_role)
        rag_context = await rag_service.retrieve_context(
            role=current_role,
            user_id=user_id,
            query=user_text,
        )

        state = await state_machine.get_state(user_id, current_role.id, user_name)
        state.relationship_level = relationship_context.relationship
        decision = decision_engine.decide(state, emotion)
        system_prompt, user_prompt = prompt_agent.build_prompt(
            current_role,
            state,
            emotion,
            decision,
            conversation_history,
            rag_context,
        )

        try:
            response_text = await generation_layer.generate(system_prompt, user_prompt)
        except Exception as exc:
            if not self._should_use_local_fallback(exc):
                raise
            response_text = self._build_local_fallback_response(
                role_name=current_role.role_name,
                user_text=user_text,
            )

        assistant_messages = await self.chat_service.save_assistant_messages(
            user_id=user_id,
            role_id=current_role.id,
            content=response_text,
            decision_data=decision.model_dump(),
        )
        for assistant_message in assistant_messages:
            await self._index_message_for_rag(assistant_message)
        await state_machine.update_after_interaction(state, decision.mood_delta)
        logger.info(
            "RAG final response: role=%s user=%s relationship=%s rv=%s delta=%s pending=%s response=%r",
            current_role.role_name,
            user_id,
            relationship_context.relationship,
            relationship_context.current_rv,
            relationship_context.last_delta,
            relationship_context.pending_delta,
            response_text,
        )

        assistant_message = assistant_messages[-1]

        return {
            "role": current_role,
            "relationship": relationship_context.relationship,
            "relationship_label": relationship_context.relationship_label,
            "emotion": emotion,
            "decision": decision,
            "assistant_message": assistant_message,
            "assistant_messages": assistant_messages,
            "response_text": response_text,
        }

    async def _resolve_role(self, user_id: str, role_id: Optional[int]):
        if role_id is not None:
            role = await self.role_service.get_role(role_id)
            if role and role.is_active:
                return role
            return None
        return await self.role_service.get_user_current_role(user_id)

    def _should_use_local_fallback(self, exc: Exception) -> bool:
        exc_text = str(exc)
        return (
            "Blocked due to abusive traffic patterns" in exc_text
            or "403 Forbidden" in exc_text
            or "StatusCode.PERMISSION_DENIED" in exc_text
            or "http2 header with status: 403" in exc_text
        )

    def _build_local_fallback_response(self, *, role_name: str, user_text: str) -> str:
        condensed_text = " ".join((user_text or "").split())[:80]
        if condensed_text:
            return (
                f"我是{role_name}，刚刚云端回复通道临时拥堵了，但我先接住你这句话："
                f"“{condensed_text}”。你再继续发我一句，我马上接着和你聊。"
            )
        return (
            f"我是{role_name}，刚刚云端回复通道临时拥堵了。"
            "你再发我一句，我马上接着和你聊。"
        )

    async def _index_message_for_rag(self, message) -> None:
        try:
            await rag_service.index_chat_memory(message)
        except Exception as exc:
            logger.warning("Weaviate memory index failed: %s", exc, exc_info=True)

    async def _ensure_role_knowledge(self, role) -> None:
        try:
            await rag_service.index_role_knowledge(role)
        except Exception as exc:
            logger.warning("Weaviate role knowledge ensure failed: %s", exc, exc_info=True)
