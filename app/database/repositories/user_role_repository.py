from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

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

    async def set_current_role(self, user_id: str, role_id: int) -> UserRole:
        """设置用户的当前角色"""
        # 先将用户的所有角色设为非当前
        await self.session.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        result = await self.session.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        for user_role in result.scalars().all():
            user_role.is_current = False

        # 获取或创建新的当前角色
        user_role = await self.get_user_role(user_id, role_id)
        if not user_role:
            user_role = UserRole(
                user_id=user_id,
                role_id=role_id,
                relationship=DEFAULT_RELATIONSHIP,
                is_current=True,
                first_interaction_at=datetime.utcnow(),
            )
            self.session.add(user_role)
        else:
            user_role.is_current = True

        user_role.last_interaction_at = datetime.utcnow()
        await self.session.flush()
        return user_role

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
