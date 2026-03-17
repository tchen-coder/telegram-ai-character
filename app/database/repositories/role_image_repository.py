from typing import List, Optional

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import RoleImage
from app.database.repositories.base import BaseRepository


class RoleImageRepository(BaseRepository[RoleImage]):
    """角色图片资源数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, RoleImage)

    async def get_by_id(self, image_id: int) -> Optional[RoleImage]:
        return await self.session.get(RoleImage, image_id)

    async def list_by_role(self, role_id: int) -> List[RoleImage]:
        result = await self.session.execute(
            select(RoleImage)
            .where(RoleImage.role_id == role_id)
            .order_by(
                asc(RoleImage.sort_order),
                asc(RoleImage.id),
            )
        )
        return result.scalars().all()

    async def list_active_by_role(
        self,
        role_id: int,
        *,
        image_type: Optional[str] = None,
        stage_key: Optional[str] = None,
    ) -> List[RoleImage]:
        stmt = select(RoleImage).where(
            RoleImage.role_id == role_id,
            RoleImage.is_active == True,
        )
        if image_type:
            stmt = stmt.where(RoleImage.image_type == image_type)
        if stage_key:
            stmt = stmt.where(RoleImage.stage_key == stage_key)
        result = await self.session.execute(
            stmt.order_by(
                asc(RoleImage.sort_order),
                asc(RoleImage.id),
            )
        )
        return result.scalars().all()
