from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import UserRoleRelationshipState
from app.database.repositories.base import BaseRepository


class UserRoleRelationshipStateRepository(BaseRepository[UserRoleRelationshipState]):
    """用户-角色关系状态数据访问层。"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, UserRoleRelationshipState)

    async def get_by_user_and_role(
        self,
        user_id: str,
        role_id: int,
    ) -> Optional[UserRoleRelationshipState]:
        result = await self.session.execute(
            select(UserRoleRelationshipState).where(
                UserRoleRelationshipState.user_id == user_id,
                UserRoleRelationshipState.role_id == role_id,
            )
        )
        return result.scalars().first()
