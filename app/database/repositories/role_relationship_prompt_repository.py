from typing import List, Optional

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import RoleRelationshipPrompt
from app.database.repositories.base import BaseRepository


class RoleRelationshipPromptRepository(BaseRepository[RoleRelationshipPrompt]):
    """角色关系提示词数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, RoleRelationshipPrompt)

    async def get_by_id(self, prompt_id: int) -> Optional[RoleRelationshipPrompt]:
        return await self.session.get(RoleRelationshipPrompt, prompt_id)

    async def list_by_role(self, role_id: int) -> List[RoleRelationshipPrompt]:
        result = await self.session.execute(
            select(RoleRelationshipPrompt)
            .where(RoleRelationshipPrompt.role_id == role_id)
            .order_by(
                asc(RoleRelationshipPrompt.relationship),
                asc(RoleRelationshipPrompt.id),
            )
        )
        return result.scalars().all()

    async def get_by_role_and_relationship(
        self,
        role_id: int,
        relationship: int,
    ) -> Optional[RoleRelationshipPrompt]:
        result = await self.session.execute(
            select(RoleRelationshipPrompt).where(
                RoleRelationshipPrompt.role_id == role_id,
                RoleRelationshipPrompt.relationship == relationship,
            )
        )
        return result.scalars().first()
