import json
from datetime import datetime
from typing import Optional
import redis.asyncio as redis
from app.models import UserState
from app.config import get_settings
from app.relationship_prompts import DEFAULT_RELATIONSHIP

class StateMachine:
    """状态机：负责用户状态的读取、初始化、更新"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        settings = get_settings()
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
    
    async def close(self):
        if self.redis:
            await self.redis.close()
    
    def _key(self, user_id: str, role_id: int) -> str:
        return f"user_state:{user_id}:{role_id}"

    async def get_state(self, user_id: str, role_id: int, user_name: str = None) -> UserState:
        """读取用户状态，不存在则初始化"""
        data = await self.redis.get(self._key(user_id, role_id))
        if data:
            return UserState(**json.loads(data))
        # 新用户初始化
        state = UserState(
            user_id=user_id,
            role_id=role_id,
            user_name=user_name,
            relationship_level=DEFAULT_RELATIONSHIP,
            character_mood=0.1,
            interaction_count=0
        )
        await self.save_state(state)
        return state
    
    async def save_state(self, state: UserState):
        """保存用户状态"""
        state.updated_at = datetime.now()
        await self.redis.set(
            self._key(state.user_id, state.role_id),
            state.model_dump_json(),
            ex=86400 * 30  # 30天过期
        )
    
    async def update_after_interaction(self, state: UserState, mood_delta: float) -> UserState:
        """交互后更新状态"""
        # 情绪衰减更新: new_mood = old_mood * 0.7 + mood_delta * 0.3
        state.character_mood = min(1.0, max(0.0, state.character_mood * 0.7 + mood_delta * 0.3))
        state.interaction_count += 1
        state.last_interaction = datetime.now()

        # 暂停自动关系升级，relationship_level 维持当前值。
        await self.save_state(state)
        return state

    async def clear_state(self, user_id: str, role_id: int) -> None:
        if not self.redis:
            return
        await self.redis.delete(self._key(user_id, role_id))

state_machine = StateMachine()
