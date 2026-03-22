from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import UserRoleRelationshipEvent
from app.database.repositories.base import BaseRepository


class UserRoleRelationshipEventRepository(BaseRepository[UserRoleRelationshipEvent]):
    """用户-角色关系事件日志数据访问层。"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, UserRoleRelationshipEvent)
