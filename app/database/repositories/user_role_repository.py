from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, and_

from app.database.models import UserRole
from app.database.repositories.base import BaseRepository
from app.relationship_prompts import DEFAULT_RELATIONSHIP


class UserRoleRepository(BaseRepository[UserRole]):
    """用户-角色关系数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, UserRole)

    async def get_user_current_role(self, user_id: str) -> Optional[UserRole]:
        """获取用户当前选择的角色"""
        result = await self.session.execute(
            select(UserRole).where(
                and_(UserRole.user_id == user_id, UserRole.is_current == True)
            )
        )
        return result.scalars().first()

    async def get_user_roles(self, user_id: str) -> List[UserRole]:
        """获取用户的所有角色"""
        result = await self.session.execute(
            select(UserRole).where(UserRole.user_id == user_id).order_by(UserRole.created_at)
        )
        return result.scalars().all()

    async def get_user_role(self, user_id: str, role_id: int) -> Optional[UserRole]:
        """获取用户的特定角色关系"""
        result = await self.session.execute(
            select(UserRole).where(
                and_(UserRole.user_id == user_id, UserRole.role_id == role_id)
            )
        )
        return result.scalars().first()

    async def ensure_user_role(
        self,
        user_id: str,
        role_id: int,
        *,
        is_current: Optional[bool] = None,
    ) -> UserRole:
        """确保用户-角色关系存在，relationship 仅作为兼容镜像保留。"""
        user_role = await self.get_user_role(user_id, role_id)
        now = datetime.utcnow()
        if not user_role:
            user_role = UserRole(
                user_id=user_id,
                role_id=role_id,
                relationship=DEFAULT_RELATIONSHIP,
                is_current=bool(is_current) if is_current is not None else False,
                first_interaction_at=now,
                last_interaction_at=now,
            )
            self.session.add(user_role)
            await self.session.flush()
            return user_role

        if is_current is not None:
            user_role.is_current = bool(is_current)
        if not user_role.first_interaction_at:
            user_role.first_interaction_at = now
        user_role.last_interaction_at = now
        await self.session.flush()
        return user_role

    async def set_current_role(self, user_id: str, role_id: int) -> UserRole:
        """设置用户的当前角色"""
        # 先将用户的所有角色设为非当前
        result = await self.session.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        for user_role in result.scalars().all():
            user_role.is_current = False

        return await self.ensure_user_role(user_id, role_id, is_current=True)

    async def update_relationship(
        self,
        user_id: str,
        role_id: int,
        relationship: int,
    ) -> Optional[UserRole]:
        user_role = await self.get_user_role(user_id, role_id)
        if not user_role:
            return None

        user_role.relationship = relationship
        user_role.last_interaction_at = datetime.utcnow()
        await self.session.flush()
        return user_role

    async def delete_user_role(self, user_id: str, role_id: int) -> None:
        await self.session.execute(
            delete(UserRole).where(
                and_(UserRole.user_id == user_id, UserRole.role_id == role_id)
            )
        )
        await self.session.flush()
