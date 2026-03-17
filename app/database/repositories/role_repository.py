from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import Role
from app.database.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """角色数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Role)

    async def get_by_name(self, role_name: str) -> Optional[Role]:
        """根据角色名称获取角色"""
        result = await self.session.execute(
            select(Role).where(Role.role_name == role_name)
        )
        return result.scalars().first()

    async def get_active_roles(self) -> List[Role]:
        """获取所有激活的角色"""
        result = await self.session.execute(
            select(Role).where(Role.is_active == True).order_by(Role.id)
        )
        return result.scalars().all()

    async def get_all_roles(self) -> List[Role]:
        result = await self.session.execute(
            select(Role).order_by(Role.id)
        )
        return result.scalars().all()

    async def get_by_id(self, role_id: int) -> Optional[Role]:
        """根据 ID 获取角色"""
        return await self.session.get(Role, role_id)
