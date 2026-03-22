from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import RoleRelationshipConfig
from app.database.repositories.base import BaseRepository


class RoleRelationshipConfigRepository(BaseRepository[RoleRelationshipConfig]):
    """角色关系配置数据访问层。"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, RoleRelationshipConfig)

    async def get_by_role_id(self, role_id: int) -> Optional[RoleRelationshipConfig]:
        result = await self.session.execute(
            select(RoleRelationshipConfig).where(RoleRelationshipConfig.role_id == role_id)
        )
        return result.scalars().first()
